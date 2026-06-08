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

# 1.16.0 (D109): the additive CombinerSpec rank fields (rank_k /
# rebalance_frequency / direction_mode) + the event_momentum hypothesis literal +
# the post_event_drift family literal — the H1 cross_sectional_rank combiner and
# the H2 event_momentum hypothesis (v12) construct and validate against these.
# Additive/minor: §13.5 SemVer compatibility is MAJOR-only, so this pin is
# hygiene + suite-correctness (the editable install already serves 1.16.0).
# 1.15.0 (D106): RunResult.grammar_version rides the gated export (Crucible
# 9995f81, shipped 2026-06-08 00:10Z in response to the D105 yield-map reply's
# "export carries no version field" note). extra="forbid" makes this a
# REQUIRED adoption: pre-1.15.0 readers reject the new export rows outright.
FORGE_EXPECTED_CONTRACT_VERSION: str = "1.16.0"


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
