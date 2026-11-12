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

## Neu in Version 5.6 – DDJ-200 auch bei „DJ + Instrumente“, Diagnose lädt sich selbst hoch

- **DDJ-200 bei „DJ + Instrumente“ geht jetzt wirklich.** Bisher kam kein einziger Tastendruck bei Mixxx an:
  Der Zynthian (JACK) belegt alle USB-MIDI-Geräte für sich. Jetzt hört ZynSimple den DDJ mit und reicht alles über
  einen eigenen virtuellen Anschluss an Mixxx weiter – auch die LEDs zurück.
  **Einmal den Zynthian neu starten** (damit es genug virtuelle Anschlüsse gibt), dann den DDJ einstecken und
  „DJ + Instrumente“ starten. Reines DJ-Pult: dort klappt der DDJ auch, wenn er erst nach dem Einrichten steckt.
- **Diagnose automatisch hochladen:** Handy → Extras → „🩺 Diagnose automatisch hochladen“ einrichten
  (privates GitHub-Repository + Token, Anleitung steht dort). Danach landen Absturz-Berichte, Protokolle vor
  einem Einfrieren und **ungeplante Wechsel** (DJ-Pult plötzlich weg) innerhalb einer Minute dort – Claude liest sie direkt.
- Die Wache erkennt jetzt selbst, wenn das DJ-Pult ungeplant endet, und schreibt einen Bericht
  (`wechsel-….txt` in „MUSIK gekauft/_Diagnose“).

## Neu in Version 5.5 – DJ-Controller bei „DJ + Instrumente“, PLAY spielt Deck A

- **DDJ-200 bei „DJ + Instrumente“ voll nutzbar.** Mischen ging schon immer (Play, Cue, EQ, Crossfader,
  Jog, Pads). Jetzt auch **Titel wählen und laden – ohne Zynthian-Tasten:**
  - **SHIFT halten + Jog drehen** → öffnet „♫ Decks & Titel“ am Zynthian und wählt den Titel (Zeile leuchtet gold)
  - **SHIFT + Kopfhörer-Taste** links = in **Deck A** laden, rechts = in **Deck B**
  - Weiter zurück: BACK oder ✕. Die Deck-Karten oben zeigen Titel, Tempo und Restzeit.
- **Reines DJ-Pult: PLAY (die ▶-Taste über SEL) startet/stoppt jetzt Deck A**, ALT + PLAY Deck B.
  Auto-DJ liegt jetzt auf **ALT + PAD**. Die PLAY-LED leuchtet, solange ein Deck läuft.
- **Mixxx-Absturz:** Statt zurück zum Zynthian-Startbild zu fallen, startet Mixxx von selbst neu
  (im reinen DJ-Pult und bei „DJ + Instrumente“). Ein Protokoll liegt dann in „MUSIK gekauft/_Diagnose“
  (`mixxx-absturz-….txt`) – bitte schicken, dann lässt sich die Ursache finden.
- „Decks & Titel“: Die Auswahl bleibt sichtbar, auch wenn ein Deck spielt (vorher sprang der Rahmen jede Sekunde weg).

## Neu in Version 5.4 – Drehen wechselt nie die Ansicht

- **Drehregler und Tasten wechseln nie mehr die Ansicht.** Ist Mixxx vorne, wirken sie weiter auf den Mischer
  (Regler, Effekte, Freeze …), aber das Bild bleibt, wie es ist.
- **Zurück aus Mixxx: nur die Taste MENU** (öffnet ⋯ im Mischer).
- **Profi-Mischer**: Wer ihn über ⋯ öffnet, bleibt dort. ZynSimple springt nicht mehr von selbst zurück –
  zurück zu ZynSimple geht über das Zynthian-Menü („Einfacher Mischer“) oder BACK 3 s → System-Menü.

## Neu in Version 5.3 – Startbild schöner, Gans auch als Lade-Animation

- Startbild neu gestaltet: alles untereinander – Gans im goldenen Ring, darunter „zynthian“, darunter
  „ZynSimple · Barden Beats · DJ-Pult“. Nichts schneidet mehr in den Ring.
- **Gans auch als Lade-Animation** (Einstellungen → Anzeige, aus ab Werk): ersetzt das drehende Zynthian-Logo
  ganz am Anfang durch die Gans mit umlaufendem Goldring.
  - Dafür werden einmal die Startdateien des Systems (initramfs) neu gebaut – dauert etwa eine Minute im
    Hintergrund. **In dieser Minute nicht ausschalten.**
  - Sicherheitsnetz: vorher wird geprüft, ob genug Platz ist, die bisherigen Startdateien werden gesichert und
    nach dem Bauen geprüft; geht etwas schief, kommen automatisch die alten zurück. Protokoll: /tmp/zynsimple-plymouth.log
  - Wieder ausschalten stellt das Zynthian-Logo zurück (baut die Startdateien ebenfalls neu).
  - Nach einem Zynthian-Update kann das Logo zurückkommen – ZynSimple setzt die Gans dann beim nächsten Start wieder.

## Neu in Version 5.2 – Die Gans beim Hochfahren

- Beim Start zeigt der Zynthian jetzt die Gans (goldener Ring, warmer Hintergrund) statt des Vangelis-Bildes;
  bei Fehlermeldungen dieselbe Gans mit rotem Ring. Wirkt ab dem nächsten Neustart.
- Abschalten: Einstellungen → Anzeige → **Gans beim Start** (das Original-Bild kommt zurück).
- Erzeugt der Zynthian sein Bild nach einem Update neu, setzt ZynSimple die Gans beim nächsten Start wieder drauf.
- Die kurze Logo-Animation ganz am Anfang (vor dem Bild) gehört zum System und bleibt.

## Neu in Version 5.1 – Wache gegen Hänger

- **Wache**: schreibt alle 10 Sekunden mit, wie es dem Zynthian geht (Strom, Temperatur, Last, freier Speicher,
  welche Programme am meisten rechnen) und was der Kernel Auffälliges meldet (Tasten-Chip/I2C, Unterspannung,
  Speicher voll, hängende Prozesse). Friert das Gerät ein, steht nach dem Neustart drin, was davor los war.
- Abholen: am Handy unter Extras → Bühne → **⇩ Protokoll laden**, oder am PC per WLAN im Ordner
  „MUSIK gekauft/_Diagnose“ (die letzten 10 Starts).
