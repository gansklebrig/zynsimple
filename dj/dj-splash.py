#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: Startbildschirm, solange Mixxx lädt.

Die Gans gleitet ein, goldene Ringe laufen nach außen, darunter ein Ladebalken mit Klartext.
Der Balken folgt den Schritten der Sitzung (Datei /tmp/zynsimple-dj-phase) und dem Mixxx-Protokoll,
und lernt, wie lange der Start beim letzten Mal gedauert hat. Sobald das Mixxx-Fenster da ist,
läuft der Balken voll und der Startbildschirm blendet sich aus. Farben: Gold, Glut, Grün – kein Blau.
"""
import math
import os
import re
import subprocess
import sys
import time
import tkinter

DATEN = os.environ.get("HOME", "/zynthian/zynthian-my-data/dj")
PHASE = "/tmp/zynsimple-dj-phase"
DAUER = os.path.join(DATEN, ".startdauer")
MIXXX_LOG = os.path.join(DATEN, ".mixxx", "mixxx.log")
IMG = "/zynthian/zynthian-my-data/zynsimple/zynsimple/img"
MAX_S = 150

BG, GOLD, GOLD2, CHAMP, TX2, GRUEN, LINIE = "#0b0908", "#e8b04a", "#ffd98a", "#f3e9d8", "#a69a8a", "#34c78a", "#2e261f"

# Schritte: (Anteil am Balken bis hierhin, Text)
SCHRITTE = {
    "start": (0.03, "Bühne wird vorbereitet …"),
    "einrichten": (0.12, "Ton, Controller und Bibliothek werden eingerichtet …"),
    "mixxx": (0.25, "Mixxx startet …"),
}
# Hinweise aus dem Mixxx-Protokoll → (Anteil, Text)
LOG_HINWEISE = [
    (r"SoundManager|PortAudio", 0.38, "Soundkarten werden geöffnet …"),
    (r"[Cc]ontroller", 0.50, "DJ-Controller und Zynthian-Tasten werden verbunden …"),
    (r"[Ll]ibrary|[Tt]rack[Cc]ollection|database", 0.62, "Musik-Bibliothek wird gelesen …"),
    (r"[Ss]kin|LegacySkinParser", 0.80, "Ansicht wird aufgebaut …"),
    (r"[Ww]aveform|[Ee]ffect", 0.90, "Wellenformen und Effekte …"),
]


def mix(c1, c2, f):
    f = max(0.0, min(1.0, f))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


def ease(x):
    return 1 - (1 - max(0.0, min(1.0, x))) ** 3


def mixxx_fenster_da():
    """Hauptfenster von Mixxx sichtbar und groß (nicht nur Mixxx' eigener kleiner Startbildschirm)?"""
    try:
        ids = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "mixxx"], capture_output=True,
                             text=True, timeout=2).stdout.split()
        for wid in ids:
            g = subprocess.run(["xdotool", "getwindowgeometry", wid], capture_output=True, text=True, timeout=2).stdout
            m = re.search(r"Geometry:\s*(\d+)x(\d+)", g)
            if m and int(m.group(1)) >= 600 and int(m.group(2)) >= 350:
                return True
    except Exception:
        pass
    return False


