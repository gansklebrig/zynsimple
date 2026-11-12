# -*- coding: utf-8 -*-
"""
ZynSimple – Hybrid-Modus „DJ + Instrumente“: Mixxx läuft neben der Zynthian-Oberfläche.

  - Mixxx spielt über JACK (nur der Haupt-Mix) in den Kanal „DJ-Pult“ des Zynthian-Mischers:
    Fader, Mute, Zynthian-Effekte, Freeze, Szenen und der Limiter am Hauptausgang wirken auch auf die Musik.
  - Instrumente (Handpan, Mikro, Synths, Looper) laufen wie immer als eigene Spuren daneben.
  - Der DDJ-200 steuert nur Mixxx (wird aus den Zynthian-Spuren herausgenommen, damit keine Synths mitspielen).
  - Tempo: Mixxx führt → Zynthian-Tempo (Sequenzer, Delays, Looper) folgt; bei „Takt: folgen“ gibt die TR-8S
    den Takt vor, der Zynthian folgt ihr und Mixxx folgt dem Zynthian.
  - Bildschirm: Mixxx und ZynSimple wechseln sich ab (⋯ → Mixxx zeigen · MENU → zurück).
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


def portaudio_jack():
    """Kann Mixxx (über PortAudio) überhaupt mit JACK spielen? True/False, None = unklar."""
    try:
        out = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True, timeout=5).stdout
        libs = re.findall(r"libportaudio\.so[.\d]*\s.*=>\s*(\S+)", out)
        for lib in libs:
            d = subprocess.run(["ldd", lib], capture_output=True, text=True, timeout=5).stdout
            if "libjack" in d:
                return True
        return False if libs else None
    except Exception:
        return None


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
        self.vfd_ddj = None
        self.vm_ddj = None
        self.ddj_fehler = None
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
        self._deck = {1: {}, 2: {}}
        self._deck_msb = {}
        self._deck_name = {}
        self._geladen = {}

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
            if portaudio_jack() is False:
                raise RuntimeError("Mixxx kann auf diesem System nicht über JACK spielen (PortAudio ohne JACK) – "
                                   "DJ + Instrumente geht hier nicht, das reine DJ-Pult schon")
            with open("/proc/asound/cards", encoding="utf-8") as f:
                virmidi_da = "VirMIDI" in f.read()
            if not virmidi_da:
                subprocess.call(["modprobe", "snd-virmidi", "midi_devs=4"], stderr=subprocess.DEVNULL)
                time.sleep(1)
            env = self._env(m)
            if self.vfd is None:
                self._virmidi_oeffnen()
            self.ddj_fehler = None
            if self.vfd_ddj is None:
                self._virmidi_ddj_oeffnen()
            if self.vm_ddj:
                env["ZS_VIRMIDI_DDJ"] = self.vm_ddj
            subprocess.call(["/usr/bin/python3", os.path.join(DJ_DIR, "dj-einrichten.py")], env=env,
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT, timeout=120)
            self.cid = self._kanal()
            self.proc = subprocess.Popen([m], env=env, cwd=DATEN, stdout=open(LOG, "a"), stderr=subprocess.STDOUT,
                                         start_new_session=True)
            self.vorne = True
            self.phase = "laeuft"
            log.info(f"ZynSimple: Hybrid läuft (Mixxx {m}, Kanal {self.cid})")
            if self.vfd is None:
                self._virmidi_oeffnen()
            g = getattr(self.b, "geraete", None)
            if g is not None:
                g.start()                          # DJ-Controller mithören: SHIFT + Jog / SHIFT + Kopfhörer
                g.ddj_aktionen.clear()
            threading.Thread(target=self._waechter, daemon=True).start()
            threading.Thread(target=self._mixxx_lesen, daemon=True).start()
            threading.Thread(target=self._ddj_lesen, daemon=True).start()
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

    def nach_import(self):
        """Neue Titel auf dem Zynthian: Mixxx neu starten (liest dabei die Bibliothek neu ein) – aber erst,
        wenn gerade kein Deck spielt, damit kein Set abreißt."""
        if getattr(self, "_neu_wartet", False):
            return
        self._neu_wartet = True

        def warten():
            try:
                still = 0
                for _ in range(3 * 3600):
                    if not self.laeuft():
                        return
                    still = still + 1 if not self.mixxx_spielt else 0
                    if still >= 5:
                        break
                    time.sleep(1)
                log.info("ZynSimple: Hybrid – Mixxx liest neue Musik ein")
                self.stoppen()
                for _ in range(40):
                    if self.phase is None and not self.laeuft():
                        break
                    time.sleep(0.5)
                self.starten()
            finally:
                self._neu_wartet = False
        threading.Thread(target=warten, daemon=True).start()

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
        self._geladen = {}
        self._deck = {1: {}, 2: {}}
        self._midi_zurueck()
        if self.vfd is not None:
            try:
                os.close(self.vfd)
            except OSError:
                pass
            self.vfd = None
        if getattr(self, "vfd_ddj", None) is not None:
            try:
                os.close(self.vfd_ddj)
            except OSError:
                pass
            self.vfd_ddj = None
            self.vm_ddj_pfad = None
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
        """Virtuellen MIDI-Anschluss zu Mixxx öffnen (erster freier); Mixxx hat das Mapping auf allen."""
        self.midi_fehler = None
        try:
            with open("/proc/asound/cards", encoding="utf-8") as f:
                karten = re.findall(r"^\s*(\d+)\s+\[[^\]]*\]:.*(?:VirMIDI|Virtual)", f.read(), re.M)
        except OSError:
            karten = []
        if not karten:
            subprocess.call(["modprobe", "snd-virmidi"], stderr=subprocess.DEVNULL)
            self.midi_fehler = "virtueller MIDI-Anschluss fehlt (snd-virmidi)"
            return
        for k in karten:
            for p in sorted(glob.glob(f"/dev/snd/midiC{k}D*")):
                if p == getattr(self, "vm_ddj_pfad", None):
                    continue
                try:
                    self.vfd = os.open(p, os.O_RDWR | os.O_NONBLOCK)
                    self.vm_zyn_pfad = p
                    log.info(f"ZynSimple: Hybrid – Verbindung zu Mixxx über {p}")
                    return
                except OSError as e:
                    self.midi_fehler = f"{p}: {e.strerror}"
        log.warning(f"ZynSimple: Hybrid – virtueller MIDI-Anschluss nicht offen ({self.midi_fehler})")

    def _virmidi_ddj_oeffnen(self):
        """Zweiter virtueller Anschluss nur für den DJ-Controller: Im Zynthian hält JACK alle USB-MIDI-Geräte
        fest (-X raw) – Mixxx sähe den DDJ-200 sonst nie. ZynSimple hört ihn über JACK und reicht alles durch."""
        self.vm_ddj = None
        try:
            with open("/proc/asound/cards", encoding="utf-8") as f:
                karten = re.findall(r"^\s*(\d+)\s+\[[^\]]*\]:.*(?:VirMIDI|Virtual)", f.read(), re.M)
        except OSError:
            karten = []
        for k in karten:
            for p in sorted(glob.glob(f"/dev/snd/midiC{k}D*")):
                if p == getattr(self, "vm_zyn_pfad", None):
                    continue
                try:
                    self.vfd_ddj = os.open(p, os.O_RDWR | os.O_NONBLOCK)
                    self.vm_ddj_pfad = p
                    self.vm_ddj = f"{k}-{p.rsplit('D', 1)[1]}"
                    log.info(f"ZynSimple: Hybrid – DJ-Controller über {p} (VirMIDI {self.vm_ddj}) an Mixxx")
                    return
                except OSError:
                    pass
        log.warning("ZynSimple: Hybrid – kein zweiter virtueller MIDI-Anschluss für den DJ-Controller")
        try:
            with open("/etc/modprobe.d/zynsimple-virmidi.conf", "w") as f:
                f.write("# ZynSimple: mehrere virtuelle MIDI-Anschlüsse (Zynthian-Tasten und DJ-Controller → Mixxx)\n"
                        "options snd-virmidi midi_devs=4\n")
        except OSError:
            pass
        self.ddj_fehler = "DJ-Controller: einmal den Zynthian neu starten, dann geht er auch hier"
        try:
            with open("/proc/asound/cards", encoding="utf-8") as f:
                if re.search(r"DDJ", f.read()):
                    self.fehler = self.ddj_fehler
        except OSError:
            pass

    def ddj_senden(self, daten):
        """DJ-Controller → Mixxx (aus dem MIDI-Mithören von ZynSimple)."""
        fd = getattr(self, "vfd_ddj", None)
        if fd is not None:
            try:
                os.write(fd, daten)
            except OSError:
                pass

    def _ddj_lesen(self):
        """Mixxx → DJ-Controller (LEDs): was Mixxx an den virtuellen Anschluss schickt, geht per JACK an den DDJ."""
        puffer = bytearray()
        while self.laeuft():
            fd = getattr(self, "vfd_ddj", None)
            g = getattr(self.b, "geraete", None)
            if fd is None or g is None:
                time.sleep(1)
                continue
            try:
                r, _, _ = select.select([fd], [], [], 1.0)
                if not r:
                    continue
                daten = os.read(fd, 512)
            except (OSError, ValueError):
                time.sleep(0.5)
                continue
            for b in daten:
                if b >= 0xF8:
                    continue
                if b & 0x80 and b != 0xF7:
                    puffer = bytearray([b])
                    continue
                if not puffer:
                    continue
                puffer.append(b)
                st = puffer[0]
                if st == 0xF0:
                    if b == 0xF7:
                        g.ddj_aus.append(bytes(puffer))
                        puffer = bytearray()
                elif len(puffer) == (2 if 0xC0 <= st < 0xE0 else 3):
                    g.ddj_aus.append(bytes(puffer))
                    puffer = bytearray([st])

    def senden(self, cc, wert):
        if self.vfd is None:
            self._virmidi_oeffnen()
        if self.vfd is None:
            raise RuntimeError("Keine Verbindung zu Mixxx (" + (getattr(self, "midi_fehler", None) or "MIDI") + ")")
        os.write(self.vfd, bytes([0xB0, int(cc) & 0x7F, int(wert) & 0x7F]))

    # ------------------------------------------------------------------
    # Decks A und B (für die Anzeige in ZynSimple)
    # ------------------------------------------------------------------
    def decks(self):
        """[{geladen, laeuft, dauer, bpm, pos, rest, titel, kuenstler}, …] für Deck A und B."""
        out = []
        for d in (1, 2):
            z = dict(self._deck.get(d) or {})
            z.setdefault("geladen", 0)
            if z.get("geladen") and z.get("dauer"):
                k = (round(z["dauer"]), round(z.get("bpm", 0)))
                if self._deck_name.get(d, (None,))[0] != k:
                    name = None
                    gemerkt = self._geladen.get(d)
                    if gemerkt and abs(gemerkt.get("dauer", 0) - z["dauer"]) < 1.5:
                        name = gemerkt
                    else:
                        try:
                            from . import dj
                            name = dj.bibliothek_modul().finde(z["dauer"], z.get("bpm", 0))
                        except Exception:
                            name = None
                    self._deck_name[d] = (k, name)
                name = self._deck_name[d][1] or {}
                z["titel"] = name.get("title") or "Titel geladen"
                z["kuenstler"] = name.get("artist") or ""
                z["rest"] = max(0, int(z["dauer"] * (1 - z.get("pos", 0))))
            out.append(z)
        return out

    def play(self, deck):
        self.senden(114, 2 if int(deck) == 2 else 1)

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
                    if st in (0xB1, 0xB2) and 20 <= d1 <= 27:
                        dz = self._deck.setdefault(st - 0xB0, {})
                        if d1 in (22, 24, 26):
                            self._deck_msb[(st, d1)] = d2
                        elif d1 == 20:
                            dz["geladen"] = d2
                        elif d1 == 21:
                            dz["laeuft"] = d2
                        else:
                            w = (self._deck_msb.get((st, d1 - 1), 0) << 7) | d2
                            if d1 == 23:
                                dz["dauer"] = w
                            elif d1 == 25:
                                dz["bpm"] = w / 10.0
                            elif d1 == 27:
                                dz["pos"] = w / 16383.0
                    elif st & 0xF0 == 0xB0:
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
            if getattr(self, "_versteckt_starten", False) and n > 4 and self._mixxx_fenster():
                self._versteckt_starten = False
                self.verstecken()
            if ok and not verbunden:
                verbunden = True
                log.info("ZynSimple: Hybrid – Mixxx spielt in den Kanal „DJ-Pult“")
            if n % 2 == 1:
                self._midi_trennen()
            self._tempo()
            time.sleep(0.5 if n < 60 else 1.0)
        absturz = self.phase == "laeuft"
        self._aufraeumen()
        if absturz:
            # niemand hat beendet → Absturz: Protokoll sichern, Mixxx neu starten (höchstens 3× in 10 Minuten)
            jetzt = time.monotonic()
            self._abstuerze = [t for t in getattr(self, "_abstuerze", []) if jetzt - t < 600] + [jetzt]
            self._absturz_sichern()
            if len(self._abstuerze) <= 3:
                log.warning("ZynSimple: Hybrid – Mixxx abgestürzt, starte neu")
                try:
                    self._versteckt_starten = True      # Mischer bleibt vorne – kein Ansichtswechsel durch den Neustart
                    self.starten()
                    self.fehler = "Mixxx war abgestürzt und wurde neu gestartet – Titel bitte neu laden"
                except Exception as e:
                    self.fehler = f"Mixxx abgestürzt: {e}"
            else:
                self.fehler = "Mixxx stürzt immer wieder ab – Protokoll liegt in „MUSIK gekauft/_Diagnose“"

    def _absturz_sichern(self):
        try:
            ziel = os.path.join(DATEN, "MUSIK gekauft", "_Diagnose")
            os.makedirs(ziel, exist_ok=True)
            teile = [f"Mixxx (DJ + Instrumente) unerwartet beendet: {time.strftime('%F %T')}"]
            for p in (LOG, os.path.join(DATEN, ".mixxx", "mixxx.log")):
                try:
                    with open(p, encoding="utf-8", errors="replace") as f:
                        teile.append(f"--- {p} (Ende) ---\n" + "".join(f.readlines()[-250:]))
                except OSError:
                    pass
            with open(os.path.join(ziel, time.strftime("mixxx-absturz-%F_%H%M%S.txt")), "w", encoding="utf-8") as f:
                f.write("\n".join(teile))
        except Exception as e:
            log.debug(f"ZynSimple: Absturz-Protokoll: {e}")

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

    def laden(self, track_id, deck):
        """Titel aus der Bibliothek in Deck 1 (A) oder 2 (B) laden. Mixxx muss dafür kurz sichtbar sein
        (der Titel wird in sein Suchfeld getippt); war ZynSimple vorne, kommt es danach wieder nach vorne."""
        if not self.laeuft():
            raise RuntimeError("Mixxx läuft gerade nicht – erst „DJ + Instrumente“ starten")
        from . import dj
        vorher = self.vorne
        w = self._mixxx_fenster()
        if w:
            self._xdo("windowmap", w)
            self._xdo("windowraise", w)
            time.sleep(0.3)
        try:
            txt = dj.bibliothek_modul().laden(track_id, deck, self.senden)
            try:
                import sqlite3
                db = sqlite3.connect(f"file:{dj.bibliothek_modul().DB}?mode=ro", uri=True, timeout=3)
                r = db.execute("SELECT artist, title, duration FROM library WHERE id = ?", (int(track_id),)).fetchone()
                db.close()
                if r:
                    self._geladen[int(deck)] = {"artist": r[0] or "", "title": r[1] or "", "dauer": r[2] or 0}
            except Exception:
                pass
            return txt
        finally:
            if not vorher:
                self.verstecken()

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
        return "Mixxx vorne · MENU = zurück zum Mischer (Regler und Tasten wirken weiter)"

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
