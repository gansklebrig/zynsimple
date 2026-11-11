// ZynSimple: Tasten und Drehregler des Zynthian V5 als Zusatz-Controller für Mixxx.
// Der DJ-Helfer schickt: Tasten als Note 1–24 (an/aus), Drehregler als CC 1–4 (relativ, 64 = Mitte).
// Zurück an den Helfer: Note n mit Farbcode (0 aus, 1 glimmen, 2 gold, 3 rot, 4 grün, 5 gelb),
// CC 100/101 = Tempo × 10, CC 102 = Schlag, CC 103 = läuft.
//
//  Regler 1  Bibliothek blättern        · drücken: Track in Deck 1 laden
//  Regler 2  Bereich wechseln (Liste/Seitenleiste) · drücken: Track in Deck 2 laden
//  Regler 3  Effekt 1 (Stärke)          · drücken: Effekt 1 an/aus
//  Regler 4  Effekt 2 – Handpan (Stärke)· drücken: Effekt 2 an/aus
//  F1–F4     Stem-Track auf Deck A: Drums · Bass · Melodie · Vocals stumm/an (ALT halten: Deck B)
//            ohne Stems: Sampler 1–4 abspielen / stoppen
//  PLAY      Auto-DJ an/aus             REC   Set-Aufnahme an/aus
//  TEMPO     Tempo tippen (führendes Deck)
//  PAD       Handpan/Mikro im Mix an/aus
//  MIXER     Vorhören Deck 1            CTRL  Vorhören Deck 2
//  ZS3       große Bibliothek an/aus
//  ▲ ▼       Liste hoch/runter · ◀ ▶ Bereich wechseln · SEL öffnen/laden

var ZynV5 = {};
ZynV5.cfg = (typeof ZynV5Config !== "undefined") ? ZynV5Config : { autoRec: false, clock: true, handpanFx: true };
ZynV5.N = { MENU: 1, MIXER: 2, CTRL: 3, ZS3: 4, ALT: 5, TEMPO: 6, PAD: 7, F1: 8, REC: 9, STOP: 10, PLAY: 11, F2: 12,
    BACK: 13, UP: 14, SEL: 15, F3: 16, LEFT: 17, DOWN: 18, RIGHT: 19, F4: 20, DREH1: 21, DREH2: 22, DREH3: 23, DREH4: 24 };
ZynV5.F = [8, 12, 16, 20];
ZynV5.verbindungen = [];
ZynV5.fuehrend = 0;
ZynV5.alt = false;
// LED-Farbe je Stem, wenn hörbar (Drums rot, Bass gold, Melodie grün, Vocals gelb) – stumm: glimmen
ZynV5.STEM_FARBE = [3, 2, 4, 5];

ZynV5.stemDeck = function() { return ZynV5.alt ? 2 : 1; };
ZynV5.hatStems = function(deck) {
    try { return engine.getValue("[Channel" + deck + "]", "stem_count") > 0; } catch (e) { return false; }
};
ZynV5.fLeds = function() {
    var deck = ZynV5.stemDeck();
    if (ZynV5.hatStems(deck)) {
        var n = Math.min(4, engine.getValue("[Channel" + deck + "]", "stem_count"));
        for (var i = 0; i < 4; i++) {
            if (i >= n) { ZynV5.led(ZynV5.F[i], 0); continue; }
            var stumm = engine.getValue("[Channel" + deck + "_Stem" + (i + 1) + "]", "mute");
            ZynV5.led(ZynV5.F[i], stumm ? 1 : ZynV5.STEM_FARBE[i]);
        }
    } else {
        for (var k = 0; k < 4; k++) { ZynV5.samplerLed(k); }
    }
};

ZynV5.led = function(nr, code) { midi.sendShortMsg(0x90, nr, code); };

ZynV5.setze = function(group, key, value) {
    try { engine.setValue(group, key, value); } catch (e) { /* Schlüssel gibt es in dieser Mixxx-Version nicht */ }
};

ZynV5.verbinde = function(group, key, fn) {
    try {
        var c = engine.makeConnection(group, key, fn);
        if (c) { c.trigger(); ZynV5.verbindungen.push(c); }
    } catch (e) { }
};

