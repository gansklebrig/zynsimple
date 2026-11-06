# -*- coding: utf-8 -*-
"""
ZynSimple – einfache Mischer-Ansicht für Zynthian (Oram & Vangelis).

Wird über zynsimple_boot.py beim Start der Zynthian-Oberfläche eingehängt.
"""

import json
import logging
import os

log = logging.getLogger("zynsimple")

VERSION = "2.4"

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
}

SCREEN_NAME = "zynsimple"
HOME_NAMES = ("audio_mixer", "mixer", "root")


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as e:
        log.error(f"ZynSimple: Einstellungen fehlerhaft ({e}), nutze Standardwerte")
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
                        "title": "Imres\nBühne",
                        "icon": "playing.png",
                        "action": lambda *a, **k: __import__("threading").Thread(
                            target=imres.system, args=("imres",), daemon=True).start(),
                    })
            except Exception:
                pass
            def handpan(*a, **k):
                try:
                    bridge = zyngui._zs_bridge
                    bridge.extras.create_handpan(zyngui._zs_settings.get("handpan_inputs") or [1])
                    zyngui.show_screen_reset(SCREEN_NAME)
                except Exception as e:
                    _info(zyngui, f"Handpan: {e}")

            def update(*a, **k):
                scr = zyngui.screens.get(SCREEN_NAME)

                def show(text, sub="", done=False, error=False):
                    if scr is not None:
                        scr.show_update(text, sub, done, error)
                    elif done or error:
                        _info(zyngui, f"{text} {sub}")

                def run():
                    from . import updater, web
                    show("Suche nach Updates …", "GitHub wird gefragt")
                    st = updater.check(zyngui._zs_settings)
                    if st.get("available"):
                        try:
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
                        if st.get("error"):
                            show("Kein Update gefunden", f"{st['error']} – und kein USB-Stick mit Update. Antippen zum Schließen.",
                                 error=True)
                        else:
                            show(f"ZynSimple {st.get('current')} ist aktuell", "Antippen zum Schließen", done=True)

                if scr is not None:
                    zyngui.show_screen_reset(SCREEN_NAME)
                import threading
                threading.Thread(target=run, daemon=True).start()

            entries.append({"title": "Handpan\nanlegen", "icon": "microphone.png", "action": handpan})
            entries.append({"title": "ZynSimple\nUpdate", "icon": "update.png", "action": update})
            return entries + config

        menu.get_config = get_config
        menu._zs_menu = True
        log.info("ZynSimple: Eintrag im Hauptmenü angelegt")
    except Exception as e:
        log.warning(f"ZynSimple: Hauptmenü-Eintrag fehlgeschlagen: {e}")


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
