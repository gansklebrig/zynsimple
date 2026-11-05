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

if [ "$1" == "--alles" ]; then
    rm -rf "$DEST" && echo "Ordner $DEST gelöscht"
else
    echo "Der Ordner $DEST bleibt (mit '--alles' wird auch er gelöscht)."
fi

if command -v systemctl >/dev/null && systemctl list-units --type=service 2>/dev/null | grep -q zynthian.service; then
    systemctl restart zynthian
fi
echo "Fertig."
