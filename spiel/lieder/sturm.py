# -*- coding: utf-8 -*-
"""Sturm über Thalgard – Speed Metal in e-Moll: Thrash-Riff, Hymnen-Refrain, langes Solo."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Linie, diatonisch


def lied():
    L = Lied("sturm", "Sturm über Thalgard", "Speed Metal · für Profis", 172, "Em", "sturm", "Metal · rasend",
             schwierigkeit=5, farbe="#c0392b", seed=71)
    L.vorschau = "Refrain"
    L.spur("lead", 29, 0, vol=112, pan=64, hall=45, chorus=20)
    L.spur("bass", 34, 1, vol=106, pan=64, hall=10)
    L.spur("rhythm_l", 30, 2, vol=90, pan=20, hall=15)
    L.spur("rhythm_r", 30, 3, vol=90, pan=108, hall=15)
    L.spur("harmonie", 29, 4, vol=80, pan=92, hall=45)
    L.spur("orgel", 19, 5, vol=56, pan=64, hall=80)
    L.spur("drums", 16, 9, vol=114, hall=25)

    riff = ("E4:1 E4:1 B4:1 E4:1 E4:1 G4:1 E4:1 E4:1 A4:1 E4:1 E4:1 B4:1 E4:1 C5:1 B4:1 G4:1 |"
            " E4:1 E4:1 B4:1 E4:1 E4:1 G4:1 E4:1 E4:1 D5:2 C5:2 B4:2 G4:2 |"
            " C5:2 C5:1 C5:1 G4:2 C5:2 D5:2 D5:1 D5:1 A4:2 D5:2 |"
            " B4:2 D#5:2 F#5:2 B5:2 A5:2 F#5:2 D#5:2 B4:2 |")
    strophe = ("E5:4 E5:2 F#5:2 G5:4 F#5:2 E5:2 | B4:8 r:4 B4:2 D5:2 | E5:4 E5:2 G5:2 C6:4 B5:2 G5:2 |"
               " A5:8 F#5:4 D5:4 | E5:4 E5:2 F#5:2 G5:4 A5:2 B5:2 | B5:8 r:4 E6:2 D6:2 |"
               " C6:4 B5:2 A5:2 G5:4 E5:4 | F#5:8 D#5:8 |")
    refrain = ("G5:6 E5:2 G5:4 C6:4 | A5:6 F#5:2 A5:4 D6:4 | B5:6 G5:2 E5:4 G5:4 | B5:12 r:4 |"
               " E6:6 D6:2 C6:4 G5:4 | F#6:6 E6:2 D6:4 A5:4 | D#6:4 F#6:4 B6:8 | A6:4 F#6:4 D#6:8 |")
    solo = ("E5:1 G5:1 B5:1 E6:1 G6:1 E6:1 B5:1 G5:1 E5:1 G5:1 B5:1 E6:1 G6:4 |"
            " E6:1 C6:1 G5:1 E5:1 E6:1 C6:1 G5:1 E5:1 G6:4 E6:4 | F#6:2 E6:2 D6:2 A5:2 F#5:2 A5:2 D6:4 |"
            " D#6:2 F#6:2 B6:4 A6:2 F#6:2 D#6:4 | B6:4 G6:2 E6:2 B5:2 G5:2 E5:4 |"
            " C6:2 E6:2 G6:2 C7:2 B6:2 G6:2 E6:4 | D6:1 E6:1 F#6:1 G6:1 A6:4 F#6:2 D6:2 A5:4 |"
            " B5:2 D#6:2 F#6:2 A6:2 B6:8 | E6:2 D#6:2 E6:2 F#6:2 G6:2 F#6:2 E6:2 B5:2 |"
            " C6:2 B5:2 C6:2 E6:2 G6:4 E6:4 | D6:2 C#6:2 D6:2 F#6:2 A6:4 F#6:4 |"
            " B5:2 C6:2 D#6:2 F#6:2 B6:4 A6:4 | G6:1 F#6:1 E6:1 D#6:1 E6:1 F#6:1 G6:1 A6:1 B6:8 |"
            " C7:4 B6:2 G6:2 E6:4 C6:4 | A6:2 F#6:2 D6:2 A5:2 F#5:2 A5:2 D6:4 | D#6:4 F#6:4 B6:8 |")
    stampf = "E4:4 r:2 E4:2 G4:4 F#4:4 | E4:4 r:4 B4:8 | C5:4 r:2 C5:2 E5:4 D5:4 | B4:8 D#5:8 |"

    riff_akk = "Em | Em | C D | B"
    s_akk = "Em | Em | C | D | Em | Em | C | B"
    r_akk = "C | D | Em | Em | C | D | B | B"
    thrash = Drums({"k": "x...x...x...x...", "s": "..X...X...X...X.", "r": "x.x.x.x.x.x.x.x."},
                   fill={"s": "X.X.X.X.XXXXXXXX", "f": "x.x.x.x.........", "r": ""})
    doppel = Drums({"k": "xxxxxxxxxxxxxxxx", "s": "....X.......X...", "C": "x...x...x...x..."},
                   fill={"s": "X.X.X.X.XXXXXXXX", "t": "x.x.x.x.........", "C": ""})
    blast = Drums({"k": "xxxxxxxxxxxxxxxx", "s": "x.x.x.x.x.x.x.x.", "r": "x.x.x.x.x.x.x.x."},
                  fill={"s": "XXXXXXXXXXXXXXXX", "r": "", "c": "X..............."})
    halb = Drums({"k": "X.X.......X.....", "s": "........X.......", "C": "x...x...x...x..."},
                 fill={"s": "........X.X.XXXX", "C": ""})
    chug = Akkorde("XxxxXxxxXxXxXxxx", lage=46, power=True, staerke=96, legato=0.55)
    achtel = Akkorde("XxXxXxXxXxXxXxXx", lage=50, power=True, staerke=92, legato=0.6)
    halte = Akkorde("X-------X-------", lage=50, power=True, staerke=94)
    bass16 = Bass("RRRRRRRRRRRRRRRR", unten=28, staerke=96, legato=0.6)
    bass8 = Bass("R.R.R.R.R.R.R.R.", unten=28, staerke=98, legato=0.7)

    L.abschnitt("Intro", riff_akk, lead=riff, rhythm_l=chug,
                drums=Drums({"h": "x.x.x.x.x.x.x.x."}, fill={"s": "X.X.X.X.XXXXXXXX", "h": ""}, crash=False))
    L.abschnitt("Riff", riff_akk, wdh=2, lead=riff, rhythm_l=chug, rhythm_r=chug, bass=bass16, drums=thrash)
    L.abschnitt("Strophe", s_akk, wdh=2, lead=strophe, rhythm_l=achtel, rhythm_r=chug, bass=bass8, drums=thrash)
    L.abschnitt("Refrain", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "moll"),
                rhythm_l=halte, rhythm_r=achtel, bass=bass8, drums=doppel, orgel=Flaeche(64, 4, 70))
    L.abschnitt("Riff 2", riff_akk, lead=riff, rhythm_l=chug, rhythm_r=chug, bass=bass16, drums=thrash)
    L.abschnitt("Strophe 2", s_akk, lead=strophe, rhythm_l=achtel, rhythm_r=chug, bass=bass8, drums=thrash,
                orgel=Flaeche(60, 3, 50))
    L.abschnitt("Refrain 2", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "moll"),
                rhythm_l=halte, rhythm_r=achtel, bass=bass8, drums=doppel, orgel=Flaeche(64, 4, 74))
    L.abschnitt("Solo", "Em | C | D | B", wdh=4, lead=solo, rhythm_l=achtel, rhythm_r=achtel, bass=bass16,
                drums=blast, orgel=Flaeche(62, 4, 60))
    L.abschnitt("Stampfen", "Em | Em | C | B", wdh=2, lead=stampf, rhythm_l=Akkorde("X.X.......X.....", lage=46, power=True,
                staerke=100), rhythm_r=halte, bass=Bass("R.R.......R.....", unten=28, staerke=104), drums=halb)
    L.abschnitt("Refrain 3", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "moll"),
                rhythm_l=halte, rhythm_r=achtel, bass=bass8, drums=doppel, orgel=Flaeche(64, 4, 80))
    L.abschnitt("Refrain 4", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "moll"),
                rhythm_l=chug, rhythm_r=achtel, bass=bass16, drums=blast, orgel=Flaeche(64, 4, 84))
    L.abschnitt("Schluss", "Em | C | B | Em", lead="E6:16 | G6:16 | F#6:8 D#6:8 | E6:16 |",
                harmonie="B5:16 | E6:16 | D#6:8 B5:8 | B5:16 |", rhythm_l=halte, rhythm_r=halte,
                bass=Bass("R-------R-------", unten=28),
                drums=Drums({"k": "xxxxxxxxxxxxxxxx", "C": "X...X...X...X..."},
                            fill={"k": "X...............", "C": "X...............", "s": "X..............."}),
                orgel=Flaeche(64, 4, 80))
    return L
