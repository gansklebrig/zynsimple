# -*- coding: utf-8 -*-
"""Die Feuerinsel – tribal-episches Finale in c-Moll: Taiko, Panflöte, Streicher-Ostinato, Chor."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Arp, Linie


def lied():
    L = Lied("feuerinsel", "Die Feuerinsel", "Tribal-Epos · Finale", 128, "Cm", "feuerinsel",
             "episch · Trommeln & Feuer", schwierigkeit=3, farbe="#ff6a00", seed=111)
    L.vorschau = "Höhepunkt"
    L.spur("lead", 75, 0, vol=114, pan=64, hall=70)
    L.spur("bass", 38, 1, vol=100, pan=64, hall=20)
    L.spur("streicher", 48, 2, vol=76, pan=36, hall=70)
    L.spur("ostinato", 45, 3, vol=74, pan=96, hall=55)
    L.spur("chor", 52, 4, vol=78, pan=64, hall=95)
    L.spur("taiko", 116, 5, vol=104, pan=50, hall=70)
    L.spur("blech", 60, 6, vol=70, pan=84, hall=80)
    L.spur("drums", 48, 9, vol=100, hall=50)

    ruf = "C5:4 r:4 G4:4 r:4 | C5:2 Eb5:2 G5:4 r:8 | G5:4 r:4 F5:4 r:4 | Eb5:2 D5:2 C5:4 r:8 |"
    thema = ("G4:2 C5:2 Eb5:2 G5:2 F5:2 Eb5:2 D5:2 C5:2 | Eb5:4 D5:2 C5:2 G4:8 |"
             " Ab4:2 C5:2 Eb5:2 Ab5:2 G5:2 F5:2 Eb5:2 C5:2 | D5:4 F5:4 Bb5:8 |"
             " G5:2 C6:2 G5:2 Eb5:2 F5:2 G5:2 Ab5:2 G5:2 | Eb5:4 D5:2 Eb5:2 C5:8 |"
             " C6:4 Bb5:2 Ab5:2 Eb5:4 C5:4 | D5:4 Bb4:4 F5:8 |")
    aufbau = ("Eb5:2 Eb5:2 Eb5:2 Eb5:2 C5:2 C5:2 Eb5:2 Ab5:2 | F5:2 F5:2 F5:2 F5:2 D5:2 D5:2 F5:2 Bb5:2 |"
              " G5:2 G5:2 G5:2 G5:2 Eb5:2 Eb5:2 G5:2 C6:2 | C6:4 D6:4 Eb6:8 |"
              " Ab5:2 Ab5:2 C6:2 Ab5:2 Eb6:4 C6:4 | Bb5:2 Bb5:2 D6:2 Bb5:2 F6:4 D6:4 |"
              " G5:2 B5:2 D6:2 G6:2 F6:2 D6:2 B5:2 G5:2 | B5:4 D6:4 F6:4 G6:4 |")
    hoch = ("C6:6 D6:2 Eb6:4 G6:4 | F6:4 Eb6:2 D6:2 C6:8 | Ab5:4 C6:4 Eb6:4 Ab6:4 | G6:4 F6:4 D6:8 |"
            " C6:6 D6:2 Eb6:4 G6:4 | Bb6:4 Ab6:2 G6:2 Eb6:8 | Eb6:4 C6:4 D6:4 B5:4 | C6:12 r:4 |")
    ruhe = "G5:16 | Eb5:16 | G5:8 Bb5:8 | F5:16 | G5:8 C6:8 | Ab5:8 Eb5:8 | Bb5:8 G5:8 | D5:16 |"

    taiko_ruf = Linie("C2:4! r:4 C2:2 C2:2 r:4 | C2:4! r:4 C2:2 r:2 C2:2 C2:2 |", staerke=110)
    taiko_voll = Linie("C2:2! r:2 C2:2 C2:2 r:2 C2:2 C2:2 r:2 | C2:2! r:2 C2:2 C2:2 C2:1 C2:1 C2:2 C2:2! r:2 |",
                       staerke=112)
    trommeln = Drums({"k": "X.....x.X.....x.", "M": "....x.......x.x.", "f": "x.......x.......", "w": "..x...x...x...x."},
                     fill={"M": "x.x.x.x.xxxxXXXX", "f": "", "w": ""}, crash=False)
    trommeln_voll = Drums({"k": "X..x..x.X..x..x.", "s": "....X.......X...", "M": "..x...x...x...x.",
                           "C": "x.......x......."}, fill={"s": "x.x.x.x.XXXXXXXX", "f": "x.x.x.x.........", "C": ""})
    ostinato = Arp("1121112111211121", lage=60, staerke=70, legato=0.5)
    ostinato_hoch = Arp("1131113111311131", lage=67, staerke=72, legato=0.5)
    bass = Bass("R..R..R.R..R..R.", unten=36, staerke=96, legato=0.8)

    L.abschnitt("Ruf der Insel", "Cm | Cm | Cm | Cm", wdh=2, lead=ruf, taiko=taiko_ruf,
                streicher=Flaeche(48, 2, 60), chor=Flaeche(60, 3, 46), bass=Bass("R---------------", unten=36))
    L.abschnitt("Thema", "Cm | Cm | Ab | Bb", wdh=4, lead=thema, taiko=taiko_ruf, drums=trommeln,
                ostinato=ostinato, bass=bass, streicher=Flaeche(55, 3, 58))
    L.abschnitt("Aufbau", "Ab | Bb | Cm | Cm | Ab | Bb | G | G", lead=aufbau, taiko=taiko_voll, drums=trommeln,
                ostinato=ostinato_hoch, bass=Bass("RRRRRRRRRRRRRRRR", unten=36, staerke=92, legato=0.6),
                streicher=Flaeche(60, 4, 70), chor=Flaeche(64, 3, 60))
    L.abschnitt("Höhepunkt", "Cm | Cm | Ab | Bb | Cm | Cm | Ab G | Cm", wdh=2, lead=hoch, taiko=taiko_voll,
                drums=trommeln_voll, ostinato=ostinato_hoch, bass=bass, streicher=Flaeche(62, 4, 82, oktave=True),
                chor=Flaeche(67, 4, 86), blech=Flaeche(55, 3, 72))
    L.abschnitt("Atem des Feuers", "Cm | Ab | Eb | Bb | Cm | Ab | Eb | Bb", lead=ruhe, taiko=taiko_ruf,
                streicher=Flaeche(55, 3, 56), chor=Flaeche(64, 3, 58), bass=Bass("R---------------", unten=36),
                ostinato=Arp("1---------------", lage=60, staerke=60))
    L.abschnitt("Thema 2", "Cm | Cm | Ab | Bb", wdh=2, lead=thema, taiko=taiko_voll, drums=trommeln_voll,
                ostinato=ostinato, bass=bass, streicher=Flaeche(60, 4, 70), chor=Flaeche(64, 3, 64))
    L.abschnitt("Finale", "Cm | Cm | Ab | Bb | Cm | Cm | Ab G | Cm", wdh=2, lead=hoch, taiko=taiko_voll,
                drums=trommeln_voll, ostinato=ostinato_hoch, bass=bass, streicher=Flaeche(62, 4, 88, oktave=True),
                chor=Flaeche(67, 4, 92), blech=Linie(hoch, transponiert=-12, staerke=74))
    L.abschnitt("Glut", "Cm | Ab | G | Cm", lead="C6:4 Eb6:4 G6:8 | Ab6:8 Eb6:8 | G6:4 F6:4 D6:4 B5:4 | C6:16 |",
                taiko=Linie("C2:2! C2:2 C2:2 C2:2 C2:8 | C2:4! r:12 | C2:1 C2:1 C2:1 C2:1 C2:1 C2:1 C2:1 C2:1"
                            " C2:2 C2:2 C2:2 C2:2 | C2:8! r:8 |", staerke=116),
                streicher=Flaeche(62, 4, 90, oktave=True), chor=Flaeche(67, 4, 94), blech=Flaeche(55, 3, 80),
                bass=Bass("R---------------", unten=36),
                drums=Drums({"k": "X...X...X...X..."}, fill={"k": "X...............", "C": "X...............",
                                                            "s": "X..............."}))
    return L
