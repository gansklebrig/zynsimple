# -*- coding: utf-8 -*-
"""ZynSimple – Updates direkt von GitHub holen (wenn der Zynthian Internet hat)."""

import logging
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


def install(settings=None, timeout=60):
    """Lädt den aktuellen Stand von GitHub und installiert ihn."""
    from .web import install_update
    repo, branch = _repo(settings)
    url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            data = r.read(25 * 1024 * 1024)
    except Exception as e:
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
