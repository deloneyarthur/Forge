"""Value types shared by the campaign modules — the contract everything else codes to.

WHY frozen dataclasses: a campaign decision must be replayable from its run
record (plan §12.3 step 5), so every input and outcome is an immutable value
that serialises to JSON without loss. Nothing here reads a clock, a file, or a
DB (hard rule #8 keeps this module inert); ``run.py`` supplies the facts.

The cell key is the census key (`scripts/search_multiplicity_census.py`):
``(hypothesis, dte_bucket, axis, directional, regime)`` with ``axis`` in
{"named", "xsect"}. It is finer than the campaign registry's
``(directional, regime)`` pair because protection and evidence both live at
the slot level — a book leg protects its own dte bucket, not every bucket its
indicators appear in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

CellKey = tuple[str, str, str, str, str]
"""(hypothesis, dte_bucket, axis, directional, regime). '-' marks an absent role."""

Trigger = Literal[
    "leg_health",  # T1 — the designated book changed (designation_history flip)
    "refutation_retraction",  # T2 — an effect left Crucible's refutations export (content diff)
    "registry_change",  # T3 — a new indicator id inside an existing grammar family
    "basis_refresh",  # T4 — near-floor cell whose evidence is older than the staleness window
    "exploration_floor",  # T5 — never-sampled cells, deterministic weekly rotation
]

GateReason = Literal["protected_cell", "duplicate_of_leg", "dead_cell"]

CAMPAIGN_RUN_SCHEMA: str = "campaign_run/v1"
"""Schema tag written into every run record; Crucible's digest reads it (their 09-13 §6)."""


@dataclass(frozen=True, slots=True)
class CampaignConfig:
    """Operator knobs with the plan §12.7 defaults. Read from `config/forge.yaml`
    ``campaign:`` when present; every field has a default so the run needs no input."""

    weekly_cap: int = 400
    leg_health_budget: int = 200
    refutation_budget: int = 100
    registry_budget: int = 100
    basis_refresh_budget_per_cell: int = 50
    basis_refresh_max_cells: int = 2
    basis_refresh_stale_days: int = 90
    basis_refresh_near_floor_cpcv_p25: float = 1.2
    exploration_share: float = 0.10
    exploration_min: int = 20
    duplicate_jaccard: float = 0.85
    dead_min_decided: int = 1000
    dead_ratio_to_baseline: float = 0.25
    enumeration_attempts: int = 20_000
    """Configs drawn from the unchanged population before rejection-sampling to the target cells."""
    oversample_factor: int = 3
    """Candidates kept per campaign before the battery and gate, as a multiple of its budget."""
    registry_max_age_days: int = 7
    inbox_backlog_ceiling: int = 2_000
    min_hypothesis_fraction: float = 0.0
    """D037 per-hypothesis floor passed to the enumerator. 0.0 on purpose: the floor is a
    submission-mix guarantee for the daemon's 200-config batches, and under a cold-start draw
    it stops the enumerator early (the first live dry-run yielded 800 of 20,000 after 2M
    attempts). The campaign selects by CELL from a large unstratified sample of the same
    population, exactly as the goldens enumerate it (hard rule #6). Pinned by invariant."""


@dataclass(frozen=True, slots=True)
class CellStats:
    """Realized evidence for one cell from Forge's own verdict ledger (clean era, ghost cut)."""

    key: CellKey
    submitted: int
    decided: int
    converting: int
    best_cpcv_p25: float | None
    newest_decided_at: datetime | None


@dataclass(frozen=True, slots=True)
class BookLeg:
    """One component of a promoted book, in the terms the gate and triggers need."""

    config_hash: str
    portfolio_id: str
    hypothesis: str
    cell: CellKey
    signal_ids: frozenset[str]
    weight: float


