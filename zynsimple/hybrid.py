# -*- coding: utf-8 -*-
"""
ZynSimple – Hybrid-Modus „DJ + Instrumente“: Mixxx läuft neben der Zynthian-Oberfläche.

  - Mixxx spielt über JACK (nur der Haupt-Mix) in den Kanal „DJ-Pult“ des Zynthian-Mischers:
    Fader, Mute, Zynthian-Effekte, Freeze, Szenen und der Limiter am Hauptausgang wirken auch auf die Musik.
  - Instrumente (Handpan, Mikro, Synths, Looper) laufen wie immer als eigene Spuren daneben.
  - Der DDJ-200 steuert nur Mixxx (wird aus den Zynthian-Spuren herausgenommen, damit keine Synths mitspielen).
  - Tempo: Mixxx führt → Zynthian-Tempo (Sequenzer, Delays, Looper) folgt; bei „Takt: folgen“ gibt die TR-8S
    den Takt vor, der Zynthian folgt ihr und Mixxx folgt dem Zynthian.
  - Bildschirm: Mixxx und ZynSimple wechseln sich ab (⋯ → Mixxx zeigen · jede Zynthian-Taste → zurück).
    Gesucht und geladen wird am bequemsten am Handy (…:8090/bibliothek).

Ohne Kopfhörer-Vorhören (das macht der externe Mischer bzw. der DDJ-200 im reinen DJ-Modus).
"""
import glob
import logging
import os
import re
import select
import shutil
import signal
import subprocess
import threading
import time

log = logging.getLogger("zynsimple")

DATEN = "/zynthian/zynthian-my-data/dj"
DJ_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dj")
KANAL = "DJ-Pult"
LOG = "/tmp/zynsimple-hybrid-mixxx.log"
RX_NUR_MIXXX = re.compile(r"DDJ|VirMIDI|Virtual Raw", re.I)
RX_MIXXX_OUT = r"^(Mixxx|mixxx|PortAudio)[^:]*:out"


def mixxx_bin():
    if os.path.exists("/opt/mixxx-2.6/bin/mixxx") and not os.path.exists(os.path.join(DATEN, ".mixxx26-aus")):
        return "/opt/mixxx-2.6/bin/mixxx"
    return shutil.which("mixxx")


