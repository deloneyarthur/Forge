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

CLEAN_ERA_LABEL_CUT: datetime = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
VE_GHOST_LABEL_CUT: datetime = datetime(2026, 7, 18, 0, 0, 0, tzinfo=UTC)

__all__ = ["CLEAN_ERA_LABEL_CUT", "VE_GHOST_LABEL_CUT"]
