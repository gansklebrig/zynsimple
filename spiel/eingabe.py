# -*- coding: utf-8 -*-
"""
Bard Hero – alle Eingaben an einem Ort.

Quellen:
  • MIDI über die Ton-Maschine (JACK, jedes Gerät einzeln)          → Socket /tmp/bardhero-spiel.sock
  • MIDI direkt (/dev/snd/midi*, DIN-Buchse /dev/ttyAMA0), falls JACK sie nicht hat
  • Zynthian-Tasten und Drehregler (Helfer tasten.py)              → gleicher Socket
  • Tastatur, Gamepad, Touch/Maus (pygame, im Hauptprogramm)

Jedes Ereignis bekommt einen genauen Zeitstempel (time.monotonic) – daraus rechnet das Spiel die Liedzeit.
Ereignis = (art, geraet, wert, zeit, extra)
  art: an · aus (Note) · cc · taste (Taste gedrückt/losgelassen, extra 1/0) · dreh · ton (Meldung der Ton-Maschine)
"""
import collections
import glob
import os
import re
import select
import socket
import subprocess
import threading
import time

SPIEL = os.environ.get("BH_SPIEL_SOCK", "/tmp/bardhero-spiel.sock")
TASTEN_SOCK = os.environ.get("BH_TASTEN_SOCK", "/tmp/bardhero-tasten.sock")
DIN = os.environ.get("BH_DIN", "/dev/ttyAMA0")

# Standard-Belegung der Hero-Spuren
MIDI_TONKLASSE = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4}                 # C D E F G (jede Oktave)
ZYN_SPUREN = ["F1", "F2", "F3", "F4", "PLAY"]
TASTATUR_SPUREN = [["1", "a"], ["2", "s"], ["3", "d"], ["4", "f"], ["5", "g"], ["6", "h"]]
SPUR_NAMEN_MIDI = ["C", "D", "E", "F", "G"]


class MidiParser:
    """Rohe MIDI-Bytes → Nachrichten (mit Running Status, SysEx und Clock werden übergangen)."""

    def __init__(self):
        self.status = 0
        self.daten = []
        self.sysex = False

    def futter(self, bytes_):
        raus = []
        for b in bytes_:
            if b >= 0xF8:
                continue
            if b == 0xF0:
                self.sysex = True
                continue
            if b == 0xF7:
                self.sysex = False
                continue
            if self.sysex:
                continue
            if b & 0x80:
                self.status = b
                self.daten = []
                continue
            if not self.status:
                continue
            self.daten.append(b)
            typ = self.status & 0xF0
            braucht = 1 if typ in (0xC0, 0xD0) else 2
            if len(self.daten) == braucht:
                raus.append(bytes([self.status] + self.daten))
                self.daten = []
        return raus


