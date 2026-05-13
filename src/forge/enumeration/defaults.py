"""Defaults for ``StrategyConfig`` fields the v1 grammar doesn't constrain.

§3.5 has no rule on these fields, so the enumerator picks fixed values
rather than sampling. Phase 5 grammar refinements may promote any of
these into sampled parameters; the table below is the v1 baseline.

D6 from the Phase 2 closure plan. Tightening these (e.g., raising
``MIN_OPEN_INTEREST``) is auto-tightening per CLAUDE.md hard rule #4 and
ships without operator approval; widening (e.g., lowering it) is
auto-loosening and must go through ``OPEN_PROPOSALS.md`` first.
"""

from __future__ import annotations

# SelectorSpec defaults
DELTA_TOLERANCE: float = 0.05
PREFER_MONTHLY_EXPIRY: bool = False
MIN_OPEN_INTEREST: int = 100
MIN_VOLUME: int = 10
MAX_BID_ASK_SPREAD_PCT: float = 0.10

# SizerSpec mode-conditional defaults
KELLY_FRACTION: float = 0.25
VOL_TARGET_ANNUAL: float = 0.20
