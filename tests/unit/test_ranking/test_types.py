"""Tests for ``forge.ranking.types``.

Cover construction, validation, and frozenness for the Phase 4 ranker
value types. Mirrors ``test_prefilters/test_types.py`` Phase 3 cadence.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.types import RankedCandidate
from tests.fixtures.strategy_configs import minimal_strategy_config

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
