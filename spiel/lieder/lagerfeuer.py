# -*- coding: utf-8 -*-
"""Lagerfeuer am Isarufer – gemütlicher Akustik-Song in G-Dur, Mundharmonika im Zwischenspiel."""
from komponist import Lied, Drums, Bass, Akkorde, Flaeche, Arp


def lied():
    L = Lied("lagerfeuer", "Lagerfeuer am Isarufer", "Gemütlich · Akustik", 96, "G", "lagerfeuer",
             "gemütlich · zum Warmwerden", tonleiter="dur", schwierigkeit=1, farbe="#f2a33a", seed=3)
    L.vorschau = "Refrain"
    L.spur("lead", 25, 0, vol=110, pan=70, hall=55)
    L.spur("bass", 32, 1, vol=100, pan=60, hall=20)
    L.spur("strum", 25, 2, vol=78, pan=28, hall=40)
    L.spur("zupf", 24, 3, vol=70, pan=100, hall=50)
    L.spur("mundharmonika", 22, 4, vol=84, pan=80, hall=60)
    L.spur("orgel", 19, 5, vol=44, pan=64, hall=80)
    L.spur("drums", 40, 9, vol=92, hall=40)

    intro = ("D5:2 B4:2 G4:2 B4:2 D5:8 | A4:2 F#4:2 D4:2 F#4:2 A4:8 | B4:2 G4:2 E4:2 G4:2 B4:8 |"
             " C5:4 B4:4 A4:4 G4:4 |")
    strophe = ("B4:4 B4:2 A4:2 G4:4 A4:2 B4:2 | A4:6 F#4:2 D4:8 | E4:2 G4:2 B4:4 B4:2 C5:2 B4:2 A4:2 |"
               " G4:12 r:4 | B4:4 B4:2 C5:2 D5:4 B4:2 G4:2 | A4:6 B4:2 A4:4 F#4:4 |"
               " E4:2 G4:2 C5:4 B4:2 A4:2 G4:4 | A4:12 r:4 |")
    refrain = ("E5:4 E5:2 D5:2 C5:4 G4:4 | D5:6 B4:2 G4:8 | F#5:4 F#5:2 E5:2 D5:4 A4:4 | E5:6 D5:2 B4:8 |"
               " E5:4 E5:2 D5:2 C5:4 E5:4 | D5:4 B4:4 G4:4 B4:4 | A4:4 B4:2 C5:2 D5:4 F#4:4 | G4:12 r:4 |")
    bruecke = ("G4:4 B4:4 E5:8 | E5:4 D5:2 C5:2 G4:8 | B4:4 D5:4 G5:8 | F#5:6 E5:2 D5:8 |"
               " E5:4 F#5:2 G5:2 B5:8 | G5:4 E5:4 C5:8 | C5:4 B4:2 A4:2 E5:8 | D5:4 C5:2 B4:2 A4:8 |")

    strum = Akkorde("D---D-U---U-D-U-", lage=58, toene=4, staerke=74, strum=18, legato=0.95)
    strum_leise = Akkorde("D-------D-------", lage=58, toene=4, staerke=64, strum=22)
    zupf = Arp("1-3-2-3-4-3-2-3-", lage=55, staerke=60)
    bass = Bass("R-----5-R-----5-", unten=31, staerke=92)
    bass_lauf = Bass("R---5---R---5-b-", unten=31, staerke=92)
    schlag = Drums({"k": "X.......o.......", "x": "....x.......x...", "z": "xoxoxoxoxoxoxoxo"},
                   fill={"k": "X.......o.......", "x": "....x.......x.x.", "z": "xoxoxoxoxoxoxoxo"}, crash=False)
    schlag_voll = Drums({"k": "X.....o.X.......", "s": "....x.......x...", "z": "xoxoxoxoxoxoxoxo",
                         "w": "....x.......x..."}, fill={"s": "....x.......xoxx", "k": "X.....o.X.......",
                                                       "z": "xoxoxoxoxoxoxoxo"}, crash=False)

    L.abschnitt("Intro", "G | D/F# | Em | C", lead=intro, zupf=zupf, bass=Bass("R---------------", unten=31))
    L.abschnitt("Strophe", "G | D/F# | Em | C | G | D | C | D", lead=strophe, strum=strum_leise, zupf=zupf,
                bass=bass, drums=schlag)
    L.abschnitt("Refrain", "C | G | D | Em | C | G | D | G", lead=refrain, strum=strum, zupf=zupf, bass=bass_lauf,
                drums=schlag_voll, orgel=Flaeche(60, 3, 60))
    L.abschnitt("Zwischenspiel", "C | G | D | G", lead=intro,
                mundharmonika="E5:4 E5:2 D5:2 C5:4 G4:4 | D5:6 B4:2 G4:8 | F#5:4 E5:2 D5:2 A4:8 | G4:12 r:4 |",
                strum=strum, bass=bass, drums=schlag)
    L.abschnitt("Strophe 2", "G | D/F# | Em | C | G | D | C | D", lead=strophe, strum=strum, zupf=zupf,
                bass=bass_lauf, drums=schlag, mundharmonika="r:16 | r:16 | r:16 | r:8 E5:4 D5:4 | r:16 | r:16 |"
                " r:16 | r:8 F#5:4 A5:4 |")
    L.abschnitt("Refrain 2", "C | G | D | Em | C | G | D | G", lead=refrain, strum=strum, zupf=zupf, bass=bass_lauf,
                drums=schlag_voll, orgel=Flaeche(60, 3, 64))
    L.abschnitt("Brücke", "Em | C | G | D | Em | C | Am | D", lead=bruecke, strum=strum_leise,
                zupf=Arp("1-2-3-4-3-2-1-2-", lage=55, staerke=62), bass=Bass("R-------5-------", unten=31),
                drums=Drums({"z": "x.o.x.o.x.o.x.o.", "k": "X..............."}, crash=False),
                orgel=Flaeche(62, 4, 56))
    L.abschnitt("Refrain 3", "C | G | D | Em | C | G | D | G", lead=refrain, strum=strum, zupf=zupf,
                bass=bass_lauf, drums=schlag_voll, orgel=Flaeche(60, 3, 68),
                mundharmonika="r:16 | r:8 B4:4 D5:4 | r:16 | r:8 G5:4 B4:4 | r:16 | r:8 B4:4 D5:4 | r:16 | r:16 |")
    L.abschnitt("Ausklang", "G | C | G D | G", lead="B4:8 D5:8 | E5:8 C5:8 | B4:8 A4:8 | G4:16 |",
                strum=Akkorde("D-------D-------", lage=58, toene=4, staerke=60, strum=30), zupf=zupf,
                bass=Bass("R-------R-------", unten=31), mundharmonika="r:16 | r:16 | r:16 | G4+B4:16? |")
    return L
