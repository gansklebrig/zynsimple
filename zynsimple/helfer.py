# -*- coding: utf-8 -*-
"""
ZynSimple – Bedien-Erleichterungen:
  - Auto-Gain: spielen lassen, Eingangsverstärkung passend einstellen
  - Limiter am Hauptausgang (Schutz vor Übersteuern)
  - Tonart & Stimmgerät (Tonhöhe eines Eingangs live erkennen)
  - Set-Aufnahme mit einem Knopf (Zynthian-Recorder)
  - Looper-Bedienung (SooperLooper in einer Spur)
  - Sicherung & Wiederherstellen aller Einstellungen
"""

import io
import json
import logging
import math
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile

log = logging.getLogger("zynsimple")

HOME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURE_DIR = "/zynthian/zynthian-my-data/capture"
NOTEN = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "H"]

# ---------------------------------------------------------------------------
# Tonart
# ---------------------------------------------------------------------------
# Wert: "" = keine, sonst "<Ton 0–11>:<dur|moll>", z. B. "2:moll" = D-Moll
TONARTEN = [("", "keine")] + [(f"{i}:moll", f"{NOTEN[i]}-Moll") for i in range(12)] + \
           [(f"{i}:dur", f"{NOTEN[i]}-Dur") for i in range(12)]

DUR = [0, 2, 4, 5, 7, 9, 11]
MOLL = [0, 2, 3, 5, 7, 8, 10]


def tonart_name(wert):
    return next((t for v, t in TONARTEN if v == wert), "keine")


def tonleiter(wert):
    """Töne (0–11) der eingestellten Tonart, oder None."""
    try:
        ton, art = str(wert).split(":")
        ton = int(ton) % 12
    except Exception:
        return None
    return {(ton + s) % 12 for s in (MOLL if art == "moll" else DUR)}


def passende_tonarten(wert):
    """Harmonisch passende Tonarten (Camelot: gleich, ±1 Quinte, Paralleltonart) als (ton, art)."""
    try:
        ton, art = str(wert).split(":")
        ton = int(ton) % 12
    except Exception:
        return []
    out = {(ton, art), ((ton + 7) % 12, art), ((ton + 5) % 12, art)}
    out.add(((ton + 3) % 12, "dur") if art == "moll" else ((ton + 9) % 12, "moll"))
    return sorted(out)


# ---------------------------------------------------------------------------
# Auto-Gain
# ---------------------------------------------------------------------------

class AutoGain:
    ZIEL_DB = -8.0      # Spitzen sollen hier landen – Luft für laute Schläge

    def __init__(self, bridge):
        self.b = bridge
        self.lauf = None    # {"chain", "ende", "peak", "phase", "text"}

    def start(self, chain_id, sekunden=10):
        chain = self.b._chain(chain_id)
        if self.b._ctrl(chain, "gain") is None:
            raise RuntimeError("Diese Spur hat keinen Gain-Regler")
        self.lauf = {"chain": chain_id, "ende": time.monotonic() + sekunden, "peak": -99.0,
                     "phase": "hoeren", "text": "", "sek": sekunden}
        threading.Thread(target=self._run, name="zynsimple-autogain", daemon=True).start()
        return True

    def stop(self):
        if self.lauf:
            self.lauf["phase"] = "abgebrochen"

    def info(self):
        l_ = self.lauf
        if not l_:
            return None
        rest = max(0, l_["ende"] - time.monotonic())
        return {"phase": l_["phase"], "rest": rest, "peak": l_["peak"], "text": l_["text"], "sek": l_["sek"]}

    def _run(self):
        l_ = self.lauf
        try:
            chain = self.b._chain(l_["chain"])
            while time.monotonic() < l_["ende"] and l_["phase"] == "hoeren":
                m = self.b._dpm(chain)
                l_["peak"] = max(l_["peak"], m[0], m[1])
                time.sleep(0.04)
            if l_["phase"] != "hoeren":
                return
            if l_["peak"] < -55:
                l_["phase"], l_["text"] = "fehler", "Nichts gehört – ist der richtige Eingang gewählt?"
                return
            z = self.b._ctrl(chain, "gain")
            alt = float(z.value)
            neu = alt + (self.ZIEL_DB - l_["peak"])
            neu = max(float(z.value_min), min(float(z.value_max), neu))
            self.b.set_gain(chain, neu)
            diff = int(round(neu)) - int(round(alt))
            if abs(diff) < 1:
                l_["text"] = "Pegel passt schon – nichts geändert"
            else:
                l_["text"] = f"Gain {'+' if neu > 0 else ''}{int(round(neu))} dB ({'+' if diff > 0 else ''}{diff} dB)"
            if self.b.extras:
                self.b.extras.mark_dirty()
            l_["phase"] = "fertig"
        except Exception as e:
            l_["phase"], l_["text"] = "fehler", str(e)
            log.warning(f"ZynSimple Auto-Gain: {e}")


