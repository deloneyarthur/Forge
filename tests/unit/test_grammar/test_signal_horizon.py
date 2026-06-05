"""Unit tests for ``forge.grammar.signal_horizon`` (v8 / D102).

The horizon table is the Forge-owned source of truth for each indicator's
*signal horizon* in trading days — the input to §3.5 S4 (DTE matches the
signal's natural holding period) and the v8 horizon-matched DTE derivation.

It exists because the live Crucible registry does NOT carry a usable
``IndicatorMetadata.lookback`` (34 / 43 indicators report 0; the rest are
inconsistent — ``rsi_2`` reports 14, ``adx``/``hurst``/``macd`` report 0).
So Forge owns the horizon the way it already owns per-indicator threshold
ranges in ``forge.enumeration.indicator_thresholds`` (D102, operator
decision 2026-06-04).
"""

from __future__ import annotations

import pytest

from forge.enumeration.indicator_thresholds import _INDICATOR_THRESHOLD_TABLE
from forge.grammar.custom_predicates import _P2_ENTRY_DTE
from forge.grammar.signal_horizon import (
    _DEFAULT_HORIZON_DAYS,
    _SIGNAL_HORIZON_TABLE,
    BUCKETS_FOR_HORIZON_CLASS,
    buckets_for_horizon_class,
    horizon_class,
    horizon_class_for_days,
    nearest_bucket,
    signal_horizon_days,
)

# ---------------------------------------------------------------------------
# Coverage — every threshold-eligible indicator has an explicit horizon
# ---------------------------------------------------------------------------


def test_every_thresholdable_indicator_has_an_explicit_horizon() -> None:
    """Any indicator that can be a directional or regime signal (i.e. is
    not ``is_skip`` in the threshold table) MUST have an explicit horizon —
    never the silent default. A registry indicator that slips through would
    otherwise get the medium default and silently mis-bucket under S4."""
    missing = [
        ind_id
        for ind_id, spec in _INDICATOR_THRESHOLD_TABLE.items()
        if not spec.is_skip and ind_id not in _SIGNAL_HORIZON_TABLE
    ]
    assert not missing, f"threshold-eligible indicators missing a horizon entry: {missing}"


def test_all_horizons_are_positive_ints() -> None:
    for ind_id, days in _SIGNAL_HORIZON_TABLE.items():
        assert isinstance(days, int), f"{ind_id} horizon is not int"
        assert days > 0, f"{ind_id} horizon must be positive, got {days}"


def test_signal_horizon_days_default_for_unknown() -> None:
    assert signal_horizon_days("indicator_not_in_any_table_xyz") == _DEFAULT_HORIZON_DAYS


def test_signal_horizon_days_reads_the_table() -> None:
    assert signal_horizon_days("rsi_2") == 2
    assert signal_horizon_days("momentum_252") == 252


# ---------------------------------------------------------------------------
# Horizon class thresholds (D010 / §3.5 S4: short <= 6, medium <= 89)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (1, "short_lookback"),
        (6, "short_lookback"),
        (7, "medium_lookback"),
        (89, "medium_lookback"),
        (90, "long_lookback"),
        (252, "long_lookback"),
    ],
)
def test_horizon_class_for_days_boundaries(days: int, expected: str) -> None:
    assert horizon_class_for_days(days) == expected


@pytest.mark.parametrize(
    ("indicator", "expected"),
    [
        ("rsi_2", "short_lookback"),
        ("rsi_14", "medium_lookback"),
        ("bb_pct", "medium_lookback"),
        ("macd", "medium_lookback"),
        ("adx", "medium_lookback"),
        ("hurst", "long_lookback"),
        ("momentum_252", "long_lookback"),
        ("iv_rank", "medium_lookback"),
        ("pairs_zscore", "medium_lookback"),
        ("put_call_flow", "short_lookback"),
    ],
)
def test_horizon_class_known_indicators(indicator: str, expected: str) -> None:
    assert horizon_class(indicator) == expected


# ---------------------------------------------------------------------------
# §3.5 S4 horizon class -> allowed DTE buckets
# ---------------------------------------------------------------------------


