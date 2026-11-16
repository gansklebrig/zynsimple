#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bard Hero – Zynthian-Tasten, Drehregler und Tasten-LEDs.

Läuft neben dem Spiel (mit dem Python der Zynthian-Oberfläche, das libzyncore und die LEDs kennt).
  Tasten/Regler  → „T NAME 1|0 zeit“ / „D nr schritte“ an /tmp/bardhero-spiel.sock
  LEDs           ← „L NAME r g b“ / „A r g b“ an /tmp/bardhero-tasten.sock
BACK 3 s halten  → „T BACK_LANG 1“ (Spiel zeigt das System-Menü)
"""
import ctypes
import os
import socket
import sys
import threading
import time

LIB = os.environ.get("ZYNCORE_LIB", "/zynthian/zyncoder/build/libzyncore.so")
SPIEL = os.environ.get("BH_SPIEL_SOCK", "/tmp/bardhero-spiel.sock")
TASTEN_SOCK = os.environ.get("BH_TASTEN_SOCK", "/tmp/bardhero-tasten.sock")
TASTEN = {1: "MENU", 2: "MIXER", 3: "CTRL", 4: "ZS3", 5: "ALT", 6: "TEMPO", 7: "PAD", 8: "F1", 9: "REC", 10: "STOP",
          11: "PLAY", 12: "F2", 13: "BACK", 14: "UP", 15: "SEL", 16: "F3", 17: "LEFT", 18: "DOWN", 19: "RIGHT", 20: "F4",
          21: "DREH1", 22: "DREH2", 23: "DREH3", 24: "DREH4"}
LED_NR = {"MENU": 0, "MIXER": 1, "CTRL": 2, "ZS3": 3, "F1": 4, "PAD": 5, "TEMPO": 6, "ALT": 7, "REC": 8, "STOP": 9,
          "PLAY": 10, "F2": 11, "F3": 12, "SEL": 13, "UP": 14, "BACK": 15, "LEFT": 16, "DOWN": 17, "RIGHT": 18, "F4": 19}


def log(*a):
    print("Tasten:", *a, file=sys.stderr, flush=True)


class Leds:
    def __init__(self):
        self.pix = None
        try:
            import board
            import neopixel_spi as neopixel
            self.pix = neopixel.NeoPixel_SPI(board.SPI(), 20, pixel_order=neopixel.GRB, auto_write=False,
                                             frequency=6400000)
        except Exception as e:
            log("LEDs nicht verfügbar:", e)
        self.stand = {n: (0, 0, 0) for n in LED_NR}
        self.dirty = True
        threading.Thread(target=self._empfang, daemon=True).start()

    def _empfang(self):
        try:
            os.remove(TASTEN_SOCK)
        except OSError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.bind(TASTEN_SOCK)
        while True:
            try:
                t = s.recv(256).decode().split()
                if t[0] == "L" and t[1] in self.stand:
                    self.stand[t[1]] = tuple(int(x) for x in t[2:5])
                elif t[0] == "A":
                    rgb = tuple(int(x) for x in t[1:4])
                    self.stand = {n: rgb for n in LED_NR}
                self.dirty = True
            except Exception:
                pass

    def zeigen(self):
        if self.pix is None or not self.dirty:
            return
        self.dirty = False
        try:
            for name, i in LED_NR.items():
                self.pix[i] = self.stand[name]
            self.pix.show()
        except Exception:
            pass


def main():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    def senden(text):
        try:
            sock.sendto(text.encode(), SPIEL)
        except OSError:
            pass

    leds = Leds()
    try:
        lib = ctypes.cdll.LoadLibrary(LIB)
    except OSError as e:
        log("zyncore nicht gefunden – keine Tasten:", e)
        while True:
            leds.zeigen()
            time.sleep(0.05)
    lib.get_zynswitch.restype = ctypes.c_int
    lib.get_value_zynpot.restype = ctypes.c_int32
    if not lib.init_zyncontrol():
        log("zyncontrol ließ sich nicht starten")
        while True:
            leds.zeigen()
            time.sleep(0.05)
    try:
        npots = lib.get_num_zynpots()
    except Exception:
        npots = 4
    for i in range(npots):
        try:
            lib.setup_behaviour_zynpot(i, 0)
        except Exception:
            pass
    try:
        letzter = lib.get_last_zynswitch_index()
    except Exception:
        letzter = 27
    log("bereit:", letzter + 1, "Schalter,", npots, "Drehregler")
    seit = {}
    lang_gemeldet = set()
    n = 0
    while True:
        jetzt = time.monotonic()
        for idx in range(4, letzter + 1):
            name = TASTEN.get(idx - 3)
            if not name:
                continue
            d = lib.get_zynswitch(idx, 20 * 1000000)
            if d == 0 and idx not in seit:
                seit[idx] = jetzt
                senden(f"T {name} 1 {jetzt:.6f}")
            elif d > 0:
                seit.pop(idx, None)
                lang_gemeldet.discard(idx)
                senden(f"T {name} 0 {jetzt:.6f}")
            t0 = seit.get(idx)
            if name == "BACK" and t0 is not None and idx not in lang_gemeldet and jetzt - t0 > 3.0:
                lang_gemeldet.add(idx)
                senden("T BACK_LANG 1")
        for i in range(npots):
            d = lib.get_value_zynpot(i)
            if d:
                senden(f"D {i} {int(d)}")
        n += 1
        if n % 4 == 0:
            leds.zeigen()
        time.sleep(0.004)


if __name__ == "__main__":
    main()
