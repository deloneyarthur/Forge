"""Registered ``custom_python`` predicate functions.

The grammar's ``custom_python`` predicate type names a function by string;
``REGISTRY`` maps that string to the actual callable. Unknown names raise
``GrammarLoadError`` at load time (enforced by the loader), so by the time
``evaluate_custom_python`` runs, the registry lookup is guaranteed to
succeed.

Why a name registry instead of ``eval``/``exec``: see D017 + CLAUDE.md
hard rule #5 (no LLM in production loop, deterministic Python only). The
grammar YAML must never resolve to arbitrary Python; it can only name
functions explicitly registered in this module.

Module structure:

- Stub predicates (``always_pass`` / ``always_fail``) for dispatch tests.
- §3.5 predicate functions, one per rule (S4, S5, C1, C2, C4, P1, P2,
  P3, E1, E2, E3, R1, R2, R3, X1, X2). Each is a pure function:
  ``(config, registry) -> PredicateResult``. Tables and thresholds are
  module-level constants — operator-readable, single source of truth.

The 21 v1 rules in ``config/grammar.yaml`` reference these by name.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from crucible_contracts import (
    MANDATORY_EXIT_IDS,
    STOP_LOSS_EXIT_IDS,
)

from forge.grammar.models import PredicateResult
from forge.grammar.signal_horizon import (
    buckets_for_horizon_class,
    horizon_class_for_days,
    signal_horizon_days,
)

if TYPE_CHECKING:
    from crucible_contracts import IndicatorMetadata, RegistrySnapshot, StrategyConfig


CustomPredicateFn = Callable[["StrategyConfig", "RegistrySnapshot"], PredicateResult]


# ---------------------------------------------------------------------------
# Module-level tables and thresholds — operator-readable single source
# ---------------------------------------------------------------------------

# §3.5 S4 horizon bucketing (D010 classes; D102 v8 input change) now lives in
# `forge.grammar.signal_horizon`: the class thresholds, the Forge-owned
# per-indicator horizon table, and the horizon-class -> allowed-DTE-bucket map.
# It replaced `IndicatorMetadata.lookback` (0 for 34/43 live indicators) as the
# S4 input so the rule stops collapsing to "everything -> swing_short".

# §3.5 S5 hypothesis → exit composition (D071 / Phase 4 multi-exit schema).
#
# Schema (grammar v3 design — code lands ahead of grammar.yaml bump):
#   required_always:   exits that MUST appear in every config of this hypothesis.
#                      (Empty for most; volatility_event keeps its 2-element AND.)
#   required_from_set: sampler picks EXACTLY ONE from this set per config.
#                      (Empty for hypotheses where the choice is already in
#                      required_always.)
#   optional_additions: 0..K_MAX_OPTIONAL exits added uniformly at random.
#   forbidden:         exits that may NOT appear under this hypothesis.
#
# Pre-D071 the schema was {"required": (...), "forbidden": (...)}; the v2
# `required` tuple is now equivalent to `required_always` (when the hypothesis
# has no exit choice) OR a one-element `required_from_set` (when there's
# implicit choice expressed by the operator's intent).
#
# New exits — chandelier_exit, parabolic_sar_exit, target_exit,
# zscore_reversion_exit — are NOT in this table yet. They'll be added when
# (a) crucible_contracts ships the contracts bump that adds them to
# KNOWN_EXIT_IDS, and (b) Forge bumps grammar.yaml v2 → v3. Until then the
# schema is "multi-exit with the existing 13 exit IDs" — structural change
# only; full diversity comes with the v3 bump.
K_MAX_OPTIONAL: int = 2

_S5_HYPOTHESIS_EXITS: dict[str, dict[str, tuple[str, ...]]] = {
    "trend_continuation": {
        "required_always": (),
        # D071-final (v3 bump): 3-way choice among trend-style exits.
        # D236 (v23, §2.7): parabolic_sar_exit DROPPED — Crucible's real-backtest
        # exit sweep found chandelier_exit beats it +0.29 CPCV-p25 AND higher WF
        # (lifts tail AND center; parabolic whipsaws where chandelier trails
        # cleanly). trailing_atr (not refuted) is kept alongside the winner.
        "required_from_set": (
            "trailing_atr",
            "chandelier_exit",
        ),
        "optional_additions": ("time_stop",),
        "forbidden": ("hard_profit_target",),
    },
    "mean_reversion": {
        "required_always": (),
        # D071-final (v3 bump): 3-way choice among MR-style exits.
        "required_from_set": (
            "time_stop",
            "target_exit",
            "zscore_reversion_exit",
        ),
        # D071-final (v3 bump): iv_crush_exit as optional for MR strategies
        # that happen to fire during high-IV regimes.
        "optional_additions": ("iv_crush_exit",),
        "forbidden": (),
    },
    "regime_arbitrage": {
        "required_always": (),
        "required_from_set": ("regime_flip_exit",),
        "optional_additions": ("time_stop",),
        "forbidden": (),
    },
    "relative_value": {
        "required_always": (),
        # D071-final (v3 bump): convergence_exit OR zscore_reversion_exit.
        # zscore_reversion_exit lets Forge tune the convergence threshold;
        # convergence_exit uses internal Crucible logic.
        "required_from_set": ("convergence_exit", "zscore_reversion_exit"),
        "optional_additions": ("time_stop",),
        "forbidden": (),
    },
    "volatility_event": {
        "required_always": ("iv_crush_exit", "event_passed_exit"),
        "required_from_set": (),  # 2-element AND already exhausted by required_always
        "optional_additions": ("time_stop",),
        "forbidden": (),
    },
    "tail_hedge": {
        # tail_hedge is filtered at the sampler via D066's OVERLAY_ONLY_HYPOTHESES;
        # schema retained for parity / future overlay-spec lift.
        "required_always": ("roll_on_schedule_exit",),
        "required_from_set": (),
        "optional_additions": (),
        # §3.5 says "profit-taking forbidden" — read narrowly as
        # `hard_profit_target` (the only profit-taking exit in
        # KNOWN_EXIT_IDS).
        "forbidden": ("hard_profit_target",),
    },
    # H2 (v12 / D109): the post-earnings drift decays over ~5-20 td, so the
    # primary exit is a drift-decay `time_stop` (required). Momentum trailing
    # (trailing_atr / chandelier_exit) optionally lets a strong drift run.
    # `hard_profit_target` is forbidden — the payoff is convex/positive-skew
    # (long optionality into the drift), exactly the profile of the vol_event
    # winners, so capping the upside is counter-thesis.
    "event_momentum": {
        "required_always": (),
        "required_from_set": ("time_stop",),
        "optional_additions": ("trailing_atr", "chandelier_exit"),
        "forbidden": ("hard_profit_target",),
    },
}

# §3.5 C2 hypothesis → allowed directional-signal families.
# regime_arbitrage allows any family.
_C2_HYPOTHESIS_FAMILIES: dict[str, tuple[str, ...] | None] = {
    # D138 (v19): `smart_money` joins trend_continuation's directional families.
    # option_momentum (Heston-Jones-Khorram-Li JF 2023) is a momentum/persistence
    # factor in option returns — a continuation thesis; horizon 126 td (long)
    # holds it at swing_long DTE. The sibling smart_money member
    # `expected_value_estimator` is pinned OUT of the directional path (its
    # directional range is nulled → is_threshold_skippable; it stays the X2
    # fractional-kelly sizer feature). Operator-pinned (the deferred GO-doc
    # item-4 family question, resolved at activation); loosening OPEN_PROPOSALS
    # + D138.
    "trend_continuation": ("trend", "smart_money"),
    # D062: dealer_positioning indicators (gex/vex/cex/walls/gamma-flip) double
    # as mean-reversion drivers. Call/put walls and the gamma-flip line are
    # well-documented MR magnets; positive-GEX regimes are dampening. Letting
    # dealer indicators serve as the directional thesis for `mean_reversion`
    # widens the enumeration into a class of strategies the operator wants
    # explored. See IMPLEMENTATION_DECISIONS.md D062.
    "mean_reversion": ("mean_reversion", "dealer_positioning"),
    "regime_arbitrage": None,
    "relative_value": ("pairs",),
    # D062: dealer-positioning exposures (GEX/VEX/CEX, gamma-flip distance)
    # are first-class vol-regime drivers. Shipped alongside Crucible commit
    # 5af63ad which adds the 6 dealer indicators. See D062.
    "volatility_event": ("iv_structure", "flow", "dealer_positioning"),
    "tail_hedge": ("macro",),
    # H2 (v12 / D109): event_momentum is a directional post-earnings-drift
    # (PEAD) thesis. Its directional is the earnings surprise itself (`sue`,
    # family `post_event_drift`); the drift's sign/magnitude is the edge. The
    # post-event TIMING gate (`days_since_earnings`) is a different family
    # (`calendar`, post-§2.1) so C1 admits both in one config.
    "event_momentum": ("post_event_drift",),
}

# §3.5 P2 entry DTE windows per bucket. (Exit DTE thresholds are tracked
# via theta_cliff_exit's params, which isn't fully pinned in §3.5; P2
# checks the entry-side window only for v1. See OPEN_QUESTIONS.md.)
_P2_ENTRY_DTE: dict[str, tuple[int, int]] = {
    "swing_short": (14, 21),
    "swing_mid": (30, 45),
    "swing_long": (60, 90),
}

# §3.5 P3 delta-target bands per bucket.
_P3_DELTA_BAND: dict[str, tuple[float, float]] = {
    "swing_short": (0.40, 0.55),
    "swing_mid": (0.30, 0.45),
    "swing_long": (0.20, 0.35),
}

# D125 (v16) — hypothesis-scoped P3 band overrides (the first; P3 was
# bucket-only before). Trend's long-options expression sat in the
# embedded-leverage drag zone (Frazzini-Pedersen RAPS 2022) and the
# within-band evidence agreed: the verdicts delta-tercile readout shows trend
# component rate rising monotonically toward the upper band edge
# (swing_long 5/8/16 — P3's own "promotion at the edges" relax clause), with
# every honest-coverage trend component in the upper two terciles, under a
# legacy zero-slippage value bias that favored LOW delta. MR and vol_event
# gradients are flat-to-inverted (components concentrate LOW), so only trend
# widens; lower edges keep the convexity rationale. Upper edge 0.55 = the
# grammar-wide cap (no Crucible position-builder change needed).
# Operator-approved loosening: OPEN_PROPOSALS 343e71fd, recorded in D125.
_P3_DELTA_BAND_OVERRIDES: dict[str, dict[str, tuple[float, float]]] = {
    "trend_continuation": {
        "swing_long": (0.20, 0.55),
        "swing_mid": (0.30, 0.55),
    },
}


def effective_delta_band(hypothesis: str, dte_bucket: str) -> tuple[float, float] | None:
    """The P3 band for (hypothesis, bucket): override when one exists, else
    the base bucket band; None for an unknown bucket."""
    override = _P3_DELTA_BAND_OVERRIDES.get(hypothesis, {}).get(dte_bucket)
    if override is not None:
        return override
    return _P3_DELTA_BAND.get(dte_bucket)


# §3.5 R2 regime-gate indicator requirements.
# D077: expanded from (adx, hurst) to include rv_rank — PTS thesis
# "enter trend-following when realized vol is cheap" (Crucible rv_rank.py).
# D107 (v11 / H3): expanded to include gamma_flip_distance_pct — the
# dealer-gamma regime switch. Trend pays in the SHORT-gamma / vol-amplifying
# regime: per indicator_thresholds, "Positive = flip above spot -> dealers
# short gamma -> vol amplifying", so the gate fires when
# gamma_flip_distance_pct > threshold (op_regime ">", which the threshold
# table already sets — no sampler change). Web-grounded (SpotGamma/SqueezeMetrics
# negative-gamma = trending) and data-grounded (trend's 0.62% component rate is
# the weakest archetype; gating it to its productive regime is the lever).
# The mean_reversion side (long-gamma / op "<") ships as the next increment.
_R2_TREND_CONTINUATION_REGIME_INDICATORS = (
    "adx",
    "hurst",
    "rv_rank",
    "gamma_flip_distance_pct",
    # D131 (v17, operator-approved rule edit — R2's own evidence_to_relax
    # clause): market_state, the Cooper/Gutierrez/Hameed up-market filter
    # (momentum pays after up-markets, inverts after down). market-wide by
    # design → also valid on trend's rank arm (uniform across names is
    # correct for a market gate).
    "market_state",
)
# T1.4 (PROMPT_5_FORGE_V1_1_REVISED, grammar v2): expanded from
# (days_to_earnings, days_to_fomc) to include macro-event indicators
# (days_to_cpi, days_to_nfp, days_to_opex) that Crucible Prompt 6 added
# in 2026-05-17. The expansion makes the vol_event hypothesis usable on
# ETFs (SPY/QQQ/IWM/DIA), which return sentinel 999 for days_to_earnings
# (no earnings on ETFs) and would silently produce zero trades pre-T1.4.
_R3_EVENT_PROXIMITY_INDICATORS = (
    "days_to_earnings",
    "days_to_fomc",
    "days_to_cpi",
    "days_to_nfp",
    "days_to_opex",
    # D135 (v18, operator-approved adoption cut — Crucible GO doc
    # 2026-06-11): pre_earnings_setup, the composed days_to_earnings x
    # rv_rank conditioner (family calendar). It IS an earnings-proximity
    # gate — the full-fidelity pre-earnings IV-run-up expression in the
    # existing 1-gate slot (D127/D129 lineage).
    "pre_earnings_setup",
)
# ETF underlyings have no earnings — `days_to_earnings` returns the
# sentinel 999 on these tickers and the gate never fires. T1.4 forbids
# the (etf-underlying, days_to_earnings-regime) combination at validation
# time to prevent silent zero-trade outcomes. D135 (v18) adds
# pre_earnings_setup: it composes days_to_earnings, so on ETFs the
# conjunction is a permanent 0.0 (never admits) — same silent-zero-trade
# class, one derivation removed.
_R3_ETF_INCOMPATIBLE_INDICATORS = frozenset({"days_to_earnings", "pre_earnings_setup"})
_R3_ETF_UNDERLYINGS = frozenset({"SPY", "QQQ", "IWM", "DIA"})

# §3.5 R1 IV-rank gate parameters.
_R1_IV_RANK_INDICATOR = "iv_rank"
_R1_IV_RANK_MAX_THRESHOLD = 50.0
# D107 (v11 / H3, MR side): the dealer-gamma regime gate is an accepted
# ALTERNATIVE to the iv_rank cheap-IV gate for mean_reversion — MR pays in the
# LONG-gamma / dampening / ranging regime (flip below spot → op_regime "<", which
# the sampler sets; the indicator_thresholds default ">" is the trend / short-gamma
# side). The "switch": same indicator, opposite side per hypothesis.
_R1_GAMMA_REGIME_INDICATOR = "gamma_flip_distance_pct"
# D150 (v20, MR side): hurst is a third accepted R1 regime gate for mean_reversion
# — the mean-reverting H<0.5 side (op_regime "<", which the sampler sets; the
# indicator_thresholds default ">" is R2's trend / persistent side). H<0.5 is the
# purest ranging signal; C4 keeps hurst single-role (it can't be both this gate and
# the directional). Same indicator, opposite side per hypothesis — the D107 pattern.
_R1_HURST_REGIME_INDICATOR = "hurst"
# D167 (v22, MR side): rv_rank (cheap REALIZED-vol percentile, op_regime "<" = LOW =
# the calm / reversion-friendly regime — its indicator_thresholds default op is
# already "<") is a fourth accepted R1 regime gate for mean_reversion. Crucible's
# causal attribution (FORGE_mr_rv_hurst_overlap_response): rv_rank is INDEPENDENT of
# (Spearman ≈ -0.036) and DOMINATES the v21 hurst gate, and is rank-coherent (works on
# MR's confluence AND rank genomes). Added per the D107/D150 widening pattern; the
# sampler biases toward it over the prefilter-sparse iv_rank.
_R1_RV_RANK_REGIME_INDICATOR = "rv_rank"

# H2 (v12 / D109): event_momentum's post-event TIMING gate. Unlike R1/R2/R3
# this is NOT a grammar.yaml rule — adding a 22nd operator-owned rule would
# touch the rule set (hard rule #1). Instead the constraint lives entirely in
# the regime-pool builder (search_space._build_regime_pool), exactly like the
# R-rule pools: event_momentum's regime pool IS this tuple, so the sampler can
# only ever draw days_since_earnings as the gate. C1/C2/C4 (which run
# generically) enforce the rest. `days_since_earnings` is the calendar-family
# countdown "N days AFTER the print" — op "<" (from the threshold table) fires
# inside the post-event drift window.
_EVENT_MOMENTUM_REGIME_INDICATORS = ("days_since_earnings",)

# §3.5 X1 / X2 sizer-mode → required indicator id.
_X1_VOL_TARGET_INDICATOR = "realized_vol"
_X2_KELLY_INDICATOR = "expected_value_estimator"


# ---------------------------------------------------------------------------
# Stubs (Phase 1 dispatch tests)
# ---------------------------------------------------------------------------


def _always_pass(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Stub: returns passed=True regardless. Tests the dispatch path."""
    del config, registry
    return PredicateResult(passed=True)


