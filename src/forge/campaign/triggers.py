"""The five campaign triggers (plan 2026-09 §12.3, corrected by D409) as pure functions.

WHY pure: a trigger decision must be replayable from the run record, so every
trigger reads only ``TriggerInputs`` and nothing else, no clock, no RNG, no
file. The run supplies the facts and the previous run's baselines; the first
run has no baselines, so T1/T2/T3 record and do not fire (a flip you cannot
compare against is not a flip). T5's rotation is a hash of the ISO week, so
the same week always picks the same dark cells and a later ``--dry-run`` on
the same record reproduces the plan.

Budgets are decided in priority order (T1 > T2 > T3 > T4 > T5) under one
weekly cap; ``allocate_budgets`` is the only place the cap is applied.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import timedelta

from forge.campaign.types import (
    CampaignConfig,
    CampaignSpec,
    CellKey,
    CellStats,
    Trigger,
    TriggerInputs,
    TriggerOutcome,
)
from forge.enumeration.refutations import BINDINGS, RefutationBinding

_PRIORITY: tuple[Trigger, ...] = (
    "leg_health",
    "refutation_retraction",
    "registry_change",
    "basis_refresh",
    "exploration_floor",
)
_DTE_ORDER: tuple[str, ...] = ("swing_short", "swing_mid", "swing_long")
_NO_BASELINE = "no baseline (first run): recorded, not fired"


# ---------------------------------------------------------------------------
# helpers shared with the run
# ---------------------------------------------------------------------------


def cells_with_indicators(cells: Iterable[CellKey], ids: Iterable[str]) -> frozenset[CellKey]:
    """Cells whose directional or regime indicator is one of ``ids`` (T3's targets)."""
    wanted = frozenset(ids)
    return frozenset(cell for cell in cells if cell[3] in wanted or cell[4] in wanted)


def exploration_rotation(dark: Iterable[CellKey], iso_week: str) -> tuple[CellKey, ...]:
    """Dark cells in this week's deterministic order.

    A hash of ``(iso_week, cell)`` rather than an RNG: no seed to thread, no
    state to persist, and every dark cell gets its turn as the weeks roll.
    """

    def rank(cell: CellKey) -> bytes:
        return hashlib.blake2b(f"{iso_week}:{cell}".encode(), digest_size=8).digest()

    return tuple(sorted(sorted(dark), key=rank))


def _adjacent_bucket(a: str, b: str) -> bool:
    if a not in _DTE_ORDER or b not in _DTE_ORDER:
        return False
    return abs(_DTE_ORDER.index(a) - _DTE_ORDER.index(b)) == 1


def _neighbours(
    dropped: Iterable[CellKey],
    stats: Mapping[CellKey, CellStats],
    families: Mapping[str, str],
) -> frozenset[CellKey]:
    """Replacement supply for a dropped leg: the adjacent dte buckets of the same
    cell, and same-bucket cells whose directional is a registry-family sibling."""
    out: set[CellKey] = set()
    for hypothesis, dte, axis, directional, regime in dropped:
        family = families.get(directional)
        for key in stats:
            k_h, k_dte, k_axis, k_dir, k_reg = key
            if (k_h, k_axis, k_reg) != (hypothesis, axis, regime):
                continue
            adjacent = k_dir == directional and _adjacent_bucket(k_dte, dte)
            sibling = (
                k_dte == dte
                and k_dir != directional
                and family is not None
                and families.get(k_dir) == family
            )
            if adjacent or sibling:
                out.add(key)
    return frozenset(out)


# ---------------------------------------------------------------------------
# the triggers
# ---------------------------------------------------------------------------


def _t1_leg_health(inputs: TriggerInputs) -> TriggerOutcome:
    if inputs.designated_prev is None or inputs.book_cells_prev is None:
        return TriggerOutcome("leg_health", False, _NO_BASELINE)
    if inputs.designated_now == inputs.designated_prev:
        return TriggerOutcome(
            "leg_health", False, f"designated book unchanged ({inputs.designated_now})"
        )
    dropped = frozenset(inputs.book_cells_prev - inputs.book_cells_now)
    cells = dropped | _neighbours(dropped, inputs.cell_stats, inputs.registry_families_now)
    reason = (
        f"designation flipped {inputs.designated_prev} -> {inputs.designated_now}; "
        f"dropped {len(dropped)} cell(s), {len(cells)} target(s) incl. neighbours"
    )
    return TriggerOutcome(
        "leg_health",
        True,
        reason,
        CampaignSpec(
            trigger="leg_health",
            cells=cells,
            budget=inputs.config.leg_health_budget if cells else 0,
            reason=reason,
            replacement_for=dropped,
        ),
    )


def _binding_cells(
    binding: RefutationBinding, stats: Mapping[CellKey, CellStats]
) -> frozenset[CellKey]:
    if binding.kind == "deprioritize_regime_gate":
        return frozenset(k for k in stats if k[0] == binding.hypothesis and k[4] == binding.gate_id)
    if binding.kind == "deprioritize_underlying_class":
        return frozenset(k for k in stats if k[0] == binding.hypothesis)
    return frozenset()  # clip_delta shapes a draw, not a cell


def _t2_refutation_retraction(inputs: TriggerInputs) -> TriggerOutcome:
    name: Trigger = "refutation_retraction"
    if inputs.refutation_hash_prev is None or inputs.refutation_ids_prev is None:
        return TriggerOutcome(name, False, _NO_BASELINE)
    if inputs.refutation_hash_now == inputs.refutation_hash_prev:
        return TriggerOutcome(name, False, "refutations export content unchanged")
    retracted = frozenset(inputs.refutation_ids_prev - inputs.refutation_ids_now)
    if not retracted:
        return TriggerOutcome(name, False, "refutations content changed but no entry was retracted")
    bindings = {b.entry_id: b for b in BINDINGS}
    cells: set[CellKey] = set()
    notes: list[str] = []
    for entry_id in sorted(retracted):
        binding = bindings.get(entry_id)
        if binding is None:
            notes.append(f"{entry_id}: no Forge binding, nothing to release")
            continue
        released = _binding_cells(binding, inputs.cell_stats)
        if not released:
            notes.append(f"{entry_id}: {binding.kind} binding releases no cell")
        cells.update(released)
    reason = f"retracted {sorted(retracted)}; released {len(cells)} cell(s); " + "; ".join(notes)
    return TriggerOutcome(
        name,
        True,
        reason,
        CampaignSpec(
            trigger=name,
            cells=frozenset(cells),
            budget=inputs.config.refutation_budget if cells else 0,
            reason=reason,
        ),
    )


def _t3_registry_change(inputs: TriggerInputs) -> TriggerOutcome:
    name: Trigger = "registry_change"
    if inputs.registry_ids_prev is None or inputs.registry_families_prev is None:
        return TriggerOutcome(name, False, _NO_BASELINE)
    new_ids = frozenset(inputs.registry_ids_now - inputs.registry_ids_prev)
    if not new_ids:
        return TriggerOutcome(name, False, "registry indicator ids unchanged")
    known_families = frozenset(inputs.registry_families_prev.values())
    in_family = frozenset(
        i for i in new_ids if inputs.registry_families_now.get(i) in known_families
    )
    new_families = sorted({str(inputs.registry_families_now.get(i)) for i in new_ids - in_family})
    if not in_family:
        return TriggerOutcome(
            name,
            False,
            f"reopener 2 candidate: family {new_families} is new (a grammar bump, not a campaign)",
        )
    cells = cells_with_indicators(inputs.cell_stats, in_family)
    reason = f"new ids {sorted(in_family)} in existing families; {len(cells)} sampled cell(s)"
    if new_families:
        reason += f"; also reopener 2 candidate: family {new_families}"
    return TriggerOutcome(
        name,
        True,
        reason,
        CampaignSpec(
            trigger=name,
            cells=cells,
            budget=inputs.config.registry_budget,
            reason=reason,
            indicator_ids=in_family,
        ),
    )


def _t4_basis_refresh(inputs: TriggerInputs) -> TriggerOutcome:
    name: Trigger = "basis_refresh"
    cfg = inputs.config
    stale_before = inputs.now - timedelta(days=cfg.basis_refresh_stale_days)
    candidates = [
        s
        for s in inputs.cell_stats.values()
        if s.key not in inputs.protected
        and s.key not in inputs.dead
        and s.best_cpcv_p25 is not None
        and s.best_cpcv_p25 >= cfg.basis_refresh_near_floor_cpcv_p25
        and s.newest_decided_at is not None
        and s.newest_decided_at < stale_before
    ]
    if not candidates:
        return TriggerOutcome(name, False, "no stale near-floor cell outside the book")
    candidates.sort(key=lambda s: (-(s.best_cpcv_p25 or 0.0), s.key))
    chosen = frozenset(s.key for s in candidates[: cfg.basis_refresh_max_cells])
    reason = (
        f"{len(candidates)} stale near-floor cell(s), refreshing {len(chosen)}: {sorted(chosen)}"
    )
    return TriggerOutcome(
        name,
        True,
        reason,
        CampaignSpec(
            trigger=name,
            cells=chosen,
            budget=len(chosen) * cfg.basis_refresh_budget_per_cell,
            reason=reason,
        ),
    )


def _t5_exploration_floor(inputs: TriggerInputs) -> TriggerOutcome:
    name: Trigger = "exploration_floor"
    if not inputs.dark:
        return TriggerOutcome(name, False, "no dark cell in this run's sample")
    cfg = inputs.config
    head = max(cfg.exploration_min, round(cfg.exploration_share * cfg.weekly_cap))
    ordered = exploration_rotation(inputs.dark, inputs.iso_week)[:head]
    reason = f"{len(inputs.dark)} dark cell(s); rotation head {len(ordered)} for {inputs.iso_week}"
    return TriggerOutcome(
        name,
        True,
        reason,
        CampaignSpec(trigger=name, cells=frozenset(ordered), budget=len(ordered), reason=reason),
    )


def evaluate_triggers(inputs: TriggerInputs) -> tuple[TriggerOutcome, ...]:
    """All five outcomes, in priority order, fired or not, each with its reason."""
    return (
        _t1_leg_health(inputs),
        _t2_refutation_retraction(inputs),
        _t3_registry_change(inputs),
        _t4_basis_refresh(inputs),
        _t5_exploration_floor(inputs),
    )


def allocate_budgets(
    outcomes: Sequence[TriggerOutcome], config: CampaignConfig
) -> tuple[CampaignSpec, ...]:
    """Apply the weekly cap in priority order; size T5 as a share of the rest.

    Later triggers are trimmed first because the cap is walked T1 -> T5 and
    each takes what remains. A campaign with nothing to target (no cells and
    no T3 indicator ids) or nothing to spend is dropped rather than carried as
    an empty record.
    """
    by_trigger = {o.trigger: o.campaign for o in outcomes if o.fired and o.campaign is not None}
    other_total = sum(
        spec.budget
        for trigger, spec in by_trigger.items()
        if trigger != "exploration_floor" and (spec.cells or spec.indicator_ids)
    )
    remaining = config.weekly_cap
    out: list[CampaignSpec] = []
    for trigger in _PRIORITY:
        spec = by_trigger.get(trigger)
        if spec is None or not (spec.cells or spec.indicator_ids):
            continue
        budget = spec.budget
        if trigger == "exploration_floor":
            budget = min(
                len(spec.cells),
                max(config.exploration_min, round(config.exploration_share * other_total)),
            )
        budget = min(budget, remaining)
        if budget <= 0:
            continue
        remaining -= budget
        out.append(
            CampaignSpec(
                trigger=spec.trigger,
                cells=spec.cells,
                budget=budget,
                reason=spec.reason,
                replacement_for=spec.replacement_for,
                indicator_ids=spec.indicator_ids,
            )
        )
    return tuple(out)


__all__ = [
    "allocate_budgets",
    "cells_with_indicators",
    "evaluate_triggers",
    "exploration_rotation",
]
