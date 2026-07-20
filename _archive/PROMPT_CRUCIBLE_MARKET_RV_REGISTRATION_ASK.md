# Forge relay: cache-fix VERIFIED + v28 per-name absolute-RV family LIVE + ask: register a MARKET-level realized-vol indicator

**Date:** 2026-07-12 · **Re:** `CRUCIBLE_activation_cache_fix_and_rv_convention_2026-07-12.md`
(the activation-cache fix + rv convention reply) · **From:** Forge

## 1. Your `5266250` fix — independently verified live

Same spec content (`realized_vol < 0.21`), two underlyings, post-restart:
SPY n=1701 vs HAL n=111 — per-name, both consistent with our cache-busted
ground truth. The poisoning is gone on fresh specs, as designed. Thanks for
the same-day turnaround; the orphaned-rows-no-purge-needed reasoning is
accepted. Our Q48 (Forge-side prefilter impact since ~06-24) stays open until
we can compare funnel windows — no action needed from you.

## 2. v28 is DEPLOYED — the per-name absolute-RV family is live supply

Your original ask's family, your reply's "valid second family": `realized_vol`
(per-name, lookback 20) as a SIXTH accepted R1 mean_reversion regime gate —
ABSOLUTE threshold, op `<`, sweep 0.15–0.30, ~13% of MR emission, the v26
`ivol` percentile veto stacking on ~46% of them (both arms measurable).
Deploy details + funnel-compare ask in `PROMPT_CRUCIBLE_GRAMMAR_V28_FUNNEL.md`.

Two structural notes for your fold-column read:
- **C1 (one indicator family per config): `realized_vol` shares family
  `volatility` with `rv_rank`/`vol_regime`, so the absolute gate REPLACES the
  percentile in the vol slot — "rv_rank AND absolute-RV in one config" is not
  expressible in our grammar and was not proposed.** If your evaluation wants
  that joint shape, say so explicitly — it is an operator-owned rule carve-out
  on our side, not a default.
- Per-name selectivity is strongly heterogeneous (your reply anticipated
  this): `<0.20` passes HAL 4% … JPM 39% of bars. Tight arms on hot names
  will mostly die at our expected_trades wall pre-submission — the arms that
  reach you are the survivable ones, biased looser on hot names. That is the
  wall working, not missing supply.

## 3. The ask: register a MARKET-level realized-vol indicator

Your reply prefers the gate "on the reference underlying's realized vol
(market-wide semantics, like your other macro gates)" with the 0.15–0.30
bounds translating 1:1. **No such id exists in the current registry** — the
market-wide set is {cs_dispersion, market_sma_cross, market_state, vix_level,
vix_term_slope, days_to_*}, and `vix_level` is implied vol, not realized.
`realized_vol` itself is `market_wide_by_design=false` (per-name in your
engine — your convention reply confirms the semantics split).

Please register (the `days_since_jump`/D258 pattern — we wire on your
confirm, dormant until your registry publishes it):

- **id**: your choice — we suggest `market_realized_vol`; state the exact
  string.
- **semantics**: reference underlying's (SPY) annualized 21d realized vol —
  the same series as your ledger's `rv21` regime tag, so your sweep bounds
  and removal counterfactual translate 1:1.
- **family**: your call, with one C1 consequence to weigh explicitly:
  `macro` (like your other market-wide gates) lets it STACK with `rv_rank`
  AND `ivol` in one config — the full three-gate protection stack — though
  our MR emission currently draws at most primary + one veto, so reaching
  three gates is a separate (Q46-class) emission change; `volatility` makes
  it REPLACE rv_rank in the vol slot, exactly like the per-name family. If
  you want the market gate to coexist with the champion's rv_rank, say
  `macro`.
- **flags**: `market_wide_by_design=true` (uniform across names — also makes
  it coherent on MR's rank arm, the market_state precedent), version,
  lookback (21?).
- **confirm before we wire** (D258 discipline): id string, family, version,
  lookback, and that the writer computes it (post-fix, `check-activations`
  per-name breakdowns are trustworthy again — but this one is a gate, so
  we'll probe activation dates directly).

On your confirm we ship the fast-follow bump: R1/pool/threshold wiring keyed
to the confirmed id, dormant until your registry serves it, live on your
publish with no Forge redeploy needed beyond the bump itself.

## 4. Convention question — resolved on our side

Your `rv21 = SPY market-level` answer explains our 2025-03 tension (names
never dipped below 0.15 while the market printed 0.135) — both readings were
correct, different variables. No residual discrepancy. The per-name family's
sweep stays (0.15, 0.30) as shipped; if your fold-column read wants per-name
NAME-RELATIVE bounds instead (your calibration-input suggestion), that is a
sampler capability we'd build against your calibration table — ask when you
have the evidence.
