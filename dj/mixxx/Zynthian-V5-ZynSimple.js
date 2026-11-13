// ZynSimple: Tasten und Drehregler des Zynthian V5 als Zusatz-Controller für Mixxx – mit Ebenen wie bei Barden Beats.
// Der DJ-Helfer schickt: Tasten als Note 1–24 (an/aus), Drehregler als CC 1–4 (relativ, 64 = Mitte).
// Zurück an den Helfer: Note n = LED-Farbe (0 aus, 1 glimmen, 2 gold, 3 rot, 4 grün, 5 gelb),
// CC 100/101 = Tempo × 10, CC 102 = Schlag, CC 103 = läuft, SysEx = Text für die Hinweisleiste.
// Befehle an Mixxx (vom Helfer, von ZynSimple oder vom Handy): CC 110/111 = Tempo von außen × 10 (TR-8S oder
// Zynthian geben den Takt vor), CC 112 = Bibliothek-Bereich wählen, CC 113 = gefundenen Titel in Deck 1/2 laden.
//
// EBENEN (MIXER wechselt, ALT + ◀ ▶ auch):
//   MISCHEN   R1 Titel wählen (drücken: Deck A laden) · R2 Kopfhörer: Vorhören ↔ Mix (drücken: Deck B laden)
//             R3 Filter Deck A (drücken: Mitte) · R4 Filter Deck B (drücken: Mitte)
//             F1–F4 Stems Deck A (ALT: Deck B) – ohne Stems: Sampler 1–4
//   EFFEKTE   R1 Effekt 1 Stärke (drücken: an/aus) · R2 Effekt 1 wählen (drücken: Ziel A → B → A+B)
//             R3 Effekt 2 Stärke (drücken: an/aus) · R4 Effekt 2 wählen (drücken: Ziel A → B → A+B)
//             F1–F4 Loop 4 · 8 · 16 Schläge · Loop aus (auf dem vorderen Deck)
//   HANDPAN   R1 Handpan-Lautstärke · R2 Handpan-Effekt (drücken: an/aus) · R3 Master · R4 Kopfhörer-Lautstärke
//             F1 Handpan an/aus · F2 Handpan-Effekt an/aus · F3 nächster Handpan-Effekt · F4 Durchsage (Talkover)
// IMMER
//   SEL       Titel in das Deck laden, das gerade frei ist          ▲ ▼  Titel · ◀ ▶ Bereich (ALT: Ebene)
//   PLAY      Deck A ▶/❚❚ (ALT: Deck B) REC  Set aufnehmen            PAD  Handpan im Mix an/aus (ALT: Auto-DJ)
//   ALT + ▲ ▼ Bewertung des laufenden Titels ★ +1 / −1 (ab ★★★★ in der Kiste „★ Favoriten“)
//   TEMPO     Tempo tippen (ALT: Sync)   CTRL Vorhören: A → B → aus  ZS3  große Bibliothek
//   STOP      Effekte und Filter aus (Panik)

var ZynV5 = {};
ZynV5.cfg = (typeof ZynV5Config !== "undefined") ? ZynV5Config : { autoRec: false, clock: true, handpanFx: true, folgen: false };
ZynV5.N = { MENU: 1, MIXER: 2, CTRL: 3, ZS3: 4, ALT: 5, TEMPO: 6, PAD: 7, F1: 8, REC: 9, STOP: 10, PLAY: 11, F2: 12,
    BACK: 13, UP: 14, SEL: 15, F3: 16, LEFT: 17, DOWN: 18, RIGHT: 19, F4: 20, DREH1: 21, DREH2: 22, DREH3: 23, DREH4: 24 };
