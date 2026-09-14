"""The structural challenger gate (plan 2026-09 §12.3 step 4).

WHY structural only: decorrelation is owned at assembly (D186/D187) and the
freeze §6 obligation forbids tuning generation against Crucible's
``corr_to_book`` label, so "duplicative" is judged on what we can see in the
config itself: the cell it occupies and the signal content it shares with a
live book leg. "Threatening" is not judged here at all; Crucible's gates are
the arbiter and the campaign only stops sending what cannot matter (a live
leg's own cell, a near-copy of a leg, a cell already proven dead).
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet

from crucible_contracts import StrategyConfig

from forge.campaign.types import Book, CampaignConfig, CampaignSpec, CellKey, GateDecision
from forge.ranking.signal_key import signal_keys


def _jaccard(a: AbstractSet[str], b: AbstractSet[str]) -> float:
    """Intersection over union on signal content keys; empty sets never match
    (the diversifier's convention, kept so both gates agree on the measure)."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def challenger_gate(
    config: StrategyConfig,
    cell: CellKey,
    *,
    book: Book,
    campaign: CampaignSpec,
    dead: AbstractSet[CellKey],
    cfg: CampaignConfig,
) -> GateDecision:
    """Keep or refuse one prefilter survivor, with the first applicable reason.

    Order matters and is deliberate: protection is the cheapest and strongest
    claim (the cell IS a book leg's), duplication needs the leg comparison,
    and death is the weakest (statistical) claim, so it is checked last.
    """
    if cell in book.protected_cells and cell not in campaign.replacement_for:
        return GateDecision(keep=False, reason="protected_cell")
    keys = signal_keys(config)
    for leg in book.legs:
        if _jaccard(keys, leg.signal_ids) >= cfg.duplicate_jaccard:
            return GateDecision(keep=False, reason="duplicate_of_leg")
    if cell in dead:
        return GateDecision(keep=False, reason="dead_cell")
    return GateDecision(keep=True)


__all__ = ["challenger_gate"]
