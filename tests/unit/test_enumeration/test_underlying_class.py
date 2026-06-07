"""Tests for the D105 underlying classification table."""

from __future__ import annotations

from forge.enumeration.sampler import _FALLBACK_TIER_1_2_UNDERLYINGS
from forge.enumeration.underlying_class import (
    DIVERSIFIED,
    HIGH_IDIO_VOL,
    underlying_class,
)


def test_broad_index_and_sector_etfs_are_diversified() -> None:
    for t in ("SPY", "QQQ", "IWM", "DIA", "EEM", "XLK", "XLV", "SMH", "SOXX", "VIX", "TLT", "GLD"):
        assert underlying_class(t) == DIVERSIFIED, t


def test_single_names_are_high_idio_vol() -> None:
    for t in ("AAPL", "NVDA", "TSLA", "COIN", "MSTR", "SHOP", "AMD", "PLTR", "MRNA"):
        assert underlying_class(t) == HIGH_IDIO_VOL, t


def test_leveraged_and_thematic_etfs_are_high_idio_vol() -> None:
    """The handoff's boundary: TQQQ/ARKK (and kin) trade like high-vol names
    and are explicitly flagged as undersampled high-beta — they must NOT fall
    in the diversified bucket despite being ETFs."""
    for t in ("TQQQ", "SQQQ", "SOXL", "UVXY", "ARKK"):
        assert underlying_class(t) == HIGH_IDIO_VOL, t


def test_unknown_ticker_defaults_to_high_idio_vol() -> None:
    """Future universe additions are most likely single names; the default
    keeps them in the explored class rather than the wall-of-zeros one."""
    assert underlying_class("ZZZT") == HIGH_IDIO_VOL


def test_fallback_universe_fully_classified_with_expected_split() -> None:
    """The D033 fallback pool: exactly its 4 Tier-1 ETFs are diversified,
    everything else high-idio-vol (total function, no surprises offline)."""
    classes = {t: underlying_class(t) for t in _FALLBACK_TIER_1_2_UNDERLYINGS}
    diversified = {t for t, c in classes.items() if c == DIVERSIFIED}
    assert diversified == {"SPY", "QQQ", "IWM", "DIA"}
