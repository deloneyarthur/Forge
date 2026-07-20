# FYI → Crucible: one-time research cohort incoming (winning-indicator trend/MR)

**Date:** 2026-07-07 (~17:15Z) · **From:** Forge · **Action needed from Crucible:** none (FYI + optional analysis)

## What

Forge submitted a **one-time research cohort of 1,000 v24 configs** (500 trend + 500
mean-reversion) built from the **D236/D254 sweep-winning indicators**, to seed the gated
DB with tested exemplars of those winners at full-config scale.

- **trend (500):** `hypothesis=trend_continuation`, directional ∈ {`sma_slope`,`ad_slope`}
  AND `chandelier_exit` in exits (the winning entry + winning exit recipe).
- **mr (500):** `hypothesis=mean_reversion`, signals ∋ {`vol_regime`,`zscore_returns`}.

All 1,000 passed Forge's real prefilter battery (representative seeded draw, not
ranker-picked; `seed=20260707`, grammar v24, registry `47fe4080c6aefcce`). 0 overlap
with prior submissions.

## Why it may look unusual on your side

- Submitted **direct-to-inbox** (bypassing Forge's `submissions` table) because the live
  daemon holds the forge.db write lock — same pattern as the historical `requeue` script.
  → these runs get **fresh run_ids with no FK to Forge submissions**, and they are **not**
  in Forge's §7.3 in-flight accounting or feedback loop (intentional — keeps the research
  cohort out of the learning loop).
- Paced with **inbox backpressure** (≤250 pending) per the D179 flood lesson, so expect a
  gentle ~30–60 min trickle on top of normal daemon flow, not a spike.

## This is NOT a promotion play

trend/MR are the correlated core, not the decorrelated frontier. The goal is **research
data** on whether the sweep winners' indicator-level CPCV-p25 lift survives at full-config
scale (component-rate, wf_p25/tail behavior). No grammar change, no gate implication.

## Identifying the cohort

Join Crucible gated runs to the **config_hash manifest**:
`~/forge_data/winning_cohort/cohort_hashes.txt` (1,000 rows, `cohort\tconfig_hash`).
Optional-but-useful: slice these hashes for component-rate + wf_p25 by cohort vs the
matched general v24 trend/MR population.
