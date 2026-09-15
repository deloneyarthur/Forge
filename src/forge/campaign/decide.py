"""Steps 6-7 of the weekly run: what the triggers see, and the operator's budget cap
(Batch 6 A4 split from run.py).

WHY a module: the trigger inputs are the run's memory -- the previous record's baselines
beside this week's book, refutations and registry -- and `triggers.py` must stay a pure
function of them (plan 2026-09 §12.3), so the reading lives here, not there."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge.campaign.exports import _EXPORT_GLOBS, sha256_of
from forge.campaign.report import (
    baseline_cells,
    baseline_families,
    baseline_ids,
    baseline_str,
    load_latest_baseline_record,
)
from forge.campaign.types import CampaignSpec, TriggerInputs
from forge.core.paths import newest_file

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime
    from pathlib import Path

    from crucible_contracts import RegistrySnapshot

    from forge.campaign.types import Book, CampaignConfig, CellKey, CellStats


def _refutation_hash(exports_dir: Path) -> str:
    newest = newest_file(exports_dir, _EXPORT_GLOBS["refutations"])
    return sha256_of(newest) if newest is not None else ""


def _refutation_ids(exports_dir: Path) -> frozenset[str]:
    # The ids Forge is currently routing off (bound AND active): a retraction is an id
    # leaving this set. Unbound entries route nothing, so their arrival or departure is
    # not a generation event.
    from forge.enumeration import resolve_effects  # noqa: PLC0415

    return frozenset(resolve_effects(exports_dir=exports_dir).active_entry_ids)


def trigger_inputs(
    *,
    iso_week: str,
    now: datetime,
    book: Book,
    registry: RegistrySnapshot,
    exports_dir: Path,
    records_dir: Path,
    stats: Mapping[CellKey, CellStats],
    dead: frozenset[CellKey],
    dark: frozenset[CellKey],
    cfg: CampaignConfig,
) -> tuple[TriggerInputs, dict[str, object]]:
    """This week's trigger inputs, and the baselines the NEXT run reads its own against."""
    prev = load_latest_baseline_record(records_dir)
    book_cells_now = frozenset(
        leg.cell for leg in book.legs if leg.portfolio_id == book.designated_id
    )
    families_now = {meta.id: meta.family for meta in registry.indicators}
    ref_hash_now = _refutation_hash(exports_dir)
    ref_ids_now = _refutation_ids(exports_dir)
    inputs = TriggerInputs(
        iso_week=iso_week,
        designated_now=book.designated_id,
        designated_prev=prev.designated_id if prev is not None else None,
        book_cells_now=book_cells_now,
        book_cells_prev=baseline_cells(prev) if prev is not None else None,
        refutation_hash_now=ref_hash_now,
        refutation_hash_prev=baseline_str(prev, "refutation_hash") if prev else None,
        refutation_ids_now=ref_ids_now,
        refutation_ids_prev=baseline_ids(prev, "refutation_ids") if prev else None,
        registry_ids_now=frozenset(families_now),
        registry_ids_prev=baseline_ids(prev, "registry_ids") if prev else None,
        registry_families_now=families_now,
        registry_families_prev=baseline_families(prev) if prev else None,
        cell_stats=stats,
        protected=book.protected_cells,
        dead=dead,
        dark=dark,
        now=now,
        config=cfg,
    )
    baselines: dict[str, object] = {
        "book_cells": sorted(book_cells_now),
        "refutation_hash": ref_hash_now,
        "refutation_ids": sorted(ref_ids_now),
        "registry_ids": sorted(families_now),
        "registry_families": families_now,
    }
    return inputs, baselines


def cap_budgets(
    campaigns: Sequence[CampaignSpec], budget_override: int | None
) -> list[CampaignSpec]:
    """``--budget N``: at most N across the campaigns in priority order (a hand run's sizing)."""
    if budget_override is None:
        return list(campaigns)
    remaining = budget_override
    capped: list[CampaignSpec] = []
    for campaign in campaigns:
        take = min(campaign.budget, remaining)
        if take > 0:
            capped.append(
                CampaignSpec(
                    campaign.trigger,
                    campaign.cells,
                    take,
                    campaign.reason,
                    campaign.replacement_for,
                    campaign.indicator_ids,
                )
            )
            remaining -= take
    return capped
