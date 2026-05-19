# Crucible: vectorize `iv_rank.compute` per-date hot loop

**Authored:** 2026-05-19 (Forge-side observation; for hand-off to a Crucible agent in `/home/aj/proj/Crucible/`)
**Audience:** Crucible maintainer / agent
**Severity:** HIGH — single-handedly responsible for ~2-3h forge iteration wall time (3x the post-restart baseline)

---

## Problem

Forge's iter 37 has spent **2h53m** blocked in `multiprocessing.connection._recv()` on the feature_cache socket waiting for a single `feature_batch` response. The Crucible db-writer is alive and burning 219% CPU sustained (557+ minutes of CPU time accumulated) — not stuck, not idle, just **legitimately slow**.

`py-spy dump --pid <db-writer>` reveals exactly one active thread, in `iv_rank` compute:

```
Thread 2951771 (active+gil): "db_writer_client"
    _coerce_date              (optbt/features/iv/iv_rank.py:188)
    _select_near_term_maturity (optbt/features/iv/iv_rank.py:158)
    _atm_iv_for_date          (optbt/features/iv/iv_rank.py:139)
    compute                   (optbt/features/iv/iv_rank.py:93)
    compute_activation_dates  (optbt/persistence/feature_cache.py:178)
    _compute_feature_batch_locked (optbt/persistence/feature_cache.py:606)
    _execute_feature_batch    (optbt/persistence/db_writer.py:611)
    _serve_client             (optbt/persistence/db_writer.py:529)
```

All other db-writer Python threads are idle in `poll`/`select`. So the entire prefetch latency is in this one call path.

The hot loop is `IVRank.compute` at `src/optbt/features/iv/iv_rank.py:82-94`:

```python
# Pull per-date ATM IV across the entire bars window.
atm_ivs: list[float] = []
for raw_dt, raw_close in zip(
    bar_dts_df["dt"].to_list(),
    bar_dts_df["close"].to_list(),
    strict=True,
):
    d = _coerce_date(raw_dt)
    if d is None or raw_close is None:
        atm_ivs.append(float("nan"))
        continue
    spot = float(raw_close)
    atm_ivs.append(_atm_iv_for_date(store, underlying, d, spot=spot, r=rfr))
```

For each of ~1,008 bar dates in the lookback window, `_atm_iv_for_date` does **disk I/O** (chain-snapshot existence check + parquet load) then **Python-level math** (expiry filtering + `compute_atm_iv` call). When `IVRank.compute` is invoked by `compute_activation_dates` for every signal spec in a Forge batch (5,000 specs in the current prefetch), the work compounds: even with parquet feature caching, the **per-date Python iteration is the dominant cost**.

Followed by a second per-row loop at lines 96-114 that computes the trailing rank — also Python-level, sliced per iteration via `history_series.slice(...)` rather than a vectorized rolling computation.

## Why this matters

The §4.3.4 ATM IV math itself is fine. The bottleneck is structural: **per-date Python iteration where a single polars/SQL plan would express the same computation**.

Concrete ask scope: rewrite `IVRank.compute` so that the inner loops become vectorized polars or SQL operations. Two specific opportunities:

1. **Per-date ATM IV (lines 82-94)** — instead of a per-bar-date loop that reloads chain snapshots one at a time, load all chain snapshots for the underlying / date range in a single `pl.read_parquet(...).filter(asof_date in dates)` (or equivalent partition scan), then compute ATM IV vectorized across dates. The current `_atm_iv_for_date` is "expiry filter + `compute_atm_iv`" per date; both can be expressed as polars group_by + udf over the joined DataFrame.

2. **Trailing rank pass (lines 96-114)** — the per-row Python loop with `history_series.slice(...)` is equivalent to `iv_series.rolling_min(window)` + `iv_series.rolling_max(window)` followed by `(current - rolling_min) / (rolling_max - rolling_min) * 100`. Polars has native rolling reducers in C++; the Python loop is ~50-100x slower at scale.

