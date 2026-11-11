#!/bin/bash
# ZynSimple DJ-Pult: X-Sitzung (startx) anstelle der Zynthian-Oberfläche.
# Dreht den Bildschirm passend, startet die Zynthian-Tasten als Fernbedienung und Mixxx im Vollbild.
# Endet Mixxx, endet die Sitzung – der Dienst kehrt dann von selbst zum Zynthian zurück.
HIER="$(cd "$(dirname "$0")" && pwd)"
DATEN="${HOME:-/zynthian/zynthian-my-data/dj}"
[ -f /zynthian/config/zynthian_envars.sh ] && source /zynthian/config/zynthian_envars.sh
# gleiche Dreh-Einstellung wie Barden Beats, falls dort angepasst
[ -f /zynthian/zynthian-my-data/imres/einstellungen.sh ] && source /zynthian/zynthian-my-data/imres/einstellungen.sh
[ -f "$DATEN/einstellungen.sh" ] && source "$DATEN/einstellungen.sh"

xset s off -dpms s noblank 2>/dev/null
command -v xsetroot >/dev/null && xsetroot -solid "#100e0d"

# Bildschirm drehen – beim V5 ist das Display kopfüber eingebaut.
# Überschreiben in $DATEN/einstellungen.sh: DJ_DREHEN=normal|inverted|left|right
DREHEN="${DJ_DREHEN:-${IMRES_DREHEN:-}}"
if [ -z "$DREHEN" ]; then
  case "${ZYNTHIAN_KIT_VERSION:-}" in V5*) DREHEN=inverted ;; *) DREHEN=normal ;; esac
fi
TOUCH="${DJ_TOUCH_DREHEN:-${IMRES_TOUCH_DREHEN:-$DREHEN}}"
for i in $(seq 1 10); do xrandr >/dev/null 2>&1 && break; sleep 0.5; done
AUSGANG=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')
if [ -n "$AUSGANG" ]; then xrandr --output "$AUSGANG" --rotate "$DREHEN" 2>/dev/null
else xrandr -o "$DREHEN" 2>/dev/null; fi
case "$TOUCH" in
  inverted) MATRIX="-1 0 1 0 -1 1 0 0 1" ;; left) MATRIX="0 -1 1 1 0 0 0 0 1" ;;
  right) MATRIX="0 1 0 -1 0 1 0 0 1" ;; *) MATRIX="1 0 0 0 1 0 0 0 1" ;;
esac
xinput list --name-only 2>/dev/null | grep -i -E "touch|ft5|goodix|ili|edt" | while read -r GERAET; do
  xinput set-prop "$GERAET" "Coordinate Transformation Matrix" $MATRIX 2>/dev/null
done
echo "DJ-Pult: Bildschirm $AUSGANG → $DREHEN, Touch → $TOUCH"
command -v unclutter >/dev/null && unclutter -idle 1 -root &

# Zynthian-Tasten: BACK halten → Zynthian, MENU halten → Barden Beats
PY=python3
for k in /zynthian/venv/bin/python3 /usr/bin/python3; do [ -x "$k" ] && { PY="$k"; break; }; done
"$PY" "$HIER/dj-tasten.py" &
TASTEN=$!
trap 'kill $TASTEN 2>/dev/null' EXIT

# Mixxx: Einstellungen und Bibliothek liegen in $DATEN/.mixxx (wird beim Zynthian-Backup mitgesichert)
echo "DJ-Pult: starte Mixxx"
mixxx --fullScreen
echo "DJ-Pult: Mixxx beendet ($?)"
