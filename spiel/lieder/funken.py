# -*- coding: utf-8 -*-
"""Funkenflug – Funk/Disco in e-Dorisch: Saxofon-Hook, Clavinet, Slap-Bass, Bläser und Streicher."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Linie


def lied():
    L = Lied("funken", "Funkenflug", "Funk & Disco", 112, "Em", "funk", "tanzbar · catchy",
             tonleiter="dorisch", schwierigkeit=3, farbe="#ff9000", seed=21)
    L.vorschau = "Refrain"
    L.spur("lead", 65, 0, vol=110, pan=64, hall=45)
    L.spur("bass", 36, 1, vol=108, pan=64, hall=10)
    L.spur("clav", 7, 2, vol=74, pan=30, hall=20)
    L.spur("gitarre", 28, 3, vol=70, pan=100, hall=25)
    L.spur("blech", 61, 4, vol=86, pan=78, hall=45)
    L.spur("streicher", 48, 5, vol=72, pan=48, hall=70)
    L.spur("epiano", 4, 6, vol=64, pan=60, hall=50)
    L.spur("drums", 0, 9, vol=100, hall=20)

    hook = ("E5:2 E5:1 G5:1 r:2 A5:2 r:2 B5:2 A5:2 G5:2 | E5:2 D5:2 r:2 B4:2 D5:2 E5:4 r:2 |"
            " E5:2 E5:1 G5:1 r:2 A5:2 r:2 B5:2 D6:2 B5:2 | A5:2 G5:2 E5:2 D5:2 E5:8 |")
    strophe = ("r:4 B4:2 D5:2 E5:4 r:4 | r:4 C#5:2 E5:2 F#5:4 E5:4 | r:4 G5:2 F#5:2 E5:2 D5:2 B4:4 |"
               " D5:2 E5:6 r:8 | r:4 B4:2 D5:2 E5:4 r:4 | r:4 C#5:2 E5:2 F#5:4 E5:4 |"
               " r:4 G5:2 A5:2 B5:2 A5:2 G5:2 E5:2 | F#5:4 G5:4 A5:8 |")
    refrain = ("G5:4 G5:2 E5:2 G5:4 B5:4 | A5:4 F#5:2 D5:2 A5:8 | F#5:4 F#5:2 D5:2 F#5:4 A5:4 | G5:6 E5:2 B4:8 |"
               " G5:4 G5:2 E5:2 G5:4 B5:4 | D6:4 C6:2 A5:2 F#5:4 A5:4 | D#6:4 B5:2 F#5:2 A5:4 D#5:4 | E5:12 r:4 |")
    solo = ("E5:1 G5:1 A5:1 B5:1 D6:2 B5:2 A5:2 G5:2 E5:4 | r:2 C#5:2 E5:2 G5:2 F#5:2 E5:2 D5:4 |"
            " B5:2 B5:1 A5:1 G5:2 E5:2 D5:2 E5:2 G5:4 | A5:3 B5:1 A5:2 G5:2 E5:8 |"
            " E6:2 D6:2 B5:2 A5:2 G5:2 A5:2 B5:4 | C#6:2 B5:2 A5:2 F#5:2 E5:2 D5:2 E5:4 |"
            " G5:1 A5:1 B5:1 D6:1 E6:4 D6:1 B5:1 A5:1 G5:1 E5:4 | D5:2 E5:2 G5:2 A5:2 B5:8 |")

    vamp = "Em7 | A9 | Em7 | A9"
    ref_akk = "Cmaj7 | D | Bm7 | Em7 | Cmaj7 | D | B7 | Em7"
    funk_dr = Drums({"k": "X.....x...x.....", "s": "....X..g....X..g", "h": "xoxoxoxoxoxoxoxo"},
                    fill={"s": "....X..g..x.XxXX", "h": "xoxoxoxo........", "t": "..........x....."})
    disco_dr = Drums({"k": "X...X...X...X...", "s": "....X.......X...", "h": "x...x...x...x...", "o": "..x...x...x...x.",
                      "l": "....x.......x..."}, fill={"s": "....X...x.x.XXXX", "o": "", "h": "x...x..........."})
    slap = Bass("R..R..O.R.5..O.7", unten=28, staerke=100, legato=0.55)
    slap_ref = Bass("R.RO.R.OR.RO.R5O", unten=28, staerke=98, legato=0.5)
    clav = Akkorde("x.xX.x.xx.xX.x.x", lage=64, toene=3, staerke=74, legato=0.35)
    chick = Akkorde("....X.......X...", lage=66, toene=3, staerke=70, legato=0.25)
    stich = Akkorde("X.....X.....X...", lage=66, toene=4, staerke=92, legato=0.25)

    L.abschnitt("Intro", vamp, drums=funk_dr, bass=slap, gitarre=chick,
                lead="r:16 | r:16 | r:12 B4:2 D5:2 | E5:2 r:6 E5:2 G5:2 A5:2 B5:2 |")
    L.abschnitt("Hook", vamp, wdh=2, lead=hook, drums=funk_dr, bass=slap, clav=clav, gitarre=chick)
    L.abschnitt("Strophe", vamp, wdh=2, lead=strophe, drums=funk_dr, bass=slap, clav=clav, gitarre=chick,
                epiano=Flaeche(62, 4, 56))
    L.abschnitt("Refrain", ref_akk, lead=refrain, drums=disco_dr, bass=slap_ref, clav=clav, blech=stich,
                streicher=Flaeche(67, 4, 78), gitarre=chick)
    L.abschnitt("Hook 2", vamp, wdh=2, lead=hook, drums=funk_dr, bass=slap, clav=clav, gitarre=chick,
                blech=Linie("r:16 | r:8 E5+G5:2! r:2 E5+G5:2 r:2 | r:16 | r:8 E5+A5:2! r:2 E5+A5:2 r:2 |"))
    L.abschnitt("Strophe 2", vamp, wdh=2, lead=strophe, drums=funk_dr, bass=slap, clav=clav, gitarre=chick,
                epiano=Flaeche(62, 4, 58), streicher=Flaeche(71, 2, 50))
    L.abschnitt("Refrain 2", ref_akk, lead=refrain, drums=disco_dr, bass=slap_ref, clav=clav, blech=stich,
                streicher=Flaeche(67, 4, 80), gitarre=chick)
    L.abschnitt("Break", vamp, drums=Drums({"k": "X.....x...x.....", "s": "....X..g....X..g", "h": "x.x.x.x.x.x.x.x."},
                                           crash=False),
                bass=Bass("R..R..O.R.5..O.7R..R..O.R.5.bO.a", unten=28, staerke=106, legato=0.55),
                lead="r:16 | r:16 | r:16 | r:8 B4:2 D5:2 E5:2 G5:2 |")
    L.abschnitt("Solo", vamp, wdh=2, lead=solo, drums=disco_dr, bass=slap, clav=clav, gitarre=chick,
                blech=Linie("r:16 | r:12 B4+E5:2! r:2 | r:16 | r:12 C#5+E5:2! r:2 |"), epiano=Flaeche(62, 4, 54))
    L.abschnitt("Refrain 3", ref_akk, lead=refrain, drums=disco_dr, bass=slap_ref, clav=clav, blech=stich,
                streicher=Flaeche(67, 4, 84), gitarre=chick)
    L.abschnitt("Refrain 4", ref_akk, lead=refrain, drums=disco_dr, bass=slap_ref, clav=clav,
                blech=Linie(refrain, transponiert=-12, staerke=80), streicher=Flaeche(67, 4, 88), gitarre=chick)
    L.abschnitt("Schluss", vamp, lead=hook, drums=funk_dr, bass=slap, clav=clav,
                blech=Linie("r:16 | r:16 | r:16 | r:8 E5+G5+B5:4! r:4 |"))
    L.abschnitt("Aus", "Em7", lead="E5:4! r:12 |", bass=Bass("R...............", unten=28),
                drums=Drums({"k": "X...............", "c": "X..............."}, crash=False),
                blech=Linie("E5+G5+B5:4! r:12 |"), streicher=Flaeche(67, 4, 70))
    return L