# ---------------------------------------------------------------------------
# Limiter am Hauptausgang
# ---------------------------------------------------------------------------

LIMITER = ["JV/x42-dpl - Digital Peak Limiter Stereo", "JV/x42-dpl Digital Peak Limiter Stereo",
           "JV/LSP Limiter Stereo", "JV/Calf Limiter", "JV/Fast Lookahead limiter"]
RE_LIMITER = re.compile(r"limit", re.I)


def limiter_proc(bridge):
    try:
        main = bridge.cm.chains.get(0)
        for p in bridge._fx_procs(main):
            if RE_LIMITER.search(str(p.get_name() or "")) or RE_LIMITER.search(str(getattr(p, "engine", ""))):
                return p
    except Exception:
        pass
    return None


def limiter_setzen(bridge, an):
    """Limiter am Hauptausgang an- oder ausschalten (läuft im Arbeits-Thread der Brücke)."""
    done = threading.Event()
    res = {}

    def job():
        try:
            p = limiter_proc(bridge)
            if an and p is None:
                info = getattr(bridge.cm, "engine_info", None) or {}
                eng = next((e for e in LIMITER if e in info), None)
                if not eng:
                    raise RuntimeError("Kein Limiter-Plugin auf diesem Zynthian gefunden")
                p = bridge.cm.add_processor(0, eng)
                if p is not None:
                    for z in p.controllers_dict.values():
                        t = f"{z.symbol} {getattr(z, 'name', '')}".lower()
                        try:
                            if re.search(r"thresh|limit|ceil", t) and float(z.value_min) <= -1 <= float(z.value_max):
                                z.set_value(-1.0)
                            elif re.search(r"gain|input", t) and float(z.value_min) <= 0 <= float(z.value_max):
                                z.set_value(0.0)
                        except Exception:
                            pass
                res["text"] = "Limiter ist an – der Hauptausgang kann nicht mehr übersteuern"
            elif not an and p is not None:
                bridge.cm.remove_processor(0, p)
                res["text"] = "Limiter ist aus"
            else:
                res["text"] = "Limiter ist " + ("an" if an else "aus")
            if bridge.extras:
                bridge.extras.autosave(force=True)
        except Exception as e:
            res["error"] = str(e)
        finally:
            done.set()

    bridge._jobs.put((job, ()))
    done.wait(20)
    if res.get("error"):
        raise RuntimeError(res["error"])
    return res.get("text", "")


# ---------------------------------------------------------------------------
# Stimmgerät
# ---------------------------------------------------------------------------

