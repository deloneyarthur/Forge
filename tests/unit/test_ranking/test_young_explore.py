"""Tests for the young-cell explore quota (D315, Theme 2d).

The floor (D307/D312) guarantees young cells get SUBMITTED; this quota makes
them accrue UNBIASED labels faster — extra seeded-random draws from young-cell
members of the rank-non-selected pool, tagged `young_explore` so they never
pollute the two instruments built on the uniform holdout: the estimand /
ranker-vs-random A/B (prereg 61837dd2) and the campaign-audit carriage
denominator (D299). Flag-gated `FORGE_YOUNG_CELL_EXPLORE_SLOTS`, default 0 =
byte-identical.
"""

from __future__ import annotations

import random
from types import MappingProxyType

from crucible_contracts import SignalSpec

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.queue import sample_young_cell_explore
from forge.ranking.types import RankedCandidate
from tests.fixtures.strategy_configs import minimal_strategy_config


def _candidate(name: str, *, directional: str, regime: str | None) -> RankedCandidate:
    signals: tuple[SignalSpec, ...] = (
        SignalSpec(
            id=f"{name}_d",
            type="threshold",
            role="directional",
            indicators=(directional,),
            params={"threshold": 30.0, "key": f"{name}_d"},
        ),
    )
    if regime is not None:
        signals = (
            *signals,
            SignalSpec(
                id=f"{name}_r",
                type="threshold",
                role="regime_filter",
                indicators=(regime,),
                params={"threshold": 50.0, "key": f"{name}_r"},
            ),
        )
    config = minimal_strategy_config().model_copy(update={"name": name, "signals": signals})
    report = PreFilterReport(
        config=config,
        passed=True,
        # The four §6.2 ranker inputs (scorer._REQUIRED_FILTER_KEYS) so the
        # engine tests can run the real scoring path.
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "signal_density": FilterResult(passed=True, score=1.0),
                "novelty": FilterResult(passed=True, score=1.0),
                "regime_exposure": FilterResult(passed=True, score=1.0),
                "permutation_test": FilterResult(passed=True, score=1.0),
            }
        ),
        diagnostic_notes=(),
    )
    return RankedCandidate(report=report, prior_promotion_score=0.0, composite_score=0.5)


def _pool() -> list[RankedCandidate]:
    return [
        _candidate("young1", directional="hurst", regime="vix_term_slope"),
        _candidate("young2", directional="hurst", regime="vol_regime"),
        _candidate("mature1", directional="rsi_2", regime="iv_rank"),
        _candidate("bare", directional="momentum", regime=None),
    ]


_MATURE = frozenset({("rsi_2", "iv_rank")})


def test_draws_only_young_cell_members() -> None:
    picks = sample_young_cell_explore(
        _pool(), 4, random.Random(7), mature_cells=_MATURE, pinned_cells=frozenset()
    )
    names = sorted(c.report.config.name for c in picks)
    assert names == ["young1", "young2"]  # mature + bare never drawn


def test_quota_zero_or_no_maturity_data_is_inert() -> None:
    assert (
        sample_young_cell_explore(
            _pool(), 0, random.Random(7), mature_cells=_MATURE, pinned_cells=frozenset()
        )
        == []
    )
    assert (
        sample_young_cell_explore(
            _pool(), 4, random.Random(7), mature_cells=None, pinned_cells=frozenset()
        )
        == []
    )


def test_pinned_cells_excluded() -> None:
    picks = sample_young_cell_explore(
        _pool(),
        4,
        random.Random(7),
        mature_cells=_MATURE,
        pinned_cells=frozenset({("hurst", "vix_term_slope")}),
    )
    assert [c.report.config.name for c in picks] == ["young2"]


def test_draw_is_seed_deterministic() -> None:
    a = sample_young_cell_explore(
        _pool(), 1, random.Random(42), mature_cells=_MATURE, pinned_cells=frozenset()
    )
    b = sample_young_cell_explore(
        _pool(), 1, random.Random(42), mature_cells=_MATURE, pinned_cells=frozenset()
    )
    assert [c.report.config.name for c in a] == [c.report.config.name for c in b]


def test_exploration_engine_three_lanes_disjoint_and_bounded() -> None:
    """rank_batch_with_exploration: merit + holdout + young are disjoint,
    total <= n, young slots only surrendered when fillable."""
    import random as _random

    from forge.ranking import Ranker, RankerWeights
    from forge.ranking.queue import rank_batch_with_exploration

    reports = []
    for i in range(6):
        cand = _candidate(f"m{i}", directional="rsi_2", regime="iv_rank")
        reports.append(cand.report)
    for i in range(3):
        cand = _candidate(f"y{i}", directional="hurst", regime="vix_term_slope")
        reports.append(cand.report)

    ranker = Ranker(
        weights=RankerWeights(
            signal_density=0.30,
            novelty=0.25,
            regime_diversity=0.20,
            permutation_test=0.15,
            prior_promotion_proximity=0.10,
        )
    )
    selected, holdout, young = rank_batch_with_exploration(
        ranker,
        reports,
        [],
        6,
        holdout_n=1,
        rng=_random.Random(1),
        young_explore_n=2,
        young_rng=_random.Random(2),
        mature_cells=_MATURE,
    )
    all_hashes = [c.report.config.config_hash for c in [*selected, *holdout, *young]]
    assert len(all_hashes) == len(set(all_hashes))  # disjoint
    assert len(selected) + len(holdout) + len(young) <= 6
    assert len(selected) == 3  # 6 - 1 holdout - 2 young
    assert len(young) <= 2
    assert all(c.report.config.name.startswith("y") for c in young)


def test_exploration_engine_young_off_matches_holdout_form() -> None:
    """young_explore_n=0 must reproduce rank_batch_with_holdout exactly."""
    import random as _random

    from forge.ranking import Ranker, RankerWeights
    from forge.ranking.queue import rank_batch_with_exploration, rank_batch_with_holdout

    reports = [_candidate(f"m{i}", directional="rsi_2", regime="iv_rank").report for i in range(5)]
    ranker = Ranker(
        weights=RankerWeights(
            signal_density=0.30,
            novelty=0.25,
            regime_diversity=0.20,
            permutation_test=0.15,
            prior_promotion_proximity=0.10,
        )
    )
    s1, h1 = rank_batch_with_holdout(ranker, reports, [], 4, holdout_n=1, rng=_random.Random(9))
    s2, h2, y2 = rank_batch_with_exploration(
        ranker, reports, [], 4, holdout_n=1, rng=_random.Random(9), young_explore_n=0
    )
    assert [c.report.config.config_hash for c in s1] == [c.report.config.config_hash for c in s2]
    assert [c.report.config.config_hash for c in h1] == [c.report.config.config_hash for c in h2]
    assert y2 == []
