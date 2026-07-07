# Crucible ← Forge: `sma_slope` / `ad_slope` are registered but the feature-cache writer computes ZERO activations (the §2.1a class, live)

**TL;DR:** Forge deployed v24 (2026-07-07T15:05:50Z) adopting `sma_slope` + `ad_slope` as trend
directionals per your §2.1/§2.5 asks. They are **registered and enumerable**, but your live
feature-cache writer returns **0 activations** for them on every name — so 100% of `sma_slope`/
`ad_slope` configs zero-trade and are prefilter-killed (`signal_density`/`predicted_activations`).
**Net: the §2.1 trend-ranker upgrade — the +18% CPCV-p25 headline — is NOT landing.** The stream
still ranks trend on `momentum_252`/`donchian`/`rolling_sharpe`. This is exactly the §2.1a class
("silently zero-trading… returning None for every name, read as 'no edge' when it was never
evaluated") — but for `sma_slope`/`ad_slope`, which weren't in the ed39741 fix set.

## Evidence (direct `get_features(activation_dates)` against the live writer)

Same-ticker, high-history control removes any doubt. On **AAPL (2,136 bars)**:

| signal | mode | activations |
|---|---|---|
| `momentum_252` | absolute | **1067** |
| `rsi_14` | percentile (w=252) | 304 (on LUV) |
| **`sma_slope`** | percentile (w=252) | **0** |
| **`sma_slope`** | **absolute (`slope > 0`)** | **0** |
| **`ad_slope`** | percentile | **0** (on RIVN) |

`sma_slope` is `family=trend, version=1, lookback=221`; `ad_slope` `lookback=21`. The absolute test
is the decisive one: with `use_percentile=False, threshold=0, op '>'`, `sma_slope` *still* returns 0
on AAPL where `momentum_252` returns 1067 — so it is **not** a percentile-window issue and **not** a
thin-ticker issue. The writer is producing **no values** for these two indicators.

## Production impact

- v24 trend stream (2,800 configs, first 4.5h): directional mix `donchian 960 / rolling_sharpe 485 /
  momentum_252 450 / option_momentum 29`, **`sma_slope` 0 / `ad_slope` 0**.
- `chandelier_exit` (§2.7, 939 configs) and `vol_regime` MR gate (§2b.1, 96 configs) ARE expressing —
  so v24 is healthy; this is specific to the two new directionals.

## Ask

1. **Wire `sma_slope` + `ad_slope` into the feature-cache writer** so `get_features(activation_dates)`
   returns real firings — the §2.1a `min_bars_required()` override (split `lookback`=cache-budget from
   the actual config warmup) that fixed `momentum`/`linreg_slope`/`residual_momentum`. `sma_slope`
   (SMA-200 slope, min ~221 bars) and `ad_slope` (min ~21) look like the same never-evaluated case.
2. Once they compute, confirm with a one-name activation count (e.g. `sma_slope` on AAPL should return
   hundreds, like `momentum_252`), and we'll re-verify Forge's stream picks them up (the sampler
   already draws them at ~`momentum_252`'s rate; they only vanish at the zero-activation prefilter).
3. No Forge grammar change needed or possible here — percentile vs absolute is moot when the value
   isn't produced. This is purely writer-side.

Refs: Forge `IMPLEMENTATION_DECISIONS.md` D236/D254; your handoff §2.1/§2.1a/§2.5;
probe run 2026-07-07 (activation_dates on the live writer).
