"""§T2 regime-complement supply metric (shadow / telemetry-only).

Pins the regime-bet classifier roll-up (grounded in C2 / R1 / R2 / R3 / D107),
the per-batch supply tally over the submitted batch vs the passed pool, and the
`regime_supply:` journal line — the grep contract the EOD reads depend on.
"""

from __future__ import annotations

import pytest
from crucible_contracts import SignalSpec

from forge.ranking.regime_supply import (
    REGIME_BET_CLASSES,
    classify_regime_bet,
    compute_regime_complement_supply,
)
from tests.fixtures.strategy_configs import minimal_strategy_config


def test_trend_continuation_is_the_trending_dominant_sleeve() -> None:
    bet = classify_regime_bet(minimal_strategy_config(hypothesis="trend_continuation"))
    assert bet.bet_class == "trending_dominant"


def test_mean_reversion_is_the_ranging_complement() -> None:
    # R1/D107: long-gamma / low-vol / ranging payer — the default fixture hypothesis.
    bet = classify_regime_bet(minimal_strategy_config(hypothesis="mean_reversion"))
    assert bet.bet_class == "ranging_complement"


def test_tail_hedge_is_the_bear_complement() -> None:
    bet = classify_regime_bet(minimal_strategy_config(hypothesis="tail_hedge"))
    assert bet.bet_class == "bear_complement"


@pytest.mark.parametrize(
    "hypothesis",
    ["volatility_event", "relative_value", "regime_arbitrage", "event_momentum"],
)
def test_non_bear_ranging_hypotheses_are_other(hypothesis: str) -> None:
    # Honestly un-classified rather than force-fit into a bear/ranging payoff.
    bet = classify_regime_bet(minimal_strategy_config(hypothesis=hypothesis))
    assert bet.bet_class == "other"


def test_classify_captures_the_gate_op_cell_key() -> None:
    # The finer (hypothesis x regime_gate x op) cell the future T2 floor reserves on.
    config = minimal_strategy_config(
        hypothesis="mean_reversion",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
                params={"period": 2, "threshold": 30.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("gamma_flip_distance_pct",),
                params={"threshold": 0.0, "op": "<"},
            ),
        ),
    )
    bet = classify_regime_bet(config)
    assert bet.hypothesis == "mean_reversion"
    assert bet.regime_gate_id == "gamma_flip_distance_pct"
    assert bet.op == "<"


def test_op_is_none_when_gate_has_no_op_param() -> None:
    # Default fixture regime gate carries only a threshold — op absent, not crashed.
    bet = classify_regime_bet(minimal_strategy_config())
    assert bet.op is None
    assert bet.regime_gate_id == "iv_rank"


def test_supply_tally_counts_and_complement_share() -> None:
    selected = [
        minimal_strategy_config(hypothesis="trend_continuation"),
        minimal_strategy_config(hypothesis="trend_continuation"),
        minimal_strategy_config(hypothesis="trend_continuation"),
        minimal_strategy_config(hypothesis="mean_reversion"),
        minimal_strategy_config(hypothesis="tail_hedge"),
        minimal_strategy_config(hypothesis="volatility_event"),
    ]
    supply = compute_regime_complement_supply(selected, selected)

    assert supply.selected["trending_dominant"] == 3
    assert supply.selected["ranging_complement"] == 1
    assert supply.selected["bear_complement"] == 1
    assert supply.selected["other"] == 1
    assert supply.selected_total == 6
    # complement = ranging + bear = 2 of 6.
    assert supply.complement_selected == 2


def test_pool_and_selected_are_counted_separately() -> None:
    selected = [minimal_strategy_config(hypothesis="trend_continuation")]
    pool = [
        minimal_strategy_config(hypothesis="trend_continuation"),
        minimal_strategy_config(hypothesis="mean_reversion"),
        minimal_strategy_config(hypothesis="tail_hedge"),
    ]
    supply = compute_regime_complement_supply(selected, pool)

    assert supply.selected_total == 1
    assert supply.complement_selected == 0
    # The pool (the reservable ceiling) carries complement the batch did not.
    assert supply.pool_total == 3
    assert supply.complement_pool == 2


def test_empty_inputs_are_zero_with_no_division_error() -> None:
    supply = compute_regime_complement_supply([], [])
    assert supply.selected_total == 0
    assert supply.pool_total == 0
    assert supply.complement_selected == 0
    assert all(supply.selected[cls] == 0 for cls in REGIME_BET_CLASSES)
    # summary_line must not raise on an empty batch (0.0% not ZeroDivisionError).
    line = supply.summary_line()
    assert "0.0%" in line


def test_summary_line_is_the_greppable_journal_contract() -> None:
    selected = [
        minimal_strategy_config(hypothesis="trend_continuation"),
        minimal_strategy_config(hypothesis="mean_reversion"),
    ]
    pool = [
        *selected,
        minimal_strategy_config(hypothesis="tail_hedge"),
        minimal_strategy_config(hypothesis="volatility_event"),
    ]
    line = compute_regime_complement_supply(selected, pool).summary_line()

    assert line.startswith("regime_supply:")
    assert "complement(ranging+bear)" in line
    # bear is called out explicitly (the load-bearing 0 for the current stream).
    assert "bear selected 0 pool 1" in line
    # per-cell selected/pool breakdown present for re-bucketing from the journal.
    assert "trending=1/1" in line
    assert "ranging=1/1" in line


def test_metric_is_pure_deterministic_and_non_mutating() -> None:
    # Daemon-inert rests on this being a pure tally: same inputs -> identical
    # result, inputs untouched (the loop logs the line and threads it nowhere).
    selected = [
        minimal_strategy_config(hypothesis="trend_continuation"),
        minimal_strategy_config(hypothesis="tail_hedge"),
    ]
    pool = list(selected)
    first = compute_regime_complement_supply(selected, pool)
    second = compute_regime_complement_supply(selected, pool)
    assert first.selected == second.selected
    assert first.pool == second.pool
    assert len(selected) == 2  # inputs unchanged
    assert len(pool) == 2
