"""Coordinate-space derivation for Phase 2 enumeration (§4.2).

Given a (grammar, registry) pair, produces a `SearchSpace`: a frozen,
canonically-ordered view of every CSP variable's allowed values. The sampler
consumes this once per batch; it does not re-resolve grammar or registry
data per candidate.

§4.2's CSP-style algorithm separates *variables and domains* from *search*.
This module is the variables-and-domains half; `sampler.py` is the search
half.

Why canonical ordering matters: §13.1 / CLAUDE.md hard rule #6 — given the
same `(grammar_version, registry_hash, seed)`, enumeration must produce the
same sequence. Two `SearchSpace`s built from equal inputs must be bit-equal,
which requires sorted collections and `MappingProxyType` views.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from crucible_contracts import MANDATORY_EXIT_IDS

# These module-level tables are the single source of truth for the v1
# grammar's parameter spaces (DTE windows, delta bands, family mappings,
# §3.5 S5 exit profile). Phase 1 declared them with leading underscores
# inside the predicate-functions module; Phase 2 reads them as shared
# grammar-derived data. A future cleanup can promote them to a top-level
# `forge.grammar.tables` module without semantic change.
from forge.grammar.custom_predicates import (
    _C2_HYPOTHESIS_FAMILIES,
    _P2_ENTRY_DTE,
    _P3_DELTA_BAND,
    _R1_IV_RANK_INDICATOR,
    _R2_TREND_STRENGTH_INDICATORS,
    _R3_EVENT_PROXIMITY_INDICATORS,
    _S5_HYPOTHESIS_EXITS,
    _X1_VOL_TARGET_INDICATOR,
    _X2_KELLY_INDICATOR,
)
from forge.grammar.models import Grammar, NumericalRangePredicate

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot


# Canonical DTE-bucket order — mirrors `StrategyConfig.dte_bucket` Literal.
_DTE_BUCKETS: tuple[str, ...] = ("swing_short", "swing_mid", "swing_long")

# Canonical hypothesis order — mirrors `StrategyConfig.hypothesis` Literal.
_HYPOTHESES: tuple[str, ...] = (
    "trend_continuation",
    "mean_reversion",
    "regime_arbitrage",
    "relative_value",
    "volatility_event",
    "tail_hedge",
)

# D066 — hypotheses Forge must NOT enumerate as a standalone StrategyConfig.
# Crucible's runner rejects these at dispatch (RunnerError, runner.py:397)
# because they belong to OverlaySpec semantics, not StrategySpec. Prior to
# this guard, 1851 / 4039 = 45.8% of inbox configs were tail_hedge round-
# trips that errored at Crucible-side dispatch — pure wasted compute. The
# sampler filters these out of `samplable_hypotheses`; the submitter drops
# any that leak through. Grammar.yaml still lists `tail_hedge` (hard rule
# #1 — operator-owned), so this set is Forge's runtime policy, not a
# grammar edit. When OverlaySpec lands in `crucible_contracts`, the
# overlay-aware enumeration path can re-admit tail_hedge as a portfolio
# overlay (see OPEN_QUESTIONS.md contracts gap, 2026-05-18).
OVERLAY_ONLY_HYPOTHESES: frozenset[str] = frozenset({"tail_hedge"})

# Fallback if no §3.5 P4 numerical_range rule is present in the grammar
# (won't happen with v1; defended in `build_search_space`).
_P4_DEFAULT_RISK_PCT_RANGE: tuple[float, float] = (0.005, 0.02)

_P4_FIELD = "sizer.per_trade_risk_pct"


@dataclass(frozen=True, slots=True)
class SearchSpace:
    """Frozen, canonically-ordered view of the v1 enumeration space.

    Every collection is sorted; every mapping is wrapped in
    `MappingProxyType` so the structure is genuinely immutable. Two
    instances built from equal `(grammar, registry)` inputs compare equal,
    which the §13.1 determinism property test verifies.
    """

    hypotheses: tuple[str, ...]
    sizer_modes: tuple[str, ...]
    samplable_sizer_modes: tuple[str, ...]
    dte_buckets: tuple[str, ...]

    indicators_by_family: Mapping[str, tuple[str, ...]]
    directional_indicators_by_hypothesis: Mapping[str, tuple[str, ...]]
    regime_indicators_by_hypothesis: Mapping[str, tuple[str, ...]]

    # Sparse: only modes WITH a §3.5 X-rule requirement that the current
    # registry can satisfy. ``samplable_sizer_modes`` is the filtered set
    # of modes the sampler may pick — a mode is samplable iff it has no
    # X-rule or its X-rule is satisfied.
    sizer_required_indicator: Mapping[str, str]

    dte_entry_window_by_bucket: Mapping[str, tuple[int, int]]
    delta_band_by_bucket: Mapping[str, tuple[float, float]]
    risk_pct_range: tuple[float, float]

    s5_required_by_hypothesis: Mapping[str, tuple[str, ...]]
    s5_forbidden_by_hypothesis: Mapping[str, tuple[str, ...]]
    e1_mandatory: tuple[str, ...]


def build_search_space(
    grammar: Grammar,
    registry: RegistrySnapshot,
) -> SearchSpace:
    """Pre-resolve the enumeration coordinate space from grammar + registry.

    Pure function: equal inputs always produce equal `SearchSpace` outputs.
    """
    registry_ids = {ind.id for ind in registry.indicators}

    indicators_by_family = _build_indicators_by_family(registry)
    directional = _build_directional_pool(indicators_by_family)
    regime = _build_regime_pool(registry_ids)
    samplable_modes, sizer_req = _build_sizer_mode_views(registry.sizer_modes, registry_ids)
    risk_pct_range = _resolve_p4_risk_pct_range(grammar)

    s5_required = MappingProxyType({h: _S5_HYPOTHESIS_EXITS[h]["required"] for h in _HYPOTHESES})
    s5_forbidden = MappingProxyType({h: _S5_HYPOTHESIS_EXITS[h]["forbidden"] for h in _HYPOTHESES})

    return SearchSpace(
        hypotheses=_HYPOTHESES,
        sizer_modes=tuple(sorted(registry.sizer_modes)),
        samplable_sizer_modes=samplable_modes,
        dte_buckets=_DTE_BUCKETS,
        indicators_by_family=indicators_by_family,
        directional_indicators_by_hypothesis=directional,
        regime_indicators_by_hypothesis=regime,
        sizer_required_indicator=sizer_req,
        dte_entry_window_by_bucket=MappingProxyType(dict(_P2_ENTRY_DTE)),
        delta_band_by_bucket=MappingProxyType(dict(_P3_DELTA_BAND)),
        risk_pct_range=risk_pct_range,
        s5_required_by_hypothesis=s5_required,
        s5_forbidden_by_hypothesis=s5_forbidden,
        e1_mandatory=tuple(sorted(MANDATORY_EXIT_IDS)),
    )


def _build_indicators_by_family(
    registry: RegistrySnapshot,
) -> Mapping[str, tuple[str, ...]]:
    by_family: dict[str, list[str]] = {}
    for ind in registry.indicators:
        by_family.setdefault(ind.family, []).append(ind.id)
    return MappingProxyType({fam: tuple(sorted(ids)) for fam, ids in sorted(by_family.items())})


def _build_directional_pool(
    indicators_by_family: Mapping[str, tuple[str, ...]],
) -> Mapping[str, tuple[str, ...]]:
    """For each hypothesis, return the indicator ids whose family appears in
    §3.5 C2's allowed-families table. `regime_arbitrage` allows any family."""
    pool: dict[str, tuple[str, ...]] = {}
    for hyp in _HYPOTHESES:
        allowed_families = _C2_HYPOTHESIS_FAMILIES[hyp]
        if allowed_families is None:
            ids = sorted(ind for family_ids in indicators_by_family.values() for ind in family_ids)
        else:
            ids = sorted(
                ind for fam in allowed_families for ind in indicators_by_family.get(fam, ())
            )
        pool[hyp] = tuple(ids)
    return MappingProxyType(pool)


