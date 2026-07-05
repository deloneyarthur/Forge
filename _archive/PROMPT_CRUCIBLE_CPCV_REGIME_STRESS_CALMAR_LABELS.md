# Crucible ask — round-2 refit-distribution labels: CPCV paths, regime-stress percentiles, WF-calmar

**From**: Forge session, 2026-06-19
**Re**: completing the generation quality-model target sweep. Piggybacks on **`wf_percentile_refit`**
(the round-1 label — it worked great). Same refit-lane machinery; no gate change.
**Status**: DATA REQUEST.

---

## TL;DR

`wf_percentile_refit` let us sweep **24 candidate quality targets** through the same rich-feature
ridge. The finding: **downside / floor metrics are the predictable *and* binding ones** —
`regime_stress_p25` IC **+0.52** (top), the WF floor (`wf_p10`/`wf_min`/`wf_p25`) ~**+0.50**, while
every *ceiling* metric (`wf_p95/p90/p75`) sits at ~**+0.25**. To finish the sweep on the metrics we
still **can't see from Forge's export**, please emit three more per-honest-component distributions on
the same refit lane. **Prefer the per-element SERIES** (as you did with `wf_folds`) so we can derive
any stat ourselves.

## 1. Why — and what round 1 found

The generation quality model predicts a component's quality from rich config features and steers the
stream toward it. Round-1 result: the predictable, edge-driven signal is a component's **downside
behaviour** (worst folds / worst-regime returns / consistency), not its peak — and the single best
metric, `regime_stress_p25_return`, *is* the BEAR/RANGING worst-Q payer the T3a work is chasing. Two
loose ends remain, both blocked only by missing labels:

1. **`regime_stress` only exists at p25** in our export — but it's our top target, so we want its
   *other* percentiles (is p10 even better? does the floor-beats-ceiling pattern hold *within*
   regime-stress?).
2. **The CPCV family and calmar** are gate metrics we never receive per-component (only `cpcv_p25`).

## 2. The asks (per honest component, join key `config_hash`)

**A. CPCV path Sharpe distribution.** Percentiles `cpcv_p10/p25/p50/p75/p95` **+ the per-path series**
`cpcv_paths: [sharpe, …]` + `n_cpcv_paths`. Same reconstruction as the WF label (cv_results
`metric='sharpe'` joined to cv_folds, the CPCV path rows) — we only have `cpcv_p25` today.

**B. regime-stress distribution at more percentiles.** Percentiles `regime_stress_p10/p25/p50/p75/p95`
of the **same stress-regime return distribution `regime_stress_p25_return` is the p25 of**, **+ the
per-period series** `regime_stress_periods: [ret, …]` + `n_stress_periods`. If a per-regime split
(BEAR vs RANGING vs high-vol) is cheap, include it — that directly tells us whether the in-scope
(ranging) vs out-of-scope (bear) decomposition holds at the component level.

**C. walk-forward calmar.** Per honest component on the refit window — `wf_calmar_p50` (+ `p25/p75` if
cheap). It's a §8.7 gate but isn't in our per-component export. **If calmar is portfolio-only (not
computed per-component), just say so and skip it** — don't synthesize one.

## 3. Format — extend `wf_percentile_refit`

Add these fields to the **same `components[]` array** (keyed `config_hash`), or a sibling file keyed
identically. **Series arrays are preferred over fixed percentiles** — from `wf_folds` we computed
mean / trimmed-mean / CoV / frac-positive / top-quartile ourselves, so a series means you emit once
and we derive the rest.

## 4. Methodology

Same gate-consistent reconstruction as round 1 (np.percentile, linear interp, NaN-dropped; identical
to `gate._safe_percentile`), on the full-history refit window. **No gate change, no threshold moved**
(hard rules 3/6) — additional output on existing computations.

## 5. Population / volume

Same honest components the refit lane already processes; one row per component. Include the `n_*`
counts so we can drop percentiles resting on too few paths/periods.

## 6. Scope

These are per-component **predictability** labels — to pick the quality-model target. The marginal
**book-contribution** (the *leverage* axis — does selecting high-X actually lift assembled books) is a
separate, heavier **assembly-side** ask we'll raise once the target is locked; **not bundled here**.

**Format:** JSON to `~/optbt_data/exports/`, versioned/timestamped (e.g.
`refit_distributions_<ISO8601>.json` or extend `wf_percentile_refit`). Forge pulls by mtime.
