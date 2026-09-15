"""Registry snapshots that SERVE the ids an emission property is about.

WHY: the minimal fixture registry deliberately serves few ids, so a property asserted on it can
pass vacuously. A retirement whose whole content is "id X stops being emitted" proves nothing on
a registry that never served X (the D340 trap caught in the v52 work). These helpers add the ids
with families and flags exactly as the live registry publishes them, so the sampler leaves its
fixture dormancy and the assertion bites. The `v17..v31` chain is the one the sampler goldens
pin: each step adds exactly the ids that grammar version activated, in the order the goldens
were captured with, so moving them here changes no golden VALUE (hard rule #6).
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


def v17_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """+ the two v17 (D131) activations: iv_minus_rv (ve directional), market_state (R2)."""
    return with_indicators(
        base,
        meta("iv_minus_rv", "iv_structure", lookback=21),
        meta("market_state", "macro", market_wide=True),
    )


def v18_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """+ the v18 (D135) adoption-cut ids, flags as the 2026-06-10 52-id snapshot published them."""
    return with_indicators(
        base,
        meta("iv_term_slope", "iv_structure"),
        meta("option_momentum", "smart_money", lookback=147),
        meta("pre_earnings_setup", "calendar", version=2, lookback=252),
    )


def v25_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """+ days_since_jump, the v25 (D258) trend veto (served live since 2026-07-09)."""
    return with_indicators(
        base, meta("days_since_jump", "volatility", version=3, lookback=252, rank_coherent=True)
    )


def v26_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """+ dsj AND ivol (idiosyncratic_vol, contracts 1.28.0), the v26 (D263) MR veto state."""
    return with_indicators(
        base,
        meta("days_since_jump", "volatility", version=3, lookback=252, rank_coherent=True),
        meta("ivol", "idiosyncratic_vol", lookback=63, rank_coherent=True),
    )


def v27_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """v26 + the two v27 (D264) resid_vix activations."""
    return with_indicators(
        v26_registry(base),
        meta("residual_momentum", "trend", lookback=504, rank_coherent=True),
        meta("vix_term_slope", "macro", market_wide=True),
    )


def v29_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """v26 + market_realized_vol (macro, market-wide), the v29 (D266) state."""
    return with_indicators(
        v26_registry(base), meta("market_realized_vol", "macro", market_wide=True)
    )


def v31_registry(base: RegistrySnapshot) -> RegistrySnapshot:
    """v29 + the parameterized `momentum` (trend, rank-coherent), the v31 (D270) state."""
    return with_indicators(
        v29_registry(base), meta("momentum", "trend", lookback=504, rank_coherent=True)
    )