def _always_fail(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Stub: returns passed=False. Companion to ``_always_pass``."""
    del config, registry
    return PredicateResult(passed=False, detail="custom_python: always_fail stub")


# ---------------------------------------------------------------------------
# Registry-lookup helpers — used by several predicates
# ---------------------------------------------------------------------------


def _indicator_by_id(
    indicator_id: str,
    registry: RegistrySnapshot,
) -> IndicatorMetadata | None:
    """Return the registered IndicatorMetadata for ``indicator_id``, or
    ``None`` if not registered."""
    for im in registry.indicators:
        if im.id == indicator_id:
            return im
    return None


def _directional_signal(config: StrategyConfig) -> object | None:
    """The unique directional signal (or None if zero/multiple — S2
    enforces uniqueness, so callers can assume non-None for a
    grammar-valid config)."""
    matches = [s for s in config.signals if s.role == "directional"]
    if len(matches) == 1:
        return matches[0]
    return None


def _regime_filter_signals(config: StrategyConfig) -> list[object]:
    return [s for s in config.signals if s.role == "regime_filter"]


def _lookback_class_for_indicators(
    indicators: tuple[str, ...],
    registry: RegistrySnapshot,
) -> str | None:
    """§3.5 S4 / D010 bucketing: max over the signal's indicators' Forge-owned
    *signal horizons* → short / medium / long lookback class. Returns ``None``
    if any indicator isn't in the registry (caller's job to report).

    D102 (v8): the horizon now comes from ``forge.grammar.signal_horizon``,
    not ``IndicatorMetadata.lookback`` — the live registry reports 0 for most
    indicators, which collapsed this to "everything is short_lookback". Registry
    *membership* is still required (a grammar-valid config must reference real
    indicators); only the horizon *value* moved to the Forge-owned table."""
    horizons: list[int] = []
    for ind_id in indicators:
        if _indicator_by_id(ind_id, registry) is None:
            return None
        horizons.append(signal_horizon_days(ind_id))
    if not horizons:
        return None
    return horizon_class_for_days(max(horizons))


# ---------------------------------------------------------------------------
# §3.5 S4 — DTE bucket matches the directional signal's lookback class.
# ---------------------------------------------------------------------------


def _s4_lookback_class_matches_dte_bucket(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    directional = _directional_signal(config)
    if directional is None:
        return PredicateResult(
            passed=False,
            detail="S4: no unique directional signal (S2 should catch this first)",
        )
    klass = _lookback_class_for_indicators(directional.indicators, registry)  # type: ignore[attr-defined]
    if klass is None:
        return PredicateResult(
            passed=False,
            detail=(
                f"S4: directional signal references indicator(s) "
                f"{directional.indicators!r} not present in registry"  # type: ignore[attr-defined]
            ),
        )
    allowed = buckets_for_horizon_class(klass)
    if config.dte_bucket in allowed:
        return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"S4: lookback_class={klass!r} (from directional signal) is "
            f"incompatible with dte_bucket={config.dte_bucket!r}; "
            f"allowed buckets: {list(allowed)}"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 S5 — Exit framework consistent with hypothesis.
# ---------------------------------------------------------------------------


def _s5_exits_match_hypothesis(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """D071 — validate the v3 multi-exit composition:

    1. All `required_always` exits are present.
    2. Exactly one of `required_from_set` is present (or required_from_set
       is empty, meaning the choice is already exhausted via
       required_always — e.g., volatility_event's 2-element AND).
    3. Any exits beyond E1 mandatory + required_always + chosen_required
       must come from `optional_additions`.
    4. Optional-additions count <= K_MAX_OPTIONAL (i.e., 2).
    5. No `forbidden` exit is present.
    """
    del registry
    table = _S5_HYPOTHESIS_EXITS.get(config.hypothesis)
    if table is None:
        return PredicateResult(
            passed=False,
            detail=(
                f"S5: unknown hypothesis {config.hypothesis!r} "
                f"(should be impossible given contracts Literal)"
            ),
        )
    exit_ids = {e.id for e in config.exits}
    required_always = set(table["required_always"])
    required_set = set(table["required_from_set"])
    optional_pool = set(table["optional_additions"])
    forbidden = set(table["forbidden"])

    parts: list[str] = []

    # (1) required_always: all must be present
    missing_always = sorted(required_always - exit_ids)
    if missing_always:
        parts.append(f"missing required_always {missing_always}")

    # (2) required_from_set: exactly 1 if non-empty
    chosen_from_set = exit_ids & required_set
    if required_set and len(chosen_from_set) != 1:
        if not chosen_from_set:
            parts.append(
                f"required_from_set: none of {sorted(required_set)} present (must pick exactly 1)",
            )
        else:
            parts.append(
                f"required_from_set: {sorted(chosen_from_set)} present (must pick exactly 1)",
            )

    # (3) any exits beyond E1 + required_always + chosen_required must be optional_additions
    from crucible_contracts import MANDATORY_EXIT_IDS  # noqa: PLC0415

    allowed_set = MANDATORY_EXIT_IDS | required_always | chosen_from_set | optional_pool
    foreign = sorted(exit_ids - allowed_set)
    if foreign:
        parts.append(f"foreign exits not in any allow-set {foreign}")

    # (4) optional-additions count cap
    n_optional = len(exit_ids & optional_pool)
    if n_optional > K_MAX_OPTIONAL:
        parts.append(
            f"too many optional_additions: {n_optional} > K_MAX_OPTIONAL={K_MAX_OPTIONAL}",
        )

    # (5) forbidden
    present_forbidden = sorted(forbidden & exit_ids)
    if present_forbidden:
        parts.append(f"forbidden exits present {present_forbidden}")

    if parts:
        return PredicateResult(
            passed=False,
            detail=f"S5: under hypothesis={config.hypothesis!r}, {'; '.join(parts)}",
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 C1 — No two indicators from the same family.
# ---------------------------------------------------------------------------


def _c1_no_duplicate_indicator_families(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    seen_families: dict[str, str] = {}  # family -> indicator_id (first seen)
    for signal in config.signals:
        for ind_id in signal.indicators:
            im = _indicator_by_id(ind_id, registry)
            if im is None:
                return PredicateResult(
                    passed=False,
                    detail=(f"C1: indicator {ind_id!r} (in signal {signal.id!r}) not in registry"),
                )
            if im.family in seen_families:
                return PredicateResult(
                    passed=False,
                    detail=(
                        f"C1: indicators {seen_families[im.family]!r} and "
                        f"{ind_id!r} share family {im.family!r}"
                    ),
                )
            seen_families[im.family] = ind_id
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 C2 — Directional signal family matches hypothesis.
# ---------------------------------------------------------------------------


def _c2_directional_family_matches_hypothesis(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    directional = _directional_signal(config)
    if directional is None:
        return PredicateResult(
            passed=False,
            detail="C2: no unique directional signal (S2 should catch this first)",
        )
    allowed = _C2_HYPOTHESIS_FAMILIES.get(config.hypothesis)
    if allowed is None:
        # regime_arbitrage: any family is allowed.
        return PredicateResult(passed=True)

    indicator_ids = directional.indicators  # type: ignore[attr-defined]
    if not indicator_ids:
        return PredicateResult(
            passed=False,
            detail="C2: directional signal has zero indicators",
        )
    # Use the first indicator's family as the signal's family (signals
    # are restricted to one indicator-per-family by C1, so any indicator
    # works for this check on a grammar-valid config).
    im = _indicator_by_id(indicator_ids[0], registry)
    if im is None:
        return PredicateResult(
            passed=False,
            detail=(f"C2: directional signal's indicator {indicator_ids[0]!r} not in registry"),
        )
    if im.family in allowed:
        return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"C2: hypothesis={config.hypothesis!r} requires directional "
            f"family in {list(allowed)}; got {im.family!r}"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 C4 — Regime gate cannot use the same indicator as the directional signal.
# ---------------------------------------------------------------------------


def _c4_regime_indicators_disjoint_from_directional(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    directional = _directional_signal(config)
    if directional is None:
        return PredicateResult(
            passed=False,
            detail="C4: no unique directional signal (S2 should catch this first)",
        )
    directional_ids = set(directional.indicators)  # type: ignore[attr-defined]
    for regime in _regime_filter_signals(config):
        overlap = set(regime.indicators) & directional_ids  # type: ignore[attr-defined]
        if overlap:
            return PredicateResult(
                passed=False,
                detail=(
                    f"C4: regime signal {regime.id!r} shares "  # type: ignore[attr-defined]
                    f"indicator(s) {sorted(overlap)} with the directional "
                    f"signal"
                ),
            )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 P1 — Indicator parameters within published ranges.
# ---------------------------------------------------------------------------


def _p1_indicator_params_within_registry_ranges(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """Phase-1 reading: every signal's `params` keys must appear in the
    union of its indicators' `params_schema` keys (i.e., no params keyed
    to an unknown parameter name). The `params_schema` shape itself is
    JSON-Schema-ish but not pinned in contracts; full type-and-range
    validation is deferred to a follow-up rule.
    """
    # Signal-type-specific predicate params that live on `signal.params` but
    # are NOT indicator params (they configure the signal's evaluator, not
    # the underlying indicator computation). P1 strips these before checking.
    # See `crucible_contracts` ThresholdSignal._compare / passthrough.
    _SIGNAL_TYPE_PREDICATE_PARAMS: dict[str, frozenset[str]] = {
        "threshold": frozenset({"threshold", "op"}),
        "passthrough": frozenset(),
        "rule": frozenset(),
    }

    for signal in config.signals:
        allowed_keys: set[str] = set()
        for ind_id in signal.indicators:
            im = _indicator_by_id(ind_id, registry)
            if im is None:
                return PredicateResult(
                    passed=False,
                    detail=(f"P1: indicator {ind_id!r} (signal {signal.id!r}) not in registry"),
                )
            allowed_keys |= set(im.params_schema)
        signal_type_keys = _SIGNAL_TYPE_PREDICATE_PARAMS.get(signal.type, frozenset())
        unknown_keys = set(signal.params) - allowed_keys - signal_type_keys
        # Permit unknown keys only when the indicator(s) declare an empty
        # schema (the registry hasn't documented any parameter shape
        # yet — typical for Phase-1 synthetic data).
        if unknown_keys and allowed_keys:
            return PredicateResult(
                passed=False,
                detail=(
                    f"P1: signal {signal.id!r} has parameter(s) "
                    f"{sorted(unknown_keys)} not declared by its "
                    f"indicator(s) {list(signal.indicators)}"
                ),
            )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 P2 — DTE bucket parameter ranges (entry-side only for v1).
# ---------------------------------------------------------------------------


def _p2_dte_window_matches_bucket(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    entry_window = _P2_ENTRY_DTE.get(config.dte_bucket)
    if entry_window is None:
        return PredicateResult(
            passed=False,
            detail=f"P2: unknown dte_bucket {config.dte_bucket!r}",
        )
    entry_min, entry_max = entry_window
    if config.selector.dte_min < entry_min or config.selector.dte_max > entry_max:
        return PredicateResult(
            passed=False,
            detail=(
                f"P2: dte_bucket={config.dte_bucket!r} entry window is "
                f"[{entry_min}, {entry_max}]; got selector.dte_min="
                f"{config.selector.dte_min}, dte_max="
                f"{config.selector.dte_max}"
            ),
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 P3 — Delta target within DTE-appropriate band.
# ---------------------------------------------------------------------------


def _p3_delta_target_in_dte_band(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    band = effective_delta_band(config.hypothesis, config.dte_bucket)
    if band is None:
        return PredicateResult(
            passed=False,
            detail=f"P3: unknown dte_bucket {config.dte_bucket!r}",
        )
    lo, hi = band
    if not (lo <= config.selector.delta_target <= hi):
        return PredicateResult(
            passed=False,
            detail=(
                f"P3: dte_bucket={config.dte_bucket!r} delta band is "
                f"[{lo}, {hi}]; got delta_target="
                f"{config.selector.delta_target}"
            ),
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 E1 — Mandatory exits always present.
# ---------------------------------------------------------------------------


def _e1_mandatory_exits_present(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    exit_ids = {e.id for e in config.exits}
    missing = sorted(MANDATORY_EXIT_IDS - exit_ids)
    if missing:
        return PredicateResult(
            passed=False,
            detail=f"E1: missing mandatory exits {missing}",
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 E2 — At most 2 stop-loss exits.
# ---------------------------------------------------------------------------


def _e2_at_most_two_stop_loss_exits(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    present = [e.id for e in config.exits if e.id in STOP_LOSS_EXIT_IDS]
    if len(present) > 2:
        return PredicateResult(
            passed=False,
            detail=(f"E2: {len(present)} stop-loss exits {sorted(set(present))}; max allowed is 2"),
        )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 E3 — Trailing stop requires activation threshold.
# ---------------------------------------------------------------------------


def _e3_trailing_atr_has_activation_threshold(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    for exit_spec in config.exits:
        if exit_spec.id != "trailing_atr":
            continue
        threshold = exit_spec.params.get("activate_after_gain_pct")
        if threshold is None:
            return PredicateResult(
                passed=False,
                detail=("E3: trailing_atr exit must set params.activate_after_gain_pct"),
            )
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            return PredicateResult(
                passed=False,
                detail=(
                    f"E3: trailing_atr.params.activate_after_gain_pct must "
                    f"be numeric; got {threshold!r}"
                ),
            )
        if threshold < 0.30:
            return PredicateResult(
                passed=False,
                detail=(
                    f"E3: trailing_atr.params.activate_after_gain_pct must "
                    f"be ≥ 0.30; got {threshold}"
                ),
            )
    return PredicateResult(passed=True)


# ---------------------------------------------------------------------------
# §3.5 R1 — Low-IV strategies require IV-rank gate.
# ---------------------------------------------------------------------------


def _r1_mean_reversion_requires_iv_rank_gate(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """D013 collapsed the second clause of R1 (it was tautological given
    C2): the rule fires whenever hypothesis == mean_reversion.

    D107 (v11 / H3, MR side): a dealer-gamma regime gate
    (`gamma_flip_distance_pct`) is an accepted ALTERNATIVE to the iv_rank
    cheap-IV gate — MR pays in the long-gamma / dampening / ranging regime.
    Either gate satisfies R1."""
    del registry
    if config.hypothesis != "mean_reversion":
        return PredicateResult(passed=True)
    for regime in _regime_filter_signals(config):
        inds = regime.indicators  # type: ignore[attr-defined]
        # D107: a gamma-flip regime gate satisfies R1 on its own (the side is
        # set by the sampler's op, not constrained here — like adx/hurst in R2).
        if _R1_GAMMA_REGIME_INDICATOR in inds:
            return PredicateResult(passed=True)
        # D150: a hurst gate satisfies R1 on its own — the mean-reverting H<0.5
        # side (op "<" set by the sampler). Same convention as the gamma gate.
        if _R1_HURST_REGIME_INDICATOR in inds:
            return PredicateResult(passed=True)
        # D167 (v22): an rv_rank gate satisfies R1 on its own — cheap realized vol
        # (op "<" = LOW = calm/reversion-friendly, the rv_rank default side). Same
        # op-agnostic convention as the gamma/hurst gates (no threshold cap).
        if _R1_RV_RANK_REGIME_INDICATOR in inds:
            return PredicateResult(passed=True)
        if _R1_IV_RANK_INDICATOR not in inds:
            continue
        threshold = regime.params.get("threshold")  # type: ignore[attr-defined]
        if (
            isinstance(threshold, (int, float))
            and not isinstance(threshold, bool)
            and threshold <= _R1_IV_RANK_MAX_THRESHOLD
        ):
            return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"R1: hypothesis=mean_reversion requires a regime_filter signal with "
            f"{_R1_IV_RANK_INDICATOR!r} (params.threshold ≤ {_R1_IV_RANK_MAX_THRESHOLD}), "
            f"{_R1_GAMMA_REGIME_INDICATOR!r} (the D107 dealer-gamma regime gate), "
            f"{_R1_HURST_REGIME_INDICATOR!r} (the D150 mean-reverting regime gate), "
            f"or {_R1_RV_RANK_REGIME_INDICATOR!r} (the D167 cheap-realized-vol regime gate)"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 R2 — Trend strategies require trend-strength gate.
# ---------------------------------------------------------------------------


def _r2_trend_requires_trend_strength_gate(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    if config.hypothesis != "trend_continuation":
        return PredicateResult(passed=True)
    for regime in _regime_filter_signals(config):
        if any(
            ind in _R2_TREND_CONTINUATION_REGIME_INDICATORS
            for ind in regime.indicators  # type: ignore[attr-defined]
        ):
            return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"R2: hypothesis=trend_continuation requires a regime_filter "
            f"signal using one of {list(_R2_TREND_CONTINUATION_REGIME_INDICATORS)}"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 R3 — Volatility-event strategies require event-proximity gate.
# ---------------------------------------------------------------------------


def _r3_volatility_event_requires_event_proximity_gate(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    """§3.5 R3 — volatility_event configs need at least one event-proximity
    regime gate, AND the gate must be ETF-compatible when the config's
    underlying is an ETF (T1.4 / grammar v2).

    Pre-grammar-v2: only checked the event-proximity-gate requirement.
    Tier 2 expansion (D033) exposed the silent-failure case where
    `days_to_earnings` returns sentinel 999 on ETF underlyings — the
    gate never fires and the config produces 0 trades. Grammar v2
    rejects (vol_event, ETF, days_to_earnings) combinations at
    validation time.
    """
    del registry
    if config.hypothesis != "volatility_event":
        return PredicateResult(passed=True)

    is_etf_underlying = (config.underlying or "") in _R3_ETF_UNDERLYINGS
    matched_indicator: str | None = None
    for regime in _regime_filter_signals(config):
        for ind in regime.indicators:  # type: ignore[attr-defined]
            if ind in _R3_EVENT_PROXIMITY_INDICATORS:
                matched_indicator = ind
                # On ETF underlyings, reject indicators that return
                # sentinel values (e.g., days_to_earnings = 999) and
                # would silently produce zero trades. Continue scanning
                # other indicators in case the config also has an
                # ETF-compatible one.
                if is_etf_underlying and ind in _R3_ETF_INCOMPATIBLE_INDICATORS:
                    continue
                return PredicateResult(passed=True)
    if matched_indicator is None:
        return PredicateResult(
            passed=False,
            detail=(
                f"R3: hypothesis=volatility_event requires a regime_filter "
                f"signal using one of {list(_R3_EVENT_PROXIMITY_INDICATORS)}"
            ),
        )
    # Matched an event-proximity indicator but it's ETF-incompatible.
    return PredicateResult(
        passed=False,
        detail=(
            f"R3: hypothesis=volatility_event with underlying="
            f"{config.underlying!r} (ETF) cannot use regime_filter indicator "
            f"{matched_indicator!r}; ETF underlyings have no earnings (sentinel 999). "
            f"Use one of "
            f"{sorted(set(_R3_EVENT_PROXIMITY_INDICATORS) - _R3_ETF_INCOMPATIBLE_INDICATORS)}"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 X1 — Vol-target sizing requires realized_vol indicator.
# ---------------------------------------------------------------------------


def _x1_vol_target_requires_realized_vol_indicator(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    if config.sizer.mode != "vol_target":
        return PredicateResult(passed=True)
    for signal in config.signals:
        if _X1_VOL_TARGET_INDICATOR in signal.indicators:
            return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"X1: sizer.mode=vol_target requires at least one signal to "
            f"reference indicator {_X1_VOL_TARGET_INDICATOR!r}"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 X2 — Fractional Kelly requires expected_value_estimator.
# ---------------------------------------------------------------------------


def _x2_kelly_requires_expected_value_estimator(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    if config.sizer.mode != "fractional_kelly":
        return PredicateResult(passed=True)
    for signal in config.signals:
        if _X2_KELLY_INDICATOR in signal.indicators:
            return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"X2: sizer.mode=fractional_kelly requires at least one "
            f"signal to reference indicator {_X2_KELLY_INDICATOR!r}"
        ),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


REGISTRY: dict[str, CustomPredicateFn] = {
    # Stubs (Phase 1 dispatch path tests)
    "always_pass": _always_pass,
    "always_fail": _always_fail,
    # §3.5 v1 ruleset
    "lookback_class_matches_dte_bucket": _s4_lookback_class_matches_dte_bucket,
    "exits_match_hypothesis": _s5_exits_match_hypothesis,
    "no_duplicate_indicator_families": _c1_no_duplicate_indicator_families,
    "directional_family_matches_hypothesis": _c2_directional_family_matches_hypothesis,
    "regime_indicators_disjoint_from_directional": _c4_regime_indicators_disjoint_from_directional,
    "indicator_params_within_registry_ranges": _p1_indicator_params_within_registry_ranges,
    "dte_window_matches_bucket": _p2_dte_window_matches_bucket,
    "delta_target_in_dte_band": _p3_delta_target_in_dte_band,
    "mandatory_exits_present": _e1_mandatory_exits_present,
    "at_most_two_stop_loss_exits": _e2_at_most_two_stop_loss_exits,
    "trailing_atr_has_activation_threshold": _e3_trailing_atr_has_activation_threshold,
    "mean_reversion_requires_iv_rank_gate": _r1_mean_reversion_requires_iv_rank_gate,
    "trend_requires_trend_strength_gate": _r2_trend_requires_trend_strength_gate,
    "volatility_event_requires_event_proximity_gate": (
        _r3_volatility_event_requires_event_proximity_gate
    ),
    "vol_target_requires_realized_vol_indicator": _x1_vol_target_requires_realized_vol_indicator,
    "kelly_requires_expected_value_estimator": _x2_kelly_requires_expected_value_estimator,
}


def register(name: str, fn: CustomPredicateFn) -> None:
    """Register a custom-predicate function. Duplicate names raise
    ``ValueError`` so the registry can't be silently overwritten."""
    if name in REGISTRY:
        msg = f"custom-predicate name {name!r} already registered"
        raise ValueError(msg)
    REGISTRY[name] = fn


__all__ = ["REGISTRY", "CustomPredicateFn", "register"]
