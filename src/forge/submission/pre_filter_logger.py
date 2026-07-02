"""Write one row per (candidate, filter) to `pre_filter_logs`.

§9.1 schema:

    pre_filter_logs(
        forge_candidate_id  UUID,
        filter_name         VARCHAR(64),
        passed              BOOLEAN,
        score               DOUBLE,
        details_json        JSON,
        evaluated_at        TIMESTAMP,
        config_hash         VARCHAR(16),     -- D076 / Q16
        forge_batch_id      UUID,            -- D076 / Q16
        PRIMARY KEY (forge_candidate_id, filter_name)
    )

D021/D8 deferred this from Phase 3 (chicken-and-egg: no batch ID yet).
D023/D8 wires it in Phase 4. The submitter mints `forge_candidate_id`
when inserting into `submissions`; the survivor-path writer
(`record_pre_filter_logs`) is called per-candidate right after that.

D076 / Q16 (2026-05-20) added a rejected-config path so the table wasn't
survivor-only (which showed a misleading 100% pass rate per filter). D219
(2026-07-02, pipeline-perf P0-1) REMOVED that per-row rejected write: it
fsynced ~31k rows/batch (~190s of the submit phase) into a table with zero
readers, and the same pass/reject breakdown already lives in
`batch_summaries.prefilter_rejections{,_by_hypothesis}` plus the
`battery_survival_by_hypothesis` journal line. The table is survivor-only
again (the misleading-pass-rate concern is moot — nothing reads it); survivor
rows still carry `config_hash` + `forge_batch_id` for join-back.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

    from forge.prefilters.types import PreFilterReport


def record_pre_filter_logs(
    db: duckdb.DuckDBPyConnection,
    *,
    candidate_id: uuid.UUID,
    report: PreFilterReport,
    evaluated_at: datetime,
    batch_id: uuid.UUID | None = None,
) -> int:
    """Insert one row per filter result for `candidate_id` (survivor path).

    Populates `config_hash` (D076) from the report's config and
    `forge_batch_id` from the optional kwarg so audit queries can join
    survivor rows back to a batch without needing the `submissions`
    table. `batch_id` is optional to preserve the pre-D076 call
    signature; submitter wires it from `BatchContext`.

    Returns the count of rows written. Raises `ValueError` if
    `evaluated_at` is naive (tz-naive timestamps round-trip ambiguously
    through DuckDB) and `duckdb.ConstraintException` if the
    (candidate_id, filter_name) primary key collides.
    """
    if evaluated_at.tzinfo is None:
        msg = (
            "record_pre_filter_logs: evaluated_at must be timezone-aware; "
            "use forge.core.clock.utc_now()"
        )
        raise ValueError(msg)

    config_hash = report.config.config_hash
    batch_str = str(batch_id) if batch_id is not None else None
    rows = [
        (
            str(candidate_id),
            filter_name,
            result.passed,
            float(result.score),
            json.dumps(dict(result.details)),
            evaluated_at,
            config_hash,
            batch_str,
        )
        for filter_name, result in report.filter_results.items()
    ]
    db.executemany(
        """
        INSERT INTO pre_filter_logs
            (forge_candidate_id, filter_name, passed, score, details_json,
             evaluated_at, config_hash, forge_batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


__all__ = ["record_pre_filter_logs"]
