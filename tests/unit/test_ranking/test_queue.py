"""Tests for ``forge.ranking.queue.rank_batch``.

End-to-end orchestration: score every passed `PreFilterReport` via the
`Ranker` + `compute_prior_promotion_proximity`, then run §6.3 greedy
diversification to pick `n`. Mirrors how `forge run` will use it.
"""

from __future__ import annotations

import math
from types import MappingProxyType

import pytest
from crucible_contracts import SignalSpec, StrategyConfig

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.model import gate_tail_prior, gate_tail_rank_score
from forge.ranking.queue import (
    _PRODUCTION_FLOOR_EXEMPT_HYPOTHESES,
    _PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS,
    rank_batch,
)
from forge.ranking.scorer import Ranker
from forge.ranking.types import RankedCandidate, RankerWeights
from tests.fixtures.strategy_configs import minimal_strategy_config


def _default_weights() -> RankerWeights:
    return RankerWeights(
        signal_density=0.30,
        novelty=0.25,
        regime_diversity=0.20,
        permutation_test=0.15,
        prior_promotion_proximity=0.10,
    )


def _named_config(name: str, signal_ids: tuple[str, ...]) -> StrategyConfig:
    if not signal_ids:
        msg = "_named_config: need at least one signal"
        raise ValueError(msg)
    # Phase 5 D024/D10: vary params.key by id so the test's id-based
    # intent maps to distinct content_keys under the new similarity scheme.
    signals = (
        SignalSpec(
            id=signal_ids[0],
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"threshold": 30.0, "key": signal_ids[0]},
        ),
        *tuple(
            SignalSpec(
                id=sid,
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0, "key": sid},
            )
            for sid in signal_ids[1:]
        ),
    )
    return minimal_strategy_config().model_copy(update={"name": name, "signals": signals})


def _report(
    name: str,
    *,
    signals: tuple[str, ...],
    signal_density: float = 1.0,
    novelty: float = 1.0,
    regime_exposure: float = 1.0,
    permutation_test: float = 1.0,
    passed: bool = True,
) -> PreFilterReport:
    return PreFilterReport(
        config=_named_config(name, signals),
        passed=passed,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "resource_feasibility": FilterResult(passed=True, score=1.0),
                "signal_density": FilterResult(passed=True, score=signal_density),
                "expected_trades": FilterResult(passed=True, score=1.0),
                "novelty": FilterResult(passed=True, score=novelty),
                "regime_exposure": FilterResult(passed=True, score=regime_exposure),
                "permutation_test": FilterResult(passed=True, score=permutation_test),
            }
        ),
        diagnostic_notes=(),
        composite_score=None,
    )


# ---------------------------------------------------------------------------
# Boundary
# ---------------------------------------------------------------------------


def test_empty_reports_returns_empty() -> None:
    r = Ranker(weights=_default_weights())
    out = rank_batch(r, (), promoted_strategies=(), n=10)
    assert out == []


def test_n_zero_returns_empty() -> None:
    r = Ranker(weights=_default_weights())
    out = rank_batch(
        r,
        (_report("a", signals=("X",)),),
        promoted_strategies=(),
        n=0,
    )
    assert out == []


# ---------------------------------------------------------------------------
# P1.1 — gate-tail hard-gate ordering (shadow↔production parity)
# ---------------------------------------------------------------------------

_GATE_TAIL_FLOOR = 0.02


def _tnorm(t: float) -> float:
    """Any strictly-increasing map into (0,1) — stands in for robustness_tail_norm, which
    is monotone in the raw tail prediction the shadow ranks by."""
    return 1.0 / (1.0 + math.exp(-t))


