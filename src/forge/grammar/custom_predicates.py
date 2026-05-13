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

if TYPE_CHECKING:
    from crucible_contracts import IndicatorMetadata, RegistrySnapshot, StrategyConfig


CustomPredicateFn = Callable[["StrategyConfig", "RegistrySnapshot"], PredicateResult]


# ---------------------------------------------------------------------------
# Module-level tables and thresholds — operator-readable single source
# ---------------------------------------------------------------------------

# D010 lookback bucketing — max-over-indicators of IndicatorMetadata.lookback.
_LOOKBACK_SHORT_MAX = 6
_LOOKBACK_MEDIUM_MAX = 89  # long_lookback is anything >= 90

_LOOKBACK_DTE_TABLE: dict[str, tuple[str, ...]] = {
    "short_lookback": ("swing_short",),
    "medium_lookback": ("swing_short", "swing_mid"),
    "long_lookback": ("swing_mid", "swing_long"),
}

# §3.5 S5 hypothesis → required + forbidden exits.
_S5_HYPOTHESIS_EXITS: dict[str, dict[str, tuple[str, ...]]] = {
    "trend_continuation": {
        "required": ("trailing_atr",),
        "forbidden": ("hard_profit_target",),
    },
    "mean_reversion": {
        "required": ("time_stop",),
        "forbidden": (),
    },
    "regime_arbitrage": {
        "required": ("regime_flip_exit",),
        "forbidden": (),
    },
    "relative_value": {
        "required": ("convergence_exit",),
        "forbidden": (),
    },
    "volatility_event": {
        "required": ("iv_crush_exit", "event_passed_exit"),
        "forbidden": (),
    },
    "tail_hedge": {
        "required": ("roll_on_schedule_exit",),
        # §3.5 says "profit-taking forbidden" — read narrowly as
        # `hard_profit_target` (the only profit-taking exit in
        # KNOWN_EXIT_IDS).
        "forbidden": ("hard_profit_target",),
    },
}

# §3.5 C2 hypothesis → allowed directional-signal families.
# regime_arbitrage allows any family.
_C2_HYPOTHESIS_FAMILIES: dict[str, tuple[str, ...] | None] = {
    "trend_continuation": ("trend",),
    "mean_reversion": ("mean_reversion",),
    "regime_arbitrage": None,
    "relative_value": ("pairs",),
    "volatility_event": ("iv_structure", "flow"),
    "tail_hedge": ("macro",),
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

# §3.5 R2/R3 regime-gate indicator requirements.
_R2_TREND_STRENGTH_INDICATORS = ("adx", "hurst")
_R3_EVENT_PROXIMITY_INDICATORS = ("days_to_earnings", "days_to_fomc")

# §3.5 R1 IV-rank gate parameters.
_R1_IV_RANK_INDICATOR = "iv_rank"
_R1_IV_RANK_MAX_THRESHOLD = 50.0

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
    """D010 bucketing: max over indicators' lookback → short / medium /
    long lookback class. Returns ``None`` if any indicator isn't in the
    registry (caller's job to report)."""
    lookbacks: list[int] = []
    for ind_id in indicators:
        im = _indicator_by_id(ind_id, registry)
        if im is None:
            return None
        lookbacks.append(im.lookback)
    if not lookbacks:
        return None
    max_lb = max(lookbacks)
    if max_lb <= _LOOKBACK_SHORT_MAX:
        return "short_lookback"
    if max_lb <= _LOOKBACK_MEDIUM_MAX:
        return "medium_lookback"
    return "long_lookback"


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
    allowed = _LOOKBACK_DTE_TABLE.get(klass, ())
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
    missing = [eid for eid in table["required"] if eid not in exit_ids]
    present_forbidden = [eid for eid in table["forbidden"] if eid in exit_ids]
    if missing or present_forbidden:
        parts: list[str] = []
        if missing:
            parts.append(f"missing required exits {missing}")
        if present_forbidden:
            parts.append(f"forbidden exits present {present_forbidden}")
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
        unknown_keys = set(signal.params) - allowed_keys
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
    band = _P3_DELTA_BAND.get(config.dte_bucket)
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
    C2): the rule fires whenever hypothesis == mean_reversion."""
    del registry
    if config.hypothesis != "mean_reversion":
        return PredicateResult(passed=True)
    for regime in _regime_filter_signals(config):
        if _R1_IV_RANK_INDICATOR not in regime.indicators:  # type: ignore[attr-defined]
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
            f"R1: hypothesis=mean_reversion requires a regime_filter "
            f"signal with indicator {_R1_IV_RANK_INDICATOR!r} and "
            f"params.threshold ≤ {_R1_IV_RANK_MAX_THRESHOLD}"
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
            ind in _R2_TREND_STRENGTH_INDICATORS
            for ind in regime.indicators  # type: ignore[attr-defined]
        ):
            return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"R2: hypothesis=trend_continuation requires a regime_filter "
            f"signal using one of {list(_R2_TREND_STRENGTH_INDICATORS)}"
        ),
    )


# ---------------------------------------------------------------------------
# §3.5 R3 — Volatility-event strategies require event-proximity gate.
# ---------------------------------------------------------------------------


def _r3_volatility_event_requires_event_proximity_gate(
    config: StrategyConfig,
    registry: RegistrySnapshot,
) -> PredicateResult:
    del registry
    if config.hypothesis != "volatility_event":
        return PredicateResult(passed=True)
    for regime in _regime_filter_signals(config):
        if any(
            ind in _R3_EVENT_PROXIMITY_INDICATORS
            for ind in regime.indicators  # type: ignore[attr-defined]
        ):
            return PredicateResult(passed=True)
    return PredicateResult(
        passed=False,
        detail=(
            f"R3: hypothesis=volatility_event requires a regime_filter "
            f"signal using one of {list(_R3_EVENT_PROXIMITY_INDICATORS)}"
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
