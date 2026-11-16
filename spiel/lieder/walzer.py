# -*- coding: utf-8 -*-
"""Mondwalzer – gemütlicher Walzer im 3/4-Takt in F-Dur: Flöte, Streicher-Um-pa-pa, Harfe, Celesta."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Arp, Linie


def lied():
    L = Lied("walzer", "Mondwalzer", "Walzer · 3/4", 150, "F", "walzer", "gemütlich · verträumt",
             takt=(3, 4), tonleiter="dur", schwierigkeit=2, farbe="#ffd98a", seed=61)
    L.vorschau = "Walzer A"
    L.spur("lead", 73, 0, vol=110, pan=64, hall=70)
    L.spur("bass", 45, 1, vol=100, pan=60, hall=50)
    L.spur("streicher", 48, 2, vol=72, pan=40, hall=75)
    L.spur("harfe", 46, 3, vol=66, pan=96, hall=70)
    L.spur("celesta", 8, 4, vol=60, pan=84, hall=85)
    L.spur("horn", 60, 5, vol=62, pan=30, hall=80)
    L.spur("drums", 40, 9, vol=70, hall=60)

    intro = ("A5:4 C6:4 F6:4 | E6:4 C6:4 G5:4 | A5:4 C6:4 F6:4 | G6:8 E6:4 | F6:4 D6:4 Bb5:4 |"
             " G5:4 Bb5:4 E6:4 | F6:8 A5:4 | G5:8 r:4 |")
    a = ("C5:4 F5:4 A5:4 | C6:8 A5:4 | Bb5:4 G5:4 E5:4 | C5:8 r:4 | C5:4 E5:4 G5:4 | Bb5:8 G5:4 |"
         " A5:4 F5:4 C5:4 | F5:8 r:4 | C5:4 F5:4 A5:4 | Eb6:8 C6:4 | D6:4 Bb5:4 F5:4 | Db6:8 Bb5:4 |"
         " A5:4 C6:4 F6:4 | E6:4 G5:4 Bb5:4 | A5:8 G5:4 | F5:8 r:4 |")
    b = ("A5:4 D6:4 F6:4 | E6:8 C#6:4 | D6:4 A5:4 F5:4 | G5:8 Bb5:4 | C6:4 Bb5:4 G5:4 | A5:8 C6:4 |"
         " B5:4 D6:4 F6:4 | E6:8 r:4 | A5:4 D6:4 F6:4 | E6:8 C#6:4 | D6:4 A5:4 F5:4 | G5:8 Bb5:4 |"
         " C6:4 E6:4 G6:4 | F6:8 C6:4 | D6:4 B5:4 G5:4 | C6:8 r:4 |")
    trio = ("F5:4 Bb5:4 D6:4 | C6:8 A5:4 | Eb6:4 C6:4 A5:4 | Bb5:8 r:4 | D6:4 F6:4 D6:4 | Eb6:4 G6:4 Eb6:4 |"
            " C6:4 A5:4 F5:4 | Bb5:8 r:4 |")
    schluss = "A5:4 C6:4 F6:4 | F6:4 D6:4 Bb5:4 | A5:4 C6:4 F6:4 | E6:4 G6:4 Bb6:4 | A6:12 | _:12 | r:12 | r:12 |"

    a_akk = "F | F | C7 | C7 | C7 | C7 | F | F | F | F7 | Bb | Bbm | F | C7 | F | F"
    b_akk = "Dm | A7 | Dm | Gm | C7 | F | G7 | C7 | Dm | A7 | Dm | Gm | C7 | F | G7 | C7"
    t_akk = "Bb | F7 | F7 | Bb | Bb | Eb | F7 | Bb"
    umpapa = Akkorde("....X...X...", lage=62, toene=3, staerke=66, legato=0.6)
    umpapa_voll = Akkorde("....X...X...", lage=64, toene=4, staerke=72, legato=0.6)
    bass = Bass("R...........R...........", unten=29, staerke=94, legato=0.5)
    bass_wechsel = Bass("R...........5...........", unten=29, staerke=94, legato=0.5)
    harfe = Arp("1-3-5-4-5-3-", lage=58, staerke=58)
    walzer_dr = Drums({"k": "X...........", "x": "....o...o..."}, crash=False)

    L.abschnitt("Mondaufgang", "F | C7 | F | C7 | Bb | C7 | F | C7", lead=intro, harfe=harfe,
                streicher=Flaeche(62, 4, 58), celesta=Linie(intro, transponiert=12, staerke=46),
                bass=Bass("R-----------", unten=29, staerke=84))
    L.abschnitt("Walzer A", a_akk, lead=a, streicher=umpapa, bass=bass_wechsel, harfe=harfe, drums=walzer_dr)
    L.abschnitt("Walzer B", b_akk, lead=b, streicher=umpapa, bass=bass_wechsel, harfe=harfe, drums=walzer_dr,
                horn=Flaeche(55, 2, 56))
    L.abschnitt("Walzer A2", a_akk, lead=a, streicher=umpapa_voll, bass=bass_wechsel, harfe=harfe,
                drums=walzer_dr, celesta=Linie(a, transponiert=12, staerke=44), horn=Flaeche(55, 2, 52))
    L.abschnitt("Trio", t_akk, wdh=2, lead=trio, streicher=umpapa, bass=bass, harfe=harfe, drums=walzer_dr,
                horn=Linie("D4:12 | C4:12 | A3:12 | Bb3:12 | D4:12 | Eb4:12 | C4:12 | D4:12 |", staerke=62))
    L.abschnitt("Walzer B2", b_akk, lead=b, streicher=umpapa_voll, bass=bass_wechsel, harfe=harfe, drums=walzer_dr,
                celesta=Linie(b, transponiert=12, staerke=42))
    L.abschnitt("Walzer A3", a_akk, lead=a, streicher=umpapa_voll, bass=bass_wechsel, harfe=harfe,
                drums=walzer_dr, horn=Flaeche(55, 2, 58))
    L.abschnitt("Monduntergang", "F | Bb | F | C7 | F | F | F | F", lead=schluss, harfe=harfe,
                streicher=Flaeche(62, 4, 62), celesta=Linie("r:12 | r:12 | r:12 | r:12 | F6:4 A6:4 C7:4 | F7:12 | r:12 | r:12 |",
                                                            staerke=46),
                bass=Bass("R-----------", unten=29, staerke=84))
    return L
