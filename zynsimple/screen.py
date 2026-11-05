# -*- coding: utf-8 -*-
"""ZynSimple – vereinfachter Mischer-Bildschirm für den Zynthian-Touchscreen."""

import logging
import math
import tkinter

from zyngui import zynthian_gui_config as cfg
from zyngui.zynthian_gui_base import zynthian_gui_base

log = logging.getLogger("zynsimple")

FLOOR = -60.0


def _c(name, default):
    return getattr(cfg, name, default) or default


class zynsimple_screen(zynthian_gui_base):

    buttonbar_config = []  # Oram erwartet dieses Attribut

    def __init__(self, bridge, settings):
        zynthian_gui_base.__init__(self)
        self.bridge = bridge
        self.settings = settings
        self.tts_title = "Einfacher Mischer"
        self.selected = 0          # Index des ausgewählten Kanals
        self.page = 0
        self.per_page = 1
        self.strips = []
        self.sig = None
        self.items = {}            # chain_id -> dict mit Canvas-Item-IDs
        self.hits = []             # (x0, y0, x1, y1, art, chain_id, extra)
        self.drag = None           # (chain_id, y_top, y_bottom)
        self.timer = None
        self.fxedit = None         # {"chain": id, "fx": i, "page": n} – Effekt-Regler offen
        self.fx_press = None       # (chain_id, fx, after-id) für langes Drücken
        self.edit_hits = []
        self.edit_tick = 0
        try:
            from . import imres
            self.imres_installed = imres.installed()
        except Exception:
            self.imres_installed = False

        self.col_bg = _c("color_bg", "#000000")
        self.col_panel = _c("color_panel_bg", "#3a424d")
        self.col_tx = _c("color_tx", "#ffffff")
        self.col_tx2 = _c("color_tx_off", "#a0a0a0")
        self.col_sel = "#f2a33a"
        self.col_mute = "#e5484d"
        self.col_solo = "#f5d90a"
        self.col_fx = "#3dd68c"
        family = _c("font_family", "Audiowide")
        h = max(320, int(self.height))
        self.f_big = (family, max(10, h // 30))
        self.f_mid = (family, max(9, h // 38))
        self.f_small = (family, max(8, h // 48))

        self.canvas = tkinter.Canvas(self.main_frame, width=self.width, height=self.height,
                                     bg=self.col_bg, bd=0, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="news")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    # ------------------------------------------------------------------
    # Lebenszyklus
    # ------------------------------------------------------------------

    def build_view(self):
        self.sig = None
        return True

    def show(self):
        super().show()
        try:
            self.set_title("Einfacher Mischer")
        except Exception:
            pass
        self.sig = None
        self.tick()

    def hide(self):
        if self.timer:
            try:
                self.canvas.after_cancel(self.timer)
            except Exception:
                pass
            self.timer = None
        super().hide()

    def tick(self):
        self.timer = None
        if not self.shown:
            return
        try:
            if self.fxedit:
                self.edit_tick += 1
                if self.edit_tick % 6 == 1:
                    self.draw_editor()
                self.timer = self.canvas.after(80, self.tick)
                return
            data = self.bridge.snapshot()
            self.strips = data["strips"]
            if self.strips:
                self.selected = max(0, min(self.selected, len(self.strips) - 1))
            sig = repr([(s["id"], s["name"], s["mute"], s["solo"], s["preset"] and s["preset"]["name"],
                         s.get("freeze"), [(f["name"], f["on"], f.get("sync")) for f in s["fx"]])
                        for s in self.strips]) \
                + f"|{self.selected}|{self.page}|{self.canvas.winfo_width()}x{self.canvas.winfo_height()}"
            if sig != self.sig:
                self.sig = sig
                self.draw()
            self.update_dynamic()
        except Exception as e:
            log.exception(f"ZynSimple Bildschirm: {e}")
        self.timer = self.canvas.after(80, self.tick)

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    def _geom(self):
        W = max(200, self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else int(self.width))
        H = max(200, self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else int(self.height))
        return W, H

    def draw(self):
        cv = self.canvas
        cv.delete("all")
        self.items = {}
        self.hits = []
        W, H = self._geom()
        bar_h = max(36, H // 10)
        strip_h = H - bar_h
        n = len(self.strips)

        min_w = int(self.settings.get("strip_min_width", 130))
        self.per_page = max(1, min(n if n else 1, W // min_w))
        pages = max(1, math.ceil(n / self.per_page)) if n else 1
        # Seite so wählen, dass der ausgewählte Kanal sichtbar ist
        self.page = min(self.selected // self.per_page, pages - 1)
        first = self.page * self.per_page
        visible = self.strips[first:first + self.per_page]
        sw = W / self.per_page

        if not n:
            cv.create_text(W / 2, strip_h / 2, fill=self.col_tx2, font=self.f_mid, justify="center",
                           text="Noch keine Kanäle.\nMenü → „Handpan anlegen“")

        for k, s in enumerate(visible):
            self._draw_strip(s, first + k, k * sw + 3, 3, sw - 6, strip_h - 6)

        # Untere Leiste
        y0 = strip_h
        cv.create_rectangle(0, y0, W, H, fill=self.col_bg, outline="")
        bw = max(60, W // 8)
        self._button(4, y0 + 4, bw, bar_h - 8, "◀", self.page > 0, "page", None, -1)
        self._button(8 + bw, y0 + 4, bw, bar_h - 8, "▶", self.page < pages - 1, "page", None, 1)
        try:
            from . import updater
            upd = updater.status.get("available") and updater.status.get("latest")
        except Exception:
            upd = None
        cv.create_text(16 + 2 * bw, y0 + bar_h / 2, anchor="w", font=self.f_small,
                       fill=self.col_sel if upd else self.col_tx2,
                       text=f"Update {upd}: Menü" if upd else f"Seite {self.page + 1}/{pages}")
        pw = max(110, W // 5)
        self._button(W - pw - 4, y0 + 4, pw, bar_h - 8, "Profi-Mischer", True, "expert", None, None)
        self._button(W - 2 * pw - 10, y0 + 4, pw, bar_h - 8, "Menü", True, "menu", None, None)
        if self.imres_installed:
            self._button(W - 3 * pw - 16, y0 + 4, pw, bar_h - 8, "♫ Imres", True, "imres", None, None,
                         fill=self.col_sel, fg="#000000")

    def _button(self, x, y, w, h, text, enabled, art, cid, extra, fill=None, fg=None, font=None):
        cv = self.canvas
        r = cv.create_rectangle(x, y, x + w, y + h, fill=fill or self.col_panel, outline="", width=0)
        t = cv.create_text(x + w / 2, y + h / 2, text=text, font=font or self.f_mid,
                           fill=(fg or self.col_tx) if enabled else self.col_tx2)
        if enabled:
            self.hits.append((x, y, x + w, y + h, art, cid, extra))
        return r, t

    def _draw_strip(self, s, index, x, y, w, h):
        cv = self.canvas
        cid = s["id"]
        sel = index == self.selected
        it = {}
        cv.create_rectangle(x, y, x + w, y + h, fill="#15181c", outline=self.col_sel if sel else "#2b313a",
                            width=3 if sel else 1)
        self.hits.append((x, y, x + w, y + h, "select", cid, index))
        pad = 6
        cx0, cx1 = x + pad, x + w - pad
        cy = y + pad

        # Name
        name = s["name"]
        max_chars = max(4, int(w / (self.f_big[1] * 0.9)))
        if len(name) > max_chars:
            name = name[:max_chars - 1] + "…"
        it["name"] = cv.create_text(x + w / 2, cy + self.f_big[1], text=name, font=self.f_big, fill=self.col_tx)
        if s["kind"] != "main":
            self.hits.append((x, y, x + w, cy + self.f_big[1] * 2, "chanedit", cid, None))
        cy += self.f_big[1] * 2 + 4

        # Preset-Zeile
        row_h = max(30, int(h * 0.09))
        if s["preset"]:
            aw = max(28, int(w * 0.22))
            self._button(cx0, cy, aw, row_h, "‹", True, "preset", cid, -1, fill="#000000", fg=self.col_sel,
                         font=self.f_big)
            self._button(cx1 - aw, cy, aw, row_h, "›", True, "preset", cid, 1, fill="#000000", fg=self.col_sel,
                         font=self.f_big)
            pn = s["preset"]["name"]
            mc = max(3, int((w - 2 * aw) / (self.f_small[1] * 0.85)))
            if len(pn) > mc:
                pn = pn[:mc - 1] + "…"
            cv.create_text(x + w / 2, cy + row_h / 2, text=pn, font=self.f_small, fill=self.col_tx)
        elif s.get("gain") is not None:
            aw = max(28, int(w * 0.22))
            self._button(cx0, cy, aw, row_h, "−", True, "gain", cid, -1, fill="#000000", fg=self.col_sel, font=self.f_big)
            self._button(cx1 - aw, cy, aw, row_h, "+", True, "gain", cid, 1, fill="#000000", fg=self.col_sel, font=self.f_big)
            g = s["gain"]
            cv.create_text(x + w / 2, cy + row_h / 2, text=f"Gain {'+' if g > 0 else ''}{g} dB", font=self.f_small,
                           fill=self.col_tx)
            self.hits.append((cx0 + aw, cy, cx1 - aw, cy + row_h, "gain0", cid, None))
        else:
            kind = {"audio": "Audio-Eingang", "main": "Hauptausgang", "bus": "Bus"}.get(s["kind"], "")
            cv.create_text(x + w / 2, cy + row_h / 2, text=kind, font=self.f_small, fill=self.col_tx2)
        cy += row_h + 6

        # Unten: Mute/Solo und Effekte
        ms_h = max(36, int(h * 0.11))
        fx_h = max(26, int(h * 0.075))
        prio = {"reverb": 0, "delay": 1, "comp": 2, "eq": 3}
        max_fx = 4 if h > 330 else 3 if h > 260 else 2
        fx_list = sorted(sorted(s["fx"], key=lambda f: prio.get(f.get("kind"), 4))[:max_fx], key=lambda f: f["i"])
        if len(fx_list) > 2:
            fx_h = max(22, int(h * 0.062))
        bottom = y + h - pad
        ms_y = bottom - ms_h
        fx_y = ms_y - 6 - len(fx_list) * (fx_h + 4)

        # Fader + Meter
        fy0, fy1 = cy, fx_y - 6
        mw = max(8, int(w * 0.09))
        it["meterA"] = (cx0, fy0, cx0 + mw / 2 - 1, fy1)
        it["meterB"] = (cx0 + mw / 2 + 1, fy0, cx0 + mw, fy1)
        for key in ("meterA", "meterB"):
            a, b, c, d = it[key]
            cv.create_rectangle(a, b, c, d, fill="#000000", outline="")
            it[key + "_bar"] = cv.create_rectangle(a, d, c, d, fill=self.col_fx, outline="")
            it[key + "_hold"] = cv.create_line(a, d, c, d, fill="#ffffff", width=2)
        fx0 = cx0 + mw + 6
        it["fader"] = (fx0, fy0, cx1, fy1)
        cv.create_rectangle(fx0, fy0, cx1, fy1, fill="#000000", outline="")
        it["fill"] = cv.create_rectangle(fx0, fy1, cx1, fy1, fill=self.col_sel, outline="")
        it["cap"] = cv.create_rectangle(fx0 + 4, fy1 - 4, cx1 - 4, fy1 + 4, fill="#ffffff", outline="")
        it["val"] = cv.create_text((fx0 + cx1) / 2, fy0 + self.f_small[1] + 4, text="", font=self.f_small,
                                   fill=self.col_tx)
        if s["level"] is not None:
            self.hits.append((fx0, fy0, cx1, fy1, "fader", cid, (fy0, fy1)))

        # Effekte
        fy = fx_y
        for f in fx_list:
            on = f["on"]
            label = ("● " if on else "○ ") + f["name"] + (f" ♩{f['sync']}" if f.get("sync") else "")
            mc = max(3, int((cx1 - cx0) / (self.f_small[1] * 0.85)))
            if len(label) > mc:
                label = label[:mc - 1] + "…"
            self._button(cx0, fy, cx1 - cx0, fx_h, label, True, "fx", cid, f["i"],
                         fill=self.col_fx if on else "#000000", fg="#000000" if on else self.col_tx,
                         font=self.f_small)
            fy += fx_h + 4

        # Mute / Solo
        if s.get("freeze") is not None:
            fw = max(30, int((cx1 - cx0) * 0.3))
            self._button(cx1 - fw, ms_y, fw, ms_h, "❄", True, "freeze", cid, None,
                         fill="#f5f0e6" if s["freeze"] else "#000000",
                         fg="#000000" if s["freeze"] else None, font=self.f_big)
            cx1 = cx1 - fw - 4
        if s["solo"] is None:
            self._button(cx0, ms_y, cx1 - cx0, ms_h, "MUTE", True, "mute", cid, None,
                         fill=self.col_mute if s["mute"] else "#000000")
        else:
            half = (cx1 - cx0 - 4) / 2
            self._button(cx0, ms_y, half, ms_h, "M", True, "mute", cid, None,
                         fill=self.col_mute if s["mute"] else "#000000")
            self._button(cx0 + half + 4, ms_y, half, ms_h, "S", True, "solo", cid, None,
                         fill=self.col_solo if s["solo"] else "#000000",
                         fg="#000000" if s["solo"] else None)
        self.items[cid] = it

    def update_dynamic(self):
        import time as _t
        now = _t.monotonic()
        if not hasattr(self, "clip_t"):
            self.clip_t = {}
        cv = self.canvas
        for s in self.strips:
            it = self.items.get(s["id"])
            if not it:
                continue
            fx0, fy0, fx1, fy1 = it["fader"]
            lvl = s["level"] if s["level"] is not None else 0.0
            if self.drag and self.drag[0] == s["id"] and self.drag[3] is not None:
                lvl = self.drag[3]
            y = fy1 - (fy1 - fy0) * max(0.0, min(1.0, lvl))
            cv.coords(it["fill"], fx0, y, fx1, fy1)
            cv.coords(it["cap"], fx0 + 4, y - 4, fx1 - 4, y + 4)
            cv.itemconfig(it["fill"], fill="#555555" if s["mute"] else self.col_sel)
            db = "−∞" if lvl <= 0.0001 else f"{20 * math.log10(lvl):.1f}"
            cv.itemconfig(it["val"], text=f"{db} dB")
            m = s.get("meter") or [FLOOR] * 4
            if max(m[2], m[3]) >= -0.5:
                self.clip_t[s["id"]] = now
            if "name" in it:
                cv.itemconfig(it["name"], fill=self.col_mute if now - self.clip_t.get(s["id"], -99) < 2.5 else self.col_tx)
            for k, key in enumerate(("meterA", "meterB")):
                a, b, c, d = it[key]
                frac = max(0.0, min(1.0, (m[k] - FLOOR) / -FLOOR))
                hold = max(0.0, min(1.0, (m[k + 2] - FLOOR) / -FLOOR))
                yb = d - (d - b) * frac
                cv.coords(it[key + "_bar"], a, yb, c, d)
                col = self.col_fx if m[k] < -12 else (self.col_solo if m[k] < -3 else self.col_mute)
                cv.itemconfig(it[key + "_bar"], fill=col)
                yh = d - (d - b) * hold
                cv.coords(it[key + "_hold"], a, yh, c, yh)

    # ------------------------------------------------------------------
    # Touch
    # ------------------------------------------------------------------

    def _hit(self, x, y, prefer=None):
        found = None
        for h in reversed(self.hits):
            if h[0] <= x <= h[2] and h[1] <= y <= h[3]:
                if prefer is None or h[4] == prefer:
                    return h
                if found is None:
                    found = h
        return found

    def _index_of(self, cid):
        for i, s in enumerate(self.strips):
            if s["id"] == cid:
                return i
        return None

    def on_press(self, ev):
        if self.fxedit:
            return self.editor_press(ev)
        h = self._hit(ev.x, ev.y)
        if not h:
            return
        art, cid, extra = h[4], h[5], h[6]
        if cid is not None:
            idx = self._index_of(cid)
            if idx is not None:
                self.selected = idx
        try:
            if art == "fader":
                self.drag = [cid, extra[0], extra[1], None]
                self._drag_to(ev.y)
            elif art in ("mute", "solo"):
                self.bridge.action(cid, art)
            elif art == "preset":
                self.bridge.action(cid, "preset_next" if extra > 0 else "preset_prev")
            elif art == "fx":
                # kurz = an/aus, lang (0,6 s) = Regler öffnen
                aid = self.canvas.after(600, lambda c=cid, i=extra: self.open_editor(c, i))
                self.fx_press = (cid, extra, aid)
                return
            elif art == "freeze":
                self.bridge.action(cid, "freeze")
            elif art == "gain":
                self.bridge.action(cid, "gain", {"step": extra})
            elif art == "gain0":
                self.bridge.action(cid, "gain", 0)
            elif art == "chanedit":
                self.open_editor(cid, "chan")
            elif art == "page":
                self.selected = max(0, min(len(self.strips) - 1,
                                           (self.page + extra) * self.per_page))
            elif art == "expert":
                self.open_expert()
            elif art == "menu":
                self.zyngui.show_screen("main_menu")
            elif art == "imres":
                import threading
                from . import imres
                threading.Thread(target=imres.system, args=("imres",), daemon=True).start()
                try:
                    self.set_title("Imres-Bühne startet …")
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"ZynSimple Touch: {e}")
        self.sig = None

    def _drag_to(self, y):
        cid, y0, y1, _ = self.drag
        v = max(0.0, min(1.0, (y1 - y) / max(1, (y1 - y0))))
        self.drag[3] = v
        try:
            self.bridge.action(cid, "level", v)
        except Exception:
            pass
        self.update_dynamic()

    def on_motion(self, ev):
        if self.fxedit:
            return self.editor_motion(ev)
        if self.drag:
            self._drag_to(ev.y)

    def on_release(self, ev):
        self.drag = None
        self.edit_drag = None
        if self.fx_press:
            cid, i, aid = self.fx_press
            self.fx_press = None
            try:
                self.canvas.after_cancel(aid)
            except Exception:
                pass
            try:
                self.bridge.action(cid, "fx", i)
            except Exception as e:
                log.warning(f"ZynSimple: {e}")
            self.sig = None

    # ------------------------------------------------------------------
    # Effekt-Regler auf dem Touchscreen
    # ------------------------------------------------------------------

    def open_editor(self, cid, fx):
        self.fx_press = None
        self.fxedit = {"chain": cid, "fx": fx, "page": 0}
        self.edit_tick = 0
        self.edit_drag = None
        self.draw_editor()

    def close_editor(self):
        self.fxedit = None
        self.sig = None

    def _editor_params(self):
        x = self.bridge.extras
        chain = self.bridge._chain(self.fxedit["chain"])
        if self.fxedit["fx"] == "chan":
            flat = []
            g = self.bridge._ctrl(chain, "gain")
            if g is not None:
                flat.append(g)
            flat += list(x._input_ctrls().values())
            return x, chain, None, flat
        proc = x.find_fx(chain, self.fxedit["fx"])
        flat = [z for _, items in x.params(proc) for z in items]
        return x, chain, proc, flat

    def draw_editor(self):
        cv = self.canvas
        try:
            x, chain, proc, flat = self._editor_params()
        except Exception:
            return self.close_editor()
        cv.delete("all")
        self.edit_hits = []
        W, H = self._geom()
        pages = max(1, math.ceil(len(flat) / 4))
        pg = self.fxedit["page"] = max(0, min(self.fxedit["page"], pages - 1))
        shown = flat[pg * 4:pg * 4 + 4]
        self.edit_shown = shown
        top = 8
        cv.create_text(16, top + self.f_big[1], anchor="w", font=self.f_big, fill=self.col_tx,
                       text=f"{self.bridge._name(chain)} · " + (proc.get_name() if proc else "Gain & Eingang"))
        bar_h = max(36, H // 10)
        area_y0, area_y1 = top + self.f_big[1] * 2 + 10, H - bar_h - 8
        row = (area_y1 - area_y0) / 4
        for k, z in enumerate(shown):
            y = area_y0 + k * row
            lbl = getattr(z, "short_name", None) or getattr(z, "name", z.symbol)
            if proc is None:
                lbl = "Gain (Mischer)" if z.symbol == "gain" else f"Eingang Soundkarte: {getattr(z, 'name', z.symbol)}"
            cv.create_text(16, y + row * 0.28, anchor="w", font=self.f_mid, fill=self.col_tx,
                           text=f"Knopf {k + 1}:  {lbl}")
            try:
                txt = str(z.get_value2label())
            except Exception:
                txt = str(z.value)
            cv.create_text(W - 16, y + row * 0.28, anchor="e", font=self.f_mid, fill=self.col_sel, text=txt)
            bx0, bx1, by0, by1 = 16, W - 16, y + row * 0.5, y + row * 0.85
            cv.create_rectangle(bx0, by0, bx1, by1, fill="#000000", outline="#2b313a")
            try:
                frac = (float(z.value) - float(z.value_min)) / max(1e-9, float(z.value_max) - float(z.value_min))
            except Exception:
                frac = 0
            cv.create_rectangle(bx0, by0, bx0 + (bx1 - bx0) * max(0, min(1, frac)), by1, fill=self.col_sel, outline="")
            self.edit_hits.append((bx0, by0 - 8, bx1, by1 + 8, "param", k, (bx0, bx1)))
        if not shown:
            cv.create_text(W / 2, (area_y0 + area_y1) / 2, font=self.f_mid, fill=self.col_tx2,
                           text="Keine Regler vorhanden.")
        # Untere Leiste
        y0 = H - bar_h
        bw = max(90, W // 6)
        def btn(xx, label, art, extra=None, on=True, fill=None, fg=None):
            cv.create_rectangle(xx, y0 + 4, xx + bw, H - 4, fill=fill or self.col_panel, outline="")
            cv.create_text(xx + bw / 2, (y0 + H) / 2, text=label, font=self.f_mid,
                           fill=(fg or self.col_tx) if on else self.col_tx2)
            if on:
                self.edit_hits.append((xx, y0 + 4, xx + bw, H - 4, art, None, extra))
        btn(4, "◀ Seite", "epage", -1, pg > 0)
        btn(8 + bw, "Seite ▶", "epage", 1, pg < pages - 1)
        cv.create_text(16 + 2 * bw, (y0 + H) / 2, anchor="w", font=self.f_small, fill=self.col_tx2,
                       text=f"{pg + 1}/{pages}")
        if proc is not None and x.fx_kind(proc) == "delay" and x._sync_target(proc):
            cur = x.state["sync"].get(str(proc.id))
            btn(W - 2 * bw - 10, f"♩ {cur}" if cur else "♩ aus", "esync", None, True,
                fill=self.col_sel if cur else None, fg="#000000" if cur else None)
        btn(W - bw - 4, "Fertig", "eclose")

    def editor_press(self, ev):
        for h in self.edit_hits:
            if h[0] <= ev.x <= h[2] and h[1] <= ev.y <= h[3]:
                art, extra = h[4], h[6]
                if art == "param":
                    self.edit_drag = (h[5], extra)
                    self.editor_motion(ev)
                elif art == "epage":
                    self.fxedit["page"] += extra
                    self.draw_editor()
                elif art == "esync":
                    self.cycle_sync()
                elif art == "eclose":
                    self.close_editor()
                return

    def editor_motion(self, ev):
        d = getattr(self, "edit_drag", None)
        if not d:
            return
        k, (bx0, bx1) = d
        try:
            z = self.edit_shown[k]
            frac = max(0.0, min(1.0, (ev.x - bx0) / max(1, bx1 - bx0)))
            v = float(z.value_min) + frac * (float(z.value_max) - float(z.value_min))
            if getattr(z, "is_integer", False) or getattr(z, "is_toggle", False) or getattr(z, "labels", None):
                v = int(round(v))
            z.set_value(v)
        except Exception as e:
            log.debug(f"Regler: {e}")
        self.draw_editor()

    def cycle_sync(self):
        from .extras import DIVISIONS
        x, chain, proc, _ = self._editor_params()
        order = [None] + list(DIVISIONS)
        cur = x.state["sync"].get(str(proc.id))
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "1/4"
        try:
            x.set_sync(chain, self.fxedit["fx"], nxt)
        except Exception as e:
            log.warning(f"ZynSimple: {e}")
        self.draw_editor()

    def open_expert(self):
        self.zyngui._zs_allow_home = True
        home = "mixer" if self.bridge.vangelis else "audio_mixer"
        self.zyngui.show_screen(home)

    # ------------------------------------------------------------------
    # Drehgeber & Tasten
    # ------------------------------------------------------------------

    def _sel_strip(self):
        if 0 <= self.selected < len(self.strips):
            return self.strips[self.selected]
        return None

    def zynpot_cb(self, i, dval):
        try:
            role = list(cfg.layout["ctrl_order"]).index(i)
        except Exception:
            role = i
        if self.fxedit:
            try:
                x, chain, proc, _ = self._editor_params()
                if role < len(self.edit_shown):
                    x.nudge_param(proc, self.edit_shown[role], dval)
                    self.draw_editor()
            except Exception as e:
                log.debug(f"Regler: {e}")
            return True
        s = self._sel_strip()
        try:
            if role == 3 and s:          # SELECT-Knopf: Lautstärke
                chain = self.bridge._chain(s["id"])
                self.bridge.nudge_level(chain, dval)
            elif role == 2 and self.strips:  # SNAPSHOT-Knopf: Kanal wählen
                self.selected = max(0, min(len(self.strips) - 1, self.selected + (1 if dval > 0 else -1)))
            elif role == 1 and s and s["preset"]:  # BACK-Knopf: Preset
                self.bridge.action(s["id"], "preset_next" if dval > 0 else "preset_prev")
            elif role == 0 and self.strips:  # LAYER-Knopf: Summe
                main = [x for x in self.strips if x["kind"] == "main"]
                if main:
                    self.bridge.nudge_level(self.bridge._chain(main[0]["id"]), dval)
        except Exception as e:
            log.warning(f"ZynSimple Drehgeber: {e}")
        return True

    def zynpot_abs(self, i, val):
        return True

    def switch_select(self, t="S"):
        if self.fxedit:
            if t == "S" and hasattr(self, "edit_shown"):
                self.fxedit["page"] += 1
                pages = max(1, math.ceil(len(self._editor_params()[3]) / 4))
                if self.fxedit["page"] >= pages:
                    self.fxedit["page"] = 0
                self.draw_editor()
            else:
                self.close_editor()
            return True
        s = self._sel_strip()
        if not s:
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
        s = self._sel_strip()
        if s:
            self.bridge.nudge_level(self.bridge._chain(s["id"]), 2)

    def arrow_down(self, nudge=-1):
        s = self._sel_strip()
        if s:
            self.bridge.nudge_level(self.bridge._chain(s["id"]), -2)

    def back_action(self):
        if self.fxedit:
            self.close_editor()
        return True  # Auf dem Startbildschirm tut ZURÜCK nichts

    # Oram fragt diese Methoden auf manchen Bildschirmen ab
    def toggle_midi_learn(self, *a, **k):
        pass

    def midi_learn_options(self, *a, **k):
        pass

    def midi_unlearn_action(self, *a, **k):
        pass