class Hybrid:
    def __init__(self, bridge, settings):
        self.b = bridge
        self.settings = settings
        self.proc = None
        self.cid = None
        self.vfd = None
        self.vorne = False
        self.fehler = None
        self.phase = None             # None | "start" | "laeuft" | "stopp"
        self.mixxx_bpm = 0.0
        self.mixxx_spielt = False
        self.gesendet = 0.0
        self.getrennt = set()          # MIDI-Eingänge, die gerade nur Mixxx gehören
        self._jack = None
        self._lock = threading.Lock()
        self._fenster = None

    # ------------------------------------------------------------------
    def laeuft(self):
        return self.proc is not None and self.proc.poll() is None

    def status(self):
        return {"an": self.laeuft(), "phase": self.phase, "vorne": self.vorne, "fehler": self.fehler,
                "kanal": self.cid, "tempo": round(self.mixxx_bpm, 1) if self.mixxx_spielt else None,
                "moeglich": bool(mixxx_bin())}

    # ------------------------------------------------------------------
    # Start / Stopp
    # ------------------------------------------------------------------
    def starten(self):
        with self._lock:
            if self.laeuft() or self.phase == "start":
                return "läuft schon"
            m = mixxx_bin()
            if not m:
                raise RuntimeError("Mixxx fehlt – einmal das DJ-Pult starten, dann wird es installiert")
            self.phase = "start"
            self.fehler = None
        threading.Thread(target=self._starten, args=(m,), daemon=True).start()
        return "DJ + Instrumente startet …"

    def _env(self, m):
        env = dict(os.environ)
        env["HOME"] = DATEN
        env["ZS_MIXXX"] = m
        env["ZS_HYBRID"] = "1"
        env.setdefault("DISPLAY", ":0")
        if env.get("WAYLAND_DISPLAY"):
            env["QT_QPA_PLATFORM"] = "xcb"        # Fenster per xdotool umschaltbar (über XWayland)
        return env

    def _starten(self, m):
        try:
            with open("/proc/asound/cards", encoding="utf-8") as f:
                virmidi_da = "VirMIDI" in f.read()
            if not virmidi_da:
                subprocess.call(["modprobe", "snd-virmidi", "midi_devs=1"], stderr=subprocess.DEVNULL)
                time.sleep(1)
            env = self._env(m)
            subprocess.call(["/usr/bin/python3", os.path.join(DJ_DIR, "dj-einrichten.py")], env=env,
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT, timeout=120)
            self.cid = self._kanal()
            self.proc = subprocess.Popen([m], env=env, cwd=DATEN, stdout=open(LOG, "a"), stderr=subprocess.STDOUT,
                                         start_new_session=True)
            self.vorne = True
            self.phase = "laeuft"
            log.info(f"ZynSimple: Hybrid läuft (Mixxx {m}, Kanal {self.cid})")
            self._virmidi_oeffnen()
            threading.Thread(target=self._waechter, daemon=True).start()
            threading.Thread(target=self._mixxx_lesen, daemon=True).start()
        except Exception as e:
            self.fehler = str(e)
            self.phase = None
            log.exception(f"ZynSimple: Hybrid-Start fehlgeschlagen: {e}")

    def stoppen(self):
        if not self.laeuft():
            self.phase = None
            return "läuft nicht"
        self.phase = "stopp"
        threading.Thread(target=self._stoppen, daemon=True).start()
        return "Mixxx wird beendet …"

    def _stoppen(self):
        p = self.proc
        try:
            p.send_signal(signal.SIGTERM)          # Mixxx speichert Bibliothek und Einstellungen
            p.wait(20)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        # aufgeräumt wird im Wächter, sobald Mixxx weg ist

    def _aufraeumen(self):
        if self.proc is None and self.phase is None:
            return
        self.proc = None
        self.phase = None
        self.vorne = False
        self._midi_zurueck()
        if self.vfd is not None:
            try:
                os.close(self.vfd)
            except OSError:
                pass
            self.vfd = None
        self._zynsimple_vorne()
        log.info("ZynSimple: Hybrid beendet")

    # ------------------------------------------------------------------
    # Kanal im Zynthian-Mischer
    # ------------------------------------------------------------------
    def kanal_pruefen(self):
        """Der Kanal „DJ-Pult“ darf nie Soundkarten-Eingänge haben (sonst käme z. B. die Handpan doppelt).
        Nach einem Neustart setzt der Zynthian leere Eingangslisten manchmal wieder auf 1+2."""
        try:
            for cid, ch in list(self.b.cm.chains.items()):
                if cid != 0 and (getattr(ch, "title", "") or "") == KANAL and \
                        any(isinstance(i, int) for i in (getattr(ch, "audio_in", None) or [])):
                    self.b.tracks.set_inputs(cid, [])
                    log.info("ZynSimple: Kanal „DJ-Pult“ ohne Soundkarten-Eingänge")
        except Exception as e:
            log.debug(f"ZynSimple: DJ-Kanal prüfen: {e}")

    def _kanal(self):
        cm = self.b.cm
        for cid, ch in list(cm.chains.items()):
            if cid != 0 and (getattr(ch, "title", "") or "") == KANAL:
                self.kanal_pruefen()
                return cid
        cid = self.b.tracks.add("audio", title=KANAL)
        try:
            self.b.tracks.set_inputs(cid, [])     # keine Soundkarten-Eingänge – nur Mixxx
        except Exception as e:
            log.warning(f"ZynSimple: Hybrid-Kanal ohne Eingänge: {e}")
        return cid

    def _ziel_ports(self, jc):
        chain = self.b.cm.chains.get(self.cid)
        if chain is None:
            return []
        namen = []
        try:
            for proc in (chain.audio_slots[0] if chain.audio_slots else []):
                jn = proc.get_jackname()
                if jn.startswith("zynmixer"):
                    jn += f":input_{proc.mixer_chan:02d}"
                namen.append(jn)
        except Exception:
            pass
        try:
            namen.append(f"zynmixer_chan:input_{chain.mixer_chan:02d}")
        except Exception:
            pass
        for n in namen:
            ports = [p for p in jc.get_ports(n, is_input=True, is_audio=True)
                     if not re.search(r"side|sc_|_sc\b", p.name, re.I)]
            if ports:
                return ports[:2]
        return []

    def _jack_verbinden(self):
        try:
            if self._jack is None:
                import jack
                self._jack = jack.Client("zynsimple_hybrid", no_start_server=True)
            jc = self._jack
            quellen = jc.get_ports(RX_MIXXX_OUT, is_output=True, is_audio=True)[:2]
            ziele = self._ziel_ports(jc)
            if not quellen or not ziele:
                return False
            soll = {(q.name, ziele[min(i, len(ziele) - 1)].name) for i, q in enumerate(quellen)}
            for q in quellen:
                for z in jc.get_all_connections(q):
                    if (q.name, z.name) not in soll:
                        jc.disconnect(q.name, z.name)      # PortAudio verbindet sonst direkt mit der Soundkarte
            for q, z in soll:
                if z not in [x.name for x in jc.get_all_connections(q)]:
                    jc.connect(q, z)
            return True
        except Exception as e:
            log.debug(f"ZynSimple: Hybrid JACK: {e}")
            self._jack = None
            return False

    # ------------------------------------------------------------------
    # DDJ-200 nur für Mixxx
    # ------------------------------------------------------------------
    def _zyncore(self):
        try:
            from zyncoder.zyncore import lib_zyncore
            return lib_zyncore
        except Exception:
            return None

    def _midi_trennen(self):
        lib = self._zyncore()
        if lib is None:
            return
        try:
            import zynautoconnect as za
            for idev, port in enumerate(list(za.devices_in)):
                if port is None:
                    continue
                if RX_NUR_MIXXX.search(" ".join([port.name] + [str(a) for a in port.aliases or []])):
                    lib.zmip_set_flag_active_chain(idev, 0)
                    for zmop in range(16):
                        lib.zmop_set_route_from(zmop, idev, 0)
                    if idev not in self.getrennt:
                        self.getrennt.add(idev)
                        try:
                            za.set_zynseq_input_zmop(idev, False)
                        except Exception:
                            pass
                        log.info(f"ZynSimple: Hybrid – {port.aliases[1] if len(port.aliases) > 1 else port.name} nur für Mixxx")
        except Exception as e:
            log.debug(f"ZynSimple: Hybrid MIDI: {e}")

    def _midi_zurueck(self):
        lib = self._zyncore()
        if lib is None or not self.getrennt:
            return
        try:
            import zynautoconnect as za
            zmops = [c.zmop_index for c in self.b.cm.chains.values() if getattr(c, "zmop_index", None) is not None]
            for idev in self.getrennt:
                lib.zmip_set_flag_active_chain(idev, 1)
                for zmop in zmops:
                    if 0 <= zmop < 16:
                        lib.zmop_set_route_from(zmop, idev, 1)
                try:
                    za.set_zynseq_input_zmop(idev, True)
                    za.update_midi_in_dev_mode(idev)
                except Exception:
                    pass
        except Exception as e:
            log.debug(f"ZynSimple: Hybrid MIDI zurück: {e}")
        self.getrennt = set()

    # ------------------------------------------------------------------
    # Tempo-Brücke über den virtuellen MIDI-Anschluss (Mixxx-Mapping „Zynthian V5 (ZynSimple)“)
    # ------------------------------------------------------------------
    def _virmidi_oeffnen(self):
        try:
            with open("/proc/asound/cards", encoding="utf-8") as f:
                m = re.search(r"^\s*(\d+)\s+\[\S+\s*\]:.*(VirMIDI|Virtual)", f.read(), re.M)
            if m:
                p = sorted(glob.glob(f"/dev/snd/midiC{m.group(1)}D*"))
                if p:
                    self.vfd = os.open(p[0], os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            log.warning(f"ZynSimple: Hybrid – virtueller MIDI-Anschluss nicht offen ({e})")

    def senden(self, cc, wert):
        if self.vfd is None:
            raise RuntimeError("Keine Verbindung zu Mixxx (virtueller MIDI-Anschluss fehlt)")
        os.write(self.vfd, bytes([0xB0, int(cc) & 0x7F, int(wert) & 0x7F]))

    def _mixxx_lesen(self):
        puffer, sysex, msb = [], False, 0
        while self.laeuft():
            if self.vfd is None:
                time.sleep(1)
                continue
            try:
                r, _, _ = select.select([self.vfd], [], [], 1.0)
                if not r:
                    continue
                daten = os.read(self.vfd, 256)
            except (OSError, ValueError):
                time.sleep(0.5)
                continue
            for b in daten:
                if b >= 0xF8:
                    continue
                if b == 0xF0:
                    sysex = True
                    continue
                if sysex:
                    if b == 0xF7 or b & 0x80:
                        sysex = False
                    continue
                if b & 0x80:
                    puffer = [b]
                else:
                    puffer.append(b)
                if len(puffer) == 3:
                    st, d1, d2 = puffer
                    puffer = [st]
                    if st & 0xF0 == 0xB0:
                        if d1 == 100:
                            msb = d2
                        elif d1 == 101:
                            self.mixxx_bpm = ((msb << 7) | d2) / 10.0
                        elif d1 == 103:
                            self.mixxx_spielt = d2 > 0

    def _tempo(self):
        from . import takt
        try:
            zs = self.b.sm.zynseq
        except Exception:
            return
        if takt.wert(self.settings) == "folgen":
            # TR-8S → Zynthian → Mixxx
            try:
                bpm = float(zs.get_tempo())
            except Exception:
                return
            if 30 <= bpm <= 300 and abs(bpm - self.gesendet) >= 0.05 and self.vfd is not None:
                w = int(round(bpm * 10))
                try:
                    self.senden(110, (w >> 7) & 0x7F)
                    self.senden(111, w & 0x7F)
                    self.gesendet = bpm
                except OSError:
                    pass
        elif self.mixxx_spielt and 30 <= self.mixxx_bpm <= 300:
            # Mixxx → Zynthian (Sequenzer, Delays im Takt, Looper, Clock an die TR-8S)
            try:
                if abs(float(zs.get_tempo()) - self.mixxx_bpm) >= 0.05:
                    zs.set_tempo(self.mixxx_bpm)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _waechter(self):
        n = 0
        verbunden = False
        while self.laeuft():
            n += 1
            ok = self._jack_verbinden()
            if ok and not verbunden:
                verbunden = True
                log.info("ZynSimple: Hybrid – Mixxx spielt in den Kanal „DJ-Pult“")
            if n % 2 == 1:
                self._midi_trennen()
            self._tempo()
            time.sleep(0.5 if n < 60 else 1.0)
        if self.phase == "laeuft":
            self.fehler = "Mixxx wurde beendet"
        self._aufraeumen()

    # ------------------------------------------------------------------
    # Bildschirm: Mixxx oder ZynSimple vorne
    # ------------------------------------------------------------------
    def _xdo(self, *args):
        if not shutil.which("xdotool"):
            return ""
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        try:
            return subprocess.run(["xdotool"] + list(args), env=env, capture_output=True, text=True, timeout=5).stdout
        except Exception:
            return ""

    def _mixxx_fenster(self):
        ids = self._xdo("search", "--onlyvisible", "--class", "mixxx").split() or \
            self._xdo("search", "--class", "mixxx").split()
        return ids[-1] if ids else None

    def zeigen(self):
        if not self.laeuft():
            raise RuntimeError("DJ + Instrumente läuft nicht")
        w = self._mixxx_fenster()
        if not w:
            raise RuntimeError("Mixxx-Fenster nicht gefunden (startet noch?)")
        self._xdo("windowmap", w)
        self._xdo("windowraise", w)
        self._xdo("windowfocus", w)
        self.vorne = True
        return "Mixxx vorne · beliebige Zynthian-Taste = zurück zum Mischer"

    def verstecken(self):
        w = self._mixxx_fenster()
        if w:
            self._xdo("windowunmap", w)
        self.vorne = False
        self._zynsimple_vorne()

    def _zynsimple_vorne(self):
        try:
            from zyngui import zynthian_gui_config as cfg
            top = cfg.top

            def hoch():
                try:
                    top.lift()
                    top.attributes("-topmost", True)
                    top.after(300, lambda: top.attributes("-topmost", False))
                    top.focus_force()
                except Exception:
                    pass
            top.after(0, hoch)
        except Exception:
            pass
