#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: Stems im Hintergrund vorbereiten.

Woher die Tracks kommen:
  - Mixxx-Kiste „Stems vorbereiten“ (in Mixxx Tracks hineinziehen)
  - Ordner „MUSIK gekauft/Stems erzeugen“ (per WLAN Dateien hineinlegen)

Was passiert: Demucs trennt jeden Track in Drums, Bass, Melodie (Rest) und Vocals. Daraus wird eine
NI-Stem-Datei (.stem.mp4) im Ordner „MUSIK gekauft/Stems“, die Mixxx 2.6 mit einzeln schaltbaren Spuren abspielt.

Rücksicht: Läuft mit niedrigster Priorität und pausiert, solange DJ-Pult, DJ + Instrumente oder die Barden-Beats-Bühne laufen.
Status für die Anzeige: /tmp/zynsimple-stems.json
"""
import glob
import json
import os
import re
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time

DATEN = "/zynthian/zynthian-my-data/dj"
MUSIK = os.path.join(DATEN, "MUSIK gekauft")
AUSGABE = os.path.join(MUSIK, "Stems")
EINGANG = os.path.join(MUSIK, "Stems erzeugen")
DB = os.path.join(DATEN, ".mixxx", "mixxxdb.sqlite")
ZS_JSON = "/zynthian/zynthian-my-data/zynsimple/zynsimple.json"
VENV = "/opt/zynsimple-stems/venv"
STATUS = "/tmp/zynsimple-stems.json"
GEMERKT = os.path.join(DATEN, ".stems-erledigt.json")
KISTE = "Stems vorbereiten"
ENDUNGEN = (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".aif", ".aiff", ".opus")
# Farben der Spuren in Mixxx – ohne Blau
STEMS = [("Drums", "#E0445E"), ("Bass", "#E8B04A"), ("Melodie", "#34C78A"), ("Vocals", "#FF8A3D")]
DEMUCS_NAMEN = ["drums", "bass", "other", "vocals"]

status = {"aktiv": True, "pause": False, "warteschlange": 0, "fertig_heute": 0, "aktuell": "", "prozent": 0.0,
          "eta_s": None, "fehler": None, "letzte": [], "t": 0}


def schreiben(**kw):
    status.update(kw)
    status["t"] = int(time.time())
    try:
        with open(STATUS + ".neu", "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False)
        os.replace(STATUS + ".neu", STATUS)
    except OSError:
        pass


def einstellung_an():
    try:
        with open(ZS_JSON, encoding="utf-8") as f:
            return bool(json.load(f).get("dj_stems", True))
    except Exception:
        return True


def dj_laeuft():
    """Wird gerade gespielt? DJ-Pult, Barden-Beats-Bühne oder Mixxx (DJ + Instrumente) → Stems pausieren."""
    for d in ("zynsimple-dj", "imres-buehne"):
        if subprocess.call(["systemctl", "is-active", "-q", d]) == 0:
            return True
    return subprocess.call(["pgrep", "-x", "mixxx"], stdout=subprocess.DEVNULL) == 0


def gemerkt():
    try:
        with open(GEMERKT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def merken(d):
    with open(GEMERKT + ".neu", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(GEMERKT + ".neu", GEMERKT)


def schluessel(p):
    try:
        st = os.stat(p)
        return f"{p}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        return p


def ziel_fuer(p):
    name = os.path.splitext(os.path.basename(p))[0]
    return os.path.join(AUSGABE, name + ".stem.mp4")


# ---------------------------------------------------------------------------------------------
# Warteschlange
# ---------------------------------------------------------------------------------------------
def aus_kiste():
    """Tracks der Mixxx-Kiste „Stems vorbereiten“ (nur lesen, solange Mixxx nicht läuft)."""
    if not os.path.exists(DB) or dj_laeuft():
        return []
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=3)
        rows = con.execute(
            "SELECT tl.location FROM crates c JOIN crate_tracks ct ON ct.crate_id=c.id "
            "JOIN library l ON l.id=ct.track_id JOIN track_locations tl ON tl.id=l.location "
            "WHERE c.name=? AND l.mixxx_deleted=0", (KISTE,)).fetchall()
        con.close()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        print("Kiste lesen:", e, flush=True)
        return []


def kiste_aufraeumen(fertige_pfade):
    """Erledigte Tracks aus der Kiste nehmen – nur wenn Mixxx nicht läuft."""
    if not fertige_pfade or not os.path.exists(DB) or dj_laeuft():
        return
    try:
        con = sqlite3.connect(DB, timeout=5)
        cid = con.execute("SELECT id FROM crates WHERE name=?", (KISTE,)).fetchone()
        if cid:
            for p in fertige_pfade:
                con.execute("DELETE FROM crate_tracks WHERE crate_id=? AND track_id IN "
                            "(SELECT l.id FROM library l JOIN track_locations tl ON tl.id=l.location WHERE tl.location=?)",
                            (cid[0], p))
            n = con.execute("SELECT COUNT(*) FROM crate_tracks WHERE crate_id=?", (cid[0],)).fetchone()[0]
            con.execute("UPDATE crates SET count=? WHERE id=?", (n, cid[0]))
        con.commit()
        con.close()
    except Exception as e:
        print("Kiste aufräumen:", e, flush=True)


def aus_ordner():
    os.makedirs(EINGANG, exist_ok=True)
    out = []
    for root, _, files in os.walk(EINGANG):
        for f in sorted(files):
            if f.lower().endswith(ENDUNGEN) and not f.lower().endswith(".stem.mp4"):
                out.append(os.path.join(root, f))
    return out


def warteschlange():
    erledigt = gemerkt()
    q = []
    for p in aus_kiste() + aus_ordner():
        if not os.path.isfile(p) or p.lower().endswith((".stem.mp4", ".stem.m4a")):
            continue
        if schluessel(p) in erledigt or os.path.exists(ziel_fuer(p)):
            continue
        if p not in q:
            q.append(p)
    return q


# ---------------------------------------------------------------------------------------------
# Stem-Datei bauen
# ---------------------------------------------------------------------------------------------
def dauer(p):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def boxen(data, start, ende):
    """Top-Level-Boxen eines MP4-Bereichs: [(typ, anfang, groesse)]"""
    out, i = [], start
    while i + 8 <= ende:
        size, typ = struct.unpack(">I4s", data[i:i + 8])
        kopf = 8
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            kopf = 16
        elif size == 0:
            size = ende - i
        out.append((typ.decode("latin-1"), i, size, kopf))
        i += size
    return out


def manifest_einfuegen(pfad):
    """NI-Stem-Manifest (Box „stem“ in moov/udta) anhängen. ffmpeg schreibt moov ans Dateiende, darum verschiebt
    das Einfügen keine Audiodaten und die Offsets bleiben gültig."""
    manifest = {
        "version": 1,
        "mastering_dsp": {
            "compressor": {"enabled": False, "input_gain": 0.5, "output_gain": 0.5, "threshold": 0, "dry_wet": 50,
                           "attack": 0.003, "release": 0.3, "ratio": 3, "hp_cutoff": 300},
            "limiter": {"enabled": False, "threshold": 0, "ceiling": -0.35, "release": 0.05},
        },
        "stems": [{"name": n, "color": c} for n, c in STEMS],
    }
    js = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    stem_box = struct.pack(">I", 8 + len(js)) + b"stem" + js
    with open(pfad, "rb") as f:
        data = bytearray(f.read())
    top = boxen(data, 0, len(data))
    moov = next((b for b in top if b[0] == "moov"), None)
    if not moov or moov[1] + moov[2] != len(data) or moov[3] != 8:
        raise RuntimeError("moov steht nicht am Dateiende – Manifest nicht einfügbar")
    _, m_anf, m_gr, _ = moov
    kinder = boxen(data, m_anf + 8, m_anf + m_gr)
    udta = next((b for b in kinder if b[0] == "udta"), None)
    if udta and udta[3] == 8:
        _, u_anf, u_gr, _ = udta
        ende_udta = u_anf + u_gr
        data[ende_udta:ende_udta] = stem_box
        struct.pack_into(">I", data, u_anf, u_gr + len(stem_box))
        struct.pack_into(">I", data, m_anf, m_gr + len(stem_box))
    else:
        neu = struct.pack(">I", 8 + len(stem_box)) + b"udta" + stem_box
        data.extend(neu)
        struct.pack_into(">I", data, m_anf, m_gr + len(neu))
    with open(pfad + ".neu", "wb") as f:
        f.write(data)
    os.replace(pfad + ".neu", pfad)


def demucs_laufen(quelle, tmp, sekunden):
    """Demucs mit niedriger Priorität; pausiert, solange das DJ-Pult läuft. Liefert den Ordner mit den 4 WAVs."""
    py = os.path.join(VENV, "bin", "python")
    threads = os.environ.get("STEMS_THREADS", "2")
    env = dict(os.environ, OMP_NUM_THREADS=threads, MKL_NUM_THREADS=threads, PYTHONUNBUFFERED="1")
    cmd = ["nice", "-n", "19", "ionice", "-c", "3", py, "-m", "demucs", "-n", "htdemucs", "-d", "cpu",
           "--segment", "7", "-j", "1", "-o", tmp, quelle]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    os.set_blocking(p.stdout.fileno(), False)
    puffer = b""
    t0 = time.monotonic()
    pausiert_seit = None
    pause_gesamt = 0.0
    while True:
        rc = p.poll()
        # Rücksicht: DJ-Pult oder Schalter aus → anhalten
        stopp = dj_laeuft() or not einstellung_an()
        if stopp and pausiert_seit is None:
            os.killpg(p.pid, signal.SIGSTOP)
            pausiert_seit = time.monotonic()
            schreiben(pause=True)
        elif not stopp and pausiert_seit is not None:
            os.killpg(p.pid, signal.SIGCONT)
            pause_gesamt += time.monotonic() - pausiert_seit
            pausiert_seit = None
            schreiben(pause=False)
        try:
            stueck = os.read(p.stdout.fileno(), 65536)
            if stueck:
                puffer = (puffer + stueck)[-4000:]
        except (BlockingIOError, OSError):
            pass
        m = re.findall(rb"(\d+)%\|", puffer)
        if m and pausiert_seit is None:
            pz = int(m[-1])
            lauf = time.monotonic() - t0 - pause_gesamt
            eta = lauf / pz * (100 - pz) if pz >= 3 else None
            schreiben(prozent=float(pz), eta_s=int(eta) if eta else None)
        if rc is not None:
            break
        time.sleep(1.0)
    if p.returncode != 0:
        letzte = puffer.decode("utf-8", "replace").strip().splitlines()[-1:] or ["unbekannt"]
        raise RuntimeError("Demucs: " + letzte[0][:160])
    name = os.path.splitext(os.path.basename(quelle))[0]
    kand = glob.glob(os.path.join(tmp, "htdemucs", "*"))
    ordner = next((k for k in kand if os.path.basename(k) == name), kand[0] if kand else None)
    if not ordner:
        raise RuntimeError("Demucs hat keine Spuren geschrieben")
    return ordner


def stem_bauen(quelle):
    os.makedirs(AUSGABE, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="zs-stems-", dir=DATEN)
    try:
        sek = dauer(quelle)
        ordner = demucs_laufen(quelle, tmp, sek)
        spuren = [os.path.join(ordner, n + ".wav") for n in DEMUCS_NAMEN]
        for s in spuren:
            if not os.path.exists(s):
                raise RuntimeError(f"Spur fehlt: {os.path.basename(s)}")
        schreiben(prozent=99.0, eta_s=5)
        ziel = ziel_fuer(quelle)
        zwischen = os.path.join(tmp, "stem.mp4")
        cmd = ["nice", "-n", "19", "ffmpeg", "-v", "error", "-y", "-i", quelle]
        for s in spuren:
            cmd += ["-i", s]
        cmd += ["-map", "0:a:0", "-map", "1:a", "-map", "2:a", "-map", "3:a", "-map", "4:a",
                "-c:a", "aac", "-b:a", "256k", "-ar", "44100", "-ac", "2", "-map_metadata", "0",
                "-disposition:a:0", "default", "-disposition:a:1", "0", "-disposition:a:2", "0",
                "-disposition:a:3", "0", "-disposition:a:4", "0", zwischen]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg: " + (r.stderr.strip().splitlines() or ["?"])[-1][:160])
        manifest_einfuegen(zwischen)
        shutil.move(zwischen, ziel + ".teil")
        os.replace(ziel + ".teil", ziel)
        return ziel
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------
def main():
    if not os.path.exists(os.path.join(VENV, "bin", "python")):
        schreiben(aktiv=False, fehler="Stem-Werkzeug fehlt – in den Einstellungen „Stems einrichten“ tippen")
        return
    erledigt_jetzt = []
    while True:
        if not einstellung_an():
            schreiben(pause=True, aktuell="", prozent=0.0, warteschlange=len(warteschlange()))
            time.sleep(30)
            continue
        if dj_laeuft():
            schreiben(pause=True)
            time.sleep(15)
            continue
        kiste_aufraeumen(erledigt_jetzt)
        erledigt_jetzt = []
        q = warteschlange()
        schreiben(pause=False, warteschlange=len(q), aktuell="", prozent=0.0, eta_s=None)
        if not q:
            time.sleep(60)
            continue
        quelle = q[0]
        name = os.path.basename(quelle)
        print("Stems für", name, flush=True)
        schreiben(aktuell=name, prozent=0.0, fehler=None)
        e = gemerkt()
        try:
            t0 = time.monotonic()
            ziel = stem_bauen(quelle)
            e[schluessel(quelle)] = {"ziel": ziel, "t": int(time.time()), "sek": int(time.monotonic() - t0)}
            status["fertig_heute"] += 1
            status["letzte"] = ([f"✓ {name}"] + status["letzte"])[:5]
            erledigt_jetzt.append(quelle)
            # aus dem Eingangsordner: Original ist jetzt in der Stem-Datei enthalten
            if quelle.startswith(EINGANG + os.sep):
                os.remove(quelle)
        except Exception as ex:
            print("Fehler:", ex, flush=True)
            e[schluessel(quelle)] = {"fehler": str(ex)[:200], "t": int(time.time())}
            status["letzte"] = ([f"✕ {name}: {str(ex)[:80]}"] + status["letzte"])[:5]
            schreiben(fehler=f"{name}: {ex}")
        merken(e)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        schreiben(aktiv=False, fehler=str(ex))
        print("Stem-Arbeiter:", ex, file=sys.stderr)
        sys.exit(1)
