"""Tests for ``forge.ranking.queue.rank_batch``.

End-to-end orchestration: score every passed `PreFilterReport` via the
`Ranker` + `compute_prior_promotion_proximity`, then run §6.3 greedy
diversification to pick `n`. Mirrors how `forge run` will use it.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest
from crucible_contracts import SignalSpec, StrategyConfig

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.queue import rank_batch
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
    signals = (
        SignalSpec(
            id=signal_ids[0],
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"threshold": 30.0},
        ),
        *tuple(
            SignalSpec(
                id=sid,
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0},
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
