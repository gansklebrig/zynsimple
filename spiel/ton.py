#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bard Hero – Ton-Maschine (eigener Prozess, damit das Bild den Ton nie stören kann).

  • spielt die Stems eines Liedes (Band, Melodie, Bass) sample-genau ab
  • schaltet Melodie/Bass stumm, wenn daneben gegriffen wird (wie bei Guitar Hero) – mit sanfter Blende
  • Mikrofon (Zynthian-Eingang 1, 2 oder beide) mit Pegel, Hall und „Ducking“ (Musik wird leiser beim Sprechen)
  • Effekt-Geräusche, Einzähl-Klicks, Vorschau in der Liedauswahl, Metronom zum Kalibrieren
  • liest MIDI über JACK – jedes Gerät auf eigenem Eingang, damit zwei Spieler unterscheidbar sind

Klang über JACK (Zynthian). Ohne JACK über SDL (pygame) – dann ohne getrennte MIDI-Geräte.

Steuerung:  JSON-Befehle per Datagramm an  /tmp/bardhero-ton.sock
Zustand:    /dev/shm/bardhero-ton  (Position, Pegel …, siehe ZUSTAND)
MIDI:       Datagramme „M <monotonic> <quelle> <hexbytes>“ an /tmp/bardhero-spiel.sock
"""
import collections
import json
import mmap
import os
import socket
import struct
import sys
import threading
import time
import wave

import numpy as np

STEUER = os.environ.get("BH_TON_SOCK", "/tmp/bardhero-ton.sock")
SPIEL = os.environ.get("BH_SPIEL_SOCK", "/tmp/bardhero-spiel.sock")
ZUSTAND_DATEI = os.environ.get("BH_TON_SHM", "/dev/shm/bardhero-ton" if os.path.isdir("/dev/shm") else "/tmp/bardhero-ton")
# Zähler, Liedzeit, monotonic dieser Liedzeit, spielt, geladen-Nr., Rate, Mikro-Spitze, Ausgang-Spitze,
# Latenz, Aussetzer, Backend (1=JACK, 2=SDL), Vorschau-läuft
ZUSTAND = struct.Struct("<Q d d i i i f f f i i i")


def log(*a):
    print("Ton:", *a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------------------------------------
# Geräusche (einmal beim Start berechnet)
# ---------------------------------------------------------------------------------------------------------
def geraeusche(rate):
    def t(sek):
        return np.arange(int(rate * sek), dtype=np.float32) / rate

    def huelle(x, a=0.002, r=0.1):
        n = len(x)
        e = np.ones(n, np.float32)
        na = max(1, int(a * rate))
        e[:na] = np.linspace(0, 1, na)
        e *= np.exp(-np.arange(n) / (r * rate)).astype(np.float32)
        return x * e

    z = np.random.default_rng(3)
    s = {}
    # daneben gegriffen: dumpfes, verstimmtes „Plonk“
    x = t(0.28)
    s["fehler"] = huelle(0.5 * np.sin(2 * np.pi * (110 + 40 * np.exp(-x * 30)) * x)
                         + 0.35 * np.sin(2 * np.pi * 117 * x) + 0.15 * z.standard_normal(len(x)).astype(np.float32)
                         * np.exp(-x * 60), r=0.09) * 0.55
    # Einzähl-Stöcke
    x = t(0.06)
    s["klick"] = huelle(z.standard_normal(len(x)).astype(np.float32) * 0.5 + np.sin(2 * np.pi * 2400 * x), r=0.012) * 0.5
    s["klick_hoch"] = huelle(z.standard_normal(len(x)).astype(np.float32) * 0.5 + np.sin(2 * np.pi * 3200 * x), r=0.014) * 0.6
    # Inspiration: aufsteigendes Rauschen mit Schimmer
    x = t(1.1)
    sweep = np.sin(2 * np.pi * np.cumsum(300 + 1800 * (x / x[-1]) ** 2) / rate)
    s["inspiration"] = (0.25 * sweep + 0.12 * z.standard_normal(len(x)).astype(np.float32) * (x / x[-1])) \
        * np.minimum(1, (x[-1] - x) * 6) * np.minimum(1, x * 3) * 0.7
    # Menü: kurzer Holzton
    x = t(0.09)
    s["menue"] = huelle(np.sin(2 * np.pi * 880 * x) + 0.4 * np.sin(2 * np.pi * 1320 * x), r=0.025) * 0.25
    s["ok"] = huelle(np.sin(2 * np.pi * 660 * x) + 0.5 * np.sin(2 * np.pi * 990 * x), r=0.05) * 0.3
    # Jubel: gefiltertes Rauschen, an- und abschwellend
    x = t(2.6)
    roh = z.standard_normal(len(x)).astype(np.float32)
    roh = np.convolve(roh, np.ones(6) / 6, mode="same").astype(np.float32)
    mod = 1 + 0.3 * np.sin(2 * np.pi * 7 * x) * np.sin(2 * np.pi * 0.7 * x)
    s["jubel"] = roh * mod * np.minimum(1, x * 2) * np.minimum(1, (x[-1] - x) * 1.2) * 0.22
    # Buh: tiefes Brummen
    x = t(1.6)
    s["buh"] = (np.sin(2 * np.pi * (95 + 8 * np.sin(2 * np.pi * 3 * x)) * x) * 0.3
                + 0.08 * z.standard_normal(len(x)).astype(np.float32)) * np.minimum(1, x * 4) * np.minimum(1, (x[-1] - x) * 2)
    return {k: v.astype(np.float32) for k, v in s.items()}


def wav_laden(pfad, rate):
    with wave.open(pfad) as w:
        ch = w.getnchannels()
        r = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, ch)
    if r != rate:
        # lineare Umrechnung (nur, wenn JACK mit einer anderen Rate läuft)
        n = int(len(a) * rate / r)
        idx = np.linspace(0, len(a) - 1, n)
        a = np.stack([np.interp(idx, np.arange(len(a)), a[:, c]) for c in range(ch)], axis=1).astype(np.int16)
    return np.ascontiguousarray(a)


# ---------------------------------------------------------------------------------------------------------
# Mischpult (läuft im Ton-Rückruf)
# ---------------------------------------------------------------------------------------------------------
class Mischer:
    HALL = (1557, 1617, 1491, 1422)

    def __init__(self, rate):
        self.rate = rate
        self.stems = {}
        self.laenge = 0
        self.pos = 0                    # Liedposition in Samples (negativ = Vorlauf)
        self.spielt = False
        self.geladen = 0
        self.pegel = {"master": 0.9, "musik": 1.0, "lead": 1.0, "bass": 1.0, "mic": 0.0, "hall": 0.25,
                      "ducking": 0.0, "sfx": 0.8, "mic_kanal": 1}
        self.gate = {"lead": 1.0, "bass": 1.0}
        self.gate_ist = {"lead": 1.0, "bass": 1.0}
        self.sfx = geraeusche(rate)
        self.aktiv = []                 # [array, pos, start_sample]
        self.klicks = []                # Liedzeiten in Samples
        self.vorschau = None
        self.vorschau_pos = 0
        self.vorschau_gain = 0.0
        self.duck = 1.0
        self.hall_puffer = [np.zeros(d, np.float32) for d in self.HALL]
        self.hall_idx = [0] * len(self.HALL)
        self.mic_spitze = 0.0
        self.aus_spitze = 0.0
        self.lock = threading.Lock()

    # -- Befehle (aus dem Steuer-Thread) --
    def laden(self, stems, nr, laenge_s=0.0):
        with self.lock:
            self.stems = stems
            self.laenge = max(len(a) for a in stems.values()) if stems else int(laenge_s * self.rate)
            self.pos = 0
            self.spielt = False
            self.geladen = nr

    def start(self, ab_s, klicks):
        with self.lock:
            self.pos = int(ab_s * self.rate)
            self.klicks = sorted(int(k * self.rate) for k in klicks)
            self.gate_ist = {"lead": 1.0, "bass": 1.0}
            self.gate = {"lead": 1.0, "bass": 1.0}
            self.spielt = True
            self.vorschau = None

    def geraeusch(self, name, lautstaerke=1.0):
        a = self.sfx.get(name)
        if a is not None:
            with self.lock:
                self.aktiv.append([a * lautstaerke, 0])
                self.aktiv = self.aktiv[-12:]

    # -- Hall (Kammfilter, blockweise; Verzögerung > Block) --
    def _hall(self, x):
        n = len(x)
        aus = np.zeros(n, np.float32)
        for k, d in enumerate(self.HALL):
            buf = self.hall_puffer[k]
            i = self.hall_idx[k]
            # gelesen wird, was vor d Samples hineinging
            if i + n <= d:
                alt = buf[i:i + n].copy()
            else:
                alt = np.concatenate([buf[i:], buf[:(i + n) - d]])
            neu = x + 0.78 * alt
            if i + n <= d:
                buf[i:i + n] = neu
            else:
                buf[i:] = neu[:d - i]
                buf[:(i + n) - d] = neu[d - i:]
            self.hall_idx[k] = (i + n) % d
            aus += alt
        return aus * 0.22

    def block(self, n, mic1=None, mic2=None):
        """n Samples Stereo (float32, Form (n, 2))."""
        out = np.zeros((n, 2), np.float32)
        p = self.pegel
        with self.lock:
            # --- Lied ---
            if self.spielt:
                a = self.pos
                b = a + n
                lo = max(a, 0)
                hi = min(b, self.laenge)
                if hi > lo:
                    o0 = lo - a
                    musik = p["musik"] * self.duck
                    for name, arr in self.stems.items():
                        if lo >= len(arr):
                            continue
                        h = min(hi, len(arr))
                        teil = arr[lo:h].astype(np.float32) * (1.0 / 32768)
                        if teil.shape[1] == 1:
                            teil = np.repeat(teil, 2, axis=1)
                        g = musik
                        if name in self.gate:
                            g *= p[name]
                            z0 = self.gate_ist[name]
                            z1 = self.gate[name]
                            if z0 != z1:
                                schritt = len(teil) / (0.012 * self.rate)        # 12 ms Blende
                                ziel = min(z1, z0 + schritt) if z1 > z0 else max(z1, z0 - schritt)
                                rampe = np.linspace(z0, ziel, len(teil), dtype=np.float32)[:, None]
                                self.gate_ist[name] = float(ziel)
                                out[o0:o0 + len(teil)] += teil * rampe * g
                                continue
                            g *= z0
                        if g:
                            out[o0:o0 + len(teil)] += teil * g
                # Einzähl-Klicks
                while self.klicks and self.klicks[0] < b:
                    k = self.klicks.pop(0)
                    if k >= a:
                        self.aktiv.append([self.sfx["klick"], -(k - a)])
                self.pos = b
                if self.pos > self.laenge + self.rate:
                    self.spielt = False
            # --- Vorschau ---
            if self.vorschau is not None:
                v = self.vorschau
                i = self.vorschau_pos
                teil = v[i:i + n]
                if len(teil) < n:
                    teil = np.concatenate([teil, v[:n - len(teil)]])
                    self.vorschau_pos = n - (len(v) - i)
                else:
                    self.vorschau_pos = i + n
                self.vorschau_gain = min(1.0, self.vorschau_gain + n / (0.4 * self.rate))
                out += teil.astype(np.float32) * (self.vorschau_gain * p["musik"] * 0.8 / 32768)
            # --- Geräusche ---
            if self.aktiv:
                rest = []
                for e in self.aktiv:
                    arr, ap = e
                    if ap < 0:                       # beginnt erst später in diesem Block
                        start = -ap
                        if start >= n:
                            e[1] = ap + n
                            rest.append(e)
                            continue
                        teil = arr[:n - start]
                        out[start:start + len(teil)] += teil[:, None] * p["sfx"]
                        e[1] = len(teil)
                    else:
                        teil = arr[ap:ap + n]
                        out[:len(teil)] += teil[:, None] * p["sfx"]
                        e[1] = ap + len(teil)
                    if e[1] < len(arr):
                        rest.append(e)
                self.aktiv = rest
        # --- Mikrofon ---
        mic = None
        k = p["mic_kanal"]
        if p["mic"] > 0 and k:
            if k == 1 and mic1 is not None:
                mic = mic1
            elif k == 2 and mic2 is not None:
                mic = mic2
            elif k == 3 and mic1 is not None and mic2 is not None:
                mic = (mic1 + mic2) * 0.5
        if mic is not None and len(mic) == n:
            m = mic * p["mic"]
            self.mic_spitze = max(self.mic_spitze * 0.9, float(np.abs(mic).max()))
            nass = self._hall(m) if p["hall"] > 0 else 0
            sig = m + (nass * p["hall"] * 2 if p["hall"] > 0 else 0)
            out += np.stack([sig, sig], axis=1)
            # Ducking: Musik leiser, solange gesprochen wird
            if p["ducking"] > 0:
                lautheit = float(np.sqrt(np.mean(mic * mic)))
                ziel = 1.0 - p["ducking"] * 0.65 if lautheit > 0.02 else 1.0
                faktor = 0.25 if ziel < self.duck else 0.03
                self.duck += (ziel - self.duck) * faktor
            else:
                self.duck = 1.0
        else:
            self.mic_spitze *= 0.9
            self.duck += (1.0 - self.duck) * 0.05
        out *= p["master"]
        np.clip(out, -1.0, 1.0, out=out)
        self.aus_spitze = max(self.aus_spitze * 0.92, float(np.abs(out).max()) if n else 0.0)
        return out


# ---------------------------------------------------------------------------------------------------------
# Zustand für das Spiel
# ---------------------------------------------------------------------------------------------------------
class Zustand:
    def __init__(self):
        with open(ZUSTAND_DATEI, "wb") as f:
            f.write(b"\0" * 4096)
        self.f = open(ZUSTAND_DATEI, "r+b")
        self.m = mmap.mmap(self.f.fileno(), 4096)
        self.zaehler = 0

    def schreiben(self, liedzeit, mono, spielt, geladen, rate, mic, aus, latenz, aussetzer, backend, vorschau):
        self.zaehler += 1
        self.m[0:ZUSTAND.size] = ZUSTAND.pack(self.zaehler, liedzeit, mono, spielt, geladen, rate, mic, aus,
                                              latenz, aussetzer, backend, vorschau)


# ---------------------------------------------------------------------------------------------------------
# Maschine
# ---------------------------------------------------------------------------------------------------------
class Maschine:
    def __init__(self):
        self.backend = 0
        self.rate = 48000
        self.latenz = 0.0
        self.aussetzer = 0
        self.mix = None
        self.zustand = Zustand()
        self.midi_raus = collections.deque(maxlen=512)
        self.sock_spiel = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.midi_ports = {}            # Portname → (eigener Port, Anzeigename)
        self.laeuft = True

    # ---- JACK ----
    def jack_starten(self):
        import jack
        self.jack = jack
        c = jack.Client("bardhero", no_start_server=True)
        self.c = c
        self.rate = c.samplerate
        self.mix = Mischer(self.rate)
        self.aus = [c.outports.register("aus_l"), c.outports.register("aus_r")]
        self.ein = [c.inports.register("mic_1"), c.inports.register("mic_2")]

        @c.set_process_callback
        def process(frames):
            jetzt = time.monotonic()
            mono_hoerbar = jetzt + self.latenz
            liedzeit = self.mix.pos / self.rate
            # MIDI einsammeln (jeder Eingang = ein Gerät)
            for name, (port, anzeige) in list(self.midi_ports.items()):
                for off, daten in port.incoming_midi_events():
                    t = jetzt - (frames - off) / self.rate
                    self.midi_raus.append((t, anzeige, bytes(daten)))
            m1 = self.ein[0].get_array()
            m2 = self.ein[1].get_array()
            out = self.mix.block(frames, m1, m2)
            self.aus[0].get_array()[:] = out[:, 0]
            self.aus[1].get_array()[:] = out[:, 1]
            self.zustand.schreiben(liedzeit, mono_hoerbar, int(self.mix.spielt), self.mix.geladen, self.rate,
                                   self.mix.mic_spitze, self.mix.aus_spitze, self.latenz, self.aussetzer, 1,
                                   int(self.mix.vorschau is not None))

        @c.set_xrun_callback
        def xrun(delay):
            self.aussetzer += 1

        c.activate()
        self.verbinden()
        try:
            lat = self.aus[0].get_latency_range(jack.PLAYBACK)[1] if hasattr(self.aus[0], "get_latency_range") else 0
        except Exception:
            lat = 0
        self.latenz = (lat or c.blocksize * 2) / self.rate
        self.backend = 1
        log(f"JACK: {self.rate} Hz, Block {c.blocksize}, Latenz {self.latenz * 1000:.1f} ms")
        threading.Thread(target=self._midi_suchen, daemon=True).start()

    def verbinden(self):
        c = self.c
        try:
            ziele = c.get_ports(is_audio=True, is_input=True, is_physical=True)
            for i, p in enumerate(self.aus):
                if i < len(ziele):
                    try:
                        c.connect(p, ziele[i])
                    except Exception:
                        pass
            quellen = c.get_ports(is_audio=True, is_output=True, is_physical=True)
            for i, p in enumerate(self.ein):
                if i < len(quellen):
                    try:
                        c.connect(quellen[i], p)
                    except Exception:
                        pass
        except Exception as e:
            log("Verbinden:", e)

    def _midi_suchen(self):
        """Neue MIDI-Geräte finden (auch eingesteckte) – jedes bekommt einen eigenen Eingang."""
        n = 0
        while self.laeuft:
            try:
                for q in self.c.get_ports(is_midi=True, is_output=True):
                    name = q.name
                    if name in self.midi_ports or name.startswith("bardhero:"):
                        continue
                    if not (q.is_physical or name.startswith(("a2j:", "ttymidi", "system:"))):
                        continue
                    anzeige = name
                    try:
                        al = [a for a in q.aliases if ":" in a]
                        if al:
                            anzeige = al[-1].split(":", 1)[1]
                    except Exception:
                        pass
                    for vorsilbe in ("alsa_pcm:", "a2j:"):
                        anzeige = anzeige.replace(vorsilbe, "")
                    n += 1
                    port = self.c.midi_inports.register(f"midi_{n}")
                    self.midi_ports[name] = (port, anzeige[:40])
                    try:
                        self.c.connect(q, port)
                    except Exception as e:
                        log("MIDI verbinden:", e)
                    log("MIDI-Gerät:", anzeige)
                    self.melden(f"G {anzeige}")
            except Exception as e:
                log("MIDI suchen:", e)
            time.sleep(2.0)

    # ---- SDL (ohne JACK) ----
    def sdl_starten(self):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        from pygame._sdl2 import audio as sdl_audio
        from pygame._sdl2 import sdl2
        sdl2.init_subsystem(sdl2.INIT_AUDIO)
        _ = pygame
        self.rate = 48000
        self.mix = Mischer(self.rate)
        self.mic_ring = collections.deque(maxlen=8)
        block = 512

        def rueck(geraet, puffer):
            n = len(puffer) // 8
            jetzt = time.monotonic()
            liedzeit = self.mix.pos / self.rate
            mic = None
            if self.mic_ring:
                mic = self.mic_ring.popleft()
                if len(mic) != n:
                    mic = np.resize(mic, n)
            out = self.mix.block(n, mic, mic)
            puffer[:] = out.astype(np.float32).tobytes()
            self.zustand.schreiben(liedzeit, jetzt + self.latenz, int(self.mix.spielt), self.mix.geladen, self.rate,
                                   self.mix.mic_spitze, self.mix.aus_spitze, self.latenz, self.aussetzer, 2,
                                   int(self.mix.vorschau is not None))

        def aufnahme(geraet, puffer):
            a = np.frombuffer(bytes(puffer), dtype=np.float32)
            self.mic_ring.append(a.copy())

        namen = sdl_audio.get_audio_device_names(False) or [""]
        self.dev = sdl_audio.AudioDevice(devicename=namen[0], iscapture=False, frequency=self.rate,
                                         audioformat=sdl_audio.AUDIO_F32, numchannels=2, chunksize=block,
                                         allowed_changes=0, callback=rueck)
        self.dev.pause(0)
        try:
            mics = sdl_audio.get_audio_device_names(True)
            if not mics:
                raise RuntimeError("kein Aufnahmegerät")
            self.mic_dev = sdl_audio.AudioDevice(devicename=mics[0], iscapture=True, frequency=self.rate,
                                                 audioformat=sdl_audio.AUDIO_F32, numchannels=1, chunksize=block,
                                                 allowed_changes=0, callback=aufnahme)
            self.mic_dev.pause(0)
        except Exception as e:
            log("kein Mikrofon-Eingang:", e)
        self.latenz = block * 2 / self.rate
        self.backend = 2
        log(f"SDL: {self.rate} Hz, Block {block}")

    # ---- Steuerung ----
    def melden(self, text):
        try:
            self.sock_spiel.sendto(text.encode("utf-8"), SPIEL)
        except OSError:
            pass

    def _midi_senden(self):
        while self.laeuft:
            while self.midi_raus:
                t, quelle, daten = self.midi_raus.popleft()
                self.melden(f"M {t:.6f} {quelle.replace(' ', '_')} {daten.hex()}")
            time.sleep(0.002)

    def _laden(self, ordner, nr):
        try:
            stems = {}
            for name in ("band", "lead", "bass"):
                p = os.path.join(ordner, name + ".wav")
                if os.path.isfile(p):
                    stems[name] = wav_laden(p, self.rate)
            self.mix.laden(stems, nr)
            self.melden(f"L {nr}")
        except Exception as e:
            log("Laden:", e)
            self.melden(f"F {nr} {e}")

    def befehl(self, b):
        cmd = b.get("cmd")
        mx = self.mix
        if cmd == "laden":
            threading.Thread(target=self._laden, args=(b["ordner"], int(b.get("nr", 1))), daemon=True).start()
        elif cmd == "start":
            mx.start(float(b.get("ab", 0.0)), b.get("klicks", []))
        elif cmd == "stop":
            with mx.lock:
                mx.spielt = False
        elif cmd == "pause":
            with mx.lock:
                mx.spielt = False
        elif cmd == "weiter":
            with mx.lock:
                mx.pos = int(float(b.get("ab", mx.pos / mx.rate)) * mx.rate)
                mx.spielt = True
        elif cmd == "gate":
            mx.gate[b.get("stem", "lead")] = 1.0 if b.get("an") else 0.0
        elif cmd == "pegel":
            for k, v in b.items():
                if k in mx.pegel:
                    mx.pegel[k] = int(v) if k == "mic_kanal" else float(v)
        elif cmd == "sfx":
            mx.geraeusch(b.get("name", ""), float(b.get("laut", 1.0)))
        elif cmd == "vorschau":
            try:
                v = wav_laden(b["datei"], self.rate)
                if v.shape[1] == 1:
                    v = np.repeat(v, 2, axis=1)
                with mx.lock:
                    mx.vorschau = v
                    mx.vorschau_pos = 0
                    mx.vorschau_gain = 0.0
            except Exception as e:
                log("Vorschau:", e)
        elif cmd == "vorschau_aus":
            with mx.lock:
                mx.vorschau = None
        elif cmd == "leer":
            mx.laden({}, int(b.get("nr", 1)), float(b.get("dauer", 30)))
            self.melden(f"L {int(b.get('nr', 1))}")
        elif cmd == "ende":
            self.laeuft = False

    def lauf(self):
        try:
            if os.environ.get("BH_TON") == "sdl":
                raise RuntimeError("SDL gewünscht")
            self.jack_starten()
        except Exception as e:
            log("JACK nicht verfügbar:", e)
            self.sdl_starten()
        self.melden(f"B {self.backend} {self.rate}")
        threading.Thread(target=self._midi_senden, daemon=True).start()
        try:
            os.remove(STEUER)
        except OSError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.bind(STEUER)
        s.settimeout(0.5)
        while self.laeuft:
            try:
                daten = s.recv(65536)
            except socket.timeout:
                if os.getppid() == 1 and not os.environ.get("BH_TON_FREI"):
                    break                                 # Spiel ist weg → aufhören
                continue
            try:
                self.befehl(json.loads(daten.decode("utf-8")))
            except Exception as e:
                log("Befehl:", e)
        try:
            os.remove(STEUER)
        except OSError:
            pass
        if self.backend == 1:
            self.c.deactivate()
            self.c.close()
        log("Ende")


if __name__ == "__main__":
    try:
        os.nice(-5)
    except OSError:
        pass
    Maschine().lauf()
