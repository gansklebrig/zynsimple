# -*- coding: utf-8 -*-
"""
ZynSimple – einfache Mischer-Ansicht für Zynthian (Oram & Vangelis).

Wird über zynsimple_boot.py beim Start der Zynthian-Oberfläche eingehängt.
"""

import json
import logging
import os

log = logging.getLogger("zynsimple")

VERSION = "4.4"

HOME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(HOME_DIR, "zynsimple.json")

DEFAULTS = {
    "web_enabled": True,
    "web_port": 8090,
    "pin": "",
    "screen_enabled": True,
    "replace_home": True,
    "strip_min_width": 130,
    "led_recolor": True,
    "led_colors": {},
    "autosave": True,
    "autosave_seconds": 20,
    "handpan_inputs": [1],
    "update_check": True,
    "idle_seconds": 45,
    "splash": True,
    "xy_spring": False,
    "synth_midi_chan": 0,
    "update_repo": "gansklebrig/zynsimple",
    "update_branch": "main",
    "help_seen": False,
    "tonart": "",
    "master_limiter": False,
    "dj_auto_rec": False,
    "dj_clock": True,
    "takt": "senden",
    "start_modus": "zynthian",
    "ton_anzeige": "keytar",
    "bsp_an": False,
    "bsp_drums": False,
    "keytar_geraet": None,
    "keytar_kanal": None,
    "dj_handpan_fx": True,
    "dj_stems": True,
}

SCREEN_NAME = "zynsimple"
HOME_NAMES = ("audio_mixer", "mixer", "root")


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            gespeichert = json.load(f)
        s.update(gespeichert)
        if "takt" not in gespeichert and gespeichert.get("dj_clock") is False:
            s["takt"] = "aus"
    except FileNotFoundError:
        pass
    except Exception as e:
        log.error(f"ZynSimple: Einstellungen fehlerhaft ({e}), nutze Standardwerte")
    if s.get("takt") not in ("senden", "folgen", "aus"):
        s["takt"] = "senden" if s.get("dj_clock", True) else "aus"
    return s


def setup(zyngui):
    """Wird nach create_screens() im Hauptthread aufgerufen."""
    settings = load_settings()
    from .core import Bridge
    bridge = Bridge(zyngui)
    zyngui._zs_bridge = bridge
    zyngui._zs_settings = settings
    bridge.settings = settings
    try:
        from . import updater
        updater.start_background_check(settings)
    except Exception as e:
        log.warning(f"ZynSimple: Update-Prüfung nicht gestartet ({e})")
    try:
        from .extras import Extras
        bridge.extras = Extras(bridge, settings)
        from .perform import Perform
        bridge.perform = Perform(bridge, bridge.extras)
        from .tracks import Tracks
        from .extras import HOME_DIR
        bridge.tracks = Tracks(bridge, HOME_DIR)
        from zyngui import zynthian_gui_config
        bridge.extras.start_autosave(zynthian_gui_config.top)
        _hook_exit(zyngui, bridge.extras)
    except Exception as e:
        log.exception(f"ZynSimple: Extras fehlgeschlagen: {e}")
    try:
        from .hybrid import Hybrid
        bridge.hybrid = Hybrid(bridge, settings)
    except Exception as e:
        bridge.hybrid = None
        log.warning(f"ZynSimple: DJ + Instrumente nicht verfügbar ({e})")
    try:
        from .geraete import Geraete
        bridge.geraete = Geraete(bridge, settings)
        if settings.get("keytar_geraet") or settings.get("bsp_an") or settings.get("ton_anzeige") == "alle":
            bridge.geraete.start()
    except Exception as e:
        bridge.geraete = None
        log.warning(f"ZynSimple: MIDI-Geräte nicht verfügbar ({e})")
    _buehne(zyngui, bridge, settings)

    if settings.get("led_recolor", True):
        try:
            from . import leds
            leds.apply(zyngui, settings.get("led_colors") or {})
        except Exception as e:
            log.exception(f"ZynSimple: LED-Farben fehlgeschlagen: {e}")

    if settings.get("web_enabled", True):
        from . import web
        web.start(bridge, settings.get("web_port", 8090), settings.get("pin", ""))

    if settings.get("screen_enabled", True):
        try:
            from .screen import zynsimple_screen
            zyngui.screens[SCREEN_NAME] = zynsimple_screen(bridge, settings)
            log.info("ZynSimple: Touchscreen-Ansicht angelegt")
        except Exception as e:
            log.exception(f"ZynSimple: Touchscreen-Ansicht fehlgeschlagen: {e}")
        _add_menu_entry(zyngui)
    _hook_power(zyngui)
    _start_aktion(zyngui)
    _update_fertig_zeigen(zyngui)