- **Stems** rechnen jetzt nur noch, wenn weder DJ-Pult, DJ + Instrumente noch die Barden-Beats-Bühne laufen –
  damit sie beim Spielen keine Rechenzeit und keinen Speicher wegnehmen.

## Neu in Version 5.0 – Decks sichtbar, keine Hänger mehr

- **♫ Decks & Titel** (Kanal „DJ-Pult“, MIXER oder ALT + PLAY): oben stehen jetzt **Deck A und Deck B** –
  welcher Titel, läuft er (▶) oder steht er (❚❚), Tempo, Restzeit und Fortschritt. **Deck antippen = Start/Stopp.**
  Auch Titel, die am DDJ-200 geladen wurden, werden erkannt (über Länge und Tempo aus der Bibliothek).
- **Hänger behoben:** Das Suchen und Einhängen von USB-Sticks lief bisher alle paar Sekunden im Vordergrund und
  konnte die Oberfläche bis zu 20 s blockieren. Jetzt läuft es im Hintergrund. Auch das Umschalten zwischen
  Mixxx und Mischer blockiert die Tasten nicht mehr.
- **Titel laden:** „Keine Verbindung“ – der Weg zu Mixxx wird jetzt neu aufgebaut, wenn er weg ist, und es wird
  jeder freie virtuelle MIDI-Anschluss probiert. Mixxx wird zum Laden ohne „Fenster aktivieren“ nach vorne geholt
  (ohne Fenstermanager blieb das hängen).
- **Auswahlrahmen:** Beim Blättern mit Drehregler/Pfeilen blieben alte Rahmen stehen (alle A/B-Knöpfe sahen
  ausgewählt aus) – behoben, auch im Stick-Browser und bei „Tasten belegen“.

## Neu in Version 4.9 – Tasten wechseln nie mehr von selbst die Ansicht

- **Ansicht wechseln geht nur noch über ⋯** (oder die Taste **MENU**, die ⋯ öffnet): DJ-Pult, DJ + Instrumente,
  Mixxx zeigen, Barden Beats, Profi-Mischer, Zynthian-Menü, Einstellungen.
- **Drehregler drücken + drehen** löst beim Loslassen nichts mehr aus. Langes Drücken eines Drehreglers öffnet
  nicht mehr das XY-Feld oder den Profi-Mischer.
- **Drehregler kurz drücken**: in Listen = antippen (wie SEL), im Mischer = zeigt, was der Regler gerade steuert.
- **SEL lang** öffnet nicht mehr den Profi-Mischer.
- **MIXER, CTRL, ZS3, PAD** springen nicht mehr in Zynthian-Seiten. Bei DJ + Instrumente ist **MIXER = ♫ Titel laden**.

## Neu in Version 4.8 – Ton bei DJ + Instrumente

- Mixxx meldete im Modus DJ + Instrumente „ohne Tonausgabegeräte konfiguriert“: ZynSimple hatte den
  JACK-Gerätenamen selbst eingetragen, und der passte nicht. Jetzt wählt Mixxx JACK und das Gerät selbst;
  wohin der Ton geht (Kanal „DJ-Pult“), legt weiterhin ZynSimple fest.
- Kann Mixxx auf dem System gar nicht über JACK spielen, sagt ZynSimple das jetzt klar, statt Mixxx starten zu lassen.
- Reste der Hybrid-Einstellung werden vor dem reinen DJ-Pult entfernt.

## Neu in Version 4.7 – Tasten-Grundregeln, die überall gelten

**Überall gleich:**
- **BACK kurz** = eine Ebene zurück – in jeder Seite (Titel laden, Stick, Tasten belegen, Keytar, Einstellungen …).
  Etwas länger gedrückt wirft dich nicht mehr aus ZynSimple heraus.
- **BACK 3 s halten** = System-Menü (Update, Neustart, Ausschalten, DJ-Pult, Barden Beats) – in ZynSimple,
  im DJ-Pult und in Barden Beats. (In den Original-Zynthian-Seiten bleiben es 2 s.)
- **Drehregler oder Pfeile** = Auswahl bewegen; am Ende einer Liste blättert es von selbst auf die nächste Seite.
- **SEL** = das Ausgewählte antippen.
- Ist Mixxx vorne, holt nur MENU den Mischer zurück.

**DJ + Instrumente – so spielt man damit:**
1. **ALT + PLAY** (oder der goldene Knopf „♫ Titel laden“ im Kanal DJ-Pult) öffnet die Musik.
2. Mit dem Drehregler einen Titel wählen, **F1 = in Deck A**, **F2 = in Deck B**. **F3 / F4** wechseln zwischen
   „Neu dazu“, „★ Favoriten“ und „A – Z“. **BACK** = zurück zum Mischer.
3. Abspielen, überblenden, EQ, Hot Cues: am **DDJ-200**. Lautstärke, Effekte, Freeze, Szenen der Musik und der
   Instrumente: am **Zynthian** (die Musik ist der Kanal „DJ-Pult“ – wie jede andere Spur).
4. Suchen per Text: am Handy (…:8090/bibliothek).

**Ausschalten:** STOP gedrückt halten schaltet im DJ-Pult nicht mehr aus (STOP ist nur noch Panik). Zum
Ausschalten am besten **BACK 3 s → Ausschalten** und erst danach den Netzschalter – so ist alles gespeichert.
Wird einfach der Strom gezogen, prüft der Zynthian die Karte beim nächsten Start (das richtet die Version 4.0 ein),
aber Einstellungen der letzten Sekunden können fehlen.

## Neu in Version 4.6 – Titel laden bei DJ + Instrumente

- Im Mischer hat der Kanal **„DJ-Pult“** jetzt oben einen goldenen Knopf **♫ Titel laden** (auch im ⋯-Menü).
- Reiter **Neu dazu** (zuletzt übernommene Musik zuerst), **★ Favoriten** und **A – Z** (mit Buchstaben-Leiste
  nach Künstler). **A** oder **B** antippen = Titel landet in Deck A oder B. Mixxx blitzt dabei kurz auf
  (der Titel wird dort gesucht), danach ist der Mischer wieder vorne.
- Mit Drehregler/Pfeilen bedienbar; ▲ ▼ unten blättern. Suchen per Texteingabe geht am Handy: …:8090/bibliothek.
- Frisch übernommene Musik erscheint, sobald Mixxx sie eingelesen hat (passiert automatisch, sobald kein Deck spielt).

