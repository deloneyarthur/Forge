"""Young-CELL exploration floor — data side (D307, Theme 2b).

WHY: the D287 lesson generalized. A (directional, regime) CELL can be starved
at selection even when both of its arms are individually mature — the D136
arm floor keys on ``(role, indicator_id)``, so vix_term_slope maturing within
days of v27 left the resid x vix PAIR unprotected, and it took a hand pin
(the retired D287 hand pin) plus a diagnosis session to fix. This module gives every
cell younger than K honest-era verdicts automatic floor slots; the campaign
registry's hand-pinned cells become the OVERRIDE (bigger slot counts for
cells Crucible explicitly asked to read), not the only mechanism.

A cell is the ``campaigns.config_cell`` key: (first directional
indicator, first regime indicator). Maturity mirrors the arm floor exactly —
≥ K verdict rows in the honest era, ve ghost rows excluded (D290) — so
"mature" keeps meaning "the learner has had a chance to see it".

Flag-gated OFF (`FORGE_YOUNG_CELL_FLOOR`, main.py): `mature_cells=None` keeps
production selection byte-identical until the operator's deploy window flips
the env. The selection mechanics live in ``forge.ranking.diversifier``
(phase 0c); this module owns the maturity query.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT, VE_GHOST_LABEL_CUT
from forge.ranking.campaigns import ExperimentCell, config_cell_from_json

if TYPE_CHECKING:
    import duckdb

# Mirrors the D132 §8 arm-floor parameters (K=25 / 2 slots / ≤10% batch) —
# same operator-approved shape, one granularity level down. The pinned
# experiment-cell floor (D287/D299) keeps its own larger slot count.
YOUNG_CELL_VERDICT_THRESHOLD: int = 25
CELL_FLOOR_SLOTS_PER_CELL: int = 2
CELL_FLOOR_BATCH_FRACTION: float = 0.10


def compute_mature_cells(
    conn: duckdb.DuckDBPyConnection,
    *,
    era_cut: datetime = CLEAN_ERA_LABEL_CUT,
    threshold: int = YOUNG_CELL_VERDICT_THRESHOLD,
) -> frozenset[ExperimentCell]:
    """Cells with ≥ ``threshold`` honest-era verdicts (everything else is
    young). Counts VERDICT rows, not configs, mirroring
    ``arm_floor.compute_mature_arms`` — a refit child is an independent gate
    evaluation (D124). Ghost-era ve rows never mature a cell (D290)."""
    cut = era_cut
    if cut.tzinfo is not None:
        # DuckDB TIMESTAMP columns are naive-UTC by repo convention.
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    ve_cut = VE_GHOST_LABEL_CUT.astimezone(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT s.config_json, COUNT(*)
        FROM verdicts v
        JOIN submissions s ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ?
          AND NOT (
            json_extract_string(s.config_json, '$.hypothesis') = 'volatility_event'
            AND v.decided_at < ?
          )
        GROUP BY s.config_json
        """,
        [cut, ve_cut],
    ).fetchall()
    counts: Counter[ExperimentCell] = Counter()
    for config_json, n in rows:
        cell = config_cell_from_json(json.loads(config_json))
        if cell is not None:
            counts[cell] += int(n)
    return frozenset(cell for cell, count in counts.items() if count >= threshold)


__all__ = [
    "CELL_FLOOR_BATCH_FRACTION",
    "CELL_FLOOR_SLOTS_PER_CELL",
    "YOUNG_CELL_VERDICT_THRESHOLD",
    "compute_mature_cells",
]