ZynV5.F = [8, 12, 16, 20];
ZynV5.EBENEN = ["MISCHEN", "EFFEKTE", "HANDPAN"];
ZynV5.EBENE_FARBE = [2, 4, 3];          // MIXER-LED: Mischen gold, Effekte grün, Handpan rot
ZynV5.STEM_FARBE = [3, 2, 4, 5];        // Drums rot, Bass gold, Melodie grün, Vocals gelb
ZynV5.STEM_NAME = ["Drums", "Bass", "Melodie", "Vocals"];
ZynV5.LOOPS = [4, 8, 16];
ZynV5.HANDPAN_FX = "[EffectRack1_EffectUnit3]";
ZynV5.auxDa = function() { return ZynV5.hole("[Auxiliary1]", "input_configured") > 0; };
ZynV5.auxUm = function(key, text) {
    if (!ZynV5.auxDa()) { ZynV5.zeige("Handpan: kein Eingang in Mixxx eingerichtet (im Mischpult läuft die Handpan über den Zynthian)"); return 0; }
    var v = ZynV5.umschalten("[Auxiliary1]", key); ZynV5.zeige(text + (v ? " an" : " aus")); return v;
};
ZynV5.ebene = 0;
ZynV5.alt = false;
ZynV5.fuehrend = 0;
ZynV5.ziel = [0, 0];                    // Effekt 1/2: 0 = Deck A, 1 = Deck B, 2 = beide
ZynV5.verbindungen = [];
ZynV5.extMsb = 0;
ZynV5.extBpm = 0;
ZynV5.deckAlt = [null, {}, {}];         // zuletzt gesendeter Deck-Zustand (nur Änderungen schicken)
ZynV5.deckTakt = 0;

// ---------------------------------------------------------------------------------------------
// Grundlagen
// ---------------------------------------------------------------------------------------------
ZynV5.led = function(nr, code) { midi.sendShortMsg(0x90, nr, code); };
ZynV5.setze = function(g, k, v) { try { engine.setValue(g, k, v); } catch (e) { } };
ZynV5.hole = function(g, k) { try { return engine.getValue(g, k); } catch (e) { return 0; } };
ZynV5.umschalten = function(g, k) { ZynV5.setze(g, k, ZynV5.hole(g, k) ? 0 : 1); return ZynV5.hole(g, k); };
ZynV5.verbinde = function(g, k, fn) {
    try { var c = engine.makeConnection(g, k, fn); if (c) { c.trigger(); ZynV5.verbindungen.push(c); } } catch (e) { }
};
ZynV5.pz = function(v) { return Math.round(v * 100) + " %"; };

// Text an die Hinweisleiste (über den DJ-Helfer): jedes Zeichen als zwei 7-Bit-Bytes (Umlaute bleiben erhalten)
ZynV5.sage = function(art, text) {
    var s = art + "|" + text, d = [0xF0, 0x7D];
    for (var i = 0; i < s.length && i < 120; i++) { var c = s.charCodeAt(i); d.push((c >> 7) & 0x7F, c & 0x7F); }
    d.push(0xF7);
    try { midi.sendSysexMsg(d, d.length); } catch (e) { }
};
ZynV5.zeige = function(text) { ZynV5.sage("T", text); };
ZynV5.ebeneMelden = function() {
    ZynV5.sage("E", ZynV5.EBENEN[ZynV5.ebene] + "|" + (ZynV5.alt ? 1 : 0) + "|" + (ZynV5.hatStems(ZynV5.stemDeck()) ? 1 : 0));
};

ZynV5.stemDeck = function() { return ZynV5.alt ? 2 : 1; };
ZynV5.hatStems = function(deck) { return ZynV5.hole("[Channel" + deck + "]", "stem_count") > 0; };
ZynV5.vorne = function() { return ZynV5.fuehrend || 1; };