START_AKTION = "/run/zynsimple-start-aktion"
GESTARTET = "/run/zynsimple-gestartet"


def _buehne(zyngui, bridge, settings):
    """Für den Auftritt: Takt (MIDI-Clock) halten, Unterspannung melden und sichern, Startmodus nach dem Einschalten."""
    try:
        from zyngui import zynthian_gui_config
        top = zynthian_gui_config.top
    except Exception:
        return
    zustand = {"n": 0, "gesichert": 0.0}

    def schleife():
        import time
        zustand["n"] += 1
        try:
            from . import takt
            if takt.wert(settings) != "aus":
                takt.anwenden(settings)          # auch, wenn die TR-8S erst später eingesteckt wird
        except Exception as e:
            log.debug(f"ZynSimple: Takt: {e}")
        if getattr(bridge, "hybrid", None) is not None and zustand["n"] % 3 == 1:
            bridge.hybrid.kanal_pruefen()
        try:
            from . import dj
            stick = dj.musik_stick() if dj.eingerichtet() else None
            if stick and stick != zustand.get("stick"):
                scr = zyngui.screens.get(SCREEN_NAME)
                if scr is not None:
                    scr._flash(f"„{stick}“ mit Musik erkannt · ⋯ → ⇩ Musik übernehmen")
            zustand["stick"] = stick
        except Exception:
            pass
        try:
            from . import helfer
            st = helfer.strom()
            if st and st["jetzt"]:
                scr = zyngui.screens.get(SCREEN_NAME)
                if scr is not None:
                    scr._warn("⚡ Strom zu schwach – Netzteil/Akku prüfen · alles ist gesichert")
                if time.monotonic() - zustand["gesichert"] > 60 and getattr(bridge, "extras", None):
                    zustand["gesichert"] = time.monotonic()
                    bridge.extras.save_now("Unterspannung")
                    os.sync()
        except Exception as e:
            log.debug(f"ZynSimple: Strom: {e}")
        top.after(10000, schleife)

    top.after(12000, schleife)

    # Startmodus: nur beim ersten Start der Oberfläche nach dem Einschalten
    if os.path.exists(GESTARTET):
        return
    try:
        open(GESTARTET, "w").close()
    except OSError:
        return
    modus = settings.get("start_modus", "zynthian")
    if modus == "dj":
        top.after(9000, lambda: start_dj(zyngui))
    elif modus == "hybrid" and getattr(bridge, "hybrid", None):
        def hybrid_los():
            try:
                _info(zyngui, bridge.hybrid.starten())
            except Exception as e:
                _info(zyngui, str(e))
        top.after(12000, hybrid_los)


