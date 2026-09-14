"""Structural invariants of campaign mode (plan 2026-09 §12; D406/D409).

(a) a protected cell is never admitted without a replacement campaign naming it;
(b) the weekly cap is never exceeded; (c) T2 fires only on a content change WITH
a retracted id; (d) the triggers and the gate are pure: same inputs, same
outputs, and no clock or RNG anywhere in those modules (hard rule #8 in spirit,
replayability in practice).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import forge.campaign.gate as gate_module
import forge.campaign.triggers as triggers_module
from forge.campaign.cells import cell_key
from forge.campaign.gate import challenger_gate
from forge.campaign.triggers import allocate_budgets, evaluate_triggers
from forge.campaign.types import (
    Book,
    CampaignConfig,
    CampaignSpec,
    CellKey,
    CellStats,
    TriggerInputs,
    TriggerOutcome,
)
from tests.fixtures.strategy_configs import minimal_strategy_config

_NOW = datetime(2026, 9, 13, 3, 0, tzinfo=UTC)
_CELL: CellKey = ("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")


def _inputs(**overrides: object) -> TriggerInputs:
    base: dict[str, object] = {
        "iso_week": "2026-W37",
        "designated_now": "b",
        "designated_prev": "b",
        "book_cells_now": frozenset({_CELL}),
        "book_cells_prev": frozenset({_CELL}),
        "refutation_hash_now": "h1",
        "refutation_hash_prev": "h1",
        "refutation_ids_now": frozenset({"hurst-mr-conditioner"}),
        "refutation_ids_prev": frozenset({"hurst-mr-conditioner"}),
        "registry_ids_now": frozenset({"rsi_2", "iv_rank", "hurst"}),
        "registry_ids_prev": frozenset({"rsi_2", "iv_rank", "hurst"}),
        "registry_families_now": {"rsi_2": "osc", "iv_rank": "vol", "hurst": "regime"},
        "registry_families_prev": {"rsi_2": "osc", "iv_rank": "vol", "hurst": "regime"},
        "cell_stats": {
            _CELL: CellStats(_CELL, 10, 10, 1, 0.9, _NOW),
            ("mean_reversion", "swing_mid", "named", "rsi_2", "hurst"): CellStats(
                ("mean_reversion", "swing_mid", "named", "rsi_2", "hurst"), 10, 10, 1, 1.3, _NOW
            ),
        },
        "protected": frozenset({_CELL}),
        "dead": frozenset(),
        "dark": frozenset({("trend_continuation", "swing_long", "named", "donchian", "hurst")}),
        "now": _NOW,
        "config": CampaignConfig(),
    }
    base.update(overrides)
    return TriggerInputs(**base)  # type: ignore[arg-type]


# (a) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "trigger", ["refutation_retraction", "registry_change", "basis_refresh", "exploration_floor"]
)
def test_protected_cell_never_admitted_without_replacement(trigger: str) -> None:
    challenger = minimal_strategy_config(name="challenger", underlying="QQQ")
    cell = cell_key(challenger)
    book = Book(designated_id="b", designated_at="d", legs=(), protected_cells=frozenset({cell}))
    campaign = CampaignSpec(
        trigger=trigger,  # type: ignore[arg-type]
        cells=frozenset({cell}),
        budget=10,
        reason="t",
    )
    decision = challenger_gate(
        challenger, cell, book=book, campaign=campaign, dead=frozenset(), cfg=CampaignConfig()
    )
    assert not decision.keep
    assert decision.reason == "protected_cell"


# (b) -----------------------------------------------------------------------


@given(
    cap=st.integers(min_value=1, max_value=2_000),
    budgets=st.lists(st.integers(min_value=0, max_value=5_000), min_size=5, max_size=5),
)
def test_allocation_never_exceeds_the_weekly_cap(cap: int, budgets: list[int]) -> None:
    cfg = CampaignConfig(weekly_cap=cap)
    triggers = (
        "leg_health",
        "refutation_retraction",
        "registry_change",
        "basis_refresh",
        "exploration_floor",
    )
    outcomes = tuple(
        TriggerOutcome(
            trigger=t,  # type: ignore[arg-type]
            fired=True,
            reason="t",
            campaign=CampaignSpec(
                trigger=t,  # type: ignore[arg-type]
                cells=frozenset({_CELL}),
                budget=b,
                reason="t",
            ),
        )
        for t, b in zip(triggers, budgets, strict=True)
    )
    assert sum(s.budget for s in allocate_budgets(outcomes, cfg)) <= cap


# (c) -----------------------------------------------------------------------


def test_t2_requires_both_a_content_change_and_a_retracted_id() -> None:
    hash_only = evaluate_triggers(_inputs(refutation_hash_now="h2"))[1]
    ids_only = evaluate_triggers(_inputs(refutation_ids_now=frozenset()))[1]
    both = evaluate_triggers(_inputs(refutation_hash_now="h2", refutation_ids_now=frozenset()))[1]
    assert not hash_only.fired
    assert not ids_only.fired
    assert both.fired


# (d) -----------------------------------------------------------------------


def test_triggers_are_pure_same_inputs_same_outputs() -> None:
    inputs = _inputs(designated_now="c", refutation_hash_now="h2", refutation_ids_now=frozenset())
    assert evaluate_triggers(inputs) == evaluate_triggers(inputs)


@pytest.mark.parametrize("module", [triggers_module, gate_module])
def test_decision_modules_use_no_clock_and_no_rng(module: object) -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert not re.search(r"datetime\.now|utcnow|utc_now\(|import random|\brandom\.", source)