// ---------------------------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------------------------
ZynV5.init = function(id, debugging) {
    // Handpan/Mikro (Zynthian-Eingänge) in den Mix, mit eigener Effekt-Einheit 3
    // Handpan-Eingang nur anfassen, wenn Mixxx dafür wirklich ein Eingangsgerät hat – sonst öffnet Mixxx eine
    // Rückfrage („kein Eingabegerät für diesen Aux“), die am Zynthian niemand wegtippen kann
    if (ZynV5.cfg.handpanFx && ZynV5.auxDa()) {
        ZynV5.setze("[Auxiliary1]", "main_mix", 1);
        ZynV5.setze("[Auxiliary1]", "master", 1);
        ZynV5.setze("[EffectRack1_EffectUnit2]", "group_[Auxiliary1]_enable", 0);
        ZynV5.setze(ZynV5.HANDPAN_FX, "group_[Auxiliary1]_enable", 1);
    }
    // Effekt 1 auf Deck A, Effekt 2 auf Deck B – wie es die Hinweisleiste zeigt
    ZynV5.zielSetzen(0, 0);
    ZynV5.zielSetzen(1, 1);
    // LEDs
    ZynV5.F.forEach(function(nr, i) {
        ZynV5.verbinde("[Sampler" + (i + 1) + "]", "play_indicator", function() { ZynV5.fLeds(); });
        ZynV5.verbinde("[Sampler" + (i + 1) + "]", "track_loaded", function() { ZynV5.fLeds(); });
    });
    for (var dk = 1; dk <= 2; dk++) {
        ZynV5.verbinde("[Channel" + dk + "]", "stem_count", function() { ZynV5.fLeds(); ZynV5.ebeneMelden(); });
        ZynV5.verbinde("[Channel" + dk + "]", "loop_enabled", function() { ZynV5.fLeds(); });
        for (var st = 1; st <= 4; st++) {
            ZynV5.verbinde("[Channel" + dk + "_Stem" + st + "]", "mute", function() { ZynV5.fLeds(); });
        }
    }
    // PLAY-LED: grün = Deck A läuft (mit ALT: Deck B)
    ZynV5.verbinde("[Channel1]", "play", function() { ZynV5.playLed(); });
    ZynV5.verbinde("[Channel2]", "play", function() { ZynV5.playLed(); });
    ZynV5.verbinde("[Recording]", "status", function(v) { ZynV5.led(ZynV5.N.REC, v === 2 ? 3 : (v === 1 ? 5 : 1)); });
    ZynV5.verbinde("[Auxiliary1]", "main_mix", function(v) { ZynV5.led(ZynV5.N.PAD, v ? 2 : 1); ZynV5.fLeds(); });
    ZynV5.verbinde("[Channel1]", "pfl", function() { ZynV5.pflLed(); });
    ZynV5.verbinde("[Channel2]", "pfl", function() { ZynV5.pflLed(); });
    ZynV5.verbinde("[EffectRack1_EffectUnit1]", "enabled", function() { ZynV5.fLeds(); });
    ZynV5.verbinde("[EffectRack1_EffectUnit2]", "enabled", function() { ZynV5.fLeds(); });
    ZynV5.verbinde(ZynV5.HANDPAN_FX, "enabled", function() { ZynV5.fLeds(); });
    [ZynV5.N.TEMPO, ZynV5.N.UP, ZynV5.N.DOWN, ZynV5.N.LEFT, ZynV5.N.RIGHT, ZynV5.N.SEL, ZynV5.N.ZS3, ZynV5.N.ALT]
        .forEach(function(n) { ZynV5.led(n, 1); });
    ZynV5.led(ZynV5.N.MIXER, ZynV5.EBENE_FARBE[0]);
    // Takt für die TR-8S
    for (var d = 1; d <= Math.max(2, Math.min(4, ZynV5.hole("[Master]", "num_decks") || 2)); d++) {
        (function(deck) {
            ZynV5.verbinde("[Channel" + deck + "]", "beat_active", function(v) {
                if (v > 0 && deck === ZynV5.fuehrend && ZynV5.cfg.clock) { midi.sendShortMsg(0xB0, 102, 127); }
            });
        })(d);
    }
    // Takt kommt von außen (TR-8S oder Zynthian): neu geladene Titel laufen sofort im Takt mit
    if (ZynV5.cfg.folgen) {
        for (var s = 1; s <= 2; s++) {
            (function(deck) {
                ZynV5.verbinde("[Channel" + deck + "]", "track_loaded", function(v) {
                    if (v) { ZynV5.setze("[Channel" + deck + "]", "sync_enabled", 1); }
                });
            })(s);
        }
    }
    ZynV5.timer = engine.beginTimer(100, ZynV5.tempoSenden);
    ZynV5.deckTimer = engine.beginTimer(100, ZynV5.deckSenden);
    if (ZynV5.cfg.autoRec) {
        engine.beginTimer(5000, function() {
            if (!ZynV5.hole("[Recording]", "status")) { ZynV5.setze("[Recording]", "toggle_recording", 1); }
        }, true);
    }
    engine.beginTimer(1500, function() { ZynV5.ebeneMelden(); ZynV5.fLeds(); }, true);
};

ZynV5.shutdown = function() {
    for (var n = 1; n <= 24; n++) { ZynV5.led(n, 0); }
    midi.sendShortMsg(0xB0, 103, 0);
};

// ---------------------------------------------------------------------------------------------
// LEDs
// ---------------------------------------------------------------------------------------------
ZynV5.pflLed = function() {
    var a = ZynV5.hole("[Channel1]", "pfl"), b = ZynV5.hole("[Channel2]", "pfl");
    ZynV5.led(ZynV5.N.CTRL, a ? 2 : (b ? 4 : 1));
};

