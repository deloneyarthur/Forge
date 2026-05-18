"""DuckDB connection helpers for Forge's own database.

Reads/writes never block the Crucible read path — this is a separate DB at
`~/forge_data/forge.db`. Phase 5 onward will add ORM-ish helpers; Phase 0
gives just the connection and schema-ensure primitives.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from forge.persistence.schemas import DDL_STATEMENTS


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply all schema DDL idempotently."""
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)


def open_db(path: Path | str = ":memory:") -> duckdb.DuckDBPyConnection:
    """Open (or create) a Forge DB at `path` and ensure the schema is current.

    `path` may be `":memory:"` for tests; otherwise the parent directory is
    created if missing.
    """
    if path == ":memory:":
        conn = duckdb.connect(":memory:")
    else:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(p))
    # D061: pin session TZ to UTC. All Forge timestamps flow through
    # forge.core.clock.utc_now() (hard rule #8), so on-disk naive TIMESTAMP
    # values are implicit-UTC wall clocks. Without this, DuckDB coerces them
    # via the host's session TZ on read, silently shifting aware-vs-naive
    # comparisons (the D052 aged-out flush no-op'd in production for exactly
    # this reason — see IMPLEMENTATION_DECISIONS.md D061).
    conn.execute("SET TimeZone='UTC'")
    ensure_schema(conn)
    return conn


@contextmanager
def db_connection(path: Path | str = ":memory:") -> Iterator[duckdb.DuckDBPyConnection]:
    """Context manager that opens, schema-ensures, and closes a Forge DB."""
    conn = open_db(path)
    try:
        yield conn
    finally:
        conn.close()
