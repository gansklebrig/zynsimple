# -*- coding: utf-8 -*-
"""
ZynSimple Extras:
  - Automatisches Speichern (last_state.zss, wird beim Start geladen)
  - Effekt-Regler (alle Parameter eines Effekts)
  - Delay im Takt (Tempo vom Zynthian / TR-8S-Clock)
  - Freeze (lange, schwebende Hallfahne)
  - Fußschalter (MIDI-CC lernen und Aktionen auslösen)
  - Handpan-Vorlage (Audio-Kette mit Low-Cut, Kompressor, Delay, Hall)
"""

import json
import logging
import os
import re
import threading
import time

log = logging.getLogger("zynsimple")

HOME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(HOME_DIR, "zynsimple_state.json")

DIVISIONS = {"1/2": 2.0, "1/4.": 1.5, "1/4": 1.0, "1/8.": 0.75, "1/8": 0.5, "1/8T": 1 / 3, "1/16": 0.25}

# Bevorzugte Plugins für die Handpan-Vorlage (erstes vorhandenes wird genommen)
HANDPAN_CHAIN = [
    ("lowcut", ["JV/HighPassFilter", "JV/Invada High Pass Filter (mono)",
                "JV/x42-eq - Parametric Equalizer Mono", "JV/Glame Highpass Filter"]),
    ("comp", ["JV/Calf Compressor", "JV/Calf Mono Compressor", "JV/Dyson compressor"]),
    ("delay", ["JV/Bollie Delay", "JV/Gxdigital_delay_st", "JV/GxEcho-Stereo", "JV/Calf Vintage Delay"]),
    ("reverb", ["JV/Dragonfly Hall Reverb", "JV/Dragonfly Plate Reverb", "JV/Calf Reverb", "JV/GVerb"]),
]

# Effekt-Auswahl: (Gruppe, Name, Symbol, [Plugins in Wunschreihenfolge])
FX_TILES = [
    ("Hall", "Großer Hall", "🏛", ["JV/Dragonfly Hall Reverb"]),
    ("Hall", "Platte", "✨", ["JV/Dragonfly Plate Reverb"]),
    ("Hall", "Raum", "🚪", ["JV/Dragonfly Room Reverb"]),
    ("Hall", "Wolken-Hall", "☁", ["JV/Aether", "JV/CloudReverb"]),
    ("Hall", "Shimmer", "🌟", ["JV/Shiroverb", "JV/Gxshimmizita"]),
    ("Hall", "Weicher Hall", "🌫", ["JV/MVerb", "JV/DuskVerb", "JV/GxReverb-Stereo"]),
    ("Echo", "Delay", "🔁", ["JV/Bollie Delay"]),
    ("Echo", "Echo", "〰", ["JV/GxEcho-Stereo"]),
    ("Echo", "Röhren-Echo", "📼", ["JV/GxTubeDelay", "JV/Calf Vintage Delay"]),
    ("Echo", "Digital-Delay", "⏱", ["JV/Gxdigital_delay_st"]),
    ("Echo", "Rückwärts", "⏪", ["JV/Calf Reverse Delay"]),
    ("Echo", "Pingpong", "↔", ["JV/Ping Pong Pan"]),
    ("Textur", "Granular", "🌾", ["JV/Granulator"]),
    ("Textur", "Glitzer-Körner", "💫", ["JV/Argotlunar2"]),
    ("Textur", "Harmonizer", "🎶", ["JV/Harmonizer", "JV/Harmonizer2"]),
    ("Textur", "Tonhöhe", "🎚", ["JV/MDA RePsycho!", "JV/Super Capo", "JV/Capo"]),
    ("Bewegung", "Chorus", "🌊", ["JV/Calf Multi Chorus", "JV/GxChorus-Stereo"]),
    ("Bewegung", "Flanger", "🌀", ["JV/Calf Flanger"]),
    ("Bewegung", "Phaser", "🌗", ["JV/Calf Phaser"]),
    ("Bewegung", "Tremolo", "💓", ["JV/Calf Pulsator"]),
    ("Bewegung", "Auto-Pan", "🎧", ["JV/TAP AutoPanner"]),
    ("Bewegung", "Rotor", "🎡", ["JV/Calf Rotary Speaker"]),
    ("Farbe", "Filter", "🎛", ["JV/Calf Filter"]),
    ("Farbe", "Wah / Hüllkurve", "👄", ["JV/Calf Envelope Filter"]),
    ("Farbe", "Sättigung", "🔥", ["JV/Calf Saturator"]),
    ("Farbe", "Tonband", "🎞", ["JV/CHOWTapeModel", "JV/Calf Tape Simulator"]),
    ("Farbe", "Vinyl", "💿", ["JV/Calf Vinyl"]),
    ("Farbe", "Bitcrusher", "👾", ["JV/Calf Crusher"]),
    ("Farbe", "Ringmodulator", "🔔", ["JV/Calf Ring Modulator"]),
    ("Farbe", "Stereo-Breite", "↹", ["JV/Calf Multi Spread"]),
    ("Dynamik", "Kompressor", "🗜", ["JV/Calf Compressor", "JV/Calf Mono Compressor"]),
]

