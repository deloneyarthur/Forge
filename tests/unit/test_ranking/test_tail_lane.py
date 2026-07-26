"""The tail lane: a concurrent fourth submission arm ordered by a DIFFERENT objective.

WHY A CONCURRENT ARM AND NOT A SWITCH (prereg `8cfe95f4a6e9`). Crucible's observation from
the Q59 fix: `k5_share` read at +5.09 sigma because it was a **concurrent arm split**, not a
tuned constant — "concurrency is what makes drift cancel". Their own instrument has a drift
floor where bootstrap SEs understate across-window variation by 1.3-2.1x and do NOT shrink
with n, so a before/after comparison across time is not readable at any sample size. Two
arms in the SAME batches is.

So the tail lane takes slots from the merit lane and runs beside it, rather than replacing
the ranker. The incumbent arm is the control; both are scored on the same batches.

Flag-off (`tail_n == 0` or no scorer) must be byte-identical — the daemon path is shared.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from types import MappingProxyType

from crucible_contracts import SignalSpec, StrategyConfig

from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking import rank_batch_with_exploration
from forge.ranking.scorer import Ranker
from forge.ranking.types import RankerWeights
from tests.fixtures.strategy_configs import minimal_strategy_config

_NOW = datetime(2026, 7, 26, tzinfo=UTC)


def _report(name: str, *, hypothesis: str = "mean_reversion") -> PreFilterReport:
    # Structurally DISTINCT signal ids per config: the diversifier penalises Jaccard
    # overlap, so identical configs would collapse to a near-zero score after the first
    # pick and the selection would be driven by the penalty rather than by the scorer
    # under test.
    cfg = minimal_strategy_config(
        name=name,
        hypothesis=hypothesis,
        signals=(
            SignalSpec(
                id=f"{name}_directional",
                type="threshold",
                role="directional",
                indicators=(f"ind_{name}",),
                params={"threshold": 30.0, "key": name},
            ),
        ),
    )
    return PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=MappingProxyType(
            {
                name: FilterResult(passed=True, score=0.5)
                for name in (
                    "signal_density",
                    "novelty",
                    "regime_exposure",
                    "permutation_test",
                )
            }
        ),
        diagnostic_notes=(),
    )


def _reports(n: int) -> list[PreFilterReport]:
    return [_report(f"cfg{i:03d}") for i in range(n)]


def _ranker() -> Ranker:
    return Ranker(
        weights=RankerWeights(
            signal_density=0.30,
            novelty=0.25,
            regime_diversity=0.20,
            permutation_test=0.15,
            prior_promotion_proximity=0.10,
        )
    )


def _kwargs(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "promoted_strategies": (),
        "holdout_n": 0,
        "rng": random.Random(7),
    }
    base.update(over)
    return base


def test_flag_off_is_byte_identical_and_returns_an_empty_tail() -> None:
    """`tail_n=0` must leave the three existing lanes exactly as they were."""
    reports = _reports(20)
    sel_a, hold_a, young_a, tail_a = rank_batch_with_exploration(
        _ranker(), reports, n=10, **_kwargs()
    )
    sel_b, hold_b, young_b, tail_b = rank_batch_with_exploration(
        _ranker(), reports, n=10, tail_n=0, tail_scorer=lambda _c: 1.0, **_kwargs()
    )
    assert tail_a == []
    assert tail_b == []
    assert [c.report.config.config_hash for c in sel_a] == [
        c.report.config.config_hash for c in sel_b
    ]
    assert hold_a == hold_b
    assert young_a == young_b


def test_tail_lane_is_filled_by_the_tail_scorer_not_the_ranker() -> None:
    """The whole point: the tail arm orders by a different objective. Configs the
    ranker would never reach must be selectable by the tail scorer."""
    reports = _reports(20)
    # Score the LAST five configs highest for the tail objective only.
    hot = {f"cfg{i:03d}" for i in range(15, 20)}

    def tail_scorer(cfg: StrategyConfig) -> float:
        return 1.0 if cfg.name in hot else 0.0

    selected, _holdout, _young, tail = rank_batch_with_exploration(
        _ranker(), reports, n=10, tail_n=5, tail_scorer=tail_scorer, **_kwargs()
    )
    assert len(tail) == 5
    assert {c.report.config.name for c in tail} <= hot
    # Disjoint arms — a config is in exactly one lane, so the arm split is readable.
    assert not (
        {c.report.config.config_hash for c in tail}
        & {c.report.config.config_hash for c in selected}
    )


def test_tail_slots_come_out_of_the_merit_lane_not_the_batch() -> None:
    """The lane must not inflate the batch — total stays <= n, so throughput is
    unchanged and the comparison is like-for-like."""
    reports = _reports(30)
    selected, holdout, young, tail = rank_batch_with_exploration(
        _ranker(), reports, n=12, tail_n=5, tail_scorer=lambda _c: 1.0, **_kwargs()
    )
    assert len(tail) == 5
    assert len(selected) + len(holdout) + len(young) + len(tail) <= 12
    assert len(selected) == 7


def test_holdout_stays_uniform_over_configs_neither_arm_selected() -> None:
    """The holdout is the unbiased estimand lane. It must draw from what NEITHER
    the merit arm nor the tail arm took, or it stops being uniform over
    non-selected survivors."""
    reports = _reports(30)
    selected, holdout, _young, tail = rank_batch_with_exploration(
        _ranker(),
        reports,
        n=15,
        tail_n=4,
        tail_scorer=lambda _c: 1.0,
        **_kwargs(holdout_n=3),
    )
    taken = {c.report.config.config_hash for c in selected} | {
        c.report.config.config_hash for c in tail
    }
    assert len(holdout) == 3
    assert not ({c.report.config.config_hash for c in holdout} & taken)


def test_a_short_pool_never_under_fills_the_merit_lane() -> None:
    """If the tail scorer can only fill part of its quota the merit lane keeps the
    rest — a starved tail arm must not cost throughput."""
    reports = _reports(6)
    selected, _holdout, _young, tail = rank_batch_with_exploration(
        _ranker(), reports, n=6, tail_n=4, tail_scorer=lambda _c: 1.0, **_kwargs()
    )
    assert len(selected) + len(tail) == 6


def test_no_scorer_means_no_tail_lane_even_with_slots_requested() -> None:
    """A missing artifact must degrade to the incumbent, never to an empty batch."""
    reports = _reports(20)
    selected, _holdout, _young, tail = rank_batch_with_exploration(
        _ranker(), reports, n=10, tail_n=5, tail_scorer=None, **_kwargs()
    )
    assert tail == []
    assert len(selected) == 10
