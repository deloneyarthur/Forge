"""Tests for ``forge.ranking.scorer.Ranker``.

§6.2 weighted composite: 0.30·signal_density + 0.25·novelty +
0.20·regime_diversity + 0.15·permutation_test +
0.10·prior_promotion_proximity. The weights live on the Ranker
(D023/D2.a — same pattern as Phase 3 Calibration).

Note on naming: §6.2 calls the third weight "regime_diversity" but
Phase 3 ships the filter as ``regime_exposure``. The Ranker maps the
weight to the filter score (§5.3.6 == §6.2 "regime_diversity"); this
test surfaces the mapping.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.scorer import Ranker
from forge.ranking.types import RankerWeights
from tests.fixtures.strategy_configs import minimal_strategy_config


def _default_weights() -> RankerWeights:
    return RankerWeights(
        signal_density=0.30,
        novelty=0.25,
        regime_diversity=0.20,
        permutation_test=0.15,
        prior_promotion_proximity=0.10,
    )


def _report(
    *,
    signal_density: float = 1.0,
    novelty: float = 1.0,
    regime_exposure: float = 1.0,
    permutation_test: float = 1.0,
    extra: dict[str, FilterResult] | None = None,
) -> PreFilterReport:
    """Build a 7-filter-passed PreFilterReport. ``regime_exposure`` is the
    §5.3.6 filter name (§6.2 calls the corresponding weight ``regime_diversity``)."""
    filters: dict[str, FilterResult] = {
        "structural_redundancy": FilterResult(passed=True, score=1.0),
        "resource_feasibility": FilterResult(passed=True, score=1.0),
        "signal_density": FilterResult(passed=True, score=signal_density),
        "expected_trades": FilterResult(passed=True, score=1.0),
        "novelty": FilterResult(passed=True, score=novelty),
        "regime_exposure": FilterResult(passed=True, score=regime_exposure),
        "permutation_test": FilterResult(passed=True, score=permutation_test),
    }
    if extra is not None:
        filters.update(extra)
    return PreFilterReport(
        config=minimal_strategy_config(),
        passed=True,
        filter_results=MappingProxyType(filters),
        diagnostic_notes=(),
        composite_score=None,
    )


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


def test_all_zeros_and_zero_prior_returns_zero() -> None:
    r = Ranker(weights=_default_weights())
    score = r.score(
        _report(signal_density=0.0, novelty=0.0, regime_exposure=0.0, permutation_test=0.0),
        prior_promotion_score=0.0,
    )
    assert score == pytest.approx(0.0)


def test_all_ones_and_one_prior_returns_one() -> None:
    r = Ranker(weights=_default_weights())
    score = r.score(
        _report(signal_density=1.0, novelty=1.0, regime_exposure=1.0, permutation_test=1.0),
        prior_promotion_score=1.0,
    )
    assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Weight x component math
# ---------------------------------------------------------------------------


def test_score_is_weighted_sum() -> None:
    """Composite = 0.30·0.8 + 0.25·0.6 + 0.20·0.4 + 0.15·0.2 +
    0.10·0.5 = 0.24 + 0.15 + 0.08 + 0.03 + 0.05 = 0.55."""
    r = Ranker(weights=_default_weights())
    score = r.score(
        _report(
            signal_density=0.8,
            novelty=0.6,
            regime_exposure=0.4,
            permutation_test=0.2,
        ),
        prior_promotion_score=0.5,
    )
    expected = 0.30 * 0.8 + 0.25 * 0.6 + 0.20 * 0.4 + 0.15 * 0.2 + 0.10 * 0.5
    assert score == pytest.approx(expected)


def test_regime_diversity_weight_maps_to_regime_exposure_filter() -> None:
    """§6.2's ``regime_diversity`` weight reads ``regime_exposure`` filter
    score (Phase 3 named §5.3.6 ``regime_exposure``)."""
    w = RankerWeights(
        signal_density=0.0,
        novelty=0.0,
        regime_diversity=1.0,
        permutation_test=0.0,
        prior_promotion_proximity=0.0,
    )
    r = Ranker(weights=w)
    score = r.score(_report(regime_exposure=0.42), prior_promotion_score=0.0)
    assert score == pytest.approx(0.42)


def test_each_filter_score_contributes_only_its_weight() -> None:
    """Set only `signal_density` non-zero with weight=1.0 isolated to it,
    confirm composite equals the filter's score."""
    w = RankerWeights(
        signal_density=1.0,
        novelty=0.0,
        regime_diversity=0.0,
        permutation_test=0.0,
        prior_promotion_proximity=0.0,
    )
    r = Ranker(weights=w)
    score = r.score(_report(signal_density=0.7), prior_promotion_score=0.0)
    assert score == pytest.approx(0.7)


