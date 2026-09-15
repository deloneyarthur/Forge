"""Registry snapshots that SERVE the ids an emission property is about.

WHY: the minimal fixture registry deliberately serves few ids, so a property asserted on it can
pass vacuously. A retirement whose whole content is "id X stops being emitted" proves nothing on
a registry that never served X (the D340 trap caught in the v52 work). These helpers add the ids
with families and flags exactly as the live registry publishes them, so the sampler leaves its
fixture dormancy and the assertion bites. The long `_v17..._v31` chain that the sampler goldens
pin stays beside those goldens in `test_sampler.py`.
"""

from __future__ import annotations

from crucible_contracts import IndicatorMetadata, RegistrySnapshot


def meta(
    ind_id: str,
    family: str,
    *,
    version: int = 1,
    lookback: int = 0,
    rank_coherent: bool = False,
    market_wide: bool = False,
) -> IndicatorMetadata:
    return IndicatorMetadata(
        id=ind_id,
        version=version,
        family=family,
        lookback=lookback,
        params_schema={},
        rank_per_name_coherent=rank_coherent,
        market_wide_by_design=market_wide,
    )


def with_indicators(base: RegistrySnapshot, *extra: IndicatorMetadata) -> RegistrySnapshot:
    return base.model_copy(update={"indicators": (*base.indicators, *extra)})


def v33_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """Every id the v33 (D276) and v34 (D278) items touch."""
    return with_indicators(
        base,
        meta("residual_momentum", "trend", lookback=504, rank_coherent=True),
        meta("vix_term_slope", "macro", market_wide=True),
        meta("days_since_jump", "volatility", version=3, lookback=252, rank_coherent=True),
        meta("gamma_flip_distance_pct", "dealer_positioning", lookback=1),
        meta("option_momentum", "smart_money", lookback=147),
        meta("pre_earnings_setup", "calendar", version=2, lookback=252),
        meta("days_to_nfp", "calendar"),
        meta("days_to_cpi", "calendar"),
    )


def v44_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """The ids the vix conditioner path touches; vix_term_slope becomes an R2 trend gate here."""
    return with_indicators(
        base,
        meta("residual_momentum", "trend", lookback=504, rank_coherent=True),
        meta("vix_term_slope", "macro", market_wide=True),
        meta("days_since_jump", "volatility", version=3, lookback=252, rank_coherent=True),
        meta("market_state", "macro", market_wide=True),
    )


def rtr_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """+ ref_trailing_return, the ve veto (live v4 entry, verified 2026-07-19)."""
    return with_indicators(
        base, meta("ref_trailing_return", "macro", lookback=10, market_wide=True)
    )


def its_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """+ iv_term_slope, the ve C2 iv_structure directional."""
    return with_indicators(
        base, meta("iv_term_slope", "iv_structure", lookback=90, rank_coherent=True)
    )
