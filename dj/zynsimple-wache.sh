#!/bin/bash
# ZynSimple Wache: schreibt alle 10 s auf, wie es dem Zynthian geht (Strom, Wärme, Last, Speicher,
# wer am meisten Rechenzeit braucht) und was der Kernel Auffälliges meldet (I2C/Tasten, Unterspannung,
# Speicher voll, hängende Prozesse). Friert das Gerät ein, steht nach dem Neustart hier, was davor los war.
# Kopie fürs Weitergeben: Ordner „MUSIK gekauft/_Diagnose“ (per WLAN am PC sichtbar).
DIR=/zynthian/zynthian-my-data/zynsimple
LOG="$DIR/wache.log"
AUSGABE="/zynthian/zynthian-my-data/dj/MUSIK gekauft/_Diagnose"
mkdir -p "$DIR"
# Beim Start: das Protokoll vom letzten Mal sichern (das enthält den Moment vor dem Einfrieren)
if [ -s "$LOG" ]; then
  mkdir -p "$AUSGABE" 2>/dev/null
  cp "$LOG" "$AUSGABE/wache-bis-$(date -r "$LOG" +%Y-%m-%d_%H-%M).txt" 2>/dev/null
  ls -1t "$AUSGABE"/wache-bis-*.txt 2>/dev/null | tail -n +11 | xargs -r rm -f
  mv "$LOG" "$LOG.vorher"
fi
echo "=== Start $(date '+%F %T') · $(uname -r) ===" > "$LOG"
dmesg -w -T 2>/dev/null | grep --line-buffered -iE "i2c|mcp23|gpio|under-?voltage|throttl|oom|out of memory|hung_task|blocked for more|soft lockup|mmc|usb .*disconnect|ext4.*error|fat.*error" \
  | while read -r z; do echo "KERNEL $z" >> "$LOG"; done &
HIER="$(cd "$(dirname "$0")" && pwd)"
KONF=/zynthian/zynthian-my-data/zynsimple/diagnose.json
VORHER=""
N=0
# Unerwarteter Wechsel (DJ-Pult plötzlich weg, ohne dass jemand im Menü gewechselt hat): Bericht schreiben
wechsel_bericht() {
  mkdir -p "$AUSGABE" 2>/dev/null || return
  {
    echo "Unerwarteter Wechsel: $(date '+%F %T') · vorher [$1] → jetzt [$2]"
    echo "--- Wache (letzte 40 Zeilen) ---"; tail -n 40 "$LOG"
    echo "--- Kernel ---"; dmesg -T 2>/dev/null | tail -n 30
    echo "--- DJ-Sitzung ---"; journalctl -u zynsimple-dj -n 120 --no-pager 2>/dev/null
    echo "--- Zynthian ---"; journalctl -u zynthian -n 60 --no-pager 2>/dev/null
    echo "--- mixxx.log (Ende) ---"; tail -n 200 /zynthian/zynthian-my-data/dj/.mixxx/mixxx.log 2>/dev/null
    echo "--- Mixxx bei DJ + Instrumente (Ende) ---"; tail -n 120 /tmp/zynsimple-hybrid-mixxx.log 2>/dev/null
  } > "$AUSGABE/wechsel-$(date +%F_%H%M%S).txt" 2>/dev/null
  ls -1t "$AUSGABE"/wechsel-*.txt 2>/dev/null | tail -n +11 | xargs -r rm -f
}
while true; do
  N=$((N + 1))
  thr=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
  temp=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)
  last=$(cut -d' ' -f1-3 /proc/loadavg)
  frei=$(awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo)
  swap=$(awk '/SwapTotal/{t=$2} /SwapFree/{f=$2} END{printf "%d", (t-f)/1024}' /proc/meminfo)
  top=$(ps -eo pcpu,rss,comm --sort=-pcpu --no-headers 2>/dev/null | head -3 | awk '{printf "%s %s%% %dMB | ", $3, $1, $2/1024}')
  dienste=$(for d in zynthian zynsimple-dj imres-buehne imres-hintergrund zynsimple-stems; do
      systemctl is-active --quiet "$d" 2>/dev/null && printf "%s " "$d"; done)
  # DJ-Pult beendet, ohne dass ein Wechsel bestellt war (/run/zynsimple-dj.ziel schreibt das Menü)?
  case " $VORHER " in *" zynsimple-dj "*)
    case " $dienste " in *" zynsimple-dj "*) ;; *)
      [ -f /run/zynsimple-dj.ziel ] || { echo "$(date '+%F %T') WECHSEL ungeplant: DJ-Pult beendet" >> "$LOG"; wechsel_bericht "$VORHER" "$dienste"; } ;;
    esac ;;
  esac
  VORHER="$dienste"
  # Neue Diagnose-Dateien hochladen (falls eingerichtet) – jede Minute, im Hintergrund
  if [ $((N % 6)) -eq 1 ] && [ -s "$KONF" ] && [ -f "$HIER/diagnose-hochladen.py" ]; then
    nice -n 15 timeout 300 /usr/bin/python3 "$HIER/diagnose-hochladen.py" >> /tmp/zynsimple-diagnose.log 2>&1 &
  fi
  echo "$(date '+%F %T') strom=$thr temp=$temp last=$last frei=${frei}MB swap=${swap}MB aktiv=[${dienste% }] top: ${top% | }" >> "$LOG"
  if [ "$(wc -l < "$LOG")" -gt 6000 ]; then tail -n 4000 "$LOG" > "$LOG.k" && mv "$LOG.k" "$LOG"; fi
  sleep 10
done
