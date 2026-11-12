# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult – Musik am Handy suchen und ins Deck laden.

Gesucht wird direkt in der Mixxx-Bibliothek (nur lesend, Mixxx darf dabei laufen).
Laden: der Titel wird in Mixxx' Suchfeld getippt und dann über das Mapping „Zynthian V5 (ZynSimple)“
ins Deck geladen (CC 112 = Bereich wählen, CC 113 = Deck 1/2). Genutzt von dj-web.py (DJ-Modus)
und von ZynSimple selbst (Hybrid-Modus).
"""
import os
import re
import sqlite3
import subprocess
import time

DATEN = "/zynthian/zynthian-my-data/dj"
DB = os.path.join(DATEN, ".mixxx", "mixxxdb.sqlite")
TONARTEN = ["", "C", "D♭", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "H",
            "Cm", "C♯m", "Dm", "E♭m", "Em", "Fm", "F♯m", "Gm", "G♯m", "Am", "B♭m", "Hm"]


def _db():
    if not os.path.exists(DB):
        raise RuntimeError("Noch keine Bibliothek – das DJ-Pult einmal starten, dann ist sie da")
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=3)


def woerter(text):
    """Suchwörter ohne Zeichen, die Mixxx' Suche anders versteht (- am Anfang, „:“, Anführungszeichen)."""
    return [w for w in re.findall(r"[^\W_]+(?:'[^\W_]+)?", str(text or ""), re.U) if w][:8]


def suche(q="", favoriten=False, limit=60, sortierung="sterne", buchstabe=None, start=0):
    """sortierung: „sterne“ (Favoriten zuerst), „neu“ (zuletzt dazugekommen), „az“ (Künstler A–Z).
    buchstabe: nur Künstler (bzw. Titel ohne Künstler), die mit diesem Buchstaben beginnen („#“ = Ziffern/Zeichen)."""
    w = woerter(q)
    wo = " WHERE l.mixxx_deleted = 0 AND IFNULL(t.fs_deleted, 0) = 0"
    args = []
    for x in w:
        wo += (" AND (IFNULL(l.artist,'') || ' ' || IFNULL(l.title,'') || ' ' || IFNULL(l.album,'') || ' ' || "
               "IFNULL(t.filename,'')) LIKE ?")
        args.append(f"%{x}%")
    if favoriten:
        wo += " AND l.rating >= 4"
    name = "UPPER(COALESCE(NULLIF(TRIM(l.artist),''), NULLIF(TRIM(l.title),''), t.filename))"
    if buchstabe == "#":
        wo += f" AND SUBSTR({name}, 1, 1) NOT BETWEEN 'A' AND 'Z'"
    elif buchstabe:
        wo += f" AND SUBSTR({name}, 1, 1) = ?"
        args.append(str(buchstabe)[:1].upper())
    ordnung = {"neu": "l.datetime_added DESC, l.id DESC",
               "az": f"{name}, l.album COLLATE NOCASE, l.tracknumber, l.title COLLATE NOCASE"}.get(
        sortierung, "l.rating DESC, l.artist COLLATE NOCASE, l.title COLLATE NOCASE")
    von = " FROM library l JOIN track_locations t ON l.location = t.id"
    sql = ("SELECT l.id, l.artist, l.title, l.bpm, l.key_id, l.key, l.rating, l.duration, t.filename" + von + wo +
           f" ORDER BY {ordnung} LIMIT ? OFFSET ?")
    con = _db()
    try:
        try:
            rows = con.execute(sql, args + [int(limit), int(start)]).fetchall()
        except sqlite3.OperationalError:          # ältere Bibliothek ohne Spalte (tracknumber/datetime_added)
            sql = sql.replace(", l.tracknumber", "").replace("l.datetime_added DESC, ", "")
            rows = con.execute(sql, args + [int(limit), int(start)]).fetchall()
        treffer = con.execute("SELECT COUNT(*)" + von + wo, args).fetchone()[0]
        gesamt = con.execute("SELECT COUNT(*) FROM library WHERE mixxx_deleted = 0").fetchone()[0]
    finally:
        con.close()
    out = []
    for tid, artist, title, bpm, key_id, key, rating, dauer, datei in rows:
        if not title:
            title = os.path.splitext(datei or "")[0]
        ton = TONARTEN[key_id] if isinstance(key_id, int) and 0 < key_id < len(TONARTEN) else (key or "")
        out.append({"id": tid, "artist": artist or "", "title": title or "", "bpm": round(bpm or 0, 1),
                    "tonart": ton, "sterne": int(rating or 0), "dauer": int(dauer or 0)})
    return {"titel": out, "gesamt": gesamt, "treffer": treffer}


