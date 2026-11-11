#!/bin/bash
# ZynSimple DJ-Pult: X-Sitzung (startx) anstelle der Zynthian-Oberfläche.
# Richtet Mixxx passend ein, dreht den Bildschirm, startet den DJ-Helfer (Tasten, LEDs, TR-8S-Clock) und Mixxx.
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

PY=python3
for k in /zynthian/venv/bin/python3 /usr/bin/python3; do [ -x "$k" ] && { PY="$k"; break; }; done

# Startbildschirm mit der Gans und Ladebalken, bis Mixxx da ist
phase() { echo "$1" > /tmp/zynsimple-dj-phase; }
phase start
TKPY=""
for k in /zynthian/venv/bin/python3 /usr/bin/python3; do [ -x "$k" ] && "$k" -c "import tkinter" 2>/dev/null && { TKPY="$k"; break; }; done
[ -n "$TKPY" ] && "$TKPY" "$HIER/dj-splash.py" &

# Zynthian-Tasten als Controller, LEDs, TR-8S-Clock, BACK/MENU/STOP halten
"$PY" "$HIER/dj-helfer.py" &
HELFER=$!
trap 'kill $HELFER 2>/dev/null' EXIT
sleep 1   # virtueller MIDI-Anschluss steht, bevor Mixxx ihn sucht

# Mixxx einrichten (Ton, Controller, Bibliothek „MUSIK gekauft“, Kiste „Passt zur Handpan“, Aufnahmen, Ansicht)
phase einrichten
ZS_MIXXX=mixxx; [ -x /opt/mixxx-2.6/bin/mixxx ] && [ ! -f "$DATEN/.mixxx26-aus" ] && ZS_MIXXX=/opt/mixxx-2.6/bin/mixxx
export ZS_MIXXX
/usr/bin/python3 "$HIER/dj-einrichten.py"
phase mixxx

# Mixxx 2.6 (mit Stems), wenn eingebaut – sonst die normale Version
MIXXX=mixxx
[ -x /opt/mixxx-2.6/bin/mixxx ] && [ ! -f "$DATEN/.mixxx26-aus" ] && MIXXX=/opt/mixxx-2.6/bin/mixxx
export ZS_MIXXX="$MIXXX"

# Mixxx: Einstellungen und Bibliothek liegen in $DATEN/.mixxx (wird beim Zynthian-Backup mitgesichert)
for VERSUCH in 1 2; do
  START=$(date +%s)
  echo "DJ-Pult: starte Mixxx (Versuch $VERSUCH)"
  "$MIXXX" --fullScreen
  RC=$?
  echo "DJ-Pult: Mixxx beendet ($RC)"
  # Sofort wieder zu (unter 20 s, ohne dass jemand beendet hat)? Dann lag es meist an der eigenen Ansicht:
  # einmal mit der Standard-Ansicht LateNight neu starten.
  if [ $(( $(date +%s) - START )) -lt 20 ] && [ ! -f /run/zynsimple-dj.ziel ] && [ ! -f "$DATEN/.skin-kaputt" ] \
     && grep -q "ZynSimple-Glut" "$DATEN/.mixxx/mixxx.cfg" 2>/dev/null; then
    echo "DJ-Pult: eigene Ansicht ging nicht – nehme LateNight"
    touch "$DATEN/.skin-kaputt"
    /usr/bin/python3 "$HIER/dj-einrichten.py"
    continue
  fi
  break
done
