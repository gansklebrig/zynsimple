# -*- coding: utf-8 -*-
"""Bard Hero – alle Lieder in der Reihenfolge der Liedauswahl."""
import importlib

REIHENFOLGE = [
    "lagerfeuer", "taverne", "funken", "drache", "neon", "moor", "goblins", "walzer", "sturm",
    "handpan", "kraken", "punk", "feuerinsel",
]

_cache = {}


def lied(name):
    if name not in _cache:
        _cache[name] = importlib.import_module(name).lied()
    return _cache[name]


def alle():
    raus = []
    for name in REIHENFOLGE:
        try:
            raus.append(lied(name))
        except ImportError:
            continue
    return raus
