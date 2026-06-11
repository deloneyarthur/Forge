"""Shadow-vs-incumbent readout for the learned verdict model (D132 / F2).

Joins `shadow_scores ⋈ submissions ⋈ verdicts` over a checkpoint window and
computes, per model_id, the metrics the F3 promotion criterion is judged on:
AUC (model vs the incumbent §6.2 composite), precision@K with K = realized
positives, Brier (model only — the composite is not a probability), and a
calibration table. Labels come from `forge.ranking.dataset.label_for` — the
same function the training frame uses, so eval and training cannot disagree
on what counts as a positive.

Refit children contribute one row per verdict (D124 continuity), mirroring
the training-set policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING

from forge.ranking.dataset import label_for, parse_gate_results
from forge.ranking.model import auc_score, brier_score

if TYPE_CHECKING:
    from datetime import datetime

    import duckdb

# One calibration row: (bin_low_edge, n, mean_model_score, empirical_rate).
CalibrationRow = tuple[float, int, float, float]


@dataclass(frozen=True, slots=True)
class ShadowEvaluation:
    """Window metrics for one model_id. Rank metrics are None on a
    single-class window rather than fabricated."""

    model_id: str
    n_decided: int
    n_positive: int
    model_auc: float | None
    incumbent_auc: float | None
    auc_margin: float | None
    model_precision_at_k: float | None
    incumbent_precision_at_k: float | None
    model_brier: float
    calibration: tuple[CalibrationRow, ...]


def _precision_at_k(labels: list[int], scores: list[float], k: int) -> float:
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return sum(labels[i] for i in order[:k]) / k


def _safe_auc(labels: list[int], scores: list[float]) -> float | None:
    try:
        return auc_score(labels, scores)
    except ValueError:
        return None


def _calibration(labels: list[int], scores: list[float]) -> tuple[CalibrationRow, ...]:
    bins: dict[int, list[tuple[float, int]]] = {}
    for score, label in zip(scores, labels, strict=True):
        bins.setdefault(min(int(score * 10), 9), []).append((score, label))
    rows: list[CalibrationRow] = []
    for index in sorted(bins):
        members = bins[index]
        n = len(members)
        rows.append(
            (
                index / 10.0,
                n,
                sum(s for s, _ in members) / n,
                sum(y for _, y in members) / n,
            )
        )
    return tuple(rows)


def evaluate_shadow(
    conn: duckdb.DuckDBPyConnection, *, since: datetime
) -> tuple[ShadowEvaluation, ...]:
    """One evaluation per model_id over verdicts decided in the window."""
    cut = since
    if cut.tzinfo is not None:
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT ss.model_id, ss.model_score, ss.composite_score,
               v.decision, v.gate_results
        FROM shadow_scores ss
        JOIN submissions s ON ss.forge_candidate_id = s.forge_candidate_id
        JOIN verdicts v ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ?
        ORDER BY ss.model_id, ss.forge_candidate_id, v.crucible_run_id
        """,
        [cut],
    ).fetchall()

    by_model: dict[str, list[tuple[float, float, int]]] = {}
    for model_id, model_score, composite_score, decision, gate_results_json in rows:
        label = label_for(decision, parse_gate_results(gate_results_json))
        by_model.setdefault(model_id, []).append(
            (float(model_score), float(composite_score), label)
        )

    evaluations: list[ShadowEvaluation] = []
    for model_id in sorted(by_model):
        triples = by_model[model_id]
        labels = [y for _, _, y in triples]
        model_scores = [m for m, _, _ in triples]
        composite_scores = [c for _, c, _ in triples]
        k = sum(labels)
        model_auc = _safe_auc(labels, model_scores)
        incumbent_auc = _safe_auc(labels, composite_scores)
        evaluations.append(
            ShadowEvaluation(
                model_id=model_id,
                n_decided=len(labels),
                n_positive=k,
                model_auc=model_auc,
                incumbent_auc=incumbent_auc,
                auc_margin=(
                    model_auc - incumbent_auc
                    if model_auc is not None and incumbent_auc is not None
                    else None
                ),
                model_precision_at_k=(_precision_at_k(labels, model_scores, k) if k else None),
                incumbent_precision_at_k=(
                    _precision_at_k(labels, composite_scores, k) if k else None
                ),
                model_brier=brier_score(labels, model_scores),
                calibration=_calibration(labels, model_scores),
            )
        )
    return tuple(evaluations)
