#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZynSimple DJ-Pult: richtet Mixxx vor jedem Start passend ein, damit niemand in die Menüs muss.

  - Ton: Zynthian-Ausgang = Master, USB-Soundkarte (falls gesteckt) = Kopfhörer, Eingänge 1+2 = Handpan/Mikro (Aux)
  - Controller: Pioneer DDJ (200, 400, FLX4 …) und die Zynthian-Tasten/-Regler werden aktiviert
  - Bibliothek: Ordner „MUSIK gekauft“ (WLAN-Freigabe und auf USB-Sticks), Neu-Einlesen beim Start
  - Kiste „Passt zur Handpan“: Tracks in harmonisch passenden Tonarten
  - Kiste „★ Favoriten“: alle Tracks ab vier Sternen (Sterne: ALT + ▲ ▼ am Zynthian)
  - Aufnahmen: auf den USB-Stick (Ordner DJ-Sets), sonst in den DJ-Ordner
  - Ansicht: eigene kompakte Ansicht „ZynSimple Glut“ (ohne Blau), Rückfall auf LateNight

Alles, was der Nutzer in Mixxx selbst ändert, bleibt – außer den hier verwalteten Schlüsseln.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
DATEN = os.environ.get("HOME", "/zynthian/zynthian-my-data/dj")
MIXXX = os.path.join(DATEN, ".mixxx")
ZS_JSON = "/zynthian/zynthian-my-data/zynsimple/zynsimple.json"
MUSIK = os.path.join(DATEN, "MUSIK gekauft")
SKIN = "ZynSimple-Glut"
SKIN_ERSATZ = "LateNight"
OHNE_KH = re.compile(r"TR-?8|TR-?6|DDJ|VirMIDI|Virtual|MIDI", re.I)


def log(*a):
    print("DJ-Einrichtung:", *a, flush=True)


