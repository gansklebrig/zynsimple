# -*- coding: utf-8 -*-
"""
Bard Hero – Kompositions-Werkzeug.

Ein Lied wird abschnittsweise beschrieben: Akkorde pro Takt, dazu Muster für Schlagzeug, Bass, Begleitung,
Arpeggios, Flächen und ausgeschriebene Melodien. Daraus entstehen
  • MIDI-Dateien (ganze Band / nur Melodie / nur Bass) zum Rendern mit FluidSynth
  • die Noten-Daten (chart) für das Spiel

Schreibweise der Melodien (alle Längen in Sechzehnteln):
  "D5:4 F5:2 A5:2 | G5:8 r:8 |"     Note:Länge, r = Pause, | = Taktstrich (wird geprüft!)
  "_:4"                               verlängert die vorige Note
  "C5+E5:4"                           Doppelgriff (für Begleitstimmen)
  "A5:2!"  /  "A5:2?"                 betont / leise
  Länge weglassen = gleiche Länge wie vorher.

Schlagzeug-Raster (eine Zeichenreihe pro Instrument, pro Zeichen ein Sechzehntel):
  X = laut, x = normal, o = leise, g = Geisternote, . = nichts
"""

import random
import re
import struct

PPQ = 480
SECH = PPQ // 4                      # ein Sechzehntel

NOTEN = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11, "H": 11}
NAMEN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]

DRUM = {
    "k": 36, "K": 35, "s": 38, "S": 40, "x": 37, "l": 39, "h": 42, "p": 44, "o": 46, "r": 51, "b": 53,
    "c": 49, "C": 57, "y": 55, "n": 52, "t": 50, "T": 48, "m": 47, "M": 45, "f": 43, "F": 41,
    "w": 54, "z": 70, "Z": 69, "g": 56, "v": 75, "q": 76, "Q": 77, "u": 63, "U": 64, "e": 62,
    "j": 60, "J": 61, "a": 73, "A": 74, "i": 81, "I": 80, "W": 58,
}
STAERKE = {"X": 120, "x": 98, "o": 74, "g": 48}

AKKORDTYPEN = {
    "": (0, 4, 7), "m": (0, 3, 7), "5": (0, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10),
    "maj7": (0, 4, 7, 11), "sus4": (0, 5, 7), "sus2": (0, 2, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
    "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14), "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9), "9": (0, 4, 7, 10, 14),
    "m9": (0, 3, 7, 10, 14), "7sus4": (0, 5, 7, 10), "dim7": (0, 3, 6, 9), "m7b5": (0, 3, 6, 10),
}

TONLEITERN = {
    "dur": (0, 2, 4, 5, 7, 9, 11), "moll": (0, 2, 3, 5, 7, 8, 10), "dorisch": (0, 2, 3, 5, 7, 9, 10),
    "harmonisch": (0, 2, 3, 5, 7, 8, 11), "phrygisch": (0, 1, 3, 5, 7, 8, 10), "mixolydisch": (0, 2, 4, 5, 7, 9, 10),
    "kurd": (0, 2, 3, 5, 7, 8, 10),
}


def tonklasse(name):
    name = name.strip()
    pc = NOTEN[name[0].upper()]
    for z in name[1:]:
        if z == "#":
            pc += 1
        elif z == "b":
            pc -= 1
    return pc % 12


def note_zahl(text):
    """'C#5' → 73 (C4 = 60)."""
    m = re.fullmatch(r"([A-Ha-h])([#b]*)(-?\d)", text)
    if not m:
        raise ValueError(f"Unbekannte Note {text!r}")
    pc = NOTEN[m.group(1).upper()] + m.group(2).count("#") - m.group(2).count("b")
    return 12 * (int(m.group(3)) + 1) + pc


