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


def test_expected_contract_version_matches_installed() -> None:
    """Exact pin equality, not just major-compat (D123).

    §13.5's runtime check is deliberately MAJOR-only, so a contracts minor
    release ships silently under a stale pin. Crucible's tree carries the
    mirror of this test; without it Forge can run indefinitely against
    contract surface it never explicitly adopted (the 1.17.0→1.18.0 gap this
    test was born RED on). A failure here means: read the new release, then
    bump `FORGE_EXPECTED_CONTRACT_VERSION` in the same commit as any code
    the release requires.
    """
    from crucible_contracts import CONTRACT_VERSION

    assert CONTRACT_VERSION == FORGE_EXPECTED_CONTRACT_VERSION


def test_indicator_metadata_rank_path_flags_fail_closed() -> None:
    """The 1.18.0 rank-path flags exist and default to excluded (D123).

    The v16 enumeration policy keys the rank branch on these two fields, so
    their absence-semantics are load-bearing: an indicator whose snapshot
    entry omits them must read as NOT rank-eligible (`rank_per_name_coherent
    is False`) and NOT a market-wide gate. This is the agreed fail-closed
    default — a new Crucible indicator ships off the rank branch until
    proven coherent — and it is what makes pre-1.18 snapshot files parse
    unchanged.
    """
    from crucible_contracts import IndicatorMetadata

    meta = IndicatorMetadata(
        id="rsi_2",
        version=1,
        family="mean_reversion",
        lookback=2,
        params_schema={},
    )
    assert meta.rank_per_name_coherent is False
    assert meta.market_wide_by_design is False
