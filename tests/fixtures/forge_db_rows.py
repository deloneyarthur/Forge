"""Row builders for Forge's own ledger and for Crucible's ``GatedRun`` model.

WHY one home: six test files each carried an ``_insert_submission`` and seven a
``_gated_run``, all the same shape with different defaults. A duplicated builder
drifts (one grew ``selection_mode``, one stamped ``datetime.now``), and the drift
is invisible until a schema change breaks the copies one at a time. Every default
here is the most common value across the copies it replaced; a test that needs a
different value passes it explicitly, so nothing it pins moved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from crucible_contracts import GatedRun
from crucible_contracts.models import GateResult, PromotionDecision, RunResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    import duckdb

# The verdict export ships NAIVE UTC timestamps; the ledger columns follow suit.
DEFAULT_DECIDED_AT: datetime = datetime(2026, 6, 9, 11, 37, 46)  # noqa: DTZ001
DEFAULT_SUBMITTED_AT: datetime = datetime(2026, 6, 10, 11, 0)  # noqa: DTZ001


def make_gated_run(
    *,
    config_hash: str,
    decision: str = "reject",
    decided_at: datetime | None = None,
    run_id: str | None = None,
    trade_count: int = 120,
    grammar_version: str | None = None,
    metrics: Mapping[str, float] | None = None,
    gate_results: Mapping[str, GateResult] | None = None,
    decided_by: str = "runner.forge_minimal",
    period_start: date = date(2021, 6, 2),
    period_end: date = date(2026, 6, 1),
    measurement_basis: str | None = None,
    fullhist_refit_of: str | None = None,
    refit_selection: str | None = None,
) -> GatedRun:
    """One Crucible verdict for ``config_hash`` in the export's row shape."""
    rid = run_id or str(uuid.uuid4())
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics=dict(metrics) if metrics is not None else {"total_return": 0.1},
            trade_count=trade_count,
            period_start=period_start,
            period_end=period_end,
            grammar_version=grammar_version,
            measurement_basis=measurement_basis,
            fullhist_refit_of=fullhist_refit_of,
            refit_selection=refit_selection,
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results=dict(gate_results) if gate_results is not None else {},
            decided_at=decided_at if decided_at is not None else DEFAULT_DECIDED_AT,
            decided_by=decided_by,
        ),
    )


def trade_count_gate(trade_count: int, *, threshold: float = 100.0) -> dict[str, GateResult]:
    """The ``min_oos_trade_count`` gate result the trade-rate tests key on."""
    return {
        "min_oos_trade_count": GateResult(
            gate_name="min_oos_trade_count",
            passed=trade_count >= threshold,
            value=float(trade_count),
            threshold=threshold,
        ),
    }


def insert_submission(
    conn: duckdb.DuckDBPyConnection | Any,
    *,
    config_hash: str,
    config_json: str = "{}",
    batch_id: uuid.UUID | str | None = None,
    submitted_at: datetime | None = None,
    status: str = "submitted",
    crucible_run_id: str | None = None,
    selection_mode: str | None = None,
    candidate_id: uuid.UUID | str | None = None,
) -> str:
    """Insert one ``submissions`` row; returns the candidate id it minted."""
    cid = str(candidate_id or uuid.uuid4())
    conn.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, config_json, "
        "submitted_at, status, crucible_run_id, selection_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            cid,
            str(batch_id or uuid.uuid4()),
            config_hash,
            config_json,
            submitted_at if submitted_at is not None else DEFAULT_SUBMITTED_AT,
            status,
            crucible_run_id,
            selection_mode,
        ],
    )
    return cid


def aware_utc(dt: datetime) -> datetime:
    """Tag a naive ledger timestamp as UTC for comparisons with ``utc_now()``."""
    return dt.replace(tzinfo=UTC)


__all__ = [
    "DEFAULT_DECIDED_AT",
    "DEFAULT_SUBMITTED_AT",
    "aware_utc",
    "insert_submission",
    "make_gated_run",
    "trade_count_gate",
]
