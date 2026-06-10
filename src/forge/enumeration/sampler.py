"""Stratified hypothesis-first sampler for grammar-valid ``StrategyConfig``.

§4.2's CSP-style algorithm with the D7 amendment (sizer mode picked second so
§3.5 X1/X2 indicator chaining can complete) and the v8 / D102 reorder
(directional picked BEFORE the DTE bucket, so the bucket can be DERIVED from
the directional signal's horizon instead of sampled blind):

1. Pick hypothesis (only those with non-empty directional + regime pools).
2. Pick sizer mode (only those in ``samplable_sizer_modes``).
3. Pick the directional indicator (§3.5 C2 pool) that has a §3.5-S4-permitted
   DTE bucket (chain-compat aware) AND a C1/C4/R-valid regime partner.
4. Derive the DTE bucket from the directional's signal horizon (v8 / D102):
   ``DTE_target = k * horizon`` for mean_reversion / trend_continuation, an
   event-bracket window for volatility_event, snapped to the nearest
   §3.5-S4-permitted bucket; relative_value picks uniformly (its per-trade DTE
   is a Crucible runtime choice off the live spread half-life).
5. Pick the regime indicator from the §3.5 R-rule pool, C4-disjoint in id,
   C1-disjoint in family from directional. §3.5 S4 gates the directional
   horizon only, so the regime no longer constrains the bucket.
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
from forge.enumeration.search_space import (
    NON_ENUMERABLE_HYPOTHESES,
    RANK_COMBINER_HYPOTHESES,
)
from forge.enumeration.underlying_class import underlying_class
from forge.grammar.signal_horizon import (
    buckets_for_horizon_class,
    horizon_class,
    nearest_bucket,
    signal_horizon_days,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from crucible_contracts import IndicatorMetadata, RegistrySnapshot

    from forge.enumeration.search_space import SearchSpace

_logger = structlog.get_logger(__name__)


# Fallback for hypotheses absent from the rejection-weights map. Production
# never hits it: the CLI fills every samplable hypothesis (D105 —
# `compute_hypothesis_component_weights` returns a complete, max-normalized
# map, so a missing key only occurs in direct sampler calls with partial
# maps). On that normalized scale 1/11 reads as ~9% of the best class — the
# same explore share the old Beta(1,10) prior-mean fallback gave. Kept local
# to avoid a circular import between enumeration and feedback.
_HYPOTHESIS_WEIGHT_PRIOR_MEAN: float = 1.0 / 11.0

# D103 (v9) — dynamic relative_value regime-gate weighting. The sampler tilts the
# regime pick toward gates that `forge.feedback.rejection_weights` has learned
# yield accepted relative_value components. Kept local to avoid an
# enumeration→feedback import cycle. Scoped to relative_value (the one
# hypothesis with no §3.5 R-rule, so its regime pool is the whole registry);
# every other hypothesis keeps its uniform `rng.choice` pick.
#
# D105 rescale: the weights are now RAW component-rate posteriors
# (rejection_weights COMPONENT_ALPHA/BETA — Beta(1,50), prior mean 1/51 ≈ 0.02,
# typical learned-good gate ~0.04), so the prior fallback and exploration floor
# sit on that scale: an unseen gate samples at ~half a good gate's weight, and
# a learned-bad gate keeps ~a quarter of a good gate's draw probability
# (~2% per gate across the ~34-gate registry pool — the same per-gate
# exploration share the D067-scale constants produced under the old estimand).
_REGIME_WEIGHT_PRIOR_MEAN: float = 1.0 / 51.0
_REGIME_EXPLORATION_FLOOR: float = 0.01
_REGIME_CURATED_HYPOTHESIS: str = "relative_value"

# D105 — hypothesis x dte_bucket weighting. Same component-rate scale and
# prior/floor rationale as the regime constants above: an unseen cell samples
# at ~half a learned-good cell's weight, a learned-bad cell keeps ~a quarter of
# a good cell's draw probability. Consumed by the joint (directional, bucket)
# draw in `_select_bucket_directional_regime` — the bucket is DERIVED from the
# directional's horizon (D102), and for most indicators every k lands in one
# bucket, so steering the bucket mix necessarily steers the directional pick.
_BUCKET_WEIGHT_PRIOR_MEAN: float = 1.0 / 51.0
_BUCKET_EXPLORATION_FLOOR: float = 0.01

# D105 — underlying-class weighting, same component-rate scale and rationale.
# Per-ticker weight = its class's learned weight, so the high-idio-vol class
# (the minting cohort: AAPL/NVDA/TSLA at 12.8-27.9% yield) outdraws the
# diversified ETF/index class (0 components / ~390 decided), while the floor
# keeps diversified evidence flowing to revise the zero.
_UNDERLYING_CLASS_PRIOR_MEAN: float = 1.0 / 51.0
_UNDERLYING_CLASS_EXPLORATION_FLOOR: float = 0.01


class SamplerError(Exception):
    """Raised when the sampler cannot construct a config from the current
    grammar + registry slice (empty pool at some CSP step)."""


# v8 (D102) — horizon-matched DTE. The directional signal's Forge-owned signal
# horizon (forge.grammar.signal_horizon) drives the DTE bucket: DTE_target =
# k * horizon, snapped to the nearest §3.5-S4-permitted bucket. `k` is the
# exploration knob the grammar now varies instead of raw DTE — it spans "just
# enough time for the thesis" (2x) to "generous" (4x). Per the Crucible
# horizon-matched-DTE handoff (2026-06-04).
_K_MULTIPLIERS: tuple[int, ...] = (2, 3, 4)

# Hypotheses whose DTE is k*horizon off the DIRECTIONAL oscillator/trend period.
# H2 (v12 / D109): event_momentum joins — DTE = k * the sue drift window
# (horizon 10 td) → {20,30,40} td → swing_short/swing_mid, enough DTE to ride the
# 5-20 td post-earnings drift without forcing a blind uniform bucket pick.
_HORIZON_MATCHED_HYPOTHESES: frozenset[str] = frozenset(
    {"mean_reversion", "trend_continuation", "event_momentum"}
)

# volatility_event brackets the event instead: DTE_target = (entry lead before
# the event) + (post-event realization window). Events don't want a k multiple
# of an oscillator period — they want enough DTE to reach the event and capture
# the move. Lead is the exploration knob; the window is fixed at the midpoint of
# the handoff's 10-15 td. Targets {17, 22, 32} -> swing_short / swing_short /
# swing_mid, matching the handoff's "brackets the event -> swing_short/mid".
_VOL_EVENT_LEAD_DAYS: tuple[int, ...] = (5, 10, 20)
_VOL_EVENT_POST_WINDOW_TD: int = 12

# H1 (v12 / D109) — cross_sectional_rank combiner option (the breadth lever).
# rank_k = how many top-ranked names to trade per rebalance; trade count ≈
# rank_k * rebalances (x2 for long_short), deterministic and ≫ the 100-trade
# floor. These are the enumerated knobs; the gate on whether to draw a rank
# combiner at all is the per-hypothesis `rank_combiner_share` (None/empty → never,
# byte-identical cold path, hard rule #6).
_RANK_K_CHOICES: tuple[int, ...] = (5, 10, 20)
_RANK_REBALANCE_CHOICES: tuple[str, ...] = ("weekly", "monthly")
_RANK_DIRECTION_MODES: tuple[str, ...] = ("long_only", "long_short")

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

# Earnings-calendar regime indicators return a sentinel on ETF underlyings (no
# earnings), so the gate never fires → 0 trades. A config gating on either the
# forward (days_to_earnings; R3 / T1.4) or the backward (days_since_earnings;
# H2 / event_momentum) countdown must therefore be single-name. T1.4 added the
# forward one to the exclusion; v12 adds the backward twin so event_momentum is
# single-name by construction (only event_momentum draws days_since_earnings, so
# this leaves every pre-v12 hypothesis's underlying draw byte-identical — #6).
_EARNINGS_CALENDAR_ETF_INCOMPATIBLE: frozenset[str] = frozenset(
    {"days_to_earnings", "days_since_earnings"}
)


def _pick_underlying(
    rng: random.Random,
    hypothesis: str,
    regime_indicators: tuple[str, ...] = (),
    underlying_class_weights: Mapping[str, float] | None = None,
    underlying_name_weights: Mapping[str, float] | None = None,
    factor_cell_discounts: Mapping[str, float] | None = None,
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

    D105: ``underlying_class_weights`` tilts the draw by each ticker's learned
    class (`forge.enumeration.underlying_class`) — the pool itself never
    changes, only the draw probability, and the T1.4 exclusion applies before
    weighting. None/empty keeps the uniform `rng.choice` byte-identical.

    D106: ``underlying_name_weights`` (per-name posteriors anchored on the
    class — `compute_underlying_name_weights`) take precedence per ticker;
    names the feedback hasn't observed fall through to their class weight,
    then the prior. The chain keeps every ticker on one coherent
    component-rate scale, so AAPL-grade evidence concentrates draws without
    starving the unobserved remainder of its class.

    H4 (orthogonal-yield): ``factor_cell_discounts`` is the
    (hypothesis, directional)-sliced ``{underlying-name: discount}`` map for
    THIS config's chosen hypothesis+directional (sample_config does the slice).
    Each ticker's weight is multiplied by its own marginal-value discount
    (over-mined names < 1.0; absent → 1.0) BEFORE the exploration floor, so the
    floor still guarantees every ticker a minimum draw and a crowded name stays
    explorable — the discount spreads an over-mined name (AAPL) across its
    minting peers (NVDA/AMD) rather than toward the non-minting diversified
    class. None/empty keeps the D105/D106 (and pre-D105) draw byte-identical
    (hard rule #6 — multiply by exactly 1.0).
    """
    if hypothesis == "relative_value":
        return None
    underlyings = _load_underlyings()
    if any(ind in _EARNINGS_CALENDAR_ETF_INCOMPATIBLE for ind in regime_indicators):
        pool = tuple(u for u in underlyings if u not in _TIER_1_ETF_UNDERLYINGS)
    else:
        pool = underlyings
    if underlying_class_weights or underlying_name_weights or factor_cell_discounts:
        names = underlying_name_weights or {}
        classes = underlying_class_weights or {}
        discounts = factor_cell_discounts or {}

        def _ticker_weight(ticker: str) -> float:
            weight = names.get(ticker)
            if weight is None:
                weight = classes.get(underlying_class(ticker), _UNDERLYING_CLASS_PRIOR_MEAN)
            weight *= discounts.get(ticker, 1.0)
            return max(weight, _UNDERLYING_CLASS_EXPLORATION_FLOOR)

        return rng.choices(pool, weights=[_ticker_weight(u) for u in pool], k=1)[0]
    return rng.choice(pool)


