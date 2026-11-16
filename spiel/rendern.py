#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bard Hero – Lieder rendern.

Für jedes Lied entstehen im Datenordner  lieder/<id>/ :
  band.wav   alles außer Melodie und Bass        lead.wav   die Spiel-Melodie
  bass.wav   der Bass (Duett: Spieler 2)          vorschau.wav   20 s für die Liedauswahl
  chart.json Noten, Abschnitte, Tempo
Gerendert wird mit FluidSynth und einem General-MIDI-Soundfont. Fehlt beides, springt ein einfacher
eingebauter Synthesizer ein (klingt schlichter, aber das Spiel läuft).

Aufruf:  rendern.py [--neu] [--rate 48000] [lied-id …]      Fortschritt: Zeilen „LIED i n id titel“, „FERTIG“
Ein Lied wird nur neu gerendert, wenn sich seine Noten, der Soundfont oder die Rate geändert haben.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import wave

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HIER, os.path.join(HIER, "lieder")]
DATEN = os.environ.get("BH_DATEN", "/zynthian/zynthian-my-data/bardhero")
VERSION = "3"            # erhöhen, wenn sich die Art des Renderns ändert

import numpy as np  # noqa: E402

import lieder  # noqa: E402


def soundfont():
    if os.environ.get("BH_SF2") and os.path.isfile(os.environ["BH_SF2"]):
        return os.environ["BH_SF2"]
    ordner = ["/zynthian/zynthian-my-data/soundfonts/sf2", "/zynthian/zynthian-data/soundfonts/sf2",
              "/usr/share/sounds/sf2", "/usr/share/sounds/sf3", "/usr/share/soundfonts"]
    for name in ("FluidR3_GM.sf2", "FluidR3_GM_GS.sf2", "GeneralUser GS v1.471.sf2", "GeneralUser_GS.sf2",
                 "FluidR3_GM.sf3", "default-GM.sf2", "default-GM.sf3"):
        for o in ordner:
            p = os.path.join(o, name)
            if os.path.isfile(p):
                return os.path.realpath(p)
    for o in ordner:
        for p in sorted(glob.glob(os.path.join(o, "*.sf[23]"))):
            if "gm" in os.path.basename(p).lower() or "general" in os.path.basename(p).lower():
                return p
    return None


def fluidsynth():
    return shutil.which("fluidsynth")


def _fingerabdruck(lied, sf2, rate):
    h = hashlib.sha1()
    h.update(VERSION.encode())
    h.update(str(rate).encode())
    h.update((sf2 or "ersatz").encode())
    h.update(lied.midi("alle"))
    return h.hexdigest()


def _wav_lesen(p):
    with wave.open(p) as w:
        n = w.getnframes()
        ch = w.getnchannels()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    return a.reshape(-1, ch) if ch > 1 else np.repeat(a[:, None], 2, axis=1)


def _wav_schreiben(p, a, rate, mono=False):
    a = np.clip(a, -1.0, 1.0)
    if mono:
        a = a.mean(axis=1)
    with wave.open(p + ".teil", "wb") as w:
        w.setnchannels(1 if mono else 2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((a * 32767).astype("<i2").tobytes())
    os.replace(p + ".teil", p)


def _fluid(mid, wav, sf2, rate):
    cmd = [fluidsynth(), "-ni", "-q", "-g", "0.32", "-r", str(rate), "-o", "synth.cpu-cores=4",
           "-F", wav, "-T", "wav", "-O", "s16", sf2, mid]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=900)
    if r.returncode != 0 or not os.path.isfile(wav) or os.path.getsize(wav) < 1000:
        raise RuntimeError("FluidSynth: " + r.stderr.decode(errors="replace")[-300:])


