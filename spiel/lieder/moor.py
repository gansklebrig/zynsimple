# -*- coding: utf-8 -*-
"""Die Hexe vom Moor – düsterer Folk-Jig im 6/8-Takt, e-Moll: Geige, Harfe, Cello, Trommeln."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Arp, Linie


def lied():
    L = Lied("moor", "Die Hexe vom Moor", "Düsterer Folk-Jig · 6/8", 138, "Em", "moor", "geheimnisvoll · wild",
             takt=(6, 8), schwierigkeit=3, farbe="#8fbf3a", seed=41)
    L.vorschau = "Jig A"
    L.spur("lead", 40, 0, vol=112, pan=60, hall=60)
    L.spur("bass", 32, 1, vol=98, pan=64, hall=30)
    L.spur("harfe", 46, 2, vol=76, pan=96, hall=70)
    L.spur("cello", 42, 3, vol=74, pan=34, hall=70)
    L.spur("gitarre", 25, 4, vol=66, pan=24, hall=40)
    L.spur("floete", 73, 5, vol=70, pan=100, hall=75)
    L.spur("chor", 53, 6, vol=58, pan=64, hall=95)
    L.spur("drums", 0, 9, vol=96, hall=50)

    intro = "E5:12 | G5:6 E5:6 | C5:12 | B4:12 | E5:6 G5:6 | C6:12 | A5:6 C6:6 | B5:12 |"
    jig_a = ("E5:2 G5:2 B5:2 E6:2 B5:2 G5:2 | F#5:2 A5:2 D6:2 A5:2 F#5:2 D5:2 | E5:2 F#5:2 G5:2 A5:2 B5:2 G5:2 |"
             " F#5:6 D#5:4 B4:2 | E5:2 G5:2 B5:2 E6:2 D6:2 B5:2 | A5:2 D6:2 F#6:2 E6:2 D6:2 A5:2 |"
             " G5:2 E5:2 C5:2 D#5:2 F#5:2 A5:2 | G5:2 F#5:2 D#5:2 E5:6 |")
    jig_b = ("A5:4 B5:2 C6:4 A5:2 | B5:4 G5:2 E5:6 | D6:4 C6:2 B5:2 A5:2 F#5:2 | G5:6 E5:6 |"
             " C6:4 B5:2 A5:2 C6:2 E6:2 | E6:4 D6:2 B5:6 | D#6:2 F#6:2 D#6:2 B5:2 A5:2 F#5:2 | E5:12 |")
    hexe = ("B4:4 C5:2 B4:2 G4:2 E4:2 | E4:2 G4:2 C5:2 E5:4 C5:2 | A4:2 C5:2 E5:2 A5:4 G5:2 | F#5:4 D#5:2 B4:6 |"
            " E5:2 F#5:2 G5:2 B5:4 G5:2 | C6:4 B5:2 G5:2 E5:2 G5:2 | A5:2 C6:2 E6:2 D6:2 C6:2 A5:2 | B5:6 D#6:6 |")
    ruhe = "B5:12 | G5:12 | A5:6 C6:6 | B5:12 | E6:12 | C6:12 | A5:6 F#5:6 | E5:12 |"

    a_akk = "Em | D | Em | B7 | Em | D | C B7 | Em"
    b_akk = "Am | Em | D | Em | Am | Em | B7 | Em"
    c_akk = "Em | C | Am | B7 | Em | C | Am | B7"
    harfe = Arp("1-3-5-4-5-3-", lage=55, staerke=64)
    harfe_schnell = Arp("135435135435", lage=60, staerke=58, legato=0.8)
    gitarre = Akkorde("X-xX-xX-xX-x", lage=57, toene=4, staerke=72, strum=12, legato=0.7)
    bass = Bass("R-----5-----", unten=28, staerke=92)
    bass_jig = Bass("R---R-5---5-", unten=28, staerke=94)
    trommel = Drums({"k": "X.....x.....", "M": "x..o.ox..o.o", "f": "......x.....", "w": "x.x.x.x.x.x."},
                    fill={"M": "x.x.x.x.x.xx", "f": "......x.x.xX", "w": ""})
    trommel_wild = Drums({"k": "X..x..X..x..", "s": "...x.....x..", "M": "x.ox.ox.ox.o", "w": "x.x.x.x.x.x."},
                         fill={"s": "x.x.x.xxxxXX", "M": "", "w": ""})
    leise = Drums({"M": "x.....o.....", "k": "X..........."}, crash=False)

    L.abschnitt("Nebel", c_akk, lead=intro, harfe=harfe, cello=Flaeche(43, 2, 70), drums=leise,
                chor=Flaeche(64, 3, 50))
    L.abschnitt("Jig A", a_akk, lead=jig_a, harfe=harfe, gitarre=gitarre, bass=bass, drums=trommel,
                cello=Flaeche(43, 2, 64))
    L.abschnitt("Jig A2", a_akk, lead=jig_a, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig, drums=trommel_wild,
                floete=Linie(jig_a, transponiert=-12, staerke=66))
    L.abschnitt("Jig B", b_akk, lead=jig_b, harfe=harfe, gitarre=gitarre, bass=bass_jig, drums=trommel,
                cello=Flaeche(43, 2, 66))
    L.abschnitt("Jig B2", b_akk, lead=jig_b, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig, drums=trommel_wild,
                floete=Linie("E6:12 | B5:12 | A5:12 | B5:12 | C6:12 | B5:12 | B5:12 | E6:12 |", staerke=60))
    L.abschnitt("Hexentanz", c_akk, lead=hexe, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig,
                drums=trommel_wild, chor=Flaeche(62, 3, 66), cello=Flaeche(43, 2, 70))
    L.abschnitt("Hexentanz 2", c_akk, lead=hexe, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig,
                drums=trommel_wild, chor=Flaeche(64, 4, 74), floete=Linie(hexe, transponiert=12, staerke=56))
    L.abschnitt("Jig A3", a_akk, lead=jig_a, harfe=harfe, gitarre=gitarre, bass=bass, drums=trommel,
                floete=Linie(jig_a, transponiert=-12, staerke=62))
    L.abschnitt("Jig B3", b_akk, lead=jig_b, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig,
                drums=trommel_wild, cello=Flaeche(43, 2, 70))
    L.abschnitt("Stille im Moor", "Em | C | Am | B7 | Em | C | Am B7 | Em", lead=ruhe, harfe=harfe,
                cello=Flaeche(43, 2, 66), chor=Flaeche(64, 3, 58), drums=leise)
    L.abschnitt("Jig Finale", a_akk, lead=jig_a, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig,
                drums=trommel_wild, chor=Flaeche(64, 3, 70), floete=Linie(jig_a, transponiert=-12, staerke=66))
    L.abschnitt("Jig Finale B", b_akk, lead=jig_b, harfe=harfe_schnell, gitarre=gitarre, bass=bass_jig,
                drums=trommel_wild, chor=Flaeche(64, 3, 74), cello=Flaeche(43, 2, 72))
    L.abschnitt("Verschwunden", "Em | C B7 | Em | Em", lead="E6:12 | C6:6 B5:6 | E5:12 | r:12 |",
                harfe=Arp("1-3-5-8-----", lage=55, staerke=60), cello=Flaeche(43, 2, 64),
                drums=Drums({"k": "X...........", "M": "......x....."}, nur=[0, 1], crash=False))
    return L
