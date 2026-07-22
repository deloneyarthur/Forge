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
    _C2_HYPOTHESIS_EXTRA_IDS,
    _C2_HYPOTHESIS_FAMILIES,
    _EVENT_MOMENTUM_REGIME_INDICATORS,
    _MR_REGIME_VETO_INDICATORS,
    _P2_ENTRY_DTE,
    _P3_DELTA_BAND,
    _P3_DELTA_BAND_OVERRIDES,
    _R1_GAMMA_REGIME_INDICATOR,
    _R1_HURST_REGIME_INDICATOR,
    _R1_IV_RANK_INDICATOR,
    _R1_MARKET_REALIZED_VOL_REGIME_INDICATOR,
    _R1_REALIZED_VOL_REGIME_INDICATOR,
    _R1_RV_RANK_REGIME_INDICATOR,
    _R1_VOL_REGIME_INDICATOR,
    _R2_TREND_CONTINUATION_REGIME_INDICATORS,
    _R2_TREND_VOLATILITY_VETO_INDICATORS,
    _R3_EVENT_PROXIMITY_INDICATORS,
    _S5_HYPOTHESIS_EXITS,
    _VE_REGIME_VETO_INDICATORS,
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
#
# v47 (D328) — freeze-program retirements of two hypotheses with no productive
# form (Crucible reads: FORGE_single_name_trend_mr_retirement_read +
# FORGE_event_momentum_soxl_degenerate_reply):
#   relative_value — refuted (D215/D276: xsect rank-IC negative, corr-to-MR
#     0.88) + dormant (0 recent submission flow).
#   event_momentum — single-name-ONLY (its `sue` directional is
#     rank_per_name_coherent=False → no xsect form; Crucible "no cross-sectional
#     PEAD form exists" + xsect-PEAD ask WITHDRAWN) and dead (3 components, 0
#     conversion). Its only book use — pure_sue175's SOXL leg — is the D268
#     degenerate (inert sue/days_since_earnings → naked long-SOXL calls, 0 PEAD;
#     unreproducible since SOXL is excluded from earnings-gated configs). A
#     generation change never de-promotes that frozen book.
DISABLED_HYPOTHESES: frozenset[str] = frozenset(
    {"regime_arbitrage", "relative_value", "event_momentum"}
)

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


# D125 (v16) — rank/universe exclusion is keyed on the contracts-1.18.0
# registry flags, retiring the v13-v15 explicit id sets
# (SINGLE_NAME_ONLY_INDICATOR_IDS / RANK_DECOUPLED_GATE_INDICATOR_IDS). The
# excluded class is `NOT rank_per_name_coherent AND NOT market_wide_by_design`
# — exactly the D118 key, but published per-indicator by Crucible from
# ClassVars asserted against their runner code (the authority on per-name
# fan-out), with FAIL-CLOSED defaults: a new indicator ships excluded until
# Crucible proves coherence, so the dealer/iv_rank fail-open eras cannot
# recur. v16 also drops v15's confluence exemption (D122: EV-as-sizing has no
# live wiring; on the rank path a confluence signal is a rank-score factor —
# output-neutral warm, config-freezing cold — so the X2 kelly EV chain pins
# its config single-name). The dealer family stays excluded INDEPENDENTLY of
# its flags: D115's re-admission clause needs the reference gate AND coherent
# single-name MRxgamma evidence — a Crucible flag flip alone is only half the
# trigger, and the D112 ~100x runner-cost rationale is coherence-independent.
# D270 (v31): POLICY rank exclusions — ids kept out of universe-wide rank
# configs even though their registry flags would admit them. `momentum` IS
# rank_per_name_coherent, but the cross_sectional_rank combiner sorts
# DESCENDING unconditionally: top-N by raw momentum buys the STRONGEST names —
# the exact INVERSE of the capitulation-bounce mechanism the id was activated
# for (a tightening; the threshold/confluence path is the validated form).
_RANK_POLICY_EXCLUDED_IDS: frozenset[str] = frozenset({"momentum"})


