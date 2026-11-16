# -*- coding: utf-8 -*-
"""Handpan-Traum – Ambient-Techno in D-Kurd: Steel-Drum als Handpan, Didgeridoo-Bass, 808-Beat."""
from komponist import Lied, Drums, Bass, Flaeche, Arp, Linie


def lied():
    L = Lied("handpan", "Handpan-Traum", "Ambient Techno · D Kurd", 122, "Dm", "handpan", "schwebend · treibend",
             tonleiter="kurd", schwierigkeit=2, farbe="#e8b04a", seed=81)
    L.vorschau = "Drop"
    L.spur("lead", 114, 0, vol=112, pan=64, hall=80)
    L.spur("bass", 39, 1, vol=100, pan=64, hall=30)
    L.spur("flaeche", 89, 2, vol=72, pan=40, hall=95, chorus=50)
    L.spur("kalimba", 108, 3, vol=56, pan=96, hall=85)
    L.spur("atmo", 99, 4, vol=56, pan=70, hall=100)
    L.spur("stimme", 53, 5, vol=50, pan=30, hall=100)
    L.spur("drums", 25, 9, vol=104, hall=40)

    intro = ("D4:2 A4:2 F4:2 A4:2 D5:4 A4:4 | Bb3:2 F4:2 D4:2 F4:2 Bb4:4 F4:4 | C4:2 G4:2 E4:2 G4:2 C5:4 G4:4 |"
             " D4:4 F4:4 A4:8 | D4:2 A4:2 F4:2 A4:2 D5:4 A4:4 | Bb3:2 F4:2 D4:2 F4:2 Bb4:4 F4:4 |"
             " C4:2 G4:2 E4:2 G4:2 C5:4 G4:4 | A4:4 F4:4 D4:8 |")
    groove = ("D4:3 A4:3 F4:2 r:2 D5:2 C5:2 A4:2 | F4:3 A4:3 D5:2 r:2 E5:2 D5:2 A4:2 |"
              " Bb4:3 F4:3 D4:2 r:2 F4:2 Bb4:2 D5:2 | C5:3 G4:3 E4:2 r:2 G4:2 A4:2 G4:2 |"
              " D4:3 A4:3 F4:2 r:2 D5:2 C5:2 A4:2 | F4:3 A4:3 D5:2 r:2 E5:2 D5:2 A4:2 |"
              " Bb4:3 F4:3 D4:2 r:2 F4:2 Bb4:2 D5:2 | C5:3 E5:3 G5:2 r:2 E5:2 D5:2 C5:2 |")
    schweben = "G4:8 Bb4:8 | D5:16 | C5:8 A4:8 | G4:8 E4:8 | D5:8 F5:8 | D5:16 | C5:8 F5:8 | E5:16 |"
    drop = ("D5:1 A4:1 F4:1 A4:1 D5:1 A4:1 F4:1 A4:1 D5:2 E5:2 F5:2 E5:2 | D5:2 A4:2 F4:2 A4:2 C5:2 A4:2 D5:4 |"
            " Bb4:1 F4:1 D4:1 F4:1 Bb4:1 F4:1 D4:1 F4:1 Bb4:2 C5:2 D5:2 C5:2 | C5:2 G4:2 E4:2 G4:2 C5:2 D5:2 E5:4 |"
            " D5:1 A4:1 F4:1 A4:1 D5:1 A4:1 F4:1 A4:1 D5:2 E5:2 F5:2 E5:2 | D5:2 A4:2 F4:2 A4:2 C5:2 A4:2 D5:4 |"
            " Bb4:1 F4:1 D4:1 F4:1 Bb4:1 F4:1 D4:1 F4:1 Bb4:2 C5:2 D5:2 C5:2 | C5:2 E5:2 G5:2 E5:2 F5:2 E5:2 D5:4 |")

    i_akk = "Dm | Bb | C | Dm | Dm | Bb | C | Dm"
    g_akk = "Dm | Dm | Bb | C | Dm | Dm | Bb | C"
    s_akk = "Gm | Bb | F | C | Gm | Bb | F | C"
    # Didgeridoo-artiger Bass: tiefer Grundton mit rhythmischen Stößen
    didge = Bass("R..R.R..R..R.R..", unten=38, staerke=90, legato=0.9)
    didge_lang = Bass("R---------R--R--", unten=38, staerke=84)
    vier = Drums({"k": "X...X...X...X...", "l": "....x.......x...", "h": "..x...x...x...x.", "z": "oooooooooooooooo"},
                 fill={"l": "....x.......x.xx", "h": "..x...x...x....."})
    vier_voll = Drums({"k": "X...X...X...X...", "l": "....x.......x...", "o": "..x...x...x...x.",
                       "h": "x.x.x.x.x.x.x.x.", "z": "oxoxoxoxoxoxoxox"},
                      fill={"l": "....x...x.x.xxxx", "o": "", "h": ""})
    still = Drums({"z": "o.o.o.o.o.o.o.o.", "k": "X..............."}, crash=False)
    kalimba = Arp("1.3.5.3.2.4.3.5.", lage=72, staerke=50)

    L.abschnitt("Erwachen", i_akk, lead=intro, flaeche=Flaeche(58, 4, 62), atmo=Flaeche(70, 3, 50),
                bass=didge_lang, drums=still)
    L.abschnitt("Groove", g_akk, wdh=2, lead=groove, flaeche=Flaeche(58, 4, 60), bass=didge, drums=vier,
                kalimba=kalimba)
    L.abschnitt("Schweben", s_akk, lead=schweben, flaeche=Flaeche(60, 4, 70), atmo=Flaeche(72, 3, 56),
                stimme=Flaeche(65, 3, 56), bass=didge_lang, drums=still)
    L.abschnitt("Aufbau", g_akk, lead=groove, flaeche=Flaeche(58, 4, 64), bass=didge,
                drums=Drums({"k": "X...X...X...X...", "z": "oxoxoxoxoxoxoxox", "l": "........x......."},
                            fill={"l": "x.x.x.x.xxxxXXXX", "k": "X.X.X.X.X.X.X.X."}),
                kalimba=kalimba)
    L.abschnitt("Drop", g_akk, wdh=2, lead=drop, flaeche=Flaeche(60, 4, 74), bass=didge, drums=vier_voll,
                kalimba=Arp("1353135313531353", lage=72, staerke=48, legato=0.6), stimme=Flaeche(65, 3, 52))
    L.abschnitt("Schweben 2", s_akk, lead=schweben, flaeche=Flaeche(60, 4, 70), atmo=Flaeche(72, 3, 60),
                stimme=Flaeche(65, 3, 60), bass=didge, drums=vier,
                kalimba=Linie(schweben, transponiert=12, staerke=46))
    L.abschnitt("Drop 2", g_akk, lead=drop, flaeche=Flaeche(60, 4, 76), bass=didge, drums=vier_voll,
                kalimba=Arp("1353135313531353", lage=72, staerke=48, legato=0.6))
    L.abschnitt("Heimkehr", i_akk, lead=intro, flaeche=Flaeche(58, 4, 60), atmo=Flaeche(70, 3, 54),
                bass=didge_lang, drums=still, kalimba=kalimba)
    L.abschnitt("Stille", "Dm | Dm", lead="D4:4 A4:4 D5:8 | r:16 |", flaeche=Flaeche(58, 4, 50),
                bass=Bass("R---------------", unten=38, staerke=70))
    return L
