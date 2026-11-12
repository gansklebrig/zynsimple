#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: Tempo (BPM) und Tonart aller Titel im Hintergrund ermitteln.

Sucht in der Mixxx-Bibliothek Titel ohne BPM oder ohne Tonart, hört sich je Titel 90 Sekunden aus der Mitte an
und trägt die Werte in die Bibliothek ein – nur was fehlt (Werte aus den Dateiangaben bleiben unangetastet).
Mixxx verfeinert das Tempo beim ersten Laden ins Deck ohnehin noch mit seinem Beatgrid.

Rücksicht: niedrigste Priorität, schreibt nur, solange Mixxx nicht läuft (DJ-Pult / DJ + Instrumente aus),
und pausiert auch auf der Barden-Beats-Bühne. Abschaltbar: Einstellungen → DJ-Pult → „Titel automatisch analysieren“.
Status: /tmp/zynsimple-analyse.json
"""
import json
import os
import sqlite3
import subprocess
import sys
import time

import numpy as np

DATEN = "/zynthian/zynthian-my-data/dj"
DB = os.path.join(DATEN, ".mixxx", "mixxxdb.sqlite")
ZS_JSON = "/zynthian/zynthian-my-data/zynsimple/zynsimple.json"
STATUS = "/tmp/zynsimple-analyse.json"
GEMERKT = os.path.join(DATEN, ".analyse-erledigt.json")
SR = 11025

TON = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
# Krumhansl-Kessler-Profile
DUR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MOLL = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

status = {"aktiv": True, "pause": False, "offen": 0, "fertig": 0, "aktuell": "", "t": 0}


def schreiben(**kw):
    status.update(kw)
    status["t"] = int(time.time())
    try:
        with open(STATUS + ".neu", "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False)
        os.replace(STATUS + ".neu", STATUS)
    except OSError:
        pass


def einstellung_an():
    try:
        with open(ZS_JSON, encoding="utf-8") as f:
            return bool(json.load(f).get("dj_analyse", True))
    except Exception:
        return True


def besetzt():
    """Mixxx läuft (dann gehört ihm die Bibliothek) oder es wird gerade gespielt → warten."""
    for d in ("zynsimple-dj", "imres-buehne"):
        if subprocess.call(["systemctl", "is-active", "-q", d]) == 0:
            return True
    return subprocess.call(["pgrep", "-x", "mixxx"], stdout=subprocess.DEVNULL) == 0


def gemerkt():
    try:
        with open(GEMERKT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def merken(d):
    try:
        with open(GEMERKT + ".neu", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(GEMERKT + ".neu", GEMERKT)
    except OSError:
        pass


# ---------------------------------------------------------------------------------------------
# Hören
# ---------------------------------------------------------------------------------------------
def laden(pfad, dauer):
    """90 s Mono aus der Mitte des Titels (Intro/Outro sind oft ohne Bass und Tonart)."""
    start = max(0.0, min(60.0, (dauer or 0) / 2 - 45)) if dauer and dauer > 100 else 0.0
    for ss in (start, 0.0):
        r = subprocess.run(["nice", "-n", "19", "ffmpeg", "-v", "error", "-nostdin", "-ss", str(ss), "-t", "90", "-i", pfad,
                            "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, timeout=180)
        x = np.frombuffer(r.stdout, dtype=np.float32)
        if len(x) > SR * 10:
            return x
    return None


def tempo(x):
    """Tempo aus der Autokorrelation der Einsatz-Hüllkurve (spektraler Fluss), 60–190 BPM, Vorliebe um 122."""
    n, hop = 1024, 128
    fenster = np.hanning(n).astype(np.float32)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spek = np.log1p(30 * np.abs(np.fft.rfft(x[idx] * fenster, axis=1)))
    fluss = np.maximum(0, np.diff(spek, axis=0)).sum(axis=1)
    fluss -= np.convolve(fluss, np.ones(16) / 16, mode="same")
    fluss = np.maximum(fluss, 0)
    fluss -= fluss.mean()
    fps = SR / hop
    ak = np.correlate(fluss, fluss, mode="full")[len(fluss) - 1:]
    lags = np.arange(len(ak))
    with np.errstate(divide="ignore"):
        bpm = 60 * fps / lags
    gut = (bpm >= 60) & (bpm <= 190)
    gewicht = np.exp(-0.5 * (np.log2(np.where(gut, bpm, 1) / 122.0) / 0.9) ** 2)
    wert = np.where(gut, ak * gewicht, -np.inf)
    i = int(np.argmax(wert))
    if 1 <= i < len(ak) - 1:                      # Spitze verfeinern
        a, b, c = ak[i - 1], ak[i], ak[i + 1]
        d = (a - c) / (2 * (a - 2 * b + c)) if (a - 2 * b + c) != 0 else 0
        i = i + max(-0.5, min(0.5, d))
    if i <= 0:
        return None
    b = 60 * fps / i
    return round(float(b), 1) if 60 <= b <= 190 else None


def tonart(x):
    """Tonart aus dem Chroma (Energie je Halbton, 55 Hz – 2 kHz) gegen die Krumhansl-Profile. → (ton 0–11, moll?)"""
    n, hop = 8192, 4096
    fenster = np.hanning(n).astype(np.float32)
    frames = 1 + (len(x) - n) // hop
    if frames < 4:
        return None
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    mag = np.abs(np.fft.rfft(x[idx] * fenster, axis=1))
    f = np.fft.rfftfreq(n, 1 / SR)
    nutz = (f >= 55) & (f <= 2000)
    midi = 69 + 12 * np.log2(f[nutz] / 440.0)
    klasse = np.round(midi).astype(int) % 12
    nah = np.abs(midi - np.round(midi)) < 0.35       # nur Energie nahe am Halbton
    m = mag[:, nutz][:, nah]
    m = m / (m.sum(axis=1, keepdims=True) + 1e-9)    # jeder Moment zählt gleich
    chroma = np.zeros(12)
    # tiefe Töne (Bass, bis ~260 Hz) zählen doppelt: der Grundton liegt meist im Bass – trennt Moll von Paralleldur
    w = np.where(f[nutz][nah] < 260, 2.0, 1.0)
    np.add.at(chroma, klasse[nah], m.sum(axis=0) * w)
    if chroma.sum() <= 0:
        return None
    best, wahl = -2.0, None
    for t in range(12):
        for moll, prof in ((False, DUR), (True, MOLL)):
            r = np.corrcoef(chroma, np.roll(prof, t))[0, 1]
            if r > best:
                best, wahl = r, (t, moll)
    return wahl


# ---------------------------------------------------------------------------------------------
def offene(con, erledigt):
    rows = con.execute(
        "SELECT l.id, t.location, l.duration, l.bpm, l.key_id FROM library l JOIN track_locations t ON l.location = t.id "
        "WHERE l.mixxx_deleted = 0 AND t.fs_deleted = 0 AND (IFNULL(l.bpm, 0) < 1 OR IFNULL(l.key_id, 0) = 0) "
        "ORDER BY l.datetime_added DESC").fetchall()
    out = []
    for tid, pfad, dauer, bpm, key_id in rows:
        try:
            st = os.stat(pfad)
        except OSError:
            continue
        if erledigt.get(pfad) == f"{st.st_size}|{int(st.st_mtime)}":
            continue                      # schon versucht (nichts Brauchbares gefunden)
        out.append((tid, pfad, dauer, bpm, key_id, f"{st.st_size}|{int(st.st_mtime)}"))
    return out


def eintragen(tid, bpm_neu, ton):
    con = sqlite3.connect(DB, timeout=10)
    try:
        if bpm_neu:
            con.execute("UPDATE library SET bpm = ? WHERE id = ? AND IFNULL(bpm, 0) < 1", (bpm_neu, tid))
        if ton:
            t, moll = ton
            con.execute("UPDATE library SET key_id = ?, key = ? WHERE id = ? AND IFNULL(key_id, 0) = 0",
                        (t + 13 if moll else t + 1, TON[t] + ("m" if moll else ""), tid))
        con.commit()
    finally:
        con.close()


def main():
    if "--datei" in sys.argv:                   # zum Ausprobieren: analyse-arbeiter.py --datei titel.mp3
        x = laden(sys.argv[sys.argv.index("--datei") + 1], 0)
        t = tonart(x)
        print("BPM", tempo(x), "Tonart", (TON[t[0]] + ("m" if t[1] else "")) if t else None)
        return
    erledigt = gemerkt()
    fertig = 0
    while True:
        if not einstellung_an():
            schreiben(aktiv=False, pause=False, aktuell="")
            time.sleep(60)
            continue
        if not os.path.exists(DB) or besetzt():
            schreiben(aktiv=True, pause=True, aktuell="")
            time.sleep(30)
            continue
        try:
            con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
            liste = offene(con, erledigt)
            con.close()
        except Exception as e:
            schreiben(fehler=str(e))
            time.sleep(120)
            continue
        schreiben(aktiv=True, pause=False, offen=len(liste), fertig=fertig, aktuell="")
        if not liste:
            time.sleep(300)
            continue
        tid, pfad, dauer, bpm, key_id, sig = liste[0]
        schreiben(aktuell=os.path.basename(pfad))
        try:
            x = laden(pfad, dauer)
            b = tempo(x) if x is not None and not (bpm and bpm >= 1) else None
            t = tonart(x) if x is not None and not key_id else None
        except Exception:
            x, b, t = None, None, None
        if besetzt():                           # Mixxx ist inzwischen gestartet → später nochmal
            continue
        try:
            if b or t:
                eintragen(tid, b, t)
                fertig += 1
        except Exception as e:
            schreiben(fehler=str(e))
            time.sleep(60)
            continue
        # was sich nicht bestimmen ließ, nicht endlos wiederholen
        if (not (bpm and bpm >= 1) and not b) or (not key_id and not t):
            erledigt[pfad] = sig
            merken(erledigt)
        time.sleep(1)


if __name__ == "__main__":
    main()