def rank_excluded_indicator_ids(registry: RegistrySnapshot) -> frozenset[str]:
    """Indicator ids that may never appear in a universe-wide config's
    signals (rank branch: any role; universe regime pools: gate role).
    Flag-derived (dealer family + every non-coherent non-market-wide id) plus
    the D270 policy set."""
    return _RANK_POLICY_EXCLUDED_IDS | frozenset(
        ind.id
        for ind in registry.indicators
        if ind.family == DEALER_POSITIONING_FAMILY
        or (not ind.rank_per_name_coherent and not ind.market_wide_by_design)
    )


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
    # D258 (v25) / D263 (v26): optional VETO gates that AND on top of the primary
    # regime gate (§3.5 S3): dsj event-frequency veto on trend_continuation (v25),
    # ivol name-selection veto on mean_reversion (v26). Empty per hypothesis until
    # the registry serves the id, so the sampler's veto draw is skipped entirely →
    # byte-identical cold path.
    regime_veto_indicators_by_hypothesis: Mapping[str, tuple[str, ...]]
    # D263 (v26) / D266 (v29): the registry family per VETO ID (dsj→volatility,
    # ivol→idiosyncratic_vol, market_realized_vol→macro), so the sampler's C1
    # guard checks each veto id's OWN family — a veto id is eligible iff no
    # same-family indicator is already in the config. Per-ID (not
    # per-hypothesis) since v29: the MR pool holds ids from TWO families.
    # Keyed only by served ids (members of a non-empty pool).
    regime_veto_family_by_id: Mapping[str, str]

    # Sparse: only modes WITH a §3.5 X-rule requirement that the current
    # registry can satisfy. ``samplable_sizer_modes`` is the filtered set
    # of modes the sampler may pick — a mode is samplable iff it has no
    # X-rule or its X-rule is satisfied.
    sizer_required_indicator: Mapping[str, str]

    dte_entry_window_by_bucket: Mapping[str, tuple[int, int]]
    delta_band_by_bucket: Mapping[str, tuple[float, float]]
    # D125 (v16): hypothesis-scoped P3 band overrides (trend swing_long/mid
    # upper edges → 0.55); sampler draws from the effective band.
    delta_band_overrides_by_hypothesis: Mapping[str, Mapping[str, tuple[float, float]]]
    risk_pct_range: tuple[float, float]

    # D125 (v16): flag-derived universe exclusion (see
    # `rank_excluded_indicator_ids`) — the rank-branch skip reads this.
    rank_excluded_ids: frozenset[str]

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
    rank_excluded = rank_excluded_indicator_ids(registry)
    regime = _build_regime_pool(
        registry_ids,
        # Regime pools are universe gate pools — the whole flag-excluded
        # class (dealer included) is out (D125/v16).
        single_name_only_ids=rank_excluded,
    )
    samplable_modes, sizer_req = _build_sizer_mode_views(registry.sizer_modes, registry_ids)
    risk_pct_range = _resolve_p4_risk_pct_range(grammar)

    # D258 (v25) / D263 (v26) / D266 (v29): the veto pools (dsj on trend;
    # ivol + market_realized_vol on MR), intersected with registry_ids so each id
    # is absent until the registry serves it — an empty pool consumes no rng
    # (byte-identical, hard rule #6), and a partially-served MR pool simply
    # offers fewer ids.
    regime_veto = MappingProxyType(
        {
            "trend_continuation": tuple(
                sorted(set(_R2_TREND_VOLATILITY_VETO_INDICATORS) & registry_ids)
            ),
            "mean_reversion": tuple(sorted(set(_MR_REGIME_VETO_INDICATORS) & registry_ids)),
            # D290 (v39): the ve index-tape veto (ref_trailing_return) — same
            # registry-gated dormancy as the trend/MR pools.
            "volatility_event": tuple(sorted(set(_VE_REGIME_VETO_INDICATORS) & registry_ids)),
        }
    )
    # D263 (v26) / D266 (v29): the veto family per ID, read from registry
    # metadata, so the sampler's C1 guard uses each veto id's OWN family
    # (dsj→volatility, ivol→idiosyncratic_vol, market_realized_vol→macro).
    # Per-ID since v29 — the MR pool spans two families.
    _id_to_family = {ind.id: ind.family for ind in registry.indicators}
    regime_veto_family = MappingProxyType(
        {i: _id_to_family[i] for ids in regime_veto.values() for i in ids},
    )

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
        regime_veto_indicators_by_hypothesis=regime_veto,
        regime_veto_family_by_id=regime_veto_family,
        sizer_required_indicator=sizer_req,
        dte_entry_window_by_bucket=MappingProxyType(dict(_P2_ENTRY_DTE)),
        delta_band_by_bucket=MappingProxyType(dict(_P3_DELTA_BAND)),
        delta_band_overrides_by_hypothesis=MappingProxyType(
            {
                hyp: MappingProxyType(dict(buckets))
                for hyp, buckets in _P3_DELTA_BAND_OVERRIDES.items()
            }
        ),
        risk_pct_range=risk_pct_range,
        rank_excluded_ids=rank_excluded,
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