def system_menue(zyngui):
    """Das Zynthian-Power-Menü (Abbrechen · Ausschalten · Neu starten), erweitert um Updates und die Apps."""
    import threading
    adm = zyngui.screens.get("admin")
    items = [
        {"icon": "cancel.png", "title": "Abbrechen", "action": lambda *a, **k: zyngui.close_screen()},
        {"icon": "poweroff.png", "title": "Ausschalten", "action": lambda *a, **k: adm.power_off_confirmed()},
        {"icon": "reboot.png", "title": "Neu starten", "action": lambda *a, **k: adm.reboot_confirmed()},
    ]
    try:
        from . import updater
        neu = updater.status.get("available") and updater.status.get("latest")
    except Exception:
        neu = None
    items.append({"icon": "settings.png", "title": f"ZynSimple-Update {neu} bereit" if neu else "ZynSimple aktualisieren",
                  "action": lambda *a, **k: start_update(zyngui)})
    if adm is not None and hasattr(adm, "update_software"):
        items.append({"icon": "zynthian_logo.png", "title": "Zynthian aktualisieren",
                      "action": lambda *a, **k: adm.update_software()})
    try:
        from . import imres
        if imres.installed():
            def bb_update(*a, **k):
                imres.system_update()
                _info(zyngui, "Barden Beats wird im Hintergrund aktualisiert")
                zyngui.close_screen()
            items.append({"icon": "audio.png", "title": "Barden Beats aktualisieren", "action": bb_update})
            items.append({"icon": "special_chain.png", "title": "Barden Beats",
                          "action": lambda *a, **k: threading.Thread(target=imres.system, args=("imres",), daemon=True).start()})
    except Exception:
        pass
    try:
        from . import dj
        if dj.eingerichtet():
            items.append({"icon": "audio_generator.png", "title": "DJ-Pult", "action": lambda *a, **k: start_dj(zyngui)})
            hy = getattr(getattr(zyngui, "_zs_bridge", None), "hybrid", None)
            if hy is not None and dj.mixxx_da():
                if hy.laeuft():
                    items.append({"icon": "audio_generator.png", "title": "DJ + Instrumente beenden",
                                  "action": lambda *a, **k: (_info(zyngui, hy.stoppen()), zyngui.close_screen())})
                else:
                    items.append({"icon": "audio_generator.png", "title": "DJ + Instrumente",
                                  "action": lambda *a, **k: (zyngui.show_screen_reset(SCREEN_NAME), _info(zyngui, hy.starten()))})
    except Exception:
        pass
    items.append({"icon": "mixer.png", "title": "Einfacher Mischer",
                  "action": lambda *a, **k: zyngui.show_screen_reset(SCREEN_NAME)})
    zyngui.screens["grid_sel"].setup("System", items, cols=3)
    zyngui.show_screen("grid_sel")


def _ist_back(cfg_eintrag):
    try:
        return str(cfg_eintrag.get("S") or "").strip().upper().split(" ")[0] == "BACK"
    except Exception:
        return False


def _hook_power(zyngui):
    """BACK 2 s halten (Zynthians „lang“) und das Power-Menü → erweitertes System-Menü."""
    try:
        adm = zyngui.screens.get("admin")
        if adm is not None and not getattr(adm, "_zs_power", False):
            adm.power = lambda *a, **k: system_menue(zyngui)
            adm._zs_power = True
        orig = getattr(zyngui, "custom_switch_ui_action", None)
        if callable(orig) and not getattr(zyngui, "_zs_back_long", False):
            from zyngui import zynthian_gui_config as cfg

            def custom_switch_ui_action(i, t, *a, **k):
                try:
                    if t == "L" and _ist_back(cfg.custom_switch_ui_actions[i]):
                        system_menue(zyngui)
                        return True
                except Exception as e:
                    log.debug(f"ZynSimple: BACK lang: {e}")
                return orig(i, t, *a, **k)

            zyngui.custom_switch_ui_action = custom_switch_ui_action
            zyngui._zs_back_long = True
        log.info("ZynSimple: BACK 2 s → System-Menü")
    except Exception as e:
        log.warning(f"ZynSimple: System-Menü nicht eingehängt: {e}")


