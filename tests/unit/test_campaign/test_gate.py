"""Tests for ``forge.campaign.gate`` (plan 2026-09 §12.3 step 4).

The challenger gate is STRUCTURAL: a protected cell (a live book leg's cell)
is refused unless the campaign is a replacement for exactly that cell; a
config whose signal content overlaps a book leg beyond the Jaccard bar is a
duplicate; a dead cell is never resubmitted. It never reads Crucible's
corr_to_book label (the freeze §6 obligation) and never predicts.
"""

from __future__ import annotations

from forge.campaign.cells import cell_key
from forge.campaign.gate import challenger_gate
from forge.campaign.types import Book, BookLeg, CampaignConfig, CampaignSpec, CellKey
from forge.ranking.diversifier import _signal_keys
from tests.fixtures.strategy_configs import minimal_strategy_config

_CFG = CampaignConfig()


def _leg(config: object, portfolio_id: str = "book") -> BookLeg:
    cfg = config  # type: ignore[assignment]
    return BookLeg(
        config_hash=cfg.config_hash,  # type: ignore[attr-defined]
        portfolio_id=portfolio_id,
        hypothesis=cfg.hypothesis,  # type: ignore[attr-defined]
        cell=cell_key(cfg),  # type: ignore[arg-type]
        signal_ids=_signal_keys(cfg),  # type: ignore[arg-type]
        weight=0.5,
    )


def _book(*legs: BookLeg) -> Book:
    return Book(
        designated_id="book",
        designated_at="2026-08-06",
        legs=tuple(legs),
        protected_cells=frozenset(leg.cell for leg in legs),
    )


def _campaign(
    cells: frozenset[CellKey], replacement_for: frozenset[CellKey] = frozenset()
) -> CampaignSpec:
    return CampaignSpec(
        trigger="basis_refresh",
        cells=cells,
        budget=10,
        reason="test",
        replacement_for=replacement_for,
    )


def test_protected_cell_is_refused_without_a_replacement_campaign() -> None:
    leg_cfg = minimal_strategy_config(name="leg")
    challenger = minimal_strategy_config(name="challenger", underlying="QQQ")
    book = _book(_leg(leg_cfg))
    cell = cell_key(challenger)
    assert cell in book.protected_cells
    decision = challenger_gate(
        challenger,
        cell,
        book=book,
        campaign=_campaign(frozenset({cell})),
        dead=frozenset(),
        cfg=_CFG,
    )
    assert (decision.keep, decision.reason) == (False, "protected_cell")


def test_replacement_campaign_may_enter_its_own_protected_cell() -> None:
    leg_cfg = minimal_strategy_config(name="leg", underlying="SPY")
    # a different regime threshold makes the signal content differ -> not a duplicate
    challenger = leg_cfg.model_copy(
        update={
            "name": "challenger",
            "signals": (
                leg_cfg.signals[0],
                leg_cfg.signals[1].model_copy(update={"params": {"threshold": 80}}),
            ),
        }
    )
    cell = cell_key(challenger)
    book = _book(_leg(leg_cfg))
    campaign = _campaign(frozenset({cell}), replacement_for=frozenset({cell}))
    decision = challenger_gate(
        challenger, cell, book=book, campaign=campaign, dead=frozenset(), cfg=_CFG
    )
    assert decision.keep
    assert decision.reason is None


def test_duplicate_of_a_leg_is_refused_even_outside_its_cell() -> None:
    leg_cfg = minimal_strategy_config(name="leg", dte_bucket="swing_long")
    # same signals, different bucket: a different cell, but the same content
    challenger = minimal_strategy_config(name="challenger", dte_bucket="swing_short")
    book = _book(_leg(leg_cfg))
    cell = cell_key(challenger)
    assert cell not in book.protected_cells
    decision = challenger_gate(
        challenger,
        cell,
        book=book,
        campaign=_campaign(frozenset({cell})),
        dead=frozenset(),
        cfg=_CFG,
    )
    assert (decision.keep, decision.reason) == (False, "duplicate_of_leg")


def test_partial_overlap_below_the_bar_is_kept() -> None:
    leg_cfg = minimal_strategy_config(name="leg", dte_bucket="swing_long")
    challenger = leg_cfg.model_copy(
        update={
            "name": "challenger",
            "dte_bucket": "swing_short",
            "signals": (
                leg_cfg.signals[0],
                leg_cfg.signals[1].model_copy(update={"params": {"threshold": 80}}),
            ),
        }
    )
    book = _book(_leg(leg_cfg))
    cell = cell_key(challenger)
    decision = challenger_gate(
        challenger,
        cell,
        book=book,
        campaign=_campaign(frozenset({cell})),
        dead=frozenset(),
        cfg=_CFG,
    )
    assert decision.keep  # Jaccard 1/3 < 0.85


def test_dead_cell_is_refused() -> None:
    challenger = minimal_strategy_config(name="challenger")
    cell = cell_key(challenger)
    decision = challenger_gate(
        challenger,
        cell,
        book=_book(),
        campaign=_campaign(frozenset({cell})),
        dead=frozenset({cell}),
        cfg=_CFG,
    )
    assert (decision.keep, decision.reason) == (False, "dead_cell")


def test_reason_precedence_protected_before_duplicate_before_dead() -> None:
    leg_cfg = minimal_strategy_config(name="leg")
    challenger = minimal_strategy_config(name="challenger")  # same cell AND same content
    cell = cell_key(challenger)
    book = _book(_leg(leg_cfg))
    protected = challenger_gate(
        challenger,
        cell,
        book=book,
        campaign=_campaign(frozenset({cell})),
        dead=frozenset({cell}),
        cfg=_CFG,
    )
    assert protected.reason == "protected_cell"
    replacement = challenger_gate(
        challenger,
        cell,
        book=book,
        campaign=_campaign(frozenset({cell}), replacement_for=frozenset({cell})),
        dead=frozenset({cell}),
        cfg=_CFG,
    )
    assert replacement.reason == "duplicate_of_leg"


def test_empty_book_keeps_everything_not_dead() -> None:
    challenger = minimal_strategy_config(name="challenger")
    cell = cell_key(challenger)
    decision = challenger_gate(
        challenger,
        cell,
        book=_book(),
        campaign=_campaign(frozenset({cell})),
        dead=frozenset(),
        cfg=_CFG,
    )
    assert decision.keep
