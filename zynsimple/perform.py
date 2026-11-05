# -*- coding: utf-8 -*-
"""
ZynSimple Perform – Live-Funktionen ohne Menü:
  - „Tiefe“-Makro pro Kanal (trocken → weit & schwebend)
  - Live-Regler: 4 Knöpfe = Tiefe + ★ Lieblingsregler (oder sinnvolle Vorgaben)
  - Szenen 1–8 mit sanftem Überblenden
  - Halte-Momente: Echo-Wurf, Freeze (in extras), Panik
  - XY-Feld (X = Echo, Y = Raum)
"""

import logging
import re
import threading
import time

log = logging.getLogger("zynsimple")

RE_WET = re.compile(r"wet|mix|blend|amount|late|reverb.?level|effect.?level", re.I)
RE_NOT_WET = re.compile(r"dry|early|input|gain|mode|predelay|pre.?delay|damp|width|low|high|cut", re.I)
RE_SIZE = re.compile(r"decay|size|rt60|room|length|time", re.I)
RE_FEEDBACK = re.compile(r"feed.?back|\bfb\b|repeat|regen", re.I)


def _t(z):
    return f"{z.symbol} {getattr(z, 'name', '')}"


def _frac(z, f):
    lo, hi = float(z.value_min), float(z.value_max)
    return lo + (hi - lo) * max(0.0, min(1.0, f))


def _pos(z):
    try:
        lo, hi = float(z.value_min), float(z.value_max)
        return (float(z.value) - lo) / (hi - lo) if hi > lo else 0.0
    except Exception:
        return 0.0


def _num(z):
    return not getattr(z, "labels", None) and not getattr(z, "is_toggle", False) and not isinstance(z.value, str)


