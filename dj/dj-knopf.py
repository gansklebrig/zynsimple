#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: der ☰-Knopf oben rechts über Mixxx – immer sichtbar, öffnet das DJ-Menü.
Erscheint, sobald Mixxx bereit ist. Ist noch keine Musik in der Bibliothek, öffnet er das Menü einmal von selbst.
"""
import os
import re
import sqlite3
import subprocess
import time
import tkinter

HIER = os.path.dirname(os.path.abspath(__file__))
DB = "/zynthian/zynthian-my-data/dj/.mixxx/mixxxdb.sqlite"
GOLD, BG, KARTE = "#e8b04a", "#0b0908", "#2a2014"
BREITE, HOEHE = 92, 36


def mixxx_da():
    try:
        ids = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "mixxx"], capture_output=True,
                             text=True, timeout=2).stdout.split()
        for wid in ids:
            g = subprocess.run(["xdotool", "getwindowgeometry", wid], capture_output=True, text=True, timeout=2).stdout
            m = re.search(r"Geometry:\s*(\d+)x(\d+)", g)
            if m and int(m.group(1)) >= 600:
                return True
    except Exception:
        pass
    return False


def titel():
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2)
        n = con.execute("SELECT COUNT(*) FROM library WHERE mixxx_deleted=0").fetchone()[0]
        con.close()
        return n
    except Exception:
        return None


class Knopf:
    def __init__(self):
        self.root = tkinter.Tk()
        self.root.overrideredirect(True)
        W = self.root.winfo_screenwidth()
        self.root.geometry(f"{BREITE}x{HOEHE}+{W - BREITE - 4}+4")
        self.root.configure(bg=BG, cursor="none")
        cv = tkinter.Canvas(self.root, width=BREITE, height=HOEHE, bg=BG, highlightthickness=0, bd=0)
        cv.pack()
        cv.create_rectangle(1, 1, BREITE - 1, HOEHE - 1, fill=KARTE, outline=GOLD, width=2)
        cv.create_text(BREITE / 2, HOEHE / 2, text="☰  Menü", font=("DejaVu Sans", 12, "bold"), fill=GOLD)
        cv.bind("<ButtonPress-1>", lambda e: self.menue())
        self.proc = None
        self.root.withdraw()
        self.root.after(1500, self.warten)

    def menue(self, grund=""):
        if self.proc is not None and self.proc.poll() is None:
            return
        py = "/zynthian/venv/bin/python3" if os.path.exists("/zynthian/venv/bin/python3") else "/usr/bin/python3"
        self.proc = subprocess.Popen([py, os.path.join(HIER, "dj-menue.py")] + ([grund] if grund else []))

    def warten(self):
        """Erst zeigen, wenn Mixxx da ist (sonst läge er über dem Startbildschirm)."""
        if not mixxx_da():
            self.root.after(1500, self.warten)
            return
        self.root.deiconify()
        self.vorne()
        if not titel() and not getattr(self, "auto_gezeigt", False):
            self.auto_gezeigt = True
            self.root.after(2500, lambda: self.menue())

    def vorne(self):
        self.n = getattr(self, "n", 0) + 1
        # Mixxx weg (z. B. „USB-Stick neu einlesen“)? Dann verstecken, bis es wieder da ist
        if self.n % 5 == 0 and not mixxx_da():
            self.root.withdraw()
            self.root.after(1500, self.warten)
            return
        try:
            if self.proc is None or self.proc.poll() is not None:
                self.root.lift()
                self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(700, self.vorne)


if __name__ == "__main__":
    try:
        Knopf().root.mainloop()
    except Exception as e:
        print("DJ-Knopf:", e)
