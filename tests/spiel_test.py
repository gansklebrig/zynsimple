"""Bard Hero ohne Bildschirm durchspielen: Menüs, Liedauswahl, Spiel mit einem „Roboter“, der fast alles trifft,
Duell mit zwei Geräten, Pause, Ergebnis, Pegel, Einstellungen. Speichert Bildschirmfotos.

Aufruf:  python3 tests/spiel_test.py [fotos-ordner]
Braucht gerenderte Lieder in BH_DATEN (sonst rendert es zwei Lieder mit dem eingebauten Synthesizer).
"""
import os
import random
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
SPIEL = os.path.join(os.path.dirname(HIER), "spiel")
FOTOS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bh-fotos"
os.makedirs(FOTOS, exist_ok=True)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("BH_TON", "sdl")
os.environ.setdefault("BH_KEINE_TASTEN", "1")
os.environ.setdefault("BH_DATEN", "/tmp/bh-test-daten")
sys.path[:0] = [SPIEL, os.path.join(SPIEL, "lieder")]

import pygame  # noqa: E402
import bardhero as bh  # noqa: E402

random.seed(4)
fehler = []


def foto(app, name):
    pygame.image.save(app.bildschirm, os.path.join(FOTOS, name + ".png"))


def laufen(app, sek, bot=None):
    ende = time.monotonic() + sek
    while time.monotonic() < ende and app.laeuft:
        if bot:
            bot(app)
        app.schritt(1 / 60)
        time.sleep(1 / 120)


def taste(app, name, geraet="tast"):
    t = time.monotonic()
    app.eingaben.q.append(("taste", geraet, name, t, 1))
    app.eingaben.q.append(("taste", geraet, name, t + 0.05, 0))
    laufen(app, 0.12)


def warten_auf(app, klasse, sek=120, bot=None):
    ende = time.monotonic() + sek
    while not isinstance(app.szene, klasse) and time.monotonic() < ende:
        laufen(app, 0.2, bot)
    if not isinstance(app.szene, klasse):
        fehler.append(f"{klasse.__name__} kam nicht (jetzt {type(app.szene).__name__})")
        return False
    return True


class Roboter:
    """Spielt die Noten eines Spielers über ein MIDI-Gerät – trifft etwa 92 %."""

    def __init__(self, sp, geraet, trefferquote=0.92):
        self.sp = sp
        self.geraet = geraet
        self.quote = trefferquote
        self.erledigt = set()

    def __call__(self, app):
        sz = app.szene
        if not isinstance(sz, bh.Spiel) or sz.zustand != "spielt" or sz.pause:
            return
        z = app.ton.z
        if not z or not app.ton.spielt():
            return
        t = app.ton.liedzeit()
        for i in range(self.sp.idx, min(len(self.sp.noten), self.sp.idx + 6)):
            n = self.sp.noten[i]
            if i in self.erledigt or n.t > t + 0.03:
                continue
            self.erledigt.add(i)
            if random.random() > self.quote:
                continue
            mono = n.t - z[1] + z[2] + random.gauss(0, 0.015)
            if self.sp.modus == "hero":
                note = [60, 62, 64, 65, 67][n.spur]
            else:
                note = 60 + n.spur
            app.eingaben.q.append(("an", self.geraet, note, mono, 100))
            ende = n.halten_bis or (n.t + 0.08)
            app.eingaben.q.append(("aus", self.geraet, note, mono + (ende - n.t), 0))


def daten_vorbereiten():
    daten = os.environ["BH_DATEN"]
    if any(os.path.isfile(os.path.join(daten, "lieder", x, "fertig")) for x in ("drache", "lagerfeuer")):
        return
    import rendern
    rendern.DATEN = daten
    rendern.fluidsynth = lambda: None
    rendern.alle(nur=["lagerfeuer", "drache"], melden=lambda t: None)


