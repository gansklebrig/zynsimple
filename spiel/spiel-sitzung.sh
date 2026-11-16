#!/bin/bash
# Bard Hero: X-Sitzung (startx) anstelle der Zynthian-Oberfläche.
# Richtet Display und Beamer ein (Einstellung „Bild“: automatisch · Zynthian-Display · Beamer · beide) und startet das Spiel.
# Endet das Spiel, endet die Sitzung – der Dienst kehrt dann von selbst zum Zynthian zurück.
HIER="$(cd "$(dirname "$0")" && pwd)"
DATEN="${BH_DATEN:-/zynthian/zynthian-my-data/bardhero}"
[ -f /zynthian/config/zynthian_envars.sh ] && source /zynthian/config/zynthian_envars.sh
# gleiche Dreh-Einstellung wie DJ-Pult / Barden Beats, falls dort angepasst
[ -f /zynthian/zynthian-my-data/imres/einstellungen.sh ] && source /zynthian/zynthian-my-data/imres/einstellungen.sh
[ -f /zynthian/zynthian-my-data/dj/einstellungen.sh ] && source /zynthian/zynthian-my-data/dj/einstellungen.sh
[ -f "$DATEN/einstellungen.sh" ] && source "$DATEN/einstellungen.sh"

xset s off -dpms s noblank 2>/dev/null
command -v xsetroot >/dev/null && xsetroot -solid "#0b0908"

# Drehung des eingebauten Displays – beim V5 ist es kopfüber eingebaut
DREHEN="${BH_DREHEN:-${DJ_DREHEN:-${IMRES_DREHEN:-}}}"
if [ -z "$DREHEN" ]; then
  case "${ZYNTHIAN_KIT_VERSION:-}" in V5*) DREHEN=inverted ;; *) DREHEN=normal ;; esac
fi
AUSGABE=$(/usr/bin/python3 -c "import json;print(json.load(open('$DATEN/einstellungen.json')).get('ausgabe','auto'))" 2>/dev/null || echo auto)

for i in $(seq 1 10); do xrandr >/dev/null 2>&1 && break; sleep 0.5; done
INTERN=$(xrandr 2>/dev/null | awk '/ connected/ && $1 !~ /HDMI/ {print $1; exit}')
HDMI=$(xrandr 2>/dev/null | awk '/ connected/ && $1 ~ /HDMI/ {print $1; exit}')
[ "$AUSGABE" = auto ] && { [ -n "$HDMI" ] && [ -n "$INTERN" ] && AUSGABE=beide || AUSGABE=einer; }
[ -z "$HDMI" ] && AUSGABE=display
[ -z "$INTERN" ] && AUSGABE=hdmi

case "$AUSGABE" in
  display|einer)
    [ -n "$HDMI" ] && xrandr --output "$HDMI" --off 2>/dev/null
    xrandr --output "$INTERN" --auto --rotate "$DREHEN" 2>/dev/null ;;
  hdmi)
    [ -n "$INTERN" ] && xrandr --output "$INTERN" --off 2>/dev/null
    xrandr --output "$HDMI" --mode "${BH_HDMI_MODUS:-1280x720}" --rotate normal 2>/dev/null \
      || xrandr --output "$HDMI" --auto --rotate normal 2>/dev/null ;;
  beide)
    # Beamer in 1280x720, das Display zeigt dasselbe Bild (verkleinert, gedreht)
    MODUS="${BH_HDMI_MODUS:-1280x720}"
    xrandr --output "$HDMI" --mode "$MODUS" --pos 0x0 --rotate normal 2>/dev/null || xrandr --output "$HDMI" --auto --pos 0x0
    GROESSE=$(xrandr 2>/dev/null | awk -v o="$HDMI" '$1==o {for(i=1;i<=NF;i++) if ($i ~ /^[0-9]+x[0-9]+\+/) {split($i,a,"+"); print a[1]; exit}}')
    GROESSE="${GROESSE:-$MODUS}"
    xrandr --output "$INTERN" --auto --rotate "$DREHEN" --pos 0x0 --scale-from "$GROESSE" 2>/dev/null \
      || xrandr --output "$INTERN" --auto --rotate "$DREHEN" --same-as "$HDMI" 2>/dev/null ;;
esac
echo "Bard Hero: Bild $AUSGABE · Display ${INTERN:-–} ($DREHEN) · Beamer ${HDMI:-–}"

# Touch auf das eingebaute Display legen (dreht und skaliert mit)
xinput list --name-only 2>/dev/null | grep -i -E "touch|ft5|goodix|ili|edt" | while read -r GERAET; do
  if [ -n "$INTERN" ] && xinput map-to-output "$GERAET" "$INTERN" 2>/dev/null; then continue; fi
  case "$DREHEN" in
    inverted) M="-1 0 1 0 -1 1 0 0 1" ;; left) M="0 -1 1 1 0 0 0 0 1" ;; right) M="0 1 0 -1 0 1 0 0 1" ;; *) M="1 0 0 0 1 0 0 0 1" ;;
  esac
  xinput set-prop "$GERAET" "Coordinate Transformation Matrix" $M 2>/dev/null
done

export BH_DATEN="$DATEN"
export SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR=1
cd "$HIER" || exit 1
/usr/bin/python3 "$HIER/bardhero.py"
echo "Bard Hero beendet ($?)"
