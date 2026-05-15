# Crucible EV-indicator deadlock fix

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/` (do not edit).
**Operator authorization:** 2026-05-14 — this blocks Forge's v1 pipeline.

---

## 1. The bug

`expected_value_estimator` (committed in `b323afc`) calls back into the
writer socket via `DBProxy` from inside `compute()` to fetch the
`trades` table. The writer holds `self._db_lock` for the entire
`compute_feature_batch` call (`db_writer.py:567`). The nested DBProxy
connection spawns a new handler thread, which tries to acquire the
same `db_lock` and blocks indefinitely. The outer compute waits on EV.
**Self-referential deadlock.**

Observed symptoms (Forge v1 pipeline, 2026-05-14, 19:17 PDT onward):
- Writer + Forge processes both at ~0% CPU for 80+ minutes
- `runs.duckdb.wal` and `db_writer.wal` unchanged since iteration start
- Zero writer log entries since service start
- `ss -x` shows ESTABLISHED unix-socket connections with no data flowing
- Writer wchan: `futex_do_wait`; Forge wchan: `unix_stream_read_generic`

Anything that submits a `feature_batch` request whose `signals` contains
even one `expected_value_estimator` spec will deadlock the writer
permanently (only `systemctl --user stop crucible-db-writer.service`
breaks it).

## 2. Recommended fix — request-scoped BatchContext

`compute_feature_batch` should pre-load all writer-resident data the
per-spec compute might need, attach it to a request-scoped context,
and run the per-spec compute against the in-memory context. Indicators
that need writer-resident lookups (today: EV; tomorrow: anything
querying signals_fired, trades, runs) read from the context — no
nested socket call.

Sketch:

```python
# optbt/persistence/feature_cache.py
@dataclass(frozen=True)
class BatchContext:
    underlying: str
    bars: pl.DataFrame
    trades: pl.DataFrame | None      # NEW — None if 0 rows or read failed
    # add fields as new indicators need them; keep all per-batch-fixed

def compute_feature_batch(request, *, conn, data_root):
    bars = load_bars(...)
    trades = _load_trades_for_underlying(conn, request.underlying)
    ctx = BatchContext(underlying=request.underlying, bars=bars, trades=trades)
    _CURRENT_BATCH_CTX.set(ctx)              # contextvar
    try:
        ...
        for spec in request.signals:
            fired = compute_activation_dates(spec, bars)   # already exists
            ...
    finally:
        _CURRENT_BATCH_CTX.reset(...)
```

Then `expected_value_estimator._fetch_completed_trades` checks
`_CURRENT_BATCH_CTX.get(None)` first; if present, reads from
`ctx.trades` (no socket call). Falls back to the current
DBProxy → direct-RO ladder when called outside a batch (tests,
ad-hoc CLI use).

This eliminates the deadlock **architecturally** — not just for EV.

## 3. Smaller stop-gap (acceptable if you want a 1-day fix)

If the full context refactor is too much surface for one branch, the
minimum viable fix is:

1. In `compute_feature_batch`, before the per-spec loop, do
   `trades = _load_completed_trades(conn, request.underlying)` once
   (it's a single SELECT under the already-held db_lock).
2. Stash on a `contextvars.ContextVar` (`_CURRENT_BATCH_TRADES`).
3. In `expected_value_estimator._fetch_completed_trades`, check the
   ContextVar first; if present, return the cached DataFrame. Otherwise,
   fall through to the existing DBProxy → direct-RO ladder.

This is ~30 lines, scoped to two files. The full BatchContext refactor
generalizes the same pattern but is the right long-term shape.

## 4. Acceptance criteria

This is done when **all** of:

1. New regression test: `tests/integration/test_feature_batch_deadlock.py`
   submits a `FeatureBatchRequest` containing at least one
   `expected_value_estimator` spec against a running writer; the
   request completes in <30s (currently hangs forever).
2. EV indicator produces equivalent values to before (verify on a
   warm trades table — at least one prior backtest run in the DB).
3. EV unit tests still pass (`pl.read_database` / direct-RO paths
   when called outside the writer's request scope).
4. Full Crucible test suite green (`uv run pytest`).
5. `ruff check` + `mypy --strict` clean on changed scope.
6. No new writer threads spawned per feature_batch request when the
   request contains only EV specs (verify via `ps -T`).

## 5. Hand-off back to Forge

When done:

1. Restart `crucible-db-writer.service`.
2. Forge will resume its pipeline; iteration 1 will hit the EV-using
   configs without deadlocking.
3. Forge will re-enable EV in its sampler (currently treating it as
   skippable as a temporary unblock — Forge change is reversible).

## 6. Out of scope

- Forge-side changes — Forge will re-enable EV after Crucible ships.
- Any change to the v1 stubs other than EV.
- Re-architecting the writer's single-lock design (the BatchContext
  approach works within the current single-lock model).
- Pushing your branch (operator pushes manually).

## 7. References

- The deadlock-introducing commit: `b323afc` (EV v2).
- The lock acquisition: `src/optbt/persistence/db_writer.py:567`.
- The recursive socket call: `src/optbt/features/smart_money/expected_value_estimator.py:204`.
- Forge OPEN_QUESTIONS.md (will be updated post-mortem with Q15
  pointing back to this brief).

Build slowly. Test ruthlessly. The deadlock test is your ground truth.