def main():
    daten_vorbereiten()
    app = bh.App()
    app.wechsel(bh.Lade(app))
    app.uhr = pygame.time.Clock()
    app.start_render_ab = time.monotonic() + 0.5
    laufen(app, 1.0)
    foto(app, "01-laden")
    if not warten_auf(app, bh.Titel, 300):
        return
    laufen(app, 1.0)
    foto(app, "02-titel")
    # Solo
    taste(app, "return")
    warten_auf(app, bh.Spielerwahl)
    taste(app, "up")
    taste(app, "right")              # Stufe ändern
    taste(app, "left")
    laufen(app, 0.5)
    foto(app, "03-spielerwahl")
    taste(app, "down")
    taste(app, "return")
    warten_auf(app, bh.Liedwahl)
    ids = [x["id"] for x in app.lieder]
    while app.lieder[app.szene.wahl]["id"] != "drache":
        taste(app, "down")
    laufen(app, 1.5)
    foto(app, "04-liedwahl")
    taste(app, "return")
    warten_auf(app, bh.Spiel)
    sz = app.szene
    sz.c["ende"] = 36
    rob = Roboter(sz.spieler[0], "midi:Keytar:1")
    laufen(app, 3.0, rob)
    foto(app, "05-einzaehlen")
    laufen(app, 12, rob)
    foto(app, "06-spiel")
    taste(app, "escape")
    laufen(app, 0.6)
    foto(app, "07-pause")
    taste(app, "return")             # weiter
    laufen(app, 6, rob)
    sp = sz.spieler[0]
    sp.insp = 1.0
    sz.inspiration(sp)
    laufen(app, 3, rob)
    foto(app, "08-inspiration")
    warten_auf(app, bh.Ergebnis, 60, rob)
    laufen(app, 2.5)
    foto(app, "09-ergebnis")
    print(f"Solo: {sp.punkte} Punkte, Treffer {sp.getroffen}/{sp.getroffen + sp.verpasst}, Fehlgriffe {sp.fehlgriffe}, "
          f"Serie {sp.max_combo}")
    if sp.quote() < 0.8:
        fehler.append(f"Roboter traf nur {sp.quote():.0%}")
    taste(app, "return")
    warten_auf(app, bh.Liedwahl)
    taste(app, "escape")
    warten_auf(app, bh.Spielerwahl)
    taste(app, "escape")
    warten_auf(app, bh.Titel)
    # Duell: zwei Geräte, Spieler 2 im Barden-Modus
    taste(app, "down")
    taste(app, "return")
    warten_auf(app, bh.Spielerwahl)
    t = time.monotonic()
    app.eingaben.q.append(("an", "midi:Keytar:1", 60, t, 100))
    laufen(app, 0.3)
    foto(app, "10-duell-geraet")
    app.eingaben.q.append(("an", "midi:BeatStep:1", 60, t, 100))
    laufen(app, 0.3)
    app.e["spieler"][1]["modus"] = "hero"
    app.szene.baue_menue()
    app.szene.m.wahl = 2
    taste(app, "right")              # Spieler 2: Barde
    laufen(app, 0.3)
    foto(app, "11-duell-optionen")
    app.szene.m.wahl = len(app.szene.m.e) - 1
    taste(app, "return")
    warten_auf(app, bh.Liedwahl)
    while app.lieder[app.szene.wahl]["id"] != "lagerfeuer":
        taste(app, "up")
    taste(app, "return")
    warten_auf(app, bh.Spiel)
    sz = app.szene
    sz.c["ende"] = 26
    r1 = Roboter(sz.spieler[0], "midi:Keytar:1", 0.95)
    r2 = Roboter(sz.spieler[1], "midi:BeatStep:1", 0.7)
    laufen(app, 20, lambda a: (r1(a), r2(a)))
    foto(app, "12-duell-spiel")
    warten_auf(app, bh.Ergebnis, 40, lambda a: (r1(a), r2(a)))
    laufen(app, 2.5)
    foto(app, "13-duell-ergebnis")
    a, b = sz.spieler
    if b.modus != "barde":
        fehler.append("Spieler 2 sollte im Barden-Modus spielen")
    print(f"Duell: P1 {a.punkte} ({a.quote():.0%}) · P2 {b.punkte} ({b.quote():.0%})")
    taste(app, "return")
    # Pegel & Einstellungen
    app.wechsel(bh.Titel(app))
    app.szene.m.wahl = 3
    taste(app, "return")
    warten_auf(app, bh.Pegel)
    taste(app, "right")
    laufen(app, 0.4)
    foto(app, "14-pegel")
    taste(app, "escape")
    app.szene.m.wahl = 4
    taste(app, "return")
    warten_auf(app, bh.Einstellungen)
    laufen(app, 0.4)
    foto(app, "15-einstellungen")
    # alle Themen einmal zeigen
    for lied in app.lieder:
        hg = bh.Hintergrundbild(app, lied["thema"], lied["bpm"], bh.g.hex2rgb(lied["farbe"]))
        for _ in range(40):
            hg.zeichnen(app.bildschirm)
            hg.t0 -= 0.05
        foto(app, "th-" + lied["id"])
    app.beenden("ende")
    app.aufraeumen()
    _ = ids


if __name__ == "__main__":
    t0 = time.monotonic()
    try:
        main()
    finally:
        for f in fehler:
            print("✗", f)
        print(f"fertig in {time.monotonic() - t0:.0f} s · Fotos: {FOTOS}")
    sys.exit(1 if fehler else 0)
