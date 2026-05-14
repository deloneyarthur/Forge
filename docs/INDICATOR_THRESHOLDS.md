# Indicator threshold audit — Crucible-real distributions on SPY (2020-2025)

**Audit date:** 2026-05-14
**Source data:** `~/optbt_data/bars_underlying/symbol=SPY/` — 1508 trading days, 2020-01-02 → 2025-12-31.
**Compute path:** `optbt.features.base.build(id).compute(bars.lazy())` for each of the 33 indicators advertised in Crucible's `RegistrySnapshot` (commit `b447597` writer-side feature_cache).

**Why this exists:** Forge's enumerator (`sampler.py:132`) sets `params={"threshold": 30.0}` as a generic default for every threshold-style `SignalSpec`. Real-data audit shows this default is **meaningful for only ~1 in 4 indicators**. The rest produce 0 activations (signal never fires), making `signal_density` filter reject 100% of candidates under the real Crucible cache.

This document is the **threshold map** that informs Forge's per-indicator threshold sampling.

---

## Categories

### 1. Bounded 0-100, oversold/overbought style (4 indicators)

| Indicator | min | p25 | p50 | p75 | max | NaN% | Threshold suggestion |
|---|---:|---:|---:|---:|---:|---:|---|
| `rsi` | 0.0 | 45.0 | 58.4 | 67.8 | 89.3 | 0.1% | low: 20-35; high: 65-80 |
| `rsi_14` | (= `rsi`) | | | | | | low: 20-35; high: 65-80 |
| `rsi_2` | 0.0 | 18.7 | 68.7 | 92.1 | 100.0 | 0.1% | low: 5-15; high: 85-95 |
| `adx` | 9.2 | 17.0 | 22.4 | 28.2 | 50.6 | 1.9% | trend strong: 25-30 |

### 2. Bounded 0-1, position-in-range style (4 indicators)

| Indicator | min | p25 | p50 | p75 | max | NaN% | Threshold suggestion |
|---|---:|---:|---:|---:|---:|---:|---|
| `bb_pct` | -0.39 | 0.39 | 0.70 | 0.86 | 1.21 | 1.3% | low: 0.05-0.20; high: 0.80-0.95 |
| `donchian` | 0.0 | 0.45 | 0.78 | 0.93 | 1.0 | 1.3% | low: 0.05-0.20; high: 0.80-0.95 |
| `keltner_pct` | -0.67 | 0.41 | 0.72 | 0.92 | 1.62 | 0% | low: 0.05-0.20; high: 0.80-1.20 |
| `hurst` | 0.29 | 0.52 | 0.57 | 0.63 | 0.86 | 6.6% | mean-reverting <0.5 ; trending >0.5 |

### 3. Volatility (small positive, log-scale) (5 indicators)

| Indicator | min | p25 | p50 | p75 | max | NaN% | Threshold suggestion |
|---|---:|---:|---:|---:|---:|---:|---|
| `realized_vol` | 0.06 | 0.11 | 0.14 | 0.20 | 0.94 | 1.3% | calm: <0.12; stressed: >0.20 |
| `parkinson_vol` | 0.06 | 0.085 | 0.12 | 0.16 | 0.56 | 1.3% | calm: <0.10; stressed: >0.18 |
| `garman_klass_vol` | 0.06 | 0.085 | 0.12 | 0.16 | 0.60 | 1.3% | calm: <0.10; stressed: >0.18 |
| `yang_zhang_vol` | 0.08 | 0.11 | 0.15 | 0.21 | 0.93 | 1.3% | calm: <0.13; stressed: >0.22 |
| `atr_pct` | 0.005 | 0.009 | 0.012 | 0.017 | 0.080 | 0% | calm: <0.010; stressed: >0.020 |

### 4. Signed, z-score / sharpe style (2 indicators)

| Indicator | min | p25 | p50 | p75 | max | NaN% | Threshold suggestion |
|---|---:|---:|---:|---:|---:|---:|---|
| `zscore_returns` | -3.30 | -1.12 | -0.10 | 0.99 | 3.31 | 2.6% | extreme low: <-2; extreme high: >2 |
| `rolling_sharpe` | -3.47 | 0.09 | 1.43 | 2.60 | 7.03 | 4.2% | low: <0.5; high: >2.0 |

### 5. Signed, returns / momentum style (3 indicators)

| Indicator | min | p25 | p50 | p75 | max | NaN% | Threshold suggestion |
|---|---:|---:|---:|---:|---:|---:|---|
| `momentum_252` | -0.27 | 0.06 | 0.14 | 0.23 | 0.55 | 16.7% | trending up: >0.10; trending down: <0.0 |
| `returns_12m_skip1` | (= `momentum_252`) | | | | | | trending up: >0.10; trending down: <0.0 |
| `macd` | -6.4 | -0.84 | 0.04 | 0.77 | 5.4 | 6.9% | sign-based, threshold 0 |

### 6. Binary / categorical (3 indicators)

