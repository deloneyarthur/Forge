# Indicator threshold audit — Crucible-real distributions on SPY (2020-2025)

**Audit date:** 2026-05-14
**Source data:** `~/optbt_data/bars_underlying/symbol=SPY/` — 1508 trading days, 2020-01-02 → 2025-12-31.
**Compute path:** `optbt.features.base.build(id).compute(bars.lazy())` for each of the 33 indicators advertised in Crucible's `RegistrySnapshot` *at the time of the audit* (commit `b447597` writer-side feature_cache). **NB:** the registry has grown substantially since — the audit covered only the 33 then-present; the addenda at the bottom (v6/v18) and `_INDICATOR_THRESHOLD_TABLE` track the later ones. For the authoritative live set and count, read the newest `registry_snapshot_*.json` (by mtime), not this doc — any snapshot filename/count quoted in this doc is a historical example.

**Why this exists:** Forge's enumerator (`sampler.py:132`) sets `params={"threshold": 30.0}` as a generic default for every threshold-style `SignalSpec`. Real-data audit shows this default is **meaningful for only ~1 in 4 indicators**. The rest produce 0 activations (signal never fires), making `signal_density` filter reject 100% of candidates under the real Crucible cache.

This document is the **threshold map** that informs Forge's per-indicator threshold sampling.

> **⚠ HISTORICAL SNAPSHOT (2026-05-14, pre-D031). For indicator *liveness* and *current* threshold
> specs, the CODE is authoritative — read `src/forge/enumeration/indicator_thresholds.py` (the live
> `_INDICATOR_THRESHOLD_TABLE`) + the newest Crucible `RegistrySnapshot`
> (`~/optbt_data/exports/registry_snapshot_*.json`, newest by mtime), NOT this narrative.** The
> distribution tables below were computed once on SPY in 2026-05 and are kept as a calibration record;
> the indicator *set* and the *ranges* have moved on since (see the v6/v18 addenda at the bottom).
>
> What is verified WRONG in the original 2026-05-14 text, and corrected inline below:
> - **The §9 "Stubs (NaN-only)" list is FALSE.** D030's "stub" framing for the five indicators
>   `iv_rank`, `vix_level`, `pairs_zscore`, `put_call_flow`, `expected_value_estimator` was **obsoleted
>   by D031 (2026-05-15)**: Crucible shipped real `version=2` implementations of all five. They are LIVE
>   today — confirmed present in the latest registry snapshot (`2026-06-24T070003Z.json`, 58 indicators)
>   and each carries a live threshold spec in `_INDICATOR_THRESHOLD_TABLE` (e.g. `iv_rank`
>   `regime_range=(10,50)`, honoring §3.5 R1). Crucible re-confirmed coverage 2026-06-15
>   (`../Crucible/docs/handoffs/FORGE_iv_rank_already_live_coverage.md`): `iv_rank` non-NaN ~100%
>   single-name (used in 3,998 runs / 77 components — impossible for a NaN stub), `iv_term_slope`
>   94–100%, `iv_minus_rv` 98–99%.
> - **The "§9 skip-list" and the "§3.5 R1 structurally unsatisfiable" caveat are WRONG as of D031.**
>   `iv_rank` is live ⇒ R1 is satisfiable; it is a valid `mean_reversion` regime gate.
> - **"skew / risk-reversal is absent — no indicator built" is now STALE.** As of the current registry,
>   skew-surface indicators DO exist (`skew_25d`, `butterfly_25d`, `realized_skew`, family
>   `iv_structure`/`volatility`). They are registry-published but NOT yet in Forge's threshold table, so
>   Forge does not enumerate them as threshold signals today (see "Registry vs. Forge table gap" below).
>   Caveat unchanged: classic skew/risk-reversal reads a *seller* signal, wrong-signed for long premium —
>   admitting any of these is a grammar/operator decision, not an audit conclusion.
>
> Root cause of a 2026-06-15 mis-derivation ([[D154]]): an audit read this stale doc instead of the
> code. See [[indicator-thresholds-doc-stale-pre-d031]].

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

### 9. ~~Stubs (NaN-only on real data)~~ — **SUPERSEDED by D031 (2026-05-15): all five are LIVE.**

> **This entire section is obsolete.** It reflects the 2026-05-14 audit *before* Crucible shipped real
> implementations. Per `indicator_thresholds.py:18-22` (D031) and Crucible's 2026-06-15 coverage handoff,
> all five compute real values and are enumerated with live threshold specs. **Do NOT skip them.** The table
> below is retained only as a historical record of the pre-D031 state; the "skip" suggestions are WRONG today.

