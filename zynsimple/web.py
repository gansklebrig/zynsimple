# -*- coding: utf-8 -*-
"""ZynSimple – kleiner Webserver für Handy/Tablet."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("zynsimple")

WWW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "www")


def make_handler(bridge, pin):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ZynSimple/1.0"

        def log_message(self, fmt, *args):  # leise
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            if not pin:
                return True
            return self.headers.get("X-Zynsimple-Pin", "") == str(pin)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                try:
                    with open(os.path.join(WWW, "index.html"), "rb") as f:
                        self._send(200, f.read(), "text/html; charset=utf-8")
                except OSError:
                    self._send(500, "index.html fehlt", "text/plain; charset=utf-8")
            elif path == "/api/state":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    data = bridge.snapshot()
                    data["pin"] = bool(pin)
                    try:
                        from . import VERSION
                        data["app_version"] = VERSION
                    except Exception:
                        pass
                    self._send(200, data)
                except Exception as e:
                    self._send(500, {"error": str(e)})
            elif path == "/api/imres":
                from . import imres
                self._send(200, imres.status())
            elif path == "/api/dj":
                from . import dj
                st = dj.status()
                try:
                    with open(dj.INSTALL_LOG, encoding="utf-8", errors="replace") as f:
                        st["log"] = [z.rstrip() for z in f.readlines()[-3:]]
                except OSError:
                    st["log"] = []
                st["import"] = dj.import_stand()
                self._send(200, st)
            elif path == "/api/aufnahmen":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                from . import helfer
                self._send(200, {"liste": helfer.aufnahmen(), "laeuft": helfer.aufnahme_laeuft(bridge)})
            elif path in ("/datei/aufnahme", "/datei/sicherung"):
                from urllib.parse import parse_qs
                q = {k: v[0] for k, v in parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "").items()}
                if pin and q.get("pin", "") != str(pin):
                    return self._send(401, {"error": "pin"})
                from . import helfer
                try:
                    if path == "/datei/sicherung":
                        body, name, ctype = helfer.sicherung_bauen(bridge), helfer.sicherung_name(), "application/zip"
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        fp = helfer.aufnahme_pfad(q.get("f", ""))
                        size = os.path.getsize(fp)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(size))
                        self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(fp)}"')
                        self.end_headers()
                        with open(fp, "rb") as f:
                            shutil.copyfileobj(f, self.wfile, 256 * 1024)
                except FileNotFoundError:
                    self._send(404, {"error": "nicht gefunden"})
            elif path == "/api/update_check":
                from . import updater
                force = "force" in self.path
                st = updater.check(bridge.settings) if force or not updater.status["checked"] else dict(updater.status)
                if not st.get("current"):
                    from . import VERSION
                    st["current"] = VERSION
                self._send(200, st)
            elif path == "/api/live":
                from urllib.parse import parse_qs
                q = {k: v[0] for k, v in parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "").items()}
                try:
                    chain = bridge._chain(q["chain"])
                    pf = bridge.perform
                    x, y = pf.xy_pos(chain)
                    self._send(200, {"slots": [pf.slot_info(chain, s) for s in pf.live_slots(chain)], "xy": [x, y]})
                except Exception as e:
                    self._send(400, {"error": str(e)})
            elif path == "/api/settings":
                from . import settings as st
                self._send(200, {"items": st.items(bridge.settings), "address": st.address(bridge.settings)})
            elif path == "/api/theme":
                from . import theme
                self._send(200, theme.status())
            elif path == "/api/synth_list":
                x = bridge.extras
                self._send(200, {"tiles": x.synth_tiles(), "all": x.all_synths()})
            elif path == "/api/fx_list":
                x = bridge.extras
                self._send(200, {"tiles": x.fx_tiles(), "all": x.all_fx()})
            elif path in ("/api/fx", "/api/extras"):
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                from urllib.parse import parse_qs
                q = {k: v[0] for k, v in parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "").items()}
                try:
                    x = bridge.extras
                    if path == "/api/fx":
                        self._send(200, x.fx_detail(bridge._chain(q["chain"]), int(q["fx"])))
                    else:
                        local = find_local_update()
                        self._send(200, {
                            "foot": x.foot_info(),
                            "autosave": x.autosave_info,
                            "tempo": x.tempo(),
                            "inputs": x.available_inputs(),
                            "handpan_plugins": [n[3:] for _, n in x.plan_handpan()],
                            "local_update": os.path.basename(local) if local else None,
                            "inputs_hw": x.input_levels(),
                        })
                except Exception as e:
                    self._send(400, {"error": str(e)})
            else:
                self._send(404, {"error": "nicht gefunden"})

        def do_POST(self):
            if self.path.split("?", 1)[0] == "/api/imres":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    from . import imres
                    n = min(int(self.headers.get("Content-Length", 0)), 1024)
                    req = json.loads(self.rfile.read(n) or b"{}")
                    imres.system(str(req.get("aktion", "")))
                    self._send(200, {"ok": True})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/dj":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    from . import dj, start_dj
                    n = min(int(self.headers.get("Content-Length", 0)), 1024)
                    aktion = str(json.loads(self.rfile.read(n) or b"{}").get("aktion", "dj"))
                    if aktion == "dj":
                        start_dj(bridge.zyngui)
                    elif aktion == "import":
                        dj.import_starten()
                    else:
                        dj.system(aktion)
                    self._send(200, {"ok": True, "mixxx": dj.mixxx_da()})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/restore":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    from . import helfer
                    n = int(self.headers.get("Content-Length", 0))
                    if not 0 < n < 30 * 1024 * 1024:
                        raise ValueError("Datei fehlt oder ist zu groß")
                    self._send(200, {"ok": True, "message": helfer.sicherung_einspielen(bridge, self.rfile.read(n))})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/settings":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    from . import settings as st
                    n = min(int(self.headers.get("Content-Length", 0)), 2048)
                    req = json.loads(self.rfile.read(n) or b"{}")
                    st.save(bridge.settings, req)
                    for k in req:
                        st.apply_live(bridge, k)
                    self._send(200, {"ok": True, "items": st.items(bridge.settings)})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/theme":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    from . import theme
                    n = min(int(self.headers.get("Content-Length", 0)), 1024)
                    req = json.loads(self.rfile.read(n) or b"{}")
                    msg = theme.revert() if req.get("action") == "revert" else theme.apply(req.get("font"))
                    self._send(200, {"ok": True, "message": msg})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/update_github":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    from . import updater
                    self._send(200, {"ok": True, "message": updater.install(bridge.settings)})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/update_local":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    self._send(200, {"ok": True, "message": install_local_update()})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] == "/api/update":
                if not self._authorized():
                    return self._send(401, {"error": "pin"})
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    if not 0 < n < 20 * 1024 * 1024:
                        raise ValueError("Datei fehlt oder ist zu groß")
                    msg = install_update(self.rfile.read(n))
                    self._send(200, {"ok": True, "message": msg})
                except Exception as e:
                    self._send(400, {"error": str(e)})
                return
            if self.path.split("?", 1)[0] != "/api/action":
                return self._send(404, {"error": "nicht gefunden"})
            if not self._authorized():
                return self._send(401, {"error": "pin"})
            try:
                n = min(int(self.headers.get("Content-Length", 0)), 4096)
                req = json.loads(self.rfile.read(n) or b"{}")
                res = bridge.action(req.get("chain"), req["op"], req.get("value"))
                self._send(200, {"ok": True, "result": res})
            except Exception as e:
                self._send(400, {"error": str(e)})

    return Handler


def install_update(data):
    """Entpackt eine neue zynsimple.zip und startet die Installation im Hintergrund."""
    tmp = tempfile.mkdtemp(prefix="zynsimple-update-")
    try:
        zpath = os.path.join(tmp, "update.zip")
        with open(zpath, "wb") as f:
            f.write(data)
        if not zipfile.is_zipfile(zpath):
            raise ValueError("Das ist keine ZIP-Datei")
        with zipfile.ZipFile(zpath) as z:
            for name in z.namelist():
                if name.startswith("/") or ".." in name.split("/"):
                    raise ValueError("Ungültige ZIP-Datei")
            z.extractall(tmp)
        src = None
        cands = [os.path.join(tmp, "zynsimple"), tmp] + \
            [os.path.join(tmp, d) for d in sorted(os.listdir(tmp)) if os.path.isdir(os.path.join(tmp, d))]
        for cand in cands:
            if os.path.isfile(os.path.join(cand, "install.sh")) and \
                    os.path.isfile(os.path.join(cand, "zynsimple", "__init__.py")):
                src = cand
                break
        if not src:
            raise ValueError("In der ZIP fehlt install.sh – ist das wirklich ZynSimple?")
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    script = os.path.join(src, "install.sh")
    logf = os.path.join(tempfile.gettempdir(), "zynsimple-update.log")
    # Außerhalb des Zynthian-Dienstes starten, damit der Neustart das Update nicht abbricht
    cmd = f"sleep 1; bash '{script}' > '{logf}' 2>&1; rm -rf '{tmp}'"
    if shutil.which("systemd-run"):
        subprocess.Popen(["systemd-run", "--no-block", "--collect", "--unit", f"zynsimple-update-{os.getpid()}-{int(__import__('time').time())}",
                          "/bin/bash", "-c", cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["/bin/bash", "-c", cmd], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log.info("ZynSimple: Update wird installiert")
    return "Update wird installiert. Der Zynthian startet gleich neu."


UPDATE_DIRS = ["/media/root", "/media", "/root", "/zynthian/zynthian-my-data"]


def find_local_update():
    """Sucht eine zynsimple*.zip auf USB-Stick oder im Zynthian (neueste zuerst)."""
    found = []
    for base in UPDATE_DIRS:
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            if root[len(base):].count(os.sep) >= 2:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("zynsimple", "imres")]
            for f in files:
                if f.lower().startswith("zynsimple") and f.lower().endswith(".zip"):
                    p = os.path.join(root, f)
                    try:
                        found.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
    return max(found)[1] if found else None


def install_local_update():
    p = find_local_update()
    if not p:
        raise ValueError("Keine zynsimple-ZIP gefunden (USB-Stick eingesteckt?)")
    with open(p, "rb") as f:
        return install_update(f.read())


def start(bridge, port=8090, pin=""):
    def run():
        try:
            httpd = ThreadingHTTPServer(("0.0.0.0", int(port)), make_handler(bridge, pin))
            httpd.daemon_threads = True
            log.info(f"ZynSimple Web läuft auf Port {port}")
            httpd.serve_forever()
        except Exception as e:
            log.error(f"ZynSimple Web konnte nicht starten: {e}")

    threading.Thread(target=run, name="zynsimple-web", daemon=True).start()
