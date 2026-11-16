# -*- coding: utf-8 -*-
"""Neonnebel – Synthwave in a-Moll: Sägezahn-Lead, Arpeggiator, warme Flächen, Elektro-Schlagzeug."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Arp, Linie


def lied():
    L = Lied("neon", "Neonnebel", "Synthwave · Nachtfahrt", 100, "Am", "synthwave", "verträumt · treibend",
             schwierigkeit=2, farbe="#d94ad0", seed=31)
    L.vorschau = "Refrain"
    L.spur("lead", 81, 0, vol=104, pan=64, hall=70, chorus=60)
    L.spur("bass", 38, 1, vol=102, pan=64, hall=10)
    L.spur("arp", 80, 2, vol=62, pan=88, hall=60)
    L.spur("flaeche", 89, 3, vol=78, pan=40, hall=90, chorus=40)
    L.spur("poly", 90, 4, vol=66, pan=64, hall=70)
    L.spur("glocke", 98, 5, vol=58, pan=96, hall=90)
    L.spur("drums", 24, 9, vol=104, hall=50)

    intro = "A5:6 C6:2 E6:8 | F5:6 A5:2 C6:8 | E5:6 G5:2 C6:8 | D6:6 B5:2 G5:8 |"
    strophe = ("E5:4 E5:2 D5:2 C5:4 A4:4 | C5:4 D5:2 E5:2 F5:4 E5:4 | G5:4 G5:2 E5:2 C5:4 E5:4 | D5:12 r:4 |"
               " E5:4 E5:2 D5:2 C5:4 E5:4 | A5:4 G5:2 F5:2 C5:4 F5:4 | E5:4 D5:2 C5:2 G5:4 E5:4 | D5:8 B4:4 G4:4 |")
    refrain = ("A5:4 C6:4 A5:2 G5:2 F5:4 | G5:4 B5:4 D6:8 | E6:6 D6:2 B5:4 G5:4 | A5:12 r:4 |"
               " A5:4 C6:4 A5:2 G5:2 F5:4 | G5:4 B5:4 D6:4 G6:4 | E6:4 D6:4 B5:4 D6:4 | C6:4 B5:4 A5:8 |")
    bruecke = "F5:8 A5:8 | G5:8 B5:8 | A5:8 C6:8 | B5:8 D6:8 | F6:8 D6:8 | D6:8 B5:8 | C6:8 A5:8 | B5:16 |"
    solo = ("A5:2 C6:2 E6:2 A6:2 G6:2 E6:2 C6:2 A5:2 | F5:2 A5:2 C6:2 F6:2 E6:2 C6:2 A5:2 F5:2 |"
            " G5:2 C6:2 E6:2 G6:2 E6:2 C6:2 G5:2 E5:2 | D5:2 G5:2 B5:2 D6:2 G6:8 |"
            " E6:4 D6:2 C6:2 B5:2 C6:2 A5:4 | C6:4 A5:2 F5:2 A5:2 C6:2 F6:4 |"
            " E6:2 G6:2 E6:2 C6:2 D6:2 E6:2 G6:4 | B5:4 D6:4 G6:8 |")

    s_akk = "Am | F | C | G | Am | F | C | G"
    r_akk = "F | G | Em | Am | F | G | Em | Am"
    arp16 = Arp("1235123512351235", lage=64, staerke=62, legato=0.6)
    arp8 = Arp("1-3-5-3-1-3-5-3-", lage=64, staerke=58)
    puls = Bass("RRRRRRRRRRRRRRRR", unten=28, staerke=88, legato=0.7)
    oktav = Bass("ROROROROROROROROR"[:16], unten=28, staerke=90, legato=0.6)
    beat = Drums({"k": "X...X...X...X...", "s": "....X.......X...", "h": "..x...x...x...x."},
                 fill={"s": "....X.......XxXX", "T": "........x.x....."})
    beat_halb = Drums({"k": "X.........X.....", "s": "........X.......", "h": "x.x.x.x.x.x.x.x."},
                      fill={"s": "........X...xxxx"})
    still = Drums({"h": "....x.......x...", "k": "X..............."}, crash=False)

    L.abschnitt("Intro", s_akk, lead=intro, arp=arp16, flaeche=Flaeche(60, 4, 64), drums=still,
                bass=Bass("R-------R-------", unten=28))
    L.abschnitt("Strophe", s_akk, lead=strophe, arp=arp8, flaeche=Flaeche(60, 4, 60), bass=puls, drums=beat_halb)
    L.abschnitt("Refrain", r_akk, lead=refrain, arp=arp16, flaeche=Flaeche(62, 4, 76), bass=oktav, drums=beat,
                poly=Akkorde("X--.X--.X--.X-X.", lage=60, toene=3, staerke=66, legato=0.8))
    L.abschnitt("Zwischenspiel", "Am | F | C | G", lead=intro, arp=arp16, flaeche=Flaeche(60, 4, 64), bass=puls,
                drums=beat, glocke=Linie("E6:16 | C6:16 | G6:16 | D6:16 |", staerke=60))
    L.abschnitt("Strophe 2", s_akk, lead=strophe, arp=arp16, flaeche=Flaeche(60, 4, 62), bass=puls, drums=beat,
                glocke=Linie("r:16 | r:16 | r:16 | B5:8 D6:8 |", staerke=56))
    L.abschnitt("Refrain 2", r_akk, lead=refrain, arp=arp16, flaeche=Flaeche(62, 4, 78), bass=oktav, drums=beat,
                poly=Akkorde("X--.X--.X--.X-X.", lage=60, toene=3, staerke=68, legato=0.8))
    L.abschnitt("Brücke", "Dm | Em | F | G | Dm | Em | F | G", lead=bruecke, flaeche=Flaeche(62, 4, 72),
                bass=Bass("R-------R-------", unten=28), drums=beat_halb, arp=arp8,
                glocke=Linie("A5:16 | B5:16 | C6:16 | D6:16 | F6:16 | E6:16 | C6:16 | D6:16 |", staerke=52))
    L.abschnitt("Solo", s_akk, lead=solo, arp=arp16, flaeche=Flaeche(60, 4, 66), bass=oktav, drums=beat,
                poly=Akkorde("X--.X--.X--.X-X.", lage=60, toene=3, staerke=62, legato=0.8))
    L.abschnitt("Refrain 3", r_akk, lead=refrain, arp=arp16, flaeche=Flaeche(62, 4, 80), bass=oktav, drums=beat,
                poly=Akkorde("X--.X--.X--.X-X.", lage=60, toene=3, staerke=70, legato=0.8),
                glocke=Linie(refrain, transponiert=12, staerke=46))
    L.abschnitt("Refrain 4", r_akk, lead=refrain, arp=arp16, flaeche=Flaeche(62, 4, 82), bass=oktav, drums=beat,
                poly=Akkorde("X--.X--.X--.X-X.", lage=60, toene=3, staerke=72, legato=0.8))
    L.abschnitt("Ausfahrt", s_akk, lead=intro, arp=arp8, flaeche=Flaeche(60, 4, 58), drums=still,
                bass=Bass("R-------R-------", unten=28))
    L.abschnitt("Ende", "Am", lead="A5:16 |", flaeche=Flaeche(60, 4, 56), bass=Bass("R---------------", unten=28))
    return L
