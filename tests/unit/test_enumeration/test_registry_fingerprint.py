"""Unit tests for ``forge.enumeration.registry_fingerprint``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crucible_contracts import (
    IndicatorMetadata,
    RegistrySnapshot,
)

from forge.enumeration.registry_fingerprint import registry_hash
from tests.fixtures.strategy_configs import minimal_registry_snapshot


def _snapshot(**overrides: object) -> RegistrySnapshot:
    """Compact factory: one-indicator snapshot with override hooks."""
    base = {
        "indicators": (
            IndicatorMetadata(
                id="rsi_2",
                version=1,
                family="mean_reversion",
                lookback=2,
                params_schema={},
            ),
        ),
        "signal_types": ("threshold",),
        "exit_ids": ("expiry_exit",),
        "sizer_modes": ("fixed_risk_pct",),
        "snapshot_taken_at": datetime(2026, 5, 13, tzinfo=UTC),
        "crucible_version": "0.0.0-synthetic",
    }
    base.update(overrides)
    return RegistrySnapshot(**base)  # type: ignore[arg-type]


def test_hash_is_16_hex_chars() -> None:
    h = registry_hash(_snapshot())
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_is_stable_for_same_snapshot() -> None:
    """Required by §13.1: same registry content → same hash, every call."""
    a = registry_hash(_snapshot())
    b = registry_hash(_snapshot())
    assert a == b


def test_hash_stable_for_fixture_registry() -> None:
    """Test fixture isn't time-dependent and should hash identically each run."""
    a = registry_hash(minimal_registry_snapshot())
    b = registry_hash(minimal_registry_snapshot())
    assert a == b


@pytest.mark.parametrize(
    "field",
    [
        "indicators",
        "signal_types",
        "exit_ids",
        "sizer_modes",
        "snapshot_taken_at",
        "crucible_version",
    ],
)
def test_hash_is_sensitive_to_each_field(field: str) -> None:
    """Every snapshot field must contribute to the hash; otherwise §13.1
    would fail to notice a registry change."""
    baseline = _snapshot()
    baseline_hash = registry_hash(baseline)

    if field == "indicators":
        modified = _snapshot(
            indicators=(
                *baseline.indicators,
                IndicatorMetadata(
                    id="ema_50",
                    version=1,
                    family="trend",
                    lookback=50,
                    params_schema={},
                ),
            ),
        )
    elif field == "signal_types":
        modified = _snapshot(signal_types=("threshold", "rule"))
    elif field == "exit_ids":
        modified = _snapshot(exit_ids=("expiry_exit", "earnings_exit"))
    elif field == "sizer_modes":
        modified = _snapshot(sizer_modes=("fixed_risk_pct", "vol_target"))
    elif field == "snapshot_taken_at":
        modified = _snapshot(snapshot_taken_at=datetime(2027, 1, 1, tzinfo=UTC))
    else:  # crucible_version
        modified = _snapshot(crucible_version="9.9.9-bumped")

    assert registry_hash(modified) != baseline_hash


def test_hash_is_sensitive_to_indicator_internals() -> None:
    """A change to an indicator's family (e.g., reclassifying adx) must
    produce a different hash — exactly the kind of registry change that
    affects enumeration outcomes."""
    a = _snapshot(
        indicators=(
            IndicatorMetadata(
                id="adx",
                version=1,
                family="volatility",
                lookback=14,
                params_schema={},
            ),
        ),
    )
    b = _snapshot(
        indicators=(
            IndicatorMetadata(
                id="adx",
                version=1,
                family="trend_strength",
                lookback=14,
                params_schema={},
            ),
        ),
    )
    assert registry_hash(a) != registry_hash(b)