# D270 (v31): per-hypothesis directional-pool PIN-EXCLUSIONS (sampler-side
# policy, not a §3.5 rule — the _EVENT_MOMENTUM_REGIME_INDICATORS pattern).
# `momentum` gains a directional threshold entry for the MR capitulation
# family; being family `trend` it would otherwise auto-join
# trend_continuation's family-derived pool with contrarian `<` semantics under
# a continuation thesis AND the wrong exit chassis (trend requires a trailing
# exit; the validated capitulation chassis is time-stop-primary). Pinning it
# out also keeps trend's draw sequence byte-identical across the bump.
#
# D276 (v33) — generation-health retirements (Crucible
# FORGE_generation_health_capitulation_addendum_2026-07-15 §B, measured on the
# last-7-day funnel; EMISSION-side only, the C2 predicate still accepts the
# submitted lineage):
#   option_momentum — 100% structurally dead (47/wk, median 5 OOS trades, ~0
#     component conversions in the month since the v19 min_months fix); retired
#     from every hypothesis that could draw it (trend via C2 smart_money;
#     regime_arbitrage via its any-family pool). The sibling smart_money id
#     `expected_value_estimator` stays the X2 kelly chain feature.
#   gamma_flip_distance_pct as a MEAN_REVERSION directional — dead in every
#     gate combination (~100/wk, 94-97% WF=0). MR-scoped: it remains an R1
#     REGIME gate (D107), and the other dealer directionals (walls, gex) keep
#     their D062 admission.
_DIRECTIONAL_POOL_EXCLUDED_IDS: dict[str, frozenset[str]] = {
    "trend_continuation": frozenset({"momentum", "option_momentum"}),
    "regime_arbitrage": frozenset({"option_momentum"}),
    "mean_reversion": frozenset({"gamma_flip_distance_pct"}),
}


def _build_directional_pool(
    indicators_by_family: Mapping[str, tuple[str, ...]],
) -> Mapping[str, tuple[str, ...]]:
    """For each hypothesis, return the indicator ids whose family appears in
    §3.5 C2's allowed-families table. `regime_arbitrage` allows any family.
    D270 (v31): the C2 per-id carve-outs (`_C2_HYPOTHESIS_EXTRA_IDS`) are
    unioned in (registry-gated); the pin-exclusions above are removed."""
    all_ids = {ind for family_ids in indicators_by_family.values() for ind in family_ids}
    pool: dict[str, tuple[str, ...]] = {}
    for hyp in _HYPOTHESES:
        allowed_families = _C2_HYPOTHESIS_FAMILIES[hyp]
        if allowed_families is None:
            ids = set(all_ids)
        else:
            ids = {ind for fam in allowed_families for ind in indicators_by_family.get(fam, ())}
        ids.update(i for i in _C2_HYPOTHESIS_EXTRA_IDS.get(hyp, ()) if i in all_ids)
        ids -= _DIRECTIONAL_POOL_EXCLUDED_IDS.get(hyp, frozenset())
        pool[hyp] = tuple(sorted(ids))
    return MappingProxyType(pool)


# D276 (v33): vol_event regime-gate EMISSION exclusions — see the WHY at the
# use site in `_build_regime_pool`.
_VOL_EVENT_REGIME_EXCLUDED_IDS: frozenset[str] = frozenset({"pre_earnings_setup"})

