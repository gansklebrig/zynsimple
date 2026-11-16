"""Musik-Prüfung der Bard-Hero-Lieder: Taktstriche, Tonumfang, Notendichte und Töne, die mit dem Akkord reiben.

Aufruf:  python3 tests/lieder_pruefen.py [lied …] [-v]     Rückgabe 1 bei echten Fehlern (Aufbau), Hinweise sonst nur gezeigt.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
SPIEL = os.path.join(os.path.dirname(HIER), "spiel")
sys.path[:0] = [SPIEL, os.path.join(SPIEL, "lieder")]
import komponist  # noqa: E402
import lieder  # noqa: E402

LAUT = "-v" in sys.argv
nur = [a for a in sys.argv[1:] if not a.startswith("-")]
fehler = 0
for name in lieder.REIHENFOLGE:
    if nur and name not in nur:
        continue
    try:
        L = lieder.lied(name)
    except Exception as e:
        print(f"✗ {name}: {e}")
        fehler += 1
        continue
    leiter = komponist.TONLEITERN[L.tonleiter]
    g = komponist.tonklasse(L.tonart.rstrip("m"))
    hinweise = []
    for teil in (L.lead, L.bass):
        sp = L.spuren[teil]
        noten = sorted(sp.noten)
        tiefst = min(n for _, _, n, _ in noten)
        hoechst = max(n for _, _, n, _ in noten)
        reibt = 0
        for t, d, n, s in noten:
            akk = None
            for at, al, a in L.akkord_log:
                if at <= t < at + al:
                    akk = a
                    break
            if akk is None:
                continue
            pc = n % 12
            stark = (t % L.takt_ticks) % (komponist.PPQ * (2 if L.nenner == 4 else 1)) == 0
            if pc in akk.toene():
                continue
            halbton = any(min((pc - x) % 12, (x - pc) % 12) == 1 for x in akk.toene())
            if stark and halbton and d >= komponist.PPQ:
                reibt += 1
                if LAUT:
                    takt = t // L.takt_ticks + 1
                    hinweise.append(f"   {teil}: Takt {takt} {komponist.notenname(n)}{n // 12 - 1} reibt an {akk.text}")
        dichte = len(noten) / L.sekunden(L.pos)
        print(f"{'✓'} {L.titel:<26} {teil:<5} {len(noten):4} Noten  {dichte:4.1f}/s  "
              f"{komponist.notenname(tiefst)}{tiefst // 12 - 1}–{komponist.notenname(hoechst)}{hoechst // 12 - 1}"
              f"  reibt: {reibt}")
    print(f"   {L.sekunden(L.pos) // 60:.0f}:{L.sekunden(L.pos) % 60:02.0f} min · {L.bpm} BPM · "
          f"{len(L.abschnitte)} Abschnitte · Tonart {L.tonart} {L.tonleiter}")
    for h in hinweise[:40]:
        print(h)
sys.exit(1 if fehler else 0)
