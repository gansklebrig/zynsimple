# -*- coding: utf-8 -*-
"""Glut des Drachen – epischer Power Metal in d-Moll, Schlussrefrain eine Stufe höher in e-Moll."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Arp, Linie, diatonisch


def lied():
    L = Lied("drache", "Glut des Drachen", "Epischer Power Metal", 150, "Dm", "drache", "episch · Metal",
             schwierigkeit=4, farbe="#e5484d", seed=7)
    L.vorschau = "Refrain"
    L.spur("lead", 29, 0, vol=112, pan=64, hall=50, chorus=30)
    L.spur("bass", 34, 1, vol=104, pan=64, hall=10)
    L.spur("rhythm_l", 30, 2, vol=88, pan=24, hall=20)
    L.spur("rhythm_r", 30, 3, vol=88, pan=104, hall=20)
    L.spur("harmonie", 29, 4, vol=84, pan=96, hall=55, chorus=30)
    L.spur("streicher", 48, 5, vol=76, pan=50, hall=80)
    L.spur("chor", 52, 6, vol=82, pan=78, hall=90)
    L.spur("pauke", 47, 7, vol=100, pan=64, hall=70)
    L.spur("drums", 16, 9, vol=112, hall=30)

    intro = ("D5:8 F5:4 A5:4 | Bb5:6 A5:2 G5:4 F5:4 | E5:8 G5:4 C6:4 | C#6:12 E5:4 |"
             " D6:8 C6:4 A5:4 | Bb5:8 D6:4 F6:4 | E6:4 D6:4 Bb5:4 G5:4 | A5:12 r:4 |")
    riff = ("D5:2 D5:1 D5:1 A5:2 D5:1 D5:1 F5:2 D5:1 D5:1 E5:2 F5:2 |"
            " D5:2 D5:1 D5:1 A5:2 D5:1 D5:1 Bb5:2 A5:2 G5:2 F5:2 |"
            " C5:2 C5:1 C5:1 G5:2 C5:1 C5:1 E5:2 C5:1 C5:1 D5:2 E5:2 |"
            " A4:2 A4:1 A4:1 E5:2 A4:1 A4:1 C#5:2 E5:2 A5:4 |")
    strophe_a = ("r:2 A4:2 D5:2 E5:2 F5:4 E5:2 D5:2 | E5:4 D5:4 A4:8 | r:2 Bb4:2 D5:2 F5:2 G5:4 F5:2 D5:2 |"
                 " E5:6 F5:2 G5:8 | r:2 A4:2 D5:2 E5:2 F5:4 G5:2 A5:2 | A5:4 G5:2 F5:2 E5:8 |")
    strophe_1 = strophe_a + " r:2 G5:2 Bb5:2 A5:2 G5:4 F5:2 E5:2 | C#5:4 E5:4 A5:8 |"
    strophe_2 = strophe_a + " r:2 G5:2 Bb5:2 A5:2 G5:4 A5:2 Bb5:2 | A5:12 r:4 |"
    vor = ("F5:4 F5:2 G5:2 F5:4 D5:4 | E5:4 E5:2 F5:2 G5:8 | A5:4 A5:2 Bb5:2 A5:4 F5:4 | D5:8 r:4 A4:4 |"
           " Bb4:4 D5:4 F5:4 Bb5:4 | C6:4 Bb5:4 A5:4 G5:4 | Bb5:4 A5:4 G5:4 F5:4 | E5:4 C#5:4 E5:4 A5:4 |")
    refrain = ("D6:6 C6:2 A5:4 F5:4 | D6:6 C6:2 Bb5:4 F5:4 | C6:6 Bb5:2 A5:4 C6:4 | G5:12 r:4 |"
               " D6:6 C6:2 A5:4 D6:2 E6:2 | F6:6 E6:2 D6:4 Bb5:4 | Bb5:4 D6:4 C#6:4 E6:4 | D6:12 r:4 |")
    refrain_harm = diatonisch(refrain.replace("C#6", "C6"), -2, "D", "moll")
    solo = ("D5:2 F5:2 A5:2 D6:2 A5:2 F5:2 D5:2 F5:2 | Bb4:2 D5:2 F5:2 Bb5:2 F5:2 D5:2 Bb4:2 D5:2 |"
            " C5:2 E5:2 G5:2 C6:2 G5:2 E5:2 C5:2 E5:2 | A4:2 C#5:2 E5:2 A5:2 C#6:4 A5:4 |"
            " D6:1 C6:1 A5:1 F5:1 D6:1 C6:1 A5:1 F5:1 D6:2 F6:2 E6:2 D6:2 |"
            " D6:1 Bb5:1 F5:1 D5:1 D6:1 Bb5:1 F5:1 D5:1 F6:4 D6:4 |"
            " E6:2 D6:2 C6:2 Bb5:2 A5:2 G5:2 F5:2 E5:2 | C#5:2 E5:2 A5:2 C#6:2 E6:8 |")
    bruecke = "D5:16 | C5:8 A4:8 | Bb4:8 D5:8 | A4:16 | F5:16 | E5:8 C5:8 | D5:8 G5:8 | A5:8 C#6:4 E6:4 |"

    galopp = Drums({"k": "X.xxX.xxX.xxX.xx", "s": "....X.......X...", "r": "x.x.x.x.x.x.x.x."},
                   fill={"s": "x.x.x.x.xxxxXXXX", "t": "", "r": "", "k": "X...X...X...X..."})
    strophe_dr = Drums({"k": "X.....x.X.x.....", "s": "....X.......X...", "h": "x.x.x.x.x.x.x.x."},
                       fill={"s": "....x.x.xxxxXXXX", "m": "........x.x.....", "h": ""})
    doppel = Drums({"k": "xxxxxxxxxxxxxxxx", "s": "....X.......X...", "C": "x.......x.......", "r": "..x.x.x...x.x.x."},
                   fill={"s": "X.X.X.X.XXXXXXXX", "f": "x.x.x.x.........", "r": "", "C": ""})
    intro_dr = Drums({"T": "X...........x...", "F": "........x.......", "c": "X..............."}, crash=False)
    ruhig = Drums({"k": "X.......X.......", "x": "....x.......x...", "r": "x...x...x...x..."}, crash=False)

    galopp_git = Akkorde("X.xxX.xxX.xxX.xx", lage=50, power=True, staerke=96, legato=0.7)
    achtel_git = Akkorde("XxXxXxXxXxXxXxXx", lage=50, power=True, staerke=92, legato=0.6)
    lang_git = Akkorde("X---------------", lage=50, power=True, staerke=100)

    L.abschnitt("Intro", "Dm | Bb | C | A | Dm | Bb | Gm | A",
                lead=intro, streicher=Flaeche(60, 4, 70), chor=Flaeche(67, 3, 64), drums=intro_dr,
                pauke=Linie("D3:2! D3:2 r:12 | Bb2:2! r:14 | C3:2! r:14 | A2:2 A2:2 A2:2 A2:2 r:8 |"),
                bass=Bass("R---------------"), rhythm_l=lang_git)
    L.abschnitt("Riff", "Dm | Bb | C | A", wdh=2, lead=riff, drums=galopp, bass=Bass("R.RRR.RRR.RRR.RR"),
                rhythm_l=galopp_git, rhythm_r=galopp_git, streicher=Flaeche(62, 3, 54))
    L.abschnitt("Strophe 1", "Dm | Dm | Bb | C | Dm | Dm C | Gm | A", lead=strophe_1, drums=strophe_dr,
                bass=Bass("R.R.R.R.R.R.R.R5"), rhythm_l=Akkorde("X.x.x.x.X.x.x.x.", lage=50, power=True, staerke=82),
                rhythm_r=Akkorde("X---------------", lage=50, power=True, staerke=70))
    L.abschnitt("Strophe 1b", "Dm | Dm | Bb | C | Dm | Dm C | Gm | A", lead=strophe_2, drums=strophe_dr,
                bass=Bass("R.R.R.R.R.R.R.R5"), rhythm_l=Akkorde("X.x.x.x.X.x.x.x.", lage=50, power=True, staerke=82),
                rhythm_r=Akkorde("X.x.x.x.X.x.x.x.", lage=50, power=True, staerke=78),
                streicher=Flaeche(60, 3, 50))
    L.abschnitt("Aufstieg", "Bb | C | Dm | Dm | Bb | C | Gm | A", lead=vor,
                drums=Drums({"k": "X...x...X...x...", "s": "....X.......X...", "r": "x.x.x.x.x.x.x.x."},
                            fill={"s": "X.X.X.X.XXXXXXXX", "k": "X.X.X.X.X.X.X.X.", "r": ""}),
                bass=Bass("RRRRRRRRRRRRRRRR"), rhythm_l=achtel_git, rhythm_r=achtel_git,
                streicher=Flaeche(62, 4, 72), chor=Flaeche(69, 3, 58))
    L.abschnitt("Refrain", "Dm | Bb | F | C | Dm | Bb | Gm A | Dm", lead=refrain, harmonie=refrain_harm,
                drums=doppel, bass=Bass("R.RRR.RRR.RRR.RR"), rhythm_l=galopp_git, rhythm_r=galopp_git,
                streicher=Flaeche(64, 4, 80, oktave=True), chor=Flaeche(69, 4, 82))
    L.abschnitt("Riff 2", "Dm | Bb | C | A", lead=riff, drums=galopp, bass=Bass("R.RRR.RRR.RRR.RR"),
                rhythm_l=galopp_git, rhythm_r=galopp_git)
    L.abschnitt("Strophe 2", "Dm | Dm | Bb | C | Dm | Dm C | Gm | A", lead=strophe_2, drums=strophe_dr,
                bass=Bass("R.R.R.R.R.R.R.R5"), rhythm_l=Akkorde("X.x.x.x.X.x.x.x.", lage=50, power=True, staerke=84),
                rhythm_r=Akkorde("X.x.x.x.X.x.x.x.", lage=50, power=True, staerke=80), streicher=Flaeche(60, 3, 52))
    L.abschnitt("Aufstieg 2", "Bb | C | Dm | Dm | Bb | C | Gm | A", lead=vor,
                drums=Drums({"k": "X...x...X...x...", "s": "....X.......X...", "r": "x.x.x.x.x.x.x.x."},
                            fill={"s": "X.X.X.X.XXXXXXXX", "k": "X.X.X.X.X.X.X.X.", "r": ""}),
                bass=Bass("RRRRRRRRRRRRRRRR"), rhythm_l=achtel_git, rhythm_r=achtel_git,
                streicher=Flaeche(62, 4, 72), chor=Flaeche(69, 3, 62))
    L.abschnitt("Refrain 2", "Dm | Bb | F | C | Dm | Bb | Gm A | Dm", lead=refrain, harmonie=refrain_harm,
                drums=doppel, bass=Bass("R.RRR.RRR.RRR.RR"), rhythm_l=galopp_git, rhythm_r=galopp_git,
                streicher=Flaeche(64, 4, 80, oktave=True), chor=Flaeche(69, 4, 84))
    L.abschnitt("Solo", "Dm | Bb | C | A | Dm | Bb | C | A", lead=solo, drums=doppel,
                bass=Bass("RRRRRRRRRRRRRRRR"), rhythm_l=achtel_git, rhythm_r=achtel_git,
                harmonie=Linie("r:16 | r:16 | r:16 | r:16 | A5:16 | F5:16 | G5:16 | E5:16 |", staerke=70))
    L.abschnitt("Brücke", "Bb | F | Gm | Dm | Bb | F | Gm | A", lead=bruecke, drums=ruhig,
                bass=Bass("R-------R-------"), streicher=Flaeche(60, 4, 64), chor=Flaeche(67, 3, 70),
                harmonie=Arp("1234321234321234", lage=60, staerke=56),
                pauke=Linie("r:16 | r:16 | r:16 | r:16 | r:16 | r:16 | r:16 | A2:1 A2:1 A2:1 A2:1 A2:2 A2:2 A2:2 A2:2 A2:4! |"))
    L.abschnitt("Refrain in E", "Em | C | G | D | Em | C | Am B | Em", wdh=1,
                lead=Linie(refrain, transponiert=2), harmonie=Linie(refrain_harm, transponiert=2),
                drums=doppel, bass=Bass("R.RRR.RRR.RRR.RR"), rhythm_l=galopp_git, rhythm_r=galopp_git,
                streicher=Flaeche(66, 4, 86, oktave=True), chor=Flaeche(71, 4, 90))
    L.abschnitt("Refrain in E 2", "Em | C | G | D | Em | C | Am B | Em",
                lead=Linie(refrain, transponiert=2), harmonie=Linie(refrain_harm, transponiert=2),
                drums=doppel, bass=Bass("R.RRR.RRR.RRR.RR"), rhythm_l=galopp_git, rhythm_r=galopp_git,
                streicher=Flaeche(66, 4, 90, oktave=True), chor=Flaeche(71, 4, 94))
    L.abschnitt("Schluss", "Em | C | D | Em", lead="E6:16 | E6:8 G6:8 | F#6:16 | E6:16 |",
                harmonie="B5:16 | C6:8 E6:8 | D6:16 | B5:16 |",
                drums=Drums({"k": "X...X...X...X...", "s": "X.......X.......", "C": "X.......X......."},
                            fill={"s": "X...............", "k": "X...............", "C": "X...............",
                                  "T": "X..............."}),
                bass=Bass("R---------------"), rhythm_l=lang_git, rhythm_r=lang_git,
                streicher=Flaeche(66, 4, 90, oktave=True), chor=Flaeche(71, 4, 96),
                pauke=Linie("E2:1 E2:1 E2:1 E2:1 E2:4! r:8 | r:16 | r:16 | E2:16! |"))
    return L