class Stimmgeraet:
    """Hört auf einen Eingang (JACK) und erkennt die Tonhöhe (Autokorrelation)."""

    def __init__(self):
        self.client = None
        self.eingang = 1
        self.buf = []
        self.sr = 48000
        self.wert = {"hz": None, "note": None, "cent": 0, "pegel": -99}
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def laeuft(self):
        return self.client is not None

    def start(self, eingang=1):
        self.stop()
        import jack
        self.eingang = int(eingang)
        self._stop.clear()
        c = jack.Client("zynsimple_stimmgeraet", no_start_server=True)
        port = c.inports.register("ein")
        self.sr = c.samplerate
        self.buf = []

        @c.set_process_callback
        def process(frames):
            data = bytes(port.get_buffer())    # float32, kopiert – die Analyse läuft außerhalb
            with self._lock:
                self.buf.append(data)
                if len(self.buf) > 32:
                    del self.buf[:-32]

        c.activate()
        quellen = c.get_ports(is_audio=True, is_output=True, is_physical=True)
        if len(quellen) >= self.eingang:
            c.connect(quellen[self.eingang - 1], port)
        self.client = c
        threading.Thread(target=self._analyse, name="zynsimple-stimmgeraet", daemon=True).start()

    def stop(self):
        self._stop.set()
        c, self.client = self.client, None
        if c is not None:
            try:
                c.deactivate()
                c.close()
            except Exception:
                pass
        self.wert = {"hz": None, "note": None, "cent": 0, "pegel": -99}

    def _analyse(self):
        import array
        try:
            import numpy as np
        except Exception:
            np = None
        while not self._stop.is_set():
            time.sleep(0.08)
            with self._lock:
                roh = b"".join(self.buf[-8:])
            if len(roh) < 4 * 2048:
                continue
            a = array.array("f")
            a.frombytes(roh[-4 * 4096:] if len(roh) >= 4 * 4096 else roh)
            hz, pegel = (self._pitch_np(np, a) if np is not None else self._pitch_py(a))
            if hz is None:
                self.wert = {"hz": None, "note": None, "cent": 0, "pegel": pegel}
                continue
            midi = 69 + 12 * math.log2(hz / 440.0)
            n = int(round(midi))
            self.wert = {"hz": round(hz, 1), "note": n % 12, "oktave": n // 12 - 1,
                         "cent": int(round((midi - n) * 100)), "pegel": pegel}

    def _pitch_np(self, np, a):
        x = np.frombuffer(a.tobytes(), dtype=np.float32).astype(np.float64)
        x = x - x.mean()
        rms = float(np.sqrt((x * x).mean()) or 1e-9)
        pegel = 20 * math.log10(rms + 1e-9)
        if pegel < -50:
            return None, pegel
        n = len(x)
        spec = np.fft.rfft(x, 2 * n)
        ac = np.fft.irfft(spec * np.conj(spec))[:n]
        lo, hi = int(self.sr / 1100), int(self.sr / 50)
        seg = ac[lo:hi]
        if not len(seg) or ac[0] <= 0:
            return None, pegel
        k = int(np.argmax(seg)) + lo
        if ac[k] / ac[0] < 0.3:
            return None, pegel
        # parabolische Feinabstimmung
        if 1 <= k < n - 1:
            y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]
            d = (y0 - y2) / (2 * (y0 - 2 * y1 + y2)) if (y0 - 2 * y1 + y2) else 0
            k = k + d
        return self.sr / k, pegel

    def _pitch_py(self, a):
        x = a[::4]
        sr = self.sr / 4
        m = sum(x) / len(x)
        x = [v - m for v in x[-1024:]]
        rms = math.sqrt(sum(v * v for v in x) / len(x)) or 1e-9
        pegel = 20 * math.log10(rms)
        if pegel < -50:
            return None, pegel
        n = len(x)
        lo, hi = int(sr / 1100) or 1, min(n - 1, int(sr / 50))
        best, bk = 0.0, 0
        e0 = sum(v * v for v in x)
        for k in range(lo, hi):
            s = 0.0
            for i in range(0, n - k, 2):
                s += x[i] * x[i + k]
            if s > best:
                best, bk = s, k
        if not bk or best * 2 / e0 < 0.3:
            return None, pegel
        return sr / bk, pegel


# ---------------------------------------------------------------------------
# Set-Aufnahme
# ---------------------------------------------------------------------------

def _recorder(bridge):
    sm = bridge.sm
    for name in ("audio_recorder",):
        r = getattr(sm, name, None) or getattr(bridge.zyngui, name, None)
        if r is not None:
            return r
    return None


def aufnahme_laeuft(bridge):
    r = _recorder(bridge)
    if r is None:
        return False
    for attr in ("rec_proc", "recording"):
        v = getattr(r, attr, None)
        if v is not None and not callable(v):
            return bool(v)
    st = getattr(r, "status", None)
    if callable(st):
        try:
            return bool(st())
        except Exception:
            return False
    return bool(st)


