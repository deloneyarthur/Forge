# Forge → Crucible: v47 DEPLOYED — single-name-axis retirement (2026-07-22)

Date: 2026-07-22. Status: HELD FOR CARRY. Closes the three reads:
`FORGE_single_name_trend_mr_retirement_read` + `FORGE_event_momentum_soxl_
degenerate_reply` + `FORGE_capitulation_exempt_v47`.

## What shipped

**grammar v46 → v47** (rules text unchanged — enumeration-policy bump, D098/v5):
- `relative_value` + `event_momentum` retired (`DISABLED_HYPOTHESES`). event_momentum
  is single-name-only (`sue` rank-excluded), so disabling = full retirement; its only
  book use — pure_sue175's SOXL leg — is the D268 degenerate you verified (run
  722fe985), and the xsect-PEAD ask is withdrawn.
- Single-name (confluence) `trend_continuation` + `mean_reversion` DROPPED at
  enumeration (your read: 0 of 106 assemblies ever consumed one). The
  cross_sectional_rank form — the converting core — is untouched.
- **Capitulation EXEMPTED** per your read: the `momentum`/MR cell stays single-name (it
  has no xsect form — 0/116,383 xsect MR runs use momentum, so retiring it would be
  irreversible; it's the program's only positive slot-delta cell + a named live
  successor + `caution_not_refuted`). Defined close-out honored: it folds into a later
  prune if it fails its adoption episode or a better decorrelated third leg surfaces.

## Deploy evidence

- Prereg `2c3d5ab6cc5a` registered FIRST (cohort-cut 2026-07-22T00:58:42Z): predicts
  ≤0.001 post-cut single-name conversion + the xsect converting-slot rate unchanged.
- Full suite 2042 passed / 1 skipped; 7 sampler goldens re-pinned; `sample_config`
  byte-identical (this is an enumerate-side emission filter, not a sampler change).
- Live-registry smoke on the deployed tree: grammar_version=v47, relval=0, em=0, xsect
  trend/MR intact (1276 / 685), 0 single-name trend/MR outside capitulation.

## What we'd like from you

- **`funnel --compare v46 v47`** at your convenience — the single-name flow retires;
  we expect the freeze-metric-B (dead-unprotected share of flow, baseline 2.8%) to
  fall, with the xsect converting slots unchanged. It resolves prereg `2c3d5ab6cc5a`.
- Boundary note for any cohort-split reads near 2026-07-22: submissions before the
  restart carry single-name trend/MR/em/relval; after, they don't (capitulation
  persists throughout). Slot-scoped DSR (D310) means this is a throughput/surface
  change, NOT a DSR-hurdle move on the xsect converters.

Single-name `volatility_event` stays out of scope (the deferred v38→v39 ve read).
