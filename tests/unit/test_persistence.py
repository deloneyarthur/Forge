"""Unit tests for Forge's own DuckDB schema."""

from __future__ import annotations

import duckdb
import pytest

from forge.persistence.db import db_connection, ensure_schema
from forge.persistence.schemas import TABLE_NAMES


def test_schema_creates_all_tables() -> None:
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'",
        ).fetchall()
        present = {r[0] for r in rows}
    assert present >= TABLE_NAMES


def test_schema_idempotent() -> None:
    with db_connection() as conn:
        ensure_schema(conn)
        ensure_schema(conn)  # second apply must not raise


def test_config_hash_uniqueness_enforced() -> None:
    """Hard rule #9 / §13.4: a config_hash cannot appear twice in submissions."""
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status)
            VALUES (gen_random_uuid(), gen_random_uuid(), 'abc123',
                    '{}', now(), 'pending')
            """,
        )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                """
                INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status)
                VALUES (gen_random_uuid(), gen_random_uuid(), 'abc123',
                        '{}', now(), 'pending')
                """,
            )