| Indicator | values | NaN% | Threshold suggestion |
|---|---|---:|---|
| `ema_cross` | -1 / +1 | 6.9% | threshold 0 (sign) |
| `supertrend` | -1 / +1 | 0.7% | threshold 0 (sign) |
| `vol_regime` | 0 / 1 / 2 | 16.7% | threshold 0 or 1 (regime boundary) |

### 7. Calendar (large scale) (2 indicators)

| Indicator | min | p25 | p50 | p75 | max | NaN% | Threshold suggestion |
|---|---:|---:|---:|---:|---:|---:|---|
| `days_to_fomc` | 0 | 15 | 34 | 209 | 755 | 0% | imminent: <7; near: 7-30 |
| `days_to_earnings` | 999 | 999 | 999 | 999 | 999 | 0% | **stub-like** — SPY has no earnings; always 999. Useful only on single-name underlyings. |

### 8. Price-scale (NOT for thresholding) (3 indicators)

| Indicator | min | p50 | max | Notes |
|---|---:|---:|---:|---|
| `ema` | 276 | 441 | 683 | Price level; compare to price, not threshold |
| `ema_50` | 337 | 442 | 677 | Same |
| `sma` | 251 | 438 | 684 | Same |

**Recommendation:** Forge should NOT generate threshold signals on these. Use them only in `passthrough` or comparison signals where the predicate compares two indicators rather than indicator-vs-constant.

### 9. Stubs (NaN-only on real data) (4 indicators)

| Indicator | Why NaN | Threshold suggestion |
|---|---|---|
| `iv_rank` | needs ATM IV history; chain_snapshots may not have computable IV for all dates | **skip in enumeration** until Crucible ships real IV cache |
| `expected_value_estimator` | needs prior trade history; signal-self-referential | **skip** until Crucible ships EV pipeline |
| `pairs_zscore` | needs ticker-pair definitions; SPY-only data | **skip** until pair registry ships |
| `put_call_flow` | needs options-flow data; chain_snapshots lack call/put volume | **skip** until flow ingest ships |
| `vix_level` | needs VIX bars; not in `bars_underlying/symbol=SPY/` | **skip** until VIX ingest ships |

### 10. Microstructure (low signal on SPY) (1 indicator)

| Indicator | min | p50 | max | Notes |
|---|---:|---:|---:|---|
| `amihud` | 0.000 | 0.000 | 0.000 | Liquidity proxy; SPY is so liquid that the metric is ~0. Threshold ~0 fires everywhere; not useful as threshold on SPY. |

---

## Implementation plan (Forge `sampler.py`)

Replace the universal `params={"threshold": 30.0}` default in `sampler.py:132/138` with an indicator-aware sampler:

```python
def _sample_threshold(indicator_id: str, role: str, rng: Random) -> dict:
    """Sample a threshold (and optionally op) appropriate for the indicator + role."""
    spec = _INDICATOR_THRESHOLD_TABLE.get(indicator_id)
    if spec is None or spec.is_skip:
        raise EnumerationSkip(f"{indicator_id!r} has no usable threshold under real Crucible compute")
    # role-aware: directional signals fire on "extreme" values; regime_filter fires on "allow window"
    if role == "directional":
        return spec.directional_sample(rng)
    elif role == "regime_filter":
        return spec.regime_sample(rng)
    elif role == "confluence":
        return spec.confluence_sample(rng)
```

`_INDICATOR_THRESHOLD_TABLE` lives in a new `forge.enumeration.indicator_thresholds` module with one entry per indicator family.

**Skip-list (5 indicators)** — never enumerate threshold signals on stubs:
- `iv_rank`, `expected_value_estimator`, `pairs_zscore`, `put_call_flow`, `vix_level`

**Skip from directional** but allow as passthrough/comparison **(3 indicators)** — price-scale:
- `ema`, `ema_50`, `sma`

**Conditional skip** — `days_to_earnings` only enumerable for non-SPY (single-name) underlyings; v1 SPY-only so skip.

**Grammar impact (§3.5 R1 / X2 caveats):**
- §3.5 R1 says mean_reversion strategies must use `iv_rank` as the regime gate. If `iv_rank` is a stub, **R1 is structurally unsatisfiable** until Crucible ships real IV. Two paths:
  - (a) Drop R1 from v1 grammar until IV ships; document as Phase 9 v4 dependency
  - (b) Accept that all mean_reversion configs fail at the signal_density / pre-filter stage until IV ships
- §3.5 X2 says fractional Kelly sizer requires `expected_value_estimator`. Same constraint; same paths.

These are **operator-decision** items beyond this audit's scope.

---

## Q13 closure note

Q13 in `OPEN_QUESTIONS.md` documented "100% rejection at permutation_test under synthetic cache." With the real Crucible cache active (`b447597`), the rejection has shifted to `signal_density` because threshold defaults don't match real indicator scales. The fix is indicator-aware threshold sampling per this audit. Logged as **Q14** in `OPEN_QUESTIONS.md`.