The docstring already states "Both steps memoize their per-date ATM IV results in the parquet FeatureCache (root = data_root / 'feature_cache_partitions') so re-running over the same date range is near-free after first compute" — but the live evidence (2h53m and counting) shows the cache isn't hitting often enough to dominate. Worth confirming whether `_compute_feature_batch_locked` cache-key construction includes per-signal-spec parameters (threshold value, op) that change every spec; if it does, the cache misses on every new spec even though the underlying ATM-IV-per-date data is identical.

## Suggested approach (sketch)

```python
# Vectorized ATM IV per date
chain_partition_files = sorted(
    (data_root / "chain_snapshots" / f"underlying={underlying}").glob(
        "asof_date=*/data.parquet"
    )
)
chains_all = pl.scan_parquet(
    [str(p) for p in chain_partition_files],
    hive_partitioning=True,
).filter(pl.col("asof_date").is_in(target_dates))

# Pick near-term maturity per asof_date (single group_by)
near_term = (
    chains_all
    .with_columns((pl.col("expiry") - pl.col("asof_date")).dt.total_days().alias("dte"))
    .filter(pl.col("dte") >= _MIN_DTE_DAYS)
    .sort(["asof_date", "dte"])
    .group_by("asof_date")
    .first()
    .select(["asof_date", "expiry"])
    .collect()
)

# Join back to get one_maturity per asof_date, then call compute_atm_iv via udf
# (or inline its math if numerically straightforward)

# Trailing rank — polars rolling reducers
iv_series = ...  # the per-date atm IV polars Series
mins = iv_series.rolling_min(window_size=window, min_periods=1)
maxs = iv_series.rolling_max(window_size=window, min_periods=1)
denom = maxs - mins
rank = pl.when(denom == 0).then(50.0).otherwise((iv_series - mins) / denom * 100)
```

Names are illustrative; the agent should adapt to the actual partition layout and `DataStore` API.

## Verification

1. **Functional parity** — the existing iv_rank unit tests must continue to pass. Add a test that compares vectorized output against the current per-date loop on a known fixture (10-20 dates, hand-traced).
2. **Performance** — a representative timing harness. For `IVRank.compute(bars)` with `bars.height == 1008` and the SPY chain partitions populated, target **≤500 ms** for the full compute (vs current ~10-60 seconds per call observed via live profiling). The 100x target is realistic for the per-date loop → polars rolling rewrite.
3. **Cache key audit** — confirm `_compute_feature_batch_locked`'s cache key for activation_dates does NOT include the threshold value / op (only the indicator id + params that affect the value series). Threshold compare happens AFTER the value series is computed; cache should hit across spec-thresholds.

## Companion telemetry

The previously-shipped `CRUCIBLE_FEATURE_CACHE_TELEMETRY_AGENT_PROMPT.md` (2026-05-19 — see the Forge repo for the active version of that document) asked for per-request elapsed_ms logging. If that telemetry prompt has not yet shipped, including its hook here would let the operator measure the before/after of this vectorization directly in the journal.

## Out of scope

- Changing the §4.3.4 math itself (`compute_atm_iv`, near-term-maturity selection rule).
- Changing the IV rank formula (rank-in-trailing-window stays the same).
- Forge-side code.
- Any other indicator's compute path (this prompt targets `iv_rank` specifically; if `realized_vol`, `pairs_zscore`, etc. show similar profiles after telemetry lands, those are separate prompts).

## Coordinate doc

Forge-side reference: `OPEN_QUESTIONS.md` (no Q-entry yet — this is operational tuning, not a structural contract gap). Iter 37 of `forge.service` (start `2026-05-19T20:50:50Z`) is the live evidence; the py-spy stack above came from that process state. Delete this prompt file after the change ships and a forge iteration confirms reduced prefetch wall time.