def test_prior_promotion_contributes_under_its_weight() -> None:
    w = RankerWeights(
        signal_density=0.0,
        novelty=0.0,
        regime_diversity=0.0,
        permutation_test=0.0,
        prior_promotion_proximity=1.0,
    )
    r = Ranker(weights=w)
    score = r.score(_report(), prior_promotion_score=0.33)
    assert score == pytest.approx(0.33)


# ---------------------------------------------------------------------------
# Composite is always in [0, 1]
# ---------------------------------------------------------------------------


def test_composite_is_clamped_to_unit_interval() -> None:
    """With well-formed inputs the math sits in [0, 1] by construction;
    this guards float-arithmetic edge cases (e.g. 0.30+0.25+...= 1.0
    sometimes drifts by 1e-17)."""
    r = Ranker(weights=_default_weights())
    score = r.score(
        _report(signal_density=1.0, novelty=1.0, regime_exposure=1.0, permutation_test=1.0),
        prior_promotion_score=1.0,
    )
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Missing filter results
# ---------------------------------------------------------------------------


def test_missing_signal_density_raises() -> None:
    r = Ranker(weights=_default_weights())
    rep = PreFilterReport(
        config=minimal_strategy_config(),
        passed=True,
        filter_results=MappingProxyType(
            {
                "novelty": FilterResult(passed=True, score=1.0),
                "regime_exposure": FilterResult(passed=True, score=1.0),
                "permutation_test": FilterResult(passed=True, score=1.0),
            }
        ),
        diagnostic_notes=(),
    )
    with pytest.raises(ValueError, match=r"signal_density"):
        r.score(rep, prior_promotion_score=0.0)


def test_missing_regime_exposure_raises() -> None:
    r = Ranker(weights=_default_weights())
    rep = PreFilterReport(
        config=minimal_strategy_config(),
        passed=True,
        filter_results=MappingProxyType(
            {
                "signal_density": FilterResult(passed=True, score=1.0),
                "novelty": FilterResult(passed=True, score=1.0),
                "permutation_test": FilterResult(passed=True, score=1.0),
            }
        ),
        diagnostic_notes=(),
    )
    with pytest.raises(ValueError, match=r"regime_exposure"):
        r.score(rep, prior_promotion_score=0.0)


# ---------------------------------------------------------------------------
# prior_promotion_score validation
# ---------------------------------------------------------------------------


def test_prior_promotion_score_rejects_negative() -> None:
    r = Ranker(weights=_default_weights())
    with pytest.raises(ValueError, match=r"prior_promotion"):
        r.score(_report(), prior_promotion_score=-0.1)


def test_prior_promotion_score_rejects_above_one() -> None:
    r = Ranker(weights=_default_weights())
    with pytest.raises(ValueError, match=r"prior_promotion"):
        r.score(_report(), prior_promotion_score=1.5)


def test_prior_promotion_score_rejects_nan() -> None:
    r = Ranker(weights=_default_weights())
    with pytest.raises(ValueError, match=r"prior_promotion"):
        r.score(_report(), prior_promotion_score=float("nan"))


# ---------------------------------------------------------------------------
# Frozenness
# ---------------------------------------------------------------------------


def test_ranker_is_frozen() -> None:
    r = Ranker(weights=_default_weights())
    with pytest.raises(Exception, match=r"cannot assign|frozen"):
        r.weights = _default_weights()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Determinism — same inputs, same output
# ---------------------------------------------------------------------------


def test_score_is_deterministic() -> None:
    r = Ranker(weights=_default_weights())
    rep = _report(signal_density=0.5, novelty=0.5, regime_exposure=0.5, permutation_test=0.5)
    a = r.score(rep, prior_promotion_score=0.5)
    b = r.score(rep, prior_promotion_score=0.5)
    assert a == b