def _uses_single_name_only_indicator(
    signals: list[SignalSpec],
    rank_excluded_ids: frozenset[str],
) -> bool:
    """D112 (v13) → D125 (v16): True when a drawn signal makes the config
    single-name-only — it never takes the cross_sectional_rank branch.

    v16 keys the check on the registry's contracts-1.18.0 flags
    (`SearchSpace.rank_excluded_ids` = the dealer family + every
    `NOT rank_per_name_coherent AND NOT market_wide_by_design` id — Crucible's
    fail-closed ClassVar truth about per-name fan-out), retiring the v13-v15
    explicit id sets. ANY role counts, confluence included: D122 corrected the
    v15 premise — EV-as-sizing has no live wiring anywhere, and on the rank
    path a confluence signal is a rank-score factor, where a decoupled
    indicator is output-neutral warm and a cold-cohort FREEZE (uniform NaN →
    empty scores → rebalance no-ops) cold. The X2 kelly EV chain therefore
    pins its config single-name; kelly emission itself is untouched."""
    return any(ind in rank_excluded_ids for sig in signals for ind in sig.indicators)


def sample_config(
    space: SearchSpace,
    registry: RegistrySnapshot,
    rng: random.Random,
    *,
    hypothesis_weights: Mapping[str, float] | None = None,
    regime_weights: Mapping[str, float] | None = None,
    bucket_weights: Mapping[tuple[str, str], float] | None = None,
    directional_bucket_weights: Mapping[tuple[str, str, str], float] | None = None,
    underlying_class_weights: Mapping[str, float] | None = None,
    underlying_name_weights: Mapping[str, float] | None = None,
    orthogonal_yield_discounts: Mapping[tuple[str, str, str], float] | None = None,
    rank_combiner_share: Mapping[str, float] | None = None,
    forced_hypothesis: str | None = None,
) -> StrategyConfig:
    """Construct one grammar-valid ``StrategyConfig`` using ``rng`` for every choice.

    Raises ``SamplerError`` only when the registry is so sparse that no
    grammar-valid config can be built (empty pool at some CSP step).

    ``hypothesis_weights`` biases the hypothesis pick toward those with
    higher posterior promotion rates (long-term #1). When None, falls
    back to uniform `rng.choice`. Hypotheses missing from the map get
    the prior-mean weight so they remain explorable.

    ``regime_weights`` (D103) biases the relative_value regime-gate pick
    toward indicators that feedback has learned yield accepted
    components. Applied ONLY to relative_value (the one hypothesis with no
    §3.5 R-rule); every other hypothesis keeps its uniform pick. When None /
    empty, relative_value also falls back to uniform — so the pre-D103
    sequence is preserved at cold-start and for all other hypotheses.

    ``bucket_weights`` (D105) biases the joint (directional, DTE-bucket) pick
    toward ``(hypothesis, dte_bucket)`` cells that feedback has learned yield
    accepted components. When None / empty, the pre-D105 two-step draw
    (uniform directional → k/lead-derived bucket) is preserved byte-identically
    (hard rule #6: weights are an additional input).

    ``underlying_class_weights`` (D105) biases the underlying pick by each
    ticker's learned class (high-idio-vol vs diversified ETF/index). None /
    empty keeps the uniform pick byte-identical.

    ``directional_bucket_weights`` (D106) refines the joint pick with
    ``(hypothesis, directional, dte_bucket)`` cells, falling back to the
    ``bucket_weights`` pair cell per option (the triple is pair-anchored, so
    the chain is scale-coherent). ``underlying_name_weights`` (D106) refines
    the underlying pick per ticker, falling back to the class weight. Both
    None/empty preserve the respective D105 (and, transitively, pre-D105)
    behaviour byte-identically.

    ``orthogonal_yield_discounts`` (H4) is the
    ``(hypothesis, directional, underlying-name)`` marginal-value discount map.
    It is sliced here by the chosen ``(hypothesis, directional)`` to a
    ``{underlying-name: discount}`` map and forwarded to the underlying pick,
    which multiplies each ticker's weight by its own discount (over-mined names
    < 1.0). None/empty preserves the draw byte-identically (hard rule #6).

    ``rank_combiner_share`` (H1, v12) is the per-hypothesis probability of
    emitting a ``cross_sectional_rank`` combiner (the breadth lever) instead of
    the default confluence — applied ONLY to the breadth-starved directional
    archetypes in ``RANK_COMBINER_HYPOTHESES``. On a rank draw the combiner
    carries ``rank_k`` / ``rebalance_frequency`` / ``direction_mode`` and the
    underlying is set to None (the runner ranks ``universe.tickers``). None/empty
    — and any hypothesis not in the map or mapped to 0.0 — draws NO rng and keeps
    the confluence path byte-identical (hard rule #6); the draw is the LAST
    decision so it never perturbs the signal/selector/sizer/exit/underlying
    sequence of a same-seed config.

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

    # v8 (D102): horizon-matched DTE. Pick the directional first, derive the
    # DTE target from its signal horizon (k*horizon, or the event-bracket for
    # volatility_event), and snap to the nearest §3.5-S4-permitted bucket. The
    # regime is then chosen by C1/C4/R-rules only — its horizon no longer gates
    # the bucket (that was the degenerate-registry artifact v8 removes; the S4
    # validator only ever checked the directional signal).
    bucket, directional_id, regime_id = _select_bucket_directional_regime(
        space,
        by_id,
        hypothesis,
        chain_id,
        rng,
        regime_weights=regime_weights,
        bucket_weights=bucket_weights,
        directional_bucket_weights=directional_bucket_weights,
    )

    # H4: slice the (hypothesis, directional, name) discount map down to this
    # config's chosen (hypothesis, directional) — the factor cell is only fully
    # determined once the underlying (the name) is drawn below, so the discount
    # can only attach to the underlying pick, conditioned on the already-chosen
    # hypothesis + directional. None/empty → no slice → no-op.
    factor_cell_discounts: dict[str, float] | None = None
    if orthogonal_yield_discounts:
        factor_cell_discounts = {
            name: disc
            for (h, d, name), disc in orthogonal_yield_discounts.items()
            if h == hypothesis and d == directional_id
        }

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
    # silently gate-rejects on min_oos_trade_count. The `_directional_candidates`
    # + `_compatible_regimes` filters call `is_threshold_skippable` to exclude
    # indicators without audited threshold ranges; this assert catches any
    # future regression where an indicator slips through.
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

    selector = _build_selector(space, hypothesis, bucket, rng)
    sizer = _build_sizer(space, mode, rng)
    exits = _build_exits(space, hypothesis, rng)

    config_name = f"forge_{hypothesis}_{bucket}_{rng.getrandbits(32):08x}"

    # D033 — per-config underlying from Tier 1+2 pool.
    # D098 — relative_value returns None (pairs strategy; Crucible loads the legs).
    # T1.4: pass regime indicator IDs so the picker can constrain to single-names
    # when the regime contains an ETF-incompatible indicator (e.g.,
    # days_to_earnings / days_since_earnings — sentinel on ETFs, no earnings).
    underlying = _pick_underlying(
        rng,
        hypothesis,
        regime_indicators=tuple(
            ind for sig in signals if sig.role == "regime_filter" for ind in sig.indicators
        ),
        underlying_class_weights=underlying_class_weights,
        underlying_name_weights=underlying_name_weights,
        factor_cell_discounts=factor_cell_discounts,
    )

    # H1 (v12 / D109) — cross_sectional_rank combiner, the breadth lever. Drawn
    # LAST and gated on `rank_combiner_share` so the confluence cold path is
    # byte-identical (hard rule #6): no share for this hypothesis (or share 0.0,
    # short-circuited before rng) → no rng draw, combiner stays confluence. On a
    # rank draw the runner ranks `universe.tickers(asof, tier)` by the directional
    # score and trades top-rank_k (+ bottom for long_short) each rebalance, so the
    # underlying is None (a single name is meaningless). The directional + regime
    # signals are unchanged — the runner routes role=="regime_filter" to its gates
    # and the directional to the rank score. Routing to Crucible's composable
    # rank runner is by combiner.type on the forge_-prefixed config name.
    #
    # D112 (v13): a config that drew ANY dealer_positioning signal never takes
    # the rank branch — dealer indicators are single-name only (the dealer
    # headline x universe is Crucible's ~100x runner tail; see
    # `DEALER_POSITIONING_FAMILY`). D116 (v14) widened the skip to the
    # chain-reading ids; D118 (v15) re-keyed it on Crucible's indicator→mode
    # map; D125 (v16) keys it on the contracts-1.18.0 registry flags
    # (`space.rank_excluded_ids` — fail-closed, so new indicators auto-inherit
    # exclusion) and drops the v15 confluence exemption (D122: the X2 kelly EV
    # chain is a rank-score factor on this path, not sizing — output-neutral
    # warm, config-freezing cold — so kelly-chain draws stay single-name).
    # Consequences: mean_reversion and event_momentum never rank (their pools/
    # signal sets are flag-excluded) until Crucible flips
    # `rank_per_name_coherent`; trend_continuation (bar-only gates) keeps the
    # rank arm, minus its kelly-chain draws. The skip consumes no rng, so
    # unaffected draw sequences are unchanged; the skipped config keeps its
    # signals and pinned underlying — full single-name sampling weight.
    combiner = CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1)
    if rank_combiner_share and hypothesis in RANK_COMBINER_HYPOTHESES:
        share = rank_combiner_share.get(hypothesis, 0.0)
        if (
            share > 0.0
            and not _uses_single_name_only_indicator(signals, space.rank_excluded_ids)
            and rng.random() < share
        ):
            combiner = CombinerSpec(
                type="cross_sectional_rank",
                rank_k=rng.choice(_RANK_K_CHOICES),
                rebalance_frequency=rng.choice(_RANK_REBALANCE_CHOICES),  # type: ignore[arg-type]
                direction_mode=rng.choice(_RANK_DIRECTION_MODES),  # type: ignore[arg-type]
            )
            underlying = None

    return StrategyConfig(
        name=config_name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket=bucket,  # type: ignore[arg-type]
        underlying=underlying,
        tier=2,
        signals=tuple(signals),
        combiner=combiner,
        selector=selector,
        sizer=sizer,
        exits=exits,
        equity_hedge_metadata=None,  # D5: Forge submits pure options
    )


def _chain_compatible_buckets(
    space: SearchSpace,
    chain_id: str | None,
) -> tuple[str, ...]:
    """DTE buckets compatible with the X1/X2 chain indicator's §3.5 S4 horizon
    class (all buckets when the sizer mode requires no chained indicator)."""
    if chain_id is None:
        return space.dte_buckets
    return buckets_for_horizon_class(horizon_class(chain_id))


def _compatible_regimes(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    directional_id: str,
    chain_family: str | None,
) -> tuple[str, ...]:
    """Regime indicators that pair with ``directional_id`` under §3.5 C1
    (different family), C4 (different id) and the R-rules, are threshold-able,
    and (D077) don't share the X1/X2 chain indicator's family.

    v8 (D102): NO horizon constraint vs the bucket. §3.5 S4 governs the
    *directional* signal's horizon only (as the validator always has), so the
    regime gate is free to pair with any bucket. Dropping the constraint also
    undoes the degenerate-registry artifact (every lookback 0) that forced
    trend regimes onto rv_rank — adx/hurst can now gate swing_mid/long."""
    directional_family = by_id[directional_id].family
    return tuple(
        i
        for i in space.regime_indicators_by_hypothesis[hypothesis]
        if i in by_id
        and i != directional_id
        and by_id[i].family != directional_family
        and not is_threshold_skippable(i, "regime_filter")
        and (chain_family is None or by_id[i].family != chain_family)
    )


def _directional_candidates(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    chain_compat_buckets: tuple[str, ...],
    chain_family: str | None,
) -> tuple[str, ...]:
    """Directional indicators that can anchor a config for this hypothesis:
    threshold-able, in the registry, with at least one §3.5-S4-permitted DTE
    bucket (after chain-compat) AND at least one compatible regime partner.
    Canonical (sorted) order is preserved from the search space for #6."""
    chain_compat = set(chain_compat_buckets)
    return tuple(
        d
        for d in space.directional_indicators_by_hypothesis[hypothesis]
        if d in by_id
        and not is_threshold_skippable(d, "directional")
        and chain_compat.intersection(buckets_for_horizon_class(horizon_class(d)))
        and _compatible_regimes(space, by_id, hypothesis, d, chain_family)
    )


