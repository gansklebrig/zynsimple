# -*- coding: utf-8 -*-
"""
Bard Hero – aus den Noten eines Liedes die spielbaren Noten machen.

Hero-Modus:   5 Spuren (Leicht 3, Mittel 4). Die Spur folgt der Melodie – höher = weiter rechts.
Barden-Modus: die Spuren sind eine Klaviatur (C bis H) – man spielt die echten Töne, Oktave egal.
Stufen dünnen die Noten aus: Leicht nur die wichtigen, Meister jede einzelne.
"""
import json
import os

STUFEN = ["leicht", "mittel", "schwer", "meister"]
STUFEN_NAME = {"leicht": "Leicht", "mittel": "Mittel", "schwer": "Schwer", "meister": "Meister"}
# kleinster Abstand zwischen zwei Noten (s) und Spuren im Hero-Modus
ABSTAND = {"leicht": 0.42, "mittel": 0.22, "schwer": 0.12, "meister": 0.0}
SPUREN = {"leicht": 3, "mittel": 4, "schwer": 5, "meister": 5}
# Bauformen der Controller (Hero-Modus)
FORMEN = {
    "reihe5": {"name": "5 Tasten in einer Reihe", "kurz": "5 Tasten", "tasten": 5},
    "reihe6": {"name": "6 Tasten in einer Reihe", "kurz": "6 Tasten", "tasten": 6},
    "3x2": {"name": "6 Tasten: 3 oben, 3 unten", "kurz": "3 + 3 Tasten", "tasten": 6},
}


def spuren_anzahl(form, stufe):
    """Wie viele Spuren der Hero-Modus bei dieser Bauform und Stufe nutzt."""
    if form == "3x2":
        return 3 if stufe == "leicht" else 6          # Leicht: nur die untere Reihe
    t = FORMEN.get(form, FORMEN["reihe5"])["tasten"]
    return min(t, {"leicht": 3, "mittel": 4, "schwer": 5, "meister": 6}[stufe])
FENSTER = {"leicht": 0.125, "mittel": 0.105, "schwer": 0.095, "meister": 0.085}   # Trefferfenster ± s
# deutsche Notennamen (H statt B, B statt Bb)
NAMEN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "H"]
NAMEN_B = ["C", "Des", "D", "Es", "E", "F", "Ges", "G", "As", "A", "B", "H"]


def grundton(tonart):
    """'Bb' / 'F#m' / 'Em' → Tonklasse (englische Schreibweise wie in den Liedern)."""
    t = tonart.rstrip("m") or "C"
    pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(t[0].upper(), 0)
    for z in t[1:]:
        pc += 1 if z == "#" else (-1 if z == "b" else 0)
    return pc % 12


class Note:
    __slots__ = ("t", "dauer", "spur", "ton", "insp", "phrase", "status", "halten_bis", "gehalten", "punkte_halten")

    def __init__(self, t, dauer, spur, ton):
        self.t = t
        self.dauer = dauer
        self.spur = spur
        self.ton = ton
        self.insp = False
        self.phrase = -1
        self.status = 0            # 0 offen · 1 getroffen · 2 verpasst
        self.halten_bis = 0.0
        self.gehalten = False
        self.punkte_halten = 0.0


def laden(ordner):
    with open(os.path.join(ordner, "chart.json"), encoding="utf-8") as f:
        return json.load(f)


def _ausduennen(noten, stufe, schlag):
    """Noten für die Stufe auswählen: zu dichte Noten fallen weg, betonte bleiben."""
    abstand = ABSTAND[stufe]
    if abstand <= 0:
        return list(noten)
    raus = []
    for n in noten:
        t, d, p = n
        if raus and t - raus[-1][0] < abstand - 1e-3:
            # die wichtigere behalten: die auf dem Schlag bzw. die längere
            alt = raus[-1]
            def gewicht(x):
                pos = (x[0] / schlag) % 1.0
                return (2 if min(pos, 1 - pos) < 0.04 else (1 if abs(pos - 0.5) < 0.04 else 0)) + min(x[1], 1.0)
            if gewicht(n) > gewicht(alt) + 0.2:
                raus[-1] = n
            continue
        raus.append(n)
    if stufe == "leicht":
        # gleiche Töne direkt hintereinander zusammenfassen
        dicht = []
        for n in raus:
            if dicht and dicht[-1][2] == n[2] and n[0] - dicht[-1][0] < 0.6:
                continue
            dicht.append(n)
        raus = dicht
    return raus


