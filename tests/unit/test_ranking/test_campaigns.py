"""Tests for ``forge.ranking.campaigns`` (D299) — the campaign registry.

The discover -> concentrate -> farm loop as a first-class object. Two hard
guarantees under test:

  1. **D287 continuity (byte-identical selection).** The derived
     ``EXPERIMENT_CELLS`` / ``EXPERIMENT_CELL_SLOTS`` in
     ``forge.ranking.experiment_cells`` must equal the hand-pinned D287
     constants exactly — the registry is a refactor of the pin's HOME, never
     of its value. Ranking behavior must not move without its own D-entry.
  2. **Registry hygiene.** Campaigns are code, edited only with a D-entry
     (the D276/D286 sampler-pin convention); the validator makes malformed
     records an import error rather than silent misbehavior.
"""

from __future__ import annotations

import pytest

from forge.ranking.campaigns import (
    CAMPAIGNS,
    DEFAULT_SELECTION_SLOTS,
    Campaign,
    active_selection_cells,
    active_selection_slots,
    campaign_member_fn,
    config_cell_from_json,
    validate_registry,
)
from tests.fixtures.strategy_configs import minimal_strategy_config

# ---------------------------------------------------------------------------
# Registry content — the seed records and the D287 continuity guarantee
# ---------------------------------------------------------------------------


def test_registry_validates() -> None:
    validate_registry(CAMPAIGNS)


def test_d287_floor_retired_no_active_cells() -> None:
    """THE load-bearing test: the derived selection floor reflects the registry.

    D287→D299 history: the resid x vix pin derived byte-identical until D305,
    when Crucible's 2026-07-20 housekeeping relay CLOSED the two-arm read
    (both chassis shortlists empty) — the campaign's pre-agreed `retire_on`
    condition — and the campaign flipped farming→retired. The derived floor
    is now EMPTY (phase 0b reserves nothing); slots fall back to the D287
    default. If this moves again, that requires its own D-entry.
    """
    from forge.ranking.experiment_cells import EXPERIMENT_CELL_SLOTS, EXPERIMENT_CELLS

    assert frozenset() == EXPERIMENT_CELLS
    assert EXPERIMENT_CELL_SLOTS == DEFAULT_SELECTION_SLOTS
    assert frozenset() == active_selection_cells(CAMPAIGNS)
    assert active_selection_slots(CAMPAIGNS) == DEFAULT_SELECTION_SLOTS


def test_resid_vix_campaign_retired_with_record() -> None:
    """The D305 retirement is a status flip, not a deletion: the campaign row
    stays (audit trail + the reopening condition on record)."""
    by_name = {c.name: c for c in CAMPAIGNS}
    resid = by_name["resid-vix-two-arm"]
    assert resid.status == "retired"
    assert resid.selection_cell == ("residual_momentum", "vix_term_slope")
    assert resid.retired_note is not None
    assert "BOTH-AXES" in resid.retired_note


def test_seed_registry_names_unique_and_present() -> None:
    names = [c.name for c in CAMPAIGNS]
    assert len(names) == len(set(names))
    # The three seed campaigns as of D299. Extending the registry is expected;
    # renaming/dropping a seed silently is not (each retire is a D-entry —
    # resid-vix-two-arm retired at D305, row retained).
    assert {"resid-vix-two-arm", "mr-timer-duration", "ve-exit-repair"} <= set(names)


# ---------------------------------------------------------------------------
# Derivation helpers — status scoping and slot uniformity
# ---------------------------------------------------------------------------


def _campaign(**overrides: object) -> Campaign:
    base: dict[str, object] = {
        "name": "test-campaign",
        "status": "farming",
        "origin": "test relay",
        "decision_refs": ("D000",),
        "opened": "2026-01-01",
        "funnel_read": "funnel --compare vX vY",
        "retire_on": "test close",
    }
    base.update(overrides)
    return Campaign(**base)  # type: ignore[arg-type]


def test_only_farming_cells_reach_selection() -> None:
    farming = _campaign(name="a", selection_cell=("d1", "r1"), selection_slots=4)
    retired = _campaign(name="b", status="retired", selection_cell=("d2", "r2"), selection_slots=4)
    confirmed = _campaign(
        name="c", status="confirmed", selection_cell=("d3", "r3"), selection_slots=4
    )
    cells = active_selection_cells((farming, retired, confirmed))
    assert cells == frozenset({("d1", "r1")})


def test_no_active_selection_campaigns_keeps_default_slots() -> None:
    generation_only = _campaign(name="a", hypothesis="mean_reversion")
    assert active_selection_cells((generation_only,)) == frozenset()
    assert active_selection_slots((generation_only,)) == DEFAULT_SELECTION_SLOTS


def test_mixed_slot_counts_raise() -> None:
    a = _campaign(name="a", selection_cell=("d1", "r1"), selection_slots=4)
    b = _campaign(name="b", selection_cell=("d2", "r2"), selection_slots=6)
    with pytest.raises(ValueError, match="uniform"):
        active_selection_slots((a, b))


def test_validate_rejects_duplicate_names() -> None:
    a = _campaign(name="dup")
    b = _campaign(name="dup")
    with pytest.raises(ValueError, match="dup"):
        validate_registry((a, b))


