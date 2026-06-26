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
from forge.ranking.model import auc_score, brier_score, gate_tail_rank_score

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


# tail_model_id sentinel for the cross-model pooled evaluation (§8.6 streak). The
# daily timer rolls a fresh robustness model each run, so per-model windows stay
# sparse; tail_score is a prediction of `cpcv_p25` in the SAME units across models,
# so pooling the (score, realized) pairs is the apples-to-apples methodology check.
_POOLED_TAIL_MODEL_ID = "pooled"


# The realized worst-quartile gate the tail eval correlates predictions against. The
# original cpcv lane (D147) used cpcv_sharpe_p25; the wf_p25 quality lane (D191/D192)
# uses wf_sharpe_p25 — both are gate-emitted metrics in `gate_results`.
_DEFAULT_TAIL_GATE = "cpcv_sharpe_p25"


def _tail_triples_by_model(
    conn: duckdb.DuckDBPyConnection, *, since: datetime, gate: str = _DEFAULT_TAIL_GATE
) -> dict[str, list[tuple[float, float, float]]]:
    """`(tail_score, composite_score, realized `gate` value)` per tail_model_id over the
    window. Restricted to verified-coverage rows carrying a `gate` value — apples-to-apples
    with what the tail model predicts (§8.2 assumes verified coverage)."""
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
        realized = gate_results.get(gate)
        if realized is None or realized.value is None:
            continue
        by_model.setdefault(tail_model_id, []).append(
            (float(tail_score), float(composite_score), float(realized.value))
        )
    return by_model