| Indicator | ~~Why NaN (pre-D031)~~ | **Live status (D031+, current)** |
|---|---|---|
| `iv_rank` | ~~needs ATM IV history~~ | **LIVE** — non-NaN ~100% single-name; spec `directional_range=(20,40)`, `regime_range=(10,50)` (R1 ≤ 50 honored). The §3.5 R1 mean_reversion gate. |
| `expected_value_estimator` | ~~needs prior trade history~~ | **LIVE** (v2); now the X2 fractional-Kelly sizer feature (D138 nulled its directional range). |
| `pairs_zscore` | ~~needs pair definitions~~ | **LIVE** (v2); relative_value's directional pool. |
| `put_call_flow` | ~~needs options-flow data~~ | **LIVE** (v2). |
| `vix_level` | ~~needs VIX bars~~ | **LIVE** (v2); calm-regime gate `regime_range=(15,30)`. |

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

**~~Skip-list (5 indicators)~~ — OBSOLETE (D031):** `iv_rank`, `expected_value_estimator`, `pairs_zscore`,
`put_call_flow`, `vix_level` are **all LIVE** and enumerated. The only true skips are the price-scale
indicators (`ema`, `ema_50`, `sma`) and raw $-scale (`gex`/`vex`/`cex`/`atr`), per `_SKIP_SPEC` in
`indicator_thresholds.py`.

**Skip from directional** but allow as passthrough/comparison **(3 indicators)** — price-scale:
- `ema`, `ema_50`, `sma`

**~~Conditional skip~~ — OBSOLETE:** ~~`days_to_earnings` only enumerable for non-SPY (single-name) underlyings; v1 SPY-only so skip~~. The universe has been multi-name for months and `days_to_earnings` is **live** — it serves as a `volatility_event` R3 regime gate. The part that remains true: it is only meaningful for single-name underlyings (no earnings date for SPY/index).

**Registry vs. Forge table gap (current, derive-from-source).** The live registry advertises more
indicators than `_INDICATOR_THRESHOLD_TABLE` carries. Any registry id absent from the table returns
`is_threshold_skippable() == True` (defensive invariant: no empty-params threshold leak) — so Forge does
**not** enumerate it as a directional/regime threshold signal; it is at most a `passthrough`/`confluence`
indicator. As of the `2026-06-24T070003Z.json` snapshot, the published-but-not-in-table set was:
`butterfly_25d`, `cs_dispersion`, `iv_vs_index`, `ivol`, `realized_skew`, `skew_25d`, `vix_term_slope`,
`vol_of_vol` (families `iv_structure` / `macro` / `volatility`). This list is a moving target — re-derive
it from the diff of the newest registry snapshot against the table, not from this line. Adding any of these
to the threshold table is a grammar/operator decision (and for the skew-surface ids, a *direction* decision
— classic skew is seller-signed; see the banner).

**~~Grammar impact (§3.5 R1 / X2 caveats)~~ — OBSOLETE (D031): both constraints are satisfied.**
- §3.5 R1: `iv_rank` is **live**, so R1 is **satisfiable** and `iv_rank` is a valid mean_reversion regime gate
  (`regime_range=(10,50)`). Caveat that *is* current (D150, not stale): the sampler **de-weights** `iv_rank`
  3:1 vs the ranging proxies (`gamma_flip`/`hurst`) for mean_reversion because it *fires sparsely* (trade-count
  prefilter), but it stays explorable (weight 1.0, never zeroed). It is also excluded from the
  `cross_sectional_rank` path (D116, `rank_per_name_coherent=false`) — single-name path only.
- §3.5 X2: `expected_value_estimator` is **live**; the fractional-Kelly sizer constraint is satisfied.

These are **operator-decision** items beyond this audit's scope.

---

## Q13 closure note

Q13 in `OPEN_QUESTIONS.md` documented "100% rejection at permutation_test under synthetic cache." With the real Crucible cache active (`b447597`), the rejection has shifted to `signal_density` because threshold defaults don't match real indicator scales. The fix is indicator-aware threshold sampling per this audit. Logged as **Q14** in `OPEN_QUESTIONS.md`.

---

## v6 (2026-06-02, D099) — percentile-parameterized thresholds for the firing-starved indicators

