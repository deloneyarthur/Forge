"""Shadow scoring for the learned verdict model (D132 / F2) — telemetry only.

`run_shadow_scoring` is called from the production loop AFTER selection and
submission, so it cannot influence what gets submitted (the design's shadow
no-op invariant). It reads the just-written submissions rows for the batch,
scores each submitted candidate with the latest model artifact, and records
(model_score, composite_score) pairs for the later `forge ranker-model eval`
comparison.

Failure posture: this is instrumentation — ANY internal error degrades to
"0 rows recorded" with a structlog warning (the funnel-export precedent in
the loop). No model artifact / no models dir is the normal pre-F2-training
state and logs nothing above debug.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from forge.ranking.features import extract_features
from forge.ranking.model import load_latest_model, score_features

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

    import duckdb
    from crucible_contracts import RegistrySnapshot

    from forge.ranking.types import RankedCandidate

_LOG = structlog.get_logger(__name__)


def run_shadow_scoring(
    conn: duckdb.DuckDBPyConnection,
    *,
    models_dir: Path,
    candidates: Sequence[RankedCandidate],
    registry: RegistrySnapshot,
    batch_id: str,
    scored_at: datetime,
) -> int:
    """Record shadow scores for the batch's submitted candidates; never raises."""
    try:
        model = load_latest_model(models_dir)
        if model is None:
            return 0
        by_hash = {c.report.config.config_hash: c for c in candidates}
        rows = conn.execute(
            "SELECT forge_candidate_id, config_hash FROM submissions WHERE forge_batch_id = ?",
            [batch_id],
        ).fetchall()
        recorded = 0
        for candidate_id, config_hash in rows:
            candidate = by_hash.get(config_hash)
            if candidate is None:
                continue
            features = extract_features(candidate.report.config, registry).as_dict()
            conn.execute(
                "INSERT OR IGNORE INTO shadow_scores (forge_candidate_id, model_id, "
                "model_score, composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
                [
                    str(candidate_id),
                    model.model_id,
                    score_features(model, features),
                    candidate.composite_score,
                    scored_at,
                ],
            )
            recorded += 1
        _LOG.info(
            "shadow_scores_recorded",
            model_id=model.model_id,
            batch_id=batch_id,
            recorded=recorded,
        )
        return recorded
    except Exception as exc:
        _LOG.warning("shadow_scoring_failed", batch_id=batch_id, error=str(exc))
        return 0
