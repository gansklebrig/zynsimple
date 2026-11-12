# -*- coding: utf-8 -*-
"""ZynSimple – DJ-Pult (Mixxx im Vollbild, z. B. mit dem Pioneer DDJ-200)."""

import logging
import os
import shutil
import subprocess

log = logging.getLogger("zynsimple")

BEFEHL = "/usr/local/bin/zynsimple-dj"
INSTALL_LOG = "/tmp/zynsimple-dj-install.log"
ERLAUBT = ("dj", "zynthian", "imres", "aus", "neustart", "hybrid")


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


def musik_stick():
    """Name des eingesteckten USB-Sticks / der SD-Karte (im USB-Kartenleser) – oder None."""
    try:
        st = stick_modul().sticks()
    except Exception:
        return None
    return st[0]["name"] if st else None


def stick_modul():
    """dj/stick.py – Stick/Karte durchblättern und Auswahl übernehmen (gemeinsam mit der DJ-Handy-Seite)."""
    import importlib.util
    import sys
    mod = sys.modules.get("zs_dj_stick")
    if mod is None:
        pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dj", "stick.py")
        spec = importlib.util.spec_from_file_location("zs_dj_stick", pfad)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules["zs_dj_stick"] = mod
    return mod


def import_starten(auswahl=None):
    """Musik vom USB-Stick übernehmen (läuft losgelöst; Fortschritt über import_stand()).
    auswahl: Liste von Ordnern/Dateien auf dem Stick – sonst der ganze Ordner „MUSIK gekauft“."""
    if not eingerichtet():
        raise RuntimeError("DJ-Pult ist nicht eingerichtet")
    if _laeuft("/run/zynsimple-dj-import.lock"):
        raise RuntimeError("Es wird gerade schon Musik übernommen")
    liste = stick_modul().auswahl_vorbereiten(auswahl) if auswahl else None
    try:
        os.remove(IMPORT_LOG)
    except OSError:
        pass
    _losgeloest(["importieren"] + ([liste] if liste else []))


def import_stand():
    """{"phase": "laeuft"|"fertig"|"fehler"|None, "n", "gesamt", "bytes", "gesamt_b", "datei", "text"}"""
    return stick_modul().import_stand()


def system(aktion):
    if aktion not in ERLAUBT:
        raise ValueError(f"Unbekannte Aktion {aktion}")
    if not eingerichtet():
        raise RuntimeError("DJ-Pult ist nicht eingerichtet – ZynSimple einmal neu installieren")
    log.info(f"ZynSimple: DJ-Modus {aktion}")
    _losgeloest([aktion])


# ---------------------------------------------------------------------------------------------
# Lange Hintergrund-Aufgaben: Mixxx 2.6 bauen, Stem-Werkzeug einrichten, Stems berechnen
# ---------------------------------------------------------------------------------------------
MIXXX26 = "/opt/mixxx-2.6/bin/mixxx"
MIXXX26_LOG = "/tmp/zynsimple-mixxx26.log"
STEMS_PY = "/opt/zynsimple-stems/venv/bin/python"
STEMS_INSTALL_LOG = "/tmp/zynsimple-stems-install.log"
STEMS_STATUS = "/tmp/zynsimple-stems.json"