def _update_fertig_zeigen(zyngui):
    """War das ein Neustart nach einem Update? Dann kurz zeigen, dass alles geklappt hat."""
    p = os.path.join(HOME_DIR, ".update_fertig")
    try:
        with open(p, encoding="utf-8") as f:
            ver = f.read().strip()
        os.remove(p)
    except OSError:
        return
    from . import fortschritt as fs
    from .updater import UPDATE_SCHRITTE

    def zeigen():
        scr = zyngui.screens.get(SCREEN_NAME)
        if scr is None:
            return
        fs.start(f"Update auf {ver}", UPDATE_SCHRITTE)
        fs.fertig(f"ZynSimple {ver} läuft – alles erledigt")
        scr.show_update(f"Update auf {ver} fertig", "Antippen zum Schließen", done=True)
        zynthian_gui_config.top.after(7000, lambda: (fs.ende(), scr.mode == "update" and setattr(scr, "mode", "mix"),
                                                     setattr(scr, "sig", None)))
    try:
        from zyngui import zynthian_gui_config
        zynthian_gui_config.top.after(4500, zeigen)
    except Exception:
        pass


def _start_aktion(zyngui):
    """Kommt die Oberfläche aus dem DJ-Pult oder Barden Beats mit einem Auftrag (z. B. Update)?"""
    try:
        with open(START_AKTION, encoding="utf-8") as f:
            aktion = f.read().strip()
        os.remove(START_AKTION)
    except OSError:
        return

    def los():
        if aktion == "zynsimple-update":
            start_update(zyngui)
        elif aktion == "zynthian-update":
            adm = zyngui.screens.get("admin")
            if adm is not None and hasattr(adm, "update_software"):
                adm.update_software()
        elif aktion == "menue":
            system_menue(zyngui)
        elif aktion == "hybrid":
            hy = getattr(getattr(zyngui, "_zs_bridge", None), "hybrid", None)
            if hy is not None:
                try:
                    _info(zyngui, hy.starten())
                except Exception as e:
                    _info(zyngui, str(e))
    try:
        from zyngui import zynthian_gui_config
        zynthian_gui_config.top.after(6000, los)
    except Exception:
        pass


def _hook_exit(zyngui, extras):
    """Vor dem Beenden/Herunterfahren noch einmal alles speichern."""
    orig = getattr(zyngui, "exit", None)
    if not callable(orig) or getattr(zyngui, "_zs_exit_hooked", False):
        return

    def exit_and_save(*args, **kwargs):
        try:
            if not getattr(zyngui, "_zs_saved_on_exit", False):
                zyngui._zs_saved_on_exit = True
                extras.save_now("Beenden")
        except Exception as e:
            log.warning(f"ZynSimple: Speichern beim Beenden fehlgeschlagen ({e})")
        return orig(*args, **kwargs)

    zyngui.exit = exit_and_save
    zyngui._zs_exit_hooked = True


def _info(zyngui, text):
    try:
        zyngui.show_info(text, 3000)
    except Exception:
        log.info(f"ZynSimple: {text}")


def _add_menu_entry(zyngui):
    """Eintrag „Einfacher Mischer“ ins Zynthian-Hauptmenü."""
    try:
        menu = zyngui.screens.get("main_menu")
        orig = getattr(menu, "get_config", None)
        if not callable(orig) or getattr(menu, "_zs_menu", False):
            return

        def open_simple(*args, **kwargs):
            zyngui.show_screen_reset(SCREEN_NAME)

        def get_config():
            config = list(orig() or [])
            entries = [{
                "title": "Einfacher\nMischer",
                "icon": "mixer.png",
                "action": open_simple,
            }]
            try:
                from . import imres
                if imres.installed():
                    entries.append({
                        "title": "Barden\nBeats",
                        "icon": "playing.png",
                        "action": lambda *a, **k: __import__("threading").Thread(
                            target=imres.system, args=("imres",), daemon=True).start(),
                    })
            except Exception:
                pass
            try:
                from . import dj
                if dj.eingerichtet():
                    entries.append({"title": "DJ-Pult", "icon": "playing.png",
                                    "action": lambda *a, **k: start_dj(zyngui)})
            except Exception:
                pass

            def settings_page(*a, **k):
                zyngui.show_screen_reset(SCREEN_NAME)
                scr = zyngui.screens.get(SCREEN_NAME)
                if scr is not None:
                    scr.open_settings()

            entries.append({"title": "Einstellungen\n& Update", "icon": "settings.png", "action": settings_page})
            return entries + config

        menu.get_config = get_config
        menu._zs_menu = True
        log.info("ZynSimple: Eintrag im Hauptmenü angelegt")
    except Exception as e:
        log.warning(f"ZynSimple: Hauptmenü-Eintrag fehlgeschlagen: {e}")


