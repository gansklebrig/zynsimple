# -*- coding: utf-8 -*-
"""ZynSimple – Verbindung zur Imres-Bühne (Klangwelten), falls auf dem Zynthian installiert."""

import json
import logging
import os
import shutil
import subprocess
import urllib.request

log = logging.getLogger("zynsimple")

BRUECKE = os.environ.get("IMRES_BRUECKE", "http://127.0.0.1:8790")
DATEN = os.environ.get("IMRES_DATEN", "/zynthian/zynthian-my-data/imres")
MODUS = os.environ.get("IMRES_MODUS", "/usr/local/bin/imres-modus")
ERLAUBT = ("imres", "hintergrund", "zynthian")


def installed():
    return os.path.isfile(MODUS) or os.path.isdir(os.path.join(DATEN, "seite"))


def bridge_ok(timeout=0.6):
    try:
        with urllib.request.urlopen(BRUECKE + "/zyn/status", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def status():
    inst = installed()
    return {"installed": inst, "bridge": bridge_ok() if inst else False}


def system_update():
    """Barden Beats im Hintergrund aktualisieren (die Bühne bleibt, wie sie ist)."""
    modus = MODUS if os.path.isfile(MODUS) else os.path.join(DATEN, "seite", "zynthian", "imres-modus")
    cmd = ["systemd-run", "--no-block", "--collect", modus, "aktualisieren"] if shutil.which("systemd-run") \
        else ["setsid", modus, "aktualisieren"]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def system(aktion):
    """Schaltet den Modus: imres (Bühne im Vollbild), hintergrund (zusammen), zynthian (nur Zynthian)."""
    if aktion not in ERLAUBT:
        raise ValueError(f"Unbekannte Aktion {aktion}")
    if not installed():
        raise RuntimeError("Imres ist auf diesem Zynthian nicht installiert")
    # 1. Über die Imres-Brücke (macht das sauber und losgelöst)
    try:
        req = urllib.request.Request(BRUECKE + "/zyn/system", data=json.dumps({"aktion": aktion}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as r:
            if r.status == 200:
                log.info(f"ZynSimple: Imres-Modus {aktion} über die Brücke")
                return
    except Exception as e:
        log.info(f"ZynSimple: Imres-Brücke nicht erreichbar ({e}), starte direkt")
    # 2. Direkt – außerhalb des Zynthian-Dienstes, weil „imres“ ihn beendet
    modus = MODUS if os.path.isfile(MODUS) else os.path.join(DATEN, "seite", "zynthian", "imres-modus")
    if shutil.which("systemd-run"):
        cmd = ["systemd-run", "--no-block", "--collect", modus, aktion]
    else:
        cmd = ["setsid", modus, aktion]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
