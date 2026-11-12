# -*- coding: utf-8 -*-
"""
ZynSimple – MIDI-Geräte: BeatStep Pro, Keytar (oder jeder andere Controller) und die Ton-Anzeige.

  Mithören     eigener JACK-MIDI-Eingang je Gerät (liest nur mit, ändert nichts am Weg zu den Synths)
  Anlernen     „Taste auf der Keytar drücken“ → Gerät und MIDI-Kanal stehen fest
  Mehrkanal    Geräte mit mehreren Spuren (BeatStep Pro, Keytar am DIN) werden im Zynthian auf
               „mehrere Kanäle gleichzeitig“ (MULTI) gestellt – jede Spur hört nur ihren Kanal
  Ton-Anzeige  welche Töne gerade gespielt werden (für die Keytar ohne Display), grün = passt zur Tonart
"""
import collections
import logging
import re
import threading
import time

log = logging.getLogger("zynsimple")

RX_BSP = re.compile(r"beat\s*step\s*pro|beatsteppro|\bBSP\b", re.I)
RX_DDJ = re.compile(r"DDJ-?200", re.I)
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
        # DJ-Controller (DDJ-200) bei „DJ + Instrumente“: SHIFT + Jog = Titel wählen, SHIFT + Kopfhörer = laden
        self.ddj_namen = set()
        self.ddj_q = collections.deque(maxlen=256)
        self.ddj_aktionen = collections.deque(maxlen=64)
        self.ddj_roh = collections.deque(maxlen=2048)      # DDJ → Mixxx (bei „DJ + Instrumente“ durchreichen)
        self.ddj_aus = collections.deque(maxlen=2048)      # Mixxx → DDJ (LEDs)
        self.ddj_out = None
        self._ddj_ziel = None
        self._ddj_shift = [False, False]
        self._ddj_jog = 0

    # ------------------------------------------------------------------
    def start(self):
        if self.lauf:
            return
        try:
            import jack
            self.jc = jack.Client("zynsimple_midi", no_start_server=True)
            self.jc.set_process_callback(self._process)
            self.ddj_out = self.jc.midi_outports.register("ddj_out")
            self.jc.activate()
            self.lauf = True
            threading.Thread(target=self._pflege, daemon=True).start()
            threading.Thread(target=self._ddj_durchreichen, daemon=True).start()
            threading.Thread(target=self._auswerten, daemon=True).start()
        except Exception as e:
            log.warning(f"ZynSimple: MIDI mithören geht nicht ({e})")

    def _process(self, frames):
        # Echtzeit: nur kopieren, nichts auswerten
        o = self.ddj_out
        if o is not None:
            o.clear_buffer()
            while self.ddj_aus:
                try:
                    o.write_midi_event(0, self.ddj_aus.popleft())
                except Exception:
                    break
        for name, p in list(self.ports.items()):
            ddj = name in self.ddj_namen
            for _, data in p.incoming_midi_events():
                if ddj:
                    self.ddj_roh.append(bytes(data))
                if len(data) < 3:
                    continue
                if ddj:
                    if 0x80 <= data[0] < 0xA0 or 0xB0 <= data[0] < 0xC0:
                        self.ddj_q.append(bytes(data[:3]))
                elif 0x80 <= data[0] < 0xA0:
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
                self._ddj_ausgang(za)
            except Exception as e:
                log.debug(f"ZynSimple: MIDI-Geräte: {e}")
            time.sleep(3)

    def _ddj_ausgang(self, za):
        """Eigenen Ausgang mit dem DDJ verbinden (LEDs von Mixxx)."""
        if self.ddj_out is None:
            return
        for p in list(getattr(za, "devices_out", []) or []):
            if p is not None and RX_DDJ.search(_text(p)):
                if p.name not in [c.name for c in self.jc.get_all_connections(self.ddj_out)]:
                    try:
                        self.jc.connect(self.ddj_out, p.name)
                        log.info(f"ZynSimple: DJ-Controller-LEDs über {p.name}")
                    except Exception:
                        pass
                return

    def _ddj_durchreichen(self):
        """DDJ → Mixxx: alles, was der DDJ sendet, über den eigenen Anschluss an Mixxx (nur bei „DJ + Instrumente“)."""
        while self.lauf:
            hy = getattr(self.b, "hybrid", None)
            bereit = hy is not None and hy.ddj_bereit()
            if not self.ddj_roh:
                time.sleep(0.001 if bereit else 0.05)
                continue
            while self.ddj_roh:
                msg = self.ddj_roh.popleft()
                if bereit:
                    hy.ddj_senden(msg)

    def _ddj(self, st, d1, d2):
        """DDJ-200 (Mixxx-Belegung ab Werk): SHIFT = Note 0x3F, Jog = CC 0x21 (64 = Stillstand),
        SHIFT + Kopfhörer = Note 0x68 – jeweils Kanal 1 (Deck A) und 2 (Deck B)."""
        typ, k = st & 0xF0, st & 0x0F
        if k > 1:
            return
        an = typ == 0x90 and d2 > 0
        if typ in (0x80, 0x90) and d1 == 0x3F:
            self._ddj_shift[k] = an
            self._ddj_jog = 0
        elif typ == 0xB0 and d1 == 0x21 and any(self._ddj_shift):
            self._ddj_jog += d2 - 64
            if abs(self._ddj_jog) > 9:
                self.ddj_aktionen.append(("runter" if self._ddj_jog > 0 else "hoch", 0))
                self._ddj_jog = 0
        elif typ == 0x90 and d1 == 0x68 and an:
            self.ddj_aktionen.append(("laden", k + 1))

    def _auswerten(self):
        while self.lauf:
            while self.ddj_q:
                try:
                    self._ddj(*self.ddj_q.popleft())
                except Exception as e:
                    log.debug(f"ZynSimple: DDJ: {e}")
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
            if an and self.lernen_cb:
                cb, self.lernen_cb = self.lernen_cb, None
                try:
                    cb(geraet, kanal)
                except Exception as e:
                    log.warning(f"ZynSimple: Anlernen: {e}")

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
