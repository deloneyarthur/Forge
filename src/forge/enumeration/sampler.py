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

import functools
import hashlib
import random
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
    load_universe_tickers_from_export,
)
from crucible_contracts.exceptions import QueryError

from forge.enumeration import defaults
from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.search_space import NON_ENUMERABLE_HYPOTHESES
from forge.grammar.custom_predicates import (
    _LOOKBACK_MEDIUM_MAX,
    _LOOKBACK_SHORT_MAX,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from crucible_contracts import IndicatorMetadata, RegistrySnapshot

    from forge.enumeration.search_space import SearchSpace

_logger = structlog.get_logger(__name__)


# Prior mean for hypotheses absent from the rejection-weights map.
# Mirrors `forge.feedback.rejection_weights.prior_mean` to avoid a
# circular import between enumeration and feedback. Kept local but
# semantically tied to DEFAULT_ALPHA / DEFAULT_BETA there.
_HYPOTHESIS_WEIGHT_PRIOR_MEAN: float = 1.0 / 11.0


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

# D033 fallback — used when the Crucible universe export is absent.
_FALLBACK_TIER_1_2_UNDERLYINGS: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "AMD",
    "META",
    "AMZN",
    "GOOGL",
    "NFLX",
    "AVGO",
    "BAC",
    "JPM",
    "XOM",
    "CVX",
    "BA",
    "GE",
    "GS",
    "MS",
    "COIN",
    "MSTR",
)

# Exports directory Crucible publishes to. `load_universe_tickers_from_export`
# globs `universe_tickers*.json` within it (contracts 1.13.0).
_UNIVERSE_EXPORT_DIR = Path("~/optbt_data/exports").expanduser()


@functools.lru_cache(maxsize=1)
def _load_underlyings() -> tuple[str, ...]:
    """D078 / Q23: load Tier 1+2 tickers from Crucible's universe export via the
    blessed `crucible_contracts.load_universe_tickers_from_export` helper.

    Q23 (audit H-5) closed by contracts 1.13.0: the universe read is now on the
    `EXPORT_LAYOUT` surface, so this is no longer an uncontracted hard-rule-#2
    deviation — the prior raw `json.loads` + `universe_uncontracted_read` warning
    are gone. Falls back to the D033 hardcoded list when the export is absent or
    empty; a present-but-unparseable export raises `QueryError` (M-13 drift
    signal), which we log loudly before falling back. Cached for the process
    lifetime — restart to pick up changes.
    """
    try:
        tickers = load_universe_tickers_from_export(_UNIVERSE_EXPORT_DIR)
    except QueryError as err:
        # M-13: present-but-unparseable export is a DRIFT signal distinct from
        # the expected "absent" offline case. The helper raises loudly; we log
        # and fall back rather than silently narrowing the pool ~152 -> 24.
        _logger.warning(
            "universe_export_unreadable",
            path=str(_UNIVERSE_EXPORT_DIR),
            error=str(err),
            open_question="Q23",
        )
        tickers = ()
    if tickers:
        return tuple(tickers)
    _logger.info("universe_fallback_hardcoded", n_tickers=len(_FALLBACK_TIER_1_2_UNDERLYINGS))
    return _FALLBACK_TIER_1_2_UNDERLYINGS


def universe_fingerprint() -> str:
    """H-3: stable 16-hex fingerprint of the resolved underlying pool (D078).

    The universe pool shadows `_pick_underlying`'s draws but isn't in
    `registry_hash`/`grammar_version`, so the day Crucible publishes
    `universe_tickers.json` (or changes it) every same-seed reproduction would
    silently diverge (hard rule #6). This folds into `mint_batch_id` +
    `batch_summaries`. `_load_underlyings()` already returns a sorted tuple, so
    the hash is order-stable.
    """
    payload = "|".join(_load_underlyings())
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


_TIER_1_ETF_UNDERLYINGS: frozenset[str] = frozenset({"SPY", "QQQ", "IWM", "DIA"})