def finde(dauer, bpm=0):
    """Welcher Titel ist das? (Mixxx verrät dem Mapping keine Namen – Länge und Tempo reichen meist.)"""
    if not dauer:
        return None
    con = _db()
    try:
        rows = con.execute("SELECT l.id, l.artist, l.title, t.filename, l.bpm FROM library l JOIN track_locations t "
                           "ON l.location = t.id WHERE l.mixxx_deleted = 0 AND ABS(l.duration - ?) < 0.8",
                           (float(dauer),)).fetchall()
    finally:
        con.close()
    if not rows:
        return None
    if len(rows) > 1 and bpm:
        rows.sort(key=lambda r: abs((r[4] or 0) - bpm))
    tid, artist, title, datei, _ = rows[0]
    return {"id": tid, "artist": artist or "", "title": title or os.path.splitext(datei or "")[0]}


def _x_env():
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    xa = os.path.join(DATEN, ".Xauthority")
    if "XAUTHORITY" not in env and os.path.exists(xa):
        env["XAUTHORITY"] = xa
    return env


def _x_fenster():
    try:
        out = subprocess.run(["xdotool", "search", "--class", "mixxx"], env=_x_env(), capture_output=True,
                             text=True, timeout=4).stdout.split()
    except Exception:
        out = []
    return out[-1:]          # das Hauptfenster ist das zuletzt angelegte


def _xdo(*args):
    try:
        return subprocess.call(["xdotool"] + list(args), env=_x_env(), stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=4)
    except subprocess.TimeoutExpired:
        return 1


def laden(track_id, deck, senden):
    """Titel ins Deck 1 (A) oder 2 (B) laden. senden(cc, wert) schickt einen Befehl an das Mixxx-Mapping."""
    deck = 2 if int(deck) == 2 else 1
    con = _db()
    try:
        r = con.execute("SELECT l.artist, l.title, t.filename FROM library l JOIN track_locations t "
                        "ON l.location = t.id WHERE l.id = ?", (int(track_id),)).fetchone()
    finally:
        con.close()
    if not r:
        raise RuntimeError("Titel nicht (mehr) in der Bibliothek")
    artist, title, datei = r
    such = " ".join(woerter(f"{artist or ''} {title or ''}") or woerter(os.path.splitext(datei or "")[0]))
    if not such:
        raise RuntimeError("Titel hat keinen Namen, nach dem Mixxx suchen kann")
    if subprocess.call(["which", "xdotool"], stdout=subprocess.DEVNULL) != 0:
        raise RuntimeError("xdotool fehlt – DJ-Pult einmal über die Einstellungen neu einrichten")
    # Ohne Fenstermanager gibt es kein „aktivieren“ – Mixxx-Fenster nach vorne holen und Tastatur-Fokus geben
    for w in _x_fenster():
        _xdo("windowmap", w)
        _xdo("windowraise", w)
        _xdo("windowfocus", w)
    time.sleep(0.2)
    senden(112, 1)                     # Suchfeld
    time.sleep(0.25)
    _xdo("key", "--clearmodifiers", "ctrl+a")
    _xdo("type", "--delay", "8", such)
    time.sleep(1.0)                    # Mixxx filtert mit kurzer Verzögerung
    senden(113, deck)                  # erster Treffer → Deck
    time.sleep(0.8)
    # Suche wieder leeren, damit die Bibliothek wie vorher aussieht
    senden(112, 1)
    time.sleep(0.2)
    _xdo("key", "--clearmodifiers", "ctrl+a", "BackSpace")
    senden(112, 3)
    name = f"{artist} – {title}" if artist else (title or datei)
    return f"„{name}“ → Deck {'A' if deck == 1 else 'B'}"
