# -*- coding: utf-8 -*-
"""ZynSimple – DJ-Pult (Mixxx im Vollbild, z. B. mit dem Pioneer DDJ-200)."""

import logging
import os
import shutil
import subprocess

log = logging.getLogger("zynsimple")

BEFEHL = "/usr/local/bin/zynsimple-dj"
INSTALL_LOG = "/tmp/zynsimple-dj-install.log"
ERLAUBT = ("dj", "zynthian", "imres", "aus", "neustart")


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


IMPORT_LOG = "/tmp/zynsimple-dj-import.log"
SAMBA_LOG = "/tmp/zynsimple-dj-samba.log"
_samba = {"t": 0, "an": False}


def samba_an():
    """Läuft die WLAN-Freigabe? (kurz zwischengespeichert)"""
    import time
    if time.monotonic() - _samba["t"] > 5:
        _samba["t"] = time.monotonic()
        try:
            r = subprocess.run(["systemctl", "is-active", "-q", "smbd"], timeout=2)
            _samba["an"] = r.returncode == 0 and os.path.exists("/etc/samba/zynsimple-dj.conf")
        except Exception:
            _samba["an"] = False
    return _samba["an"]


def samba_einrichten():
    _samba["t"] = 0
    _losgeloest(["samba"])


def import_starten():
    """Musik vom USB-Stick übernehmen (läuft losgelöst; Fortschritt über import_stand())."""
    if not eingerichtet():
        raise RuntimeError("DJ-Pult ist nicht eingerichtet")
    try:
        os.remove(IMPORT_LOG)
    except OSError:
        pass
    _losgeloest(["importieren"])


def import_stand():
    """{"phase": "laeuft"|"fertig"|"fehler"|None, "n", "gesamt", "datei", "text"}"""
    try:
        with open(IMPORT_LOG, encoding="utf-8", errors="replace") as f:
            zeilen = [z.rstrip("\n") for z in f if z.strip()]
    except OSError:
        return {"phase": None}
    if not zeilen:
        return {"phase": "laeuft", "n": 0, "gesamt": 0, "datei": ""}
    letzte = zeilen[-1]
    if letzte.startswith("FEHLER"):
        return {"phase": "fehler", "text": letzte[7:]}
    if letzte.startswith("FERTIG"):
        return {"phase": "fertig", "text": f"{letzte.split()[1]} Dateien sind jetzt auf dem Zynthian"}
    teile = letzte.split(" ", 3)
    if teile[0] == "STAND" and len(teile) >= 3:
        return {"phase": "laeuft", "n": int(teile[1]), "gesamt": int(teile[2]), "datei": teile[3] if len(teile) > 3 else ""}
    return {"phase": "laeuft", "n": 0, "gesamt": 0, "datei": ""}


def system(aktion):
    if aktion not in ERLAUBT:
        raise ValueError(f"Unbekannte Aktion {aktion}")
    if not eingerichtet():
        raise RuntimeError("DJ-Pult ist nicht eingerichtet – ZynSimple einmal neu installieren")
    log.info(f"ZynSimple: DJ-Modus {aktion}")
    _losgeloest([aktion])
