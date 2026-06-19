# Crucible ask — quality-target LEVERAGE: does component `regime_stress_p25` lift assembled books?

**From**: Forge session, 2026-06-19
**Re**: `FORGE_generation_model_plan.md` (quality half); follows the round-2 distribution labels.
**Status**: DATA REQUEST (the leverage axis) + an outcome note (§3).

---

## TL;DR

We locked **`regime_stress_p25_return`** as the generation quality-model target on the
**predictability** axis — a 47-metric rich-feature-ridge sweep ranked it top (IC +0.52); downside
robustness beats every ceiling/center metric. Before we steer generation by it, validate the
**leverage** axis: does *selecting* high-`regime_stress_p25` components actually lift assembled books
toward the binding gates (WF-median 2.0, cpcv-p25 1.5)? We need a per-component (or correlational)
book-**contribution** read.

## 1. Why — predictability ≠ causality

`regime_stress_p25` is the metric Forge generation can best predict from config structure. But we
don't know it *drives* promotion. If high-`regime_stress` components don't lift books, we'd be
steering toward a predictable-but-inert proxy. This is the "marginal book-contribution" gold-standard
target we deferred — now it's the gating question for shipping the quality lane.

## 2. The ask (any one — easiest first)

**A. Correlational (cheapest, settles go/no-go).** Across assembled books / §8.7 portfolio campaigns,
do **passing** books contain higher-`regime_stress_p25` components than **failing** ones? A simple
"mean component `regime_stress_p25` in passing vs failing assembled books" (± a rank correlation of
book-pass-margin vs mean-component-`regime_stress`).

**B. Marginal-contribution (better).** For components that have appeared in assembled books, a
per-component label = the delta to the book's binding gates (WF-median, cpcv-p25) from including it
(leave-one-out or Shapley-ish). Keyed `config_hash` so Forge correlates it with `regime_stress_p25`
(and with `wf_p10`/`wf_p25`, the WF-native alternates).

**C. Direct (best, if cheap).** Assemble books from a **high-`regime_stress`** vs a
**low-`regime_stress`** component pool and report the binding gates — does the high pool assemble to
better books?

Whatever's cheapest. Even (A) is enough to decide whether to flip the quality lane on.

## 3. Outcome note (courtesy — what the round-2 labels settled)

`refit_distributions` and `regime_stress_distribution` are **consumed**. Findings:
- The WF/CPCV percentile families and the regime-stress percentiles all **confirmed** the verdict:
  generation predicts **downside robustness, not the peak** (ceilings lowest IC everywhere).
- **Within regime-stress the percentiles are collinear** (it's a tight, ~98%-positive return
  bootstrap) → the existing gate metric **`regime_stress_p25_return` is statistically tied with any
  regime-stress percentile**. So **you don't need to maintain the extra regime-stress percentiles in
  production** — the existing gate suffices. The rerun was still worth it (it ruled out
  "a deeper percentile is better," which holds for WF but not regime-stress).
- The WF/CPCV **per-fold/per-path series** were the valuable part (we derived the floor metrics from
  them); keep those emitted if cheap, but no new productionization is needed for the locked target.

## 4. Scope

Assembly-side read; **no gate change, no threshold moved** (hard rules 3/6). Join key `config_hash`.
Format JSON to `~/optbt_data/exports/`, versioned/timestamped; Forge pulls by mtime.