def _laeuft(lock):
    """Hält ein Hintergrund-Job seine Sperrdatei? (flock)"""
    import fcntl
    try:
        with open(lock, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    except OSError:
        return False


def _log(pfad):
    try:
        with open(pfad, encoding="utf-8", errors="replace") as f:
            return f.read().replace("\r", "\n").splitlines()
    except OSError:
        return []


def mixxx26_da():
    return os.path.exists(MIXXX26)


def mixxx26_starten():
    _losgeloest(["mixxx26"])


MIXXX26_SCHRITTE = [("Platz prüfen", 1), ("Quellcode laden", 7), ("Bau-Pakete", 12), ("Konfigurieren", 3),
                    ("Kompilieren", 75), ("Installieren", 2)]


def mixxx26_stand():
    import re
    z = [x.strip() for x in _log(MIXXX26_LOG) if x.strip()]
    st = {"schritte": MIXXX26_SCHRITTE, "schritt": 0, "teil": 0.0, "detail": "", "zeile": "",
          "laeuft": _laeuft("/run/zynsimple-mixxx26.lock"), "fertig": mixxx26_da() and any(x.startswith("FERTIG") for x in z),
          "fehler": next((x[7:] for x in z if x.startswith("FEHLER")), None)}
    phasen = ["platz", "quelle", "pakete", "konfigurieren", "bauen", "installieren"]
    idx = 0
    for i, x in enumerate(z):
        if x.startswith("PHASE "):
            p = x[6:]
            if p in phasen:
                idx = phasen.index(p)
                st["schritt"], st["teil"], st["detail"] = idx, 0.0, ""
            continue
        if idx == 1:
            m = re.search(r"(Receiving objects|Resolving deltas):\s+(\d+)%.*?(?:,\s*([\d.]+\s*[KMG]iB))?(?:\s*\|\s*([\d.]+\s*[KMG]iB/s))?", x)
            if m:
                pz = int(m.group(2)) / 100
                st["teil"] = pz * 0.85 if m.group(1).startswith("Receiving") else 0.85 + pz * 0.15
                st["detail"] = " · ".join(t.replace("iB", "B") for t in (m.group(3), m.group(4)) if t) or "Quellcode wird geladen"
        elif idx == 2:
            m = re.search(r"(\d+) upgraded, (\d+) newly installed", x)
            if m:
                st["_n"] = int(m.group(1)) + int(m.group(2))
            if re.match(r"(Setting up|Unpacking) ", x):
                st["_k"] = st.get("_k", 0) + 1
                if st.get("_n"):
                    st["teil"] = min(1.0, st["_k"] / (2 * st["_n"]))
                st["detail"] = x[:90]
        elif idx == 4:
            m = re.match(r"\[\s*(\d+)%\]\s*(.*)", x)
            if m:
                st["teil"] = int(m.group(1)) / 100
                st["detail"] = f"{m.group(1)} % der Dateien übersetzt"
                st["zeile"] = re.sub(r"^Building CXX object .*?/src/", "src/", m.group(2))[-110:]
        elif idx in (3, 5):
            st["zeile"] = x[-110:]
    st.pop("_n", None)
    st.pop("_k", None)
    if st["fertig"]:
        st["schritt"], st["teil"], st["detail"] = len(MIXXX26_SCHRITTE) - 1, 1.0, "Mixxx 2.6 ist eingebaut"
    return st


def stems_bereit():
    return os.path.exists(STEMS_PY)


def stems_einrichten():
    _losgeloest(["stems-einrichten"])


STEMS_SCHRITTE = [("Pakete", 10), ("Python-Umgebung", 10), ("Demucs + PyTorch", 70), ("KI-Modell", 10)]


def stems_install_stand():
    import re
    z = [x.strip() for x in _log(STEMS_INSTALL_LOG) if x.strip()]
    st = {"schritte": STEMS_SCHRITTE, "schritt": 0, "teil": 0.0, "detail": "", "zeile": "",
          "laeuft": _laeuft("/run/zynsimple-stems-install.lock"), "fertig": "FERTIG" in z and stems_bereit(),
          "fehler": next((x[7:] for x in z if x.startswith("FEHLER")), None)}
    phasen = ["pakete", "python", "demucs", "modell"]
    idx, pakete = 0, 0
    for x in z:
        if x.startswith("PHASE ") and x[6:] in phasen:
            idx = phasen.index(x[6:])
            st["schritt"], st["teil"] = idx, 0.0
            continue
        m = re.match(r"pmstatus:([^:]+):([\d.]+):(.*)", x)
        if m and idx == 0:
            st["teil"], st["detail"] = float(m.group(2)) / 100, _deutsch(m.group(3))
        m = re.match(r"PIP (Collecting|Downloading|Installing collected packages|Successfully installed)\s*(.*)", x)
        if m and idx == 2:
            if m.group(1) == "Collecting":
                pakete += 1
                st["detail"] = f"Paket {pakete}: {m.group(2)[:60]}"
                st["teil"] = min(0.6, pakete / 40)
            elif m.group(1) == "Downloading":
                st["zeile"] = "lade " + m.group(2)[:100]
            elif m.group(1).startswith("Installing"):
                st["teil"], st["detail"] = 0.75, "Pakete werden installiert (dauert etwas)"
            else:
                st["teil"] = 1.0
        if idx == 3 and "Modell bereit" in x:
            st["teil"] = 1.0
    if st["fertig"]:
        st["schritt"], st["teil"], st["detail"] = 3, 1.0, "Stem-Werkzeug ist bereit"
    return st


def stems_status():
    import json
    try:
        with open(STEMS_STATUS, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    try:
        r = subprocess.run(["systemctl", "is-active", "-q", "zynsimple-stems"], timeout=2)
        d["dienst"] = r.returncode == 0
    except Exception:
        d["dienst"] = False
    d["bereit"] = stems_bereit()
    return d
