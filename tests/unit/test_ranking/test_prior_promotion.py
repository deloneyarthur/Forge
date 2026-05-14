"""Tests for ``forge.ranking.prior_promotion``.

§6.2 prior_promotion_proximity_score: max Jaccard overlap of a
candidate's signal IDs vs each previously-promoted config's signal IDs.

Phase 4 D023/D1.a — empty promoted list → 0.0; identical signal set → 1.0;
disjoint → 0.0. The metric mirrors the §5.3.5 novelty filter's set
construction so the pipeline stays coherent.
"""

from __future__ import annotations

import pytest
from crucible_contracts import StrategyConfig

from forge.ranking.prior_promotion import compute_prior_promotion_proximity
from tests.fixtures.strategy_configs import minimal_strategy_config


def _two_signal_config(
    *,
    name: str,
    directional_id: str,
    regime_id: str,
) -> StrategyConfig:
    """Build a minimal config with two named signals."""
    from crucible_contracts import SignalSpec

    cfg = minimal_strategy_config()
    # Phase 5 D024/D10: vary `params.key` with the id so content_key
    # tracks the test's id-based intent under the new similarity scheme.
    return cfg.model_copy(
        update={
            "name": name,
            "signals": (
                SignalSpec(
                    id=directional_id,
                    type="threshold",
                    role="directional",
                    indicators=("rsi_2",),
                    params={"threshold": 30.0, "key": directional_id},
                ),
                SignalSpec(
                    id=regime_id,
                    type="threshold",
                    role="regime_filter",
                    indicators=("iv_rank",),
                    params={"threshold": 50.0, "key": regime_id},
                ),
            ),
        },
    )


# ---------------------------------------------------------------------------
# Happy path — empty promoted list
# ---------------------------------------------------------------------------


def test_empty_promoted_list_returns_zero() -> None:
    """No promoted history yet → no proximity signal — week 1 batches
    pass through the §6.2 0.10 weight as a contribution of 0.0."""
    candidate = minimal_strategy_config()
    score = compute_prior_promotion_proximity(candidate, ())
    assert score == 0.0


# ---------------------------------------------------------------------------
# Identity — same signals → 1.0
# ---------------------------------------------------------------------------


def test_identical_signal_set_returns_one() -> None:
    candidate = _two_signal_config(name="c1", directional_id="rsi_dir", regime_id="iv_rg")
    promoted = _two_signal_config(name="p1", directional_id="rsi_dir", regime_id="iv_rg")
    score = compute_prior_promotion_proximity(candidate, (promoted,))
    assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Disjoint — fully different signals → 0.0
# ---------------------------------------------------------------------------


def test_disjoint_signal_sets_return_zero() -> None:
    candidate = _two_signal_config(name="c", directional_id="rsi_dir_a", regime_id="iv_rg_a")
    promoted = _two_signal_config(name="p", directional_id="rsi_dir_b", regime_id="iv_rg_b")
    score = compute_prior_promotion_proximity(candidate, (promoted,))
    assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Partial — one shared signal → 1/3 (1 intersection, 3 union)
# ---------------------------------------------------------------------------


def test_half_overlap_returns_jaccard() -> None:
    """Candidate signals {A, B}; promoted {A, C} → intersection=1, union=3,
    Jaccard = 1/3."""
    candidate = _two_signal_config(name="c", directional_id="A", regime_id="B")
    promoted = _two_signal_config(name="p", directional_id="A", regime_id="C")
    score = compute_prior_promotion_proximity(candidate, (promoted,))
    assert score == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# Max across promoted list
# ---------------------------------------------------------------------------


def test_returns_max_across_multiple_promoted() -> None:
    """When the candidate overlaps multiple promoted configs, the score
    is the *maximum* Jaccard, not the mean or sum."""
    candidate = _two_signal_config(name="c", directional_id="A", regime_id="B")
    # First promoted: fully matches → Jaccard=1.0
    promoted_match = _two_signal_config(name="p1", directional_id="A", regime_id="B")
    # Second promoted: disjoint → Jaccard=0.0
    promoted_other = _two_signal_config(name="p2", directional_id="X", regime_id="Y")
    score = compute_prior_promotion_proximity(candidate, (promoted_other, promoted_match))
    assert score == pytest.approx(1.0)


def test_returns_max_when_no_match_is_perfect() -> None:
    """All overlaps are partial — verify the maximum, not the last one."""
    candidate = _two_signal_config(name="c", directional_id="A", regime_id="B")
    p1 = _two_signal_config(name="p1", directional_id="A", regime_id="C")  # 1/3
    p2 = _two_signal_config(name="p2", directional_id="A", regime_id="B")  # 1.0
    p3 = _two_signal_config(name="p3", directional_id="X", regime_id="Y")  # 0.0
    score = compute_prior_promotion_proximity(candidate, (p1, p2, p3))
    assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Defensive behavior — empty signal sets shouldn't crash
# ---------------------------------------------------------------------------


def test_score_is_always_in_unit_interval() -> None:
    candidate = _two_signal_config(name="c", directional_id="A", regime_id="B")
    promoted = _two_signal_config(name="p", directional_id="A", regime_id="C")
    score = compute_prior_promotion_proximity(candidate, (promoted,))
    assert 0.0 <= score <= 1.0


def test_iterable_promoted_works() -> None:
    """Argument is `Iterable`, not just `list` — a generator should work."""
    candidate = _two_signal_config(name="c", directional_id="A", regime_id="B")
    promoted = [_two_signal_config(name="p", directional_id="A", regime_id="B")]
    gen = (p for p in promoted)
    score = compute_prior_promotion_proximity(candidate, gen)
    assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# §6.2 specifically — single shared directional vs different regime
# ---------------------------------------------------------------------------


def test_jaccard_two_directional_one_regime() -> None:
    """Candidate {Dir1, Reg1}, promoted {Dir1, Reg2}: 1 shared / 3 total = 1/3."""
    candidate = _two_signal_config(name="c", directional_id="Dir1", regime_id="Reg1")
    promoted = _two_signal_config(name="p", directional_id="Dir1", regime_id="Reg2")
    score = compute_prior_promotion_proximity(candidate, (promoted,))
    assert score == pytest.approx(1 / 3)
