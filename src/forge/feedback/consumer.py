"""§8.2 feedback consumer — joins Crucible's gated runs to Forge's submissions.

`consume_batch_results(forge_db, crucible_db, *, batch_id=None, since=None)`
returns one `BatchFeedback` for one batch. As a side effect:

- For each matched submission, updates `submissions.status` from `submitted`
  to `gated` and sets `crucible_run_id` to the Crucible-side run id.
- Updates `batch_summaries.promotion_rate`, `common_failures`, and
  (when 100% of submitted candidates are gated) `completed_at`.

The function is idempotent: re-consuming the same batch returns an equivalent
`BatchFeedback` and leaves the DB unchanged. The DESIGN.md §8.2 pseudo-code
sketches `get_gated_runs(filter=batch_id)`; in practice Crucible has no
`forge_batch_id` column, so the join is Forge-side via `config_hash`.

D024/D1: signature is `(forge_db, crucible_db, *, batch_id=None, since=None)`.

D046 (2026-05-18): `reconcile_all_pending` reconciles ALL batches with
`submitted` rows against the gated-runs export — not just the latest.
The single-batch path was correct when Crucible processed a batch within
one Forge poll cycle; once latency exceeded that, older batches stranded
silently. `consume_batch_results` gained an optional `crucible_runs`
argument so the reconciler can fetch the export once and reuse it across
every in-flight batch.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

from crucible_contracts import (
    StrategyConfig,
    get_recent_gated_runs,
    load_recent_gated_runs_from_export,
)

from forge.feedback.types import BatchFeedback, CandidateOutcome

if TYPE_CHECKING:
    from datetime import datetime

    import duckdb
    from crucible_contracts import GatedRun


# Conservative upper bound: pull this many recent gated runs from Crucible
# and Python-side-filter. Phase 5 batches are O(200); this leaves headroom.
_DEFAULT_CRUCIBLE_LIMIT: int = 10_000


def _resolve_batch_id(
    db: duckdb.DuckDBPyConnection,
    *,
    batch_id: uuid.UUID | None,
    since: datetime | None,
) -> uuid.UUID:
    if batch_id is not None:
        return batch_id
    if since is None:
        msg = "consume_batch_results requires batch_id or since (or both)"
        raise ValueError(msg)
    row = db.execute(
        """
        SELECT forge_batch_id
        FROM submissions
        WHERE status IN ('submitted', 'gated')
        ORDER BY submitted_at DESC
        LIMIT 1
        """,
    ).fetchone()
    if row is None:
        msg = "no batch with submitted rows found; pass batch_id explicitly"
        raise ValueError(msg)
    return uuid.UUID(str(row[0]))


def _load_submissions(
    db: duckdb.DuckDBPyConnection,
    batch_id: uuid.UUID,
) -> list[tuple[uuid.UUID, StrategyConfig, str]]:
    """Return (candidate_id, config, status) tuples for one batch.

    Skips rows with status='skipped_duplicate' or 'submission_failed' — those
    never reached Crucible's inbox so they can't have a gated counterpart.
    """
    rows = db.execute(
        """
        SELECT forge_candidate_id, config_json, status
        FROM submissions
        WHERE forge_batch_id = ?
          AND status IN ('submitted', 'gated')
        ORDER BY submitted_at, forge_candidate_id
        """,
        [str(batch_id)],
    ).fetchall()
    out: list[tuple[uuid.UUID, StrategyConfig, str]] = []
    for cid, cfg_json, status in rows:
        cfg = StrategyConfig.model_validate_json(cfg_json)
        out.append((uuid.UUID(str(cid)), cfg, str(status)))
    return out


def _update_submission_to_gated(
    db: duckdb.DuckDBPyConnection,
    candidate_id: uuid.UUID,
    run_id: str,
) -> None:
    """Idempotent: only transitions 'submitted' -> 'gated'; re-runs are no-ops."""
    db.execute(
        """
        UPDATE submissions
        SET status = 'gated', crucible_run_id = ?
        WHERE forge_candidate_id = ? AND status = 'submitted'
        """,
        [run_id, str(candidate_id)],
    )


def _common_failures(outcomes: tuple[CandidateOutcome, ...]) -> dict[str, int]:
    """Count gate-failure occurrences across rejected outcomes."""
    counts: dict[str, int] = {}
    for o in outcomes:
        if o.promoted:
            continue
        for gate_name, gate in o.gated_run.decision.gate_results.items():
            if not gate.passed:
                counts[gate_name] = counts.get(gate_name, 0) + 1
    return counts


def _update_batch_summary(
    db: duckdb.DuckDBPyConnection,
    *,
    batch_id: uuid.UUID,
    submitted_count: int,
    outcomes: tuple[CandidateOutcome, ...],
    completed: bool,
    decided_at_max: datetime | None,
) -> None:
    promoted = sum(1 for o in outcomes if o.promoted)
    rate = promoted / submitted_count if submitted_count > 0 else 0.0
    common = _common_failures(outcomes)
    common_json = json.dumps(common, sort_keys=True)
    if completed and decided_at_max is not None:
        db.execute(
            """
            UPDATE batch_summaries
            SET promotion_rate = ?, common_failures = ?, completed_at = ?
            WHERE forge_batch_id = ?
            """,
            [rate, common_json, decided_at_max, str(batch_id)],
        )
    else:
        db.execute(
            """
            UPDATE batch_summaries
            SET promotion_rate = ?, common_failures = ?
            WHERE forge_batch_id = ?
            """,
            [rate, common_json, str(batch_id)],
        )


def _fetch_crucible_runs(
    crucible_db: Path,
    exports_dir: Path,
) -> list[GatedRun]:
    """Return recent gated runs via the EXPORT_LAYOUT file path with DB fallback.

    Production path: read `EXPORT_LAYOUT.gated_runs_*.json` — works while
    `crucible-db-writer.service` holds the DuckDB lock. Falls back to a
    direct DuckDB read when no export exists (test fixtures).

    Returns an empty list only when:
      - exports_dir has no `gated_runs_*.json` file AND
      - the direct DuckDB read returned no rows (NOT when it failed).

    Raises `QueryError` when the export is missing AND the direct DuckDB
    read fails — that's the "Crucible offline" condition the resilience
    suite (Phase 6 D025/D3.i) expects callers to surface as a clean exit.
    """
    runs = load_recent_gated_runs_from_export(
        exports_dir,
        limit=_DEFAULT_CRUCIBLE_LIMIT,
    )
    if runs:
        return runs
    # No export file (or it's empty). Try the direct DB.
    return get_recent_gated_runs(crucible_db, limit=_DEFAULT_CRUCIBLE_LIMIT)


def consume_batch_results(
    forge_db: duckdb.DuckDBPyConnection,
    crucible_db: Path,
    *,
    batch_id: uuid.UUID | None = None,
    since: datetime | None = None,
    exports_dir: Path | None = None,
    crucible_runs: list[GatedRun] | None = None,
) -> BatchFeedback:
    """Join Crucible gated runs to Forge submissions and update DB state.

    Reads gated-run state via `EXPORT_LAYOUT.gated_runs_*.json` (contracts
    v1.8.0+) by default, falling back to a direct DuckDB read when no
    export is present. The export path side-steps the writer-lock issue
    that blocks direct read-only opens while `crucible-db-writer.service`
    is running.

    When `crucible_runs` is supplied (D046 reconciler path), the export
    fetch is skipped — the caller is responsible for passing the same
    snapshot to every per-batch invocation in a reconcile pass.
    """
    if since is not None and since.tzinfo is None:
        msg = "consume_batch_results: since must be timezone-aware (tzinfo required)"
        raise ValueError(msg)

    resolved_batch_id = _resolve_batch_id(forge_db, batch_id=batch_id, since=since)
    submission_rows = _load_submissions(forge_db, resolved_batch_id)
    submitted_count = len(submission_rows)
    hash_to_row: dict[str, tuple[uuid.UUID, StrategyConfig, str]] = {
        cfg.config_hash: (cid, cfg, status) for cid, cfg, status in submission_rows
    }

    if crucible_runs is None:
        if exports_dir is None:
            exports_dir = Path.home() / "optbt_data" / "exports"
        crucible_runs = _fetch_crucible_runs(crucible_db, exports_dir)

    matched: dict[str, GatedRun] = {}
    for gr in crucible_runs:
        h = gr.run.config_hash
        if h not in hash_to_row:
            continue
        if since is not None:
            # DuckDB returns TIMESTAMP rows as naive datetimes; normalize both
            # sides to aware-UTC so the comparison is well-defined.
            decided = gr.decision.decided_at
            if decided.tzinfo is None:
                decided = decided.replace(tzinfo=UTC)
            if decided < since:
                continue
        if h not in matched:
            matched[h] = gr

    ordered_outcomes: list[tuple[CandidateOutcome, datetime]] = []
    for _cid, cfg, _status in submission_rows:
        matched_run = matched.get(cfg.config_hash)
        if matched_run is None:
            continue
        ordered_outcomes.append(
            (
                CandidateOutcome(config=cfg, gated_run=matched_run),
                matched_run.decision.decided_at,
            )
        )

    for cid, cfg, _status in submission_rows:
        matched_run = matched.get(cfg.config_hash)
        if matched_run is None:
            continue
        _update_submission_to_gated(forge_db, cid, matched_run.run.run_id)

    outcomes = tuple(o for o, _ in ordered_outcomes)
    completed = len(outcomes) == submitted_count and submitted_count > 0
    decided_at_max = max((d for _, d in ordered_outcomes), default=None)

    _update_batch_summary(
        forge_db,
        batch_id=resolved_batch_id,
        submitted_count=submitted_count,
        outcomes=outcomes,
        completed=completed,
        decided_at_max=decided_at_max,
    )

    return BatchFeedback(
        batch_id=resolved_batch_id,
        submitted_count=submitted_count,
        outcomes=outcomes,
    )


def reconcile_all_pending(
    forge_db: duckdb.DuckDBPyConnection,
    crucible_db: Path,
    *,
    exports_dir: Path | None = None,
) -> tuple[BatchFeedback, ...]:
    """Reconcile every batch with `submitted` rows against the gated-runs export.

    D046 (2026-05-18): the single-batch `consume_batch_results` path was the
    Phase 5 default and is correct when Crucible processes a batch within one
    Forge poll cycle. Once Crucible's per-run latency exceeded the cycle (post
    Tier-2 D033 / pre Crucible-side concurrency tuning), older batches
    accumulated stranded `submitted` rows that the latest-batch-only path
    never reached — by 2026-05-17 the loop had 11 stranded batches and 3,712
    un-reconciled candidates.

    This function reads the gated-runs export once and per-batch reconciles
    every `forge_batch_id` that still has `status='submitted'` rows. Each
    per-batch call is itself idempotent (re-running over the same data is a
    no-op), so the whole sweep is safe to invoke on every poll.

    Returns one `BatchFeedback` per batch reconciled, sorted by the batch's
    minimum `submitted_at` (oldest first) so the caller's logging stays
    deterministic across runs.
    """
    if exports_dir is None:
        exports_dir = Path.home() / "optbt_data" / "exports"
    runs = _fetch_crucible_runs(crucible_db, exports_dir)

    batch_rows = forge_db.execute(
        """
        SELECT forge_batch_id, MIN(submitted_at) AS first_submitted
        FROM submissions
        WHERE status = 'submitted'
        GROUP BY forge_batch_id
        ORDER BY first_submitted ASC, forge_batch_id ASC
        """,
    ).fetchall()

    feedbacks: list[BatchFeedback] = []
    for batch_id_raw, _ts in batch_rows:
        batch_id = uuid.UUID(str(batch_id_raw))
        fb = consume_batch_results(
            forge_db,
            crucible_db,
            batch_id=batch_id,
            exports_dir=exports_dir,
            crucible_runs=runs,
        )
        feedbacks.append(fb)
    return tuple(feedbacks)


__all__ = ["consume_batch_results", "reconcile_all_pending"]
