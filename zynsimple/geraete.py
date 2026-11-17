# -*- coding: utf-8 -*-
"""
ZynSimple – MIDI-Geräte: BeatStep Pro, Keytar (oder jeder andere Controller) und die Ton-Anzeige.

  Mithören     eigener JACK-MIDI-Eingang je Gerät (liest nur mit, ändert nichts am Weg zu den Synths)
  Anlernen     „Taste auf der Keytar drücken“ → Gerät und MIDI-Kanal stehen fest
  Mehrkanal    Geräte mit mehreren Spuren (BeatStep Pro, Keytar am DIN) werden im Zynthian auf
               „mehrere Kanäle gleichzeitig“ (MULTI) gestellt – jede Spur hört nur ihren Kanal
  Ton-Anzeige  welche Töne gerade gespielt werden (für die Keytar ohne Display), grün = passt zur Tonart
  Weitergeben  alles von der angelernten Handpan (z. B. Neotone) zusätzlich an einen MIDI-Ausgang
               (z. B. Streichfett) – so spielen Zynthian-Synth und externer Synth gleichzeitig
"""
import collections
import logging
import re
import threading
import time

log = logging.getLogger("zynsimple")

RX_BSP = re.compile(r"beat\s*step\s*pro|beatsteppro|\bBSP\b", re.I)
RX_DDJ = re.compile(r"DDJ-?(FLX\d+|[A-Z]{0,3}\d+)", re.I)     # Pioneer DDJ-200, -400, -FLX4 …
RX_NICHT = re.compile(r"zynsimple|ZynMidiRouter|VirMIDI|Virtual Raw|Midi Through|zynseq|zynmidi", re.I)

# BeatStep Pro ab Werk: SEQ 1 = Kanal 1, SEQ 2 = Kanal 2, Drums = Kanal 10
BSP_SPUREN = [
    ("bass", "BSP 1 · Bass", 0, ["JV/JC303", "JV/Triceratops", "JV/Surge XT", "JV/Helm", "ZY"]),
    ("melodie", "BSP 2 · Melodie", 1, ["JV/Surge XT", "JV/Obxd", "JV/padthv1", "JV/Helm", "ZY"]),
    ("drums", "BSP Drums", 9, ["JV/FluidGM", "FS"]),
]


def notenname(n):
    from .helfer import NOTEN
    return f"{NOTEN[n % 12]}{n // 12 - 1}"


def _name(port):
    try:
        al = list(port.aliases or [])
        return str(al[1] if len(al) > 1 else (al[0] if al else port.name))
    except Exception:
        return str(port)


def _text(port):
    try:
        return " ".join([port.name] + [str(a) for a in (port.aliases or [])])
    except Exception:
        return str(port)