def test_gate_tail_ordering_hard_gates_and_matches_shadow() -> None:
    # (name, P(component), tail_pred). Disjoint signals -> jaccard 0 -> the diversifier applies
    # no penalty, so rank_batch's output order is exactly the composite order.
    specs = [
        ("hi_elig", 0.50, 2.0),  # eligible, highest tail
        ("mid_elig", 0.30, 0.5),  # eligible, mid tail
        ("lo_elig", 0.10, -1.0),  # eligible, low tail
        ("hi_inelig", 0.005, 3.0),  # INELIGIBLE (P<floor) but very high tail — the soft-gate trap
        ("lo_inelig", 0.001, -2.0),  # ineligible, low tail
    ]
    p_of = {n: p for n, p, _ in specs}
    t_of = {n: t for n, _, t in specs}
    reports = tuple(_report(n, signals=(n.upper(),)) for n, _, _ in specs)

    def scorer(cfg: StrategyConfig) -> float:
        return gate_tail_prior(p_of[cfg.name], _tnorm(t_of[cfg.name]), p_floor=_GATE_TAIL_FLOOR)

    ranked = rank_batch(
        Ranker(weights=_default_weights()),
        reports,
        promoted_strategies=(),
        n=len(specs),
        verdict_scorer=scorer,
        gate_tail_ordering=True,
    )
    prod_order = [c.report.config.name for c in ranked]
    eligible = {"hi_elig", "mid_elig", "lo_elig"}

    # 1. HARD gate: every eligible outranks every ineligible (the whole fidelity fix).
    assert max(prod_order.index(n) for n in eligible) < min(
        prod_order.index(n) for n in prod_order if n not in eligible
    )
    # 2. The high-tail INELIGIBLE — which a soft blend could float to the top — is gated out.
    assert prod_order[0] == "hi_elig"
    assert "hi_inelig" not in prod_order[: len(eligible)]
    # 3. Ineligible composites pin to 0.0 (the diversifier-proof hard-gate fixed point).
    for c in ranked:
        if c.report.config.name not in eligible:
            assert c.composite_score == 0.0
    # 4. PARITY: eligible order == the shadow's gate_tail_rank_score order (same inputs).
    shadow_order = [
        n
        for n, _, _ in sorted(
            specs,
            key=lambda s: gate_tail_rank_score(s[1], s[2], p_floor=_GATE_TAIL_FLOOR),
            reverse=True,
        )
    ]
    assert [n for n in prod_order if n in eligible] == [n for n in shadow_order if n in eligible]


def test_gate_tail_ordering_off_keeps_the_blend() -> None:
    # Default (False) is byte-identical: composite = the §6.2 blend, not the raw prior.
    r = Ranker(weights=_default_weights())
    report = _report("x", signals=("X",), signal_density=0.8)

    def scorer(_cfg: StrategyConfig) -> float:
        return 0.4

    off = rank_batch(r, (report,), promoted_strategies=(), n=1, verdict_scorer=scorer)
    assert off[0].composite_score == pytest.approx(r.score(report, 0.4))
    assert off[0].composite_score != pytest.approx(0.4)  # the blend is not the raw prior

    on = rank_batch(
        r, (report,), promoted_strategies=(), n=1, verdict_scorer=scorer, gate_tail_ordering=True
    )
    assert on[0].composite_score == pytest.approx(0.4)  # gate-tail: composite IS the prior


# ---------------------------------------------------------------------------
# Filters short-circuited (passed=False) are skipped
# ---------------------------------------------------------------------------


def test_failed_reports_are_filtered_out() -> None:
    r = Ranker(weights=_default_weights())
    out = rank_batch(
        r,
        (
            _report("good", signals=("X",)),
            _report("bad", signals=("Y",), passed=False),
        ),
        promoted_strategies=(),
        n=5,
    )
    assert len(out) == 1
    assert out[0].report.config.name == "good"


# ---------------------------------------------------------------------------
# Returns RankedCandidates with composite_score populated
# ---------------------------------------------------------------------------


def test_each_candidate_has_composite_score_set() -> None:
    r = Ranker(weights=_default_weights())
    out = rank_batch(
        r,
        (
            _report(
                "a",
                signals=("X",),
                signal_density=0.5,
                novelty=0.5,
                regime_exposure=0.5,
                permutation_test=0.5,
            ),
        ),
        promoted_strategies=(),
        n=5,
    )
    assert len(out) == 1
    # Composite = 0.30*0.5 + 0.25*0.5 + 0.20*0.5 + 0.15*0.5 + 0.10*0
    # = 0.5 * 0.90 = 0.45 (with prior_promotion_proximity=0.0 since
    # promoted_strategies is empty).
    assert out[0].composite_score == pytest.approx(0.45)
    assert out[0].prior_promotion_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Prior promotion influences the score
# ---------------------------------------------------------------------------