ZynV5.init = function(id, debugging) {
    // Handpan/Mikro (Zynthian-Eingänge) in den Mix, mit Effekt-Einheit 2
    if (ZynV5.cfg.handpanFx) {
        ZynV5.setze("[Auxiliary1]", "main_mix", 1);
        ZynV5.setze("[Auxiliary1]", "master", 1);
        ZynV5.setze("[EffectRack1_EffectUnit2]", "group_[Auxiliary1]_enable", 1);
    }
    // LEDs: Sampler, Auto-DJ, Aufnahme, Handpan, Vorhören
    ZynV5.F.forEach(function(nr, i) {
        var g = "[Sampler" + (i + 1) + "]";
        ZynV5.verbinde(g, "play_indicator", function() { ZynV5.fLeds(); });
        ZynV5.verbinde(g, "track_loaded", function() { ZynV5.fLeds(); });
    });
    // Stems (Mixxx 2.6): LEDs folgen stumm/an und dem geladenen Track
    for (var dk = 1; dk <= 2; dk++) {
        ZynV5.verbinde("[Channel" + dk + "]", "stem_count", function() { ZynV5.fLeds(); });
        for (var st = 1; st <= 4; st++) {
            ZynV5.verbinde("[Channel" + dk + "_Stem" + st + "]", "mute", function() { ZynV5.fLeds(); });
        }
    }
    ZynV5.verbinde("[AutoDJ]", "enabled", function(v) { ZynV5.led(ZynV5.N.PLAY, v ? 4 : 1); });
    ZynV5.verbinde("[Recording]", "status", function(v) { ZynV5.led(ZynV5.N.REC, v === 2 ? 3 : (v === 1 ? 5 : 1)); });
    ZynV5.verbinde("[Auxiliary1]", "main_mix", function(v) { ZynV5.led(ZynV5.N.PAD, v ? 2 : 1); });
    ZynV5.verbinde("[Channel1]", "pfl", function(v) { ZynV5.led(ZynV5.N.MIXER, v ? 4 : 1); });
    ZynV5.verbinde("[Channel2]", "pfl", function(v) { ZynV5.led(ZynV5.N.CTRL, v ? 4 : 1); });
    ZynV5.verbinde("[EffectRack1_EffectUnit1]", "enabled", function(v) { ZynV5.led(ZynV5.N.ZS3, 1); });
    [ZynV5.N.TEMPO, ZynV5.N.UP, ZynV5.N.DOWN, ZynV5.N.LEFT, ZynV5.N.RIGHT, ZynV5.N.SEL].forEach(function(n) { ZynV5.led(n, 1); });
    // Takt für die TR-8S: Schläge der Decks
    for (var d = 1; d <= 4; d++) {
        (function(deck) {
            ZynV5.verbinde("[Channel" + deck + "]", "beat_active", function(v) {
                if (v > 0 && deck === ZynV5.fuehrend && ZynV5.cfg.clock) { midi.sendShortMsg(0xB0, 102, 127); }
            });
        })(d);
    }
    ZynV5.timer = engine.beginTimer(100, ZynV5.tempoSenden);
    // Set automatisch aufnehmen
    if (ZynV5.cfg.autoRec) {
        engine.beginTimer(5000, function() {
            if (!engine.getValue("[Recording]", "status")) { engine.setValue("[Recording]", "toggle_recording", 1); }
        }, true);
    }
};

ZynV5.shutdown = function() {
    for (var n = 1; n <= 24; n++) { ZynV5.led(n, 0); }
    midi.sendShortMsg(0xB0, 103, 0);
};

ZynV5.samplerLed = function(i) {
    var g = "[Sampler" + (i + 1) + "]";
    var code = engine.getValue(g, "play_indicator") ? 2 : (engine.getValue(g, "track_loaded") ? 5 : 1);
    ZynV5.led(ZynV5.F[i], code);
};

// Welches Deck ist „vorne“? Das, das läuft und am lautesten im Mix ist.
ZynV5.waehleDeck = function() {
    var best = 0, bestW = 0;
    var xf = engine.getValue("[Master]", "crossfader");
    for (var d = 1; d <= 4; d++) {
        var g = "[Channel" + d + "]";
        if (!engine.getValue(g, "play")) { continue; }
        var o = engine.getValue(g, "orientation");
        var w = engine.getValue(g, "volume") * (o === 0 ? Math.min(1, 1 - xf) : (o === 2 ? Math.min(1, 1 + xf) : 1));
        if (w > bestW) { bestW = w; best = d; }
    }
    return best;
};

