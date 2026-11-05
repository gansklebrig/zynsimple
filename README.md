# ZynSimple

Einfache Mischer-Ansicht für den **Zynthian** (V5, ZynthianOS Oram & Vangelis) – auf dem Touchscreen und am Handy.

- Großer Mischer mit Pegelanzeige, Mute/Solo, Presets, Effekte an/aus
- Effekt-Regler, Delay im Takt (TR-8S-Clock), Freeze, Fußschalter
- Handpan-Vorlage per Knopfdruck, automatisches Speichern
- Tasten-LEDs ohne Blau, Imres-Bühne direkt erreichbar
- Updates mit einem Tipp – direkt von hier

## Installieren (per SSH auf dem Zynthian, mit Internet)

```
curl -sL https://github.com/gansklebrig/zynsimple/archive/refs/heads/main.tar.gz | tar xz -C /root && bash /root/zynsimple-main/install.sh
```

Danach am Handy: `http://<IP-des-Zynthian>:8090`

Ausführliche Anleitung: [ANLEITUNG.md](ANLEITUNG.md)

Der Zynthian-Code selbst wird nicht verändert. Entfernen: `bash /zynthian/zynthian-my-data/zynsimple/uninstall.sh`
