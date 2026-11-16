# -*- coding: utf-8 -*-
"""Galopp der Goblins – schneller, frecher Ska-Punk in B-Dur mit Trompete, Posaune und Offbeat-Orgel."""
from komponist import Lied, Drums, Bass, Akkorde, Linie


def lied():
    L = Lied("goblins", "Galopp der Goblins", "Ska-Punk · frech & schnell", 184, "Bb", "goblins",
             "lustig · sehr schnell", tonleiter="dur", schwierigkeit=4, farbe="#9ad13a", seed=51)
    L.vorschau = "Refrain"
    L.spur("lead", 56, 0, vol=110, pan=64, hall=40)
    L.spur("bass", 33, 1, vol=104, pan=64, hall=10)
    L.spur("skank", 27, 2, vol=76, pan=28, hall=25)
    L.spur("orgel", 17, 3, vol=66, pan=100, hall=30)
    L.spur("posaune", 57, 4, vol=82, pan=84, hall=40)
    L.spur("brett", 29, 5, vol=70, pan=40, hall=20)
    L.spur("drums", 0, 9, vol=104, hall=20)

    hook = ("D5:2 F5:2 Bb5:2 F5:2 D5:2 F5:2 Bb5:2 C6:2 | D6:4 Bb5:2 G5:2 r:2 G5:2 A5:2 Bb5:2 |"
            " G5:2 Eb5:2 G5:2 Bb5:2 Eb6:4 D6:2 C6:2 | C6:4 A5:2 F5:2 C6:4 r:4 |"
            " D5:2 F5:2 Bb5:2 F5:2 D5:2 F5:2 Bb5:2 C6:2 | D6:4 Bb5:2 G5:2 r:2 G5:2 A5:2 Bb5:2 |"
            " G5:2 Eb5:2 G5:2 Bb5:2 Eb6:4 D6:2 C6:2 | F5:2 G5:2 A5:2 Bb5:2 C6:4 F6:4 |")
    strophe = ("r:2 F5:2 F5:2 D5:2 r:2 F5:2 G5:2 F5:2 | r:2 G5:2 G5:2 D5:2 r:2 Bb4:2 C5:2 D5:2 |"
               " r:2 Eb5:2 Eb5:2 G5:2 r:2 Bb5:2 G5:2 Eb5:2 | F5:4 A5:4 C6:4 r:4 |"
               " r:2 F5:2 F5:2 D5:2 r:2 F5:2 Bb5:2 A5:2 | r:2 G5:2 Bb5:2 D6:2 r:2 Bb5:2 A5:2 G5:2 |"
               " Eb5:2 G5:2 Bb5:2 Eb6:2 D6:2 C6:2 Bb5:2 G5:2 | A5:4 C6:4 F5:8 |")
    refrain = ("Bb5:4 Bb5:2 C6:2 Bb5:4 G5:4 | A5:4 A5:2 Bb5:2 C6:8 | D6:4 C6:2 A5:2 F5:4 A5:4 | Bb5:6 A5:2 G5:8 |"
               " Bb5:4 Bb5:2 C6:2 Eb6:4 D6:4 | C6:4 A5:2 F5:2 C6:4 Eb6:4 | D6:6 C6:2 Bb5:8 |"
               " r:4 F5:2 G5:2 A5:2 Bb5:2 r:4 |")
    bruecke = ("C5:2 r:2 Eb5:2 r:2 G5:2 r:2 Eb5:2 r:2 | F5:2 r:2 A5:2 r:2 C6:2 r:2 A5:2 r:2 |"
               " Bb5:2 r:2 D6:2 r:2 F6:4 D6:4 | G5:2 r:2 Bb5:2 r:2 D6:8 |"
               " Eb6:2 D6:2 C6:2 Bb5:2 G5:2 Bb5:2 C6:4 | A5:2 C6:2 F6:2 C6:2 A5:2 F5:2 C5:4 |"
               " F5:1 G5:1 A5:1 Bb5:1 C6:1 D6:1 Eb6:1 F6:1 r:8 | r:16 |")
    solo = ("F5:1 Bb5:1 D6:1 F6:1 D6:2 Bb5:2 F5:2 D5:2 Bb4:4 | G5:2 Bb5:2 D6:2 G6:2 F6:2 D6:2 Bb5:4 |"
            " Eb6:2 D6:2 C6:2 Bb5:2 G5:2 Eb5:2 G5:4 | A5:2 C6:2 Eb6:2 C6:2 A5:2 F5:2 A5:4 |"
            " Bb5:1 C6:1 D6:1 Eb6:1 F6:4 D6:4 Bb5:4 | Bb5:2 A5:2 G5:2 D6:2 Bb5:4 G5:4 |"
            " G5:2 Bb5:2 Eb6:2 G6:2 F6:2 Eb6:2 D6:2 C6:2 | C6:4 D6:2 Eb6:2 F6:8 |")

    v_akk = "Bb | Gm | Eb | F | Bb | Gm | Eb | F"
    r_akk = "Eb | F | Dm | Gm | Eb | F | Bb | Bb"
    skank = Akkorde("..X...X...X...X.", lage=64, toene=3, staerke=86, legato=0.25)
    orgel = Akkorde("..XX..XX..XX..XX", lage=60, toene=3, staerke=70, legato=0.3)
    brett = Akkorde("XxXxXxXxXxXxXxXx", lage=50, power=True, staerke=86, legato=0.6)
    lauf = Bass("R.3.5.O.R.3.5.a.", unten=31, staerke=98, legato=0.7)
    punk = Bass("RRRRRRRRRRRRRRRR", unten=31, staerke=96, legato=0.6)
    ska = Drums({"k": "X.......X.......", "s": "....X.......X...", "h": "..x...x...x...x."},
                fill={"s": "....X...x.xxXxXX", "h": ""})
    punk_dr = Drums({"k": "X...X...X...X...", "s": "..X...X...X...X.", "c": "x...x...x...x..."},
                    fill={"s": "X.X.X.X.XXXXXXXX", "c": "", "t": "", "k": "X...X...X...X..."})
    lachen = Linie("r:16 | r:16 | r:16 | r:12 Bb2:1 r:1 Bb2:1 r:1 | r:16 | r:16 | r:16 | r:8 F2:2 F2:2 Bb2:4! |",
                   staerke=96)

    L.abschnitt("Intro", v_akk, lead=hook, skank=skank, orgel=orgel, bass=lauf, drums=ska, posaune=lachen)
    L.abschnitt("Strophe", v_akk, wdh=2, lead=strophe, skank=skank, orgel=orgel, bass=lauf, drums=ska)
    L.abschnitt("Refrain", r_akk, lead=refrain, brett=brett, orgel=orgel, bass=punk, drums=punk_dr,
                posaune=Linie(refrain, transponiert=-12, staerke=74))
    L.abschnitt("Hook", v_akk, lead=hook, skank=skank, orgel=orgel, bass=lauf, drums=ska, posaune=lachen)
    L.abschnitt("Strophe 2", v_akk, wdh=2, lead=strophe, skank=skank, orgel=orgel, bass=lauf, drums=ska,
                posaune=Linie("r:16 | r:16 | r:16 | F3:4 A3:4 C4:4 r:4 | r:16 | r:16 | r:16 | A3:4 C4:4 F3:8 |",
                              staerke=72))
    L.abschnitt("Refrain 2", r_akk, lead=refrain, brett=brett, orgel=orgel, bass=punk, drums=punk_dr,
                posaune=Linie(refrain, transponiert=-12, staerke=76))
    L.abschnitt("Schleichen", "Cm | F | Bb | Gm | Cm | F | F | F", lead=bruecke,
                bass=Bass("R...R...5...R...", unten=31, staerke=90, legato=0.4),
                drums=Drums({"k": "X.......X.......", "v": "..x...x...x...x."},
                            fill={"s": "X.X.X.X.XXXXXXXX", "t": "X...X...X...X...", "v": ""}, crash=False),
                posaune=Linie("C3:2 r:14 | F2:2 r:14 | Bb2:2 r:14 | G2:2 r:14 | C3:2 r:14 | F2:2 r:14 | r:16 | r:16 |"))
    L.abschnitt("Solo", v_akk, lead=solo, skank=skank, orgel=orgel, bass=lauf, drums=punk_dr,
                brett=Akkorde("X.......X.......", lage=50, power=True, staerke=80))
    L.abschnitt("Refrain 3", r_akk, lead=refrain, brett=brett, orgel=orgel, bass=punk, drums=punk_dr,
                skank=skank, posaune=Linie(refrain, transponiert=-12, staerke=78))
    L.abschnitt("Refrain 4", r_akk, lead=refrain, brett=brett, orgel=orgel, bass=punk, drums=punk_dr,
                skank=skank, posaune=Linie(refrain, transponiert=-12, staerke=80))
    L.abschnitt("Schluss", "Bb | Bb | F | Bb", lead="Bb5:2 F5:2 D5:2 F5:2 Bb5:8 | r:16 | C6:2 A5:2 F5:2 A5:2 C6:8 |"
                " Bb5:4 r:4 Bb4:4! r:4 |", brett=Akkorde("X-------........X-------........", lage=50, power=True),
                bass=Bass("R-------........", unten=31), drums=Drums({"k": "X...............", "s": "X..............."},
                                                                fill={"k": "X.......X.......", "c": "X.......X......."}),
                posaune=Linie("Bb2:8 r:8 | r:16 | F2:8 r:8 | Bb2:4 r:4 Bb2:4! r:4 |"))
    return L
