#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: Hinweisleiste unten am Bildschirm – zeigt immer, was die Zynthian-Regler und F1–F4 gerade tun.

  - links die Ebene (MIXER wechselt): MISCHEN gold · EFFEKTE grün · HANDPAN rot
  - daneben die 4 Regler (drehen / drücken) und F1–F4 – passend zur Ebene, zu ALT und ob ein Stem-Track geladen ist
  - bei jeder Bedienung eine kurze Einblendung darüber („Filter A: 62 %“, „Loop 8 an“ …)

Nachrichten kommen vom Mixxx-Mapping über den DJ-Helfer (Socket /tmp/zynsimple-dj-hud.sock):
  E|<EBENE>|<alt 0/1>|<stems 0/1>      T|<Text für die Einblendung>
Farben: Gold, Glut, Rot, Grün – kein Blau.
"""
import os
import re
import socket
import subprocess
import time
import tkinter

SOCK = "/tmp/zynsimple-dj-hud.sock"
MENUE_SOCK = "/tmp/zynsimple-dj-menue.sock"
BG, KARTE, LINIE, GOLD, GOLD2, CHAMP, TX2, ROT, GRUEN = ("#0b0908", "#1f1915", "#3a2e22", "#e8b04a", "#ffd98a",
                                                         "#f3e9d8", "#a69a8a", "#e0445e", "#34c78a")
HOEHE = 46
SCHRIFT = "DejaVu Sans"
FARBE = {"MISCHEN": GOLD, "EFFEKTE": GRUEN, "HANDPAN": ROT}

# (Regler 1–4: (drehen, drücken)), F1–F4
BELEGUNG = {
    "MISCHEN": [("Titel wählen", "→ Deck A"), ("Kopfhörer-Mix", "→ Deck B"), ("Filter A", "Mitte"), ("Filter B", "Mitte")],
    "EFFEKTE": [("Effekt 1 Stärke", "an/aus"), ("Effekt 1 wählen", "Ziel A/B"), ("Effekt 2 Stärke", "an/aus"),
                ("Effekt 2 wählen", "Ziel A/B")],
    "HANDPAN": [("Handpan laut", "normal"), ("Handpan-Effekt", "an/aus"), ("Master", "normal"), ("Kopfhörer", "normal")],
}


def f_text(ebene, alt, stems):
    if ebene == "MISCHEN":
        if stems:
            return f"F1–F4  Stems Deck {'B' if alt else 'A'}: Drums · Bass · Melodie · Vocals" + ("" if alt else "   (ALT: Deck B)")
        return "F1–F4  Sampler 1–4" + ("" if alt else "   (Stem-Track laden: Stems schalten)")
    if ebene == "EFFEKTE":
        return "F1–F4  Loop 4 · Loop 8 · Loop 16 · Loop aus (vorderes Deck)"
    return "F1 Handpan an/aus · F2 Effekt an/aus · F3 nächster Effekt · F4 Durchsage"


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


class Leiste:
    def __init__(self):
        self.root = tkinter.Tk()
        self.root.overrideredirect(True)
        self.W, self.H = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{self.W}x{HOEHE}+0+{self.H - HOEHE}")
        self.root.configure(bg=BG, cursor="none")
        self.cv = tkinter.Canvas(self.root, width=self.W, height=HOEHE, bg=BG, highlightthickness=0, bd=0)
        self.cv.pack()
        # Einblendung (eigenes Fenster über der Leiste)
        self.tw = tkinter.Toplevel(self.root)
        self.tw.overrideredirect(True)
        self.tw.configure(bg=BG, cursor="none")
        self.tcv = tkinter.Canvas(self.tw, width=440, height=58, bg=BG, highlightthickness=0, bd=0)
        self.tcv.pack()
        self.tw.withdraw()
        self.toast_bis = 0
        self.ebene, self.alt, self.stems = "MISCHEN", False, False
        self.sichtbar = False
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            os.remove(SOCK)
        except OSError:
            pass
        self.sock.bind(SOCK)
        self.sock.setblocking(False)
        self.zeichnen()
        self.root.withdraw()
        self.n = 0
        self.root.after(1500, self.pruefen)
        self.root.after(40, self.lesen)

    def zeichnen(self):
        cv, W = self.cv, self.W
        cv.delete("all")
        cv.create_rectangle(0, 0, W, HOEHE, fill=BG, outline="")
        cv.create_line(0, 0, W, 0, fill=LINIE)
        farbe = FARBE.get(self.ebene, GOLD)
        # Ebene
        cv.create_rectangle(4, 4, 104, HOEHE - 4, fill=KARTE, outline=farbe, width=2)
        cv.create_text(54, 16, text=self.ebene, font=(SCHRIFT, 10, "bold"), fill=farbe)
        cv.create_text(54, 32, text="MIXER: Ebene" if not self.alt else "ALT gehalten", font=(SCHRIFT, 7), fill=TX2)
        # Regler
        bel = BELEGUNG.get(self.ebene, BELEGUNG["MISCHEN"])
        x0, breite = 110, (W - 110 - 6) / 4
        for i, (drehen, druecken) in enumerate(bel):
            x = x0 + i * breite
            cv.create_rectangle(x + 2, 4, x + breite - 2, 26, fill=KARTE, outline=LINIE)
            cv.create_text(x + 8, 15, anchor="w", text=f"R{i + 1}", font=(SCHRIFT, 8, "bold"), fill=farbe)
            cv.create_text(x + 28, 15, anchor="w", text=drehen, font=(SCHRIFT, 9), fill=CHAMP)
            cv.create_text(x + breite - 6, 15, anchor="e", text="⏎ " + druecken, font=(SCHRIFT, 7), fill=TX2)
        cv.create_text(x0 + 4, 36, anchor="w", text=f_text(self.ebene, self.alt, self.stems), font=(SCHRIFT, 9),
                       fill=GOLD2 if self.ebene == "MISCHEN" and self.stems else CHAMP)
        cv.create_text(W - 8, 36, anchor="e", text="SEL laden · ☰/MENU Hilfe", font=(SCHRIFT, 7), fill=TX2)

    def toast(self, text):
        t = self.tcv
        t.delete("all")
        farbe = FARBE.get(self.ebene, GOLD)
        t.create_rectangle(1, 1, 439, 57, fill="#2a2014", outline=farbe, width=2)
        t.create_text(220, 29, text=text, font=(SCHRIFT, 13, "bold"), fill=CHAMP, width=420, justify="center")
        self.tw.geometry(f"440x58+{(self.W - 440) // 2}+{self.H - HOEHE - 70}")
        if self.sichtbar:
            self.tw.deiconify()
            self.tw.lift()
            self.tw.attributes("-topmost", True)
        self.toast_bis = time.monotonic() + 1.8

    def lesen(self):
        while True:
            try:
                msg = self.sock.recv(1024).decode("utf-8", "replace")
            except (BlockingIOError, OSError):
                break
            teile = msg.split("|")
            if teile[0] == "E" and len(teile) >= 4:
                self.ebene, self.alt, self.stems = teile[1], teile[2] == "1", teile[3] == "1"
                self.zeichnen()
            elif teile[0] == "T" and len(teile) >= 2:
                self.toast("|".join(teile[1:]))
        if self.toast_bis and time.monotonic() > self.toast_bis:
            self.toast_bis = 0
            self.tw.withdraw()
        self.root.after(40, self.lesen)

    def pruefen(self):
        """Nur zeigen, wenn Mixxx da ist und kein Menü offen ist."""
        self.n += 1
        menue = os.path.exists(MENUE_SOCK)
        da = self.sichtbar if self.n % 4 else mixxx_da()
        soll = da and not menue
        if soll and not self.sichtbar:
            self.root.deiconify()
        elif not soll and self.sichtbar:
            self.root.withdraw()
            self.tw.withdraw()
        self.sichtbar = soll
        if soll:
            try:
                self.root.lift()
                self.root.attributes("-topmost", True)
            except Exception:
                pass
        self.root.after(700, self.pruefen)


if __name__ == "__main__":
    try:
        Leiste().root.mainloop()
    except Exception as e:
        print("DJ-Hinweisleiste:", e)