ZynV5.fLeds = function() {
    var i;
    if (ZynV5.ebene === 0) {
        var deck = ZynV5.stemDeck();
        if (ZynV5.hatStems(deck)) {
            var n = Math.min(4, ZynV5.hole("[Channel" + deck + "]", "stem_count"));
            for (i = 0; i < 4; i++) {
                if (i >= n) { ZynV5.led(ZynV5.F[i], 0); continue; }
                ZynV5.led(ZynV5.F[i], ZynV5.hole("[Channel" + deck + "_Stem" + (i + 1) + "]", "mute") ? 1 : ZynV5.STEM_FARBE[i]);
            }
        } else {
            for (i = 0; i < 4; i++) {
                var g = "[Sampler" + (i + 1) + "]";
                ZynV5.led(ZynV5.F[i], ZynV5.hole(g, "play_indicator") ? 2 : (ZynV5.hole(g, "track_loaded") ? 5 : 1));
            }
        }
    } else if (ZynV5.ebene === 1) {
        var dg = "[Channel" + ZynV5.vorne() + "]", an = ZynV5.hole(dg, "loop_enabled");
        for (i = 0; i < 3; i++) {
            ZynV5.led(ZynV5.F[i], an && Math.abs(ZynV5.hole(dg, "beatloop_size") - ZynV5.LOOPS[i]) < 0.01 ? 4 : 1);
        }
        ZynV5.led(ZynV5.F[3], an ? 3 : 1);
    } else {
        ZynV5.led(ZynV5.F[0], ZynV5.hole("[Auxiliary1]", "main_mix") ? 2 : 1);
        ZynV5.led(ZynV5.F[1], ZynV5.hole(ZynV5.HANDPAN_FX, "enabled") ? 4 : 1);
        ZynV5.led(ZynV5.F[2], 1);
        ZynV5.led(ZynV5.F[3], ZynV5.hole("[Auxiliary1]", "talkover") ? 3 : 1);
    }
};

// ---------------------------------------------------------------------------------------------
// Tempo/Takt für die TR-8S
// ---------------------------------------------------------------------------------------------
ZynV5.waehleDeck = function() {
    var best = 0, bestW = 0, xf = ZynV5.hole("[Master]", "crossfader");
    var decks = Math.max(2, Math.min(4, ZynV5.hole("[Master]", "num_decks") || 2));   // nur vorhandene Decks (sonst Log-Flut)
    for (var d = 1; d <= decks; d++) {
        var g = "[Channel" + d + "]";
        if (!ZynV5.hole(g, "play")) { continue; }
        var o = ZynV5.hole(g, "orientation");
        var w = ZynV5.hole(g, "volume") * (o === 0 ? Math.min(1, 1 - xf) : (o === 2 ? Math.min(1, 1 + xf) : 1));
        if (w > bestW) { bestW = w; best = d; }
    }
    return best;
};

ZynV5.tempoSenden = function() {
    var alt = ZynV5.fuehrend;
    ZynV5.fuehrend = ZynV5.waehleDeck();
    if (alt !== ZynV5.fuehrend && ZynV5.ebene === 1) { ZynV5.fLeds(); }
    if (!ZynV5.cfg.clock) { return; }
    if (!ZynV5.fuehrend) { midi.sendShortMsg(0xB0, 103, 0); return; }
    var v = Math.max(0, Math.min(16383, Math.round(ZynV5.hole("[Channel" + ZynV5.fuehrend + "]", "bpm") * 10)));
    midi.sendShortMsg(0xB0, 100, (v >> 7) & 0x7F);
    midi.sendShortMsg(0xB0, 101, v & 0x7F);
    midi.sendShortMsg(0xB0, 103, 127);
};

// ---------------------------------------------------------------------------------------------
// Effekte
// ---------------------------------------------------------------------------------------------
ZynV5.ZIEL_TEXT = ["Deck A", "Deck B", "Deck A + B"];
ZynV5.zielSetzen = function(e, z) {
    var u = "[EffectRack1_EffectUnit" + (e + 1) + "]";
    ZynV5.ziel[e] = z;
    ZynV5.setze(u, "group_[Channel1]_enable", z === 0 || z === 2 ? 1 : 0);
    ZynV5.setze(u, "group_[Channel2]_enable", z === 1 || z === 2 ? 1 : 0);
};

