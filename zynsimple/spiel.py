# -*- coding: utf-8 -*-
"""ZynSimple – Bard Hero (Rhythmusspiel mit der Keytar) starten, einmalig einrichten."""

import logging
import os
import re
import shutil
import subprocess
import time

log = logging.getLogger("zynsimple")

BEFEHL = "/usr/local/bin/bard-hero"
INSTALL_LOG = "/tmp/bardhero-install.log"
ERLAUBT = ("start", "zynthian", "aus", "neustart")
SCHRITTE = [("Paketliste", 6), ("Herunterladen", 60), ("Installieren", 30), ("Einrichten", 4)]


def eingerichtet():
    return os.path.isfile(BEFEHL)


def bereit():
    try:
        return subprocess.call([BEFEHL, "bereit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20) == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _losgeloest(args):
    """Außerhalb des Zynthian-Dienstes starten – das Spiel beendet die Oberfläche."""
    if shutil.which("systemd-run"):
        cmd = ["systemd-run", "--quiet", "--collect", "--no-block", BEFEHL] + list(args)
    else:
        cmd = ["setsid", BEFEHL] + list(args)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def system(aktion):
    if aktion not in ERLAUBT:
        raise ValueError(f"Unbekannte Aktion {aktion}")
    if not eingerichtet():
        raise RuntimeError("Bard Hero ist nicht eingerichtet – ZynSimple einmal neu installieren")
    _losgeloest([aktion])


def installieren():
    """Pakete einmalig installieren – mit Fortschritt aus apt. (ok, meldung)"""
    from . import fortschritt as fs
    from .dj import _deutsch
    if bereit():
        return True, "Bard Hero ist bereit"
    fs.start("Bard Hero wird eingerichtet (einmalig)", SCHRITTE)
    fs.schritt(0, "Paketquellen werden geprüft")
    try:
        os.remove(INSTALL_LOG)
    except OSError:
        pass
    _losgeloest(["installieren"])
    total = 0
    pos = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 30 * 60:
        time.sleep(0.4)
        try:
            with open(INSTALL_LOG, encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                neu = f.read()
                pos = f.tell()
        except OSError:
            continue
        for z in neu.splitlines():
            z = z.strip()
            if z == "PHASE paketliste":
                fs.schritt(0, "Paketquellen werden aktualisiert")
            elif z == "PHASE laden":
                fs.schritt(1, "Spiel-Bausteine werden geladen")
            elif z == "PHASE einrichten":
                fs.schritt(3, "Wird eingerichtet")
            elif z == "FERTIG":
                fs.fertig("Bard Hero ist bereit")
                return True, "Bard Hero ist bereit"
            elif z == "FEHLER":
                letzte = neu.strip().splitlines()[-2:] if neu.strip() else []
                text = " ".join(letzte)
                meldung = ("Kein Internet – für die einmalige Installation braucht der Zynthian WLAN oder Kabel."
                           if re.search(r"resolve|Temporary failure|Could not", text) else "Installation fehlgeschlagen")
                fs.fehler(meldung)
                return False, meldung
            m = re.search(r"Need to get ([\d.,]+)\s*([kMG]?B)", z)
            if m:
                faktor = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9}.get(m.group(2), 1)
                total = int(float(m.group(1).replace(",", "")) * faktor)
                fs.teil(total=total, detail=f"{fs.groesse(total)} zu laden")
            m = re.match(r"dlstatus:(\d+):([\d.]+):(.*)", z)
            if m:
                pct = float(m.group(2)) / 100
                if total:
                    fs.teil(bytes_=int(total * pct), total=total, detail=_deutsch(m.group(3)))
                else:
                    fs.teil(anteil=pct, detail=_deutsch(m.group(3)))
            m = re.match(r"pmstatus:([^:]+):([\d.]+):(.*)", z)
            if m:
                if fs.STAND.get("schritt", 0) < 2:
                    fs.schritt(2)
                fs.teil(anteil=float(m.group(2)) / 100, detail=_deutsch(m.group(3)), zeile=f"Paket: {m.group(1)}")
    fs.fehler("Installation hat zu lange gedauert")
    return False, "Installation hat zu lange gedauert"
