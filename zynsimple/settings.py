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
    ("update_check", "Updates selbst suchen", "bool", None, "beim Start und alle 6 Stunden · braucht Internet"),
]


def _config_file():
    from . import CONFIG_FILE
    return CONFIG_FILE


def items(settings):
    out = []
    for key, title, kind, choices, hint in SPEC:
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
    spec = {k: (kind, choices) for k, _, kind, choices, _ in SPEC}
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


def cycle(settings, key):
    """Nächster Wert (für den Touchscreen: antippen = weiterschalten)."""
    for k, _, kind, choices, _ in SPEC:
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