ZynV5.tempoSenden = function() {
    ZynV5.fuehrend = ZynV5.waehleDeck();
    if (!ZynV5.cfg.clock) { return; }
    if (!ZynV5.fuehrend) { midi.sendShortMsg(0xB0, 103, 0); return; }
    var bpm = engine.getValue("[Channel" + ZynV5.fuehrend + "]", "bpm");
    var v = Math.max(0, Math.min(16383, Math.round(bpm * 10)));
    midi.sendShortMsg(0xB0, 100, (v >> 7) & 0x7F);
    midi.sendShortMsg(0xB0, 101, v & 0x7F);
    midi.sendShortMsg(0xB0, 103, 127);
};

ZynV5.umschalten = function(group, key) { engine.setValue(group, key, engine.getValue(group, key) ? 0 : 1); };

ZynV5.taste = function(channel, control, value, status, group) {
    var an = (status & 0xF0) === 0x90 && value > 0;
    if (control === ZynV5.N.ALT) {   // ALT halten: F1–F4 wirken auf Deck B
        ZynV5.alt = an;
        ZynV5.led(ZynV5.N.ALT, an ? 2 : 1);
        ZynV5.fLeds();
        return;
    }
    if (!an) { return; }
    var N = ZynV5.N;
    switch (control) {
    case N.DREH1: engine.setValue("[Channel1]", "LoadSelectedTrack", 1); return;
    case N.DREH2: engine.setValue("[Channel2]", "LoadSelectedTrack", 1); return;
    case N.DREH3: ZynV5.umschalten("[EffectRack1_EffectUnit1]", "enabled"); return;
    case N.DREH4: ZynV5.umschalten("[EffectRack1_EffectUnit2]", "enabled"); return;
    case N.PLAY: ZynV5.umschalten("[AutoDJ]", "enabled"); return;
    case N.REC: engine.setValue("[Recording]", "toggle_recording", 1); return;
    case N.TEMPO: if (ZynV5.fuehrend) { engine.setValue("[Channel" + ZynV5.fuehrend + "]", "bpm_tap", 1); } return;
    case N.PAD:
        ZynV5.umschalten("[Auxiliary1]", "main_mix");
        return;
    case N.MIXER: ZynV5.umschalten("[Channel1]", "pfl"); return;
    case N.CTRL: ZynV5.umschalten("[Channel2]", "pfl"); return;
    case N.ZS3: ZynV5.umschalten("[Skin]", "show_maximized_library"); return;
    case N.UP: engine.setValue("[Library]", "MoveUp", 1); return;
    case N.DOWN: engine.setValue("[Library]", "MoveDown", 1); return;
    case N.LEFT: engine.setValue("[Library]", "MoveFocusBackward", 1); return;
    case N.RIGHT: engine.setValue("[Library]", "MoveFocusForward", 1); return;
    case N.SEL: engine.setValue("[Library]", "GoToItem", 1); return;
    }
    var f = ZynV5.F.indexOf(control);
    if (f >= 0 && ZynV5.hatStems(ZynV5.stemDeck())) {
        var sg = "[Channel" + ZynV5.stemDeck() + "_Stem" + (f + 1) + "]";
        ZynV5.umschalten(sg, "mute");
        return;
    }
    if (f >= 0) {
        var g = "[Sampler" + (f + 1) + "]";
        if (engine.getValue(g, "play")) { engine.setValue(g, "cue_gotoandstop", 1); } else { engine.setValue(g, "cue_gotoandplay", 1); }
    }
};

ZynV5.regler = function(channel, control, value, status, group) {
    var d = value - 64;
    switch (control) {
    case 1: engine.setValue("[Library]", "MoveVertical", d); break;
    case 2: engine.setValue("[Library]", "MoveFocus", d > 0 ? 1 : -1); break;
    case 3:
        engine.setValue("[EffectRack1_EffectUnit1]", "super1",
            Math.max(0, Math.min(1, engine.getValue("[EffectRack1_EffectUnit1]", "super1") + d * 0.02)));
        break;
    case 4:
        engine.setValue("[EffectRack1_EffectUnit2]", "super1",
            Math.max(0, Math.min(1, engine.getValue("[EffectRack1_EffectUnit2]", "super1") + d * 0.02)));
        break;
    }
};
