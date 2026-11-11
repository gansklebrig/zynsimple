#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: liest im DJ-Modus die Tasten des Zynthian V5 (über libzyncore) und schaltet um.

  BACK 1,5 s halten  → zurück zur Zynthian-Oberfläche
  MENU 1,5 s halten  → weiter zu Barden Beats (wenn installiert)

Die Tasten-LEDs von BACK und MENU leuchten dabei warm, alle anderen sind aus.
Läuft nur, solange die DJ-Sitzung läuft (wird von dj-sitzung.sh gestartet).
"""
import ctypes
import os
import subprocess
import time

LIB = os.environ.get("ZYNCORE_LIB", "/zynthian/zyncoder/build/libzyncore.so")
BEFEHL = "/usr/local/bin/zynsimple-dj"
HALTEN_S = 1.5
# CUSTOM_SWITCH_nn → Index nn + 3 (wie in der Zynthian-Oberfläche)
TASTEN = {1 + 3: "MENU", 13 + 3: "BACK"}
LED_NR = {"MENU": 0, "BACK": 15}
ZIEL = {"BACK": "zynthian", "MENU": "imres"}


def leds():
    try:
        import board
        import neopixel_spi as neopixel
        pix = neopixel.NeoPixel_SPI(board.SPI(), 20, pixel_order=neopixel.GRB, auto_write=False, frequency=6400000)
        for i in range(20):
            pix[i] = (0, 0, 0)
        pix[LED_NR["BACK"]] = (150, 90, 20)
        if os.path.exists("/usr/local/bin/imres-modus"):
            pix[LED_NR["MENU"]] = (40, 140, 60)
        pix.show()
    except Exception as e:
        print("DJ-Tasten: LEDs nicht verfügbar:", e, flush=True)


def umschalten(name):
    ziel = ZIEL[name]
    if ziel == "imres" and not os.path.exists("/usr/local/bin/imres-modus"):
        return
    print("DJ-Tasten: wechsle zu", ziel, flush=True)
    cmd = [BEFEHL, ziel]
    if subprocess.call(["which", "systemd-run"], stdout=subprocess.DEVNULL) == 0:
        cmd = ["systemd-run", "--no-block", "--collect", "--quiet"] + cmd
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def main():
    try:
        lib = ctypes.cdll.LoadLibrary(LIB)
    except OSError as e:
        print("DJ-Tasten: zyncore nicht gefunden – keine Tasten:", e, flush=True)
        return
    lib.get_zynswitch.restype = ctypes.c_int
    if not lib.init_zyncontrol():
        print("DJ-Tasten: zyncontrol ließ sich nicht starten", flush=True)
        return
    leds()
    print("DJ-Tasten bereit: BACK halten → Zynthian, MENU halten → Barden Beats", flush=True)
    seit = {}
    erledigt = set()
    while True:
        jetzt = time.monotonic()
        for idx, name in TASTEN.items():
            d = lib.get_zynswitch(idx, 20 * 1000000)
            if d == 0:
                seit.setdefault(idx, jetzt)
            elif d > 0:
                seit.pop(idx, None)
                erledigt.discard(idx)
            t0 = seit.get(idx)
            if t0 is not None and idx not in erledigt and jetzt - t0 >= HALTEN_S:
                erledigt.add(idx)
                umschalten(name)
        time.sleep(0.02)


if __name__ == "__main__":
    main()