class Start:
    def __init__(self):
        self.root = tkinter.Tk()
        self.root.overrideredirect(True)
        self.W, self.H = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{self.W}x{self.H}+0+0")
        self.root.configure(bg=BG, cursor="none")
        self.cv = tkinter.Canvas(self.root, width=self.W, height=self.H, bg=BG, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.t0 = time.monotonic()
        self.fertig_seit = None
        self.anteil = 0.0
        self.ziel = 0.02
        self.text = "Bühne wird vorbereitet …"
        try:
            with open(DAUER) as f:
                self.erwartet = max(8.0, min(MAX_S, float(f.read().strip())))
        except Exception:
            self.erwartet = 35.0
        self.log_pos = 0
        try:
            self.log_pos = os.path.getsize(MIXXX_LOG)
        except OSError:
            pass
        self.img = None
        H = self.H
        for h in (380, 300, 220):
            p = os.path.join(IMG, f"gans_{h}.png")
            if os.path.exists(p) and (h <= H * 0.6 or h == 220):
                try:
                    self.img = tkinter.PhotoImage(file=p)
                except Exception:
                    pass
                break
        self.aufbauen()
        self.root.after(30, self.schritt)
        self.root.after(200, self.nach_vorne)
        self.root.after(1500, self.pruefen)

    def aufbauen(self):
        cv, W, H = self.cv, self.W, self.H
        ih = self.img.height() if self.img else 160
        self.cy = H * 0.40
        self.cx = W / 2
        self.R = max(ih, 140) * 0.42
        self.glut = [cv.create_oval(0, 0, 0, 0, fill=BG, outline="") for _ in range(4)]
        self.ringe = [cv.create_oval(0, 0, 0, 0, outline=BG, width=3) for _ in range(4)]
        self.funken = [cv.create_oval(0, 0, 0, 0, fill=BG, outline="") for _ in range(14)]
        self.bild = cv.create_image(self.cx, self.cy + 30, image=self.img) if self.img else \
            cv.create_text(self.cx, self.cy, text="♫", font=("DejaVu Sans", 90), fill=GOLD)
        fh = max(22, H // 15)
        ty = min(H - 120, self.cy + ih / 2 + fh * 0.9)
        self.titel = cv.create_text(self.cx, ty, text="DJ-Pult", font=("Audiowide", fh), fill=BG)
        self.unter = cv.create_text(self.cx, ty + fh * 1.05, text="TheAlmightyGoose legt auf",
                                    font=("Audiowide", max(10, fh // 2)), fill=BG)
        # Ladebalken
        bw = min(W * 0.62, 520)
        self.bx0, self.bx1 = self.cx - bw / 2, self.cx + bw / 2
        self.by0 = min(H - 52, ty + fh * 1.9)
        self.by1 = self.by0 + 14
        cv.create_rectangle(self.bx0, self.by0, self.bx1, self.by1, fill="#16120f", outline=LINIE)
        self.balken = cv.create_rectangle(self.bx0 + 1, self.by0 + 1, self.bx0 + 1, self.by1 - 1, fill=GOLD, outline="")
        self.glanz = cv.create_rectangle(0, self.by0 + 2, 0, self.by0 + 5, fill=GOLD2, outline="")
        self.prozent = cv.create_text(self.bx1, self.by1 + 16, anchor="e", text="", font=("DejaVu Sans", 10), fill=TX2)
        self.info = cv.create_text(self.bx0, self.by1 + 16, anchor="w", text="", font=("DejaVu Sans", 11), fill=CHAMP)

    def nach_vorne(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(300, self.nach_vorne)

    def pruefen(self):
        """Schritt der Sitzung, Mixxx-Protokoll und Mixxx-Fenster abfragen."""
        try:
            with open(PHASE) as f:
                ph = f.read().strip()
            if ph in SCHRITTE:
                a, t = SCHRITTE[ph]
                if a > self.ziel:
                    self.ziel, self.text = a, t
        except OSError:
            pass
        try:
            with open(MIXXX_LOG, errors="replace") as f:
                f.seek(self.log_pos)
                neu = f.read()
                self.log_pos = f.tell()
            for rx, a, t in LOG_HINWEISE:
                if a > self.ziel and re.search(rx, neu):
                    self.ziel, self.text = a, t
        except OSError:
            pass
        if self.fertig_seit is None and mixxx_fenster_da():
            self.fertig_seit = time.monotonic()
            self.ziel, self.text = 1.0, "Los geht's!"
            try:
                with open(DAUER, "w") as f:
                    f.write(f"{time.monotonic() - self.t0:.1f}")
            except OSError:
                pass
        self.root.after(400, self.pruefen)

    def schritt(self):
        cv = self.cv
        jetzt = time.monotonic()
        t = jetzt - self.t0
        if t > MAX_S:
            self.root.destroy()
            return
        # Balken: Zeit-Schätzung (bleibt unter 95 %) oder erreichter Schritt – das Größere; weich nachgeführt
        schaetz = 0.95 * (1 - math.exp(-t / (self.erwartet * 0.55)))
        soll = max(self.ziel, schaetz if self.fertig_seit is None else 1.0)
        self.anteil += (soll - self.anteil) * (0.12 if self.fertig_seit else 0.06)
        x = self.bx0 + 1 + (self.bx1 - self.bx0 - 2) * self.anteil
        cv.coords(self.balken, self.bx0 + 1, self.by0 + 1, x, self.by1 - 1)
        cv.itemconfig(self.balken, fill=mix(GOLD, GRUEN, ease((self.anteil - 0.9) / 0.1)))
        gx = self.bx0 + ((t * 160) % max(1, (x - self.bx0 + 40))) - 20
        cv.coords(self.glanz, max(self.bx0 + 2, gx), self.by0 + 2, min(x, gx + 26), self.by0 + 5)
        cv.itemconfig(self.prozent, text=f"{int(self.anteil * 100)} %")
        punkte = "." * (1 + int(t * 2) % 3) if self.fertig_seit is None else ""
        cv.itemconfig(self.info, text=self.text.rstrip(" …") + (" " + punkte if punkte else ""))
        # Gans gleitet ein und schwebt sanft
        if self.img:
            cv.coords(self.bild, self.cx, self.cy + 30 * (1 - ease(t / 0.9)) + 4 * math.sin(t * 1.6))
        # Glut hinter der Gans, pulsierend mit dem Fortschritt
        for k, g in enumerate(self.glut):
            r = self.R * (1.55 - k * 0.25) * (1 + 0.035 * math.sin(t * 2.2 + k))
            cv.coords(g, self.cx - r, self.cy - r, self.cx + r, self.cy + r)
            cv.itemconfig(g, fill=mix(BG, "#3a2410", ease(t / 1.0) * (0.22 + 0.16 * k) * (0.8 + 0.2 * self.anteil)))
        # goldene Ringe nach außen – im Takt (≈ 120 BPM)
        for k, rg in enumerate(self.ringe):
            ph = (t * 0.5 + k / 4) % 1
            r = self.R * (0.95 + ph * 1.8)
            cv.coords(rg, self.cx - r, self.cy - r, self.cx + r, self.cy + r)
            cv.itemconfig(rg, outline=mix(BG, GOLD, (1 - ph) * 0.6 * ease(t / 0.7)))
        # Funken kreisen um die Gans
        for k, fk in enumerate(self.funken):
            w = t * (0.6 + 0.05 * k) + k * 2 * math.pi / len(self.funken)
            rr = self.R * (1.25 + 0.25 * math.sin(t * 1.3 + k))
            fx, fy = self.cx + rr * math.cos(w), self.cy + rr * 0.8 * math.sin(w)
            s = 2 + (k % 3)
            cv.coords(fk, fx - s, fy - s, fx + s, fy + s)
            cv.itemconfig(fk, fill=mix(BG, GOLD2 if k % 2 else GOLD, ease(t / 1.2) * (0.5 + 0.5 * math.sin(t * 3 + k))))
        # Schrift blendet ein
        cv.itemconfig(self.titel, fill=mix(BG, GOLD, ease((t - 0.3) / 0.7)))
        cv.itemconfig(self.unter, fill=mix(BG, CHAMP, ease((t - 0.7) / 0.7)))
        # Ende: kurz voll stehen lassen, dann weg
        if self.fertig_seit is not None and jetzt - self.fertig_seit > 1.4 and self.anteil > 0.98:
            self.root.destroy()
            return
        self.root.after(33, self.schritt)


if __name__ == "__main__":
    try:
        Start().root.mainloop()
    except Exception as e:
        print("DJ-Startbildschirm:", e, file=sys.stderr)
