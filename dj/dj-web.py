#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult – Handy-Seite während des DJ-Modus (gleiche Adresse wie sonst ZynSimple: Port 8090).

  /                Musik suchen, ★ Favoriten, Titel in Deck A/B laden
  /api/bib         Suche (q, fav)
  /api/bib/laden   {id, deck}
  /api/system      {aktion: zynthian | neu-einlesen}

Läuft nur in der DJ-Sitzung (dj-sitzung.sh). Befehle an Mixxx gehen über den DJ-Helfer.
"""
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import bibliothek  # noqa: E402
import stick  # noqa: E402

BEFEHL_SOCK = "/tmp/zynsimple-dj-befehl.sock"
ZS_JSON = "/zynthian/zynthian-my-data/zynsimple/zynsimple.json"
_lade_lock = threading.Lock()


def senden(cc, wert):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.sendto(f"CC {int(cc)} {int(wert)}".encode(), BEFEHL_SOCK)
    finally:
        s.close()


def port():
    try:
        with open(ZS_JSON, encoding="utf-8") as f:
            return int(json.load(f).get("web_port", 8090))
    except Exception:
        return 8090


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def antwort(self, code, daten, typ="application/json; charset=utf-8"):
        roh = daten if isinstance(daten, bytes) else json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/import":
            with open(os.path.join(HIER, "www", "import.html"), "rb") as f:
                return self.antwort(200, f.read().replace(b"__MODUS__", b"dj"), "text/html; charset=utf-8")
        if u.path == "/api/stick":
            try:
                return self.antwort(200, stick.liste(parse_qs(u.query).get("pfad", [""])[0] or None))
            except Exception as e:
                return self.antwort(200, {"fehler": str(e)})
        if u.path == "/api/stick/stand":
            return self.antwort(200, stick.import_stand())
        if u.path in ("/", "/bibliothek", "/index.html"):
            with open(os.path.join(HIER, "www", "bibliothek.html"), "rb") as f:
                return self.antwort(200, f.read().replace(b"__MODUS__", b"dj"), "text/html; charset=utf-8")
        if u.path == "/api/bib":
            q = parse_qs(u.query)
            try:
                return self.antwort(200, bibliothek.suche(q.get("q", [""])[0], q.get("fav", ["0"])[0] == "1"))
            except Exception as e:
                return self.antwort(200, {"fehler": str(e), "titel": [], "gesamt": 0})
        return self.antwort(404, {"fehler": "gibt es nicht"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        try:
            if u.path == "/api/bib/laden":
                with _lade_lock:
                    return self.antwort(200, {"text": bibliothek.laden(body.get("id"), body.get("deck", 1), senden)})
            if u.path == "/api/stick/summe":
                return self.antwort(200, stick.summe(body.get("pfade") or []))
            if u.path == "/api/stick/abwaehlen":
                return self.antwort(200, {"wahl": stick.abwaehlen(body.get("wahl") or [], body.get("pfad"))})
            if u.path == "/api/stick/import":
                liste = stick.auswahl_vorbereiten(body.get("pfade") or [])
                try:
                    os.remove(stick.IMPORT_LOG)
                except OSError:
                    pass
                subprocess.Popen(["systemd-run", "--no-block", "--collect", "--quiet", "/usr/local/bin/zynsimple-dj",
                                  "importieren", liste], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return self.antwort(200, {"text": "Wird übernommen … neue Titel erscheinen in Mixxx nach "
                                                  "☰ → USB-Stick neu einlesen"})
            if u.path == "/api/system":
                aktion = body.get("aktion")
                if aktion not in ("zynthian", "neu-einlesen"):
                    raise ValueError("Unbekannte Aktion")
                subprocess.Popen(["systemd-run", "--no-block", "--collect", "--quiet", "/usr/local/bin/zynsimple-dj", aktion],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return self.antwort(200, {"text": "Zurück zum Zynthian …" if aktion == "zynthian" else "USB-Sticks werden neu eingelesen …"})
        except Exception as e:
            return self.antwort(200, {"fehler": str(e)})
        return self.antwort(404, {"fehler": "gibt es nicht"})


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", port()), Handler)
    print("DJ-Handy-Seite auf Port", port(), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
