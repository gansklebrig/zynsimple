# -*- coding: utf-8 -*-
"""
Tastenbelegung der Zynthian-Tasten – gemeinsam für Mischer (ZynSimple), DJ-Pult und Barden Beats.

Gespeichert wird, welche Funktion auf welcher Taste liegt: {"dj": {"REC": "STOP", "STOP": "REC"}, …}
(echte Taste → Funktion; nur was vom Standard abweicht). Umbelegen = zwei Tasten tauschen,
so ist jede Funktion immer genau einmal erreichbar. ALT- und Halten-Belegungen wandern mit.

Dieselbe Datei liest auch Barden Beats (zynthian/tastenbelegung.py dort ist eine Kopie).
"""
import json
import os
import time

DATEI = "/zynthian/zynthian-my-data/tasten.json"

# LED-Nummer jeder Taste am V5 (gleich in ZynSimple, DJ-Helfer und Barden Beats)
LED_NR = {"MENU": 0, "MIXER": 1, "CTRL": 2, "ZS3": 3, "F1": 4, "PAD": 5, "TEMPO": 6, "ALT": 7, "REC": 8, "STOP": 9,
          "PLAY": 10, "F2": 11, "F3": 12, "SEL": 13, "UP": 14, "BACK": 15, "LEFT": 16, "DOWN": 17, "RIGHT": 18, "F4": 19}

# So sitzen die Tasten am Gerät (für die Auswahl am Display): Zeilen von oben nach unten
LAYOUT = [["MENU", "MIXER", "CTRL", "ZS3"], ["ALT", "TEMPO", "PAD", "F1"], ["REC", "STOP", "PLAY", "F2"],
          ["BACK", "UP", "SEL", "F3"], ["LEFT", "DOWN", "RIGHT", "F4"]]

ANZEIGE = {"MENU": "MENU", "MIXER": "MIXER", "CTRL": "CTRL", "ZS3": "ZS3", "ALT": "ALT", "TEMPO": "METRONOM",
           "PAD": "PAD", "REC": "REC", "STOP": "STOP", "PLAY": "PLAY", "BACK": "BACK", "SEL": "SEL",
           "UP": "▲", "DOWN": "▼", "LEFT": "◀", "RIGHT": "▶", "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4"}

# Welche Tasten je Modus umbelegt werden dürfen (BACK bleibt immer BACK: Rückweg und System-Menü)
TASTEN = {
    "mischer": ["F1", "F2", "F3", "F4", "UP", "DOWN", "LEFT", "RIGHT", "REC", "PLAY", "STOP", "TEMPO"],
    "dj": ["MENU", "MIXER", "CTRL", "ZS3", "ALT", "TEMPO", "PAD", "F1", "F2", "F3", "F4", "REC", "STOP", "PLAY",
           "UP", "DOWN", "LEFT", "RIGHT", "SEL"],
    "barden": ["MENU", "MIXER", "CTRL", "ZS3", "ALT", "TEMPO", "PAD", "F1", "F2", "F3", "F4", "REC", "STOP", "PLAY",
               "UP", "DOWN", "LEFT", "RIGHT", "SEL"],
}

MODUS_NAME = {"mischer": "Mischer", "dj": "DJ-Pult", "barden": "Barden Beats"}

# Was die Funktionen tun: (kurz, ALT, halten)
FUNKTIONEN = {
    "mischer": {
        "F1": ("Effekt 1 an/aus", "Szene 1", "Regler von Effekt 1"),
        "F2": ("Effekt 2 an/aus", "Szene 2", "Regler von Effekt 2"),
        "F3": ("Effekt 3 an/aus", "Szene 3", "Regler von Effekt 3"),
        "F4": ("Effekt 4 an/aus", "Szene 4", "Regler von Effekt 4"),
        "UP": ("Tiefe hoch", "", ""), "DOWN": ("Tiefe runter", "", ""),
        "LEFT": ("Kanal links", "", ""), "RIGHT": ("Kanal rechts", "", ""),
        "REC": ("❄ Freeze an/aus", "", "Freeze, solange gedrückt"),
        "PLAY": ("↯ Echo-Wurf", "", ""),
        "STOP": ("Panik (Hall, Echos, Töne aus)", "", ""),
        "TEMPO": ("Tempo tippen", "", ""),
    },
    "dj": {
        "MENU": ("☰ DJ-Menü", "", "zu Barden Beats"),
        "MIXER": ("Ebene wechseln", "", ""),
        "CTRL": ("Vorhören A → B → aus", "", ""),
        "ZS3": ("große Bibliothek", "", ""),
        "ALT": ("zweite Belegung (halten)", "", ""),
        "TEMPO": ("Tempo tippen", "Sync", ""),
        "PAD": ("Handpan im Mix an/aus", "", ""),
        "F1": ("Stem/Loop/Handpan 1", "Deck B", ""), "F2": ("Stem/Loop/Effekt 2", "Deck B", ""),
        "F3": ("Stem/Loop/Effekt 3", "Deck B", ""), "F4": ("Stem/Loop/Durchsage 4", "Deck B", ""),
        "REC": ("Set aufnehmen", "", ""),
        "STOP": ("Panik (Effekte, Filter aus)", "", "ausschalten (3 s)"),
        "PLAY": ("Auto-DJ an/aus", "", ""),
        "UP": ("Titel hoch", "★ +1", ""), "DOWN": ("Titel runter", "★ −1", ""),
        "LEFT": ("Bereich links", "Ebene zurück", ""), "RIGHT": ("Bereich rechts", "Ebene vor", ""),
        "SEL": ("Titel ins freie Deck laden", "", ""),
    },
    "barden": {
        "MENU": ("Modus/Menü", "Optionen", "System"),
        "MIXER": ("Reglerbank wechseln", "", "Bank zurück"),
        "CTRL": ("Mischpult", "frei belegbar", ""),
        "ZS3": ("Spuren der Stimmung", "frei belegbar", ""),
        "ALT": ("zweite Belegung (halten)", "", ""),
        "TEMPO": ("Tempo", "frei belegbar", ""),
        "PAD": ("frei belegbar", "Drumpad", ""),
        "F1": ("Auswahl 1", "zweite Reihe 1", ""), "F2": ("Auswahl 2", "zweite Reihe 2", ""),
        "F3": ("Auswahl 3", "zweite Reihe 3", ""), "F4": ("Auswahl 4", "zweite Reihe 4", ""),
        "REC": ("frei belegbar", "frei belegbar", ""),
        "STOP": ("frei belegbar", "frei belegbar", "Panik"),
        "PLAY": ("frei belegbar", "frei belegbar", ""),
        "UP": ("hoch", "", ""), "DOWN": ("runter", "", ""), "LEFT": ("links", "", ""), "RIGHT": ("rechts", "", ""),
        "SEL": ("auswählen", "", ""),
    },
}