def _dte_target(
    hypothesis: str,
    directional_id: str,
    rng: random.Random,
) -> float | None:
    """The v8 (D102) DTE target in trading days, or ``None`` to pick uniformly.

    - mean_reversion / trend_continuation: ``k * signal_horizon(directional)``,
      k ∈ {2, 3, 4} — DTE matches the directional oscillator/trend period.
    - volatility_event: ``entry_lead + post_event_window`` — enough DTE to
      bracket the event and capture the realized move.
    - relative_value: ``None``. Its per-pair DTE is a Crucible *runtime* choice
      (k * the live spread half-life), so Forge can't fix one at generation;
      it samples a bucket uniformly among the S4-permitted set and lets Crucible
      adapt per trade. See the horizon-matched-DTE handoff (2026-06-04)."""
    if hypothesis in _HORIZON_MATCHED_HYPOTHESES:
        return float(rng.choice(_K_MULTIPLIERS) * signal_horizon_days(directional_id))
    if hypothesis == "volatility_event":
        return float(rng.choice(_VOL_EVENT_LEAD_DAYS) + _VOL_EVENT_POST_WINDOW_TD)
    return None


def _directional_bucket_options(
    hypothesis: str,
    directional_id: str,
    chain_compat_set: set[str],
) -> tuple[str, ...]:
    """The DTE buckets one directional can induce, WITH multiplicity (D105).

    Mirrors the cold-path derivation exactly: each k (horizon-matched
    hypotheses) or event lead (volatility_event) maps to its
    ``nearest_bucket``; relative_value lists its S4-permitted buckets directly
    (its target is a Crucible runtime concern — see `_dte_target`). Repeats are
    deliberate: a bucket reachable by 2 of 3 knob values carries 2x the
    structural mass, exactly as the cold path's uniform knob draw does, so the
    learned weight composes WITH the structural prior instead of replacing it.
    """
    allowed = tuple(
        b for b in buckets_for_horizon_class(horizon_class(directional_id)) if b in chain_compat_set
    )
    if hypothesis in _HORIZON_MATCHED_HYPOTHESES:
        horizon = signal_horizon_days(directional_id)
        return tuple(nearest_bucket(allowed, float(k * horizon)) for k in _K_MULTIPLIERS)
    if hypothesis == "volatility_event":
        return tuple(
            nearest_bucket(allowed, float(lead + _VOL_EVENT_POST_WINDOW_TD))
            for lead in _VOL_EVENT_LEAD_DAYS
        )
    return allowed


