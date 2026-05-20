# Crucible: vectorize remaining per-bar Python loops + complete telemetry payload

**Authored:** 2026-05-19 (Forge-side observation; follow-up to the iv_rank vectorization that just shipped)
**Audience:** Crucible maintainer / agent
**Severity:** HIGH — same shape as the iv_rank bottleneck that consumed 3+ hours of forge iteration time; the dealer-positioning family hits every batch and is the new dominant cost

---

## Context

The iv_rank vectorization just landed and is working — `iv_rank.compute` is no longer in the db-writer hot path. Excellent. But a single Forge iteration (post-restart at 17:34) immediately surfaced a new bottleneck with the **same shape** as the old iv_rank bug. py-spy on the active db-writer thread (PID 3098888, post-restart):

```
Thread 3099518 (active+gil): "db_writer_client"
    pdf                        (scipy/stats/_distn_infrastructure.py:2082)
    gamma                      (optbt/features/dealer/greeks_math.py:103)
    _gex_at_hypothetical_spot  (optbt/features/dealer/aggregate.py:150)
    gamma_flip                 (optbt/features/dealer/aggregate.py:115)
    _fn                        (optbt/features/dealer/gamma_flip_distance.py:62)
    compute_per_bar            (optbt/features/dealer/_indicator_base.py:68)
    compute                    (optbt/features/dealer/gamma_flip_distance.py:70)
```

And `compute_per_bar` is **a shared helper used by 6 indicators**, all of which now compete for the same hot loop:

```
optbt/features/dealer/cex.py
optbt/features/dealer/gex.py
optbt/features/dealer/vex.py
optbt/features/dealer/gamma_flip_distance.py
optbt/features/dealer/call_wall_distance.py
optbt/features/dealer/put_wall_distance.py
```

The helper at `src/optbt/features/dealer/_indicator_base.py:23-74` is the iv_rank anti-pattern verbatim — per-bar Python iteration, per-date disk load, per-date `compute_fn` invocation:

```python
df = bars.select(["dt", "close"]).collect()
out: list[float] = []
for raw_dt, raw_close in zip(df["dt"].to_list(), df["close"].to_list(), strict=True):
    d = _coerce_date(raw_dt)
    if d is None or raw_close is None:
        out.append(float("nan")); continue
    if not store.chain_snapshot_exists(underlying, d):
        out.append(float("nan")); continue
    chain = store.load_chain_snapshot(underlying, d, columns=chain_columns)
    if chain.is_empty():
        out.append(float("nan")); continue
    try:
        out.append(float(compute_fn(chain, float(raw_close), d)))
    except Exception:
        out.append(float("nan"))
return pl.Series(series_name, out, dtype=pl.Float64)
```

**One fix to this function vectorizes 6 indicators at once** — the same structural payoff as iv_rank, applied at the shared base.

## Additional confirmed offender — flow/put_call_flow.py

`src/optbt/features/flow/put_call_flow.py:46-72` has the exact same per-date Python loop calling `_flow_ratio_for_date` which does `chain_snapshot_exists` → `load_chain_snapshot` → filter + sum:

```python
out: list[float] = []
for raw_dt in bar_dts_df["dt"].to_list():
    d = _coerce_date(raw_dt)
    if d is None:
        out.append(float("nan")); continue
    ratio = _flow_ratio_for_date(store, underlying, d)
    out.append(ratio)
return pl.Series("put_call_flow", out, dtype=pl.Float64)
```

Same vectorization opportunity: scan all chain partitions for the underlying once, group_by(asof_date), aggregate volume by `right`, return ratio per date.

## Audit candidates (please check + treat if same pattern)

These were flagged by a grep for `.to_list()` iteration or `for raw_dt` in `src/optbt/features/`:

