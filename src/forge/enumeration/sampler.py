"""Stratified hypothesis-first sampler for grammar-valid ``StrategyConfig``.

§4.2's CSP-style algorithm with the D7 amendment (sizer mode picked second so
§3.5 X1/X2 indicator chaining can complete):

1. Pick hypothesis (only those with non-empty directional + regime pools).
2. Pick sizer mode (only those in ``samplable_sizer_modes``).
3. Pick DTE bucket (filtered for compat with the X1/X2 chain indicator's
   §3.5 S4 lookback class, if a chain is required).
4. Pick directional indicator from §3.5 C2 pool, S4-compatible with bucket.
5. Pick regime indicator from §3.5 R-rule pool, S4-compatible, C4-disjoint
   in id, C1-disjoint in family from directional.
6. Sample selector params: ``delta_target`` in §3.5 P3 band; ``dte_min`` /
   ``dte_max`` from the §3.5 P2 entry window for the bucket.
7. Sample sizer: ``per_trade_risk_pct`` in §3.5 P4 range; mode-specific
   knobs from ``forge.enumeration.defaults``.
8. Compose exits: §3.5 E1 mandatory + §3.5 S5 required for the hypothesis;
   forbidden exits are simply not added.
9. If the sizer mode demands a chained indicator (X1/X2) and it isn't
   already on the strategy, attach as a confluence signal.

Configs are valid-by-construction (closure-plan path (a)). The iterator
runs ``validate()`` as a safety net and logs any residual rejections.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
)

from forge.enumeration import defaults
from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)

if TYPE_CHECKING:
    from crucible_contracts import IndicatorMetadata, RegistrySnapshot

    from forge.enumeration.search_space import SearchSpace


class SamplerError(Exception):
    """Raised when the sampler cannot construct a config from the current
    grammar + registry slice (empty pool at some CSP step)."""


# Bucket → S4-allowed lookback classes. Mirror of
# ``forge.grammar.custom_predicates._LOOKBACK_DTE_TABLE`` inverted: that
# table maps lookback_class → allowed buckets; here we want bucket →
# allowed classes. Keep semantics aligned with §3.5 S4 + D010.
_LOOKBACK_CLASSES_FOR_BUCKET: dict[str, frozenset[str]] = {
    "swing_short": frozenset({"short_lookback", "medium_lookback"}),
    "swing_mid": frozenset({"medium_lookback", "long_lookback"}),
    "swing_long": frozenset({"long_lookback"}),
}

# Inverse: lookback_class → allowed buckets. Used to pick a bucket that is
# compatible with an already-chosen indicator (the X1/X2 chain case).
_BUCKETS_FOR_LOOKBACK_CLASS: dict[str, tuple[str, ...]] = {
    "short_lookback": ("swing_short",),
    "medium_lookback": ("swing_short", "swing_mid"),
    "long_lookback": ("swing_mid", "swing_long"),
}

# D010 lookback-class thresholds — must match
# ``forge.grammar.custom_predicates._lookback_class``.
_LOOKBACK_SHORT_MAX = 6
_LOOKBACK_MEDIUM_MAX = 89


def _lookback_class(lookback: int) -> str:
    if lookback <= _LOOKBACK_SHORT_MAX:
        return "short_lookback"
    if lookback <= _LOOKBACK_MEDIUM_MAX:
        return "medium_lookback"
    return "long_lookback"


def sample_config(
    space: SearchSpace,
    registry: RegistrySnapshot,
    rng: random.Random,
) -> StrategyConfig:
    """Construct one grammar-valid ``StrategyConfig`` using ``rng`` for every choice.

    Raises ``SamplerError`` only when the registry is so sparse that no
    grammar-valid config can be built (empty pool at some CSP step).
    """
    by_id: dict[str, IndicatorMetadata] = {ind.id: ind for ind in registry.indicators}

    samplable_hypotheses = tuple(
        h
        for h in space.hypotheses
        if space.directional_indicators_by_hypothesis[h]
        and space.regime_indicators_by_hypothesis[h]
    )
    if not samplable_hypotheses:
        msg = "no hypothesis has non-empty directional + regime pools"
        raise SamplerError(msg)
    if not space.samplable_sizer_modes:
        msg = "no sizer mode is samplable in the current registry"
        raise SamplerError(msg)

    hypothesis = rng.choice(samplable_hypotheses)
    mode = rng.choice(space.samplable_sizer_modes)
    chain_id = space.sizer_required_indicator.get(mode)

    viable = _viable_buckets(space, by_id, hypothesis, chain_id)
    if not viable:
        msg = (
            f"no DTE bucket has a (directional, regime) pair satisfying §3.5 "
            f"S4 + C1/C4 + R-rules for hypothesis={hypothesis} mode={mode}"
        )
        raise SamplerError(msg)
    bucket = rng.choice(viable)

    # `viable` guarantees at least one valid (directional, regime) pair
    # exists for this bucket; we now make the random pick. The directional
    # pick can in principle land on an indicator family that blocks every
    # regime via C1; in that case we fall back to the deterministic-by-rng
    # `_pair_for_bucket` search to keep path (a) intact.
    directional_id, regime_id = _pick_directional_regime_pair(space, by_id, hypothesis, bucket, rng)

    signals = [
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=(directional_id,),
            params=_directional_signal_params(directional_id, rng),
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=(regime_id,),
            params=_regime_signal_params(hypothesis, regime_id, rng),
        ),
    ]
    if chain_id is not None and chain_id not in {directional_id, regime_id}:
        signals.append(
            SignalSpec(
                id=f"sig_chain_{chain_id}",
                type="passthrough",
                role="confluence",
                indicators=(chain_id,),
            )
        )

    selector = _build_selector(space, bucket, rng)
    sizer = _build_sizer(space, mode, rng)
    exits = _build_exits(space, hypothesis, rng)

    config_name = f"forge_{hypothesis}_{bucket}_{rng.getrandbits(32):08x}"
    return StrategyConfig(
        name=config_name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket=bucket,  # type: ignore[arg-type]
        underlying=None,
        tier=1,
        signals=tuple(signals),
        combiner=CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1),
        selector=selector,
        sizer=sizer,
        exits=exits,
        equity_hedge_metadata=None,  # D5: Forge submits pure options
    )


def _viable_buckets(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    chain_id: str | None,
) -> tuple[str, ...]:
    """Buckets compatible with (a) the X1/X2 chain indicator's §3.5 S4
    lookback class, if any, AND (b) at least one (directional, regime)
    pair that satisfies §3.5 S4 + C1 + C4 + R-rules. The actual pick
    happens inside the bucket; this only certifies existence."""
    if chain_id is None:
        chain_compat_buckets = space.dte_buckets
    else:
        chain_cls = _lookback_class(by_id[chain_id].lookback)
        chain_compat_buckets = _BUCKETS_FOR_LOOKBACK_CLASS[chain_cls]

    directional_pool = space.directional_indicators_by_hypothesis[hypothesis]
    regime_pool = space.regime_indicators_by_hypothesis[hypothesis]

    viable: list[str] = []
    for bucket in space.dte_buckets:
        if bucket not in chain_compat_buckets:
            continue
        allowed_cls = _LOOKBACK_CLASSES_FOR_BUCKET[bucket]
        compat_directionals = [
            i
            for i in directional_pool
            if i in by_id
            and _lookback_class(by_id[i].lookback) in allowed_cls
            and not is_threshold_skippable(i)
        ]
        compat_regimes = [
            i
            for i in regime_pool
            if i in by_id
            and _lookback_class(by_id[i].lookback) in allowed_cls
            and not is_threshold_skippable(i)
        ]
        if _has_valid_pair(compat_directionals, compat_regimes, by_id):
            viable.append(bucket)
    return tuple(viable)


def _has_valid_pair(
    directionals: list[str],
    regimes: list[str],
    by_id: dict[str, IndicatorMetadata],
) -> bool:
    """True iff some (d, r) pair from the inputs has different ids (C4)
    AND different families (C1)."""
    return any(d != r and by_id[d].family != by_id[r].family for d in directionals for r in regimes)


def _pick_directional_regime_pair(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    bucket: str,
    rng: random.Random,
) -> tuple[str, str]:
    """Pick a (directional, regime) pair satisfying §3.5 S4 + C1 + C4 for
    the given bucket. Precondition: ``bucket`` is in ``_viable_buckets``,
    so at least one valid pair exists. The pick is rng-driven; if the
    rng-chosen directional has no compatible regime, fall back to the
    first valid pair by canonical id order (still deterministic)."""
    allowed_cls = _LOOKBACK_CLASSES_FOR_BUCKET[bucket]
    compat_directionals = tuple(
        i
        for i in space.directional_indicators_by_hypothesis[hypothesis]
        if i in by_id
        and _lookback_class(by_id[i].lookback) in allowed_cls
        and not is_threshold_skippable(i)
    )
    compat_regimes = tuple(
        i
        for i in space.regime_indicators_by_hypothesis[hypothesis]
        if i in by_id
        and _lookback_class(by_id[i].lookback) in allowed_cls
        and not is_threshold_skippable(i)
    )

    directional_id = rng.choice(compat_directionals)
    directional_family = by_id[directional_id].family
    regimes = tuple(
        i for i in compat_regimes if i != directional_id and by_id[i].family != directional_family
    )
    if regimes:
        return directional_id, rng.choice(regimes)

    # Fall back: scan compat_directionals in id order for one with a valid
    # regime partner. Guaranteed by ``_viable_buckets`` precondition.
    for d_id in compat_directionals:
        d_family = by_id[d_id].family
        candidate_regimes = tuple(
            i for i in compat_regimes if i != d_id and by_id[i].family != d_family
        )
        if candidate_regimes:
            return d_id, rng.choice(candidate_regimes)
    msg = f"_viable_buckets precondition violated for hypothesis={hypothesis} bucket={bucket}"
    raise SamplerError(msg)


def _build_selector(
    space: SearchSpace,
    bucket: str,
    rng: random.Random,
) -> SelectorSpec:
    """§3.5 P2 entry-side DTE + §3.5 P3 delta band, with the rest of the
    ``SelectorSpec`` fields fixed from ``forge.enumeration.defaults``."""
    dte_low, dte_high = space.dte_entry_window_by_bucket[bucket]
    delta_low, delta_high = space.delta_band_by_bucket[bucket]
    return SelectorSpec(
        delta_target=round(rng.uniform(delta_low, delta_high), 3),
        delta_tolerance=defaults.DELTA_TOLERANCE,
        dte_min=dte_low,
        dte_max=dte_high,
        prefer_monthly_expiry=defaults.PREFER_MONTHLY_EXPIRY,
        min_open_interest=defaults.MIN_OPEN_INTEREST,
        min_volume=defaults.MIN_VOLUME,
        max_bid_ask_spread_pct=defaults.MAX_BID_ASK_SPREAD_PCT,
    )


def _build_sizer(
    space: SearchSpace,
    mode: str,
    rng: random.Random,
) -> SizerSpec:
    """§3.5 P4 ``per_trade_risk_pct`` sampling; mode-specific knobs come
    from ``defaults`` since v1 grammar doesn't constrain them."""
    risk_low, risk_high = space.risk_pct_range
    return SizerSpec(
        mode=mode,  # type: ignore[arg-type]
        per_trade_risk_pct=round(rng.uniform(risk_low, risk_high), 4),
        kelly_fraction=defaults.KELLY_FRACTION,
        vol_target_annual=defaults.VOL_TARGET_ANNUAL,
    )