def start_update(zyngui, *a, **k):
    """Update suchen und installieren – GitHub zuerst, sonst USB-Stick, mit Animation."""
    scr = zyngui.screens.get(SCREEN_NAME)

    def show(text, sub="", done=False, error=False):
        if scr is not None:
            scr.show_update(text, sub, done, error)
        elif done or error:
            _info(zyngui, f"{text} {sub}")

    def run():
        from . import updater, web
        from . import fortschritt as fs
        fs.start("ZynSimple-Update", updater.UPDATE_SCHRITTE)
        fs.schritt(0, "GitHub wird gefragt")
        show("Suche nach Updates …", "GitHub wird gefragt")
        st = updater.check(zyngui._zs_settings)
        if st.get("available"):
            try:
                fs.teil(anteil=1.0, detail=f"Version {st['latest']} gefunden (du hast {st.get('current')})")
                fs.STAND["titel"] = f"Update {st.get('current')} → {st['latest']}"
                show(f"Update {st['latest']} wird geladen …", "von GitHub · bitte nicht ausschalten")
                updater.install(zyngui._zs_settings)
                show(f"Update {st['latest']} wird installiert …", "Die Oberfläche startet gleich neu")
                return
            except Exception as e:
                log.warning(f"ZynSimple: GitHub-Update: {e}")
        try:
            local = web.find_local_update()
            if local:
                show("Update vom USB-Stick …", os.path.basename(local))
                web.install_local_update()
                show("Update wird installiert …", "Die Oberfläche startet gleich neu")
                return
            raise FileNotFoundError
        except Exception:
            fs.ende()
            if st.get("error"):
                show("Kein Update gefunden", f"{st['error']} – und kein USB-Stick mit Update. Antippen zum Schließen.",
                     error=True)
            else:
                show(f"ZynSimple {st.get('current')} ist aktuell", "Antippen zum Schließen", done=True)

    if scr is not None:
        zyngui.show_screen_reset(SCREEN_NAME)
    import threading
    threading.Thread(target=run, daemon=True).start()


def start_dj(zyngui, *a, **k):
    """DJ-Pult starten – beim ersten Mal wird Mixxx installiert (mit Anzeige)."""
    scr = zyngui.screens.get(SCREEN_NAME)

    def show(text, sub="", done=False, error=False):
        if scr is not None:
            scr.show_update(text, sub, done, error)
        else:
            _info(zyngui, f"{text} {sub}")

    def run():
        from . import dj
        if not dj.eingerichtet():
            show("DJ-Pult fehlt", "ZynSimple einmal neu installieren. Antippen zum Schließen.", error=True)
            return
        if not dj.mixxx_da():
            show("DJ-Pult wird eingerichtet …", "Mixxx wird einmalig installiert · braucht Internet · einige Minuten")
            ok, msg = dj.installieren()
            if not ok:
                show("Mixxx fehlt noch", f"{msg} Antippen zum Schließen.", error=True)
                return
        show("DJ-Pult startet …", "Zurück: Mixxx beenden oder BACK 2 s halten → System-Menü")
        dj.system("dj")

    if scr is not None:
        # im Tk-Hauptthread umschalten (der Aufruf kann auch vom Handy-Webserver kommen)
        try:
            from zyngui import zynthian_gui_config
            zynthian_gui_config.top.after(0, lambda: zyngui.show_screen_reset(SCREEN_NAME))
        except Exception:
            pass
    import threading
    threading.Thread(target=run, daemon=True).start()