def rendern(lied, ziel, rate, sf2, melden=None):
    os.makedirs(ziel, exist_ok=True)
    stems = {}
    if sf2 and fluidsynth():
        for teil in ("band", "lead", "bass"):
            if melden:
                melden(teil)
            mid = os.path.join(ziel, teil + ".mid")
            with open(mid, "wb") as f:
                f.write(lied.midi(teil))
            roh = os.path.join(ziel, teil + ".roh.wav")
            _fluid(mid, roh, sf2, rate)
            stems[teil] = _wav_lesen(roh)
            os.remove(roh)
            os.remove(mid)
    else:
        import ersatz
        for teil in ("band", "lead", "bass"):
            if melden:
                melden(teil)
            stems[teil] = ersatz.rendern(lied, teil, rate)
    n = max(len(a) for a in stems.values())
    n = min(n, int(lied.laenge_s() * rate) + rate * 2)
    for k in stems:
        a = stems[k][:n]
        if len(a) < n:
            a = np.concatenate([a, np.zeros((n - len(a), 2), np.float32)])
        stems[k] = a
    # Mischung angleichen: Melodie gut hörbar (2 dB unter der Band), Bass 4 dB darunter
    def rms_db(a):
        b = a[::4]
        laut = np.abs(b).max(axis=1) > 0.003
        if not laut.any():
            return -90.0
        return 20 * np.log10(np.sqrt(np.mean(b[laut] ** 2)) + 1e-9)
    band_db = rms_db(stems["band"])
    for k, ziel_db in (("lead", band_db - 1.5), ("bass", band_db - 4.0)):
        g = 10 ** ((ziel_db - rms_db(stems[k])) / 20)
        stems[k] = stems[k] * float(min(4.0, max(0.25, g)))
    summe = stems["band"] + stems["lead"] + stems["bass"]
    spitze = float(np.abs(summe).max()) or 1.0
    # gleich laut über alle Lieder (≈ -16 dBFS), aber ohne Übersteuern
    faktor = min(10 ** ((-16 - rms_db(summe)) / 20), 0.97 / spitze)
    for k, a in stems.items():
        _wav_schreiben(os.path.join(ziel, k + ".wav"), a * faktor, rate, mono=(k == "bass"))
    # Vorschau: 20 s ab dem Refrain, mit Ein- und Ausblendung
    c = lied.chart()
    start = c.get("vorschau") or c["ende"] * 0.35
    a0 = int(start * rate)
    v = summe[a0:a0 + 20 * rate] * faktor
    blende = np.ones(len(v), np.float32)
    f = min(len(v) // 4, rate)
    if f:
        blende[:f] = np.linspace(0, 1, f)
        blende[-2 * f:] = np.linspace(1, 0, 2 * f)
    _wav_schreiben(os.path.join(ziel, "vorschau.wav"), v * blende[:, None], rate)
    c["rate"] = rate
    c["klang"] = os.path.basename(sf2) if sf2 and fluidsynth() else "eingebaut"
    with open(os.path.join(ziel, "chart.json.teil"), "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)
    os.replace(os.path.join(ziel, "chart.json.teil"), os.path.join(ziel, "chart.json"))


def offen(rate=48000, sf2=None, nur=None):
    """Welche Lieder müssen (neu) gerendert werden? → [(lied, ziel, fingerabdruck)]"""
    sf2 = sf2 if sf2 is not None else soundfont()
    raus = []
    for lied in lieder.alle():
        if nur and lied.id not in nur:
            continue
        ziel = os.path.join(DATEN, "lieder", lied.id)
        fp = _fingerabdruck(lied, sf2 if fluidsynth() else None, rate)
        try:
            with open(os.path.join(ziel, "fertig"), encoding="utf-8") as f:
                if f.read().strip() == fp and os.path.isfile(os.path.join(ziel, "chart.json")):
                    continue
        except OSError:
            pass
        raus.append((lied, ziel, fp))
    return raus


def alle(rate=48000, neu=False, nur=None, melden=print):
    sf2 = soundfont()
    liste = offen(rate, sf2, nur) if not neu else [
        (lied, os.path.join(DATEN, "lieder", lied.id), _fingerabdruck(lied, sf2 if fluidsynth() else None, rate))
        for lied in lieder.alle() if not nur or lied.id in nur]
    for i, (lied, ziel, fp) in enumerate(liste):
        melden(f"LIED {i + 1} {len(liste)} {lied.id} {lied.titel}")
        try:
            os.remove(os.path.join(ziel, "fertig"))
        except OSError:
            pass
        rendern(lied, ziel, rate, sf2, lambda t: melden(f"TEIL {t}"))
        with open(os.path.join(ziel, "fertig"), "w", encoding="utf-8") as f:
            f.write(fp)
    melden("FERTIG")
    return len(liste)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if "--soundfont" in args:
        print(soundfont() or "keiner")
        sys.exit(0)
    rate = 48000
    if "--rate" in args:
        i = args.index("--rate")
        rate = int(args[i + 1])
        del args[i:i + 2]
    neu = "--neu" in args
    args = [a for a in args if not a.startswith("--")]
    alle(rate, neu, args or None, lambda t: print(t, flush=True))
