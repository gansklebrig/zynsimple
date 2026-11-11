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

    def show(self):
        super().show()
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
            if self.mode == "mix":
                idle_s = float(self.settings.get("idle_seconds", 45) or 0)
                if idle_s and time.monotonic() - self.last_input > idle_s and not self.drag:
                    self.start_idle()
                else:
                    sig = self._signature()
                    if sig != self.sig:
                        self.sig = sig
                        self.draw()
                    self.update_dynamic()
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
            elif self.mode == "update":
                self.draw_update()
                delay = 40
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
        return repr([(s["id"], s["name"], s["mute"], s["solo"], s["preset"] and s["preset"]["name"], s.get("gain"),
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

        if not n:
            cv.create_text(mix_w / 2, strip_h / 2, fill=P["tx2"], font=self.f_mid, justify="center",
                           text="Noch keine Kanäle.\nRechts auf ＋ tippen")
        for k, s in enumerate(visible):
            self._draw_strip(s, first + k, k * sw + 4, 4, sw - 6, strip_h - 6)

        # ＋ Neue Spur
        ax0, ax1 = mix_w + 1, mix_w + add_w - 3
        self.rrect(ax0, 4, ax1, strip_h - 2, 12, fill=P["bg"], outline=P["gold_dim"], dash=(4, 4))
        cv.create_text((ax0 + ax1) / 2, strip_h * 0.42, text="＋", font=self.f_huge, fill=P["gold"])
        cv.create_text((ax0 + ax1) / 2, strip_h * 0.62, text="S\nP\nU\nR", font=self.f_tiny, fill=P["gold"],
                       justify="center")
        self.hits.append((ax0, 4, ax1, strip_h - 2, "newtrack", None, None))
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
        mb = self.data.get("morph_beats", 4)
        lbl = "hart" if not mb else f"↝ {int(mb)}"
        self._button(sx + 4, y + pad + 2, int(sbw * 1.3), h - 2 * pad - 2, lbl, True, "morph", None, None,
                     fill=P["card2"], fg=P["gold2"] if self.data.get("morph") else P["champ"], font=self.f_small)
        tx = sx + 12 + int(sbw * 1.3)
        bpm = self.data.get("tempo")
        self.tap_btn = (tx, y + pad + 2, int(sbw * 2.1), h - 2 * pad - 2)
        self._button(tx, y + pad + 2, int(sbw * 2.1), h - 2 * pad - 2, f"TAP {bpm:g}" if bpm else "TAP", True, "tap",
                     None, None, fill=P["bg"], fg=P["gold"], outline=P["gold"], font=self.f_small)
        # rechts: Effekte, Sperre, Mehr
        mw = max(54, int(W * 0.08))
        ew = int(mw * 1.35)
        self._button(W - 3 * (pad + mw) - (ew - mw), y + pad + 2, ew, h - 2 * pad - 2, "Effekte", True, "fxview",
                     None, None, fill=P["card2"], fg=P["gold"], outline=P["gold_dim"], font=self.f_small)
        self._button(W - pad - mw, y + pad + 2, mw, h - 2 * pad - 2, "⋯", True, "more", None, None,
                     font=self.f_big, fg=P["gold"])
        self._button(W - 2 * (pad + mw), y + pad + 2, mw, h - 2 * pad - 2,
                     "gesperrt" if self.locked else "Sperre", True, "lock", None, None,
                     fill=P["rose"] if self.locked else P["card2"], font=self.f_tiny)
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
        name = self._clip_text(s["name"], w - 2 * pad, self.f_big)
        it["name"] = cv.create_text(x + w / 2, cy + self.f_big[1] * 0.95, text=name, font=self.f_big, fill=P["champ"])
        if s["kind"] != "main":
            self.hits.append((x, y, x + w, cy + self.f_big[1] * 2, "chanedit", cid, None))
        cy += self.f_big[1] * 2
        cv.create_line(cx0 + 10, cy, cx1 - 10, cy, fill=P["gold_dim"] if sel else P["line"])
        cy += 4

        # Preset- oder Gain-Zeile
        row_h = max(28, int(h * 0.085))
        aw = max(26, int(w * 0.22))
        if s["preset"]:
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
        self.items[cid] = it

    def _draw_live(self, x, y, w, h):
        cv = self.canvas
        s = self._sel_strip()
        self.rrect(x, y, x + w, y + h, 14, fill=P["card"], outline=P["gold_dim"], width=1)
        cv.create_text(x + 12, y + 14, anchor="w", text="LIVE", font=self.f_small, fill=P["gold"])
        # Systemlast oben rechts (wird in update_dynamic aufgefrischt)
        self.sys_item = cv.create_text(x + w - 10, y + 14, anchor="e", font=self.f_tiny, fill=P["tx2"], text="")
        self.sys_hit = (x + w * 0.45, y, x + w, y + 28)
        self.hits.append((x + w * 0.45, y, x + w, y + 28, "sysinfo", None, None))
        if not s or s["kind"] == "main":
            cv.create_text(x + w / 2, y + h / 2, text="Kanal wählen", font=self.f_small, fill=P["tx2"])
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
        if self.mode == "splash":
            return self.stop_splash()
        if self.mode == "update":
            u = getattr(self, "upd", {})
            if u.get("done") or u.get("error"):
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
        h = self._hit(self.hits, ev.x, ev.y)
        if not h:
            return
        art, cid, extra = h[4], h[5], h[6]
        if self.locked and art not in ("lock", "select"):
            if art in ("newtrack", "chanedit"):
                self._flash("Gesperrt – Sperre lang drücken zum Entsperren")
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
                self._flash("Bedienung gesperrt – Sperre lang drücken zum Entsperren" if self.locked else "Entsperrt")
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
            if art == "fx" and not long_done:
                self.bridge.action(cid, "fx", extra)
            elif art == "scene" and not long_done:
                try:
                    self.bridge.action(None, "scene_load", extra)
                except KeyError:
                    self._flash(f"Szene {extra} ist leer – lang drücken speichert")
            elif art == "lock" and not long_done:
                if not self.locked:
                    self.locked = True
                    self._flash("Gesperrt – lang drücken zum Entsperren")
                else:
                    self._flash("Zum Entsperren lang drücken")
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
        items = [("menu", "Zynthian-Menü", "Ketten, Snapshots, Admin"),
                 ("expert", "Profi-Mischer", "der originale Zynthian-Mischer"),
                 ("newtrack", "＋ Neue Spur", "Eingang, Handpan, Gesang, Synth …"),
                 ("idle", "Bühnenbild", "Animation jetzt zeigen"),
                 ("settings", f"Update {upd} bereit" if upd else "Einstellungen", "Update, Start-Logo, Bühnenbild …"),
                 ("close", "Zurück", "")]
        if self.dj_installed:
            items.insert(0, ("dj", "🎧 DJ-Pult", "Mixxx mit dem DDJ-200"))
        if self.imres_installed:
            items.insert(0, ("imres", "♫ Barden Beats", "Bühne & Klangwelten im Vollbild"))
        cols = 4 if len(items) > 6 else 3
        rows = math.ceil(len(items) / cols)
        gw, gh = (W - 40) / cols, (H - 70) / rows
        for k, (art, title, sub) in enumerate(items):
            cx, cy = 20 + (k % cols) * gw, 52 + (k // cols) * gh
            gold = art in ("imres", "dj") or (art == "settings" and upd)
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
                if art == "menu":
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

    def open_synth_browser(self):
        items = [dict(t) for t in self.x.synth_tiles()]
        known = {t["eng"] for t in items}
        for c in self.x.all_synths():
            for it in c["items"]:
                if it["eng"] not in known:
                    items.append({"group": c["cat"], "label": it["name"], "icon": "", "eng": it["eng"]})
        self.browser = {"chain": None, "page": 0, "items": items, "busy": None, "synth": True}
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
                    result["chain"] = self.x.create_synth(eng, int(self.settings.get("synth_midi_chan", 0)))
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
        gw = (W - 24) / 4
        main = info["kind"] == "main"
        armed = self.trk.get("armed", 0) > time.monotonic()
        tiles = [
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
            x0, y0 = 12 + (k % 4) * gw, gy0 + (k // 4) * gh
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
        cv.create_text(18, 26, anchor="w", text="Einstellungen", font=self.f_huge, fill=P["gold"])
        a = getattr(self, "set_addr", {}) or {}
        cv.create_text(W - 18, 18, anchor="e", font=self.f_tiny, fill=P["tx2"], text="Handy / Tablet:")
        cv.create_text(W - 18, 36, anchor="e", font=self.f_small, fill=P["champ"],
                       text=(a.get("url") or a.get("name") or "–") + ("  · PIN" if a.get("pin") else ""))
        # Update-Leiste
        y0, y1 = 54, 54 + max(54, int(H * 0.13))
        avail = us.get("available")
        self.rrect(12, y0, W - 12, y1, 14, fill="#2a2014" if avail else P["card"],
                   outline=P["gold"] if avail else P["line"], width=2 if avail else 1)
        if avail:
            line = f"Update {us.get('latest')} ist da  ·  installiert: {VERSION}"
        elif us.get("error"):
            line = f"ZynSimple {VERSION}  ·  GitHub nicht erreichbar"
        elif us.get("latest"):
            line = f"ZynSimple {VERSION}  ·  aktuell"
        else:
            line = f"ZynSimple {VERSION}"
        cv.create_text(28, (y0 + y1) / 2, anchor="w", text=line, font=self.f_mid, fill=P["champ"])
        bw = max(150, int(W * 0.24))
        self._tbtn(W - 20 - bw, y0 + 7, W - 20, y1 - 7, "Jetzt installieren" if avail else "Update suchen", "s_update",
                   fill=P["gold"] if avail else None, fg=P["black"] if avail else P["gold"], font=self.f_small,
                   outline=None if avail else P["gold_dim"])
        # Einstellungen als Kacheln: antippen = nächster Wert
        bar_h = max(40, H // 10)
        items = st.items(self.settings)
        cols = 3
        rows = math.ceil(len(items) / cols)
        gy0, gy1 = y1 + 10, H - bar_h - 8
        gw, gh = (W - 24) / cols, (gy1 - gy0) / rows
        for k, it in enumerate(items):
            x0, yy = 12 + (k % cols) * gw, gy0 + (k // cols) * gh
            on = it["value"] not in (False, 0, None) if it["kind"] == "bool" else True
            self.rrect(x0 + 4, yy + 4, x0 + gw - 4, yy + gh - 4, 12, fill=P["card2"], outline=P["line"])
            cv.create_text(x0 + 16, yy + 6 + gh * 0.2, anchor="w", text=self._clip_text(it["title"], gw - 30, self.f_tiny),
                           font=self.f_tiny, fill=P["tx2"])
            if it["kind"] == "bool":
                pw = gw * 0.28
                px0, py0 = x0 + gw - 16 - pw, yy + gh * 0.36
                self.rrect(px0, py0, px0 + pw, py0 + gh * 0.32, 99, fill=P["gold"] if on else P["bg"], outline=P["line"])
                kr = gh * 0.13
                kx = px0 + pw - kr - 5 if on else px0 + kr + 5
                cv.create_oval(kx - kr, py0 + gh * 0.16 - kr, kx + kr, py0 + gh * 0.16 + kr,
                               fill=P["black"] if on else P["tx2"], outline="")
                cv.create_text(x0 + 16, yy + gh * 0.52, anchor="w", text="an" if on else "aus", font=self.f_mid,
                               fill=P["gold"] if on else P["tx2"])
            else:
                cv.create_text(x0 + 16, yy + gh * 0.52, anchor="w", font=self.f_mid, fill=P["gold"],
                               text=self._clip_text(it["text"], gw - 40, self.f_mid))
                cv.create_text(x0 + gw - 18, yy + gh * 0.52, anchor="e", text="›", font=self.f_big, fill=P["gold_dim"])
            if it["hint"] and gh > 70:
                cv.create_text(x0 + 16, yy + gh * 0.8, anchor="w", font=self.f_tiny, fill=P["tx2"],
                               text=self._clip_text(it["hint"], gw - 30, self.f_tiny))
            self.trk_hits.append((x0 + 4, yy + 4, x0 + gw - 4, yy + gh - 4, "s_cycle", it["key"]))
        # Leiste unten
        yb = H - bar_h
        cv.create_line(8, yb + 1, W - 8, yb + 1, fill=P["gold_dim"])
        try:
            from . import theme
            th = theme.status()
        except Exception:
            th = {"active": False}
        armed = self.set_armed.get("theme", 0) > now
        bw2 = max(150, int(W * 0.22))
        self._tbtn(6, yb + 4, 6 + bw2, H - 4,
                   "Wirklich? Neustart" if armed else ("Altes Design" if th.get("active") else "Design „Glut“"), "s_theme",
                   fill=P["rose"] if armed else None, fg="#ffffff" if armed else None, font=self.f_small)
        self._tbtn(12 + bw2, yb + 4, 12 + bw2 * 2, H - 4, "Zynthian-Admin", "s_admin", font=self.f_small)
        armed_s = self.set_armed.get("save", 0) > now
        self._tbtn(18 + bw2 * 2, yb + 4, 18 + bw2 * 3, H - 4, "✓ gespeichert" if armed_s else "Jetzt speichern",
                   "s_save", font=self.f_small, fg=P["emerald"] if armed_s else None)
        self._tbtn(W - 150, yb + 4, W - 6, H - 4, "Fertig", "close", fill=P["gold"], fg=P["black"])

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
            if art == "s_cycle":
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

    def zynpot_cb(self, i, dval):
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
        if self.mode in ("more", "xy", "fxview", "update", "track", "newtrack", "settings"):
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

    def _pad_role(self, i):
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
        return None

    def switch(self, i, t):
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
            return False
        if self.mode == "idle":
            if t == "P":
                self._touch()
                self.stop_idle()
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
        if self.locked:
            return True
        chain = self._sel_chain()
        b = self.bridge
        try:
            alt = bool(self.zyngui.get_alt_mode())
        except Exception:
            alt = False
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
        if self.mode in ("browse", "more", "xy", "track", "newtrack", "settings"):
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
            self.open_expert()
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
            led = self.LED_INDEX[f"F{n}"]
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
        ws.wsleds[self.LED_INDEX["REC"]] = col(170, 150, 120) if s and s.get("freeze") else col(40, 30, 20)
        ws.wsleds[self.LED_INDEX["PLAY"]] = col(230, 170, 20) if s and s.get("throw") else col(40, 26, 4)
        ws.wsleds[self.LED_INDEX["STOP"]] = col(90, 0, 10)
        for k in ("UP", "DOWN", "LEFT", "RIGHT"):
            ws.wsleds[self.LED_INDEX[k]] = col(60, 35, 5)
        if self.mode == "idle" and self.anim:
            # Im Bühnenbild glimmen die Pads mit der Lautstärke
            g = self.anim.get("glow", 0)
            for k, led in enumerate((4, 11, 12, 19, 8, 9, 10)):
                f = max(0.0, min(1.0, g * 1.4 - k * 0.08))
                ws.wsleds[led] = col(int(40 + 190 * f), int(12 + 110 * f * f), int(2 + 30 * f * f * f))