def _pick_underlying(
    rng: random.Random,
    hypothesis: str,
    regime_indicators: tuple[str, ...] = (),
) -> str | None:
    """Per-config underlying selection from the Tier 1+2 pool.

    D078: reads from Crucible's universe export when available, falls back
    to the D033 hardcoded list. Determinism preserved via shared rng.

    D098 (v5): `relative_value` returns None — it is a pairs strategy whose
    legs Crucible's PairsConvergence resolves itself (post-commit 4f5271f it
    loads all pair legs regardless of tier, so a single anchor ticker is no
    longer needed). This reverts D079, which had assigned a concrete ticker to
    work around the OLD path's anchor requirement; the tier-loading fix removed
    that requirement, and stamping a single underlying on a pairs config is
    misleading. The rng draw is still consumed below for non-pairs hypotheses,
    keeping the per-hypothesis sampling sequence aligned.

    T1.4 (grammar v2 / D039): when the regime indicators include any
    ETF-incompatible indicator (e.g., `days_to_earnings`), the pool is
    constrained to single-names only — preserves grammar R3's ETF-aware
    compatibility constraint at sample time so the validator doesn't have
    to reject the config downstream.
    """
    if hypothesis == "relative_value":
        return None
    underlyings = _load_underlyings()
    if any(ind == "days_to_earnings" for ind in regime_indicators):
        single_names = tuple(u for u in underlyings if u not in _TIER_1_ETF_UNDERLYINGS)
        return rng.choice(single_names)
    return rng.choice(underlyings)


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
    *,
    hypothesis_weights: Mapping[str, float] | None = None,
    forced_hypothesis: str | None = None,
) -> StrategyConfig:
    """Construct one grammar-valid ``StrategyConfig`` using ``rng`` for every choice.

    Raises ``SamplerError`` only when the registry is so sparse that no
    grammar-valid config can be built (empty pool at some CSP step).

    ``hypothesis_weights`` biases the hypothesis pick toward those with
    higher posterior promotion rates (long-term #1). When None, falls
    back to uniform `rng.choice`. Hypotheses missing from the map get
    the prior-mean weight so they remain explorable.

    ``forced_hypothesis`` (D037) overrides the weighted pick when set —
    use it from the iterator to enforce a per-hypothesis stratified
    floor and prevent the failure-bias sampler from collapsing onto a
    single hypothesis. Raises ``SamplerError`` if the forced hypothesis
    is not in the samplable pool (i.e., has empty directional or regime
    pools under the current registry).
    """
    by_id: dict[str, IndicatorMetadata] = {ind.id: ind for ind in registry.indicators}

    # D066/D098: exclude non-enumerable hypotheses — overlay-only tail_hedge
    # (Crucible's runner RunnerErrors it at dispatch) + disabled-by-policy
    # regime_arbitrage (low-yield by construction). See
    # `NON_ENUMERABLE_HYPOTHESES` in search_space.py for rationale.
    samplable_hypotheses = tuple(
        h
        for h in space.hypotheses
        if h not in NON_ENUMERABLE_HYPOTHESES
        and space.directional_indicators_by_hypothesis[h]
        and space.regime_indicators_by_hypothesis[h]
    )
    if not samplable_hypotheses:
        msg = "no hypothesis has non-empty directional + regime pools"
        raise SamplerError(msg)
    if not space.samplable_sizer_modes:
        msg = "no sizer mode is samplable in the current registry"
        raise SamplerError(msg)

    if forced_hypothesis is not None:
        if forced_hypothesis not in samplable_hypotheses:
            msg = (
                f"forced_hypothesis={forced_hypothesis!r} not in samplable pool "
                f"{list(samplable_hypotheses)} — empty directional or regime pool"
            )
            raise SamplerError(msg)
        hypothesis = forced_hypothesis
    elif hypothesis_weights:
        weights = [
            hypothesis_weights.get(h, _HYPOTHESIS_WEIGHT_PRIOR_MEAN) for h in samplable_hypotheses
        ]
        hypothesis = rng.choices(samplable_hypotheses, weights=weights, k=1)[0]
    else:
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
    directional_id, regime_id = _pick_directional_regime_pair(
        space,
        by_id,
        hypothesis,
        bucket,
        rng,
        chain_id=chain_id,
    )

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
    # Belt-and-suspenders: a `type='threshold'` signal with no `threshold`
    # key in params bypasses Crucible's predicate (`lambda _v: False`) and
    # silently gate-rejects on min_oos_trade_count. The `_viable_buckets`
    # + `_pick_directional_regime_pair` filters call `is_threshold_skippable`
    # to exclude indicators without audited threshold ranges; this assert
    # catches any future regression where an indicator slips through.
    for sig in signals:
        if sig.type == "threshold" and "threshold" not in sig.params:
            msg = (
                f"empty-threshold leak: signal id={sig.id} "
                f"indicators={sig.indicators} type=threshold but params "
                f"missing 'threshold' key — add the indicator to "
                "_INDICATOR_THRESHOLD_TABLE or mark it is_skip=True"
            )
            raise SamplerError(msg)
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
        # D033 — per-config underlying from Tier 1+2 pool.
        # D079 — relative_value now also gets a real ticker (was None → 99%
        # zero-trade because pairs_convergence needs a concrete primary).
        # T1.4: pass regime indicator IDs so the picker can constrain to
        # single-names when the regime contains an ETF-incompatible
        # indicator (e.g., days_to_earnings — sentinel 999 on ETFs).
        underlying=_pick_underlying(
            rng,
            hypothesis,
            regime_indicators=tuple(
                ind for sig in signals if sig.role == "regime_filter" for ind in sig.indicators
            ),
        ),
        tier=2,
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
            and not is_threshold_skippable(i, "directional")
        ]
        chain_family = by_id[chain_id].family if chain_id is not None else None
        compat_regimes = [
            i
            for i in regime_pool
            if i in by_id
            and _lookback_class(by_id[i].lookback) in allowed_cls
            and not is_threshold_skippable(i, "regime_filter")
            and (chain_family is None or by_id[i].family != chain_family)
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
    *,
    chain_id: str | None = None,
) -> tuple[str, str]:
    """Pick a (directional, regime) pair satisfying §3.5 S4 + C1 + C4 for
    the given bucket. Precondition: ``bucket`` is in ``_viable_buckets``,
    so at least one valid pair exists. The pick is rng-driven; if the
    rng-chosen directional has no compatible regime, fall back to the
    first valid pair by canonical id order (still deterministic).

    D077: when a sizer-required chain indicator is present, regime
    indicators whose family matches the chain's family are excluded to
    prevent C1 violations (e.g., rv_rank + realized_vol both volatility).
    """
    allowed_cls = _LOOKBACK_CLASSES_FOR_BUCKET[bucket]
    chain_family = by_id[chain_id].family if chain_id is not None else None
    compat_directionals = tuple(
        i
        for i in space.directional_indicators_by_hypothesis[hypothesis]
        if i in by_id
        and _lookback_class(by_id[i].lookback) in allowed_cls
        and not is_threshold_skippable(i, "directional")
    )
    compat_regimes = tuple(
        i
        for i in space.regime_indicators_by_hypothesis[hypothesis]
        if i in by_id
        and _lookback_class(by_id[i].lookback) in allowed_cls
        and not is_threshold_skippable(i, "regime_filter")
        and (chain_family is None or by_id[i].family != chain_family)
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
    """§3.5 P2 entry-side DTE + §3.5 P3 delta band.

    D074 (Phase 5): pre-D074 dte_min and dte_max were pinned to the §3.5
    P2 window's exact bounds (e.g., swing_short always emitted dte_min=14
    and dte_max=21). Now `dte_min` is sampled uniformly from the low half
    of the window and `dte_max` from the high half, guaranteeing
    `dte_min < dte_max` by construction (disjoint halves around the
    midpoint). This widens the option-selection space and produces
    distinct fingerprints (D069) for what were previously identical
    selector configs.

    Hard rule check: the §3.5 P2 validator only requires
    `window_low <= dte_min AND dte_max <= window_high`; sampling within
    the window stays valid by construction.
    """
    dte_low, dte_high = space.dte_entry_window_by_bucket[bucket]
    delta_low, delta_high = space.delta_band_by_bucket[bucket]
    mid = (dte_low + dte_high) // 2
    return SelectorSpec(
        delta_target=round(rng.uniform(delta_low, delta_high), 3),
        delta_tolerance=defaults.DELTA_TOLERANCE,
        dte_min=rng.randint(dte_low, mid),
        dte_max=rng.randint(mid + 1, dte_high),
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
    """§3.5 P4 ``per_trade_risk_pct`` sampling; D074 (Phase 5) adds
    mode-specific knob sampling for `fractional_kelly` and `vol_target`.

    Pre-D074, `kelly_fraction` and `vol_target_annual` were hardcoded to
    their defaults (0.25 and 0.20 respectively), so every fractional_kelly
    config used identical Kelly sizing and every vol_target config used
    identical vol targeting. D074 samples both within ranges:

      - `fractional_kelly`: kelly_fraction in [0.10, 0.50] (quarter to
        half Kelly typical). Conservative half-Kelly (0.50) at the upper
        end; quarter-Kelly (0.25) is the legacy default; 0.10 captures
        "fractional Kelly with strong conservatism."
      - `vol_target`: vol_target_annual in [0.10, 0.30] (10-30%
        annualized target). 20% is the legacy default; the range covers
        risk-on / risk-off variants without changing the sizer math.

    `fixed_risk_pct` mode keeps both at defaults (the mode doesn't read
    them).

    The grammar doesn't constrain these knobs; they're sampler-side
    variation. Hard rule #6 (determinism) preserved — rng-driven from
    the SeedHierarchy.
    """
    risk_low, risk_high = space.risk_pct_range
    kelly_fraction: float = defaults.KELLY_FRACTION
    vol_target_annual: float = defaults.VOL_TARGET_ANNUAL
    if mode == "fractional_kelly":
        kelly_fraction = round(rng.uniform(0.10, 0.50), 3)
    elif mode == "vol_target":
        vol_target_annual = round(rng.uniform(0.10, 0.30), 3)
    return SizerSpec(
        mode=mode,  # type: ignore[arg-type]
        per_trade_risk_pct=round(rng.uniform(risk_low, risk_high), 4),
        kelly_fraction=kelly_fraction,
        vol_target_annual=vol_target_annual,
    )


def _build_exits(
    space: SearchSpace,
    hypothesis: str,
    rng: random.Random,
) -> tuple[ExitSpec, ...]:
    """§3.5 E1 mandatory + §3.5 S5 multi-exit composition (D071).

    v3 schema:
      - E1 mandatory exits (always included).
      - `required_always` per hypothesis (always included).
      - Exactly one from `required_from_set` (rng pick), if non-empty.
      - 0..K_MAX_OPTIONAL from `optional_additions` (each picked with p=0.5,
        truncated to K).

    Forbidden exits per S5 are simply omitted; no need to materialize the
    forbidden set. §3.5 E3 demands ``activate_after_gain_pct ≥ 0.30`` on
    any ``trailing_atr`` exit; `_exit_params` sets it here so trend
    configs are valid by construction.

    Determinism: every rng-driven decision (required-from-set pick,
    optional-additions Bernoulli) follows the seed hierarchy. Same
    (grammar_version, registry_hash, seed) produces byte-identical exits.
    """
    # D071 / Phase 4 — K_MAX_OPTIONAL is the cap on optional_additions
    # picked per config. Mirrors `K_MAX_OPTIONAL` in
    # `forge.grammar.custom_predicates`. Kept local to avoid an
    # enumeration→grammar import chain.
    _K_MAX_OPTIONAL = 2

    ids: list[str] = list(space.e1_mandatory)
    ids.extend(space.s5_required_always_by_hypothesis[hypothesis])
    required_set = space.s5_required_from_set_by_hypothesis[hypothesis]
    if required_set:
        ids.append(rng.choice(required_set))
    optional_pool = space.s5_optional_additions_by_hypothesis[hypothesis]
    # Each optional independently picked with p=0.5, then truncated to K.
    picked_optional = [opt for opt in optional_pool if rng.random() < 0.5]
    ids.extend(picked_optional[:_K_MAX_OPTIONAL])
    # Preserve order, deduplicate (E1 / required_always / optional may overlap).
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

    D068: Crucible's `pairs_convergence` template reads its CSP-style
    entry rule (pvalue / |zscore| / halflife window / lookback) from
    `signals[0].params`, NOT the generic threshold/op that drives
    activation detection. Pre-D068, every `relative_value` config ran
    with template defaults (pval<0.05, |z|>2.0, hl ∈ (5,30)) — diagnostic
    across 62 sessions x 15 pairs showed only 0.3% (3 of 930) entry-
    eligible (1,154 / 4,039 = 28.6% of submissions, all 0 trades).
    Populating these knobs widens entry eligibility to 4-9% in sweeps,
    restoring usable variation. See IMPLEMENTATION_DECISIONS.md D068.
    """
    params = sample_threshold_params(indicator_id, "directional", rng)
    if indicator_id == "pairs_zscore":
        params.update(_sample_pairs_template_params(rng))
    return params


def _sample_pairs_template_params(rng: random.Random) -> dict[str, object]:
    """D068 + D072 — extra keys for Crucible's pairs_convergence template.

    The template reads these via `signals[0].params.get(key, default)`;
    populating them lets the sampler vary the pairs strategy's entry
    rule across submissions.

    **D068 (2026-05-19)** shipped initial ranges that bridged template
    defaults to the "widened-aggressive" end of the sensitivity sweep
    (pvalue 0.05-0.20, zscore 0.8-2.0). Even at the aggressive end the
    diagnostic showed ~9% (asof, pair) eligibility — but the gauntlet
    cohort revealed `relative_value` configs are still **97.5% zero-
    trade** (309 / 317 in the 1,000-cohort, with ZERO configs in the
    10+ trade bucket). The wider end of D068's range still isn't fully
    sampled because uniform random splits midpoint-centered.

    **D072 (2026-05-19)** shifts the ranges toward the more permissive
    end while preserving the conservative tail:
      - `pvalue_max` 0.05-0.20 → **0.10-0.25** (the diagnostic's
        widened-aggressive setting was pval<0.20; pushing to 0.25
        admits weaker cointegration evidence).
      - `zscore_entry` 0.8-2.0 → **0.5-1.5** (template default 2.0 was
        too strict; median |z| among pvalue-passers in the diagnostic
        was 1.06, so 0.5-1.5 puts most picks BELOW that median).
      - `halflife_min` (2, 3, 5, 8) → **(1, 2, 3, 5)** (allow faster
        mean-reverters; median observed halflife was 3.32).
      - `halflife_max` (15, 30, 45, 60) → **(20, 45, 60, 90)** (allow
        slower mean-reverters; many pairs have longer halflives that
        the prior cap excluded).
      - `lookback` (126, 189, 252, 378, 504) → **(126, 189, 252, 378)**
        (drop the 504 option; longer lookback means fewer recompute
        windows in a 90-day backtest, lower effective signal turnover).

    `halflife_min` (1..5) and `halflife_max` (20..90) remain disjoint
    so `halflife_min < halflife_max` holds by construction.

    Hard rule #3 check (never lower Crucible's gate): unaffected.
    Crucible's gauntlet (Sharpe, profit_factor, etc.) is the same;
    we're just letting Forge submit configs that more often produce
    SOMETHING for the gauntlet to evaluate.
    """
    return {
        "lookback": rng.choice((126, 189, 252, 378)),
        "pvalue_max": round(rng.uniform(0.10, 0.25), 3),
        "zscore_entry": round(rng.uniform(0.5, 1.5), 3),
        "halflife_min": rng.choice((1, 2, 3, 5)),
        "halflife_max": rng.choice((20, 45, 60, 90)),
    }


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
    params = sample_threshold_params(regime_id, "regime_filter", rng)
    if regime_id == "rv_rank":
        params.update(_sample_rv_rank_params(rng))
    return params


def _sample_rv_rank_params(rng: random.Random) -> dict[str, object]:
    """D077 — Crucible rv_rank indicator params.

    Crucible defaults: rv_window=21, window=252. Sampling range per
    the PTS calibration handoff (PROMPT_FORGE_RV_RANK_WIRING.md).
    """
    return {
        "rv_window": rng.choice((10, 21)),
        "window": rng.choice((126, 252)),
    }


def _exit_params(exit_id: str, rng: random.Random) -> dict[str, object]:
    """E3: ``trailing_atr`` requires ``activate_after_gain_pct ≥ 0.30``."""
    if exit_id == "trailing_atr":
        return {"activate_after_gain_pct": round(rng.uniform(0.30, 0.50), 2)}
    return {}