def start_import(zyngui, *a, auswahl=None, **k):
    """Musik vom USB-Stick auf den Zynthian kopieren – mit Fortschritt auf dem Display.
    auswahl: Ordner/Titel aus dem Stick-Browser; ohne = der ganze Ordner „MUSIK gekauft“."""
    scr = zyngui.screens.get(SCREEN_NAME)

    def show(text, sub="", done=False, error=False):
        if scr is not None:
            scr.show_update(text, sub, done, error)

    def run():
        import time
        from . import dj
        from . import fortschritt as fs
        fs.start("Musik vom USB-Stick übernehmen", [("Stick prüfen", 5), ("Kopieren", 92), ("Fertig", 3)])
        fs.schritt(0, "Auswahl wird geprüft" if auswahl else "Ordner „MUSIK gekauft“ wird gesucht")
        show("Musik wird übernommen …", "deine Auswahl vom Stick" if auswahl else "vom USB-Stick (Ordner „MUSIK gekauft“)")
        try:
            dj.import_starten(auswahl)
        except Exception as e:
            fs.fehler(str(e))
            show("Import ging nicht", f"{e} Antippen zum Schließen.", error=True)
            return
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4 * 3600:
            time.sleep(0.4)
            st = dj.import_stand()
            if st["phase"] == "fertig":
                hy = getattr(getattr(zyngui, "_zs_bridge", None), "hybrid", None)
                extra = ""
                if hy is not None and hy.laeuft():
                    hy.nach_import()
                    extra = " Mixxx liest die neuen Titel ein, sobald gerade nichts läuft (ca. 20 s)."
                fs.fertig(st["text"] + " · der Stick kann raus")
                show("Musik übernommen", "Antippen zum Schließen." + extra, done=True)
                return
            if st["phase"] == "fehler":
                fs.fehler(st["text"])
                show("Import ging nicht", st["text"] + ". Antippen zum Schließen.", error=True)
                return
            if st.get("gesamt"):
                if fs.STAND.get("schritt", 0) < 1:
                    fs.schritt(1)
                fs.teil(bytes_=st.get("bytes", 0), total=st.get("gesamt_b") or None,
                        detail=f"{st['n']} von {st['gesamt']} Dateien",
                        zeile=("kopiere: " if st.get("kopiert") else "schon da: ") + st.get("datei", ""))

    if scr is not None:
        try:
            from zyngui import zynthian_gui_config
            zynthian_gui_config.top.after(0, lambda: zyngui.show_screen_reset(SCREEN_NAME))
        except Exception:
            pass
    import threading
    threading.Thread(target=run, daemon=True).start()


AUFGABEN = {
    "mixxx26": "Mixxx 2.6 mit Stems wird gebaut",
    "stems-einrichten": "Stem-Werkzeug wird eingerichtet",
    "stems": "Stems vorbereiten",
}