def _hero_spuren(noten, anzahl):
    """Melodie → Spuren. Pro Phrase wird der Tonumfang auf die Spuren verteilt, Richtung bleibt erhalten."""
    if not noten:
        return []
    spuren = []
    # Phrasen: Lücken über 0.6 s trennen
    phrasen = [[noten[0]]]
    for a, b in zip(noten, noten[1:]):
        if b[0] - (a[0] + a[1]) > 0.6 or len(phrasen[-1]) >= 16:
            phrasen.append([])
        phrasen[-1].append(b)
    for ph in phrasen:
        toene = sorted(set(p for _, _, p in ph))
        if len(toene) <= anzahl:
            # gleichmäßig verteilen, mittig
            versatz = (anzahl - len(toene)) // 2
            karte = {t: versatz + i for i, t in enumerate(toene)}
            if len(toene) == 1:
                karte = {toene[0]: anzahl // 2}
        else:
            lo, hi = toene[0], toene[-1]
            karte = {t: int(round((t - lo) / max(1, hi - lo) * (anzahl - 1))) for t in toene}
        vorher = None
        for t, d, p in ph:
            s = karte[p]
            # verschiedene Töne nacheinander sollen nicht auf derselben Spur landen
            if vorher is not None and p != vorher[0] and s == vorher[1]:
                s = min(anzahl - 1, s + 1) if p > vorher[0] else max(0, s - 1)
            spuren.append(s)
            vorher = (p, s)
    return spuren


def bauen(chart, teil="lead", modus="hero", stufe="mittel", anzahl=None):
    """→ (noten, spur_namen)"""
    roh = [tuple(x) for x in chart.get(teil, [])]
    schlag = chart.get("schlag", 0.5)
    roh = _ausduennen(roh, stufe, schlag)
    if modus == "barde":
        # Barden-Modus: Spuren wie eine Klaviatur (eine Oktave, C bis H) – die Note fällt auf ihre Taste
        b_vorz = "b" in chart.get("tonart", "") or chart.get("tonart") in ("F", "Dm", "Gm", "Cm")
        namen = list(NAMEN_B if b_vorz else NAMEN)
        noten = [Note(t, d, p % 12, p) for t, d, p in roh]
    else:
        anzahl = anzahl or SPUREN[stufe]
        sp = _hero_spuren(roh, anzahl)
        noten = [Note(t, d, s, p) for (t, d, p), s in zip(roh, sp)]
        namen = None
    # Haltenoten: lang genug, und genug Platz bis zur nächsten
    for a, b in zip(noten, noten[1:] + [None]):
        frei = (b.t - a.t) if b else a.dauer
        if a.dauer >= 0.42 and frei >= 0.42:
            a.halten_bis = a.t + min(a.dauer, frei - 0.08) * 0.95
    _inspiration(noten, schlag)
    return noten, namen


def _inspiration(noten, schlag):
    """Etwa jede vierte Phrase (ab 10 s) leuchtet golden – ohne Fehler gespielt füllt sie die Inspiration."""
    if not noten:
        return
    nr = 0
    start = 0
    for i in range(1, len(noten) + 1):
        ende = i == len(noten) or noten[i].t - noten[i - 1].t > max(2 * schlag, 0.7) or i - start >= 12
        if ende:
            if i - start >= 4 and noten[start].t > 10 and nr % 4 == 1:
                for n in noten[start:i]:
                    n.insp = True
                    n.phrase = nr
            nr += 1
            start = i