- `src/optbt/features/iv/smile.py` — uses `.to_list()` iteration; confirm whether it falls in any active Forge submission path.
- `src/optbt/features/smart_money/expected_value_estimator.py` — uses DBProxy with SQL; likely already vectorized, but worth confirming under load (Forge's X2 fractional_kelly sizer chains this indicator into every config that picks that mode).

Calendar indicators (`days_to_fomc`, `days_to_cpi`, etc.) also use `.to_list()` but are cheap date arithmetic — not in scope unless py-spy shows them hot.

## Suggested approach (mirrors the iv_rank fix)

For both `dealer/_indicator_base.py::compute_per_bar` and `flow/put_call_flow.py::compute`:

```python
# 1. Bulk-scan all chain snapshots for the underlying / date range.
chain_files = sorted(
    (data_root / "chain_snapshots" / f"underlying={underlying}").glob(
        "asof_date=*/data.parquet"
    )
)
target_dates = set(df["dt"].to_list())
chains_all = (
    pl.scan_parquet([str(p) for p in chain_files], hive_partitioning=True)
    .filter(pl.col("asof_date").is_in(target_dates))
    .select(chain_columns + ["asof_date"])
    .collect()
)

# 2. Per-date scalar compute via group_by + udf
#    (for dealer indicators, compute_fn already accepts (chain, spot, asof)).
results = (
    chains_all
    .group_by("asof_date")
    .map_groups(
        lambda group: pl.DataFrame({
            "asof_date": group["asof_date"].head(1),
            series_name: [compute_fn(group, spot_for_date[group["asof_date"][0]], group["asof_date"][0])],
        })
    )
)

# 3. Left-join back to bars to preserve NaN for missing dates
out = bars.join(results, left_on="dt", right_on="asof_date", how="left")[series_name]
```

Names illustrative — adapt to the actual partition layout. The shape that matters: **one parquet scan total**, not one-per-bar-date. For the put_call_flow case the compute is even simpler (just `volume.filter(right="C").sum() / total`) and can be done as a single polars expression chain.

## Completing the telemetry payload (the second ask)

The `db_writer_request_handled` event now fires on every feature_batch request (visible in journal at `2026-05-20T00:34:46.122594Z`). But the JSON payload only contains `event`/`level`/`timestamp` — the `extra: {...}` fields (`request_kind`, `feature_names`, `n_signals`, `underlying`, `data_history_days`, `elapsed_ms`) **aren't being serialized to the output stream**, even though the code passes them in. Compare to `db_writer_ready` which DOES emit `extra: {"db": "...", "socket": "...", "wal": "..."}` correctly.

The code at `src/optbt/persistence/db_writer.py:530-545` (post-restart line numbers) is:

```python
logger.info(
    "db_writer_request_handled",
    extra={
        "request_kind": "feature_batch",
        "feature_names": list(parsed_req.feature_names),
        "n_signals": len(parsed_req.signals),
        "underlying": parsed_req.underlying,
        "data_history_days": parsed_req.data_history_days,
        "elapsed_ms": int((time.monotonic() - t_start) * 1000),
    },
)
```

That `extra={...}` form is the stdlib `logging` idiom which attaches the fields to the `LogRecord` but doesn't propagate them through the structlog formatter the rest of the codebase uses. Other events that emit correctly likely use the structlog-bound idiom, e.g. `log.info("event_name", request_kind=..., n_signals=..., elapsed_ms=...)` (kwargs as structured event keys) rather than the `extra={}` parameter.

Quick check: compare the call site of `db_writer_ready` (which serializes `extra`) to `db_writer_request_handled` (which doesn't) and apply the same idiom. Once that's done, the journal will carry per-request:

```json
{"event": "db_writer_request_handled", "extra": {"n_signals": 500, "elapsed_ms": 42117, "underlying": "SPY", ...}, ...}
```

— which is the prerequisite the original telemetry prompt asked for (without it, we can count requests but not measure them).

## Verification

1. **Functional parity for vectorization** — existing unit tests for each dealer indicator + put_call_flow must pass. Add one regression test comparing vectorized output to the prior per-bar output on a small fixture.
2. **Performance target** — `compute_per_bar` (after fix) for `bars.height == 1008`: **≤500 ms** total. Same target as iv_rank.
3. **Telemetry payload** — `journalctl --user -u crucible-db-writer.service | grep db_writer_request_handled | tail -1` should show a JSON line containing `"extra": {"n_signals": ..., "elapsed_ms": ..., ...}`.
4. **End-to-end** — restart `crucible-db-writer.service`, then a fresh Forge iteration's prefetch should complete in **≤15 min** (vs the current ~hours).

## Out of scope

- The dealer math itself (GEX/VEX/CEX greeks aggregation, gamma-flip detection, wall finding) — algorithm stays the same.
- Forge-side code.
- iv_rank (already vectorized).
- Crucible's runner / gauntlet.

## Coordinate doc

Forge-side references:
- The earlier iv_rank prompt (`CRUCIBLE_IV_RANK_VECTORIZATION_AGENT_PROMPT.md`) shipped 2026-05-19 — this is the same shape applied to the dealer family and put_call_flow.
- The earlier telemetry prompt (`CRUCIBLE_FEATURE_CACHE_TELEMETRY_AGENT_PROMPT.md`) shipped 2026-05-19 — `db_writer_request_handled` fires but its `extra` payload is missing; this prompt closes that loop.
- Live evidence: `forge.service` iter 37 restart at `2026-05-19T17:34:41 PT`. As of authoring, db-writer thread 3099518 is computing `gamma_flip_distance` per the py-spy stack above. The next forge `enumerated=` line will be the first signal that the dealer-family hot loop has been replaced.

Delete this prompt file after the changes land and a forge iteration confirms `≤15 min` prefetch wall time.
