"""The Tier-1 generation-A/B env gate (`FORGE_GENERATION_ARM_B_SHARE`).

Pins the OFF-default and the clamp. A reboot onto this code before the operator's activation
window must change nothing: share 0 means the iterator draws no arm coin, consumes no rng and
stamps no `generation_arm`, so enumeration stays byte-identical (hard rule #6).

The upper clamp is the experimental-design guard rather than tidiness — arm B may never take
more than half the stream, because an A/B that reallocates most of generation to the treatment
has no control left to compare against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.cli.main import _load_book_usable_regime_weights, _resolve_generation_arm_b_share
from forge.persistence.db import open_db


def test_absent_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORGE_GENERATION_ARM_B_SHARE", raising=False)
    assert _resolve_generation_arm_b_share() == 0.0


@pytest.mark.parametrize("raw", ["", "   ", "on", "half", "0.5x", "NaN-ish"])
def test_malformed_degrades_to_zero(raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Degrade-never-crash: a typo in the unit file must leave the arm off, not halt the
    daemon and not silently run an experiment nobody configured."""
    monkeypatch.setenv("FORGE_GENERATION_ARM_B_SHARE", raw)
    assert _resolve_generation_arm_b_share() == 0.0


def test_valid_share_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_GENERATION_ARM_B_SHARE", "0.25")
    assert _resolve_generation_arm_b_share() == pytest.approx(0.25)


def test_clamped_so_a_control_arm_always_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_GENERATION_ARM_B_SHARE", "0.95")
    assert _resolve_generation_arm_b_share() == 0.5
    monkeypatch.setenv("FORGE_GENERATION_ARM_B_SHARE", "-1")
    assert _resolve_generation_arm_b_share() == 0.0


def test_weights_degrade_to_empty_on_a_cold_db(tmp_path: Path) -> None:
    """No honest-arm rows -> {} -> the caller keeps the incumbent map and the arm is INERT.
    A cold start must not produce a half-learned map that quietly steers the draw."""
    db = tmp_path / "forge.db"
    open_db(db).close()
    assert _load_book_usable_regime_weights(db) == {}


def test_weights_degrade_to_empty_on_a_missing_db(tmp_path: Path) -> None:
    assert _load_book_usable_regime_weights(tmp_path / "nope.db") == {}
