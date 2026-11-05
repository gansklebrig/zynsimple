# -*- coding: utf-8 -*-
"""ZynSimple – eigenes Farbschema für die RGB-Tasten des V5 (ohne Blau)."""

import logging

log = logging.getLogger("zynsimple")

# Farbschema „Glut“: warme Töne, kein Blau. Werte = (Rot, Grün, Blau) 0..255
DEFAULT_SCHEME = {
    "default": [150, 45, 0],    # Grundfarbe aller Tasten: tiefes Bernstein (war Blau)
    "alt":     [130, 0, 130],   # Alternativmodus: Lila (wie bisher)
    "active":  [0, 200, 0],     # aktiv: Grün (wie bisher)
    "active2": [210, 130, 0],   # zweite Aktiv-Farbe: Goldgelb (war Orange)
    "active3": [150, 120, 60],  # dritte Aktiv-Farbe: warmes Weiß (war Türkis)
    "admin":   [160, 0, 0],     # Admin/Aufnahme: Rot (wie bisher)
}


def _rgb(base, v):
    r, g, b = (int(x) for x in v)
    return base.create_color(r, g, b)


def apply(zyngui, scheme=None):
    sch = dict(DEFAULT_SCHEME)
    if isinstance(scheme, dict):
        sch.update({k: v for k, v in scheme.items() if k in DEFAULT_SCHEME})

    try:
        from zyngui.zynthian_wsleds_base import zynthian_wsleds_base as base_cls
    except Exception as e:
        log.info(f"ZynSimple LEDs: keine LED-Steuerung gefunden ({e})")
        return

    if not getattr(base_cls, "_zs_patched", False):
        orig = base_cls.setup_colors

        def setup_colors(self):
            orig(self)
            try:
                s = getattr(base_cls, "_zs_scheme", DEFAULT_SCHEME)
                self.wscolor_blue = _rgb(self, s["default"])
                self.wscolor_blue_light = _rgb(self, s["active3"])
                self.wscolor_purple = _rgb(self, s["alt"])
                self.wscolor_orange = _rgb(self, s["active2"])
                self.wscolor_green = _rgb(self, s["active"])
                self.wscolor_red = _rgb(self, s["admin"])
                self.wscolor_default = self.wscolor_blue
                self.wscolor_alt = self.wscolor_purple
                self.wscolor_active = self.wscolor_green
                self.wscolor_active2 = self.wscolor_orange
                self.wscolor_active3 = self.wscolor_blue_light
                self.wscolor_admin = self.wscolor_red
                # Zuordnung für die Bildschirm-Tastatur neu aufbauen
                self.wscolors_dict = {
                    str(self.wscolor_off): "0",
                    str(self.wscolor_blue): "B",
                    str(self.wscolor_green): "G",
                    str(self.wscolor_red): "R",
                    str(self.wscolor_orange): "O",
                    str(self.wscolor_yellow): "Y",
                    str(self.wscolor_purple): "P",
                    str(self.wscolor_blue_light): "T",
                }
            except Exception as e:
                log.warning(f"ZynSimple LEDs: Farbschema fehlerhaft ({e})")

        base_cls.setup_colors = setup_colors
        base_cls._zs_patched = True

    base_cls._zs_scheme = sch

    # Bereits laufende LED-Treiber sofort umfärben
    for name in ("wsleds", "wsleds_v5touch"):
        inst = getattr(zyngui, name, None)
        if inst is not None and isinstance(inst, base_cls):
            try:
                inst.setup_colors()
                if hasattr(inst, "beat_color"):
                    inst.beat_color = inst.wscolor_default
                if hasattr(inst, "reset_last_state"):
                    inst.reset_last_state()
            except Exception as e:
                log.warning(f"ZynSimple LEDs: Umfärben fehlgeschlagen ({e})")
    log.info("ZynSimple: LED-Farbschema ohne Blau aktiv")