ZynV5.ebeneWechseln = function(schritt) {
    ZynV5.ebene = (ZynV5.ebene + schritt + ZynV5.EBENEN.length) % ZynV5.EBENEN.length;
    ZynV5.led(ZynV5.N.MIXER, ZynV5.EBENE_FARBE[ZynV5.ebene]);
    ZynV5.ebeneMelden();
    ZynV5.fLeds();
    ZynV5.zeige("Ebene: " + ["Mischen", "Effekte", "Handpan"][ZynV5.ebene]);
};

// ---------------------------------------------------------------------------------------------
// Tasten
// ---------------------------------------------------------------------------------------------
ZynV5.freiesDeck = function() {
    var a = ZynV5.hole("[Channel1]", "play"), b = ZynV5.hole("[Channel2]", "play");
    if (a && !b) { return 2; }
    if (b && !a) { return 1; }
    if (!ZynV5.hole("[Channel1]", "track_loaded")) { return 1; }
    if (!ZynV5.hole("[Channel2]", "track_loaded")) { return 2; }
    return 1;
};

ZynV5.taste = function(channel, control, value, status, group) {
    var an = (status & 0xF0) === 0x90 && value > 0, N = ZynV5.N;
    if (control === N.ALT) {
        ZynV5.alt = an;
        ZynV5.led(N.ALT, an ? 2 : 1);
        ZynV5.fLeds();
        ZynV5.ebeneMelden();
        return;
    }
    if (!an) { return; }
    var e, u, v, f, g;
    switch (control) {
    // ---- Regler drücken
    case N.DREH1:
        if (ZynV5.ebene === 0) { ZynV5.setze("[Channel1]", "LoadSelectedTrack", 1); ZynV5.zeige("Titel → Deck A"); }
        else if (ZynV5.ebene === 1) { v = ZynV5.umschalten("[EffectRack1_EffectUnit1]", "enabled"); ZynV5.zeige("Effekt 1 " + (v ? "an" : "aus")); }
        else { ZynV5.setze("[Auxiliary1]", "pregain", 1); ZynV5.zeige("Handpan-Lautstärke: normal"); }
        return;
    case N.DREH2:
        if (ZynV5.ebene === 0) { ZynV5.setze("[Channel2]", "LoadSelectedTrack", 1); ZynV5.zeige("Titel → Deck B"); }
        else if (ZynV5.ebene === 1) { ZynV5.zielSetzen(0, (ZynV5.ziel[0] + 1) % 3); ZynV5.zeige("Effekt 1 wirkt auf " + ZynV5.ZIEL_TEXT[ZynV5.ziel[0]]); }
        else { v = ZynV5.umschalten(ZynV5.HANDPAN_FX, "enabled"); ZynV5.zeige("Handpan-Effekt " + (v ? "an" : "aus")); }
        return;
    case N.DREH3:
        if (ZynV5.ebene === 0) { ZynV5.setze("[QuickEffectRack1_[Channel1]]", "super1", 0.5); ZynV5.zeige("Filter A: Mitte (aus)"); }
        else if (ZynV5.ebene === 1) { v = ZynV5.umschalten("[EffectRack1_EffectUnit2]", "enabled"); ZynV5.zeige("Effekt 2 " + (v ? "an" : "aus")); }
        else { ZynV5.setze("[Master]", "gain", 1); ZynV5.zeige("Master: normal"); }
        return;
    case N.DREH4:
        if (ZynV5.ebene === 0) { ZynV5.setze("[QuickEffectRack1_[Channel2]]", "super1", 0.5); ZynV5.zeige("Filter B: Mitte (aus)"); }
        else if (ZynV5.ebene === 1) { ZynV5.zielSetzen(1, (ZynV5.ziel[1] + 1) % 3); ZynV5.zeige("Effekt 2 wirkt auf " + ZynV5.ZIEL_TEXT[ZynV5.ziel[1]]); }
        else { ZynV5.setze("[Master]", "headGain", 1); ZynV5.zeige("Kopfhörer: normal"); }
        return;
    // ---- immer gleich
    case N.MIXER: ZynV5.ebeneWechseln(1); return;
    case N.LEFT: if (ZynV5.alt) { ZynV5.ebeneWechseln(-1); } else { ZynV5.setze("[Library]", "MoveFocusBackward", 1); } return;
    case N.RIGHT: if (ZynV5.alt) { ZynV5.ebeneWechseln(1); } else { ZynV5.setze("[Library]", "MoveFocusForward", 1); } return;
    case N.UP:
    case N.DOWN:
        if (ZynV5.alt) {
            g = "[Channel" + ZynV5.vorne() + "]";
            if (!ZynV5.hole(g, "track_loaded")) { ZynV5.zeige("Erst einen Titel laden – dann ALT + ▲ ▼ = Sterne"); return; }
            ZynV5.setze(g, control === N.UP ? "stars_up" : "stars_down", 1);
            ZynV5.zeige((control === N.UP ? "★ +1" : "★ −1") + " für Deck " + (ZynV5.vorne() === 1 ? "A" : "B") +
                " · ab ★★★★ in „★ Favoriten“");
            return;
        }
        ZynV5.setze("[Library]", control === N.UP ? "MoveUp" : "MoveDown", 1);
        return;
    case N.SEL:
        f = ZynV5.freiesDeck();
        ZynV5.setze("[Channel" + f + "]", "LoadSelectedTrack", 1);
        ZynV5.zeige("Titel → Deck " + (f === 1 ? "A" : "B"));
        return;
    case N.PLAY:
        // PLAY = Deck A starten/stoppen · ALT + PLAY = Deck B
        f = ZynV5.alt ? 2 : 1;
        g = "[Channel" + f + "]";
        if (!ZynV5.hole(g, "track_loaded")) { ZynV5.zeige("Deck " + (f === 1 ? "A" : "B") + " ist leer – erst einen Titel laden (SEL)"); return; }
        v = ZynV5.umschalten(g, "play");
        ZynV5.zeige((v ? "▶ " : "❚❚ ") + "Deck " + (f === 1 ? "A" : "B") + (f === 1 ? "  ·  ALT + PLAY = Deck B" : ""));
        return;
    case N.REC: ZynV5.setze("[Recording]", "toggle_recording", 1); ZynV5.zeige("Aufnahme umgeschaltet (REC-LED: rot = läuft)"); return;
    case N.TEMPO:
        g = "[Channel" + ZynV5.vorne() + "]";
        if (ZynV5.alt) { ZynV5.setze(g, "beatsync", 1); ZynV5.zeige("Sync: Deck " + (ZynV5.vorne() === 1 ? "A" : "B") + " im Takt"); }
        else { ZynV5.setze(g, "bpm_tap", 1); ZynV5.zeige("Tempo tippen: " + ZynV5.hole(g, "bpm").toFixed(1) + " BPM"); }
        return;
    case N.PAD:
        if (ZynV5.alt) {                                   // ALT + PAD = Auto-DJ
            v = ZynV5.umschalten("[AutoDJ]", "enabled");
            ZynV5.zeige(v ? "Auto-DJ an – mischt selbst weiter" : "Auto-DJ aus");
            return;
        }
        ZynV5.auxUm("main_mix", "Handpan im Mix"); return;
    case N.CTRL:
        var a = ZynV5.hole("[Channel1]", "pfl"), b = ZynV5.hole("[Channel2]", "pfl");
        var neu = a ? 2 : (b ? 0 : 1);           // A → B → aus → A
        ZynV5.setze("[Channel1]", "pfl", neu === 1 ? 1 : 0);
        ZynV5.setze("[Channel2]", "pfl", neu === 2 ? 1 : 0);
        ZynV5.zeige("Vorhören im Kopfhörer: " + ["aus", "Deck A", "Deck B"][neu]);
        return;
    case N.ZS3: ZynV5.umschalten("[Skin]", "show_maximized_library"); return;
    case N.STOP:
        for (e = 1; e <= 3; e++) { ZynV5.setze("[EffectRack1_EffectUnit" + e + "]", "enabled", 0); }
        ZynV5.setze("[QuickEffectRack1_[Channel1]]", "super1", 0.5);
        ZynV5.setze("[QuickEffectRack1_[Channel2]]", "super1", 0.5);
        ZynV5.zeige("Panik: alle Effekte und Filter aus");
        return;
    }
    // ---- F1–F4 je nach Ebene
    f = ZynV5.F.indexOf(control);
    if (f < 0) { return; }
    if (ZynV5.ebene === 0) {
        var deck = ZynV5.stemDeck();
        if (ZynV5.hatStems(deck)) {
            v = ZynV5.umschalten("[Channel" + deck + "_Stem" + (f + 1) + "]", "mute");
            ZynV5.zeige((deck === 1 ? "A" : "B") + ": " + ZynV5.STEM_NAME[f] + (v ? " stumm" : " an"));
        } else {
            g = "[Sampler" + (f + 1) + "]";
            if (ZynV5.hole(g, "play")) { ZynV5.setze(g, "cue_gotoandstop", 1); } else { ZynV5.setze(g, "cue_gotoandplay", 1); }
        }
    } else if (ZynV5.ebene === 1) {
        g = "[Channel" + ZynV5.vorne() + "]";
        if (f < 3) {
            ZynV5.setze(g, "beatloop_" + ZynV5.LOOPS[f] + "_toggle", 1);
            ZynV5.zeige("Loop " + ZynV5.LOOPS[f] + " Schläge auf Deck " + (ZynV5.vorne() === 1 ? "A" : "B"));
        } else if (ZynV5.hole(g, "loop_enabled")) {
            ZynV5.setze(g, "reloop_toggle", 1);
            ZynV5.zeige("Loop aus");
        }
        ZynV5.fLeds();
    } else {
        if (f === 0) { ZynV5.auxUm("main_mix", "Handpan im Mix"); }
        else if (f === 1) { v = ZynV5.umschalten(ZynV5.HANDPAN_FX, "enabled"); ZynV5.zeige("Handpan-Effekt " + (v ? "an" : "aus")); }
        else if (f === 2) { ZynV5.setze(ZynV5.HANDPAN_FX.replace("]", "_Effect1]"), "effect_selector", 1); ZynV5.zeige("Nächster Handpan-Effekt"); }
        else { ZynV5.auxUm("talkover", "Durchsage (Talkover)"); }
        ZynV5.fLeds();
    }
};

