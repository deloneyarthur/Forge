"""Phase 0 integration: `crucible_contracts` is importable and version-compatible."""

from __future__ import annotations

import pytest

from forge.core.contracts_check import (
    FORGE_EXPECTED_CONTRACT_VERSION,
    SchemaVersionMismatch,
    check_contracts_version,
)


def test_contracts_version_compatible() -> None:
    version = check_contracts_version()
    assert version
    assert version.split(".", 1)[0] == FORGE_EXPECTED_CONTRACT_VERSION.split(".", 1)[0]


def test_contracts_models_importable() -> None:
    # Hard rule #2: only `crucible_contracts` is the inter-system surface.
    # Sanity-check that the symbols Forge will rely on are reachable.
    from crucible_contracts import (
        GatedRun,
        IndicatorMetadata,
        StrategyConfig,
        get_recent_gated_runs,
    )

    assert StrategyConfig is not None
    assert IndicatorMetadata is not None
    assert GatedRun is not None
    assert callable(get_recent_gated_runs)


def test_version_mismatch_raises() -> None:
    from crucible_contracts import validate_schema_version

    with pytest.raises(SchemaVersionMismatch):
        validate_schema_version("2.0.0", "1.1.0")
