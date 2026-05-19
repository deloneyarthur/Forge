"""§7 submitter — write ranked candidates to Crucible's inbox + Forge's DB.

D023/D7 wraps `crucible_contracts.submit_candidate` with Forge-side
bookkeeping:

1. Insert a `submissions` row with status `pending`. The §13.4 unique
   index on `config_hash` rejects duplicate hashes here — caught and
   recorded as `skipped_duplicate` (idempotent re-run = no-op).
2. Call `submit_candidate(config, batch_inbox)`; on success update the
   row to `submitted` with the receipt's inbox path.
3. On contracts failure, mark `submission_failed` and surface the error.
4. After each candidate's row commits, write its pre-filter logs.

`submit_batch` also writes the `batch_summaries` row up front (with
`promotion_rate=NULL`; Phase 5 backfills it). A repeat call with the
same `batch_id` is a no-op for the summary (INSERT OR IGNORE).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import duckdb
from crucible_contracts import submit_candidate

from forge.submission.pre_filter_logger import record_pre_filter_logs

if TYPE_CHECKING:
    from collections.abc import Sequence

    from forge.ranking.types import RankedCandidate
    from forge.submission.batch import BatchContext

_log = logging.getLogger(__name__)


SubmissionStatus = Literal["submitted", "skipped_duplicate", "submission_failed"]


@dataclass(frozen=True, slots=True)
class SubmissionRecord:
    """One candidate's outcome."""

    candidate_id: uuid.UUID
    config_hash: str
    status: SubmissionStatus
    inbox_path: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class BatchSubmissionResult:
    """Aggregate outcome of a `submit_batch` call."""

    batch_id: uuid.UUID
    submitted_count: int
    skipped_duplicate_count: int
    failed_count: int
    records: tuple[SubmissionRecord, ...]