@dataclass(frozen=True, slots=True)
class Book:
    """The designated book plus every promoted book's cells.

    ``designated_id`` comes from `designation_history` (daily since 2026-09-14);
    ``protected_cells`` spans ALL promoted books (a live leg is never a target
    unless a replacement campaign names its cell). Contributions are filtered to
    the designated book — a config in several books carries the last-iterated
    book's score (Crucible 09-13 §1), so other-book rows are unknown, not healthy.
    """

    designated_id: str | None
    designated_at: str | None
    legs: tuple[BookLeg, ...]
    protected_cells: frozenset[CellKey]
    marginal_sharpe: Mapping[str, float] = field(default_factory=dict)
    """config_hash -> marginal_sharpe, designated book only (frozen at assembly; informational)."""


@dataclass(frozen=True, slots=True)
class CampaignSpec:
    """One campaign the run will generate for: which cells, how many, and why."""

    trigger: Trigger
    cells: frozenset[CellKey]
    budget: int
    reason: str
    replacement_for: frozenset[CellKey] = frozenset()
    """Protected cells this campaign is allowed to enter (T1 only)."""
    indicator_ids: frozenset[str] = frozenset()
    """T3 only: new registry ids to target; their cells have never been sampled, so
    the run's rejection sampler keeps any config carrying one of these ids."""


@dataclass(frozen=True, slots=True)
class TriggerOutcome:
    """What one trigger saw and decided; every field lands in the run record."""

    trigger: Trigger
    fired: bool
    reason: str
    campaign: CampaignSpec | None = None


@dataclass(frozen=True, slots=True)
class TriggerInputs:
    """Everything the five triggers may read. ``*_prev`` fields are None on the
    first run (no baseline) — T1/T2/T3 then record a baseline and do not fire."""

    iso_week: str
    designated_now: str | None
    designated_prev: str | None
    book_cells_now: frozenset[CellKey]
    book_cells_prev: frozenset[CellKey] | None
    refutation_hash_now: str
    refutation_hash_prev: str | None
    refutation_ids_now: frozenset[str]
    refutation_ids_prev: frozenset[str] | None
    registry_ids_now: frozenset[str]
    registry_ids_prev: frozenset[str] | None
    registry_families_now: Mapping[str, str]
    """indicator id -> family, newest registry snapshot."""
    registry_families_prev: Mapping[str, str] | None
    cell_stats: Mapping[CellKey, CellStats]
    protected: frozenset[CellKey]
    dead: frozenset[CellKey]
    dark: frozenset[CellKey]
    """Cells present in this run's enumeration sample with no submission and no verdict ever."""
    now: datetime
    config: CampaignConfig


@dataclass(frozen=True, slots=True)
class GateDecision:
    keep: bool
    reason: GateReason | None = None


@dataclass(frozen=True, slots=True)
class BootCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    """The replayable record of one weekly run — `~/forge_data/campaigns/<run_id>.json`.

    ``watermarks`` maps each export read to ``"<file name>@<sha256[:12]>"`` so a
    later ``--dry-run`` on the same files reproduces the same plan; ``baselines``
    carries the values the next run's T1/T2/T3 compare against.
    """

    schema_version: str
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    dry_run: bool
    status: Literal["ok", "no_trigger", "boot_failed", "error"]
    grammar_version: str | None
    registry_hash: str | None
    enumeration_inputs_hash: str | None
    seed: int | None
    iso_week: str
    watermarks: Mapping[str, str]
    boot: tuple[BootCheck, ...]
    designated_id: str | None
    triggers: tuple[TriggerOutcome, ...]
    campaigns: tuple[CampaignSpec, ...]
    enumerated: int
    kept_in_cells: int
    survived_battery: int
    gated_out: Mapping[str, int]
    submitted: int
    submitted_hashes: tuple[str, ...]
    batch_id: str | None
    baselines: Mapping[str, object]
    """refutation_hash/ids, registry_ids/families, book_cells: what the next run compares to."""
    notes: tuple[str, ...] = ()


__all__ = [
    "CAMPAIGN_RUN_SCHEMA",
    "Book",
    "BookLeg",
    "BootCheck",
    "CampaignConfig",
    "CampaignSpec",
    "CellKey",
    "CellStats",
    "GateDecision",
    "GateReason",
    "RunRecord",
    "Trigger",
    "TriggerInputs",
    "TriggerOutcome",
]
