# -*- coding: utf-8 -*-
"""
ZynSimple – Live-Mischer für den Zynthian-Touchscreen.

Aufbau (800 × 440):
  links   Kanalzüge (Name → Pegel-Seite, Gain/Preset, Fader, Effekte, M/S/❄)
  rechts  LIVE-Leiste: die 4 Drehknöpfe (Tiefe + ★) und Halte-Tasten (Freeze, Echo-Wurf, Panik, XY)
  unten   Seiten · Szenen 1–4 · Überblenden · Sperre · ⋯
Überlagerungen: Effekt-Regler, Effekt-Auswahl, XY-Feld, ⋯-Seite, Bühnenbild (Ruhe-Animation).
"""

import logging
import math
import os
import random
import re
import threading
import time
import tkinter

from zyngui import zynthian_gui_config as cfg
from zyngui.zynthian_gui_base import zynthian_gui_base

log = logging.getLogger("zynsimple")

FLOOR = -60.0

# Glamouröse Palette: tiefes Schwarz, Champagner, Gold, Rosé – kein Blau
P = {
    "bg": "#0b0908", "card": "#16120f", "card2": "#1f1915", "line": "#2e261f",
    "gold": "#e8b04a", "gold2": "#ffd98a", "gold_dim": "#7a5a26", "champ": "#f3e9d8", "tx2": "#a69a8a",
    "rose": "#e0445e", "solo": "#f5d48a", "emerald": "#34c78a", "ice": "#f4efe6", "purple": "#a855c9",
    "black": "#000000",
}
KIND_COL = {"reverb": "#e8b04a", "delay": "#ffcf5a", "comp": "#c9a27a", "eq": "#d98b5f", "other": "#a855c9"}


def _mix(c1, c2, f):
    f = max(0.0, min(1.0, f))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


