#!/bin/bash
# ZynSimple – Entfernen. Der Zynthian-Code selbst wurde nie verändert.
DEST="${ZS_DIR:-/zynthian/zynthian-my-data/zynsimple}"

echo "== ZynSimple wird entfernt =="
for PY in /zynthian/venv/bin/python3 python3 python3.11 python3.12 python3.13; do
    command -v "$PY" >/dev/null 2>&1 || [ -x "$PY" ] || continue
    SITE=$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' 2>/dev/null) || continue
    if [ -f "$SITE/zynsimple.pth" ]; then
        rm -f "$SITE/zynsimple.pth" && echo "Entfernt: $SITE/zynsimple.pth"
    fi
done

# Stem-Dienst entfernen (das Werkzeug unter /opt/zynsimple-stems und Mixxx 2.6 unter /opt/mixxx-2.6 bleiben;
# mit „rm -rf /opt/zynsimple-stems /opt/mixxx-2.6“ lassen sie sich von Hand löschen)
if [ -f /etc/systemd/system/zynsimple-stems.service ]; then
    systemctl disable --now zynsimple-stems 2>/dev/null
    rm -f /etc/systemd/system/zynsimple-stems.service
fi

# DJ-Pult entfernen (Mixxx selbst bleibt installiert: sudo apt remove mixxx)
if [ -f /etc/systemd/system/zynsimple-dj.service ]; then
    systemctl stop zynsimple-dj 2>/dev/null
    rm -f /etc/systemd/system/zynsimple-dj.service /usr/local/bin/zynsimple-dj /etc/samba/zynsimple-dj.conf
    rm -rf /usr/share/mixxx/skins/ZynSimple-Glut
    sed -i '/zynsimple-dj.conf/d' /etc/samba/smb.conf 2>/dev/null
    systemctl daemon-reload 2>/dev/null
    echo "DJ-Pult entfernt"
fi

if [ "$1" == "--alles" ]; then
    rm -rf "$DEST" && echo "Ordner $DEST gelöscht"
else
    echo "Der Ordner $DEST bleibt (mit '--alles' wird auch er gelöscht)."
fi

if command -v systemctl >/dev/null && systemctl list-units --type=service 2>/dev/null | grep -q zynthian.service; then
    systemctl restart zynthian
fi
echo "Fertig."