def start_aufgabe(zyngui, art, starten=False):
    """Lange Hintergrund-Aufgabe anzeigen (und ggf. starten). Antippen schließt nur die Anzeige – die Aufgabe läuft weiter."""
    import threading
    import time
    from . import dj
    from . import fortschritt as fs
    scr = zyngui.screens.get(SCREEN_NAME)
    if starten:
        if art == "mixxx26":
            dj.mixxx26_starten()
        elif art == "stems-einrichten":
            dj.stems_einrichten()
    if scr is None:
        return

    def stand():
        if art == "mixxx26":
            return dj.mixxx26_stand()
        if art == "stems-einrichten":
            return dj.stems_install_stand()
        d = dj.stems_status()
        n = d.get("warteschlange", 0)
        st = {"schritte": [("Warten", 5), ("Trennen (Demucs)", 90), ("Stem-Datei", 5)], "schritt": 0, "teil": 0.0,
              "detail": "", "zeile": " · ".join(d.get("letzte", [])[:2]), "fertig": False, "fehler": d.get("fehler"),
              "titel": f"Stems vorbereiten · {n} in der Warteschlange" if n else "Stems vorbereiten"}
        if d.get("pause"):
            st["detail"] = "pausiert – das DJ-Pult läuft oder „Stems“ ist ausgeschaltet"
        elif d.get("aktuell"):
            pz = d.get("prozent", 0.0)
            st["schritt"], st["teil"] = (2, 0.5) if pz >= 99 else (1, pz / 100)
            eta = d.get("eta_s")
            st["detail"] = f"„{d['aktuell']}“" + (f" · noch ca. {eta // 60 + 1} min" if eta else "")
        elif not n:
            st["detail"] = "Nichts zu tun – Tracks in die Mixxx-Kiste „Stems vorbereiten“ ziehen"
            st["fertig"] = True
        return st

    def fuellen(s):
        if not fs.STAND.get("aktiv") or fs.STAND.get("aufgabe") != art:
            fs.start(s.get("titel") or AUFGABEN[art], s["schritte"])
            fs.STAND["aufgabe"] = art
            fs.STAND["hintergrund"] = True
        if s.get("titel"):
            fs.STAND["titel"] = s["titel"]
        if s.get("fehler"):
            fs.fehler(s["fehler"])
            return
        if s.get("fertig"):
            fs.fertig(s.get("detail", ""))
            return
        fs.STAND["fertig"] = False
        if s["schritt"] != fs.STAND.get("schritt"):
            fs.schritt(s["schritt"])
        fs.STAND["teil"] = s["teil"]
        fs.teil(detail=s.get("detail", ""), zeile=s.get("zeile", ""))

    def lauf():
        time.sleep(0.6 if starten else 0)
        while True:
            try:
                fuellen(stand())
            except Exception as e:
                log.debug(f"Aufgabe {art}: {e}")
            time.sleep(0.6)
            if scr.mode != "update" or fs.STAND.get("aufgabe") != art:
                return

    fs.start(AUFGABEN[art], [("Start", 1)])
    fs.STAND["aufgabe"] = art
    fs.STAND["hintergrund"] = True
    scr.show_update(AUFGABEN[art], "Antippen schließt die Anzeige – die Aufgabe läuft weiter")
    try:
        from zyngui import zynthian_gui_config
        zynthian_gui_config.top.after(0, lambda: zyngui.show_screen_reset(SCREEN_NAME))
    except Exception:
        pass
    threading.Thread(target=lauf, daemon=True).start()


def redirect(zyngui, screen, hmode=None):
    """Entscheidet, ob ein Startbildschirm-Aufruf auf die einfache Ansicht umgeleitet wird."""
    try:
        settings = getattr(zyngui, "_zs_settings", None)
        if not settings or not settings.get("replace_home", True):
            return screen
        if SCREEN_NAME not in zyngui.screens:
            return screen
        if screen not in HOME_NAMES:
            return screen
        # Ausdrücklich gewünscht (Taste „Profi-Mischer“)
        if getattr(zyngui, "_zs_allow_home", False):
            zyngui._zs_allow_home = False
            return screen
        # Ist der Profi-Mischer gerade offen, bleibt er offen –
        # außer bei „nach Hause“ (BACK lang drücken = Verlauf zurücksetzen)
        current = getattr(zyngui, "current_screen", None)
        if current in HOME_NAMES and hmode != getattr(zyngui, "SCREEN_HMODE_RESET", 3):
            return screen
        return SCREEN_NAME
    except Exception:
        return screen
