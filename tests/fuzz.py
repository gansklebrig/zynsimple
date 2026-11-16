"""Fuzz-Test für ZynSimple: drückt zufällig alle Tasten, Regler und Bildschirm-Knöpfe in allen Ansichten.

Prüft: keine Abstürze (auch nicht im Log), und aus jeder Ansicht führt BACK zurück ins Mischpult.
Aufruf (im Repo):  python3 tests/fuzz.py [schritte] [seed]      → Rückgabe 1, wenn etwas schiefging
Läuft automatisch bei jedem Hochladen (GitHub Actions, .github/workflows/test.yml)."""
import collections
import html
import logging
import os
import random
import sys
import tempfile
import threading
import time
import traceback

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HIER)
sys.path[:0] = [REPO, os.path.join(HIER, "stub"), os.path.join(REPO, "dj"), HIER]
SCHRITTE = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
random.seed(SEED)
os.environ.setdefault("HOME", tempfile.mkdtemp())

# ---------- Canvas-Ersatz ----------
from canvas_attrappe import C  # noqa: E402
JOBS = []          # (fällig, id, fn)
JOB_N = [0]
UHR = [0.0]


class Canvas(C):  # noqa: F821
    def __init__(s, *a, **k):
        C.__init__(s, 800, 440)  # noqa: F821

    def bind(s, *a, **k): pass
    def grid(s, *a, **k): pass
    def config(s, *a, **k): pass
    configure = config
    def tag_bind(s, *a, **k): pass
    def lift(s, *a): pass
    def tag_lower(s, *a): pass
    def focus_set(s): pass
    def winfo_toplevel(s): return s
    def move(s, *a): pass
    def find_withtag(s, t): return ()
    def gettags(s, i): return ()
    def cget(s, k): return ""
    def create_image(s, *a, **k): return s._add("")
    def create_window(s, *a, **k): return s._add("")
    def update_idletasks(s): pass
    def after(s, ms=0, fn=None, *args):
        if fn is None:
            return None
        JOB_N[0] += 1
        JOBS.append((UHR[0] + ms / 1000.0, JOB_N[0], lambda: fn(*args)))
        return f"after#{JOB_N[0]}"

    def after_cancel(s, jid):
        try:
            n = int(str(jid).split("#")[1])
        except Exception:
            return
        JOBS[:] = [j for j in JOBS if j[1] != n]

    def after_idle(s, fn, *a):
        return s.after(0, fn, *a)


import tkinter  # stub
tkinter.Canvas = Canvas
tkinter.PhotoImage = type("PhotoImage", (), {"__init__": lambda s, *a, **k: None})

FEHLER = collections.OrderedDict()


class Fang(logging.Handler):
    def emit(self, rec):
        if rec.levelno >= logging.ERROR:
            tb = "".join(traceback.format_exception(*rec.exc_info)) if rec.exc_info else rec.getMessage()
            schluessel = tb.strip().splitlines()[-1][:160] + " @ " + (
                [z for z in tb.splitlines() if "zynsimple" in z and "File" in z] or ["?"])[-1].strip()[:160]
            FEHLER.setdefault(schluessel, (tb, list(VERLAUF)[-12:]))


logging.getLogger().addHandler(Fang())
logging.getLogger().setLevel(logging.WARNING)

from zynsimple import DEFAULTS  # noqa: E402
import zynsimple.screen as scr  # noqa: E402
import zynsimple.dj as dj_  # noqa: E402

VERLAUF = collections.deque(maxlen=40)


