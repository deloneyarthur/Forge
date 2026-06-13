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

import math
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING

from forge.feedback.rejection_weights import honest_regime_coverage_row
from forge.ranking.dataset import label_for, parse_gate_results
from forge.ranking.model import auc_score, brier_score

if TYPE_CHECKING:
    from collections.abc import Sequence
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


# ---------------------------------------------------------------------------
# Tail-aware eval (T1) — predicted cpcv_p25 (tail_score) vs realized cpcv_p25
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TailEvaluation:
    """Window metrics for one tail_model_id: does ranking by the predicted
    `cpcv_p25` (tail_score) surface configs with higher REALIZED `cpcv_p25`?
    `spearman` is None on <2 points / all-ties; the top-K means compare the tail
    model's top picks against the incumbent composite's, both over the same window."""

    tail_model_id: str
    n_decided: int
    spearman: float | None
    k: int
    model_top_k_mean_cpcv: float | None
    incumbent_top_k_mean_cpcv: float | None
    overall_mean_cpcv: float | None


def _average_ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks, ties sharing their average rank (deterministic)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman_corr(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank-correlation (Pearson on average ranks). None on <2 points or
    a zero-variance side (all ties) — not a fabricated 0."""
    if len(xs) < 2:
        return None
    rx, ry = _average_ranks(xs), _average_ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx <= 0.0 or vy <= 0.0:
        return None
    return cov / math.sqrt(vx * vy)


def _top_k_mean(pairs: list[tuple[float, float]], k: int) -> float | None:
    """Mean of the second element over the top-k pairs by the first (desc)."""
    if not pairs or k <= 0:
        return None
    top = sorted(pairs, key=lambda p: -p[0])[:k]
    return sum(value for _, value in top) / len(top)


def evaluate_tail_shadow(
    conn: duckdb.DuckDBPyConnection, *, since: datetime
) -> tuple[TailEvaluation, ...]:
    """One eval per tail_model_id over the window. Restricted to verified-coverage
    rows carrying a `cpcv_sharpe_p25` value — apples-to-apples with what the tail
    model predicts (the §8.2 score-time convention assumes verified coverage)."""
    cut = since
    if cut.tzinfo is not None:
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT ss.tail_model_id, ss.tail_score, ss.composite_score, v.gate_results
        FROM shadow_scores ss
        JOIN submissions s ON ss.forge_candidate_id = s.forge_candidate_id
        JOIN verdicts v ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ? AND ss.tail_score IS NOT NULL AND ss.tail_model_id IS NOT NULL
        ORDER BY ss.tail_model_id, ss.forge_candidate_id, v.crucible_run_id
        """,
        [cut],
    ).fetchall()

    by_model: dict[str, list[tuple[float, float, float]]] = {}
    for tail_model_id, tail_score, composite_score, gate_results_json in rows:
        gate_results = parse_gate_results(gate_results_json)
        if not honest_regime_coverage_row(gate_results):
            continue
        cpcv = gate_results.get("cpcv_sharpe_p25")
        if cpcv is None or cpcv.value is None:
            continue
        by_model.setdefault(tail_model_id, []).append(
            (float(tail_score), float(composite_score), float(cpcv.value))
        )

    evaluations: list[TailEvaluation] = []
    for tail_model_id in sorted(by_model):
        triples = by_model[tail_model_id]
        n = len(triples)
        tail_scores = [t for t, _, _ in triples]
        composites = [c for _, c, _ in triples]
        cpcvs = [v for _, _, v in triples]
        k = max(1, n // 10)
        evaluations.append(
            TailEvaluation(
                tail_model_id=tail_model_id,
                n_decided=n,
                spearman=spearman_corr(tail_scores, cpcvs),
                k=k,
                model_top_k_mean_cpcv=_top_k_mean(list(zip(tail_scores, cpcvs, strict=True)), k),
                incumbent_top_k_mean_cpcv=_top_k_mean(list(zip(composites, cpcvs, strict=True)), k),
                overall_mean_cpcv=(sum(cpcvs) / n if n else None),
            )
        )
    return tuple(evaluations)