class Eingaben:
    def __init__(self):
        self.q = collections.deque(maxlen=2000)
        self.geraete = {}                  # id → Anzeigename
        self.ton_meldungen = collections.deque(maxlen=50)
        self.laeuft = True
        self.jack_midi = False
        self.letzte = collections.deque(maxlen=64)    # (zeit, bytes, geraet) – zum Erkennen doppelter Wege
        self.doppelt = collections.Counter()
        self.ignoriert = set()
        self.lock = threading.Lock()
        try:
            os.remove(SPIEL)
        except OSError:
            pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(SPIEL)
        self.sock_tasten = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        threading.Thread(target=self._socket, daemon=True).start()
        threading.Thread(target=self._roh, daemon=True).start()

    # ---- MIDI-Nachricht → Ereignis ----
    def _midi(self, t, quelle, daten):
        if len(daten) < 2:
            return
        st = daten[0] & 0xF0
        ch = daten[0] & 0x0F
        geraet = f"midi:{quelle}:{ch + 1}"
        # gleiche Nachricht kurz vorher über einen anderen Weg? (JACK und direkt zugleich) → zweiten Weg stilllegen
        if geraet in self.ignoriert:
            return
        for (t2, d2, g2) in self.letzte:
            if d2 == daten and g2 != geraet and abs(t - t2) < 0.03 and g2.split(":")[1] != quelle:
                self.doppelt[geraet] += 1
                if self.doppelt[geraet] >= 3:
                    self.ignoriert.add(geraet)
                return
        self.letzte.append((t, daten, geraet))
        if geraet not in self.geraete:
            self.geraete[geraet] = quelle.replace("_", " ") + (f" · Kanal {ch + 1}" if ch else "")
        if st == 0x90 and len(daten) >= 3 and daten[2] > 0:
            self.q.append(("an", geraet, daten[1], t, daten[2]))
        elif st == 0x80 or (st == 0x90 and len(daten) >= 3):
            self.q.append(("aus", geraet, daten[1], t, 0))
        elif st == 0xB0 and len(daten) >= 3:
            self.q.append(("cc", geraet, daten[1], t, daten[2]))
        elif st == 0xE0 and len(daten) >= 3:
            wert = ((daten[2] << 7) | daten[1]) - 8192
            self.q.append(("cc", geraet, -1, t, wert))

    def _socket(self):
        while self.laeuft:
            try:
                d = self.sock.recv(4096).decode("utf-8", "replace")
            except OSError:
                time.sleep(0.1)
                continue
            teile = d.split(" ")
            art = teile[0]
            try:
                if art == "M" and len(teile) >= 4:
                    self.jack_midi = True
                    self._midi(float(teile[1]), teile[2], bytes.fromhex(teile[3]))
                elif art == "T" and len(teile) >= 3:          # Zynthian-Taste
                    t = float(teile[3]) if len(teile) > 3 else time.monotonic()
                    self.q.append(("taste", "zyn", teile[1], t, int(teile[2])))
                    self.geraete.setdefault("zyn", "Zynthian-Tasten")
                elif art == "D" and len(teile) >= 3:          # Drehregler
                    self.q.append(("dreh", "zyn", int(teile[1]), time.monotonic(), int(teile[2])))
                elif art == "G":                              # neues Gerät bei JACK
                    self.jack_midi = True
                    self.ton_meldungen.append(d)
                else:
                    self.ton_meldungen.append(d)
            except (ValueError, IndexError):
                pass

    # ---- MIDI direkt (ohne JACK) ----
    def _roh(self):
        offen = {}                 # pfad → (fd, parser, name)
        parser = {}
        zuletzt = 0.0
        while self.laeuft:
            jetzt = time.monotonic()
            if jetzt - zuletzt > 2.0:
                zuletzt = jetzt
                for pfad, name in self._roh_geraete():
                    if pfad in offen:
                        continue
                    try:
                        if pfad == DIN:
                            subprocess.call(["stty", "-F", pfad, "38400", "raw", "-echo"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            fd = os.open(pfad, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY)
                        else:
                            fd = os.open(pfad, os.O_RDONLY | os.O_NONBLOCK)
                        offen[pfad] = (fd, name)
                        parser[pfad] = MidiParser()
                    except OSError:
                        offen[pfad] = (None, name)          # belegt (z. B. von JACK) – nicht nochmal versuchen
                # verschwundene Geräte
                for pfad in list(offen):
                    if not os.path.exists(pfad):
                        fd = offen.pop(pfad)[0]
                        if fd is not None:
                            os.close(fd)
            fds = {v[0]: k for k, v in offen.items() if v[0] is not None}
            if not fds:
                time.sleep(0.5)
                continue
            try:
                r, _, _ = select.select(list(fds), [], [], 0.25)
            except (OSError, ValueError):
                time.sleep(0.2)
                continue
            t = time.monotonic()
            for fd in r:
                pfad = fds[fd]
                try:
                    daten = os.read(fd, 256)
                except OSError:
                    os.close(fd)
                    offen[pfad] = (None, offen[pfad][1])
                    continue
                for msg in parser[pfad].futter(daten):
                    self._midi(t, offen[pfad][1], msg)

    def _roh_geraete(self):
        raus = []
        try:
            with open("/proc/asound/cards", encoding="utf-8") as f:
                karten = {int(m.group(1)): m.group(3).strip() for m in
                          re.finditer(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(.*)$", f.read(), re.M)}
        except OSError:
            karten = {}
        for p in sorted(glob.glob("/dev/snd/midiC*D*")):
            m = re.search(r"midiC(\d+)D(\d+)", p)
            name = karten.get(int(m.group(1)), p) if m else p
            if re.search(r"VirMIDI|Virtual|Midi Through", name, re.I):
                continue
            name = name.split(" - ")[-1].strip() or name
            raus.append((p, name.replace(" ", "_")[:32]))
        if DIN and os.path.exists(DIN) and not self.jack_midi_din():
            raus.append((DIN, "MIDI-Buchse"))
        return raus

    def jack_midi_din(self):
        return any("ttymidi" in g or "serial" in g.lower() for g in self.geraete)

    # ---- Zynthian-LEDs ----
    def led(self, name, rgb):
        try:
            self.sock_tasten.sendto(f"L {name} {rgb[0]} {rgb[1]} {rgb[2]}".encode(), TASTEN_SOCK)
        except OSError:
            pass

    def leds_alle(self, rgb):
        try:
            self.sock_tasten.sendto(f"A {rgb[0]} {rgb[1]} {rgb[2]}".encode(), TASTEN_SOCK)
        except OSError:
            pass

    def holen(self):
        raus = []
        while self.q:
            raus.append(self.q.popleft())
        return raus

    def ende(self):
        self.laeuft = False
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------------------
# Was bedeutet ein Ereignis? (Menü-Steuerung und Spuren)
# ---------------------------------------------------------------------------------------------------------
ZYN_NAV = {"UP": "hoch", "DOWN": "runter", "LEFT": "links", "RIGHT": "rechts", "SEL": "ok", "BACK": "zurueck",
           "MENU": "menue", "PLAY": "ok", "STOP": "zurueck", "DREH1": "ok", "DREH2": "ok", "DREH3": "ok", "DREH4": "ok"}
TASTATUR_NAV = {"up": "hoch", "down": "runter", "left": "links", "right": "rechts", "return": "ok", "enter": "ok",
                "space": "ok", "escape": "zurueck", "backspace": "zurueck", "tab": "menue"}
MIDI_NAV = {0: "hoch", 2: "runter", 4: "links", 5: "rechts", 7: "ok", 9: "zurueck"}   # C D E F G A


def navigation(ev):
    """Ereignis → hoch/runter/links/rechts/ok/zurueck/menue, ('dreh', ±n) oder None."""
    art, geraet, wert, t, extra = ev
    if art == "taste" and extra:
        if geraet == "zyn":
            return ZYN_NAV.get(wert)
        if geraet == "tast":
            return TASTATUR_NAV.get(wert)
        if geraet.startswith("pad"):
            return {"hoch": "hoch", "runter": "runter", "links": "links", "rechts": "rechts", "0": "ok",
                    "1": "zurueck", "7": "menue", "9": "menue"}.get(str(wert))
    if art == "an":
        return MIDI_NAV.get(wert % 12)
    if art == "dreh":
        return ("dreh", extra)
    return None


def belegung_von(belegung, geraet):
    """Angelernte Belegung eines Geräts (MIDI: unabhängig vom Kanal)."""
    if not geraet:
        return None
    return belegung.get(geraet) or belegung.get(geraet.rsplit(":", 1)[0] if geraet.startswith("midi:") else geraet)


def hero_spur(ev, belegung, anzahl=5):
    """Ereignis → (Spur, gedrückt?) im Hero-Modus. belegung: {geraet: {schlüssel: spur}} (angelernt)."""
    art, geraet, wert, t, extra = ev
    eigen = belegung_von(belegung, geraet)
    if art in ("an", "aus"):
        gedrueckt = art == "an"
        if eigen:
            s = eigen.get(str(wert))
            if s is None:
                s = eigen.get("k" + str(wert % 12))
        else:
            s = MIDI_TONKLASSE.get(wert % 12)
        return (s, gedrueckt) if s is not None and s < anzahl else (None, gedrueckt)
    if art == "taste":
        if eigen:
            s = eigen.get(str(wert))
        elif geraet == "zyn":
            s = ZYN_SPUREN.index(wert) if wert in ZYN_SPUREN else None
        elif geraet == "tast":
            s = next((i for i, k in enumerate(TASTATUR_SPUREN) if wert in k), None)
        elif geraet.startswith("pad"):
            s = int(wert) if str(wert).isdigit() else None
        else:
            s = None
        return (s, bool(extra)) if s is not None and s < anzahl else (None, bool(extra))
    return (None, False)


def barden_ton(ev):
    """Barden-Modus: Notenereignis → (Tonklasse, gedrückt?)."""
    art, geraet, wert, t, extra = ev
    if art in ("an", "aus"):
        return wert % 12, art == "an"
    return None, False
