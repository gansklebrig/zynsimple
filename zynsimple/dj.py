# -*- coding: utf-8 -*-
"""ZynSimple – DJ-Pult (Mixxx im Vollbild, z. B. mit dem Pioneer DDJ-200)."""

import logging
import os
import shutil
import subprocess

log = logging.getLogger("zynsimple")

BEFEHL = "/usr/local/bin/zynsimple-dj"
INSTALL_LOG = "/tmp/zynsimple-dj-install.log"
ERLAUBT = ("dj", "zynthian", "imres")


def eingerichtet():
    return os.path.isfile(BEFEHL)


def mixxx_da():
    return shutil.which("mixxx") is not None


def status():
    return {"eingerichtet": eingerichtet(), "mixxx": mixxx_da(),
            "imres": os.path.isfile("/usr/local/bin/imres-modus")}


def _losgeloest(args, wait=False):
    """Außerhalb des Zynthian-Dienstes starten – der DJ-Modus beendet die Oberfläche."""
    if shutil.which("systemd-run"):
        cmd = ["systemd-run", "--quiet", "--collect"] + (["--wait"] if wait else ["--no-block"]) + [BEFEHL] + list(args)
    else:
        cmd = ["setsid", BEFEHL] + list(args)
    if wait:
        return subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


def installieren():
    """Mixxx einmalig installieren (blockiert, dauert einige Minuten). Gibt (ok, meldung) zurück."""
    if mixxx_da():
        return True, "Mixxx ist schon da"
    rc = _losgeloest(["installieren"], wait=True)
    if rc == 0 and mixxx_da():
        return True, "Mixxx ist installiert"
    letzte = ""
    try:
        with open(INSTALL_LOG, encoding="utf-8", errors="replace") as f:
            zeilen = [z.strip() for z in f if z.strip() and z.strip() not in ("FEHLER",)]
        letzte = zeilen[-1] if zeilen else ""
    except OSError:
        pass
    if "resolve" in letzte or "Temporary failure" in letzte or "Could not" in letzte:
        return False, "Kein Internet – der Zynthian braucht für die einmalige Installation WLAN oder Kabel."
    return False, "Installation fehlgeschlagen" + (f": {letzte[:120]}" if letzte else "")


def system(aktion):
    if aktion not in ERLAUBT:
        raise ValueError(f"Unbekannte Aktion {aktion}")
    if not eingerichtet():
        raise RuntimeError("DJ-Pult ist nicht eingerichtet – ZynSimple einmal neu installieren")
    log.info(f"ZynSimple: DJ-Modus {aktion}")
    _losgeloest([aktion])