def _select_bucket_directional_regime(
    space: SearchSpace,
    by_id: dict[str, IndicatorMetadata],
    hypothesis: str,
    chain_id: str | None,
    rng: random.Random,
    *,
    regime_weights: Mapping[str, float] | None = None,
    bucket_weights: Mapping[tuple[str, str], float] | None = None,
    directional_bucket_weights: Mapping[tuple[str, str, str], float] | None = None,
) -> tuple[str, str, str]:
    """v8 (D102) horizon-matched selection. Returns ``(bucket, directional_id,
    regime_id)``.

    Draw order is fixed for determinism (#6): directional → DTE target →
    bucket → regime. The directional is picked first because the DTE bucket is
    DERIVED from its signal horizon (vs the pre-v8 bucket-first CSP). Valid by
    construction: ``_directional_candidates`` guarantees a non-empty allowed
    bucket set and a non-empty regime set, so no fallback scan is needed.

    With ``bucket_weights`` (D105) the directional + bucket are drawn JOINTLY
    over every (candidate, induced-bucket) pair, weighted by the pair's
    ``(hypothesis, bucket)`` cell. The joint draw is load-bearing: most
    directionals are bucket-locked across k (macd → all swing_mid,
    momentum_252 → all swing_long), so a k-only reweight could not move the
    bucket mix at all — the cell weight must steer WHICH directional anchors
    the config. ``directional_bucket_weights`` (D106) refines each option with
    its (hypothesis, directional, bucket) triple when learned — the triple is
    anchored on the pair cell (`compute_hypothesis_directional_bucket_weights`),
    so the triple → pair → prior fallback chain stays on one scale and a flat
    multiplication's double-counting is avoided. Cold start (None/empty for
    both) keeps the two-step draw above, byte-identical to pre-D105.
    """
    chain_compat = _chain_compatible_buckets(space, chain_id)
    chain_compat_set = set(chain_compat)
    chain_family = by_id[chain_id].family if chain_id is not None else None

    candidates = _directional_candidates(space, by_id, hypothesis, chain_compat, chain_family)
    if not candidates:
        msg = (
            f"no directional indicator has a §3.5 S4-permitted DTE bucket with a "
            f"C1/C4/R-valid regime partner for hypothesis={hypothesis} chain={chain_id}"
        )
        raise SamplerError(msg)

    if bucket_weights or directional_bucket_weights:
        triples = directional_bucket_weights or {}
        pairs = bucket_weights or {}

        def _option_weight(directional: str, bucket_name: str) -> float:
            weight = triples.get((hypothesis, directional, bucket_name))
            if weight is None:
                weight = pairs.get((hypothesis, bucket_name), _BUCKET_WEIGHT_PRIOR_MEAN)
            return max(weight, _BUCKET_EXPLORATION_FLOOR)

        options = tuple(
            (d, b)
            for d in candidates
            for b in _directional_bucket_options(hypothesis, d, chain_compat_set)
        )
        weights = [_option_weight(d, b) for d, b in options]
        directional_id, bucket = rng.choices(options, weights=weights, k=1)[0]
    else:
        directional_id = rng.choice(candidates)
        target = _dte_target(hypothesis, directional_id, rng)
        allowed = tuple(
            b
            for b in buckets_for_horizon_class(horizon_class(directional_id))
            if b in chain_compat_set
        )
        bucket = nearest_bucket(allowed, target) if target is not None else rng.choice(allowed)

    regimes = _compatible_regimes(space, by_id, hypothesis, directional_id, chain_family)
    regime_id = _pick_regime(hypothesis, regimes, rng, regime_weights)
    return bucket, directional_id, regime_id


