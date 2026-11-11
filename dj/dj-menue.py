#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: Start-Menü – übersichtlich und selbsterklärend, liegt über Mixxx.

Öffnet sich über den ☰-Knopf oben rechts, mit BACK 2 s halten – und von selbst, wenn noch keine Musik da ist.
Oben steht, was gerade los ist (USB-Stick, Anzahl Titel, Mixxx-Version), darunter große Kacheln:
  Musik:     Auflegen · USB-Stick neu einlesen · Musik übernehmen
  Wechseln:  Zum Zynthian · Barden Beats · So geht's
  System:    Updates · Neu starten · Ausschalten
Farben: Gold, Glut, Rot, Grün – kein Blau.
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import tkinter

BEFEHL = "/usr/local/bin/zynsimple-dj"
IMRES = "/usr/local/bin/imres-modus"
DATEN = "/zynthian/zynthian-my-data/dj"
DB = os.path.join(DATEN, ".mixxx", "mixxxdb.sqlite")
STICKS = "/tmp/zynsimple-dj-sticks.json"
IMPORT_LOG = "/tmp/zynsimple-dj-import.log"
BG, CARD, CARD2, LINIE, GOLD, GOLD2, CHAMP, TX2 = "#0b0908", "#1f1915", "#2a2014", "#5a4524", "#e8b04a", "#ffd98a", "#f3e9d8", "#a69a8a"
ROT, GRUEN = "#e0445e", "#34c78a"
SCHLIESSEN_NACH = 90
SCHRIFT = "DejaVu Sans"

HILFE = [
    ("Titel wählen", "Regler 1 drehen (oder am DDJ-200: SHIFT + Jogwheel)"),
    ("In Deck A / B laden", "Regler 1 drücken = Deck A · Regler 2 drücken = Deck B · oder Titel antippen und ziehen"),
    ("Abspielen", "am DDJ-200: PLAY ▶ links/rechts · Lautstärke: Fader · Überblenden: Crossfader"),
    ("Im Takt", "SYNC am DDJ-200 drücken – das Tempo passt sich an"),
    ("Vorhören", "MIXER = Deck A · CTRL = Deck B im Kopfhörer (USB-Soundkarte)"),
    ("Effekte", "Regler 3 / 4 drehen = Stärke · drücken = an/aus"),
    ("Stems", "F1–F4: Drums · Bass · Melodie · Vocals stumm/an (ALT halten = Deck B)"),
    ("Aufnahme · Auto-DJ", "REC = Set aufnehmen · PLAY (Zynthian) = Auto-DJ an/aus"),
    ("Menü", "☰ oben rechts oder BACK 2 s halten"),
]


def ausfuehren(aktion):
    cmd = [BEFEHL, aktion]
    if subprocess.call(["which", "systemd-run"], stdout=subprocess.DEVNULL) == 0:
        cmd = ["systemd-run", "--no-block", "--collect", "--quiet"] + cmd
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def anzahl_titel():
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2)
        n = con.execute("SELECT COUNT(*) FROM library WHERE mixxx_deleted=0").fetchone()[0]
        con.close()
        return n
    except Exception:
        return None


