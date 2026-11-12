# -*- coding: utf-8 -*-
"""
ZynSimple – Startbild: die Gans statt des Vangelis-Bildes beim Hochfahren des Zynthian.

Der Zynthian zeigt beim Start /zynthian/config/img/fb_zynthian_boot.jpg (und bei Fehlern fb_zynthian_error.jpg).
Beide erzeugt er einmalig aus seinem Logo-Bild – nach einem Zynthian-Update manchmal neu. ZynSimple schaut bei
jedem Start nach und legt die Gans wieder darüber. Das Original bleibt als *.zynthian daneben liegen
(Einstellung „Gans beim Start“ aus → Original zurück).
"""
import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading

log = logging.getLogger("zynsimple")

IMG_DIR = "/zynthian/config/img"
ZIELE = {"boot": os.path.join(IMG_DIR, "fb_zynthian_boot.jpg"), "fehler": os.path.join(IMG_DIR, "fb_zynthian_error.jpg")}
GANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "gans_380.png")
BILD_VERSION = 2                       # neue Gestaltung → einmal neu erzeugen
ANIM_SKRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plymouth-gans.sh")
ANIM_FRAME = "/usr/share/plymouth/themes/zynloganim/frame-0.png"


def _md5(p):
    try:
        with open(p, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


def _groesse(p):
    try:
        out = subprocess.run(["identify", "-format", "%w %h", p], capture_output=True, text=True, timeout=10).stdout
        w, h = (int(x) for x in out.split()[:2])
        return w, h
    except Exception:
        return 1024, 600


def bild_bauen(ziel, art, w, h):
    """Alles untereinander: Gans im Ring (Mitte oben), darunter „zynthian“, darunter die Zeile in Gold.
    Oben bleibt Platz für Meldungen des Zynthian. Dunkler, warmer Hintergrund – ohne Blau."""
    ring = "#e0445e" if art == "fehler" else "#e8b04a"
    glut = "#3a1414" if art == "fehler" else "#3a2610"
    r = int(h * 0.25)                         # Ring-Radius
    cx, cy = w // 2, int(h * 0.42)
    gh = int(r * 1.62)                        # Gans passt in den Ring
    titel = max(12, int(h * 0.085))
    zeile = max(8, int(h * 0.042))
    y_titel = cy + r + int(h * 0.02)          # Oberkante „zynthian“
    y_zeile = y_titel + int(titel * 1.25)
    tmp = ziel + ".neu.jpg"
    cmd = ["convert", "-size", f"{w}x{h}", f"radial-gradient:{glut}-#0b0908",
           "-fill", "none", "-stroke", "#3a2c18", "-strokewidth", "2", "-draw", f"circle {cx},{cy} {cx + r + 8},{cy}",
           "-stroke", ring, "-strokewidth", "3", "-draw", f"circle {cx},{cy} {cx + r},{cy}",
           "(", GANS, "-resize", f"x{gh}", ")", "-gravity", "north", "-geometry", f"+0+{cy - gh // 2}",
           "-composite", "-stroke", "none",
           "-fill", "#f3e9d8", "-font", "DejaVu-Sans", "-pointsize", str(titel),
           "-gravity", "north", "-annotate", f"+0+{y_titel}", "zynthian",
           "-fill", ring, "-pointsize", str(zeile), "-annotate", f"+0+{y_zeile}",
           "ZynSimple   ·   Barden Beats   ·   DJ-Pult" if art == "boot" else "Da ging etwas schief",
           "-strip", "-quality", "92", tmp]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    os.replace(tmp, ziel)


def anwenden(settings, merker_datei):
    """Gans setzen (oder bei ausgeschalteter Einstellung das Original zurückholen)."""
    try:
        with open(merker_datei, encoding="utf-8") as f:
            merker = json.load(f)
    except Exception:
        merker = {}
    an = bool(settings.get("boot_gans", True))
    geaendert = False
    for art, ziel in ZIELE.items():
        if not os.path.exists(ziel) and not os.path.exists(ziel + ".zynthian"):
            continue
        original = ziel + ".zynthian"
        if not an:
            if os.path.exists(original):
                shutil.copy2(original, ziel)
                os.remove(original)
                merker.pop(art, None)
                geaendert = True
            continue
        jetzt = _md5(ziel)
        if jetzt and jetzt == merker.get(art) and merker.get("v") == BILD_VERSION:
            continue                                    # unsere Gans ist schon drauf
        if not os.path.exists(GANS) or not shutil.which("convert"):
            log.info("ZynSimple: Startbild – ImageMagick oder Gans fehlt")
            return
        try:
            shutil.copy2(ziel, original)                 # vom Zynthian (neu) erzeugtes Bild aufheben
            w, h = _groesse(ziel)
            bild_bauen(ziel, art, w, h)
            merker[art] = _md5(ziel)
            merker["v"] = BILD_VERSION
            geaendert = True
            log.info(f"ZynSimple: Startbild ({art}) → Gans {w}×{h}")
        except Exception as e:
            log.warning(f"ZynSimple: Startbild nicht gesetzt ({e})")
    # Lade-Animation (Plymouth): nur auf Wunsch – sie baut die Startdateien neu (dauert ~1 Minute)
    anim = bool(settings.get("boot_animation", False)) and an
    try:
        jetzt = _md5(ANIM_FRAME)
        if os.path.exists(ANIM_SKRIPT) and os.path.exists(ANIM_FRAME):
            if anim and jetzt != merker.get("anim"):
                log.info("ZynSimple: Lade-Animation → Gans (baut Startdateien neu)")
                if subprocess.call(["bash", ANIM_SKRIPT, "an"], timeout=900) == 0:
                    merker["anim"] = _md5(ANIM_FRAME)
                    geaendert = True
            elif not anim and merker.get("anim"):
                if subprocess.call(["bash", ANIM_SKRIPT, "aus"], timeout=900) == 0:
                    merker.pop("anim", None)
                    geaendert = True
    except Exception as e:
        log.warning(f"ZynSimple: Lade-Animation: {e}")
    if geaendert:
        try:
            with open(merker_datei, "w", encoding="utf-8") as f:
                json.dump(merker, f)
        except OSError:
            pass


def im_hintergrund(settings, merker_datei):
    threading.Thread(target=anwenden, args=(settings, merker_datei), daemon=True).start()
