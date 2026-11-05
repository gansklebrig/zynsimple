# ZynSimple – einfacher Mischer für den Zynthian

ZynSimple legt über den Zynthian eine aufgeräumte Mischer-Ansicht:

- **auf dem Zynthian-Touchscreen** als neuer Startbildschirm
- **auf Handy oder Tablet** im Browser (gleiches WLAN)

Pro Instrument (jede Kette im Zynthian) siehst du:

| Element | Funktion |
|---|---|
| Name | Name der Kette, z. B. „Audio In 1+2“ |
| ‹ Preset › | Sound weiterschalten (nur bei Synth-Ketten im Zynthian) |
| Pegelanzeige | Grün = gut, Gelb = laut, Rot = zu laut |
| Fader | Lautstärke, oben = 0 dB (Web: Doppeltippen springt auf 0 dB) |
| Effekt-Tasten | Hall, Delay usw. an/aus (grün = an) |
| M / S | Stumm / Solo |

Ganz rechts steht immer **Summe** (Hauptausgang).

Der Zynthian-Code wird **nicht verändert**. Updates überschreiben also nichts,
und mit dem Deinstallieren ist alles wieder wie vorher.

---

## Installation (einmalig, ca. 2 Minuten)

Du brauchst einen Rechner im selben Netz wie der Zynthian.

1. **Dateien auf den Zynthian kopieren** (am Rechner, im Ordner mit der ZIP-Datei):

   ```
   scp zynsimple.zip root@zynthian.local:/root/
   ```
   Passwort: `opensynth` (falls du es nicht geändert hast)

2. **Per SSH anmelden und installieren:**

   ```
   ssh root@zynthian.local
   cd /root && unzip -o zynsimple.zip && bash zynsimple/install.sh
   ```

3. Die Zynthian-Oberfläche startet neu. Danach siehst du den einfachen Mischer.
   Am Ende zeigt das Skript die Adresse für Handy/Tablet an, z. B.
   **http://zynthian.local:8090**

> Tipp: Auf dem Handy die Seite „Zum Startbildschirm hinzufügen“ – dann
> öffnet sie sich wie eine App im Vollbild.

---

## Bedienung am Zynthian

**Touch:** Fader ziehen, Tasten tippen. Unten:
- **◀ ▶** blättern, wenn mehr Kanäle da sind als aufs Display passen
- **Menü** öffnet das normale Zynthian-Hauptmenü (Ketten anlegen, Snapshots …)
- **Profi-Mischer** öffnet den originalen Zynthian-Mischer

**Drehknöpfe** (der ausgewählte Kanal hat einen orangen Rahmen):

| Knopf | Funktion |
|---|---|
| SELECT (rechts unten) | Lautstärke des ausgewählten Kanals |
| SNAPSHOT | Kanal auswählen |
| BACK | Preset weiterschalten |
| LAYER | Lautstärke der Summe |

**SELECT drücken:** kurz = Mute, mittel = Solo, lang = Profi-Mischer.

Zurück zum einfachen Mischer: BACK drücken. Lang auf BACK drücken bringt dich
wie gewohnt von überall „nach Hause“ – und zu Hause ist jetzt der einfache Mischer.

---

## Neu in Version 1.6 – Effekte durchprobieren & neues Design

**＋ Effekt – viele Effekte durchschalten**
- Handy: in jedem Kanal **„＋ Effekt“** tippen. Gerät: **„＋ Effekt“** im Kanal (wenn Platz ist)
  oder Kanalnamen antippen → **„＋ Effekte“**.
- Es erscheinen Kacheln nach Gruppen: Hall, Echo, Textur, Bewegung, Farbe, Dynamik
  (am Gerät 9 pro Seite, blättern mit ◀ ▶ oder Drehknopf). Dahinter: **alle** Effekte des Zynthian.
- **Antippen setzt den Effekt sofort in den Kanal** und öffnet direkt seine Regler.
- Wählst du danach einen anderen, **ersetzt** er den letzten Versuch – so schaltest du
  schnell durch, ohne dass sich Effekte stapeln. **✓ Behalten** macht ihn fest; der
  nächste kommt dann dazu. **🗑 Entfernen** (Handy) nimmt ihn wieder raus.

**🎨 Design der ganzen Zynthian-Oberfläche**
- Handy → ⚙ Extras → „Design der Zynthian-Oberfläche“ → **Design übernehmen**.
  Färbt alle Zynthian-Menüs warm im Stil des einfachen Mischers – ohne Blau.
  Optional andere Schrift. **Altes Design zurück** stellt alles wieder her.

