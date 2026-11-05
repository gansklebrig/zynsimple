# -*- coding: utf-8 -*-
"""
ZynSimple – Brücke zwischen der einfachen Ansicht (Web + Touchscreen)
und dem Zynthian-Kern. Unterstützt Oram und Vangelis.
"""

import logging
import queue
import threading
import time

log = logging.getLogger("zynsimple")

METER_FLOOR = -60.0


def _db(v):
    try:
        v = float(v)
    except Exception:
        return METER_FLOOR
    if v != v:  # NaN
        return METER_FLOOR
    return round(max(METER_FLOOR, min(6.0, v)), 1)


class Bridge:
    """Liest den Mischerzustand und führt Aktionen aus."""

    def __init__(self, zyngui):
        self.zyngui = zyngui
        self.sm = zyngui.state_manager
        self.cm = zyngui.chain_manager
        self.vangelis = hasattr(self.sm, "zynmixer_chan")
        self.version = "vangelis" if self.vangelis else "oram"
        self._jobs = queue.Queue()
        self._last_dpm_update = 0
        self._oram_dpm = []
        self.extras = None          # wird in setup() gesetzt
        self.settings = {}
        threading.Thread(target=self._worker, name="zynsimple-worker", daemon=True).start()
        log.info(f"ZynSimple Bridge aktiv (Zynthian {self.version})")

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------

    def _worker(self):
        while True:
            fn, args = self._jobs.get()
            try:
                fn(*args)
            except Exception as e:
                log.exception(f"ZynSimple Aktion fehlgeschlagen: {e}")

    def _chains(self):
        cm = self.cm
        ids = getattr(cm, "ordered_chain_ids", None) or list(cm.chains.keys())
        chains = [cm.chains[i] for i in list(ids) if i in cm.chains]
        main = [c for c in chains if c.chain_id == 0]
        rest = [c for c in chains if c.chain_id != 0]
        return [c for c in rest + main if self._has_strip(c)]

    def _has_strip(self, chain):
        if self.vangelis:
            p = getattr(chain, "zynmixer_proc", None)
            return p is not None and getattr(p, "mixer_chan", None) is not None
        return getattr(chain, "mixer_chan", None) is not None

    def _ctrl(self, chain, symbol):
        """Mischer-Controller (zctrl) eines Kanals oder None."""
        try:
            if self.vangelis:
                return chain.zynmixer_proc.controllers_dict.get(symbol)
            return self.sm.zynmixer.zctrls[chain.mixer_chan].get(symbol)
        except Exception:
            return None

    def _kind(self, chain):
        try:
            if chain.chain_id == 0:
                return "main"
            if chain.is_synth():
                return "synth"
            if hasattr(chain, "is_mixbus") and chain.is_mixbus():
                return "bus"
            if chain.is_audio():
                return "audio"
        except Exception:
            pass
        return "other"

    def _name(self, chain):
        if chain.chain_id == 0:
            return "Summe"
        try:
            t = chain.get_title() or chain.get_name()
        except Exception:
            t = None
        if not t:
            t = f"Kanal {chain.chain_id}"
        t = str(t).replace("\n", " ").strip()
        return t

    def _sound_proc(self, chain):
        """Prozessor, dessen Presets man umschalten kann (der Klangerzeuger)."""
        try:
            procs = chain.get_processors("Synth")
            return procs[0] if procs else None
        except Exception:
            return None

    def _fx_procs(self, chain):
        try:
            return [p for p in chain.get_processors("Audio Effect")
                    if getattr(p, "eng_code", None) not in ("MI", "MR")]
        except Exception:
            return []

    @staticmethod
    def _bypass_ctrl(proc):
        """Gibt (zctrl, invertiert) zurück. invertiert=True heißt: Wert 1 = an."""
        z = getattr(proc, "bypass_zctrl", None)
        if z is not None:
            return z, False
        try:
            for sym, z in proc.controllers_dict.items():
                s = str(sym).lower().lstrip(":")
                if getattr(z, "is_bypass", False) or s.endswith("bypass"):
                    return z, False
            for sym, z in proc.controllers_dict.items():
                s = str(sym).lower().lstrip(":")
                if s in ("enabled", "enable", "on", "active"):
                    return z, True
        except Exception:
            pass
        return None, False

    def _fx_on(self, proc):
        z, inv = self._bypass_ctrl(proc)
        if z is None:
            return None
        try:
            v = z.value
            if inv:
                return bool(v)
            bv = getattr(z, "bypass_value", None)
            if bv is None:
                bv = z.value_max
            return v != bv
        except Exception:
            return None

    def _dpm(self, chain):
        """Liefert [a, b, hold_a, hold_b] in dB."""
        try:
            if self.vangelis:
                p = chain.zynmixer_proc
                d = p.zynmixer.dpm[p.mixer_chan]
                return [_db(d.a), _db(d.b), _db(d.a_hold), _db(d.b_hold)]
            st = self._oram_dpm[chain.mixer_chan]
            return [_db(st[0]), _db(st[1]), _db(st[2]), _db(st[3])]
        except Exception:
            return [METER_FLOOR] * 4

    def _refresh_dpm(self):
        now = time.monotonic()
        if now - self._last_dpm_update < 0.04:
            return
        self._last_dpm_update = now
        try:
            if self.vangelis:
                for zm in (self.sm.zynmixer_chan, self.sm.zynmixer_bus):
                    zm.enable_dpm(True)
                    zm.update_dpm_states()
            else:
                zm = self.sm.zynmixer
                last = zm.MAX_NUM_CHANNELS - 1
                zm.enable_dpm(0, last, True)
                self._oram_dpm = zm.get_dpm_states(0, last)
        except Exception as e:
            log.debug(f"DPM-Fehler: {e}")

    # ------------------------------------------------------------------
    # Zustand lesen
    # ------------------------------------------------------------------

    def snapshot(self, meters=True):
        if meters:
            self._refresh_dpm()
        strips = []
        try:
            chains = self._chains()
        except Exception as e:
            log.debug(f"Ketten nicht lesbar: {e}")
            chains = []
        for chain in chains:
            try:
                strips.append(self._strip(chain, meters))
            except Exception as e:
                log.debug(f"Kanal {getattr(chain, 'chain_id', '?')} nicht lesbar: {e}")
        return {"version": self.version, "strips": strips}

    def _strip(self, chain, meters):
        kind = self._kind(chain)
        lvl = self._ctrl(chain, "level")
        mute = self._ctrl(chain, "mute")
        solo = self._ctrl(chain, "solo") if kind != "main" else None
        gain = self._ctrl(chain, "gain")

        preset = None
        sp = self._sound_proc(chain)
        if sp is not None:
            plist = getattr(sp, "preset_list", None) or []
            preset = {
                "name": sp.preset_name or "—",
                "index": int(getattr(sp, "preset_index", 0) or 0),
                "count": len(plist),
                "engine": str(sp.get_name() or ""),
            }

        fx = []
        for i, p in enumerate(self._fx_procs(chain)):
            try:
                name = p.get_name() or f"Effekt {i + 1}"
            except Exception:
                name = f"Effekt {i + 1}"
            item = {"i": i, "name": str(name), "on": self._fx_on(p)}
            if self.extras:
                item["kind"] = self.extras.fx_kind(p)
                item["sync"] = self.extras.state["sync"].get(str(p.id))
            fx.append(item)

        return {
            "id": chain.chain_id,
            "name": self._name(chain),
            "kind": kind,
            "level": round(float(lvl.value), 4) if lvl is not None else None,
            "gain": int(round(float(gain.value))) if gain is not None else None,
            "mute": bool(mute.value) if mute is not None else None,
            "solo": bool(solo.value) if solo is not None else None,
            "meter": self._dpm(chain) if meters else None,
            "preset": preset,
            "fx": fx,
            "freeze": (self.extras.is_frozen(chain) if self.extras.freeze_available(chain) else None)
                      if self.extras and kind != "main" else None,
        }

    # ------------------------------------------------------------------
    # Aktionen
    # ------------------------------------------------------------------

    def _chain(self, chain_id):
        c = self.cm.chains.get(int(chain_id))
        if c is None or not self._has_strip(c):
            raise KeyError(f"Kanal {chain_id} gibt es nicht")
        return c

    def action(self, chain_id, op, value=None):
        res = self._action(chain_id, op, value)
        if self.extras and op not in ("learn", "learn_cancel"):
            self.extras.mark_dirty()
        return res

    def _action(self, chain_id, op, value=None):
        if op == "handpan":
            v = value if isinstance(value, dict) else {}
            return {"plugins": self.extras.create_handpan(v.get("inputs") or [1], v.get("title") or "Handpan")}
        if op == "learn_cancel":
            return self.extras.cancel_learn()
        if op == "foot_delete":
            return self.extras.delete_foot(int(value))
        if op == "input_level":
            return self.extras.set_input_level(str(value["sym"]), value["value"])
        chain = self._chain(chain_id)
        x = self.extras
        if op == "fx_param":
            return x.set_param(chain, int(value["fx"]), str(value["sym"]), value["value"])
        if op == "fx_sync":
            return x.set_sync(chain, int(value["fx"]), value.get("div"))
        if op == "freeze":
            return x.set_freeze(chain, None if value is None else bool(value))
        if op == "fx_try":
            v = value if isinstance(value, dict) else {"eng": value}
            return {"fx": x.try_fx(chain, str(v["eng"]), bool(v.get("keep")))}
        if op == "fx_keep":
            return x.keep_fx(chain)
        if op == "fx_remove":
            return x.remove_fx(chain, int(value))
        if op == "learn":
            v = value if isinstance(value, dict) else {}
            return x.start_learn(v.get("action", "freeze"), chain.chain_id, v.get("fx"), v.get("mode", "toggle"))
        if op == "level":
            self.set_level(chain, float(value))
        elif op == "mute":
            self.set_toggle(chain, "mute", value)
        elif op == "gain":
            self.set_gain(chain, value)
        elif op == "solo":
            if chain.chain_id == 0:
                return
            self.set_toggle(chain, "solo", value)
        elif op in ("preset_next", "preset_prev"):
            self._jobs.put((self._step_preset, (chain, 1 if op == "preset_next" else -1)))
        elif op == "fx":
            self._jobs.put((self._toggle_fx, (chain, int(value))))
        else:
            raise ValueError(f"Unbekannte Aktion {op}")
        try:
            self.sm.set_event_flag()
        except Exception:
            pass

    def set_level(self, chain, value):
        value = max(0.0, min(1.0, value))
        if self.vangelis:
            z = self._ctrl(chain, "level")
            if z is not None:
                z.set_value(value)
        else:
            self.sm.zynmixer.set_level(chain.mixer_chan, value, True)

    def set_gain(self, chain, value):
        """Vorverstärkung des Kanals in dB (−40 … +40). Wert oder {"step": ±n}."""
        z = self._ctrl(chain, "gain")
        if z is None:
            raise ValueError("Diese Zynthian-Version hat keinen Gain-Regler im Mischer")
        if isinstance(value, dict):
            value = float(z.value) + float(value.get("step", 0))
        v = int(round(max(float(z.value_min), min(float(z.value_max), float(value)))))
        z.set_value(v)

    def nudge_level(self, chain, steps):
        z = self._ctrl(chain, "level")
        if z is not None:
            self.set_level(chain, float(z.value) + steps * 0.01)
            if self.extras:
                self.extras.mark_dirty()

    def set_toggle(self, chain, symbol, value=None):
        z = self._ctrl(chain, symbol)
        if z is None:
            return
        if value is None:
            value = 0 if z.value else 1
        value = 1 if value else 0
        if self.vangelis:
            z.set_value(value)
        else:
            mc = chain.mixer_chan
            if symbol == "mute":
                self.sm.zynmixer.set_mute(mc, value, True)
            elif symbol == "solo":
                self.sm.zynmixer.set_solo(mc, value, True)

    def _step_preset(self, chain, direction):
        proc = self._sound_proc(chain)
        if proc is None:
            return
        plist = getattr(proc, "preset_list", None) or []
        if not plist:
            try:
                proc.load_preset_list()
                plist = proc.preset_list or []
            except Exception:
                return
        n = len(plist)
        if n == 0:
            return
        idx = int(getattr(proc, "preset_index", 0) or 0)
        for _ in range(n):
            idx = (idx + direction) % n
            entry = plist[idx]
            if len(entry) > 2 and entry[2] and entry[0] not in (None, ""):
                proc.set_preset(idx)
                log.info(f"ZynSimple: Preset {entry[2]} auf {self._name(chain)}")
                return

    def _toggle_fx(self, chain, index):
        procs = self._fx_procs(chain)
        if not 0 <= index < len(procs):
            return
        proc = procs[index]
        z, inv = self._bypass_ctrl(proc)
        if z is None:
            log.warning(f"ZynSimple: Effekt {proc.get_name()} hat keinen Bypass-Schalter")
            return
        on = self._fx_on(proc)
        if inv:
            z.set_value(z.value_min if on else z.value_max)
        else:
            bv = getattr(z, "bypass_value", None)
            if bv is None:
                bv = z.value_max
            other = z.value_min if bv == z.value_max else z.value_max
            z.set_value(bv if on else other)
