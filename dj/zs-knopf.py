#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple ♪-Knopf: kleiner Knopf oben rechts über dem Mischpult.
1 s halten oder doppelt tippen → das DJ-Pult startet (Mixxx im Vollbild).
(Früher kam dieser Knopf aus Barden Beats und startete Barden Beats – das gibt es nur noch unter
Einstellungen → System.)

Läuft nur, solange die Zynthian-Oberfläche läuft (zynsimple-knopf.service, PartOf=zynthian.service).
Ecke: IMRES_KNOPF=ro|lo|ru|lu|aus in /zynthian/zynthian-my-data/imres/einstellungen.sh (wie bisher).
"""
import json
import os
import re
import sys
import time
import urllib.request

EINST = "/zynthian/zynthian-my-data/imres/einstellungen.sh"
HALTEN_MS = 1000
GROESSE = 60


def einstellung(name, standard):
    try:
        with open(EINST, encoding="utf-8") as f:
            for zeile in f:
                m = re.match(r"\s*(?:export\s+)?" + name + r"=[\"']?([^\"'#\s]*)", zeile)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return os.environ.get(name, standard)


# ---------- Touch direkt vom Gerät lesen ----------
# Die Zynthian-Oberfläche kann Berührungen für sich behalten (dann bekommt das ♫-Fenster nichts mit).
# Darum lesen wir den Touchscreen zusätzlich direkt (/dev/input) – unabhängig davon, welches Fenster oben ist.
import fcntl
import glob
import struct
import threading

EV_KEY, EV_ABS, BTN_TOUCH = 1, 3, 0x14a
ABS_X, ABS_Y, ABS_MT_X, ABS_MT_Y = 0x00, 0x01, 0x35, 0x36
EVENT = struct.Struct("llHHi")


def _absinfo(fd, code):
    buf = bytearray(24)
    req = (2 << 30) | (24 << 16) | (ord("E") << 8) | (0x40 + code)
    fcntl.ioctl(fd, req, buf)
    _wert, mini, maxi = struct.unpack("iii", bytes(buf[:12]))
    return mini, maxi


def touch_geraete():
    """Eingabegeräte mit absoluten Koordinaten und Berührung (Touchscreens)"""
    gefunden = []
    try:
        with open("/proc/bus/input/devices", encoding="utf-8", errors="replace") as f:
            bloecke = f.read().split("\n\n")
    except OSError:
        return gefunden
    for b in bloecke:
        name = re.search(r'N: Name="([^"]*)"', b)
        handler = re.search(r"H: Handlers=([^\n]*)", b)
        absb = re.search(r"B: ABS=([0-9a-f ]+)", b)
        if not (handler and absb):
            continue
        ev = re.search(r"(event\d+)", handler.group(1))
        if ev and ("touch" in b.lower() or "ft5" in b.lower() or "goodix" in b.lower() or "ili" in b.lower() or "edt" in b.lower() or int(absb.group(1).split()[-1], 16) & 3 == 3):
            gefunden.append(("/dev/input/" + ev.group(1), name.group(1) if name else "?"))
    return gefunden


def ecke_getroffen(x, y, ecke):
    """x, y: 0 … 1 in Rohkoordinaten. Gezählt werden die Ecke des Knopfs und die gegenüberliegende (falls der Touch gedreht ist)"""
    r, o = ecke.startswith("r"), not ecke.endswith("u")
    def drin(xx, yy):
        return (xx > .84 if r else xx < .16) and (yy < .18 if o else yy > .82)
    return drin(x, y) or drin(1 - x, 1 - y)


def touch_lesen(pfad, ecke, zustand, melden):
    try:
        fd = os.open(pfad, os.O_RDONLY)
    except OSError as e:
        print("Touch nicht lesbar:", pfad, e, flush=True)
        return
    try:
        bx = _absinfo(fd, ABS_MT_X); by = _absinfo(fd, ABS_MT_Y)
        if bx[1] <= bx[0]:
            bx = _absinfo(fd, ABS_X); by = _absinfo(fd, ABS_Y)
    except OSError:
        bx, by = (0, 4095), (0, 4095)
    print("Touch direkt gelesen:", pfad, "Bereich", bx, by, flush=True)
    x = y = None
    unten = False
    while True:
        try:
            daten = os.read(fd, EVENT.size * 64)
        except OSError:
            time.sleep(1)
            continue
        if not daten:
            time.sleep(.05)
            continue
        for i in range(0, len(daten) - EVENT.size + 1, EVENT.size):
            _s, _us, typ, code, wert = EVENT.unpack_from(daten, i)
            if typ == EV_ABS and code in (ABS_X, ABS_MT_X):
                x = (wert - bx[0]) / max(1, bx[1] - bx[0])
            elif typ == EV_ABS and code in (ABS_Y, ABS_MT_Y):
                y = (wert - by[0]) / max(1, by[1] - by[0])
            elif typ == EV_KEY and code == BTN_TOUCH:
                unten = bool(wert)
                if not unten:
                    zustand["roh_seit"] = None
            if typ == 0 and x is not None and y is not None:   # Ende eines Pakets
                if unten and ecke_getroffen(x, y, ecke):
                    if zustand.get("roh_seit") is None:
                        zustand["roh_seit"] = time.monotonic()
                        print("Ecke berührt (direkt): %.2f %.2f" % (x, y), flush=True)
                        melden()
                else:
                    zustand["roh_seit"] = None


def ziel_starten():
    """DJ-Pult starten – über ZynSimple, das zeigt dabei „DJ-Pult startet …“."""
    port = 8090
    try:
        with open("/zynthian/zynthian-my-data/zynsimple/zynsimple.json", encoding="utf-8") as f:
            port = int(json.load(f).get("web_port", 8090))
    except Exception:
        pass
    try:
        req = urllib.request.Request("http://127.0.0.1:%d/api/dj" % port, data=json.dumps({"aktion": "dj"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=3).read()
    except Exception as e:
        print("ZynSimple nicht erreichbar:", e, flush=True)
        os.system("setsid /usr/local/bin/zynsimple-dj dj >/dev/null 2>&1 &")


def main():
    ecke = einstellung("IMRES_KNOPF", "ro").lower()
    if ecke in ("aus", "off", "0", "nein"):
        print("♪-Knopf ist ausgeschaltet (IMRES_KNOPF=aus)")
        while True:
            time.sleep(3600)
    import tkinter as tk
    # warten, bis die Zynthian-Oberfläche (X) da ist
    root = None
    for _ in range(120):
        try:
            root = tk.Tk()
            break
        except Exception:
            time.sleep(1)
    if root is None:
        sys.exit(1)
    root.overrideredirect(True)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = 0 if ecke.startswith("l") else sw - GROESSE
    y = sh - GROESSE if ecke.endswith("u") else 0
    root.geometry("%dx%d+%d+%d" % (GROESSE, GROESSE, x, y))
    print("♪-Knopf bereit: Ecke %s, Bildschirm %dx%d, Position %d,%d" % (ecke, sw, sh, x, y), flush=True)
    root.configure(bg="#120e18")
    c = tk.Canvas(root, width=GROESSE, height=GROESSE, bg="#120e18", highlightthickness=0, bd=0)
    c.pack()
    rand = c.create_rectangle(1, 1, GROESSE - 2, GROESSE - 2, outline="#e0a046", width=2)
    fuell = c.create_rectangle(2, GROESSE - 2, GROESSE - 2, GROESSE - 2, outline="", fill="#7a5418")
    c.create_text(GROESSE // 2, GROESSE // 2 - 1, text="♪", font=("DejaVu Sans", 28, "bold"), fill="#e0a046")
    zustand = {"seit": None, "ausgeloest": False, "letzter_tipp": 0, "roh_seit": None}
    for pfad, name in touch_geraete():
        print("Touchscreen:", name, pfad, flush=True)
        threading.Thread(target=touch_lesen, args=(pfad, ecke, zustand, lambda: None), daemon=True).start()

    def ausloesen(wie):
        if zustand["ausgeloest"]:
            return
        zustand["ausgeloest"] = True
        print("♪-Knopf ausgelöst (%s)" % wie, flush=True)
        c.itemconfigure(rand, outline="#50ff70")
        c.coords(fuell, 2, 2, GROESSE - 2, GROESSE - 2)
        root.update_idletasks()
        ziel_starten()

    def ticken():
        seit = zustand["seit"] if zustand["seit"] is not None else zustand.get("roh_seit")
        if seit is None and not zustand["ausgeloest"] and zustand.get("war_roh"):
            zustand["war_roh"] = False
            c.coords(fuell, 2, GROESSE - 2, GROESSE - 2, GROESSE - 2)
        if seit is not None and not zustand["ausgeloest"]:
            zustand["war_roh"] = zustand["seit"] is None
            anteil = min(1.0, (time.monotonic() - seit) * 1000 / HALTEN_MS)
            c.coords(fuell, 2, GROESSE - 2 - (GROESSE - 4) * anteil, GROESSE - 2, GROESSE - 2)
            if anteil >= 1.0:
                ausloesen("gehalten")
        root.after(40, ticken)

    def druck(_e):
        jetzt = time.monotonic()
        print("♪-Knopf berührt", flush=True)
        c.itemconfigure(rand, outline="#fff0c0")
        if jetzt - zustand["letzter_tipp"] < 0.6:   # Doppeltipp geht auch
            ausloesen("Doppeltipp")
            return
        zustand["letzter_tipp"] = jetzt
        zustand["seit"] = jetzt

    def los(_e):
        zustand["seit"] = None
        if not zustand["ausgeloest"]:
            c.coords(fuell, 2, GROESSE - 2, GROESSE - 2, GROESSE - 2)
            c.itemconfigure(rand, outline="#e0a046")

    def obenhalten():
        try:
            root.lift()
            root.attributes("-topmost", True)
        except Exception:
            pass
        root.after(1500, obenhalten)

    for w in (c, root):
        w.bind("<ButtonPress-1>", druck)
        w.bind("<ButtonRelease-1>", los)
    ticken()
    obenhalten()
    root.mainloop()


if __name__ == "__main__":
    main()
