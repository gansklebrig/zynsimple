#!/bin/bash
# ZynSimple: Lade-Animation beim Hochfahren (Plymouth) – Gans statt Zynthian-Logo, oder zurück zum Original.
#   plymouth-gans.sh an   → Bilder erzeugen, ins Theme legen, Startdateien (initramfs) neu bauen
#   plymouth-gans.sh aus  → Original zurück, Startdateien neu bauen
# Sicherheit: vorher Platz prüfen, die bisherigen Startdateien sichern, danach prüfen – sonst zurück.
set -u
MODUS="${1:-an}"
HIER="$(cd "$(dirname "$0")" && pwd)"
GANS="$HIER/img/gans_380.png"
THEMES=/usr/share/plymouth/themes
LOG=/tmp/zynsimple-plymouth.log
exec >"$LOG" 2>&1
echo "Start: $(date) · $MODUS"
command -v update-initramfs >/dev/null || { echo "kein update-initramfs"; exit 1; }
[ -d "$THEMES/zynloganim" ] || { echo "Zynthian-Theme fehlt"; exit 1; }

frames() {   # $1 = Zielordner, $2 = 0 oder 180 (gedreht)
  local ziel="$1" dreh="$2" tmp
  tmp=$(mktemp -d)
  convert "$GANS" -resize x210 "$tmp/g.png" || return 1
  for i in $(seq 0 41); do
    local a=$(( i * 360 / 42 ))
    local b=$(( a + 75 ))
    convert -size 300x300 xc:none \
      -fill none -stroke "#5a4524" -strokewidth 3 -draw "circle 150,150 150,12" \
      -stroke "#e8b04a" -strokewidth 5 -draw "arc 12,12 288,288 $a,$b" \
      -stroke "#ffd98a" -strokewidth 2 -draw "arc 12,12 288,288 $((a + 30)),$((b - 20))" \
      "$tmp/g.png" -gravity center -compose over -composite \
      -rotate "$dreh" "$ziel/frame-$i.png" || return 1
  done
  rm -rf "$tmp"
}

for T in zynloganim zynloganim-inverted; do
  [ -d "$THEMES/$T" ] || continue
  if [ "$MODUS" = "an" ]; then
    [ -d "$THEMES/$T.zynthian" ] || cp -a "$THEMES/$T" "$THEMES/$T.zynthian"
    D=0; [ "$T" = "zynloganim-inverted" ] && D=180
    frames "$THEMES/$T" "$D" || { echo "Bilder ließen sich nicht erzeugen"; exit 1; }
  elif [ -d "$THEMES/$T.zynthian" ]; then
    rm -rf "$THEMES/$T" && mv "$THEMES/$T.zynthian" "$THEMES/$T"
  fi
done

# Startdateien sichern, Platz prüfen, neu bauen, prüfen
BOOT=/boot/firmware; [ -d "$BOOT" ] || BOOT=/boot
BRAUCHT=0
for F in "$BOOT"/initramfs*; do [ -f "$F" ] && BRAUCHT=$(( BRAUCHT + $(stat -c %s "$F") * 2 )); done
FREI=$(( $(df -Pk "$BOOT" | awk 'NR==2{print $4}') * 1024 ))
if [ "$FREI" -lt "$BRAUCHT" ]; then echo "Zu wenig Platz auf $BOOT – Startdateien bleiben, wie sie sind"; exit 1; fi
for F in "$BOOT"/initramfs*; do [ -f "$F" ] && [ "${F%.vor-gans}" = "$F" ] && cp -a "$F" "$F.vor-gans"; done
if ! nice -n 19 update-initramfs -u; then
  echo "Neu bauen ging nicht – alte Startdateien zurück"
  for F in "$BOOT"/initramfs*.vor-gans; do mv -f "$F" "${F%.vor-gans}"; done
  exit 1
fi
for F in "$BOOT"/initramfs*.vor-gans; do
  N="${F%.vor-gans}"
  if [ ! -s "$N" ] || [ "$(stat -c %s "$N")" -lt 1000000 ]; then
    echo "Neue Startdatei $N sieht kaputt aus – alte zurück"; mv -f "$F" "$N"
  else
    rm -f "$F"
  fi
done
sync
echo "Fertig: $(date)"
