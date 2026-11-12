#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple – Diagnose automatisch hochladen.

Alles Neue im Ordner „MUSIK gekauft/_Diagnose“ (Absturz-Protokolle, Wache-Protokolle vor einem Einfrieren)
wird in ein privates GitHub-Repository geladen, sobald Internet da ist. Dort kann Claude es direkt lesen.

Einrichtung (einmal, am Handy unter http://zynthian.local:8080 → Bühne → „Diagnose automatisch hochladen“):
  privates Repository (z. B. zynsimple-diagnose) + Fine-grained Token nur für dieses Repository,
  Recht „Contents: Read and write“. Gespeichert in /zynthian/zynthian-my-data/zynsimple/diagnose.json.

Aufruf:  diagnose-hochladen.py            neue Dateien hochladen (die Wache ruft das jede Minute auf)
         diagnose-hochladen.py --test     Verbindung prüfen (lädt eine kleine Testdatei hoch)
         diagnose-hochladen.py --jetzt    zusätzlich das laufende Wache-Protokoll hochladen
"""
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

KONF = "/zynthian/zynthian-my-data/zynsimple/diagnose.json"
ORDNER = "/zynthian/zynthian-my-data/dj/MUSIK gekauft/_Diagnose"
MERKER = os.path.join(ORDNER, ".hochgeladen.json")
WACHE = "/zynthian/zynthian-my-data/zynsimple/wache.log"
SPERRE = "/run/zynsimple-diagnose.lock"
MAX_BYTES = 900 * 1024


def konf():
    try:
        with open(KONF, encoding="utf-8") as f:
            k = json.load(f)
        if k.get("token") and k.get("repo"):
            return k
    except Exception:
        pass
    return None


def hochladen(k, pfad_im_repo, inhalt, nachricht):
    if len(inhalt) > MAX_BYTES:
        inhalt = b"[gekuerzt - nur das Ende]\n" + inhalt[-MAX_BYTES:]
    url = f"https://api.github.com/repos/{k['repo']}/contents/{urllib.request.quote(pfad_im_repo)}"
    daten = json.dumps({"message": nachricht, "content": base64.b64encode(inhalt).decode()}).encode()
    req = urllib.request.Request(url, data=daten, method="PUT", headers={
        "Authorization": f"Bearer {k['token']}", "Accept": "application/vnd.github+json",
        "User-Agent": "ZynSimple-Diagnose", "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def lesen(p):
    with open(p, "rb") as f:
        return f.read()


def main():
    k = konf()
    if not k:
        print("Diagnose-Upload ist nicht eingerichtet")
        return 2
    # nicht doppelt laufen
    try:
        fd = os.open(SPERRE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        if time.time() - os.path.getmtime(SPERRE) < 600:
            return 0
        os.remove(SPERRE)
        open(SPERRE, "w").close()
    try:
        return _main(k)
    finally:
        try:
            os.remove(SPERRE)
        except OSError:
            pass


def _main(k):
    geraet = socket.gethostname() or "zynthian"
    tag = time.strftime("%Y-%m-%d")
    if "--test" in sys.argv:
        try:
            hochladen(k, f"{geraet}/test-{time.strftime('%Y-%m-%d_%H%M%S')}.txt",
                      f"Verbindung klappt · {time.strftime('%F %T')}\n".encode(), "Test vom Zynthian")
            print("OK – Diagnose-Upload funktioniert")
            return 0
        except urllib.error.HTTPError as e:
            print({401: "Token falsch oder abgelaufen", 403: "Token darf nicht schreiben (Contents: Read and write?)",
                   404: "Repository nicht gefunden (Name? Token für dieses Repository freigegeben?)"}.get(
                e.code, f"GitHub-Fehler {e.code}"))
            return 1
        except Exception as e:
            print(f"Keine Verbindung: {e}")
            return 1
    try:
        with open(MERKER, encoding="utf-8") as f:
            erledigt = json.load(f)
    except Exception:
        erledigt = {}
    neu = []
    try:
        for n in sorted(os.listdir(ORDNER)):
            p = os.path.join(ORDNER, n)
            if n.startswith(".") or not os.path.isfile(p) or not n.endswith(".txt"):
                continue
            mt = int(os.path.getmtime(p))
            if erledigt.get(n) != mt:
                neu.append((n, p, mt))
    except FileNotFoundError:
        pass
    fehler = 0
    for n, p, mt in neu[-20:]:
        try:
            hochladen(k, f"{geraet}/{tag}/{n}", lesen(p), f"Diagnose: {n}")
            erledigt[n] = mt
            print("hochgeladen:", n)
        except urllib.error.HTTPError as e:
            if e.code == 422:          # gibt es schon (gleicher Name) → als erledigt merken
                erledigt[n] = mt
            else:
                fehler += 1
                print(n, "→ GitHub-Fehler", e.code)
                break
        except Exception as e:
            fehler += 1
            print(n, "→", e)
            break
    if "--jetzt" in sys.argv and os.path.exists(WACHE):
        try:
            hochladen(k, f"{geraet}/{tag}/wache-jetzt-{time.strftime('%H%M%S')}.txt", lesen(WACHE)[-MAX_BYTES:],
                      "Wache-Protokoll (auf Wunsch)")
            print("hochgeladen: Wache-Protokoll")
        except Exception as e:
            fehler += 1
            print("Wache-Protokoll →", e)
    if neu:
        try:
            with open(MERKER, "w", encoding="utf-8") as f:
                json.dump(erledigt, f)
        except OSError:
            pass
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