// ---------------------------------------------------------------------------------------------
// Regler
// ---------------------------------------------------------------------------------------------
ZynV5.drehen = function(g, k, d, min, max, schritt, name, alsPz) {
    var v = Math.max(min, Math.min(max, ZynV5.hole(g, k) + d * schritt));
    ZynV5.setze(g, k, v);
    ZynV5.zeige(name + ": " + (alsPz === false ? v.toFixed(2) : ZynV5.pz((v - min) / (max - min))));
};

ZynV5.regler = function(channel, control, value, status, group) {
    var d = value - 64, fein = ZynV5.alt ? 0.25 : 1;
    if (ZynV5.ebene === 0) {
        switch (control) {
        case 1: ZynV5.setze("[Library]", "MoveVertical", ZynV5.alt ? d * 10 : d); return;
        case 2: ZynV5.drehen("[Master]", "headMix", d, -1, 1, 0.05 * fein, "Kopfhörer Vorhören ↔ Mix"); return;
        case 3: ZynV5.drehen("[QuickEffectRack1_[Channel1]]", "super1", d, 0, 1, 0.02 * fein, "Filter A (Mitte = aus)"); return;
        case 4: ZynV5.drehen("[QuickEffectRack1_[Channel2]]", "super1", d, 0, 1, 0.02 * fein, "Filter B (Mitte = aus)"); return;
        }
    } else if (ZynV5.ebene === 1) {
        switch (control) {
        case 1: ZynV5.drehen("[EffectRack1_EffectUnit1]", "super1", d, 0, 1, 0.02 * fein, "Effekt 1 Stärke"); return;
        case 2: ZynV5.setze("[EffectRack1_EffectUnit1_Effect1]", "effect_selector", d > 0 ? 1 : -1); ZynV5.zeige("Effekt 1: anderer Effekt (Name oben im Bild)"); return;
        case 3: ZynV5.drehen("[EffectRack1_EffectUnit2]", "super1", d, 0, 1, 0.02 * fein, "Effekt 2 Stärke"); return;
        case 4: ZynV5.setze("[EffectRack1_EffectUnit2_Effect1]", "effect_selector", d > 0 ? 1 : -1); ZynV5.zeige("Effekt 2: anderer Effekt (Name oben im Bild)"); return;
        }
    } else {
        switch (control) {
        case 1: ZynV5.drehen("[Auxiliary1]", "pregain", d, 0, 4, 0.05 * fein, "Handpan-Lautstärke"); return;
        case 2: ZynV5.drehen(ZynV5.HANDPAN_FX, "super1", d, 0, 1, 0.02 * fein, "Handpan-Effekt"); return;
        case 3: ZynV5.drehen("[Master]", "gain", d, 0, 5, 0.05 * fein, "Master-Lautstärke"); return;
        case 4: ZynV5.drehen("[Master]", "headGain", d, 0, 5, 0.05 * fein, "Kopfhörer-Lautstärke"); return;
        }
    }
};

