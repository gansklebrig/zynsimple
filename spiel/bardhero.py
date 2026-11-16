#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bard Hero – Rhythmusspiel für den Zynthian.

Mit der Keytar (oder jedem MIDI-Gerät, den Zynthian-Tasten, Tastatur oder Gamepad) spielt man die Melodie
eines Liedes, die Band spielt den Rest. Daneben gegriffen → die Melodie verstummt.

  Solo     ein Spieler
  Duell    zwei Spieler, gleiche Melodie, wer hat mehr Punkte?
  Duett    Spieler 1 Melodie, Spieler 2 Bass

Spielarten: Hero (5 Tasten, C D E F G) · Barde (echte Töne, Klaviatur)
Stufen:     Leicht · Mittel · Schwer · Meister

Bedienung im Menü: Keytar C ▲  D ▼  E ◀  F ▶  G ✓  A zurück · Zynthian: Pfeile, SEL, BACK, Drehregler
                   Tastatur: Pfeile, Enter, Esc · Touch: antippen
"""
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HIER, os.path.join(HIER, "lieder")]
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

import chart  # noqa: E402
import eingabe  # noqa: E402
import grafik as g  # noqa: E402
from ton import ZUSTAND, ZUSTAND_DATEI, STEUER  # noqa: E402

DATEN = os.environ.get("BH_DATEN", "/zynthian/zynthian-my-data/bardhero")
EINST_DATEI = os.path.join(DATEN, "einstellungen.json")
REKORD_DATEI = os.path.join(DATEN, "rekorde.json")
BEFEHL = "/usr/local/bin/bard-hero"
VERSION = "1.1"

STANDARD = {
    "grafik": 2, "fps": 60, "tempo": "normal", "versatz_ms": 0, "durchfallen": False, "insp_auto": True,
    "ausgabe": "auto",
    "pegel": {"master": 0.9, "musik": 1.0, "lead": 1.0, "bass": 1.0, "mic": 0.0, "hall": 0.25, "ducking": 0.5,
              "sfx": 0.7, "mic_kanal": 1},
    "spieler": [{"modus": "hero", "stufe": "leicht"}, {"modus": "hero", "stufe": "leicht"}],
    "belegung": {},
}
SICHT = {"langsam": 1.8, "normal": 1.35, "schnell": 1.0}
MODUS_NAME = {"hero": "Hero · Tasten", "barde": "Barde · echte Töne"}


def einstellungen_laden():
    e = json.loads(json.dumps(STANDARD))
    try:
        with open(EINST_DATEI, encoding="utf-8") as f:
            neu = json.load(f)
        for k, v in neu.items():
            if isinstance(v, dict) and isinstance(e.get(k), dict):
                e[k].update(v)
            else:
                e[k] = v
    except (OSError, ValueError):
        pass
    return e


def speichern(pfad, daten):
    try:
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad + ".neu", "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=1)
        os.replace(pfad + ".neu", pfad)
    except OSError as e:
        print("Speichern ging nicht:", e, file=sys.stderr)


def tonart_text(t):
    """'Bb' → 'B-Dur', 'F#m' → 'Fis-Moll' (deutsche Namen)."""
    moll = t.endswith("m")
    t = t.rstrip("m")
    namen = {"Bb": "B", "B": "H", "Eb": "Es", "Ab": "As", "Db": "Des", "F#": "Fis", "C#": "Cis", "G#": "Gis"}
    n = namen.get(t, t)
    return (n.lower() + "-Moll") if moll else (n + "-Dur")


def python_mit(*module):
    for py in ("/usr/bin/python3", "/zynthian/venv/bin/python3", sys.executable):
        if os.path.exists(py) and subprocess.call([py, "-c", "import " + ",".join(module)],
                                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return py
    return sys.executable


# ---------------------------------------------------------------------------------------------------------
# Verbindung zur Ton-Maschine
# ---------------------------------------------------------------------------------------------------------
class Ton:
    def __init__(self):
        self.proc = None
        self.sock = __import__("socket").socket(__import__("socket").AF_UNIX, __import__("socket").SOCK_DGRAM)
        self.nr = 0
        self.letzter_zaehler = -1
        self.still_seit = time.monotonic()
        self.z = None
        self.starten()

    def starten(self):
        if os.environ.get("BH_TON_EXTERN"):
            return
        py = python_mit("numpy", "jack") if not os.environ.get("BH_TON") == "sdl" else python_mit("numpy", "pygame")
        try:
            self.proc = subprocess.Popen([py, os.path.join(HIER, "ton.py")], start_new_session=False)
        except OSError as e:
            print("Ton-Maschine startet nicht:", e, file=sys.stderr)
        self.still_seit = time.monotonic()

    def cmd(self, **k):
        try:
            self.sock.sendto(json.dumps(k).encode("utf-8"), STEUER)
        except OSError:
            pass

    def lesen(self):
        try:
            with open(ZUSTAND_DATEI, "rb") as f:
                d = f.read(ZUSTAND.size)
            if len(d) == ZUSTAND.size:
                self.z = ZUSTAND.unpack(d)
        except OSError:
            pass
        jetzt = time.monotonic()
        if self.z and self.z[0] != self.letzter_zaehler:
            self.letzter_zaehler = self.z[0]
            self.still_seit = jetzt
        elif jetzt - self.still_seit > 6 and self.proc is not None and self.proc.poll() is not None:
            print("Ton-Maschine neu gestartet", file=sys.stderr)
            self.starten()
        return self.z

    @property
    def bereit(self):
        return self.z is not None and time.monotonic() - self.still_seit < 2

    def rate(self):
        return self.z[5] if self.z and self.z[5] else 48000

    def geladen(self):
        return self.z[4] if self.z else 0

    def spielt(self):
        return bool(self.z and self.z[3])

    def liedzeit(self, mono=None):
        if not self.z:
            return 0.0
        mono = time.monotonic() if mono is None else mono
        if not self.z[3]:
            return self.z[1]
        return self.z[1] + (mono - self.z[2])

    def mic(self):
        return self.z[6] if self.z else 0.0

    def aus(self):
        return self.z[7] if self.z else 0.0

    def ende(self):
        self.cmd(cmd="ende")
        if self.proc:
            try:
                self.proc.wait(2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---------------------------------------------------------------------------------------------------------
# Spieler
# ---------------------------------------------------------------------------------------------------------
class Spieler:
    def __init__(self, nr, modus, stufe, teil="lead", geraete=None, form="reihe5", haupt=None):
        self.form = form                  # Bauform des Controllers (Hero): reihe5 · reihe6 · 3x2
        self.haupt = haupt                # Gerät, mit dem sich der Spieler gemeldet hat
        self.nr = nr
        self.modus = modus
        self.stufe = stufe
        self.teil = teil
        self.geraete = geraete            # None = alle Eingaben
        self.noten = []
        self.namen = None
        self.bahn = None
        self.idx = 0
        self.punkte = 0
        self.combo = 0
        self.max_combo = 0
        self.getroffen = 0
        self.perfekt = 0
        self.verpasst = 0
        self.fehlgriffe = 0
        self.insp = 0.0
        self.insp_aktiv = False
        self.publikum = 0.6
        self.gedrueckt = set()
        self.ok = True
        self.phrase_kaputt = set()
        self.letzte_drueck = {}
        self.fehl_anzeige = 0.0
        self.text = []                    # [(text, farbe, bis)]
        self.ausgebuht = False
        self.punkte_float = 0.0

    def kopie(self):
        """Frischer Spieler mit gleichen Einstellungen (Neustart, nächstes Lied)."""
        return Spieler(self.nr, self.modus, self.stufe, self.teil, self.geraete, self.form, self.haupt)

    @property
    def multi(self):
        m = 1 + min(3, self.combo // 10)
        return m * (2 if self.insp_aktiv else 1)

    def anzahl(self):
        return sum(1 for _ in self.noten)

    def quote(self):
        n = self.getroffen + self.verpasst
        return self.getroffen / n if n else 0.0

    def sterne(self):
        q = self.quote()
        return 5 if q >= 0.95 else 4 if q >= 0.85 else 3 if q >= 0.7 else 2 if q >= 0.5 else 1


# ---------------------------------------------------------------------------------------------------------
# Menü-Baustein
# ---------------------------------------------------------------------------------------------------------
class Menue:
    def __init__(self, eintraege, wahl=0):
        self.e = eintraege                # [(schlüssel, text, wert_oder_None)]
        self.wahl = wahl
        self.rects = []

    def nav(self, n):
        if n == "hoch":
            self.wahl = (self.wahl - 1) % len(self.e)
        elif n == "runter":
            self.wahl = (self.wahl + 1) % len(self.e)
        elif isinstance(n, tuple) and n[0] == "dreh":
            self.wahl = max(0, min(len(self.e) - 1, self.wahl + (1 if n[1] > 0 else -1)))

    def tipp(self, pos):
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                self.wahl = i
                return True
        return False

    @property
    def key(self):
        return self.e[self.wahl][0]

    def zeichnen(self, s, rect, groesse=None, mit_pfeilen=False):
        x, y, w, h = rect
        n = len(self.e)
        zh = min(h / max(1, n), (groesse or h / 7) * 1.9)
        gr = groesse or int(min(zh * 0.42, h * 0.07))
        self.rects = []
        for i, (k, t, v) in enumerate(self.e):
            r = pygame.Rect(x, y + i * zh + zh * 0.08, w, zh * 0.84)
            an = i == self.wahl
            g.rrect(s, (52, 36, 18) if an else (24, 18, 14), r, int(zh * 0.25))
            g.rrect(s, g.GOLD if an else (60, 46, 34), r, int(zh * 0.25), 3 if an else 1)
            if v is None:
                g.text_zeigen(s, t, gr, r.center, g.GOLD2 if an else g.CHAMP)
            else:
                wert = f"◀ {v} ▶" if an and mit_pfeilen else str(v)
                gz = gr
                while gz > gr * 0.6 and g.schrift(gz).size(t)[0] + g.schrift(gz).size(wert)[0] + gz * 3 > r.w:
                    gz -= 1
                g.text_zeigen(s, t, gz, (r.x + gr, r.centery), g.GOLD2 if an else g.CHAMP, "links")
                g.text_zeigen(s, wert, gz, (r.right - gr, r.centery), g.GLUT if an else g.TX2, "rechts")
            self.rects.append(r)


FORM_WAHL = [("keytar", "Keytar / Keyboard (C D E F G)"), ("reihe5", "5 Tasten in einer Reihe"),
             ("3x2", "6 Tasten: 3 oben, 3 unten"), ("reihe6", "6 Tasten in einer Reihe")]
FORM_TEXT = {"keytar": "C D E F G", "reihe5": "5 Tasten", "reihe6": "6 Tasten", "3x2": "3 oben + 3 unten"}
SPALTE = ["links", "Mitte", "rechts"]


def tasten_text(form, i):
    """Welche Taste ist gemeint? (für das Anlernen)"""
    if form == "3x2":
        return f"{'obere' if i >= 3 else 'untere'} Reihe, {SPALTE[i % 3]}"
    return f"Taste {i + 1} von links"


def zeichne_controller(s, mitte, u, form, aktiv=None, fertig=-1, gedrueckt=()):
    """Bauform des Controllers als kleine Zeichnung. aktiv = Taste, die gerade gemeint ist."""
    cx, cy = mitte
    if form == "3x2":
        rahmen = pygame.Rect(0, 0, u * 3.6, u * 1.75)
        rahmen.center = (cx, cy)
        g.rrect(s, (30, 22, 16), rahmen, int(u * 0.25))
        for i in range(6):
            oben = i >= 3
            r = pygame.Rect(0, 0, u * 0.95, u * 0.62)
            r.center = (cx + (i % 3 - 1) * u * 1.1, cy + (-u * 0.38 if oben else u * 0.38))
            grund = g.KOHLE if oben else g.ELFENBEIN
            rand = g.ORANGE if oben else g.GOLD
            if i <= fertig or i in gedrueckt:
                grund = g.misch(grund, rand, 0.65)
            if i == aktiv:
                g.leuchten(s, r.center, u * 0.9, rand, 0.9)
            g.rrect(s, grund, r, int(u * 0.12))
            g.rrect(s, rand, r, int(u * 0.12), 4 if i == aktiv else 2)
        return
    if form in ("reihe5", "reihe6"):
        n = 5 if form == "reihe5" else 6
        rahmen = pygame.Rect(0, 0, u * (n * 0.9 + 0.5), u * 1.1)
        rahmen.center = (cx, cy)
        g.rrect(s, (30, 22, 16), rahmen, int(u * 0.25))
        for i in range(n):
            x = cx + (i - (n - 1) / 2) * u * 0.9
            c = g.SPUR_FARBEN[i]
            an = i <= fertig or i in gedrueckt or i == aktiv
            if i == aktiv:
                g.leuchten(s, (x, cy), u * 0.8, c, 0.9)
            pygame.draw.circle(s, c if an else g.heller(c, 0.35), (int(x), int(cy)), int(u * 0.33))
            pygame.draw.circle(s, g.heller(c, 0.8), (int(x), int(cy)), int(u * 0.33), 2)
        return
    # Keytar / Keyboard: eine Oktave, C bis G farbig
    w = u * 0.5
    links = cx - 4 * w
    for k in range(8):
        r = pygame.Rect(links + k * w, cy - u * 0.6, w - 2, u * 1.2)
        c = g.SPUR_FARBEN[k] if k < 5 else g.ELFENBEIN
        g.rrect(s, g.misch(g.ELFENBEIN, c, 0.55 if k < 5 else 0), r, 4)
        if k < 5:
            g.text_zeigen(s, "CDEFG"[k], int(u * 0.3), (r.centerx, r.bottom - u * 0.2), g.SCHWARZ, schatten=False)
    for k in (0, 1, 3, 4, 5):
        r = pygame.Rect(links + (k + 1) * w - w * 0.3, cy - u * 0.6, w * 0.6, u * 0.7)
        g.rrect(s, (20, 14, 10), r, 3)


HINWEIS = "Keytar: C ▲  D ▼  E ◀  F ▶  G ✓  A zurück   ·   Zynthian: Pfeile · SEL · BACK"


# ---------------------------------------------------------------------------------------------------------
# Szenen
# ---------------------------------------------------------------------------------------------------------
class Szene:
    def __init__(self, app):
        self.app = app

    def ereignis(self, ev, nav):
        pass

    def tipp(self, pos):
        pass

    def update(self, dt):
        pass

    def zeichnen(self, s):
        pass

    def betreten(self):
        pass


class Hintergrundbild:
    """Ein laufender Hintergrund mit eigenem Takt (für die Menüs)."""

    def __init__(self, app, thema, bpm=110, farbe=g.GLUT):
        self.hg = g.Hintergrund(thema, app.groesse, app.e["grafik"], farbe)
        self.bpm = bpm
        self.t0 = time.monotonic()
        self.letzter = -1

    def zeichnen(self, s):
        t = time.monotonic() - self.t0
        b = t * self.bpm / 60
        schlag = int(b)
        neu = schlag != self.letzter
        self.letzter = schlag
        self.hg.zeichnen(s, t, b % 1, 0.5, False, neu, neu and schlag % 4 == 0)


def abdunkeln(s, staerke=150):
    d = pygame.Surface(s.get_size())
    d.fill((0, 0, 0))
    d.set_alpha(staerke)
    s.blit(d, (0, 0))


class Lade(Szene):
    def betreten(self):
        self.hg = Hintergrundbild(self.app, "feuerinsel", 90)

    def update(self, dt):
        if self.app.lieder_bereit() and self.app.ton.bereit:
            self.app.wechsel(Titel(self.app))

    def zeichnen(self, s):
        W, H = s.get_size()
        self.hg.zeichnen(s)
        abdunkeln(s, 120)
        g.text_zeigen(s, "BARD HERO", int(H * 0.14), (W / 2, H * 0.3), g.GOLD2, fett=True)
        r = self.app.render
        if not self.app.ton.bereit:
            zeile = "Ton wird gestartet …"
        elif r["gesamt"]:
            zeile = f"Lieder werden vorbereitet: {r['nr']} von {r['gesamt']} · {r['titel']}"
        else:
            zeile = "Lieder werden geprüft …"
        g.text_zeigen(s, zeile, int(H * 0.045), (W / 2, H * 0.55), g.CHAMP)
        bw = W * 0.6
        anteil = (r["nr"] - 1 + r["teil"] / 3) / r["gesamt"] if r["gesamt"] else 0
        g.rrect(s, (40, 30, 22), (W / 2 - bw / 2, H * 0.62, bw, H * 0.04), 10)
        g.rrect(s, g.GLUT, (W / 2 - bw / 2, H * 0.62, max(10, bw * anteil), H * 0.04), 10)
        g.text_zeigen(s, "Beim ersten Start einmalig – danach geht es sofort los.", int(H * 0.035), (W / 2, H * 0.72), g.TX2)


class Titel(Szene):
    def betreten(self):
        self.hg = Hintergrundbild(self.app, "feuerinsel", 100)
        self.m = Menue([("solo", "Solo spielen", None), ("duell", "Duell · 2 Spieler", None),
                        ("duett", "Duett · Melodie + Bass", None), ("ton", "Ton & Mikrofon", None),
                        ("einst", "Einstellungen", None), ("raus", "Zum Mischpult", None)],
                       getattr(self.app, "titel_wahl", 0))
        self.app.ton.cmd(cmd="vorschau_aus")
        self.app.eingaben.leds_alle((40, 14, 0))
        self.flammen = g.Funken(120)

    def ereignis(self, ev, nav):
        self.m.nav(nav)
        if nav in ("hoch", "runter"):
            self.app.sfx("menue")
        if nav == "ok":
            self.waehlen()

    def tipp(self, pos):
        if self.m.tipp(pos):
            self.waehlen()

    def waehlen(self):
        k = self.m.key
        self.app.titel_wahl = self.m.wahl
        self.app.sfx("ok")
        if k in ("solo", "duell", "duett"):
            self.app.wechsel(Spielerwahl(self.app, k))
        elif k == "ton":
            self.app.wechsel(Pegel(self.app, self))
        elif k == "einst":
            self.app.wechsel(Einstellungen(self.app))
        elif k == "raus":
            self.app.wechsel(System(self.app, self))

    def zeichnen(self, s):
        W, H = s.get_size()
        self.hg.zeichnen(s)
        abdunkeln(s, 70)
        t = time.monotonic()
        if self.app.e["grafik"] and len(self.flammen.p) < 120 and int(t * 60) % 2 == 0:
            x = W * (0.5 + 0.35 * math.sin(t * 7.3) * math.cos(t * 2.1))
            self.flammen.neu(x, H * 1.0, math.sin(t * 3) * 20, -60 - 50 * abs(math.sin(t * 5)), 4.0, 2.5, g.ORANGE)
        self.flammen.schritt(self.app.dt)
        self.flammen.zeichnen(s)
        g.leuchten(s, (W / 2, H * 0.17), H * 0.3, (255, 90, 10), 0.6)
        g.text_zeigen(s, "BARD HERO", int(H * 0.15), (W / 2, H * 0.17), g.GOLD2, fett=True)
        g.text_zeigen(s, "Spiel die Melodie – die Band spielt den Rest", int(H * 0.035), (W / 2, H * 0.28), g.CHAMP)
        bw = min(W * 0.5, H * 0.9)
        self.m.zeichnen(s, (W / 2 - bw / 2, H * 0.34, bw, H * 0.56))
        g.text_zeigen(s, HINWEIS, int(H * 0.028), (W / 2, H * 0.95), g.TX2)
        geraete = ", ".join(sorted(set(self.app.eingaben.geraete.values())))[:90]
        if geraete:
            g.text_zeigen(s, "Erkannt: " + geraete, int(H * 0.026), (W / 2, H * 0.915), (120, 110, 96))


class Spielerwahl(Szene):
    """Wer spielt mit welchem Gerät (Bauform wird erkannt bzw. angelernt), Spielart und Stufe."""

    def __init__(self, app, art):
        super().__init__(app)
        self.art = art
        self.zwei = art in ("duell", "duett")
        self.schritt = "geraet1"
        self.geraete = [None, None]

    def betreten(self):
        self.hg = Hintergrundbild(self.app, "taverne", 100)
        self.baue_menue()

    def anzahl(self):
        return 2 if self.zwei else 1

    def baue_menue(self):
        e = self.app.e["spieler"]
        eintraege = []
        for i in range(self.anzahl()):
            wer = f"Spieler {i + 1}" if self.zwei else ""
            teil = ""
            if self.art == "duett":
                teil = " (Melodie)" if i == 0 else " (Bass)"
            def zeile(text):
                return f"{wer}{teil} · {text}" if self.zwei else text
            dev = self.geraete[i]
            eintraege.append((f"ctrl{i}", zeile("Controller"), FORM_TEXT[self.app.anzeige_form(dev)]))
            eintraege.append((f"modus{i}", zeile("Spielart"), MODUS_NAME[e[i]["modus"]]))
            eintraege.append((f"stufe{i}", zeile("Stufe"), chart.STUFEN_NAME[e[i]["stufe"]]))
        eintraege.append(("los", "Weiter zur Liedauswahl", None))
        alt = getattr(self, "m", None)
        self.m = Menue(eintraege, alt.wahl if alt else len(eintraege) - 1)

    def ereignis(self, ev, nav):
        if self.schritt.startswith("geraet"):
            art, geraet = ev[0], ev[1]
            if art in ("an", "taste") and (ev[4] if art == "taste" else True):
                if nav == "zurueck" and geraet in ("zyn", "tast"):
                    return self.app.wechsel(Titel(self.app))
                i = 0 if self.schritt == "geraet1" else 1
                if i == 1 and geraet == self.geraete[0]:
                    return
                self.geraete[i] = geraet
                self.app.sfx("ok")
                self.schritt = "geraet2" if (i == 0 and self.zwei) else "optionen"
                self.baue_menue()
            return
        if nav == "zurueck":
            return self.app.wechsel(Titel(self.app))
        self.m.nav(nav)
        if self.m.key.startswith("ctrl"):
            if nav == "ok":
                self.einrichten()
            return
        if nav in ("links", "rechts") or (nav == "ok" and self.m.key != "los"):
            self.aendern(1 if nav != "links" else -1)
        elif nav == "ok":
            self.los()

    def tipp(self, pos):
        if self.schritt.startswith("geraet"):
            return
        if self.m.tipp(pos):
            if self.m.key == "los":
                self.los()
            elif self.m.key.startswith("ctrl"):
                self.einrichten()
            else:
                self.aendern(1)

    def einrichten(self):
        i = int(self.m.key[-1])
        self.app.sfx("ok")
        self.app.wechsel(Anlernen(self.app, i + 1, self.geraete[i], zurueck=self))

    def aendern(self, d):
        k = self.m.key
        e = self.app.e["spieler"]
        if k.startswith("modus"):
            i = int(k[-1])
            e[i]["modus"] = "barde" if e[i]["modus"] == "hero" else "hero"
        elif k.startswith("stufe"):
            i = int(k[-1])
            st = chart.STUFEN
            e[i]["stufe"] = st[(st.index(e[i]["stufe"]) + d) % len(st)]
        self.app.sfx("menue")
        self.baue_menue()

    def los(self):
        e = self.app.e["spieler"]
        self.app.speichern()
        spieler = []
        for i in range(self.anzahl()):
            teil = "bass" if (self.art == "duett" and i == 1) else "lead"
            dev = self.geraete[i]
            spieler.append(Spieler(i + 1, e[i]["modus"], e[i]["stufe"], teil, {dev} if self.zwei else None,
                                   self.app.form_von(dev), dev))
        self.app.sfx("ok")
        self.app.wechsel(Liedwahl(self.app, self.art, spieler))

    def zeichnen(self, s):
        W, H = s.get_size()
        self.hg.zeichnen(s)
        abdunkeln(s, 150)
        titel = {"solo": "Solo", "duell": "Duell", "duett": "Duett"}[self.art]
        g.text_zeigen(s, titel, int(H * 0.08), (W / 2, H * 0.1), g.GOLD2, fett=True)
        if self.schritt.startswith("geraet"):
            i = 0 if self.schritt == "geraet1" else 1
            wer = f"Spieler {i + 1}:" if self.zwei else "Los geht's:"
            g.text_zeigen(s, wer, int(H * 0.07), (W / 2, H * 0.32), g.SPUR_FARBEN[i * 3])
            g.text_zeigen(s, "drück eine Taste auf deinem Instrument", int(H * 0.05), (W / 2, H * 0.43), g.CHAMP)
            g.text_zeigen(s, "Keytar, Gitarren-Controller, BeatStep, Zynthian-Tasten, Tastatur oder Gamepad",
                          int(H * 0.034), (W / 2, H * 0.52), g.TX2)
            if i == 1 and self.geraete[0]:
                g.text_zeigen(s, "Spieler 1: " + self.app.geraet_name(self.geraete[0]), int(H * 0.035),
                              (W / 2, H * 0.62), g.GRUEN)
                zeichne_controller(s, (W / 2, H * 0.74), H * 0.07, self.app.anzeige_form(self.geraete[0]))
            g.text_zeigen(s, "BACK / Esc = zurück", int(H * 0.03), (W / 2, H * 0.92), g.TX2)
            return
        mw = W * 0.6
        self.m.zeichnen(s, (W * 0.03, H * 0.19, mw, H * 0.64), mit_pfeilen=True)
        # rechts: die Controller, so wie das Spiel sie sieht
        rx = W * 0.03 + mw + (W - mw - W * 0.03) / 2
        for i in range(self.anzahl()):
            dev = self.geraete[i]
            form = self.app.anzeige_form(dev)
            y = H * (0.36 if self.anzahl() == 1 else 0.3 + i * 0.3)
            if self.zwei:
                g.text_zeigen(s, f"Spieler {i + 1}", int(H * 0.035), (rx, y - H * 0.11), g.SPUR_FARBEN[i * 3])
            u = min(H * 0.07, (W - mw) * 0.2)
            zeichne_controller(s, (rx, y), u, form)
            g.text_zeigen(s, self.app.geraet_name(dev), int(H * 0.03), (rx, y + u * 1.3), g.CHAMP)
            hinweis = self.app.einricht_hinweis(dev)
            if hinweis:
                g.text_zeigen(s, hinweis, int(H * 0.026), (rx, y + u * 1.3 + H * 0.04), g.GLUT)
        tipp = ("Hero: die Noten fallen auf die Tasten deines Controllers."
                if self.app.e["spieler"][0]["modus"] == "hero" else
                "Barde: spiel die echten Töne der Melodie – jede Oktave zählt.")
        g.text_zeigen(s, tipp, int(H * 0.032), (W / 2, H * 0.87), g.TX2)
        g.text_zeigen(s, HINWEIS, int(H * 0.026), (W / 2, H * 0.95), g.TX2)


class Liedwahl(Szene):
    def __init__(self, app, art, spieler):
        super().__init__(app)
        self.art = art
        self.spieler = spieler
        self.wahl = getattr(app, "lied_wahl", 0)
        self.hg = None
        self.hg_id = None
        self.vorschau_ab = 0.0
        self.rects = []

    def betreten(self):
        self.vorschau_ab = time.monotonic() + 0.6
        self.vorschau_id = None

    def liste(self):
        return self.app.lieder

    def ereignis(self, ev, nav):
        L = self.liste()
        if nav == "zurueck":
            self.app.ton.cmd(cmd="vorschau_aus")
            return self.app.wechsel(Spielerwahl(self.app, self.art))
        if nav in ("hoch", "links") or (isinstance(nav, tuple) and nav[1] < 0):
            self.wahl = (self.wahl - 1) % len(L)
            self.vorschau_ab = time.monotonic() + 0.6
            self.app.sfx("menue")
        elif nav in ("runter", "rechts") or (isinstance(nav, tuple) and nav[1] > 0):
            self.wahl = (self.wahl + 1) % len(L)
            self.vorschau_ab = time.monotonic() + 0.6
            self.app.sfx("menue")
        elif nav == "ok":
            self.starten()

    def tipp(self, pos):
        for i, r in self.rects:
            if r.collidepoint(pos):
                if i == self.wahl:
                    self.starten()
                else:
                    self.wahl = i
                    self.vorschau_ab = time.monotonic() + 0.4
                return

    def starten(self):
        lied = self.liste()[self.wahl]
        if not lied["bereit"]:
            self.app.sfx("fehler")
            return
        self.app.lied_wahl = self.wahl
        self.app.ton.cmd(cmd="vorschau_aus")
        self.app.sfx("ok")
        self.app.wechsel(Spiel(self.app, self.art, self.spieler, lied))

    def update(self, dt):
        lied = self.liste()[self.wahl]
        if self.hg_id != lied["id"]:
            self.hg_id = lied["id"]
            self.hg = Hintergrundbild(self.app, lied["thema"], lied["bpm"], g.hex2rgb(lied["farbe"]))
        if self.vorschau_ab and time.monotonic() > self.vorschau_ab:
            self.vorschau_ab = 0
            if lied["bereit"] and self.vorschau_id != lied["id"]:
                self.vorschau_id = lied["id"]
                self.app.ton.cmd(cmd="vorschau", datei=os.path.join(DATEN, "lieder", lied["id"], "vorschau.wav"))
            elif not lied["bereit"]:
                self.vorschau_id = None
                self.app.ton.cmd(cmd="vorschau_aus")

    def zeichnen(self, s):
        W, H = s.get_size()
        if self.hg:
            self.hg.zeichnen(s)
        abdunkeln(s, 110)
        L = self.liste()
        g.text_zeigen(s, "Liedauswahl", int(H * 0.06), (W * 0.27, H * 0.07), g.GOLD2, fett=True)
        # Liste links (scrollend)
        lx, ly, lw = W * 0.03, H * 0.13, W * 0.48
        zh = H * 0.083
        sichtbar = int((H * 0.8) // zh)
        start = max(0, min(self.wahl - sichtbar // 2, len(L) - sichtbar))
        self.rects = []
        for k, lied in enumerate(L[start:start + sichtbar]):
            i = start + k
            r = pygame.Rect(lx, ly + k * zh, lw, zh * 0.88)
            an = i == self.wahl
            g.rrect(s, (54, 36, 18) if an else (22, 17, 13), r, 12)
            farbe = g.hex2rgb(lied["farbe"])
            pygame.draw.rect(s, farbe, (r.x + 6, r.y + r.h * 0.2, 6, r.h * 0.6), border_radius=3)
            g.text_zeigen(s, lied["titel"], int(zh * 0.36), (r.x + 22, r.centery - zh * 0.12), g.GOLD2 if an else g.CHAMP, "links")
            g.text_zeigen(s, lied["untertitel"], int(zh * 0.24), (r.x + 22, r.centery + zh * 0.2), g.TX2, "links")
            if not lied["bereit"]:
                g.text_zeigen(s, "wird vorbereitet …", int(zh * 0.24), (r.right - 12, r.centery), g.GLUT, "rechts")
            else:
                for f in range(lied["schwierigkeit"]):
                    g.leuchten(s, (r.right - 18 - f * zh * 0.24, r.centery), zh * 0.1, (255, 110, 20), 0.9)
            if an:
                g.rrect(s, g.GOLD, r, 12, 3)
            self.rects.append((i, r))
        # Details rechts
        lied = L[self.wahl]
        dx, dw = W * 0.55, W * 0.42
        kasten = pygame.Rect(dx, H * 0.13, dw, H * 0.72)
        g.rrect(s, (16, 12, 10), kasten, 16)
        g.rrect(s, g.hex2rgb(lied["farbe"]), kasten, 16, 2)
        y = kasten.y + H * 0.07
        for z in g.umbrechen(lied["titel"], int(H * 0.06), dw * 0.9):
            g.text_zeigen(s, z, int(H * 0.06), (kasten.centerx, y), g.GOLD2, fett=True)
            y += H * 0.07
        g.text_zeigen(s, lied["untertitel"], int(H * 0.036), (kasten.centerx, y), g.CHAMP)
        y += H * 0.06
        dauer = lied["laenge"]
        g.text_zeigen(s, f"{int(dauer // 60)}:{int(dauer % 60):02d} min  ·  {lied['bpm']} BPM  ·  {lied['tonart']}",
                      int(H * 0.032), (kasten.centerx, y), g.TX2)
        y += H * 0.05
        g.text_zeigen(s, lied["stimmung"], int(H * 0.032), (kasten.centerx, y), g.GLUT)
        y += H * 0.07
        for sp in self.spieler:
            schl = self.app.rekord_schluessel(lied["id"], sp)
            rek = self.app.rekorde.get(schl, [])
            wer = f"Spieler {sp.nr}" if len(self.spieler) > 1 else "Rekord"
            inhalt = f"{rek[0]['punkte']:,} Punkte · {'★' * rek[0]['sterne']}".replace(",", ".") if rek else "noch keiner"
            g.text_zeigen(s, f"{wer} ({chart.STUFEN_NAME[sp.stufe]}, {MODUS_NAME[sp.modus].split(' ·')[0]}): {inhalt}",
                          int(H * 0.03), (kasten.centerx, y), g.CHAMP)
            y += H * 0.045
        g.text_zeigen(s, "✓ spielen  ·  zurück = Spielerwahl", int(H * 0.03), (kasten.centerx, kasten.bottom - H * 0.04), g.TX2)
        g.text_zeigen(s, HINWEIS, int(H * 0.026), (W / 2, H * 0.95), g.TX2)


class Spiel(Szene):
    def __init__(self, app, art, spieler, lied):
        super().__init__(app)
        self.art = art
        self.spieler = spieler
        self.lied = lied
        self.ordner = os.path.join(DATEN, "lieder", lied["id"])
        self.c = chart.laden(self.ordner)
        self.schlag = self.c["schlag"]
        self.takt_s = self.c["takt_s"]
        self.zustand = "laden"
        self.nr = app.neue_nr()
        self.gates = {"lead": True, "bass": True}
        self.abschnitt = ""
        self.abschnitt_bis = 0
        self.letzter_schlag = -99
        self.insp_klang_bis = 0
        self.pause = None
        self.start_mono = 0

    def betreten(self):
        app = self.app
        W, H = app.groesse
        sicht = SICHT.get(app.e["tempo"], 1.35)
        n = len(self.spieler)
        for i, sp in enumerate(self.spieler):
            sp.noten, sp.namen = chart.bauen(self.c, sp.teil, sp.modus, sp.stufe)
            if n == 1:
                bw = min(W * 0.56, H * 1.05)
                rect = (W / 2 - bw / 2, H * 0.08, bw, H * 0.92)
            else:
                bw = min(W * 0.4, H * 0.9)
                cx = W * (0.25 if i == 0 else 0.75)
                rect = (cx - bw / 2, H * 0.12, bw, H * 0.88)
            spuren = chart.spuren_anzahl(sp.form, sp.stufe) if sp.modus == "hero" else 12
            if sp.modus == "hero":
                sp.noten, _ = chart.bauen(self.c, sp.teil, sp.modus, sp.stufe, spuren)
            namen = sp.namen
            if sp.modus == "hero":
                namen = self.app.spur_namen(sp, spuren)
            sp.bahn = g.Bahn(rect, sp.modus, spuren, namen, sicht, sp.form)
        self.hg = g.Hintergrund(self.c["thema"], app.groesse, app.e["grafik"], g.hex2rgb(self.c["farbe"]))
        app.render_pausieren(True)
        app.ton.cmd(cmd="pegel", **app.e["pegel"])
        app.ton.cmd(cmd="laden", ordner=self.ordner, nr=self.nr)
        self.lade_start = time.monotonic()
        app.eingaben.leds_alle((0, 0, 0))

    def start(self):
        vor = 4 * self.schlag
        klicks = [-vor + k * self.schlag for k in range(4)]
        self.app.ton.cmd(cmd="start", ab=-vor - 0.4, klicks=klicks)
        self.zustand = "spielt"
        self.start_mono = time.monotonic()
        for sp in self.spieler:
            sp.idx = 0

    def versatz(self):
        return self.app.e["versatz_ms"] / 1000.0

    # ---- Eingaben ----
    def ereignis(self, ev, nav):
        art, geraet = ev[0], ev[1]
        if self.pause:
            return self.pause_ereignis(nav)
        if art == "taste" and geraet == "zyn" and ev[2] in ("BACK", "MENU") and ev[4]:
            return self.pausieren()
        if art == "taste" and geraet == "tast" and ev[2] in ("escape", "p") and ev[4]:
            return self.pausieren()
        if self.zustand != "spielt":
            return
        for sp in self.spieler:
            if sp.geraete is not None and geraet not in sp.geraete:
                continue
            self.spieler_eingabe(sp, ev)

    def spieler_eingabe(self, sp, ev):
        t = self.app.ton.liedzeit(ev[3]) - self.versatz()
        art = ev[0]
        if art == "cc":
            # Pedal, Modulationsrad oder Pitchbend zündet die Inspiration
            if (ev[2] == -1 and abs(ev[4]) > 3000) or (ev[2] in (1, 64, 11) and ev[4] > 64):
                self.inspiration(sp)
            return
        if art == "taste" and ev[1] == "tast" and ev[2] == "space" and ev[4]:
            return self.inspiration(sp)
        # Gitarren mit Anschlag-Leiste: Bünde greifen, gewertet wird beim Anschlagen
        bel = eingabe.belegung_von(self.app.e["belegung"], ev[1]) or {}
        anschlag = bel.get("_anschlag") if sp.modus == "hero" else None
        if anschlag and art == "taste" and str(ev[2]) in anschlag:
            if ev[4]:
                self.werten(sp, set(sp.gedrueckt), t)
            return
        if sp.modus == "hero":
            spur, an = eingabe.hero_spur(ev, self.app.e["belegung"], sp.bahn.n)
        else:
            spur, an = eingabe.barden_ton(ev)
        if spur is None:
            return
        if not an:
            sp.gedrueckt.discard(spur)
            for n in sp.noten[max(0, sp.idx - 8):sp.idx + 4]:
                if n.gehalten and n.spur == spur:
                    n.gehalten = False
            return
        sp.gedrueckt.add(spur)
        # Inspiration: äußere Spuren gleichzeitig
        sp.letzte_drueck[spur] = t
        if sp.modus == "hero" and spur in (0, sp.bahn.n - 1):
            andere = sp.bahn.n - 1 if spur == 0 else 0
            if abs(sp.letzte_drueck.get(andere, -9) - t) < 0.07:
                self.inspiration(sp)
        if anschlag:
            return
        self.werten(sp, {spur}, t)

    def werten(self, sp, spuren, t):
        """Gegriffene Spur(en) zum Zeitpunkt t → Treffer, Fehlgriff oder (weit weg von Noten) nichts."""
        fenster = chart.FENSTER[sp.stufe]
        beste = None
        naechste_irgendwo = 9.0
        i = sp.idx
        while i < len(sp.noten):
            n = sp.noten[i]
            if n.t > t + fenster:
                if n.status == 0:
                    naechste_irgendwo = min(naechste_irgendwo, n.t - t)
                break
            if n.status == 0:
                naechste_irgendwo = min(naechste_irgendwo, abs(n.t - t))
                if n.spur in spuren and abs(n.t - t) <= fenster:
                    if beste is None or abs(n.t - t) < abs(beste.t - t):
                        beste = n
            i += 1
        if beste:
            self.treffer(sp, beste, t)
        elif naechste_irgendwo < 0.3:
            self.fehlgriff(sp)

    def treffer(self, sp, n, t):
        n.status = 1
        perfekt = abs(n.t - t) < 0.04
        sp.getroffen += 1
        sp.perfekt += perfekt
        sp.combo += 1
        sp.max_combo = max(sp.max_combo, sp.combo)
        sp.punkte += 50 * sp.multi + (10 if perfekt else 0)
        sp.publikum = min(1.0, sp.publikum + 0.012)
        if n.halten_bis and n.spur in sp.gedrueckt:
            n.gehalten = True
        sp.bahn.treffer(n.spur, perfekt)
        if not sp.ok:
            sp.ok = True
            self.gate_pruefen()
        if n.insp and n.phrase not in sp.phrase_kaputt:
            letzte = all(m.status == 1 for m in sp.noten if m.phrase == n.phrase)
            if letzte:
                sp.insp = min(1.0, sp.insp + 0.25)
                sp.text.append(("Inspiration +", g.GOLD2, time.monotonic() + 1.2))
                self.app.sfx("ok")
                if self.app.e["insp_auto"] and sp.insp >= 0.999:
                    self.inspiration(sp)
        if sp.combo in (10, 20, 30, 50, 100, 200, 300, 500):
            sp.text.append((f"{sp.combo}er-Serie!", g.GLUT, time.monotonic() + 1.0))

    def fehler(self, sp, n=None):
        if sp.combo >= 15:
            sp.text.append(("Serie gerissen", g.ROT, time.monotonic() + 0.9))
        sp.combo = 0
        sp.fehl_anzeige = 1.0
        if n is not None and n.insp:
            sp.phrase_kaputt.add(n.phrase)
        if sp.ok:
            sp.ok = False
            self.gate_pruefen()
        if sp.publikum <= 0 and self.app.e["durchfallen"] and not sp.ausgebuht:
            sp.ausgebuht = True

    def fehlgriff(self, sp):
        sp.fehlgriffe += 1
        sp.publikum = max(0.0, sp.publikum - 0.02)
        self.app.sfx("fehler", 0.8)
        # die nächste offene Inspirations-Phrase gilt als verpatzt
        for n in sp.noten[sp.idx:sp.idx + 3]:
            if n.status == 0 and n.insp:
                sp.phrase_kaputt.add(n.phrase)
                break
        self.fehler(sp)

    def inspiration(self, sp):
        if sp.insp_aktiv or sp.insp < 0.5:
            return
        sp.insp_aktiv = True
        sp.text.append(("INSPIRATION!", g.ORANGE, time.monotonic() + 1.6))
        self.app.sfx("inspiration")
        self.app.eingaben.leds_alle((255, 90, 0))

    def gate_pruefen(self):
        for teil in ("lead", "bass"):
            sps = [sp for sp in self.spieler if sp.teil == teil]
            an = any(sp.ok for sp in sps) if sps else True
            if an != self.gates[teil]:
                self.gates[teil] = an
                self.app.ton.cmd(cmd="gate", stem=teil, an=an)

    # ---- Pause ----
    def pausieren(self):
        if self.zustand != "spielt":
            return
        self.pause = Menue([("weiter", "Weiterspielen", None), ("neu", "Nochmal von vorn", None),
                            ("pegel", "Ton & Mikrofon", None), ("aufgeben", "Zur Liedauswahl", None)])
        self.pause_zeit = self.app.ton.liedzeit()
        self.app.ton.cmd(cmd="pause")
        self.app.render_pausieren(False)

    def pause_ereignis(self, nav):
        self.pause.nav(nav)
        if nav == "zurueck":
            return self.fortsetzen()
        if nav == "ok":
            self.pause_waehlen()

    def pause_waehlen(self):
        k = self.pause.key
        if k == "weiter":
            self.fortsetzen()
        elif k == "neu":
            self.pause = None
            self.app.ton.cmd(cmd="stop")
            neu = [sp.kopie() for sp in self.spieler]
            self.app.wechsel(Spiel(self.app, self.art, neu, self.lied))
        elif k == "pegel":
            self.app.wechsel(Pegel(self.app, self))
        elif k == "aufgeben":
            self.pause = None
            self.app.ton.cmd(cmd="stop")
            self.app.ton.cmd(cmd="gate", stem="lead", an=True)
            self.app.ton.cmd(cmd="gate", stem="bass", an=True)
            self.app.render_pausieren(False)
            neu = [sp.kopie() for sp in self.spieler]
            self.app.wechsel(Liedwahl(self.app, self.art, neu))

    def fortsetzen(self):
        self.pause = None
        zurueck = max(-1.5, self.pause_zeit - 2 * self.schlag)
        self.app.ton.cmd(cmd="weiter", ab=zurueck)
        self.app.render_pausieren(True)
        # Noten, die in den 2 Schlägen Rücklauf liegen, wieder öffnen (nicht als verpasst werten)
        for sp in self.spieler:
            for n in sp.noten:
                if zurueck - 0.2 < n.t < self.pause_zeit + 0.5 and n.status == 2:
                    n.status = 0
            while sp.idx > 0 and sp.noten[sp.idx - 1].t > zurueck - 0.2:
                sp.idx -= 1

    def tipp(self, pos):
        if self.pause:
            if self.pause.tipp(pos):
                self.pause_waehlen()
            return
        W, H = self.app.groesse
        if pos[1] < H * 0.12:
            self.pausieren()

    # ---- Ablauf ----
    def update(self, dt):
        app = self.app
        if self.zustand == "laden":
            if app.ton.geladen() == self.nr:
                self.start()
            elif time.monotonic() - self.lade_start > 25:
                app.meldung("Das Lied ließ sich nicht laden")
                app.wechsel(Liedwahl(app, self.art, self.spieler))
            return
        if self.pause or self.zustand != "spielt":
            return
        t = app.ton.liedzeit() - self.versatz()
        # Abschnitt
        for name, ab in self.c["abschnitte"]:
            if ab <= t + 0.05:
                if name != self.abschnitt:
                    if self.abschnitt and t > 1:
                        self.abschnitt_bis = time.monotonic() + 2.2
                    self.abschnitt = name
        for sp in self.spieler:
            fenster = chart.FENSTER[sp.stufe]
            # verpasste Noten
            while sp.idx < len(sp.noten):
                n = sp.noten[sp.idx]
                if n.status == 0 and n.t < t - fenster:
                    n.status = 2
                    sp.verpasst += 1
                    sp.publikum = max(0.0, sp.publikum - 0.035)
                    self.fehler(sp, n)
                    sp.idx += 1
                elif n.status != 0 and n.t < t - fenster:
                    sp.idx += 1
                else:
                    break
            # Haltenoten
            for n in sp.noten[max(0, sp.idx - 12):sp.idx + 2]:
                if n.gehalten:
                    if t >= n.halten_bis:
                        n.gehalten = False
                    elif n.spur in sp.gedrueckt:
                        sp.punkte_float += 25 * sp.multi * dt / self.schlag
                        if sp.punkte_float >= 1:
                            sp.punkte += int(sp.punkte_float)
                            sp.punkte_float -= int(sp.punkte_float)
            # Inspiration läuft ab: volle Leiste = 8 Takte
            if sp.insp_aktiv:
                sp.insp -= dt / (8 * self.takt_s)
                if sp.insp <= 0:
                    sp.insp = 0
                    sp.insp_aktiv = False
                    if not any(x.insp_aktiv for x in self.spieler):
                        app.eingaben.leds_alle((0, 0, 0))
            sp.fehl_anzeige = max(0.0, sp.fehl_anzeige - dt * 3)
            sp.text = [x for x in sp.text if x[2] > time.monotonic()]
        # Ende
        if t > self.c["ende"] + 2.5 or (all(sp.ausgebuht for sp in self.spieler)):
            self.zustand = "ende"
            app.ton.cmd(cmd="stop")
            app.ton.cmd(cmd="gate", stem="lead", an=True)
            app.ton.cmd(cmd="gate", stem="bass", an=True)
            app.render_pausieren(False)
            app.sfx("buh" if all(sp.ausgebuht for sp in self.spieler) else "jubel")
            app.wechsel(Ergebnis(app, self.art, self.spieler, self.lied))

    def zeichnen(self, s):
        app = self.app
        W, H = s.get_size()
        t = app.ton.liedzeit() - self.versatz() if self.zustand == "spielt" else -9
        if self.pause:
            t = self.pause_zeit - self.versatz()
        b = t / self.schlag
        schlag = math.floor(b)
        neu = schlag != self.letzter_schlag and t > 0
        takt_neu = neu and round(t / self.takt_s * 1000) % 1000 < 80 if self.takt_s else False
        self.letzter_schlag = schlag
        insp = any(sp.insp_aktiv for sp in self.spieler)
        self.hg.zeichnen(s, max(0.0, t) if t > -8 else time.monotonic() % 1000, b % 1 if t > 0 else 0.5,
                         0.5, insp, neu, takt_neu)
        for sp in self.spieler:
            start = sp.idx
            k = 0
            while start > 0 and k < 30 and (sp.noten[start - 1].t > t - 0.4 or sp.noten[start - 1].halten_bis > t):
                start -= 1
                k += 1
            sp.bahn.zeichnen(s, t, sp.noten, start, sp.gedrueckt, sp.insp_aktiv, self.schlag, app.dt, sp.fehl_anzeige)
            self.hud(s, sp, len(self.spieler) > 1)
        # Fortschritt oben
        ende = self.c["ende"]
        p = max(0.0, min(1.0, t / ende)) if ende else 0
        pygame.draw.rect(s, (40, 30, 22), (0, 0, W, max(4, H // 120)))
        pygame.draw.rect(s, g.hex2rgb(self.c["farbe"]), (0, 0, W * p, max(4, H // 120)))
        if len(self.spieler) == 1:
            g.text_zeigen(s, self.c["titel"], int(H * 0.032), (W * 0.02, H * 0.04), g.CHAMP, "links")
        if time.monotonic() < self.abschnitt_bis and not self.pause:
            if len(self.spieler) == 1:
                g.text_zeigen(s, self.abschnitt, int(H * 0.05), (W / 2, H * 0.12), g.GOLD2)
            else:
                for sp in self.spieler:
                    g.text_zeigen(s, self.abschnitt, int(H * 0.04), (sp.bahn.rect.centerx, sp.bahn.rect.y + H * 0.06),
                                  g.GOLD2)
        # Einzählen
        if self.zustand == "laden":
            g.text_zeigen(s, "Lied wird geladen …", int(H * 0.06), (W / 2, H * 0.45), g.GOLD2)
        elif -4 * self.schlag - 0.1 < t < 0:
            zahl = int(-t / self.schlag) + 1
            g.text_zeigen(s, str(min(4, zahl)), int(H * 0.2), (W / 2, H * 0.42), g.GOLD2, fett=True)
        if self.pause:
            abdunkeln(s, 170)
            g.text_zeigen(s, "Pause", int(H * 0.09), (W / 2, H * 0.16), g.GOLD2, fett=True)
            bw = min(W * 0.5, H * 0.9)
            self.pause.zeichnen(s, (W / 2 - bw / 2, H * 0.28, bw, H * 0.5))
            g.text_zeigen(s, HINWEIS, int(H * 0.026), (W / 2, H * 0.94), g.TX2)

    def hud(self, s, sp, zwei):
        W, H = s.get_size()
        r = sp.bahn.rect
        gr = int(H * (0.04 if not zwei else 0.034))
        punkte = f"{sp.punkte:,}".replace(",", ".")
        farbe = g.SPUR_FARBEN[0] if sp.nr == 1 else g.SPUR_FARBEN[3]
        if not zwei:
            x = r.x - W * 0.02
            g.text_zeigen(s, punkte, int(H * 0.07), (x, H * 0.3), g.GOLD2, "rechts", fett=True)
            g.text_zeigen(s, "Punkte", gr, (x, H * 0.36), g.TX2, "rechts")
            self.multi_ring(s, (x - H * 0.08, H * 0.5), H * 0.07, sp)
            if sp.combo >= 2:
                g.text_zeigen(s, f"{sp.combo} in Folge", gr, (x, H * 0.62), g.CHAMP, "rechts")
            self.leisten(s, sp, r.right + W * 0.02, H * 0.25, H * 0.55, zwei)
        else:
            y = r.y - H * 0.06
            aussen = sp.nr == 1
            g.text_zeigen(s, f"Spieler {sp.nr}" + (" · Bass" if sp.teil == "bass" else ""), gr,
                          (r.x if aussen else r.right, y), farbe, "links" if aussen else "rechts")
            g.text_zeigen(s, punkte, int(gr * 1.3), (r.centerx, y), g.GOLD2, fett=True)
            self.multi_ring(s, (r.x + H * 0.06, r.y + H * 0.1), H * 0.045, sp)
            if sp.combo >= 2:
                g.text_zeigen(s, f"{sp.combo}", gr, (r.x + H * 0.06, r.y + H * 0.17), g.CHAMP)
            self.leisten(s, sp, r.right - H * 0.05, r.y + H * 0.05, H * 0.35, zwei)
        for k, (txt, fb, bis) in enumerate(sp.text[-3:]):
            g.text_zeigen(s, txt, int(H * 0.045), (r.centerx, r.y + r.h * 0.35 + k * H * 0.055), fb, fett=True)
        if sp.ausgebuht:
            g.text_zeigen(s, "Ausgebuht!", int(H * 0.08), r.center, g.ROT, fett=True)

    def multi_ring(self, s, pos, radius, sp):
        m = sp.multi
        farbe = [g.CHAMP, g.GRUEN, g.GELB, g.ORANGE, g.ROT][min(4, m // (2 if sp.insp_aktiv else 1))]
        if sp.insp_aktiv:
            farbe = g.ORANGE
            g.leuchten(s, pos, radius * 1.8, (255, 100, 10), 0.7)
        pygame.draw.circle(s, (20, 14, 10), (int(pos[0]), int(pos[1])), int(radius))
        anteil = (sp.combo % 10) / 10 if sp.combo < 30 else 1.0
        if anteil > 0:
            pygame.draw.arc(s, farbe, (pos[0] - radius, pos[1] - radius, radius * 2, radius * 2),
                            math.pi / 2, math.pi / 2 + anteil * 2 * math.pi, max(3, int(radius * 0.18)))
        pygame.draw.circle(s, heller_rand(farbe), (int(pos[0]), int(pos[1])), int(radius), 2)
        g.text_zeigen(s, f"×{m}", int(radius * 0.9), pos, farbe, fett=True)

    def leisten(self, s, sp, x, y, h, zwei):
        W, H = s.get_size()
        b = max(10, H * 0.022)
        # Inspiration (Flamme)
        pygame.draw.rect(s, (30, 20, 14), (x, y, b, h), border_radius=6)
        f = sp.insp
        if f > 0:
            pygame.draw.rect(s, g.ORANGE if sp.insp_aktiv else g.GOLD, (x, y + h * (1 - f), b, h * f), border_radius=6)
            if f >= 0.5:
                g.leuchten(s, (x + b / 2, y + h * (1 - f)), b * 2, (255, 120, 20), 0.8)
        pygame.draw.line(s, g.CHAMP, (x - 2, y + h / 2), (x + b + 2, y + h / 2), 1)
        if not zwei:
            g.text_zeigen(s, "Inspiration", int(H * 0.024), (x + b / 2, y + h + H * 0.03), g.TX2)
        # Publikum
        x2 = x + b * 2.2
        pygame.draw.rect(s, (30, 20, 14), (x2, y, b, h), border_radius=6)
        p = sp.publikum
        farbe = g.misch(g.ROT, g.GRUEN, p)
        pygame.draw.rect(s, farbe, (x2, y + h * (1 - p), b, h * p), border_radius=6)
        if not zwei:
            g.text_zeigen(s, "Publikum", int(H * 0.024), (x2 + b / 2, y + h + H * 0.065), g.TX2)
        if f >= 0.5 and not sp.insp_aktiv and not self.app.e["insp_auto"]:
            g.text_zeigen(s, "Außen!", int(H * 0.03), (x + b, y - H * 0.03), g.GOLD2)


def heller_rand(c):
    return g.heller(c, 0.7)


class Ergebnis(Szene):
    def __init__(self, app, art, spieler, lied):
        super().__init__(app)
        self.art = art
        self.spieler = spieler
        self.lied = lied
        self.neu_rekord = {}
        for sp in spieler:
            if sp.ausgebuht:
                continue
            self.neu_rekord[sp.nr] = app.rekord_eintragen(lied["id"], sp, art)
        self.t0 = time.monotonic()
        self.funken = g.Funken(300)

    def betreten(self):
        self.hg = Hintergrundbild(self.app, self.lied["thema"], self.lied["bpm"], g.hex2rgb(self.lied["farbe"]))

    def ereignis(self, ev, nav):
        if time.monotonic() - self.t0 < 1.0:
            return
        if nav in ("ok", "zurueck"):
            neu = [sp.kopie() for sp in self.spieler]
            self.app.wechsel(Liedwahl(self.app, self.art, neu))

    def tipp(self, pos):
        self.ereignis(None, "ok")

    def zeichnen(self, s):
        W, H = s.get_size()
        self.hg.zeichnen(s)
        abdunkeln(s, 140)
        g.text_zeigen(s, self.lied["titel"], int(H * 0.06), (W / 2, H * 0.08), g.GOLD2, fett=True)
        n = len(self.spieler)
        sieger = None
        if n == 2 and self.art == "duell":
            a, b = self.spieler
            sieger = a if a.punkte > b.punkte else (b if b.punkte > a.punkte else None)
            g.text_zeigen(s, f"Spieler {sieger.nr} gewinnt!" if sieger else "Unentschieden!", int(H * 0.07),
                          (W / 2, H * 0.18), g.ORANGE, fett=True)
        elif n == 2:
            ges = sum(sp.punkte for sp in self.spieler)
            g.text_zeigen(s, f"Zusammen: {ges:,} Punkte".replace(",", "."), int(H * 0.06), (W / 2, H * 0.18), g.ORANGE)
        dt = time.monotonic() - self.t0
        for i, sp in enumerate(self.spieler):
            cx = W / 2 if n == 1 else W * (0.27 + 0.46 * i)
            y = H * (0.25 if n == 1 else 0.3)
            if n > 1:
                g.text_zeigen(s, f"Spieler {sp.nr}" + (" (Bass)" if sp.teil == "bass" else ""), int(H * 0.045),
                              (cx, y), g.SPUR_FARBEN[0 if sp.nr == 1 else 3])
                y += H * 0.07
            sterne = 0 if sp.ausgebuht else sp.sterne()
            for k in range(5):
                an = k < sterne and dt > 0.4 + k * 0.25
                x = cx + (k - 2) * H * 0.09
                if an:
                    g.leuchten(s, (x, y + H * 0.05), H * 0.06, (255, 160, 30), 0.8)
                g.text_zeigen(s, "★", int(H * 0.09), (x, y + H * 0.05), g.GOLD2 if an else (60, 50, 40))
            y += H * 0.14
            g.text_zeigen(s, f"{sp.punkte:,}".replace(",", "."), int(H * 0.08), (cx, y), g.CHAMP, fett=True)
            y += H * 0.08
            zeilen = [f"Treffer: {sp.getroffen} von {sp.getroffen + sp.verpasst} ({sp.quote() * 100:.0f} %)",
                      f"Längste Serie: {sp.max_combo}", f"Genau auf den Punkt: {sp.perfekt}",
                      f"{chart.STUFEN_NAME[sp.stufe]} · {MODUS_NAME[sp.modus]}"]
            if sp.ausgebuht:
                zeilen.insert(0, "Ausgebuht – nächstes Mal!")
            for z in zeilen:
                g.text_zeigen(s, z, int(H * 0.034), (cx, y), g.TX2)
                y += H * 0.048
            if self.neu_rekord.get(sp.nr):
                g.text_zeigen(s, "Neuer Rekord!", int(H * 0.05), (cx, y + H * 0.02), g.ORANGE, fett=True)
                if self.app.e["grafik"] and len(self.funken.p) < 250:
                    self.funken.neu(cx + (time.monotonic() * 977 % 1 - 0.5) * W * 0.3, H, 0, -200, 1.6, 3, g.GOLD2)
        self.funken.schritt(self.app.dt, 60)
        self.funken.zeichnen(s)
        g.text_zeigen(s, "✓ weiter", int(H * 0.035), (W / 2, H * 0.94), g.TX2)


class Pegel(Szene):
    """Ton & Mikrofon: alle Pegel mit Live-Anzeige."""

    def __init__(self, app, zurueck):
        super().__init__(app)
        self.zurueck = zurueck
        self.bauen()

    def bauen(self, wahl=0):
        p = self.app.e["pegel"]
        kanal = {0: "aus", 1: "Eingang 1", 2: "Eingang 2", 3: "Eingang 1 + 2"}[int(p["mic_kanal"])]
        self.m = Menue([("master", "Gesamt", f"{p['master'] * 100:.0f} %"), ("musik", "Musik (Band)", f"{p['musik'] * 100:.0f} %"),
                        ("lead", "Melodie", f"{p['lead'] * 100:.0f} %"), ("bass", "Bass", f"{p['bass'] * 100:.0f} %"),
                        ("sfx", "Effekt-Geräusche", f"{p['sfx'] * 100:.0f} %"),
                        ("mic_kanal", "Mikrofon-Eingang", kanal), ("mic", "Mikrofon", f"{p['mic'] * 100:.0f} %"),
                        ("hall", "Hall auf dem Mikrofon", f"{p['hall'] * 100:.0f} %"),
                        ("ducking", "Musik leiser beim Sprechen", f"{p['ducking'] * 100:.0f} %"),
                        ("fertig", "Fertig", None)], wahl)

    def ereignis(self, ev, nav):
        if nav == "zurueck":
            return self.fertig()
        self.m.nav(nav)
        if nav in ("links", "rechts"):
            self.aendern(1 if nav == "rechts" else -1)
        elif nav == "ok":
            if self.m.key == "fertig":
                self.fertig()
            else:
                self.aendern(1)

    def tipp(self, pos):
        if self.m.tipp(pos):
            if self.m.key == "fertig":
                self.fertig()
            else:
                W = self.app.groesse[0]
                self.aendern(1 if pos[0] > W / 2 else -1)

    def aendern(self, d):
        k = self.m.key
        p = self.app.e["pegel"]
        if k == "mic_kanal":
            p[k] = (int(p[k]) + d) % 4
        elif k in p:
            grenze = 1.5 if k in ("master", "musik", "lead", "bass", "mic") else 1.0
            p[k] = round(max(0.0, min(grenze, p[k] + d * 0.05)), 2)
        self.app.ton.cmd(cmd="pegel", **p)
        self.app.sfx("menue")
        self.bauen(self.m.wahl)

    def fertig(self):
        self.app.speichern()
        self.app.wechsel(self.zurueck, neu=False)

    def zeichnen(self, s):
        W, H = s.get_size()
        s.fill(g.BG)
        g.text_zeigen(s, "Ton & Mikrofon", int(H * 0.06), (W / 2, H * 0.07), g.GOLD2, fett=True)
        bw = min(W * 0.62, H * 1.15)
        self.m.zeichnen(s, (W * 0.04, H * 0.13, bw, H * 0.8), int(H * 0.032), mit_pfeilen=True)
        # Pegelanzeigen
        x = W * 0.04 + bw + W * 0.05
        for i, (name, wert) in enumerate((("Ausgang", self.app.ton.aus()), ("Mikrofon", self.app.ton.mic()))):
            xx = x + i * W * 0.12
            h = H * 0.6
            y = H * 0.15
            pygame.draw.rect(s, (30, 22, 16), (xx, y, W * 0.05, h), border_radius=8)
            v = min(1.0, max(0.0, (20 * math.log10(max(1e-5, wert)) + 48) / 48))
            farbe = g.GRUEN if v < 0.75 else (g.GELB if v < 0.92 else g.ROT)
            pygame.draw.rect(s, farbe, (xx, y + h * (1 - v), W * 0.05, h * v), border_radius=8)
            g.text_zeigen(s, name, int(H * 0.03), (xx + W * 0.025, y + h + H * 0.04), g.TX2)
        g.text_zeigen(s, "Mikro an Zynthian-Eingang 1 oder 2 – ideal: grün, kurz gelb", int(H * 0.028),
                      (x + W * 0.1, H * 0.86), g.TX2)
        g.text_zeigen(s, "◀ ▶ ändern  ·  zurück = fertig", int(H * 0.028), (W / 2, H * 0.96), g.TX2)


class Einstellungen(Szene):
    def __init__(self, app, wahl=0):
        super().__init__(app)
        self.bauen(wahl)

    def bauen(self, wahl=0):
        e = self.app.e
        self.m = Menue([
            ("grafik", "Grafik", ["Ruhig", "Mittel", "Prächtig"][e["grafik"]]),
            ("fps", "Bilder pro Sekunde", str(e["fps"])),
            ("tempo", "Notentempo", {"langsam": "Langsam", "normal": "Normal", "schnell": "Schnell"}[e["tempo"]]),
            ("versatz", "Verzögerung ausgleichen", f"{e['versatz_ms']} ms"),
            ("kalib", "Verzögerung messen …", None),
            ("durchfallen", "Ausbuhen möglich", "an" if e["durchfallen"] else "aus"),
            ("insp_auto", "Inspiration", "zündet selbst" if e["insp_auto"] else "äußere Tasten zugleich"),
            ("anlernen1", "Controller einrichten: Spieler 1 …", None),
            ("anlernen2", "Controller einrichten: Spieler 2 …", None),
            ("ausgabe", "Bild", {"auto": "automatisch", "display": "Zynthian-Display", "hdmi": "Beamer (HDMI)",
                                 "beide": "Display + Beamer"}[e["ausgabe"]]),
            ("fertig", "Fertig", None)], wahl)

    def ereignis(self, ev, nav):
        if nav == "zurueck":
            return self.fertig()
        self.m.nav(nav)
        if nav in ("links", "rechts"):
            self.aendern(1 if nav == "rechts" else -1)
        elif nav == "ok":
            self.aendern(1, ok=True)

    def tipp(self, pos):
        if self.m.tipp(pos):
            self.aendern(1, ok=True)

    def aendern(self, d, ok=False):
        e = self.app.e
        k = self.m.key
        if k == "grafik":
            e["grafik"] = (e["grafik"] + d) % 3
            self.app.bild_neu()
        elif k == "fps":
            e["fps"] = 30 if e["fps"] == 60 else 60
        elif k == "tempo":
            t = ["langsam", "normal", "schnell"]
            e["tempo"] = t[(t.index(e["tempo"]) + d) % 3]
        elif k == "versatz":
            e["versatz_ms"] = max(-200, min(300, e["versatz_ms"] + d * 5))
        elif k == "kalib" and ok:
            return self.app.wechsel(Kalibrieren(self.app))
        elif k == "durchfallen":
            e["durchfallen"] = not e["durchfallen"]
        elif k == "insp_auto":
            e["insp_auto"] = not e["insp_auto"]
        elif k.startswith("anlernen") and ok:
            return self.app.wechsel(Anlernen(self.app, int(k[-1])))
        elif k == "ausgabe":
            a = ["auto", "display", "hdmi", "beide"]
            e["ausgabe"] = a[(a.index(e["ausgabe"]) + d) % 4]
            self.app.meldung("Bild-Ausgabe gilt ab dem nächsten Start von Bard Hero")
        elif k == "fertig" and ok:
            return self.fertig()
        self.app.sfx("menue")
        self.app.speichern()
        self.bauen(self.m.wahl)

    def fertig(self):
        self.app.speichern()
        self.app.wechsel(Titel(self.app))

    def zeichnen(self, s):
        W, H = s.get_size()
        s.fill(g.BG)
        g.text_zeigen(s, "Einstellungen", int(H * 0.06), (W / 2, H * 0.07), g.GOLD2, fett=True)
        bw = min(W * 0.8, H * 1.4)
        self.m.zeichnen(s, (W / 2 - bw / 2, H * 0.13, bw, H * 0.78), int(H * 0.032), mit_pfeilen=True)
        g.text_zeigen(s, f"◀ ▶ ändern  ·  ✓ öffnen  ·  Bard Hero {VERSION}", int(H * 0.028), (W / 2, H * 0.96), g.TX2)


class Kalibrieren(Szene):
    """Klicks im Takt – im Takt mitdrücken. Aus dem Mittel wird die Verzögerung."""

    def betreten(self):
        self.bpm = 100
        self.schlag = 60 / self.bpm
        self.n = 16
        self.nr = self.app.neue_nr()
        self.app.ton.cmd(cmd="leer", nr=self.nr, dauer=self.n * self.schlag + 3)
        self.gestartet = False
        self.abw = []
        self.fertig_t = 0

    def update(self, dt):
        if not self.gestartet and self.app.ton.geladen() == self.nr:
            self.gestartet = True
            klicks = [k * self.schlag for k in range(self.n)]
            self.app.ton.cmd(cmd="start", ab=-1.0, klicks=klicks)
        if self.gestartet and not self.fertig_t and self.app.ton.liedzeit() > self.n * self.schlag + 0.5:
            self.fertig_t = time.monotonic()
            if len(self.abw) >= 6:
                self.abw.sort()
                mitte = self.abw[len(self.abw) // 4: len(self.abw) * 3 // 4] or self.abw
                self.ergebnis = int(round(sum(mitte) / len(mitte) * 1000 / 5) * 5)
                self.app.e["versatz_ms"] = max(-200, min(300, self.ergebnis))
                self.app.speichern()
            else:
                self.ergebnis = None

    def ereignis(self, ev, nav):
        if self.fertig_t or nav == "zurueck":
            if nav in ("ok", "zurueck") or self.fertig_t and time.monotonic() - self.fertig_t > 1:
                self.app.ton.cmd(cmd="stop")
                return self.app.wechsel(Einstellungen(self.app, 4))
            return
        if self.gestartet and (ev[0] == "an" or (ev[0] == "taste" and ev[4])):
            t = self.app.ton.liedzeit(ev[3])
            k = round(t / self.schlag)
            if 0 <= k < self.n:
                self.abw.append(t - k * self.schlag)

    def tipp(self, pos):
        self.ereignis(("taste", "maus", 0, time.monotonic(), 1), None)

    def zeichnen(self, s):
        W, H = s.get_size()
        s.fill(g.BG)
        g.text_zeigen(s, "Verzögerung messen", int(H * 0.06), (W / 2, H * 0.1), g.GOLD2, fett=True)
        if not self.fertig_t:
            g.text_zeigen(s, "Drück bei jedem Klick eine Taste – genau im Takt", int(H * 0.045), (W / 2, H * 0.3), g.CHAMP)
            t = self.app.ton.liedzeit()
            phase = (t / self.schlag) % 1 if t > 0 else 1
            g.leuchten(s, (W / 2, H * 0.58), H * (0.12 + 0.1 * (1 - phase) ** 4), g.GLUT, 0.9)
            g.text_zeigen(s, f"{len(self.abw)} / {self.n}", int(H * 0.05), (W / 2, H * 0.82), g.TX2)
        else:
            if self.ergebnis is None:
                g.text_zeigen(s, "Zu wenige Treffer – bitte nochmal versuchen", int(H * 0.045), (W / 2, H * 0.45), g.ROT)
            else:
                g.text_zeigen(s, f"Ausgleich: {self.ergebnis} ms", int(H * 0.07), (W / 2, H * 0.45), g.GRUEN)
                g.text_zeigen(s, "ist gespeichert", int(H * 0.04), (W / 2, H * 0.55), g.TX2)
            g.text_zeigen(s, "✓ zurück", int(H * 0.035), (W / 2, H * 0.9), g.TX2)


class Anlernen(Szene):
    """Controller einrichten: Bauform wählen (5er-Reihe, 3 + 3, 6er-Reihe, Keytar), Tasten der Reihe nach drücken,
    bei Gitarren mit Anschlag-Leiste auch den Anschlag. Gilt für jedes Gerät (MIDI, Gamepad, Tastatur, Zynthian)."""

    def __init__(self, app, nr, geraet=None, zurueck=None):
        super().__init__(app)
        self.nr = nr
        self.geraet = geraet
        self.zurueck = zurueck
        self.schritt = "form" if geraet else "geraet"
        self.form = None
        self.spur = 0
        self.belegung = {}
        self.anschlag = []
        self.seit = 0.0
        self.menue_bauen()

    def menue_bauen(self):
        vorschlag = self.app.form_vorschlag(self.geraet) if self.geraet else "keytar"
        wahl = next((i for i, (k, _) in enumerate(FORM_WAHL) if k == vorschlag), 0)
        self.m = Menue([(k, t, None) for k, t in FORM_WAHL], wahl)

    def raus(self):
        z = self.zurueck
        if z is None:
            return self.app.wechsel(Einstellungen(self.app, 6 + self.nr))
        if hasattr(z, "baue_menue"):
            z.baue_menue()
        self.app.wechsel(z, neu=False)

    def gedrueckt(self, ev):
        return ev[0] == "an" or (ev[0] == "taste" and ev[4])

    def ereignis(self, ev, nav):
        if self.schritt == "geraet":
            if nav == "zurueck" and ev[1] in ("zyn", "tast"):
                return self.raus()
            if self.gedrueckt(ev):
                self.geraet = ev[1]
                self.schritt = "form"
                self.menue_bauen()
                self.app.sfx("ok")
            return
        if self.schritt == "form":
            if nav == "zurueck":
                return self.raus()
            self.m.nav(nav)
            if nav == "ok":
                self.form_gewaehlt()
            return
        # Tasten und Anschlag: nur das gewählte Gerät zählt; andere Geräte dürfen abbrechen
        if ev[1] != self.geraet:
            if nav == "zurueck":
                return self.raus()
            return
        if not self.gedrueckt(ev):
            return
        schluessel = str(ev[2])
        if self.schritt == "tasten":
            if schluessel in self.belegung:
                return
            self.belegung[schluessel] = self.spur
            if ev[0] == "an":
                self.belegung.setdefault("k" + str(ev[2] % 12), self.spur)
            self.app.sfx("ok")
            self.spur += 1
            if self.spur >= chart.FORMEN[self.form]["tasten"]:
                if self.geraet.startswith("pad"):
                    self.schritt = "anschlag"
                    self.seit = time.monotonic()
                else:
                    self.speichern()
        elif self.schritt == "anschlag":
            if schluessel in self.belegung:
                return
            self.anschlag = ["hoch", "runter"] if schluessel in ("hoch", "runter") else [schluessel]
            self.app.sfx("ok")
            self.speichern()

    def tipp(self, pos):
        if self.schritt == "form" and self.m.tipp(pos):
            self.form_gewaehlt()
        elif self.schritt == "anschlag":
            self.speichern()

    def form_gewaehlt(self):
        self.form = self.m.key
        self.app.sfx("ok")
        if self.form == "keytar":
            # zurück zur Standardbelegung (Keytar C D E F G, Tastatur 1–5 …)
            self.app.e["belegung"].pop(self.ziel(), None)
            self.app.speichern()
            self.app.meldung(f"{self.app.geraet_name(self.geraet)}: Standard-Belegung")
            return self.raus()
        self.schritt = "tasten"
        self.spur = 0
        self.belegung = {}

    def ziel(self):
        return self.geraet.rsplit(":", 1)[0] if self.geraet.startswith("midi:") else self.geraet

    def speichern(self):
        b = dict(self.belegung)
        b["_form"] = self.form
        if self.anschlag:
            b["_anschlag"] = self.anschlag
        self.app.e["belegung"][self.ziel()] = b
        self.app.speichern()
        extra = " · mit Anschlag-Leiste" if self.anschlag else ""
        self.app.meldung(f"{self.app.geraet_name(self.geraet)}: {chart.FORMEN[self.form]['name']}{extra} gespeichert")
        self.raus()

    def update(self, dt):
        if self.schritt == "anschlag" and time.monotonic() - self.seit > 6:
            self.speichern()                        # keine Anschlag-Leiste → jede Taste zählt sofort

    def zeichnen(self, s):
        W, H = s.get_size()
        s.fill(g.BG)
        g.text_zeigen(s, f"Controller einrichten · Spieler {self.nr}", int(H * 0.06), (W / 2, H * 0.09), g.GOLD2,
                      fett=True)
        if self.geraet:
            g.text_zeigen(s, self.app.geraet_name(self.geraet), int(H * 0.035), (W / 2, H * 0.16), g.TX2)
        if self.schritt == "geraet":
            g.text_zeigen(s, "Drück eine Taste auf dem Controller, den du einrichten willst", int(H * 0.042),
                          (W / 2, H * 0.45), g.CHAMP)
        elif self.schritt == "form":
            g.text_zeigen(s, "Wie sehen die Tasten aus?", int(H * 0.045), (W / 2, H * 0.24), g.CHAMP)
            mw = W * 0.5
            self.m.zeichnen(s, (W * 0.04, H * 0.3, mw, H * 0.52), int(H * 0.034))
            form = self.m.key
            zeichne_controller(s, (W * 0.04 + mw + (W * 0.96 - mw - W * 0.04) / 2, H * 0.56),
                               min(H * 0.1, (W - mw) * 0.16), form)
            erkannt = self.app.pad_name(self.geraet)
            if erkannt:
                g.text_zeigen(s, f"Erkannt: {erkannt}", int(H * 0.03), (W / 2, H * 0.86), g.GLUT)
        elif self.schritt == "tasten":
            ges = chart.FORMEN[self.form]["tasten"]
            g.text_zeigen(s, f"Drück: {tasten_text(self.form, self.spur)}", int(H * 0.05), (W / 2, H * 0.28), g.CHAMP)
            g.text_zeigen(s, f"{self.spur + 1} von {ges}", int(H * 0.035), (W / 2, H * 0.35), g.TX2)
            zeichne_controller(s, (W / 2, H * 0.58), H * 0.1, self.form, aktiv=self.spur, fertig=self.spur - 1)
        elif self.schritt == "anschlag":
            g.text_zeigen(s, "Hat deine Gitarre eine Anschlag-Leiste?", int(H * 0.05), (W / 2, H * 0.34), g.CHAMP)
            g.text_zeigen(s, "Dann jetzt einmal anschlagen.", int(H * 0.042), (W / 2, H * 0.44), g.GOLD2)
            rest = max(0, 6 - (time.monotonic() - self.seit))
            g.text_zeigen(s, f"Sonst einfach warten ({rest:.0f} s) – dann zählt jeder Tastendruck sofort.",
                          int(H * 0.034), (W / 2, H * 0.56), g.TX2)
        g.text_zeigen(s, "BACK / Esc = abbrechen", int(H * 0.03), (W / 2, H * 0.94), g.TX2)


class System(Szene):
    def __init__(self, app, zurueck):
        super().__init__(app)
        self.zurueck = zurueck
        self.m = Menue([("abbrechen", "Abbrechen", None), ("zynthian", "Zum Mischpult", None),
                        ("aus", "Ausschalten", None), ("neustart", "Neu starten", None)])

    def ereignis(self, ev, nav):
        if nav == "zurueck":
            return self.app.wechsel(self.zurueck, neu=False)
        self.m.nav(nav)
        if nav == "ok":
            self.waehlen()

    def tipp(self, pos):
        if self.m.tipp(pos):
            self.waehlen()

    def waehlen(self):
        k = self.m.key
        if k == "abbrechen":
            return self.app.wechsel(self.zurueck, neu=False)
        self.app.beenden(k)

    def zeichnen(self, s):
        W, H = s.get_size()
        s.fill(g.BG)
        g.text_zeigen(s, "Bard Hero verlassen?", int(H * 0.07), (W / 2, H * 0.15), g.GOLD2, fett=True)
        bw = min(W * 0.5, H * 0.9)
        self.m.zeichnen(s, (W / 2 - bw / 2, H * 0.3, bw, H * 0.5))


# ---------------------------------------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------------------------------------
class App:
    def __init__(self):
        self.e = einstellungen_laden()
        try:
            with open(REKORD_DATEI, encoding="utf-8") as f:
                self.rekorde = json.load(f)
        except (OSError, ValueError):
            self.rekorde = {}
        pygame.init()
        pygame.joystick.init()
        self.pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        pygame.mouse.set_visible(False)
        self.bildschirm = None
        self.szene = None
        self.bild_neu()
        pygame.display.set_caption("Bard Hero")
        self.ton = Ton()
        self.eingaben = eingabe.Eingaben()
        self.tasten_proc = self._tasten_starten()
        self.nr = 0
        self.dt = 0.016
        self.szene = None
        self.meldung_text = ("", 0)
        self.render = {"nr": 0, "gesamt": 0, "teil": 0, "titel": "", "proc": None, "fertig": False, "pausiert": False}
        self.lieder = []
        self.lieder_lesen()
        self.laeuft = True
        self.ziel = None

    # ---- Bild ----
    def bild_neu(self):
        info = pygame.display.get_desktop_sizes()[0] if hasattr(pygame.display, "get_desktop_sizes") else (800, 480)
        dw, dh = info if info and info[0] else (800, 480)
        hoehe = {0: 432, 1: 540, 2: 720}[self.e["grafik"]]
        hoehe = min(hoehe, dh)
        breite = int(round(hoehe * dw / dh / 2) * 2)
        self.groesse = (breite, hoehe)
        flags = 0
        if os.environ.get("SDL_VIDEODRIVER") != "dummy" and not os.environ.get("BH_FENSTER"):
            flags = pygame.SCALED | pygame.FULLSCREEN
        try:
            self.bildschirm = pygame.display.set_mode(self.groesse, flags, vsync=1 if flags else 0)
        except Exception:
            self.bildschirm = pygame.display.set_mode(self.groesse, flags)
        if self.szene is not None:
            self.szene.betreten()

    # ---- Lieder ----
    def lieder_lesen(self):
        import lieder
        raus = []
        for L in lieder.alle():
            ordner = os.path.join(DATEN, "lieder", L.id)
            bereit = os.path.isfile(os.path.join(ordner, "fertig")) and os.path.isfile(os.path.join(ordner, "chart.json"))
            raus.append({"id": L.id, "titel": L.titel, "untertitel": L.untertitel, "stimmung": L.stimmung,
                         "schwierigkeit": L.schwierigkeit, "farbe": L.farbe, "thema": L.thema, "bpm": L.bpm,
                         "tonart": tonart_text(L.tonart),
                         "laenge": L.sekunden(L.pos), "bereit": bereit})
        self.lieder = raus

    def lieder_bereit(self):
        return any(x["bereit"] for x in self.lieder) and (self.render["fertig"] or self.render["nr"] > 1
                                                           or all(x["bereit"] for x in self.lieder))

    def render_starten(self):
        if self.render["proc"] is not None:
            return
        py = python_mit("numpy")
        cmd = [py, os.path.join(HIER, "rendern.py"), "--rate", str(int(self.ton.rate()))]
        if shutil.which("nice"):
            cmd = ["nice", "-n", "15"] + cmd
        try:
            self.render["proc"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                                   start_new_session=True, env=dict(os.environ, BH_DATEN=DATEN))
            os.set_blocking(self.render["proc"].stdout.fileno(), False)
        except OSError as e:
            print("Rendern startet nicht:", e, file=sys.stderr)
            self.render["fertig"] = True

    def render_lesen(self):
        p = self.render["proc"]
        if p is None or self.render["fertig"]:
            return
        try:
            while True:
                z = p.stdout.readline()
                if not z:
                    break
                t = z.split()
                if t[0] == "LIED":
                    self.render.update(nr=int(t[1]), gesamt=int(t[2]), teil=0, titel=" ".join(t[4:]))
                    self.lieder_lesen()
                elif t[0] == "TEIL":
                    self.render["teil"] += 1
                elif t[0] == "FERTIG":
                    self.render["fertig"] = True
                    self.lieder_lesen()
        except (OSError, ValueError, IndexError):
            pass
        if p.poll() is not None and not self.render["fertig"]:
            self.render["fertig"] = True
            self.lieder_lesen()

    def render_pausieren(self, an):
        p = self.render["proc"]
        if p is None or p.poll() is not None or self.render["pausiert"] == an:
            return
        try:
            os.killpg(p.pid, signal.SIGSTOP if an else signal.SIGCONT)
            self.render["pausiert"] = an
        except OSError:
            pass

    # ---- Helfer ----
    def _tasten_starten(self):
        if os.environ.get("BH_KEINE_TASTEN") or not os.path.exists("/zynthian"):
            return None
        py = "/zynthian/venv/bin/python3" if os.path.exists("/zynthian/venv/bin/python3") else "/usr/bin/python3"
        try:
            return subprocess.Popen([py, os.path.join(HIER, "tasten.py")])
        except OSError:
            return None

    def neue_nr(self):
        self.nr += 1
        return self.nr + int(time.time()) % 100000 * 10

    def sfx(self, name, laut=1.0):
        self.ton.cmd(cmd="sfx", name=name, laut=laut)

    def speichern(self):
        speichern(EINST_DATEI, self.e)

    def meldung(self, text):
        self.meldung_text = (text, time.monotonic() + 3)

    def geraet_name(self, geraet):
        if geraet is None:
            return "–"
        if geraet == "zyn":
            return "Zynthian-Tasten"
        if geraet == "tast":
            return "Tastatur"
        if geraet.startswith("pad"):
            return "Gamepad " + geraet[3:]
        if geraet == "maus":
            return "Touch"
        return self.eingaben.geraete.get(geraet, geraet.split(":")[1].replace("_", " "))

    def pad_name(self, geraet):
        if geraet and geraet.startswith("pad"):
            try:
                return self.pads[int(geraet[3:])].get_name()
            except (IndexError, ValueError, pygame.error):
                return None
        return None

    def form_vorschlag(self, geraet):
        """Bauform, die zum Gerät passt: angelernt, sonst am Namen erkannt (Gamepad), sonst Keytar."""
        bel = eingabe.belegung_von(self.e["belegung"], geraet)
        if bel and bel.get("_form"):
            return bel["_form"]
        name = (self.pad_name(geraet) or "").lower()
        if name:
            if "live" in name or "ghl" in name:
                return "3x2"
            return "reihe5"
        if geraet and (geraet.startswith("midi:")):
            return "keytar"
        return "reihe5"

    def form_von(self, geraet):
        """Bauform für die Notenbahn (Keytar = 5 Tasten C D E F G)."""
        f = self.form_vorschlag(geraet)
        return "reihe5" if f == "keytar" else f

    def anzeige_form(self, geraet):
        bel = eingabe.belegung_von(self.e["belegung"], geraet)
        if bel and bel.get("_form"):
            return bel["_form"]
        if geraet in ("tast", "zyn") or not geraet:
            return "reihe5"
        return self.form_vorschlag(geraet)

    def einricht_hinweis(self, geraet):
        """Kurzer Hinweis, wenn ein Gerät noch eingerichtet werden sollte."""
        if not geraet or eingabe.belegung_von(self.e["belegung"], geraet):
            return ""
        if geraet.startswith("pad"):
            return "bitte einrichten: ✓ auf „Controller“"
        if geraet.startswith("midi:"):
            return "anders belegt? ✓ auf „Controller“"
        return ""

    def spur_namen(self, sp, anzahl=5):
        """Beschriftung unter den Tasten der Notenbahn (None = keine)."""
        g0 = sp.haupt
        if sp.form == "3x2":
            return None
        bel = eingabe.belegung_von(self.e["belegung"], g0)
        if g0 == "zyn" and not bel:
            return ["F1", "F2", "F3", "F4", "PLAY", ""]
        if g0 == "tast" and not bel:
            return ["1", "2", "3", "4", "5", "6"]
        if g0 and g0.startswith("pad"):
            return None
        if bel:
            namen = [""] * 6
            for k, v in bel.items():
                if k.isdigit() and isinstance(v, int) and v < 6 and not namen[v]:
                    namen[v] = chart.NAMEN[int(k) % 12] if g0.startswith("midi:") else k
            return namen
        return eingabe.SPUR_NAMEN_MIDI + [""]

    def rekord_schluessel(self, lied, sp):
        return f"{lied}:{sp.teil}:{sp.modus}:{sp.stufe}"

    def rekord_eintragen(self, lied, sp, art):
        k = self.rekord_schluessel(lied, sp)
        liste = self.rekorde.setdefault(k, [])
        bester = liste[0]["punkte"] if liste else -1
        liste.append({"punkte": sp.punkte, "sterne": sp.sterne(), "quote": round(sp.quote(), 3),
                      "datum": time.strftime("%Y-%m-%d"), "art": art})
        liste.sort(key=lambda x: -x["punkte"])
        del liste[5:]
        speichern(REKORD_DATEI, self.rekorde)
        return sp.punkte > bester and sp.punkte > 0

    def wechsel(self, szene, neu=True):
        self.szene = szene
        if neu or not getattr(szene, "_betreten", False):
            szene.betreten()
            szene._betreten = True

    def beenden(self, ziel):
        self.ziel = ziel
        self.laeuft = False

    # ---- Hauptschleife ----
    def lauf(self):
        self.wechsel(Lade(self))
        self.uhr = pygame.time.Clock()
        self.start_render_ab = time.monotonic() + 1.0
        while self.laeuft:
            self.schritt()
        self.aufraeumen()

    def schritt(self, dt=None):
        self.dt = dt if dt is not None else min(0.1, self.uhr.tick(self.e["fps"]) / 1000.0)
        self.ton.lesen()
        if self.render["proc"] is None and self.ton.bereit and time.monotonic() > self.start_render_ab:
            self.render_starten()
        self.render_lesen()
        # pygame-Ereignisse
        jetzt = time.monotonic()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.beenden("ende")
            elif ev.type in (pygame.KEYDOWN, pygame.KEYUP):
                name = pygame.key.name(ev.key)
                if ev.type == pygame.KEYDOWN and name == "f12":
                    self.beenden("ende")
                self.eingaben.q.append(("taste", "tast", name, jetzt, 1 if ev.type == pygame.KEYDOWN else 0))
            elif ev.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                self.eingaben.q.append(("taste", f"pad{ev.joy}", str(ev.button), jetzt,
                                        1 if ev.type == pygame.JOYBUTTONDOWN else 0))
            elif ev.type == pygame.JOYHATMOTION:
                r = {(0, 1): "hoch", (0, -1): "runter", (-1, 0): "links", (1, 0): "rechts"}.get(tuple(ev.value))
                if r:
                    self.eingaben.q.append(("taste", f"pad{ev.joy}", r, jetzt, 1))
            elif ev.type == pygame.JOYDEVICEADDED:
                self.pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
            elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                pos = ev.pos if ev.type == pygame.MOUSEBUTTONDOWN else (ev.x * self.groesse[0], ev.y * self.groesse[1])
                self.szene.tipp(pos)
        for ev in self.eingaben.holen():
            if ev[0] == "taste" and ev[2] == "BACK_LANG":
                if not isinstance(self.szene, System):
                    if isinstance(self.szene, Spiel):
                        self.szene.pausieren()
                    self.wechsel(System(self, self.szene))
                continue
            nav = eingabe.navigation(ev)
            self.szene.ereignis(ev, nav)
        self.szene.update(self.dt)
        s = self.bildschirm
        self.szene.zeichnen(s)
        text, bis = self.meldung_text
        if text and time.monotonic() < bis:
            W, H = self.groesse
            r = g.text(text, int(H * 0.035)).get_rect(center=(W / 2, H * 0.88))
            g.rrect(s, (40, 26, 12), r.inflate(H * 0.06, H * 0.03), 12)
            g.text_zeigen(s, text, int(H * 0.035), r.center, g.GOLD2)
        pygame.display.flip()

    def aufraeumen(self):
        self.ton.cmd(cmd="stop")
        self.ton.ende()
        p = self.render["proc"]
        if p is not None and p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGCONT)
                os.killpg(p.pid, signal.SIGTERM)
            except OSError:
                pass
        if self.tasten_proc is not None:
            self.tasten_proc.terminate()
        self.eingaben.leds_alle((0, 0, 0))
        self.eingaben.ende()
        pygame.quit()
        if self.ziel in ("zynthian", "aus", "neustart") and os.path.exists(BEFEHL):
            cmd = [BEFEHL, self.ziel]
            if shutil.which("systemd-run"):
                cmd = ["systemd-run", "--no-block", "--collect", "--quiet"] + cmd
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    os.makedirs(os.path.join(DATEN, "lieder"), exist_ok=True)
    try:
        App().lauf()
    except Exception:
        import traceback
        text = traceback.format_exc()
        print(text, file=sys.stderr)
        try:
            with open(os.path.join(DATEN, "absturz.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + VERSION + "\n" + text + "\n")
        except OSError:
            pass
        for ende in ("ton", "tasten"):
            subprocess.call(["pkill", "-f", os.path.join(HIER, ende + ".py")], stderr=subprocess.DEVNULL)
        sys.exit(1)


if __name__ == "__main__":
    main()
