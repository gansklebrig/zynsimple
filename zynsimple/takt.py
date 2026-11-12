# -*- coding: utf-8 -*-
"""
ZynSimple – gemeinsamer Takt (MIDI-Clock) im Zynthian- und im Hybrid-Modus.

Einstellung „takt“:
  senden  der Zynthian gibt den Takt vor und schickt MIDI-Clock an die TR-8S/TR-6S (USB) und die DIN-Buchse
  folgen  die TR-8S (oder was an der DIN-Buchse Clock schickt) gibt den Takt vor – der Zynthian läuft als Slave mit:
          Sequenzer, Delays im Takt, Looper und im Hybrid-Modus auch Mixxx
  aus     ZynSimple fasst die Clock-Einstellungen des Zynthian nicht an

Im reinen DJ-Modus erledigt das der DJ-Helfer (dj/dj-helfer.py) mit derselben Einstellung.
"""
import logging
import re

log = logging.getLogger("zynsimple")

RX_TR = re.compile(r"TR-?\d+S\b|TR-?8|TR-?6", re.I)
RX_DIN = re.compile(r"ttymidi|DIN", re.I)


def wert(settings):
    t = settings.get("takt")
    if t in ("senden", "folgen", "aus"):
        return t
    return "senden" if settings.get("dj_clock", True) else "aus"


def _text(port):
    try:
        return " ".join([port.name] + [str(a) for a in (port.aliases or [])])
    except Exception:
        return str(port)


def _passt(port):
    t = _text(port)
    return bool(RX_TR.search(t) or RX_DIN.search(t))


def anwenden(settings):
    """Clock-Wege im Zynthian setzen. Ändert nur etwas, wenn es nötig ist (darf oft aufgerufen werden)."""
    t = wert(settings)
    try:
        import zynautoconnect as za
    except Exception:
        return "kein Zynthian"
    try:
        outs = [p for p in list(za.devices_out) if p is not None]
        ins = [(i, p) for i, p in enumerate(list(za.devices_in)) if p is not None]
        unsere_out = [p.aliases[0] for p in outs if _passt(p)]
        jetzt = list(za.get_midi_clock_output_ports() or [])
        ext = za.get_ext_clock_zmip()
        ext_unser = 0 <= ext < len(za.devices_in) and za.devices_in[ext] is not None and _passt(za.devices_in[ext])
        if t == "senden":
            fehlt = [n for n in unsere_out if n not in jetzt]
            if fehlt:
                za.set_midi_clock_output_ports(jetzt + fehlt)
                log.info(f"ZynSimple: Takt geht an {', '.join(fehlt)}")
            if ext_unser:
                za.set_ext_clock_zmip(-1)
            return "senden"
        if t == "folgen":
            if unsere_out and any(n in jetzt for n in unsere_out):
                za.set_midi_clock_output_ports([n for n in jetzt if n not in unsere_out])
            quelle = next((i for i, p in ins if RX_TR.search(_text(p))), None)
            if quelle is None:
                quelle = next((i for i, p in ins if RX_DIN.search(_text(p))), None)
            if quelle is not None and ext != quelle:
                za.set_ext_clock_zmip(quelle)
                log.info(f"ZynSimple: Takt kommt von {_text(za.devices_in[quelle])}")
            return "folgen" if quelle is not None else "folgen (TR-8S nicht gefunden)"
        return "aus"
    except Exception as e:
        log.debug(f"ZynSimple: Takt: {e}")
        return f"Fehler: {e}"


def aufraeumen(settings):
    """Beim Umschalten auf „aus“: was ZynSimple gesetzt hat, wieder lösen."""
    try:
        import zynautoconnect as za
        jetzt = list(za.get_midi_clock_output_ports() or [])
        unsere = [p.aliases[0] for p in za.devices_out if p is not None and _passt(p)]
        if any(n in jetzt for n in unsere):
            za.set_midi_clock_output_ports([n for n in jetzt if n not in unsere])
        ext = za.get_ext_clock_zmip()
        if 0 <= ext < len(za.devices_in) and za.devices_in[ext] is not None and _passt(za.devices_in[ext]):
            za.set_ext_clock_zmip(-1)
    except Exception as e:
        log.debug(f"ZynSimple: Takt aufräumen: {e}")


def quelle_text(settings):
    """Kurzer Text für die Anzeige: wer gibt gerade den Takt vor?"""
    t = wert(settings)
    try:
        import zynautoconnect as za
        if t == "folgen":
            ext = za.get_ext_clock_zmip()
            if 0 <= ext < len(za.devices_in) and za.devices_in[ext] is not None:
                return "TR-8S gibt den Takt vor"
            return "warte auf die TR-8S (USB anstecken oder DIN-Kabel)"
        if t == "senden":
            n = [p for p in za.devices_out if p is not None and _passt(p)]
            return "Zynthian gibt den Takt an die TR-8S" if n else "Zynthian gibt den Takt (keine TR-8S gefunden)"
    except Exception:
        pass
    return "ZynSimple lässt die Clock-Einstellungen in Ruhe"