// ---------------------------------------------------------------------------------------------
// Befehle von außen (DJ-Helfer, ZynSimple im Hybrid-Modus, Handy-Bibliothek)
// ---------------------------------------------------------------------------------------------
ZynV5.befehl = function(channel, control, value, status, group) {
    if (control === 110) { ZynV5.extMsb = value; return; }
    if (control === 111) {
        var bpm = ((ZynV5.extMsb << 7) | value) / 10;
        if (bpm < 30 || bpm > 300) { return; }
        ZynV5.setze("[InternalClock]", "bpm", bpm);
        if (ZynV5.hole("[InternalClock]", "sync_leader") !== 2) { ZynV5.setze("[InternalClock]", "sync_leader", 2); }
        if (Math.abs(bpm - ZynV5.extBpm) >= 0.5) { ZynV5.zeige("Takt von außen: " + bpm.toFixed(1) + " BPM · SYNC-Decks folgen"); }
        ZynV5.extBpm = bpm;
        return;
    }
    if (control === 112) { ZynV5.setze("[Library]", "focused_widget", value); return; }
    if (control === 114) {
        var gp = "[Channel" + (value === 2 ? 2 : 1) + "]";
        if (ZynV5.hole(gp, "track_loaded")) { ZynV5.setze(gp, "play", ZynV5.hole(gp, "play") ? 0 : 1); }
        return;
    }
    if (control === 113) {
        var deck = value === 2 ? 2 : 1;
        ZynV5.setze("[Library]", "focused_widget", 3);
        ZynV5.setze("[Library]", "MoveDown", 1);
        ZynV5.setze("[Library]", "MoveVertical", -10000);
        engine.beginTimer(200, function() {
            ZynV5.setze("[Channel" + deck + "]", "LoadSelectedTrack", 1);
            ZynV5.zeige("Vom Handy → Deck " + (deck === 1 ? "A" : "B"));
        }, true);
    }
};