def einstellungen():
    s = {"tonart": "", "dj_auto_rec": False, "dj_clock": True, "dj_handpan_fx": True}
    try:
        with open(ZS_JSON, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    # einstellungen.sh im DJ-Ordner überschreibt (z. B. DJ_SKIN=LateNight)
    try:
        with open(os.path.join(DATEN, "einstellungen.sh"), encoding="utf-8") as f:
            for z in f:
                m = re.match(r"\s*(?:export\s+)?(DJ_[A-Z_]+)=[\"']?([^\"'#\n]*)", z)
                if m:
                    s[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    # Takt: „senden“ (Mixxx/Zynthian geben den Takt an die TR-8S), „folgen“ (TR-8S gibt den Takt vor), „aus“
    if s.get("takt") not in ("senden", "folgen", "aus"):
        s["takt"] = "senden" if s.get("dj_clock", True) else "aus"
    return s


MIXXX_BIN = os.environ.get("ZS_MIXXX", "mixxx")
MIXXX_SHARE = ["/opt/mixxx-2.6/share/mixxx"] if MIXXX_BIN.startswith("/opt/mixxx-2.6") else []


def mixxx_version():
    """Mixxx-Version – „mixxx --version“ dauert auf dem Pi Sekunden, darum gemerkt, solange Mixxx gleich bleibt."""
    merk = os.path.join(DATEN, ".mixxx-version")
    try:
        import shutil
        pfad = MIXXX_BIN if os.path.isabs(MIXXX_BIN) else (shutil.which(MIXXX_BIN) or MIXXX_BIN)
        schluessel = f"{pfad}|{os.stat(pfad).st_mtime:.0f}"
    except Exception:
        schluessel = None
    try:
        with open(merk) as f:
            k, v = f.read().strip().rsplit("=", 1)
        if schluessel and k == schluessel:
            a, b = v.split(".")
            return int(a), int(b)
    except Exception:
        pass
    try:
        out = subprocess.run([MIXXX_BIN, "--version"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"(\d+)\.(\d+)", out)
        if m:
            ver = int(m.group(1)), int(m.group(2))
            if schluessel:
                try:
                    with open(merk, "w") as f:
                        f.write(f"{schluessel}={ver[0]}.{ver[1]}")
                except Exception:
                    pass
            return ver
    except Exception:
        pass
    return 2, 4


def musik_stand(ordner):
    """Fingerabdruck der Musikordner (neueste Änderung eines Unterordners + Anzahl) – ändert sich,
    sobald Musik dazukommt oder verschwindet (Stick-Import, WLAN-Ordner, Stick eingesteckt)."""
    teile = []
    for o in ordner:
        neu, n = 0.0, 0
        try:
            for wurzel, dirs, dateien in os.walk(o):
                try:
                    neu = max(neu, os.stat(wurzel).st_mtime)
                except OSError:
                    pass
                n += len(dateien)
        except Exception:
            pass
        teile.append(f"{o}:{neu:.0f}:{n}")
    return "|".join(teile)


def neu_einlesen_noetig(ordner):
    """Bibliothek nur neu einlesen, wenn sich an der Musik etwas geändert hat – spart beim Start Zeit."""
    merk = os.path.join(DATEN, ".musik-stand")
    jetzt = musik_stand(ordner)
    try:
        with open(merk) as f:
            alt = f.read()
    except Exception:
        alt = None
    try:
        with open(merk, "w") as f:
            f.write(jetzt)
    except Exception:
        return True
    return alt != jetzt or not os.path.exists(os.path.join(MIXXX, "mixxxdb.sqlite"))


# ---------------------------------------------------------------------------------------------
# Soundkarten
# ---------------------------------------------------------------------------------------------
def karten():
    """[(nr, id, name, treiber, kann_abspielen, kann_aufnehmen)]"""
    out = []
    try:
        with open("/proc/asound/cards", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return out
    for m in re.finditer(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(\S+)\s+-\s+(.*)$", text, re.M):
        nr, kid, treiber, name = int(m.group(1)), m.group(2), m.group(3), m.group(4).strip()
        play = bool(glob.glob(f"/proc/asound/card{nr}/pcm*p"))
        cap = bool(glob.glob(f"/proc/asound/card{nr}/pcm*c"))
        out.append((nr, kid, name, treiber, play, cap))
    return out


def wiedergabe_kanaele(nr):
    """Wie viele Ausgangskanäle die USB-Soundkarte hat (DDJ-400/FLX4: 4 = Master 1/2 + Kopfhörer 3/4)."""
    try:
        with open(f"/proc/asound/card{nr}/stream0", encoding="utf-8", errors="replace") as f:
            text = f.read()
        teil = text.split("Capture:")[0]
        werte = [int(x) for x in re.findall(r"Channels:\s*(\d+)", teil)]
        if werte:
            return max(werte)
    except OSError:
        pass
    return 2


def ton_einrichten(s):
    k = karten()
    haupt = next((c for c in k if c[4] and c[3] != "USB-Audio" and not re.search(r"hdmi|vc4|headphones|loopback", c[1] + c[2], re.I)), None)
    if haupt is None:
        haupt = next((c for c in k if c[4]), None)
    # Kopfhörer: am liebsten die Buchse am DJ-Controller (DDJ-400/FLX4 haben eine Soundkarte eingebaut),
    # sonst eine andere USB-Soundkarte
    ddj = next((c for c in k if c[4] and c is not haupt and re.search(r"DDJ", c[1] + " " + c[2], re.I)
                and wiedergabe_kanaele(c[0]) >= 4), None)
    kh = ddj or next((c for c in k if c[4] and c[3] == "USB-Audio" and c is not haupt
                      and not OHNE_KH.search(c[1] + " " + c[2])), None)
    if haupt is None:
        log("keine Soundkarte gefunden")
        return False, None
    log(f"Master: {haupt[2]} ({haupt[1]})" + (f" · Kopfhörer: {kh[2]} ({kh[1]})" if kh else " · keine Kopfhörer-Soundkarte"))
    zeilen = [
        "# Von ZynSimple erzeugt (DJ-Pult) – wird bei jedem Start neu geschrieben",
        f'pcm.zs_haupt {{ type hw; card "{haupt[1]}"; device 0 }}',
        f'ctl.!default {{ type hw; card "{haupt[1]}" }}',
    ]
    if kh and kh is ddj:
        # DJ-Controller: Kanal 1/2 = seine MASTER-Buchsen (bekommen den Mix auch), 3/4 = PHONES vorne
        zeilen += [
            f'pcm.zs_kh {{ type hw; card "{kh[1]}"; device 0; channels 4 }}',
            # über plug: der DDJ kann andere Formate/Raten als die Zynthian-Soundkarte
            'pcm.zs_haupt_p { type plug; slave.pcm "zs_haupt" }',
            'pcm.zs_kh_p { type plug; slave { pcm "zs_kh"; channels 4 } }',
            "pcm.zs_multi {",
            "  type multi",
            '  slaves.a.pcm "zs_haupt_p"', "  slaves.a.channels 2",
            '  slaves.b.pcm "zs_kh_p"', "  slaves.b.channels 4",
            "  bindings.0 { slave a; channel 0 }", "  bindings.1 { slave a; channel 1 }",
            "  bindings.2 { slave b; channel 2 }", "  bindings.3 { slave b; channel 3 }",
            "  bindings.4 { slave b; channel 0 }", "  bindings.5 { slave b; channel 1 }",
            "}",
            'pcm.zs_aus { type plug; slave.pcm "zs_multi"; slave.channels 6; '
            "ttable.0.0 1; ttable.1.1 1; ttable.2.2 1; ttable.3.3 1; ttable.0.4 1; ttable.1.5 1 }",
        ]
    elif kh:
        zeilen += [
            f'pcm.zs_kh {{ type hw; card "{kh[1]}"; device 0 }}',
            "pcm.zs_multi {",
            "  type multi",
            '  slaves.a.pcm "zs_haupt"', "  slaves.a.channels 2",
            '  slaves.b.pcm "zs_kh"', "  slaves.b.channels 2",
            "  bindings.0 { slave a; channel 0 }", "  bindings.1 { slave a; channel 1 }",
            "  bindings.2 { slave b; channel 0 }", "  bindings.3 { slave b; channel 1 }",
            "}",
            'pcm.zs_aus { type plug; slave.pcm "zs_multi"; ttable.0.0 1; ttable.1.1 1; ttable.2.2 1; ttable.3.3 1 }',
        ]
    else:
        zeilen += ['pcm.zs_aus { type plug; slave.pcm "zs_haupt" }']
    zeilen += ['pcm.!default { type asym; playback.pcm "zs_aus"; capture.pcm "plug:zs_haupt" }']
    with open(os.path.join(DATEN, ".asoundrc"), "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    if kh and not ton_probe(4):
        # Zusammenschalten klappt mit dieser Karte nicht → lieber ohne Kopfhörer als ganz ohne Ton
        log(f"Kopfhörer über {kh[2]} lässt sich nicht öffnen – DJ-Pult spielt nur über den Zynthian-Ausgang")
        with open(os.path.join(DATEN, ".asoundrc"), "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen[:3] + ['pcm.zs_aus { type plug; slave.pcm "zs_haupt" }',
                                           'pcm.!default { type asym; playback.pcm "zs_aus"; capture.pcm "plug:zs_haupt" }']) + "\n")
        return True, None
    return True, kh


def ton_probe(kanaele):
    """Kurz Stille über „default“ abspielen – geht das Gerät überhaupt auf?"""
    try:
        r = subprocess.run(["aplay", "-q", "-D", "default", "-c", str(kanaele), "-r", "48000", "-f", "S16_LE",
                            "-d", "1", "/dev/zero"], env=dict(os.environ, HOME=DATEN), capture_output=True, timeout=8)
        return r.returncode == 0
    except FileNotFoundError:
        return True                 # kein aplay → nicht prüfbar, einfach versuchen
    except Exception:
        return False


def soundconfig_zurueck():
    """Rest früherer Versionen („DJ + Instrumente“): die DJ-Ton-Einstellung wiederherstellen."""
    pfad = os.path.join(MIXXX, "soundconfig.xml")
    merker = os.path.join(MIXXX, ".soundconfig.zynsimple")
    if os.path.exists(pfad + ".dj"):
        os.replace(pfad + ".dj", pfad)
        if os.path.exists(merker + ".dj"):
            os.replace(merker + ".dj", merker)
        log("Ton-Einstellung vom DJ-Pult wiederhergestellt")


def soundconfig(s, kh, ver):
    """soundconfig.xml – nur verwaltet, solange der Nutzer sie nicht selbst geändert hat."""
    pfad = os.path.join(MIXXX, "soundconfig.xml")
    merker = os.path.join(MIXXX, ".soundconfig.zynsimple")
    soundconfig_zurueck()
    try:
        with open(pfad, encoding="utf-8", errors="replace") as f:
            if 'api="JACK' in f.read():
                os.remove(pfad)             # Rest vom Hybrid-Modus – im reinen DJ-Pult gibt es kein JACK
                log("JACK-Einstellung vom Hybrid-Modus entfernt")
    except OSError:
        pass
    if os.path.exists(pfad):
        try:
            with open(pfad, "rb") as f:
                ist = hashlib.sha1(f.read()).hexdigest()
            with open(merker, encoding="utf-8") as f:
                war = f.read().strip()
            if ist != war:
                log("Ton-Einstellungen wurden in Mixxx geändert – bleiben so")
                return
        except OSError:
            log("eigene Ton-Einstellungen gefunden – bleiben so")
            return
    main = "Main" if ver >= (2, 4) else "Master"
    teile = [f'  <output type="{main}" index="0" channel="0" channel_count="2"/>']
    if kh:
        teile.append('  <output type="Headphones" index="0" channel="2" channel_count="2"/>')
    if s.get("dj_handpan_fx", True):
        teile.append('  <input type="Auxiliary" index="0" channel="0" channel_count="2"/>')
    xml = ('<!DOCTYPE SoundManagerConfig>\n'
           '<SoundManagerConfig api="ALSA" samplerate="48000" latency="5" sync_buffers="2" deck_count="4" '
           'force_network_clock="0">\n'
           ' <SoundDevice name="default" alias="default" portAudioIndex="-1">\n' + "\n".join(teile) + "\n"
           ' </SoundDevice>\n</SoundManagerConfig>\n')
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(xml)
    with open(merker, "w", encoding="utf-8") as f:
        f.write(hashlib.sha1(xml.encode()).hexdigest())


# ---------------------------------------------------------------------------------------------
# mixxx.cfg
# ---------------------------------------------------------------------------------------------
def cfg_lesen(pfad):
    data, order = {}, []
    sek = None
    try:
        with open(pfad, encoding="utf-8", errors="replace") as f:
            for z in f:
                z = z.rstrip("\n")
                m = re.match(r"^\[(.+)\]\s*$", z)
                if m:
                    sek = "[" + m.group(1) + "]"
                    if sek not in data:
                        data[sek] = {}
                        order.append(sek)
                elif sek and z.strip():
                    k, _, v = z.partition(" ")
                    data[sek][k] = v
    except OSError:
        pass
    return data, order


def cfg_schreiben(pfad, data, order):
    for sek in data:
        if sek not in order:
            order.append(sek)
    with open(pfad + ".neu", "w", encoding="utf-8") as f:
        for sek in order:
            f.write(sek + "\n")
            for k, v in data[sek].items():
                f.write(f"{k} {v}\n")
            f.write("\n")
    os.replace(pfad + ".neu", pfad)


def midi_namen():
    """Namen der MIDI-Geräte, wie Mixxx sie sieht (ALSA-Sequencer-Ports)."""
    namen = set()
    try:
        out = subprocess.run(["amidi", "-l"], capture_output=True, text=True, timeout=5).stdout
        for z in out.splitlines()[1:]:
            teile = z.split(None, 2)
            if len(teile) == 3:
                namen.add(teile[2].strip())
    except Exception:
        pass
    try:
        out = subprocess.run(["aconnect", "-l"], capture_output=True, text=True, timeout=5).stdout
        for m in re.finditer(r"^\s+\d+\s+'([^']+)'", out, re.M):
            namen.add(m.group(1).strip())
    except Exception:
        pass
    return namen


def schluessel(name):
    return re.sub(r"[ /\\]", "_", name)


RX_DDJ = re.compile(r"DDJ-?(FLX\d+|[A-Z]{0,3}\d+|[A-Z]{2,3}\d?)", re.I)

def ddj_modell(name):
    """„DDJ-400 MIDI 1“ → „400“, „DDJ-FLX4“ → „FLX4“, „DDJ-200“ → „200“."""
    m = RX_DDJ.search(name or "")
    return m.group(1).upper() if m else None


def ddj_mapping(modell):
    """Mitgelieferte Mixxx-Belegung für das DDJ-Modell (z. B. Pioneer-DDJ-400.midi.xml)."""
    for basis in [b + "/controllers" for b in MIXXX_SHARE] + ["/usr/share/mixxx/controllers",
                                                              "/usr/local/share/mixxx/controllers"]:
        kand = sorted(f for f in glob.glob(os.path.join(basis, f"*DDJ-{modell}.midi.xml")) +
                      glob.glob(os.path.join(basis, f"*DDJ-{modell} *.midi.xml")) if "lternative" not in f)
        if kand:
            return kand[0]
    return None


def angeschlossene_ddj():
    """Modelle der angeschlossenen Pioneer-Controller (aus den MIDI-Namen und /proc/asound/cards)."""
    out = set()
    texte = list(midi_namen())
    try:
        with open("/proc/asound/cards", encoding="utf-8") as f:
            texte.append(f.read())
    except OSError:
        pass
    for t in texte:
        for m in RX_DDJ.finditer(t):
            out.add(m.group(1).upper())
    return out


def controller(data, ver):
    ziel = os.path.join(MIXXX, "controllers")
    os.makedirs(ziel, exist_ok=True)
    for f in glob.glob(os.path.join(HIER, "mixxx", "*.midi.xml")) + glob.glob(os.path.join(HIER, "mixxx", "*.js")):
        shutil.copy(f, ziel)
    # Belegung je DDJ-Modell (DDJ-200, DDJ-400, DDJ-FLX4 …) – angeschlossene zuerst, sonst die üblichen
    modelle = angeschlossene_ddj() or {"200", "400", "FLX4"}
    mappings = {}
    for mo in modelle:
        x = ddj_mapping(mo)
        if x:
            mappings[mo] = x
    log("DDJ-Modelle:", ", ".join(sorted(modelle)), "→", ", ".join(os.path.basename(v) for v in mappings.values()) or "keine Belegung")
    zyn = os.path.join(ziel, "Zynthian-V5-ZynSimple.midi.xml")
    namen = midi_namen()
    for mo in mappings:
        namen |= {f"DDJ-{mo}", f"DDJ-{mo} MIDI 1"}          # auch wenn der DDJ gerade nicht steckt
    # alte Zuordnungen (frühere Versionen: VirMIDI, „ZynSimple DDJ-200“ …) erst einmal aus – unten wird neu belegt
    for sek in ("[Controller]",):
        for k in list(data.get(sek, {})):
            if re.search(r"VirMIDI|Virtual_Raw|ZynSimple|DDJ", k, re.I):
                data[sek][k] = "0"
    for name in namen:
        datei = None
        mo = ddj_modell(name) if not re.search(r"ZynSimple", name, re.I) else None
        if mo:
            datei = mappings.get(mo)
        elif re.search(r"VirMIDI|Virtual Raw MIDI", name, re.I):
            datei = zyn
        if not datei:
            continue
        for k in {schluessel(name), schluessel(re.sub(r"\s+MIDI\s*\d*$", "", name)), schluessel(name + " MIDI 1")}:
            for sek in ("[ControllerPreset]", "[ControllerMapping]"):
                data.setdefault(sek, {})[k] = datei
            data.setdefault("[Controller]", {})[k] = "1"
        log(f"Controller {name} → {os.path.basename(datei)}")


def sticks():
    """Eingehängte USB-Sticks/SD-Karten (hängt nicht eingehängte selbst ein) – siehe stick.py."""
    try:
        sys.path.insert(0, HIER)
        import stick
        return [x["pfad"] for x in stick.sticks(warten=True)]
    except Exception as e:
        log("Sticks:", e)
    out = []
    for base in ("/media/root", "/media"):
        try:
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if os.path.ismount(p) and p not in out:
                    out.append(p)
        except OSError:
            pass
    return out


def usb_musik():
    """Musik auf USB-Sticks: der Ordner „MUSIK gekauft“, wenn es ihn gibt – sonst der ganze Stick."""
    out = []
    for stick in sticks():
        p = os.path.join(stick, "MUSIK gekauft")
        if not os.path.isdir(p):
            p = stick
        # schon auf den Zynthian übernommen (Import-Knopf)? Dann nicht doppelt in die Bibliothek
        if not os.path.exists(os.path.join(p, ".zynsimple-importiert")):
            out.append(p)
    for p in out:
        log("USB-Musik:", p)
    return out


def usb_stick():
    for base in ("/media/root", "/media"):
        try:
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d)
                if os.path.ismount(p) and os.access(p, os.W_OK):
                    return p
        except OSError:
            pass
    return None


def bibliothek(ordner):
    db = os.path.join(MIXXX, "mixxxdb.sqlite")
    if not os.path.exists(db):
        return
    try:
        con = sqlite3.connect(db, timeout=5)
        for o in ordner:
            con.execute("INSERT OR IGNORE INTO directories (directory) VALUES (?)", (o,))
        con.commit()
        con.close()
    except Exception as e:
        log("Bibliothek:", e)


def passende_kiste(s):
    """Kiste „Passt zur Handpan (…)“ aus den erkannten Tonarten füllen."""
    db = os.path.join(MIXXX, "mixxxdb.sqlite")
    if not os.path.exists(db):
        return
    sys.path.insert(0, "/zynthian/zynthian-my-data/zynsimple")
    try:
        from zynsimple.helfer import passende_tonarten, tonart_name
    except Exception as e:
        log("Tonarten:", e)
        return
    wert = s.get("tonart") or ""
    try:
        con = sqlite3.connect(db, timeout=5)
        alt = con.execute("SELECT id FROM crates WHERE name LIKE 'Passt zur Handpan%'").fetchall()
        for (cid,) in alt:
            con.execute("DELETE FROM crate_tracks WHERE crate_id=?", (cid,))
            con.execute("DELETE FROM crates WHERE id=?", (cid,))
        keys = []
        for ton, art in passende_tonarten(wert):
            keys.append(ton + 1 if art == "dur" else ton + 13)      # Mixxx: 1–12 Dur ab C, 13–24 Moll ab C
        if keys:
            name = f"Passt zur Handpan ({tonart_name(wert)})"
            cur = con.execute("INSERT INTO crates (name, count, show, locked, autodj_source) VALUES (?, 0, 1, 0, 0)", (name,))
            cid = cur.lastrowid
            q = "SELECT id FROM library WHERE mixxx_deleted=0 AND key_id IN (%s)" % ",".join("?" * len(keys))
            ids = [r[0] for r in con.execute(q, keys).fetchall()]
            con.executemany("INSERT OR IGNORE INTO crate_tracks (crate_id, track_id) VALUES (?, ?)", [(cid, t) for t in ids])
            con.execute("UPDATE crates SET count=? WHERE id=?", (len(ids), cid))
            log(f"Kiste „{name}“: {len(ids)} Tracks")
        con.commit()
        con.close()
    except Exception as e:
        log("Kiste:", e)


def stem_kiste():
    """Kiste „Stems vorbereiten“ anlegen: Tracks hineinziehen → werden im Hintergrund in Stems zerlegt."""
    db = os.path.join(MIXXX, "mixxxdb.sqlite")
    if not os.path.exists(db):
        return
    try:
        con = sqlite3.connect(db, timeout=5)
        if not con.execute("SELECT id FROM crates WHERE name='Stems vorbereiten'").fetchone():
            con.execute("INSERT INTO crates (name, count, show, locked, autodj_source) VALUES ('Stems vorbereiten', 0, 1, 0, 0)")
        con.commit()
        con.close()
    except Exception as e:
        log("Stem-Kiste:", e)
    for d in ("Stems", "Stems erzeugen"):
        os.makedirs(os.path.join(MUSIK, d), exist_ok=True)


def favoriten_kiste():
    """Kiste „★ Favoriten“: alle Tracks mit mindestens vier Sternen (vor jedem Start neu gefüllt)."""
    db = os.path.join(MIXXX, "mixxxdb.sqlite")
    if not os.path.exists(db):
        return
    try:
        con = sqlite3.connect(db, timeout=5)
        row = con.execute("SELECT id FROM crates WHERE name='★ Favoriten'").fetchone()
        cid = row[0] if row else con.execute(
            "INSERT INTO crates (name, count, show, locked, autodj_source) VALUES ('★ Favoriten', 0, 1, 0, 0)").lastrowid
        con.execute("DELETE FROM crate_tracks WHERE crate_id=?", (cid,))
        ids = [r[0] for r in con.execute("SELECT id FROM library WHERE mixxx_deleted=0 AND rating>=4").fetchall()]
        con.executemany("INSERT OR IGNORE INTO crate_tracks (crate_id, track_id) VALUES (?, ?)", [(cid, t) for t in ids])
        con.execute("UPDATE crates SET count=? WHERE id=?", (len(ids), cid))
        con.commit()
        con.close()
        log(f"Kiste „★ Favoriten“: {len(ids)} Tracks")
    except Exception as e:
        log("Favoriten:", e)


def skin(data, s):
    wahl = s.get("DJ_SKIN") or SKIN
    if wahl == SKIN:
        quelle = os.path.join(HIER, "mixxx", "skin", SKIN)
        for basis in [b + "/skins" for b in MIXXX_SHARE] + ["/usr/share/mixxx/skins", "/usr/local/share/mixxx/skins"]:
            if os.path.isdir(basis):
                ziel = os.path.join(basis, SKIN)
                shutil.rmtree(ziel, ignore_errors=True)
                shutil.copytree(quelle, ziel)
                break
        if os.path.exists(os.path.join(DATEN, ".skin-kaputt")):
            wahl = SKIN_ERSATZ
            log("eigene Ansicht ist beim letzten Mal nicht gestartet → LateNight")
    data.setdefault("[Config]", {})["ResizableSkin"] = wahl
    data["[Config]"]["Skin"] = wahl


def config_js(s):
    ziel = os.path.join(MIXXX, "controllers", "Zynthian-V5-ZynSimple-config.js")
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("// Von ZynSimple erzeugt – Einstellungen kommen aus dem Zynthian (Einstellungen → DJ-Pult)\n")
        f.write("var ZynV5Config = " + json.dumps({
            "autoRec": bool(s.get("dj_auto_rec")),
            "clock": s.get("takt") == "senden",
            "folgen": s.get("takt") == "folgen",
            "handpanFx": bool(s.get("dj_handpan_fx", True)),
            "lautstaerke": int(s.get("dj_lautstaerke", 100) or 100),
        }) + ";\n")


def stick_status():
    """Kurzinfo für das DJ-Menü: welcher Stick, wie viele Musikdateien."""
    endungen = (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".aif", ".aiff", ".opus", ".mp4")
    info = []
    for p in usb_musik():
        n = 0
        for _, _, files in os.walk(p):
            n += sum(1 for f in files if f.lower().endswith(endungen))
            if n > 20000:
                break
        info.append({"pfad": p, "name": os.path.basename(p.rstrip("/")) or p, "dateien": n})
    try:
        with open("/tmp/zynsimple-dj-sticks.json", "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False)
    except OSError:
        pass


def main():
    os.makedirs(MIXXX, exist_ok=True)
    os.makedirs(MUSIK, exist_ok=True)
    s = einstellungen()
    ver = mixxx_version()
    try:
        ok, kh = ton_einrichten(s)
        if ok:
            soundconfig(s, kh, ver)
    except Exception as e:
        log("Ton-Einrichtung:", e)
    pfad = os.path.join(MIXXX, "mixxx.cfg")
    data, order = cfg_lesen(pfad)
    # Controller zuerst – der DDJ muss steuern, auch wenn weiter unten etwas schiefgeht
    try:
        controller(data, ver)
    except Exception as e:
        log("Controller:", e)
    try:
        ordner = [MUSIK] + usb_musik()
    except Exception as e:
        log("USB-Musik:", e)
        ordner = [MUSIK]
    data.setdefault("[Playlist]", {})["Directory"] = ordner[-1]
    lib = data.setdefault("[Library]", {})
    lib["RescanOnStartup"] = "1" if (neu_einlesen_noetig(ordner) or os.environ.get("ZS_NEU_EINLESEN")) else "0"
    # Seitenleiste aufräumen: nur, was man hier braucht (keine iTunes/Rekordbox/Serato/Traktor …)
    for k in ("ShowITunesLibrary", "ShowRekordboxLibrary", "ShowSeratoLibrary", "ShowTraktorLibrary",
              "ShowRhythmboxLibrary", "ShowBansheeLibrary"):
        lib[k] = "0"
    if lib.get("RowHeight") in (None, "", "30"):
        lib["RowHeight"] = "34"         # etwas mehr Luft zwischen den Zeilen – gleiche Schriftgröße
    # Mixxx 2.5+/2.6: nie mehr fragen „Darf Mixxx die Menüleiste ausblenden?“ – ausgeblendet, ohne Rückfrage
    data.setdefault("[Config]", {})["hide_menubar"] = "1"
    data["[Config]"]["show_menubar_hint"] = "0"
    # Mixxx auf Deutsch
    if not data.setdefault("[Config]", {}).get("Locale", "").strip():
        data["[Config]"]["Locale"] = "de_DE"
    stick = usb_stick()
    rec = os.path.join(stick, "DJ-Sets") if stick else os.path.join(DATEN, "DJ-Sets")
    try:
        os.makedirs(rec, exist_ok=True)
    except OSError:
        rec = os.path.join(DATEN, "DJ-Sets")
        os.makedirs(rec, exist_ok=True)
    data.setdefault("[Recording]", {})["Directory"] = rec
    data["[Recording]"].setdefault("Encoding", "FLAC")
    skin(data, s)
    cfg_schreiben(pfad, data, order)
    for schritt in (lambda: config_js(s), lambda: bibliothek(ordner), lambda: passende_kiste(s),
                    stem_kiste, favoriten_kiste, stick_status):
        try:
            schritt()
        except Exception as e:
            log("Fehler (übersprungen):", e)
    log("fertig")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("Fehler:", e)
