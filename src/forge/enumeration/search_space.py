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
    _EVENT_MOMENTUM_REGIME_INDICATORS,
    _P2_ENTRY_DTE,
    _P3_DELTA_BAND,
    _R1_GAMMA_REGIME_INDICATOR,
    _R1_IV_RANK_INDICATOR,
    _R2_TREND_CONTINUATION_REGIME_INDICATORS,
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
# event_momentum (v12 / D109) is appended last, matching the contracts 1.16.0
# Literal order (so by-feature joins and golden orderings stay aligned).
_HYPOTHESES: tuple[str, ...] = (
    "trend_continuation",
    "mean_reversion",
    "regime_arbitrage",
    "relative_value",
    "volatility_event",
    "tail_hedge",
    "event_momentum",
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

# D098 (v5) — hypotheses Forge stops enumerating because they are low-yield by
# construction, not by a wiring bug. `regime_arbitrage` routes to the same
# ComposableLongOptions template as the productive hypotheses, but its enumerated
# signal set is incoherent: the mandatory regime_filter stacks contradictory
# regime concepts (momentum_252 trend + rsi_2 mean-reversion + iv_rank vol +
# expected_value_estimator) that rarely all align — 81% zero-trade, and the few
# that trade carry no edge thesis (Crucible pre-v5 investigation, DESIGN §20).
# Like `OVERLAY_ONLY_HYPOTHESES` this is Forge runtime policy, NOT a grammar
# edit: grammar.yaml S1 still lists `regime_arbitrage` (hard rule #1 — the
# operator owns the rule set), so a hand-authored regime_arbitrage config still
# validates. Forge simply never enumerates one. Re-admit by removing it here.
DISABLED_HYPOTHESES: frozenset[str] = frozenset({"regime_arbitrage"})

# The union Forge never enumerates as a standalone StrategyConfig: overlay-only
# (D066) + disabled-by-policy (D098). Every enumeration-path filter reads this.
NON_ENUMERABLE_HYPOTHESES: frozenset[str] = OVERLAY_ONLY_HYPOTHESES | DISABLED_HYPOTHESES

# H1 (v12 / D109) — hypotheses that may use the cross_sectional_rank combiner as
# a breadth-manufacturing OPTION (vs the default confluence). Scoped to the
# breadth-starved DIRECTIONAL archetypes: trend_continuation + mean_reversion
# (single-name firing ≈ 1 trade → killed at the 100-trade floor) plus
# event_momentum (§2.4 — PEAD's productive form is cross-sectional). vol_event
# (event-single-name, already clears breadth via recurring events) and
# relative_value (pairs) keep confluence. The rank draw is gated on
# `rank_combiner_share`; with no share the combiner is always confluence
# (byte-identical cold path, hard rule #6). The runner routes a rank config to
# the composable rank-top-K template by combiner.type, regardless of hypothesis.
RANK_COMBINER_HYPOTHESES: frozenset[str] = frozenset(
    {"trend_continuation", "mean_reversion", "event_momentum"}
)

# D112 (v13) — dealer_positioning indicators are SINGLE-NAME ONLY. Their
# headline series (per-bar greek grid) costs ~100x a single-name headline on
# Crucible's serial runner (5-14 min vs 1-3 s — the throughput tail), and the
# decided universe-wide dealer cohort cleared no §8.7 gate. So no dealer
# indicator may appear in a universe-wide config: the H1 cross_sectional_rank
# combiner (sampler skips the rank draw for dealer-signal configs) or
# relative_value's underlying=None universe scan (`_build_regime_pool` excludes
# the family). Single-name dealer enumeration is untouched — it is the
# promotion frontier (the only CPCV-p25-gate clearers in the decided pool).
DEALER_POSITIONING_FAMILY: str = "dealer_positioning"

# D116 (v14) → D118 (v15) — single-name-only indicator ids beyond the dealer
# family. v14 carried the chain-reading pair as an interim set; v15 re-keys on
# Crucible's full indicator→mode map (`rank_gate_class_map.json`, 2026-06-09,
# 45 indicators, completeness-asserted their side). The broken class is
# per-name DECOUPLING from the evaluated sym, not chain reads: on the
# rank/pairs paths the indicator's data source comes from its own params
# (`underlying`/`symbol`), which those paths never thread per-name, so the
# declared per-name semantics never compute. Modes: iv_rank fires on noise
# (the reference chain's IV at the name's spot — garbage_mismatch);
# put_call_flow returns the reference's value for every name
# (hidden_uniform_reference); sue / days_since_earnings / days_to_earnings
# are per-name events keyed on params["symbol"] → NaN → inert fail-open (an
# ungated arm; as a rank DIRECTIONAL, sue would rank the universe on NaN —
# the dealer-directional 0/8 pattern). Bar-only indicators compute on the
# name's own bars and are unaffected. market_wide_by_design ids (vix_level,
# days_to_cpi/fomc/nfp/opex) are deliberately NOT here — uniform-across-names
# is correct for a market gate. Durable key = a `rank_per_name_coherent`
# flag on registry indicator metadata (contracts gap, surfaced to Crucible);
# until then this explicit set mirrors the map.
SINGLE_NAME_ONLY_INDICATOR_IDS: frozenset[str] = frozenset(
    {
        "iv_rank",
        "put_call_flow",
        "sue",
        "days_since_earnings",
        "days_to_earnings",
    }
)

# D118 (v15) — `expected_value_estimator` is excluded as a universe GATE or
# DIRECTIONAL only (it reads the runs-DB trades table keyed on
# params["underlying"] → the reference's EV for every ranked name —
# hidden_uniform_reference with an inert NaN fallback). Role-scoped
# deliberately: the §3.5 X2 fractional_kelly sizer chain (role="confluence"
# passthrough) is reference-keyed on EVERY path — single-name kelly configs
# size off the same default-underlying EV with empty params — so EV-as-sizing
# must not block the rank branch (see `_uses_single_name_only_indicator`).
RANK_DECOUPLED_GATE_INDICATOR_IDS: frozenset[str] = frozenset({"expected_value_estimator"})

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

    # D071 (Phase 4 multi-exit): pre-D071 schema was s5_required_by_hypothesis
    # (single tuple). Post-D071 the sampler reads `required_always` (must-all-
    # appear) + `required_from_set` (sampler picks 1) + `optional_additions`
    # (sampler picks 0..K_MAX_OPTIONAL). `s5_required_by_hypothesis` is
    # retained as a derived convenience = required_always + first element of
    # required_from_set (deterministic; used by callers that need ONE required
    # tuple, e.g., legacy tests during the v2→v3 transition). The forbidden
    # set is unchanged.
    s5_required_always_by_hypothesis: Mapping[str, tuple[str, ...]]
    s5_required_from_set_by_hypothesis: Mapping[str, tuple[str, ...]]
    s5_optional_additions_by_hypothesis: Mapping[str, tuple[str, ...]]
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
    regime = _build_regime_pool(
        registry_ids,
        single_name_only_ids=(
            frozenset(indicators_by_family.get(DEALER_POSITIONING_FAMILY, ()))
            | (SINGLE_NAME_ONLY_INDICATOR_IDS & registry_ids)
            # Regime pools are gate pools, so the gate-only EV exclusion
            # applies here unconditionally (the role-scoping only matters in
            # the sampler's rank-branch check, where the X2 chain is exempt).
            | (RANK_DECOUPLED_GATE_INDICATOR_IDS & registry_ids)
        ),
    )
    samplable_modes, sizer_req = _build_sizer_mode_views(registry.sizer_modes, registry_ids)
    risk_pct_range = _resolve_p4_risk_pct_range(grammar)

    # D071: derive new schema fields from _S5_HYPOTHESIS_EXITS.
    s5_required_always = MappingProxyType(
        {h: _S5_HYPOTHESIS_EXITS[h]["required_always"] for h in _HYPOTHESES},
    )
    s5_required_from_set = MappingProxyType(
        {h: _S5_HYPOTHESIS_EXITS[h]["required_from_set"] for h in _HYPOTHESES},
    )
    s5_optional_additions = MappingProxyType(
        {h: _S5_HYPOTHESIS_EXITS[h]["optional_additions"] for h in _HYPOTHESES},
    )
    s5_forbidden = MappingProxyType(
        {h: _S5_HYPOTHESIS_EXITS[h]["forbidden"] for h in _HYPOTHESES},
    )
    # Legacy convenience: required_always + the first (canonical) element of
    # required_from_set, for callers / tests that need a single tuple.
    s5_required_legacy = MappingProxyType(
        {
            h: (
                *_S5_HYPOTHESIS_EXITS[h]["required_always"],
                *(_S5_HYPOTHESIS_EXITS[h]["required_from_set"][:1]),
            )
            for h in _HYPOTHESES
        }
    )

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
        s5_required_always_by_hypothesis=s5_required_always,
        s5_required_from_set_by_hypothesis=s5_required_from_set,
        s5_optional_additions_by_hypothesis=s5_optional_additions,
        s5_required_by_hypothesis=s5_required_legacy,
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
    *,
    single_name_only_ids: frozenset[str],
) -> Mapping[str, tuple[str, ...]]:
    """Per-hypothesis regime-gate options.

    §3.5 R1/R2/R3 pin specific indicator ids for three hypotheses; event_momentum
    (v12 / D109) is pinned to its post-event timing gate the same way but via
    sampler-side policy rather than a grammar.yaml rule (hard rule #1 — see
    `_EVENT_MOMENTUM_REGIME_INDICATORS`). regime_arbitrage and tail_hedge have no
    constraint, so any registry indicator may serve. relative_value is also
    R-rule-free but runs as the universe template (underlying=None), so it
    excludes ``single_name_only_ids`` — the dealer family (D112/v13), the
    chain-reading ids (D116/v14), and the per-name event/DB ids re-keyed from
    Crucible's indicator→mode map (D118/v15, see
    `SINGLE_NAME_ONLY_INDICATOR_IDS` + `RANK_DECOUPLED_GATE_INDICATOR_IDS`) —
    from its pool. Single-name hypotheses keep their full pools: the per-name
    decoupling only exists on Crucible's universe paths. The sampler enforces
    §3.5 C4 (regime disjoint from directional) at sample time.
    """
    pool: dict[str, tuple[str, ...]] = {}
    for hyp in _HYPOTHESES:
        if hyp == "trend_continuation":
            pool[hyp] = tuple(sorted(set(_R2_TREND_CONTINUATION_REGIME_INDICATORS) & registry_ids))
        elif hyp == "mean_reversion":
            # D107 (v11 / H3, MR side): gamma_flip_distance_pct joins iv_rank as
            # an accepted R1 regime gate (the long-gamma / ranging regime).
            pool[hyp] = tuple(
                sorted({_R1_IV_RANK_INDICATOR, _R1_GAMMA_REGIME_INDICATOR} & registry_ids)
            )
        elif hyp == "volatility_event":
            pool[hyp] = tuple(sorted(set(_R3_EVENT_PROXIMITY_INDICATORS) & registry_ids))
        elif hyp == "event_momentum":
            # H2 (v12 / D109): post-event TIMING gate only (days_since_earnings).
            # Sampler-side policy, not a grammar.yaml rule (hard rule #1) — see
            # `_EVENT_MOMENTUM_REGIME_INDICATORS` in custom_predicates.
            pool[hyp] = tuple(sorted(set(_EVENT_MOMENTUM_REGIME_INDICATORS) & registry_ids))
        elif hyp == "relative_value":
            # D112 (v13) + D116 (v14) + D118 (v15): the universe template
            # never carries a dealer, chain-reading, or per-name event/DB gate.
            pool[hyp] = tuple(sorted(registry_ids - single_name_only_ids))
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
