"""Startup compatibility check against `crucible_contracts`.

Hard rule #2: no imports from Crucible internals. All inter-system access goes
through `crucible_contracts`. This module enforces SemVer compatibility at CLI
entry (§13.5); a mismatch halts execution before any further work.

`FORGE_EXPECTED_CONTRACT_VERSION` is the version this build of Forge was
written against. Bump when adopting a new contracts release; major-version
bumps are deliberate events that may require code changes elsewhere.
"""

from __future__ import annotations

from crucible_contracts import (
    CONTRACT_VERSION,
    SchemaVersionMismatch,
    validate_schema_version,
)

FORGE_EXPECTED_CONTRACT_VERSION: str = "1.7.0"


def check_contracts_version() -> str:
    """Validate the installed `crucible_contracts` version is compatible.

    Returns the installed version string on success. Raises
    `SchemaVersionMismatch` on major-version mismatch.
    """
    validate_schema_version(FORGE_EXPECTED_CONTRACT_VERSION, CONTRACT_VERSION)
    return CONTRACT_VERSION


__all__ = [
    "FORGE_EXPECTED_CONTRACT_VERSION",
    "SchemaVersionMismatch",
    "check_contracts_version",
]