def test_prior_promotion_lifts_matching_candidate() -> None:
    """A candidate that shares signals with a promoted strategy should
    score higher than an otherwise-identical candidate that doesn't."""
    r = Ranker(weights=_default_weights())
    promoted = _named_config("promoted", ("X", "Y"))
    matching = _report(
        "match",
        signals=("X", "Y"),
        signal_density=0.5,
        novelty=0.5,
        regime_exposure=0.5,
        permutation_test=0.5,
    )
    non_matching = _report(
        "non_match",
        signals=("A", "B"),
        signal_density=0.5,
        novelty=0.5,
        regime_exposure=0.5,
        permutation_test=0.5,
    )
    out = rank_batch(
        r,
        (matching, non_matching),
        promoted_strategies=(promoted,),
        n=2,
    )
    by_name = {c.report.config.name: c for c in out}
    assert by_name["match"].composite_score > by_name["non_match"].composite_score
    assert by_name["match"].prior_promotion_score == pytest.approx(1.0)
    assert by_name["non_match"].prior_promotion_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Diversification kicks in: near-duplicate gets demoted
# ---------------------------------------------------------------------------


def test_near_duplicate_loses_second_slot() -> None:
    r = Ranker(weights=_default_weights())
    top = _report("top", signals=("X", "Y"))
    twin = _report("twin", signals=("X", "Y"))
    different = _report("different", signals=("A", "B"))
    out = rank_batch(r, (top, twin, different), promoted_strategies=(), n=2)
    names = [c.report.config.name for c in out]
    # `top` first (all four filter scores = 1.0, prior = 0); then `different`
    # because `twin` gets a 100% penalty against `top`. Tie-breaking on
    # the first pick is by iteration order — `top` arrives first.
    assert names == ["top", "different"]


# ---------------------------------------------------------------------------
# Return shape: every element is a RankedCandidate
# ---------------------------------------------------------------------------


def test_returns_ranked_candidates() -> None:
    r = Ranker(weights=_default_weights())
    out = rank_batch(
        r,
        (_report("a", signals=("X",)),),
        promoted_strategies=(),
        n=1,
    )
    assert all(isinstance(c, RankedCandidate) for c in out)


# ---------------------------------------------------------------------------
# D149 — F3 wiring: prior_promotion_proximity := P(component) via verdict_scorer.
# When a scorer is injected it REPLACES the Jaccard prior term; None falls back to
# the legacy Jaccard prior (the kill-switch path).
# ---------------------------------------------------------------------------


def test_rank_batch_verdict_scorer_drives_the_prior() -> None:

    ranker = Ranker(weights=_default_weights())
    # Two passing reports, identical filter scores -> composite differs only via the
    # prior term. The verdict scorer makes "b" the high-P(component) pick.
    reports = [_report("a", signals=("sa1", "sa2")), _report("b", signals=("sb1", "sb2"))]
    p_component = {"a": 0.0, "b": 1.0}

    def verdict_scorer(config: StrategyConfig) -> float:
        return p_component[config.name]

    out = rank_batch(ranker, reports, promoted_strategies=(), n=2, verdict_scorer=verdict_scorer)
    assert [c.report.config.name for c in out] == ["b", "a"]  # the scorer drives order
    by_name = {c.report.config.name: c for c in out}
    # prior_promotion_score now reflects P(component), not Jaccard(=0 with no promotions)
    assert by_name["b"].prior_promotion_score == pytest.approx(1.0)
    assert by_name["a"].prior_promotion_score == pytest.approx(0.0)


def test_rank_batch_verdict_scorer_none_is_legacy_jaccard() -> None:
    """The kill-switch path: verdict_scorer=None reproduces the legacy Jaccard prior
    (0.0 with no promotions) byte-for-byte."""
    ranker = Ranker(weights=_default_weights())
    reports = [_report(f"c{i}", signals=(f"s{i}a", f"s{i}b")) for i in range(4)]
    legacy = rank_batch(ranker, reports, promoted_strategies=(), n=4)
    explicit_none = rank_batch(ranker, reports, promoted_strategies=(), n=4, verdict_scorer=None)
    assert [c.report.config.name for c in legacy] == [c.report.config.name for c in explicit_none]
    assert all(c.prior_promotion_score == 0.0 for c in explicit_none)


# ---------------------------------------------------------------------------
# Determinism: same inputs -> same selection order
# ---------------------------------------------------------------------------


def test_deterministic_for_same_inputs() -> None:
    r = Ranker(weights=_default_weights())
    reports = tuple(
        _report(f"r{i}", signals=(f"sig_{i}",), signal_density=0.5 + i * 0.05) for i in range(5)
    )
    a = rank_batch(r, reports, promoted_strategies=(), n=3)
    b = rank_batch(r, reports, promoted_strategies=(), n=3)
    assert [c.report.config.name for c in a] == [c.report.config.name for c in b]


# ---------------------------------------------------------------------------
# n > pool -> returns all passed candidates
# ---------------------------------------------------------------------------


