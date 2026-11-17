// ZynSimple: PAD FX 1 und PAD FX 2 für den Pioneer DDJ-400 (in der Mixxx-Belegung nicht vorhanden).
// Wie in rekordbox: Pad gedrückt halten = Effekt an, loslassen = aus. Beide Decks gleich belegt.
//
//   PAD FX 1:  1 Echo · 2 Flanger · 3 Hall · 4 Phaser · 5 Roll ¼ · 6 Roll ⅛ · 7 Roll 1/16 · 8 Bremse
//   PAD FX 2:  1 Bitcrusher · 2 Tremolo · 3 Autopan · 4 Verzerrung · 5 Hochpass · 6 Tiefpass · 7 Rückwärts · 8 Spinback
//
// Effekte 1–4 laufen über Effekt-Einheit 4 (nur für die Pads). Die Reihenfolge der Effekte in Mixxx legt
// ZynSimple beim Start fest (effects.xml) – nur dann stimmen die Nummern. Sonst gehen nur Roll/Filter/Bremse.

var ZSPadFx = {};

// Nummer in der Mixxx-Effektliste (so schreibt sie dj-einrichten.py: EFFEKT_REIHE)
ZSPadFx.NR = { echo: 1, flanger: 2, reverb: 3, phaser: 4, bitcrusher: 5, tremolo: 6, autopan: 7, distortion: 8 };

ZSPadFx.FX1 = [
    { fx: "echo" }, { fx: "flanger" }, { fx: "reverb" }, { fx: "phaser" },
    { roll: "0.25" }, { roll: "0.125" }, { roll: "0.0625" }, { brems: true },
];
ZSPadFx.FX2 = [
    { fx: "bitcrusher" }, { fx: "tremolo" }, { fx: "autopan" }, { fx: "distortion" },
    { filter: 0.85 }, { filter: 0.15 }, { rueck: true }, { spin: true },
];

ZSPadFx.UNIT = "[EffectRack1_EffectUnit4]";
ZSPadFx.SLOT = "[EffectRack1_EffectUnit4_Effect1]";
ZSPadFx.aktiv = {};          // "status:note" → Eintrag, solange gedrückt

ZSPadFx.reiheOk = function() {
    return typeof ZynSimpleFxReihe !== "undefined" && ZynSimpleFxReihe === true;
};

ZSPadFx.init = function() {
    // Einheit 4 gehört den Pads: an, keinem Deck zugeordnet, Effekt aus
    engine.setValue(ZSPadFx.UNIT, "enabled", 1);
    engine.setValue(ZSPadFx.UNIT, "mix", 0.7);
    engine.setValue(ZSPadFx.UNIT, "group_[Channel1]_enable", 0);
    engine.setValue(ZSPadFx.UNIT, "group_[Channel2]_enable", 0);
    engine.setValue(ZSPadFx.SLOT, "enabled", 0);
};

ZSPadFx.pad = function(channel, control, value, status, group) {
    var liste = (control & 0xF0) === 0x10 ? ZSPadFx.FX1 : ZSPadFx.FX2;
    var e = liste[control & 0x07];
    var deck = (status & 0x0F) === 0x07 ? 1 : 2;      // 0x97 = Deck 1, 0x99 = Deck 2
    var g = "[Channel" + deck + "]";
    var an = value > 0;
    if (!e) { return; }
    midi.sendShortMsg(status, control, an ? 0x7F : 0x00);  // Pad leuchtet, solange gedrückt
    try {
        if (e.fx) {
            if (!ZSPadFx.reiheOk()) { return; }
            if (an) {
                engine.setValue(ZSPadFx.SLOT, "loaded_effect", ZSPadFx.NR[e.fx]);
                engine.setValue(ZSPadFx.UNIT, "group_[Channel1]_enable", deck === 1 ? 1 : 0);
                engine.setValue(ZSPadFx.UNIT, "group_[Channel2]_enable", deck === 2 ? 1 : 0);
                engine.setValue(ZSPadFx.UNIT, "enabled", 1);
                engine.setValue(ZSPadFx.SLOT, "enabled", 1);
            } else {
                engine.setValue(ZSPadFx.SLOT, "enabled", 0);
            }
        } else if (e.roll) {
            engine.setValue(g, "beatlooproll_" + e.roll + "_activate", an ? 1 : 0);
        } else if (e.brems) {
            engine.brake(deck, an);
        } else if (e.spin) {
            engine.spinback(deck, an);
        } else if (e.rueck) {
            engine.setValue(g, "reverseroll", an ? 1 : 0);
        } else if (e.filter) {
            engine.setValue("[QuickEffectRack1_" + g + "]", "super1", an ? e.filter : 0.5);
        }
    } catch (err) {
        print("ZSPadFx: " + err);
    }
};

ZSPadFx.shutdown = function() {
    engine.setValue(ZSPadFx.SLOT, "enabled", 0);
};
