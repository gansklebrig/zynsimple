# -*- coding: utf-8 -*-
"""
ZynSimple Boot-Haken.

Wird über eine .pth-Datei bei jedem Python-Start geladen, tut aber nur
etwas, wenn die Zynthian-Oberfläche (zyngui.zynthian_gui) importiert wird.
So bleibt der Zynthian-Code unverändert und Updates überschreiben nichts.

Notbremse: Datei  zynsimple.disabled  neben dieser Datei anlegen.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGET = "zyngui.zynthian_gui"


def _patch(module):
    import logging
    log = logging.getLogger("zynsimple")
    try:
        cls = module.zynthian_gui
    except AttributeError:
        log.error("ZynSimple: zynthian_gui-Klasse nicht gefunden")
        return

    orig_create = cls.create_screens
    orig_show = cls.show_screen

    def create_screens(self, *args, **kwargs):
        result = orig_create(self, *args, **kwargs)
        try:
            import zynsimple
            zynsimple.setup(self)
        except Exception as e:
            log.exception(f"ZynSimple: Start fehlgeschlagen: {e}")
        return result

    def show_screen(self, *args, **kwargs):
        try:
            import zynsimple
            hmode = args[1] if len(args) > 1 else kwargs.get("hmode")
            if args:
                args = (zynsimple.redirect(self, args[0], hmode),) + tuple(args[1:])
            elif "screen" in kwargs:
                kwargs["screen"] = zynsimple.redirect(self, kwargs["screen"], hmode)
        except Exception:
            pass
        return orig_show(self, *args, **kwargs)

    cls.create_screens = create_screens
    cls.show_screen = show_screen
    log.info("ZynSimple: in Zynthian-Oberfläche eingehängt")


class _Finder:
    """Meta-Path-Finder, der nur auf zyngui.zynthian_gui reagiert."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _TARGET:
            return None
        import importlib.machinery
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or not hasattr(spec.loader, "exec_module"):
            return spec
        loader = spec.loader
        orig_exec = loader.exec_module

        def exec_module(module):
            orig_exec(module)
            try:
                _patch(module)
            except Exception:
                pass

        loader.exec_module = exec_module
        return spec


def _install():
    if os.path.exists(os.path.join(_HERE, "zynsimple.disabled")):
        return
    if _HERE not in sys.path:
        sys.path.append(_HERE)
    if not any(isinstance(f, _Finder) for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder())


try:
    _install()
except Exception:
    pass
