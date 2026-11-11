#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: macht im DJ-Modus aus den Tasten und Reglern des Zynthian V5 einen Zusatz-Controller für Mixxx.

  Tasten & Drehregler  → virtueller MIDI-Anschluss (snd-virmidi) → Mixxx-Mapping „Zynthian V5 (ZynSimple)“
  Mixxx → LEDs der Tasten, Tempo und Takt des laufenden Tracks
  Tempo/Takt           → MIDI-Clock für die TR-8S (USB oder DIN-Buchse)

  BACK 2 s halten    → System-Menü (Updates, Neustart, Ausschalten, Zynthian, Barden Beats)
  MENU 1,5 s halten  → weiter zu Barden Beats (wenn installiert)
  STOP 3 s halten    → alles speichern und ausschalten

Läuft nur, solange die DJ-Sitzung läuft (wird von dj-sitzung.sh gestartet).
"""
import ctypes
import glob
import json
import os
import re
import select
import subprocess
import threading
import time

LIB = os.environ.get("ZYNCORE_LIB", "/zynthian/zyncoder/build/libzyncore.so")
BEFEHL = "/usr/local/bin/zynsimple-dj"
ZS_JSON = "/zynthian/zynthian-my-data/zynsimple/zynsimple.json"
IMRES = "/usr/local/bin/imres-modus"

# CUSTOM_SWITCH_nn → Index nn + 3; Nummer = MIDI-Note an Mixxx
TASTEN = {1: "MENU", 2: "MIXER", 3: "CTRL", 4: "ZS3", 5: "ALT", 6: "TEMPO", 7: "PAD", 8: "F1", 9: "REC", 10: "STOP",
          11: "PLAY", 12: "F2", 13: "BACK", 14: "UP", 15: "SEL", 16: "F3", 17: "LEFT", 18: "DOWN", 19: "RIGHT", 20: "F4",
          21: "DREH1", 22: "DREH2", 23: "DREH3", 24: "DREH4"}
LED_NR = {"MENU": 0, "MIXER": 1, "CTRL": 2, "ZS3": 3, "F1": 4, "PAD": 5, "TEMPO": 6, "ALT": 7, "REC": 8, "STOP": 9,
          "PLAY": 10, "F2": 11, "F3": 12, "SEL": 13, "UP": 14, "BACK": 15, "LEFT": 16, "DOWN": 17, "RIGHT": 18, "F4": 19}
NUMMER = {v: k for k, v in TASTEN.items()}
# LED-Farbcodes, die das Mixxx-Mapping schickt (ohne Blau)
FARBE = {0: (0, 0, 0), 1: (26, 12, 2), 2: (200, 130, 15), 3: (210, 20, 25), 4: (30, 170, 60), 5: (235, 210, 60)}
HALTEN = {"BACK": (2.0, "menue"), "MENU": (1.5, "imres"), "STOP": (3.0, "aus")}
HIER = os.path.dirname(os.path.abspath(__file__))
_menue = {"proc": None}


def log(*a):
    print("DJ-Helfer:", *a, flush=True)


def einstellungen():
    s = {"dj_clock": True}
    try:
        with open(ZS_JSON, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


# ---------------------------------------------------------------------------------------------------------
# MIDI-Anschlüsse (roh, ohne Zusatzbibliotheken)
# ---------------------------------------------------------------------------------------------------------
def karte_nach_name(rx):
    try:
        with open("/proc/asound/cards", encoding="utf-8") as f:
            for m in re.finditer(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(.*)$", f.read(), re.M):
                if re.search(rx, m.group(2) + " " + m.group(3), re.I):
                    return int(m.group(1))
    except OSError:
        pass
    return None


def rawmidi(nr):
    if nr is None:
        return None
    p = sorted(glob.glob(f"/dev/snd/midiC{nr}D*"))
    return p[0] if p else None


class Virtuell:
    """Virtueller MIDI-Anschluss zu Mixxx."""

    def __init__(self):
        self.fd = None
        for _ in range(20):
            p = rawmidi(karte_nach_name(r"VirMIDI|Virtual"))
            if p:
                try:
                    self.fd = os.open(p, os.O_RDWR | os.O_NONBLOCK)
                    log("virtueller MIDI-Anschluss:", p)
                    break
                except OSError as e:
                    log("virtueller MIDI-Anschluss nicht offen:", e)
            time.sleep(0.5)

    def send(self, *b):
        if self.fd is not None:
            try:
                os.write(self.fd, bytes(b))
            except OSError:
                pass


class Clock:
    """MIDI-Clock (24 pro Viertel) im Tempo des laufenden Tracks, mit Start/Stopp und Takt-Ausrichtung."""

    def __init__(self, an):
        self.an = an
        self.bpm = 0.0
        self.spielt = False
        self.gestartet = False
        self.zaehler = 0
        self.ziele = []
        self.lock = threading.Lock()
        self.schlag = None
        if not an:
            return
        p = rawmidi(karte_nach_name(r"TR-?8|TR-?6"))
        if p:
            try:
                self.ziele.append(os.open(p, os.O_WRONLY | os.O_NONBLOCK))
                log("Clock an TR-8S (USB):", p)
            except OSError as e:
                log("TR-8S USB nicht offen:", e)
        din = os.environ.get("DJ_CLOCK_DIN", "/dev/ttyAMA0")
        if din and os.path.exists(din):
            try:
                subprocess.call(["stty", "-F", din, "38400", "raw", "-echo"], stderr=subprocess.DEVNULL)
                self.ziele.append(os.open(din, os.O_WRONLY | os.O_NONBLOCK | os.O_NOCTTY))
                log("Clock an MIDI-OUT (DIN):", din)
            except OSError as e:
                log("DIN nicht offen:", e)
        threading.Thread(target=self._lauf, daemon=True).start()

    def _send(self, b):
        for fd in self.ziele:
            try:
                os.write(fd, bytes([b]))
            except OSError:
                pass

    def takt(self):
        """Mixxx meldet einen Schlag des führenden Decks."""
        with self.lock:
            self.schlag = time.monotonic()

    def _lauf(self):
        naechster = time.monotonic()
        while True:
            with self.lock:
                bpm, spielt, schlag = self.bpm, self.spielt, self.schlag
                self.schlag = None
            jetzt = time.monotonic()
            if not spielt or bpm < 30:
                if self.gestartet:
                    self._send(0xFC)
                    self.gestartet = False
                time.sleep(0.01)
                naechster = time.monotonic()
                continue
            iv = 60.0 / bpm / 24.0
            if schlag is not None:
                if not self.gestartet:
                    self._send(0xFA)            # Start genau auf dem Schlag
                    self.gestartet = True
                    self.zaehler = 0
                    naechster = schlag
                else:
                    pos = self.zaehler % 24
                    if 2 < pos < 22:            # weggelaufen → neu auf den Schlag setzen
                        self.zaehler = 0
                        naechster = schlag
            if not self.gestartet:
                time.sleep(0.002)
                continue
            if jetzt >= naechster:
                self._send(0xF8)
                self.zaehler += 1
                naechster += iv
                if jetzt - naechster > 0.05:
                    naechster = jetzt + iv
            else:
                time.sleep(min(0.002, naechster - jetzt))


# ---------------------------------------------------------------------------------------------------------
# LEDs
# ---------------------------------------------------------------------------------------------------------
class Leds:
    def __init__(self):
        self.pix = None
        self.stand = {n: 0 for n in LED_NR}
        try:
            import board
            import neopixel_spi as neopixel
            self.pix = neopixel.NeoPixel_SPI(board.SPI(), 20, pixel_order=neopixel.GRB, auto_write=False,
                                             frequency=6400000)
        except Exception as e:
            log("LEDs nicht verfügbar:", e)
        self.stand["BACK"] = 2
        if os.path.exists(IMRES):
            self.stand["MENU"] = 4
        self.stand["STOP"] = 3
        self.zeigen()

    def setzen(self, name, code):
        if name in self.stand and name not in ("BACK", "MENU", "STOP"):
            self.stand[name] = code
            self.zeigen()

    def zeigen(self):
        if self.pix is None:
            return
        try:
            for name, i in LED_NR.items():
                self.pix[i] = FARBE.get(self.stand.get(name, 0), (0, 0, 0))
            self.pix.show()
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------------------
def menue_zeigen():
    """System-Menü über Mixxx legen (BACK 2 s)."""
    p = _menue["proc"]
    if p is not None and p.poll() is None:
        return
    for py in ("/zynthian/venv/bin/python3", "/usr/bin/python3"):
        if os.path.exists(py) and subprocess.call([py, "-c", "import tkinter"], stderr=subprocess.DEVNULL) == 0:
            _menue["proc"] = subprocess.Popen([py, os.path.join(HIER, "dj-menue.py")], env=dict(os.environ, DISPLAY=":0"))
            return
    umschalten("zynthian")      # ohne Tk: wie früher direkt zurück zum Zynthian


def umschalten(ziel):
    if ziel == "menue":
        return menue_zeigen()
    if ziel == "imres" and not os.path.exists(IMRES):
        return
    log("wechsle zu", ziel)
    cmd = [BEFEHL, ziel]
    if subprocess.call(["which", "systemd-run"], stdout=subprocess.DEVNULL) == 0:
        cmd = ["systemd-run", "--no-block", "--collect", "--quiet"] + cmd
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def mixxx_lesen(v, clock, leds):
    """Nachrichten von Mixxx: LEDs, Tempo, Takt."""
    puffer = []
    bpm_msb = 0
    while True:
        if v.fd is None:
            time.sleep(1)
            continue
        r, _, _ = select.select([v.fd], [], [], 1.0)
        if not r:
            continue
        try:
            daten = os.read(v.fd, 256)
        except OSError:
            time.sleep(0.1)
            continue
        for b in daten:
            if b >= 0xF8:
                continue
            if b & 0x80:
                puffer = [b]
            else:
                puffer.append(b)
            if len(puffer) == 3:
                st, d1, d2 = puffer
                puffer = [st]            # running status
                typ = st & 0xF0
                if typ == 0x90:
                    name = TASTEN.get(d1)
                    if name:
                        leds.setzen(name, d2)
                elif typ == 0xB0:
                    if d1 == 100:
                        bpm_msb = d2
                    elif d1 == 101:
                        with clock.lock:
                            clock.bpm = ((bpm_msb << 7) | d2) / 10.0
                    elif d1 == 102 and d2:
                        clock.takt()
                    elif d1 == 103:
                        with clock.lock:
                            clock.spielt = d2 > 0


def main():
    s = einstellungen()
    v = Virtuell()
    clock = Clock(bool(s.get("dj_clock", True)))
    leds = Leds()
    threading.Thread(target=mixxx_lesen, args=(v, clock, leds), daemon=True).start()
    try:
        lib = ctypes.cdll.LoadLibrary(LIB)
    except OSError as e:
        log("zyncore nicht gefunden – keine Tasten:", e)
        while True:
            time.sleep(60)
    lib.get_zynswitch.restype = ctypes.c_int
    lib.get_value_zynpot.restype = ctypes.c_int32
    if not lib.init_zyncontrol():
        log("zyncontrol ließ sich nicht starten")
        while True:
            time.sleep(60)
    try:
        npots = lib.get_num_zynpots()
    except Exception:
        npots = 4
    for i in range(npots):
        try:
            lib.setup_behaviour_zynpot(i, 0)
        except Exception:
            pass
    try:
        letzter = lib.get_last_zynswitch_index()
    except Exception:
        letzter = 27
    log("bereit:", letzter + 1, "Schalter,", npots, "Drehregler")
    seit = {}
    erledigt = set()
    while True:
        jetzt = time.monotonic()
        for idx in range(4, letzter + 1):
            nr = idx - 3
            name = TASTEN.get(nr)
            if not name:
                continue
            d = lib.get_zynswitch(idx, 20 * 1000000)
            if d == 0:
                if idx not in seit:
                    seit[idx] = jetzt
                    if name not in HALTEN:
                        v.send(0x90, nr, 127)
            elif d > 0:
                seit.pop(idx, None)
                erledigt.discard(idx)
                if name not in HALTEN:
                    v.send(0x80, nr, 0)
            t0 = seit.get(idx)
            if t0 is not None and name in HALTEN and idx not in erledigt and jetzt - t0 >= HALTEN[name][0]:
                erledigt.add(idx)
                umschalten(HALTEN[name][1])
        for i in range(npots):
            d = lib.get_value_zynpot(i)
            if d:
                v.send(0xB0, 1 + i, max(1, min(127, 64 + int(d))))
        time.sleep(0.008)


if __name__ == "__main__":
    main()
