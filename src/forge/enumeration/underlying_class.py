"""Forge-owned underlying classification table (D105).

WHY this exists: Crucible's v9 yield map (2026-06-07 handoff) showed the
strongest component-yield structure sits on the underlying axis — high
idiosyncratic-vol single names minted at 12.8-27.9% (AAPL 17/61, NVDA 8/36,
TSLA 6/47) while every diversified ETF/index underlying with >=30 decided sat
at exactly 0 components (~390 decided across SPY/QQQ/XL*/SMH/SOXX/EEM/VIX/...).
Per-hypothesis weights cannot express that, and the universe export carries no
class metadata, so Forge owns the classification the same way it owns the
signal-horizon and threshold tables: as auditable enumeration-policy domain
knowledge keyed by ticker.

Two classes only (the handoff's recommendation — per-name Bayesian smoothing
can come later): ``DIVERSIFIED`` is the curated ETF/index list below;
everything else is ``HIGH_IDIO_VOL``. Leveraged and volatility/thematic ETFs
(TQQQ, SQQQ, SOXL, UVXY, ARKK) are deliberately NOT in the diversified list —
they trade like high-vol names and the handoff explicitly flags TQQQ/ARKK among
the undersampled high-beta candidates. Unknown tickers (future universe
additions) default to HIGH_IDIO_VOL: additions are most likely single names,
and the cost of a misclassified new ETF is a diluted class posterior, not a
crash — extend the list when the universe changes.

Operator-owned in spirit (it parameterises the sampler's underlying draw):
change memberships with a Decision Log entry, as with the horizon table.
"""

from __future__ import annotations

HIGH_IDIO_VOL: str = "high_idio_vol"
DIVERSIFIED: str = "diversified"

# Curated diversified ETF/index underlyings (universe snapshot 2026-06-07,
# 124 tickers). Broad index, sector/industry, bond/commodity, and index-level
# volatility reads — the "wall of zeros" cohort in the yield map.
_DIVERSIFIED_ETF_INDEX: frozenset[str] = frozenset(
    {
        # broad equity index
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "EEM",
        "EFA",
        # sector / industry
        "XLB",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLU",
        "XLV",
        "XLY",
        "SMH",
        "SOXX",
        "XBI",
        # bond / credit / commodity
        "TLT",
        "HYG",
        "GLD",
        "SLV",
        "USO",
        "UNG",
        # volatility index (an index-level read, not an idiosyncratic-vol name)
        "VIX",
    }
)


def underlying_class(ticker: str) -> str:
    """Class of one underlying: ``DIVERSIFIED`` (curated list) or
    ``HIGH_IDIO_VOL`` (everything else, including leveraged/thematic ETFs and
    unknown future additions — see the module docstring for why that default)."""
    return DIVERSIFIED if ticker in _DIVERSIFIED_ETF_INDEX else HIGH_IDIO_VOL


__all__ = ["DIVERSIFIED", "HIGH_IDIO_VOL", "underlying_class"]
