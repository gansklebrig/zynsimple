#!/bin/bash
# Echte Fehler (unbekannte Namen, Syntax …) – harmlose Hinweise (ungenutzte Variablen/Importe) zählen nicht.
cd "$(dirname "$0")/.." || exit 1
FEHLER=$(python3 -m pyflakes zynsimple dj spiel tests 2>&1 | grep -v "assigned to but never used\|imported but unused\|f-string is missing placeholders\|redefinition of unused\|unable to detect undefined names" )
for f in dj/*.sh dj/zynsimple-dj spiel/*.sh spiel/bard-hero install.sh uninstall.sh; do
  [ -f "$f" ] && { bash -n "$f" 2>&1 || FEHLER="$FEHLER
$f: Syntaxfehler"; }
done
if [ -n "$FEHLER" ]; then echo "$FEHLER"; exit 1; fi
echo "Code-Prüfung: alles sauber"