class Akkord:
    def __init__(self, text):
        self.text = text
        m = re.fullmatch(r"([A-H][#b]?)([a-z0-9#]*)(?:/([A-H][#b]?))?", text)
        if not m:
            raise ValueError(f"Unbekannter Akkord {text!r}")
        self.grund = tonklasse(m.group(1))
        art = m.group(2)
        if art not in AKKORDTYPEN:
            raise ValueError(f"Unbekannte Akkordart {text!r}")
        self.intervalle = AKKORDTYPEN[art]
        self.bass = tonklasse(m.group(3)) if m.group(3) else self.grund

    def toene(self):
        return [(self.grund + i) % 12 for i in self.intervalle]

    def tief(self, unten):
        """Grundton (bzw. Basston) als tiefste Note ab `unten`."""
        n = unten + ((self.bass - unten) % 12)
        return n

    def ton(self, stufe, unten):
        """Akkordton relativ zum Grundton ab `unten`: 1=Grundton, 3=Terz, 5=Quinte, 7=Septime."""
        r = self.tief(unten)
        if stufe == "R":
            return r
        rel = {"3": 1, "5": 2, "7": 3}.get(stufe)
        if rel is None:
            return r
        iv = self.intervalle
        if self.bass != self.grund:
            r = unten + ((self.grund - unten) % 12)
        if stufe == "5":
            q = 7 if 7 in iv else (6 if 6 in iv else (8 if 8 in iv else 7))
            return r + q
        if stufe == "3":
            t = [i for i in iv if i in (3, 4, 2, 5)]
            return r + (t[0] if t else 4)
        if stufe == "7":
            t = [i for i in iv if i in (9, 10, 11)]
            return r + (t[0] if t else 10)
        return r

    def stimmen(self, zentrum, anzahl=None, vorher=None):
        """Enge Lage um `zentrum`, möglichst nah an der vorigen Lage (Stimmführung)."""
        toene = [(self.grund + i) % 12 for i in self.intervalle]
        if anzahl and anzahl > len(toene):
            toene = toene + [toene[0]] * (anzahl - len(toene))
        elif anzahl:
            toene = toene[:anzahl]
        beste = None
        for unten in range(zentrum - 9, zentrum + 3):
            lage = []
            n = unten
            for k, pc in enumerate(toene):
                n = n + ((pc - n) % 12) if k == 0 else n + ((pc - n - 1) % 12) + 1
                lage.append(n)
            mitte = sum(lage) / len(lage)
            kosten = abs(mitte - zentrum)
            if vorher:
                kosten = 0.4 * kosten + sum(min(abs(a - b) for b in vorher) for a in lage) / len(lage)
            if beste is None or kosten < beste[0]:
                beste = (kosten, lage)
        return sorted(beste[1])


class Spur:
    def __init__(self, name, programm, kanal, vol=100, pan=64, hall=40, chorus=0, bank=0):
        self.name = name
        self.programm = programm
        self.kanal = kanal
        self.vol = vol
        self.pan = pan
        self.hall = hall
        self.chorus = chorus
        self.bank = bank
        self.noten = []              # (tick, dauer, note, staerke)
        self.cc = []                 # (tick, controller, wert)


