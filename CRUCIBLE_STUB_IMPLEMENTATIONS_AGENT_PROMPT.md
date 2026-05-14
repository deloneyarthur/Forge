# Crucible stub-indicator implementations

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/docs/INDICATOR_THRESHOLDS.md`, `/home/aj/proj/Forge/OPEN_QUESTIONS.md`.
**Operator authorization:** 2026-05-14 — Path A (D028) was "Crucible implements all 10 missing indicators" but the implementation shipped 5 as no-op stubs (return NaN). This brief asks for honest implementations.

---

## 1. The problem

Crucible v3 (`phase9v3`) registered 10 new indicators in the registry to close Q12's vocabulary gap. Five of them are functional; **five are NaN-returning stubs**:

| Stub | Family | What it should return |
|---|---|---|
| `iv_rank` | iv_structure | Rank of current ATM IV vs trailing-N IV history, 0-100 |
| `vix_level` | macro | VIX index value per date |
| `put_call_flow` | dealer_positioning | Daily call_volume − put_volume / total, signed |
| `pairs_zscore` | pairs | Rolling spread z-score for a configured ticker pair |
| `expected_value_estimator` | smart_money | Trailing EV (win_rate × avg_win − loss_rate × avg_loss) for Kelly sizer |

Forge's audit (`docs/INDICATOR_THRESHOLDS.md`, 2026-05-14) measured each on SPY 2020-2025 bars and confirmed all 5 produce NaN throughout. This means:

- Any Forge config using one of these indicators as its directional or regime signal scores **0 activations** under the real feature cache.
- §3.5 R1 (mean_reversion → `iv_rank` regime gate) is **structurally unsatisfiable** today.
- §3.5 X2 (fractional Kelly sizer → `expected_value_estimator`) is unsatisfiable.
- ~30-40% of Forge's enumeration space is dead-on-arrival.

The operator's direction (2026-05-14): these indicators **should be properly implemented** so the grammar's spec language works end-to-end.

---

## 2. Scope — implement each indicator honestly

Each indicator gets one file under `src/optbt/features/<family>/<name>.py`, registered via `@register`, with `ClassVar id/version/lookback` and `compute(bars: pl.LazyFrame) -> pl.Series`. Tests under `tests/unit/features/`.

### 2a. `iv_rank` (highest priority — blocks §3.5 R1)

**Math:** `(current_atm_iv − min(history)) / (max(history) − min(history)) × 100`, where history is the trailing `window` (default 252 trading days) of ATM IV values. Clamp output to [0, 100]. Already implemented as `iv_history.iv_rank()` — wrap in an `@register`ed IndicatorBase subclass with id `iv_rank`.

**Data dependency:** ATM IV per date per underlying. `features/iv/atm_iv.py::compute_atm_iv()` exists; needs to be applied across the chain_snapshots history. The current stub returns NaN because the daily-ATM-IV pipeline isn't wired through `compute(bars_lazy)`. The fix may need a separate per-date computation that joins chain_snapshots to bars dates.

**Acceptance:** After this lands, Forge's `iv_rank` activation count on SPY 2020-2025 should be ~30-70% (rank values < 30 fire). Specifically: `forge prefilter --max 200 --seed 42 --summary` shows non-zero survival for mean_reversion hypotheses.

### 2b. `vix_level`

**Math:** Just the VIX index value per date. Already there is `features/macro/vix.py` — but apparently it's not wired into the registered `vix_level` indicator. Either:
- Wrap `features/macro/vix.py`'s function in a registered IndicatorBase subclass.
- OR if no VIX data is ingested yet, add a small ingest step (Polygon ticker `I:VIX`).

**Data dependency:** VIX daily close bars. Probably needs ingestion to `bars_underlying/symbol=VIX/` or a separate macro-bars location.

**Acceptance:** `vix_level` returns valid values (12-80 range typically) for every trading day in the SPY bars window. Forge's audit shows VIX < 30 ~70-80% of days under threshold-style queries.

### 2c. `put_call_flow`

**Math:** `(call_volume − put_volume) / (call_volume + put_volume)` per date, range [-1, 1].

**Data dependency:** Daily call/put volume from chain_snapshots. Check if `chain_snapshots/` parquet files have a `volume` column. If yes, aggregate per date; if no, document the data gap.

**Acceptance:** `put_call_flow` returns values in [-1, 1] for every trading day. Forge's audit shows the metric varying across the window (not constant).

### 2d. `pairs_zscore`

**Math:** For a configured ticker pair (e.g., XLF/XLU), compute log spread `log(y) − β × log(x)` where β is the OLS hedge ratio from `features/pairs/cointegration.py`, then rolling z-score of that spread over `window` (default 60).

**Data dependency:** Bars for both legs of the pair. `config/pair_candidates.yaml` exists with curated pairs.

**Open question:** Forge's grammar produces SignalSpecs where `indicators=("pairs_zscore",)` but doesn't currently specify WHICH pair. Two paths:
1. Parametrize via `signal.params["leg_a"]` / `signal.params["leg_b"]` — requires Forge enumerator to pick pairs.
2. Hardcode a default pair (e.g., first entry in `pair_candidates.yaml`) — simpler v1.

Pick (2) for v1; flag (1) as a Forge follow-on.

**Acceptance:** `pairs_zscore` returns values typically in [-3, 3]. Forge's audit shows variation across the window.

### 2e. `expected_value_estimator` (most complex)

**Math:** `win_rate × avg_win − loss_rate × avg_loss` over a trailing window of signal firings. **This is signal-self-referential** — needs the *prior* trade outcomes for the same signal.

**Data dependency:** Prior trade outcomes per signal. Crucible's `trades` table has this but it's per-`run_id`, not per-signal. Either:
1. Aggregate trades by `(strategy_id, signal_id)` across all completed runs → compute EV per signal.
2. Maintain a separate per-signal trade-history table populated by the backtest runner.

For v1: implement as `compute_ev_for_signal(signal_id, lookback_window)` that queries the runs DB for prior trades matching the signal. If no prior trades exist (cold start), return NaN. As Forge submits more configs and Crucible accumulates trades, the EV becomes meaningful.

**Acceptance:** Returns NaN for new/unseen signals (cold start), real values once ≥ 30 trade outcomes accumulated. Forge's X2 rule then becomes meaningful for Kelly sizing.

---

## 3. Per-indicator deliverables

Per the existing `iv_rank.py` / etc. shape:
- `src/optbt/features/<family>/<name>.py` — `IndicatorBase` subclass with `@register`, `id`, `version=2` (bump from v1 stub), `lookback`, `params_schema`, and a working `compute(bars: pl.LazyFrame) -> pl.Series`.
- `tests/unit/features/<family>/test_<name>.py` — `IndicatorBase` contract + value-distribution sanity (a smoke test that produces > 100 non-NaN values on SPY 2020-2025).

For the data-dependent ones (vix_level, put_call_flow, expected_value_estimator), include in your PR description any new data ingest steps or scripts.

---

## 4. Acceptance criteria

This work is done when **all** of:

1. Each of the 5 stubs has a registered IndicatorBase subclass producing non-NaN values on real SPY bars.
2. `forge prefilter --max 200 --seed 42 --summary` (run after restarting `forge.service`) shows **non-zero survival** across all hypotheses (currently ~0%).
3. §3.5 R1 (mean_reversion + iv_rank) and §3.5 X2 (fractional Kelly + expected_value_estimator) produce viable configs.
4. Tests pass: per-indicator unit test + full Crucible suite green.
5. Existing v3 indicator versions are bumped from `version=1` to `version=2` so the feature_cache table's window_hash invalidates the old stub entries.

---

## 5. Out of scope

- **Forge-side changes** — Forge's `docs/INDICATOR_THRESHOLDS.md` already documents what threshold values each indicator should use. Forge's enumerator (`sampler.py`) consumes that table.
- **New grammar rules** — §3.5 R1 / X2 stay as-is; this work makes them viable, not different.
- **Multi-underlying** — v1 stays SPY-only; multi-underlying is a separate workstream.
- **Real options-flow tape** — `put_call_flow` uses chain_snapshots volume; the upstream Polygon-flow-tape integration is separate.

---

## 6. Hand-off back to Forge

When done:

1. Restart `crucible-db-writer.service` so the indicator registry reloads.
2. Forge's `CrucibleFeatureCache` will start serving non-NaN data automatically on next batch.
3. Operator restarts `forge.service`; the loop sees real activations + survival above 0% for the first time on these indicators.

---

## 7. References

- Forge audit: `docs/INDICATOR_THRESHOLDS.md` (per-indicator distributions on SPY 2020-2025).
- Forge `OPEN_QUESTIONS.md` Q13 (synthetic-cache rejection symptoms), Q14 (threshold-semantics + stub implications).
- Forge `IMPLEMENTATION_DECISIONS.md` D028 (Path A) + D029 (v1 go-live) + D030 (indicator-aware thresholds, pending commit).
- Crucible v3 commit `phase9v3` (where the stubs originally landed).
- Crucible v3+1 commit `b447597` (writer-served feature cache; the new stubs ride on this).

Implement slowly. Test ruthlessly. The audit is your ground truth.