class zynsimple_screen(zynthian_gui_base):

    buttonbar_config = []  # Oram erwartet dieses Attribut

    # Langer Druck auf diese Bedienelemente erklärt sie (kurz tippen wirkt wie gewohnt)
    EXPLAIN = {
        "mute": "M = stumm schalten. Die Spur ist nicht mehr zu hören, ihre Einstellungen bleiben.",
        "solo": "S = Solo: nur diese Spur hören (alle anderen werden still). Nochmal tippen beendet es.",
        "freeze": "❄ Freeze: der Hall wird „eingefroren“ und schwebt endlos weiter. Nochmal tippen löst ihn.",
        "preset": "‹ › blättert durch die Klänge (Presets) dieses Synths.",
        "gain": "Gain = Vorverstärkung des Eingangs. Wird der Name rot, ist es zu laut: hier runter (−).",
        "gain0": "Antippen setzt den Gain auf 0 dB zurück. Tipp: Auto-Gain auf der Spur-Seite stellt ihn selbst ein.",
        "morph": "Überblenden: wie lange (in Schlägen) der Wechsel zu einer anderen Szene dauert. „hart“ = sofort.",
    }
    DEFER = set(EXPLAIN)

    TASTEN_HILFE = [
        ("Drehregler 1–4", "die vier LIVE-Regler rechts (Tiefe, Hall, Echo …) des gewählten Kanals"),
        ("F1 – F4", "Effekt 1–4 des Kanals an/aus · lang: Regler des Effekts"),
        ("ALT + F1 – F4", "Szene 1–4 laden · lang: aktuellen Klang als Szene speichern"),
        ("◀  ▶", "anderen Kanal wählen"),
        ("▲  ▼", "Tiefe (Regler 1) des Kanals hoch / runter"),
        ("SEL", "kurz: stumm · doppelt: Solo"),
        ("MENU", "⋯ – von hier aus zu DJ-Pult, DJ + Instrumente, Barden Beats, Profi-Mischer, Einstellungen"),
        ("Drehregler drücken", "in Listen: antippen · im Mischer: zeigt, was der Regler gerade steuert"),
        ("REC", "❄ Freeze – tippen = an/aus, halten = nur solange gedrückt"),
        ("PLAY", "↯ Echo-Wurf, solange gedrückt"),
        ("STOP", "Panik: Hall, Echos und hängende Töne aus"),
        ("METRONOM", "Tempo tippen (TAP)"),
        ("BACK", "eine Ebene zurück – überall · 3 s halten: System-Menü (Update, Neustart, Ausschalten, DJ)"),
        ("In Listen", "Drehregler oder Pfeile wählen, am Ende blättert es weiter · SEL = antippen"),
        ("ALT + PLAY", "♫ Titel laden (bei DJ + Instrumente) · dort F1 = Deck A, F2 = Deck B, F3/F4 = Reiter"),
    ]

    def __init__(self, bridge, settings):
        zynthian_gui_base.__init__(self)
        self.bridge = bridge
        self.settings = settings
        self.tts_title = "Einfacher Mischer"
        self.selected = 0
        self.page = 0
        self.per_page = 1
        self.strips = []
        self.data = {}
        self.sig = None
        self.items = {}
        self.live_items = []
        self.hits = []
        self.drag = None
        self.timer = None
        self.mode = "mix"          # mix | edit | browse | more | xy | idle
        self.fxedit = None
        self.browser = None
        self.press = None          # (art, cid, extra, after-id, t0) für langes Drücken
        self.edit_hits = []
        self.edit_tick = 0
        self.edit_drag = None
        self.locked = False
        self.last_input = time.monotonic()
        self.clip_t = {}
        self.pad_t = {}
        self.anim = None
        self.splash_done = not settings.get("splash", True)
        try:
            from . import imres
            self.imres_installed = imres.installed()
        except Exception:
            self.imres_installed = False
        try:
            from . import dj
            self.dj_installed = dj.eingerichtet()
        except Exception:
            self.dj_installed = False
        self.help_anchors = []
        self.help_page = 0
        self.warn = None
        self.warn_items = None
        self.rec_on = False
        self.tip_items = []
        self.tuner = None
        self.autogain = None

        family = getattr(cfg, "font_family", None) or "Audiowide"
        h = max(320, int(self.height))
        self.f_big = (family, max(10, h // 30))
        self.f_mid = (family, max(9, h // 38))
        self.f_small = (family, max(8, h // 48))
        self.f_tiny = (family, max(7, h // 58))
        self.f_huge = (family, max(14, h // 16))

        self.canvas = tkinter.Canvas(self.main_frame, width=self.width, height=self.height,
                                     bg=P["bg"], bd=0, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="news")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self._hook_leds()

    # ------------------------------------------------------------------
    # Grundlagen
    # ------------------------------------------------------------------

    @property
    def pf(self):
        return self.bridge.perform

    @property
    def x(self):
        return self.bridge.extras

    def _geom(self):
        W = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else int(self.width)
        H = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else int(self.height)
        return max(200, W), max(200, H)

    def rrect(self, x0, y0, x1, y1, r=8, **kw):
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _button(self, x, y, w, h, text, enabled, art, cid, extra, fill=None, fg=None, font=None, outline=None, r=8):
        self.rrect(x, y, x + w, y + h, r, fill=fill or P["card2"], outline=outline or "", width=1)
        self.canvas.create_text(x + w / 2, y + h / 2, text=text, font=font or self.f_mid,
                                fill=(fg or P["champ"]) if enabled else P["tx2"])
        if enabled:
            self.hits.append((x, y, x + w, y + h, art, cid, extra))

    # ------------------------------------------------------------------
    # Bedienung mit den Zynthian-Tasten: Drehregler/Pfeile wählen, SEL löst aus, BACK zurück
    # ------------------------------------------------------------------
    FOKUS_MODES = ("more", "settings", "track", "newtrack", "autogain", "tuner", "looper", "stick", "lernen", "tasten", "bib")

    def _fokus_ziele(self):
        roh = [(h[0], h[1], h[2], h[3], h[4], None) for h in getattr(self, "more_hits", [])] if self.mode == "more" \
            else [(h[0], h[1], h[2], h[3], h[4], h[5]) for h in getattr(self, "trk_hits", [])]
        beste = {}
        for x0, y0, x1, y1, art, extra in roh:
            k = (art, repr(extra))
            fl = (x1 - x0) * (y1 - y0)
            if k not in beste or fl < beste[k][0]:
                beste[k] = (fl, (x0, y0, x1, y1))
        ziele = [v[1] for v in beste.values()]
        ziele.sort(key=lambda r: (round((r[1] + r[3]) / 2 / 24), (r[0] + r[2]) / 2))
        return ziele

    def _fokus_zeichnen(self):
        if not getattr(self, "fokus_aktiv", False) or self.mode not in self.FOKUS_MODES:
            return
        z = self._fokus_ziele()
        if not z:
            return
        self.fokus_i = min(getattr(self, "fokus_i", 0), len(z) - 1)
        x0, y0, x1, y1 = z[self.fokus_i]
        self.rrect(x0 - 3, y0 - 3, x1 + 3, y1 + 3, 12, fill="", outline=P["gold2"], width=4)

    def _fokus_neu(self):
        self._redraw()
        self._fokus_zeichnen()

    def _blaettern(self, schritt):
        """Listen mit Seiten (Titel laden, Stick, Tasten): eine Seite weiter/zurück. True, wenn geblättert."""
        try:
            if self.mode == "bib":
                b = self.bib
                n = self._bib_pro()
                neu = b["start"] + schritt * n
                if 0 <= neu < (b["daten"] or {}).get("treffer", 0):
                    b["start"] = neu
                    self._bib_holen()
                    return True
            elif self.mode == "stick":
                st = self.stick
                if st.get("daten") and (st["seite"] + schritt >= 0):
                    alt = st["seite"]
                    st["seite"] += schritt
                    self.draw_stick()
                    if st["seite"] != alt:
                        return True
            elif self.mode == "tasten" and not self.tst.get("wahl"):
                alt = self.tst["seite"]
                self.tst["seite"] = max(0, alt + schritt)
                self.draw_tasten()
                return self.tst["seite"] != alt
        except Exception as e:
            log.debug(f"Blättern: {e}")
        return False

    def fokus_linear(self, schritt):
        z = self._fokus_ziele()
        if not z:
            return
        if not getattr(self, "fokus_aktiv", False):
            self.fokus_aktiv, self.fokus_i = True, 0
        else:
            i = getattr(self, "fokus_i", 0) + schritt
            if not 0 <= i < len(z) and self._blaettern(1 if i >= len(z) else -1):
                z = self._fokus_ziele()
                self.fokus_i = 0 if i >= 0 else len(z) - 1
                if self.mode == "bib" and schritt > 0:
                    self.fokus_i = self._bib_erste_zeile()
            else:
                self.fokus_i = i % len(z)
        self._fokus_neu()

    def _bib_erste_zeile(self):
        z = self._fokus_ziele()
        zeilen = self.bib.get("zeilen") or []
        if zeilen:
            ya = zeilen[0][0]
            for k, r in enumerate(z):
                if r[1] >= ya - 2:
                    return k
        return 0

    def fokus_richtung(self, richtung):
        z = self._fokus_ziele()
        if not z:
            return
        if not getattr(self, "fokus_aktiv", False):
            self.fokus_aktiv, self.fokus_i = True, 0
            return self._fokus_neu()
        x0, y0, x1, y1 = z[min(self.fokus_i, len(z) - 1)]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}[richtung]
        best, bi = None, None
        for i, (a, b, c, d) in enumerate(z):
            mx, my = (a + c) / 2 - cx, (b + d) / 2 - cy
            vor = mx * dx + my * dy
            if vor <= 4:
                continue
            if dx and not (b < y1 and d > y0):      # links/rechts nur innerhalb derselben Zeile
                continue
            wert = vor + (abs(mx * dy) + abs(my * dx)) * 2.5
            if best is None or wert < best:
                best, bi = wert, i
        if bi is not None:
            self.fokus_i = bi
        elif dy and self._blaettern(dy):              # unten/oben am Rand: nächste/vorige Seite
            self.fokus_i = self._bib_erste_zeile() if self.mode == "bib" and dy > 0 else 0
        self._fokus_neu()

    def fokus_ausloesen(self):
        z = self._fokus_ziele()
        if not z:
            return
        if not getattr(self, "fokus_aktiv", False):
            self.fokus_aktiv, self.fokus_i = True, 0
            return self._fokus_neu()
        x0, y0, x1, y1 = z[min(self.fokus_i, len(z) - 1)]

        class E:
            pass
        e = E()
        e.x, e.y = (x0 + x1) / 2, (y0 + y1) / 2
        modus_vorher = self.mode
        self._fokus_tippen = True
        try:
            self.on_press(e)
            self.on_release(e)
        finally:
            self._fokus_tippen = False
        if self.mode != modus_vorher:
            self.fokus_i = 0
        if self.mode in self.FOKUS_MODES:
            self._fokus_zeichnen()

    def _anchor(self, x0, y0, x1, y1, text, side="in"):
        """Merkt sich ein Bedienelement für die Hilfe-Ansicht (?)."""
        self.help_anchors.append((x0, y0, x1, y1, text, side))

    def _show_tip(self, x, y, text, ms=4200):
        """Kleine Erklärung neben dem Finger (für langen Druck)."""
        cv = self.canvas
        for it in self.tip_items:
            cv.delete(it)
        W, H = self._geom()
        w = min(360, W - 20)
        t = cv.create_text(0, 0, text=text, font=self.f_small, fill=P["champ"], width=w - 28, anchor="nw")
        bb = cv.bbox(t) or (0, 0, w - 28, 40)
        h = (bb[3] - bb[1]) + 22
        x0 = max(10, min(W - w - 10, x - w / 2))
        y0 = y - h - 24 if y - h - 24 > 10 else min(H - h - 10, y + 24)
        box = self.rrect(x0, y0, x0 + w, y0 + h, 12, fill="#2a2014", outline=P["gold"], width=2)
        cv.coords(t, x0 + 14, y0 + 11)
        cv.tag_raise(t)
        self.tip_items = [box, t]
        self.canvas.after(ms, lambda items=list(self.tip_items): [cv.delete(i) for i in items])

    def _clip_text(self, text, width, font):
        mc = max(3, int(width / (font[1] * 0.78)))
        return text if len(text) <= mc else text[:mc - 1] + "…"

    def _touch(self):
        self.last_input = time.monotonic()

    def _save_soon(self):
        try:
            self.x.mark_dirty()
        except Exception:
            pass

    def _sel_strip(self):
        if 0 <= self.selected < len(self.strips):
            return self.strips[self.selected]
        return None

    def _sel_chain(self):
        s = self._sel_strip()
        if s:
            try:
                return self.bridge._chain(s["id"])
            except Exception:
                return None
        return None

    def _index_of(self, cid):
        for i, s in enumerate(self.strips):
            if s["id"] == cid:
                return i
        return None

    def _redraw(self):
        self.sig = None
        if self.mode == "edit":
            self.draw_editor()
        elif self.mode == "browse":
            self.draw_browser()
        elif self.mode == "more":
            self.draw_more()
        elif self.mode == "xy":
            self.draw_xy()
        elif self.mode == "fxview":
            self.draw_fxview()
        elif self.mode == "track":
            self.draw_track()
        elif self.mode == "newtrack":
            self.draw_newtrack()
        elif self.mode == "settings":
            self.draw_settings()

    # ------------------------------------------------------------------
    # Lebenszyklus
    # ------------------------------------------------------------------

    def build_view(self):
        self.sig = None
        return True

    BACK_HALTEN_S = 3.0      # BACK so lange halten → System-Menü

    def show(self):
        super().show()
        # Lange Drücke selbst messen (BACK 3 s), statt dass der Zynthian nach 2 s von sich aus „lang“ meldet
        try:
            self._autolong_vorher = getattr(self.zyngui, "zynswitch_autolong_disabled", False)
            self.zyngui.zynswitch_autolong_disabled = True
        except Exception:
            pass
        try:
            self.set_title("Live-Mischer")
        except Exception:
            pass
        self._touch()
        self.sig = None
        if not self.splash_done:
            self.start_splash()
        if self.timer is None:
            self.tick()

    def hide(self):
        try:
            self.zyngui.zynswitch_autolong_disabled = getattr(self, "_autolong_vorher", False)
        except Exception:
            pass
        self._back_abbrechen()
        if self.shown:
            self._save_soon()
        if self.timer:
            try:
                self.canvas.after_cancel(self.timer)
            except Exception:
                pass
            self.timer = None
        if self.mode == "idle":
            self.mode = "mix"
        super().hide()

    def tick(self):
        self.timer = None
        if not self.shown:
            return
        delay = 80
        try:
            if self.mode != "idle":
                self.data = self.bridge.snapshot()
                self.strips = self.data["strips"]
                if self.strips:
                    self.selected = max(0, min(self.selected, len(self.strips) - 1))
            self.edit_tick2 = getattr(self, "edit_tick2", 0) + 1
            if self.edit_tick2 % 15 == 1:
                try:
                    from . import helfer
                    r = helfer.aufnahme_laeuft(self.bridge)
                    if r != self.rec_on:
                        self.rec_on = r
                        self.sig = None
                except Exception:
                    pass
            if self.mode == "mix" and not self.settings.get("help_seen") and self.splash_done \
                    and any(s_["kind"] != "main" for s_ in self.strips) and time.monotonic() - self.last_input > 1.5:
                self.open_help(willkommen=True)
            if self.mode == "mix":
                idle_s = float(self.settings.get("idle_seconds", 45) or 0)
                if idle_s and time.monotonic() - self.last_input > idle_s and not self.drag:
                    self.start_idle()
                else:
                    sig = self._signature()
                    if sig != self.sig:
                        self.sig = sig
                        self._ton_sig = None
                        self.draw()
                    self.update_dynamic()
                    self._ton_anzeige()
            elif self.mode == "edit":
                self.edit_tick += 1
                if self.edit_tick % 3 == 1:
                    self.refresh_editor()
            elif self.mode == "xy":
                self.edit_tick += 1
                if self.edit_tick % 4 == 1 and not self.edit_drag:
                    try:
                        self._xy_move(*self.pf.xy_pos(self.bridge._chain(self.xy_chain)))
                    except Exception:
                        pass
            elif self.mode == "fxview":
                sig = self._signature()
                if sig != getattr(self, "fx_sig", None):
                    self.fx_sig = sig
                    self.draw_fxview()
            elif self.mode in ("track", "newtrack"):
                self.edit_tick += 1
                if self.edit_tick % 6 == 1:
                    self.tick_track()
            elif self.mode == "splash":
                self.draw_splash()
                delay = 33
            elif self.mode == "settings":
                self.edit_tick += 1
                if self.edit_tick % 12 == 1:
                    self.tick_settings()
            elif self.mode == "lernen":
                self.tick_lernen()
            elif self.mode == "bib":
                self.tick_bib()
            elif self.mode == "stick":
                if self.stick.get("neu"):
                    self.stick["neu"] = False
                    self.draw_stick()
            elif self.mode == "update":
                self.draw_update()
                delay = 40
            elif self.mode in ("autogain", "tuner", "looper"):
                self.draw_tool()
                delay = 60
            elif self.mode == "idle":
                self.data = self.bridge.snapshot()
                self.strips = self.data["strips"]
                self.draw_idle()
                delay = 50
        except Exception as e:
            log.exception(f"ZynSimple Bildschirm: {e}")
        self.timer = self.canvas.after(delay, self.tick)

    def _signature(self):
        W, H = self._geom()
        d = self.data
        return repr(self.rec_on) + repr([(s["id"], s["name"], s["mute"], s["solo"], s["preset"] and s["preset"]["name"], s.get("gain"),
                      s.get("freeze"), s.get("throw"), [(f["name"], f["on"], f.get("sync")) for f in s["fx"]])
                     for s in self.strips]) + \
            f"|{self.selected}|{W}x{H}|{d.get('scenes')}|{d.get('last_scene')}|{d.get('morph')}|" \
            f"{d.get('morph_beats')}|{self.locked}|{d.get('undo')}"

    # ------------------------------------------------------------------
    # Hauptansicht
    # ------------------------------------------------------------------

    def draw(self):
        cv = self.canvas
        cv.delete("all")
        self.items = {}
        self.live_items = []
        self.hits = []
        self.help_anchors = []
        self.tip_items = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        bar_h = max(40, H // 10)
        live_w = int(max(170, W * 0.24))
        mix_w = W - live_w
        strip_h = H - bar_h
        n = len(self.strips)

        add_w = max(40, int(W * 0.05))
        mix_w -= add_w
        min_w = int(self.settings.get("strip_min_width", 124))
        self.per_page = max(1, min(n if n else 1, mix_w // min_w))
        pages = max(1, math.ceil(n / self.per_page)) if n else 1
        self.page = min(self.selected // self.per_page, pages - 1)
        first = self.page * self.per_page
        visible = self.strips[first:first + self.per_page]
        sw = mix_w / self.per_page

        leer = not any(s_["kind"] != "main" for s_ in self.strips)
        if leer:
            self._draw_empty(0, 0, mix_w + add_w, strip_h)
        else:
            for k, s in enumerate(visible):
                self._draw_strip(s, first + k, k * sw + 4, 4, sw - 6, strip_h - 6)

        # ＋ Neue Spur
        ax0, ax1 = mix_w + 1, mix_w + add_w - 3
        if not leer:
            self.rrect(ax0, 4, ax1, strip_h - 2, 12, fill=P["bg"], outline=P["gold_dim"], dash=(4, 4))
            cv.create_text((ax0 + ax1) / 2, strip_h * 0.42, text="＋", font=self.f_huge, fill=P["gold"])
            cv.create_text((ax0 + ax1) / 2, strip_h * 0.62, text="S\nP\nU\nR", font=self.f_tiny, fill=P["gold"],
                           justify="center")
            self.hits.append((ax0, 4, ax1, strip_h - 2, "newtrack", None, None))
            self._anchor(ax0, 4, ax1, strip_h - 2, "＋ neue Spur: Handpan, Mikro, Synth, Looper …", "left")
        # Rückgängig nach dem Löschen
        u = self.data.get("undo")
        if u:
            bw_, bh_ = min(mix_w - 20, 420), max(44, int(H * 0.1))
            bx, by = (mix_w - bw_) / 2, strip_h * 0.42
            self.rrect(bx, by, bx + bw_, by + bh_, 14, fill="#2a2014", outline=P["gold"], width=2)
            cv.create_text(bx + 16, by + bh_ / 2, anchor="w", font=self.f_small, fill=P["champ"],
                           text=self._clip_text(f"„{u['name']}“ gelöscht", bw_ * 0.55, self.f_small))
            self._button(bx + bw_ - 190, by + 6, 182, bh_ - 12, f"↶ Zurückholen {u['left']}", True, "undo",
                         None, None, fill=P["gold"], fg=P["black"], font=self.f_small)
            mix_w += add_w
        else:
            mix_w += add_w

        self._draw_live(mix_w + 2, 4, live_w - 6, strip_h - 6)
        self._draw_bar(0, strip_h, W, bar_h, pages)
        # Warn-Banner (Klartext, wird in update_dynamic ein-/ausgeblendet)
        bx1 = mix_w - 6
        wb = self.rrect(8, 6, bx1, 6 + max(34, int(H * 0.08)), 10, fill="#3a1218", outline=P["rose"], width=2,
                        state="hidden")
        wt = cv.create_text(20, 6 + max(34, int(H * 0.08)) / 2, anchor="w", text="", font=self.f_small,
                            fill="#ffe9ec", width=bx1 - 36, state="hidden")
        self.warn_items = (wb, wt)
        if self.mode == "help":
            self.draw_help()

    # ------------------------------------------------------------------
    # Stick-Browser: Inhalt von USB-Stick / SD-Karte, Alben und Titel antippen, gesammelt übernehmen
    # ------------------------------------------------------------------
    def open_stick(self, pfad=None):
        self.stick = {"pfad": pfad, "daten": None, "wahl": set(), "seite": 0, "fehler": None, "neu": False,
                      "summe": None, "erst": pfad is None}
        self.mode = "stick"
        self.fokus_i = 0
        self._stick_laden(pfad)
        self.draw_stick()

    def _stick_laden(self, pfad):
        st = self.stick
        st["daten"], st["fehler"], st["pfad"], st["seite"] = None, None, pfad, 0

        def lauf():
            try:
                from . import dj
                d = dj.stick_modul().liste(pfad)
                # nur ein Stick steckt → gleich hinein
                if pfad is None and len(d["eintraege"]) == 1 and st.get("erst"):
                    st["erst"] = False
                    st["pfad"] = d["eintraege"][0]["pfad"]
                    d = dj.stick_modul().liste(st["pfad"])
                st["daten"] = d
            except Exception as e:
                st["fehler"] = str(e)
            st["neu"] = True
        threading.Thread(target=lauf, daemon=True).start()

    def _stick_summe(self):
        st = self.stick
        try:
            from . import dj
            st["summe"] = dj.stick_modul().summe(st["wahl"]) if st["wahl"] else None
        except Exception:
            st["summe"] = None

    def _stick_gewaehlt(self, pfad):
        """Gewählt – selbst oder weil ein Ordner darüber gewählt ist."""
        return any(pfad == w or pfad.startswith(w + os.sep) for w in self.stick["wahl"])

    def draw_stick(self):
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        st = self.stick
        from . import dj
        gr = dj.stick_modul().groesse
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        cv.create_text(20, 28, anchor="w", text="⇩ Musik übernehmen", font=self.f_big, fill=P["gold"])
        self._tbtn(W - 170, 8, W - 12, 50, "✕ Schließen", "k_close", font=self.f_small)
        d = st["daten"]
        if st["fehler"] or d is None:
            text = st["fehler"] or "Stick wird gelesen …"
            cv.create_text(W / 2, H / 2, text=text, font=self.f_mid, fill=P["rose"] if st["fehler"] else P["tx2"],
                           width=W - 80, justify="center")
            if st["fehler"]:
                self._tbtn(W / 2 - 110, H / 2 + 40, W / 2 + 110, H / 2 + 90, "⟳ Nochmal", "k_neu", font=self.f_small)
            return
        cv.create_text(20, 66, anchor="w", text=self._clip_text(d["name"], W - 40, self.f_small), font=self.f_small,
                       fill=P["tx2"])
        zeilen = []
        if d["eltern"] is not None and not (d["eltern"] == "" and len(dj.stick_modul().sticks()) <= 1):
            zeilen.append(("hoch", None))
        zeilen += [("eintrag", e) for e in d["eintraege"]]
        y0, y1 = 84, H - 74
        rh = max(46, int(H / 9.5))
        pro = max(1, int((y1 - y0) // rh))
        seiten = max(1, math.ceil(len(zeilen) / pro))
        st["seite"] = min(st["seite"], seiten - 1)
        if not d["eintraege"]:
            diag = d.get("diagnose") or ["Hier ist keine Musik (mp3, flac, wav, m4a, ogg …)"]
            cv.create_text(W / 2, y0 + 40, text="Keine Musik gefunden – das sieht der Zynthian:" if d.get("diagnose")
                           else "", font=self.f_mid, fill=P["gold"])
            cv.create_text(W / 2, (y0 + y1) / 2 + 10, text="\n\n".join(diag), font=self.f_small, fill=P["champ"],
                           width=W - 80, justify="center")
            self._tbtn(W / 2 - 110, y1 - 52, W / 2 + 110, y1 - 4, "⟳ Nochmal suchen", "k_neu", font=self.f_small)
        for k, (art, e) in enumerate(zeilen[st["seite"] * pro:(st["seite"] + 1) * pro]):
            ya, yb = y0 + k * rh + 2, y0 + (k + 1) * rh - 2
            if art == "hoch":
                self._tbtn(14, ya, W - 14, yb, "⟵  eine Ebene hoch", "k_hoch", font=self.f_small)
                continue
            an = self._stick_gewaehlt(e["pfad"])
            self.rrect(14, ya, W - 14, yb, 12, fill="#2a2014" if an else P["card"],
                       outline=P["gold"] if an else P["line"], width=2 if an else 1)
            # Auswahl-Kästchen
            bw = yb - ya - 8
            self.rrect(22, ya + 4, 22 + bw, yb - 4, 8, fill=P["gold"] if an else P["card2"],
                       outline=P["gold"] if an else P["gold_dim"], width=2)
            cv.create_text(22 + bw / 2, (ya + yb) / 2, text="✓" if an else "", font=self.f_mid, fill=P["black"])
            self.trk_hits.append((14, ya, 30 + bw, yb, "k_wahl", e["pfad"]))
            # Name und Angaben
            tx = 36 + bw
            name = ("▸ " if e["ordner"] else "♪ ") + e["name"]
            cv.create_text(tx, ya + (yb - ya) * 0.36, anchor="w", font=self.f_small, fill=P["champ"],
                           text=self._clip_text(name, W - tx - 70, self.f_small))
            info = (f"{e['titel']} Titel · " if e["ordner"] else "") + gr(e["bytes"])
            if e["da"] and e["da"] >= e["titel"]:
                info += " · ✓ schon auf dem Zynthian"
            elif e["da"]:
                info += f" · {e['da']} schon da"
            cv.create_text(tx, ya + (yb - ya) * 0.72, anchor="w", font=self.f_tiny,
                           fill=P["emerald"] if e["da"] and e["da"] >= e["titel"] else P["tx2"], text=info)
            if e["ordner"]:
                cv.create_text(W - 34, (ya + yb) / 2, text="›", font=self.f_big, fill=P["gold"])
                self.trk_hits.append((30 + bw, ya, W - 14, yb, "k_auf", e["pfad"]))
            else:
                self.trk_hits.append((30 + bw, ya, W - 14, yb, "k_wahl", e["pfad"]))
        # Leiste unten
        by0, by1 = H - 64, H - 10
        bx = 14
        if seiten > 1:
            self._tbtn(bx, by0, bx + 56, by1, "▲", "k_seite", -1, font=self.f_small)
            cv.create_text(bx + 92, (by0 + by1) / 2, text=f"{st['seite'] + 1}/{seiten}", font=self.f_tiny, fill=P["tx2"])
            self._tbtn(bx + 128, by0, bx + 184, by1, "▼", "k_seite", 1, font=self.f_small)
            bx += 196
        self._tbtn(bx, by0, bx + 130, by1, "Alle hier", "k_alle", font=self.f_small)
        bx += 138
        su = st.get("summe")
        if st["wahl"]:
            self._tbtn(bx, by0, bx + 100, by1, "Nichts", "k_nichts", font=self.f_small)
            bx += 108
        lw = 230
        if su:
            txt = f"{su['titel']} Titel · {gr(su['bytes'])}" + (f"\n{su['neu']} neu" if su["da"] else "")
            cv.create_text((bx + W - lw - 20) / 2, (by0 + by1) / 2, text=txt, font=self.f_tiny, fill=P["champ"],
                           justify="center")
        else:
            cv.create_text((bx + W - lw - 20) / 2, (by0 + by1) / 2, text="Alben/Titel antippen ☐",
                           font=self.f_tiny, fill=P["tx2"])
        if st["wahl"]:
            self._tbtn(W - lw - 14, by0, W - 14, by1, "⇩ Übernehmen", "k_los", fill=P["gold"], fg=P["black"],
                       font=self.f_mid)
        else:
            self.rrect(W - lw - 14, by0, W - 14, by1, 14, fill=P["card"], outline=P["line"])
            cv.create_text(W - lw / 2 - 14, (by0 + by1) / 2, text="⇩ Übernehmen", font=self.f_mid, fill=P["tx2"])

    def stick_press(self, ev):
        h = None
        for hh in reversed(getattr(self, "trk_hits", [])):
            if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]:
                h = hh
                break
        if not h:
            return
        art, extra = h[4], h[5]
        st = self.stick
        if art == "k_close":
            return self.close_stick()
        if art == "k_neu":
            self._stick_laden(st["pfad"])
        elif art == "k_hoch":
            self._stick_hoch()
        elif art == "k_auf":
            self.fokus_i = 0
            self._stick_laden(extra)
        elif art == "k_seite":
            st["seite"] = max(0, st["seite"] + extra)
            self.fokus_i = 0
        elif art == "k_wahl":
            from . import dj
            sm = dj.stick_modul()
            if self._stick_gewaehlt(extra):
                st["wahl"] = set(sm.abwaehlen(st["wahl"], extra))
            else:
                st["wahl"] = set(sm.waehlen(st["wahl"], extra))
            self._stick_summe()
        elif art == "k_alle":
            for e in (st["daten"] or {}).get("eintraege", []):
                if not self._stick_gewaehlt(e["pfad"]):
                    st["wahl"].add(e["pfad"])
            self._stick_summe()
        elif art == "k_nichts":
            st["wahl"].clear()
            st["summe"] = None
        elif art == "k_los":
            from . import start_import
            auswahl = sorted(st["wahl"])
            try:
                from . import dj
                dj.stick_modul().auswahl_vorbereiten(auswahl)      # prüft Platz, bevor es losgeht
            except Exception as e:
                self._flash(str(e))
                return
            start_import(self.zyngui, auswahl=auswahl)
            return
        self.draw_stick()

    def _stick_hoch(self):
        d = self.stick.get("daten") or {}
        if d.get("eltern") is None:
            return self.close_stick()
        if d.get("eltern") == "":
            try:
                from . import dj
                if len(dj.stick_modul().sticks()) <= 1:
                    return self.close_stick()
            except Exception:
                return self.close_stick()
        self.fokus_i = 0
        self._stick_laden(d["eltern"] or None)
        self.draw_stick()

    def close_stick(self):
        self.mode = "mix"
        self.sig = None

    # ------------------------------------------------------------------
    # Keytar anlernen: Taste drücken → Gerät und Kanal erkannt → Synth wählen
    # ------------------------------------------------------------------
    def open_lernen(self):
        g = getattr(self.bridge, "geraete", None)
        if g is None:
            self._flash("MIDI mithören geht hier nicht")
            return
        self.lern = {"t0": time.monotonic(), "ergebnis": None}
        lern = self.lern

        def treffer(geraet, kanal):
            lern["ergebnis"] = (geraet, kanal)
        g.lernen(treffer)
        self.mode = "lernen"
        self.fokus_i = 0
        self.draw_lernen()

    def draw_lernen(self):
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        cv.create_text(W / 2, H * 0.2, text="🎸 Keytar anlernen", font=self.f_huge, fill=P["gold"])
        n = int((time.monotonic() - self.lern["t0"]) * 2) % 4
        cv.create_text(W / 2, H * 0.42, text="Drück jetzt eine Taste auf der Keytar" + "." * n, font=self.f_big,
                       fill=P["champ"])
        cv.create_text(W / 2, H * 0.55, width=W - 80, justify="center", font=self.f_small, fill=P["tx2"],
                       text="Der Zynthian merkt sich, an welcher Buchse und auf welchem MIDI-Kanal sie sendet. "
                            "Danach suchst du den Klang aus – und am Display steht immer, welcher Ton gerade spielt.")
        self._tbtn(W / 2 - 120, H * 0.72, W / 2 + 120, H * 0.72 + 56, "Abbrechen", "l_ab", font=self.f_mid)

    def tick_lernen(self):
        r = self.lern.get("ergebnis")
        if not r:
            return self.draw_lernen()
        geraet, kanal = r
        from . import settings as st
        st.save(self.settings, {"keytar_geraet": geraet, "keytar_kanal": kanal,
                                "ton_anzeige": self.settings.get("ton_anzeige") if self.settings.get("ton_anzeige") != "aus"
                                else "keytar"})
        try:
            self.bridge.geraete.multi_setzen({geraet})
        except Exception:
            pass
        self._flash(f"Keytar erkannt: „{geraet}“, Kanal {kanal + 1} – jetzt den Klang wählen")
        self.open_synth_browser(kanal=kanal, titel="Keytar")

    def lern_press(self, ev):
        h = next((hh for hh in reversed(self.trk_hits) if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]), None)
        if h and h[4] == "l_ab":
            self.lern_ab()

    def lern_ab(self):
        try:
            self.bridge.geraete.lernen_abbrechen()
        except Exception:
            pass
        self.mode = "mix"
        self.sig = None

    # ------------------------------------------------------------------
    # Ton-Anzeige (oben in der Mitte, über dem Mischer)
    # ------------------------------------------------------------------
    def _ton_anzeige(self):
        g = getattr(self.bridge, "geraete", None)
        cv = self.canvas
        r = g.gespielt() if g is not None else None
        sig = (r[0], r[1], tuple(r[2])) if r else None
        if sig == getattr(self, "_ton_sig", None):
            if sig:
                cv.tag_raise("tonanz")
            return
        self._ton_sig = sig
        cv.delete("tonanz")
        if not r or not r[2]:
            return
        self._touch()
        from . import helfer
        from .geraete import notenname
        geraet, kanal, noten = r
        leiter = helfer.tonleiter(self.settings.get("tonart"))
        W, H = self._geom()
        teile = noten[-6:]
        fb = (self.f_huge[0], max(18, int(H / 9)))
        breite = max(W * 0.22, min(W * 0.9, len(teile) * fb[1] * 2.4 + 40))
        x0, x1 = (W - breite) / 2, (W + breite) / 2
        y0, y1 = H * 0.16, H * 0.16 + fb[1] * 2.2 + 26
        self.rrect(x0, y0, x1, y1, 18, fill="#16120f", outline=P["gold"], width=3, tags="tonanz")
        schritt = (breite - 40) / len(teile)
        for i, n in enumerate(teile):
            passt = leiter is None or (n % 12) in leiter
            cv.create_text(x0 + 20 + schritt * (i + 0.5), y0 + fb[1] * 1.2, text=notenname(n), font=fb,
                           fill=(P["emerald"] if leiter is not None else P["gold2"]) if passt else P["rose"],
                           tags="tonanz")
        name = "Keytar" if (geraet, kanal) == (self.settings.get("keytar_geraet"), self.settings.get("keytar_kanal")) \
            else geraet
        zusatz = "" if leiter is None else ("  ·  " + helfer.tonart_name(self.settings.get("tonart")))
        cv.create_text(W / 2, y1 - 16, text=f"{name} · Kanal {kanal + 1}{zusatz}", font=self.f_tiny, fill=P["tx2"],
                       tags="tonanz")

    # ------------------------------------------------------------------
    # Tasten belegen: jede Funktion auflisten, auf eine andere Taste legen (Tausch)
    # ------------------------------------------------------------------
    def open_tasten(self, modus="mischer"):
        self.tst = {"modus": modus, "seite": 0, "wahl": None, "armed": 0}
        self.mode = "tasten"
        self.fokus_i = 0
        self.draw_tasten()

    def draw_tasten(self):
        from . import dj
        tb = dj.tasten_modul()
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        t = self.tst
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        cv.create_text(20, 28, anchor="w", text="⌨ Tasten belegen", font=self.f_big, fill=P["gold"])
        self._tbtn(W - 150, 8, W - 12, 50, "✓ Fertig", "u_zu", fill=P["gold"], fg=P["black"], font=self.f_small)
        # Reiter: Mischer · DJ-Pult · Barden Beats
        tx = 20
        tw = (W - 40 - 16) / 3
        for m in ("mischer", "dj", "barden"):
            an = m == t["modus"]
            self._tbtn(tx, 58, tx + tw, 98, tb.MODUS_NAME[m], "u_modus", m, fill="#2a2014" if an else None,
                       outline=P["gold"] if an else None, fg=P["gold"] if an else None, font=self.f_small)
            tx += tw + 8
        if t["wahl"]:
            return self._tasten_auswahl(tb, W, H)
        rows = tb.liste(t["modus"])
        y0, y1 = 108, H - 70
        rh = max(44, int(H / 10.5))
        pro = max(1, int((y1 - y0) // rh))
        seiten = max(1, math.ceil(len(rows) / pro))
        t["seite"] = min(t["seite"], seiten - 1)
        for k, r in enumerate(rows[t["seite"] * pro:(t["seite"] + 1) * pro]):
            ya, yb = y0 + k * rh + 2, y0 + (k + 1) * rh - 2
            self.rrect(14, ya, W - 14, yb, 12, fill="#2a2014" if r["geaendert"] else P["card"],
                       outline=P["gold_dim"] if r["geaendert"] else P["line"])
            text = r["kurz"]
            mehr = " · ".join(x for x in ((f"ALT: {r['alt']}" if r["alt"] else ""),
                                          (f"halten: {r['halten']}" if r["halten"] else "")) if x)
            cv.create_text(28, ya + (yb - ya) * (0.36 if mehr else 0.5), anchor="w", font=self.f_small,
                           fill=P["champ"], text=self._clip_text(text, W * 0.62, self.f_small))
            if mehr:
                cv.create_text(28, ya + (yb - ya) * 0.72, anchor="w", font=self.f_tiny, fill=P["tx2"],
                               text=self._clip_text(mehr, W * 0.62, self.f_tiny))
            bw = max(110, W * 0.2)
            lab = r["taste_name"] + ("  (sonst " + r["name"] + ")" if r["geaendert"] else "")
            self._tbtn(W - 22 - bw * 1.35, ya + 4, W - 22, yb - 4, "Taste: " + lab, "u_fkt", r["funktion"],
                       fill=P["gold"] if r["geaendert"] else None, fg=P["black"] if r["geaendert"] else P["gold"],
                       font=self.f_tiny)
            self.trk_hits.append((14, ya, W - 22 - bw * 1.35, yb, "u_fkt", r["funktion"]))
        by0, by1 = H - 60, H - 10
        bx = 14
        if seiten > 1:
            self._tbtn(bx, by0, bx + 56, by1, "▲", "u_seite", -1, font=self.f_small)
            cv.create_text(bx + 92, (by0 + by1) / 2, text=f"{t['seite'] + 1}/{seiten}", font=self.f_tiny, fill=P["tx2"])
            self._tbtn(bx + 128, by0, bx + 184, by1, "▼", "u_seite", 1, font=self.f_small)
            bx += 196
        cv.create_text(bx + 6, (by0 + by1) / 2, anchor="w", font=self.f_tiny, fill=P["tx2"], width=W - bx - 290,
                       text="Zeile antippen → neue Taste wählen · die zwei Tasten tauschen · BACK bleibt immer BACK")
        armed = t["armed"] > time.monotonic()
        self._tbtn(W - 264, by0, W - 14, by1, "Wirklich?" if armed else "↺ Standard", "u_reset",
                   fill=P["rose"] if armed else None, fg="#ffffff" if armed else None, font=self.f_small)

    def _tasten_auswahl(self, tb, W, H):
        """Auswahl der neuen Taste – so angeordnet wie am Gerät."""
        cv = self.canvas
        t = self.tst
        f = t["wahl"]
        fk = tb.FUNKTIONEN.get(t["modus"], {}).get(f, ("", "", ""))[0]
        cv.create_text(W / 2, 118, text=f"„{fk}“ auf welche Taste?", font=self.f_mid, fill=P["champ"])
        k = tb.karte(t["modus"])
        jetzt = tb.taste(t["modus"], f)
        gx0, gy0, gx1, gy1 = W * 0.12, 140, W * 0.88, H - 66
        cw, ch = (gx1 - gx0) / 4, (gy1 - gy0) / 5
        for zi, zeile in enumerate(tb.LAYOUT):
            for si, phys in enumerate(zeile):
                x0, y0 = gx0 + si * cw, gy0 + zi * ch
                frei = phys in k
                hier = phys == jetzt
                fkt = k.get(phys)
                sub = (tb.FUNKTIONEN.get(t["modus"], {}).get(fkt, ("",))[0] if frei else "fest")
                self._tbtn(x0 + 3, y0 + 3, x0 + cw - 3, y0 + ch - 3, tb.ANZEIGE.get(phys, phys), "u_ziel" if frei else "u_nix",
                           phys, sub=self._clip_text(sub, cw - 10, self.f_tiny), on=frei,
                           fill=P["gold"] if hier else None, fg=P["black"] if hier else None, font=self.f_small)
        self._tbtn(W / 2 - 110, H - 58, W / 2 + 110, H - 10, "Abbrechen", "u_ab", font=self.f_small)

    def tasten_press(self, ev):
        h = next((hh for hh in reversed(self.trk_hits) if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]), None)
        if not h:
            return
        art, extra = h[4], h[5]
        from . import dj
        tb = dj.tasten_modul()
        t = self.tst
        if art == "u_zu":
            self.mode = "settings"
            return self.draw_settings()
        if art == "u_modus":
            t.update(modus=extra, seite=0, wahl=None)
        elif art == "u_seite":
            t["seite"] = max(0, t["seite"] + extra)
        elif art == "u_fkt":
            t["wahl"] = extra
        elif art == "u_ab":
            t["wahl"] = None
        elif art == "u_ziel":
            try:
                tb.tauschen(t["modus"], t["wahl"], extra)
                self._flash(f"{tb.ANZEIGE.get(extra, extra)}: jetzt „"
                            f"{tb.FUNKTIONEN[t['modus']].get(t['wahl'], ('',))[0]}“")
            except Exception as e:
                self._flash(str(e))
            t["wahl"] = None
        elif art == "u_reset":
            if t["armed"] > time.monotonic():
                tb.zuruecksetzen(t["modus"])
                t["armed"] = 0
                self._flash(f"{tb.MODUS_NAME[t['modus']]}: alle Tasten wieder wie ab Werk")
            else:
                t["armed"] = time.monotonic() + 3
                self.canvas.after(3100, lambda: self.mode == "tasten" and self.draw_tasten())
        self.fokus_i = 0 if art in ("u_modus", "u_fkt", "u_ab", "u_ziel") else self.fokus_i
        self.draw_tasten()

    # ------------------------------------------------------------------
    # ♫ Titel laden (DJ + Instrumente): Bibliothek am Display, A/B = in Deck laden
    # ------------------------------------------------------------------
    BIB_REITER = [("neu", "Neu dazu"), ("fav", "★ Favoriten"), ("az", "A – Z")]
    BIB_BUCHSTABEN = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["#"]

    def open_bib(self):
        hy = getattr(self.bridge, "hybrid", None)
        if hy is None or not hy.laeuft():
            self._flash("Erst „DJ + Instrumente“ starten – dann lassen sich Titel laden")
            return
        self.bib = {"reiter": "neu", "buchstabe": None, "start": 0, "daten": None, "fehler": None, "laedt": None}
        self.mode = "bib"
        self.fokus_i = 0
        self._bib_holen()
        self.draw_bib()

    def _bib_pro(self):
        W, H = self._geom()
        return max(3, int((H - 108 - 70 - (40 if self.bib["reiter"] == "az" else 0)) // max(44, int(H / 10.5))))

    def _bib_holen(self):
        b = self.bib
        try:
            from . import dj
            r = b["reiter"]
            b["daten"] = dj.bibliothek_modul().suche(
                favoriten=r == "fav", limit=self._bib_pro(), start=b["start"],
                sortierung={"neu": "neu", "fav": "sterne", "az": "az"}[r], buchstabe=b["buchstabe"] if r == "az" else None)
            b["fehler"] = None
        except Exception as e:
            b["daten"], b["fehler"] = None, str(e)

    def draw_bib(self):
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        b = self.bib
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        cv.create_text(20, 28, anchor="w", text="♫ Titel laden", font=self.f_big, fill=P["gold"])
        self._tbtn(W - 150, 8, W - 12, 50, "✕ Zurück", "b_zu", font=self.f_small)
        self._tbtn(W - 330, 8, W - 160, 50, "Mixxx zeigen", "b_mixxx", font=self.f_small)
        tw = (W - 40 - 16) / 3
        for i, (k, t) in enumerate(self.BIB_REITER):
            an = b["reiter"] == k
            self._tbtn(20 + i * (tw + 8), 58, 20 + i * (tw + 8) + tw, 98, t, "b_reiter", k,
                       fill="#2a2014" if an else None, outline=P["gold"] if an else None,
                       fg=P["gold"] if an else None, font=self.f_small)
        y0 = 108
        if b["reiter"] == "az":
            bw = (W - 28) / len(self.BIB_BUCHSTABEN)
            for i, ch in enumerate(self.BIB_BUCHSTABEN):
                an = b["buchstabe"] == ch
                self._tbtn(14 + i * bw + 1, y0, 14 + (i + 1) * bw - 1, y0 + 34, ch, "b_buchst", ch,
                           fill=P["gold"] if an else None, fg=P["black"] if an else None, font=self.f_tiny)
            y0 += 42
        d = b["daten"]
        y1 = H - 66
        if b["fehler"] or not d:
            cv.create_text(W / 2, (y0 + y1) / 2, text=b["fehler"] or "…", font=self.f_mid, fill=P["rose"],
                           width=W - 80, justify="center")
        elif not d["titel"]:
            cv.create_text(W / 2, (y0 + y1) / 2, width=W - 80, justify="center", font=self.f_mid, fill=P["tx2"],
                           text={"fav": "Noch keine Favoriten – im DJ-Pult gibt ALT + ▲ dem laufenden Titel einen Stern",
                                 }.get(b["reiter"], "Keine Titel – Musik übernehmen (⋯ → ⇩ Musik übernehmen); "
                                                    "Mixxx liest neue Titel beim nächsten Start ein"))
        else:
            rh = (y1 - y0) / self._bib_pro()
            bw = max(64, W * 0.085)
            b["zeilen"] = []
            for k, t in enumerate(d["titel"]):
                ya, yb = y0 + k * rh + 2, y0 + (k + 1) * rh - 2
                b["zeilen"].append((ya, yb, t["id"]))
                hier = b["laedt"] and b["laedt"][0] == t["id"]
                self.rrect(14, ya, W - 14, yb, 12, fill="#2a2014" if hier else P["card"],
                           outline=P["gold"] if hier else P["line"])
                tx_w = W - 50 - 2 * bw - 20
                cv.create_text(28, ya + (yb - ya) * 0.34, anchor="w", font=self.f_small, fill=P["champ"],
                               text=self._clip_text(t["title"], tx_w, self.f_small))
                info = " · ".join(x for x in (t["artist"], f"{t['bpm']:g} BPM" if t["bpm"] else "", t["tonart"],
                                              "★" * t["sterne"]) if x)
                cv.create_text(28, ya + (yb - ya) * 0.72, anchor="w", font=self.f_tiny, fill=P["tx2"],
                               text=self._clip_text(info, tx_w, self.f_tiny))
                for j, deck in enumerate((1, 2)):
                    x1 = W - 22 - (1 - j) * (bw + 8)
                    lauf = hier and b["laedt"][1] == deck
                    self._tbtn(x1 - bw, ya + 4, x1, yb - 4, "…" if lauf else ("A" if deck == 1 else "B"), "b_laden",
                               (t["id"], deck), fill=P["gold"] if lauf else None,
                               fg=P["black"] if lauf else (P["gold"] if deck == 1 else P["emerald"]), font=self.f_mid)
        by0, by1 = H - 58, H - 10
        if d and d["treffer"] > self._bib_pro():
            seiten = math.ceil(d["treffer"] / self._bib_pro())
            seite = b["start"] // self._bib_pro()
            self._tbtn(14, by0, 70, by1, "▲", "b_seite", -1, font=self.f_small)
            cv.create_text(110, (by0 + by1) / 2, text=f"{seite + 1}/{seiten}", font=self.f_tiny, fill=P["tx2"])
            self._tbtn(150, by0, 206, by1, "▼", "b_seite", 1, font=self.f_small)
        cv.create_text(W - 16, (by0 + by1) / 2, anchor="e", font=self.f_tiny, fill=P["tx2"],
                       text=(f"{d['gesamt']} Titel · " if d else "") + "Regler: Titel wählen · F1 = Deck A · F2 = Deck B · Handy: …:8090/bibliothek")

    def bib_press(self, ev):
        h = next((hh for hh in reversed(self.trk_hits) if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]), None)
        if not h:
            return
        art, extra = h[4], h[5]
        b = self.bib
        if art == "b_zu":
            self.mode = "mix"
            self.sig = None
            return
        if art == "b_mixxx":
            try:
                self.bridge.hybrid.zeigen()
            except Exception as e:
                self._flash(str(e))
            return
        if art == "b_reiter":
            b.update(reiter=extra, start=0, buchstabe=None)
            self.fokus_i = 0
        elif art == "b_buchst":
            b.update(buchstabe=None if b["buchstabe"] == extra else extra, start=0)
        elif art == "b_seite":
            n = self._bib_pro()
            b["start"] = max(0, min(b["start"] + extra * n, max(0, (b["daten"] or {}).get("treffer", 0) - 1) // n * n))
        elif art == "b_laden":
            return self.bib_press_laden(*extra)
        self._bib_holen()
        self.draw_bib()

    def _bib_taste(self, role):
        """Titel laden mit den F-Tasten: F1 = Deck A, F2 = Deck B (ausgewählte Zeile) · F3/F4 = Reiter wechseln."""
        b = self.bib
        if role in ("F3", "F4"):
            ks = [k for k, _ in self.BIB_REITER]
            b.update(reiter=ks[(ks.index(b["reiter"]) + (1 if role == "F4" else -1)) % len(ks)], start=0, buchstabe=None)
            self.fokus_i = 0
            self._bib_holen()
            return self.draw_bib()
        zeilen = b.get("zeilen") or []
        if not zeilen:
            return
        tid = zeilen[0][2]
        if getattr(self, "fokus_aktiv", False):
            z = self._fokus_ziele()
            if z:
                x0, y0, x1, y1 = z[min(self.fokus_i, len(z) - 1)]
                cy = (y0 + y1) / 2
                tid = next((r[2] for r in zeilen if r[0] <= cy <= r[1]), tid)
        self.bib_press_laden(tid, 1 if role == "F1" else 2)

    def bib_press_laden(self, tid, deck):
        b = self.bib
        if b["laedt"]:
            return
        b["laedt"] = (tid, deck)

        def lauf():
            try:
                txt = self.bridge.hybrid.laden(tid, deck)
            except Exception as e:
                txt = f"Laden ging nicht: {e}"
            b["laedt"] = None
            b["meldung"] = txt
        threading.Thread(target=lauf, daemon=True).start()
        self.draw_bib()

    def tick_bib(self):
        b = self.bib
        if b.get("meldung"):
            self._flash(b.pop("meldung"))
            self.draw_bib()

    def open_help(self, willkommen=False):
        self.mode = "help"
        self.help_page = 0
        self.help_welcome = willkommen
        self.sig = None
        self.draw()

    def close_help(self):
        self.mode = "mix"
        self.sig = None
        if not self.settings.get("help_seen"):
            try:
                from . import settings as st
                st.save_intern(self.settings, "help_seen", True)
            except Exception:
                pass

    def draw_help(self):
        cv = self.canvas
        W, H = self._geom()
        if self.help_page == 0:
            # Bildschirm abdunkeln, Bedienelemente golden umranden und beschriften
            cv.create_rectangle(0, 0, W, H, fill="#000000", stipple="gray50", outline="")
            for x0, y0, x1, y1, text, side in self.help_anchors:
                cv.create_rectangle(x0, y0, x1, y1, outline=P["gold"], width=2, dash=(5, 3))
            stufe = 0
            for x0, y0, x1, y1, text, side in sorted(self.help_anchors, key=lambda a: (a[5] != "up", a[0])):
                bw = max(130, min(230, (x1 - x0) + 30)) if side in ("up", "down", "in") else 200
                t = cv.create_text(0, 0, text=text, font=self.f_tiny, fill=P["champ"], width=bw - 16, anchor="nw")
                bb = cv.bbox(t) or (0, 0, bw - 16, 20)
                bh = bb[3] - bb[1] + 12
                cx = (x0 + x1) / 2
                if side == "up":
                    # Beschriftungen der Leiste abwechselnd in zwei Reihen, damit nichts überlappt
                    bx, by = cx - bw / 2, y0 - bh - 6 - (stufe % 2) * (bh + 26)
                    stufe += 1
                elif side == "down":
                    bx, by = cx - bw / 2, y1 + 6
                elif side == "left":
                    bx, by = x0 - bw - 6, (y0 + y1) / 2 - bh / 2
                else:
                    bx, by = cx - bw / 2, (y0 + y1) / 2 - bh / 2
                bx = max(4, min(W - bw - 4, bx))
                by = max(4, min(H - bh - 4, by))
                box = self.rrect(bx, by, bx + bw, by + bh, 8, fill="#2a2014", outline=P["gold"])
                cv.coords(t, bx + 8, by + 6)
                cv.tag_raise(t)
            titel = "Willkommen bei ZynSimple!" if getattr(self, "help_welcome", False) else "So funktioniert der Mischer"
            tw = min(W - 40, 520)
            self.rrect((W - tw) / 2, H * 0.36, (W + tw) / 2, H * 0.36 + 74, 14, fill=P["card"], outline=P["gold"], width=2)
            cv.create_text(W / 2, H * 0.36 + 24, text=titel, font=self.f_big, fill=P["gold"])
            cv.create_text(W / 2, H * 0.36 + 52, font=self.f_tiny, fill=P["tx2"],
                           text="Antippen: weiter zu den Tasten am Zynthian · langer Druck auf M, S, ❄ … erklärt sie auch")
        else:
            cv.delete("all")
            cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
            cv.create_text(18, 28, anchor="w", text="Tasten & Regler am Zynthian", font=self.f_big, fill=P["gold"])
            cv.create_text(W - 18, 28, anchor="e", text="antippen schließt", font=self.f_tiny, fill=P["tx2"])
            rows = self.TASTEN_HILFE
            cols = 2
            per = math.ceil(len(rows) / cols)
            rh = (H - 64) / per
            cw = (W - 24) / cols
            for k, (taste, was) in enumerate(rows):
                x0, y0 = 12 + (k // per) * cw, 54 + (k % per) * rh
                self.rrect(x0 + 3, y0 + 2, x0 + cw - 3, y0 + rh - 2, 10, fill=P["card2"], outline=P["line"])
                kw = cw * 0.3
                self.rrect(x0 + 10, y0 + 8, x0 + kw, y0 + rh - 8, 8, fill="#2a2014", outline=P["gold_dim"])
                cv.create_text(x0 + (10 + kw) / 2, y0 + rh / 2, text=taste, font=self.f_tiny, fill=P["gold"])
                cv.create_text(x0 + kw + 12, y0 + rh / 2, anchor="w", text=was, font=self.f_tiny, fill=P["champ"],
                               width=cw - kw - 24)

    # ------------------------------------------------------------------
    # Werkzeuge: Auto-Gain, Stimmgerät, Looper
    # ------------------------------------------------------------------

    def open_tool(self, art, cid):
        self.tool = {"art": art, "chain": cid, "t0": time.monotonic(), "loop": [], "n": 0}
        self.mode = art
        try:
            if art == "autogain":
                self.bridge.action(cid, "hf_autogain", {"sek": 10})
            elif art == "tuner":
                from . import helfer
                info = self.bridge.tracks.info(cid)
                self.tool["eingang"] = (info.get("inputs") or [1])[0]
                self.tool["n_in"] = max(2, info.get("n_inputs", 2))
                self.tuner = helfer.Stimmgeraet()
                self.tuner.start(self.tool["eingang"])
            elif art == "looper":
                r = self.bridge.action(cid, "hf_looper")
                self.tool["loop"], self.tool["takt"] = r["tasten"], r.get("takt")
        except Exception as e:
            self.tool["fehler"] = str(e)
        self.draw_tool()

    def close_tool(self):
        if self.mode == "tuner" and self.tuner:
            self.tuner.stop()
            self.tuner = None
        if self.mode == "autogain":
            ag = getattr(self.bridge, "autogain", None)
            if ag and ag.lauf and ag.lauf["phase"] == "hoeren":
                ag.stop()
        cid = self.tool.get("chain")
        self.mode = "track"
        self.trk = {"chain": cid, "armed": 0}
        self.draw_track()

    def draw_tool(self):
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        t = self.tool
        art = t["art"]
        try:
            name = self.bridge._name(self.bridge._chain(t["chain"]))
        except Exception:
            name = ""
        titel = {"autogain": "Auto-Gain", "tuner": "Stimmgerät", "looper": "Looper"}[art]
        cv.create_text(18, 30, anchor="w", text=f"{titel}  ·  {name}", font=self.f_big, fill=P["gold"])
        self._tbtn(W - 160, 10, W - 12, 52, "Fertig", "t_close", fill=P["gold"], fg=P["black"], font=self.f_small)
        if t.get("fehler"):
            cv.create_text(W / 2, H / 2, text=t["fehler"], font=self.f_mid, fill=P["rose"], width=W - 80, justify="center")
            return
        if art == "autogain":
            info = self.bridge.action(t["chain"], "hf_autogain_info") or {}
            ph = info.get("phase")
            cx, cy = W / 2, H * 0.5
            if ph == "hoeren":
                rest = info.get("rest", 0)
                cv.create_text(cx, H * 0.22, text="Jetzt spielen – so laut wie beim Auftritt", font=self.f_mid,
                               fill=P["champ"])
                cv.create_text(cx, cy, text=f"{int(rest + 0.99)}", font=(self.f_huge[0], self.f_huge[1] * 3),
                               fill=P["gold"])
                frac = max(0.0, min(1.0, (info.get("peak", -99) + 60) / 60))
                bx0, bx1, by = W * 0.15, W * 0.85, H * 0.78
                self.rrect(bx0, by, bx1, by + 22, 8, fill=P["black"], outline=P["line"])
                col = P["emerald"] if info.get("peak", -99) < -12 else (P["gold2"] if info.get("peak", -99) < -3 else P["rose"])
                cv.create_rectangle(bx0 + 2, by + 2, bx0 + 2 + (bx1 - bx0 - 4) * frac, by + 20, fill=col, outline="")
                cv.create_text(cx, by + 40, text="lautester Schlag bisher", font=self.f_tiny, fill=P["tx2"])
            else:
                ok = ph == "fertig"
                cv.create_text(cx, cy - 30, text="✓" if ok else "!", font=(self.f_huge[0], self.f_huge[1] * 2),
                               fill=P["emerald"] if ok else P["rose"])
                cv.create_text(cx, cy + 40, text=info.get("text", ""), font=self.f_mid, fill=P["champ"], width=W - 80,
                               justify="center")
                self._tbtn(cx - 120, H - 70, cx + 120, H - 20, "Nochmal messen", "t_again", font=self.f_small)
        elif art == "tuner":
            from . import helfer
            w = self.tuner.wert if self.tuner else {}
            cx, cy = W / 2, H * 0.48
            leiter = helfer.tonleiter(self.settings.get("tonart"))
            if w.get("note") is None:
                cv.create_text(cx, cy, text="Spiel einen einzelnen Ton …", font=self.f_mid, fill=P["tx2"])
            else:
                cent = w.get("cent", 0)
                gut = abs(cent) <= 5
                col = P["emerald"] if gut else (P["gold"] if abs(cent) <= 20 else P["rose"])
                cv.create_text(cx, cy - 40, text=f"{helfer.NOTEN[w['note']]}{w.get('oktave', '')}",
                               font=(self.f_huge[0], self.f_huge[1] * 3), fill=col)
                # Nadel
                bx0, bx1, by = W * 0.12, W * 0.88, cy + 50
                cv.create_line(bx0, by, bx1, by, fill=P["line"], width=3)
                for c in (-50, -25, 0, 25, 50):
                    xx = cx + (bx1 - bx0) / 2 * c / 50
                    cv.create_line(xx, by - 10, xx, by + 10, fill=P["gold_dim"] if c else P["gold"], width=2)
                xx = cx + (bx1 - bx0) / 2 * max(-50, min(50, cent)) / 50
                cv.create_oval(xx - 12, by - 12, xx + 12, by + 12, fill=col, outline="")
                cv.create_text(cx, by + 34, font=self.f_small, fill=P["champ"],
                               text=f"{'+' if cent > 0 else ''}{cent} Cent  ·  {w.get('hz')} Hz" +
                                    ("   ✓ sauber" if gut else ("   zu hoch" if cent > 0 else "   zu tief")))
                if leiter is not None:
                    drin = w["note"] in leiter
                    cv.create_text(cx, by + 62, font=self.f_tiny, fill=P["gold"] if drin else P["rose"],
                                   text=("gehört zu " if drin else "nicht in ") + helfer.tonart_name(self.settings.get("tonart")))
            # Eingang wählen
            cv.create_text(18, H - 36, anchor="w", text="EINGANG", font=self.f_tiny, fill=P["gold"])
            for k in range(1, t.get("n_in", 2) + 1):
                on = k == t.get("eingang")
                x0 = 100 + (k - 1) * 64
                self._tbtn(x0, H - 58, x0 + 56, H - 14, str(k), "t_in", k, fill=P["gold"] if on else P["bg"],
                           fg=P["black"] if on else P["champ"], font=self.f_small)
            if leiter is None:
                cv.create_text(W - 18, H - 36, anchor="e", font=self.f_tiny, fill=P["tx2"],
                               text="Tipp: Tonart in den Einstellungen setzen")
        elif art == "looper":
            t["n"] += 1
            if t["n"] % 8 == 1:
                try:
                    r = self.bridge.action(t["chain"], "hf_looper")
                    t["loop"], t["takt"] = r["tasten"], r.get("takt")
                except Exception as e:
                    t["fehler"] = str(e)
            tasten = [x_ for x_ in t["loop"] if x_["key"] != "_state"]
            st_ = next((x_["label"] for x_ in t["loop"] if x_["key"] == "_state"), "")
            tk = t.get("takt") or {}
            gy0 = 96
            if tk.get("kann_takt"):
                from . import helfer
                # Länge: frei oder im Takt (1/2/4 Takte) · Loops: wählen, ＋ = weiterer Loop
                yy0, yy1 = 62, 104
                cv.create_text(18, (yy0 + yy1) / 2, anchor="w", text="LÄNGE", font=self.f_tiny, fill=P["gold"])
                bx = 18 + int(self.f_tiny[1] * 5.5)
                cw = max(60, int(W * 0.09))
                for n_, txt in helfer.LOOP_LAENGEN:
                    on = tk.get("takte") == n_
                    self._tbtn(bx, yy0, bx + cw, yy1, txt, "t_takt", n_, fill=P["gold"] if on else None,
                               fg=P["black"] if on else P["champ"], font=self.f_tiny)
                    bx += cw + 6
                bx += 18
                cv.create_text(bx, (yy0 + yy1) / 2, anchor="w", text="LOOP", font=self.f_tiny, fill=P["gold"])
                bx += int(self.f_tiny[1] * 4.5)
                lw = max(44, int(W * 0.055))
                for k_ in range(1, tk.get("loops", 1) + 1):
                    on = tk.get("gewaehlt") == k_
                    self._tbtn(bx, yy0, bx + lw, yy1, str(k_), "t_wahl", k_, fill=P["emerald"] if on else None,
                               fg=P["black"] if on else P["champ"], font=self.f_small)
                    bx += lw + 6
                if tk.get("loops", 1) < min(4, tk.get("max_loops", 1)) and bx + lw < W - 10:
                    self._tbtn(bx, yy0, bx + lw, yy1, "＋", "t_loops", tk.get("loops", 1) + 1, font=self.f_small)
                info = ("im Takt: Aufnahme startet und endet auf der Eins · Tempo vom Zynthian" if tk.get("takte")
                        else "frei: Aufnahme so lang, wie du drückst")
                cv.create_text(W / 2, yy1 + 14, text=info + (f"  ·  {st_}" if st_ else ""), font=self.f_tiny, fill=P["tx2"])
                gy0 = yy1 + 30
            elif st_:
                cv.create_text(W / 2, 74, text=f"Zustand: {st_}", font=self.f_small, fill=P["tx2"])
            cols = 3
            rows = max(1, math.ceil(len(tasten) / cols))
            gy1 = H - 20
            gw, gh = (W - 24) / cols, (gy1 - gy0) / rows
            for k, b_ in enumerate(tasten):
                x0, y0 = 12 + (k % cols) * gw, gy0 + (k // cols) * gh
                on = b_.get("on")
                rot = b_["key"] == "record"
                self._tbtn(x0 + 5, y0 + 5, x0 + gw - 5, y0 + gh - 5, b_["label"], "t_loop", b_["key"],
                           fill=(P["rose"] if rot else P["gold"]) if on else None,
                           fg=("#ffffff" if rot else P["black"]) if on else (P["rose"] if rot else None),
                           font=self.f_big)
            if not tasten:
                cv.create_text(W / 2, H / 2, text="Dieser Looper bietet keine Tasten an", font=self.f_mid, fill=P["tx2"])

    def tool_press(self, ev):
        h = None
        for hh in reversed(getattr(self, "trk_hits", [])):
            if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]:
                h = hh
                break
        if not h:
            return
        art, extra = h[4], h[5]
        try:
            if art == "t_close":
                return self.close_tool()
            if art == "t_again":
                self.bridge.action(self.tool["chain"], "hf_autogain", {"sek": 10})
            elif art == "t_in" and self.tuner:
                self.tool["eingang"] = extra
                self.tuner.start(extra)
            elif art in ("t_loop", "t_takt", "t_wahl", "t_loops"):
                wert = extra if art == "t_loop" else f"{ {'t_takt': 'takt', 't_wahl': 'wahl', 't_loops': 'loops'}[art] }:{extra}"
                r = self.bridge.action(self.tool["chain"], "hf_looper", wert)
                self.tool["loop"], self.tool["takt"] = r["tasten"], r.get("takt")
        except Exception as e:
            self._flash(str(e))
        self.draw_tool()

    def _draw_empty(self, x, y, w, h):
        """Leerer Start: statt eines leeren Mischers die Frage, was angeschlossen wird."""
        cv = self.canvas
        cv.create_text(x + w / 2, y + 30, text="Was schließt du an?", font=self.f_huge, fill=P["gold"])
        cv.create_text(x + w / 2, y + 62, font=self.f_small, fill=P["tx2"],
                       text="Antippen – die Spur ist sofort da, mit passenden Effekten")
        tiles = [("handpan", "Handpan", "Low-Cut, Kompressor,\nDelay im Takt, Hall"),
                 ("vocal", "Mikro / Gesang", "Kompressor und\nPlatten-Hall"),
                 ("instrument", "Instrument", "Gitarre, Didgeridoo …\nmit etwas Raum"),
                 ("synth", "Synth", "spielt über MIDI\nmit dem Keyboard"),
                 ("looper", "Looper", "Schichten aufnehmen\nund übereinanderlegen"),
                 ("audio", "Leerer Eingang", "ohne Effekte –\nselbst zusammenstellen")]
        cols, rows = 3, 2
        gx0, gy0, gx1, gy1 = x + 10, y + 86, x + w - 10, y + h - 6
        gw, gh = (gx1 - gx0) / cols, (gy1 - gy0) / rows
        for k, (key, title, sub) in enumerate(tiles):
            x0, y0 = gx0 + (k % cols) * gw, gy0 + (k // cols) * gh
            hot = key == "handpan"
            self.rrect(x0 + 5, y0 + 5, x0 + gw - 5, y0 + gh - 5, 14, fill="#2a2014" if hot else P["card2"],
                       outline=P["gold"] if hot else P["gold_dim"], width=2 if hot else 1)
            cv.create_text(x0 + gw / 2, y0 + gh * 0.36, text=title, font=self.f_mid, fill=P["champ"])
            cv.create_text(x0 + gw / 2, y0 + gh * 0.66, text=sub, font=self.f_tiny, fill=P["tx2"], justify="center")
            self.hits.append((x0 + 5, y0 + 5, x0 + gw - 5, y0 + gh - 5, "empty_tpl", None, key))
        self._anchor(gx0 + 5, gy0 + 5, gx1 - 5, gy1 - 5, "Tippe an, was du anschließt – Eingang 1 ist vorgewählt, "
                     "ändern kannst du ihn danach auf der Spur-Seite (Name antippen)")
    def _draw_bar(self, x, y, W, h, pages):
        cv = self.canvas
        cv.create_line(8, y + 1, W - 8, y + 1, fill=P["gold_dim"])
        pad = 4
        bw = max(44, int(W * 0.06))
        self._button(pad, y + pad + 2, bw, h - 2 * pad - 2, "◀", self.page > 0, "page", None, -1)
        self._button(2 * pad + bw, y + pad + 2, bw, h - 2 * pad - 2, "▶", self.page < pages - 1, "page", None, 1)
        # Szenen
        sx = 3 * pad + 2 * bw + 8
        cv.create_text(sx, y + h / 2, anchor="w", text="SZENE", font=self.f_tiny, fill=P["gold"])
        sx += int(self.f_tiny[1] * 5.8)
        scenes = self.data.get("scenes") or {}
        cur = self.data.get("last_scene")
        alt = False
        try:
            alt = bool(self.zyngui.get_alt_mode())
        except Exception:
            pass
        sbw = max(42, int(W * 0.058))
        for k in range(1, 5):
            n = k + 4 if alt else k
            has = scenes.get(str(n))
            on = cur == str(n)
            self._button(sx, y + pad + 2, sbw, h - 2 * pad - 2, str(n), True, "scene", None, n,
                         fill=P["gold"] if on else (P["card2"] if has else P["bg"]),
                         fg=P["black"] if on else (P["champ"] if has else P["tx2"]),
                         outline=P["gold_dim"] if has and not on else P["line"], font=self.f_mid)
            sx += sbw + pad
        self._anchor(3 * pad + 2 * bw + 8, y + pad, sx, y + h - pad,
                     "Szenen: tippen = laden · lang drücken = jetzigen Klang speichern", "up")
        mb = self.data.get("morph_beats", 4)
        lbl = "hart" if not mb else f"↝ {int(mb)}"
        self._button(sx + 4, y + pad + 2, int(sbw * 1.3), h - 2 * pad - 2, lbl, True, "morph", None, None,
                     fill=P["card2"], fg=P["gold2"] if self.data.get("morph") else P["champ"], font=self.f_small)
        tx = sx + 12 + int(sbw * 1.3)
        bpm = self.data.get("tempo")
        tw_ = int(sbw * 1.65)
        self.tap_btn = (tx, y + pad + 2, tw_, h - 2 * pad - 2)
        self._button(tx, y + pad + 2, tw_, h - 2 * pad - 2, f"TAP {bpm:g}" if bpm else "TAP", True, "tap",
                     None, None, fill=P["bg"], fg=P["gold"], outline=P["gold"], font=self.f_small)
        self._anchor(sx + 4, y + pad, tx + tw_, y + h - pad, "Überblenden zwischen Szenen · TAP: Tempo im Takt tippen", "up")
        rx = tx + tw_ + pad
        rw_ = int(sbw * 1.15)
        self._button(rx, y + pad + 2, rw_, h - 2 * pad - 2, "● REC", True, "rec", None, None,
                     fill=P["rose"] if self.rec_on else P["bg"], fg="#ffffff" if self.rec_on else P["rose"],
                     outline=P["rose"], font=self.f_tiny)
        self._anchor(rx, y + pad, rx + rw_, y + h - pad, "Set aufnehmen (alles, was rauskommt)", "up")
        # rechts: Effekte, Sperre, Mehr
        mw = max(54, int(W * 0.08))
        ew = int(mw * 1.35)
        self._button(W - 3 * (pad + mw) - (ew - mw), y + pad + 2, ew, h - 2 * pad - 2, "Effekte", True, "fxview",
                     None, None, fill=P["card2"], fg=P["gold"], outline=P["gold_dim"], font=self.f_small)
        self._button(W - pad - mw, y + pad + 2, mw, h - 2 * pad - 2, "⋯", True, "more", None, None,
                     font=self.f_big, fg=P["gold"])
        self._button(W - 2 * (pad + mw), y + pad + 2, mw, h - 2 * pad - 2,
                     "AUFTRITT" if self.locked else "Auftritt", True, "lock", None, None,
                     fill=P["rose"] if self.locked else P["card2"], font=self.f_tiny)
        self._anchor(W - 3 * (pad + mw) - (ew - mw), y + pad, W - 3 * (pad + mw) - (ew - mw) + ew, y + h - pad,
                     "alle Effekte aller Spuren", "up")
        self._anchor(W - 2 * (pad + mw), y + pad, W - pad, y + h - pad,
                     "Auftritt: nur Fader, Mute, Szenen, Panik · ⋯ = Mehr: DJ, Barden Beats, Einstellungen", "up")
        try:
            from . import updater
            if updater.status.get("available"):
                cv.create_text(W - 3 * (pad + mw) - (ew - mw) - 8, y + h / 2, anchor="e", font=self.f_tiny,
                               fill=P["gold"], text=f"Update {updater.status.get('latest')} → ⋯")
        except Exception:
            pass

    def _draw_strip(self, s, index, x, y, w, h):
        cv = self.canvas
        cid = s["id"]
        sel = index == self.selected
        it = {}
        self.rrect(x, y, x + w, y + h, 12, fill=P["card2"] if sel else P["card"],
                   outline=P["gold"] if sel else P["line"], width=2 if sel else 1)
        self.hits.append((x, y, x + w, y + h, "select", cid, index))
        pad = 6
        cx0, cx1 = x + pad, x + w - pad
        cy = y + pad

        # Name (antippen → Spur-Seite: Eingänge, Name, Löschen …)
        first_vis = not any(a[4].startswith("Name antippen") for a in self.help_anchors)
        name = self._clip_text(s["name"], w - 2 * pad, self.f_big)
        it["name"] = cv.create_text(x + w / 2, cy + self.f_big[1] * 0.95, text=name, font=self.f_big, fill=P["champ"])
        if s["kind"] != "main":
            self.hits.append((x, y, x + w, cy + self.f_big[1] * 2, "chanedit", cid, None))
        if first_vis and s["kind"] != "main":
            self._anchor(x, y, x + w, cy + self.f_big[1] * 2, "Name antippen: Eingang, Auto-Gain, Stimmgerät, Löschen …")
        cy += self.f_big[1] * 2
        cv.create_line(cx0 + 10, cy, cx1 - 10, cy, fill=P["gold_dim"] if sel else P["line"])
        cy += 4

        # Preset- oder Gain-Zeile
        row_h = max(28, int(h * 0.085))
        aw = max(26, int(w * 0.22))
        hy_ = getattr(self.bridge, "hybrid", None)
        if s["name"] == "DJ-Pult" and hy_ is not None and hy_.laeuft():
            # DJ + Instrumente: direkter Weg zur Musik
            self._button(cx0, cy, cx1 - cx0, row_h, "♫ Titel laden", True, "bib", cid, None, fill=P["gold"],
                         fg=P["black"], font=self.f_small)
            if first_vis:
                self._anchor(cx0, cy, cx1, cy + row_h, "Musik in Deck A oder B laden")
        elif s["preset"]:
            self._button(cx0, cy, aw, row_h, "‹", True, "preset", cid, -1, fill=P["bg"], fg=P["gold"], font=self.f_big)
            self._button(cx1 - aw, cy, aw, row_h, "›", True, "preset", cid, 1, fill=P["bg"], fg=P["gold"], font=self.f_big)
            cv.create_text(x + w / 2, cy + row_h / 2, font=self.f_small, fill=P["champ"],
                           text=self._clip_text(s["preset"]["name"], w - 2 * aw - 8, self.f_small))
        elif s.get("gain") is not None:
            self._button(cx0, cy, aw, row_h, "−", True, "gain", cid, -1, fill=P["bg"], fg=P["gold"], font=self.f_big)
            self._button(cx1 - aw, cy, aw, row_h, "+", True, "gain", cid, 1, fill=P["bg"], fg=P["gold"], font=self.f_big)
            g = s["gain"]
            cv.create_text(x + w / 2, cy + row_h * 0.3, font=self.f_tiny, fill=P["tx2"], text="GAIN")
            cv.create_text(x + w / 2, cy + row_h * 0.68, font=self.f_small, fill=P["champ"],
                           text=f"{'+' if g > 0 else ''}{g} dB")
            self.hits.append((cx0 + aw, cy, cx1 - aw, cy + row_h, "gain0", cid, None))
            if first_vis:
                self._anchor(cx0, cy, cx1, cy + row_h, "Gain: Eingang lauter/leiser")
        else:
            kind = {"audio": "Audio-Eingang", "main": "Hauptausgang", "bus": "Bus"}.get(s["kind"], "")
            cv.create_text(x + w / 2, cy + row_h / 2, text=kind, font=self.f_small, fill=P["tx2"])
        cy += row_h + 6

        # unten: M/S/❄ und Effekte
        ms_h = max(34, int(h * 0.1))
        fx_h = max(28, int(h * 0.08))
        prio = {"reverb": 0, "delay": 1, "comp": 2, "eq": 3}
        max_fx = 3 if h > 300 else 2
        fx_list = sorted(sorted(s["fx"], key=lambda f: prio.get(f.get("kind"), 4))[:max_fx], key=lambda f: f["i"])
        add_btn = s["kind"] != "main"
        bottom = y + h - pad
        ms_y = bottom - ms_h
        fx_y = ms_y - 6 - (len(fx_list) + (1 if add_btn else 0)) * (fx_h + 4)

        # Fader + Pegel
        fy0, fy1 = cy, fx_y - 6
        mw = max(8, int(w * 0.09))
        it["meterA"] = (cx0, fy0, cx0 + mw / 2 - 1, fy1)
        it["meterB"] = (cx0 + mw / 2 + 1, fy0, cx0 + mw, fy1)
        for key in ("meterA", "meterB"):
            a, b, c, d = it[key]
            cv.create_rectangle(a, b, c, d, fill=P["black"], outline="")
            it[key + "_bar"] = cv.create_rectangle(a, d, c, d, fill=P["emerald"], outline="")
            it[key + "_hold"] = cv.create_line(a, d, c, d, fill=P["champ"], width=2)
        fx0 = cx0 + mw + 6
        it["fader"] = (fx0, fy0, cx1, fy1)
        self.rrect(fx0, fy0, cx1, fy1, 8, fill=P["black"], outline=P["line"])
        it["fill"] = cv.create_rectangle(fx0 + 2, fy1, cx1 - 2, fy1 - 1, fill=P["gold"], outline="")
        it["glow"] = cv.create_line(fx0 + 2, fy1, cx1 - 2, fy1, fill=P["gold2"], width=2)
        it["cap"] = cv.create_rectangle(fx0 + 5, fy1 - 4, cx1 - 5, fy1 + 4, fill=P["champ"], outline="")
        it["val"] = cv.create_text((fx0 + cx1) / 2, fy0 + self.f_small[1] + 4, text="", font=self.f_small, fill=P["champ"])
        if s["level"] is not None:
            self.hits.append((fx0, fy0, cx1, fy1, "fader", cid, (fy0, fy1)))
        if first_vis and s["kind"] != "main":
            self._anchor(cx0, fy0 + (fy1 - fy0) * 0.3, cx1, fy0 + (fy1 - fy0) * 0.62,
                         "Fader: Lautstärke ziehen · Balken links = Pegel (rot = zu laut)")

        # Effekte (kurz = an/aus, lang = Regler)
        fy = fx_y
        for f in fx_list:
            on = f["on"]
            col = KIND_COL.get(f.get("kind"), P["emerald"])
            label = f["name"] + (f"  ♩{f['sync']}" if f.get("sync") else "")
            self._button(cx0, fy, cx1 - cx0, fx_h, self._clip_text(label, cx1 - cx0 - 8, self.f_small), True,
                         "fx", cid, f["i"], fill=col if on else P["bg"], fg=P["black"] if on else P["champ"],
                         font=self.f_small, outline=col if not on else "", r=6)
            fy += fx_h + 4
        if first_vis and s["kind"] != "main" and fx_list:
            self._anchor(cx0, fx_y, cx1, fy, "Effekt antippen = an/aus · lang drücken = Regler")
        if add_btn:
            more = len(s["fx"]) - len(fx_list)
            self._button(cx0, fy, cx1 - cx0, fx_h, f"＋ Effekt" + (f"  (+{more})" if more > 0 else ""), True,
                         "browse", cid, None, fill=P["bg"], fg=P["gold"], font=self.f_small, outline=P["gold_dim"], r=6)

        # Mute / Solo / Freeze
        bx1 = cx1
        if s.get("freeze") is not None:
            fw = max(28, int((cx1 - cx0) * 0.3))
            self._button(cx1 - fw, ms_y, fw, ms_h, "❄", True, "freeze", cid, None,
                         fill=P["ice"] if s["freeze"] else P["bg"], fg=P["black"] if s["freeze"] else P["champ"],
                         font=self.f_big, outline=P["line"])
            bx1 = cx1 - fw - 4
        if s["solo"] is None:
            self._button(cx0, ms_y, bx1 - cx0, ms_h, "MUTE", True, "mute", cid, None,
                         fill=P["rose"] if s["mute"] else P["bg"], outline=P["line"])
        else:
            half = (bx1 - cx0 - 4) / 2
            self._button(cx0, ms_y, half, ms_h, "M", True, "mute", cid, None,
                         fill=P["rose"] if s["mute"] else P["bg"], outline=P["line"])
            self._button(cx0 + half + 4, ms_y, half, ms_h, "S", True, "solo", cid, None,
                         fill=P["solo"] if s["solo"] else P["bg"], fg=P["black"] if s["solo"] else None,
                         outline=P["line"])
        if first_vis and s["kind"] != "main":
            self._anchor(cx0, ms_y, cx1, ms_y + ms_h, "M stumm · S solo · ❄ Hall einfrieren (lang drücken erklärt)", "down")
        self.items[cid] = it

    def _draw_live(self, x, y, w, h):
        cv = self.canvas
        s = self._sel_strip()
        self.rrect(x, y, x + w, y + h, 14, fill=P["card"], outline=P["gold_dim"], width=1)
        cv.create_text(x + 12, y + 14, anchor="w", text="LIVE", font=self.f_small, fill=P["gold"])
        # ?-Knopf: erklärt alles auf dieser Seite
        qx = x + 12 + int(self.f_small[1] * 3.6)
        self.rrect(qx, y + 3, qx + 34, y + 26, 99, fill="#2a2014", outline=P["gold"], width=2)
        cv.create_text(qx + 17, y + 14, text="?", font=self.f_small, fill=P["gold"])
        self.hits.append((qx - 6, y, qx + 40, y + 30, "help", None, None))
        # Systemlast oben rechts (wird in update_dynamic aufgefrischt)
        self.sys_item = cv.create_text(x + w - 10, y + 14, anchor="e", font=self.f_tiny, fill=P["tx2"], text="")
        self.sys_hit = (x + w * 0.45, y, x + w, y + 28)
        self.hits.append((x + w * 0.45, y, x + w, y + 28, "sysinfo", None, None))
        if not s or s["kind"] == "main":
            leer = not any(s_["kind"] != "main" for s_ in self.strips)
            cv.create_text(x + w / 2, y + h / 2, font=self.f_small, fill=P["tx2"], width=w - 24, justify="center",
                           text="Hier erscheinen die Live-Regler,\nsobald es eine Spur gibt" if leer else "Kanal wählen")
            return
        cv.create_text(x + 12, y + 32, anchor="w", font=self.f_tiny, fill=P["champ"],
                       text=self._clip_text(s["name"], w - 24, self.f_tiny))
        chain = self._sel_chain()
        slots = []
        if chain is not None:
            try:
                slots = [self.pf.slot_info(chain, sl) for sl in self.pf.live_slots(chain)]
            except Exception as e:
                log.debug(f"Live: {e}")
        top = y + 42
        pads_h = int(h * 0.32)
        self._anchor(x + 6, top, x + w - 6, y + h - pads_h - 8,
                     "Die 4 Drehregler am Zynthian – oder hier ziehen", "left")
        self._anchor(x + 6, y + h - pads_h, x + w - 6, y + h - 4,
                     "Halten wirkt solange gedrückt · Panik beruhigt alles", "left")
        sh = (h - 42 - pads_h - 8) / 4
        for k, sl in enumerate(slots):
            sy = top + k * sh
            star = "★ " if sl.get("pin") else ""
            label = f"{k + 1}  {star}{sl['name']}"
            if sl.get("fxname") and not sl.get("pin"):
                label += f" · {sl['fxname']}"
            cv.create_text(x + 12, sy + sh * 0.26, anchor="w", font=self.f_tiny, fill=P["champ"],
                           text=self._clip_text(label, w - 70, self.f_tiny))
            vt = cv.create_text(x + w - 12, sy + sh * 0.26, anchor="e", font=self.f_tiny, fill=P["gold2"],
                                text=sl.get("text", ""))
            bx0, bx1, by0, by1 = x + 12, x + w - 12, sy + sh * 0.5, sy + sh * 0.78
            self.rrect(bx0, by0, bx1, by1, 5, fill=P["black"], outline=P["line"])
            bar = cv.create_rectangle(bx0 + 1, by0 + 1, bx0 + 1, by1 - 1, fill=P["gold"], outline="")
            self.live_items.append((k, bar, vt, (bx0, by0, bx1, by1)))
            if sl["kind"] != "none":
                self.hits.append((bx0, sy, bx1, sy + sh, "slot", s["id"], (k, bx0, bx1)))
        # Halte-Tasten
        py = y + h - pads_h
        gw = (w - 30) / 2
        gh = (pads_h - 16) / 2
        frz = s.get("freeze")
        thr = s.get("throw")
        self._button(x + 10, py, gw, gh, "❄ Freeze", frz is not None, "p_freeze", s["id"], None,
                     fill=P["ice"] if frz else P["bg"], fg=P["black"] if frz else None, font=self.f_small,
                     outline=P["line"])
        self._button(x + 20 + gw, py, gw, gh, "↯ Echo", True, "p_throw", s["id"], None,
                     fill=P["gold"] if thr else P["bg"], fg=P["black"] if thr else None, font=self.f_small,
                     outline=P["line"])
        self._button(x + 10, py + gh + 6, gw, gh, "XY-Feld", True, "xy", s["id"], None, fill=P["bg"],
                     font=self.f_small, fg=P["gold"], outline=P["gold_dim"])
        self._button(x + 20 + gw, py + gh + 6, gw, gh, "Panik", True, "panic", None, None, fill=P["bg"],
                     font=self.f_small, fg=P["rose"], outline=P["rose"])

    def _warn(self, text):
        now = time.monotonic()
        if self.warn and self.warn["text"] == text:
            self.warn["t"] = now
        elif not self.warn or now - self.warn["t"] > 1.5:
            self.warn = {"text": text, "t": now}

    def update_dynamic(self):
        now = time.monotonic()
        cv = self.canvas
        for s in self.strips:
            it = self.items.get(s["id"])
            if not it:
                continue
            fx0, fy0, fx1, fy1 = it["fader"]
            lvl = s["level"] if s["level"] is not None else 0.0
            if self.drag and self.drag[0] == "fader" and self.drag[1] == s["id"] and self.drag[4] is not None:
                lvl = self.drag[4]
            yy = fy1 - (fy1 - fy0) * max(0.0, min(1.0, lvl))
            cv.coords(it["fill"], fx0 + 2, yy, fx1 - 2, fy1 - 1)
            cv.coords(it["glow"], fx0 + 2, yy, fx1 - 2, yy)
            cv.coords(it["cap"], fx0 + 5, yy - 4, fx1 - 5, yy + 4)
            cv.itemconfig(it["fill"], fill="#4a3f33" if s["mute"] else P["gold"])
            db = "−∞" if lvl <= 0.0001 else f"{20 * math.log10(lvl):.1f}"
            cv.itemconfig(it["val"], text=f"{db} dB")
            m = s.get("meter") or [FLOOR] * 4
            if max(m[2], m[3]) >= -0.5:
                self.clip_t[s["id"]] = now
                if s["kind"] == "main":
                    self._warn("Hauptausgang übersteuert – Fader runter oder in den Einstellungen "
                               "„Schutz vor Übersteuern“ einschalten")
                elif s.get("gain") is not None:
                    self._warn(f"„{s['name']}“ ist zu laut – Gain runter (−) oder Auto-Gain (Namen antippen)")
                else:
                    self._warn(f"„{s['name']}“ ist zu laut – Fader runter")
            cv.itemconfig(it["name"], fill=P["rose"] if now - self.clip_t.get(s["id"], -99) < 2.5 else P["champ"])
            for k, key in enumerate(("meterA", "meterB")):
                a, b, c, d = it[key]
                frac = max(0.0, min(1.0, (m[k] - FLOOR) / -FLOOR))
                hold = max(0.0, min(1.0, (m[k + 2] - FLOOR) / -FLOOR))
                cv.coords(it[key + "_bar"], a, d - (d - b) * frac, c, d)
                cv.itemconfig(it[key + "_bar"], fill=P["emerald"] if m[k] < -12 else (P["gold2"] if m[k] < -3 else P["rose"]))
                yh = d - (d - b) * hold
                cv.coords(it[key + "_hold"], a, yh, c, yh)
        # Systemlast
        self._paint_sys()
        v = self.data.get("sys") or {}
        if v.get("xrun"):
            self._warn("Kurze Aussetzer im Ton – zu viele Effekte? Einen Hall weniger hilft meist.")
        elif v.get("hot"):
            self._warn("Der Zynthian wird sehr warm – für Luft sorgen.")
        elif v.get("volt"):
            self._warn("Zu wenig Strom – Netzteil oder Akku prüfen.")
        wi = self.warn_items
        if wi:
            show = self.warn and now - self.warn["t"] < 4.0
            try:
                cv.itemconfig(wi[0], state="normal" if show else "hidden")
                cv.itemconfig(wi[1], state="normal" if show else "hidden", text=self.warn["text"] if show else "")
                if show:
                    cv.tag_raise(wi[0])
                    cv.tag_raise(wi[1])
            except Exception:
                pass
        # Live-Leiste
        chain = self._sel_chain()
        if chain is not None and self.live_items:
            try:
                slots = [self.pf.slot_info(chain, sl) for sl in self.pf.live_slots(chain)]
                for k, bar, vt, (bx0, by0, bx1, by1) in self.live_items:
                    if k < len(slots):
                        v = max(0.0, min(1.0, float(slots[k].get("value") or 0)))
                        cv.coords(bar, bx0 + 1, by0 + 1, bx0 + 1 + (bx1 - bx0 - 2) * v, by1 - 1)
                        cv.itemconfig(vt, text=slots[k].get("text", ""))
            except Exception as e:
                log.debug(f"Live-Anzeige: {e}")

    # ------------------------------------------------------------------
    # Touch
    # ------------------------------------------------------------------

    def _hit(self, hits, x, y):
        for h in reversed(hits):
            if h[0] <= x <= h[2] and h[1] <= y <= h[3]:
                return h
        return None

    def on_press(self, ev):
        if not getattr(self, "_fokus_tippen", False):
            self.fokus_aktiv = False
        if self.mode == "splash":
            return self.stop_splash()
        if self.mode == "update":
            u = getattr(self, "upd", {})
            from . import fortschritt as fs
            if u.get("done") or u.get("error") or fs.STAND.get("fertig") or fs.STAND.get("fehler") \
                    or fs.STAND.get("hintergrund"):
                fs.ende()
                self.mode = "mix"
                self.sig = None
            return
        was_idle = self.mode == "idle"
        self._touch()
        if was_idle:
            self.stop_idle()
            return
        if self.mode == "browse":
            return self.browser_press(ev)
        if self.mode == "edit":
            return self.editor_press(ev)
        if self.mode == "more":
            return self.more_press(ev)
        if self.mode == "xy":
            return self.xy_press(ev)
        if self.mode == "fxview":
            return self.fxview_press(ev)
        if self.mode in ("track", "newtrack"):
            return self.track_press(ev)
        if self.mode == "settings":
            return self.settings_press(ev)
        if self.mode == "stick":
            return self.stick_press(ev)
        if self.mode == "lernen":
            return self.lern_press(ev)
        if self.mode == "tasten":
            return self.tasten_press(ev)
        if self.mode == "bib":
            return self.bib_press(ev)
        if self.mode == "help":
            if self.help_page == 0:
                self.help_page = 1
                self.draw_help()
            else:
                self.close_help()
            return
        if self.mode in ("autogain", "tuner", "looper"):
            return self.tool_press(ev)
        h = self._hit(self.hits, ev.x, ev.y)
        if not h:
            return
        art, cid, extra = h[4], h[5], h[6]
        if self.locked and art not in ("lock", "select", "fader", "scene", "panic", "mute", "help", "rec"):
            self._flash("Auftritts-Modus: nur Fader, Mute, Szenen und Panik – „AUFTRITT“ lang drücken beendet ihn")
            return
        if art in self.DEFER:
            # kurz tippen = wie immer (beim Loslassen) · lang drücken = Erklärung
            aid = self.canvas.after(650, lambda: self._long_press())
            self.press = [art, cid, extra, aid, time.monotonic(), False, (ev.x, ev.y)]
            if cid is not None:
                idx = self._index_of(cid)
                if idx is not None and idx != self.selected:
                    self.selected = idx
            return
        if cid is not None and art != "panic":
            idx = self._index_of(cid)
            if idx is not None and idx != self.selected:
                self.selected = idx
                self.sig = None
        b = self.bridge
        try:
            if art == "fader":
                self.drag = ["fader", cid, extra[0], extra[1], None]
                self._drag_to(ev.x, ev.y)
            elif art == "slot":
                self.drag = ["slot", cid, extra[1], extra[2], extra[0]]
                self._drag_to(ev.x, ev.y)
            elif art in ("mute", "solo"):
                b.action(cid, art)
            elif art == "preset":
                b.action(cid, "preset_next" if extra > 0 else "preset_prev")
            elif art in ("fx", "scene", "lock", "p_freeze"):
                # kurz/lang unterscheiden
                delay = {"fx": 550, "scene": 800, "lock": 900, "p_freeze": 350}[art]
                aid = self.canvas.after(delay, lambda: self._long_press())
                self.press = [art, cid, extra, aid, time.monotonic(), False]
                if art == "p_freeze":
                    chain = b._chain(cid)
                    self.press.append(self.x.is_frozen(chain))
                    self.x.set_freeze(chain, True)
                return
            elif art == "p_throw":
                b.action(cid, "throw", True)
                self.press = ["p_throw", cid, None, None, time.monotonic(), False]
                return
            elif art == "freeze":
                b.action(cid, "freeze")
            elif art == "gain":
                b.action(cid, "gain", {"step": extra})
            elif art == "gain0":
                b.action(cid, "gain", 0)
            elif art == "chanedit":
                self.open_track(cid)
                return
            elif art == "bib":
                self.open_bib()
                return
            elif art == "newtrack":
                self.open_newtrack()
                return
            elif art == "undo":
                self._run_track(lambda: b.action(None, "track_undo"), "Spur ist zurück")
                return
            elif art == "browse":
                self.open_browser(cid)
                return
            elif art == "page":
                self.selected = max(0, min(len(self.strips) - 1, (self.page + extra) * self.per_page))
            elif art == "morph":
                order = [0, 2, 4, 8, 16]
                cur = int(self.data.get("morph_beats", 4) or 0)
                b.action(None, "morph_beats", order[(order.index(cur) + 1) % len(order)] if cur in order else 4)
            elif art == "more":
                self.open_more()
                return
            elif art == "xy":
                self.open_xy(cid)
                return
            elif art == "panic":
                b.action(None, "panic")
                self._flash("Panik – alles beruhigt")
            elif art == "sysinfo":
                v = self.data.get("sys") or {}
                self._flash(f"DSP {v.get('dsp', '?')} % (Audio-Last) · CPU {v.get('cpu', '?')} % · "
                            f"{v.get('temp', '?')} °C" + (" · Aussetzer!" if v.get("xrun") else ""))
                return
            elif art == "tap":
                self.do_tap()
                return
            elif art == "fxview":
                self.open_fxview()
                return
            elif art == "help":
                self.open_help()
                return
            elif art == "rec":
                from . import helfer
                self._flash(helfer.aufnahme_umschalten(b))
                self.rec_on = helfer.aufnahme_laeuft(b)
            elif art == "empty_tpl":
                if extra == "synth":
                    self.open_synth_browser()
                    return
                tp = b.action(None, "track_templates")
                ins = [tp.get("free", 1)]
                title = {"handpan": "Handpan", "vocal": "Gesang", "instrument": "Instrument", "looper": "Looper",
                         "audio": "Eingang"}.get(extra, "Spur")

                def fertig(res, t=title):
                    self.mode = "mix"
                    self.sig = None
                    if "e" not in res and not self.settings.get("help_seen"):
                        self.canvas.after(600, lambda: self.open_help(willkommen=True))
                self.mode = "newtrack"
                self.ntrk = {"tpl": tp, "inputs": ins}
                self._run_track(lambda: b.action(None, "track_add", {"template": extra, "inputs": ins}),
                                f"{title} ist da", fertig)
                self.draw_newtrack()
                return
        except Exception as e:
            log.warning(f"ZynSimple Touch: {e}")
            self._flash(str(e))
        self.sig = None

    def _long_press(self):
        if not self.press:
            return
        art, cid, extra = self.press[0], self.press[1], self.press[2]
        self.press[5] = True
        try:
            if art in self.EXPLAIN:
                xy = self.press[6] if len(self.press) > 6 else (200, 200)
                self._show_tip(xy[0], xy[1], self.EXPLAIN[art])
                return
            if art in ("fx", "vfx"):
                self.press = None
                self.open_editor(cid, extra)
            elif art == "scene":
                self.press = None
                self.bridge.action(None, "scene_save", extra)
                self._flash(f"Szene {extra} gespeichert")
            elif art == "lock":
                self.press = None
                self.locked = not self.locked
                self._flash("Auftritts-Modus an" if self.locked else "Auftritts-Modus beendet – alles wieder bedienbar")
        except Exception as e:
            self._flash(str(e))
        self.sig = None

    def on_release(self, ev):
        if self.mode == "xy":
            self.xy_release()
        if self.mode == "fxview" and self.press and self.press[0] == "vfx":
            p, self.press = self.press, None
            try:
                self.canvas.after_cancel(p[3])
            except Exception:
                pass
            if not p[5]:
                try:
                    self.bridge.action(p[1], "fx", p[2])
                except Exception as e:
                    self._flash(str(e))
            self.fx_sig = None
            return
        self.drag = None
        self.edit_drag = None
        p, self.press = self.press, None
        if not p:
            return
        art, cid, extra, aid, t0, long_done = p[:6]
        if aid:
            try:
                self.canvas.after_cancel(aid)
            except Exception:
                pass
        try:
            if art in self.DEFER:
                if not long_done:
                    self._simple_action(art, cid, extra)
            elif art == "fx" and not long_done:
                self.bridge.action(cid, "fx", extra)
            elif art == "scene" and not long_done:
                try:
                    self.bridge.action(None, "scene_load", extra)
                except KeyError:
                    self._flash(f"Szene {extra} ist leer – lang drücken speichert")
            elif art == "lock" and not long_done:
                if not self.locked:
                    self.locked = True
                    self._flash("Auftritts-Modus: nur Fader, Mute, Szenen und Panik – lang drücken beendet ihn")
                else:
                    self._flash("Zum Beenden „AUFTRITT“ lang drücken")
            elif art == "p_throw":
                self.bridge.action(cid, "throw", False)
            elif art == "p_freeze":
                was = p[6] if len(p) > 6 else False
                chain = self.bridge._chain(cid)
                held = time.monotonic() - t0 > 0.35
                # halten = nur solange gedrückt · kurz tippen = umschalten
                if held or was:
                    self.x.set_freeze(chain, False)
        except Exception as e:
            self._flash(str(e))
        self.sig = None

    def _simple_action(self, art, cid, extra):
        b = self.bridge
        if art in ("mute", "solo"):
            b.action(cid, art)
        elif art == "preset":
            b.action(cid, "preset_next" if extra > 0 else "preset_prev")
        elif art == "freeze":
            b.action(cid, "freeze")
        elif art == "gain":
            b.action(cid, "gain", {"step": extra})
        elif art == "gain0":
            b.action(cid, "gain", 0)
        elif art == "morph":
            order = [0, 2, 4, 8, 16]
            cur = int(self.data.get("morph_beats", 4) or 0)
            b.action(None, "morph_beats", order[(order.index(cur) + 1) % len(order)] if cur in order else 4)
        self.sig = None

    def _drag_to(self, x, y):
        d = self.drag
        if not d:
            return
        try:
            if d[0] == "fader":
                v = max(0.0, min(1.0, (d[3] - y) / max(1, (d[3] - d[2]))))
                d[4] = v
                self.bridge.action(d[1], "level", v)
            elif d[0] == "slot":
                v = max(0.0, min(1.0, (x - d[2]) / max(1, (d[3] - d[2]))))
                self.bridge.action(d[1], "slot", {"i": d[4], "frac": v})
        except Exception as e:
            log.debug(f"Ziehen: {e}")
        self.update_dynamic()

    def on_motion(self, ev):
        self._touch()
        if self.mode == "edit":
            return self.editor_motion(ev)
        if self.mode == "xy":
            return self.xy_motion(ev)
        if self.drag:
            self._drag_to(ev.x, ev.y)

    def do_tap(self):
        s = self._sel_strip()
        r = self.bridge.action(s["id"] if s else None, "tap") or {}
        if r.get("taps", 0) >= 2:
            self._flash(f"Tempo {r['bpm']:g} BPM – weiter tippen verfeinert")
        else:
            self._flash("Im Takt weiter tippen …")
        # sichtbares Blinken der TAP-Taste
        try:
            x, y, w, h = self.tap_btn
            fl = self.rrect(x, y, x + w, y + h, 8, fill=P["gold"], outline="")
            tx = self.canvas.create_text(x + w / 2, y + h / 2, text=f"TAP {r.get('bpm') or ''}", font=self.f_small, fill=P["black"])
            self.canvas.after(120, lambda: (self.canvas.delete(fl), self.canvas.delete(tx)))
        except Exception:
            pass
        self.sig = None

    def _flash(self, text):
        try:
            self.set_title(text, timeout=2.5)
        except TypeError:
            try:
                self.set_title(text)
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # ⋯-Seite (selten Gebrauchtes)
    # ------------------------------------------------------------------

    def open_more(self):
        self.mode = "more"
        self.draw_more()

    def draw_more(self):
        cv = self.canvas
        cv.delete("all")
        self.more_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        cv.create_text(20, 26, anchor="w", text="Mehr", font=self.f_big, fill=P["gold"])
        try:
            from . import updater
            upd = updater.status.get("available") and updater.status.get("latest")
        except Exception:
            upd = None
        items = [("help", "? Hilfe", "erklärt Bildschirm und Tasten"),
                 ("menu", "Zynthian-Menü", "Ketten, Snapshots, Admin"),
                 ("expert", "Profi-Mischer", "der originale Zynthian-Mischer"),
                 ("newtrack", "＋ Neue Spur", "Eingang, Handpan, Gesang, Synth …"),
                 ("idle", "Bühnenbild", "Animation jetzt zeigen"),
                 ("settings", f"Update {upd} bereit" if upd else "Einstellungen", "Update, Start-Logo, Bühnenbild …"),
                 ("close", "Zurück", "")]
        if self.dj_installed:
            items.insert(0, ("dj", "♪ DJ-Pult", "Mixxx mit dem DDJ-200"))
            try:
                from . import dj as dj_
                stick_ = dj_.musik_stick()
            except Exception:
                stick_ = None
            if stick_:
                items.insert(0, ("djimport", "⇩ Musik übernehmen", f"„{stick_}“: Alben/Titel auswählen"))
            hy = getattr(self.bridge, "hybrid", None)
            if hy is not None and hy.laeuft():
                items.insert(0, ("hybrid_aus", "DJ + Instr. beenden", "Mixxx schließen · Spuren bleiben"))
                items.insert(0, ("hybrid_zeigen", "Mixxx zeigen", "zurück: beliebige Zynthian-Taste"))
                items.insert(0, ("bib", "♫ Titel laden", "Musik in Deck A oder B"))
            elif hy is not None and hy.status()["moeglich"]:
                items.insert(1, ("hybrid", "♫ DJ + Instrumente", "Mixxx im Kanal „DJ-Pult“ · Spuren laufen weiter"))
        if self.imres_installed:
            items.insert(0, ("imres", "♫ Barden Beats", "Bühne & Klangwelten im Vollbild"))
        cols = 4 if len(items) > 6 else 3
        rows = math.ceil(len(items) / cols)
        gw, gh = (W - 40) / cols, (H - 70) / rows
        for k, (art, title, sub) in enumerate(items):
            cx, cy = 20 + (k % cols) * gw, 52 + (k // cols) * gh
            gold = art in ("imres", "dj", "hybrid", "hybrid_zeigen", "djimport", "bib") or (art == "settings" and upd)
            self.rrect(cx + 5, cy + 5, cx + gw - 5, cy + gh - 5, 14, fill=P["card2"] if not gold else "#2a2014",
                       outline=P["gold"] if gold else P["line"], width=2 if gold else 1)
            cv.create_text(cx + gw / 2, cy + gh * 0.42, text=title, font=self.f_mid, fill=P["champ"],
                           width=gw - 24, justify="center")
            if sub:
                cv.create_text(cx + gw / 2, cy + gh * 0.68, text=sub, font=self.f_tiny, fill=P["tx2"],
                               width=gw - 24, justify="center")
            self.more_hits.append((cx, cy, cx + gw, cy + gh, art))

    def more_press(self, ev):
        for h in self.more_hits:
            if h[0] <= ev.x <= h[2] and h[1] <= ev.y <= h[3]:
                art = h[4]
                self.mode = "mix"
                self.sig = None
                if art == "help":
                    self.open_help()
                elif art == "menu":
                    self.zyngui.show_screen("main_menu")
                elif art == "expert":
                    self.open_expert()
                elif art == "imres":
                    from . import imres
                    threading.Thread(target=imres.system, args=("imres",), daemon=True).start()
                    self._flash("Barden Beats startet …")
                elif art == "dj":
                    from . import start_dj
                    start_dj(self.zyngui)
                elif art == "djimport":
                    return self.open_stick()
                elif art == "bib":
                    return self.open_bib()
                elif art in ("hybrid", "hybrid_zeigen", "hybrid_aus"):
                    hy = self.bridge.hybrid
                    try:
                        if art == "hybrid":
                            hy.starten()
                            self._flash("DJ + Instrumente startet – Mixxx spielt gleich im Kanal „DJ-Pult“ · "
                                        "beliebige Zynthian-Taste = zurück zum Mischer")
                        elif art == "hybrid_zeigen":
                            hy.zeigen()
                        else:
                            self._flash(hy.stoppen())
                    except Exception as e:
                        self._flash(str(e))
                elif art == "newtrack":
                    self.open_newtrack()
                elif art == "idle":
                    self.start_idle()
                elif art == "synth":
                    self.open_synth_browser()
                elif art == "settings":
                    self.open_settings()
                return

    def open_expert(self):
        self.zyngui._zs_allow_home = True
        home = "mixer" if self.bridge.vangelis else "audio_mixer"
        self.zyngui.show_screen(home)

    # ------------------------------------------------------------------
    # XY-Feld
    # ------------------------------------------------------------------

    def open_xy(self, cid):
        self.mode = "xy"
        self.xy_chain = cid
        self.xy_spring = bool(self.settings.get("xy_spring", False))
        self.edit_tick = 0
        self.draw_xy()

    def draw_xy(self):
        cv = self.canvas
        cv.delete("all")
        self.xy_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        try:
            chain = self.bridge._chain(self.xy_chain)
            x, y = self.pf.xy_pos(chain)
            name = self.bridge._name(chain)
        except Exception:
            self.mode = "mix"
            self.sig = None
            return
        side = 120
        bx0, by0, bx1, by1 = 20, 44, W - side - 20, H - 16
        self.xy_box = (bx0, by0, bx1, by1)
        self.rrect(bx0, by0, bx1, by1, 16, fill=P["card"], outline=P["gold_dim"], width=1)
        for k in range(1, 4):
            gx = bx0 + (bx1 - bx0) * k / 4
            gy = by0 + (by1 - by0) * k / 4
            cv.create_line(gx, by0 + 6, gx, by1 - 6, fill=P["line"], dash=(2, 6))
            cv.create_line(bx0 + 6, gy, bx1 - 6, gy, fill=P["line"], dash=(2, 6))
        px, py = bx0 + (bx1 - bx0) * x, by1 - (by1 - by0) * y
        self.xy_dot = []
        for r, col in ((34, "#2a2014"), (24, "#4a3618"), (15, P["gold_dim"]), (9, P["gold"]), (4, P["gold2"])):
            self.xy_dot.append((cv.create_oval(px - r, py - r, px + r, py + r, fill=col, outline=""), r))
        cv.create_text(20, 22, anchor="w", text=f"XY · {name}", font=self.f_big, fill=P["gold"])
        cv.create_text(bx1 - 10, by1 - 12, anchor="e", text="Echo →", font=self.f_small, fill=P["tx2"])
        cv.create_text(bx0 + 12, by0 + 14, anchor="w", text="↑ Raum", font=self.f_small, fill=P["tx2"])
        self.xy_lbl = cv.create_text(px, py - 42, text=f"Echo {int(x * 100)} · Raum {int(y * 100)}", font=self.f_tiny,
                                     fill=P["champ"])
        sx = W - side - 4
        def btn(yy, label, art, on=False):
            self.rrect(sx, yy, W - 10, yy + 56, 12, fill=P["gold"] if on else P["card2"], outline=P["line"])
            cv.create_text((sx + W - 10) / 2, yy + 28, text=label, font=self.f_small,
                           fill=P["black"] if on else P["champ"], width=side - 20, justify="center")
            self.xy_hits.append((sx, yy, W - 10, yy + 56, art))
        btn(44, "zurück-\nfedern", "spring", self.xy_spring)
        btn(110, "Fertig", "close")

    def xy_press(self, ev):
        for h in self.xy_hits:
            if h[0] <= ev.x <= h[2] and h[1] <= ev.y <= h[3]:
                if h[4] == "close":
                    self.mode = "mix"
                    self.sig = None
                    self._save_soon()
                elif h[4] == "spring":
                    self.xy_spring = not self.xy_spring
                    self.draw_xy()
                return
        bx0, by0, bx1, by1 = self.xy_box
        if bx0 <= ev.x <= bx1 and by0 <= ev.y <= by1:
            try:
                chain = self.bridge._chain(self.xy_chain)
                self.xy_start = self.pf.xy_pos(chain)
            except Exception:
                self.xy_start = (0, 0)
            self.edit_drag = "xy"
            self.xy_motion(ev)

    def _xy_move(self, x, y):
        bx0, by0, bx1, by1 = self.xy_box
        x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
        px, py = bx0 + (bx1 - bx0) * x, by1 - (by1 - by0) * y
        cv = self.canvas
        for item, r in getattr(self, "xy_dot", []):
            cv.coords(item, px - r, py - r, px + r, py + r)
        if getattr(self, "xy_lbl", None):
            cv.coords(self.xy_lbl, px, py - 42)
            cv.itemconfig(self.xy_lbl, text=f"Echo {int(x * 100)} · Raum {int(y * 100)}")

    def xy_motion(self, ev):
        if self.edit_drag != "xy":
            return
        bx0, by0, bx1, by1 = self.xy_box
        x = (ev.x - bx0) / max(1, bx1 - bx0)
        y = (by1 - ev.y) / max(1, by1 - by0)
        try:
            self.bridge.action(self.xy_chain, "xy", {"x": x, "y": y})
        except Exception:
            pass
        self._xy_move(x, y)

    def xy_release(self):
        if self.edit_drag == "xy" and getattr(self, "xy_spring", False):
            x, y = getattr(self, "xy_start", (0, 0))
            try:
                self.bridge.action(self.xy_chain, "xy", {"x": x, "y": y})
            except Exception:
                pass
            self._xy_move(x, y)

    # ------------------------------------------------------------------
    # Große Effekt-Ansicht: alle Kanäle, alle Effekte, große Mute-Tasten
    # ------------------------------------------------------------------

    def open_fxview(self):
        self.mode = "fxview"
        self.fx_page = 0
        self.fx_sig = None
        self.draw_fxview()

    def draw_fxview(self):
        cv = self.canvas
        cv.delete("all")
        self.fxv_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        bar_h = max(40, H // 10)
        chans = [s for s in self.strips if s["kind"] != "main"]
        per = 4
        pages = max(1, math.ceil(len(chans) / per))
        self.fx_page = max(0, min(getattr(self, "fx_page", 0), pages - 1))
        shown = chans[self.fx_page * per:self.fx_page * per + per]
        rh = (H - bar_h - 8) / per
        mw = int(W * 0.2)
        if not chans:
            cv.create_text(W / 2, (H - bar_h) / 2, text="Noch keine Kanäle", font=self.f_mid, fill=P["tx2"])
        for r, s in enumerate(shown):
            y0, y1 = 6 + r * rh, 6 + (r + 1) * rh - 6
            muted = bool(s.get("mute"))
            self.rrect(6, y0, 6 + mw, y1, 14, fill=P["rose"] if muted else P["card2"], outline=P["line"])
            cv.create_text(6 + mw / 2, y0 + (y1 - y0) * 0.36, text=self._clip_text(s["name"], mw - 12, self.f_small),
                           font=self.f_small, fill="#ffffff" if muted else P["champ"])
            cv.create_text(6 + mw / 2, y0 + (y1 - y0) * 0.7, text="STUMM" if muted else "MUTE",
                           font=self.f_mid, fill="#ffffff" if muted else P["tx2"])
            self.fxv_hits.append((6, y0, 6 + mw, y1, "vmute", s["id"], None))
            fx = s["fx"]
            n = max(1, min(6, len(fx) + 1))
            gx0 = 14 + mw
            gw = (W - gx0 - 6) / max(4, n)
            for k, f in enumerate(fx[:5]):
                x0 = gx0 + k * gw
                on = f.get("on")
                col = KIND_COL.get(f.get("kind"), P["emerald"])
                self.rrect(x0, y0, x0 + gw - 8, y1, 14, fill=col if on else P["card"],
                           outline=col, width=2 if not on else 1)
                cv.create_text(x0 + (gw - 8) / 2, y0 + (y1 - y0) * 0.4, width=gw - 20, justify="center",
                               text=self._clip_text(f["name"], (gw - 16) * 1.8, self.f_small), font=self.f_small,
                               fill=P["black"] if on else P["champ"])
                cv.create_text(x0 + (gw - 8) / 2, y0 + (y1 - y0) * 0.78, font=self.f_tiny,
                               fill="#3a2a10" if on else P["tx2"], text="AN" if on else "aus")
                self.fxv_hits.append((x0, y0, x0 + gw - 8, y1, "vfx", s["id"], f["i"]))
            if len(fx) < 5:
                x0 = gx0 + len(fx) * gw
                self.rrect(x0, y0, x0 + gw - 8, y1, 14, fill=P["bg"], outline=P["gold_dim"], dash=(4, 4))
                cv.create_text(x0 + (gw - 8) / 2, (y0 + y1) / 2, text="＋ Effekt", font=self.f_small, fill=P["gold"])
                self.fxv_hits.append((x0, y0, x0 + gw - 8, y1, "vadd", s["id"], None))
        yb = H - bar_h
        cv.create_line(8, yb + 1, W - 8, yb + 1, fill=P["gold_dim"])
        bw = max(80, W // 7)
        synths = [s for s in chans if s["kind"] == "synth"]

        def btn(xx, w, label, art, on=True, fill=None, fg=None):
            self.rrect(xx, yb + 6, xx + w, H - 4, 10, fill=fill or P["card2"], outline="")
            cv.create_text(xx + w / 2, (yb + H) / 2 + 1, text=label, font=self.f_small,
                           fill=(fg or P["champ"]) if on else P["tx2"])
            if on:
                self.fxv_hits.append((xx, yb + 6, xx + w, H - 4, art, None, None))
        btn(4, int(bw * 0.6), "◀", "vpage-", self.fx_page > 0)
        btn(8 + int(bw * 0.6), int(bw * 0.6), "▶", "vpage+", self.fx_page < pages - 1)
        cv.create_text(16 + int(bw * 1.2), (yb + H) / 2, anchor="w", font=self.f_tiny, fill=P["tx2"],
                       text="tippen = an/aus · lang = Regler")
        btn(W - 3 * bw - 12, bw, "＋ Synth", "vsynth", True, fg=P["gold"])
        if synths:
            allm = all(s.get("mute") for s in synths)
            btn(W - 2 * bw - 8, bw, "Synths laut" if allm else "Synths stumm", "vsmute", True,
                fill=P["rose"] if allm else None)
        btn(W - bw - 4, bw, "Mischer", "vclose", True, fill=P["gold"], fg=P["black"])

    def fxview_press(self, ev):
        h = self._hit(self.fxv_hits, ev.x, ev.y)
        if not h:
            return
        art, cid, extra = h[4], h[5], h[6]
        b = self.bridge
        try:
            if art == "vmute":
                b.action(cid, "mute")
            elif art == "vfx":
                aid = self.canvas.after(550, lambda: self._long_press())
                self.press = ["vfx", cid, extra, aid, time.monotonic(), False]
                return
            elif art == "vadd":
                self.open_browser(cid)
                return
            elif art == "vpage-":
                self.fx_page -= 1
            elif art == "vpage+":
                self.fx_page += 1
            elif art == "vsynth":
                self.open_synth_browser()
                return
            elif art == "vsmute":
                b.action(None, "mute_kind", {"kind": "synth"})
            elif art == "vclose":
                self.mode = "mix"
                self.sig = None
                return
        except Exception as e:
            self._flash(str(e))
        self.fx_sig = None
        self.data = b.snapshot()
        self.strips = self.data["strips"]
        self.draw_fxview()

    # ------------------------------------------------------------------
    # Effekt-Auswahl (9 Kacheln pro Seite)
    # ------------------------------------------------------------------

    def open_synth_browser(self, kanal=None, titel=None):
        items = [dict(t) for t in self.x.synth_tiles()]
        known = {t["eng"] for t in items}
        for c in self.x.all_synths():
            for it in c["items"]:
                if it["eng"] not in known:
                    items.append({"group": c["cat"], "label": it["name"], "icon": "", "eng": it["eng"]})
        self.browser = {"chain": None, "page": 0, "items": items, "busy": None, "synth": True, "kanal": kanal,
                        "titel": titel}
        self.mode = "browse"
        self.draw_browser()

    def open_browser(self, cid):
        items = [dict(t) for t in self.x.fx_tiles()]
        known = {t["eng"] for t in items}
        for c in self.x.all_fx():
            for it in c["items"]:
                if it["eng"] not in known:
                    items.append({"group": c["cat"], "label": it["name"], "icon": "", "eng": it["eng"]})
        self.browser = {"chain": cid, "page": 0, "items": items, "busy": None}
        self.mode = "browse"
        self.draw_browser()

    def close_browser(self):
        self.browser = None
        self.mode = "mix"
        self.sig = None
        self._save_soon()

    def draw_browser(self):
        cv = self.canvas
        b = self.browser
        cv.delete("all")
        self.browse_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        bar_h = max(40, H // 10)
        per = 9
        pages = max(1, math.ceil(len(b["items"]) / per))
        b["page"] = max(0, min(b["page"], pages - 1))
        shown = b["items"][b["page"] * per:b["page"] * per + per]
        try:
            name = self.bridge._name(self.bridge._chain(b["chain"])) if b["chain"] is not None else \
                f"spielt auf MIDI-Kanal {int(self.settings.get('synth_midi_chan', 0)) + 1} mit"
        except Exception:
            name = ""
        cv.create_text(16, 8 + self.f_big[1], anchor="w", font=self.f_big, fill=P["gold"],
                       text="＋ Synth" if b.get("synth") else "＋ Effekt")
        cv.create_text(16 + self.f_big[1] * 6.5, 8 + self.f_big[1], anchor="w", font=self.f_mid, fill=P["champ"], text=name)
        cv.create_text(W - 16, 8 + self.f_big[1], anchor="e", font=self.f_tiny, fill=P["tx2"],
                       text="antippen = eigener Kanal mit Fader & Effekten" if b.get("synth")
                       else "antippen = sofort einsetzen · der nächste ersetzt ihn")
        y0 = 8 + self.f_big[1] * 2 + 8
        gh = (H - bar_h - 8 - y0) / 3
        gw = (W - 16) / 3
        for k, t in enumerate(shown):
            cx, cy = 8 + (k % 3) * gw, y0 + (k // 3) * gh
            busy = b["busy"] == t["eng"]
            self.rrect(cx + 4, cy + 4, cx + gw - 4, cy + gh - 4, 14, outline=P["gold"] if busy else P["line"],
                       width=2 if busy else 1, fill="#2a2014" if busy else P["card"])
            cv.create_text(cx + gw / 2, cy + gh * 0.32, text=t["group"].upper(), font=self.f_tiny, fill=P["gold"])
            cv.create_text(cx + gw / 2, cy + gh * 0.62, text=self._clip_text(t["label"], gw * 1.7, self.f_mid),
                           font=self.f_mid if t["icon"] else self.f_small, fill=P["champ"], width=gw - 18, justify="center")
            self.browse_hits.append((cx, cy, cx + gw, cy + gh, "pick", t["eng"]))
        yb = H - bar_h
        bw = max(90, W // 6)

        def btn(xx, label, art, val=None, on=True):
            self.rrect(xx, yb + 4, xx + bw, H - 4, 10, fill=P["card2"], outline="")
            cv.create_text(xx + bw / 2, (yb + H) / 2, text=label, font=self.f_mid, fill=P["champ"] if on else P["tx2"])
            if on:
                self.browse_hits.append((xx, yb + 4, xx + bw, H - 4, art, val))
        btn(4, "◀", "bpage", -1, b["page"] > 0)
        btn(8 + bw, "▶", "bpage", 1, b["page"] < pages - 1)
        cv.create_text(16 + 2 * bw, (yb + H) / 2, anchor="w", font=self.f_small, fill=P["tx2"],
                       text=f"Seite {b['page'] + 1}/{pages}" + ("  · lädt …" if b["busy"] else "  · Drehknopf blättert"))
        btn(W - bw - 4, "Zurück", "bclose")

    def browser_press(self, ev):
        b = self.browser
        if b["busy"]:
            return
        for h in self.browse_hits:
            if h[0] <= ev.x <= h[2] and h[1] <= ev.y <= h[3]:
                art, val = h[4], h[5]
                if art == "bpage":
                    b["page"] += val
                    self.draw_browser()
                elif art == "bclose":
                    self.close_browser()
                elif art == "pick":
                    self.pick_fx(val)
                return

    def pick_fx(self, eng):
        b = self.browser
        b["busy"] = eng
        self.draw_browser()
        cid = b["chain"]
        result = {}

        synth = b.get("synth")

        def run():
            try:
                if synth:
                    kanal = b.get("kanal")
                    result["chain"] = self.x.create_synth(
                        eng, int(kanal if kanal is not None else self.settings.get("synth_midi_chan", 0)), b.get("titel"))
                else:
                    result["fx"] = self.x.try_fx(self.bridge._chain(cid), eng)
            except Exception as e:
                result["error"] = str(e)

        def wait(t):
            if t.is_alive():
                self.canvas.after(200, lambda: wait(t))
                return
            self.browser = None
            if "chain" in result:
                self.mode = "mix"
                self.sig = None
                self.strips = self.bridge.snapshot()["strips"]
                idx = self._index_of(result["chain"])
                if idx is not None:
                    self.selected = idx
                self._flash("Synth ist da – eigener Kanal, Mute unten")
            elif "fx" in result:
                self.open_editor(cid, result["fx"])
            else:
                self.mode = "mix"
                self.sig = None
                self._flash(f"Effekt: {result.get('error')}")

        t = threading.Thread(target=run, daemon=True)
        t.start()
        self.canvas.after(200, lambda: wait(t))

    # ------------------------------------------------------------------
    # Effekt-Regler / Pegel-Seite
    # ------------------------------------------------------------------

    def open_editor(self, cid, fx):
        self.press = None
        self.fxedit = {"chain": cid, "fx": fx, "page": 0}
        self.mode = "edit"
        self.edit_tick = 0
        self.edit_drag = None
        self.draw_editor()

    def close_editor(self):
        self.fxedit = None
        self.mode = "mix"
        self.sig = None
        self._save_soon()

    def _editor_params(self):
        chain = self.bridge._chain(self.fxedit["chain"])
        if self.fxedit["fx"] == "chan":
            flat = []
            g = self.bridge._ctrl(chain, "gain")
            if g is not None:
                flat.append(g)
            flat += list(self.x._input_ctrls().values())
            return self.x, chain, None, flat
        proc = self.x.find_fx(chain, self.fxedit["fx"])
        flat = [z for _, items in self.x.params(proc) for z in items]
        return self.x, chain, proc, flat

    def draw_editor(self):
        cv = self.canvas
        try:
            x, chain, proc, flat = self._editor_params()
        except Exception:
            return self.close_editor()
        cv.delete("all")
        self.edit_hits = []
        self.ed_items = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        pages = max(1, math.ceil(len(flat) / 4))
        pg = self.fxedit["page"] = max(0, min(self.fxedit["page"], pages - 1))
        shown = flat[pg * 4:pg * 4 + 4]
        self.edit_shown = shown
        pins = set()
        if proc is not None:
            pins = {sym for eng, sym in self.pf.pinned(chain) if eng == proc.eng_code}
        cv.create_text(16, 8 + self.f_big[1], anchor="w", font=self.f_big, fill=P["gold"],
                       text=(proc.get_name() if proc else "Gain & Eingang"))
        cv.create_text(W - 16, 8 + self.f_big[1], anchor="e", font=self.f_small, fill=P["champ"], text=self.bridge._name(chain))
        bar_h = max(40, H // 10)
        area_y0, area_y1 = 8 + self.f_big[1] * 2 + 10, H - bar_h - 8
        row = (area_y1 - area_y0) / 4
        for k, z in enumerate(shown):
            y = area_y0 + k * row
            lbl = getattr(z, "short_name", None) or getattr(z, "name", z.symbol)
            if proc is None:
                lbl = "Gain (Mischer)" if z.symbol == "gain" else f"Eingang Soundkarte: {getattr(z, 'name', z.symbol)}"
            cv.create_text(16, y + row * 0.28, anchor="w", font=self.f_mid, fill=P["champ"], text=f"{k + 1}   {lbl}")
            try:
                txt = str(z.get_value2label())
            except Exception:
                txt = str(z.value)
            star_w = 0
            if proc is not None:
                star_w = 44
                on = z.symbol in pins
                self.rrect(W - 16 - star_w + 4, y + row * 0.06, W - 16, y + row * 0.46, 8,
                           fill=P["gold"] if on else P["card2"], outline=P["line"])
                cv.create_text(W - 16 - star_w / 2 + 2, y + row * 0.26, text="★", font=self.f_mid,
                               fill=P["black"] if on else P["tx2"])
                self.edit_hits.append((W - 16 - star_w, y, W - 16, y + row * 0.5, "pin", k, None))
            vt = cv.create_text(W - 24 - star_w, y + row * 0.28, anchor="e", font=self.f_mid, fill=P["gold2"], text=txt)
            bx0, bx1, by0, by1 = 16, W - 16, y + row * 0.55, y + row * 0.85
            self.rrect(bx0, by0, bx1, by1, 6, fill=P["black"], outline=P["line"])
            try:
                frac = (float(z.value) - float(z.value_min)) / max(1e-9, float(z.value_max) - float(z.value_min))
            except Exception:
                frac = 0
            bar = cv.create_rectangle(bx0 + 2, by0 + 2, bx0 + 2 + (bx1 - bx0 - 4) * max(0, min(1, frac)), by1 - 2,
                                      fill=P["gold"], outline="")
            self.ed_items.append((z, vt, bar, (bx0, by0, bx1, by1)))
            self.edit_hits.append((bx0, by0 - 8, bx1, by1 + 8, "param", k, (bx0, bx1)))
        if not shown:
            cv.create_text(W / 2, (area_y0 + area_y1) / 2, font=self.f_mid, fill=P["tx2"], text="Keine Regler vorhanden.")
        y0 = H - bar_h
        bw = max(84, int(W / 6.5))

        def btn(xx, label, art, extra=None, on=True, fill=None, fg=None):
            self.rrect(xx, y0 + 4, xx + bw, H - 4, 10, fill=fill or P["card2"], outline="")
            cv.create_text(xx + bw / 2, (y0 + H) / 2, text=label, font=self.f_mid if len(label) < 11 else self.f_small,
                           fill=(fg or P["champ"]) if on else P["tx2"])
            if on:
                self.edit_hits.append((xx, y0 + 4, xx + bw, H - 4, art, None, extra))
        btn(4, "◀ Seite", "epage", -1, pg > 0)
        btn(8 + bw, "Seite ▶", "epage", 1, pg < pages - 1)
        # rechte Knöpfe von rechts nach links
        right = [("Fertig", "eclose", None, None)]
        if proc is None:
            right.append(("＋ Effekte", "ebrowse", P["gold"], P["black"]))
        elif x.is_trial(chain, self.fxedit["fx"]):
            right += [("✓ Behalten", "ekeep", P["emerald"], P["black"]), ("↺ Andere", "ebrowse", None, None)]
        else:
            armed = getattr(self, "fx_del_armed", 0) > time.monotonic()
            right.append(("Wirklich?" if armed else "Entfernen", "edel", P["rose"] if armed else None,
                          "#ffffff" if armed else P["rose"]))
        if proc is not None and x.fx_kind(proc) == "delay" and x._sync_target(proc):
            cur = x.state["sync"].get(str(proc.id))
            right.append((f"♩ {cur}" if cur else "♩ aus", "esync", P["gold"] if cur else None, P["black"] if cur else None))
        xx = W - 4
        for label, art, fill, fg in right:
            xx -= bw
            btn(xx, label, art, None, True, fill=fill, fg=fg)
            xx -= 6
        tx0 = 16 + 2 * bw
        if xx - tx0 > 60:
            cv.create_text(tx0, (y0 + H) / 2, anchor="w", font=self.f_small, fill=P["tx2"],
                           text=self._clip_text(f"{pg + 1}/{pages}" + ("  · ★ = auf die Live-Knöpfe" if proc is not None else ""),
                                                xx - tx0, self.f_small))
        self.ed_sig = self._editor_sig()

    def _editor_sig(self):
        try:
            x, chain, proc, flat = self._editor_params()
        except Exception:
            return None
        pins = tuple(self.pf.pinned(chain)) if proc is not None else ()
        sync = x.state["sync"].get(str(proc.id)) if proc is not None else None
        trial = x.is_trial(chain, self.fxedit["fx"]) if proc is not None else None
        return (self.fxedit["page"], tuple(id(z) for z in flat), pins, sync, trial, self._geom())

    def refresh_editor(self):
        """Nur Werte und Balken nachziehen – kein Neuzeichnen (sonst flackert das Bild)."""
        sig = self._editor_sig()
        if sig is None:
            return self.close_editor()
        if sig != getattr(self, "ed_sig", None) or not getattr(self, "ed_items", None):
            self.ed_sig = sig
            return self.draw_editor()
        cv = self.canvas
        for z, vt, bar, (bx0, by0, bx1, by1) in self.ed_items:
            try:
                txt = str(z.get_value2label())
            except Exception:
                txt = str(z.value)
            try:
                frac = (float(z.value) - float(z.value_min)) / max(1e-9, float(z.value_max) - float(z.value_min))
            except Exception:
                frac = 0
            if cv.itemcget(vt, "text") != txt:
                cv.itemconfig(vt, text=txt)
            cv.coords(bar, bx0 + 2, by0 + 2, bx0 + 2 + (bx1 - bx0 - 4) * max(0, min(1, frac)), by1 - 2)

    def editor_press(self, ev):
        for h in self.edit_hits:
            if h[0] <= ev.x <= h[2] and h[1] <= ev.y <= h[3]:
                art, extra = h[4], h[6]
                if art == "param":
                    self.edit_drag = (h[5], extra)
                    self.editor_motion(ev)
                elif art == "pin":
                    try:
                        z = self.edit_shown[h[5]]
                        on = self.pf.toggle_pin(self.bridge._chain(self.fxedit["chain"]), self.fxedit["fx"], z.symbol)
                        self._flash("★ liegt jetzt auf einem Live-Knopf" if on else "★ entfernt")
                    except Exception as e:
                        self._flash(str(e))
                    self.draw_editor()
                elif art == "epage":
                    self.fxedit["page"] += extra
                    self.draw_editor()
                elif art == "esync":
                    self.cycle_sync()
                elif art == "eclose":
                    self.close_editor()
                elif art == "ebrowse":
                    cid = self.fxedit["chain"]
                    self.fxedit = None
                    self.open_browser(cid)
                elif art == "ekeep":
                    _, chain, _, _ = self._editor_params()
                    self.x.keep_fx(chain)
                    self.draw_editor()
                elif art == "edel":
                    if getattr(self, "fx_del_armed", 0) > time.monotonic():
                        self.fx_del_armed = 0
                        try:
                            self.bridge.action(self.fxedit["chain"], "fx_remove", self.fxedit["fx"])
                            self._flash("Effekt entfernt")
                        except Exception as e:
                            self._flash(str(e))
                        self.close_editor()
                    else:
                        self.fx_del_armed = time.monotonic() + 3
                        self.draw_editor()
                        self.canvas.after(3100, lambda: self.mode == "edit" and self.draw_editor())
                return

    def editor_motion(self, ev):
        d = self.edit_drag
        if not d or d == "xy":
            return
        k, (bx0, bx1) = d
        try:
            z = self.edit_shown[k]
            frac = max(0.0, min(1.0, (ev.x - bx0) / max(1, bx1 - bx0)))
            v = float(z.value_min) + frac * (float(z.value_max) - float(z.value_min))
            if getattr(z, "is_integer", False) or getattr(z, "is_toggle", False) or getattr(z, "labels", None):
                v = int(round(v))
            z.set_value(v)
            self.x.mark_dirty()
        except Exception as e:
            log.debug(f"Regler: {e}")
        self.refresh_editor()

    def cycle_sync(self):
        from .extras import DIVISIONS
        x, chain, proc, _ = self._editor_params()
        order = [None] + list(DIVISIONS)
        cur = x.state["sync"].get(str(proc.id))
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "1/4"
        try:
            x.set_sync(chain, self.fxedit["fx"], nxt)
        except Exception as e:
            self._flash(str(e))
        self.draw_editor()

    # ------------------------------------------------------------------
    # Systemlast
    # ------------------------------------------------------------------

    def _paint_sys(self):
        it = getattr(self, "sys_item", None)
        if not it:
            return
        v = self.data.get("sys") or {}
        parts, col = [], P["tx2"]
        load = v.get("dsp") if v.get("dsp") is not None else v.get("cpu")
        if load is not None:
            parts.append(f"{'DSP' if v.get('dsp') is not None else 'CPU'} {load}%")
            col = P["emerald"] if load < 60 else (P["gold2"] if load < 80 else P["rose"])
        if v.get("temp") is not None:
            parts.append(f"{v['temp']}°")
            if v["temp"] >= 75:
                col = P["rose"]
        if v.get("xrun"):
            parts.append("⚠ Aussetzer")
            col = P["rose"]
        elif v.get("volt"):
            parts.append("⚡ Strom")
            col = P["rose"]
        try:
            self.canvas.itemconfig(it, text=" · ".join(parts), fill=col)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Spuren: Spur-Seite und „＋ Neue Spur“
    # ------------------------------------------------------------------

    def _run_track(self, fn, ok_text, then=None):
        """Spur-Aktion im Hintergrund (Zynthian braucht dafür ein paar Sekunden)."""
        if getattr(self, "track_busy", None):
            return
        self.track_busy = ok_text
        res = {}

        def run():
            try:
                res["r"] = fn()
            except Exception as e:
                res["e"] = str(e)

        def wait(t):
            if t.is_alive():
                self.canvas.after(150, lambda: wait(t))
                return
            self.track_busy = None
            if "e" in res:
                self._flash(f"Ging nicht: {res['e']}")
            else:
                self._flash(ok_text)
            try:
                self.data = self.bridge.snapshot()
                self.strips = self.data["strips"]
            except Exception:
                pass
            r = res.get("r")
            new = r.get("chain") if isinstance(r, dict) else None
            if new is not None:
                idx = self._index_of(new)
                if idx is not None:
                    self.selected = idx
            if then:
                then(res)
            self.sig = None
            self._redraw()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        self.canvas.after(150, lambda: wait(t))
        self._redraw()

    def open_track(self, cid):
        idx = self._index_of(cid)
        if idx is not None:
            self.selected = idx
        self.mode = "track"
        self.trk = {"chain": cid, "armed": 0}
        self.edit_tick = 0
        self.draw_track()

    def open_newtrack(self):
        self.mode = "newtrack"
        try:
            tp = self.bridge.action(None, "track_templates")
        except Exception as e:
            self._flash(str(e))
            self.mode = "mix"
            return
        self.ntrk = {"tpl": tp, "inputs": [tp.get("free", 1)]}
        self.draw_newtrack()

    def tick_track(self):
        # Spur weg (z. B. vom Handy gelöscht)? Dann zurück zum Mischer.
        if self.mode == "track":
            try:
                self.bridge._chain(self.trk["chain"])
            except Exception:
                if not getattr(self, "track_busy", None):
                    self.mode = "mix"
                    self.sig = None
                return
            sig = repr(self.bridge.tracks.info(self.trk["chain"]))
            if sig != getattr(self, "trk_sig", None):
                self.draw_track()

    def _tbtn(self, x0, y0, x1, y1, label, art, extra=None, sub=None, fill=None, fg=None, outline=None, on=True,
              font=None):
        cv = self.canvas
        self.rrect(x0, y0, x1, y1, 14, fill=fill or P["card2"], outline=outline or P["line"],
                   width=2 if outline else 1)
        f = font or self.f_mid
        if sub:
            t = cv.create_text((x0 + x1) / 2, 0, text=sub, font=self.f_tiny, width=x1 - x0 - 14, justify="center",
                               anchor="n", fill=P["tx2"])
            bb = cv.bbox(t)
            sub_h = (bb[3] - bb[1]) if bb else self.f_tiny[1] * 1.4
            total = f[1] * 1.5 + 6 + sub_h
            ty = (y0 + y1) / 2 - total / 2
            cv.create_text((x0 + x1) / 2, ty + f[1] * 0.75, text=label, font=f, width=x1 - x0 - 12, justify="center",
                           fill=(fg or P["champ"]) if on else P["tx2"])
            cv.coords(t, (x0 + x1) / 2, ty + f[1] * 1.5 + 6)
            if fg == "#ffffff":
                cv.itemconfig(t, fill="#ffe9ec")
        else:
            cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label, font=f, width=x1 - x0 - 12, justify="center",
                           fill=(fg or P["champ"]) if on else P["tx2"])
        if on:
            self.trk_hits.append((x0, y0, x1, y1, art, extra))

    def draw_track(self):
        cv = self.canvas
        try:
            info = self.bridge.tracks.info(self.trk["chain"])
        except Exception:
            self.mode = "mix"
            self.sig = None
            return
        self.trk_sig = repr(info)
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        busy = getattr(self, "track_busy", None)
        kind = {"audio": "Audio-Eingang", "synth": "Synth", "bus": "Bus", "main": "Summe"}.get(info["kind"], "Spur")
        # Kopf: Name groß, antippen = umbenennen
        cv.create_text(18, 30, anchor="w", text=self._clip_text(info["name"], W * 0.62, self.f_huge),
                       font=self.f_huge, fill=P["gold"])
        cv.create_text(20, 62, anchor="w", text=kind.upper() + ("   · " + ", ".join(info["fx"]) if info["fx"] else ""),
                       font=self.f_tiny, fill=P["tx2"])
        if info["kind"] != "main":
            self._tbtn(W - 190, 10, W - 12, 58, "✎ Umbenennen", "rename", font=self.f_small)
            self.trk_hits.append((0, 0, W - 200, 60, "rename", None))
        y = 82
        # Eingänge oder MIDI-Kanal
        if info.get("inputs") is not None:
            cv.create_text(18, y + 22, anchor="w", text="EINGANG", font=self.f_tiny, fill=P["gold"])
            n = max(2, info["n_inputs"])
            cw = min(76, (W - 130 - 8 * n) / n)
            for k in range(1, n + 1):
                on = k in info["inputs"]
                x0 = 110 + (k - 1) * (cw + 8)
                self._tbtn(x0, y, x0 + cw, y + 46, str(k), "inp", k, fill=P["gold"] if on else P["bg"],
                           fg=P["black"] if on else P["champ"], outline=None if on else P["line"])
            if not info["inputs"]:
                cv.create_text(W - 18, y + 23, anchor="e", text="kein Eingang – stumm", font=self.f_tiny, fill=P["rose"])
            else:
                dup = [f"{i} auch bei „{', '.join(info['used'][str(i)])}“" for i in info["inputs"] if str(i) in info.get("used", {})]
                if dup:
                    cv.create_text(W - 18, y + 23, anchor="e", font=self.f_tiny, fill=P["gold2"], width=W * 0.42,
                                   text=self._clip_text("Eingang " + "; ".join(dup), W * 0.8, self.f_tiny))
            y += 62
        elif info.get("midi_chan") is not None or info.get("midi_all"):
            cv.create_text(18, y + 22, anchor="w", text="MIDI-KANAL", font=self.f_tiny, fill=P["gold"])
            mc = info.get("midi_chan")
            self._tbtn(130, y, 190, y + 46, "‹", "midi", -1, font=self.f_big)
            cv.create_text(240, y + 23, text="alle" if mc is None else str(mc + 1), font=self.f_big, fill=P["champ"])
            self._tbtn(290, y, 350, y + 46, "›", "midi", 1, font=self.f_big)
            cv.create_text(370, y + 23, anchor="w", text="Keyboard auf denselben Kanal stellen", font=self.f_tiny,
                           fill=P["tx2"])
            y += 62
        # Kacheln
        bar_h = max(40, H // 10)
        gy0, gy1 = y, H - bar_h - 10
        gh = (gy1 - gy0) / 2
        gw = (W - 24) / 5
        main = info["kind"] == "main"
        armed = self.trk.get("armed", 0) > time.monotonic()
        try:
            from . import helfer
            has_loop = helfer.looper_proc(self.bridge, self.bridge._chain(self.trk["chain"])) is not None
        except Exception:
            has_loop = False
        has_gain = any(s_["id"] == self.trk["chain"] and s_.get("gain") is not None for s_ in self.strips)
        tiles = [
            ("⟳ Looper", "looper", None, "Aufnehmen · Darüber", True) if has_loop else
            ("Auto-Gain", "autogain", None, "10 s spielen → Pegel passt", has_gain and not main),
            ("Stimmgerät", "tuner", None, "für diesen Eingang", bool(info.get("inputs"))),
            ("◀ nach links", "move", -1, "Reihenfolge", info["left"] and not main),
            ("nach rechts ▶", "move", 1, "Reihenfolge", info["right"] and not main),
            ("⧉ Verdoppeln", "dup", None, "gleiche Effekte", info["can_dup"] and not main),
            ("Gain & Pegel", "gain", None, "Übersteuern? hier", True),
            ("＋ Effekt", "addfx", None, "Hall, Echo, …", not main),
            ("Effekte", "fxlist", None, f"{len(info['fx'])} in dieser Spur", bool(info["fx"])),
            ("Zynthian-Optionen", "options", None, "alles Weitere", True),
            ("Wirklich löschen?" if armed else "Spur löschen", "delete", None,
             "nochmal tippen" if armed else ("20 s rückgängig" if info.get("can_undo") else "endgültig!"), info["can_delete"]),
        ]
        for k, (label, art, extra, sub, on) in enumerate(tiles):
            x0, y0 = 12 + (k % 5) * gw, gy0 + (k // 5) * gh
            dele = art == "delete"
            self._tbtn(x0 + 4, y0 + 4, x0 + gw - 4, y0 + gh - 4, label, art, extra, sub=sub, on=on and not busy,
                       fill=(P["rose"] if armed else P["bg"]) if dele and on else None,
                       fg=("#ffffff" if armed else P["rose"]) if dele else None,
                       outline=P["rose"] if dele and on else None, font=self.f_small)
        # Leiste
        yb = H - bar_h
        cv.create_line(8, yb + 1, W - 8, yb + 1, fill=P["gold_dim"])
        if busy:
            cv.create_text(16, (yb + H) / 2, anchor="w", text=busy.replace("ist da", "…") + " – bitte warten",
                           font=self.f_small, fill=P["gold2"])
        self._tbtn(W - 170, yb + 4, W - 6, H - 4, "Fertig", "close", fill=P["gold"], fg=P["black"])

    def draw_newtrack(self):
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        tp = self.ntrk["tpl"]
        busy = getattr(self, "track_busy", None)
        cv.create_text(18, 30, anchor="w", text="＋ Neue Spur", font=self.f_huge, fill=P["gold"])
        cv.create_text(W - 18, 30, anchor="e", text="eigener Fader, Mute und Effekte", font=self.f_tiny, fill=P["tx2"])
        y = 66
        cv.create_text(18, y + 22, anchor="w", text="EINGANG", font=self.f_tiny, fill=P["gold"])
        n = max(2, tp.get("n_inputs", 2))
        cw = min(76, (W - 130 - 8 * n) / n)
        for k in range(1, n + 1):
            on = k in self.ntrk["inputs"]
            x0 = 110 + (k - 1) * (cw + 8)
            self._tbtn(x0, y, x0 + cw, y + 46, str(k), "ninp", k, fill=P["gold"] if on else P["bg"],
                       fg=P["black"] if on else P["champ"], outline=None if on else P["line"])
        used = tp.get("used") or {}
        dup = [f"{i} hört schon „{', '.join(used[str(i)])}“" for i in self.ntrk["inputs"] if str(i) in used]
        cv.create_text(W - 18, y + 23, anchor="e", font=self.f_tiny, width=W * 0.42,
                       fill=P["gold2"] if dup else P["tx2"],
                       text=self._clip_text("Eingang " + "; ".join(dup), W * 0.8, self.f_tiny) if dup
                       else "Stereo: zwei Eingänge wählen")
        bar_h = max(40, H // 10)
        gy0, gy1 = y + 62, H - bar_h - 10
        items = tp.get("templates", [])
        cols = 3 if len(items) > 4 else len(items) or 1
        rows = math.ceil(len(items) / cols) or 1
        gw, gh = (W - 24) / cols, (gy1 - gy0) / rows
        for k, t in enumerate(items):
            x0, y0 = 12 + (k % cols) * gw, gy0 + (k // cols) * gh
            sub = t["sub"]
            if t.get("plugins"):
                sub += "\n" + " · ".join(t["plugins"])
            hot = busy and busy.startswith(t["title"])
            self._tbtn(x0 + 4, y0 + 4, x0 + gw - 4, y0 + gh - 4, t["title"], "tpl", t["key"], sub=sub,
                       fill="#2a2014" if hot else None, outline=P["gold"] if hot or t["key"] == "audio" else None,
                       on=not busy, font=self.f_mid)
        yb = H - bar_h
        cv.create_line(8, yb + 1, W - 8, yb + 1, fill=P["gold_dim"])
        if busy:
            cv.create_text(16, (yb + H) / 2, anchor="w", text=busy.replace("ist da", "wird angelegt …"),
                           font=self.f_small, fill=P["gold2"])
        else:
            cv.create_text(16, (yb + H) / 2, anchor="w", text="Kachel antippen = Spur ist sofort da",
                           font=self.f_tiny, fill=P["tx2"])
        self._tbtn(W - 170, yb + 4, W - 6, H - 4, "Zurück", "close")

    def track_press(self, ev):
        h = None
        for hh in reversed(getattr(self, "trk_hits", [])):
            if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]:
                h = hh
                break
        if not h:
            return
        art, extra = h[4], h[5]
        b = self.bridge
        if art == "close":
            self.mode = "mix"
            self.sig = None
            return
        if self.mode == "newtrack":
            if art == "ninp":
                cur = self.ntrk["inputs"]
                if extra in cur:
                    if len(cur) > 1:
                        cur.remove(extra)
                else:
                    cur.append(extra)
                    if len(cur) > 2:
                        cur.pop(0)
                cur.sort()
                self.draw_newtrack()
            elif art == "tpl":
                if extra == "synth":
                    self.open_synth_browser()
                    return
                if extra == "keytar":
                    self.open_lernen()
                    return
                if extra == "beatstep":
                    from . import settings as st
                    st.save(self.settings, {"bsp_an": True})
                    try:
                        self.bridge.geraete.start()
                    except Exception:
                        pass
                    drums = bool(self.settings.get("bsp_drums"))

                    def fertig(res):
                        if "e" not in res:
                            self.mode = "mix"
                            self.sig = None
                    self._run_track(lambda: {"chain": self.x.create_beatstep(drums)},
                                    "BeatStep Pro ist da: Bass auf Kanal 1, Melodie auf Kanal 2" +
                                    (", Drums auf Kanal 10" if drums else ""), fertig)
                    return
                title = next((t["title"] for t in self.ntrk["tpl"]["templates"] if t["key"] == extra), "Spur")
                ins = list(self.ntrk["inputs"])

                def done(res):
                    if "e" not in res:
                        self.mode = "mix"
                        self.sig = None
                self._run_track(lambda: b.action(None, "track_add", {"template": extra, "inputs": ins}),
                                f"{title} ist da", done)
            return
        cid = self.trk["chain"]
        try:
            if art in ("autogain", "tuner", "looper"):
                self.open_tool(art, cid)
                return
            if art == "inp":
                b.action(cid, "track_inputs", {"toggle": extra})
                self.draw_track()
            elif art == "midi":
                info = b.tracks.info(cid)
                cur = info.get("midi_chan") or 0
                b.action(cid, "track_midi", {"chan": (cur + extra) % 16})
                self.draw_track()
            elif art == "move":
                b.action(cid, "track_move", {"dir": extra})
                self.data = b.snapshot()
                self.strips = self.data["strips"]
                idx = self._index_of(cid)
                if idx is not None:
                    self.selected = idx
                self.draw_track()
            elif art == "rename":
                self._rename(cid)
            elif art == "dup":
                self._run_track(lambda: b.action(cid, "track_dup"), "Verdoppelt", lambda r: self._after_new(r))
            elif art == "gain":
                self.open_editor(cid, "chan")
            elif art == "addfx":
                self.open_browser(cid)
            elif art == "fxlist":
                self.open_fxview()
                chans = [s_ for s_ in self.strips if s_["kind"] != "main"]
                idx = next((k for k, s_ in enumerate(chans) if s_["id"] == cid), 0)
                self.fx_page = idx // 4
                self.draw_fxview()
            elif art == "options":
                self._zyn_options(cid)
            elif art == "delete":
                if self.trk.get("armed", 0) > time.monotonic():
                    self.trk["armed"] = 0

                    def gone(res):
                        if "e" not in res:
                            self.mode = "mix"
                            self.sig = None
                    self._run_track(lambda: b.action(cid, "track_remove"), "Spur gelöscht – unten zurückholen", gone)
                else:
                    self.trk["armed"] = time.monotonic() + 3
                    self.draw_track()
                    self.canvas.after(3100, lambda: self.mode == "track" and self.draw_track())
        except Exception as e:
            self._flash(str(e))

    def _after_new(self, res):
        r = res.get("r")
        if isinstance(r, dict) and r.get("chain") is not None and self.mode == "track":
            self.trk = {"chain": r["chain"], "armed": 0}

    def _rename(self, cid):
        cur = ""
        try:
            cur = self.bridge.tracks.info(cid)["title"] or self.bridge.tracks.info(cid)["name"]
        except Exception:
            pass

        def done(title):
            try:
                self.bridge.action(cid, "track_rename", {"title": title})
            except Exception as e:
                self._flash(str(e))
            self.zyngui.show_screen("zynsimple")
            self.open_track(cid)
        try:
            self.zyngui.show_keyboard(done, cur, 32)
        except TypeError:
            self.zyngui.show_keyboard(done, cur)
        except Exception as e:
            self._flash(f"Tastatur geht nicht: {e}")

    def _zyn_options(self, cid):
        try:
            self.zyngui._zs_allow_home = True
            if cid != 0:
                self.zyngui.chain_manager.set_active_chain_by_id(cid)
            self.zyngui.screens["chain_options"].setup(cid)
            self.zyngui.show_screen("chain_options")
            self.mode = "mix"
        except Exception as e:
            self._flash(f"Zynthian-Optionen: {e}")

    # ------------------------------------------------------------------
    # Einstellungen & Update
    # ------------------------------------------------------------------

    def open_settings(self):
        self.mode = "settings"
        self.set_pick = None
        self.edit_tick = 0
        self.set_armed = {}
        try:
            from . import settings as st
            self.set_addr = st.address(self.settings)
        except Exception:
            self.set_addr = {}
        self.draw_settings()

    def tick_settings(self):
        try:
            from . import updater
            sig = repr(updater.status)
        except Exception:
            sig = None
        if sig != getattr(self, "set_sig", None):
            self.draw_settings()

    # Aufbau der Einstellungen: Reiter → Zeilen. ("set", Schlüssel, Symbol) oder ("act", Aktion, Symbol)
    SET_PAGES = [
        ("anzeige", "Anzeige", [("set", "replace_home", "⌂"), ("set", "splash", "✦"), ("set", "idle_seconds", "◐"),
                                ("set", "strip_min_width", "▥"), ("act", "s_theme", "◑"), ("set", "led_recolor", "●")]),
        ("bedienung", "Bedienung", [("set", "autosave", "↺"), ("act", "s_save", "✓"), ("set", "master_limiter", "▣"),
                                    ("set", "tonart", "♯"), ("set", "xy_spring", "✥"), ("set", "synth_midi_chan", "♪"),
                                    ("act", "s_tasten", "⌨")]),
        ("dj", "DJ-Pult", [("act", "s_dj", "♪"), ("set", "dj_auto_rec", "●"), ("act", "s_djhandy", "⌕"),
                           ("set", "dj_handpan_fx", "◎"), ("act", "s_djimport", "⇩"), ("act", "s_djordner", "▤"),
                           ("act", "s_mixxx26", "◆"), ("act", "s_stems", "≋")]),
        ("buehne", "Bühne", [("act", "s_hybrid", "♫"), ("act", "s_djimport", "⇩"), ("set", "takt", "⏱"), ("set", "start_modus", "⏻"),
                             ("act", "s_gig_merken", "✓"), ("act", "s_gig_laden", "↺"), ("act", "s_strom", "⚡")]),
        ("geraete", "Geräte", [("act", "s_keytar", "🎸"), ("set", "ton_anzeige", "♪"), ("act", "s_bsp", "🎛"),
                               ("set", "bsp_drums", "🥁")]),
        ("system", "System", [("act", "s_imres", "♫"), ("act", "s_handy", "▤"), ("set", "update_check", "⟳"),
                              ("act", "s_sichern", "⇩"), ("act", "s_zurueck", "⇧"), ("act", "s_admin", "⚙")]),
    ]

    def _set_action(self, art, now):
        """Titel, Erklärung, Knopf-Text (None = nur Info) und ob die Zeile sichtbar ist."""
        if art == "s_theme":
            try:
                from . import theme
                active = theme.status().get("active")
            except Exception:
                active = False
            armed = self.set_armed.get("theme", 0) > now
            return ("Farbschema „Glut“", "warme Farben für die ganze Zynthian-Oberfläche · sie startet dafür neu",
                    "Wirklich?" if armed else ("Ausschalten" if active else "Einschalten"), True, armed)
        if art == "s_save":
            armed = self.set_armed.get("save", 0) > now
            return ("Jetzt speichern", "Mischer, Effekte und Spuren sofort sichern",
                    "✓ Gesichert" if armed else "Speichern", True, False)
        if art == "s_dj":
            return ("DJ-Pult", "Mixxx im Vollbild mit dem DDJ-200 · zurück: BACK 3 s → System-Menü", "Starten",
                    getattr(self, "dj_installed", False), False)
        if art == "s_imres":
            return ("Barden Beats", "Bühne & Klangwelten im Vollbild · zurück: BACK 3 s → System-Menü", "Starten",
                    getattr(self, "imres_installed", False), False)
        if art == "s_handy":
            a = getattr(self, "set_addr", {}) or {}
            url = (a.get("url") or a.get("name") or "–") + ("  · mit PIN" if a.get("pin") else "")
            return ("Am Handy bedienen", f"im Browser öffnen:  {url}", None, True, False)
        if art == "s_admin":
            return ("Zynthian-Admin", "WLAN, Audio, Neustart, Ausschalten", "Öffnen", True, False)
        if art == "s_sichern":
            return ("Sicherung auf USB-Stick", "alle Einstellungen, Szenen und der Mischer als eine Datei",
                    "Sichern", True, False)
        if art == "s_zurueck":
            armed = self.set_armed.get("zurueck", 0) > now
            return ("Sicherung einspielen", "holt die neueste Sicherung vom USB-Stick zurück · startet neu",
                    "Wirklich?" if armed else "Einspielen", True, armed)
        if art in ("s_mixxx26", "s_stems"):
            try:
                from . import dj
                if not dj.eingerichtet():
                    return ("", "", None, False, False)
                if art == "s_mixxx26":
                    if dj.mixxx26_da():
                        return ("Mixxx 2.6 mit Stems", "eingebaut · bei Stem-Tracks schalten F1–F4 Drums, Bass, Melodie, Vocals",
                                None, True, False)
                    st = dj.mixxx26_stand()
                    if st["laeuft"]:
                        from . import fortschritt as fs_
                        g = [w for _, w in st["schritte"]]
                        p = 100 * (sum(g[:st["schritt"]]) + g[st["schritt"]] * st["teil"]) / sum(g)
                        return ("Mixxx 2.6 wird gebaut", f"{int(p)} % · {st['schritte'][st['schritt']][0]} · {st['detail']}",
                                "Anzeigen", True, False)
                    return ("Mixxx 2.6 mit Stems (Beta)", "einmalig auf dem Zynthian bauen · 1–2 Stunden · Internet, 6 GB frei"
                            + (f" · letzter Versuch: {st['fehler']}" if st.get("fehler") else ""), "Einbauen", True, False)
                if not dj.stems_bereit():
                    st = dj.stems_install_stand()
                    if st["laeuft"]:
                        return ("Stem-Werkzeug wird eingerichtet", st["detail"] or "läuft …", "Anzeigen", True, False)
                    return ("Stems vorbereiten", "KI-Werkzeug einrichten (≈ 1 GB, Internet) – trennt Drums, Bass, Melodie, Vocals",
                            "Einrichten", True, False)
                d = dj.stems_status()
                an = self.settings.get("dj_stems", True)
                if not an:
                    text = "ausgeschaltet"
                elif d.get("pause"):
                    text = "pausiert, solange das DJ-Pult läuft"
                elif d.get("aktuell"):
                    text = f"{int(d.get('prozent', 0))} % „{d['aktuell']}“ · {d.get('warteschlange', 1)} in der Warteschlange"
                else:
                    text = "nichts zu tun · Tracks in die Kiste „Stems vorbereiten“ ziehen"
                return ("Stems vorbereiten", text, "Anzeigen" if (an and d.get("aktuell")) else ("Pause" if an else "Weiter"),
                        True, False)
            except Exception as e:
                return ("Stems", str(e), None, True, False)
        if art == "s_tasten":
            try:
                from . import dj
                tb = dj.tasten_modul()
                n = sum(1 for m in tb.TASTEN for r in tb.liste(m) if r["geaendert"])
            except Exception:
                n = 0
            return ("Tasten belegen", "alle Tasten von Mischer, DJ-Pult und Barden Beats · jede Funktion auf jede Taste"
                    + (f" · {n} umbelegt" if n else ""), "Öffnen", True, False)
        if art == "s_keytar":
            g_, k_ = self.settings.get("keytar_geraet"), self.settings.get("keytar_kanal")
            if g_:
                return ("Keytar", f"„{g_}“, MIDI-Kanal {int(k_) + 1} · neu anlernen: Taste drücken",
                        "Neu anlernen", True, False)
            return ("Keytar anlernen", "MIDI-Kabel an den DIN-Eingang · eine Taste drücken – Kanal wird erkannt",
                    "Anlernen", True, False)
        if art == "s_bsp":
            g = getattr(self.bridge, "geraete", None)
            da = g.bsp_da() if g is not None else None
            return ("BeatStep Pro", (f"„{da}“ steckt · " if da else "per USB anstecken · ")
                    + "legt Bass (Kanal 1) und Melodie (Kanal 2) an" +
                    (" + Drums (Kanal 10)" if self.settings.get("bsp_drums") else ""), "Spuren anlegen", True, False)
        if art == "s_djhandy":
            a = getattr(self, "set_addr", {}) or {}
            url = (a.get("url") or a.get("name") or "http://zynthian.local:8090") + "/bibliothek"
            return ("Musik am Handy suchen", f"{url} · Titel antippen → A/B = ins Deck laden · ★ Favoriten",
                    None, getattr(self, "dj_installed", False), False)
        if art == "s_hybrid":
            hy = getattr(self.bridge, "hybrid", None)
            if hy is None or not getattr(self, "dj_installed", False):
                return ("", "", None, False, False)
            st_ = hy.status()
            if not st_["moeglich"]:
                return ("DJ + Instrumente", "erst einmal das DJ-Pult starten (installiert Mixxx)", None, True, False)
            if st_["an"]:
                return ("DJ + Instrumente läuft", "Mixxx spielt im Kanal „DJ-Pult“ · ⋯ → Mixxx zeigen",
                        "Beenden", True, False)
            return ("DJ + Instrumente", "Mixxx und alle Spuren gleichzeitig · Musik als Kanal im Mischer"
                    + (f" · zuletzt: {st_['fehler']}" if st_.get("fehler") else ""), "Starten", True, False)
        if art == "s_gig_merken":
            from . import helfer
            armed = self.set_armed.get("gig", 0) > now
            w = helfer.auftritt_info()
            return ("Auftritts-Stand merken", f"Spuren, Effekte, Szenen wie jetzt sichern · gemerkt: {w}" if w else
                    "Spuren, Effekte, Szenen wie jetzt sichern – vor dem Auftritt", "✓ Gemerkt" if armed else "Merken",
                    True, False)
        if art == "s_gig_laden":
            from . import helfer
            armed = self.set_armed.get("gigladen", 0) > now
            return ("Auftritts-Stand zurückholen", "falls etwas verstellt ist: alles wie beim Merken",
                    "Wirklich?" if armed else "Zurückholen", helfer.auftritt_info() is not None, armed)
        if art == "s_strom":
            from . import helfer
            if not hasattr(self, "_strom") or now - self._strom[0] > 5:
                self._strom = (now, helfer.strom())
            st_ = self._strom[1]
            if st_ is None:
                return ("Strom", "nicht messbar", None, False, False)
            if st_["jetzt"]:
                return ("⚡ Strom zu schwach!", "Netzteil (5 V / 5 A) oder Akku prüfen · ZynSimple sichert alles sofort",
                        None, True, True)
            if st_["seit_start"]:
                return ("Strom: war kurz zu schwach", "seit dem Einschalten mindestens einmal · stärkeres Netzteil nehmen",
                        None, True, False)
            return ("Strom: in Ordnung", "bei Unterspannung warnt der Zynthian und sichert alles", None, True, False)
        if art == "s_djimport":
            from . import dj
            stick = dj.musik_stick()
            return ("Musik übernehmen",
                    (f"„{stick}“ steckt – Alben und Titel auswählen" if stick else
                     "USB-Stick oder SD-Karte (Kartenleser) einstecken · Alben und Titel auswählen")
                    + " · nur Neues wird kopiert", "Auswählen", getattr(self, "dj_installed", False), False)
        if art == "s_djordner":
            a = getattr(self, "set_addr", {}) or {}
            ip = a.get("ip") or "zynthian"
            try:
                from . import dj
                an = dj.samba_an()
            except Exception:
                an = False
            if an:
                return ("Musik per WLAN", f"am PC: \\\\{ip}\\MUSIK gekauft · Benutzer musik · Passwort gekauft",
                        None, True, False)
            return ("Musik per WLAN", "WLAN-Ordner ist noch nicht eingerichtet – braucht einmal Internet",
                    "Einrichten", True, False)
        return (art, "", None, False, False)

    def draw_settings(self):
        from . import settings as st
        from . import VERSION
        cv = self.canvas
        cv.delete("all")
        self.trk_hits = []
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        try:
            from . import updater
            us = dict(updater.status)
            self.set_sig = repr(updater.status)
        except Exception:
            us = {}
        now = time.monotonic()
        page = getattr(self, "set_page", "anzeige")

        # Kopf: Titel + Fertig
        hh = max(40, int(H * 0.09))
        cv.create_text(18, hh / 2 + 2, anchor="w", text="⚙ Einstellungen", font=self.f_big, fill=P["gold"])
        self._tbtn(W - 150, 6, W - 8, hh, "✓ Fertig", "close", fill=P["gold"], fg=P["black"], font=self.f_small)

        # Update – immer sichtbar, wie „Bühne aktualisieren“ bei Barden Beats
        avail = us.get("available")
        y0, y1 = hh + 8, hh + 8 + max(64, int(H * 0.16))
        self.rrect(10, y0, W - 10, y1, 14, fill="#2a2014" if avail else P["card"],
                   outline=P["gold"] if avail else P["gold_dim"], width=2)
        if avail:
            title, sub = f"Neue Version {us.get('latest')} ist da", f"du hast {VERSION} · antippen zum Installieren, die Oberfläche startet danach neu"
        elif us.get("error"):
            title, sub = f"ZynSimple {VERSION}", "kein Internet? Update geht auch per USB-Stick (zynsimple….zip)"
        elif us.get("latest"):
            title, sub = f"ZynSimple {VERSION} – aktuell", "holt die neueste Version aus dem Internet (oder vom USB-Stick)"
        else:
            title, sub = f"ZynSimple {VERSION}", "holt die neueste Version aus dem Internet (oder vom USB-Stick)"
        bw = max(170, int(W * 0.27))
        tw = W - 50 - bw
        cv.create_text(28, y0 + (y1 - y0) * 0.36, anchor="w", text="⬇ " + title, font=self.f_mid, fill=P["champ"])
        cv.create_text(28, y0 + (y1 - y0) * 0.70, anchor="w", text=self._clip_text(sub, tw, self.f_tiny),
                       font=self.f_tiny, fill=P["tx2"])
        self._tbtn(W - 22 - bw, y0 + 9, W - 22, y1 - 9, "Jetzt aktualisieren" if avail else "Nach Updates suchen",
                   "s_update", fill=P["gold"] if avail else None, fg=P["black"] if avail else P["gold"],
                   font=self.f_small, outline=None if avail else P["gold_dim"])
        # ganze Karte antippbar
        self.trk_hits.insert(0, (10, y0, W - 10, y1, "s_update", None))

        # Reiter
        ty0, ty1 = y1 + 8, y1 + 8 + max(34, int(H * 0.08))
        n = len(self.SET_PAGES)
        tw = (W - 20) / n
        for k, (pid, ptitle, _) in enumerate(self.SET_PAGES):
            x0 = 10 + k * tw
            on = pid == page
            self._tbtn(x0 + 3, ty0, x0 + tw - 3, ty1, ptitle, "s_page", pid, fill="#2a2014" if on else P["card"],
                       fg=P["gold"] if on else P["tx2"], outline=P["gold"] if on else None, font=self.f_small)

        # Zeilen der Seite (zwei Spalten)
        rows = []
        items = {it["key"]: it for it in st.items(self.settings)}
        for kind, key, sym in next(p for p in self.SET_PAGES if p[0] == page)[2]:
            if kind == "set" and key in items:
                rows.append((kind, key, sym, items[key]))
            elif kind == "act":
                t = self._set_action(key, now)
                if t[3]:
                    rows.append((kind, key, sym, t))
        gy0, gy1 = ty1 + 8, H - 6
        per_col = max(1, math.ceil(len(rows) / 2))
        gw = (W - 20) / 2
        gh = min((gy1 - gy0) / per_col, H * 0.22)
        for k, (kind, key, sym, d) in enumerate(rows):
            col, r = k // per_col, k % per_col
            x0, yy = 10 + col * gw, gy0 + r * gh
            x1, yb = x0 + gw - 4, yy + gh - 4
            armed = kind == "act" and d[4]
            self.rrect(x0 + 2, yy, x1, yb, 12, fill=P["card2"], outline=P["rose"] if armed else P["line"],
                       width=2 if armed else 1)
            cv.create_text(x0 + 24, (yy + yb) / 2, text=sym, font=self.f_big, fill=P["gold"])
            rw = gw * (0.38 if kind == "set" and d["kind"] == "choice" else 0.30)   # rechts: Schalter / Wert / Knopf
            textw = gw - 46 - rw - 14
            if kind == "set":
                title, hint = d["title"], d["hint"] or ""
            else:
                title, hint = d[0], d[1]
            cv.create_text(x0 + 46, yy + (yb - yy) * 0.34, anchor="w", font=self.f_small, fill=P["champ"],
                           text=self._clip_text(title, textw, self.f_small))
            if hint:
                cv.create_text(x0 + 46, yy + (yb - yy) * 0.52, anchor="nw", font=self.f_tiny, fill=P["tx2"],
                               text=hint, width=textw)
            cx1 = x1 - 12
            cy = (yy + yb) / 2
            if kind == "set" and d["kind"] == "bool":
                on = bool(d["value"])
                pw, ph = min(rw * 0.62, 70), min(gh * 0.36, 30)
                px0 = cx1 - pw
                self.rrect(px0, cy - ph / 2, cx1, cy + ph / 2, 99, fill=P["gold"] if on else P["bg"], outline=P["line"])
                kr = ph / 2 - 4
                kx = cx1 - kr - 4 if on else px0 + kr + 4
                cv.create_oval(kx - kr, cy - kr, kx + kr, cy + kr, fill=P["black"] if on else P["tx2"], outline="")
                cv.create_text(px0 - 8, cy, anchor="e", text="an" if on else "aus", font=self.f_tiny,
                               fill=P["gold"] if on else P["tx2"])
                self.trk_hits.append((x0 + 2, yy, x1, yb, "s_cycle", key))
            elif kind == "set":
                cv.create_text(cx1, cy, anchor="e", text="›", font=self.f_big, fill=P["gold_dim"])
                cv.create_text(cx1 - 18, cy, anchor="e", font=self.f_small, fill=P["gold"],
                               text=self._clip_text(d["text"], rw - 20, self.f_small))
                self.trk_hits.append((x0 + 2, yy, x1, yb, "s_cycle", key))
            elif d[2]:
                bh = min(gh * 0.5, 40)
                self._tbtn(cx1 - rw, cy - bh / 2, cx1, cy + bh / 2, d[2], key,
                           fill=P["rose"] if armed else None, fg="#ffffff" if armed else P["gold"],
                           outline=None if armed else P["gold_dim"], font=self.f_tiny)
                self.trk_hits.insert(0, (x0 + 2, yy, x1, yb, key, None))
        if getattr(self, "set_pick", None):
            self._draw_picker(W, H)

    def _draw_picker(self, W, H):
        """Auswahl für lange Listen (Tonart, MIDI-Kanal): alles auf einen Blick statt 25× tippen."""
        from . import settings as st
        cv = self.canvas
        key = self.set_pick
        ch = st.choices_of(key)
        title = next((t for k, t, *_ in st.SPEC if k == key), key)
        self.trk_hits = []
        cv.delete("all")
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        self.rrect(14, 14, W - 14, H - 14, 16, fill=P["card"], outline=P["gold"], width=2)
        cv.create_text(34, 40, anchor="w", text=title, font=self.f_big, fill=P["gold"])
        self._tbtn(W - 170, 22, W - 26, 58, "✕ Abbrechen", "s_pickclose", font=self.f_small)
        cols = 6 if len(ch) > 16 else 4
        rows = math.ceil(len(ch) / cols)
        gx0, gy0, gx1, gy1 = 26, 72, W - 26, H - 26
        gw, gh = (gx1 - gx0) / cols, (gy1 - gy0) / rows
        cur = self.settings.get(key)
        for k, (val, text) in enumerate(ch):
            x0, y0 = gx0 + (k % cols) * gw, gy0 + (k // cols) * gh
            on = val == cur
            self._tbtn(x0 + 3, y0 + 3, x0 + gw - 3, y0 + gh - 3, text, "s_pickval", val,
                       fill=P["gold"] if on else None, fg=P["black"] if on else None, font=self.f_small)

    def settings_press(self, ev):
        h = None
        for hh in reversed(getattr(self, "trk_hits", [])):
            if hh[0] <= ev.x <= hh[2] and hh[1] <= ev.y <= hh[3]:
                h = hh
                break
        if not h:
            return
        art, extra = h[4], h[5]
        try:
            if art == "close":
                self.mode = "mix"
                self.sig = None
                return
            if art == "s_page":
                self.set_page = extra
                self.set_pick = None
            elif art == "s_pickval":
                from . import settings as st
                key, val = self.set_pick, extra
                self.set_pick = None
                st.save(self.settings, {key: val})
                st.apply_live(self.bridge, key)
            elif art == "s_pickclose":
                self.set_pick = None
            elif art == "s_cycle" and len(__import__("zynsimple.settings", fromlist=["x"]).choices_of(extra)) > 6:
                self.set_pick = extra
            elif art == "s_cycle":
                from . import settings as st
                st.save(self.settings, {extra: st.cycle(self.settings, extra)})
                st.apply_live(self.bridge, extra)
                if extra == "strip_min_width":
                    self.sig = None
            elif art == "s_update":
                from . import start_update
                start_update(self.zyngui)
                return
            elif art == "s_admin":
                self.mode = "mix"
                self.zyngui.show_screen("admin")
                return
            elif art == "s_dj":
                from . import start_dj
                start_dj(self.zyngui)
                return
            elif art == "s_imres":
                from . import imres
                threading.Thread(target=imres.system, args=("imres",), daemon=True).start()
                self.mode = "mix"
                self.sig = None
                self._flash("Barden Beats startet …")
                return
            elif art == "s_handy":
                pass
            elif art == "s_keytar":
                return self.open_lernen()
            elif art == "s_tasten":
                return self.open_tasten()
            elif art == "s_bsp":
                from . import settings as st_
                st_.save(self.settings, {"bsp_an": True})
                if getattr(self.bridge, "geraete", None):
                    self.bridge.geraete.start()
                drums = bool(self.settings.get("bsp_drums"))
                self.mode = "mix"
                self.sig = None
                self._run_track(lambda: {"chain": self.x.create_beatstep(drums)},
                                "BeatStep Pro ist da: Bass auf Kanal 1, Melodie auf Kanal 2" +
                                (", Drums auf Kanal 10" if drums else ""))
                return
            elif art == "s_hybrid":
                hy = self.bridge.hybrid
                if hy.laeuft():
                    self._flash(hy.stoppen())
                else:
                    self._flash(hy.starten() + " · beliebige Zynthian-Taste = zurück zum Mischer")
            elif art == "s_gig_merken":
                from . import helfer
                self._flash(helfer.auftritt_merken(self.bridge))
                self.set_armed["gig"] = time.monotonic() + 2
                self.canvas.after(2100, lambda: self.mode == "settings" and self.draw_settings())
            elif art == "s_gig_laden":
                if self.set_armed.get("gigladen", 0) > time.monotonic():
                    from . import helfer
                    self.set_armed["gigladen"] = 0
                    threading.Thread(target=lambda: self._flash(helfer.auftritt_laden(self.bridge)), daemon=True).start()
                    self._flash("Auftritts-Stand wird geladen …")
                else:
                    self.set_armed["gigladen"] = time.monotonic() + 3
                    self.canvas.after(3100, lambda: self.mode == "settings" and self.draw_settings())
            elif art == "s_djordner":
                from . import dj
                if not dj.samba_an():
                    dj.samba_einrichten()
                    self._flash("WLAN-Ordner wird eingerichtet – dauert beim ersten Mal 1–2 Minuten")
            elif art == "s_djimport":
                return self.open_stick()
            elif art == "s_mixxx26":
                from . import dj, start_aufgabe
                if not dj.mixxx26_da():
                    st = dj.mixxx26_stand()
                    if not st["laeuft"] and self.set_armed.get("m26", 0) < time.monotonic():
                        self.set_armed["m26"] = time.monotonic() + 4
                        self._flash("Dauert 1–2 Stunden, braucht Internet – zum Starten nochmal tippen")
                    else:
                        start_aufgabe(self.zyngui, "mixxx26", starten=not st["laeuft"])
                        return
            elif art == "s_stems":
                from . import dj, start_aufgabe
                from . import settings as st_
                if not dj.stems_bereit():
                    start_aufgabe(self.zyngui, "stems-einrichten", starten=not dj.stems_install_stand()["laeuft"])
                    return
                d = dj.stems_status()
                if self.settings.get("dj_stems", True) and d.get("aktuell"):
                    start_aufgabe(self.zyngui, "stems")
                    return
                st_.save_intern(self.settings, "dj_stems", not self.settings.get("dj_stems", True))
            elif art == "s_sichern":
                from . import helfer
                self._flash(helfer.sicherung_auf_stick(self.bridge))
            elif art == "s_zurueck":
                if self.set_armed.get("zurueck", 0) > time.monotonic():
                    from . import helfer
                    self._flash(helfer.sicherung_vom_stick(self.bridge))
                else:
                    self.set_armed["zurueck"] = time.monotonic() + 3
                    self.canvas.after(3100, lambda: self.mode == "settings" and self.draw_settings())
            elif art == "s_save":
                self.x.save_now("Einstellungen")
                self.set_armed["save"] = time.monotonic() + 2
                self.canvas.after(2100, lambda: self.mode == "settings" and self.draw_settings())
            elif art == "s_theme":
                if self.set_armed.get("theme", 0) > time.monotonic():
                    from . import theme
                    msg = theme.revert() if theme.status().get("active") else theme.apply()
                    self._flash(msg)
                else:
                    self.set_armed["theme"] = time.monotonic() + 3
                    self.canvas.after(3100, lambda: self.mode == "settings" and self.draw_settings())
        except Exception as e:
            self._flash(str(e))
        self.draw_settings()

    # ------------------------------------------------------------------
    # Start-Logo: TheAlmightyGoose aus dem Heldensturm
    # ------------------------------------------------------------------

    SPLASH_SECONDS = 3.2

    def start_splash(self):
        self.splash_done = True
        W, H = self._geom()
        img = None
        try:
            import os
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
            for h in (380, 300, 220):
                if h <= H * 0.66 or h == 220:
                    img = tkinter.PhotoImage(file=os.path.join(d, f"gans_{h}.png"))
                    break
        except Exception as e:
            log.warning(f"ZynSimple: Logo nicht ladbar ({e})")
        self.splash = {"t0": time.monotonic(), "img": img, "items": None}
        self.mode = "splash"
        self.draw_splash()

    def stop_splash(self):
        if self.mode != "splash":
            return
        self.mode = "mix"
        self.splash = None
        self._touch()
        self.sig = None
        self.canvas.delete("all")

    def draw_splash(self):
        sp = getattr(self, "splash", None)
        if not sp:
            return
        cv = self.canvas
        W, H = self._geom()
        t = time.monotonic() - sp["t0"]
        if t >= self.SPLASH_SECONDS:
            return self.stop_splash()
        img = sp["img"]
        ih = img.height() if img else 0
        text_h = self.f_huge[1] * 2 + self.f_small[1] * 2.2
        top = max(6, (H - ih - text_h) / 2)
        cx, cy = W / 2, top + ih * 0.5
        if sp["items"] is None:
            cv.delete("all")
            cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
            glow = [cv.create_oval(0, 0, 0, 0, fill=P["bg"], outline="") for _ in range(4)]
            rings = [cv.create_oval(0, 0, 0, 0, outline=P["bg"], width=3) for _ in range(4)]
            pic = cv.create_image(cx, cy + 30, image=img) if img else None
            name = cv.create_text(cx, top + ih + self.f_huge[1] * 1.0, text="ZynSimple", font=self.f_huge, fill=P["bg"])
            try:
                from . import VERSION
            except Exception:
                VERSION = "?"
            ver = cv.create_text(cx, top + ih + self.f_huge[1] * 1.9 + self.f_small[1], font=self.f_small,
                                 fill=P["bg"], text=f"Version {VERSION}  ·  TheAlmightyGoose")
            sp["items"] = {"rings": rings, "glow": glow, "pic": pic, "name": name, "ver": ver}
        it = sp["items"]
        ease = lambda x: 1 - (1 - max(0.0, min(1.0, x))) ** 3
        # Gans gleitet sanft nach oben
        if it["pic"]:
            cv.coords(it["pic"], cx, cy + 30 * (1 - ease(t / 0.7)))
        # warmes Glühen hinter der Gans
        R = max(ih, 120) * 0.42
        for k, g in enumerate(it["glow"]):
            r = R * (1.5 - k * 0.25) * (1 + 0.03 * math.sin(t * 3 + k))
            cv.coords(g, cx - r, cy - r, cx + r, cy + r)
            cv.itemconfig(g, fill=_mix(P["bg"], "#3a2410", ease(t / 0.8) * (0.25 + 0.18 * k)))
        # goldene Ringe laufen nach außen
        for k, rg in enumerate(it["rings"]):
            ph = (t * 0.55 + k / 4) % 1
            r = R * (0.9 + ph * 1.6)
            cv.coords(rg, cx - r, cy - r, cx + r, cy + r)
            cv.itemconfig(rg, outline=_mix(P["bg"], P["gold"], (1 - ph) * 0.55 * ease(t / 0.6)))
        # Schrift blendet ein, am Ende alles aus
        out = ease((t - (self.SPLASH_SECONDS - 0.5)) / 0.5) if t > self.SPLASH_SECONDS - 0.5 else 0
        cv.itemconfig(it["name"], fill=_mix(_mix(P["bg"], P["gold"], ease((t - 0.35) / 0.6)), P["bg"], out))
        cv.itemconfig(it["ver"], fill=_mix(_mix(P["bg"], P["champ"], ease((t - 0.7) / 0.6)), P["bg"], out))

    # ------------------------------------------------------------------
    # Update-Anzeige
    # ------------------------------------------------------------------

    def show_update(self, text, sub="", done=False, error=False):
        """Zeigt groß und animiert an, dass gerade ein Update läuft."""
        if self.mode != "update":
            self.upd_t0 = time.monotonic()
        self.mode = "update"
        self.upd = {"text": text, "sub": sub, "done": done, "error": error}

    def draw_update(self):
        from . import fortschritt as fs
        if fs.STAND.get("aktiv"):
            return self.draw_fortschritt(fs)
        cv = self.canvas
        cv.delete("all")
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        u = getattr(self, "upd", {"text": "", "sub": ""})
        t = time.monotonic() - getattr(self, "upd_t0", time.monotonic())
        cx, cy, R = W / 2, H * 0.42, min(W, H) * 0.2
        col = P["rose"] if u.get("error") else (P["emerald"] if u.get("done") else P["gold"])
        # Glut
        for k in range(5, 0, -1):
            r = R * (1.2 + k * 0.25) * (1 + 0.04 * math.sin(t * 2))
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=_mix(P["bg"], "#3a2410", 0.15 * (6 - k)), outline="")
        if u.get("done") or u.get("error"):
            cv.create_oval(cx - R, cy - R, cx + R, cy + R, outline=col, width=6)
            cv.create_text(cx, cy, text="✓" if u.get("done") else "!", font=self.f_huge, fill=col)
        else:
            # drei kreisende Bögen + pulsierender Kern
            for k, (spd, ext, wid) in enumerate(((180, 100, 6), (-120, 60, 4), (260, 40, 3))):
                rr = R * (1 - k * 0.18)
                start = (t * spd) % 360
                cv.create_arc(cx - rr, cy - rr, cx + rr, cy + rr, start=start, extent=ext, style="arc",
                              outline=_mix(col, P["gold2"], k * 0.4), width=wid)
            pr = R * 0.28 * (1 + 0.15 * math.sin(t * 5))
            cv.create_oval(cx - pr, cy - pr, cx + pr, cy + pr, fill=P["gold2"], outline="")
            # Fortschritts-Punkte
            n = int(t * 3) % 4
            for k in range(3):
                dx = (k - 1) * 22
                cv.create_oval(cx + dx - 5, H * 0.78 - 5, cx + dx + 5, H * 0.78 + 5,
                               fill=P["gold"] if k < n else P["line"], outline="")
        cv.create_text(cx, H * 0.67, text=u.get("text", ""), font=self.f_big, fill=P["champ"])
        if u.get("sub"):
            cv.create_text(cx, H * 0.87, text=u["sub"], font=self.f_small, fill=P["tx2"], width=W - 60, justify="center")

    def draw_fortschritt(self, fs):
        """Echter Fortschritt: Ring mit Prozent, Schritte mit Haken, Daten (MB, Tempo, Restzeit), letzte Meldung."""
        cv = self.canvas
        cv.delete("all")
        W, H = self._geom()
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        d = fs.als_dict()
        u = getattr(self, "upd", {})
        t = time.monotonic() - getattr(self, "upd_t0", time.monotonic())
        fehler = d.get("fehler") or (u.get("error") and u.get("sub"))
        fertig = d.get("fertig") or u.get("done")
        p = 100.0 if fertig else d.get("prozent", 0.0)
        col = P["rose"] if fehler else (P["emerald"] if fertig else P["gold"])
        # Ring links
        R = min(W * 0.17, H * 0.27)
        cx, cy = 26 + R + 10, 66 + R + 14
        for k in range(4, 0, -1):
            rr = R * (1.02 + k * 0.06) * (1 + (0.02 * math.sin(t * 2.4) if not (fertig or fehler) else 0))
            cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=_mix(P["bg"], "#3a2410", 0.14 * (5 - k)), outline="")
        cv.create_oval(cx - R, cy - R, cx + R, cy + R, outline=P["line"], width=10)
        if p > 0.2:
            cv.create_arc(cx - R, cy - R, cx + R, cy + R, start=90, extent=-min(359.9, 3.6 * p), style="arc",
                          outline=col, width=10)
        if not (fertig or fehler):
            # kleiner Lichtpunkt an der Spitze des Rings – bewegt sich nur mit dem echten Fortschritt
            a = math.radians(90 - 3.6 * p)
            px, py = cx + R * math.cos(a), cy - R * math.sin(a)
            gl = 7 + 2 * math.sin(t * 6)
            cv.create_oval(px - gl, py - gl, px + gl, py + gl, fill=P["gold2"], outline="")
        cv.create_text(cx, cy - 6, text="✓" if fertig else ("!" if fehler else f"{int(p)} %"),
                       font=(self.f_huge[0], int(self.f_huge[1] * (1.6 if (fertig or fehler) else 1.15))), fill=col)
        if not (fertig or fehler) and not d.get("hintergrund"):
            cv.create_text(cx, cy + self.f_huge[1] * 0.95, text=f"{d.get('dauer', 0)} s", font=self.f_tiny, fill=P["tx2"])
        # Schritte rechts
        sx0, sy = cx + R + 40, 70
        schritte = d.get("schritte", [])
        sh = min(44, (H * 0.62 - sy) / max(1, len(schritte)) + 10)
        for k, name in enumerate(schritte):
            yy = sy + k * sh
            erledigt = fertig or k < d.get("schritt", 0)
            jetzt = not fertig and k == d.get("schritt", 0)
            farbe = P["emerald"] if erledigt else (col if jetzt else P["line"])
            self.rrect(sx0, yy, sx0 + 30, yy + 30, 99, fill=farbe if erledigt else P["bg"], outline=farbe, width=2)
            cv.create_text(sx0 + 15, yy + 15, text="✓" if erledigt else str(k + 1), font=self.f_small,
                           fill=P["black"] if erledigt else (col if jetzt else P["tx2"]))
            cv.create_text(sx0 + 42, yy + 15, anchor="w", text=name, font=self.f_mid if jetzt else self.f_small,
                           fill=P["champ"] if (jetzt or erledigt) else P["tx2"])
            if jetzt and d.get("detail"):
                cv.create_text(sx0 + 42 + len(name) * self.f_mid[1] * 0.75 + 12, yy + 15, anchor="w",
                               text=self._clip_text(d["detail"], W - sx0 - 70 - len(name) * self.f_mid[1] * 0.75, self.f_tiny),
                               font=self.f_tiny, fill=P["tx2"])
        # Balken unten
        bx0, bx1, by = 20, W - 20, H - 86
        self.rrect(bx0, by, bx1, by + 18, 9, fill=P["black"], outline=P["line"])
        if p > 0.5:
            fx = bx0 + 2 + (bx1 - bx0 - 4) * p / 100
            self.rrect(bx0 + 2, by + 2, max(bx0 + 16, fx), by + 16, 7, fill=col, outline="")
            if not (fertig or fehler):
                gx = bx0 + ((t * 140) % max(1, fx - bx0 + 30)) - 15
                cv.create_rectangle(max(bx0 + 4, gx), by + 4, min(fx - 2, gx + 24), by + 7, fill=P["gold2"], outline="")
        # Daten und letzte Meldung
        if fehler:
            info = str(fehler)
        elif fertig:
            info = d.get("detail") or "Fertig"
        else:
            info = d.get("daten") or d.get("detail") or ""
        cv.create_text(20, by + 38, anchor="w", text=self._clip_text(info, W - 40, self.f_small), font=self.f_small,
                       fill=P["rose"] if fehler else P["champ"])
        if d.get("zeile") and not fertig:
            cv.create_text(20, by + 62, anchor="w", text=self._clip_text(d["zeile"], W - 40, self.f_tiny), font=self.f_tiny,
                           fill=P["tx2"])
        if fertig or fehler or d.get("hintergrund"):
            cv.create_text(W - 20, by + 62, anchor="e", font=self.f_tiny, fill=P["tx2"],
                           text="Antippen zum Schließen" if (fertig or fehler) else "Antippen schließt die Anzeige · läuft im Hintergrund weiter")
        # Kopf zuletzt, damit nichts darüber liegt
        cv.create_rectangle(0, 0, W, 50, fill=P["bg"], outline="")
        cv.create_text(20, 28, anchor="w", text=d.get("titel", "Update"), font=self.f_big, fill=P["gold"])
        if not fertig and not fehler and not d.get("hintergrund"):
            cv.create_text(W - 20, 28, anchor="e", text="bitte nicht ausschalten", font=self.f_tiny, fill=P["rose"])

    # ------------------------------------------------------------------
    # Bühnenbild (Ruhe-Animation)
    # ------------------------------------------------------------------

    def start_idle(self):
        self.mode = "idle"
        W, H = self._geom()
        self.anim = {"t0": time.monotonic(), "rings": [], "pulses": [], "sparks": [], "last_ring": 0,
                     "last_beat": 0, "beat_n": 0, "crystal": 0.0, "glow": 0.0}
        self.canvas.delete("all")

    def stop_idle(self):
        self.mode = "mix"
        self.anim = None
        self.sig = None
        self.draw()

    def _active(self):
        """Welche Effekte klingen gerade (in nicht stummen Kanälen)?"""
        kinds, names, frozen, tiefe = set(), [], False, 0.0
        for s in self.strips:
            if s["kind"] == "main" or s.get("mute"):
                continue
            for f in s["fx"]:
                if f.get("on"):
                    k = f.get("kind") or "other"
                    n = f["name"].lower()
                    if any(w in n for w in ("granul", "argot", "grain")):
                        k = "grain"
                    if any(w in n for w in ("chorus", "phaser", "flanger", "pulsator", "tremolo", "rotary", "pan")):
                        k = "mod"
                    kinds.add(k)
                    names.append(f["name"])
            frozen = frozen or bool(s.get("freeze"))
            if s.get("tiefe") is not None:
                tiefe = max(tiefe, s["tiefe"])
        return kinds, names, frozen, tiefe

    def draw_idle(self):
        a = self.anim
        if a is None:
            return
        cv = self.canvas
        cv.delete("all")
        W, H = self._geom()
        now = time.monotonic()
        t = now - a["t0"]
        cx, cy = W / 2, H * 0.47
        main = next((s for s in self.strips if s["kind"] == "main"), None)
        lvl = 0.0
        if main and main.get("meter"):
            lvl = max(0.0, min(1.0, (max(main["meter"][0], main["meter"][1]) - FLOOR) / -FLOOR))
        a["glow"] += (lvl - a["glow"]) * 0.15
        g = a["glow"]
        kinds, names, frozen, tiefe = self._active()

        # Glut im Hintergrund – atmet mit der Lautstärke
        cv.create_rectangle(0, 0, W, H, fill=P["bg"], outline="")
        R = min(W, H) * (0.35 + 0.35 * g)
        for k in range(7, 0, -1):
            f = k / 7
            col = _mix(P["bg"], "#5a2a0c", (1 - f) * (0.4 + 0.6 * g))
            r = R * f
            cv.create_oval(cx - r * 1.4, cy - r, cx + r * 1.4, cy + r, fill=col, outline="")

        # Hall: Ringe wie auf Wasser
        if "reverb" in kinds:
            every = 1.6 - 0.9 * tiefe
            if now - a["last_ring"] > every:
                a["last_ring"] = now
                a["rings"].append([now, 0.6 + 0.8 * tiefe])
            keep = []
            for born, life in a["rings"]:
                age = (now - born) / (4.0 * life)
                if age < 1:
                    keep.append([born, life])
                    r = 20 + age * min(W, H) * 0.75 * life
                    col = _mix(P["gold"], P["bg"], age)
                    cv.create_oval(cx - r * 1.3, cy - r, cx + r * 1.3, cy + r, outline=col, width=2)
            a["rings"] = keep

        # Delay: Lichtpulse im Takt, die verblassen
        if "delay" in kinds:
            bpm = self.x.tempo() or 100
            beat = 60.0 / bpm
            if now - a["last_beat"] > beat:
                a["last_beat"] = now
                a["beat_n"] += 1
                a["pulses"].append([now, a["beat_n"]])
            keep = []
            for born, n in a["pulses"]:
                for e in range(4):
                    age = (now - born - e * beat * 0.5) / (beat * 0.9)
                    if 0 <= age < 1:
                        side = -1 if (n + e) % 2 else 1
                        px = cx + side * (60 + e * 70)
                        r = 6 + age * 26
                        col = _mix(P["gold2"], P["bg"], age * 0.6 + e * 0.12)
                        cv.create_oval(px - r, cy - r, px + r, cy + r, outline=col, width=2)
                if now - born < beat * 3:
                    keep.append([born, n])
            a["pulses"] = keep

        # Modulation: schwingende Linien
        if "mod" in kinds:
            for k in range(3):
                pts = []
                amp = 18 + 10 * k
                for xx in range(0, W + 20, 20):
                    pts += [xx, cy + H * 0.28 + math.sin(xx / 70.0 + t * (1.2 + 0.4 * k) + k) * amp]
                cv.create_line(*pts, fill=_mix(P["purple"], P["bg"], 0.3 + 0.2 * k), width=2, smooth=True)

        # Granular / Textur: aufsteigende Funken
        if "grain" in kinds or "other" in kinds or not kinds:
            n_new = 1 + int(4 * g) if kinds else (1 if random.random() < 0.3 else 0)
            for _ in range(n_new):
                a["sparks"].append([random.uniform(W * 0.15, W * 0.85), H + 5, random.uniform(-0.6, 0.6),
                                    random.uniform(1.0, 2.6), random.uniform(0.7, 1.0)])
            keep = []
            for sp in a["sparks"]:
                sp[0] += sp[2] + math.sin(t * 2 + sp[1] / 40) * 0.4
                sp[1] -= sp[3]
                sp[4] -= 0.008
                if sp[1] > -5 and sp[4] > 0:
                    keep.append(sp)
                    col = _mix(P["bg"], "#ffb347", sp[4])
                    cv.create_oval(sp[0] - 2, sp[1] - 2, sp[0] + 2, sp[1] + 2, fill=col, outline="")
            a["sparks"] = keep[-160:]

        # Freeze: Kristalle wachsen
        a["crystal"] = min(1.0, a["crystal"] + 0.02) if frozen else max(0.0, a["crystal"] - 0.04)
        if a["crystal"] > 0:
            L = a["crystal"]
            for (ox, oy) in ((0, 0), (W, 0), (0, H), (W, H)):
                base = math.atan2(cy - oy, cx - ox)
                for k in range(7):
                    ang = base + (k - 3) * 0.16
                    ln = (60 + 24 * (k % 3)) * L * 2.2
                    ex, ey = ox + math.cos(ang) * ln, oy + math.sin(ang) * ln
                    col = _mix(P["bg"], P["ice"], 0.18 + 0.32 * L)
                    cv.create_line(ox, oy, ex, ey, fill=col, width=2)
                    mx, my = ox + math.cos(ang) * ln * 0.6, oy + math.sin(ang) * ln * 0.6
                    for s2 in (-0.6, 0.6):
                        cv.create_line(mx, my, mx + math.cos(ang + s2) * ln * 0.25, my + math.sin(ang + s2) * ln * 0.25,
                                       fill=col, width=1)

        # Schrift
        cv.create_text(W / 2, H * 0.47, text="✦", font=self.f_huge, fill=_mix(P["gold_dim"], P["gold2"], g))
        sc = self.data.get("last_scene")
        bpm = self.x.tempo()
        info = "   ·   ".join(v for v in (f"Szene {sc}" if sc else "", f"{bpm:g} BPM" if bpm else "",
                                          "FREEZE" if frozen else "") if v)
        if info:
            cv.create_text(W / 2, 30, text=info, font=self.f_small, fill=P["gold"])
        if names:
            cv.create_text(W / 2, H - 46, text="  ·  ".join(dict.fromkeys(names))[:90], font=self.f_small, fill=P["champ"])
        cv.create_text(W / 2, H - 20, text="antippen oder Knopf drehen, um zurückzukehren", font=self.f_tiny, fill=P["tx2"])

    # ------------------------------------------------------------------
    # Drehgeber
    # ------------------------------------------------------------------

    def _mixxx_weg(self):
        """Hybrid: Ist Mixxx vorne, holt jede Zynthian-Taste/jeder Regler zuerst den Mischer zurück."""
        hy = getattr(self.bridge, "hybrid", None)
        if hy is not None and hy.vorne:
            try:
                hy.verstecken()
            except Exception:
                hy.vorne = False
            self._touch()
            self.sig = None
            return True
        return False

    def zynpot_cb(self, i, dval):
        # Drücken + Drehen: das Loslassen danach darf nichts auslösen (kein Ansichtswechsel, kein Klick)
        try:
            if self.zyngui.zynpot_pr_state[i] > 0:
                self.zyngui.zynpot_pr_state[i] += 1
        except Exception:
            pass
        if self._mixxx_weg():
            return True
        if self.mode == "splash":
            self.stop_splash()
            return True
        was_idle = self.mode == "idle"
        self._touch()
        if was_idle:
            self.stop_idle()
            return True
        try:
            role = list(cfg.layout["ctrl_order"]).index(i)
        except Exception:
            role = i
        if self.mode == "browse":
            if not self.browser["busy"]:
                self.browser["page"] += 1 if dval > 0 else -1
                self.draw_browser()
            return True
        if self.mode == "edit":
            try:
                x, chain, proc, _ = self._editor_params()
                if role < len(self.edit_shown):
                    x.nudge_param(proc, self.edit_shown[role], dval)
                    self.refresh_editor()
            except Exception as e:
                log.debug(f"Regler: {e}")
            return True
        if self.mode in self.FOKUS_MODES:
            self.fokus_linear(1 if dval > 0 else -1)
            return True
        if self.mode in ("xy", "fxview", "update", "help"):
            return True
        if self.locked:
            return True
        chain = self._sel_chain()
        if chain is None:
            return True
        try:
            # Die vier Knöpfe = die vier Live-Regler rechts
            self.pf.nudge_slot(chain, role, dval)
            self.update_dynamic()
        except Exception as e:
            log.warning(f"ZynSimple Drehgeber: {e}")
        return True

    def zynpot_abs(self, i, val):
        return True

    # ------------------------------------------------------------------
    # Tasten: die 20 Pads des V5 (und die klassischen 4 Tasten)
    # ------------------------------------------------------------------

    def _pad_role_roh(self, i):
        try:
            acts = cfg.custom_switch_ui_actions[i - 4]
        except Exception:
            return None
        if not acts:
            return None
        txt = " ".join(str(v) for v in acts.values() if v).upper()
        m = re.search(r"PROGRAM_CHANGE\s+(\d)", txt)
        if m:
            return f"F{m.group(1)}"
        if re.search(r"(^|\s)TEMPO(\s|$)", txt):
            return "TAP"
        for key, role in (("TOGGLE_RECORD", "REC"), ("TOGGLE_PLAY", "PLAY"), ("ARROW_UP", "UP"),
                          ("ARROW_DOWN", "DOWN"), ("ARROW_LEFT", "LEFT"), ("ARROW_RIGHT", "RIGHT")):
            if key in txt:
                return role
        if re.search(r"(^|\s)STOP(\s|$)", txt):
            return "STOP"
        if str(acts.get("S") or "").strip().upper().split(" ")[0] == "BACK":
            return "BACK"
        return None

    def _pad_role(self, i):
        """Rolle der Taste – mit eigener Tastenbelegung (Einstellungen → Bedienung → Tasten belegen)."""
        r = self._pad_role_roh(i)
        if r is None or r == "BACK":
            return r
        try:
            from . import dj
            f = dj.tasten_modul().funktion("mischer", "TEMPO" if r == "TAP" else r)
            return "TAP" if f == "TEMPO" else f
        except Exception:
            return r

    def _led(self, rolle):
        """LED der Taste, auf der die Funktion gerade liegt."""
        try:
            from . import dj
            tb = dj.tasten_modul()
            return tb.LED_NR[tb.taste("mischer", rolle)]
        except Exception:
            return self.LED_INDEX[rolle]

    def switch(self, i, t):
        if self._mixxx_weg():
            self._schluck = None if t in ("S", "B", "L") else i   # Druck und Loslassen gehören zusammen
            return True
        if getattr(self, "_schluck", None) == i and t in ("S", "B", "L"):
            self._schluck = None
            return True
        if self.mode == "splash":
            if t == "P":
                self.stop_splash()
            return True
        if i < 4:
            if self.mode == "idle":
                self._touch()
                self.stop_idle()
                return True
            return False
        role = self._pad_role(i)
        if role is None:
            return self._fremde_taste(i, t)
        if role == "BACK":
            # BACK: kurz = eine Ebene zurück (überall), 3 s halten = System-Menü
            if t == "P":
                self._back_abbrechen()
                self._back_timer = self.canvas.after(int(self.BACK_HALTEN_S * 1000), self._back_lang)
                return True
            war_lang = getattr(self, "_back_lang_erledigt", False)
            self._back_abbrechen()
            if war_lang:
                return True
            self._touch()
            if self.mode in ("mix", "splash"):
                return False             # im Mischer: wie gewohnt (Zynthian)
            self.back_action()
            return True
        if self.mode == "idle":
            if t == "P":
                self._touch()
                self.stop_idle()
            return True
        if self.mode in self.FOKUS_MODES and role in ("UP", "DOWN", "LEFT", "RIGHT"):
            if t == "P":
                self.fokus_richtung(role)
            return True
        if self.mode == "bib" and role in ("F1", "F2", "F3", "F4"):
            if t == "S":
                self._bib_taste(role)
            return True
        if self.mode == "help" and t == "P":
            self.on_press(type("E", (), {"x": 0, "y": 0})())
            return True
        if self.mode != "mix":
            # In den Unterseiten bleiben die Pfeile normale Navigation
            if role in ("LEFT", "RIGHT") and self.mode == "browse" and t == "P":
                self.browser["page"] += -1 if role == "LEFT" else 1
                self.draw_browser()
                return True
            if role in ("LEFT", "RIGHT") and self.mode == "edit" and t == "P":
                self.fxedit["page"] += -1 if role == "LEFT" else 1
                self.draw_editor()
                return True
            return False
        self._touch()
        chain = self._sel_chain()
        b = self.bridge
        try:
            alt = bool(self.zyngui.get_alt_mode())
        except Exception:
            alt = False
        if self.locked and not (role == "STOP" or role in ("LEFT", "RIGHT") or (alt and role.startswith("F"))):
            if t == "S":
                self._flash("Auftritts-Modus – nur Panik, Szenen (ALT+F) und Kanalwahl")
            return True
        try:
            if role.startswith("F"):
                n = int(role[1:])
                if alt:                                   # ALT + F1–F4 = Szenen
                    if t == "P":
                        self.pad_t[i] = time.monotonic()
                    elif t in ("B", "L"):
                        b.action(None, "scene_save", n)
                        self._flash(f"Szene {n} gespeichert")
                    elif t == "S":
                        try:
                            b.action(None, "scene_load", n)
                        except KeyError:
                            self._flash(f"Szene {n} ist leer – ALT + F{n} lang drücken speichert")
                elif chain is not None:                   # F1–F4 = Effekte 1–4 des Kanals
                    idx = n - 1
                    if idx < len(b._fx_procs(chain)):
                        if t == "S":
                            b.action(chain.chain_id, "fx", idx)
                            try:
                                fxs = b.snapshot(meters=False)
                                st_ = next(x_ for x_ in fxs["strips"] if x_["id"] == chain.chain_id)["fx"][idx]
                                self._flash(f"F{n}: {st_['name']} {'an' if st_['on'] else 'aus'}  ·  lang drücken = Regler")
                            except Exception:
                                pass
                        elif t in ("B", "L"):
                            self.open_editor(chain.chain_id, idx)
                    elif t == "S":
                        self.open_browser(chain.chain_id)
            elif role == "REC" and chain is not None:     # ❄ Freeze: tippen = an/aus, halten = solange gedrückt
                if t == "P":
                    self.pad_t[i] = (time.monotonic(), self.x.is_frozen(chain))
                    self.x.set_freeze(chain, True)
                else:
                    t0, was = self.pad_t.pop(i, (time.monotonic(), False))
                    if was or time.monotonic() - t0 > 0.35:
                        self.x.set_freeze(chain, False)
            elif role == "PLAY" and alt:                  # ALT + PLAY: ♫ Titel laden (DJ + Instrumente)
                if t == "S":
                    self.open_bib()
                    return True
            elif role == "PLAY" and chain is not None:    # ↯ Echo-Wurf: solange gedrückt
                b.action(chain.chain_id, "throw", t == "P")
            elif role == "TAP":                           # Tap-Tempo auf der METRONOM-Taste
                if t == "P":
                    self.do_tap()
            elif role == "STOP":                          # Panik
                if t == "S":
                    b.action(None, "panic")
                    self._flash("Panik – alles beruhigt")
            elif role in ("LEFT", "RIGHT"):
                if t == "P" and self.strips:
                    self.selected = max(0, min(len(self.strips) - 1, self.selected + (-1 if role == "LEFT" else 1)))
            elif role in ("UP", "DOWN") and chain is not None:
                if t == "P":
                    self.pf.nudge_slot(chain, 0, 3 if role == "UP" else -3)   # Tiefe
        except Exception as e:
            self._flash(str(e))
        self.sig = None
        return True

    def _fremde_taste(self, i, t):
        """Tasten, die sonst die Zynthian-Oberfläche bedient (MENU, MIXER, CTRL, ZS3, PAD): in ZynSimple
        wechseln sie nicht mehr die Ansicht. MENU öffnet ⋯ – nur von dort geht es in andere Ansichten.
        ALT und die Drehknöpfe bleiben beim Zynthian."""
        try:
            acts = cfg.custom_switch_ui_actions[i - 4] or {}
        except Exception:
            return False
        txt = " ".join(str(v) for v in acts.values() if v).upper()
        if not txt or "ALT" in txt or "ZYNPOT" in txt:
            return False
        if t != "S":
            return True
        self._touch()
        if re.search(r"(^|\s)MENU(\s|$)", txt):
            if self.mode == "more":
                self.mode = "mix"
                self.sig = None
            else:
                self._mixxx_weg()
                self.mode = "more"
                self.fokus_i = 0
                self.draw_more()
            return True
        hy = getattr(self.bridge, "hybrid", None)
        if re.search(r"MIXER", txt) and hy is not None and hy.laeuft() and self.mode == "mix":
            self.open_bib()                               # bei DJ + Instrumente: MIXER = ♫ Titel laden
            return True
        self._flash("Diese Taste hat hier keine Aufgabe · andere Ansicht: MENU (⋯)")
        return True

    def cuia_v5_zynpot_switch(self, params):
        """Drehknopf drücken (V5). In ZynSimple nur Funktionen der aktuellen Seite – nie eine andere Ansicht
        (der Zynthian würde sonst z. B. bei langem Drücken das XY-Feld oder den Profi-Mischer öffnen)."""
        try:
            i, t = int(params[0]), str(params[1]).upper()
        except Exception:
            return True
        if self._mixxx_weg():
            return True
        self._touch()
        if t not in ("S", "B"):
            return True                                   # lang gedrückt: bewusst nichts
        if self.mode == "splash":
            self.stop_splash()
        elif self.mode == "idle":
            self.stop_idle()
        elif self.mode in self.FOKUS_MODES:
            self.fokus_ausloesen()                        # wie SEL: das Ausgewählte antippen
        elif self.mode in ("edit", "help", "update", "browse", "xy", "fxview"):
            if i == 3:
                self.switch_select(t)
        elif self.mode == "mix":
            ch = self._sel_chain()
            if ch is not None:
                try:
                    sl = self.pf.slot_info(ch, self.pf.live_slots(ch)[i])
                    self._flash(f"Regler {i + 1}: {sl['name']} {sl.get('text', '')}".strip())
                except Exception:
                    pass
        return True

    def _back_lang(self):
        self._back_timer = None
        self._back_lang_erledigt = True
        from . import system_menue
        system_menue(self.zyngui)

    def _back_abbrechen(self):
        tm = getattr(self, "_back_timer", None)
        if tm:
            try:
                self.canvas.after_cancel(tm)
            except Exception:
                pass
        self._back_timer = None
        self._back_lang_erledigt = False

    def switch_select(self, t="S"):
        self._touch()
        if self.mode == "idle":
            self.stop_idle()
            return True
        if self.mode == "edit":
            if t == "S":
                self.fxedit["page"] += 1
                pages = max(1, math.ceil(len(self._editor_params()[3]) / 4))
                if self.fxedit["page"] >= pages:
                    self.fxedit["page"] = 0
                self.draw_editor()
            else:
                self.close_editor()
            return True
        if self.mode == "help":
            if t == "S":
                self.on_press(type("E", (), {"x": 0, "y": 0})())
            else:
                self.close_help()
            return True
        if self.mode in self.FOKUS_MODES:
            if t == "S":
                self.fokus_ausloesen()
            else:
                self.back_action()
            return True
        if self.mode == "update":
            self.on_press(type("E", (), {"x": 0, "y": 0})())
            return True
        if self.mode in ("browse", "xy"):
            self.mode = "mix"
            self.browser = None
            self.sig = None
            return True
        s = self._sel_strip()
        if not s or self.locked:
            return True
        if t == "S":
            self.bridge.action(s["id"], "mute")
        elif t == "B":
            if s["solo"] is not None:
                self.bridge.action(s["id"], "solo")
        elif t == "L":
            self._flash("Profi-Mischer und Zynthian-Menü: MENU oder ⋯")
        return True

    def select(self, index=None):
        if index is not None and self.strips:
            self.selected = max(0, min(len(self.strips) - 1, int(index)))

    def arrow_left(self):
        self.selected = max(0, self.selected - 1)

    def arrow_right(self):
        self.selected = min(max(0, len(self.strips) - 1), self.selected + 1)

    def arrow_up(self, nudge=1):
        c = self._sel_chain()
        if c is not None:
            self.pf.nudge_slot(c, 0, 3)

    def arrow_down(self, nudge=-1):
        c = self._sel_chain()
        if c is not None:
            self.pf.nudge_slot(c, 0, -3)

    def back_action(self):
        self._touch()
        if self.mode == "splash":
            self.stop_splash()
        elif self.mode == "idle":
            self.stop_idle()
        elif self.mode == "browse":
            self.close_browser()
        elif self.mode == "edit":
            self.close_editor()
        elif self.mode == "help":
            self.close_help()
        elif self.mode in ("autogain", "tuner", "looper"):
            self.close_tool()
        elif self.mode == "stick":
            self._stick_hoch()
        elif self.mode == "lernen":
            self.lern_ab()
        elif self.mode == "bib":
            self.mode = "mix"
            self.sig = None
        elif self.mode == "tasten":
            if self.tst.get("wahl"):
                self.tst["wahl"] = None
                self.draw_tasten()
            else:
                self.mode = "settings"
                self.draw_settings()
        elif self.mode in ("more", "xy", "fxview", "track", "newtrack", "settings"):
            self.mode = "mix"
            self.sig = None
        return True

    def toggle_midi_learn(self, *a, **k):
        pass

    def midi_learn_options(self, *a, **k):
        pass

    def midi_unlearn_action(self, *a, **k):
        pass

    # ------------------------------------------------------------------
    # LEDs der Pads (solange dieser Bildschirm offen ist)
    # ------------------------------------------------------------------

    LED_INDEX = {"F1": 4, "F2": 11, "F3": 12, "F4": 19, "REC": 8, "STOP": 9, "PLAY": 10,
                 "UP": 14, "LEFT": 16, "DOWN": 17, "RIGHT": 18}

    def _hook_leds(self):
        ws = getattr(self.zyngui, "wsleds", None)
        if ws is None or getattr(ws, "_zs_leds", False) or not hasattr(ws, "update_wsleds"):
            return
        orig = ws.update_wsleds
        screen = self

        def update_wsleds(*a, **k):
            orig(*a, **k)
            try:
                if screen.shown and screen.zyngui.current_screen == "zynsimple":
                    screen.paint_leds(ws)
            except Exception as e:
                log.debug(f"LEDs: {e}")

        ws.update_wsleds = update_wsleds
        ws._zs_leds = True

    def paint_leds(self, ws):
        if not getattr(ws, "wsleds", None) or getattr(ws, "num_leds", 0) < 20:
            return
        col = lambda r, g, b: ws.create_color(r, g, b)
        dim = col(28, 12, 2)
        try:
            alt = bool(self.zyngui.get_alt_mode())
        except Exception:
            alt = False
        s = self._sel_strip()
        kinds_rgb = {"reverb": (200, 120, 10), "delay": (220, 170, 10), "comp": (150, 90, 40), "eq": (170, 70, 20),
                     "other": (120, 0, 120)}
        for n in range(1, 5):
            led = self._led(f"F{n}")
            if alt:
                sc = (self.data.get("scenes") or {}).get(str(n + 0))
                if self.data.get("last_scene") == str(n):
                    ws.wsleds[led] = col(230, 150, 20)
                elif sc:
                    ws.wsleds[led] = col(110, 0, 110)
                else:
                    ws.wsleds[led] = dim
            elif s and n - 1 < len(s["fx"]):
                f = s["fx"][n - 1]
                rgb = kinds_rgb.get(f.get("kind"), (0, 160, 60))
                ws.wsleds[led] = col(*rgb) if f.get("on") else col(rgb[0] // 8, rgb[1] // 8, rgb[2] // 8)
            else:
                ws.wsleds[led] = dim
        ws.wsleds[self._led("REC")] = col(170, 150, 120) if s and s.get("freeze") else col(40, 30, 20)
        ws.wsleds[self._led("PLAY")] = col(230, 170, 20) if s and s.get("throw") else col(40, 26, 4)
        ws.wsleds[self._led("STOP")] = col(90, 0, 10)
        for k in ("UP", "DOWN", "LEFT", "RIGHT"):
            ws.wsleds[self._led(k)] = col(60, 35, 5)
        if self.mode == "idle" and self.anim:
            # Im Bühnenbild glimmen die Pads mit der Lautstärke
            g = self.anim.get("glow", 0)
            for k, led in enumerate((4, 11, 12, 19, 8, 9, 10)):
                f = max(0.0, min(1.0, g * 1.4 - k * 0.08))
                ws.wsleds[led] = col(int(40 + 190 * f), int(12 + 110 * f * f), int(2 + 30 * f * f * f))


# Fokus-Rahmen nach jedem Zeichnen der Seiten, die sich mit den Zynthian-Tasten bedienen lassen
def _mit_fokus(name):
    orig = getattr(zynsimple_screen, name)

    def neu(self, *a, **k):
        r = orig(self, *a, **k)
        try:
            self._fokus_zeichnen()
        except Exception:
            pass
        return r
    neu.__name__ = name
    setattr(zynsimple_screen, name, neu)


for _n in ("draw_more", "draw_track", "draw_newtrack", "draw_tool", "draw_settings", "draw_stick", "draw_lernen", "draw_tasten", "draw_bib"):
    _mit_fokus(_n)
