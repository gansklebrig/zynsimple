# -*- coding: utf-8 -*-
"""
ZynSimple – Spuren verwalten: anlegen, löschen (mit Rückgängig), verdoppeln,
umbenennen, verschieben, Eingänge und MIDI-Kanal ändern, Systemlast.
"""

import logging
import os
import threading
import time

log = logging.getLogger("zynsimple")

UNDO_SECONDS = 20

# Neue Spur: (Vorlage, Symbol, Titel, Beschreibung, Standardname)
NEW_TRACKS = [
    ("audio", "🎤", "Audio-Eingang", "leerer Kanal für Mikro oder Instrument", "Eingang"),
    ("handpan", "🪘", "Handpan", "Low-Cut, Kompressor, Delay im Takt, Hall", "Handpan"),
    ("vocal", "🎙", "Gesang", "Low-Cut, Kompressor, Platten-Hall", "Gesang"),
    ("instrument", "🎸", "Instrument", "Low-Cut und etwas Raum", "Instrument"),
    ("synth", "🎹", "Synth", "spielt über MIDI mit", ""),
    ("looper", "🔁", "Looper", "Schichten aufnehmen und übereinanderlegen", "Looper"),
]


class Tracks:
    def __init__(self, bridge, data_dir):
        self.b = bridge
        self.dir = data_dir
        self.undo = None            # {"path", "name", "t"}
        self._lock = threading.Lock()
        self._sys = {"t": 0}
        self._cpu_prev = None

    @property
    def cm(self):
        return self.b.cm

    @property
    def sm(self):
        return self.b.sm

    # ------------------------------------------------------------------
    # Infos
    # ------------------------------------------------------------------

    def n_inputs(self):
        try:
            return self.b.extras.available_inputs()
        except Exception:
            return 2

    def info(self, chain_id):
        """Alles, was die Spur-Seite braucht."""
        chain = self.b._chain(chain_id)
        kind = self.b._kind(chain)
        ids = self._order()
        pos = ids.index(chain.chain_id) if chain.chain_id in ids else 0
        out = {
            "id": chain.chain_id,
            "name": self.b._name(chain),
            "title": str(getattr(chain, "title", "") or ""),
            "kind": kind,
            "can_delete": chain.chain_id != 0,
            "left": pos > 0,
            "right": pos < len(ids) - 1,
            "n_inputs": self.n_inputs(),
            "inputs": None,
            "midi_chan": None,
            "fx": [f.get_name() for f in self.b._fx_procs(chain)],
            "can_dup": self._can_export(),
            "can_undo": self._can_export(),
            "used": self.used_inputs(skip=chain.chain_id),
        }
        if kind != "main":
            ai = getattr(chain, "audio_in", None)
            if kind in ("audio", "other") and isinstance(ai, list):
                out["inputs"] = [int(i) for i in ai if isinstance(i, int) or str(i).isdigit()]
            mc = getattr(chain, "midi_chan", None)
            if kind == "synth" and isinstance(mc, int):
                out["midi_chan"] = mc if 0 <= mc < 16 else None
                out["midi_all"] = mc == 0xffff
        return out

    def templates(self):
        x = self.b.extras
        out = []
        for key, icon, title, sub, _ in NEW_TRACKS:
            item = {"key": key, "icon": icon, "title": title, "sub": sub}
            if key not in ("audio", "synth", "looper"):
                try:
                    item["plugins"] = [e.replace("JV/", "") for _, e in x.plan_handpan(key)]
                except Exception:
                    item["plugins"] = []
            out.append(item)
        return {"templates": out, "n_inputs": self.n_inputs(), "free": self._free_input(), "used": self.used_inputs()}

    def used_inputs(self, skip=None):
        """Welche Spur hört schon auf welchen Eingang? {"1": ["Handpan"], …}"""
        used = {}
        for c in self.b._chains():
            if c.chain_id in (0, skip):
                continue
            for i in getattr(c, "audio_in", None) or []:
                if isinstance(i, int):
                    used.setdefault(str(i), []).append(self.b._name(c))
        return used

    def _order(self):
        """Reihenfolge der Spuren ohne Summe, wie sie im Mischer erscheinen."""
        return [s.chain_id for s in self.b._chains() if s.chain_id != 0]

    def undo_info(self):
        u = self.undo
        if not u:
            return None
        left = UNDO_SECONDS - (time.monotonic() - u["t"])
        if left <= 0:
            return None
        return {"name": u["name"], "left": int(left + 0.99)}

    # ------------------------------------------------------------------
    # Systemlast (DSP, CPU, Temperatur, Aussetzer)
    # ------------------------------------------------------------------

    def sys(self):
        now = time.monotonic()
        if now - self._sys["t"] < 1.0:
            return self._sys["v"]
        v = {"dsp": None, "cpu": None, "temp": None, "xrun": False, "volt": False, "hot": False}
        sm = self.sm
        try:
            v["dsp"] = int(round(float(sm.status_cpu_load)))
        except Exception:
            pass
        try:
            v["xrun"] = bool(getattr(sm, "status_xrun", False))
            v["volt"] = bool(getattr(sm, "status_undervoltage", False))
            v["hot"] = bool(getattr(sm, "status_overtemp", False))
        except Exception:
            pass
        try:
            with open("/proc/stat") as f:
                z = f.readline().split()
            nums = list(map(int, z[1:9]))
            idle, total = nums[3] + nums[4], sum(nums)
            if self._cpu_prev and total > self._cpu_prev[1]:
                v["cpu"] = int(round(100 * (1 - (idle - self._cpu_prev[0]) / (total - self._cpu_prev[1]))))
            self._cpu_prev = (idle, total)
        except Exception:
            pass
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                v["temp"] = int(round(int(f.read().strip()) / 1000))
        except Exception:
            pass
        self._sys = {"t": now, "v": v}
        return v

    # ------------------------------------------------------------------
    # Aktionen
    # ------------------------------------------------------------------

    def add(self, template, inputs=None, title=None, midi_chan=0, eng=None):
        """Neue Spur aus einer Vorlage. Liefert die neue Kanal-ID."""
        x = self.b.extras
        if template == "synth":
            if not eng:
                raise ValueError("Welcher Synth? (eng fehlt)")
            return x.create_synth(eng, int(midi_chan or 0), title or None)
        tpl = next((t for t in NEW_TRACKS if t[0] == template), None)
        if not tpl:
            raise ValueError("Diese Vorlage gibt es nicht")
        inputs = [int(i) for i in (inputs or []) if 1 <= int(i) <= 32] or [self._free_input()]
        if not title:
            title = tpl[4] if template != "audio" else f"Eingang {'+'.join(str(i) for i in inputs)}"
        return x.create_handpan(inputs, title, template=template, wait=True)

    def _free_input(self):
        """Erster Eingang, den noch keine Spur benutzt."""
        used = set()
        for c in self.cm.chains.values():
            for i in getattr(c, "audio_in", None) or []:
                if isinstance(i, int):
                    used.add(i)
        n = self.n_inputs()
        return next((i for i in range(1, n + 1) if i not in used), 1)

    def rename(self, chain_id, title):
        title = str(title or "").strip()[:32]
        if not title:
            raise ValueError("Name ist leer")
        chain = self.b._chain(chain_id)
        if chain.chain_id == 0:
            raise ValueError("Die Summe kann man nicht umbenennen")
        try:
            self.cm.set_chain_title(chain.chain_id, title)
        except Exception:
            chain.title = title
        return title

    def set_inputs(self, chain_id, inputs):
        chain = self.b._chain(chain_id)
        inputs = sorted({int(i) for i in inputs if 1 <= int(i) <= 32})
        try:
            self.cm.set_chain_audio_inputs(chain.chain_id, inputs or None)
        except Exception:
            chain.audio_in = inputs
            try:
                chain.rebuild_audio_graph()
            except Exception:
                pass
        if not inputs:
            # Zynthian setzt bei leerer Liste „SYSTEM“ – wir wollen wirklich gar keinen Eingang
            chain.audio_in = []
            try:
                chain.rebuild_audio_graph()
            except Exception:
                pass
        self._reconnect()
        return [i for i in (getattr(chain, "audio_in", None) or []) if isinstance(i, int)]

    def toggle_input(self, chain_id, n):
        chain = self.b._chain(chain_id)
        cur = [i for i in (getattr(chain, "audio_in", None) or []) if isinstance(i, int)]
        n = int(n)
        return self.set_inputs(chain_id, [i for i in cur if i != n] if n in cur else cur + [n])

    def set_midi(self, chain_id, chan):
        chain = self.b._chain(chain_id)
        chan = max(0, min(15, int(chan)))
        self.cm.set_midi_chan(chain.chain_id, chan)
        self._reconnect(midi=True)
        return chan

    def move(self, chain_id, direction):
        chain = self.b._chain(chain_id)
        if chain.chain_id == 0:
            raise ValueError("Die Summe bleibt rechts")
        ids = self._order()
        if chain.chain_id not in ids:
            raise ValueError("Spur nicht gefunden")
        pos = ids.index(chain.chain_id)
        tgt = pos + (1 if int(direction) > 0 else -1)
        if not 0 <= tgt < len(ids):
            return pos
        other = ids[tgt]
        cm = self.cm
        if hasattr(cm, "ordered_chain_ids"):             # Oram
            order = cm.ordered_chain_ids
            a, b = order.index(chain.chain_id), order.index(other)
            order[a], order[b] = order[b], order[a]
            try:
                from zyngui import zynthian_gui_config
                zynthian_gui_config.zyngui.screens["audio_mixer"].refresh_visible_strips()
            except Exception:
                pass
            return tgt
        keys = list(cm.chains)
        cm.move_chain(chain.chain_id, keys.index(other))
        return tgt

    def _move_to(self, chain_id, idx):
        """Schiebt eine Spur Schritt für Schritt an Position idx (ohne Summe gezählt)."""
        for _ in range(64):
            ids = self._order()
            if chain_id not in ids:
                return
            pos = ids.index(chain_id)
            if pos == idx or not 0 <= idx < len(ids):
                return
            self.move(chain_id, 1 if idx > pos else -1)

    def _can_export(self):
        return hasattr(self.sm, "export_chain") and hasattr(self.sm, "load_snapshot")

    def _export(self, chain_id, path):
        self.sm.export_chain(path, chain_id)
        if not os.path.isfile(path) or os.path.getsize(path) < 10:
            raise RuntimeError("Spur konnte nicht zwischengespeichert werden")

    def _import(self, path):
        try:
            self.sm.load_snapshot(path, load_chains=True, load_sequences=False, merge=True)
        except TypeError:
            self.sm.load_snapshot(path, True, False, True)
        self._reconnect(midi=True)

    def remove(self, chain_id):
        """Löscht eine Spur. Vorher wird sie gesichert, damit „Rückgängig“ geht."""
        chain = self.b._chain(chain_id)
        cid = chain.chain_id
        if cid == 0:
            raise ValueError("Die Summe kann man nicht löschen")
        name = self.b._name(chain)
        ids = self._order()
        pos = ids.index(cid) if cid in ids else None
        with self._lock:
            undo = None
            if self._can_export():
                path = os.path.join(self.dir, "zynsimple_undo.zss")
                try:
                    self._export(cid, path)
                    undo = {"path": path, "name": name, "t": time.monotonic(), "pos": pos}
                except Exception as e:
                    log.warning(f"ZynSimple: Rückgängig nicht möglich ({e})")
            try:
                getattr(self.b.extras, "trials", {}).pop(cid, None)
            except Exception:
                pass
            ok = self.cm.remove_chain(cid)
            if ok is False:
                raise RuntimeError("Zynthian hat das Löschen abgelehnt")
            self._reconnect(midi=True)
            self.undo = undo
        try:
            self.b.extras.autosave(force=True)
        except Exception:
            pass
        return {"name": name, "undo": bool(undo)}

    def undo_remove(self):
        u = self.undo_info()
        if not u:
            raise RuntimeError("Nichts zum Wiederherstellen")
        with self._lock:
            path, pos = self.undo["path"], self.undo.get("pos")
            self.undo = None
            before = set(self.cm.chains)
            self._import(path)
            new = [c for c in self.cm.chains if c not in before]
            if new and pos is not None:
                try:
                    self._move_to(new[0], pos)
                except Exception as e:
                    log.debug(f"Rückgängig: Position {e}")
        try:
            self.b.extras.autosave(force=True)
        except Exception:
            pass
        return new[0] if new else None

    def duplicate(self, chain_id):
        chain = self.b._chain(chain_id)
        if chain.chain_id == 0:
            raise ValueError("Die Summe gibt es nur einmal")
        if not self._can_export():
            raise RuntimeError("Verdoppeln geht auf diesem Zynthian nicht")
        with self._lock:
            path = os.path.join(self.dir, "zynsimple_dup.zss")
            self._export(chain.chain_id, path)
            before = set(self.cm.chains)
            self._import(path)
            new = [c for c in self.cm.chains if c not in before]
        if new:
            try:
                self.rename(new[0], (self.b._name(chain) + " 2")[:32])
                ids = self._order()
                self._move_to(new[0], ids.index(chain.chain_id) + 1)
            except Exception as e:
                log.debug(f"Verdoppeln: {e}")
        try:
            self.b.extras.autosave(force=True)
        except Exception:
            pass
        return new[0] if new else None

    def _reconnect(self, midi=False):
        try:
            self.cm.rebuild_optimisation_cache()
        except Exception:
            pass
        try:
            import zynautoconnect
            zynautoconnect.request_audio_connect(True)
            if midi:
                zynautoconnect.request_midi_connect(True)
        except Exception:
            pass
