"""forge.persistence — DuckDB schema and connection wrapper for Forge's own DB."""

from __future__ import annotations

from forge.persistence.db import db_connection, ensure_schema, open_db
from forge.persistence.registry_loader import (
    DEFAULT_EXPORTS_DIR,
    find_latest_snapshot,
    load_registry,
)
from forge.persistence.schemas import DDL_STATEMENTS, SCHEMA_VERSION

__all__ = [
    "DDL_STATEMENTS",
    "DEFAULT_EXPORTS_DIR",
    "SCHEMA_VERSION",
    "db_connection",
    "ensure_schema",
    "find_latest_snapshot",
    "load_registry",
    "open_db",
]