## Neu in Version 1.5 – Gain & Eingangspegel (gegen Übersteuern)

- **CLIP-Warnung:** Übersteuert ein Kanal, leuchtet am Handy ein rotes **CLIP**, am Gerät wird
  der Kanalname rot (2,5 Sekunden lang).
- **Gain pro Kanal** (−40 … +40 dB): Handy: **− / +** unter dem Namen, auf den Wert tippen = 0 dB.
  Gerät: **− / +** in der zweiten Zeile (bei Audio-Kanälen) – oder den **Kanalnamen antippen**.
- **Eingangspegel der Soundkarte:** Gerät: Kanalnamen antippen → Knopf 2 und 3.
  Handy: ⚙ Extras → „Eingangspegel der Soundkarte“.

**Was hilft gegen Übersteuern?** Zuerst den **Eingangspegel der Soundkarte** runter – der wirkt,
bevor der Ton digital wird. Leuchtet CLIP trotzdem noch, den **Gain** im Mischer runter.
Steht der Gain schon im Minus und CLIP leuchtet weiter, ist das Mikro-Signal für den Eingang
zu stark (Mikro weiter weg, oder Vorverstärker/Pad am Mikro).

## Neu in Version 1.4 – Updates aus dem Internet

ZynSimple liegt jetzt auf GitHub: **github.com/gansklebrig/zynsimple**.
Hat der Zynthian Internet, holt er neue Versionen selbst:

- **Handy:** ⚙ Extras → **Nach Updates suchen** → **Jetzt installieren**.
  Gibt es eine neue Version, steht oben rechts **„Update 1.x ●“** – antippen genügt.
- **Gerät:** **Menü → „ZynSimple Update“**. Ist eine neue Version da, steht sie unten
  im einfachen Mischer („Update 1.x: Menü“).
- Geprüft wird automatisch kurz nach dem Start und dann alle 6 Stunden. Installiert
  wird **nie von selbst** – erst wenn du tippst (also nie mitten im Auftritt).
- Ohne Internet funktionieren Datei-Upload und USB-Stick wie bisher.

**Neu einrichten auf einem frischen Zynthian** (per SSH, mit Internet):
```
curl -sL https://github.com/gansklebrig/zynsimple/archive/refs/heads/main.tar.gz | tar xz -C /root && bash /root/zynsimple-main/install.sh
```

## Neu in Version 1.3 – Handpan als Effektgerät

- **🪘 Handpan anlegen:** Handy → Reiter **⚙ Extras** (Eingang wählen) oder am Gerät
  **Menü → „Handpan anlegen“** (nimmt Eingang 1, änderbar in `zynsimple.json`:
  `"handpan_inputs": [1, 2]`). Ergebnis: Kanal „Handpan“ mit Low-Cut → Kompressor →
  Delay (im Takt, 1/4 punktiert) → Hall.
- **Effekt-Regler:** Handy: **⚙** neben einem Effekt tippen. Gerät: Effekt-Taste
  **lang drücken** (0,6 s). Die vier Drehknöpfe regeln dann die vier angezeigten Werte,
  SELECT blättert zur nächsten Seite, BACK schließt. Kurz tippen schaltet wie bisher an/aus.
- **♩ Delay im Takt:** im Effekt-Regler eines Delays die Notenlänge wählen (1/4, 1/8 …).
  Das Tempo kommt vom Zynthian – schickt die TR-8S ihre Clock, folgt das Delay ihr.
  Wer die Delay-Zeit von Hand verstellt, schaltet „im Takt“ ab.
- **❄ Freeze:** Taste neben M/S. Hall wird maximal lang, Delay-Echos stehen fast endlos –
  eine schwebende Fläche, über die du weiterspielst. Nochmal tippen = alles wie vorher.
- **🦶 Fußschalter:** ⚙ Extras → Aktion (Freeze, Effekt an/aus, Stumm), Kanal, Modus
  (umschalten oder nur solange gedrückt) → **Lernen** → einmal auf den MIDI-Fußtaster treten.
- **💾 Automatisch speichern:** Alle 20 Sekunden wird geprüft, ob sich etwas geändert hat,
  und dann gespeichert. Beim Einschalten lädt der Zynthian genau diesen Stand – auch
  wenn einfach der Strom gezogen wurde.