## Neu in Version 4.5 – USB-Stick wird zuverlässiger gefunden

- Sticks und Karten werden jetzt über das Gerät selbst erkannt (nicht nur über den Ordner /media) und, falls
  das System sie nicht von selbst geöffnet hat, von ZynSimple eingehängt – auch NTFS.
- Findet der Zynthian keine Musik, sagt er jetzt **warum** (im Stick-Browser, am Handy unter …:8090/import und
  im DJ-Menü): z. B. „Mac-Format – nicht lesbar“, „erkannt, ließ sich nicht öffnen“ oder „0 Musikdateien“.
- **Format**: am besten **exFAT** (auch für große Dateien und Sticks über 32 GB) oder **FAT32**; NTFS geht auch.
  Mac-Formate (APFS, Mac OS Extended) kann der Zynthian nicht lesen.

## Neu in Version 4.4 – Tasten selbst belegen

- **Einstellungen → Bedienung → ⌨ Tasten belegen** listet jede Funktion (kurz, mit ALT, gehalten) und auf
  welcher Taste sie liegt – mit Reitern für **Mischer**, **DJ-Pult** und **Barden Beats**.
- Zeile antippen → die neue Taste wählen (so angeordnet wie am Gerät). Die zwei Tasten **tauschen** ihre
  Aufgabe, so bleibt jede Funktion genau einmal erreichbar. ALT- und Halten-Belegung und die LEDs wandern mit.
