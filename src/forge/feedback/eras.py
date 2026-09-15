"""The label-era cuts every learned reader honours — one home, no copies.

WHY a leaf module: these two literals decide which Crucible verdicts count as
evidence anywhere in Forge (the weight learners, the trainers, the young-cell
and arm floors, the yield auditor, the weekly campaign's cell stats). They used
to live inside ``feedback/rejection_weights.py`` — a 1,100-line weight learner
the final-state tree retires (plan 2026-09 §12.4) — so every survivor that only
needed the dates had to import the learner. Literal constants, not clock reads
(hard rule #8 untouched).

``CLEAN_ERA_LABEL_CUT`` — label-era key for the learned verdict model (D132 /
F1). Stricter than the value cut on purpose: training LABELS must come from the
engine that enforces earnings exits and reads correct single-name chains — the
composite clean-era boundary (Crucible's exit-era runner restart, D130/D131;
the v2 registry and v17 followed within 19 minutes of the same boot). Any era
boundary declared after a model's training cutoff obsoletes that model (the F3
era guard refuses it).

``VE_GHOST_LABEL_CUT`` — D290 (the v39 companion), the ve ghost-label cut.
Crucible's 2026-07-19 ve close-out: 23/25 stored-cpcv ve components were GHOSTS
(their put_wall/gex/vex/cex staleness blind spot, fixed their side 2026-07-18),
and 34,273 ve verdicts / 657 fictional components sat inside the clean-era
training window — ~10% of all positive labels. Their §6 ask: treat pre-07-18 ve
stored scores as unrankable. ``volatility_event`` rows decided before this cut
are excluded from EVERY learned reader; non-ve rows and post-cut ve rows are
untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult

CLEAN_ERA_LABEL_CUT: datetime = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
VE_GHOST_LABEL_CUT: datetime = datetime(2026, 7, 18, 0, 0, 0, tzinfo=UTC)

_VE_GHOST_HYPOTHESIS = "volatility_event"

# D124 key 2: the coverage gate's name and the marker Crucible writes into its `detail` when the
# gate was NOT actually evaluated (a pass with this mark is a passthrough, not verified coverage).
_COVERAGE_GATE: str = "regime_coverage"
_COVERAGE_UNVERIFIED_MARK: str = "coverage_unverified"


def is_ve_ghost_label(hypothesis: str | None, decided_at: datetime) -> bool:
    """True iff this (hypothesis, decided_at) label falls under the ve ghost cut.

    Naive timestamps are UTC by repo convention (the verdicts/export era is
    uniform post-D117)."""
    if hypothesis != _VE_GHOST_HYPOTHESIS:
        return False
    decided = decided_at
    if decided.tzinfo is None:
        decided = decided.replace(tzinfo=UTC)
    return decided < VE_GHOST_LABEL_CUT


def honest_regime_coverage_row(gate_results: Mapping[str, GateResult]) -> bool:
    """D124 key 2 on a bare gate-results mapping — the single source of truth.

    Shared by the learned verdict model's label builder (D132) and the trainer
    invariants, so the two reads cannot drift: True only when the coverage gate
    REALLY evaluated and passed.
    """
    row = gate_results.get(_COVERAGE_GATE)
    return row is not None and row.passed and _COVERAGE_UNVERIFIED_MARK not in (row.detail or "")


def _honest_regime_coverage(gated_run: GatedRun) -> bool:
    """D124 key 2 on a whole `GatedRun`."""
    return honest_regime_coverage_row(gated_run.decision.gate_results)


__all__ = [
    "CLEAN_ERA_LABEL_CUT",
    "VE_GHOST_LABEL_CUT",
    "honest_regime_coverage_row",
    "is_ve_ghost_label",
]
