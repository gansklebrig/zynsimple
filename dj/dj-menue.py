#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: System-Menü (BACK 2 s halten) – liegt über Mixxx.
Abbrechen · Ausschalten · Neu starten · Updates · Zynthian · Barden Beats
Farben: Gold, Glut, Rot, Grün – kein Blau.
"""
import os
import subprocess
import sys
import time
import tkinter

BEFEHL = "/usr/local/bin/zynsimple-dj"
IMRES = "/usr/local/bin/imres-modus"
BG, CARD, LINIE, GOLD, CHAMP, TX2, ROT, GRUEN = "#0b0908", "#1f1915", "#5a4524", "#e8b04a", "#f3e9d8", "#a69a8a", "#e0445e", "#34c78a"
SCHLIESSEN_NACH = 30


def ausfuehren(aktion):
    cmd = [BEFEHL, aktion]
    if subprocess.call(["which", "systemd-run"], stdout=subprocess.DEVNULL) == 0:
        cmd = ["systemd-run", "--no-block", "--collect", "--quiet"] + cmd
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


class Menue:
    def __init__(self):
        self.root = tkinter.Tk()
        self.root.overrideredirect(True)
        W, H = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.W, self.H = W, H
        self.root.geometry(f"{W}x{H}+0+0")
        self.root.configure(bg=BG, cursor="none")
        self.cv = tkinter.Canvas(self.root, width=W, height=H, bg=BG, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>", self.druck)
        self.t0 = time.monotonic()
        self.scharf = {}
        self.hits = []
        self.items = [
            ("abbrechen", "✕  Abbrechen", "zurück zu Mixxx", None),
            ("aus", "⏻  Ausschalten", "Mixxx speichert, dann aus", ROT),
            ("neustart", "↻  Neu starten", "Mixxx speichert, dann Neustart", None),
            ("update-zynsimple", "⬇  ZynSimple aktualisieren", "wechselt zum Zynthian und sucht das Update", GOLD),
            ("update-zynthian", "⬇  Zynthian aktualisieren", "wechselt zum Zynthian und startet das System-Update", None),
        ]
        if os.path.exists(IMRES):
            self.items.append(("update-barden", "⬇  Barden Beats aktualisieren", "läuft im Hintergrund weiter", None))
        self.items.append(("zynthian", "◼  Zurück zum Zynthian", "Mischer und Synths", GRUEN))
        if os.path.exists(IMRES):
            self.items.append(("imres", "♫  Barden Beats", "Bühne & Klangwelten", GRUEN))
        self.zeichnen()
        self.root.after(200, self.vorne)
        self.root.after(1000, self.zeit)

    def vorne(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(400, self.vorne)

    def zeit(self):
        if time.monotonic() - self.t0 > SCHLIESSEN_NACH:
            self.root.destroy()
            return
        self.root.after(1000, self.zeit)

    def rrect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.cv.create_polygon(pts, smooth=True, **kw)

    def zeichnen(self):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("all")
        self.hits = []
        cv.create_text(20, 28, anchor="w", text="System", font=("Audiowide", 20), fill=GOLD)
        cv.create_text(W - 20, 28, anchor="e", text="DJ-Pult · schließt nach 30 s von selbst", font=("DejaVu Sans", 10), fill=TX2)
        cols = 3
        rows = (len(self.items) + cols - 1) // cols
        gx0, gy0, gx1, gy1 = 12, 56, W - 12, H - 12
        gw, gh = (gx1 - gx0) / cols, (gy1 - gy0) / rows
        jetzt = time.monotonic()
        for k, (key, titel, sub, farbe) in enumerate(self.items):
            x0, y0 = gx0 + (k % cols) * gw, gy0 + (k // cols) * gh
            scharf = self.scharf.get(key, 0) > jetzt
            rand = farbe or LINIE
            self.rrect(x0 + 5, y0 + 5, x0 + gw - 5, y0 + gh - 5, 14, fill=(ROT if scharf else CARD), outline=rand,
                       width=2 if farbe else 1)
            cv.create_text(x0 + gw / 2, y0 + gh * 0.42, text="Wirklich? Nochmal tippen" if scharf else titel,
                           font=("DejaVu Sans", 13, "bold"), fill="#ffffff" if scharf else CHAMP, width=gw - 24, justify="center")
            cv.create_text(x0 + gw / 2, y0 + gh * 0.70, text=sub, font=("DejaVu Sans", 9), fill=TX2, width=gw - 24,
                           justify="center")
            self.hits.append((x0 + 5, y0 + 5, x0 + gw - 5, y0 + gh - 5, key))

    def druck(self, ev):
        self.t0 = time.monotonic()
        for x0, y0, x1, y1, key in self.hits:
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                if key == "abbrechen":
                    self.root.destroy()
                    return
                # Ausschalten und Neustart erst nach einem zweiten Tippen
                if key in ("aus", "neustart") and self.scharf.get(key, 0) < time.monotonic():
                    self.scharf = {key: time.monotonic() + 3}
                    self.zeichnen()
                    self.root.after(3100, self.zeichnen)
                    return
                ausfuehren(key)
                self.root.destroy()
                return


if __name__ == "__main__":
    try:
        Menue().root.mainloop()
    except Exception as e:
        print("DJ-Menü:", e, file=sys.stderr)
