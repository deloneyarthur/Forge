"""forge.persistence — DuckDB schema and connection wrapper for Forge's own DB."""

from __future__ import annotations

from forge.persistence.db import db_connection, ensure_schema, open_db
from forge.persistence.schemas import DDL_STATEMENTS, SCHEMA_VERSION

__all__ = [
    "DDL_STATEMENTS",
    "SCHEMA_VERSION",
    "db_connection",
    "ensure_schema",
    "open_db",
]
