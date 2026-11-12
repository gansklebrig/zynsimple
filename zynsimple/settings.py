# -*- coding: utf-8 -*-
"""
ZynSimple – Einstellungen: eine Liste, die Touchscreen und Handy gleich anzeigen.
Änderungen landen sofort in zynsimple.json und wirken, wo möglich, ohne Neustart.
"""

import json
import logging
import os
import socket

log = logging.getLogger("zynsimple")

# (Schlüssel, Titel, Art, Auswahl, Hinweis)
#  Art: "bool" = an/aus · "choice" = Liste von (Wert, Text)
SPEC = [
    ("replace_home", "Startbildschirm", "choice", [(True, "Einfacher Mischer"), (False, "Zynthian-Mischer")],
     "was nach dem Einschalten und bei „nach Hause“ erscheint"),
    ("splash", "Start-Logo", "bool", None, "die Gans beim Hochfahren zeigen"),
    ("idle_seconds", "Bühnenbild nach", "choice", [(0, "nie"), (20, "20 s"), (45, "45 s"), (90, "1½ min"), (180, "3 min")],
     "Animation, wenn eine Weile niemand etwas bedient"),
    ("autosave", "Automatisch speichern", "bool", None, "alles bleibt nach dem Ausschalten erhalten"),
    ("strip_min_width", "Kanalbreite", "choice", [(110, "schmal"), (130, "normal"), (165, "breit")],
     "breiter = leichter zu treffen, weniger Kanäle pro Seite"),
    ("xy_spring", "XY-Feld federt zurück", "bool", None, "nach dem Loslassen zurück zum Startpunkt"),
    ("synth_midi_chan", "MIDI-Kanal neuer Synths", "choice", [(i, f"Kanal {i + 1}") for i in range(16)],
     "auf diesem Kanal hören neu angelegte Synths"),
    ("led_recolor", "Tasten-Farben ohne Blau", "bool", None, "warme LED-Farben · wirkt nach einem Neustart"),
    ("tonart", "Tonart der Band", "choice", None,
     "für Stimmgerät und DJ-Pult (passende Tracks) · z. B. Handpan-Grundton"),
    ("master_limiter", "Schutz vor Übersteuern", "bool", None, "Limiter am Hauptausgang · fängt laute Spitzen ab"),
    ("dj_auto_rec", "Set automatisch aufnehmen", "bool", None, "jedes DJ-Set landet als Datei auf dem USB-Stick"),
    ("takt", "Wer gibt den Takt vor?", "choice",
     [("senden", "Zynthian führt"), ("folgen", "TR-8S führt"), ("aus", "aus")],
     "Zynthian führt: TR-8S läuft mit · TR-8S führt: Zynthian, Looper und Mixxx folgen ihr (MIDI-Clock, USB/DIN)"),
    ("ton_anzeige", "Ton-Anzeige", "choice",
     [("keytar", "nur Keytar"), ("alle", "alle MIDI-Geräte"), ("aus", "aus")],
     "zeigt groß, welcher Ton gerade gespielt wird · grün = passt zur Tonart, rot = nicht"),
    ("bsp_drums", "BeatStep-Drums im Zynthian", "bool", None,
     "an: die Drum-Spur (Kanal 10) spielt ein Drumkit im Zynthian · aus: Drums macht die TR-8S"),
    ("start_modus", "Nach dem Einschalten", "choice",
     [("zynthian", "Mischer"), ("hybrid", "DJ + Instrumente"), ("dj", "DJ-Pult")],
     "womit der Zynthian startet – praktisch für den Auftritt"),
    ("dj_handpan_fx", "Handpan im DJ-Mix", "bool", None, "Zynthian-Eingänge 1+2 laufen mit in den Mix"),
    ("update_check", "Updates selbst suchen", "bool", None, "beim Start und alle 6 Stunden · braucht Internet"),
]


def _choices(key, choices):
    if key == "tonart":
        from .helfer import TONARTEN
        return TONARTEN
    return choices


def _config_file():
    from . import CONFIG_FILE
    return CONFIG_FILE


def items(settings):
    out = []
    for key, title, kind, choices, hint in SPEC:
        choices = _choices(key, choices)
        v = settings.get(key)
        if kind == "bool":
            text = "an" if v else "aus"
        else:
            text = next((t for val, t in choices if val == v), str(v))
        out.append({"key": key, "title": title, "kind": kind, "value": v, "text": text, "hint": hint,
                    "choices": [{"v": val, "t": t} for val, t in choices] if choices else None})
    return out


def save(settings, changes):
    """Übernimmt Änderungen in die laufenden Einstellungen und in zynsimple.json."""
    spec = {k: (kind, _choices(k, choices)) for k, _, kind, choices, _ in SPEC}
    path = _config_file()
    try:
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
    except Exception:
        stored = {}
    for key, val in changes.items():
        if key not in spec:
            raise ValueError(f"Unbekannte Einstellung {key}")
        kind, choices = spec[key]
        if kind == "bool":
            val = bool(val)
        else:
            vals = [c[0] for c in choices]
            match = next((c for c in vals if str(c) == str(val)), None)
            if match is None:
                raise ValueError(f"Ungültiger Wert für {key}")
            val = match
        settings[key] = val
        stored[key] = val
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    log.info(f"ZynSimple: Einstellungen geändert: {changes}")


def save_intern(settings, key, value):
    """Interne Merker (nicht in der Liste), z. B. ob die Hilfe schon gezeigt wurde."""
    path = _config_file()
    try:
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
    except Exception:
        stored = {}
    settings[key] = value
    stored[key] = value
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def choices_of(key):
    for k, _, kind, choices, _ in SPEC:
        if k == key:
            return _choices(k, choices) or []
    return []


def cycle(settings, key):
    """Nächster Wert (für den Touchscreen: antippen = weiterschalten)."""
    for k, _, kind, choices, _ in SPEC:
        choices = _choices(k, choices)
        if k == key:
            if kind == "bool":
                return not settings.get(key)
            vals = [c[0] for c in choices]
            cur = settings.get(key)
            i = vals.index(cur) if cur in vals else -1
            return vals[(i + 1) % len(vals)]
    raise ValueError(key)


def apply_live(bridge, key):
    """Was sofort wirken kann, sofort wirken lassen."""
    s = bridge.settings
    try:
        if key == "autosave" and bridge.extras:
            bridge.extras.autosave_info["enabled"] = bool(s.get("autosave"))
        if key == "ton_anzeige" and s.get("ton_anzeige") != "aus" and getattr(bridge, "geraete", None):
            bridge.geraete.start()
        if key == "takt":
            from . import takt
            if s.get("takt") == "aus":
                takt.aufraeumen(s)
            else:
                takt.anwenden(s)
        if key == "master_limiter":
            import threading
            from . import helfer

            def run():
                try:
                    log.info("ZynSimple: " + helfer.limiter_setzen(bridge, bool(s.get("master_limiter"))))
                except Exception as e:
                    log.warning(f"ZynSimple: Limiter: {e}")
            threading.Thread(target=run, daemon=True).start()
    except Exception as e:
        log.debug(f"Einstellung {key}: {e}")


def address(settings):
    ip = None
    try:
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.connect(("10.255.255.255", 1))
        ip = sk.getsockname()[0]
        sk.close()
    except Exception:
        pass
    port = settings.get("web_port", 8090)
    return {"ip": ip, "url": f"http://{ip}:{port}" if ip else None, "name": f"http://{socket.gethostname()}.local:{port}",
            "pin": bool(settings.get("pin"))}
