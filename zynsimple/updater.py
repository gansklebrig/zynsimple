# -*- coding: utf-8 -*-
"""ZynSimple – Updates direkt von GitHub holen (wenn der Zynthian Internet hat)."""

import logging
import os
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("zynsimple")

DEFAULT_REPO = "gansklebrig/zynsimple"
UA = {"User-Agent": "ZynSimple-Updater"}

status = {"current": None, "latest": None, "available": False, "checked": None, "error": None}


def _ver(s):
    try:
        return tuple(int(x) for x in str(s).strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def _repo(settings):
    return (settings or {}).get("update_repo") or DEFAULT_REPO, (settings or {}).get("update_branch") or "main"


def check(settings=None, timeout=8):
    from . import VERSION
    repo, branch = _repo(settings)
    status["current"] = VERSION
    try:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/VERSION?t={int(time.time())}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            latest = r.read(64).decode("utf-8", "replace").strip()
        status.update(latest=latest, available=_ver(latest) > _ver(VERSION), checked=time.time(), error=None)
    except urllib.error.HTTPError as e:
        status.update(checked=time.time(), error=f"GitHub antwortet mit Fehler {e.code}")
    except Exception:
        status.update(checked=time.time(), error="Kein Internet oder GitHub nicht erreichbar")
    return dict(status)


UPDATE_SCHRITTE = [("Prüfen", 3), ("Herunterladen", 45), ("Entpacken", 10), ("Installieren", 37), ("Neustart", 5)]
GROESSE_DATEI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".update_groesse")


def install(settings=None, timeout=60):
    """Lädt den aktuellen Stand von GitHub und installiert ihn – mit echtem Fortschritt (Bytes, Tempo)."""
    from . import fortschritt as fs
    from .web import install_update
    repo, branch = _repo(settings)
    url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
    if not fs.STAND.get("aktiv"):
        fs.start("ZynSimple-Update", UPDATE_SCHRITTE)
    fs.schritt(1, f"von github.com/{repo}")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            total = int(r.headers.get("Content-Length") or 0)
            if not total:
                # GitHub nennt die Größe oft nicht – dann die vom letzten Mal als Schätzung
                try:
                    with open(GROESSE_DATEI) as f:
                        schaetz = int(f.read().strip())
                except Exception:
                    schaetz = 0
            teile, n = [], 0
            while True:
                b = r.read(32 * 1024)
                if not b:
                    break
                teile.append(b)
                n += len(b)
                if n > 25 * 1024 * 1024:
                    raise RuntimeError("Download ist unerwartet groß")
                if total:
                    fs.teil(bytes_=n, total=total)
                else:
                    fs.teil(bytes_=n, anteil=min(0.97, n / schaetz) if schaetz else None)
            data = b"".join(teile)
        try:
            with open(GROESSE_DATEI, "w") as f:
                f.write(str(len(data)))
        except OSError:
            pass
        fs.teil(anteil=1.0, bytes_=len(data), total=len(data))
    except Exception as e:
        fs.fehler(f"Download fehlgeschlagen ({e}) – hat der Zynthian Internet?")
        raise RuntimeError(f"Download fehlgeschlagen ({e}). Hat der Zynthian Internet?")
    return install_update(data)


def start_background_check(settings):
    if not settings.get("update_check", True):
        return

    def run():
        time.sleep(45)   # erst wenn WLAN und Oberfläche sicher laufen
        while True:
            check(settings)
            if status["available"]:
                log.info(f"ZynSimple: Update {status['latest']} verfügbar")
            time.sleep(6 * 3600)

    threading.Thread(target=run, name="zynsimple-updatecheck", daemon=True).start()