def aufnahme_umschalten(bridge):
    r = _recorder(bridge)
    if r is None:
        raise RuntimeError("Der Zynthian-Recorder ist auf diesem System nicht verfügbar")
    if aufnahme_laeuft(bridge):
        for fn in ("stop_recording",):
            if hasattr(r, fn):
                getattr(r, fn)()
                return "Aufnahme gespeichert – am Handy unter Extras → Aufnahmen"
    else:
        f = getattr(r, "start_recording")
        try:
            f()
        except TypeError:
            f(None)
        return "Aufnahme läuft – nochmal drücken zum Beenden"
    raise RuntimeError("Recorder reagiert nicht")


def aufnahmen():
    out = []
    try:
        for root, _, files in os.walk(CAPTURE_DIR):
            for f in files:
                if f.lower().endswith((".wav", ".flac", ".ogg", ".mp3")):
                    p = os.path.join(root, f)
                    st = os.stat(p)
                    out.append({"name": os.path.relpath(p, CAPTURE_DIR), "mb": round(st.st_size / 1e6, 1),
                                "t": int(st.st_mtime)})
    except OSError:
        pass
    return sorted(out, key=lambda x: -x["t"])[:40]


def aufnahme_pfad(name):
    p = os.path.realpath(os.path.join(CAPTURE_DIR, name))
    if not p.startswith(os.path.realpath(CAPTURE_DIR) + os.sep) or not os.path.isfile(p):
        raise FileNotFoundError(name)
    return p


# ---------------------------------------------------------------------------
# Looper (SooperLooper als Effekt in einer Spur)
# ---------------------------------------------------------------------------

LOOPER_ENGINES = ["SL", "JV/SooperLooper", "AP/SooperLooper"]
RE_LOOPER = re.compile(r"looper|^SL$", re.I)
LOOP_TASTEN = [("record", "● Aufnehmen", r"^record$|rec(ord)?$"), ("overdub", "＋ Darüber", r"overdub"),
               ("trigger", "▶ Abspielen", r"trigger|^play$"), ("mute", "◼ Stumm", r"^mute$"),
               ("undo", "↶ Zurück", r"^undo$"), ("clear", "✕ Löschen", r"clear|reset")]


def looper_proc(bridge, chain):
    try:
        for p in list(getattr(chain, "get_processors", lambda: [])() or []) + list(bridge._fx_procs(chain)):
            nm = f"{p.get_name()} {getattr(p, 'engine', '')} {getattr(getattr(p, 'engine', None), 'nickname', '')}"
            if RE_LOOPER.search(nm) or "sooper" in nm.lower():
                return p
    except Exception:
        pass
    return None


def looper_tasten(bridge, chain):
    p = looper_proc(bridge, chain)
    if p is None:
        return []
    out = []
    zs = list(p.controllers_dict.values())
    for key, label, rx in LOOP_TASTEN:
        z = next((z for z in zs if re.search(rx, str(z.symbol), re.I)), None)
        if z is not None:
            out.append({"key": key, "label": label, "on": bool(z.value) if key in ("record", "overdub", "mute") else False})
    st = next((z for z in zs if re.search(r"state|status", str(z.symbol), re.I)), None)
    if st is not None:
        try:
            out.append({"key": "_state", "label": str(st.get_value2label()) if hasattr(st, "get_value2label") else str(st.value)})
        except Exception:
            pass
    return out


def looper_druck(bridge, chain, key):
    p = looper_proc(bridge, chain)
    if p is None:
        raise RuntimeError("In dieser Spur ist kein Looper")
    rx = next((r for k, _, r in LOOP_TASTEN if k == key), None)
    z = next((z for z in p.controllers_dict.values() if rx and re.search(rx, str(z.symbol), re.I)), None)
    if z is None:
        raise RuntimeError("Diese Looper-Funktion gibt es hier nicht")
    if key in ("record", "overdub", "mute"):
        z.set_value(0 if z.value else z.value_max)
    else:
        z.set_value(z.value_max)
        threading.Timer(0.15, lambda: z.set_value(z.value_min)).start()