class Kontext:
    """Was ein Muster über den Abschnitt wissen muss."""

    def __init__(self, lied, start, takte, akkorde, name):
        self.lied = lied
        self.start = start
        self.takte = takte
        self.akkorde = akkorde        # Liste pro Takt: [(Akkord, versatz_ticks, länge_ticks), …]
        self.name = name
        self.takt = lied.takt_ticks

    def akkord_bei(self, tick_rel):
        t = tick_rel // self.takt
        t = min(max(t, 0), self.takte - 1)
        im = tick_rel - t * self.takt
        wahl = self.akkorde[t][0][0]
        for a, v, l in self.akkorde[t]:
            if v <= im:
                wahl = a
        return wahl

    def naechster_akkord(self, tick_rel):
        """Akkord nach dem aktuellen (für Annäherungstöne)."""
        aktuell = self.akkord_bei(tick_rel)
        for t in range(tick_rel // self.takt, self.takte):
            for a, v, l in self.akkorde[t]:
                if t * self.takt + v > tick_rel and a is not aktuell:
                    return a
        return self.lied._folge_akkord or aktuell


# ---------------------------------------------------------------------------------------------------------
# Muster
# ---------------------------------------------------------------------------------------------------------
def _raster(text):
    return text.replace(" ", "").replace("|", "")


class Drums:
    """Schlagzeug: Raster pro Instrument, zyklisch. fill = Raster für den letzten Takt (oder {takt: raster})."""

    def __init__(self, muster, fill=None, crash=True, staerke=1.0, nur=None):
        self.muster = {k: _raster(v) for k, v in muster.items()}
        if isinstance(fill, dict) and fill and all(isinstance(k, int) for k in fill):
            self.fills = {k: {i: _raster(r) for i, r in v.items()} for k, v in fill.items()}
        elif fill:
            self.fills = {-1: {k: _raster(v) for k, v in fill.items()}}
        else:
            self.fills = {}
        self.crash = crash
        self.staerke = staerke
        self.nur = nur

    def __call__(self, ctx, spur):
        schritte = ctx.lied.schritte
        for t in range(ctx.takte):
            if self.nur is not None and t not in self.nur:
                continue
            fill = self.fills.get(t) or (self.fills.get(-1) if t == ctx.takte - 1 else None)
            muster = dict(self.muster)
            if fill:
                muster.update(fill)
            for inst, r in muster.items():
                if not r:
                    continue
                for i in range(schritte):
                    pos = t * schritte + i
                    z = r[pos % len(r)] if not fill or inst not in fill else r[i % len(r)]
                    if z in STAERKE:
                        st = min(127, int(STAERKE[z] * self.staerke))
                        spur.noten.append((ctx.start + t * ctx.takt + i * SECH, SECH, DRUM[inst], st))
        if self.crash:
            spur.noten.append((ctx.start, SECH * 4, DRUM["c"], 112))
            if ctx.start > 0:
                spur.noten.append((ctx.start, SECH, DRUM["K"], 110))


class Bass:
    """Bass-Raster: R Grundton · 3 Terz · 5 Quinte · 7 Septime · O Oktave · L Quinte drunter · a/b Annäherung
    an den nächsten Akkord von oben/unten · - halten · . Pause. Großbuchstaben X = betont (nur R/O/5 via '!')."""

    def __init__(self, raster, unten=28, staerke=100, legato=0.92):
        self.raster = _raster(raster)
        self.unten = unten
        self.staerke = staerke
        self.legato = legato

    def __call__(self, ctx, spur):
        _pitch_raster(ctx, spur, self.raster, self.unten, self.staerke, self.legato)


def _pitch_raster(ctx, spur, raster, unten, staerke, legato):
    schritte = ctx.lied.schritte
    gesamt = ctx.takte * schritte
    laufend = None
    for i in range(gesamt):
        z = raster[i % len(raster)]
        tick = i * SECH
        if z == "-" and laufend is not None:
            laufend[1] += SECH
            continue
        if laufend is not None:
            spur.noten.append((ctx.start + laufend[0], max(30, int(laufend[1] * legato)), laufend[2], laufend[3]))
            laufend = None
        if z in ".-":
            continue
        a = ctx.akkord_bei(tick)
        if z in "R35 7":
            n = a.ton(z, unten)
        elif z == "O":
            n = a.tief(unten) + 12
        elif z == "L":
            n = a.tief(unten) - 5
            if n < unten - 5:
                n += 12
        elif z in "ab":
            nxt = ctx.naechster_akkord(tick)
            ziel = nxt.tief(unten)
            n = ziel + (1 if z == "a" else -1)
        elif z == "2":
            n = a.tief(unten) + 2
        elif z == "4":
            n = a.tief(unten) + 5
        elif z == "6":
            n = a.tief(unten) + (8 if 3 in a.intervalle else 9)
        else:
            continue
        st = staerke + (14 if (i % 4 == 0) else 0)
        laufend = [tick, SECH, n, min(127, st)]
    if laufend is not None:
        spur.noten.append((ctx.start + laufend[0], max(30, int(laufend[1] * legato)), laufend[2], laufend[3]))


class Akkorde:
    """Begleitung: X Akkord · x leise · D/U geschrammelt (ab/auf) · B nur Basston · - halten · . Pause."""

    def __init__(self, raster, lage=60, toene=None, staerke=88, legato=0.9, strum=14, oktave_drunter=False,
                 power=False):
        self.raster = _raster(raster)
        self.power = power
        self.lage = lage
        self.toene = toene
        self.staerke = staerke
        self.legato = legato
        self.strum = strum
        self.oktave_drunter = oktave_drunter

    def __call__(self, ctx, spur):
        schritte = ctx.lied.schritte
        gesamt = ctx.takte * schritte
        vorher = None
        laufend = None

        def raus(lf):
            tick, dauer, noten, st, art = lf
            for k, n in enumerate(noten):
                versatz = 0
                if art == "D":
                    versatz = k * self.strum
                elif art == "U":
                    versatz = (len(noten) - 1 - k) * self.strum
                spur.noten.append((ctx.start + tick + versatz, max(30, int(dauer * self.legato) - versatz), n,
                                   max(20, st - (k * 3 if art == "U" else 0))))

        for i in range(gesamt):
            z = self.raster[i % len(self.raster)]
            tick = i * SECH
            if z == "-" and laufend is not None:
                laufend[1] += SECH
                continue
            if laufend is not None:
                raus(laufend)
                laufend = None
            if z in ".-":
                continue
            a = ctx.akkord_bei(tick)
            if z == "B":
                noten = [a.tief(self.lage - 18)]
                st = self.staerke
            elif self.power:
                r = a.tief(self.lage - 6)
                noten = [r, r + 7, r + 12]
                st = self.staerke if z in "XDU" else int(self.staerke * 0.78)
            else:
                noten = a.stimmen(self.lage, self.toene, vorher)
                vorher = noten
                if self.oktave_drunter:
                    noten = [a.tief(self.lage - 24)] + noten
                st = self.staerke if z in "XDU" else int(self.staerke * 0.72)
                if i % 4 == 0 and z in "XD":
                    st += 8
            laufend = [tick, SECH, noten, min(127, st), z]
        if laufend is not None:
            raus(laufend)


class Arp:
    """Arpeggio: Ziffern 1–9 = Akkordtöne von unten (1 Grundton, 2 nächster …, über Oktaven weiter) · - · ."""

    def __init__(self, raster, lage=60, staerke=80, legato=0.95, toene=None):
        self.raster = _raster(raster)
        self.lage = lage
        self.staerke = staerke
        self.legato = legato
        self.toene = toene

    def __call__(self, ctx, spur):
        schritte = ctx.lied.schritte
        gesamt = ctx.takte * schritte
        laufend = None
        for i in range(gesamt):
            z = self.raster[i % len(self.raster)]
            tick = i * SECH
            if z == "-" and laufend is not None:
                laufend[1] += SECH
                continue
            if laufend is not None:
                spur.noten.append((ctx.start + laufend[0], max(30, int(laufend[1] * self.legato)), laufend[2], laufend[3]))
                laufend = None
            if not z.isdigit():
                continue
            a = ctx.akkord_bei(tick)
            basis = a.stimmen(self.lage, self.toene)
            k = int(z) - 1
            n = basis[k % len(basis)] + 12 * (k // len(basis))
            st = self.staerke + (10 if i % 4 == 0 else 0)
            laufend = [tick, SECH, n, min(127, st)]
        if laufend is not None:
            spur.noten.append((ctx.start + laufend[0], max(30, int(laufend[1] * self.legato)), laufend[2], laufend[3]))


class Flaeche:
    """Gehaltene Akkorde, wechseln mit den Akkorden."""

    def __init__(self, lage=60, toene=4, staerke=70, oktave=False):
        self.lage = lage
        self.toene = toene
        self.staerke = staerke
        self.oktave = oktave

    def __call__(self, ctx, spur):
        vorher = None
        for t in range(ctx.takte):
            for a, v, l in ctx.akkorde[t]:
                noten = a.stimmen(self.lage, self.toene, vorher)
                vorher = noten
                if self.oktave:
                    noten = noten + [noten[-1] + 12]
                for n in noten:
                    spur.noten.append((ctx.start + t * ctx.takt + v, l - 10, n, self.staerke))


class Linie:
    """Ausgeschriebene Stimme (Melodie, Gegenstimme, Riff). transponiert = Halbtöne."""

    def __init__(self, text, transponiert=0, staerke=96, legato=0.94, wiederholen=True):
        self.text = text
        self.transponiert = transponiert
        self.staerke = staerke
        self.legato = legato
        self.wiederholen = wiederholen

    def __call__(self, ctx, spur):
        noten, laenge = melodie(self.text, ctx.lied.schritte, ctx.name)
        ziel = ctx.takte * ctx.takt
        versatz = 0
        while versatz < ziel:
            for tick, dauer, ns, st in noten:
                if versatz + tick >= ziel:
                    break
                for n in ns:
                    s = {"!": 118, "?": 70}.get(st, self.staerke)
                    spur.noten.append((ctx.start + versatz + tick, max(30, int(dauer * self.legato)),
                                       n + self.transponiert, min(127, s)))
            versatz += laenge
            if not self.wiederholen or laenge == 0:
                break


def melodie(text, schritte, wo=""):
    """Melodie-Text → [(tick, dauer, [noten], betonung)], Gesamtlänge. Prüft die Taktstriche."""
    ergebnis = []
    pos = 0
    dauer = 4
    letzte_takt = 0
    for tok in text.split():
        if tok == "|":
            if pos % schritte:
                raise ValueError(f"{wo}: Taktstrich nach {pos} Sechzehnteln – Takt hat {schritte}")
            letzte_takt = pos
            continue
        betonung = ""
        if tok[-1] in "!?":
            betonung = tok[-1]
            tok = tok[:-1]
        if ":" in tok:
            name, d = tok.split(":")
            dauer = int(d)
        else:
            name = tok
        if name == "r":
            pos += dauer
            continue
        if name == "_":
            if not ergebnis:
                raise ValueError(f"{wo}: '_' ohne Note davor")
            t, du, ns, b = ergebnis[-1]
            ergebnis[-1] = (t, du + dauer * SECH, ns, b)
            pos += dauer
            continue
        noten = [note_zahl(n) for n in name.split("+")]
        ergebnis.append((pos * SECH, dauer * SECH, noten, betonung))
        pos += dauer
    if pos % schritte and "|" in text:
        raise ValueError(f"{wo}: Melodie endet mitten im Takt ({pos} Sechzehntel, Takt hat {schritte})")
    _ = letzte_takt
    return ergebnis, pos * SECH


def diatonisch(text, stufen, grundton, tonleiter="moll"):
    """Melodie-Text innerhalb der Tonleiter um `stufen` verschieben (z. B. -2 = Terz drunter)."""
    leiter = TONLEITERN[tonleiter]
    g = tonklasse(grundton)
    raus = []
    for tok in text.split():
        if tok == "|":
            raus.append(tok)
            continue
        roh = tok
        suffix = ""
        if roh[-1] in "!?":
            suffix = roh[-1]
            roh = roh[:-1]
        name, _, d = roh.partition(":")
        if name in ("r", "_"):
            raus.append(tok)
            continue
        neu = []
        for n in name.split("+"):
            z = note_zahl(n)
            rel = (z - g) % 12
            okt = (z - g) // 12
            if rel in leiter:
                idx = leiter.index(rel) + stufen
                o2 = okt + idx // 7
                ziel = g + 12 * o2 + leiter[idx % 7]
            else:
                ziel = z + (3 if stufen > 0 else -4)
            neu.append(NAMEN[ziel % 12] + str(ziel // 12 - 1))
        raus.append("+".join(neu) + (":" + d if d else "") + suffix)
    return " ".join(raus)


# ---------------------------------------------------------------------------------------------------------
# Lied
# ---------------------------------------------------------------------------------------------------------
class Lied:
    def __init__(self, id, titel, untertitel, bpm, tonart, thema, stimmung, takt=(4, 4), tonleiter="moll",
                 schwierigkeit=3, farbe="#f2a33a", lead="lead", bass="bass", seed=1):
        self.id = id
        self.titel = titel
        self.untertitel = untertitel
        self.bpm = bpm
        self.tonart = tonart
        self.tonleiter = tonleiter
        self.thema = thema
        self.stimmung = stimmung
        self.schwierigkeit = schwierigkeit
        self.farbe = farbe
        self.zaehler, self.nenner = takt
        self.schritte = self.zaehler * 16 // self.nenner           # Sechzehntel pro Takt
        self.takt_ticks = self.schritte * SECH
        self.spuren = {}
        self.pos = 0
        self.abschnitte = []                                       # (name, tick)
        self.lead = lead
        self.bass = bass
        self.zufall = random.Random(seed)
        self._folge_akkord = None
        self.vorschau = None                                       # Abschnittsname für die Vorschau
        self.akkord_log = []                                       # (tick, länge, Akkord) – für die Prüfung

    def spur(self, name, programm, kanal, **kw):
        self.spuren[name] = Spur(name, programm, kanal, **kw)
        return self.spuren[name]

    def _akkorde(self, text):
        takte = [t.strip() for t in text.strip().strip("|").split("|")]
        raus = []
        for t in takte:
            teile = t.split()
            if not teile:
                raise ValueError(f"Leerer Takt in {text!r}")
            n = len(teile)
            laenge = self.takt_ticks // n
            raus.append([(Akkord(a), k * laenge, laenge) for k, a in enumerate(teile)])
        return raus

    def abschnitt(self, name, akkorde, wdh=1, **teile):
        """Hängt einen Abschnitt an. akkorde: 'Dm | Bb C | …' (ein Eintrag pro Takt). teile: spur=Muster."""
        ak = self._akkorde(akkorde) * wdh
        ctx = Kontext(self, self.pos, len(ak), ak, name)
        self.abschnitte.append((name, self.pos))
        for t, takt in enumerate(ak):
            for a, v, l in takt:
                self.akkord_log.append((self.pos + t * self.takt_ticks + v, l, a))
        for spurname, muster in teile.items():
            if muster is None:
                continue
            if spurname not in self.spuren:
                raise KeyError(f"{self.id}: Spur {spurname!r} fehlt")
            liste = muster if isinstance(muster, (list, tuple)) else [muster]
            for m in liste:
                if isinstance(m, str):
                    m = Linie(m)
                m(ctx, self.spuren[spurname])
        self.pos += len(ak) * self.takt_ticks
        return ctx

    def pause(self, takte=1):
        self.pos += takte * self.takt_ticks

    # ---- Ausgabe ---------------------------------------------------------------------------------------
    def sekunden(self, tick):
        return tick * 60.0 / (self.bpm * PPQ)

    def laenge_s(self):
        return self.sekunden(self.pos) + 3.0

    def _menschlich(self, spur):
        """Leichte Lautstärke-Schwankung (nicht für die Spiel-Stimmen, die bleiben exakt im Raster)."""
        z = self.zufall
        raus = []
        for t, d, n, s in spur.noten:
            if spur.name in (self.lead, self.bass):
                raus.append((t, d, n, max(1, min(127, s + z.randint(-4, 4)))))
            else:
                raus.append((t + (z.randint(-4, 4) if spur.kanal != 9 else z.randint(-2, 2)), d, n,
                             max(1, min(127, s + z.randint(-7, 7)))))
        return sorted(raus)

    def midi(self, welche):
        """welche: 'band' (alles außer Melodie und Bass), 'lead', 'bass', 'alle'."""
        spuren = []
        for name, sp in self.spuren.items():
            if welche == "alle" or (welche == "lead" and name == self.lead) or (welche == "bass" and name == self.bass) \
                    or (welche == "band" and name not in (self.lead, self.bass)):
                spuren.append(sp)
        return midi_datei(self, spuren)

    def chart(self):
        def noten_von(name):
            sp = self.spuren.get(name)
            if not sp:
                return []
            raus = []
            for t, d, n, s in sorted(sp.noten):
                raus.append([round(self.sekunden(t), 4), round(self.sekunden(d / 0.94 if d else 0), 4), n])
            # Doppelgriffe: nur die oberste Note zählt
            fertig = []
            for x in raus:
                if fertig and abs(fertig[-1][0] - x[0]) < 0.01:
                    if x[2] > fertig[-1][2]:
                        fertig[-1] = x
                    continue
                fertig.append(x)
            return fertig
        beat = 60.0 / self.bpm * (4 / self.nenner)
        if self.nenner == 8:
            beat = 60.0 / self.bpm * 1.5          # 6/8: punktierte Viertel als Schlag
        takt_s = self.sekunden(self.takt_ticks)
        return {
            "id": self.id, "titel": self.titel, "untertitel": self.untertitel, "bpm": self.bpm,
            "takt": [self.zaehler, self.nenner], "tonart": self.tonart, "tonleiter": self.tonleiter,
            "thema": self.thema, "stimmung": self.stimmung, "schwierigkeit": self.schwierigkeit, "farbe": self.farbe,
            "laenge": round(self.laenge_s(), 2), "ende": round(self.sekunden(self.pos), 3),
            "schlag": round(beat, 5), "takt_s": round(takt_s, 5),
            "abschnitte": [[n, round(self.sekunden(t), 3)] for n, t in self.abschnitte],
            "lead": noten_von(self.lead), "bass": noten_von(self.bass),
            "vorschau": next((round(self.sekunden(t), 3) for n, t in self.abschnitte if n == self.vorschau), None),
        }


# ---------------------------------------------------------------------------------------------------------
# MIDI-Datei (Format 1)
# ---------------------------------------------------------------------------------------------------------
def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _spur_bytes(ereignisse):
    ereignisse.sort(key=lambda e: (e[0], e[1]))
    out = bytearray()
    zuletzt = 0
    for tick, _prio, daten in ereignisse:
        out += _vlq(max(0, tick - zuletzt)) + daten
        zuletzt = max(zuletzt, tick)
    out += b"\x00\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(out)) + bytes(out)


def midi_datei(lied, spuren):
    tempo = int(60_000_000 / lied.bpm)
    kopf = [(0, 0, b"\xFF\x51\x03" + tempo.to_bytes(3, "big")),
            (0, 0, bytes([0xFF, 0x58, 0x04, lied.zaehler, {4: 2, 8: 3, 2: 1}[lied.nenner], 24, 8]))]
    for name, tick in lied.abschnitte:
        t = name.encode("utf-8")[:60]
        kopf.append((tick, 1, b"\xFF\x06" + _vlq(len(t)) + t))
    teile = [_spur_bytes(kopf)]
    for sp in spuren:
        k = sp.kanal
        ev = [(0, 0, bytes([0xB0 | k, 0, sp.bank])), (0, 0, bytes([0xC0 | k, sp.programm])),
              (0, 0, bytes([0xB0 | k, 7, sp.vol])), (0, 0, bytes([0xB0 | k, 10, sp.pan])),
              (0, 0, bytes([0xB0 | k, 91, sp.hall])), (0, 0, bytes([0xB0 | k, 93, sp.chorus]))]
        for t, c, w in sp.cc:
            ev.append((t, 2, bytes([0xB0 | k, c, w])))
        for t, d, n, s in lied._menschlich(sp):
            if not 0 <= n <= 127:
                continue
            t = max(0, t)
            ev.append((t, 3, bytes([0x90 | k, n, max(1, s)])))
            ev.append((t + max(1, d), 1, bytes([0x80 | k, n, 0])))
        teile.append(_spur_bytes(ev))
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(teile), PPQ) + b"".join(teile)


def notenname(n):
    return NAMEN[n % 12]