def test_buckets_for_horizon_class() -> None:
    assert buckets_for_horizon_class("short_lookback") == ("swing_short",)
    assert buckets_for_horizon_class("medium_lookback") == ("swing_short", "swing_mid")
    assert buckets_for_horizon_class("long_lookback") == ("swing_mid", "swing_long")


def test_buckets_for_unknown_class_is_empty() -> None:
    assert buckets_for_horizon_class("nonsense") == ()


# ---------------------------------------------------------------------------
# nearest_bucket — snap a continuous DTE target to a discrete bucket (#8)
# ---------------------------------------------------------------------------

_ALL = ("swing_short", "swing_mid", "swing_long")


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (4, "swing_short"),  # rsi_2 * k
        (17, "swing_short"),
        (28, "swing_mid"),  # rsi_14 * 2 — just past the 27.5 midpoint
        (37, "swing_mid"),
        (56, "swing_mid"),  # 56 < the 56.25 swing_mid/swing_long midpoint
        (57, "swing_long"),  # just past it
        (252, "swing_long"),
    ],
)
def test_nearest_bucket_over_all(target: float, expected: str) -> None:
    assert nearest_bucket(_ALL, target) == expected


def test_nearest_bucket_respects_allowed_set() -> None:
    # A target far above the only allowed bucket still clamps to it.
    assert nearest_bucket(("swing_short",), 1000) == "swing_short"
    # Nearest WITHIN the allowed subset, not globally.
    assert nearest_bucket(("swing_mid", "swing_long"), 1) == "swing_mid"
    assert nearest_bucket(("swing_short", "swing_mid"), 1000) == "swing_mid"


def test_nearest_bucket_tie_breaks_to_shorter_bucket() -> None:
    # Exactly the swing_short/swing_mid midpoint (17.5+37.5)/2 = 27.5:
    # tie -> canonical (shorter) bucket, deterministically (#6).
    assert nearest_bucket(_ALL, 27.5) == "swing_short"


def test_nearest_bucket_is_order_independent() -> None:
    assert nearest_bucket(("swing_long", "swing_mid", "swing_short"), 30) == nearest_bucket(
        ("swing_short", "swing_mid", "swing_long"), 30
    )


# ---------------------------------------------------------------------------
# Bucket midpoints stay in lockstep with the §3.5 P2 entry windows
# ---------------------------------------------------------------------------


def test_bucket_midpoints_match_p2_windows() -> None:
    """Drift guard: nearest_bucket()'s midpoints must equal the mean of the
    §3.5 P2 entry windows owned by custom_predicates. If P2 ever changes,
    this fails loudly rather than letting the derivation silently skew."""
    from forge.grammar.signal_horizon import _BUCKET_MIDPOINTS

    for bucket, (low, high) in _P2_ENTRY_DTE.items():
        assert _BUCKET_MIDPOINTS[bucket] == (low + high) / 2, bucket
    assert set(_BUCKET_MIDPOINTS) == set(_P2_ENTRY_DTE)
    assert set(BUCKETS_FOR_HORIZON_CLASS) == {
        "short_lookback",
        "medium_lookback",
        "long_lookback",
    }


# ---------------------------------------------------------------------------
# End-to-end horizon -> bucket sanity (the v8 thesis, pure-function level)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("indicator", "k", "expected"),
    [
        # rsi_2: short class, pinned to swing_short for every k.
        ("rsi_2", 2, "swing_short"),
        ("rsi_2", 4, "swing_short"),
        # macd: the v8 FIX. Today's degenerate registry (lookback 0) forces
        # swing_short; horizon-matched it lands swing_mid.
        ("macd", 2, "swing_mid"),
        ("macd", 4, "swing_mid"),
        # momentum_252: long class -> swing_long.
        ("momentum_252", 2, "swing_long"),
        # rsi_14: medium class, k*14 in {28..56} -> swing_mid.
        ("rsi_14", 2, "swing_mid"),
    ],
)
def test_horizon_matched_bucket_is_thesis_aligned(indicator: str, k: int, expected: str) -> None:
    allowed = buckets_for_horizon_class(horizon_class(indicator))
    target = k * signal_horizon_days(indicator)
    assert nearest_bucket(allowed, target) == expected