class Geraete:
    def __init__(self, bridge, settings):
        self.b = bridge
        self.settings = settings
        self.jc = None
        self.ports = {}                     # Name des Geräte-Ports → eigener Eingang
        self.q = collections.deque(maxlen=512)
        self.aktiv = {}                     # (gerät, kanal) → {note: zeit}
        self.zuletzt = {}                   # (gerät, kanal) → zeit des letzten Tons
        self.lernen_cb = None
        self._letzte = {}
        self.lauf = False
        self._lock = threading.Lock()
        self.ddj_namen = set()        # DJ-Controller: seine Tasten sind keine gespielten Töne
        self._neuer_kanal = {}        # Keytar spielt plötzlich auf anderem Kanal: kanal → [zeiten]
        self.hinweis = None           # Text für den Bildschirm (holt screen.tick ab)
        self.thru = None              # eigener MIDI-Ausgang: Handpan → externer Synth
        self._hp = None               # Name des Handpan-Geräts, solange weitergegeben wird

    # ------------------------------------------------------------------
    def start(self):
        if self.lauf:
            return
        try:
            import jack
            self.jc = jack.Client("zynsimple_midi", no_start_server=True)
            self.jc.set_process_callback(self._process)
            self.jc.activate()
            self.lauf = True
            threading.Thread(target=self._pflege, daemon=True).start()
            threading.Thread(target=self._auswerten, daemon=True).start()
        except Exception as e:
            log.warning(f"ZynSimple: MIDI mithören geht nicht ({e})")

    def _process(self, frames):
        # Echtzeit: nur kopieren, nichts auswerten
        out, hp = self.thru, self._hp
        if out is not None:
            out.clear_buffer()
        for name, p in list(self.ports.items()):
            ddj = name in self.ddj_namen
            for t, data in p.incoming_midi_events():
                if out is not None and name == hp and len(data) >= 2 and 0x80 <= data[0] < 0xF0:
                    try:
                        out.write_midi_event(t, bytes(data))
                    except Exception:
                        pass
                if len(data) < 3 or ddj:
                    continue
                if 0x80 <= data[0] < 0xA0:
                    self.q.append((name, bytes(data[:3])))

    def _pflege(self):
        """Neue Geräte (eingesteckt) mithören, abgezogene vergessen."""
        while self.lauf:
            try:
                import zynautoconnect as za
                da = {}
                for p in list(za.devices_in):
                    if p is not None and not RX_NICHT.search(_text(p)):
                        da[p.name] = _name(p)
                for pname, anzeige in da.items():
                    if RX_DDJ.search(anzeige) or RX_DDJ.search(pname):
                        self.ddj_namen.add(anzeige)
                    if anzeige not in self.ports:
                        nr = len(self.ports)
                        port = self.jc.midi_inports.register(f"in_{nr}")
                        self.jc.connect(pname, port)
                        self.ports[anzeige] = port
                        log.info(f"ZynSimple: höre MIDI von „{anzeige}“ mit")
                    else:
                        port = self.ports[anzeige]
                        if pname not in [c.name for c in self.jc.get_all_connections(port)]:
                            self.jc.connect(pname, port)
                self._multi_pflegen()
                self._thru_pflegen()
            except Exception as e:
                log.debug(f"ZynSimple: MIDI-Geräte: {e}")
            time.sleep(3)

    def _auswerten(self):
        while self.lauf:
            if not self.q:
                time.sleep(0.01)
                continue
            geraet, (st, note, vel) = self.q.popleft()
            kanal = st & 0x0F
            an = (st & 0xF0) == 0x90 and vel > 0
            k = (geraet, kanal)
            with self._lock:
                d = self.aktiv.setdefault(k, {})
                if an:
                    d[note] = time.monotonic()
                    self.zuletzt[k] = time.monotonic()
                else:
                    d.pop(note, None)
            if an and not self.lernen_cb:
                self._kanal_folgen(geraet, kanal)
            if an and self.lernen_cb:
                cb, self.lernen_cb = self.lernen_cb, None
                try:
                    cb(geraet, kanal)
                except Exception as e:
                    log.warning(f"ZynSimple: Anlernen: {e}")

    def ausgaenge(self):
        """MIDI-Ausgänge, an die die Handpan weitergeben kann (DIN-Buchse, USB-Synths)."""
        try:
            import zynautoconnect as za
            return [_name(p) for p in list(za.devices_out)
                    if p is not None and not RX_NICHT.search(_text(p)) and not RX_DDJ.search(_text(p))]
        except Exception:
            return []

    def _thru_pflegen(self):
        ziel, hp = self.settings.get("thru_ziel") or "", self.settings.get("handpan_geraet")
        if not ziel or not hp:
            self._hp = None
            if self.thru is not None:
                for c in self.jc.get_all_connections(self.thru):
                    self.jc.disconnect(self.thru, c)
            return
        if self.thru is None:
            self.thru = self.jc.midi_outports.register("thru_out")
        import zynautoconnect as za
        soll = [p.name for p in list(za.devices_out) if p is not None and _name(p) == ziel]
        ist = [c.name for c in self.jc.get_all_connections(self.thru)]
        for n in ist:
            if n not in soll:
                self.jc.disconnect(self.thru, n)
        for n in soll:
            if n not in ist:
                self.jc.connect(self.thru, n)
                log.info(f"ZynSimple: Handpan „{hp}“ → „{ziel}“")
        self._hp = hp

    def _kanal_folgen(self, geraet, kanal):
        """Keytar nie mehr neu einstellen: spielt das angelernte Gerät dauerhaft auf einem anderen Kanal
        (3 Töne in 6 s, auf dem alten seit 20 s nichts), zieht ZynSimple Einstellung und Spuren mit.
        Kanal 10 bleibt außen vor – dort schicken Drumcomputer (TR-8S) gern ihre Töne."""
        kg, kk = self.settings.get("keytar_geraet"), self.settings.get("keytar_kanal")
        if not kg or kk is None or geraet != kg or kanal == int(kk) or kanal == 9:
            return
        jetzt = time.monotonic()
        if jetzt - self.zuletzt.get((geraet, int(kk)), 0) < 20:
            return
        z = [t for t in self._neuer_kanal.get(kanal, []) if jetzt - t < 6] + [jetzt]
        self._neuer_kanal[kanal] = z
        if len(z) < 3:
            return
        self._neuer_kanal = {}
        alt = int(kk)
        try:
            from . import settings as st
            st.save(self.settings, {"keytar_kanal": kanal})
            for cid, chain in list(self.b.cm.chains.items()):
                if getattr(chain, "midi_chan", None) == alt and getattr(chain, "synth_slots", True):
                    self.b.tracks.set_midi(cid, kanal)
            log.info(f"ZynSimple: Keytar spielt jetzt auf Kanal {kanal + 1} (vorher {alt + 1}) – mitgezogen")
            self.hinweis = f"🎸 Keytar spielt jetzt auf Kanal {kanal + 1} – Klang zieht mit"
        except Exception as e:
            log.warning(f"ZynSimple: Keytar-Kanal mitziehen: {e}")

    # ------------------------------------------------------------------
    # Anlernen und Anzeige
    # ------------------------------------------------------------------
    def lernen(self, cb):
        """Nächster gespielter Ton (egal von welchem Gerät) → cb(gerät, kanal)."""
        self.start()
        self.lernen_cb = cb

    def lernen_abbrechen(self):
        self.lernen_cb = None

    def gespielt(self):
        """Für die Ton-Anzeige: (gerät, kanal, [noten]) der zuletzt gespielten Quelle oder None.
        Töne bleiben nach dem Loslassen noch kurz stehen (zum Ablesen)."""
        modus = self.settings.get("ton_anzeige", "aus")
        if modus == "aus":
            return None
        kt = (self.settings.get("keytar_geraet"), self.settings.get("keytar_kanal"))
        jetzt = time.monotonic()
        with self._lock:
            kandidaten = [(t, k) for k, t in self.zuletzt.items()
                          if (modus == "alle" or k == kt) and jetzt - t < 2.5]
            if not kandidaten:
                return None
            _, k = max(kandidaten)
            noten = sorted(self.aktiv.get(k, {}))
            if not noten:
                # losgelassen: den letzten Ton noch zeigen
                noten = [] if jetzt - self.zuletzt[k] > 2.5 else self._letzte.get(k, [])
            else:
                self._letzte[k] = noten
        return k[0], k[1], noten

    # ------------------------------------------------------------------
    # Mehrere Kanäle gleichzeitig (MULTI) für BeatStep Pro und Keytar
    # ------------------------------------------------------------------
    def _multi_pflegen(self):
        namen = set()
        if self.settings.get("bsp_an"):
            namen.add("__bsp__")
        if self.settings.get("keytar_geraet"):
            namen.add(self.settings["keytar_geraet"])
        if self.settings.get("handpan_geraet"):
            namen.add(self.settings["handpan_geraet"])
        if namen:
            self.multi_setzen(namen)

    def multi_setzen(self, namen):
        try:
            import zynautoconnect as za
            from zyncoder.zyncore import lib_zyncore
        except Exception:
            return
        for idev, p in enumerate(list(za.devices_in)):
            if p is None:
                continue
            treffer = _name(p) in namen or ("__bsp__" in namen and RX_BSP.search(_text(p)))
            if treffer and za.get_midi_in_dev_mode(idev):
                lib_zyncore.zmip_set_flag_active_chain(idev, False)
                za.update_midi_in_dev_mode(idev)
                log.info(f"ZynSimple: {_name(p)} → mehrere Kanäle gleichzeitig")

    def bsp_da(self):
        try:
            import zynautoconnect as za
            return next((_name(p) for p in za.devices_in if p is not None and RX_BSP.search(_text(p))), None)
        except Exception:
            return None
