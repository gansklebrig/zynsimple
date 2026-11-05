# -*- coding: utf-8 -*-
"""ZynSimple – Farbschema „Glut“ für die gesamte Zynthian-Oberfläche (ohne Blau)."""

import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger("zynsimple")

HOME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_FILE = os.path.join(HOME_DIR, "zynsimple_theme_backup.json")

# Werte für zynthian_envars (ZYNTHIAN_UI_COLOR_*), warm und ohne Blau
GLUT = {
    "ZYNTHIAN_UI_COLOR_BG": "#100e0d",
    "ZYNTHIAN_UI_COLOR_TX": "#ece6dc",
    "ZYNTHIAN_UI_COLOR_TX_OFF": "#a89f93",
    "ZYNTHIAN_UI_COLOR_ON": "#f2a33a",
    "ZYNTHIAN_UI_COLOR_OFF": "#4a423b",
    "ZYNTHIAN_UI_COLOR_HL": "#3dd68c",
    "ZYNTHIAN_UI_COLOR_ML": "#f5d90a",
    "ZYNTHIAN_UI_COLOR_LOW_ON": "#c0392b",
    "ZYNTHIAN_UI_COLOR_PANEL_BG": "#221d1a",
    "ZYNTHIAN_UI_COLOR_PANEL_HL": "#3a302a",
    "ZYNTHIAN_UI_COLOR_INFO": "#e0a046",
    "ZYNTHIAN_UI_COLOR_MIDI": "#d9822b",
    "ZYNTHIAN_UI_COLOR_ALT": "#b04ad0",
    "ZYNTHIAN_UI_COLOR_ALT2": "#ff9000",
    "ZYNTHIAN_UI_COLOR_ERROR": "#e5484d",
    "ZYNTHIAN_UI_COLOR_WARN": "#f5a623",
}

FONTS = ["Audiowide", "Rajdhani", "Exo 2", "Ropa Sans", "Share Tech", "Jura"]


def _current():
    from zyngui import zynthian_gui_config as c
    cur = {}
    for key in list(GLUT) + ["ZYNTHIAN_UI_FONT_FAMILY"]:
        attr = key.replace("ZYNTHIAN_UI_", "").lower()
        val = os.environ.get(key) or getattr(c, attr, None)
        if val:
            cur[key] = str(val)
    return cur


def status():
    active = False
    try:
        cur = _current()
        active = all(cur.get(k, "").lower() == v.lower() for k, v in GLUT.items())
        font = cur.get("ZYNTHIAN_UI_FONT_FAMILY", "Audiowide")
    except Exception:
        font = None
    return {"active": active, "backup": os.path.isfile(BACKUP_FILE), "font": font, "fonts": FONTS}


def _restart_ui():
    cmd = "sleep 1; systemctl restart zynthian"
    if shutil.which("systemd-run"):
        subprocess.Popen(["systemd-run", "--no-block", "--collect", "/bin/bash", "-c", cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["/bin/bash", "-c", cmd], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def apply(font=None):
    import zynconf
    if not os.path.isfile(BACKUP_FILE):
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(_current(), f, indent=1)
    values = dict(GLUT)
    if font and font in FONTS:
        values["ZYNTHIAN_UI_FONT_FAMILY"] = font
    zynconf.save_config(values)
    log.info("ZynSimple: Farbschema „Glut“ gespeichert – Oberfläche startet neu")
    _restart_ui()
    return "Neues Design gespeichert. Die Zynthian-Oberfläche startet kurz neu."


def revert():
    import zynconf
    try:
        with open(BACKUP_FILE, encoding="utf-8") as f:
            old = json.load(f)
    except FileNotFoundError:
        raise RuntimeError("Keine Sicherung des alten Designs gefunden")
    zynconf.save_config(old)
    os.remove(BACKUP_FILE)
    _restart_ui()
    return "Altes Design wiederhergestellt. Die Zynthian-Oberfläche startet kurz neu."
