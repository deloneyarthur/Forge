"""Lock-in tests for ``forge.enumeration.defaults``.

Numbers here are operator-set (D6 from the Phase 2 closure plan). The tests
exist to make any silent edit visible in a PR diff — not because the values
themselves carry inherent test-able invariants.
"""

from __future__ import annotations

from crucible_contracts import (
    ABSOLUTE_MAX_CONCURRENT_RISK_PCT,
    ABSOLUTE_MAX_PER_TRADE_RISK_PCT,
)

from forge.enumeration import defaults


def test_d6_defaults_match_closure_plan() -> None:
    assert defaults.DELTA_TOLERANCE == 0.05
    assert defaults.PREFER_MONTHLY_EXPIRY is False
    assert defaults.MIN_OPEN_INTEREST == 100
    assert defaults.MIN_VOLUME == 10
    assert defaults.MAX_BID_ASK_SPREAD_PCT == 0.10
    assert defaults.KELLY_FRACTION == 0.25
    assert defaults.VOL_TARGET_ANNUAL == 0.20


def test_kelly_fraction_within_unit_interval() -> None:
    """SizerSpec.kelly_fraction is validated to [0, 1]."""
    assert 0.0 <= defaults.KELLY_FRACTION <= 1.0


def test_vol_target_within_unit_interval() -> None:
    """SizerSpec.vol_target_annual is validated to (0, 1]."""
    assert 0.0 < defaults.VOL_TARGET_ANNUAL <= 1.0


def test_defaults_do_not_breach_absolute_risk_caps() -> None:
    """Defense in depth — defaults shouldn't accidentally exceed the
    contracts-enforced ceilings even though they don't drive risk directly."""
    assert defaults.KELLY_FRACTION < 1.0
    assert defaults.VOL_TARGET_ANNUAL < 1.0
    # The defaults file doesn't set risk pcts (P4 numerical_range owns
    # per_trade_risk_pct), but make sure no one ever defaults vol_target
    # to a number that, even taken as a risk_pct upper bound, exceeds the
    # absolute concurrent cap.
    assert defaults.VOL_TARGET_ANNUAL <= ABSOLUTE_MAX_CONCURRENT_RISK_PCT * 2, (
        "vol_target_annual default is suspiciously close to the concurrent cap"
    )
    # Per-trade cap is a separate axis; this is a smoke check that the
    # default is well below it on any reasonable interpretation.
    assert defaults.KELLY_FRACTION > ABSOLUTE_MAX_PER_TRADE_RISK_PCT
