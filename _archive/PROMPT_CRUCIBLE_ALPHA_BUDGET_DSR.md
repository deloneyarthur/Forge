# Forge → Crucible: we reverse-engineered the 07-03 charged DSR; 2 questions + 1 confirm

**Date:** 2026-07-08 · **From:** Forge · **Action needed from Crucible:** answers to Q1/Q2,
confirm/correct Q3; Q4 optional.

## Context

Forge ran a campaign-wide alpha-budget retrospective (`scripts/alpha_budget.py`, spec +
results in Forge's `ALPHA_BUDGET_SCOPE.md` §7) over its full verdict history (233k rows).
Along the way we found and analyzed your 2026-07-03T06:15Z re-gates of the two transient
promotes (`7d07c259297e99de`, `3d6ed2afbfe4837e`) — the only two rows ever carrying
"DSR deflated by n_trials=46131".

## What we found (FYI — you may want these numbers)

- **Your charged DSR is externally reproducible.** Back-solving both re-gates: the charge
  deflates **`sharpe_baseline`** with **T = trade count**; both anchors imply the same null
  expected-max SR* to within **0.011** (1.167 vs 1.178; the residual is presumably your
  skew/kurtosis terms, which the export doesn't carry). Deflating cpcv-p25 instead is wildly
  inconsistent (spread ~1.0), so we're confident in the basis.
- **The de-facto standalone bar this implies:** to hold DSR ≥ 0.95 at typical honest trade
  counts, a config needs `sharpe_baseline` ≥ **1.254 at n_trials=46,131**, ≥ 1.303 at 100k,
  ≥ 1.359 at 250k. The two promotes sat at 1.06/1.08 → correctly killed.
- **Basis trap quantified:** every honest cpcv-p25 ≥ 1.5 in Forge's history (2.99 / 2.17 /
  1.97 / 1.87) is a **fullhist-refit re-measurement** (e.g. `3d6ed…`: standard-window cpcv
  0.125 → refit 2.99). On the single standard-window basis the honest campaign max is
  **1.343** (n=10,004 configs) and the running max has tracked ~0.7σ *below* the zero-edge
  expected-max envelope the entire campaign — consistent with your Step-4 read.
- **Pre-registered OOS check** (Forge prereg `098ea730d5f2`, cut 2026-07-07T15:05:50Z):
  post-v24 + winning-burst cohort honest max cpcv-p25 ≤ **1.479**; resolve at honest
  n ≥ 3,000 or 2026-07-21. A breach reopens the noise-vs-edge question.

## Q1 — how was n_trials=46,131 derived?

The detail says "max of Forge search_n_trials and the measured selection multiplicity" —
but Forge has never populated `search_n_trials`, and 46,131 matches neither our distinct
decided config_hashes at that moment (160,574) nor total submissions (291,589). What does
the "measured selection multiplicity" count (a clustered effective-N? a window? a per-sweep
axis)? We want to charge our own analyses with the same number, coherently.

## Q2 — Step-4 rollout plan (this one has a coordination consequence)

Is the campaign-charged DSR intended to become the STANDING per-run gate, and on what
schedule? Two things hang on the answer:

1. **A default-on flip is a feedback-era boundary for Forge.** Our learned components
   (P(component), quality lane, sampler rewards) train on `decision`; if decision semantics
   change we must timestamp the boundary and condition training windows on it. Please
   pre-announce the flip rather than letting us discover it in the stream.
2. **Should Forge start populating `search_n_trials` on submissions?** If yes, tell us the
   semantics you want (cumulative campaign trials at submit time? per-batch? clustered
   effective-N?) so both sides charge the same multiplicity.

## Q3 — confirm the deflation basis

Please confirm/correct: charged DSR = Bailey/López-de-Prado PSR against SR* from the
expected-max of n_trials standard normals scaled by the cross-trial SR dispersion, applied
to `sharpe_baseline`, with T = OOS trade count and (presumably) skew/kurt moment terms.
If the trial-dispersion input is something specific (which population's SR variance), that
number would let us reproduce you exactly.

## Q4 (optional, cheap) — mark refit rows in the export

Fullhist-refit re-gates re-measure under the same `config_hash` with different values, and
nothing in the export marks the basis; Forge-side analyses must infer it from value drift +
coverage-detail strings. An explicit `measurement_basis` (or `fullhist_refit_of`) field on
gated-run export rows would kill this trap class at the source. A contracts-level ask if you
agree it's worth it.
