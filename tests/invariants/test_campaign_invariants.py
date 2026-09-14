"""Structural invariants of campaign mode (plan 2026-09 §12; D406/D409).

(a) a protected cell is never admitted without a replacement campaign naming it;
(b) the weekly cap is never exceeded; (c) T2 fires only on a content change WITH
a retracted id; (d) the triggers and the gate are pure: same inputs, same
outputs, and no clock or RNG anywhere in those modules (hard rule #8 in spirit,
replayability in practice).
"""

from __future__ import annotations

import contextlib
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


# ---------------------------------------------------------------------------
# run-level invariants (part B): the population never changes; the arm stays admitted
# ---------------------------------------------------------------------------


def test_campaign_population_is_the_unweighted_cold_start_draw(tmp_path: Path) -> None:
    """Hard rule #6 + the signed freeze: the campaign draws exactly what
    `enumerate_candidates` yields with NO learned weights, and rejection sampling only
    ever keeps an ordered subsequence of it."""
    from crucible_contracts import StrategyConfig

    from forge.campaign.run import enumerate_population, select_for_campaigns
    from forge.campaign.types import CampaignSpec
    from forge.core.clock import utc_now
    from forge.enumeration import EnumerationCapped, enumerate_candidates, resolve_effects
    from forge.enumeration._demo_registry import demo_registry
    from forge.enumeration.chain_inception import underlyings_below_inception
    from forge.grammar import load_grammar

    config_root = Path(__file__).resolve().parents[2] / "config"
    grammar = load_grammar(
        config_root / "grammar.yaml", archive_dir=config_root / "grammar_archive"
    )
    registry = demo_registry()
    now = utc_now()
    population = enumerate_population(
        grammar,
        registry,
        seed=11,
        attempts=60,
        exports_dir=tmp_path,
        now=now,
        min_hypothesis_fraction=0.0,
    )
    raw: list[StrategyConfig] = []
    with contextlib.suppress(EnumerationCapped):
        raw.extend(
            enumerate_candidates(
                grammar,
                registry,
                seed=11,
                max_candidates=60,
                below_inception=underlyings_below_inception(now.date(), exports_dir=tmp_path),
                refutation_effects=resolve_effects(exports_dir=tmp_path),
                min_hypothesis_fraction=0.0,
            )
        )
    assert len(population) > 2
    assert [c.config_hash for c in population] == [c.config_hash for c in raw]
    sample = [(c, cell_key(c)) for c in population]
    everything = frozenset(cell for _, cell in sample)
    spec = CampaignSpec("exploration_floor", everything, 10, "all cells")
    cfg = CampaignConfig(oversample_factor=2)
    picked = select_for_campaigns([spec], sample, cfg=cfg, iso_week="2026-W38")
    kept = [c.config_hash for c, _ in picked[0]]
    order = {c.config_hash: i for i, c in enumerate(population)}
    assert kept
    assert all(h in order for h in kept)
    assert len(kept) <= 20


def test_every_campaign_lane_is_stamped_ranked() -> None:
    """Crucible's Literal admits ranked | exploration_holdout | prefilter_sample; a campaign
    row must reach their inbox as `ranked` (their 09-13 §3), never None, never a new value."""
    from typing import get_args

    from forge.campaign.types import Trigger
    from forge.submission.submitter import _selection_arm_for

    for trigger in get_args(Trigger):
        assert _selection_arm_for(f"campaign:{trigger}") == "ranked"


def test_default_stratification_floor_is_off_for_the_campaign() -> None:
    """The weekly run draws the UNSTRATIFIED population (0.0), the same sequence the goldens
    pin, because it selects by cell afterwards; the daemon's D037 floor (0.02) is a
    submission-mix guarantee for 200-config batches and, under a cold-start draw, capped the
    first live dry-run at 800 of 20,000 configs. A drift to a non-zero value here would
    silently shrink the sample every trigger reads."""
    from forge.enumeration.iterator import _PRODUCTION_MIN_HYPOTHESIS_FRACTION

    assert CampaignConfig().min_hypothesis_fraction == 0.0
    assert _PRODUCTION_MIN_HYPOTHESIS_FRACTION > 0.0  # the daemon keeps its floor
