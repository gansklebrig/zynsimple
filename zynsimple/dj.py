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


def _deutsch(text):
    """apt-Meldungen kurz auf Deutsch."""
    import re
    for rx, ers in ((r"^Retrieving file (\d+) of (\d+)", r"Lade Datei \1 von \2"), (r"^Unpacking ", "Packe aus: "),
                    (r"^Preparing to unpack ", "Bereite vor: "), (r"^Setting up ", "Richte ein: "),
                    (r"^Installing ", "Installiere: "), (r"^Installed ", "Installiert: "),
                    (r"^Running dpkg", "Pakete werden eingetragen"), (r"^Processing triggers for ", "Abschluss: ")):
        text = re.sub(rx, ers, text)
    return text


INSTALL_SCHRITTE = [("Paketliste", 6), ("Herunterladen", 56), ("Installieren", 33), ("Einrichten", 5)]


def installieren():
    """Mixxx einmalig installieren – mit echtem Fortschritt aus apt (Download-MB, Pakete). (ok, meldung)"""
    import re
    import time
    from . import fortschritt as fs
    if mixxx_da():
        return True, "Mixxx ist schon da"
    fs.start("DJ-Pult wird eingerichtet (einmalig)", INSTALL_SCHRITTE)
    fs.schritt(0, "Paketquellen werden geprüft")
    try:
        os.remove(INSTALL_LOG)
    except OSError:
        pass
    _losgeloest(["installieren"])
    total = 0
    pos = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 40 * 60:
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
            if not z:
                continue
            if z == "PHASE paketliste":
                fs.schritt(0, "Paketquellen werden aktualisiert")
            elif z == "PHASE laden":
                fs.schritt(1, "Mixxx und Helfer werden geladen")
            elif z == "PHASE einrichten":
                fs.schritt(3, "WLAN-Ordner und Mixxx werden eingerichtet")
            elif z == "FERTIG":
                fs.fertig("Mixxx ist installiert")
                return True, "Mixxx ist installiert"
            elif z == "FEHLER":
                break
            m = re.search(r"Need to get ([\d.,]+)\s*([kMG]?B)", z)
            if m:
                faktor = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9}.get(m.group(2), 1)
                total = int(float(m.group(1).replace(",", "")) * faktor)
                fs.teil(total=total, detail=f"{fs.groesse(total)} zu laden")
            m = re.match(r"dlstatus:(\d+):([\d.]+):(.*)", z)
            if m:
                pct = float(m.group(2)) / 100
                if fs.STAND.get("schritt", 0) < 1:
                    fs.schritt(1)
                if total:
                    fs.teil(bytes_=int(total * pct), total=total, detail=_deutsch(m.group(3)))
                else:
                    fs.teil(anteil=pct, detail=_deutsch(m.group(3)))
            m = re.match(r"pmstatus:([^:]+):([\d.]+):(.*)", z)
            if m:
                if fs.STAND.get("schritt", 0) < 2:
                    fs.schritt(2)
                fs.teil(anteil=float(m.group(2)) / 100, detail=_deutsch(m.group(3)), zeile=f"Paket: {m.group(1)}")
            m = re.match(r"(?:Get|Hit|Holen|OK):\d+\s+(\S+)\s+.*?(\S+)\s+\S+\s+\S+(?:\s+\[([\d.,]+\s*[kMG]?B)\])?", z)
            if m and not z.startswith(("dlstatus", "pmstatus")):
                fs.teil(zeile=z)
        else:
            continue
        break
    letzte = ""
    try:
        with open(INSTALL_LOG, encoding="utf-8", errors="replace") as f:
            zeilen = [z.strip() for z in f if z.strip() and z.strip() not in ("FEHLER",) and not z.startswith(("dlstatus", "pmstatus", "PHASE"))]
        letzte = zeilen[-1] if zeilen else ""
    except OSError:
        pass
    if "resolve" in letzte or "Temporary failure" in letzte or "Could not" in letzte:
        meldung = "Kein Internet – der Zynthian braucht für die einmalige Installation WLAN oder Kabel."
    else:
        meldung = "Installation fehlgeschlagen" + (f": {letzte[:120]}" if letzte else "")
    fs.fehler(meldung)
    return False, meldung


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
    """{"phase": "laeuft"|"fertig"|"fehler"|None, "n", "gesamt", "bytes", "gesamt_b", "datei", "text"}"""
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
        t = letzte.split()
        neu = t[2] if len(t) > 2 else t[1]
        return {"phase": "fertig", "text": f"{t[1]} Dateien geprüft, {neu} neu auf den Zynthian kopiert"}
    teile = letzte.split(" ", 5)
    if teile[0] in ("STAND", "DATEI") and len(teile) >= 5:
        return {"phase": "laeuft", "n": int(teile[1]), "gesamt": int(teile[2]), "bytes": int(teile[3]),
                "gesamt_b": int(teile[4] or 0), "datei": teile[5] if len(teile) > 5 else "", "kopiert": teile[0] == "DATEI"}
    return {"phase": "laeuft", "n": 0, "gesamt": 0, "datei": ""}


def system(aktion):
    if aktion not in ERLAUBT:
        raise ValueError(f"Unbekannte Aktion {aktion}")
    if not eingerichtet():
        raise RuntimeError("DJ-Pult ist nicht eingerichtet – ZynSimple einmal neu installieren")
    log.info(f"ZynSimple: DJ-Modus {aktion}")
    _losgeloest([aktion])
