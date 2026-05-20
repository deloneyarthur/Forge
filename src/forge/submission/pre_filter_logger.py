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

D076 / Q16 (2026-05-20) adds the rejected-config path: rejected configs
never reached `submissions`, so the survivor-only writer left the table
showing a misleading 100% pass rate for every filter — Q16's sidenote.
`record_pre_filter_logs_for_rejected` writes one row per (rejected
config, filter that ran) with a fresh candidate_id plus the
`config_hash` and `forge_batch_id` for join-back. Survivor rows ALSO
get those columns populated now so the table is uniformly queryable.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

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


def record_pre_filter_logs_for_rejected(
    db: duckdb.DuckDBPyConnection,
    *,
    reports: Iterable[PreFilterReport],
    batch_id: uuid.UUID,
    evaluated_at: datetime,
) -> int:
    """D076 / Q16 — write rejected configs' filter results to `pre_filter_logs`.

    Iterates over `reports`, skipping passed configs (the submitter
    handles those via `record_pre_filter_logs`). For each rejected
    config, mints a fresh `forge_candidate_id` (the config isn't in
    `submissions` so it has no existing ID) and writes one row per
    filter the battery actually ran — the report's `filter_results`
    dict has only those, the short-circuit drops the rest.

    Returns the number of rows inserted. Skips silently when there
    are no rejected reports (empty iterable / all-pass batch).
    """
    if evaluated_at.tzinfo is None:
        msg = (
            "record_pre_filter_logs_for_rejected: evaluated_at must be "
            "timezone-aware; use forge.core.clock.utc_now()"
        )
        raise ValueError(msg)

    rows: list[tuple[str, str, bool, float, str, datetime, str, str]] = []
    batch_str = str(batch_id)
    for report in reports:
        if report.passed:
            continue
        candidate_id = str(uuid.uuid4())
        config_hash = report.config.config_hash
        for filter_name, result in report.filter_results.items():
            rows.append(
                (
                    candidate_id,
                    filter_name,
                    result.passed,
                    float(result.score),
                    json.dumps(dict(result.details)),
                    evaluated_at,
                    config_hash,
                    batch_str,
                ),
            )
    if not rows:
        return 0
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


__all__ = ["record_pre_filter_logs", "record_pre_filter_logs_for_rejected"]
