# -*- coding: utf-8 -*-
"""
Bard Hero – Grafik: Farben (ohne Blau), Schriften, Leucht-Sprites, Notenbahn und die Hintergründe pro Lied.

Hintergründe sind in Ebenen vorgezeichnet (Himmel, Silhouetten) – pro Bild kommen nur die bewegten Teile dazu.
Grafikstufe 0 = ruhig (nur Leuchten im Takt), 1 = mittel, 2 = alles.
"""
import colorsys
import math
import random

import pygame

# ---------------------------------------------------------------------------------------------------------
# Farben – warm, kein Blau
# ---------------------------------------------------------------------------------------------------------
BG = (11, 9, 8)
KARTE = (24, 19, 15)
KARTE2 = (34, 27, 21)
LINIE = (58, 46, 36)
GOLD = (232, 176, 74)
GOLD2 = (255, 217, 138)
CHAMP = (243, 233, 216)
TX2 = (166, 154, 138)
GLUT = (242, 163, 58)
ROT = (229, 72, 77)
GRUEN = (61, 214, 140)
GELB = (245, 217, 10)
VIOLETT = (176, 74, 208)
ORANGE = (255, 144, 0)
WEISS = (255, 248, 236)
SCHWARZ = (0, 0, 0)

SPUR_FARBEN = [GRUEN, ROT, GELB, VIOLETT, ORANGE, (255, 96, 150)]
# 3+3-Controller (wie Guitar Hero Live): untere Reihe hell (Elfenbein), obere dunkel mit Glutrand
ELFENBEIN = (246, 232, 206)
KOHLE = (46, 36, 30)
# Barden-Modus: 12 Farben quer durchs warme Spektrum – ohne Blautöne
_HUES = [0, 22, 40, 52, 68, 95, 135, 280, 300, 318, 335, 350]
TON_FARBEN = [tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h / 360, 0.78, 1.0)) for h in _HUES]
WEISSE_TASTEN = [0, 2, 4, 5, 7, 9, 11]


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def misch(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def heller(c, f):
    return tuple(min(255, int(x * f)) for x in c)


# ---------------------------------------------------------------------------------------------------------
# Schriften und Text
# ---------------------------------------------------------------------------------------------------------
_fonts = {}
_text_cache = {}
FONT_NAMEN = "audiowide,rajdhani,exo2,dejavusans,freesans,sans"


def schrift(groesse, fett=False):
    key = (int(groesse), fett)
    if key not in _fonts:
        try:
            f = pygame.font.SysFont(FONT_NAMEN, int(groesse), bold=fett)
        except Exception:
            f = pygame.font.Font(None, int(groesse * 1.3))
        _fonts[key] = f
    return _fonts[key]


def text(s, groesse, farbe=CHAMP, fett=False):
    key = (s, int(groesse), farbe, fett)
    t = _text_cache.get(key)
    if t is None:
        t = schrift(groesse, fett).render(str(s), True, farbe)
        if len(_text_cache) > 600:
            _text_cache.clear()
        _text_cache[key] = t
    return t


def text_zeigen(ziel, s, groesse, pos, farbe=CHAMP, anker="mitte", fett=False, schatten=True):
    t = text(s, groesse, farbe, fett)
    r = t.get_rect()
    setattr(r, {"mitte": "center", "links": "midleft", "rechts": "midright", "oben": "midtop",
                "obenlinks": "topleft", "unten": "midbottom"}[anker], (int(pos[0]), int(pos[1])))
    if schatten:
        sch = text(s, groesse, (0, 0, 0), fett)
        ziel.blit(sch, r.move(max(1, groesse // 18), max(1, groesse // 18)))
    ziel.blit(t, r)
    return r


def umbrechen(s, groesse, breite):
    f = schrift(groesse)
    zeilen, z = [], ""
    for w in s.split():
        neu = (z + " " + w).strip()
        if f.size(neu)[0] > breite and z:
            zeilen.append(z)
            z = w
        else:
            z = neu
    if z:
        zeilen.append(z)
    return zeilen


# ---------------------------------------------------------------------------------------------------------
# Leucht-Sprites (radiale Verläufe, additiv geblittet – schnell)
# ---------------------------------------------------------------------------------------------------------
_glow = {}


def glow(radius, farbe, staerke=1.0):
    # gerastert, damit der Vorrat klein bleibt (sonst wird bei jedem Bild neu gezeichnet)
    radius = max(2, int(radius))
    if radius > 24:
        radius = radius // 4 * 4
    staerke = max(0.0, min(1.0, round(staerke * 10) / 10))
    farbe = tuple(min(255, max(0, int(c) // 16 * 16 + 8)) for c in farbe)
    key = (radius, farbe, staerke)
    s = _glow.get(key)
    if s is None:
        s = pygame.Surface((radius * 2, radius * 2))
        s.fill((0, 0, 0))
        for i in range(radius, 0, -max(1, radius // 24)):
            f = (1 - i / radius) ** 1.8 * staerke
            pygame.draw.circle(s, tuple(min(255, max(0, int(c * f))) for c in farbe), (radius, radius), i)
        if len(_glow) > 400:
            _glow.clear()
        _glow[key] = s
    return s


def leuchten(ziel, pos, radius, farbe, staerke=1.0):
    if staerke <= 0.04 or radius < 1:
        return
    g = glow(radius, farbe, staerke)
    radius = g.get_width() // 2
    ziel.blit(g, (int(pos[0] - radius), int(pos[1] - radius)), special_flags=pygame.BLEND_ADD)


def verlauf(groesse, oben, unten, mitte=None):
    w, h = groesse
    s = pygame.Surface((w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        if mitte:
            c = misch(oben, mitte, t * 2) if t < 0.5 else misch(mitte, unten, (t - 0.5) * 2)
        else:
            c = misch(oben, unten, t)
        pygame.draw.line(s, c, (0, y), (w, y))
    return s


def rrect(ziel, farbe, rect, radius=12, breite=0):
    pygame.draw.rect(ziel, farbe, rect, breite, border_radius=int(radius))


# ---------------------------------------------------------------------------------------------------------
# Partikel
# ---------------------------------------------------------------------------------------------------------
class Partikel:
    __slots__ = ("x", "y", "vx", "vy", "leben", "max", "r", "farbe", "art")

    def __init__(self, x, y, vx, vy, leben, r, farbe, art=0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.leben = self.max = leben
        self.r = r
        self.farbe = farbe
        self.art = art


class Funken:
    def __init__(self, grenze=400):
        self.p = []
        self.grenze = grenze

    def neu(self, *a, **k):
        if len(self.p) < self.grenze:
            self.p.append(Partikel(*a, **k))

    def schritt(self, dt, schwerkraft=0.0):
        rest = []
        for p in self.p:
            p.leben -= dt
            if p.leben <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += schwerkraft * dt
            rest.append(p)
        self.p = rest

    def zeichnen(self, ziel):
        for p in self.p:
            f = p.leben / p.max
            if p.art == 1:            # Rechteck (Konfetti / Regen)
                c = heller(p.farbe, 0.4 + 0.6 * f)
                pygame.draw.line(ziel, c, (p.x, p.y), (p.x + p.vx * 0.02, p.y + p.vy * 0.02), max(1, int(p.r)))
            else:
                leuchten(ziel, (p.x, p.y), p.r * (0.5 + 0.5 * f) + 1, p.farbe, f)


# ---------------------------------------------------------------------------------------------------------
# Hintergründe
# ---------------------------------------------------------------------------------------------------------
class Hintergrund:
    def __init__(self, thema, groesse, stufe=2, farbe=GLUT, seed=1):
        self.thema = thema
        self.w, self.h = groesse
        self.stufe = stufe
        self.farbe = farbe
        self.z = random.Random(seed)
        self.funken = Funken(80 if stufe == 1 else (260 if stufe >= 2 else 0))
        self.spur = []              # für Poi-Leuchtspuren
        self.blitz = 0.0
        self.t_alt = 0.0
        self.extra = {}
        bau = getattr(self, "_bau_" + thema, None) or self._bau_standard
        self.statisch = bau()

    # ---- Bausteine ----
    def _berge(self, s, y0, hoehe, farbe, zacken=9, seed=0):
        z = random.Random(seed)
        pkt = [(0, self.h)]
        n = zacken * 2
        for i in range(n + 1):
            x = i * self.w / n
            y = y0 - (z.random() * 0.6 + (0.4 if i % 2 else 0.0)) * hoehe
            pkt.append((x, y))
        pkt.append((self.w, self.h))
        pygame.draw.polygon(s, farbe, pkt)

    def _sterne(self, s, n, farbe=(255, 236, 200), bis=0.6):
        for _ in range(n):
            x = self.z.random() * self.w
            y = self.z.random() * self.h * bis
            c = misch(BG, farbe, 0.3 + self.z.random() * 0.7)
            s.set_at((int(x), int(y)), c)
            if self.z.random() < 0.15:
                pygame.draw.circle(s, c, (int(x), int(y)), 1)

    def _baum(self, s, x, y, hoehe, farbe):
        for k in range(4):
            b = hoehe * (0.42 - k * 0.08)
            yy = y - hoehe * (0.25 + k * 0.2)
            pygame.draw.polygon(s, farbe, [(x - b, yy + hoehe * 0.3), (x + b, yy + hoehe * 0.3), (x, yy - hoehe * 0.12)])
        pygame.draw.rect(s, farbe, (x - hoehe * 0.04, y - hoehe * 0.25, hoehe * 0.08, hoehe * 0.25))

    def _bau_standard(self):
        s = verlauf((self.w, self.h), (20, 10, 8), (60, 24, 10))
        self._sterne(s, 120)
        self._berge(s, self.h * 0.8, self.h * 0.25, (16, 10, 8), seed=2)
        return s

    def _bau_lagerfeuer(self):
        s = verlauf((self.w, self.h), (12, 6, 18), (70, 34, 14), mitte=(28, 12, 22))
        self._sterne(s, 260, bis=0.55)
        self._berge(s, self.h * 0.72, self.h * 0.16, (22, 12, 14), 7, seed=3)
        # Fluss mit warmem Spiegel
        pygame.draw.rect(s, (30, 16, 12), (0, self.h * 0.74, self.w, self.h * 0.1))
        for x in (0.04, 0.12, 0.2, 0.83, 0.9, 0.97):
            self._baum(s, self.w * x, self.h * (0.98 + self.z.random() * 0.04), self.h * (0.5 + self.z.random() * 0.25),
                       (8, 5, 4))
        pygame.draw.rect(s, (14, 8, 6), (0, self.h * 0.9, self.w, self.h * 0.1))
        return s

    def _bau_taverne(self):
        s = verlauf((self.w, self.h), (40, 22, 12), (18, 10, 6))
        for i in range(0, self.w, max(8, self.w // 26)):
            c = (46 + self.z.randint(-8, 8), 26 + self.z.randint(-5, 5), 14)
            pygame.draw.line(s, misch(c, (20, 10, 6), 0.3), (i, 0), (i, self.h), 2)
        for y in (0.08, 0.5):
            pygame.draw.rect(s, (28, 14, 8), (0, self.h * y, self.w, self.h * 0.05))
        # Fässer
        for x in (0.07, 0.17, 0.85, 0.95):
            r = self.h * 0.09
            pygame.draw.ellipse(s, (34, 18, 8), (self.w * x - r, self.h * 0.82 - r * 1.2, r * 2, r * 2.4))
            for k in (-0.6, 0, 0.6):
                pygame.draw.line(s, (16, 8, 4), (self.w * x - r * 0.95, self.h * 0.82 + k * r),
                                 (self.w * x + r * 0.95, self.h * 0.82 + k * r), 3)
        pygame.draw.rect(s, (22, 12, 6), (0, self.h * 0.92, self.w, self.h * 0.08))
        return s

    def _bau_funk(self):
        s = verlauf((self.w, self.h), (24, 6, 26), (50, 10, 30))
        # Tanzboden in Perspektive
        hz = self.h * 0.62
        for i in range(-12, 13):
            pygame.draw.line(s, (60, 20, 40), (self.w / 2 + i * self.w * 0.02, hz), (self.w / 2 + i * self.w * 0.16, self.h), 1)
        y = hz
        k = 0
        while y < self.h:
            pygame.draw.line(s, (60, 20, 40), (0, y), (self.w, y), 1)
            k += 1
            y = hz + (self.h - hz) * (k / 10) ** 1.6
        return s

    def _bau_drache(self):
        s = verlauf((self.w, self.h), (30, 4, 6), (120, 34, 10), mitte=(70, 12, 10))
        self._sterne(s, 60, (255, 200, 160), 0.3)
        self._berge(s, self.h * 0.7, self.h * 0.3, (40, 10, 10), 6, seed=5)
        # Burg
        bx, by = self.w * 0.8, self.h * 0.62
        c = (18, 6, 6)
        pygame.draw.rect(s, c, (bx - self.w * 0.08, by, self.w * 0.16, self.h * 0.2))
        for k in range(-2, 3):
            pygame.draw.rect(s, c, (bx + k * self.w * 0.035 - self.w * 0.012, by - self.h * 0.12 - abs(k) * -self.h * 0.03,
                                    self.w * 0.024, self.h * 0.14))
        self._berge(s, self.h * 0.88, self.h * 0.12, (14, 4, 4), 10, seed=6)
        return s

    def _bau_synthwave(self):
        s = verlauf((self.w, self.h), (20, 4, 30), (120, 20, 70), mitte=(60, 8, 60))
        self._sterne(s, 120, (255, 200, 240), 0.4)
        # Sonne mit Streifen
        cx, cy, r = self.w / 2, self.h * 0.5, self.h * 0.22
        for y in range(int(cy - r), int(cy + r)):
            t = (y - (cy - r)) / (2 * r)
            if t > 0.5 and int((t - 0.5) * 30) % 3 == 0:
                continue
            dx = math.sqrt(max(0, r * r - (y - cy) ** 2))
            pygame.draw.line(s, misch((255, 220, 80), (255, 40, 140), t), (cx - dx, y), (cx + dx, y))
        self._berge(s, self.h * 0.62, self.h * 0.12, (40, 6, 50), 8, seed=7)
        pygame.draw.rect(s, (16, 2, 22), (0, self.h * 0.62, self.w, self.h * 0.38))
        return s

    def _bau_moor(self):
        s = verlauf((self.w, self.h), (6, 14, 8), (30, 40, 18))
        self._sterne(s, 80, (220, 255, 200), 0.4)
        pygame.draw.circle(s, (210, 220, 150), (int(self.w * 0.78), int(self.h * 0.2)), int(self.h * 0.07))
        self._berge(s, self.h * 0.75, self.h * 0.08, (12, 20, 10), 12, seed=8)
        for x in (0.06, 0.18, 0.88):
            # kahle Bäume
            bx, by = self.w * x, self.h * 0.95
            self._ast(s, bx, by, -math.pi / 2, self.h * 0.22, 5, (6, 10, 5))
        pygame.draw.rect(s, (8, 14, 6), (0, self.h * 0.9, self.w, self.h * 0.1))
        return s

    def _ast(self, s, x, y, winkel, laenge, tiefe, farbe):
        if tiefe == 0 or laenge < 3:
            return
        x2, y2 = x + math.cos(winkel) * laenge, y + math.sin(winkel) * laenge
        pygame.draw.line(s, farbe, (x, y), (x2, y2), max(1, tiefe))
        for d in (-0.5, 0.45):
            self._ast(s, x2, y2, winkel + d + self.z.uniform(-0.2, 0.2), laenge * 0.68, tiefe - 1, farbe)

    def _bau_goblins(self):
        return verlauf((self.w, self.h), (40, 60, 10), (16, 30, 6))

    def _bau_walzer(self):
        s = verlauf((self.w, self.h), (14, 6, 24), (40, 18, 40))
        self._sterne(s, 300, (255, 240, 210), 0.8)
        cx, cy, r = self.w * 0.22, self.h * 0.25, self.h * 0.11
        pygame.draw.circle(s, (255, 230, 170), (int(cx), int(cy)), int(r))
        pygame.draw.circle(s, (14, 6, 24), (int(cx + r * 0.45), int(cy - r * 0.1)), int(r * 0.9))
        return s

    def _bau_sturm(self):
        s = verlauf((self.w, self.h), (16, 12, 14), (60, 30, 26))
        self._berge(s, self.h * 0.78, self.h * 0.3, (20, 14, 14), 5, seed=9)
        # Burg auf dem Felsen
        c = (8, 6, 6)
        pygame.draw.polygon(s, c, [(self.w * 0.05, self.h), (self.w * 0.12, self.h * 0.6), (self.w * 0.26, self.h * 0.58),
                                   (self.w * 0.3, self.h)])
        for k in range(3):
            pygame.draw.rect(s, c, (self.w * (0.13 + k * 0.045), self.h * (0.42 + (k % 2) * 0.05), self.w * 0.03, self.h * 0.2))
        return s

    def _bau_handpan(self):
        return verlauf((self.w, self.h), (24, 14, 6), (50, 30, 10), mitte=(36, 20, 8))

    def _bau_kraken(self):
        s = verlauf((self.w, self.h), (24, 2, 12), (90, 14, 30))
        self._sterne(s, 120, (255, 200, 200), 0.4)
        pygame.draw.circle(s, (230, 70, 50), (int(self.w * 0.7), int(self.h * 0.25)), int(self.h * 0.12))
        pygame.draw.rect(s, (20, 4, 18), (0, self.h * 0.6, self.w, self.h * 0.4))
        return s

    def _bau_punk(self):
        s = pygame.Surface((self.w, self.h))
        s.fill((36, 12, 12))
        bh = max(8, self.h // 22)
        bw = bh * 2
        for row in range(0, self.h // bh + 1):
            for col in range(-1, self.w // bw + 2):
                x = col * bw + (bw // 2 if row % 2 else 0)
                c = (70 + self.z.randint(-14, 14), 22 + self.z.randint(-6, 6), 18)
                pygame.draw.rect(s, c, (x + 1, row * bh + 1, bw - 2, bh - 2))
        # Spray-Kleckse
        for _ in range(9):
            c = self.z.choice([GELB, (255, 90, 140), GRUEN, ORANGE, VIOLETT])
            x, y = self.z.random() * self.w, self.z.random() * self.h * 0.6
            for k in range(30):
                pygame.draw.circle(s, misch(c, (36, 12, 12), self.z.random() * 0.4),
                                   (int(x + self.z.gauss(0, self.w * 0.03)), int(y + self.z.gauss(0, self.h * 0.03))),
                                   self.z.randint(2, 6))
        return s

    def _bau_feuerinsel(self):
        s = verlauf((self.w, self.h), (8, 2, 6), (60, 16, 6))
        self._sterne(s, 200, (255, 220, 180), 0.45)
        pygame.draw.rect(s, (14, 4, 6), (0, self.h * 0.66, self.w, self.h * 0.34))
        # Insel
        pygame.draw.ellipse(s, (6, 2, 2), (self.w * 0.2, self.h * 0.6, self.w * 0.6, self.h * 0.14))
        for x in (0.3, 0.36, 0.62, 0.7):
            bx, by = self.w * x, self.h * 0.64
            pygame.draw.line(s, (6, 2, 2), (bx, by), (bx + self.w * 0.01, by - self.h * 0.12), 3)
            for d in range(5):
                w = math.pi + d * 0.6
                pygame.draw.line(s, (6, 2, 2), (bx + self.w * 0.01, by - self.h * 0.12),
                                 (bx + self.w * 0.01 + math.cos(w) * self.h * 0.06,
                                  by - self.h * 0.12 - math.sin(w) * self.h * 0.03 + self.h * 0.02), 2)
        return s

    # ---- pro Bild ----
    def zeichnen(self, ziel, t, phase, energie=0.5, insp=False, schlag_neu=False, takt_neu=False):
        dt = max(0.0, min(0.1, t - self.t_alt))
        self.t_alt = t
        ziel.blit(self.statisch, (0, 0))
        w, h = self.w, self.h
        puls = (1 - phase) ** 3                    # 1 direkt auf dem Schlag, fällt ab
        f = getattr(self, "_dyn_" + self.thema, None)
        if f and self.stufe > 0:
            f(ziel, t, dt, puls, energie, schlag_neu, takt_neu)
        else:
            leuchten(ziel, (w / 2, h * 0.75), h * (0.35 + 0.08 * puls), self.farbe, 0.35 + 0.25 * puls)
        if insp:
            # Inspiration: Flammenschein von unten
            for k in range(5):
                leuchten(ziel, (w * (0.1 + k * 0.2), h * 1.02), h * (0.28 + 0.06 * math.sin(t * 6 + k)), ORANGE, 0.55)
        self.funken.schritt(dt)
        self.funken.zeichnen(ziel)
        if self.blitz > 0:
            ziel.fill(tuple(int(255 * self.blitz * 0.7) for _ in range(3)), special_flags=pygame.BLEND_ADD)
            self.blitz = max(0.0, self.blitz - dt * 5)

    def _viele(self):
        return 2 if self.stufe >= 2 else 1

    def _dyn_lagerfeuer(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        fx, fy = w * 0.13, h * 0.9
        flacker = 0.8 + 0.2 * math.sin(t * 17) * math.sin(t * 7.3)
        leuchten(s, (fx, fy), h * 0.34 * flacker, (255, 120, 30), 0.7)
        leuchten(s, (fx, fy - h * 0.03), h * 0.08, (255, 210, 120), 0.9)
        for k in range(self._viele()):
            if self.z.random() < 0.6:
                self.funken.neu(fx + self.z.gauss(0, w * 0.01), fy - h * 0.04, self.z.gauss(0, 20), -60 - self.z.random() * 80,
                                1.5 + self.z.random() * 1.5, 2.5, (255, 150, 40))
        # Spiegelung im Fluss
        for k in range(6):
            y = h * (0.75 + k * 0.015)
            x = w * 0.5 + math.sin(t * 0.7 + k) * w * 0.2
            pygame.draw.line(s, (90, 50, 20), (x - w * 0.04, y), (x + w * 0.04, y), 1)

    def _dyn_taverne(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        for k, x in enumerate((0.15, 0.38, 0.62, 0.85)):
            schw = math.sin(t * 1.6 + k) * 0.06
            ax, ay = w * x, h * 0.12
            lx, ly = ax + math.sin(schw) * h * 0.18, ay + math.cos(schw) * h * 0.18
            pygame.draw.line(s, (20, 10, 4), (ax, ay), (lx, ly), 2)
            leuchten(s, (lx, ly), h * (0.12 + 0.03 * puls), (255, 160, 60), 0.6 + 0.3 * puls)
            pygame.draw.rect(s, (60, 30, 10), (lx - h * 0.02, ly - h * 0.03, h * 0.04, h * 0.06), 2)
        if self.z.random() < 0.3 * self._viele():
            self.funken.neu(self.z.random() * w, self.z.random() * h, self.z.gauss(0, 5), self.z.gauss(0, 5), 3, 1.5,
                            (120, 90, 50))

    def _dyn_funk(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        farben = [ORANGE, (255, 60, 160), GELB, VIOLETT]
        band = self.extra.get("band")
        if band is None:
            band = self.extra["band"] = pygame.Surface((w, h))
        band.fill((0, 0, 0))
        for k in range(4):
            if self.stufe < 2 and k % 2:
                continue
            winkel = math.sin(t * (0.6 + k * 0.17) + k) * 0.7
            x0 = w * (0.15 + k * 0.23)
            x1 = x0 + math.sin(winkel) * h
            c = tuple(int(v * (0.18 + 0.25 * puls)) for v in farben[k])
            pygame.draw.polygon(band, c, [(x0 - 4, 0), (x0 + 4, 0), (x1 + w * 0.08, h), (x1 - w * 0.08, h)])
        s.blit(band, (0, 0), special_flags=pygame.BLEND_ADD)
        # Spiegelkugel
        kx, ky = w / 2, h * 0.08
        pygame.draw.circle(s, (200, 180, 160), (int(kx), int(ky)), int(h * 0.05))
        for k in range(8):
            a = t * 2 + k * 0.8
            leuchten(s, (kx + math.cos(a) * w * 0.4, ky + abs(math.sin(a * 1.3)) * h * 0.6), h * 0.02, WEISS, 0.8)
        hz = h * 0.62
        for k in range(6):
            x = w * (0.1 + k * 0.16)
            leuchten(s, (x, hz + (h - hz) * 0.6), h * 0.12, farben[(k + int(t * 2)) % 4], 0.25 + 0.4 * puls)

    def _dyn_drache(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        leuchten(s, (w * 0.8, h * 0.62), h * (0.25 + 0.1 * puls), (255, 90, 20), 0.5)
        for _ in range(self._viele() * 2):
            if self.z.random() < 0.7:
                self.funken.neu(self.z.random() * w, h * 1.0, self.z.gauss(0, 15), -50 - self.z.random() * 90,
                                3 + self.z.random() * 2, 2, (255, 110, 30))
        # Drache fliegt alle 14 s vorbei
        p = (t % 14) / 6.0
        if p < 1:
            x = -w * 0.2 + p * w * 1.4
            y = h * (0.25 + 0.05 * math.sin(p * 6))
            fl = math.sin(t * 7) * h * 0.06
            g = h * 0.05
            c = (20, 4, 4)
            pygame.draw.polygon(s, c, [(x - g * 2, y), (x + g * 2.4, y - g * 0.2), (x + g * 3.2, y - g * 0.6),
                                       (x + g * 2.4, y + g * 0.2)])
            pygame.draw.polygon(s, c, [(x, y), (x + g * 0.4, y - g * 0.2), (x - g * 0.4, y - g * 2 - fl), (x - g * 1.4, y - g * 1.2 - fl)])
            pygame.draw.polygon(s, c, [(x - g * 2, y), (x - g * 3.4, y + g * 0.8), (x - g * 2.6, y + g * 0.2)])
            if int(t * 3) % 4 == 0:
                leuchten(s, (x + g * 3.6, y - g * 0.5), g * 1.4, (255, 140, 30), 0.8)

    def _dyn_synthwave(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        hz = h * 0.62
        c = misch((120, 20, 120), (255, 80, 200), puls)
        for i in range(-14, 15):
            pygame.draw.line(s, c, (w / 2 + i * w * 0.012, hz), (w / 2 + i * w * 0.11, h), 1)
        for k in range(12):
            p = ((k + (t * 0.8) % 1) / 12)
            y = hz + (h - hz) * p ** 2.2
            pygame.draw.line(s, c, (0, y), (w, y), 1)
        leuchten(s, (w / 2, h * 0.5), h * 0.35, (255, 60, 140), 0.25 + 0.2 * puls)

    def _dyn_moor(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        for k in range(3 * self._viele()):
            x = (t * (12 + k * 5) + k * w * 0.37) % (w * 1.4) - w * 0.2
            y = h * (0.7 + 0.06 * k % 0.2)
            leuchten(s, (x, y), h * 0.2, (60, 80, 40), 0.25)
        for k in range(10 * self._viele()):
            x = w * ((k * 0.137 + math.sin(t * 0.3 + k) * 0.05) % 1)
            y = h * (0.55 + 0.35 * ((k * 0.311 + math.sin(t * 0.5 + k * 2) * 0.04) % 1))
            an = 0.5 + 0.5 * math.sin(t * 3 + k * 1.7)
            leuchten(s, (x, y), h * 0.015 + 2, (200, 255, 80), an)

    def _dyn_goblins(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        cx, cy = w / 2, h * 0.45
        n = 16
        for k in range(n):
            a0 = t * 0.3 + k * 2 * math.pi / n
            a1 = a0 + math.pi / n
            c = [(46, 70, 12), (110, 86, 12), (30, 52, 8)][k % 3]
            pygame.draw.polygon(s, c, [(cx, cy), (cx + math.cos(a0) * w, cy + math.sin(a0) * w),
                                       (cx + math.cos(a1) * w, cy + math.sin(a1) * w)])
        for k in range(5):
            x = w * (0.08 + k * 0.21)
            sprung = abs(math.sin((t * 2.2 + k * 0.4) * math.pi)) * h * 0.08 * (0.5 + puls)
            y = h * 0.86 - sprung
            r = h * 0.06
            pygame.draw.circle(s, (70, 150, 40), (int(x), int(y)), int(r))
            pygame.draw.polygon(s, (70, 150, 40), [(x - r * 0.8, y - r * 0.3), (x - r * 1.9, y - r * 0.9), (x - r * 0.6, y - r * 0.8)])
            pygame.draw.polygon(s, (70, 150, 40), [(x + r * 0.8, y - r * 0.3), (x + r * 1.9, y - r * 0.9), (x + r * 0.6, y - r * 0.8)])
            for d in (-0.35, 0.35):
                pygame.draw.circle(s, GELB, (int(x + d * r), int(y - r * 0.15)), max(2, int(r * 0.18)))
            pygame.draw.arc(s, (30, 60, 10), (x - r * 0.5, y - r * 0.2, r, r * 0.8), math.pi * 1.1, math.pi * 1.9, 2)

    def _dyn_walzer(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        if self.z.random() < 0.5 * self._viele():
            self.funken.neu(self.z.random() * w, -5, self.z.gauss(0, 8), 20 + self.z.random() * 25, 12, 1.8,
                            (255, 230, 170))
        cx, cy = w * 0.5, h * 0.3
        for k in range(12):
            a = t * 0.35 + k * math.pi / 6
            leuchten(s, (cx + math.cos(a) * h * 0.22, cy + math.sin(a) * h * 0.08), h * 0.02 + 2,
                     GOLD2, 0.5 + 0.4 * puls)

    def _dyn_sturm(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        for k in range(4):
            x = (t * (20 + k * 9) + k * w * 0.3) % (w * 1.5) - w * 0.25
            pygame.draw.ellipse(s, (30 + k * 5, 22, 24), (x, h * (0.05 + k * 0.05), w * 0.4, h * 0.1))
        for _ in range(4 * self._viele()):
            self.funken.neu(self.z.random() * w * 1.2, -10, -120, 700, 0.8, 1, (120, 100, 100), art=1)
        if tn and self.z.random() < 0.45:
            self.blitz = 0.8
            x = self.z.random() * w
            pkt = [(x, 0)]
            y = 0
            while y < h * 0.7:
                y += h * 0.07
                x += self.z.gauss(0, w * 0.03)
                pkt.append((x, y))
            self.extra["blitz"] = (pkt, t)
        b = self.extra.get("blitz")
        if b and t - b[1] < 0.18:
            pygame.draw.lines(s, WEISS, False, b[0], 3)

    def _dyn_handpan(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        cx, cy = w / 2, h * 0.42
        leuchten(s, (cx, cy), h * (0.32 + 0.05 * puls), (200, 110, 20), 0.35 + 0.25 * puls)
        for ring in range(1, 5):
            n = 6 + ring * 4
            r = h * (0.07 * ring) * (1 + 0.04 * puls)
            for k in range(n):
                a = k * 2 * math.pi / n + t * (0.12 if ring % 2 else -0.09)
                leuchten(s, (cx + math.cos(a) * r, cy + math.sin(a) * r), h * 0.012 + 2,
                         misch(GOLD, ORANGE, ring / 4), 0.4 + 0.5 * puls)
        if self.z.random() < 0.3 * self._viele():
            self.funken.neu(self.z.random() * w, h, self.z.gauss(0, 6), -15 - self.z.random() * 20, 8, 2, GOLD2)

    def _dyn_kraken(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        for k in range(5):
            y0 = h * (0.6 + k * 0.08)
            pkt = [(0, h)]
            for i in range(0, 21):
                x = i * w / 20
                pkt.append((x, y0 + math.sin(x / w * 8 + t * (1.2 + k * 0.3) + k) * h * 0.02))
            pkt.append((w, h))
            pygame.draw.polygon(s, (40 - k * 5, 6, 30 - k * 4), pkt)
        for k, x0 in enumerate((0.1, 0.9)):
            pkt = []
            for i in range(14):
                p = i / 13
                x = w * x0 + math.sin(t * 1.3 + p * 4 + k) * w * 0.04 * p
                y = h * (1.0 - p * 0.55)
                pkt.append((x, y))
            for i in range(len(pkt) - 1):
                pygame.draw.line(s, (60, 10, 40), pkt[i], pkt[i + 1], max(2, int(h * 0.03 * (1 - i / 14))))

    def _dyn_punk(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        for x in (0.08, 0.92):
            bx = w * x
            pygame.draw.rect(s, (14, 10, 10), (bx - h * 0.1, h * 0.45, h * 0.2, h * 0.5))
            for y in (0.57, 0.8):
                r = h * (0.06 + 0.012 * puls)
                pygame.draw.circle(s, (40, 30, 30), (int(bx), int(h * y)), int(r))
                pygame.draw.circle(s, (8, 6, 6), (int(bx), int(h * y)), int(r * 0.5))
        if sn:
            for _ in range(10 * self._viele()):
                self.funken.neu(self.z.random() * w, -5, self.z.gauss(0, 40), 80 + self.z.random() * 120, 4, 3,
                                self.z.choice([GELB, (255, 90, 140), GRUEN, ORANGE, VIOLETT]), art=1)

    def _dyn_feuerinsel(self, s, t, dt, puls, e, sn, tn):
        w, h = self.w, self.h
        # Poi: zwei Feuerkugeln in Blüten-Bahnen, mit Leuchtspur
        cx, cy = w * 0.5, h * 0.42
        for k in range(2):
            a = t * 3.2 + k * math.pi
            r = h * 0.16 * (0.6 + 0.4 * math.cos(4 * t * 0.8 + k))
            x = cx + (-1 if k else 1) * w * 0.08 + math.cos(a) * r
            y = cy + math.sin(a) * r
            self.spur.append((x, y, t))
        self.spur = [p for p in self.spur if t - p[2] < (0.45 if self.stufe >= 2 else 0.2)]
        for x, y, t0 in self.spur[::1 if self.stufe >= 2 else 2]:
            f = 1 - (t - t0) / 0.45
            leuchten(s, (x, y), h * 0.02 + 3, (255, int(120 + 100 * f), 30), max(0.0, f))
        leuchten(s, (cx, h * 0.68), h * 0.25, (255, 90, 10), 0.3 + 0.3 * puls)
        for _ in range(self._viele() * 2):
            self.funken.neu(self.z.random() * w, h * 0.98, self.z.gauss(0, 15), -60 - self.z.random() * 100,
                            2 + self.z.random() * 2, 2, (255, 120, 30))


# ---------------------------------------------------------------------------------------------------------
# Notenbahn
# ---------------------------------------------------------------------------------------------------------
class Bahn:
    """Perspektivische Notenbahn. modus 'hero' (n Spuren) oder 'barde' (Klaviatur, 12 Spuren).
    form '3x2': 3 Bahnen, jede Note liegt oben (dunkel) oder unten (hell) – wie der Controller."""

    def __init__(self, rect, modus, spuren=5, namen=None, sicht=1.4, form="reihe5"):
        self.rect = pygame.Rect(rect)
        self.modus = modus
        self.form = form if modus == "hero" else "klavier"
        self.n = 12 if modus == "barde" else spuren
        self.spalten = 3 if self.form == "3x2" else self.n
        self.namen = namen
        self.sicht = sicht
        x, y, w, h = self.rect
        self.unten = w
        self.oben = w * 0.38
        self.y_oben = y + h * 0.04
        self.y_treffer = y + h * 0.86
        self.cx = x + w / 2
        self.k = 2.6
        self.brett = self._brett()
        self._sprites = {}
        self.flammen = Funken(160)
        self.gedrueckt_glow = [0.0] * 12

    def _p(self, z):
        z = max(-0.15, min(1.0, z))
        return (1 - 1 / (1 + self.k * z)) / (1 - 1 / (1 + self.k)) if z >= 0 else z * 0.9

    def tiefe(self, z):
        """z (0 = Trefferlinie, 1 = Horizont) → (y, Breite)"""
        p = self._p(z)
        y = self.y_treffer - p * (self.y_treffer - self.y_oben)
        b = self.unten + (self.oben - self.unten) * p
        return y, b

    def spur_x(self, spur, b):
        """Mitte und Breite einer Spur bei Bahnbreite b (relativ zur Mitte)."""
        if self.modus == "barde":
            weiss = WEISSE_TASTEN
            ww = b / 7
            if spur in weiss:
                i = weiss.index(spur)
                return -b / 2 + ww * (i + 0.5), ww * 0.86
            links = max(k for k in weiss if k < spur)
            i = weiss.index(links)
            return -b / 2 + ww * (i + 1), ww * 0.62
        sw = b / self.spalten
        return -b / 2 + sw * (spur % self.spalten + 0.5), sw * 0.86

    def _brett(self):
        x, y, w, h = self.rect
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        top = self.y_oben - y
        tr = self.y_treffer - y
        unten = h
        poly = [(w / 2 - self.oben / 2, top), (w / 2 + self.oben / 2, top),
                (w / 2 + self.unten / 2 * 1.05, unten), (w / 2 - self.unten / 2 * 1.05, unten)]
        pygame.draw.polygon(s, (18, 12, 10, 225), poly)
        if self.modus == "barde":
            for k in range(12):
                if k in WEISSE_TASTEN:
                    continue
                pts = []
                for z in (1.0, -0.12):
                    yy, b = self.tiefe(z)
                    m, bw = self.spur_x(k, b)
                    pts.append((w / 2 + m - bw / 2, yy - y))
                    pts.append((w / 2 + m + bw / 2, yy - y))
                pygame.draw.polygon(s, (8, 5, 4, 230), [pts[0], pts[1], pts[3], pts[2]])
        grenzen = self.spalten + 1 if self.modus == "hero" else 8
        for i in range(grenzen):
            pts = []
            for z in (1.0, -0.12):
                yy, b = self.tiefe(z)
                xx = -b / 2 + b * i / (grenzen - 1)
                pts.append((w / 2 + xx, yy - y))
            c = (90, 66, 44, 255) if i in (0, grenzen - 1) else (50, 38, 28, 200)
            pygame.draw.line(s, c, pts[0], pts[1], 3 if i in (0, grenzen - 1) else 1)
        _ = tr
        return s

    def _plektrum(self, oben, r, insp, glut=False):
        """Note für 3+3: unten helles, oben dunkles Plektrum (Spitze zeigt zur Reihe)."""
        r = max(5, int(r))
        key = ("p", oben, r, insp, glut)
        sp = self._sprites.get(key)
        if sp is None:
            w, h = r * 2 + 6, int(r * 1.5) + 6
            sp = pygame.Surface((w, h), pygame.SRCALPHA)
            cx = w / 2
            if oben:          # Spitze nach oben
                pkt = [(cx, 3), (cx + r, h * 0.55), (cx + r * 0.7, h - 4), (cx - r * 0.7, h - 4), (cx - r, h * 0.55)]
                innen, rand = KOHLE, ORANGE
            else:             # Spitze nach unten
                pkt = [(cx, h - 3), (cx + r, h * 0.45), (cx + r * 0.7, 4), (cx - r * 0.7, 4), (cx - r, h * 0.45)]
                innen, rand = ELFENBEIN, GOLD
            if glut:
                innen = misch(innen, (255, 150, 40), 0.5)
            pygame.draw.polygon(sp, (0, 0, 0, 150), [(x, y + 2) for x, y in pkt])
            pygame.draw.polygon(sp, innen, pkt)
            pygame.draw.polygon(sp, rand, pkt, max(2, r // 5))
            if insp:
                pygame.draw.polygon(sp, WEISS, pkt, max(2, r // 4))
            self._sprites[key] = sp
        return sp

    def _gem(self, farbe, r, insp):
        r = max(4, int(r))
        key = (farbe, r, insp)
        sp = self._sprites.get(key)
        if sp is None:
            sp = pygame.Surface((r * 2 + 4, int(r * 1.4) + 4), pygame.SRCALPHA)
            rr = pygame.Rect(2, 2, r * 2, int(r * 1.4))
            dunkel = heller(farbe, 0.45)
            pygame.draw.ellipse(sp, (0, 0, 0, 160), rr.move(0, 2))
            pygame.draw.ellipse(sp, dunkel, rr)
            pygame.draw.ellipse(sp, farbe, rr.inflate(-r * 0.25, -r * 0.25))
            pygame.draw.ellipse(sp, heller(farbe, 1.6), (rr.x + r * 0.45, rr.y + r * 0.2, r * 0.9, r * 0.35))
            if insp:
                pygame.draw.ellipse(sp, WEISS, rr, max(2, r // 5))
            if len(self._sprites) > 500:
                self._sprites.clear()
            self._sprites[key] = sp
        return sp

    def farbe(self, spur):
        if self.form == "3x2":
            return ORANGE if spur >= 3 else ELFENBEIN
        return TON_FARBEN[spur] if self.modus == "barde" else SPUR_FARBEN[spur % 6]

    def treffer(self, spur, perfekt=False):
        y, b = self.tiefe(0)
        m, bw = self.spur_x(spur, b)
        x = self.cx + m
        c = self.farbe(spur)
        for _ in range(14 if perfekt else 8):
            self.flammen.neu(x + random.gauss(0, bw * 0.15), y, random.gauss(0, 60), -random.uniform(80, 260),
                             random.uniform(0.25, 0.5), 3, heller(c, 1.2))

    def zeichnen(self, ziel, jetzt, noten, start, gedrueckt, insp_aktiv=False, schlag=0.5, dt=0.016, fehl=0.0):
        x0, y0 = self.rect.x, self.rect.y
        ziel.blit(self.brett, (x0, y0))
        # Schlaglinien
        if schlag > 0:
            erster = math.ceil(jetzt / schlag) * schlag
            k = 0
            while True:
                tl = erster + k * schlag
                z = (tl - jetzt) / self.sicht
                if z > 1:
                    break
                yy, b = self.tiefe(z)
                c = (70, 52, 36) if round(tl / schlag) % 4 == 0 else (40, 30, 22)
                pygame.draw.line(ziel, c, (self.cx - b / 2, yy), (self.cx + b / 2, yy), 2 if round(tl / schlag) % 4 == 0 else 1)
                k += 1
        # Trefferlinie mit Tasten
        yt, bt = self.tiefe(0)
        for s in range(self.n):
            m, bw = self.spur_x(s, bt)
            x = self.cx + m
            c = self.farbe(s)
            an = s in gedrueckt
            self.gedrueckt_glow[s] = 1.0 if an else max(0.0, self.gedrueckt_glow[s] - dt * 5)
            g = self.gedrueckt_glow[s]
            r = bw * 0.42
            if self.form == "3x2":
                oben = s >= 3
                rr = pygame.Rect(0, 0, bw * 0.78, r * 0.78)
                rr.center = (x, yt + (-r * 0.44 if oben else r * 0.44))
                grund = KOHLE if oben else (90, 80, 66)
                rrect(ziel, misch(grund, ORANGE if oben else ELFENBEIN, 0.15 + 0.85 * g), rr, 7)
                rrect(ziel, ORANGE if oben else GOLD, rr, 7, 2)
                if g > 0:
                    leuchten(ziel, rr.center, r * 1.8, ORANGE if oben else GOLD2, 0.5 * g)
                continue
            if self.modus == "barde":
                weiss = s in WEISSE_TASTEN
                rr = pygame.Rect(0, 0, bw * 0.96, r * 1.1)
                rr.center = (x, yt + (0 if weiss else -r * 0.15))
                rrect(ziel, misch((60, 50, 40) if weiss else (20, 14, 10), c, 0.35 + 0.6 * g), rr, 6)
                rrect(ziel, heller(c, 0.9), rr, 6, 2)
            else:
                pygame.draw.ellipse(ziel, misch((30, 22, 16), c, 0.25 + 0.75 * g), (x - r, yt - r * 0.7, r * 2, r * 1.4))
                pygame.draw.ellipse(ziel, c, (x - r, yt - r * 0.7, r * 2, r * 1.4), max(2, int(r * 0.18)))
            if g > 0:
                leuchten(ziel, (x, yt), r * 2.2, c, 0.5 * g)
        if fehl > 0:
            pygame.draw.line(ziel, ROT, (self.cx - bt / 2, yt), (self.cx + bt / 2, yt), max(2, int(6 * fehl)))
        # Noten (von hinten nach vorne)
        sichtbar = []
        i = start
        while i < len(noten):
            n = noten[i]
            if n.t - jetzt > self.sicht:
                break
            sichtbar.append(n)
            i += 1
        for n in reversed(sichtbar):
            if n.status == 1 and not (n.halten_bis and n.gehalten):
                continue
            z = (n.t - jetzt) / self.sicht
            c = self.farbe(n.spur)
            if n.status == 2:
                c = (70, 60, 55)
            # Haltespur
            if n.halten_bis:
                z2 = (n.halten_bis - jetzt) / self.sicht
                if z2 > -0.05:
                    za = max(z, 0.0) if n.status == 1 else z
                    ya, ba = self.tiefe(za)
                    ye, be = self.tiefe(min(z2, 1.0))
                    ma, bwa = self.spur_x(n.spur, ba)
                    me, bwe = self.spur_x(n.spur, be)
                    breit_a, breit_e = bwa * 0.22, bwe * 0.22
                    farbe = heller(c, 1.15) if n.gehalten else heller(c, 0.6)
                    pygame.draw.polygon(ziel, farbe, [(self.cx + ma - breit_a, ya), (self.cx + ma + breit_a, ya),
                                                      (self.cx + me + breit_e, ye), (self.cx + me - breit_e, ye)])
                    if n.gehalten:
                        leuchten(ziel, (self.cx + ma, ya), bwa * 0.8, c, 0.8)
            if n.status == 1:
                continue
            if z < -0.15:
                continue
            yy, b = self.tiefe(z)
            m, bw = self.spur_x(n.spur, b)
            r = bw * 0.42
            insp = n.insp
            farbe = c
            if insp_aktiv:
                farbe = misch(c, (255, 180, 60), 0.5)
            if self.form == "3x2":
                sp = self._plektrum(n.spur >= 3, r * 0.9, insp, bool(insp_aktiv))
            else:
                sp = self._gem(farbe, r, insp)
            if insp:
                leuchten(ziel, (self.cx + m, yy), r * 1.6, GOLD2, 0.45)
            ziel.blit(sp, (self.cx + m - sp.get_width() / 2, yy - sp.get_height() / 2))
            if self.modus == "barde" and self.namen and r > 9:
                text_zeigen(ziel, self.namen[n.spur], max(9, int(r * 0.75)), (self.cx + m, yy), SCHWARZ, schatten=False)
        # Tastennamen unter der Linie
        if self.namen:
            for s in range(self.n):
                if self.modus == "hero":
                    m, bw = self.spur_x(s, bt)
                    text_zeigen(ziel, self.namen[s], max(10, int(bw * 0.26)), (self.cx + m, yt + bw * 0.42),
                                heller(self.farbe(s), 0.85))
                    continue
                if self.modus == "barde":
                    m, bw = self.spur_x(s, bt)
                    if bw * 0.42 < 7:
                        continue
                    weiss = s in WEISSE_TASTEN
                    text_zeigen(ziel, self.namen[s], max(9, int(bw * 0.32)), (self.cx + m, yt + (bw * 0.5 if weiss else -bw * 0.2)),
                                TX2 if weiss else (120, 110, 100), schatten=False)
        self.flammen.schritt(dt, 400)
        self.flammen.zeichnen(ziel)
