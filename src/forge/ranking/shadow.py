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
from forge.ranking.model import (
    load_latest_model,
    load_latest_robustness_model,
    score_features,
    score_robustness,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import datetime
    from pathlib import Path

    import duckdb
    from crucible_contracts import RegistrySnapshot

    from forge.prefilters.types import PreFilterReport
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
    robustness_target: str | None = None,
    hygiene_scorer: Callable[[PreFilterReport], float] | None = None,
) -> int:
    """Record shadow scores for the batch's submitted candidates; never raises.

    ``robustness_target`` selects which robustness model to shadow (it shares the dir
    with the daily-retrained cpcv model); ``None`` keeps the original target-blind
    "newest" behavior. The production loop passes ``target_wf_p25`` so the §8.6 streak
    measures the model the quality lane uses (D191/D192).

    ``hygiene_scorer`` records the model-free §6.2 hygiene composite per row
    (comparator fix): ``composite_score`` stores whatever score production ordered
    by — under gate-tail mode that is the lane's own value, which turns any eval
    reading it as "the incumbent" self-referential. ``None`` (pre-fix callers)
    leaves the column NULL.
    """
    try:
        model = load_latest_model(models_dir)
        if model is None:
            return 0
        # D140: also score the tail-aware robustness model when one exists. NULL
        # otherwise (and for the whole pre-train history) — telemetry only; the
        # loop never reads tail_score, so this changes no submission behavior.
        robustness = load_latest_robustness_model(models_dir, target=robustness_target)
        tail_model_id = robustness.model_id if robustness is not None else None
        by_hash = {c.report.config.config_hash: c for c in candidates}
        rows = conn.execute(
            "SELECT forge_candidate_id, config_hash FROM submissions WHERE forge_batch_id = ?",
            [batch_id],
        ).fetchall()
        # P3-4 (F9): one transaction for the whole batch instead of per-row autocommit —
        # DuckDB WAL-fsyncs every autocommitted INSERT (~200 fsyncs/batch). Same rows,
        # one commit. On any failure ROLLBACK then re-raise into the outer handler so the
        # never-raises posture holds AND the shared connection isn't left mid-transaction.
        recorded = 0
        conn.execute("BEGIN TRANSACTION")
        try:
            for candidate_id, config_hash in rows:
                candidate = by_hash.get(config_hash)
                if candidate is None:
                    continue
                features = extract_features(candidate.report.config, registry).as_dict()
                tail_score = (
                    score_robustness(robustness, features) if robustness is not None else None
                )
                hygiene_score = (
                    hygiene_scorer(candidate.report) if hygiene_scorer is not None else None
                )
                conn.execute(
                    "INSERT OR IGNORE INTO shadow_scores (forge_candidate_id, model_id, "
                    "model_score, composite_score, scored_at, tail_score, tail_model_id, "
                    "hygiene_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        str(candidate_id),
                        model.model_id,
                        score_features(model, features),
                        candidate.composite_score,
                        scored_at,
                        tail_score,
                        tail_model_id,
                        hygiene_score,
                    ],
                )
                recorded += 1
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        _LOG.info(
            "shadow_scores_recorded",
            model_id=model.model_id,
            tail_model_id=tail_model_id,
            batch_id=batch_id,
            recorded=recorded,
        )
        return recorded
    except Exception as exc:
        _LOG.warning("shadow_scoring_failed", batch_id=batch_id, error=str(exc))
        return 0
