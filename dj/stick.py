# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult – USB-Stick / SD-Karte durchblättern und Ausgewähltes auf den Zynthian übernehmen.

  sticks()            eingesteckte Sticks/Karten
  liste(pfad)         Ordner und Musikdateien darin (mit Anzahl Titel, Größe, wie viel schon da ist)
  summe(pfade)        Titel/Bytes der Auswahl (verschachtelte Auswahl zählt einmal)
  auswahl_vorbereiten(pfade)  schreibt die Kopierliste für „zynsimple-dj importieren <liste>“

Genutzt von ZynSimple (Display und Handy) und von der Handy-Seite im DJ-Modus.
"""
import os
import shutil
import time

MUSIK = "/zynthian/zynthian-my-data/dj/MUSIK gekauft"
LISTE = "/run/zynsimple-import-liste.tsv"
ORDNER_NAME = "MUSIK gekauft"
AUDIO = {".mp3", ".flac", ".wav", ".aif", ".aiff", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".wma",
         ".alac", ".wv", ".stem.mp4"}
_cache = {}


def ist_audio(name):
    n = name.lower()
    return not n.startswith("._") and os.path.splitext(n)[1] in AUDIO


LESBAR = {"vfat", "exfat", "ntfs", "ntfs3", "ext2", "ext3", "ext4", "btrfs", "f2fs", "iso9660", "udf"}
FORMAT_NAME = {"vfat": "FAT32", "exfat": "exFAT", "ntfs": "NTFS", "ntfs3": "NTFS", "hfsplus": "Mac (HFS+)",
               "apfs": "Mac (APFS)", "ext4": "Linux (ext4)"}
_eingehaengt = {"t": 0.0}


def usb_laufwerke():
    """Alle USB-Speicher (Stick, Kartenleser, Festplatte) mit Format und wo sie eingehängt sind."""
    import json as _json
    import subprocess
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,TRAN,FSTYPE,LABEL,SIZE,MOUNTPOINT"],
                             capture_output=True, text=True, timeout=5).stdout
        baum = _json.loads(out).get("blockdevices", [])
    except Exception:
        return []
    teile = []
    for d in baum:
        if d.get("tran") != "usb":
            continue
        kinder = d.get("children") or [d]          # ohne Partitionstabelle: das ganze Gerät
        for k in kinder:
            if k.get("type") not in ("part", "disk"):
                continue
            teile.append({"pfad": k.get("path"), "format": k.get("fstype") or "", "name": k.get("label") or k.get("name"),
                          "groesse": int(k.get("size") or 0), "eingehaengt": k.get("mountpoint") or ""})
    return teile


def einhaengen():
    """USB-Speicher, die noch nicht eingehängt sind, einhängen (macht sonst devmon – falls das klemmt)."""
    import subprocess
    if time.monotonic() - _eingehaengt["t"] < 8:
        return
    _eingehaengt["t"] = time.monotonic()
    for t in usb_laufwerke():
        if t["eingehaengt"] or t["format"] not in LESBAR:
            continue
        ok = subprocess.call(["udisksctl", "mount", "--no-user-interaction", "-b", t["pfad"]],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20) == 0 \
            if shutil.which("udisksctl") else False
        if not ok:
            ziel = os.path.join("/media/root", "".join(c for c in t["name"] if c.isalnum() or c in "-_ ") or "USB")
            try:
                os.makedirs(ziel, exist_ok=True)
                typ = ["-t", "ntfs3"] if t["format"] in ("ntfs", "ntfs3") else []
                subprocess.call(["mount"] + typ + [t["pfad"], ziel], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20)
            except Exception:
                pass


def sticks():
    """Eingehängte USB-Sticks/Karten: [{pfad, name}]."""
    try:
        einhaengen()
    except Exception:
        pass
    out = []
    for t in usb_laufwerke():
        if t["eingehaengt"] and t["eingehaengt"] not in [s["pfad"] for s in out]:
            out.append({"pfad": t["eingehaengt"], "name": os.path.basename(t["eingehaengt"]) or t["name"]})
    for base in ("/media/root", "/media"):
        try:
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if os.path.ismount(p) and p not in [s["pfad"] for s in out]:
                    out.append({"pfad": p, "name": d})
        except OSError:
            pass
    return out


def diagnose():
    """Warum keine Musik? Für jeden USB-Speicher ein Satz."""
    zeilen = []
    for t in usb_laufwerke():
        fmt = FORMAT_NAME.get(t["format"], t["format"] or "ohne erkennbares Format")
        g = groesse(t["groesse"]) if t["groesse"] else ""
        if not t["eingehaengt"]:
            if t["format"] in ("hfsplus", "apfs"):
                zeilen.append(f"„{t['name']}“ ({g}): {fmt} – kann der Zynthian nicht lesen. Am PC/Mac auf exFAT formatieren.")
            elif t["format"] in LESBAR:
                zeilen.append(f"„{t['name']}“ ({g}, {fmt}): erkannt, ließ sich aber nicht öffnen. Abziehen und neu einstecken.")
            else:
                zeilen.append(f"„{t['name']}“ ({g}): {fmt} – nicht lesbar. Am PC auf exFAT oder FAT32 formatieren.")
            continue
        n = len(_dateien(t["eingehaengt"])) if os.path.isdir(t["eingehaengt"]) else 0
        zeilen.append(f"„{t['name']}“ ({g}, {fmt}): {n} Musikdateien" +
                      ("" if n else " – mp3, flac, wav, m4a, aiff, ogg werden erkannt"))
    if not zeilen:
        zeilen.append("Kein USB-Speicher erkannt. Anderen USB-Anschluss probieren; SD-Karten brauchen einen USB-Kartenleser.")
    return zeilen


def _stick_von(pfad):
    rp = os.path.realpath(pfad)
    for s in sticks():
        if rp == s["pfad"] or rp.startswith(s["pfad"] + os.sep):
            return s["pfad"]
    return None


def erlaubt(pfad):
    return bool(pfad) and _stick_von(pfad) is not None


def ziel_rel(datei):
    """Pfad auf dem Zynthian: innerhalb von „MUSIK gekauft“ ab dort, sonst ab der Wurzel des Sticks."""
    stick = _stick_von(datei)
    rel = os.path.relpath(os.path.realpath(datei), stick)
    teile = rel.split(os.sep)
    if ORDNER_NAME in teile[:-1]:
        teile = teile[teile.index(ORDNER_NAME) + 1:]
    return os.path.join(*teile)


def _dateien(pfad):
    """Alle Musikdateien unter pfad: [(datei, größe)]."""
    if os.path.isfile(pfad):
        return [(pfad, os.path.getsize(pfad))] if ist_audio(pfad) else []
    out = []
    for wurzel, ordner, dateien in os.walk(pfad):
        ordner[:] = sorted(d for d in ordner if not d.startswith(".") and d != "System Volume Information")
        for d in sorted(dateien):
            if ist_audio(d):
                p = os.path.join(wurzel, d)
                try:
                    out.append((p, os.path.getsize(p)))
                except OSError:
                    pass
    return out


def _schon_da(datei, groesse):
    try:
        return os.path.getsize(os.path.join(MUSIK, ziel_rel(datei))) == groesse
    except OSError:
        return False


def _info(pfad):
    try:
        mt = os.stat(pfad).st_mtime
    except OSError:
        mt = 0
    k = (pfad, mt)
    if k not in _cache:
        d = _dateien(pfad)
        _cache[k] = {"titel": len(d), "bytes": sum(g for _, g in d), "da": sum(1 for f, g in d if _schon_da(f, g))}
    return _cache[k]


def liste(pfad=None):
    if not pfad:
        st = sticks()
        return {"pfad": None, "name": "USB-Sticks und SD-Karten", "eltern": None, "diagnose": diagnose(),
                "eintraege": [dict(name=s["name"], pfad=s["pfad"], ordner=True, **_info(s["pfad"])) for s in st]}
    if not erlaubt(pfad) or not os.path.isdir(pfad):
        raise RuntimeError("Dieser Ordner ist nicht (mehr) da – Stick abgezogen?")
    stick = _stick_von(pfad)
    rp = os.path.realpath(pfad)
    eintraege = []
    with os.scandir(rp) as it:
        roh = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
    for e in roh:
        if e.name.startswith(".") or e.name == "System Volume Information":
            continue
        if e.is_dir():
            i = _info(e.path)
            if i["titel"]:
                eintraege.append(dict(name=e.name, pfad=e.path, ordner=True, **i))
        elif ist_audio(e.name):
            g = e.stat().st_size
            eintraege.append({"name": e.name, "pfad": e.path, "ordner": False, "titel": 1, "bytes": g,
                              "da": 1 if _schon_da(e.path, g) else 0})
    eltern = None if rp == stick else os.path.dirname(rp)
    name = os.path.basename(stick) + ("" if rp == stick else " › " + os.path.relpath(rp, stick).replace(os.sep, " › "))
    return {"pfad": rp, "name": name, "eltern": eltern if eltern is not None else "", "eintraege": eintraege,
            "diagnose": [] if eintraege else diagnose()}


def _bereinigt(pfade):
    """Doppelte und verschachtelte Auswahl entfernen (ist ein Ordner gewählt, zählen seine Inhalte nicht extra)."""
    ps = sorted({os.path.realpath(p) for p in pfade if erlaubt(p)})
    out = []
    for p in ps:
        if not any(p == o or p.startswith(o + os.sep) for o in out):
            out.append(p)
    return out


def summe(pfade):
    titel = bytes_ = da = 0
    for p in _bereinigt(pfade):
        i = _info(p) if os.path.isdir(p) else {"titel": 1, "bytes": os.path.getsize(p),
                                               "da": 1 if _schon_da(p, os.path.getsize(p)) else 0}
        titel += i["titel"]
        bytes_ += i["bytes"]
        da += i["da"]
    return {"titel": titel, "bytes": bytes_, "da": da, "neu": titel - da}


def auswahl_vorbereiten(pfade):
    """Kopierliste schreiben (Größe, Quelle, Ziel). Prüft vorher den Platz auf dem Zynthian."""
    zeilen = []
    gesamt = 0
    for p in _bereinigt(pfade):
        for datei, g in _dateien(p):
            if "\t" in datei or "\n" in datei:
                continue
            zeilen.append(f"{g}\t{datei}\t{ziel_rel(datei)}")
            if not _schon_da(datei, g):
                gesamt += g
    if not zeilen:
        raise RuntimeError("Nichts ausgewählt – erst Alben oder Titel antippen")
    os.makedirs(MUSIK, exist_ok=True)
    frei = shutil.disk_usage(MUSIK).free
    if frei < gesamt + 512 * 1024 * 1024:
        raise RuntimeError(f"Zu wenig Platz auf dem Zynthian: {frei // 2**20} MB frei, gebraucht {gesamt // 2**20} MB")
    with open(LISTE, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    return LISTE


def abwaehlen(wahl, pfad):
    """Einen Teil abwählen. Ist ein Ordner darüber gewählt, wird der aufgeteilt: alles darin bleibt gewählt,
    nur dieser Teil nicht."""
    wahl = set(wahl)
    if pfad in wahl:
        wahl.discard(pfad)
        return sorted(wahl)
    oben = next((w for w in wahl if pfad.startswith(w + os.sep)), None)
    if oben is None:
        return sorted(wahl)
    wahl.discard(oben)
    unter, eltern = pfad, os.path.dirname(pfad)
    while True:
        for e in liste(eltern)["eintraege"]:
            if e["pfad"] != unter:
                wahl.add(e["pfad"])
        if eltern == oben:
            break
        unter, eltern = eltern, os.path.dirname(eltern)
    return sorted(wahl)


def waehlen(wahl, pfad):
    wahl = {w for w in wahl if not w.startswith(pfad + os.sep)}
    wahl.add(pfad)
    return sorted(wahl)


IMPORT_LOG = "/tmp/zynsimple-dj-import.log"


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
        return {"phase": "fertig", "text": f"{t[1]} Titel geprüft, {neu} neu auf den Zynthian kopiert"}
    teile = letzte.split(" ", 5)
    if teile[0] in ("STAND", "DATEI") and len(teile) >= 5:
        return {"phase": "laeuft", "n": int(teile[1]), "gesamt": int(teile[2]), "bytes": int(teile[3]),
                "gesamt_b": int(teile[4] or 0), "datei": teile[5] if len(teile) > 5 else "", "kopiert": teile[0] == "DATEI"}
    return {"phase": "laeuft", "n": 0, "gesamt": 0, "datei": ""}


def groesse(b):
    if b >= 2**30:
        return f"{b / 2**30:.1f} GB".replace(".", ",")
    if b >= 2**20:
        return f"{b / 2**20:.0f} MB"
    return f"{max(1, b // 1024)} kB"
