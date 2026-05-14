"""Write one row per (candidate, filter) to `pre_filter_logs`.

§9.1 schema:

    pre_filter_logs(
        forge_candidate_id  UUID,
        filter_name         VARCHAR(64),
        passed              BOOLEAN,
        score               DOUBLE,
        details_json        JSON,
        evaluated_at        TIMESTAMP,
        PRIMARY KEY (forge_candidate_id, filter_name)
    )

D021/D8 deferred this from Phase 3 (chicken-and-egg: no batch ID yet).
D023/D8 wires it in Phase 4. The submitter mints `forge_candidate_id`
when inserting into `submissions`; this writer is called per-candidate
right after that.
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
) -> int:
    """Insert one row per filter result for `candidate_id`.

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

    rows = [
        (
            str(candidate_id),
            filter_name,
            result.passed,
            float(result.score),
            json.dumps(dict(result.details)),
            evaluated_at,
        )
        for filter_name, result in report.filter_results.items()
    ]
    db.executemany(
        """
        INSERT INTO pre_filter_logs
            (forge_candidate_id, filter_name, passed, score, details_json, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


__all__ = ["record_pre_filter_logs"]
