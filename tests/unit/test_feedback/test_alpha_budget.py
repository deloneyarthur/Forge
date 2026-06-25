"""Tier-1a: cumulative alpha-budget / multiple-testing ledger (pure core).

The production loop submits to Crucible's Deflated-Sharpe gate with
`search_n_trials` unset, so the gate charges `n_trials=1` and never deflates for
the breadth of Forge's search. This ledger measures the trial count the gate
*should* see and the Bailey & Lopez de Prado false-strategy hurdle it implies.
These tests pin the math + aggregation; the DB/CLI glue is tested separately.
"""

from __future__ import annotations

import itertools

import pytest

from forge.feedback.alpha_budget import (
    BatchRow,
    expected_max_sharpe,
    summarize_budget,
)


class TestExpectedMaxSharpe:
    def test_no_multiplicity_no_haircut(self) -> None:
        # 0 or 1 trial => nothing was selected among => no luck inflation.
        assert expected_max_sharpe(0) == 0.0
        assert expected_max_sharpe(1) == 0.0

    @pytest.mark.parametrize(
        ("n", "expected"),
        [
            (2, 0.5196),
            (10, 1.5746),
            (1000, 3.2563),
        ],
    )
    def test_benchmark_matches_bailey_lopez_de_prado(self, n: int, expected: float) -> None:
        # E[max] of N null trials, in cross-trial Sharpe-stdev units (sigma=1).
        assert expected_max_sharpe(n) == pytest.approx(expected, abs=5e-3)

    def test_monotonic_increasing_in_breadth(self) -> None:
        ns = [2, 5, 10, 100, 1_000, 100_000, 10_000_000]
        vals = [expected_max_sharpe(n) for n in ns]
        assert vals == sorted(vals)
        assert all(b > a for a, b in itertools.pairwise(vals))


class TestSummarizeBudget:
    def test_empty(self) -> None:
        b = summarize_budget([])
        assert b.n_batches == 0
        assert b.n_submitted == 0
        assert b.n_scored == 0
        assert b.scored_coverage == 0.0
        assert b.by_version == ()
        assert b.hurdle_submitted == 0.0
        assert b.hurdle_scored == 0.0

    def test_aggregates_and_brackets_the_trial_count(self) -> None:
        rows = [
            BatchRow(grammar_version="v21", batch_size=100, enumerated_count=10_000),
            BatchRow(grammar_version="v22", batch_size=200, enumerated_count=50_000),
            # legacy batch predating the enumerated_count column (D096):
            BatchRow(grammar_version="v22", batch_size=300, enumerated_count=None),
        ]
        b = summarize_budget(rows)
        assert b.n_batches == 3
        assert b.n_submitted == 600
        # None enumerated_count coalesces to batch_size (300): 10_000 + 50_000 + 300.
        assert b.n_scored == 60_300
        # 2 of 3 batches carry a real enumerated_count.
        assert b.scored_coverage == pytest.approx(2 / 3)
        # The breadth ceiling never falls below the submitted floor...
        assert b.n_scored >= b.n_submitted
        # ...and the search-luck hurdle from breadth strictly exceeds it.
        assert b.hurdle_scored > b.hurdle_submitted > 0.0

    def test_per_version_breakdown_uses_natural_version_order(self) -> None:
        # Lexical sort would wrongly put v22 before v9; the ledger must not.
        rows = [
            BatchRow("v22", 300, 30_000),
            BatchRow("v9", 100, 10_000),
            BatchRow("v10", 200, 20_000),
        ]
        b = summarize_budget(rows)
        assert [vb.grammar_version for vb in b.by_version] == ["v9", "v10", "v22"]
        v22 = next(vb for vb in b.by_version if vb.grammar_version == "v22")
        assert v22.n_submitted == 300
        assert v22.n_scored == 30_000
