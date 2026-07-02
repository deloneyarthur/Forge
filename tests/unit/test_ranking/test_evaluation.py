"""Tests for forge.ranking.evaluation (D132 / F2) — shadow vs incumbent readout.

Labels MUST agree with the dataset builder's labeling (single `label_for`
source), and the metrics feed the F3 promotion criterion: model AUC ≥
incumbent + 0.05 AND precision@K ≥ incumbent's, per checkpoint window.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import duckdb
import pytest

from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.evaluation import evaluate_shadow

_SINCE = datetime(2026, 6, 10, 17, 17, 13)  # noqa: DTZ001 — naive-UTC convention


def _gated_run(
    *,
    config_hash: str,
    decision: str,
    honest: bool = True,
    cpcv: float | None = None,
    wf: float | None = None,
):
    from datetime import date

    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

    rid = str(uuid.uuid4())
    gate_results = {
        "regime_coverage": GateResult(
            gate_name="regime_coverage",
            passed=True,
            value=None,
            threshold=None,
            detail="" if honest else "coverage_unverified",
        ),
    }
    if cpcv is not None:
        gate_results["cpcv_sharpe_p25"] = GateResult(
            gate_name="cpcv_sharpe_p25", passed=cpcv >= 1.5, value=cpcv, threshold=1.5
        )
    if wf is not None:
        # wf_sharpe_p25 is gate-EMITTED as a metric (not a gate) per D192; passed=True.
        gate_results["wf_sharpe_p25"] = GateResult(
            gate_name="wf_sharpe_p25", passed=True, value=wf, threshold=None
        )
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v17",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results=gate_results,
            decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
            decided_by="runner.forge_minimal",
        ),
    )


def _seed(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, float, float, str]],
    *,
    model_id: str = "aaaa1111bbbb2222",
) -> None:
    """rows: (config_hash, model_score, composite_score, decision)."""
    for config_hash, model_score, composite_score, decision in rows:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), config_hash, _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
            [candidate_id, model_id, model_score, composite_score, _SINCE],
        )
        record_verdicts(conn, [_gated_run(config_hash=config_hash, decision=decision)])


def test_perfect_model_beats_inverted_incumbent() -> None:
    rows = [
        ("aaaa000000000001", 0.9, 0.1, "component"),
        ("aaaa000000000002", 0.8, 0.2, "component"),
        ("aaaa000000000003", 0.2, 0.8, "reject"),
        ("aaaa000000000004", 0.1, 0.9, "reject"),
    ]
    with db_connection() as conn:
        _seed(conn, rows)
        evaluations = evaluate_shadow(conn, since=_SINCE)

    assert len(evaluations) == 1
    ev = evaluations[0]
    assert ev.model_id == "aaaa1111bbbb2222"
    assert ev.n_decided == 4
    assert ev.n_positive == 2
    assert ev.model_auc == pytest.approx(1.0)
    assert ev.incumbent_auc == pytest.approx(0.0)
    assert ev.auc_margin == pytest.approx(1.0)
    assert ev.model_precision_at_k == pytest.approx(1.0)
    assert ev.incumbent_precision_at_k == pytest.approx(0.0)
    assert 0.0 <= ev.model_brier <= 0.1


def test_dishonest_component_labels_zero_in_eval() -> None:
    # Labels must match the dataset builder: a coverage_unverified component is 0.
    with db_connection() as conn:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), "aaaa000000000009", _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
            [candidate_id, "aaaa1111bbbb2222", 0.9, 0.5, _SINCE],
        )
        record_verdicts(
            conn,
            [_gated_run(config_hash="aaaa000000000009", decision="component", honest=False)],
        )
        evaluations = evaluate_shadow(conn, since=_SINCE)

    assert evaluations[0].n_positive == 0
    # Single class — rank metrics undefined, reported as None rather than fake.
    assert evaluations[0].model_auc is None
    assert evaluations[0].auc_margin is None


def test_window_filter_excludes_older_verdicts() -> None:
    rows = [
        ("aaaa000000000001", 0.9, 0.1, "component"),
        ("aaaa000000000002", 0.1, 0.9, "reject"),
    ]
    with db_connection() as conn:
        _seed(conn, rows)
        evaluations = evaluate_shadow(
            conn,
            since=datetime(2026, 6, 11, 0, 0),  # noqa: DTZ001
        )

    assert evaluations == ()


def test_no_shadow_rows_returns_empty() -> None:
    with db_connection() as conn:
        assert evaluate_shadow(conn, since=_SINCE) == ()


# ---------------------------------------------------------------------------
# Tail-aware eval (T1) — predicted cpcv_p25 (tail_score) vs realized cpcv_p25
# ---------------------------------------------------------------------------


def _seed_tail(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, float, float, float, bool]],
    *,
    tail_model_id: str = "tail111122223333",
) -> None:
    """rows: (config_hash, tail_score, composite_score, realized_cpcv, honest)."""
    for config_hash, tail_score, composite_score, cpcv, honest in rows:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), config_hash, _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at, tail_score, tail_model_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                candidate_id,
                "logistic00000000",
                0.5,
                composite_score,
                _SINCE,
                tail_score,
                tail_model_id,
            ],
        )
        record_verdicts(
            conn, [_gated_run(config_hash=config_hash, decision="reject", honest=honest, cpcv=cpcv)]
        )


def test_tail_eval_spearman_and_top_k() -> None:
    from forge.ranking.evaluation import evaluate_tail_shadow

    # tail_score rank-correlates with realized cpcv; composite is anti-correlated.
    rows = [
        ("aaaa000000000001", 0.9, 0.1, 0.95, True),
        ("aaaa000000000002", 0.7, 0.3, 0.80, True),
        ("aaaa000000000003", 0.5, 0.5, 0.50, True),
        ("aaaa000000000004", 0.3, 0.7, 0.30, True),
        ("aaaa000000000005", 0.1, 0.9, 0.10, True),
    ]
    with db_connection() as conn:
        _seed_tail(conn, rows)
        evals = evaluate_tail_shadow(conn, since=_SINCE)

    assert len(evals) == 1
    ev = evals[0]
    assert ev.tail_model_id == "tail111122223333"
    assert ev.n_decided == 5
    assert ev.spearman == pytest.approx(1.0)
    # K = top decile -> 1; top-by-tail picks the highest realized cpcv, top-by-composite the lowest.
    assert ev.model_top_k_mean_cpcv == pytest.approx(0.95)
    assert ev.incumbent_top_k_mean_cpcv == pytest.approx(0.10)
    assert ev.overall_mean_cpcv == pytest.approx(0.53)


def _seed_tail_gates(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, float, float, float, float]],
    *,
    tail_model_id: str = "tail111122223333",
) -> None:
    """rows: (config_hash, tail_score, composite_score, realized_cpcv, realized_wf). All honest."""
    for config_hash, tail_score, composite_score, cpcv, wf in rows:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), config_hash, _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at, tail_score, tail_model_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                candidate_id,
                "logistic00000000",
                0.5,
                composite_score,
                _SINCE,
                tail_score,
                tail_model_id,
            ],
        )
        record_verdicts(
            conn, [_gated_run(config_hash=config_hash, decision="reject", cpcv=cpcv, wf=wf)]
        )


def test_tail_eval_gate_param_selects_realized_column() -> None:
    # R3: the §8.6 tail eval must be parametrizable on the realized gate column so the
    # wf_p25 quality lane accrues its OWN justification streak (predicted vs realized
    # wf_sharpe_p25), not the cpcv one. tail_score tracks realized wf but anti-tracks
    # realized cpcv here — the gate choice must flip the Spearman sign.
    from forge.ranking.evaluation import evaluate_tail_shadow

    rows = [
        # (config_hash, tail_score, composite, realized_cpcv, realized_wf)
        ("aaaa000000000001", 0.9, 0.1, 0.10, 0.95),
        ("aaaa000000000002", 0.7, 0.3, 0.30, 0.80),
        ("aaaa000000000003", 0.5, 0.5, 0.50, 0.50),
        ("aaaa000000000004", 0.3, 0.7, 0.80, 0.30),
        ("aaaa000000000005", 0.1, 0.9, 0.95, 0.10),
    ]
    with db_connection() as conn:
        _seed_tail_gates(conn, rows)
        wf_eval = evaluate_tail_shadow(conn, since=_SINCE, gate="wf_sharpe_p25")
        cpcv_eval = evaluate_tail_shadow(conn, since=_SINCE)  # default gate = cpcv_sharpe_p25

    assert wf_eval[0].spearman == pytest.approx(1.0)  # tail_score tracks realized wf_p25
    assert cpcv_eval[0].spearman == pytest.approx(-1.0)  # and anti-tracks realized cpcv


def test_tail_eval_excludes_unverified_and_missing_cpcv() -> None:
    from forge.ranking.evaluation import evaluate_tail_shadow

    with db_connection() as conn:
        _seed_tail(
            conn,
            [
                ("aaaa000000000001", 0.9, 0.1, 0.95, True),
                ("aaaa000000000002", 0.7, 0.3, 0.80, True),
                ("aaaa000000000003", 0.5, 0.5, 0.99, False),  # unverified — excluded
            ],
        )
        evals = evaluate_tail_shadow(conn, since=_SINCE)

    assert evals[0].n_decided == 2


def test_tail_eval_no_tail_scores_returns_empty() -> None:
    # A shadow row without a tail_score (the pre-train / pre-restart state).
    rows = [
        ("aaaa000000000001", 0.9, 0.1, "component"),
        ("aaaa000000000002", 0.1, 0.9, "reject"),
    ]
    with db_connection() as conn:
        _seed(conn, rows)  # inserts NULL tail_score
        from forge.ranking.evaluation import evaluate_tail_shadow

        assert evaluate_tail_shadow(conn, since=_SINCE) == ()


def test_tail_eval_pooled_across_models() -> None:
    # The §8.6 robustness-streak gate pools across the daily-rolling tail models:
    # tail_score is a prediction of cpcv_p25 in the same units, so pooling is valid
    # and dodges the per-model sparsity from the daily roll.
    from forge.ranking.evaluation import evaluate_tail_shadow, evaluate_tail_shadow_pooled

    with db_connection() as conn:
        _seed_tail(
            conn,
            [
                ("aaaa000000000001", 0.9, 0.1, 0.95, True),
                ("aaaa000000000002", 0.7, 0.3, 0.80, True),
                ("aaaa000000000003", 0.5, 0.5, 0.50, True),
            ],
            tail_model_id="aaaamodel0000001",
        )
        _seed_tail(
            conn,
            [
                ("bbbb000000000001", 0.3, 0.7, 0.30, True),
                ("bbbb000000000002", 0.1, 0.9, 0.10, True),
            ],
            tail_model_id="bbbbmodel0000002",
        )
        per_model = evaluate_tail_shadow(conn, since=_SINCE)
        pooled = evaluate_tail_shadow_pooled(conn, since=_SINCE)

    assert len(per_model) == 2  # per-model split is unchanged
    assert pooled is not None
    assert pooled.tail_model_id == "pooled"
    assert pooled.n_decided == 5  # pooled across both daily models
    assert pooled.spearman == pytest.approx(1.0)  # tail_score orders realized cpcv across the pool
    assert pooled.model_top_k_mean_cpcv == pytest.approx(0.95)  # K=1; top tail-score pick
    assert pooled.incumbent_top_k_mean_cpcv == pytest.approx(0.10)  # top composite pick
    assert pooled.overall_mean_cpcv == pytest.approx(0.53)


def test_tail_eval_pooled_empty_returns_none() -> None:
    from forge.ranking.evaluation import evaluate_tail_shadow_pooled

    with db_connection() as conn:
        assert evaluate_tail_shadow_pooled(conn, since=_SINCE) is None


def test_spearman_corr_perfect_inverted_and_degenerate() -> None:
    from forge.ranking.evaluation import spearman_corr

    assert spearman_corr([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]) == pytest.approx(1.0)
    assert spearman_corr([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    assert spearman_corr([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # zero variance
    assert spearman_corr([1.0], [1.0]) is None  # < 2 points


# ---------------------------------------------------------------------------
# Gate-then-tail re-wire shadow (two-part lane: P gates eligibility, tail orders)
# ---------------------------------------------------------------------------


def test_rewire_topk_surfaces_better_floors_than_p_baseline() -> None:
    from forge.ranking.evaluation import _rewire_topk

    # tail predicts realized perfectly; P(component) is ANTI-correlated with realized
    # (the empirical regime). Ranking by P tops out on the worst floors; gate-then-tail
    # — keep the top half by P, then order by tail — must do better.
    triples = [
        (0.5 - 0.1 * ((i - 50) / 25.0), (i - 50) / 25.0, (i - 50) / 25.0) for i in range(100)
    ]
    ev = _rewire_topk(triples, keep_frac=0.5)
    assert ev.n_decided == 100
    assert ev.k == 10
    assert ev.gate_top_k_mean is not None
    assert ev.base_top_k_mean is not None
    assert ev.delta is not None
    assert ev.delta > 0
    assert ev.gate_top_k_mean > ev.base_top_k_mean


def test_rewire_topk_empty_returns_none_delta() -> None:
    from forge.ranking.evaluation import _rewire_topk

    ev = _rewire_topk([], keep_frac=0.5)
    assert ev.n_decided == 0
    assert ev.delta is None


def _seed_rewire(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, float, float, float, bool]],
    *,
    tail_model_id: str = "tail111122223333",
) -> None:
    """rows: (config_hash, model_score(P), tail_score, realized_wf, honest)."""
    for config_hash, p, tail_score, wf, honest in rows:
        candidate_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
            [candidate_id, str(uuid.uuid4()), config_hash, _SINCE, "gated"],
        )
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at, tail_score, tail_model_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [candidate_id, "logistic00000000", p, 0.0, _SINCE, tail_score, tail_model_id],
        )
        record_verdicts(
            conn, [_gated_run(config_hash=config_hash, decision="reject", honest=honest, wf=wf)]
        )


def test_evaluate_rewire_shadow_beats_p_baseline_on_wf() -> None:
    from forge.ranking.evaluation import evaluate_rewire_shadow

    # tail_score tracks realized wf; P(component) anti-tracks it. Ranking by P alone tops
    # out on the worst floors, so the gate-then-tail re-wire must beat it (delta > 0).
    rows = [
        # (config_hash, P, tail_score, realized_wf, honest)
        ("aaaa000000000001", 0.9, 0.1, 0.10, True),
        ("aaaa000000000002", 0.7, 0.3, 0.30, True),
        ("aaaa000000000003", 0.5, 0.5, 0.50, True),
        ("aaaa000000000004", 0.3, 0.7, 0.80, True),
        ("aaaa000000000005", 0.1, 0.9, 0.95, True),
    ]
    with db_connection() as conn:
        _seed_rewire(conn, rows)
        ev = evaluate_rewire_shadow(conn, since=_SINCE, gate="wf_sharpe_p25", keep_frac=0.6)

    assert ev is not None
    assert ev.n_decided == 5
    assert ev.delta is not None
    assert ev.delta > 0


def test_evaluate_rewire_shadow_excludes_unverified() -> None:
    from forge.ranking.evaluation import evaluate_rewire_shadow

    with db_connection() as conn:
        _seed_rewire(
            conn,
            [
                ("aaaa000000000001", 0.9, 0.1, 0.10, True),
                ("aaaa000000000002", 0.1, 0.9, 0.95, True),
                ("aaaa000000000003", 0.5, 0.5, 0.99, False),  # unverified — excluded
            ],
        )
        ev = evaluate_rewire_shadow(conn, since=_SINCE, gate="wf_sharpe_p25")

    assert ev is not None
    assert ev.n_decided == 2


def test_evaluate_rewire_shadow_empty_returns_none() -> None:
    from forge.ranking.evaluation import evaluate_rewire_shadow

    with db_connection() as conn:
        assert evaluate_rewire_shadow(conn, since=_SINCE, gate="wf_sharpe_p25") is None


def test_rewire_topk_absolute_floor_overrides_keep_frac() -> None:
    """Calibration 2026-06-26: on the skewed production P-dist the keep_frac quantile is
    near-zero, so an absolute floor is the right mechanism. p_floor must override the quantile."""
    from forge.ranking.evaluation import _rewire_topk

    # (P, tail_pred, realized). keep_frac=0.5 -> quantile floor 0.3 (eligible P>=0.3 = {0.3,0.4}).
    triples = [(0.10, 0.9, 0.9), (0.20, 0.1, 0.2), (0.30, 0.5, 0.5), (0.40, 0.2, 0.1)]
    ev_quantile = _rewire_topk(triples, 0.5)
    ev_abs = _rewire_topk(triples, 0.5, p_floor=0.05)  # admits all four

    assert ev_quantile.p_floor == 0.3
    assert ev_abs.p_floor == 0.05
    # k=1; the quantile floor excludes the high-tail low-P config, the absolute floor admits it.
    assert ev_quantile.gate_top_k_mean == 0.5
    assert ev_abs.gate_top_k_mean == 0.9


# ---------------------------------------------------------------------------
# Prior-weight A/B (B2 / P1.4)
# ---------------------------------------------------------------------------


def test_prior_weighted_composite_identities() -> None:
    from forge.ranking.evaluation import prior_weighted_composite

    # At the base 0.10 weight the stored composite is returned unchanged.
    assert prior_weighted_composite(0.9, 0.3, 0.10) == pytest.approx(0.3)
    assert prior_weighted_composite(0.1, 0.8, 0.10) == pytest.approx(0.8)
    # At weight 1.0 the score is pure P (hygiene block zeroed).
    assert prior_weighted_composite(0.7, 0.3, 1.0) == pytest.approx(0.7)
    # As weight rises (P high, composite low) the score moves monotonically toward P.
    lo = prior_weighted_composite(0.9, 0.1, 0.10)
    mid = prior_weighted_composite(0.9, 0.1, 0.5)
    hi = prior_weighted_composite(0.9, 0.1, 0.9)
    assert lo < mid < hi


def test_prior_weight_evals_higher_weight_lifts_component_yield() -> None:
    """P perfectly ranks components; the composite is INVERTED (hygiene fights the
    label). Raising the prior weight must lift the top-K component yield + AUC."""
    from forge.ranking.evaluation import _prior_weight_evals

    pairs = [  # (P, composite, label) — components have high P + low composite
        (0.9, 0.1, 1),
        (0.8, 0.2, 1),
        (0.2, 0.8, 0),
        (0.1, 0.9, 0),
    ]
    base, pure = _prior_weight_evals(pairs, [0.10, 1.0])
    assert base.weight == 0.10
    assert base.n_positive == 2
    assert base.k == 2
    assert base.precision_at_k == pytest.approx(0.0)  # inverted composite ranks components last
    assert base.auc == pytest.approx(0.0)
    assert pure.precision_at_k == pytest.approx(1.0)  # pure P ranks components first
    assert pure.auc == pytest.approx(1.0)


def test_evaluate_prior_weight_ab_db_roundtrip() -> None:
    from forge.ranking.evaluation import evaluate_prior_weight_ab

    rows = [
        ("aaaa000000000001", 0.9, 0.1, "component"),
        ("aaaa000000000002", 0.8, 0.2, "component"),
        ("aaaa000000000003", 0.2, 0.8, "reject"),
        ("aaaa000000000004", 0.1, 0.9, "reject"),
    ]
    with db_connection() as conn:
        _seed(conn, rows)
        evals = evaluate_prior_weight_ab(conn, since=_SINCE, weights=[0.10, 1.0])
    assert len(evals) == 2
    assert evals[0].n_decided == 4
    assert evals[0].n_positive == 2
    assert evals[0].auc == pytest.approx(0.0)  # w=0.10: the inverted composite
    assert evals[1].auc == pytest.approx(1.0)  # w=1.0: pure P
