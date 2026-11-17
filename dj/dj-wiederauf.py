#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple – nach einem Mixxx-Absturz weitermachen, wo die Musik war.

Der DJ-Helfer schreibt jede Sekunde /run/zynsimple-decks.json (Länge, Stelle, Play, Tempo beider Decks).
Nach einem Absturz sucht dieses Skript die Titel in der Mixxx-Bibliothek (über Länge + Tempo),
schreibt controllers/ZynSimple-Wiederauf.js (Stelle/Play für das Mapping) und gibt die Dateien aus,
die dj-sitzung.sh Mixxx beim Start mitgibt (Mixxx lädt sie in Deck A und B).
"""
import json
import os
import sqlite3
import sys
import time

DATEN = os.environ.get("ZS_DJ_DATEN") or os.path.expanduser("~")
MIXXX = os.path.join(DATEN, ".mixxx")
DB = os.path.join(MIXXX, "mixxxdb.sqlite")
DECKS = "/run/zynsimple-decks.json"
JS = os.path.join(MIXXX, "controllers", "ZynSimple-Wiederauf.js")


def pfad(dauer, bpm):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=3)
    try:
        rows = con.execute("SELECT t.location, l.bpm FROM library l JOIN track_locations t ON l.location = t.id "
                           "WHERE l.mixxx_deleted = 0 AND IFNULL(t.fs_deleted, 0) = 0 AND ABS(l.duration - ?) < 0.3",
                           (float(dauer),)).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if r[0] and os.path.exists(r[0])]
    if not rows:
        return None
    rows.sort(key=lambda r: abs((r[1] or 0) - (bpm or 0)))
    return rows[0][0]


def main():
    try:
        with open(DECKS) as f:
            d = json.load(f)
    except Exception:
        return
    if time.time() - d.get("zeit", 0) > 180:          # zu alt – nichts wiederherstellen
        return
    dateien, w = [], {}
    for nr in (1, 2):
        z = d.get(f"d{nr}")
        if not z:
            continue
        try:
            p = pfad(z["dauer"], z.get("bpm"))
        except Exception as e:
            print(f"Wiederaufnahme: Bibliothek nicht lesbar ({e})", file=sys.stderr)
            return
        if p:
            dateien.append(p)
            w[f"d{nr}"] = {"pos": z["pos"], "play": bool(z["play"])}
    if not dateien:
        return
    if "d1" not in w:                                   # nur Deck B hatte einen Titel: erst A, dann nach B klonen
        w["tausch"] = True
    with open(JS, "w", encoding="utf-8") as f:
        f.write("var ZynSimpleWiederauf = " + json.dumps(w) + ";\n")
    for p in dateien:
        print(p)


if __name__ == "__main__":
    main()