- **↺ Standard** stellt den gewählten Bereich wie ab Werk. **BACK** bleibt immer BACK (Rückweg und System-Menü).
- Auch direkt im DJ-Pult (☰ → ? So geht's → ⌨ Tasten belegen) und in Barden Beats
  (MENU → ❔ Tastenbelegung → ⌨ Tasten tauschen). Alle drei lesen dieselbe Einstellung.
- Im Mischer lassen sich F1–F4, die Pfeile, REC, PLAY, STOP und METRONOM tauschen; MENU, MIXER, CTRL, ZS3, ALT,
  PAD und SEL gehören dort der Zynthian-Oberfläche selbst.

## Neu in Version 4.3 – BeatStep Pro, Keytar und Ton-Anzeige

Alles unter **Einstellungen → Geräte** (oder ⋯ → Neue Spur).

**🎛 BeatStep Pro** – „Spuren anlegen“ legt auf einmal an:
- **BSP 1 · Bass** auf MIDI-Kanal 1 (SEQ 1) und **BSP 2 · Melodie** auf Kanal 2 (SEQ 2),
- auf Wunsch **BSP Drums** auf Kanal 10 (Schalter „BeatStep-Drums im Zynthian“ – aus, wenn die TR-8S trommelt).
- Den Klang jeder Spur wählst du wie immer über die Spur. Der BeatStep Pro wird im Zynthian automatisch auf
  „mehrere Kanäle gleichzeitig“ gestellt, damit jede Spur nur ihren Kanal hört.
- Im Takt: am BeatStep Pro die Clock auf USB bzw. MIDI stellen – er folgt dann dem Zynthian bzw. der TR-8S.

**🎸 Keytar** (MIDI-Kabel an den DIN-Eingang)
- „Keytar anlernen“ → **eine Taste auf der Keytar drücken**. Der Zynthian erkennt Buchse und MIDI-Kanal selbst,
  danach wählst du den Klang. Den Kanal musst du nicht kennen; stellst du ihn an der Keytar um, einfach neu anlernen.

**♪ Ton-Anzeige**
- Sobald du spielst, steht oben groß, **welche Töne gerade klingen** (z. B. A3 · C♯4 · E4), nach dem Loslassen
  noch kurz zum Ablesen. Ist eine Tonart eingestellt, sind passende Töne **grün**, nicht passende **rot**.
- Einstellung „Ton-Anzeige“: nur Keytar, alle MIDI-Geräte oder aus.

## Neu in Version 4.2 – Stick durchblättern, Alben und Titel auswählen

- **⇩ Musik übernehmen** zeigt jetzt den **ganzen Inhalt** von USB-Stick oder SD-Karte (im Kartenleser) –
  nicht mehr nur „MUSIK gekauft“. Zu finden: ⋯-Menü (sobald etwas steckt), Einstellungen → Bühne oder
  DJ-Pult, am Handy unter **…:8090/import** (auch im DJ-Modus).
- **Kästchen ☐ antippen** = Album/Ordner oder einzelnen Titel auswählen, **Name/›** = Ordner öffnen.
  Ein gewählter Ordner nimmt alles darin mit; einen Teil darin abwählen geht trotzdem.
- Unten steht, wie viel es ist (Titel, MB, wie viel davon neu). **⇩ Übernehmen** kopiert alles gesammelt,
  mit Fortschritt. Was schon auf dem Zynthian ist, zeigt ein grünes „✓ schon auf dem Zynthian“ und wird
  nicht nochmal kopiert. Liegt etwas in „MUSIK gekauft“ auf dem Stick, landet es ohne diesen Ordnernamen
  in der Bibliothek – sonst mit derselben Ordnerstruktur wie auf dem Stick.
- Im DJ-Modus (Handy): die neuen Titel erscheinen in Mixxx nach ☰ → *USB-Stick neu einlesen*.

## Neu in Version 4.1 – Musik übernehmen in jedem Modus

- **⇩ Musik übernehmen** gibt es jetzt auch auf der Seite **Einstellungen → Bühne** (neben *DJ + Instrumente*)
  und im **⋯-Menü**, sobald ein USB-Stick oder eine SD-Karte (im USB-Kartenleser) mit Ordner
  **„MUSIK gekauft“** steckt. Beim Einstecken erscheint ein Hinweis.
- Im Modus **DJ + Instrumente** liest Mixxx die neuen Titel danach von selbst ein: Mixxx startet kurz neu
  (ca. 20 s), aber erst, wenn gerade kein Deck spielt – ein laufendes Set reißt nicht ab.

## Neu in Version 4.0 – DJ + Instrumente, gemeinsamer Takt, Looper im Takt, Bühne

**♫ DJ + Instrumente (Hybrid-Modus)** – Mixxx läuft *neben* dem Zynthian statt an seiner Stelle.
- Start: am Zynthian **⋯ → ♫ DJ + Instrumente**, **Einstellungen → Bühne**, **BACK 2 s → System-Menü**, im DJ-Menü
  (☰) unter WECHSELN, in Barden Beats im System-Menü oder am Handy (Extras → DJ + Instrumente).
- Die Musik kommt als eigener Kanal **„DJ-Pult“** in den einfachen Mischer: Fader, Mute, Zynthian-Effekte, Freeze,
  Szenen und der Limiter wirken auch auf die Musik. Handpan, Mikro, Synths und Looper laufen wie immer daneben.
- Der DDJ-200 steuert nur Mixxx (er wird aus den Zynthian-Spuren herausgenommen, damit keine Synths mitspielen).
- Bildschirm: **⋯ → ♫ Mixxx zeigen** holt Mixxx nach vorne, **jede Zynthian-Taste oder jeder Regler** bringt den
  Mischer zurück. Titel suchen und laden geht am bequemsten am Handy (siehe unten).
- Kein Kopfhörer-Vorhören in diesem Modus – dafür ist das reine DJ-Pult da (Vorhören über den DDJ-200).
- Beenden: ⋯ → *DJ + Instr. beenden* (die Spuren bleiben, der Kanal „DJ-Pult“ wird still).

**⏱ Gemeinsamer Takt** – *Einstellungen → Bühne → Wer gibt den Takt vor?* (gilt für alle Modi)
- **Zynthian führt**: Der Zynthian schickt MIDI-Clock an die TR-8S (USB) und die DIN-Buchse. Im DJ-Pult gibt
  der laufende Track das Tempo vor, bei *DJ + Instrumente* führt Mixxx und das Zynthian-Tempo folgt automatisch
  (Delays im Takt, Looper, Sequenzer).
- **TR-8S führt**: Der Zynthian läuft als **Slave** – er hört auf die Clock der TR-8S (USB, sonst DIN-Eingang).
  Delays, Looper und Sequenzer folgen ihr; im DJ-Pult und bei *DJ + Instrumente* folgt auch Mixxx: neu geladene
  Titel laufen sofort mit SYNC im Takt der TR-8S.
- **aus**: ZynSimple lässt die Clock-Einstellungen des Zynthian in Ruhe (selbst im Zynthian-Menü einstellen).

**⟳ Looper im Takt** – Spur ⟳ Looper öffnen:
- **LÄNGE frei / 1 / 2 / 4 Takte**: Im Takt startet und endet die Aufnahme auf der Eins und hat genau die
  gewählte Länge (4/4). Das Tempo kommt vom Zynthian – also von TAP, von Mixxx oder von der TR-8S.
- **LOOP 1, 2, …, ＋**: mehrere Loops in einem Looper; die Tasten wirken auf den grün markierten.
- Neue Looper-Spuren starten gleich im Takt mit 2 Takten.

**🎤 Bühne** – *Einstellungen → Bühne*
- **Auftritts-Stand merken / zurückholen**: vor dem Auftritt merken – ist mitten im Set etwas verstellt, holt
  „Zurückholen“ Spuren, Effekte und Szenen genau so zurück. (Auch am Handy.)
- **Nach dem Einschalten**: Mischer, *DJ + Instrumente* oder DJ-Pult – womit der Zynthian startet.
- **Strom**: Bei Unterspannung (schwaches Netzteil, leerer Akku) warnt der Zynthian sofort und sichert alles
  auf die Karte; im DJ-Pult erscheint der Hinweis in der Leiste. Einen Akkustand in % kann der Pi ohne
  Akku-Aufsatz (UPS-HAT) nicht messen.
- **Speicherkarte**: Nach einem Stromausfall wird die Karte beim nächsten Start automatisch geprüft und repariert
  (`fsck.repair=yes`, richtet das Update einmalig ein).

**🔎 Vorbereitung**
- **Musik am Handy suchen**: `http://zynthian.local:8090/bibliothek` (im DJ-Pult direkt `…:8090`). Künstler,
  Titel oder Album tippen, **A** oder **B** antippen – der Titel landet im Deck. Filter **★ Favoriten**.
- **Sterne**: am Zynthian **ALT + ▲ / ▼** gibt dem gerade laufenden Titel einen Stern mehr/weniger.
  Alles ab ★★★★ steht beim nächsten Start in der Mixxx-Kiste **„★ Favoriten“**.
- **Hot Cues**: die acht Pads am DDJ-200 (Modus HOT CUE): leeres Pad = Cue setzen, Pad = hinspringen,
  SHIFT + Pad = löschen. Mixxx merkt sie sich pro Titel – also zu Hause vorbereiten, auf der Bühne nur drücken.

## Neu in Version 3.8 – DJ-Pult: Ebenen, Hinweisleiste, Effekte

**Hinweisleiste unten am Bildschirm:** zeigt immer, was die 4 Zynthian-Regler (drehen / ⏎ drücken) und F1–F4 gerade tun.
Bei jeder Bedienung erscheint kurz darüber, was passiert ist („Filter A: 62 %“, „Loop 8 Schläge auf Deck A“ …).

**Ebenen – MIXER wechselt (ALT + ◀ ▶ auch). Die MIXER-LED zeigt die Ebene:**

| Ebene | R1 | R2 | R3 | R4 | F1–F4 |
| --- | --- | --- | --- | --- | --- |
| MISCHEN (gold) | Titel wählen · ⏎ Deck A | Kopfhörer Vorhören↔Mix · ⏎ Deck B | Filter A · ⏎ Mitte | Filter B · ⏎ Mitte | Stems Drums/Bass/Melodie/Vocals (ALT: Deck B) – sonst Sampler |
| EFFEKTE (grün) | Effekt 1 Stärke · ⏎ an/aus | Effekt 1 wählen · ⏎ Ziel A → B → A+B | Effekt 2 Stärke · ⏎ an/aus | Effekt 2 wählen · ⏎ Ziel | Loop 4 · 8 · 16 · Loop aus |
| HANDPAN (rot) | Handpan-Lautstärke | Handpan-Effekt · ⏎ an/aus | Master | Kopfhörer | Handpan an/aus · Effekt an/aus · nächster Effekt · Durchsage |

**Immer gleich:** SEL lädt den gewählten Titel ins **freie** Deck · ▲▼ Titel · ◀▶ Bereich · PLAY Deck A ▶/❚❚ (ALT: Deck B) · ALT+PAD Auto-DJ · REC Aufnahme ·
PAD Handpan an/aus · TEMPO tippen (ALT + TEMPO: Sync) · CTRL Vorhören A → B → aus · ZS3 große Liste ·
STOP kurz: Panik (alle Effekte und Filter aus), 3 s: ausschalten · ALT halten: fein drehen, Regler 1 springt seitenweise.

**Effekte:** Im DJ-Pult laufen die Effekte von Mixxx (Echo, Hall, Filter, Flanger …) – die Zynthian-Effekte sind in dem Modus
aus, weil der Zynthian-Ton pausiert. Die Namen stehen über der Bibliothek, FX1/FX2 leuchten grün, wenn sie an sind.
Die Handpan hat eine eigene Effekt-Einheit (Effekt 3).

## Neu in Version 3.7 – Menüs mit den Zynthian-Tasten bedienen

Alle Menüs gehen jetzt auch ohne Touchscreen – Einstellungen, Mehr, Spur-Seite, Neue Spur, Auto-Gain/Stimmgerät/Looper,
Hilfe, Update-Anzeige und das DJ-Menü:

| Taste | im Menü |
| --- | --- |
| Drehregler | nächste / vorige Kachel |
| ▲ ▼ ◀ ▶ | Kachel in diese Richtung |
| SEL (oder Regler drücken im DJ-Menü) | auslösen |
| BACK | zurück / schließen |
| MENU kurz (im DJ-Pult) | DJ-Menü auf/zu |

Die gewählte Kachel hat einen hellgoldenen Rahmen. Sobald man den Bildschirm antippt, verschwindet er wieder.

## Neu in Version 3.6 – DJ-Pult: Start-Menü und USB-Stick

- **☰ Menü** oben rechts im DJ-Pult (immer sichtbar) – oder **BACK 2 s halten**. Das Menü zeigt oben, wie viele Titel in der
  Bibliothek sind und was auf dem USB-Stick liegt, und darunter große Kacheln:
  - **Musik:** ▶ Auflegen · ⟳ USB-Stick neu einlesen · ⇩ Musik auf den Zynthian
  - **Wechseln:** Zum Zynthian · Barden Beats · **? So geht's** (alle Tasten und Regler erklärt)
  - **System:** Updates · Neu starten · Ausschalten
- Ist noch keine Musik da, öffnet sich das Menü **von selbst** und sagt, was zu tun ist.
- **USB-Stick:** Hat er keinen Ordner „MUSIK gekauft“, wird jetzt der **ganze Stick** eingelesen.
- **USB-Stick neu einlesen:** nach dem Einstecken antippen – Mixxx startet kurz neu und zeigt die Musik.
- Mixxx auf **Deutsch**, aufgeräumte Seitenleiste (ohne iTunes, Rekordbox, Serato …), größere Schrift, kein Blau mehr im Hintergrund.

## Neu in Version 3.5 – Stems im DJ-Pult

**Was Stems sind:** Ein Track wird in vier Spuren zerlegt – **Drums, Bass, Melodie (alles andere, auch Synths) und Vocals**.
Beim Auflegen lässt sich jede Spur einzeln stumm schalten, z. B. nur Drums und Bass unter die Handpan legen.

**Einmal einrichten** (Einstellungen → DJ-Pult, oder am Handy unter Extras):
1. **Mixxx 2.6 mit Stems → Einbauen.** Mixxx 2.6 gibt es für den Raspberry Pi nicht fertig, darum baut der Zynthian es selbst
   aus dem Quellcode: **1–2 Stunden**, Internet und 6 GB freier Platz nötig. Der Zynthian bleibt bedienbar, kann aber träger sein.
   Fortschritt mit echten Werten: Quellcode-MB, Pakete, „41 % der Dateien übersetzt“. Mixxx 2.6 ist noch eine Beta.
2. **Stems vorbereiten → Einrichten.** Lädt das KI-Werkzeug Demucs (ca. 1 GB).

**Stems erzeugen:** Tracks in Mixxx in die Kiste **„Stems vorbereiten“** ziehen – oder per WLAN in den Ordner
`MUSIK gekauft\Stems erzeugen` legen. Der Zynthian zerlegt sie im Hintergrund, mit niedrigster Priorität, und **pausiert,
solange das DJ-Pult läuft**. Die fertigen Dateien (`.stem.mp4`) landen in `MUSIK gekauft\Stems`. Auf dem Pi dauert ein Track
eine Weile (mehrere Minuten); Status und Restzeit stehen in den Einstellungen. Stems vom PC (z. B. mit Demucs oder NI Stem Creator
erzeugt) einfach in den Ordner `MUSIK gekauft` legen.

**Beim Auflegen** (Track mit Stems auf Deck A geladen):
- **F1–F4** = Drums · Bass · Melodie · Vocals stumm/an. **ALT halten** + F1–F4 = dasselbe für Deck B.
- LEDs: Drums rot, Bass gold, Melodie grün, Vocals gelb – glimmt nur = stumm.
- In der Ansicht erscheinen unter jedem Deck vier farbige Stem-Knöpfe (antippbar).
- Ohne Stem-Track spielen F1–F4 wie bisher die Sampler.

## Neu in Version 3.4 – Fortschritt, der wirklich etwas zeigt

Updates, die Mixxx-Installation und der Musik-Import zeigen jetzt echte Werte statt eines Timers:
- **Ring mit Prozent** – bewegt sich nur, wenn tatsächlich geladen, ausgepackt oder installiert wird.
- **Schritte mit Haken:** z. B. Prüfen → Herunterladen → Entpacken → Installieren → Neustart; beim aktuellen Schritt steht, was gerade passiert.
- **Daten:** „268 kB von 412 kB · 134 kB/s · noch ca. 2 s“, bei Mixxx die echten MB aus dem Paketmanager und welches Paket gerade ausgepackt/eingerichtet wird, beim Import Dateien und MB.
- **Nach dem Neustart** zeigt ZynSimple kurz „Update auf 3.4 fertig ✓“.
- Am Handy dasselbe: Prozent, Balken, Schritte, Daten.
- Barden Beats: Der Update-Balken zeigt jetzt Prozent, geladene MB, Tempo und die Schritte statt Sekunden.

## Neu in Version 3.3 – System-Menü: BACK 2 Sekunden halten

In **allen** Apps – Zynthian/ZynSimple, DJ-Pult und Barden Beats – öffnet **BACK 2 s halten** dasselbe System-Menü:

| Knopf | Was passiert |
| --- | --- |
| Abbrechen · Ausschalten · Neu starten | wie das bekannte Zynthian-Power-Menü (im DJ-Pult speichert Mixxx vorher) |
| ZynSimple aktualisieren | sucht das Update (GitHub, sonst USB-Stick) |
| Zynthian aktualisieren | das offizielle Zynthian-System-Update |
| Barden Beats aktualisieren | läuft im Hintergrund |
| DJ-Pult · Barden Beats · Einfacher Mischer | direkt wechseln |

Aus dem DJ-Pult oder Barden Beats wechselt ein Update erst zum Zynthian und startet dort von selbst.
Auch das normale Zynthian-Power-Menü zeigt jetzt diese erweiterte Auswahl.

## Neu in Version 3.2 – WLAN-Ordner „MUSIK gekauft“ zuverlässig

- Der Ordner wird direkt nach dem Update eingerichtet (beim ersten Mal wird Samba installiert – Internet nötig, 1–2 Minuten), nicht erst beim ersten DJ-Start.
- **Windows:** Der Zynthian erscheint unter „Netzwerk“. Sonst im Explorer oben in die Adresszeile `\\zynthian\MUSIK gekauft` oder `\\<IP>\MUSIK gekauft` tippen.
- **Anmeldung:** Benutzer `musik`, Passwort `gekauft` (Windows 10/11 lassen ohne Anmeldung nicht hinein).
- **Mac:** Finder → Gehe zu → Mit Server verbinden → `smb://zynthian.local/MUSIK gekauft`.
- Status und „Einrichten“-Knopf: Einstellungen → DJ-Pult → Musik per WLAN (oder am Handy unter Extras).

## Neu in Version 3.1 – Startbildschirm fürs DJ-Pult

Während Mixxx lädt, erscheint die Gans mit goldenen Ringen und darunter ein Ladebalken, der sagt, was gerade passiert
(Ton einrichten, Controller verbinden, Bibliothek lesen, Ansicht aufbauen). Der Balken merkt sich, wie lange der Start
beim letzten Mal gedauert hat, und blendet sich aus, sobald Mixxx bereit ist.

## Neu in Version 3.0 – leichter für alle, DJ-Pult komplett

### Für alle, die ZynSimple zum ersten Mal sehen
- **Leerer Start:** Gibt es noch keine Spur, fragt der Bildschirm „Was schließt du an?“ – Handpan, Mikro/Gesang, Instrument, Synth, Looper oder leerer Eingang. Antippen, fertig.
- **? oben neben LIVE:** legt Erklärungen über alle Bedienelemente; nochmal tippen zeigt, was die Tasten und Regler am Zynthian tun. Beim allerersten Start erscheint das von selbst.
- **Langer Druck erklärt:** M, S, ❄, Gain, ‹ › und Überblenden erklären sich, wenn man sie gedrückt hält. Kurz tippen wirkt wie immer.
- **Warnungen in Klartext** oben im Mischer: zu laut, Aussetzer, zu warm, zu wenig Strom – jeweils mit dem, was hilft.
- **F1–F4** sagen beim Drücken, welchen Effekt sie gerade schalten.

### Leichter bedienen
- **Auto-Gain** (Spur-Name antippen → Auto-Gain): 10 Sekunden so laut spielen wie beim Auftritt – der Gain stellt sich selbst ein.
- **Schutz vor Übersteuern** (Einstellungen → Bedienung): Limiter am Hauptausgang.
- **Auftritt** (statt „Sperre“): nur noch Fader, Mute, Szenen und Panik bedienbar. Lang drücken beendet. Am Zynthian gehen dann nur Panik, Szenen (ALT+F) und Kanalwahl.
- **Tonart der Band** (Einstellungen → Bedienung) und **Stimmgerät** (Spur-Seite): zeigt Ton, Cent und ob der Ton zur Tonart passt.
- **● REC** in der unteren Leiste: nimmt alles auf, was rauskommt. Herunterladen am Handy unter Extras → Aufnahmen.
- **Looper** als neue Spur: Aufnehmen, Darüber, Abspielen, Stumm, Zurück, Löschen (Spur-Name antippen → Looper).
- **Sicherung:** am Handy (Extras → Sicherung) herunterladen/einspielen oder am Zynthian auf/vom USB-Stick (Einstellungen → System).

### DJ-Pult
- **Fertig eingerichtet:** Ton, DDJ-200, Bibliothek, Aufnahmen und Ansicht stellt ZynSimple vor jedem Start selbst ein. Mit USB-Soundkarte: Kopfhörer automatisch auf der USB-Karte.
- **Zynthian als Zusatz-Controller:** Regler 1 Bibliothek blättern (drücken: in Deck A laden) · Regler 2 Bereich wechseln (drücken: in Deck B) · Regler 3/4 Effekt 1/2 (drücken: an/aus) · F1–F4 Sampler · PLAY Deck A ▶/❚❚ (ALT: Deck B) · ALT+PAD Auto-DJ · REC Aufnahme · TEMPO Tempo tippen · PAD Handpan im Mix an/aus · MIXER/CTRL Vorhören Deck A/B · ZS3 große Bibliothek · ▲▼◀▶ SEL in der Bibliothek. Die LEDs zeigen, was läuft.
- **BACK 2 s halten** → System-Menü · **MENU halten** → Barden Beats · **STOP 3 s halten** → speichern und ausschalten.
- **Eigene Ansicht „ZynSimple Glut“** für das 5-Zoll-Display: Wellenformen Bässe rot, Mitten gold, Höhen grün – kein Blau. Startet sie nicht, nimmt Mixxx automatisch LateNight.
- **Handpan/Mikro im Mix:** Zynthian-Eingänge 1+2 laufen in Mixxx mit (Effekt-Einheit 2 = Regler 4).
- **Kiste „Passt zur Handpan (…)“:** alle Tracks in Tonarten, die zur eingestellten Tonart passen.
- **TR-8S im Takt:** MIDI-Clock im Tempo des Tracks, der gerade vorne läuft – per USB an der TR-8S und an MIDI-OUT. An der TR-8S Sync auf extern stellen.
- **Musik per WLAN:** am PC `\\zynthian\MUSIK gekauft` öffnen (oder mit der IP) und Dateien hineinziehen.
- **USB-Stick:** Ordner **MUSIK gekauft** auf dem Stick wird automatisch eingelesen. **Musik vom USB-Stick übernehmen** (Einstellungen → DJ-Pult oder Handy) kopiert ihn auf den Zynthian – danach geht es ohne Stick.
- **Set automatisch aufnehmen** (Einstellungen → DJ-Pult): landet im Ordner DJ-Sets auf dem Stick.

**USB-Stick-Format:** exFAT ist am besten (geht an Windows, Mac und Zynthian, keine Größengrenze). FAT32 geht auch (einzelne Dateien bis 4 GB), NTFS meist ebenfalls.

## Neu in Version 2.7 – Einstellungen neu geordnet

Die Einstellungen (Zynthian-Hauptmenü → *Einstellungen & Update*) sind jetzt so aufgebaut wie das System-Menü von Barden Beats:

- **Update ganz oben**, immer sichtbar: „Nach Updates suchen“ bzw. „Jetzt aktualisieren“, wenn eine neue Version da ist.
- Drei Reiter: **Anzeige** (Startbildschirm, Logo, Bühnenbild, Kanalbreite, Farben) · **Bedienung** (Speichern, XY-Feld, MIDI-Kanal) · **System & Modi** (DJ-Pult, Barden Beats, Handy-Adresse, Zynthian-Admin).
- Jede Zeile erklärt in einem Satz, was sie tut. Antippen schaltet um, „Fertig“ oben rechts schließt.

## Neu in Version 2.6 – DJ-Pult (Mixxx mit dem DDJ-200)

Der Zynthian wird auf Knopfdruck zum DJ-Pult: Mixxx läuft im Vollbild, der Pioneer DDJ-200 steuert alles per USB.
Kein zweites Betriebssystem nötig – Zynthian, Barden Beats und DJ-Pult wechseln sich auf derselben SD-Karte ab.

**Starten:** Zynthian-Hauptmenü → *DJ-Pult* · oder ZynSimple → *Mehr* → *🎧 DJ-Pult* · oder Barden Beats → MENU halten → *System* → *🎧 DJ-Pult* · oder am Handy (Extras bzw. Bühne).

**Beim ersten Start** wird Mixxx einmalig installiert. Dafür braucht der Zynthian Internet, das dauert einige Minuten. Das Display zeigt den Fortschritt.
Tipp: Vorher ein Backup der SD-Karte machen (Raspberry Pi Imager oder Win32DiskImager).

**Zurück:**
- Mixxx beenden → automatisch zurück zum Zynthian
- **BACK** 1,5 s halten → Zynthian · **MENU** 1,5 s halten → Barden Beats (die beiden Tasten leuchten im DJ-Modus)
- am Handy über die Barden-Beats-Fernbedienung (`:8790`), die läuft auch im DJ-Modus weiter

**Einmal einrichten in Mixxx** (Optionen → Einstellungen):
1. *Sound-Hardware:* ALSA, Main = Zynthian-Soundkarte, Kopfhörer = USB-Soundkarte (falls vorhanden). Der Kopfhörerausgang des V5 ist nur eine Kopie des Main-Outs.
2. *Controller:* „Pioneer DDJ-200“ wählen, *Aktiviert* anhaken.
3. *Bibliothek:* USB-Stick mit der Musik hinzufügen (er erscheint unter `/media/root/…`), einmal alles analysieren lassen.
4. Danach Mixxx einmal regulär beenden, damit alles gespeichert ist.

Einstellungen und Bibliothek von Mixxx liegen in `/zynthian/zynthian-my-data/dj` und werden mit dem Zynthian-Backup gesichert.
Bildschirm verkehrt herum? In `/zynthian/zynthian-my-data/dj/einstellungen.sh` z. B. `DJ_DREHEN=normal` eintragen.
Diagnose per SSH: `zynsimple-dj pruefen`

## Neu in Version 2.5 – Einstellungen im Hauptmenü

- Im Zynthian-Hauptmenü gibt es jetzt **„Einstellungen & Update“** (ersetzt „Handpan anlegen“ und „ZynSimple Update“ – die Handpan steckt jetzt in „＋ Neue Spur“).
- Oben: Version, **Update suchen / Jetzt installieren** (GitHub, sonst USB-Stick) und die Adresse fürs Handy.
- Kacheln antippen schaltet weiter: Startbildschirm, Start-Logo, Bühnenbild nach …, Automatisch speichern, Kanalbreite, XY-Feld federt zurück, MIDI-Kanal für neue Synths, Tasten-Farben, Update-Suche beim Start.
- Unten: Design „Glut“ an/aus (zweimal tippen, Oberfläche startet neu), Zynthian-Admin, Jetzt speichern.
- Dieselben Einstellungen am Handy unter „⚙ Extras“.

## Neu in Version 2.4 – Start-Logo

- Beim Hochfahren erscheint gut drei Sekunden lang **TheAlmightyGoose** aus dem Heldensturm, darunter „ZynSimple“ und die Versionsnummer. Antippen oder eine Taste überspringt es. Abschalten: in `zynsimple.json` `"splash": false` setzen.

## Neu in Version 2.3 – Spuren in Sekunden anlegen und löschen

- **＋ Neue Spur**: rechts neben den Kanälen (Touchscreen) bzw. als letzte Kachel im Mischer (Handy). Eingang wählen (für Stereo zwei), dann eine Kachel tippen – **Audio-Eingang** (leer), **Handpan**, **Gesang**, **Instrument** oder **Synth**. Die Spur ist sofort da, mit Fader, Mute und Effekten. Hört schon eine andere Spur auf diesen Eingang, steht das als Hinweis da.
- **Namen einer Spur antippen** öffnet die Spur-Seite: umbenennen, Eingänge an/aus, MIDI-Kanal (Synths), nach links/rechts schieben, verdoppeln, Gain, Effekte hinzufügen/entfernen, Zynthian-Optionen – und **Spur löschen** (zweimal tippen).
- **Versehentlich gelöscht?** 20 Sekunden lang erscheint „↶ Zurückholen“ – die Spur kommt mit allen Effekten an ihre alte Stelle zurück.
- Im Effekt-Regler gibt es jetzt **Entfernen** (zweimal tippen).
- **Auslastung** klein oben: am Touchscreen rechts oben im LIVE-Feld, am Handy in der Kopfzeile. *DSP* ist die Audio-Last – ab ca. 80 % drohen Knackser; dazu CPU und Temperatur. Rot = Aussetzer oder zu heiß. Antippen zeigt Details.
- Behoben: Effekt-Regler und XY-Feld flackern beim Drehen nicht mehr.

## Neu in Version 2.1 – Synths dazuschalten & große Effekt-Ansicht

- **＋ Synth dazuschalten:** am Gerät **⋯ → „＋ Synth dazuschalten“** oder in der Effekt-Ansicht,
  am Handy **„＋ Synth“** oben. Kacheln: Fläche (Pad-Synth, Surge XT …), Analog (OB-Xd, Odin 2 …),
  Bass, FM & Glocken, Tasten – dahinter alle Synths des Zynthian. Der Synth bekommt einen
  **eigenen Kanal mit Fader, Mute, Effekten** und spielt über den **MIDI-Eingang mit**
  (Handy: MIDI-Kanal wählbar; Gerät: `"synth_midi_chan": 0` in `zynsimple.json` = Kanal 1).
- **Große Effekt-Ansicht:** am Gerät unten **„Effekte“**, am Handy Reiter **„✦ Effekte“**.
  Pro Kanal eine Zeile: links eine große **MUTE**-Taste, daneben jeder Effekt als große Kachel
  (tippen = an/aus, lang = Regler) und **＋ Effekt**. Mehrere Effekte pro Kanal gleichzeitig.
- **Alle Synths stumm:** eine Taste schaltet alle dazugeschalteten Synths auf einmal stumm –
  und wieder laut.
- **Größere Effekt-Tasten** im Mischer.
- **Update mit Animation:** Beim Update zeigt das Gerät eine große goldene Animation
  (Suchen → Laden → Installieren), am Handy mit den Schritten Laden · Installieren ·
  Neustart · Fertig – danach lädt die Seite von selbst mit der neuen Version.

## Version 2.0 – Live-Modus (so bedienst du ZynSimple jetzt)

### Der Bildschirm am Gerät
- **Links die Kanäle:** Name antippen = Gain & Eingangspegel · Fader ziehen ·
  Effekt **kurz** = an/aus, **lang** = seine Regler · **＋ Effekt** = durchprobieren ·
  M / S / ❄ unten.
- **Rechts die LIVE-Leiste** für den gewählten Kanal (goldener Rahmen) – sie zeigt, was die
  **vier Drehknöpfe** gerade tun:
  1. **Tiefe** – ein Regler für alles: von trocken bis weit & schwebend (Hall + Echos zusammen)
  2.–3. deine **★ Lieblingsregler** (im Effekt-Fenster den Stern antippen) – sonst Hall und Echos
  4. Lautstärke
  Darunter: **❄ Freeze** (tippen = an/aus, halten = nur solange gedrückt), **↯ Echo**
  (halten = Echo-Wurf), **XY-Feld**, **Panik**.
- **Unten:** Seiten ◀ ▶ · **Szenen 1–4** (tippen = laden, lang drücken = speichern) ·
  **↝** Überblenden (hart / 2 / 4 / 8 / 16 Schläge) · **TAP** (Tempo tippen) · **Sperre** · **⋯**
  (Zynthian-Menü, Profi-Mischer, Imres, Handpan, Bühnenbild, Update).

### Die Pads
| Pad | im Live-Mischer |
|---|---|
| **F1–F4** | Effekt 1–4 des gewählten Kanals an/aus · lang = seine Regler · Licht = Effektfarbe |
| **ALT + F1–F4** | Szenen 1–4 (bzw. 5–8 auf dem Bildschirm): tippen = laden, lang = speichern |
| **REC** | ❄ Freeze (tippen = an/aus, halten = solange gedrückt) |
| **PLAY** | ↯ Echo-Wurf, solange gedrückt |
| **STOP** | Panik: Freeze und Echo-Würfe aus, Echos gezähmt |
| **METRONOM** | Tap-Tempo |
| **◀ ▶** | Kanal wählen · **▲ ▼** Tiefe |
Alle anderen Pads (MENU, MIX, ALT …) machen weiter das Gewohnte.

### Tap-Tempo
**TAP** im Takt tippen (am Gerät auch die Metronom-Taste) – ab dem 2. Tippen läuft das Tempo,
weiteres Tippen verfeinert es. Delays im Kanal schalten dabei automatisch auf „im Takt“.
Hinweis: Schickt die TR-8S ihre Clock an den Zynthian, bestimmt sie das Tempo.

### Szenen
Ein Klangbild speichern (Pegel, Mute, Effekte an/aus, alle Effekt-Regler, Tiefe) und später
mit einem Tipp zurückholen – **weich überblendet** über die eingestellte Zahl Schläge.

### Sperre
Einmal tippen sperrt die Bedienung (gegen versehentliches Verrutschen). Entsperren: **lang drücken**.

### Bühnenbild
Nach **45 Sekunden** ohne Eingabe erscheint eine Animation, die zeigt, was gerade klingt:
Ringe = Hall · Lichtpulse im Takt = Delay · schwingende Linien = Modulation ·
Funken = Textur · Eiskristalle = Freeze · die Glut atmet mit der Lautstärke. Die Pads glimmen mit.
Antippen oder Knopf drehen holt den Mischer zurück (ohne etwas auszulösen).
Zeit ändern: `"idle_seconds": 45` in `zynsimple.json` (0 = nie).

### Am Handy
Oben die Live-Leiste: **Szenen 1–8**, Überblenden, **TAP**, **Panik**. In jedem Kanal:
**TIEFE**-Regler und **XY**, **↯ Echo** (halten) und **❄ Freeze**. Im Effekt-Fenster: **★** legt
einen Regler auf die Live-Knöpfe am Gerät.

## Neu in Version 1.7 – Alles bleibt nach dem Neustart erhalten

- **Sofort gespeichert:** Jede Änderung im einfachen Mischer (Gain, Lautstärke, Mute,
  Effekte, Effekt-Regler, Eingangspegel …) wird **2 Sekunden** nach der letzten Bewegung
  gespeichert – auch beim Schließen eines Regler- oder Effekt-Fensters.
- **Beim Herunterfahren** (Ausschalten über das Menü, Neustart, Update) wird vorher noch
  einmal alles gespeichert.
- **Eingangspegel der Soundkarte** merkt sich ZynSimple extra und stellt sie nach dem
  Start wieder ein – der Zynthian selbst tut das sonst nicht.
- Änderungen in den normalen Zynthian-Menüs werden alle 20 Sekunden mitgespeichert.
- Tipp: Strom einfach ziehen geht – nur Änderungen der letzten 2 Sekunden wären weg.

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
