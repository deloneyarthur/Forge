"""Submit meta-king candidates to Crucible's inbox + Forge's DB (A3 submit half).

The meta-king arm is a DISTINCT submission path from the §7 battery submitter:
kings are oracle-selected, not pre-filter-battery-selected, so they carry no
``PreFilterReport`` and reuse none of ``submit_batch``'s battery bookkeeping.
This module mirrors the submitter's crash-safe transaction + ``config_hash``
idempotency (hard rule #9) for the king path, and stamps the A3 provenance
fields added in contracts 1.19.0 (D176):

- ``source="meta_king"`` → Crucible's inbox watcher records
  ``runs.source="meta_king"``, gating the A4 yield read (`meta_king` vs `forge`).
- ``search_n_trials=N`` (genomes scored against the oracle to select the batch)
  → Crucible folds it into the single-config DSR ``n_trials`` — the honest
  trial-laundering correction (A3 §4).

Both fields are hash-excluded, so ``config_hash`` — the inbox filename, the
unique index, and the dedup key — is byte-identical with or without the stamp.
Kings run the full, unchanged §8.7 gauntlet as proposals (hard rule #3/#6).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import duckdb
from crucible_contracts import submit_candidate

# Reuse the single source of truth for the batch_summaries schema (the king path
# writes the same row shape the §7 submitter does, minus the battery funnel
# counts, which stay NULL).
from forge.submission.submitter import _insert_batch_summary

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from forge.king.search import King
    from forge.submission.batch import BatchContext

_log = logging.getLogger(__name__)

_SOURCE = "meta_king"

KingSubmissionStatus = Literal["submitted", "skipped_duplicate", "submission_failed"]


@dataclass(frozen=True, slots=True)
class KingSubmissionRecord:
    """One king's submission outcome."""

    candidate_id: uuid.UUID
    config_hash: str
    status: KingSubmissionStatus
    inbox_path: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class KingSubmissionResult:
    """Aggregate outcome of a :func:`submit_kings` call."""

    batch_id: uuid.UUID
    submitted_count: int
    skipped_duplicate_count: int
    failed_count: int
    records: tuple[KingSubmissionRecord, ...]


def submit_kings(
    db: duckdb.DuckDBPyConnection,
    *,
    batch: BatchContext,
    kings: Sequence[King],
    inbox_root: Path,
    search_n_trials: int,
) -> KingSubmissionResult:
    """Stamp + submit ``kings`` to ``inbox_root`` and record them in Forge's DB.

    Writes one ``batch_summaries`` row, then each king through the crash-safe
    INSERT(pending)→``submit_candidate``→UPDATE(submitted) transaction the §7
    submitter uses (idempotent via the ``config_hash`` unique index, hard rule
    #9 — a re-run with the same kings is a no-op).

    ``search_n_trials`` is the same ``N`` for every king in the batch: the
    oracle-search multiplicity that produced the selection (A3 §4).
    """
    _insert_batch_summary(db, batch=batch, batch_size=len(kings))

    records: list[KingSubmissionRecord] = []
    submitted = 0
    skipped = 0
    failed = 0
    for king in kings:
        record = _submit_one_king(
            db,
            batch=batch,
            king=king,
            inbox_root=inbox_root,
            search_n_trials=search_n_trials,
        )
        records.append(record)
        if record.status == "submitted":
            submitted += 1
        elif record.status == "skipped_duplicate":
            skipped += 1
        else:
            failed += 1

    return KingSubmissionResult(
        batch_id=batch.batch_id,
        submitted_count=submitted,
        skipped_duplicate_count=skipped,
        failed_count=failed,
        records=tuple(records),
    )


def _submit_one_king(
    db: duckdb.DuckDBPyConnection,
    *,
    batch: BatchContext,
    king: King,
    inbox_root: Path,
    search_n_trials: int,
) -> KingSubmissionRecord:
    candidate_id = uuid.uuid4()
    # Stamp the A3 provenance (all hash-excluded in contracts 1.19.0): source
    # gates the A4 read; search_n_trials is the oracle-search multiplicity
    # Crucible folds into the single-config DSR; grammar_version rides into
    # runs.grammar_version (D097). config_hash is unchanged by all three.
    config = king.config.model_copy(
        update={
            "source": _SOURCE,
            "search_n_trials": search_n_trials,
            "grammar_version": batch.grammar_version,
        },
    )
    config_hash = config.config_hash
    config_json = config.model_dump_json()

    db.execute("BEGIN TRANSACTION")
    try:
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
            db.execute("ROLLBACK")
            _log.warning(
                "submit_kings: skipping duplicate config_hash %s (already submitted)",
                config_hash,
            )
            return KingSubmissionRecord(
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
            db.execute("COMMIT")
            return KingSubmissionRecord(
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
        db.execute("COMMIT")
    except BaseException:
        # Never leave the transaction open (a stranded pending row burns the
        # config_hash slot and breaks the next king's BEGIN). Roll back, re-raise.
        db.execute("ROLLBACK")
        raise

    return KingSubmissionRecord(
        candidate_id=candidate_id,
        config_hash=config_hash,
        status="submitted",
        inbox_path=receipt.inbox_path,
        error=None,
    )


__all__ = [
    "KingSubmissionRecord",
    "KingSubmissionResult",
    "KingSubmissionStatus",
    "submit_kings",
]
