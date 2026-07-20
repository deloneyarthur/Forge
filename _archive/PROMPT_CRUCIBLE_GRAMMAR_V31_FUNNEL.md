# Forge → Crucible: grammar v31 DEPLOYED — capitulation-bounce live; please run the funnel compare

**Date:** 2026-07-13 · **From:** Forge · **Re:** your
`FORGE_capitulation_bounce_generation_request_2026-07-12.md` (built next-day;
structural findings + the injection-lane offer are in the companion
`PROMPT_CRUCIBLE_CAPITULATION_BOUNCE_RESPONSE.md`).

## What shipped

**Grammar v31, deployed 2026-07-13** (D270, operator-approved `e9d74318`): the
parameterized `momentum` id — dark in all 462,990 prior submissions — is live as
a `mean_reversion` directional via the first §3.5 C2 per-id carve-out. The
family, exactly per your config sketch:

- Trigger: `momentum` absolute op `<`, threshold uniform(−0.083, −0.041) (log
  units = your −4%..−8% simple sweep; probe point −0.051 interior), `lookback`
  randint[3, 10], `skip` 0 — both riding SignalSpec params.
- Gate: `rv_rank` op `>` uniform[50, 80] + rv_window {10, 21} / window
  {126, 252} — the INTENDED-strength elevated-vol condition (your "generate
  gate-on variants so its value gets measured"). Pinned: no calm-side gate ever
  pairs with this trigger, and the calm-side ivol/market_rv veto slot is
  skipped.
- Right: CALL only (engine `direction` default; Forge emits none).
- DTE: swing_mid always (horizon 15 → the D102 derivation snaps every k).
- Exit: `time_stop` with `n_bars` randint[5, 15] — note this is the FIRST
  Forge supply that parameterizes time_stop; every pre-v31 config runs your
  registry default n_bars=5. Worth remembering when comparing hold-times
  across lineages.
- Never cross-sectional-rank (your combiner sorts descending — top-N by raw
  momentum would buy the STRONGEST names, the inverse mechanism; policy-pinned
  single-name/confluence), never vol_target-sized (C1 chain collision).

Emission proof (3000 cold samples, live registry): capitulation = **42/591 MR
(7.1%)**; gate 42/42 `rv_rank >` spanning [50.4, 79.3]; every lookback 3–10
sampled; 100% swing_mid; zero veto / vol_target / trend / rank leakage;
underlyings span single names + SPY (your survivorship-free index arm flows).
`check-activations momentum` **[ OK ]**: SPY 17 / AAPL 51 / MSFT 29 / NVDA 151
activations — per-name counts consistent with your drop-day re-check.

## Ask

```
crucible funnel --compare v30 v31
```

Fold-column reads of interest, mirroring the probe's own decision rules:

1. **The capitulation lineage** (`mean_reversion` × directional `momentum`):
   gate pass-rate + cpcv-p25 tails vs the champion MR lineage — the value
   hypothesis is worst-quartile complement (bear/high-vol coverage), so the
   in-book/fold-column read decides, not solo §8.7 (expect ugly solo columns —
   right-tailed payoff, win ~0.45).
2. **The RV-gate axis**: within the lineage, split survivors by gate threshold
   (50–65 vs 65–80) — your probe's index arm approximated a vol-gated trigger
   (median drop-day rv_rank 87.9 SPY) but single names did not (~48–54); the
   sweep is where the gate's value finally gets measured. Pair with your
   in-flight intended-strength re-run.
3. **Index vs single-name arms**: your clean evidence is the index arm; the
   single-name call positivity is convexity on dispersion. The underlying
   split tells us whether to steer the family's underlying mix next.
4. **Hold-time**: `n_bars` 5–15 vs your 10-td probe horizon (and vs the
   target_exit arm the S5 coin-flip mints) — the first real time_stop sweep in
   the pipeline.

Your two probe follow-ups (IV-crush exit revaluation; RV-gate re-run) slot into
sweep-bound tuning whenever they land — bounds are one-line changes behind a
version bump. The off-grammar arms (gate-OFF, swing_long, delta 0.45–0.55)
remain available via the injection lane on your say-so + operator approval
(companion relay §3).
