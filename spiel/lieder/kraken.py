# -*- coding: utf-8 -*-
"""Ritt des Kraken – Surf-Rock in a-Moll: hallige Tremolo-Gitarre, Orgel, Tom-Wirbel."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Linie


def lied():
    L = Lied("kraken", "Ritt des Kraken", "Surf-Rock · Tremolo", 168, "Am", "kraken", "wild · Meer bei Blutmond",
             tonleiter="harmonisch", schwierigkeit=3, farbe="#b04ad0", seed=91)
    L.vorschau = "Welle A"
    L.spur("lead", 27, 0, vol=112, pan=64, hall=100)
    L.spur("bass", 34, 1, vol=100, pan=64, hall=20)
    L.spur("rhythmus", 27, 2, vol=72, pan=24, hall=70)
    L.spur("orgel", 16, 3, vol=62, pan=100, hall=60)
    L.spur("blech", 61, 4, vol=74, pan=80, hall=60)
    L.spur("drums", 0, 9, vol=102, hall=40)

    welle = ("A4:2 C5:2 E5:2 A5:2 G#5:2 A5:2 E5:4 | A5:1 A5:1 A5:1 A5:1 C6:2 B5:2 A5:2 E5:2 C5:4 |"
             " G4:2 B4:2 D5:2 G5:2 F#5:2 G5:2 D5:4 | G5:1 G5:1 G5:1 G5:1 B5:2 A5:2 G5:2 D5:2 B4:4 |"
             " F4:2 A4:2 C5:2 F5:2 E5:2 F5:2 C5:4 | F5:1 F5:1 F5:1 F5:1 A5:2 G5:2 F5:2 C5:2 A4:4 |"
             " E5:2 F5:2 G#5:2 B5:2 G#5:2 F5:2 E5:4 | E5:1 E5:1 E5:1 E5:1 _:4 r:4 E4:4 |")
    b = ("F5:4 E5:2 D5:2 A5:8 | C6:4 B5:2 A5:2 E5:8 | D6:4 C6:2 A5:2 F5:4 D5:4 | E5:4 G#5:4 B5:8 |"
         " F5:4 A5:2 D6:2 F6:8 | E6:4 C6:2 A5:2 E5:8 | F5:2 A5:2 C6:2 F6:2 E6:2 C6:2 A5:2 F5:2 | G#5:4 B5:4 E6:8 |")
    solo = ("A5:1 C6:1 E6:1 A6:1 E6:1 C6:1 A5:1 E5:1 A5:4 C6:4 | B5:1 D6:1 G6:1 D6:1 B5:1 G5:1 D5:1 B4:1 G5:8 |"
            " A5:2 C6:2 F6:2 C6:2 A5:2 F5:2 C5:4 | E5:2 F5:2 G#5:2 A5:2 B5:2 C6:2 D6:2 E6:2 |"
            " E6:1 E6:1 E6:1 E6:1 D6:1 D6:1 D6:1 D6:1 C6:1 C6:1 C6:1 C6:1 A5:4 |"
            " D6:1 D6:1 D6:1 D6:1 C6:1 C6:1 C6:1 C6:1 B5:1 B5:1 B5:1 B5:1 G5:4 |"
            " C6:2 A5:2 F5:2 A5:2 C6:2 F6:2 A6:4 | G#6:4 E6:4 B5:4 G#5:4 |")
    tiefe = ("A4:2 r:2 A4:2 r:2 C5:2 r:2 A4:2 r:2 | E5:2 r:6 D5:2 r:2 C5:2 r:2 |"
             " E4:2 r:2 E4:2 r:2 G#4:2 r:2 E4:2 r:2 | B4:2 r:6 A4:2 r:2 G#4:2 r:2 |")

    a_akk = "Am | Am | G | G | F | F | E | E"
    b_akk = "Dm | Am | Dm | E | Dm | Am | F | E"
    surf = Drums({"k": "X.....x.X.....x.", "s": "....X.......X...", "h": "x.x.x.x.x.x.x.x."},
                 fill={"t": "xxxx............", "m": "....xxxx........", "f": "........xxxxXXXX", "h": "", "s": ""})
    surf_voll = Drums({"k": "X.x...x.X.x...x.", "s": "....X.......X...", "r": "x.x.x.x.x.x.x.x."},
                      fill={"s": "x.x.x.x.xxxxXXXX", "r": ""})
    toms = Drums({"f": "x.ox.ox.x.ox.ox.", "k": "X.......X.......", "m": "....x.......x..."},
                 fill={"t": "xxxx", "m": "....xxxx", "f": "........xxxxXXXX"}, crash=False)
    bass = Bass("R.R.R.R.R.R.R.5.", unten=28, staerke=96, legato=0.7)
    bass_lauf = Bass("R.3.5.3.R.3.5.a.", unten=28, staerke=96, legato=0.7)
    rhythmus = Akkorde("X..X..X.X..X..X.", lage=57, toene=3, staerke=76, legato=0.5)

    L.abschnitt("Flut", "Am | Am | E | E",
                drums=Drums({"f": "oooooooooooooooo"}, fill={"f": "oooxxxxxxxxXXXXX", "c": "...............X"},
                            crash=False),
                lead="A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 | A5:16 |"
                     " E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 E5:1 | G#5:16 |",
                orgel=Flaeche(60, 3, 50))
    L.abschnitt("Welle A", a_akk, wdh=2, lead=welle, drums=surf, bass=bass, rhythmus=rhythmus, orgel=Flaeche(60, 3, 56))
    L.abschnitt("Welle B", b_akk, lead=b, drums=surf_voll, bass=bass_lauf, rhythmus=rhythmus,
                orgel=Flaeche(62, 4, 62), blech=Akkorde("X.......X.......", lage=64, toene=3, staerke=78, legato=0.6))
    L.abschnitt("Welle A2", a_akk, wdh=2, lead=welle, drums=surf_voll, bass=bass, rhythmus=rhythmus,
                orgel=Flaeche(60, 3, 58), blech=Linie("r:16 | r:16 | r:16 | r:16 | r:16 | r:16 | E4+G#4+B4:8! r:8 | r:16 |"))
    L.abschnitt("Abgrund", "Am | Am | E | E", wdh=2, lead=tiefe, drums=toms,
                bass=Bass("R...R...R...R...", unten=28, staerke=100), orgel=Flaeche(57, 3, 60))
    L.abschnitt("Solo", "Am | G | F | E | Am | G | F | E", lead=solo, drums=surf_voll, bass=bass_lauf,
                rhythmus=rhythmus, orgel=Flaeche(60, 3, 58))
    L.abschnitt("Welle B2", b_akk, lead=b, drums=surf_voll, bass=bass_lauf, rhythmus=rhythmus,
                orgel=Flaeche(62, 4, 66), blech=Akkorde("X.......X.......", lage=64, toene=3, staerke=84, legato=0.6))
    L.abschnitt("Welle A3", a_akk, lead=welle, drums=surf_voll, bass=bass, rhythmus=rhythmus,
                orgel=Flaeche(60, 3, 60), blech=Linie(welle, transponiert=-12, staerke=60))
    L.abschnitt("Untergang", "Am | F | E | Am",
                lead="A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 A5:1 C6:8 | F5:8 A5:8 | G#5:8 B5:8 | A5:16 |",
                drums=Drums({"k": "X.......X.......", "s": "....X.......X..."},
                            fill={"f": "xxxxxxxxXXXX....", "c": "............X...", "k": "............X..."}),
                bass=Bass("R-------R-------", unten=28), orgel=Flaeche(60, 3, 66),
                blech=Linie("r:16 | r:16 | E4+G#4+B4:16 | A3+C4+E4+A4:12! r:4 |"))
    return L
