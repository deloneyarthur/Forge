# Crucible: per-request telemetry for the db-writer feature_cache path

**Authored:** 2026-05-19 (Forge-side; for hand-off to a Crucible agent in `/home/aj/proj/Crucible/`)
**Audience:** Crucible maintainer / agent
**Severity:** MEDIUM — operational visibility; not blocking, but the operator currently can't diagnose Crucible-side slowness without it

---

## Problem

Forge's iter 37 has spent **1h40m+ blocked in `multiprocessing.connection._recv()` on the feature_cache socket** while waiting for `get_features` responses. Forge-side observation (via `py-spy dump`):

```
Thread 2951629 (idle): "MainThread"
    _recv (multiprocessing/connection.py:395)
    get_features (crucible_contracts/feature_cache.py:154)
    _fetch_activation_dates_chunked (forge/prefilters/crucible_feature_cache.py:157)
    prefetch_for_batch (forge/prefilters/crucible_feature_cache.py:235)
    ...
```

Crucible-side observation (`ps` on PID 2893613, the db-writer):
- 219% CPU sustained
- 400 min CPU time consumed since process start
- 646 MB RSS

So the db-writer is **legitimately computing hard** — not idle, not stuck, not network-bound. The work is happening in DuckDB's C++ executor / numpy / polars hot paths that `py-spy` can't introspect (it only sees Python frames).

But the operator has no way to see **what** the writer is computing, **how long each request takes**, or **which signal-specs are pathological**. Today's `db-writer` journal logs only at `db_writer_started` / `db_writer_ready` / `db_writer_server_started` / `db_writer_server_stopped` / `db_writer_request_failed` levels — nothing on the happy path.

## Fix scope

Add per-request structured logging to the `_serve_client` handler (or wherever individual feature_batch / feature requests are dispatched, roughly `src/optbt/persistence/db_writer.py:_serve_client`). For each request received, log:

```json
{
  "event": "db_writer_request_handled",
  "request_kind": "feature_batch",          // or whatever the dispatch tag is
  "feature_names": ["activation_dates"],     // tuple of feature names requested
  "n_signals": 500,                          // count of SignalSpecs in the request
  "underlying": "SPY",
  "data_history_days": 1008,
  "elapsed_ms": 42117,                       // wall-clock duration from request-received to response-sent
  "level": "info",
  "timestamp": "<ISO-8601 UTC>"
}
```

The `n_signals=500` + `elapsed_ms=42117` combination is the critical pair: it tells the operator "this chunk took 42 sec for 500 specs," which lets them spot outliers like "chunk 7 took 8 min" and correlate with specific signal types.

## Optional secondary (operator-tunable verbosity)

If individual specs in a chunk vary widely in cost (e.g., GEX/VEX/CEX dealer-positioning indicators are 10-100x slower than RSI), an additional `db_writer_signal_timing` event at DEBUG level (off by default) would let the operator drill in:

```json
{
  "event": "db_writer_signal_timing",
  "request_kind": "feature_batch",
  "signal_content_key": "<hash from crucible_contracts.signal_content_key>",
  "indicator_id": "gex",
  "feature_name": "activation_dates",
  "elapsed_ms": 4221,
  "level": "debug"
}
```

Toggle via env var `CRUCIBLE_DB_WRITER_LOG_PER_SIGNAL=1` so production doesn't drown in logs.

## Where the change probably lives

`src/optbt/persistence/db_writer.py:_serve_client` is the per-client request loop. The pattern is roughly:

```python
def _serve_client(self, client_conn):
    while not self._stopping:
        if not client_conn.poll(timeout=0.5):
            continue
        request = client_conn.recv()
        # ... dispatch by request kind ...
        response = self._handle_request(request)
        client_conn.send(response)
```

Wrap the `_handle_request` call with `time.monotonic()` deltas, extract the relevant request fields, and emit one log line on successful completion (or on the existing error path, which already logs).

## Verification

1. Run a single `forge run --prefilter` (or equivalent dry-run that exercises the feature_cache) and confirm one `db_writer_request_handled` log line per chunk.
2. The `n_signals` + `elapsed_ms` per line should sum roughly to the total Forge-side prefetch wall time.
3. The `db_writer_request_failed` path should remain unchanged (already logged today).

## Out of scope (do not change here)

- The actual feature compute path (no perf changes).
- The socket protocol or request schema.
- Forge-side code.

## Operator wishlist (separate, larger work — not part of this prompt)

Once the per-request telemetry surfaces hot signals/underlyings, the bigger lever is **bulk activation-dates computation**: today Forge sends 500 separate (signal_spec, "activation_dates") pairs per chunk and the writer presumably loops, invoking each indicator independently. A bulk SQL plan that computes activation_dates for all 500 specs in a single DuckDB query (joining the bars table once and applying 500 threshold predicates) could be 10-100x faster. The telemetry this prompt asks for is the prerequisite that lets the operator measure that proposed rewrite's payoff.

## Coordinate doc

Forge-side reference: the current iter 37 stall (forge service journal `2026-05-19T20:50:50Z` start, still in prefetch as of `2026-05-19T22:30Z`). No Forge-side commit gates on this change — once the telemetry ships, the operator can read the existing db-writer journal. Delete this prompt file after the change lands; reference in a Crucible commit message is sufficient.