def _build_exits(
    space: SearchSpace,
    hypothesis: str,
    rng: random.Random,
) -> tuple[ExitSpec, ...]:
    """§3.5 E1 mandatory + §3.5 S5 required for the hypothesis. Forbidden
    exits per S5 are simply omitted — there's no need to materialize a
    forbidden set. §3.5 E3 demands ``activate_after_gain_pct ≥ 0.30`` on
    any ``trailing_atr`` exit; the sampler sets it here so trend
    configs are valid by construction."""
    ids: list[str] = list(space.e1_mandatory)
    ids.extend(space.s5_required_by_hypothesis[hypothesis])
    # Preserve order, deduplicate (E1 vs S5 overlap is possible).
    deduped = list(dict.fromkeys(ids))
    return tuple(ExitSpec(id=eid, params=_exit_params(eid, rng)) for eid in deduped)


def _directional_signal_params(
    indicator_id: str,
    rng: random.Random,
) -> dict[str, object]:
    """Threshold params for the directional signal.

    Sourced from `forge.enumeration.indicator_thresholds`, which encodes
    audited per-indicator distributions on real SPY bars (see
    `docs/INDICATOR_THRESHOLDS.md`, 2026-05-14). Prior to this audit Forge
    emitted directional threshold signals with empty params; Crucible's
    predicate then returned False on every bar, producing 0 activations
    and 100% signal_density rejection under the real feature cache.
    """
    return sample_threshold_params(indicator_id, "directional", rng)


def _regime_signal_params(
    hypothesis: str,
    regime_id: str,
    rng: random.Random,
) -> dict[str, object]:
    """Threshold params for the regime_filter signal.

    Uses `forge.enumeration.indicator_thresholds.sample_threshold_params`
    for the audited per-indicator distributions. §3.5 R1's "threshold <= 50"
    constraint on iv_rank is honored by the table's `regime_range=(10, 50)`
    entry for that indicator; no special-case logic needed here.
    """
    return sample_threshold_params(regime_id, "regime_filter", rng)


def _exit_params(exit_id: str, rng: random.Random) -> dict[str, object]:
    """E3: ``trailing_atr`` requires ``activate_after_gain_pct ≥ 0.30``."""
    if exit_id == "trailing_atr":
        return {"activate_after_gain_pct": round(rng.uniform(0.30, 0.50), 2)}
    return {}