- **⬇ Update:** Handy → oben rechts **Update** oder ⚙ Extras → „Datei wählen“.
  Ohne Handy: ZIP auf einen USB-Stick, Stick in den Zynthian, **Menü → „ZynSimple Update“**.

## Neu in Version 1.2 – Imres eingebaut

Ist Imres auf dem Zynthian installiert, gibt es jetzt drei Wege dorthin – ganz ohne Handy:

- **Touchscreen:** goldene Taste **„♫ Imres“** unten im einfachen Mischer
- **Zynthian-Hauptmenü:** Eintrag **„Imres Bühne“** (neben „Einfacher Mischer“)
- **Zurück:** in Imres MENU lang → System → „Zurück zum Zynthian“ – du landest
  wieder im einfachen Mischer

**Eine Fernbedienung für alles** (Plan B, und zum schnellen Aufbauen am Anfang):
`http://zynthian.local:8090` – oben **Mischer** und **♫ Imres**. Im Imres-Reiter
die komplette Imres-Fernbedienung plus drei Knöpfe: Imres-Bühne (Vollbild),
Zusammen mit Zynthian, Nur Zynthian. Direkt öffnen: `http://zynthian.local:8090/#imres`

Hinweis: Während die Imres-Bühne im Vollbild läuft, pausiert die Zynthian-Oberfläche –
dann zeigt der Mischer-Reiter „Zynthian pausiert“, der Imres-Reiter läuft weiter.

## Neu in Version 1.1

- **Tasten-LEDs ohne Blau:** Die 20 Tasten leuchten jetzt in warmem Bernstein
  statt Blau (Lila, Grün, Goldgelb und Rot für die Zustände). Eigene Farben gehen
  in `zynsimple.json`, z. B. `"led_colors": {"default": [150, 45, 0]}`.
  Ausschalten: `"led_recolor": false`.
- **Hauptmenü-Eintrag:** Im Zynthian-Hauptmenü steht oben links
  **„Einfacher Mischer“** – so kommst du ganz ohne Handy hin.
- **Update-Knopf:** In der Handy-/Browser-Ansicht oben rechts **„Update“** tippen,
  neue `zynsimple.zip` auswählen – fertig. Kein SSH mehr nötig.

## Einstellungen

Datei: `/zynthian/zynthian-my-data/zynsimple/zynsimple.json`

```json
{
  "web_enabled": true,      // Handy/Tablet-Ansicht an/aus
  "web_port": 8090,         // Adresse http://zynthian.local:8090
  "pin": "",                // z. B. "1234" – dann fragt das Handy einmal nach der PIN
  "screen_enabled": true,   // Touchscreen-Ansicht an/aus
  "replace_home": true,     // false = Original-Mischer bleibt Startbildschirm
  "strip_min_width": 130    // kleinere Zahl = mehr Kanäle nebeneinander
}
```
(Die Kommentare mit `//` nicht in die Datei schreiben.)

Nach einer Änderung: `systemctl restart zynthian`

**PIN-Tipp für Auftritte:** Wenn der Zynthian in einem fremden WLAN hängt,
setz eine PIN, sonst kann jeder im Netz deinen Mix verändern.

---

## Wenn etwas nicht klappt

- **Zynthian startet nicht mehr richtig?** Notbremse per SSH:
  ```
  touch /zynthian/zynthian-my-data/zynsimple/zynsimple.disabled
  systemctl restart zynthian
  ```
  Wieder einschalten: `bash /zynthian/zynthian-my-data/zynsimple/install.sh`
- **Nach einem großen Zynthian-Update** ist ZynSimple evtl. weg →
  einfach `bash /zynthian/zynthian-my-data/zynsimple/install.sh` erneut ausführen.
- **Meldungen ansehen:** `journalctl -u zynthian -n 200 | grep -i zynsimple`
- **Effekt-Taste grau?** Der Effekt hat keinen Bypass-Schalter, den ZynSimple
  erkennt. Ein-/Ausschalten geht dann nur im Profi-Mischer.
- **Kein Preset-Schalter bei deinen Synths?** Richtig so: Bei Synths, die per
  Audiokabel reinkommen, gibt es im Zynthian kein Preset. Die Presets
  schaltest du am Synth selbst.

## Deinstallieren

```
bash /zynthian/zynthian-my-data/zynsimple/uninstall.sh          # abschalten
bash /zynthian/zynthian-my-data/zynsimple/uninstall.sh --alles  # komplett löschen
```

---

Funktioniert mit ZynthianOS **Oram** und **Vangelis**.
