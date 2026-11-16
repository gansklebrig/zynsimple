# -*- coding: utf-8 -*-
"""Zur Krummen Gans – lustige Tavernen-Polka in D-Dur mit Geige, Akkordeon, Tuba und Klarinette."""
from komponist import Lied, Drums, Bass, Akkorde, Linie


def lied():
    L = Lied("taverne", "Zur Krummen Gans", "Tavernen-Polka · lustig", 132, "D", "taverne",
             "lustig · schnell · zum Mitschunkeln", tonleiter="dur", schwierigkeit=3, farbe="#e0a046", seed=11)
    L.vorschau = "Teil B"
    L.spur("lead", 110, 0, vol=112, pan=64, hall=40)
    L.spur("bass", 58, 1, vol=104, pan=64, hall=20)
    L.spur("akkordeon", 21, 2, vol=80, pan=36, hall=35)
    L.spur("klarinette", 71, 3, vol=78, pan=96, hall=45)
    L.spur("posaune", 57, 4, vol=86, pan=84, hall=40)
    L.spur("gitarre", 25, 5, vol=60, pan=20, hall=30)
    L.spur("drums", 0, 9, vol=96, hall=25)

    a1 = ("F#5:2 A5:2 D6:2 A5:2 F#5:2 A5:2 D6:4 | E6:2 D6:2 C#6:2 B5:2 A5:4 F#5:4 |"
          " E5:2 G5:2 C#6:2 G5:2 E5:2 G5:2 C#6:4 | D6:2 C#6:2 B5:2 A5:2 G5:4 E5:4 |"
          " C#5:2 E5:2 A5:2 E5:2 C#5:2 E5:2 A5:4 | B5:2 A5:2 G5:2 F#5:2 E5:2 F#5:2 G5:2 E5:2 |"
          " F#5:2 A5:2 D6:2 F#6:2 E6:2 D6:2 C#6:2 E6:2 | D6:4 A5:4 D5:4 r:4 |")
    b = ("B5:3 A5:1 G5:2 B5:2 D6:4 B5:4 | C6:3 B5:1 A5:2 C6:2 E6:4 C6:4 | A5:3 G5:1 F#5:2 A5:2 D6:4 A5:4 |"
         " B5:2 A5:2 G5:2 F#5:2 E5:4 D5:4 | C#5:2 E5:2 A5:2 C#6:2 E6:4 C#6:4 | D6:2 C#6:2 B5:2 A5:2 G5:2 F#5:2 E5:4 |"
         " F#5:2 E5:2 F#5:2 A5:2 G5:2 F#5:2 E5:2 C#5:2 | D5:4 F#5:4 D5:4 r:4 |")
    trio = ("D5:4 G5:4 B5:6 A5:2 | A5:4 F#5:4 C6:8 | C6:4 B5:2 A5:2 F#5:4 A5:4 | B5:4 G5:4 D5:8 |"
            " D5:4 G5:4 B5:4 D6:4 | E6:4 D6:2 C6:2 G5:4 E5:4 | D5:2 F#5:2 A5:2 C6:2 B5:4 A5:4 | G5:12 r:4 |")
    trio2 = trio.replace("G5:12 r:4 |", "G5:4 D5:4 G4:4 r:4 |")

    akk_a = "D | D | A | A | A | A | D | D"
    akk_b = "G | G | D | D | A | A | D | D"
    akk_c = "G | D7 | D7 | G | G | C | D7 | G"

    umpa = Akkorde("B...X...B...X...", lage=62, toene=3, staerke=84, legato=0.5)
    umpa_nach = Akkorde("..X...X...X...X.", lage=62, toene=3, staerke=80, legato=0.45)
    tuba = Bass("R.......L.......", unten=33, staerke=104, legato=0.6)
    tuba_lauf = Bass("R.......L...5.b.", unten=33, staerke=104, legato=0.6)
    polka = Drums({"k": "X.......x.......", "s": "....x.......x...", "w": "..x...x...x...x.", "h": "..x...x...x...x."},
                  fill={"s": "....x...x.x.xxXX", "k": "X.......x.......", "w": "", "h": ""})
    polka_voll = Drums({"k": "X...x...X...x...", "s": "..x...x...x...x.", "w": "x.x.x.x.x.x.x.x.", "c": "X..............."},
                       fill={"s": "x.x.x.x.xxxxXXXX", "w": "", "c": ""})
    # „Hicks“-Posaune am Phrasenende
    hicks = Linie("r:16 | r:16 | r:16 | r:12 A2:2 C#3:2 | r:16 | r:16 | r:16 | r:8 A2:4 D3:4! |", staerke=96)
    klar_gegen = diatonisch_unten(a1)

    L.abschnitt("Auftakt", "D | A | D | A", lead="A5:2 r:2 A5:2 r:2 A5:2 B5:2 C#6:2 D6:2 | E6:8 r:8 |"
                " F#6:2 r:2 F#6:2 r:2 E6:2 D6:2 C#6:2 B5:2 | A5:8 r:4 A4:4 |",
                drums=Drums({"s": "x.x.x.x.x.x.xxXX", "k": "X......."}, crash=False),
                posaune=Linie("D3:4 r:12 | A2:4 r:12 | D3:4 r:12 | A2:2 B2:2 C#3:2 D3:2 E3:8 |"))
    L.abschnitt("Teil A", akk_a, lead=a1, akkordeon=umpa, bass=tuba, drums=polka, posaune=hicks,
                gitarre=umpa_nach)
    L.abschnitt("Teil A2", akk_a, lead=a1, akkordeon=umpa, bass=tuba_lauf, drums=polka_voll,
                klarinette=Linie(klar_gegen, transponiert=-12, staerke=74), gitarre=umpa_nach, posaune=hicks)
    L.abschnitt("Teil B", akk_b, lead=b, akkordeon=Akkorde("X.x.X.x.X.x.X.x.", lage=64, toene=3, staerke=84, legato=0.4),
                bass=tuba, drums=polka_voll, gitarre=umpa_nach,
                klarinette=Linie("D5:16 | E5:16 | F#5:16 | D5:16 | E5:16 | C#5:16 | D5:8 C#5:8 | D5:16 |", staerke=68))
    L.abschnitt("Teil B2", akk_b, lead=b, akkordeon=umpa, bass=tuba_lauf, drums=polka, gitarre=umpa_nach,
                posaune=Linie("r:16 | r:12 G2:2 B2:2 | r:16 | r:12 D3:2 F#3:2 | r:16 | r:12 A2:2 C#3:2 |"
                              " r:16 | r:8 A2:4 D3:4! |"))
    L.abschnitt("Teil A3", akk_a, lead=a1, akkordeon=umpa, bass=tuba, drums=polka_voll, posaune=hicks,
                gitarre=umpa_nach, klarinette=Linie(klar_gegen, transponiert=-12, staerke=74))
    L.abschnitt("Trio", akk_c, lead=trio, akkordeon=Akkorde("B...X.X.B...X.X.", lage=62, toene=3, staerke=80, legato=0.45),
                bass=Bass("R.......5.......", unten=31, staerke=100, legato=0.6), drums=polka, gitarre=umpa_nach,
                klarinette=Linie("B4:16 | C5:16 | A4:16 | B4:16 | B4:16 | C5:16 | A4:8 C5:8 | B4:16 |", staerke=66))
    L.abschnitt("Trio 2", akk_c, lead=trio2, akkordeon=umpa, bass=Bass("R.......5...R.b.", unten=31, staerke=100, legato=0.6),
                drums=polka_voll, gitarre=umpa_nach,
                posaune=Linie("G2:4 r:12 | r:16 | r:16 | r:12 D3:2 B2:2 | G2:4 r:12 | C3:4 r:12 | D3:4 r:4 D3:4 r:4 | G2:4 r:12 |"))
    L.abschnitt("Schwips", "A | A | A | A",
                lead="E5:2 r:2 E5:2 r:2 E5:2 r:2 G5:2 F#5:2 | E5:2 r:6 r:8 | C#6:2 r:2 B5:2 r:2 A5:2 r:2 G5:2 E5:2 |"
                     " A5:4 r:4 A4:2 C#5:2 E5:2 G5:2 |",
                posaune=Linie("A2:2 r:6 A2:2 r:6 | E2:4 F2:2 F#2:2 G2:8 | A2:2 r:6 A2:2 r:6 | E3:4 r:12 |"),
                drums=Drums({"k": "X.......X.......", "v": "....x.......x..."}, crash=False))
    L.abschnitt("Teil A Finale", akk_a, lead=a1, akkordeon=umpa, bass=tuba_lauf, drums=polka_voll,
                klarinette=Linie(klar_gegen, transponiert=-12, staerke=78), gitarre=umpa_nach, posaune=hicks)
    L.abschnitt("Teil B Finale", akk_b, lead=b, akkordeon=Akkorde("X.x.X.x.X.x.X.x.", lage=64, toene=3, staerke=88, legato=0.4),
                bass=tuba_lauf, drums=polka_voll, gitarre=umpa_nach,
                klarinette=Linie("D5:16 | E5:16 | F#5:16 | D5:16 | E5:16 | C#5:16 | D5:8 C#5:8 | D5:16 |", staerke=72))
    L.abschnitt("Prost!", "D | A | D | D", lead="D6:2 r:2 D6:2 r:2 F#6:2 E6:2 D6:2 C#6:2 | B5:2 A5:2 G5:2 E5:2 C#5:8 |"
                " D5:2 F#5:2 A5:2 D6:2 F#6:4 D6:4 | A5:2 r:2 D6:2! r:10 |",
                akkordeon=Akkorde("X...X...X...X...", lage=64, toene=3, staerke=90, legato=0.5),
                bass=Bass("R...L...R...L...", unten=33, staerke=104, legato=0.5),
                drums=Drums({"k": "X...X...X...X...", "s": "..x...x...x...x."},
                            fill={"k": "X.X.X...........", "s": "....X...........", "c": "....X..........."}),
                posaune=Linie("D3:4 r:12 | A2:4 r:12 | D3:4 r:12 | A2:2 r:2 D3:2! r:10 |"))
    return L


def diatonisch_unten(text):
    from komponist import diatonisch
    return diatonisch(text, -2, "D", "dur")
