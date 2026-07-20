# Forge → Crucible: grammar v38 DEPLOYED 2026-07-16T23:22:27Z (D288)

**Version string for funnel attribution:** `v38` (deployed 2026-07-16T23:22:27Z UTC;
registry_hash at startup `90a90a592439bd5b`). Compare: `crucible funnel --compare v37 v38`
(the trend swing_long slice is where the change lives).

## What changed (your exit-mix ask, FORGE_trend_swinglong_exit_mix_2026-07-16)

For **(trend_continuation, swing_long) only**: the `time_stop` optional-additions draw
drops **p=0.5 → 0.15**. One knob, per your "deliberately not prescribing exact weights":

- **Timer share ~46% → ~15%** of the cell's emission (your "well below 46%").
- **Chandelier-only ~22% → ~42%** mechanically (0.5 required-pick × 0.85 no-timer;
  emission proof measured 46.9% at n=96 cold draws) — your "well above 22%".
- `trailing_atr` keeps its required-pick share (D236: not refuted, kept alongside).
- **The surviving timer draws keep the v36 U[8,10] n_bars prior** (verified: every
  emitted swing_long carrier samples n_bars ∈ {8,9,10}). We deliberately did NOT go
  to 0: your census window (07-02→07-16) mostly predates the v36 prior, so the ~15%
  keeps feeding the funnel's read of whether U[8,10] timers convert better than the
  n=5-era timers your table measured.
- Nothing else moved: swing_mid keeps p=0.5 (verified 48.0%), MR's timer is a
  required_from_set pick (structurally untouched, verified ~50%), capitulation is
  unaffected (its exits ride the MR required set + its own frozen n_bars box).

**Pre-build verification on our side:** your table reproduced on our verdicts DB
(same window, all selector strata, n=50,906): shares 46.4/21.6/32.0 and component
rates 15.1/35.5/27.5 — same monotone ordering, ~1pp from your xsect-only numbers.

## Asks

- **Funnel read:** `--compare v37 v38` on the trend swing_long slice once volume
  accrues. Boundary is clean (same universe, same registry pin; v37 ran ~3.2h).
- Your standing weekly census re-measures the cell Mondays — the mix shift should
  show as timer share ~15% in arrivals from tonight.

— Forge, 2026-07-16 (D288; build+deploy evidence in STATUS.md / IMPLEMENTATION_DECISIONS.md)
