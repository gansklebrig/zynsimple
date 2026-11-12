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
while true; do
  thr=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
  temp=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)
  last=$(cut -d' ' -f1-3 /proc/loadavg)
  frei=$(awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo)
  swap=$(awk '/SwapTotal/{t=$2} /SwapFree/{f=$2} END{printf "%d", (t-f)/1024}' /proc/meminfo)
  top=$(ps -eo pcpu,rss,comm --sort=-pcpu --no-headers 2>/dev/null | head -3 | awk '{printf "%s %s%% %dMB | ", $3, $1, $2/1024}')
  dienste=$(for d in zynthian zynsimple-dj imres-buehne imres-hintergrund zynsimple-stems; do
      systemctl is-active --quiet "$d" 2>/dev/null && printf "%s " "$d"; done)
  echo "$(date '+%F %T') strom=$thr temp=$temp last=$last frei=${frei}MB swap=${swap}MB aktiv=[${dienste% }] top: ${top% | }" >> "$LOG"
  if [ "$(wc -l < "$LOG")" -gt 6000 ]; then tail -n 4000 "$LOG" > "$LOG.k" && mv "$LOG.k" "$LOG"; fi
  sleep 10
done