def _build_regime_pool(
    registry_ids: set[str],
) -> Mapping[str, tuple[str, ...]]:
    """Per-hypothesis regime-gate options.

    §3.5 R1/R2/R3 pin specific indicator ids for three hypotheses; the
    remaining three (regime_arbitrage, relative_value, tail_hedge) have no
    R-rule constraint, so any registry indicator may serve. The sampler
    enforces §3.5 C4 (regime disjoint from directional) at sample time.
    """
    pool: dict[str, tuple[str, ...]] = {}
    for hyp in _HYPOTHESES:
        if hyp == "trend_continuation":
            pool[hyp] = tuple(sorted(set(_R2_TREND_STRENGTH_INDICATORS) & registry_ids))
        elif hyp == "mean_reversion":
            pool[hyp] = (_R1_IV_RANK_INDICATOR,) if _R1_IV_RANK_INDICATOR in registry_ids else ()
        elif hyp == "volatility_event":
            pool[hyp] = tuple(sorted(set(_R3_EVENT_PROXIMITY_INDICATORS) & registry_ids))
        else:
            pool[hyp] = tuple(sorted(registry_ids))
    return MappingProxyType(pool)


_X_RULE_REQUIREMENTS: Mapping[str, str] = MappingProxyType(
    {
        "vol_target": _X1_VOL_TARGET_INDICATOR,
        "fractional_kelly": _X2_KELLY_INDICATOR,
    }
)


def _build_sizer_mode_views(
    sizer_modes: tuple[str, ...],
    registry_ids: set[str],
) -> tuple[tuple[str, ...], Mapping[str, str]]:
    """Resolve §3.5 X1/X2 against the registry.

    Returns ``(samplable_modes, required_indicator_map)``:

    - ``samplable_modes``: modes the sampler may pick. A mode is samplable
      iff it has no X-rule requirement OR its required indicator is in the
      registry.
    - ``required_indicator_map``: sparse — keyed only by modes whose X-rule
      requirement is *met*. ``mapping.get(mode)`` returns ``None`` for
      modes with no requirement, the sampler treats that as "no chaining
      needed".
    """
    samplable: list[str] = []
    required: dict[str, str] = {}
    for mode in sorted(sizer_modes):
        x_requirement = _X_RULE_REQUIREMENTS.get(mode)
        if x_requirement is None:
            samplable.append(mode)
        elif x_requirement in registry_ids:
            samplable.append(mode)
            required[mode] = x_requirement
    return tuple(samplable), MappingProxyType(required)


def _resolve_p4_risk_pct_range(grammar: Grammar) -> tuple[float, float]:
    """Look up the §3.5 P4 numerical_range bounds for `sizer.per_trade_risk_pct`.

    Falls back to the default if no such rule is present. v1 always defines
    P4, so the fallback exists for forward-compat with future grammar
    versions that might rename or remove the rule.
    """
    for rule in grammar.rules:
        predicate = rule.predicate
        if not isinstance(predicate, NumericalRangePredicate):
            continue
        if predicate.field != _P4_FIELD:
            continue
        if predicate.min is None or predicate.max is None:
            continue
        return (predicate.min, predicate.max)
    return _P4_DEFAULT_RISK_PCT_RANGE