**Why a second pass:** the absolute ranges above were audited once on SPY and applied to every ticker. An absolute threshold fires at an **uncontrolled, name-dependent rate** — the 2026-06-02 firing decomposition put the binding constraint on discovery at signal *firing* (~70% of decided runs never trade; `mean_reversion` ~78% directional-never-fired = absolute `rsi_2` too tight; `trend_continuation` ~58% regime-gated). The fix (Crucible's own DESIGN §5.2): for raw-unit indicators, emit a **percentile of the indicator's own trailing distribution** instead of an absolute value, so firing rate is controlled *by construction* per name.

**Mechanism (`indicator_thresholds.py`):** an `IndicatorThresholdSpec` may carry `directional_percentile_range` / `regime_percentile_range` (a `(low, high)` in **[0, 1]**). When set for the sampled role, `sample_threshold_params` emits `params = {threshold: <pct>, op, use_percentile: True, percentile_window: 252}` — same `op` as the absolute table (percentile swaps the *units* of `threshold`, never the firing direction), same single `rng.uniform` draw (so the seeded sequence is unchanged — hard rule #6). Crucible ranks the latest value vs its trailing 252 bars and compares the percentile. The percentile branch **bypasses** the native-unit auto-tightening (D073): a native tightening is meaningless for a [0,1] percentile (and the loader's baseline check rejects it anyway).

**Scope (operator decision 2026-06-02, "exclude dealer_positioning directional"):**

| (indicator, role) | percentile range | intent |
|---|---|---|
| `rsi_2`, `rsi_14`, `rsi`, `zscore_returns`, `bb_pct` — directional | `(0.05, 0.20)`, op `<` | enter in the bottom 5-20% of the oscillator's own distribution |
| `adx` — regime_filter | `(0.25, 0.50)`, op `>` | loosen the trend gate: allow ~top 50-75% |
| `hurst` — regime_filter | `(0.50, 0.75)`, op `<` | loosen the gate (op preserved; **see Q26** — the `<` direction looks backwards for trend_continuation) |

**Left absolute (out of scope):** `dealer_positioning` directional (call/put-wall, gamma-flip — the only `mean_reversion`-directional overlap with `volatility_event`); already-rank `iv_rank` / `rv_rank` (percentile-by-construction); and the entire `volatility_event` indicator set (`days_to_*`, vol indicators) — it fires in ~every fold, so D099 deliberately does not touch it. Because `mean_reversion`-family directional indicators are sampled only by `mean_reversion`, and `adx`/`hurst` are `trend_strength` (regime-only, not in `volatility_event`'s R3 gate), this `(indicator, role)` allowlist provably cannot leak into `volatility_event`.

**Coordination:** percentile mode is interpreted on Crucible's side in **two** paths — the strategy/backtest path (`494cf96`) and the feature-cache writer that answers Forge's pre-filter `activation_dates` queries (`PROMPT_CRUCIBLE_PERCENTILE_FEATURE_CACHE.md`). ~~Forge holds v6 emission undeployed until both are live.~~ *(Historical: both paths went live and v6 deployed 2026-06-02; the grammar has moved many versions past v6 since — `config/grammar.yaml` for the current version.)* The percentile ranges here are calibrated to *intent* (loosen the diagnosed-too-tight constraints), not to SPY data — they are tunable as the `crucible funnel --compare v5 v6` signal comes in.

---

## v18 (2026-06-11, D135) — adoption-cut entries, audited against the live feature cache

The D031 SPY audit predates these ids; their ranges were calibrated with a live
`FeatureCacheClient` activation-count sweep (2026-06-11, 6-10 names x ~2,119
bars each, `data_history_days=2400` — the Q31 probe pattern). Raw numbers in
D135.

| indicator | role | range | op | calibration evidence |
|---|---|---|---|---|
| `iv_term_slope` | directional | `(0.01, 0.04)` | `>` | dense series (non-NaN ≈ every bar, all names). Median ≈ +0.005..+0.01; `> 0.01` fires ~44-49% of bars, `> 0.04` ~5-20% → the range spans above-median to clearly-steep at the same ~10-50% selectivity band as `iv_minus_rv`. Units: annualized IV decimals (back ≈ 90cal ATM IV − front ≈ 30cal). |
| `pre_earnings_setup` | regime_filter | `(0.5, 0.5)` | `>` | binary composed gate — threshold degenerate by design (the `market_state` precedent). The real knobs ride the same params via `_sample_pre_earnings_setup_params`: `enter_min ∈ {5..9}` / `enter_max ∈ {12..16}` **calendar** days (centered on the literature's [7, 14]) + `rv_q ∈ [30, 60]` on the rv_rank-native [0, 100] scale. At [7,14]/q50 the gate fires 114-152 days/name — above the §5.3.3 `min_activations=30` floor. |
| `option_momentum` | — | **no entry** | — | **deliberately unsamplable.** The probe found the series data-starved on the current tier: 0 non-NaN bars over ~8.5y on MSFT/AMZN/GOOGL/META/NFLX/TSLA; 22-146 on AAPL/AMD/KO; ≤26 activations under percentile mode — below the `min_activations=30` floor at every parameterization. Q39 tracks re-activation; horizon already shelf-classed (126 td). |

**iv_term_slope failure mode (their as-built note):** imminent earnings inflate
front IV → fake-NEGATIVE slope → the `>` gate goes *quiet* pre-earnings — a
conservative miss, not a false fire. Corollary: an `iv_term_slope` directional
paired with the `pre_earnings_setup` gate is thesis-contradictory (the gate
admits exactly when the slope reads fake-negative); such draws are C1-legal and
will mostly die at the expected-trades prefilter — watch, don't special-case.