// ---------------------------------------------------------------------------------------------
// Deck-Zustand für ZynSimple (DJ + Instrumente): Kanal 2 = Deck A, Kanal 3 = Deck B
// CC 20 geladen · 21 läuft · 22/23 Länge in s · 24/25 Tempo × 10 · 26/27 Position (0–16383) · 28 Tonart (Mixxx 1–24)
// ---------------------------------------------------------------------------------------------
ZynV5.deckSenden = function() {
    ZynV5.deckTakt = (ZynV5.deckTakt + 1) % 5;
    for (var d = 1; d <= 2; d++) {
        var g = "[Channel" + d + "]", st = 0xB0 + d, alt = ZynV5.deckAlt[d];
        var neu = {
            geladen: ZynV5.hole(g, "track_loaded") ? 1 : 0,
            laeuft: ZynV5.hole(g, "play") ? 1 : 0,
            dauer: Math.max(0, Math.min(16383, Math.round(ZynV5.hole(g, "duration") || 0))),
            bpm: Math.max(0, Math.min(16383, Math.round((ZynV5.hole(g, "bpm") || 0) * 10))),
            pos: Math.max(0, Math.min(16383, Math.round((ZynV5.hole(g, "playposition") || 0) * 16383))),
            key: Math.max(0, Math.min(24, Math.round(ZynV5.hole(g, "key") || 0)))
        };
        if (neu.geladen !== alt.geladen) { midi.sendShortMsg(st, 20, neu.geladen); }
        if (neu.laeuft !== alt.laeuft) { midi.sendShortMsg(st, 21, neu.laeuft); }
        if (neu.dauer !== alt.dauer) { midi.sendShortMsg(st, 22, neu.dauer >> 7); midi.sendShortMsg(st, 23, neu.dauer & 0x7F); }
        if (neu.bpm !== alt.bpm) { midi.sendShortMsg(st, 24, neu.bpm >> 7); midi.sendShortMsg(st, 25, neu.bpm & 0x7F); }
        if (neu.key !== alt.key) { midi.sendShortMsg(st, 28, neu.key); }
        if (ZynV5.deckTakt === 0 && neu.pos !== alt.pos) { midi.sendShortMsg(st, 26, neu.pos >> 7); midi.sendShortMsg(st, 27, neu.pos & 0x7F); }
        else { neu.pos = alt.pos; }
        ZynV5.deckAlt[d] = neu;
    }
};

ZynV5.playLed = function() {
    ZynV5.led(ZynV5.N.PLAY, ZynV5.hole("[Channel1]", "play") ? 4 : (ZynV5.hole("[Channel2]", "play") ? 2 : 1));
};
