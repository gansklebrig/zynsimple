# -*- coding: utf-8 -*-
"""
Bard Hero – eingebauter Not-Synthesizer.

Springt ein, wenn FluidSynth oder ein General-MIDI-Soundfont fehlt. Klingt schlicht (Sägezahn, Rechteck,
Sinus, Rausch-Schlagzeug), aber jedes Lied ist spielbar.
"""
import numpy as np

import komponist


def _familie(programm):
    if programm < 8:
        return "klavier"
    if programm < 16:
        return "glocke"
    if programm < 24:
        return "orgel"
    if programm < 32:
        return "gitarre"
    if programm < 40:
        return "bass"
    if programm < 56:
        return "flaeche"
    if programm < 80:
        return "blaeser"
    if programm < 88:
        return "lead"
    if programm < 104:
        return "flaeche"
    return "glocke"


def _ton(familie, freq, dauer, rate, staerke):
    n = int((dauer + 0.25) * rate)
    t = np.arange(n, dtype=np.float32) / rate
    ph = 2 * np.pi * freq * t
    if familie in ("lead", "gitarre"):
        x = 2 * ((freq * t) % 1.0) - 1                                   # Sägezahn
        x = np.convolve(x, np.ones(4) / 4, mode="same")
    elif familie == "blaeser":
        x = np.sign(np.sin(ph)) * 0.5 + 0.5 * np.sin(ph)
    elif familie == "bass":
        x = np.sin(ph) + 0.3 * np.sin(2 * ph)
    elif familie == "orgel":
        x = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)
    elif familie == "glocke":
        x = np.sin(ph) + 0.4 * np.sin(2.76 * ph)
    else:
        x = np.sin(ph) + 0.3 * np.sin(2 * ph + 0.3)
    a = int(0.005 * rate) if familie not in ("flaeche",) else int(0.12 * rate)
    huelle = np.ones(n, np.float32)
    huelle[:a] = np.linspace(0, 1, a)
    abkl = {"klavier": 1.2, "glocke": 0.8, "gitarre": 1.5}.get(familie)
    if abkl:
        huelle *= np.exp(-t / abkl)
    ende = int(dauer * rate)
    huelle[ende:] *= np.exp(-(t[ende:] - dauer) / 0.06)
    return (x * huelle * (staerke / 127.0) * 0.18).astype(np.float32)


def _drum(note, rate, staerke):
    z = np.random.default_rng(note)
    if note in (35, 36):
        n = int(0.3 * rate)
        t = np.arange(n) / rate
        x = np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 12)
    elif note in (38, 40, 37, 39):
        n = int(0.2 * rate)
        t = np.arange(n) / rate
        x = (0.6 * z.standard_normal(n) + 0.4 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 22)
    elif note in (42, 44, 46, 70, 69, 54):
        n = int((0.25 if note == 46 else 0.06) * rate)
        t = np.arange(n) / rate
        x = np.diff(z.standard_normal(n + 1)) * np.exp(-t * (12 if note == 46 else 60)) * 0.5
    elif note in (49, 57, 51, 52, 55, 53):
        n = int(0.9 * rate)
        t = np.arange(n) / rate
        x = np.diff(z.standard_normal(n + 1)) * np.exp(-t * 4) * 0.4
    else:
        n = int(0.3 * rate)
        t = np.arange(n) / rate
        f = 80 + (note - 41) * 12
        x = np.sin(2 * np.pi * f * t) * np.exp(-t * 10)
    return (x * (staerke / 127.0) * 0.35).astype(np.float32)


def rendern(lied, teil, rate):
    laenge = int(lied.laenge_s() * rate) + rate
    out = np.zeros((laenge, 2), np.float32)
    for name, sp in lied.spuren.items():
        if teil == "lead" and name != lied.lead or teil == "bass" and name != lied.bass:
            continue
        if teil == "band" and name in (lied.lead, lied.bass):
            continue
        fam = _familie(sp.programm)
        pan = sp.pan / 127.0
        lr = np.array([np.cos(pan * np.pi / 2), np.sin(pan * np.pi / 2)], np.float32) * (sp.vol / 127.0)
        cache = {}
        for t, d, n, s in sp.noten:
            start = int(lied.sekunden(t) * rate)
            if sp.kanal == 9:
                key = ("d", n, s // 16)
                if key not in cache:
                    cache[key] = _drum(n, rate, s)
                x = cache[key]
            else:
                dauer = lied.sekunden(d)
                key = (n, round(dauer, 2), s // 16)
                if key not in cache:
                    cache[key] = _ton(fam, 440.0 * 2 ** ((n - 69) / 12), dauer, rate, s)
                x = cache[key]
            ende = min(laenge, start + len(x))
            if ende > start:
                out[start:ende] += x[:ende - start, None] * lr
    _ = komponist
    return out
