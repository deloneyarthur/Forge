"""D111 — durable per-candidate Crucible verdicts.

WHY this exists: Crucible's gated-runs export is a rolling top-10k window.
Forge previously kept only batch-level aggregates (`promotion_rate`,
`common_failures`) plus a status flag, so the per-candidate decision
(component/reject/promote), the 11 gate values, and the realized trade count
were unrecoverable once a row rolled off the window — at the 2026-06-09 review
only 13.2% of all submissions had any verdict on record, and the feedback
weight loaders were hostage to whatever the current window happened to hold
(the 2026-06-07 re-gate spike alone was 70% of it).

`record_verdicts` sweeps an export snapshot against every config_hash Forge
has ever submitted and appends what's new. Keyed by `crucible_run_id`, so a
Crucible re-gate (new run_id, same config) appends a second row — verdict
history is preserved, never overwritten.

`decided_at` handling: aware datetimes are converted to UTC then stored naive
(the DB-wide D061 convention). Naive values pass through verbatim — the
export's current PDT-naive skew is a Crucible-side defect (fix requested via
PROMPT_CRUCIBLE_RUNNER_CAPACITY_STABILITY.md); shifting it here would
double-shift the moment Crucible starts emitting aware UTC.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from crucible_contracts import CONTRACT_VERSION

from forge.core.clock import utc_now

if TYPE_CHECKING:
    import duckdb
    from crucible_contracts import GatedRun


def record_verdicts(
    db: duckdb.DuckDBPyConnection,
    runs: list[GatedRun],
    *,
    source_export: str | None = None,
) -> int:
    """Insert one verdicts row per export run Forge submitted; return new-row count.

    Idempotent: rows whose `crucible_run_id` already exists are ignored, so the
    sweep is safe on every reconcile pass over an overlapping window.

    ``source_export`` (D315/2c, label provenance): the gated-runs export
    filename these runs were read from — stamped per row with the installed
    contracts version, so a future era cut (the ve ghost class) filters on a
    recorded column instead of reconstructing history. Best-effort: None (the
    DB-fallback path) leaves the column NULL.
    """
    if not runs:
        return 0
    known_hashes = {
        str(h) for (h,) in db.execute("SELECT DISTINCT config_hash FROM submissions").fetchall()
    }
    # Filter to submitted configs + normalize decided_at FIRST (both cheap), before
    # the expensive gate-results serialization. P0-2 (pipeline-perf audit): the old
    # path built json.dumps(gate_results) for every matching export row each pass —
    # ~10k on a rolling window — then INSERT OR IGNORE dropped the ~99% already
    # recorded. Skip the already-recorded runs here so the JSON (the reconcile cost)
    # is built only for the ~0-130 genuinely new runs.
    candidates: list[tuple[GatedRun, datetime]] = []
    for gr in runs:
        if gr.run.config_hash not in known_hashes:
            continue
        decided = gr.decision.decided_at
        if decided.tzinfo is not None:
            decided = decided.astimezone(UTC).replace(tzinfo=None)
        candidates.append((gr, decided))
    if not candidates:
        return 0
    # Window-bounded fetch of already-recorded run_ids: a run in this batch has
    # decided_at >= the batch minimum, so its existing verdicts row (same run, same
    # conversion) is captured — the skip is complete, and INSERT OR IGNORE stays the
    # race-safe backstop (append-only D111 history preserved either way).
    min_decided = min(d for _, d in candidates)
    existing_run_ids = {
        str(rid)
        for (rid,) in db.execute(
            "SELECT crucible_run_id FROM verdicts WHERE decided_at >= ?", [min_decided]
        ).fetchall()
    }
    recorded_at = utc_now().replace(tzinfo=None)
    contracts_version = CONTRACT_VERSION
    rows: list[tuple[str, str, str, object, int, str | None, str, object, str | None, str]] = []
    for gr, decided in candidates:
        if gr.run.run_id in existing_run_ids:
            continue
        gate_json = json.dumps(
            {name: gate.model_dump() for name, gate in gr.decision.gate_results.items()},
            sort_keys=True,
        )
        rows.append(
            (
                gr.run.run_id,
                gr.run.config_hash,
                gr.decision.decision,
                decided,
                gr.run.trade_count,
                gr.run.grammar_version,
                gate_json,
                recorded_at,
                source_export,
                contracts_version,
            )
        )
    if not rows:
        return 0
    before_row = db.execute("SELECT COUNT(*) FROM verdicts").fetchone()
    before = int(before_row[0]) if before_row else 0
    db.executemany(
        """
        INSERT OR IGNORE INTO verdicts
        (crucible_run_id, config_hash, decision, decided_at, trade_count,
         grammar_version, gate_results, recorded_at, source_export,
         contracts_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    after_row = db.execute("SELECT COUNT(*) FROM verdicts").fetchone()
    after = int(after_row[0]) if after_row else 0
    return after - before


__all__ = ["record_verdicts"]