def test_n_above_pool_returns_all_passed() -> None:
    r = Ranker(weights=_default_weights())
    reports = (
        _report("a", signals=("X",)),
        _report("b", signals=("Y",), passed=False),
        _report("c", signals=("Z",)),
    )
    out = rank_batch(r, reports, promoted_strategies=(), n=100)
    assert {c.report.config.name for c in out} == {"a", "c"}


def test_rank_batch_forwards_mature_arms_to_the_arm_floor() -> None:
    """D136 — `mature_arms` reaches the diversifier: a young-arm survivor is
    selected despite being outscored when the floor is on, and the legacy
    selection is unchanged when it is None."""
    ranker = Ranker(weights=_default_weights())
    incumbents = [_report(f"m{i}", signals=(f"s{i}", f"g{i}")) for i in range(12)]
    # The incumbents' configs carry (directional, rsi_2) + (regime_filter,
    # iv_rank) per _named_config; the young report swaps its directional
    # indicator to a never-seen arm and zeroes every score component.
    young_cfg = minimal_strategy_config(
        name="young",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("iv_term_slope",),
                params={"threshold": 0.02, "key": "young"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0, "key": "young"},
            ),
        ),
    )
    young_report = PreFilterReport(
        config=young_cfg,
        passed=True,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "resource_feasibility": FilterResult(passed=True, score=1.0),
                "signal_density": FilterResult(passed=True, score=0.0),
                "expected_trades": FilterResult(passed=True, score=1.0),
                "novelty": FilterResult(passed=True, score=0.0),
                "regime_exposure": FilterResult(passed=True, score=0.0),
                "permutation_test": FilterResult(passed=True, score=0.0),
            }
        ),
        diagnostic_notes=(),
        composite_score=None,
    )
    reports = [*incumbents, young_report]
    mature = frozenset({("directional", "rsi_2"), ("regime_filter", "iv_rank")})
    floored = rank_batch(ranker, reports, promoted_strategies=(), n=10, mature_arms=mature)
    assert "young" in [c.report.config.name for c in floored]
    legacy = rank_batch(ranker, reports, promoted_strategies=(), n=10)
    assert "young" not in [c.report.config.name for c in legacy]


def test_rank_batch_exempts_relative_value_from_the_d103_floor() -> None:
    """D145 — the production floor-exemption set reaches the diversifier: a
    starved relative_value sleeve is NOT rescued by the D103 floor (its share is
    reclaimed), while the same floor still rescues it once the exemption is
    removed. Locks both the production constant and the wiring."""
    ranker = Ranker(weights=_default_weights())

    def _hyp_report(
        name: str, hypothesis: str, signals: tuple[str, ...], *, strong: bool
    ) -> PreFilterReport:
        score = 1.0 if strong else 0.0
        rep = _report(
            name,
            signals=signals,
            signal_density=score,
            novelty=score,
            regime_exposure=score,
            permutation_test=score,
        )
        cfg = rep.config.model_copy(update={"hypothesis": hypothesis})
        return PreFilterReport(
            config=cfg,
            passed=True,
            filter_results=rep.filter_results,
            diagnostic_notes=(),
            composite_score=None,
        )

    reports = [
        _hyp_report(f"mr{i}", "mean_reversion", (f"mrd{i}", f"mrr{i}"), strong=True)
        for i in range(30)
    ]
    reports += [
        _hyp_report(f"rv{i}", "relative_value", (f"rvd{i}", f"rvr{i}"), strong=False)
        for i in range(5)
    ]

    assert "relative_value" in _PRODUCTION_FLOOR_EXEMPT_HYPOTHESES
    exempt = rank_batch(
        ranker,
        reports,
        promoted_strategies=(),
        n=20,
        min_per_hypothesis=_PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS,
        floor_exempt_hypotheses=_PRODUCTION_FLOOR_EXEMPT_HYPOTHESES,
    )
    n_rv_exempt = sum(1 for c in exempt if c.report.config.hypothesis == "relative_value")
    assert n_rv_exempt == 0  # exempt -> share reclaimed by the merit-ranked mr pool

    floored = rank_batch(
        ranker,
        reports,
        promoted_strategies=(),
        n=20,
        min_per_hypothesis=_PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS,
    )
    n_rv_floored = sum(1 for c in floored if c.report.config.hypothesis == "relative_value")
    assert n_rv_floored >= 1  # rescued when NOT exempt — proves the exemption is the cause
