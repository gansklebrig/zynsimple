#!/bin/bash
# ZynSimple – Installation auf dem Zynthian
# Aufruf auf dem Zynthian (per SSH):   bash install.sh
set -e

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${ZS_DIR:-/zynthian/zynthian-my-data/zynsimple}"

echo "== ZynSimple wird installiert =="

echo "SCHRITT 1/6 Suche die Python-Umgebung der Zynthian-Oberfläche"
# 1) Python finden, mit dem die Zynthian-Oberfläche läuft
#    (Zynthian nutzt ein venv; dessen python3 ist nur ein Link aufs System-Python,
#     darum zuerst das venv nehmen und den Link NICHT auflösen)
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    PID=$(pgrep -f zynthian_main.py | head -n1 || true)
    if [ -n "$PID" ] && [ -r "/proc/$PID/environ" ]; then
        VENV=$(tr '\0' '\n' < "/proc/$PID/environ" | sed -n 's/^VIRTUAL_ENV=//p' | head -n1)
        [ -n "$VENV" ] && [ -x "$VENV/bin/python3" ] && PY="$VENV/bin/python3"
    fi
fi
if [ -z "$PY" ] && [ -x /zynthian/venv/bin/python3 ]; then
    PY=/zynthian/venv/bin/python3
fi
if [ -z "$PY" ]; then
    PID=$(pgrep -f zynthian_main.py | head -n1 || true)
    [ -n "$PID" ] && [ -e "/proc/$PID/exe" ] && PY=$(readlink -f "/proc/$PID/exe")
fi
if [ -z "$PY" ]; then
    PY=$(command -v python3)
fi
SITE=$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
echo "Python:        $PY"
echo "site-packages: $SITE"

echo "SCHRITT 2/6 Kopiere die neuen Dateien"
# 2) Dateien kopieren (Einstellungen bleiben erhalten)
mkdir -p "$DEST"
if [ "$SRC" != "$DEST" ]; then
    rm -rf "$DEST/zynsimple"
    cp -r "$SRC/zynsimple" "$DEST/"
    rm -rf "$DEST/dj"
    [ -d "$SRC/dj" ] && cp -r "$SRC/dj" "$DEST/"
    cp "$SRC/zynsimple_boot.py" "$DEST/"
    cp "$SRC/install.sh" "$SRC/uninstall.sh" "$DEST/" 2>/dev/null || true
    cp "$SRC/ANLEITUNG.md" "$DEST/" 2>/dev/null || true
fi
if [ ! -f "$DEST/zynsimple.json" ]; then
    cat > "$DEST/zynsimple.json" <<'JSON'
{
  "web_enabled": true,
  "web_port": 8090,
  "pin": "",
  "screen_enabled": true,
  "replace_home": true,
  "strip_min_width": 130
}
JSON
fi
rm -f "$DEST/zynsimple.disabled"
find "$DEST" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "SCHRITT 3/6 Richte das DJ-Pult und den WLAN-Ordner ein"
# 2b) DJ-Pult (Mixxx) einrichten – Mixxx selbst wird erst beim ersten Start installiert
if [ -f "$DEST/dj/zynsimple-dj" ] && [ -d /run/systemd/system ]; then
    ZS_DIR="$DEST" bash "$DEST/dj/zynsimple-dj" einrichten || echo "DJ-Pult: Einrichtung übersprungen"
fi

# 2c) Bühnen-Sicherheit: Speicherkarte nach Stromausfall beim Start automatisch prüfen und reparieren
for CMDLINE in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
    [ -f "$CMDLINE" ] || continue
    if ! grep -q "fsck.repair" "$CMDLINE"; then
        cp "$CMDLINE" "$CMDLINE.vor-zynsimple" && sed -i '1 s/$/ fsck.repair=yes/' "$CMDLINE" \
            && echo "Speicherkarte: wird nach Stromausfall beim Start geprüft (fsck.repair=yes)"
    fi
    break
done

echo "SCHRITT 4/6 Hänge ZynSimple in die Oberfläche ein"
# 3) Startdatei (.pth) anlegen – wird bei jedem Python-Start gelesen,
#    hängt sich aber nur in die Zynthian-Oberfläche ein.
cat > "$SITE/zynsimple.pth" <<PTH
import sys, os; p='$DEST'; os.path.isfile(p + '/zynsimple_boot.py') and (p in sys.path or sys.path.append(p)) or True; os.path.isfile(p + '/zynsimple_boot.py') and __import__('zynsimple_boot')
PTH
echo "Startdatei:    $SITE/zynsimple.pth"
# Reste früherer Installationen an anderer Stelle entfernen
for ALT in /usr/local/lib/python3*/dist-packages/zynsimple.pth /usr/lib/python3/dist-packages/zynsimple.pth /zynthian/venv/lib/python3*/site-packages/zynsimple.pth; do
    [ -f "$ALT" ] && [ "$ALT" != "$SITE/zynsimple.pth" ] && rm -f "$ALT" && echo "Alte Startdatei entfernt: $ALT"
done

echo "SCHRITT 5/6 Selbsttest"
# 4) Kurzer Selbsttest
"$PY" -c "import zynsimple_boot, sys; assert any(type(f).__name__=='_Finder' for f in sys.meta_path); print('Selbsttest:    OK')"

# Merker für die Oberfläche: nach dem Neustart „Update fertig“ zeigen
VER=$(cat "$SRC/VERSION" 2>/dev/null || echo "?")
echo "$VER" > "$DEST/.update_fertig"
echo "Fertig! Version $VER ist installiert."
echo "SCHRITT 6/6 Die Oberfläche startet neu"
# 5) Oberfläche neu starten
if [ -z "$ZS_NO_RESTART" ] && command -v systemctl >/dev/null && systemctl list-units --type=service 2>/dev/null | grep -q zynthian.service; then
    echo "Starte die Zynthian-Oberfläche neu ..."
    systemctl restart zynthian
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PORT=$("$PY" -c "import json;print(json.load(open('$DEST/zynsimple.json')).get('web_port',8090))" 2>/dev/null || echo 8090)
echo
echo "Handy/Tablet:  http://${IP:-zynthian.local}:$PORT"
echo "                  oder http://zynthian.local:$PORT"