def _insert_batch_summary(
    db: duckdb.DuckDBPyConnection,
    *,
    batch: BatchContext,
    batch_size: int,
) -> None:
    """Insert one batch_summaries row; no-op if the batch_id already exists.

    DuckDB lacks `INSERT OR IGNORE` syntax sugar, so a SELECT-first
    guard keeps the call idempotent.
    """
    existing = db.execute(
        "SELECT 1 FROM batch_summaries WHERE forge_batch_id = ?",
        [str(batch.batch_id)],
    ).fetchone()
    if existing is not None:
        return
    db.execute(
        """
        INSERT INTO batch_summaries
            (forge_batch_id, batch_size, submitted_at, grammar_version, registry_version)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            str(batch.batch_id),
            batch_size,
            batch.submitted_at,
            batch.grammar_version,
            batch.registry_hash,
        ],
    )


def _submit_one(
    db: duckdb.DuckDBPyConnection,
    *,
    batch: BatchContext,
    candidate: RankedCandidate,
    inbox_root: Path,
) -> SubmissionRecord:
    candidate_id = uuid.uuid4()
    config = candidate.report.config
    config_hash = config.config_hash
    config_json = config.model_dump_json()

    try:
        db.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(candidate_id),
                str(batch.batch_id),
                config_hash,
                config_json,
                batch.submitted_at,
                "pending",
            ],
        )
    except duckdb.ConstraintException:
        _log.warning(
            "submit_batch: skipping duplicate config_hash %s (already submitted)",
            config_hash,
        )
        return SubmissionRecord(
            candidate_id=candidate_id,
            config_hash=config_hash,
            status="skipped_duplicate",
            inbox_path=None,
            error=None,
        )

    try:
        receipt = submit_candidate(config, inbox_root)
    except Exception as err:  # contracts may raise IOError, etc.
        db.execute(
            "UPDATE submissions SET status = ? WHERE forge_candidate_id = ?",
            ["submission_failed", str(candidate_id)],
        )
        return SubmissionRecord(
            candidate_id=candidate_id,
            config_hash=config_hash,
            status="submission_failed",
            inbox_path=None,
            error=str(err),
        )

    db.execute(
        "UPDATE submissions SET status = ? WHERE forge_candidate_id = ?",
        ["submitted", str(candidate_id)],
    )
    record_pre_filter_logs(
        db,
        candidate_id=candidate_id,
        report=candidate.report,
        evaluated_at=batch.submitted_at,
    )
    return SubmissionRecord(
        candidate_id=candidate_id,
        config_hash=config_hash,
        status="submitted",
        inbox_path=receipt.inbox_path,
        error=None,
    )


def submit_batch(
    db: duckdb.DuckDBPyConnection,
    *,
    batch: BatchContext,
    candidates: Sequence[RankedCandidate],
    inbox_root: Path,
) -> BatchSubmissionResult:
    """Submit a ranked batch to Crucible's inbox + Forge's DB.

    Inbox layout: `{inbox_root}/{config_hash}.json` — flat, matching
    `crucible_contracts.INBOX_LAYOUT` (D006 confirms JSON; D026 fixes the
    earlier per-batch-subdir layout that Crucible's contract-compliant
    inbox watcher silently skipped). Batch association is preserved via
    the `submissions.forge_batch_id` column, not via filesystem grouping.
    """
    _insert_batch_summary(db, batch=batch, batch_size=len(candidates))

    records: list[SubmissionRecord] = []
    submitted = 0
    skipped = 0
    failed = 0

    for candidate in candidates:
        record = _submit_one(
            db,
            batch=batch,
            candidate=candidate,
            inbox_root=inbox_root,
        )
        records.append(record)
        if record.status == "submitted":
            submitted += 1
        elif record.status == "skipped_duplicate":
            skipped += 1
        else:
            failed += 1

    return BatchSubmissionResult(
        batch_id=batch.batch_id,
        submitted_count=submitted,
        skipped_duplicate_count=skipped,
        failed_count=failed,
        records=tuple(records),
    )


@dataclass(frozen=True, slots=True)
class PrefilterRejectionSummary:
    """D062 + D064 breakdown of a batch's pre-filter rejection counts.

    `total` is the aggregate over all rejected reports (D062, persisted to
    `batch_summaries.prefilter_rejections`). `by_hypothesis` partitions
    the same data by `config.hypothesis` so we can see which filter kills
    which hypothesis (D064, persisted to
    `batch_summaries.prefilter_rejections_by_hypothesis`).
    """

    total: dict[str, int]
    by_hypothesis: dict[str, dict[str, int]]


def record_prefilter_rejections(
    db: duckdb.DuckDBPyConnection,
    *,
    batch_id: uuid.UUID,
    reports: Sequence[object],
) -> PrefilterRejectionSummary:
    """D062 + D064: persist per-filter rejection counts to `batch_summaries`.

    `reports` is the full enumeration output (passed + rejected). For each
    rejected report, increments the counter at its first-failing filter,
    and increments the same filter under the report's hypothesis bucket.
    Passed reports are skipped. Reports without a recoverable hypothesis
    contribute only to `total`.

    No-op when the batch_summaries row is absent (idempotent reruns or
    dry-run paths). Returns the summary so callers can also log it.
    """
    total: Counter[str] = Counter()
    by_hyp: dict[str, Counter[str]] = {}
    for r in reports:
        if getattr(r, "passed", False):
            continue
        filter_results = getattr(r, "filter_results", {}) or {}
        failing = next(
            (name for name, fr in filter_results.items() if not getattr(fr, "passed", True)),
            "unknown",
        )
        total[failing] += 1
        cfg = getattr(r, "config", None)
        hyp = getattr(cfg, "hypothesis", None) if cfg is not None else None
        if isinstance(hyp, str):
            by_hyp.setdefault(hyp, Counter())[failing] += 1
    summary = PrefilterRejectionSummary(
        total=dict(total),
        by_hypothesis={h: dict(c) for h, c in by_hyp.items()},
    )
    if not summary.total:
        return summary
    db.execute(
        "UPDATE batch_summaries SET prefilter_rejections = ?, "
        "prefilter_rejections_by_hypothesis = ? "
        "WHERE forge_batch_id = ?",
        [
            json.dumps(summary.total),
            json.dumps(summary.by_hypothesis),
            str(batch_id),
        ],
    )
    return summary


__all__ = [
    "BatchSubmissionResult",
    "PrefilterRejectionSummary",
    "SubmissionRecord",
    "SubmissionStatus",
    "record_prefilter_rejections",
    "submit_batch",
]
