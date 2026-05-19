# Crucible: restore `trend_strength` family for `adx` + `hurst` (Forge registry regression)

**Authored:** 2026-05-19 (Forge-side; for hand-off to a Crucible agent working in `/home/aj/proj/Crucible/`)
**Audience:** Crucible maintainer / agent
**Severity:** HIGH — blocks the entire `trend_continuation` hypothesis from being sampled by Forge

---

## Problem

Forge's `trend_continuation` hypothesis produces **0 sampler attempts** per 5,000-candidate batch despite D067's 5% exploration floor and D037's 2% stratified-sampling floor. Crucible's post-mortem cohort confirms this is persistent: **0 of 3,829** evaluated configs are `trend_continuation`.

Root cause: the production registry (`/home/aj/optbt_data/exports/registry_snapshot_*.json`) assigns `family="trend"` to **both** `adx` and `hurst`. Forge's grammar requires these two indicators to be in a *separate* `family="trend_strength"` so the §3.5 C1 rule (directional family ≠ regime family) can be satisfied when:

- §3.5 C2[`trend_continuation`] picks a directional from `family="trend"` (`momentum_252`, `ema_cross`, `supertrend`, etc.).
- §3.5 R2 forces the regime indicator to be `adx` or `hurst` by ID.
- §3.5 C1 requires the directional and regime indicators be in *different* families.

With both directional and regime in `family="trend"`, C1 fails on every pick → `SamplerError` → after 20 forced retries the hypothesis is blacklisted for the batch → 0 successful samples.

## Historical contract (what Forge expects)

- **D019** (`/home/aj/proj/Forge/IMPLEMENTATION_DECISIONS.md`) formalized the split: "post-contracts-v1.4.0, adx + hurst live in the `trend_strength` family rather than `volatility`."
- **Forge fixture** (`tests/fixtures/strategy_configs.py::minimal_registry_snapshot`) ships them with `family="trend_strength"`.
- **Forge test** (`tests/unit/test_enumeration/test_search_space.py:116-119`) explicitly asserts `indicators_by_family["trend_strength"] == ("adx", "hurst")` and pins the expectation.

The production registry is the regression; the grammar and fixtures are the source of truth per D019.

## Fix scope (minimum viable)

Move exactly two indicators from `family="trend"` to `family="trend_strength"`:

| indicator id | current `family` | required `family` |
|---|---|---|
| `adx` | `trend` | `trend_strength` |
| `hurst` | `trend` | `trend_strength` |

All other `trend`-family indicators (`donchian`, `ema`, `ema_50`, `ema_cross`, `macd`, `momentum_252`, `returns_12m_skip1`, `rolling_sharpe`, `sma`, `supertrend`) stay in `family="trend"`.

No changes to indicator IDs, versions, lookbacks, params_schema, or computation. **This is a metadata classification change only.**

## Where the change probably lives

Likely in Crucible's indicator-registry definition file (a YAML or Python module that declares each indicator's metadata). Quick search:

```
$ grep -rn '"adx"\|"hurst"\|adx:\|hurst:' src/optbt/features/ config/
```

The change is a one-line edit per indicator (the `family` field) plus a re-snapshot of the registry export.

## Verification before declaring done

1. **Local sanity:** the registry export's `family` field for `adx` and `hurst` must read `"trend_strength"`.
2. **Forge-side smoke test:** with Crucible's new registry published, Forge's `build_search_space` should produce:
   - `indicators_by_family["trend_strength"] == ("adx", "hurst")`
   - `indicators_by_family["trend"]` no longer contains `adx` or `hurst`
   - For `trend_continuation`: `directional_indicators_by_hypothesis["trend_continuation"]` is non-empty AND disjoint from `regime_indicators_by_hypothesis["trend_continuation"]` in family.
3. **Forge live-run signal:** after the registry republishes, the next Forge iteration's `sampler_attempts:` journal line should show `trend_continuation > 0` (no other Forge change required — D069 is already live).

## Why this matters

`trend_continuation` is one of the two hypotheses Forge's overnight session work (D066, D067, D068, D069) is trying to restore to active sampling — the operator's goal is broader coverage across all six §3.5 hypotheses. With this family classification corrected, D067's exploration floor (which sets `trend_continuation` weight to ~0.091) will finally take effect.

## Out of scope (do not change here)

- Indicator computation, params, version numbers.
- The §3.5 R2 indicator list (Forge owns this; do not edit Forge's grammar).
- Any other indicator's `family` classification (`iv_rank`/`pairs_zscore`/`rsi_2`/etc. are verified correct).
- Crucible's gate thresholds or pre-filter calibration.

## Coordinate doc

Forge-side reference: `OPEN_QUESTIONS.md` Q15 (2026-05-19). Both this prompt and Q15 stay until the registry republishes and Forge confirms `trend_continuation > 0` in `sampler_attempts:` for at least one iteration; then close Q15 with a resolution stamp and delete this prompt file.