class Perform:

    def __init__(self, bridge, extras):
        self.b = bridge
        self.x = extras
        st = self.x.state
        st.setdefault("tiefe", {})      # chain_name -> 0..1
        st.setdefault("pins", {})       # chain_name -> [[fx_eng_code, sym], ...]
        st.setdefault("scenes", {})     # "1".."8" -> Szene
        st.setdefault("morph_beats", 4)
        self.throws = {}                # chain_id -> [(zctrl, alt), ...]
        self._morph = None
        self.last_scene = None
        self.taps = []
        self.tap_bpm = None

    # ------------------------------------------------------------------
    # Hilfen
    # ------------------------------------------------------------------

    def _key(self, chain):
        return self.b._name(chain)

    def _fx(self, chain, kinds):
        return [p for p in self.b._fx_procs(chain) if self.x.fx_kind(p) in kinds]

    def _find(self, proc, regex, exclude=None, numeric=True):
        for z in proc.controllers_dict.values():
            t = _t(z)
            if regex.search(t) and not (exclude and exclude.search(t)) and (not numeric or _num(z)) \
                    and not getattr(z, "is_bypass", False):
                return z
        return None

    def _save(self):
        self.x._save()
        self.x.mark_dirty()

    # ------------------------------------------------------------------
    # Tiefe-Makro
    # ------------------------------------------------------------------

    def get_tiefe(self, chain):
        return float(self.x.state["tiefe"].get(self._key(chain), 0.35))

    def macro_targets(self, chain):
        """[(zctrl, f0, f1)] – Wert bei Tiefe 0 und Tiefe 1 als Anteil des Bereichs."""
        out = []
        for p in self._fx(chain, ("reverb",)):
            z = self._find(p, RE_WET, RE_NOT_WET)
            if z is not None:
                out.append((z, 0.05, 0.85))
            z = self._find(p, RE_SIZE, re.compile(r"pre|mod|rate|width", re.I))
            if z is not None:
                out.append((z, 0.2, 0.92))
        for p in self._fx(chain, ("delay",)):
            z = self._find(p, RE_FEEDBACK)
            if z is not None:
                out.append((z, 0.08, 0.72))
            z = self._find(p, RE_WET, RE_NOT_WET)
            if z is not None:
                out.append((z, 0.0, 0.55))
        return out

    def set_tiefe(self, chain, value):
        v = max(0.0, min(1.0, float(value)))
        for z, a, b in self.macro_targets(chain):
            try:
                nv = _frac(z, a + (b - a) * v)
                if getattr(z, "is_integer", False):
                    nv = int(round(nv))
                z.set_value(nv)
            except Exception as e:
                log.debug(f"Tiefe: {e}")
        self.x.state["tiefe"][self._key(chain)] = round(v, 3)
        self._save()
        return v

    # ------------------------------------------------------------------
    # Lieblingsregler (★) und die vier Live-Knöpfe
    # ------------------------------------------------------------------

    def toggle_pin(self, chain, fx_index, sym):
        proc = self.x.find_fx(chain, fx_index)
        key = self._key(chain)
        pins = [p for p in self.x.state["pins"].get(key, []) if isinstance(p, list) and len(p) == 2]
        item = [proc.eng_code, sym]
        if item in pins:
            pins.remove(item)
        else:
            pins.append(item)
            pins = pins[-3:]       # höchstens drei – Knopf 1 ist immer „Tiefe“
        self.x.state["pins"][key] = pins
        self._save()
        return item in pins

    def pinned(self, chain):
        return [tuple(p) for p in self.x.state["pins"].get(self._key(chain), [])]

    def live_slots(self, chain):
        """Vier Regler für die Drehknöpfe: Tiefe + ★ (oder Vorgaben)."""
        slots = [{"kind": "tiefe", "name": "Tiefe", "value": self.get_tiefe(chain)}]
        used = set()
        procs = self.b._fx_procs(chain)
        for eng, sym in self.pinned(chain):
            for i, p in enumerate(procs):
                if p.eng_code == eng and sym in p.controllers_dict:
                    z = p.controllers_dict[sym]
                    slots.append({"kind": "param", "fx": i, "z": z, "pin": True,
                                  "name": f"{getattr(z, 'short_name', None) or z.symbol}", "fxname": str(p.get_name())})
                    used.add(id(z))
                    break
        # Vorgaben auffüllen
        defaults = []
        for i, p in enumerate(procs):
            k = self.x.fx_kind(p)
            if k == "reverb":
                z = self._find(p, RE_WET, RE_NOT_WET)
                if z is not None:
                    defaults.append((i, p, z, "Hall"))
            elif k == "delay":
                z = self._find(p, RE_FEEDBACK)
                if z is not None:
                    defaults.append((i, p, z, "Echos"))
        for i, p, z, label in defaults:
            if len(slots) >= 3:
                break
            if id(z) not in used:
                slots.append({"kind": "param", "fx": i, "z": z, "pin": False, "name": label, "fxname": str(p.get_name())})
                used.add(id(z))
        if len(slots) < 4:
            slots.append({"kind": "level", "name": "Lautstärke"})
        while len(slots) < 4:
            slots.append({"kind": "none", "name": "—"})
        return slots[:4]

    def slot_info(self, chain, slot):
        d = {k: v for k, v in slot.items() if k != "z"}
        if slot["kind"] == "param":
            z = slot["z"]
            d["value"] = _pos(z)
            try:
                d["text"] = str(z.get_value2label())
            except Exception:
                d["text"] = str(z.value)
            d["sym"] = z.symbol
        elif slot["kind"] == "level":
            z = self.b._ctrl(chain, "level")
            lv = float(z.value) if z is not None else 0
            d["value"] = lv
            import math
            d["text"] = "−∞" if lv <= 0.0001 else f"{20 * math.log10(lv):.1f} dB"
        elif slot["kind"] == "tiefe":
            d["text"] = f"{int(round(slot['value'] * 100))} %"
        return d

    def nudge_slot(self, chain, index, steps):
        slots = self.live_slots(chain)
        if not 0 <= index < len(slots):
            return
        s = slots[index]
        if s["kind"] == "tiefe":
            self.set_tiefe(chain, self.get_tiefe(chain) + steps * 0.02)
        elif s["kind"] == "param":
            self.x.nudge_param(self.x.find_fx(chain, s["fx"]), s["z"], steps)
        elif s["kind"] == "level":
            self.b.nudge_level(chain, steps)

    def set_slot(self, chain, index, frac):
        slots = self.live_slots(chain)
        s = slots[index]
        if s["kind"] == "tiefe":
            self.set_tiefe(chain, frac)
        elif s["kind"] == "param":
            z = s["z"]
            v = _frac(z, frac)
            if getattr(z, "is_integer", False):
                v = int(round(v))
            z.set_value(v)
            self.x.mark_dirty()
        elif s["kind"] == "level":
            self.b.set_level(chain, frac)
            self.x.mark_dirty()

    # ------------------------------------------------------------------
    # XY-Feld: X = Echo (Delay-Feedback + Anteil), Y = Raum (Hall-Anteil + Größe)
    # ------------------------------------------------------------------

    def xy(self, chain, x, y):
        x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
        for p in self._fx(chain, ("delay",)):
            for rgx, a, b in ((RE_FEEDBACK, 0.0, 0.85), (RE_WET, 0.0, 0.7)):
                z = self._find(p, rgx, RE_NOT_WET if rgx is RE_WET else None)
                if z is not None:
                    z.set_value(_frac(z, a + (b - a) * x))
        for p in self._fx(chain, ("reverb",)):
            for rgx, a, b in ((RE_WET, 0.0, 0.9), (RE_SIZE, 0.15, 0.95)):
                z = self._find(p, rgx, RE_NOT_WET if rgx is RE_WET else re.compile(r"pre|mod|rate|width", re.I))
                if z is not None:
                    z.set_value(_frac(z, a + (b - a) * y))
        self.x.mark_dirty()

    def xy_pos(self, chain):
        x = y = 0.0
        for p in self._fx(chain, ("delay",)):
            z = self._find(p, RE_FEEDBACK)
            if z is not None:
                x = min(1.0, _pos(z) / 0.85)
                break
        for p in self._fx(chain, ("reverb",)):
            z = self._find(p, RE_WET, RE_NOT_WET)
            if z is not None:
                y = min(1.0, _pos(z) / 0.9)
                break
        return x, y

    # ------------------------------------------------------------------
    # Echo-Wurf (halten) und Panik
    # ------------------------------------------------------------------

    def echo_throw(self, chain, on):
        if on:
            if chain.chain_id in self.throws:
                return True
            saved = []
            for i, p in enumerate(self.b._fx_procs(chain)):
                if self.x.fx_kind(p) != "delay":
                    continue
                if self.b._fx_on(p) is False:
                    self.b._toggle_fx(chain, i)
                    saved.append(("bypass", (chain, i)))
                for rgx, f in ((RE_FEEDBACK, 0.82), (RE_WET, 0.7)):
                    z = self._find(p, rgx, RE_NOT_WET if rgx is RE_WET else None)
                    if z is not None:
                        saved.append((z, z.value))
                        if _pos(z) < f:
                            z.set_value(_frac(z, f))
            self.throws[chain.chain_id] = saved
            return bool(saved)
        for z, old in reversed(self.throws.pop(chain.chain_id, [])):
            try:
                if z == "bypass":
                    self.b._toggle_fx(*old)
                else:
                    z.set_value(old)
            except Exception:
                pass
        return False

    def is_throwing(self, chain):
        return chain.chain_id in self.throws

    def panic(self):
        """Alles Ausufernde stoppen: Freeze aus, Echo-Würfe aus, Überblenden stoppen, Echos zähmen."""
        self._morph = None
        for cid in list(self.x.frozen):
            c = self.b.cm.chains.get(cid)
            if c is not None:
                self.x.set_freeze(c, False)
        for cid in list(self.throws):
            c = self.b.cm.chains.get(cid)
            if c is not None:
                self.echo_throw(c, False)
        for c in list(self.b.cm.chains.values()):
            if not self.b._has_strip(c):
                continue
            for p in self._fx(c, ("delay",)):
                z = self._find(p, RE_FEEDBACK)
                if z is not None and _pos(z) > 0.6:
                    z.set_value(_frac(z, 0.35))
        log.info("ZynSimple: Panik")

    # ------------------------------------------------------------------
    # Tap-Tempo: Effekte laufen im Takt dessen, was du spielst
    # ------------------------------------------------------------------

    def tap(self, chain=None):
        now = time.monotonic()
        if self.taps and now - self.taps[-1] > 2.0:
            self.taps = []
        self.taps = (self.taps + [now])[-6:]
        if len(self.taps) < 2:
            return {"taps": 1, "bpm": self.x.tempo()}
        iv = [b - a for a, b in zip(self.taps, self.taps[1:])]
        iv = iv[-4:]
        avg = sorted(iv)[len(iv) // 2] if len(iv) >= 3 else sum(iv) / len(iv)
        bpm = round(max(40.0, min(240.0, 60.0 / avg)), 1)
        self.tap_bpm = bpm
        try:
            if hasattr(self.b.sm, "set_tempo"):
                self.b.sm.set_tempo(bpm)
            else:
                self.b.sm.zynseq.set_tempo(bpm)
        except Exception as e:
            log.warning(f"ZynSimple: Tempo nicht setzbar ({e})")
        # Delays des Kanals, die noch nicht im Takt laufen, gleich mitnehmen
        if chain is not None and len(self.taps) == 2:
            for i, p in enumerate(self.b._fx_procs(chain)):
                if self.x.fx_kind(p) == "delay" and not self.x.state["sync"].get(str(p.id)) and self.x._sync_target(p):
                    try:
                        self.x.set_sync(chain, i, "1/4")
                    except Exception:
                        pass
        for proc in list(self.b.cm.processors.values()):
            if str(proc.id) in self.x.state["sync"]:
                try:
                    self.x._apply_sync(proc, bpm)
                except Exception:
                    pass
        return {"taps": len(self.taps), "bpm": bpm}

    # ------------------------------------------------------------------
    # Szenen
    # ------------------------------------------------------------------

    def _capture(self):
        chains = {}
        for c in self.b._chains():
            key = self._key(c)
            ch = {"level": None, "mute": None, "fx": []}
            z = self.b._ctrl(c, "level")
            if z is not None:
                ch["level"] = float(z.value)
            z = self.b._ctrl(c, "mute")
            if z is not None:
                ch["mute"] = int(z.value)
            for p in self.b._fx_procs(c):
                params = {}
                for sym, z in p.controllers_dict.items():
                    if getattr(z, "is_bypass", False) or not _num(z):
                        continue
                    try:
                        params[sym] = float(z.value)
                    except Exception:
                        pass
                ch["fx"].append({"eng": p.eng_code, "on": self.b._fx_on(p), "params": params})
            if key in self.x.state["tiefe"]:
                ch["tiefe"] = self.x.state["tiefe"][key]
            chains[key] = ch
        return {"chains": chains, "ts": time.time()}

    def scene_save(self, n):
        self.x.state["scenes"][str(n)] = self._capture()
        self._save()
        self.last_scene = str(n)
        log.info(f"ZynSimple: Szene {n} gespeichert")

    def scene_list(self):
        return {k: bool(v) for k, v in self.x.state["scenes"].items()}

    def scene_load(self, n, beats=None):
        sc = self.x.state["scenes"].get(str(n))
        if not sc:
            raise KeyError(f"Szene {n} ist leer – lang drücken speichert sie")
        if beats is None:
            beats = float(self.x.state.get("morph_beats", 4))
        bpm = self.x.tempo() or 100.0
        seconds = max(0.0, beats * 60.0 / bpm)
        plan, toggles = [], []
        by_name = {self._key(c): c for c in self.b._chains()}
        for key, ch in sc["chains"].items():
            c = by_name.get(key)
            if c is None:
                continue
            if ch.get("level") is not None:
                z = self.b._ctrl(c, "level")
                if z is not None:
                    plan.append((z, float(z.value), ch["level"]))
            if ch.get("mute") is not None:
                toggles.append(("mute", c, ch["mute"]))
            procs = self.b._fx_procs(c)
            used = set()
            for f in ch["fx"]:
                idx = next((i for i, p in enumerate(procs) if p.eng_code == f["eng"] and i not in used), None)
                if idx is None:
                    continue
                used.add(idx)
                p = procs[idx]
                for sym, v in f["params"].items():
                    z = p.controllers_dict.get(sym)
                    if z is not None and _num(z):
                        try:
                            plan.append((z, float(z.value), float(v)))
                        except Exception:
                            pass
                if f.get("on") is not None and self.b._fx_on(p) is not None and bool(self.b._fx_on(p)) != bool(f["on"]):
                    toggles.append(("fx", c, idx, bool(f["on"])))
            if "tiefe" in ch:
                self.x.state["tiefe"][key] = ch["tiefe"]
        self.last_scene = str(n)
        token = object()
        self._morph = token

        def apply_toggles(turn_on):
            for t in toggles:
                if t[0] == "mute" and (t[2] == 0) == turn_on:
                    self.b.set_toggle(t[1], "mute", t[2])
                elif t[0] == "fx" and t[3] == turn_on:
                    self.b._toggle_fx(t[1], t[2])

        def run():
            apply_toggles(True)            # Einschalten am Anfang (blendet ein) …
            steps = max(1, int(seconds * 20))
            for k in range(1, steps + 1):
                if self._morph is not token:
                    return
                f = k / steps
                f = f * f * (3 - 2 * f)    # weich
                for z, a, b in plan:
                    v = a + (b - a) * f
                    if getattr(z, "is_integer", False):
                        v = int(round(v))
                    try:
                        z.set_value(v)
                    except Exception:
                        pass
                if seconds > 0:
                    time.sleep(seconds / steps)
            apply_toggles(False)           # … Ausschalten am Ende
            if self._morph is token:
                self._morph = None
            self.x.mark_dirty()

        threading.Thread(target=run, name="zynsimple-morph", daemon=True).start()
        log.info(f"ZynSimple: Szene {n} ({beats:g} Schläge)")
        return seconds

    def morphing(self):
        return self._morph is not None

    def set_morph_beats(self, beats):
        self.x.state["morph_beats"] = max(0, min(32, float(beats)))
        self._save()
