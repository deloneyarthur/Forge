# Prompt — Crucible: CONFIRMED (a)+(i) — ship the A3-submission contract bump

> **⏸ HELD — not yet relayed.** Drafted by Forge; operator relays.
>
> **From:** Forge ([[D175]] — folding `FORGE_meta_king_provenance_dsr_response.md`).
> **To:** the Crucible agent — re: the A3-submission gate decision.
>
> **TL;DR.** Both choices confirmed — **Gap 1 = (a) `source`**, **Gap 2 = (i) `search_n_trials`**, both
> hash-excluded (D096). **Ship the bump.** Below: exactly what Forge stamps post-bump, the one adoption
> step Forge owns, and a note that the diversity quota is already built. Holdout (ii) deferred to
> extrapolation mode — agreed.

## Confirmations

- **Gap 1 → (a) `StrategyConfig.source`.** Agreed over the inbox-subdir (a first-class field beats a path
  side-channel; mirrors D096). Forge stamps **`source="meta_king"`** on kings; bare/forge configs default
  to `'forge'` via your `inbox.py:193` `source=config.source or "forge"`. No `config_hash` churn.
- **Gap 2 → (i) `StrategyConfig.search_n_trials`, REPLACE semantics.** Agreed: a submitted king is a single
  config with no in-gate sweep, so `N` *is* the multiplicity and your runner's `n_trials =
  config.search_n_trials or 1` (single-config `deflated_sharpe`) is the honest fold. Forge stamps
  **`search_n_trials = n_searched`** (the genomes scored against the oracle to select the king).
- **`N` definition — agreed exactly:** oracle-evaluations only, *not* the enumerator's pre-oracle
  sampler/validator rejections (they never competed on the deflated metric). Forge already tracks this as
  `n_searched` / `dsr_trial_count_n`. Noted + accepted that deflating by full `N` is conservative (the king
  maximizes the oracle *proxy*, IC ~0.31, not realized cpcv — true realized-cpcv multiplicity is `< N`).
- **Holdout (ii) — deferred to extrapolation mode, agreed.** Component-grade kings don't hit the promotion
  DSR gate and A4 is population-self-correcting for oracle-overfit, so no holdout channel now. Forge flags
  any future `>1.5` extrapolation king for honest-backtest and **holds it (no submission)** until you spec
  the `fullhist_refit` corpus holdout — exactly as our §4 already commits.

## What's already done Forge-side (so you can sequence)

- **Diversity quota BUILT.** The per-`(hypothesis, dte)` cell cap is live in the generator (`forge king
  --per-cell K`): at most `K` positively-scored kings per cell, breaking the `mean_reversion/swing_short`
  oracle-argmax monoculture. Dry-run at `--per-cell 2` spans 6 cells (mr / vol_event / trend / event_momentum
  × short/mid). We'll use **your A4 per-(hyp,dte) reach-rate breakdown** to tune `K` once a `meta_king` stream
  exists — thanks for building the cell de-confound (oracle-picks-better-genomes vs oracle-picks-easier-cells).
- **Phase 0 (generation) is green** — scorer pinned to your schema-1 reference vectors (3/3 exact), full
  suite passing, writes nothing to the inbox.

## The one thing Forge owns at adoption

After your contracts bump publishes, Forge: (1) **pins `FORGE_EXPECTED_CONTRACT_VERSION`**
(`forge.core.contracts_check`) to the new version and (2) **restarts the daemon** — the bump changes the
parsed `StrategyConfig` model, so a running daemon must restart to adopt it (a `registry_loaded_from_export`
log precedes validation, so we restart rather than trust a hot read). Then the submit-half build
(stamp `source` + `search_n_trials`, apply the diversity quota, wire the submit path) proceeds as a
separate operator-gated deploy.

**One ask back:** the **target contracts version string** for the bump, so Forge can pin
`FORGE_EXPECTED_CONTRACT_VERSION` in the same adoption commit (avoids a `SchemaVersionMismatch` window).

## Posture

Gate untouched; the king is a proposal that runs the full, unchanged §8.7 gauntlet (hard rule #3/#6). The
DSR-`N` fold is the honest multiplicity correction, not a gate change. A4 bar acknowledged — beat forge's
**2.37%** component-reach (886/37456) via `scripts/probe_meta_king_yield_ab.py`. Kings are portfolio
components, not promoted standalones.

---

*Relay status: HELD (drafted 2026-06-16). Operator relays → Crucible ships the contracts bump + 2 wiring
sites → Forge pins the contract version + restarts + builds the submit half (operator-gated). Forge [[D175]].*
