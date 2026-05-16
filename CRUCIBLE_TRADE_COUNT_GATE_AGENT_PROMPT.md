# Crucible — `min_oos_trade_count` vs swing-DTE structural mismatch

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-15 — Forge operator + reviewer flagged during 28-batch zero-promotion streak audit.

---

## 1. The pattern

Across 1000 sampled gated runs from `~/optbt_data/exports/gated_runs_2026-05-15T185806Z.json`:

```
total runs: 1000
decisions: {'reject': 1000}
trade_count: min=0 max=0 mean=0.0
```

**Every single Forge-submitted strategy in the export window produced trade_count=0.**

Top failing gates (count of runs each gate rejected):

```
min_oos_trade_count        : 1000/1000  (100%)
walk_forward_sharpe_median : 1000/1000  (cascades from trade_count=0)
cpcv_sharpe_p25            : 1000/1000  (cascades)
profit_factor              :  928/1000
sharpe_baseline            :  910/1000
deflated_sharpe            :  898/1000
```

`min_oos_trade_count` is the primary gate. Everything downstream cascades from "no trades to score."

## 2. The Forge-side fix already shipping (don't duplicate)

Forge committed D031 today (`/home/aj/proj/Forge/IMPLEMENTATION_DECISIONS.md` D031):

1. Re-triggered `crucible-registry-publisher.service` so Forge sees `version=2` metadata (was reading 24h-stale `version=1` snapshot).
2. Widened threshold ranges for three low-fire indicators (`vix_level`, `pairs_zscore`, `zscore_returns`) in `src/forge/enumeration/indicator_thresholds.py` to fire more often on real SPY data.

That addresses ~half the problem (some configs were sampling thresholds that virtually never fire on the OOS window). It is **not expected to solve** the underlying structural question this prompt is about.

## 3. The structural question — for you to investigate and decide

**Hypothesis:** `min_oos_trade_count=30` may be structurally incompatible with `swing_short` (14-21 DTE) strategies on a single ~60-90 day OOS window, regardless of any Forge calibration.

**Reasoning:**
- A `swing_short` config holds each position 14-21 days
- Non-overlapping trades on a 91-day OOS window cap at ~4-6 trades
- Even continuous daily firing of the entry predicate produces at most ~6 non-overlapping trades
- The gate requires `trade_count >= 30`
- Therefore: any honest swing strategy is structurally rejected, regardless of grammar quality

Sample gated_run metadata from the export:

```
period_start: 2025-06-04
period_end:   2025-09-02     ← single ~91-day OOS window
trade_count:  0
metrics keys: ['total_return','cagr','volatility_annual','max_drawdown',
               'max_drawdown_duration_days','sharpe','sortino','calmar']
```

## 4. Questions to answer

Please investigate and report back:

1. **Aggregation semantics**: Does `min_oos_trade_count=30` apply to a single OOS window, or does it aggregate across multiple walk-forward windows? Cite the gate's evaluator code and the runner's walk-forward driver.

2. **Per-DTE calibration**: Was `30` calibrated for a specific DTE bucket (e.g. day-trade / 0DTE / weekly)? Is there a per-`dte_bucket` threshold scheme, or one global value?

3. **Position-overlap policy**: Does Crucible allow overlapping positions (so a swing strategy firing daily can hold 14 concurrent positions)? Or one-position-at-a-time? If overlapping, what's the max concurrent and how does that interact with `ABSOLUTE_MAX_CONCURRENT_RISK_PCT`?

4. **Recommended fix shape**: Given the answers above, which of these is correct?
   - (a) Lower `min_oos_trade_count` (or make it DTE-bucket-aware: 30 for short-DTE, 5-10 for swing)
   - (b) Confirm walk-forward aggregation is happening and the 30 threshold IS reachable across N windows — in which case Forge's pattern of seeing trade_count=0 per export row is a *display/export* issue, not a gating one
   - (c) Force position-overlap in the runner for swing strategies
   - (d) Forge should filter `swing_short` from enumeration entirely (operator decision; would shrink hypothesis space considerably)

## 5. What you should NOT do

- **Do not change Forge code**. The Forge-side recalibration (D031) is already done.
- **Do not lower other gates** (sharpe_baseline, deflated_sharpe, etc.) — those cascades disappear once trade_count is non-zero. The root cause is `min_oos_trade_count`; fix that and the cascade resolves.
- **Do not loosen the gate** without a Decision Log entry citing why the new threshold is honest for the strategy class.

## 6. Background data sources

- Forge submissions DB: `~/forge_data/forge.db`, table `submissions` (3584 rows as of this writing; query examples in the session log)
- Crucible runs DB: `~/optbt_data/runs.duckdb` (1.2 GB, actively written; use the writer's DBProxy / shared connection rather than direct read while writer holds lock)
- Gated runs export: `~/optbt_data/exports/gated_runs_2026-05-15T185806Z.json` (1000 runs, 100% reject)
- Crucible gates implementation: search `gate_results` / gate evaluator under `src/optbt/` — start at the runner's gate-result construction site
- Walk-forward driver: search for `walk_forward` / `cpcv` under `src/optbt/`

## 7. Output expected

Report back with:
1. A definitive answer to questions 1-3 (cite file:line)
2. A recommended fix (a/b/c/d above, or a different shape if the data suggests one)
3. If the fix is your work: ship it + a Decision Log entry in `CRUCIBLE_CHANGES.md` (or whichever Crucible-side log is canonical) citing this prompt
4. If the fix needs operator approval: surface the trade-off and stop

Brief is OK. Aim for under 500 words of report unless the investigation reveals something material.