# ---------------------------------------------------------------------------
# Sicherung
# ---------------------------------------------------------------------------

SICHERN = ["zynsimple.json", "zynsimple_state.json"]
DJ_SICHERN = ["/zynthian/zynthian-my-data/dj/einstellungen.sh",
              "/zynthian/zynthian-my-data/dj/.mixxx/mixxx.cfg"]


def sicherung_bauen(bridge):
    """ZIP mit allen ZynSimple-Einstellungen, Szenen und dem letzten Mischer-Zustand."""
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
        for f in SICHERN:
            p = os.path.join(HOME_DIR, f)
            if os.path.isfile(p):
                z.write(p, f)
        try:
            p = bridge.sm.last_state_snapshot_fpath
            if os.path.isfile(p):
                z.write(p, "last_state.zss")
        except Exception:
            pass
        for p in DJ_SICHERN:
            if os.path.isfile(p):
                z.write(p, "dj/" + os.path.basename(p))
        from . import VERSION
        z.writestr("SICHERUNG.txt", f"ZynSimple {VERSION} · {time.strftime('%d.%m.%Y %H:%M')}\n"
                                    "Wiederherstellen: Handy → Extras → Sicherung, oder USB-Stick einstecken\n"
                                    "und am Zynthian Einstellungen → System → Wiederherstellen.\n")
    return mem.getvalue()


def sicherung_name():
    return time.strftime("Sicherung-ZynSimple-%Y-%m-%d_%H-%M.zip")


def sicherung_einspielen(bridge, daten):
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        namen = z.namelist()
        if not any(n in namen for n in SICHERN + ["last_state.zss"]):
            raise ValueError("Das ist keine ZynSimple-Sicherung")
        for n in namen:
            if n in SICHERN:
                ziel = os.path.join(HOME_DIR, n)
            elif n == "last_state.zss":
                ziel = bridge.sm.last_state_snapshot_fpath
            elif n.startswith("dj/") and os.path.basename(n) in [os.path.basename(p) for p in DJ_SICHERN]:
                ziel = next(p for p in DJ_SICHERN if os.path.basename(p) == os.path.basename(n))
                os.makedirs(os.path.dirname(ziel), exist_ok=True)
            else:
                continue
            tmp = ziel + ".neu"
            with open(tmp, "wb") as f:
                f.write(z.read(n))
            os.replace(tmp, ziel)
    # Oberfläche neu starten, damit alles geladen wird – losgelöst, weil sie dabei selbst endet
    cmd = ["systemd-run", "--no-block", "--collect", "--quiet", "/bin/sh", "-c", "sleep 2; systemctl restart zynthian"] \
        if shutil.which("systemd-run") else ["setsid", "/bin/sh", "-c", "sleep 2; systemctl restart zynthian"]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return "Sicherung eingespielt – die Oberfläche startet neu"


def usb_sticks():
    out = []
    for base in ("/media/root", "/media"):
        try:
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if os.path.ismount(p) and os.access(p, os.W_OK):
                    out.append(p)
        except OSError:
            pass
    return out


def sicherung_auf_stick(bridge):
    sticks = usb_sticks()
    if not sticks:
        raise RuntimeError("Kein USB-Stick gefunden – einstecken und nochmal versuchen")
    p = os.path.join(sticks[0], sicherung_name())
    with open(p, "wb") as f:
        f.write(sicherung_bauen(bridge))
    os.sync()
    return f"Gesichert auf dem Stick: {os.path.basename(p)}"


def sicherung_vom_stick(bridge):
    found = []
    for s in usb_sticks():
        try:
            for f in os.listdir(s):
                if f.lower().startswith("sicherung-zynsimple") and f.lower().endswith(".zip"):
                    found.append(os.path.join(s, f))
        except OSError:
            pass
    if not found:
        raise RuntimeError("Keine Sicherung-ZynSimple-….zip auf dem USB-Stick gefunden")
    p = max(found, key=os.path.getmtime)
    with open(p, "rb") as f:
        return sicherung_einspielen(bridge, f.read())