def test_validate_rejects_cell_without_slots() -> None:
    bad = _campaign(selection_cell=("d1", "r1"), selection_slots=0)
    with pytest.raises(ValueError, match="selection_slots"):
        validate_registry((bad,))


def test_validate_rejects_slots_without_cell() -> None:
    bad = _campaign(selection_slots=4)
    with pytest.raises(ValueError, match="selection_cell"):
        validate_registry((bad,))


# ---------------------------------------------------------------------------
# config_cell_from_json — must mirror experiment_cells.config_cell exactly
# ---------------------------------------------------------------------------


def test_config_cell_from_json_mirrors_config_cell() -> None:
    from forge.ranking.experiment_cells import config_cell

    config = minimal_strategy_config()
    as_json = config.model_dump(mode="json")
    assert config_cell_from_json(as_json) == config_cell(config)
    assert config_cell_from_json(as_json) == ("rsi_2", "iv_rank")


def test_config_cell_from_json_none_when_role_absent() -> None:
    config = minimal_strategy_config()
    as_json = config.model_dump(mode="json")
    # Bare-drop shape: no regime_filter signal at all.
    as_json["signals"] = [s for s in as_json["signals"] if s["role"] != "regime_filter"]
    assert config_cell_from_json(as_json) is None


# ---------------------------------------------------------------------------
# campaign_member_fn — membership resolution order
# ---------------------------------------------------------------------------


def _json_config(**overrides: object) -> dict[str, object]:
    config = minimal_strategy_config().model_dump(mode="json")
    config.update(overrides)
    return config


def test_member_fn_from_selection_cell() -> None:
    campaign = _campaign(selection_cell=("rsi_2", "iv_rank"), selection_slots=4)
    fn = campaign_member_fn(campaign)
    assert fn is not None
    assert fn(_json_config()) is True
    other = _json_config()
    other["signals"][0]["indicators"] = ["hurst"]  # type: ignore[index]
    assert fn(other) is False


def test_member_fn_from_hypothesis() -> None:
    campaign = _campaign(hypothesis="volatility_event")
    fn = campaign_member_fn(campaign)
    assert fn is not None
    assert fn(_json_config(hypothesis="volatility_event")) is True
    assert fn(_json_config(hypothesis="mean_reversion")) is False


def test_explicit_member_wins_over_cell_and_hypothesis() -> None:
    campaign = _campaign(
        hypothesis="mean_reversion",
        selection_cell=("rsi_2", "iv_rank"),
        selection_slots=4,
        member=lambda config: config.get("name") == "special",
    )
    fn = campaign_member_fn(campaign)
    assert fn is not None
    assert fn(_json_config(name="special")) is True
    assert fn(_json_config()) is False  # cell matches, but the explicit member rules


def test_member_fn_none_when_unresolvable() -> None:
    assert campaign_member_fn(_campaign()) is None


# ---------------------------------------------------------------------------
# Seed-record membership — the mr-timer-duration signature
# ---------------------------------------------------------------------------


def _seed(name: str) -> Campaign:
    return next(c for c in CAMPAIGNS if c.name == name)


def _mr_timer_config(n_bars: int, *, directional: str = "rsi_2") -> dict[str, object]:
    config = _json_config(hypothesis="mean_reversion")
    config["signals"][0]["indicators"] = [directional]  # type: ignore[index]
    config["exits"] = [
        {"id": "expiry_exit", "params": {}},
        {"id": "time_stop", "params": {"n_bars": n_bars}},
    ]
    return config


def test_mr_timer_member_matches_the_v40_cell() -> None:
    fn = campaign_member_fn(_seed("mr-timer-duration"))
    assert fn is not None
    assert fn(_mr_timer_config(10)) is True
    assert fn(_mr_timer_config(8)) is True
    assert fn(_mr_timer_config(12)) is True


def test_mr_timer_member_excludes_out_of_box_and_capitulation() -> None:
    fn = campaign_member_fn(_seed("mr-timer-duration"))
    assert fn is not None
    # Param-less / out-of-box timers are the RETIRED cell, not the campaign.
    assert fn(_mr_timer_config(5)) is False
    assert fn(_mr_timer_config(13)) is False
    # The capitulation directional (momentum) is veto-frozen out of the cell —
    # mirrors the sampler's own scoping (_pick_required_exit, D291/v40).
    assert fn(_mr_timer_config(10, directional="momentum")) is False
    # A trend config with an in-box timer is not MR.
    trend = _mr_timer_config(10)
    trend["hypothesis"] = "trend_continuation"
    assert fn(trend) is False
    # No time_stop exit at all.
    no_timer = _json_config(hypothesis="mean_reversion")
    no_timer["exits"] = [{"id": "expiry_exit", "params": {}}]
    assert fn(no_timer) is False


def test_resid_vix_seed_carries_the_d287_cell() -> None:
    campaign = _seed("resid-vix-two-arm")
    assert campaign.selection_cell == ("residual_momentum", "vix_term_slope")
    assert campaign.selection_slots == 4
    # D305: retired (the two-arm read closed) — the cell stays on the row as
    # the historical record, but derives into no active floor.
    assert campaign.status == "retired"


def test_ve_seed_is_hypothesis_wide() -> None:
    fn = campaign_member_fn(_seed("ve-exit-repair"))
    assert fn is not None
    assert fn(_json_config(hypothesis="volatility_event")) is True
    assert fn(_json_config(hypothesis="mean_reversion")) is False