_cache = {"mt": None, "d": {}, "t": 0.0, "karten": {}}


def laden():
    if time.monotonic() - _cache["t"] < 1.0 and _cache["mt"] is not None:
        return _cache["d"]
    _cache["t"] = time.monotonic()
    try:
        mt = os.path.getmtime(DATEI)
    except OSError:
        if _cache["mt"] is not None or _cache["d"]:
            _cache.update(mt=None, d={}, karten={})
        return {}
    if mt != _cache["mt"]:
        try:
            with open(DATEI, encoding="utf-8") as f:
                d = json.load(f)
            _cache.update(mt=mt, d=d if isinstance(d, dict) else {}, karten={})
        except Exception:
            _cache.update(mt=mt, d={}, karten={})
    return _cache["d"]


def karte(modus):
    """Vollständige Zuordnung echte Taste → Funktion (Standard: jede Taste ist sie selbst)."""
    laden()
    if modus in _cache["karten"]:
        return dict(_cache["karten"][modus])
    k = _karte(modus)
    _cache["karten"][modus] = k
    return dict(k)


def _karte(modus):
    k = {t: t for t in TASTEN.get(modus, [])}
    for phys, log_ in (laden().get(modus) or {}).items():
        if phys in k and log_ in k:
            k[phys] = log_
    # Sicherheitsnetz: jede Funktion genau einmal, sonst Standard
    if sorted(k.values()) != sorted(k.keys()):
        return {t: t for t in TASTEN.get(modus, [])}
    return k


def funktion(modus, phys):
    """Welche Funktion löst die echte Taste aus?"""
    return karte(modus).get(phys, phys)


def taste(modus, logisch):
    """Auf welcher echten Taste liegt die Funktion?"""
    for p, l in karte(modus).items():
        if l == logisch:
            return p
    return logisch


def _speichern(modus, k):
    d = dict(laden())
    d[modus] = {p: l for p, l in k.items() if p != l}
    os.makedirs(os.path.dirname(DATEI), exist_ok=True)
    tmp = DATEI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATEI)
    _cache.update(mt=None, t=0.0, karten={})


def tauschen(modus, logisch, ziel_phys):
    """Funktion „logisch“ auf die echte Taste „ziel_phys“ legen – was dort lag, wandert auf den alten Platz."""
    k = karte(modus)
    if logisch not in k or ziel_phys not in k:
        raise ValueError("Diese Taste lässt sich hier nicht umbelegen")
    alt_phys = taste(modus, logisch)
    k[alt_phys], k[ziel_phys] = k[ziel_phys], logisch
    _speichern(modus, k)
    return k


def zuruecksetzen(modus):
    _speichern(modus, {t: t for t in TASTEN.get(modus, [])})


def liste(modus):
    """Für die Anzeige: [{funktion, taste, kurz, alt, halten, geaendert}] in Geräte-Reihenfolge der Funktionen."""
    f = FUNKTIONEN.get(modus, {})
    out = []
    for log_ in TASTEN.get(modus, []):
        kurz, alt, halten = f.get(log_, ("", "", ""))
        p = taste(modus, log_)
        out.append({"funktion": log_, "name": ANZEIGE.get(log_, log_), "taste": p, "taste_name": ANZEIGE.get(p, p),
                    "kurz": kurz, "alt": alt, "halten": halten, "geaendert": p != log_})
    return out
