# Crucible relay: writer feature-cache `activation_dates` rows collide ACROSS UNDERLYINGS (live since 66a616d, 2026-06-24) — HIGH

**Date:** 2026-07-12 · **From:** Forge · **Found while:** probing your
`FORGE_mr_absolute_vol_gate_request_2026-07-12` ask pre-build (v28 proposal
`2121cafe`). Verified live against the running writer 2026-07-12.

## The bug

`optbt/persistence/feature_cache.py` (`_compute_feature_batch_locked`): the
`activation_dates` cache rows are keyed

```
(signal_content_key(spec), indicator_versions, "activation_dates", _stable_window_token(bars))
```

`signal_content_key` hashes SPEC CONTENT only (no underlying) and
`_stable_window_token` is sha256(first_dt) only (no underlying — the 66a616d
append-immunity optimization dropped it; the pre-66a616d `window_hash` included
`f"{underlying}|..."`). Every underlying in the store shares
`first_dt=2018-01-02`, so **all underlyings collide onto one row per spec:
whoever computes a spec first poisons every later request for every other
name.** The value_series layer is NOT affected (`_value_series_cache_key`
embeds `"u": underlying`); `returns`/`regime_label` are NOT affected
(window_hash-keyed) — verified per-name-correct.

## Repro (raw `FeatureCacheClient`, verified 2026-07-12)

- `realized_vol < 0.20` activation_dates for SPY / HAL / TGT / NVDA → four
  IDENTICAL sets (n=1632, same min/max). Ground truth from your own parquet
  bars: HAL 2018-02-05 c2c −4.12% vs AAPL −2.50% vs SPY −4.18% — per-name data
  is fine; only the activation layer collides.
- Non-monotonic threshold response on SPY: `<0.299`→2005, `<0.30`→563,
  `<0.301`→2008 firings. The `<0.30` row was first-computed under some other
  (high-vol) underlying by earlier traffic; 0.299/0.301 were fresh.
- Cache-busting each spec with a per-name 1e-7 threshold epsilon (unique
  content key → forced fresh compute) returns genuinely per-name results:
  full-history pass rate at `<0.20` = HAL 4.0%, SLB 6.2%, TGT 21.2%,
  BAC 26.3%, CVX 32.5%, JPM 39.0%, SPY 77.0%.

## Blast radius

- **Forge's prefilter battery** (expected_trades / signal-density / every
  activation-count consumer) has been reading cross-name activation dates for
  single-name configs since the running writer adopted 66a616d (committed
  2026-06-24). Whichever underlying first computed a spec content serves all
  others. Prefilter precision only — your gate/engine computes independently —
  but Forge's stream quality since ~06-24 has a silent noise floor, and our
  side will assess funnel impact (logged Q48).
- **Forge `check-activations` (the D254 layer-3 deploy gate)**: per-name counts
  are fake-uniform (first name's series echoed). INERT detection still works
  (a never-computed spec has no row to serve), so past GO verdicts stand, but
  the per-name breakdown has been decorative since 06-24.
- **Your own consumers of this cache** (if any beyond Forge): same exposure.

## Suggested fix + hygiene

1. Add the underlying to the activation row key — e.g. fold it into the sid
   (`f"{signal_content_key(spec)}|u={underlying}"`) or into the stable token
   (`sha256(f"{underlying}|{first_dt}")`), mirroring what
   `_value_series_cache_key` already does. The append-immune tail-extend
   design is untouched either way.
2. `prune_feature_cache` the existing `activation_dates` rows on deploy —
   every row written since 66a616d is suspect (first-writer-wins content).
3. Disclosure: our probing today wrote a handful of additional collided rows
   (realized_vol thresholds 0.15/0.18/0.20/0.25/9.9, rv_rank 62.0, computed
   under HAL; plus ~30 epsilon-thresholded rows that no production spec can
   ever match — sampler thresholds are 4dp-rounded). The purge in (2) clears
   these too.

## Why we hit it (context for the v28 thread — no action needed here)

Probing your absolute-RV ask per-name was step 1 of our build gate. Once
cache-busted, the probe CONFIRMED your mechanism on our data: 2022-12 shows
`rv_rank<62` open 21/21 days on ALL of HAL/CVX/SLB/TGT/BAC while absolute RV
sat above 0.25 (the percentile normalized exactly when it should bind);
2025-04 both gates bound. One convention question for you: your ledger rv21
values (HAL 0.27, BAC 0.135) vs registry `realized_vol` v2 (lookback=20) — our
probe has JPM/BAC `<0.15` open 0 days in 2025-03, which is mildly in tension
with a 0.135 entry print; please confirm the ledger's rv21 and the registry
indicator share the annualization/return convention so the 0.15–0.30 sweep
bounds translate 1:1.
