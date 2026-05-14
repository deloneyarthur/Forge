"""Tests for ``forge.ranking.types``.

Cover construction, validation, and frozenness for the Phase 4 ranker
value types. Mirrors ``test_prefilters/test_types.py`` Phase 3 cadence.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.types import (
    DiversificationConfig,
    RankedCandidate,
    RankerConfig,
    RankerWeights,
)
from tests.fixtures.strategy_configs import minimal_strategy_config

# ---------------------------------------------------------------------------
# RankerWeights — §6.2 weights with sum==1.0 invariant
# ---------------------------------------------------------------------------


def _default_weights() -> RankerWeights:
    """§10.3 defaults — the values shipped in ``config/ranker.yaml``."""
    return RankerWeights(
        signal_density=0.30,
        novelty=0.25,
        regime_diversity=0.20,
        permutation_test=0.15,
        prior_promotion_proximity=0.10,
    )


def test_default_weights_sum_to_one() -> None:
    w = _default_weights()
    total = (
        w.signal_density
        + w.novelty
        + w.regime_diversity
        + w.permutation_test
        + w.prior_promotion_proximity
    )
    assert abs(total - 1.0) < 1e-9


def test_weights_reject_sum_less_than_one() -> None:
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        RankerWeights(
            signal_density=0.30,
            novelty=0.25,
            regime_diversity=0.20,
            permutation_test=0.15,
            prior_promotion_proximity=0.05,  # sum = 0.95
        )


def test_weights_reject_sum_greater_than_one() -> None:
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        RankerWeights(
            signal_density=0.40,
            novelty=0.25,
            regime_diversity=0.20,
            permutation_test=0.15,
            prior_promotion_proximity=0.10,  # sum = 1.10
        )


def test_weights_reject_negative_component() -> None:
    with pytest.raises(ValueError, match="must be in"):
        RankerWeights(
            signal_density=-0.10,
            novelty=0.25,
            regime_diversity=0.20,
            permutation_test=0.15,
            prior_promotion_proximity=0.50,
        )


def test_weights_reject_component_above_one() -> None:
    with pytest.raises(ValueError, match="must be in"):
        RankerWeights(
            signal_density=1.50,
            novelty=-0.20,
            regime_diversity=0.20,
            permutation_test=-0.20,
            prior_promotion_proximity=-0.30,
        )


def test_weights_reject_nan() -> None:
    with pytest.raises(ValueError, match="must be in"):
        RankerWeights(
            signal_density=float("nan"),
            novelty=0.25,
            regime_diversity=0.25,
            permutation_test=0.25,
            prior_promotion_proximity=0.25,
        )


def test_weights_reject_inf() -> None:
    with pytest.raises(ValueError, match="must be in"):
        RankerWeights(
            signal_density=float("inf"),
            novelty=0.25,
            regime_diversity=0.25,
            permutation_test=0.25,
            prior_promotion_proximity=0.25,
        )


def test_weights_are_frozen() -> None:
    w = _default_weights()
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        w.signal_density = 0.99  # type: ignore[misc]


def test_weights_accept_uniform_0_2() -> None:
    """Five equal components of 0.2 sum to 1.0 — should pass."""
    w = RankerWeights(
        signal_density=0.2,
        novelty=0.2,
        regime_diversity=0.2,
        permutation_test=0.2,
        prior_promotion_proximity=0.2,
    )
    assert w.signal_density == pytest.approx(0.2)


def test_weights_zero_component_allowed_if_sum_holds() -> None:
    """A component of 0.0 is allowed as long as the rest sum to 1.0 —
    this is what a Phase 4 deployment with no promoted history yet
    *would* look like if the operator wanted to drop the proximity
    weight entirely. (D023/D1 keeps it; this guards the shape.)"""
    w = RankerWeights(
        signal_density=0.40,
        novelty=0.30,
        regime_diversity=0.20,
        permutation_test=0.10,
        prior_promotion_proximity=0.0,
    )
    assert w.prior_promotion_proximity == 0.0


# ---------------------------------------------------------------------------
# DiversificationConfig — §6.3 method + similarity metric
# ---------------------------------------------------------------------------


def test_diversification_config_greedy_jaccard() -> None:
    dc = DiversificationConfig(method="greedy", similarity_metric="jaccard")
    assert dc.method == "greedy"
    assert dc.similarity_metric == "jaccard"


def test_diversification_config_is_frozen() -> None:
    dc = DiversificationConfig(method="greedy", similarity_metric="jaccard")
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        dc.method = "dpp"  # type: ignore[misc,assignment]


# ---------------------------------------------------------------------------
# RankerConfig — bundles weights + diversification
# ---------------------------------------------------------------------------


def test_ranker_config_bundles_weights_and_diversification() -> None:
    rc = RankerConfig(
        weights=_default_weights(),
        diversification=DiversificationConfig(method="greedy", similarity_metric="jaccard"),
    )
    assert rc.weights.signal_density == pytest.approx(0.30)
    assert rc.diversification.method == "greedy"


def test_ranker_config_is_frozen() -> None:
    rc = RankerConfig(
        weights=_default_weights(),
        diversification=DiversificationConfig(method="greedy", similarity_metric="jaccard"),
    )
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        rc.weights = _default_weights()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RankedCandidate — Phase 4 ranker output
# ---------------------------------------------------------------------------


def _passed_report() -> PreFilterReport:
    """Synthesize a Phase 3-style passed report for ranker-side tests."""
    cfg = minimal_strategy_config()
    return PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "resource_feasibility": FilterResult(passed=True, score=0.95),
                "signal_density": FilterResult(passed=True, score=0.80),
                "expected_trades": FilterResult(passed=True, score=0.70),
                "novelty": FilterResult(passed=True, score=0.90),
                "regime_exposure": FilterResult(passed=True, score=0.60),
                "permutation_test": FilterResult(passed=True, score=0.85),
            }
        ),
        diagnostic_notes=(),
        composite_score=None,
    )


def test_ranked_candidate_carries_report_and_scores() -> None:
    rc = RankedCandidate(
        report=_passed_report(),
        prior_promotion_score=0.0,
        composite_score=0.72,
    )
    assert rc.report.passed is True
    assert rc.prior_promotion_score == 0.0
    assert rc.composite_score == pytest.approx(0.72)


def test_ranked_candidate_is_frozen() -> None:
    rc = RankedCandidate(
        report=_passed_report(),
        prior_promotion_score=0.0,
        composite_score=0.72,
    )
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        rc.composite_score = 0.99  # type: ignore[misc]


def test_ranked_candidate_composite_score_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="composite_score"):
        RankedCandidate(
            report=_passed_report(),
            prior_promotion_score=0.0,
            composite_score=1.5,
        )


def test_ranked_candidate_composite_score_rejects_nan() -> None:
    with pytest.raises(ValueError, match="composite_score"):
        RankedCandidate(
            report=_passed_report(),
            prior_promotion_score=0.0,
            composite_score=float("nan"),
        )


def test_ranked_candidate_prior_promotion_score_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="prior_promotion_score"):
        RankedCandidate(
            report=_passed_report(),
            prior_promotion_score=-0.1,
            composite_score=0.5,
        )
