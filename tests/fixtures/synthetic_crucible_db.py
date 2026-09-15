"""Synthetic Crucible runs DB for Forge's read-path tests.

Phase 0 deliverable: prove Forge can connect to a Crucible-shape DuckDB and
exercise `crucible_contracts` query helpers, before Crucible itself is built.
The schema here mirrors the column set that `crucible_contracts.queries`
joins against (see `_GATED_QUERY_BASE` in queries.py): `runs`,
`promotion_decisions`, `metrics`, `trades`.

Keep the schema in lockstep with `crucible_contracts` as it evolves. When
Crucible's real DDL ships, switch tests to that and retire this fixture.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
from crucible_contracts import get_recent_gated_runs

CRUCIBLE_READ_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id          UUID PRIMARY KEY,
        config_hash     VARCHAR(64) NOT NULL,
        source          VARCHAR(40),
        status          VARCHAR(20) NOT NULL,
        period_start    TIMESTAMP,
        period_end      TIMESTAMP,
        started_at      TIMESTAMP,
        finished_at     TIMESTAMP,
        -- contracts 1.15.0 (Crucible 9995f81): the gated query selects
        -- r.grammar_version for the funnel's version axis; nullable so the
        -- suite's explicit-column INSERTs are untouched (D106 adoption).
        grammar_version VARCHAR(20)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS promotion_decisions (
        run_id              UUID PRIMARY KEY,
        decision            VARCHAR(20) NOT NULL,
        gate_results_json   JSON,
        decided_at          TIMESTAMP,
        decided_by          VARCHAR(64)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS metrics (
        run_id      UUID,
        metric_name VARCHAR(64),
        value       DOUBLE,
        PRIMARY KEY (run_id, metric_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        run_id      UUID,
        trade_id    UUID,
        PRIMARY KEY (run_id, trade_id)
    )
    """,
)


def build_synthetic_crucible_db(path: Path | str) -> duckdb.DuckDBPyConnection:
    """Create the read-side schema at `path`. Returns an open writable connection."""
    if path == ":memory:":
        conn = duckdb.connect(":memory:")
    else:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(p))
    for stmt in CRUCIBLE_READ_SCHEMA:
        conn.execute(stmt)
    return conn


@contextmanager
def ephemeral_crucible_db(tmp_path: Path) -> Iterator[Path]:
    """Yield a freshly-built synthetic Crucible DB path; cleans up on exit."""
    db_path = tmp_path / "crucible_runs.duckdb"
    conn = build_synthetic_crucible_db(db_path)
    conn.close()
    try:
        yield db_path
    finally:
        if db_path.exists():
            db_path.unlink()


def write_gated_runs_export(
    exports_dir: Path,
    crucible_db: Path,
    *,
    name: str = "gated_runs_0001.json",
    limit: int = 1000,
) -> Path:
    """Publish the synthetic DB's current gated rows as a `gated_runs_*.json` export.

    WHY: since D422 Forge reads Crucible ONLY through its exports (hard rule #2), so a
    test that seeds the synthetic DB must hand the consumer what Crucible's publisher
    would have written. Reading the FIXTURE DB directly here is the one place that is
    allowed. Returns ``exports_dir`` (created) so it can be passed as ``exports_dir=``.
    """
    exports_dir.mkdir(parents=True, exist_ok=True)
    runs = get_recent_gated_runs(crucible_db, limit=limit)
    payload = {"gated_runs": [json.loads(r.model_dump_json()) for r in runs]}
    (exports_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    return exports_dir
