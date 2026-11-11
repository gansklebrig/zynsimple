# -*- coding: utf-8 -*-
"""
ZynSimple – echter Fortschritt für Updates, Installationen und Import.

Ein gemeinsamer Zustand, den der Touchscreen und das Handy anzeigen:
Schritte mit Gewicht, Prozent innerhalb des Schritts, geladene Bytes, Tempo, Restzeit und die letzte Meldung.
Kein Timer – der Balken bewegt sich nur, wenn wirklich etwas passiert.
"""

import threading
import time

_lock = threading.Lock()
STAND = {"aktiv": False}


def start(titel, schritte):
    """schritte: [(Name, Gewicht), …]"""
    with _lock:
        STAND.clear()
        STAND.update({
            "aktiv": True, "titel": titel, "schritte": [n for n, _ in schritte], "gewichte": [g for _, g in schritte],
            "schritt": 0, "teil": 0.0, "bytes": 0, "total": 0, "tempo": 0.0, "detail": "", "zeile": "",
            "fertig": False, "fehler": None, "t0": time.time(), "_tb": (time.monotonic(), 0),
        })


def schritt(i, detail=""):
    with _lock:
        if not STAND.get("aktiv"):
            return
        if i != STAND["schritt"]:
            STAND.update({"schritt": i, "teil": 0.0, "bytes": 0, "total": 0, "tempo": 0.0, "_tb": (time.monotonic(), 0)})
        STAND["detail"] = detail


def teil(anteil=None, bytes_=None, total=None, detail=None, zeile=None):
    """Fortschritt innerhalb des aktuellen Schritts."""
    with _lock:
        if not STAND.get("aktiv"):
            return
        if total is not None:
            STAND["total"] = int(total)
        if bytes_ is not None:
            jetzt = time.monotonic()
            t0, b0 = STAND["_tb"]
            if jetzt - t0 >= 0.5:
                momentan = (bytes_ - b0) / (jetzt - t0)
                STAND["tempo"] = momentan if not STAND["tempo"] else STAND["tempo"] * 0.6 + momentan * 0.4
                STAND["_tb"] = (jetzt, bytes_)
            STAND["bytes"] = int(bytes_)
            if STAND["total"] and anteil is None:
                anteil = bytes_ / STAND["total"]
        if anteil is not None:
            STAND["teil"] = max(STAND["teil"], max(0.0, min(1.0, float(anteil))))
        if detail is not None:
            STAND["detail"] = detail
        if zeile is not None:
            STAND["zeile"] = str(zeile)[-140:]


def fertig(text=""):
    with _lock:
        if STAND.get("aktiv"):
            STAND.update({"fertig": True, "schritt": len(STAND["schritte"]) - 1, "teil": 1.0, "detail": text})


def fehler(text):
    with _lock:
        if STAND.get("aktiv"):
            STAND["fehler"] = text


def ende():
    with _lock:
        STAND["aktiv"] = False


def prozent():
    s = STAND
    if not s.get("aktiv"):
        return 0.0
    if s.get("fertig"):
        return 100.0
    g = s["gewichte"]
    summe = sum(g) or 1
    vorher = sum(g[:s["schritt"]])
    return min(99.9, 100.0 * (vorher + g[s["schritt"]] * s["teil"]) / summe)


def groesse(n):
    n = float(n or 0)
    for einheit in ("B", "kB", "MB", "GB"):
        if n < 1000 or einheit == "GB":
            return (f"{n:.0f} {einheit}" if einheit in ("B", "kB") or n >= 100 else f"{n:.1f} {einheit}").replace(".", ",")
        n /= 1000


def zeile_daten():
    """Klartext-Zeile: „2,1 MB von 3,4 MB · 420 kB/s · noch ca. 4 s“"""
    s = STAND
    teile = []
    if s.get("bytes"):
        teile.append(groesse(s["bytes"]) + (f" von {groesse(s['total'])}" if s.get("total") else ""))
    if s.get("tempo", 0) > 1:
        teile.append(groesse(s["tempo"]) + "/s")
        if s.get("total") and s["total"] > s["bytes"]:
            rest = (s["total"] - s["bytes"]) / s["tempo"]
            teile.append("noch ca. " + (f"{int(rest)} s" if rest < 90 else f"{int(rest / 60 + 0.5)} min"))
    return " · ".join(teile)


def als_dict():
    with _lock:
        d = {k: v for k, v in STAND.items() if not k.startswith("_")}
    if d.get("aktiv"):
        d["prozent"] = round(prozent(), 1)
        d["daten"] = zeile_daten()
        d["dauer"] = int(time.time() - d.get("t0", time.time()))
    return d