def _build_tail_eval(
    tail_model_id: str, triples: list[tuple[float, float, float]]
) -> TailEvaluation:
    n = len(triples)
    tail_scores = [t for t, _, _ in triples]
    composites = [c for _, c, _ in triples]
    cpcvs = [v for _, _, v in triples]
    k = max(1, n // 10)
    return TailEvaluation(
        tail_model_id=tail_model_id,
        n_decided=n,
        spearman=spearman_corr(tail_scores, cpcvs),
        k=k,
        model_top_k_mean_cpcv=_top_k_mean(list(zip(tail_scores, cpcvs, strict=True)), k),
        incumbent_top_k_mean_cpcv=_top_k_mean(list(zip(composites, cpcvs, strict=True)), k),
        overall_mean_cpcv=(sum(cpcvs) / n if n else None),
    )


def evaluate_tail_shadow(
    conn: duckdb.DuckDBPyConnection, *, since: datetime, gate: str = _DEFAULT_TAIL_GATE
) -> tuple[TailEvaluation, ...]:
    """One eval per tail_model_id over the window (journal/CLI breakdown)."""
    by_model = _tail_triples_by_model(conn, since=since, gate=gate)
    return tuple(_build_tail_eval(model_id, by_model[model_id]) for model_id in sorted(by_model))


def evaluate_tail_shadow_pooled(
    conn: duckdb.DuckDBPyConnection, *, since: datetime, gate: str = _DEFAULT_TAIL_GATE
) -> TailEvaluation | None:
    """One eval POOLED across every tail_model_id in the window — the §8.6 streak
    statistic. `None` when no verified-coverage `gate`-bearing tail-scored verdict
    decided in the window (a checkpoint with nothing to judge)."""
    by_model = _tail_triples_by_model(conn, since=since, gate=gate)
    pooled = [triple for model_id in sorted(by_model) for triple in by_model[model_id]]
    if not pooled:
        return None
    return _build_tail_eval(_POOLED_TAIL_MODEL_ID, pooled)


# ---------------------------------------------------------------------------
# Gate-then-tail re-wire shadow — the two-part lane (P gates, tail orders)
# ---------------------------------------------------------------------------
# The deployed wf_p25 lane multiplies P(component) by the tail prediction; the
# 2026-06-26 A/B showed that product is swamped by P (which anti-correlates with the
# WF floor) and nets ~0. This readout shadows the re-wire — P gates eligibility, the
# tail prediction orders the survivors — against the P-alone baseline, on realized
# worst-quartile WF. Telemetry only; the production loop never reads it until the lane
# mode is flipped. Design: docs/proposals/quality-lane-rewire.md.

# Default eligibility gate: keep the top 50% by P(component), then rank by tail. The A/B's
# strongest pre-specified two-part form; the production floor is calibrated separately.
_REWIRE_KEEP_FRAC: float = 0.5


@dataclass(frozen=True, slots=True)
class RewireEvaluation:
    """Gate-then-tail (two-part) lane vs the P(component) baseline over one window.

    `delta` = gate-then-tail top-K mean realized minus the baseline's; positive ⇒ the
    re-wire surfaces configs with a higher realized worst-quartile WF floor than ranking
    by P(component) alone."""

    n_decided: int
    k: int
    p_floor: float
    keep_frac: float
    gate_top_k_mean: float | None
    base_top_k_mean: float | None
    delta: float | None
    overall_mean: float | None


def _rewire_topk(
    triples: Sequence[tuple[float, float, float]], keep_frac: float = _REWIRE_KEEP_FRAC
) -> RewireEvaluation:
    """`triples` = (P(component), tail_pred, realized). The gate keeps the top `keep_frac`
    by P and ranks survivors by `tail_pred`; the baseline ranks all by P. Pure (no DB) so
    the ranking contract is unit-testable. Top-K uses the same decile K as the tail eval."""
    n = len(triples)
    if n == 0:
        return RewireEvaluation(0, 0, 0.0, keep_frac, None, None, None, None)
    ps = sorted(t[0] for t in triples)
    p_floor = ps[min(n - 1, int((1.0 - keep_frac) * n))]
    realized = [t[2] for t in triples]
    gate_scores = [gate_tail_rank_score(p, tail, p_floor=p_floor) for p, tail, _ in triples]
    base_scores = [t[0] for t in triples]
    k = max(1, n // 10)
    gate_mean = _top_k_mean(list(zip(gate_scores, realized, strict=True)), k)
    base_mean = _top_k_mean(list(zip(base_scores, realized, strict=True)), k)
    delta = (
        gate_mean - base_mean if gate_mean is not None and base_mean is not None else None
    )
    return RewireEvaluation(
        n_decided=n,
        k=k,
        p_floor=p_floor,
        keep_frac=keep_frac,
        gate_top_k_mean=gate_mean,
        base_top_k_mean=base_mean,
        delta=delta,
        overall_mean=sum(realized) / n,
    )


def _rewire_triples(
    conn: duckdb.DuckDBPyConnection, *, since: datetime, gate: str
) -> list[tuple[float, float, float]]:
    """(P(component), tail_pred, realized `gate`) over verified-coverage decided verdicts
    carrying a `gate` value — the gate-then-tail eval population. Same join/filter as the
    tail eval, plus `model_score` (the F3 P(component) shadow score)."""
    cut = since
    if cut.tzinfo is not None:
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT ss.model_score, ss.tail_score, v.gate_results
        FROM shadow_scores ss
        JOIN submissions s ON ss.forge_candidate_id = s.forge_candidate_id
        JOIN verdicts v ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ? AND ss.tail_score IS NOT NULL AND ss.tail_model_id IS NOT NULL
        ORDER BY ss.forge_candidate_id, v.crucible_run_id
        """,
        [cut],
    ).fetchall()
    triples: list[tuple[float, float, float]] = []
    for model_score, tail_score, gate_results_json in rows:
        gate_results = parse_gate_results(gate_results_json)
        if not honest_regime_coverage_row(gate_results):
            continue
        realized = gate_results.get(gate)
        if realized is None or realized.value is None:
            continue
        triples.append((float(model_score), float(tail_score), float(realized.value)))
    return triples


def evaluate_rewire_shadow(
    conn: duckdb.DuckDBPyConnection,
    *,
    since: datetime,
    gate: str = _DEFAULT_TAIL_GATE,
    keep_frac: float = _REWIRE_KEEP_FRAC,
) -> RewireEvaluation | None:
    """Shadow readout for the gate-then-tail re-wire: does gating eligibility on
    P(component) and ordering survivors by the predicted WF floor surface configs with a
    higher REALIZED `gate` than ranking by P(component) alone? `None` when the window holds
    no verified-coverage gate-bearing tail-scored verdict. Telemetry only — the production
    loop never reads this until the lane mode is flipped."""
    triples = _rewire_triples(conn, since=since, gate=gate)
    if not triples:
        return None
    return _rewire_topk(triples, keep_frac)