# ---------- Zynthian-Ersatz ----------
class ZG:
    def __init__(s):
        s.zynpot_pr_state = [0, 0, 0, 0]
        s.zynswitch_autolong_disabled = False
        class GS:
            def setup(self, *a, **k): VERLAUF.append(("grid_sel", a[:1]))
        s.screens = {"grid_sel": GS()}
        s._zs_modus = "simple"
        s._zs_settings = dict(DEFAULTS)
        s._zs_bridge = None
        s.alt = False
        s.current_screen = "zynsimple"
        s.chain_manager = None
        s.state_manager = None

    def get_alt_mode(s): return s.alt
    def show_screen(s, *a, **k): VERLAUF.append(("zyngui.show_screen", a))
    def show_screen_reset(s, *a, **k): VERLAUF.append(("zyngui.show_screen_reset", a))
    def close_screen(s, *a, **k): pass
    def show_keyboard(s, cb, text="", *a, **k): VERLAUF.append(("tastatur", text))
    def cuia_toggle_alt_mode(s, *a): s.alt = not s.alt
    def __getattr__(s, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return lambda *a, **k: None


def strip(i, name, kind="audio"):
    return {"id": i, "name": name, "kind": kind, "level": 0.7, "gain": 0 if kind != "main" else None, "mute": False,
            "solo": False if kind != "main" else None, "meter": [-12, -14, -6, -8], "preset": None,
            "fx": [] if kind == "main" else [{"i": 0, "name": "Kompressor", "on": True, "kind": "comp"},
                                             {"i": 1, "name": "Delay", "on": False, "kind": "delay", "sync": "1/4."},
                                             {"i": 2, "name": "Hall", "on": True, "kind": "reverb"}],
            "freeze": False if kind != "main" else None, "throw": False}


class Hy:
    vorne = False
    phase = None
    fehler = None
    mixxx_spielt = False
    def laeuft(s): return random.random() < 0.5
    def status(s): return {"an": False, "moeglich": True, "fehler": None, "phase": None}
    def decks(s): return [{"geladen": 1, "laeuft": 1, "titel": "A", "kuenstler": "B", "bpm": 120.0, "pos": .3, "rest": 100,
                           "key_id": 22, "tonart": "Am"}, {}]
    def laden(s, *a): time.sleep(0.01); return "ok"
    def play(s, *a): pass
    def zeigen(s): pass
    def verstecken(s): pass
    def starten(s): return "startet"
    def stoppen(s): return "stopp"


class PF:
    def live_slots(s, c): return [0, 1, 2, 3]
    def slot_info(s, c, sl): return {"name": ["Tiefe", "Hall", "Echo", "Filter"][sl], "kind": "x", "value": 0.4, "text": "40 %"}
    def __getattr__(s, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return lambda *a, **k: None


class Tracks:
    def info(s, cid):
        return {"id": cid, "name": "Handpan", "title": "", "kind": "audio", "can_delete": True, "left": False, "right": True,
                "n_inputs": 2, "inputs": [1], "midi_chan": None, "fx": ["Low-Cut", "Kompressor", "Delay", "Hall"],
                "can_dup": True, "can_undo": True, "used": {}}
    def __getattr__(s, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return lambda *a, **k: 5


LOOP = {"tasten": [{"key": "record", "label": "● Aufnehmen", "on": True}, {"key": "overdub", "label": "＋", "on": False},
                   {"key": "trigger", "label": "▶", "on": False}, {"key": "mute", "label": "◼", "on": False},
                   {"key": "undo", "label": "↶", "on": False}, {"key": "clear", "label": "✕", "on": False},
                   {"key": "_state", "label": "Aufnahme"}],
        "takt": {"takte": 2, "loops": 2, "max_loops": 6, "gewaehlt": 2, "kann_takt": True}}


class Bridge:
    perform = PF()
    extras = None
    vangelis = True
    geraete = None
    tracks = Tracks()
    hybrid = Hy()
    cm = None

    def snapshot(s, *a, **k):
        st = [strip(1, "Handpan"), strip(2, "Didgeridoo"), strip(3, "Gesang"), strip(4, "Synth", "midi"), strip(0, "Summe", "main")]
        if random.random() < 0.1:
            st = [strip(0, "Summe", "main")]
        return {"strips": st, "scenes": {"1": 1, "2": 1}, "last_scene": "1", "morph_beats": 4, "tempo": 96,
                "sys": {"dsp": 23, "cpu": 31, "temp": 52},
                "szene_undo": {"n": "2", "left": 7, "leer": False} if random.random() < 0.3 else None}

    def _chain(s, cid): return type("Ch", (), {"chain_id": cid, "title": "x", "audio_slots": [], "midi_chan": 0})()
    def _name(s, c): return "Handpan"
    def _ctrl(s, *a, **k): return None
    def _fx_procs(s, *a, **k): return []

    def action(s, cid, op, v=None):
        VERLAUF.append(("action", cid, op, v))
        if op == "hf_autogain_info":
            return {"phase": random.choice(["hoeren", "fertig", "fehler"]), "rest": 6.2, "peak": -14, "text": "x"}
        if op == "scene_undo":
            return {"n": "2"}
        if op == "hf_looper":
            return LOOP
        if op in ("presets", "browse", "fx_list", "hf_presets"):
            return {"items": [{"name": "A", "id": 1}], "liste": []}
        return {}


# ---------- Bildschirm bauen ----------
import zyngui.zynthian_gui_config as cfg  # noqa: E402
import builtins
builtins._ZG = ZG()
o = scr.zynsimple_screen(Bridge(), dict(DEFAULTS))
o.settings["splash"] = False
o.splash_done = True
o.set_addr = {"url": "http://x:8090", "ip": "1.2.3.4"}
import zynsimple.settings as st_  # noqa: E402
st_.save_intern = lambda *a, **k: None
st_.save = lambda *a, **k: None
try:
    import zynsimple.updater as up
    up.status.update(current="6.8", latest="6.8", available=False)
except Exception:
    pass


class BM:
    def suche(s, **k):
        t = [{"id": i, "artist": "Künstler", "title": f"Titel {i}", "bpm": 120 + i, "tonart": "Am", "key_id": 22, "sterne": i % 5,
              "dauer": 200} for i in range(random.choice([0, 3, 12]))]
        return {"titel": t[:k.get("limit", 60)], "gesamt": len(t), "treffer": len(t)}


dj_.bibliothek_modul = lambda: BM()
_tb = dj_.tasten_modul()
_tb.DATEI = os.path.join(tempfile.mkdtemp(), "tasten.json")   # nie die echte Datei anfassen
o.data = Bridge().snapshot()
o.strips = o.data["strips"]
try:
    o.show()
except Exception:
    FEHLER.setdefault("show()", (traceback.format_exc(), []))
o.mode = "mix"
o.draw()


# ---------- Eingaben ----------
class Ev:
    def __init__(s, x, y): s.x, s.y = x, y


def alle_hits():
    out = []
    for n in dir(o):
        if n.endswith("hits"):
            v = getattr(o, n, None)
            if isinstance(v, list):
                for h in v:
                    if isinstance(h, (tuple, list)) and len(h) >= 4 and all(isinstance(z, (int, float)) for z in h[:4]):
                        out.append(h)
    return out


TASTEN = list(range(4, 36))
MODI = collections.Counter()


def schritt():
    MODI[o.mode] += 1
    r = random.random()
    if r < 0.40:
        hs = alle_hits()
        if hs and random.random() < 0.85:
            h = random.choice(hs)
            x, y = (h[0] + h[2]) / 2, (h[1] + h[3]) / 2
        else:
            x, y = random.uniform(0, 800), random.uniform(0, 440)
        VERLAUF.append(("tap", o.mode, round(x), round(y)))
        o.on_press(Ev(x, y))
        if random.random() < 0.15:
            o.on_motion(Ev(x + random.uniform(-80, 80), y + random.uniform(-80, 80)))
        if random.random() < 0.1:
            zeit(random.choice([0.6, 1.2, 2.5]))
        o.on_release(Ev(x, y))
    elif r < 0.70:
        i = random.choice(TASTEN)
        seq = random.choice([["P", "S"], ["P", "B"], ["P", "L"], ["S"], ["P"], ["B"], ["L"]])
        for t in seq:
            VERLAUF.append(("taste", o.mode, i, t))
            o.switch(i, t)
            if t == "P" and random.random() < 0.3:
                zeit(random.choice([0.5, 1.6, 3.2]))
    elif r < 0.82:
        i = random.randrange(4)
        d = random.choice([-5, -1, 1, 1, 3, 12])
        VERLAUF.append(("dreh", o.mode, i, d))
        o.zynpot_cb(i, d)
    elif r < 0.88:
        p = (random.randrange(4), random.choice("SBL"))
        VERLAUF.append(("drueck", o.mode, p))
        o.cuia_v5_zynpot_switch([p[0], p[1]] if random.random() < 0.5 else f"{p[0]},{p[1]}")
    elif r < 0.92:
        t = random.choice(["S", "B", "L"])
        VERLAUF.append(("sel", o.mode, t))
        o.switch_select(t)
    elif r < 0.94:
        VERLAUF.append(("back_action", o.mode))
        o.back_action()
    elif r < 0.96:
        o.zyngui.alt = not o.zyngui.alt
        VERLAUF.append(("alt", o.zyngui.alt))
    elif r < 0.97:
        zeit(random.choice([0.1, 1.0, 5.0, 40.0]))
    else:
        # direkt in einen Modus springen (damit alle Seiten oft genug drankommen)
        ziel = random.choice(["track", "newtrack", "settings", "tool_autogain", "tool_tuner", "tool_looper", "xy", "fxview",
                              "help", "more", "tasten", "editor", "lernen", "geraetneu"])
        VERLAUF.append(("springe", ziel))
        if ziel == "track": o.open_track(1)
        elif ziel == "newtrack": o.open_newtrack()
        elif ziel == "settings": o.open_settings()
        elif ziel.startswith("tool_"): o.open_tool(ziel[5:], 1)
        elif ziel == "xy": o.open_xy(1)
        elif ziel == "fxview": o.open_fxview()
        elif ziel == "help": o.open_help()
        elif ziel == "more": o.open_more()
        elif ziel == "tasten": o.open_tasten(random.choice(["mischer", "dj", "barden"]))
        elif ziel == "editor": o.open_editor(1, random.randrange(3))
        elif ziel == "browser": o.open_browser(1)
        elif ziel == "synth": o.open_synth_browser()
        elif ziel == "lernen": o.open_lernen()
        elif ziel == "geraetneu": o.mode = "mix"; o.neues_geraet(random.choice(["Keytar", "Arturia BeatStep Pro"]))



def zeit(sek):
    VERLAUF.append(("zeit", sek))
    UHR[0] += sek
    for _ in range(200):
        faellig = sorted([j for j in JOBS if j[0] <= UHR[0]], key=lambda j: j[0])
        if not faellig:
            break
        j = faellig[0]
        JOBS.remove(j)
        try:
            j[2]()
        except Exception:
            FEHLER.setdefault("after: " + traceback.format_exc().strip().splitlines()[-1],
                              (traceback.format_exc(), list(VERLAUF)[-12:]))


SACKGASSE = collections.Counter()
for n in range(SCHRITTE):
    try:
        schritt()
    except Exception:
        tb = traceback.format_exc()
        letzte = [z for z in tb.splitlines() if "zynsimple" in z and "File" in z]
        k = tb.strip().splitlines()[-1][:160] + " @ " + (letzte[-1].strip()[:160] if letzte else "?")
        FEHLER.setdefault(k, (tb, list(VERLAUF)[-12:]))
    # kommt man aus jedem Modus mit BACK wieder in den Mischer?
    if n % 50 == 49:
        m0 = o.mode
        for _ in range(6):
            if o.mode == "mix":
                break
            try:
                o.switch(16, "P"); o.switch(16, "S")   # BACK
            except Exception:
                FEHLER.setdefault("BACK: " + traceback.format_exc().strip().splitlines()[-1], (traceback.format_exc(), list(VERLAUF)[-12:]))
                break
        if o.mode != "mix":
            SACKGASSE[(m0, o.mode)] += 1

print("Modi besucht:", dict(MODI))
print("Sackgassen (Modus nach 6× BACK nicht Mischer):", dict(SACKGASSE))
print(f"{len(FEHLER)} verschiedene Fehler")
for k, (tb, verl) in FEHLER.items():
    print("=" * 100)
    print(k)
    print(tb[-1800:])
    print("Verlauf:", verl)
sys.exit(1 if FEHLER or SACKGASSE else 0)