def _pick_regime(
    hypothesis: str,
    regimes: tuple[str, ...],
    rng: random.Random,
    regime_weights: Mapping[str, float] | None,
) -> str:
    """Pick the §3.5 S3 regime gate from the compatible pool.

    For the curated hypothesis (relative_value) WITH feedback ``regime_weights``,
    draw weighted toward learned-good gates (D103) — each weight floored (D067
    analogue) so no regime is starved out of exploration, and missing gates get
    the Beta prior so unseen regimes stay explorable. Every other hypothesis —
    and the cold-start (no weights) case — draws uniform via ``rng.choice``,
    byte-identical to the pre-D103 sequence (hard rule #6: weights are an
    additional input, like ``hypothesis_weights``)."""
    if hypothesis == _REGIME_CURATED_HYPOTHESIS and regime_weights:
        weights = [
            max(regime_weights.get(r, _REGIME_WEIGHT_PRIOR_MEAN), _REGIME_EXPLORATION_FLOOR)
            for r in regimes
        ]
        return rng.choices(regimes, weights=weights, k=1)[0]
    return rng.choice(regimes)


def _build_selector(
    space: SearchSpace,
    hypothesis: str,
    bucket: str,
    rng: random.Random,
) -> SelectorSpec:
    """§3.5 P2 entry-side DTE + §3.5 P3 delta band (hypothesis-aware, D125).

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
    # D125 (v16): hypothesis-scoped P3 override (trend swing_long/mid upper
    # edges → 0.55). One rng.uniform call either way, so non-overridden draw
    # sequences are byte-identical (hard rule #6).
    delta_low, delta_high = space.delta_band_overrides_by_hypothesis.get(hypothesis, {}).get(
        bucket, space.delta_band_by_bucket[bucket]
    )
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

    **D103 (v9, 2026-06-05)** — quality-bias. D068/D072 chased FIRING
    (zero-trade was the binding constraint then). By v8 firing is solved:
    current-grammar `relative_value` fires ~77% (was 99% zero-trade on the
    pre-v5 pairs-loading-bug cohort), but the gap shifted to per-component
    Sharpe — median traded Sharpe ~-0.085, rejects fail
    `walk_forward_sharpe_median` / `cpcv_sharpe_p25`. So the ranges tighten
    back toward the higher-Sharpe region (now affordable):
      - `pvalue_max` 0.10-0.25 -> **0.02-0.12** (require stronger
        cointegration; weak cointegration = the spread doesn't converge =
        negative Sharpe). Across current gated runs pvalue_max <= 0.14 ->
        median Sharpe +0.023 vs -0.086 above.
      - `zscore_entry` 0.5-1.5 -> **1.0-2.0** (enter on a larger divergence,
        more convergence edge). zscore_entry >= 1.0 -> +0.072 vs -0.177 below.
    `lookback` / `halflife_*` unchanged. This TIGHTENS enumeration scope
    (fewer, higher-quality firings) — the converse trade of D072, made now
    that firing no longer binds.

    **D105 (v10, 2026-06-07)** — drop `lookback` 378. Crucible's yield map:
    post-rv-fix (5fd485a) the lookback > 280 band runs and trades properly
    and is **0-for-155 decided with best WF 0.19**, vs 135/135 traded <= 280
    historically and ALL 7 rv components at lookback <= 252. One choice of
    four = ~25% of rv enumeration provably wasted. Same tightening direction
    as D103 (hard rule #4: tightenings can ship); 504 was dropped by D072 on
    the same one-step-at-a-time basis.

    Hard rule #3 check (never lower Crucible's gate): unaffected.
    Crucible's gauntlet (Sharpe, profit_factor, etc.) is the same;
    we're just biasing WHICH configs Forge submits toward the region the
    gate rewards.
    """
    return {
        "lookback": rng.choice((126, 189, 252)),
        "pvalue_max": round(rng.uniform(0.02, 0.12), 3),
        "zscore_entry": round(rng.uniform(1.0, 2.0), 3),
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
    # D107 (v11 / H3): mean_reversion uses the LONG-gamma side of the flip
    # (op "<", flip below spot -> dealers long gamma -> dampening -> ranging);
    # the indicator_thresholds default op ">" is the trend / short-gamma side.
    # The regime "switch" lives here -- same gate, opposite side per hypothesis.
    if hypothesis == "mean_reversion" and regime_id == "gamma_flip_distance_pct":
        params["op"] = "<"
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