RE_FREEZE = re.compile(r"freez|infinit|\bhold\b", re.I)
RE_DECAY = re.compile(r"decay|size|rt60|reverb.?time|length", re.I)
RE_FEEDBACK = re.compile(r"feed.?back|\bfb\b|repeat|regen", re.I)
RE_BPM = re.compile(r"bpm|tempo", re.I)
RE_TIME = re.compile(r"delay|time", re.I)
RE_NOT_TIME = re.compile(r"mode|sync|div|feed|mix|mod|rate|depth|wet|dry|level|gain|predelay|pre.?delay|width", re.I)
RE_HP_FREQ = re.compile(r"freq|cutoff|hpf|f0", re.I)


def _label(z):
    return str(getattr(z, "short_name", None) or getattr(z, "name", None) or z.symbol)


def _text(z):
    return f"{z.symbol} {getattr(z, 'name', '')}"


class Extras:

    def __init__(self, bridge, settings):
        self.b = bridge
        self.settings = settings
        self.lock = threading.RLock()
        self.state = {"sync": {}, "foot": []}
        self._load()
        self.frozen = {}            # chain_id -> [(zctrl, alter Wert)]
        self.learn = None           # {"action":..., "chain":..., "fx":..., "mode":..., "ts":...}
        self.last_learn = None
        self.foot_held = {}         # (cc, chan) -> bool
        self.autosave_info = {"enabled": bool(settings.get("autosave", True)), "last": None, "error": None}
        self._last_hash = None
        self._boot = time.monotonic()
        threading.Thread(target=self._sync_loop, name="zynsimple-sync", daemon=True).start()
        self._register_midi()

    # ------------------------------------------------------------------
    # Dauerhafter Zustand
    # ------------------------------------------------------------------

    def _load(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.state["sync"] = dict(d.get("sync", {}))
            self.state["foot"] = list(d.get("foot", []))
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning(f"ZynSimple: {STATE_FILE} fehlerhaft ({e})")

    def _save(self):
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=1)
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            log.warning(f"ZynSimple: Zustand nicht gespeichert ({e})")

    # ------------------------------------------------------------------
    # Hilfen
    # ------------------------------------------------------------------

    def fx_kind(self, proc):
        cat = ""
        try:
            cat = str(self.b.cm.engine_info.get(proc.eng_code, {}).get("CAT", ""))
        except Exception:
            pass
        name = f"{cat} {proc.get_name()} {proc.eng_code}".lower()
        if "reverb" in name or "verb" in name or "hall" in name:
            return "reverb"
        if "delay" in name or "echo" in name:
            return "delay"
        if "dynamic" in name or "compress" in name:
            return "comp"
        if "filter" in name or "eq" in name or "pass" in name:
            return "eq"
        return "other"

    @staticmethod
    def params(proc):
        """Alle Regler eines Effekts, nach Seiten gruppiert."""
        pages, seen = [], set()
        try:
            screens = proc.get_ctrl_screens() or {}
        except Exception:
            screens = {}
        for title, zctrls in screens.items():
            items = []
            for z in zctrls or []:
                if z is None or id(z) in seen or getattr(z, "not_on_gui", False):
                    continue
                if getattr(z, "is_bypass", False) or z.symbol in ("bypass", ":bypass"):
                    continue
                seen.add(id(z))
                items.append(z)
            if items:
                pages.append((str(title), items))
        if not pages:
            items = [z for z in getattr(proc, "controllers_dict", {}).values()
                     if not getattr(z, "not_on_gui", False) and not getattr(z, "is_bypass", False)]
            if items:
                pages.append(("Regler", items))
        return pages

    @staticmethod
    def zctrl_info(z):
        d = {"sym": z.symbol, "name": _label(z)}
        try:
            d["min"] = float(z.value_min)
            d["max"] = float(z.value_max)
            d["value"] = float(z.value) if not isinstance(z.value, str) else z.value
        except Exception:
            d["value"] = z.value
        if getattr(z, "labels", None):
            d["labels"] = [str(x) for x in z.labels]
        try:
            d["text"] = str(z.get_value2label())
        except Exception:
            d["text"] = str(z.value)
        d["toggle"] = bool(getattr(z, "is_toggle", False))
        d["int"] = bool(getattr(z, "is_integer", False))
        return d

    def find_fx(self, chain, index):
        procs = self.b._fx_procs(chain)
        if not 0 <= index < len(procs):
            raise KeyError("Effekt nicht gefunden")
        return procs[index]

    # ------------------------------------------------------------------
    # Effekt-Regler
    # ------------------------------------------------------------------

    def fx_detail(self, chain, index):
        proc = self.find_fx(chain, index)
        out = {"name": str(proc.get_name()), "kind": self.fx_kind(proc), "pages": [],
               "sync": self.state["sync"].get(str(proc.id)), "syncable": False,
               "divisions": list(DIVISIONS)}
        for title, items in self.params(proc):
            out["pages"].append({"title": title, "params": [self.zctrl_info(z) for z in items]})
        out["syncable"] = out["kind"] == "delay" and self._sync_target(proc) is not None
        out["tempo"] = self.tempo()
        out["trial"] = self.is_trial(chain, index)
        return out

    def set_param(self, chain, index, sym, value):
        proc = self.find_fx(chain, index)
        z = proc.controllers_dict.get(sym)
        if z is None:
            raise KeyError(f"Regler {sym} nicht gefunden")
        if getattr(z, "labels", None) and isinstance(value, str):
            z.set_value(z.get_label2value(value))
            return
        v = float(value)
        v = max(float(z.value_min), min(float(z.value_max), v))
        if getattr(z, "is_integer", False) or getattr(z, "is_toggle", False):
            v = int(round(v))
        z.set_value(v)
        # Wer den Delay-Zeitregler von Hand dreht, schaltet „im Takt“ ab
        if self.state["sync"].get(str(proc.id)) and z is self._sync_target(proc)[0]:
            self.set_sync(chain, index, None)

    def nudge_param(self, proc, z, steps):
        tgt = self._sync_target(proc) if proc is not None and self.state["sync"].get(str(proc.id)) else None
        if tgt and z is tgt[0]:
            with self.lock:
                self.state["sync"].pop(str(proc.id), None)
                self._save()
        try:
            if getattr(z, "labels", None) or getattr(z, "is_integer", False) or getattr(z, "is_toggle", False):
                z.nudge(1 if steps > 0 else -1)
            else:
                rng = float(z.value_max) - float(z.value_min)
                v = float(z.value) + steps * rng / 100.0
                z.set_value(max(float(z.value_min), min(float(z.value_max), v)))
        except Exception as e:
            log.debug(f"nudge: {e}")

    # ------------------------------------------------------------------
    # Effekt-Auswahl („Probier-Platz“: neuer Effekt ersetzt den letzten Versuch)
    # ------------------------------------------------------------------

    def fx_tiles(self):
        info = getattr(self.b.cm, "engine_info", None) or {}
        out = []
        for group, label, icon, engs in FX_TILES:
            eng = next((e for e in engs if e in info), None)
            if eng:
                out.append({"group": group, "label": label, "icon": icon, "eng": eng})
        return out

    def all_fx(self):
        info = getattr(self.b.cm, "engine_info", None) or {}
        cats = {}
        for k, v in info.items():
            if v.get("TYPE") != "Audio Effect" or k in ("MI", "MR") or not str(k).startswith("JV/"):
                continue
            cats.setdefault(str(v.get("CAT") or "Andere"), []).append(
                {"eng": k, "name": str(v.get("TITLE") or v.get("NAME") or k[3:]), "on": bool(v.get("ENABLED"))})
        return [{"cat": c, "items": sorted(items, key=lambda x: (not x["on"], x["name"].lower()))}
                for c, items in sorted(cats.items())]

    def _trial(self, chain):
        if not hasattr(self, "trials"):
            self.trials = {}
        pid = self.trials.get(chain.chain_id)
        for p in self.b._fx_procs(chain):
            if p.id == pid:
                return p
        return None

    def try_fx(self, chain, eng, keep=False):
        """Setzt einen Effekt in den Kanal. Gibt den Index des neuen Effekts zurück."""
        import zynautoconnect
        cm, sm = self.b.cm, self.b.sm
        info = getattr(cm, "engine_info", None) or {}
        if eng not in info:
            raise ValueError("Diesen Effekt gibt es auf diesem Zynthian nicht")
        if not hasattr(self, "trials"):
            self.trials = {}
        old = None if keep else self._trial(chain)
        try:
            sm.start_busy("zynsimple_fx", "Effekt wird geladen")
        except Exception:
            pass
        try:
            if old is not None:
                new = cm.add_processor(chain.chain_id, eng, chain.get_slot(old))
                if new:
                    cm.remove_processor(chain.chain_id, old)
            else:
                slot = None
                for i, sl in enumerate(getattr(chain, "audio_slots", []) or []):
                    if sl and getattr(sl[0], "eng_code", None) in ("MI", "MR"):
                        slot = i
                        break
                new = cm.add_processor(chain.chain_id, eng, slot)
            if not new:
                raise RuntimeError("Effekt konnte nicht geladen werden")
            try:
                chain.rebuild_graph()
            except Exception:
                pass
            try:
                zynautoconnect.autoconnect()
            except Exception:
                zynautoconnect.request_audio_connect(True)
            if keep:
                self.trials.pop(chain.chain_id, None)
            else:
                self.trials[chain.chain_id] = new.id
        finally:
            try:
                sm.end_busy("zynsimple_fx")
            except Exception:
                pass
        procs = self.b._fx_procs(chain)
        return procs.index(new) if new in procs else len(procs) - 1

    def keep_fx(self, chain):
        if hasattr(self, "trials"):
            self.trials.pop(chain.chain_id, None)
        self.autosave(force=True)

    def remove_fx(self, chain, index):
        import zynautoconnect
        proc = self.find_fx(chain, index)
        self.b.cm.remove_processor(chain.chain_id, proc)
        try:
            chain.rebuild_graph()
        except Exception:
            pass
        zynautoconnect.request_audio_connect(True)
        if hasattr(self, "trials") and self.trials.get(chain.chain_id) == proc.id:
            self.trials.pop(chain.chain_id, None)
        self.state["sync"].pop(str(proc.id), None)
        self._save()

    def is_trial(self, chain, index):
        p = self._trial(chain)
        try:
            return p is not None and self.find_fx(chain, index) is p
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Eingangspegel der Soundkarte (vor allem anderen – gegen Übersteuern)
    # ------------------------------------------------------------------

    def _input_ctrls(self):
        if getattr(self, "_inp", None) is not None:
            return self._inp
        self._inp = {}
        try:
            from zyngine.zynthian_controller import zynthian_controller
            proc = self.b.sm.alsa_mixer_processor
            eng = proc.engine
            cfgs = eng.get_mixer_zctrls(eng.device_name, None)
            for sym, cfg in cfgs.items():
                gp = cfg.get("graph_path")
                if isinstance(gp, list) and len(gp) > 3 and gp[3] == "capture_level" and not cfg.get("is_toggle"):
                    self._inp[sym] = zynthian_controller(eng, sym, cfg)
        except Exception as e:
            log.info(f"ZynSimple: Eingangspegel nicht lesbar ({e})")
        return self._inp

    def input_levels(self):
        out = []
        for sym, z in self._input_ctrls().items():
            d = self.zctrl_info(z)
            out.append(d)
        return out

    def set_input_level(self, sym, value):
        z = self._input_ctrls().get(sym)
        if z is None:
            raise KeyError("Eingangsregler nicht gefunden")
        if isinstance(value, dict):
            value = float(z.value) + float(value.get("step", 0))
        z.set_value(int(round(max(float(z.value_min), min(float(z.value_max), float(value))))))

    # ------------------------------------------------------------------
    # Delay im Takt
    # ------------------------------------------------------------------

    def tempo(self):
        try:
            t = float(self.b.sm.zynseq.get_tempo())
            if 20 <= t <= 400:
                return round(t, 1)
        except Exception:
            pass
        return None

    def _sync_target(self, proc):
        """(zctrl, art) mit art = 'bpm' | 'ms' | 's' – oder None."""
        cands = list(getattr(proc, "controllers_dict", {}).values())
        for z in cands:
            t = _text(z)
            if RE_BPM.search(t) and not RE_NOT_TIME.search(t) and float(z.value_max) >= 120:
                return z, "bpm"
        for z in cands:
            t = _text(z)
            if RE_TIME.search(t) and not RE_NOT_TIME.search(t) and not getattr(z, "is_toggle", False):
                mx = float(z.value_max)
                if mx > 20:
                    return z, "ms"
                if mx > 0.2:
                    return z, "s"
        return None

    def set_sync(self, chain, index, division):
        proc = self.find_fx(chain, index)
        with self.lock:
            if division:
                if division not in DIVISIONS:
                    raise ValueError("Unbekannte Notenlänge")
                if self._sync_target(proc) is None:
                    raise ValueError("Dieses Delay hat keinen Zeitregler, den ZynSimple erkennt")
                self.state["sync"][str(proc.id)] = division
            else:
                self.state["sync"].pop(str(proc.id), None)
            self._save()
        self._apply_sync(proc)

    def _apply_sync(self, proc):
        div = self.state["sync"].get(str(proc.id))
        bpm = self.tempo()
        if not div or not bpm:
            return
        tgt = self._sync_target(proc)
        if not tgt:
            return
        z, art = tgt
        beat = 60.0 / bpm * DIVISIONS[div]
        if art == "bpm":
            v = bpm / DIVISIONS[div]
        elif art == "ms":
            v = beat * 1000.0
        else:
            v = beat
        v = max(float(z.value_min), min(float(z.value_max), v))
        if abs(float(z.value) - v) > 0.0005 * max(1.0, abs(v)):
            z.set_value(v)

    def _sync_loop(self):
        while True:
            time.sleep(0.5)
            try:
                if not self.state["sync"]:
                    continue
                for proc in list(self.b.cm.processors.values()):
                    if str(proc.id) in self.state["sync"]:
                        self._apply_sync(proc)
            except Exception as e:
                log.debug(f"Sync: {e}")

    # ------------------------------------------------------------------
    # Freeze
    # ------------------------------------------------------------------

    def freeze_available(self, chain):
        return any(self.fx_kind(p) in ("reverb", "delay") or
                   any(RE_FREEZE.search(_text(z)) for z in p.controllers_dict.values())
                   for p in self.b._fx_procs(chain))

    def is_frozen(self, chain):
        return chain.chain_id in self.frozen

    def set_freeze(self, chain, on=None):
        with self.lock:
            if on is None:
                on = not self.is_frozen(chain)
            if not on:
                for z, old in reversed(self.frozen.pop(chain.chain_id, [])):
                    try:
                        z.set_value(old)
                    except Exception:
                        pass
                return False
            if self.is_frozen(chain):
                return True
            saved = []
            for p in self.b._fx_procs(chain):
                ctrls = list(p.controllers_dict.values())
                real = [z for z in ctrls if RE_FREEZE.search(_text(z))]
                if real:
                    for z in real:
                        saved.append((z, z.value))
                        z.set_value(z.value_max)
                    continue
                kind = self.fx_kind(p)
                if kind == "reverb":
                    for z in ctrls:
                        if RE_DECAY.search(_text(z)) and not RE_NOT_TIME.search(_text(z)):
                            saved.append((z, z.value))
                            z.set_value(z.value_max)
                elif kind == "delay":
                    for z in ctrls:
                        if RE_FEEDBACK.search(_text(z)):
                            saved.append((z, z.value))
                            lo, hi = float(z.value_min), float(z.value_max)
                            z.set_value(lo + (hi - lo) * 0.92)
            self.frozen[chain.chain_id] = saved
            log.info(f"ZynSimple: Freeze an ({len(saved)} Regler)")
            return True

    # ------------------------------------------------------------------
    # Fußschalter
    # ------------------------------------------------------------------

    def _register_midi(self):
        try:
            from zyngine.zynthian_signal_manager import zynsigman
            zynsigman.register(zynsigman.S_MIDI, zynsigman.SS_MIDI_CC, self._midi_cc)
            log.info("ZynSimple: Fußschalter-Empfang aktiv")
        except Exception as e:
            log.warning(f"ZynSimple: MIDI-CC nicht verfügbar ({e})")

    def _midi_cc(self, izmip=None, chan=None, num=None, val=None, **kw):
        try:
            self.b._jobs.put((self._handle_cc, (chan, num, val)))
        except Exception:
            pass

    def start_learn(self, action, chain_id, fx=None, mode="toggle"):
        if action not in ("freeze", "fx", "mute"):
            raise ValueError("Unbekannte Fußschalter-Aktion")
        chain = self.b._chain(chain_id)
        self.learn = {"action": action, "chain": chain.chain_id, "chain_name": self.b._name(chain),
                      "fx": fx, "mode": "hold" if mode == "hold" else "toggle", "ts": time.time()}
        self.last_learn = None

    def cancel_learn(self):
        self.learn = None

    def delete_foot(self, index):
        with self.lock:
            if 0 <= index < len(self.state["foot"]):
                self.state["foot"].pop(index)
                self._save()

    def _resolve_chain(self, m):
        cm = self.b.cm
        c = cm.chains.get(m.get("chain"))
        if c is not None and self.b._name(c) == m.get("chain_name"):
            return c
        for c2 in cm.chains.values():
            if self.b._has_strip(c2) and self.b._name(c2) == m.get("chain_name"):
                return c2
        return c

    def _handle_cc(self, chan, num, val):
        if num is None:
            return
        pressed = (val or 0) >= 64
        if self.learn and pressed:
            if time.time() - self.learn["ts"] > 60:
                self.learn = None
            else:
                m = dict(self.learn)
                m.pop("ts", None)
                m["cc"], m["midi_chan"] = int(num), int(chan) if chan is not None else None
                with self.lock:
                    self.state["foot"] = [f for f in self.state["foot"]
                                          if not (f["cc"] == m["cc"] and f.get("midi_chan") == m["midi_chan"])]
                    self.state["foot"].append(m)
                    self._save()
                self.last_learn = m
                self.learn = None
                self.foot_held[(m["cc"], m["midi_chan"])] = True
                log.info(f"ZynSimple: Fußschalter CC{num} → {m['action']}")
                return
        for m in list(self.state["foot"]):
            if m.get("cc") != num or (m.get("midi_chan") is not None and m.get("midi_chan") != chan):
                continue
            key = (num, m.get("midi_chan"))
            was = self.foot_held.get(key, False)
            self.foot_held[key] = pressed
            if pressed == was:
                continue
            chain = self._resolve_chain(m)
            if chain is None:
                continue
            if m.get("mode") == "hold":
                self._do_foot(m, chain, pressed)
            elif pressed:
                self._do_foot(m, chain, None)

    def _do_foot(self, m, chain, state):
        a = m.get("action")
        if a == "freeze":
            self.set_freeze(chain, state)
        elif a == "mute":
            self.b.set_toggle(chain, "mute", None if state is None else (1 if state else 0))
        elif a == "fx":
            procs = self.b._fx_procs(chain)
            i = int(m.get("fx") or 0)
            if 0 <= i < len(procs):
                on = self.b._fx_on(procs[i])
                if state is None or bool(state) != bool(on):
                    self.b._toggle_fx(chain, i)

    def foot_info(self):
        return {"mappings": self.state["foot"],
                "learning": ({k: v for k, v in self.learn.items() if k != "ts"} if self.learn else None),
                "last_learn": self.last_learn}

    # ------------------------------------------------------------------
    # Handpan-Vorlage
    # ------------------------------------------------------------------

    def available_inputs(self):
        try:
            import zynautoconnect
            return max(2, len(zynautoconnect.get_audio_capture_ports()))
        except Exception:
            return 2

    def plan_handpan(self):
        info = getattr(self.b.cm, "engine_info", None) or {}
        plan = []
        for role, names in HANDPAN_CHAIN:
            found = next((n for n in names if n in info), None)
            if found:
                plan.append((role, found))
        return plan

    def create_handpan(self, inputs, title="Handpan"):
        cm = self.b.cm
        plan = self.plan_handpan()
        if not plan:
            raise RuntimeError("Keine passenden Effekte auf diesem Zynthian gefunden")
        inputs = [int(i) for i in inputs if 1 <= int(i) <= 32] or [1]
        self.b._jobs.put((self._create_handpan, (plan, inputs, title)))
        return [n[3:] for _, n in plan]

    def _create_handpan(self, plan, inputs, title):
        import zynautoconnect
        cm, sm = self.b.cm, self.b.sm
        sm.start_busy("zynsimple_handpan", "Handpan wird angelegt")
        try:
            chain_id = cm.add_chain(None, None, False, True, None, fast_refresh=True)
            if chain_id is None:
                raise RuntimeError("Kette konnte nicht angelegt werden")
            procs = {}
            for role, eng in plan:
                p = cm.add_processor(chain_id, eng)
                if p:
                    procs[role] = p
            cm.add_processor(chain_id, "MI")
            try:
                cm.set_chain_title(chain_id, title)
            except Exception:
                cm.chains[chain_id].title = title
            try:
                cm.set_chain_audio_inputs(chain_id, inputs)
            except Exception:
                cm.chains[chain_id].audio_in = inputs
                cm.chains[chain_id].rebuild_audio_graph()
            try:
                cm.rebuild_optimisation_cache()
            except Exception:
                pass
            zynautoconnect.request_audio_connect(True)
            zynautoconnect.request_midi_connect(True)
            # Sinnvolle Startwerte
            hp = procs.get("lowcut")
            if hp:
                for z in hp.controllers_dict.values():
                    if RE_HP_FREQ.search(_text(z)) and float(z.value_min) <= 90 <= float(z.value_max):
                        z.set_value(90)
                        break
            dl = procs.get("delay")
            if dl and self._sync_target(dl):
                self.state["sync"][str(dl.id)] = "1/4."
                self._save()
                self._apply_sync(dl)
            log.info(f"ZynSimple: Handpan-Kette {chain_id} angelegt ({', '.join(e for _, e in plan)})")
            self.autosave(force=True)
        except Exception as e:
            log.exception(f"ZynSimple: Handpan-Vorlage fehlgeschlagen: {e}")
        finally:
            sm.end_busy("zynsimple_handpan")

    # ------------------------------------------------------------------
    # Automatisches Speichern
    # ------------------------------------------------------------------

    def start_autosave(self, tk_root):
        if not self.autosave_info["enabled"]:
            return
        # Damit der Zynthian den gespeicherten Stand beim Start lädt
        try:
            from zyngui import zynthian_gui_config
            import zynconf
            if not zynthian_gui_config.restore_last_state:
                zynthian_gui_config.restore_last_state = 1
                zynconf.save_config({"ZYNTHIAN_UI_RESTORE_LAST_STATE": "1"})
                log.info("ZynSimple: „Letzten Stand beim Start laden“ eingeschaltet")
        except Exception as e:
            log.warning(f"ZynSimple: Start-Wiederherstellung nicht einstellbar ({e})")
        interval = max(10, int(self.settings.get("autosave_seconds", 20))) * 1000

        def loop():
            try:
                self.autosave()
            except Exception as e:
                self.autosave_info["error"] = str(e)
            tk_root.after(interval, loop)

        tk_root.after(interval, loop)

    def autosave(self, force=False):
        if not self.autosave_info["enabled"]:
            return
        sm = self.b.sm
        if not force and time.monotonic() - self._boot < 30:
            return
        try:
            if sm.is_busy() and not force:
                return
        except Exception:
            pass
        try:
            if len(self.b.cm.chains) <= 1 and not force:
                return   # leerer Zustand – nichts überschreiben
        except Exception:
            pass
        state = sm.get_state()
        data = json.JSONEncoder().encode(state)
        h = hash(data)
        if h == self._last_hash and not force:
            return
        path = sm.last_state_snapshot_fpath
        tmp = path + ".zynsimple.tmp"
        with open(tmp, "w") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        self._last_hash = h
        self.autosave_info["last"] = time.time()
        self.autosave_info["error"] = None
        log.debug("ZynSimple: automatisch gespeichert")