# D278 (v34): regime-gate EMISSION exclusions applied to EVERY hypothesis's
# pool. gamma_flip_distance_pct is dead as a gate at census scale — 12,088
# uses 07-01→07-15, 0.1% component rate, 79% WF=0.0 (~1/100th of the healthy
# gates), in every pairing (Crucible census #2 §3; supersedes v33's narrower
# assumption that single-gated cells were alive). Consistent with their older
# finding that chain-derived gates are only coherent on the reference
# underlying. EMISSION-side only: the R1/R2 predicates still accept it (the
# D107 admission lineage stays valid on re-validation), and its vol_event
# DIRECTIONAL use is untouched (C2 dealer family — the census §5 share
# question is Crucible's open adjudication). Re-admission = a deliberate
# bump on new evidence, never a pool-rebuild side effect.
_REGIME_GATE_GLOBALLY_EXCLUDED_IDS: frozenset[str] = frozenset({"gamma_flip_distance_pct"})


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
    excludes ``single_name_only_ids`` from its pool — since D125 (v16) that
    set is flag-derived (`rank_excluded_indicator_ids`: the dealer family +
    every `NOT rank_per_name_coherent AND NOT market_wide_by_design` id),
    replacing the v13-v15 explicit sets. Single-name hypotheses keep their
    full pools: the per-name decoupling only exists on Crucible's universe
    paths. The sampler enforces §3.5 C4 (regime disjoint from directional)
    at sample time.
    """
    pool: dict[str, tuple[str, ...]] = {}
    for hyp in _HYPOTHESES:
        if hyp == "trend_continuation":
            pool[hyp] = tuple(sorted(set(_R2_TREND_CONTINUATION_REGIME_INDICATORS) & registry_ids))
        elif hyp == "mean_reversion":
            # D107 (v11): gamma_flip_distance_pct joins iv_rank as an R1 regime gate
            # (long-gamma / ranging). D150 (v20): hurst (mean-reverting H<0.5 side)
            # joins as a third ranging gate — the purest ranging signal. D167 (v22):
            # rv_rank (cheap realized vol) joins as a fourth gate — Crucible-validated
            # as independent of and dominant over hurst; rank-coherent (works on both
            # MR's confluence and rank genomes, unlike the chain-reading iv_rank).
            # D254 (v24): vol_regime (discrete vol tercile, gated <2) joins as a fifth
            # gate — the xsect-MR backtest champion (+0.244 CPCV-p25 vs rv_rank in 6/6).
            # D265 (v28): realized_vol (ABSOLUTE annualized RV, 0.15-0.30 sweep) joins
            # as a sixth — the systematic-spike complement to the rv_rank percentile,
            # which normalizes regime-wide (FORGE_mr_absolute_vol_gate_request). C1
            # keeps it mutually exclusive with rv_rank/vol_regime (same family) and
            # with the vol_target chain (the sampler's chain-family guard).
            # D266 (v29): market_realized_vol joins as a seventh — the MARKET-level
            # absolute-RV gate (family macro, market-wide; Crucible's preferred
            # variant, sweep bounds translating 1:1 with their rv21 ledger tag).
            pool[hyp] = tuple(
                sorted(
                    {
                        _R1_IV_RANK_INDICATOR,
                        _R1_GAMMA_REGIME_INDICATOR,
                        _R1_HURST_REGIME_INDICATOR,
                        _R1_RV_RANK_REGIME_INDICATOR,
                        _R1_VOL_REGIME_INDICATOR,
                        _R1_REALIZED_VOL_REGIME_INDICATOR,
                        _R1_MARKET_REALIZED_VOL_REGIME_INDICATOR,
                    }
                    & registry_ids
                )
            )
        elif hyp == "volatility_event":
            # D276 (v33): pre_earnings_setup retired from EMISSION (~450
            # configs/wk at 91-100% structurally dead — the composed quiet-RV
            # pre-earnings window opens a few days per name-quarter, and ANDed
            # with any directional threshold it starves below the OOS trade
            # floor; ve conversion 0.1%). The R3 predicate still ACCEPTS it
            # (hard rule #1 — validity of the submitted lineage unchanged);
            # re-admission needs a Crucible-measured window parameter that
            # opens the gate to a usable co-fire rate.
            pool[hyp] = tuple(
                sorted(
                    (set(_R3_EVENT_PROXIMITY_INDICATORS) & registry_ids)
                    - _VOL_EVENT_REGIME_EXCLUDED_IDS
                )
            )
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
    # D278 (v34): the global regime-gate exclusions apply to EVERY pool after
    # the per-hypothesis build — one application point so a future pool
    # rebuild cannot silently re-admit a retired gate (see the constant's WHY).
    return MappingProxyType(
        {
            hyp: tuple(i for i in ids if i not in _REGIME_GATE_GLOBALLY_EXCLUDED_IDS)
            for hyp, ids in pool.items()
        }
    )


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
