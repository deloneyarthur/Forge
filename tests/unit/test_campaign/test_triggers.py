"""Tests for ``forge.campaign.triggers`` (plan 2026-09 §12.3, corrected by D409).

Five pure triggers over ``TriggerInputs``. The first run has no baseline, so
T1/T2/T3 record and do not fire; T2 keys on the refutations CONTENT hash and a
retracted id, never on file age; T5's rotation is a deterministic function of
the ISO week; the weekly cap is enforced in priority order.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from forge.campaign.triggers import (
    allocate_budgets,
    cells_with_indicators,
    evaluate_triggers,
    exploration_rotation,
)
from forge.campaign.types import (
    CampaignConfig,
    CampaignSpec,
    CellKey,
    CellStats,
    TriggerInputs,
    TriggerOutcome,
)

_NOW = datetime(2026, 9, 13, 3, 0, tzinfo=UTC)

MR_SHORT: CellKey = ("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")
MR_MID: CellKey = ("mean_reversion", "swing_mid", "named", "rsi_2", "iv_rank")
MR_LONG: CellKey = ("mean_reversion", "swing_long", "named", "rsi_2", "iv_rank")
MR_MID_RSI14: CellKey = ("mean_reversion", "swing_mid", "named", "rsi_14", "iv_rank")
MR_MID_OTHERFAM: CellKey = ("mean_reversion", "swing_mid", "named", "keltner_pct", "iv_rank")
MR_HURST: CellKey = ("mean_reversion", "swing_mid", "named", "rsi_2", "hurst")
TR_LONG: CellKey = ("trend_continuation", "swing_long", "named", "momentum_252", "hurst")
VE_MID: CellKey = ("volatility_event", "swing_mid", "named", "iv_term_slope", "ivol")

_FAMILIES: dict[str, str] = {
    "rsi_2": "oscillator",
    "rsi_14": "oscillator",
    "keltner_pct": "channel",
    "iv_rank": "vol_percentile",
    "hurst": "regime",
    "momentum_252": "momentum",
    "iv_term_slope": "term_structure",
    "ivol": "idiosyncratic_vol",
}


def _stat(
    key: CellKey,
    *,
    decided: int = 10,
    converting: int = 1,
    best: float | None = 0.5,
    age_days: int = 5,
) -> CellStats:
    return CellStats(
        key=key,
        submitted=decided,
        decided=decided,
        converting=converting,
        best_cpcv_p25=best,
        newest_decided_at=_NOW - timedelta(days=age_days),
    )


def _inputs(**overrides: Any) -> TriggerInputs:
    base: dict[str, Any] = {
        "iso_week": "2026-W37",
        "designated_now": "book-now",
        "designated_prev": "book-now",
        "book_cells_now": frozenset({MR_MID, TR_LONG}),
        "book_cells_prev": frozenset({MR_MID, TR_LONG}),
        "refutation_hash_now": "h1",
        "refutation_hash_prev": "h1",
        "refutation_ids_now": frozenset({"hurst-mr-conditioner", "deep-itm-directional"}),
        "refutation_ids_prev": frozenset({"hurst-mr-conditioner", "deep-itm-directional"}),
        "registry_ids_now": frozenset(_FAMILIES),
        "registry_ids_prev": frozenset(_FAMILIES),
        "registry_families_now": dict(_FAMILIES),
        "registry_families_prev": dict(_FAMILIES),
        "cell_stats": {k: _stat(k) for k in (MR_SHORT, MR_MID, MR_LONG, MR_HURST, TR_LONG)},
        "protected": frozenset({MR_MID, TR_LONG}),
        "dead": frozenset(),
        "dark": frozenset(),
        "now": _NOW,
        "config": CampaignConfig(),
    }
    base.update(overrides)
    return TriggerInputs(**base)


def _by_name(outcomes: tuple[TriggerOutcome, ...]) -> Mapping[str, TriggerOutcome]:
    return {o.trigger: o for o in outcomes}


# ---------------------------------------------------------------------------
# shape + first-run baseline
# ---------------------------------------------------------------------------


def test_always_five_outcomes_in_priority_order() -> None:
    outcomes = evaluate_triggers(_inputs())
    assert [o.trigger for o in outcomes] == [
        "leg_health",
        "refutation_retraction",
        "registry_change",
        "basis_refresh",
        "exploration_floor",
    ]


def test_first_run_has_no_baseline_so_t1_t2_t3_never_fire() -> None:
    outcomes = _by_name(
        evaluate_triggers(
            _inputs(
                designated_prev=None,
                book_cells_prev=None,
                refutation_hash_prev=None,
                refutation_ids_prev=None,
                registry_ids_prev=None,
                registry_families_prev=None,
                designated_now="anything",
                refutation_hash_now="changed",
                registry_ids_now=frozenset(_FAMILIES) | {"brand_new"},
                registry_families_now={**_FAMILIES, "brand_new": "oscillator"},
            )
        )
    )
    for name in ("leg_health", "refutation_retraction", "registry_change"):
        assert not outcomes[name].fired
        assert "baseline" in outcomes[name].reason


# ---------------------------------------------------------------------------
# T1 leg health
# ---------------------------------------------------------------------------


def test_t1_fires_on_designation_flip_with_dropped_cells_and_neighbours() -> None:
    outcomes = _by_name(
        evaluate_triggers(
            _inputs(
                designated_now="book-new",
                book_cells_now=frozenset({TR_LONG}),  # MR_MID was dropped
                cell_stats={
                    k: _stat(k)
                    for k in (
                        MR_SHORT,
                        MR_MID,
                        MR_LONG,
                        MR_MID_RSI14,
                        MR_MID_OTHERFAM,
                        MR_HURST,
                        TR_LONG,
                    )
                },
            )
        )
    )
    t1 = outcomes["leg_health"]
    assert t1.fired
    assert t1.campaign is not None
    assert t1.campaign.replacement_for == {MR_MID}
    # adjacent buckets (short, long) + same-family directional sibling (rsi_14);
    # NOT the other-family directional, NOT a different regime gate
    assert t1.campaign.cells == {MR_MID, MR_SHORT, MR_LONG, MR_MID_RSI14}
    assert t1.campaign.budget == CampaignConfig().leg_health_budget


def test_t1_does_not_fire_when_designation_is_unchanged() -> None:
    assert not _by_name(evaluate_triggers(_inputs()))["leg_health"].fired


def test_t1_flip_to_a_superset_book_fires_with_no_cells_and_zero_budget() -> None:
    t1 = _by_name(
        evaluate_triggers(
            _inputs(
                designated_now="book-new", book_cells_now=frozenset({MR_MID, TR_LONG, MR_SHORT})
            )
        )
    )["leg_health"]
    assert t1.fired
    assert t1.campaign is not None
    assert t1.campaign.cells == frozenset()
    assert t1.campaign.budget == 0


# ---------------------------------------------------------------------------
# T2 refutation retraction
# ---------------------------------------------------------------------------


def test_t2_fires_on_content_change_with_a_retracted_bound_id() -> None:
    t2 = _by_name(
        evaluate_triggers(
            _inputs(
                refutation_hash_now="h2",
                refutation_ids_now=frozenset({"deep-itm-directional"}),  # hurst binding retracted
            )
        )
    )["refutation_retraction"]
    assert t2.fired
    assert t2.campaign is not None
    # the hurst-mr-conditioner binding deprioritizes the MR hurst regime gate: that cell is released
    assert t2.campaign.cells == {MR_HURST}
    assert t2.campaign.budget == CampaignConfig().refutation_budget


def test_t2_keys_on_the_content_hash_and_a_retracted_id_never_on_age() -> None:
    # content changed (a verb edit) but no id left: no retraction
    same_ids = _by_name(evaluate_triggers(_inputs(refutation_hash_now="h2")))[
        "refutation_retraction"
    ]
    assert not same_ids.fired
    # ids differ but the hash did not: an impossible export state, treated as no change
    same_hash = _by_name(
        evaluate_triggers(_inputs(refutation_ids_now=frozenset({"deep-itm-directional"})))
    )["refutation_retraction"]
    assert not same_hash.fired


def test_t2_retracted_clip_delta_or_unbound_id_releases_no_cell() -> None:
    t2 = _by_name(
        evaluate_triggers(
            _inputs(
                refutation_hash_now="h2",
                refutation_ids_prev=frozenset({"deep-itm-directional", "never-bound"}),
                refutation_ids_now=frozenset(),
            )
        )
    )["refutation_retraction"]
    assert t2.fired
    assert t2.campaign is not None
    assert t2.campaign.cells == frozenset()
    assert t2.campaign.budget == 0
    assert "deep-itm-directional" in t2.reason
    assert "never-bound" in t2.reason


# ---------------------------------------------------------------------------
# T3 registry change
# ---------------------------------------------------------------------------


def test_t3_fires_on_a_new_id_in_an_existing_family() -> None:
    t3 = _by_name(
        evaluate_triggers(
            _inputs(
                registry_ids_now=frozenset(_FAMILIES) | {"rsi_7"},
                registry_families_now={**_FAMILIES, "rsi_7": "oscillator"},
            )
        )
    )["registry_change"]
    assert t3.fired
    assert t3.campaign is not None
    assert t3.campaign.indicator_ids == {"rsi_7"}
    assert t3.campaign.cells == frozenset()  # never sampled yet: no cell carries it
    assert t3.campaign.budget == CampaignConfig().registry_budget


def test_t3_new_family_is_a_reopener_candidate_not_a_campaign() -> None:
    t3 = _by_name(
        evaluate_triggers(
            _inputs(
                registry_ids_now=frozenset(_FAMILIES) | {"skew_25d"},
                registry_families_now={**_FAMILIES, "skew_25d": "skew"},
            )
        )
    )["registry_change"]
    assert not t3.fired
    assert "reopener 2 candidate" in t3.reason
    assert "skew" in t3.reason


def test_t3_targets_existing_cells_that_already_carry_the_new_id() -> None:
    t3 = _by_name(
        evaluate_triggers(
            _inputs(
                registry_ids_now=frozenset(_FAMILIES) | {"rsi_7"},
                registry_families_now={**_FAMILIES, "rsi_7": "oscillator"},
                cell_stats={
                    MR_MID: _stat(MR_MID),
                    ("mean_reversion", "swing_mid", "named", "rsi_7", "iv_rank"): _stat(
                        ("mean_reversion", "swing_mid", "named", "rsi_7", "iv_rank")
                    ),
                },
            )
        )
    )["registry_change"]
    assert t3.campaign is not None
    assert t3.campaign.cells == {("mean_reversion", "swing_mid", "named", "rsi_7", "iv_rank")}


def test_cells_with_indicators_matches_directional_or_regime() -> None:
    cells = (MR_MID, MR_HURST, TR_LONG)
    assert cells_with_indicators(cells, {"hurst"}) == {MR_HURST, TR_LONG}
    assert cells_with_indicators(cells, {"rsi_2"}) == {MR_MID, MR_HURST}
    assert cells_with_indicators(cells, {"nothing"}) == frozenset()


# ---------------------------------------------------------------------------
# T4 basis refresh
# ---------------------------------------------------------------------------


def test_t4_picks_stale_near_floor_unprotected_live_cells_best_first() -> None:
    cfg = CampaignConfig(basis_refresh_max_cells=2)
    stats = {
        MR_SHORT: _stat(MR_SHORT, best=1.3, age_days=120),  # eligible
        MR_LONG: _stat(MR_LONG, best=1.45, age_days=200),  # eligible, better
        MR_HURST: _stat(MR_HURST, best=1.9, age_days=365),  # eligible, best of all
        MR_MID: _stat(MR_MID, best=2.0, age_days=400),  # protected
        TR_LONG: _stat(TR_LONG, best=1.8, age_days=10),  # fresh
        VE_MID: _stat(VE_MID, best=1.0, age_days=400),  # below the near-floor bar
    }
    t4 = _by_name(
        evaluate_triggers(_inputs(cell_stats=stats, config=cfg, dead=frozenset({MR_SHORT})))
    )["basis_refresh"]
    assert t4.fired
    assert t4.campaign is not None
    assert t4.campaign.cells == {MR_HURST, MR_LONG}  # dead MR_SHORT excluded, top-2 by best
    assert t4.campaign.budget == 2 * cfg.basis_refresh_budget_per_cell


def test_t4_does_not_fire_without_a_stale_near_floor_cell() -> None:
    assert not _by_name(evaluate_triggers(_inputs()))["basis_refresh"].fired


# ---------------------------------------------------------------------------
# T5 exploration floor
# ---------------------------------------------------------------------------


def test_t5_rotation_is_deterministic_per_week_and_changes_across_weeks() -> None:
    dark = frozenset({MR_SHORT, MR_LONG, MR_HURST, VE_MID, MR_MID_RSI14, MR_MID_OTHERFAM})
    a = exploration_rotation(dark, "2026-W37")
    b = exploration_rotation(dark, "2026-W37")
    c = exploration_rotation(dark, "2026-W38")
    assert a == b
    assert set(a) == dark
    assert len(a) == len(dark)
    assert a != c


def test_t5_fires_only_with_dark_cells_and_keeps_rotation_head() -> None:
    assert not _by_name(evaluate_triggers(_inputs()))["exploration_floor"].fired
    dark = frozenset({MR_SHORT, MR_LONG, MR_HURST, VE_MID})
    t5 = _by_name(evaluate_triggers(_inputs(dark=dark, config=CampaignConfig(exploration_min=2))))[
        "exploration_floor"
    ]
    assert t5.fired
    assert t5.campaign is not None
    assert t5.campaign.cells <= dark
    assert t5.campaign.cells == frozenset(
        exploration_rotation(dark, "2026-W37")[: len(t5.campaign.cells)]
    )


# ---------------------------------------------------------------------------
# budget allocation
# ---------------------------------------------------------------------------


def _spec(
    trigger: str, budget: int, cells: frozenset[CellKey] = frozenset({MR_SHORT})
) -> CampaignSpec:
    return CampaignSpec(trigger=trigger, cells=cells, budget=budget, reason="test")  # type: ignore[arg-type]


def _fired(spec: CampaignSpec) -> TriggerOutcome:
    return TriggerOutcome(trigger=spec.trigger, fired=True, reason="test", campaign=spec)


def test_allocate_caps_at_the_weekly_cap_trimming_later_triggers_first() -> None:
    cfg = CampaignConfig(weekly_cap=300, leg_health_budget=200, refutation_budget=100)
    outcomes = (
        _fired(_spec("leg_health", 200)),
        _fired(_spec("refutation_retraction", 100)),
        _fired(_spec("basis_refresh", 100)),
        _fired(_spec("exploration_floor", 40, frozenset({MR_LONG, MR_HURST}))),
    )
    specs = allocate_budgets(outcomes, cfg)
    assert [s.trigger for s in specs] == ["leg_health", "refutation_retraction"]
    assert sum(s.budget for s in specs) == 300


def test_allocate_drops_zero_budget_and_cell_less_campaigns_but_keeps_t3_indicator_targets() -> (
    None
):
    t3 = CampaignSpec(
        trigger="registry_change",
        cells=frozenset(),
        budget=100,
        reason="new id",
        indicator_ids=frozenset({"rsi_7"}),
    )
    outcomes = (
        _fired(_spec("leg_health", 0, frozenset())),
        TriggerOutcome(trigger="refutation_retraction", fired=False, reason="no"),
        _fired(t3),
    )
    specs = allocate_budgets(outcomes, CampaignConfig())
    assert specs == (t3,)


def test_allocate_sizes_exploration_as_a_share_of_the_other_budgets_with_a_floor() -> None:
    cfg = CampaignConfig(exploration_share=0.10, exploration_min=20)
    dark = frozenset(
        {MR_SHORT, MR_LONG, MR_HURST, VE_MID, MR_MID_RSI14, MR_MID_OTHERFAM}
        | {("mean_reversion", "swing_short", "named", f"ind_{i}", "iv_rank") for i in range(40)}
    )
    t5 = _spec("exploration_floor", 999, dark)
    only_t5 = allocate_budgets((_fired(t5),), cfg)
    assert only_t5[0].budget == 20  # the floor when nothing else fires
    with_t1 = allocate_budgets((_fired(_spec("leg_health", 300)), _fired(t5)), cfg)
    assert with_t1[-1].budget == 30  # 10% of 300, above the floor


@pytest.mark.parametrize("cap", [1, 50, 400, 10_000])
def test_allocate_never_exceeds_cap(cap: int) -> None:
    cfg = CampaignConfig(weekly_cap=cap)
    outcomes = tuple(
        _fired(_spec(t, 5_000))
        for t in ("leg_health", "refutation_retraction", "basis_refresh", "exploration_floor")
    )
    assert sum(s.budget for s in allocate_budgets(outcomes, cfg)) <= cap
