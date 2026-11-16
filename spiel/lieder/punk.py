# -*- coding: utf-8 -*-
"""Laut und Ehrlich – energiegeladener Pop-Punk in E-Dur: Gitarren-Hook, Mitsing-Refrain, Halftime-Brücke."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Linie, diatonisch


def lied():
    L = Lied("punk", "Laut und Ehrlich", "Pop-Punk · Mitsingen", 176, "E", "punk", "energisch · catchy",
             tonleiter="dur", schwierigkeit=3, farbe="#ff5a8a", seed=101)
    L.vorschau = "Refrain"
    L.spur("lead", 29, 0, vol=112, pan=64, hall=40, chorus=20)
    L.spur("bass", 34, 1, vol=104, pan=64, hall=10)
    L.spur("rhythm_l", 30, 2, vol=86, pan=22, hall=15)
    L.spur("rhythm_r", 30, 3, vol=86, pan=106, hall=15)
    L.spur("harmonie", 29, 4, vol=76, pan=90, hall=45)
    L.spur("klavier", 0, 5, vol=62, pan=64, hall=60)
    L.spur("drums", 0, 9, vol=108, hall=20)

    hook = ("B5:2 G#5:2 E5:2 G#5:2 B5:4 E6:4 | D#6:4 B5:2 F#5:2 D#6:4 F#6:4 | E6:4 C#6:2 G#5:2 C#6:4 E6:4 |"
            " C#6:6 B5:2 A5:8 | B5:2 G#5:2 E5:2 G#5:2 B5:4 E6:4 | D#6:4 B5:2 F#5:2 D#6:4 F#6:4 |"
            " E6:4 C#6:2 G#5:2 C#6:4 E6:4 | C#6:4 B5:4 A5:4 B5:4 |")
    strophe = ("E5:2 E5:2 E5:2 F#5:2 G#5:4 E5:4 | F#5:2 F#5:2 F#5:2 G#5:2 F#5:4 D#5:4 |"
               " E5:2 E5:2 E5:2 F#5:2 G#5:4 B5:4 | A5:4 G#5:4 E5:8 | E5:2 E5:2 G#5:2 B5:2 B5:4 G#5:4 |"
               " F#5:2 F#5:2 A#5:2 B5:2 D#6:4 B5:4 | C#6:4 B5:2 G#5:2 E5:4 C#5:4 | E5:8 r:4 B4:4 |")
    vor = ("C#5:4 E5:4 A5:4 E5:4 | D#5:4 F#5:4 B5:4 F#5:4 | E5:4 G#5:4 C#6:4 G#5:4 | F#5:8 D#5:8 |"
           " E5:2 E5:2 A5:4 C#6:4 A5:4 | F#5:2 F#5:2 B5:4 D#6:4 B5:4 | G#5:2 G#5:2 C#6:4 E6:4 C#6:4 |"
           " D#6:4 F#6:4 D#6:4 B5:4 |")
    refrain = ("G#5:4 G#5:2 G#5:2 B5:4 G#5:4 | F#5:4 F#5:2 D#5:2 F#5:8 | E5:4 E5:2 G#5:2 C#6:4 B5:4 |"
               " A5:6 G#5:2 E5:8 | G#5:4 G#5:2 B5:2 E6:4 D#6:4 | F#6:4 D#6:2 B5:2 F#5:8 |"
               " E6:4 C#6:2 A5:2 E5:4 C#6:4 | B5:12 r:4 |")
    bruecke = "C#5:8 E5:8 | C#5:8 A4:8 | B4:8 G#4:8 | F#4:8 D#5:8 | E5:8 G#5:8 | A5:8 C#6:8 | B5:8 G#5:8 | F#5:4 A#5:4 B5:4 D#6:4 |"
    solo = ("E5:2 G#5:2 B5:2 E6:2 D#6:2 B5:2 G#5:4 | F#5:2 B5:2 D#6:2 F#6:2 E6:2 D#6:2 B5:4 |"
            " G#5:2 C#6:2 E6:2 G#6:2 F#6:2 E6:2 C#6:4 | A5:2 C#6:2 E6:2 A6:2 G#6:4 E6:4 |"
            " B6:1 G#6:1 E6:1 B5:1 B6:1 G#6:1 E6:1 B5:1 E6:8 | B6:1 F#6:1 D#6:1 B5:1 B6:1 F#6:1 D#6:1 B5:1 F#6:8 |"
            " C#7:2 B6:2 G#6:2 E6:2 C#6:2 E6:2 G#6:4 | A6:4 G#6:2 F#6:2 E6:4 C#6:4 |")

    v_akk = "E | B | C#m | A | E | B | C#m | A"
    p_akk = "A | B | C#m | B | A | B | C#m | B"
    r_akk = "E | B | C#m | A | E | B | A | B"
    pp = Drums({"k": "X.....x.X.x.....", "s": "....X.......X...", "h": "x.x.x.x.x.x.x.x."},
               fill={"s": "....X...x.x.XXXX", "t": "..........x.....", "h": "x.x.x.x........."})
    skate = Drums({"k": "X...X...X...X...", "s": "..X...X...X...X.", "c": "x...x...x...x..."},
                  fill={"s": "X.X.X.X.XXXXXXXX", "c": "", "f": "........x.x.x.x."})
    halb = Drums({"k": "X.........X.....", "s": "........X.......", "h": "x...x...x...x..."},
                 fill={"s": "X.X.X.X.XXXXXXXX", "h": "", "k": "X...X...X...X..."}, crash=False)
    achtel = Akkorde("XxXxXxXxXxXxXxXx", lage=52, power=True, staerke=90, legato=0.65)
    offen = Akkorde("X-------X-------", lage=52, power=True, staerke=92)
    gedaempft = Akkorde("x.x.x.x.x.x.x.x.", lage=52, power=True, staerke=74, legato=0.35)
    bass8 = Bass("R.R.R.R.R.R.R.R.", unten=28, staerke=98, legato=0.7)
    bass16 = Bass("RRRRRRRRRRRRRRRR", unten=28, staerke=96, legato=0.6)

    L.abschnitt("Intro", v_akk, lead=hook, rhythm_l=achtel, rhythm_r=achtel, bass=bass8, drums=skate)
    L.abschnitt("Strophe", v_akk, wdh=2, lead=strophe, rhythm_l=gedaempft, bass=bass8, drums=pp)
    L.abschnitt("Vorrefrain", p_akk, lead=vor, rhythm_l=achtel, rhythm_r=offen, bass=bass8, drums=pp)
    L.abschnitt("Refrain", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "dur"),
                rhythm_l=achtel, rhythm_r=achtel, bass=bass16, drums=skate, klavier=Flaeche(64, 3, 60))
    L.abschnitt("Hook", v_akk, lead=hook, rhythm_l=achtel, rhythm_r=achtel, bass=bass8, drums=skate)
    L.abschnitt("Strophe 2", v_akk, lead=strophe, rhythm_l=gedaempft, rhythm_r=gedaempft, bass=bass8, drums=pp,
                klavier=Linie("r:16 | r:16 | r:16 | r:16 | B5:4 r:12 | A#5:4 r:12 | G#5:4 r:12 | E5:4 r:12 |",
                              staerke=62))
    L.abschnitt("Vorrefrain 2", p_akk, lead=vor, rhythm_l=achtel, rhythm_r=offen, bass=bass8, drums=pp)
    L.abschnitt("Refrain 2", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "dur"),
                rhythm_l=achtel, rhythm_r=achtel, bass=bass16, drums=skate, klavier=Flaeche(64, 3, 62))
    L.abschnitt("Brücke", "C#m | A | E | B | C#m | A | E | B", lead=bruecke, drums=halb,
                rhythm_l=Akkorde("X---------------", lage=52, power=True, staerke=76),
                bass=Bass("R-------R-------", unten=28, staerke=90),
                klavier=Akkorde("X.X.X.X.X.X.X.X.", lage=64, toene=3, staerke=58, legato=0.5))
    L.abschnitt("Solo", v_akk, lead=solo, rhythm_l=achtel, rhythm_r=achtel, bass=bass16, drums=skate)
    L.abschnitt("Refrain 3", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "dur"),
                rhythm_l=offen, rhythm_r=gedaempft, bass=bass8, drums=halb, klavier=Flaeche(64, 3, 66))
    L.abschnitt("Refrain 4", r_akk, lead=refrain, harmonie=diatonisch(refrain, -2, "E", "dur"),
                rhythm_l=achtel, rhythm_r=achtel, bass=bass16, drums=skate, klavier=Flaeche(64, 3, 70))
    L.abschnitt("Schluss", "E | B | A | E", lead="G#5:4 B5:4 E6:8 | F#6:8 D#6:8 | E6:4 C#6:4 A5:8 | E6:16 |",
                harmonie="E5:4 G#5:4 B5:8 | D#6:8 B5:8 | C#6:4 A5:4 E5:8 | B5:16 |", rhythm_l=offen,
                rhythm_r=offen, bass=Bass("R-------R-------", unten=28),
                drums=Drums({"k": "X...X...X...X...", "s": "....X.......X..."},
                            fill={"k": "X...............", "s": "X...............", "c": "X..............."}))
    return L