def sticks():
    try:
        with open(STICKS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def mixxx_version():
    return "2.6 (mit Stems)" if os.path.exists("/opt/mixxx-2.6/bin/mixxx") and not os.path.exists(
        os.path.join(DATEN, ".mixxx26-aus")) else "2.4"


class Menue:
    def __init__(self, grund=""):
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
        self.grund = grund
        self.seite = "start"
        self.scharf = {}
        self.hits = []
        self.import_laeuft = False
        self.zeichnen()
        self.root.after(200, self.vorne)
        self.root.after(1000, self.zeit)

    # ------------------------------------------------------------------
    def vorne(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(400, self.vorne)

    def zeit(self):
        if time.monotonic() - self.t0 > SCHLIESSEN_NACH and not self.import_laeuft:
            self.root.destroy()
            return
        if self.import_laeuft:
            self.zeichnen()
        self.root.after(1000, self.zeit)

    def rrect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.cv.create_polygon(pts, smooth=True, **kw)

    def kachel(self, x0, y0, x1, y1, key, titel, sub, farbe=None, haupt=False):
        cv = self.cv
        scharf = self.scharf.get(key, 0) > time.monotonic()
        fill = ROT if scharf else (CARD2 if haupt else CARD)
        self.rrect(x0, y0, x1, y1, 14, fill=fill, outline=farbe or LINIE, width=3 if haupt else (2 if farbe else 1))
        cv.create_text((x0 + x1) / 2, y0 + (y1 - y0) * 0.40, text="Wirklich? Nochmal tippen" if scharf else titel,
                       font=(SCHRIFT, 15 if haupt else 13, "bold"), fill="#ffffff" if scharf else (farbe if haupt else CHAMP),
                       width=x1 - x0 - 16, justify="center")
        if sub:
            cv.create_text((x0 + x1) / 2, y0 + (y1 - y0) * 0.74, text=sub, font=(SCHRIFT, 9), fill=TX2,
                           width=x1 - x0 - 16, justify="center")
        self.hits.append((x0, y0, x1, y1, key))

    # ------------------------------------------------------------------
    def zeichnen(self):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("all")
        self.hits = []
        if self.seite == "hilfe":
            return self.zeichnen_hilfe()
        if self.seite == "updates":
            return self.zeichnen_updates()
        # Kopf mit Status
        cv.create_text(18, 24, anchor="w", text="♪ DJ-Pult", font=(SCHRIFT, 18, "bold"), fill=GOLD)
        n = anzahl_titel()
        st = sticks()
        if st:
            usb = " · ".join(f"{s['name']}: {s['dateien']} Dateien" for s in st[:2])
            usb_farbe = GRUEN if any(s["dateien"] for s in st) else GOLD
        else:
            usb, usb_farbe = "kein USB-Stick erkannt", TX2
        cv.create_text(W - 18, 16, anchor="e", text=f"Bibliothek: {n if n is not None else '?'} Titel · Mixxx {mixxx_version()}",
                       font=(SCHRIFT, 10), fill=CHAMP)
        cv.create_text(W - 18, 34, anchor="e", text="USB: " + usb, font=(SCHRIFT, 10), fill=usb_farbe)
        y = 50
        # Hinweis, wenn noch nichts da ist
        hinweis = None
        if self.import_laeuft:
            hinweis = self.import_text()
        elif not n and any(s["dateien"] for s in st):
            hinweis = (f"Auf dem USB-Stick sind {sum(s['dateien'] for s in st)} Musikdateien – "
                       "„USB-Stick neu einlesen“ tippen, dann erscheinen sie in Mixxx.")
        elif not n:
            hinweis = ("Noch keine Musik in der Bibliothek. USB-Stick einstecken und „USB-Stick neu einlesen“ tippen – "
                       "oder am PC Musik in \\\\zynthian\\MUSIK gekauft legen (Benutzer musik, Passwort gekauft).")
        elif self.grund:
            hinweis = self.grund
        if hinweis:
            self.rrect(12, y, W - 12, y + 46, 10, fill=CARD2, outline=GOLD, width=2)
            cv.create_text(24, y + 23, anchor="w", text=hinweis, font=(SCHRIFT, 10), fill=CHAMP, width=W - 48)
            y += 54
        # drei Reihen
        reihen = [
            ("MUSIK", [("auflegen", "▶  Auflegen", "Menü schließen, zurück zu Mixxx", GOLD, True),
                       ("einlesen", "⟳  USB-Stick neu einlesen", "nach dem Einstecken – Mixxx startet kurz neu", GRUEN, False),
                       ("importieren", "⇩  Musik auf den Zynthian", "kopiert den Stick – danach ohne Stick", None, False)]),
            ("WECHSELN", [("zynthian", "◼  Zum Zynthian", "Mischer und Synths", None, False),
                          ("imres", "♫  Barden Beats", "Bühne & Klangwelten", None, False) if os.path.exists(IMRES) else None,
                          ("hilfe", "?  So geht's", "Tasten und Regler erklärt", GOLD, False)]),
            ("SYSTEM", [("updates", "⬇  Updates", "ZynSimple · Zynthian · Barden Beats", None, False),
                        ("neustart", "↻  Neu starten", "speichert vorher", None, False),
                        ("aus", "⏻  Ausschalten", "speichert vorher", ROT, False)]),
        ]
        rh = (H - y - 8) / 3
        for k, (titel, kacheln) in enumerate(reihen):
            yy = y + k * rh
            cv.create_text(16, yy + 10, anchor="w", text=titel, font=(SCHRIFT, 8, "bold"), fill=TX2)
            kacheln = [x for x in kacheln if x]
            kw = (W - 24) / 3
            for j, (key, t, sub, farbe, haupt) in enumerate(kacheln):
                x0 = 12 + j * kw
                self.kachel(x0 + 4, yy + 18, x0 + kw - 4, yy + rh - 4, key, t, sub, farbe, haupt)

    def zeichnen_hilfe(self):
        cv, W, H = self.cv, self.W, self.H
        cv.create_text(18, 26, anchor="w", text="? So geht's", font=(SCHRIFT, 18, "bold"), fill=GOLD)
        self.kachel(W - 170, 8, W - 12, 46, "zurueck", "← Zurück", None, GOLD)
        rh = (H - 60) / len(HILFE)
        for k, (was, wie) in enumerate(HILFE):
            yy = 56 + k * rh
            self.rrect(12, yy + 2, W - 12, yy + rh - 2, 8, fill=CARD, outline=LINIE)
            cv.create_text(24, yy + rh / 2, anchor="w", text=was, font=(SCHRIFT, 11, "bold"), fill=GOLD)
            cv.create_text(210, yy + rh / 2, anchor="w", text=wie, font=(SCHRIFT, 10), fill=CHAMP, width=W - 230)

    def zeichnen_updates(self):
        cv, W, H = self.cv, self.W, self.H
        cv.create_text(18, 26, anchor="w", text="⬇ Updates", font=(SCHRIFT, 18, "bold"), fill=GOLD)
        self.kachel(W - 170, 8, W - 12, 46, "zurueck", "← Zurück", None, GOLD)
        items = [("update-zynsimple", "ZynSimple aktualisieren", "wechselt zum Zynthian und zeigt den Fortschritt"),
                 ("update-zynthian", "Zynthian aktualisieren", "das offizielle System-Update")]
        if os.path.exists(IMRES):
            items.append(("update-barden", "Barden Beats aktualisieren", "läuft im Hintergrund weiter"))
        kw = (W - 24) / len(items)
        for j, (key, t, sub) in enumerate(items):
            self.kachel(12 + j * kw + 4, 70, 12 + (j + 1) * kw - 4, H - 20, key, t, sub, GOLD if j == 0 else None)

    def import_text(self):
        try:
            with open(IMPORT_LOG, encoding="utf-8", errors="replace") as f:
                z = [x.strip() for x in f if x.strip()]
        except OSError:
            return "Übernehmen startet …"
        letzte = z[-1] if z else ""
        if letzte.startswith("FERTIG"):
            self.import_laeuft = False
            return "✓ Musik ist auf dem Zynthian. Jetzt „USB-Stick neu einlesen“ tippen, damit Mixxx sie anzeigt."
        if letzte.startswith("FEHLER"):
            self.import_laeuft = False
            return "✕ " + letzte[7:]
        t = letzte.split(" ", 5)
        if t[0] in ("STAND", "DATEI") and len(t) >= 5 and int(t[4] or 0):
            return f"Übernehme Musik … {int(t[3]) * 100 // max(1, int(t[4]))} % · Datei {t[1]} von {t[2]}"
        return "Übernehme Musik …"

    # ------------------------------------------------------------------
    def druck(self, ev):
        self.t0 = time.monotonic()
        for x0, y0, x1, y1, key in self.hits:
            if not (x0 <= ev.x <= x1 and y0 <= ev.y <= y1):
                continue
            if key in ("auflegen",):
                self.root.destroy()
            elif key in ("hilfe", "updates"):
                self.seite = key
                self.zeichnen()
            elif key == "zurueck":
                self.seite = "start"
                self.zeichnen()
            elif key in ("aus", "neustart") and self.scharf.get(key, 0) < time.monotonic():
                self.scharf = {key: time.monotonic() + 3}
                self.zeichnen()
                self.root.after(3100, self.zeichnen)
            elif key == "importieren":
                ausfuehren("importieren")
                self.import_laeuft = True
                self.zeichnen()
            elif key == "einlesen":
                self.cv.delete("all")
                self.cv.create_text(self.W / 2, self.H / 2, text="⟳ USB-Stick wird eingelesen …\nMixxx startet gleich neu",
                                    font=(SCHRIFT, 16, "bold"), fill=GOLD, justify="center")
                self.root.update()
                ausfuehren("neu-einlesen")
                self.root.after(1500, self.root.destroy)
            else:
                ausfuehren(key)
                self.root.destroy()
            return


if __name__ == "__main__":
    try:
        Menue(sys.argv[1] if len(sys.argv) > 1 else "").root.mainloop()
    except Exception as e:
        print("DJ-Menü:", e, file=sys.stderr)
