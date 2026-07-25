"""Tests for forge.ranking.shadow (D132 / F2) — telemetry-only shadow scoring.

The recorder runs AFTER selection and submission, reads everything and
mutates nothing but the `shadow_scores` table, and must never raise into
the production loop — a missing/corrupt model, a missing table row, or any
internal error degrades to "0 rows recorded" with a structlog warning.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import polars as pl
import pytest

from forge.persistence.db import db_connection
from forge.prefilters.types import PreFilterReport
from forge.ranking.model import (
    save_model,
    save_robustness_model,
    train_robustness_model,
    train_verdict_model,
)
from forge.ranking.shadow import run_shadow_scoring
from forge.ranking.types import RankedCandidate
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()
_ERA_CUT = datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC)
_SCORED_AT = datetime(2026, 6, 10, 22, 0, 0)  # noqa: DTZ001 — naive-UTC convention


def _toy_model_dir(tmp_path: Path) -> Path:
    records = []
    for i in range(30):
        records.append(
            {
                "crucible_run_id": f"run-{i:04d}",
                "config_hash": f"hash{i:012d}",
                "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                "decision": "component" if i % 5 == 0 else "reject",
                "label": int(i % 5 == 0),
                "hypothesis=mean_reversion": 1.0,
                "f_noise": float(i % 3),
            }
        )
    model = train_verdict_model(pl.DataFrame(records), era_cut=_ERA_CUT)
    models_dir = tmp_path / "models"
    save_model(model, models_dir)
    return models_dir


def _toy_models_dir_with_tail(tmp_path: Path) -> Path:
    """A logistic model AND a robustness model in the same dir (D140)."""
    models_dir = _toy_model_dir(tmp_path)
    records = []
    for i in range(30):
        records.append(
            {
                "crucible_run_id": f"run-{i:04d}",
                "config_hash": f"hash{i:012d}",
                "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                "decision": "component" if i % 5 == 0 else "reject",
                "label": int(i % 5 == 0),
                "target_cpcv_p25": 0.3 + 0.5 * (i % 5 == 0),
                "coverage_verified": float(i % 4 != 0),
                "hypothesis=mean_reversion": 1.0,
                "f_noise": float(i % 3),
            }
        )
    model = train_robustness_model(pl.DataFrame(records), era_cut=_ERA_CUT)
    save_robustness_model(model, models_dir)
    return models_dir


def _add_robustness_model(models_dir: Path, *, target: str) -> str:
    """Train + save a robustness model on `target` into an existing models dir; returns
    its model_id (the toy rows carry the target column directly)."""
    records = []
    for i in range(30):
        records.append(
            {
                "crucible_run_id": f"run-{i:04d}",
                "config_hash": f"hash{i:012d}",
                "decided_at": datetime(2026, 6, 11, 18, 0, i),  # noqa: DTZ001 — distinct day
                "decision": "component" if i % 5 == 0 else "reject",
                "label": int(i % 5 == 0),
                target: 0.3 + 0.5 * (i % 5 == 0),
                "coverage_verified": float(i % 4 != 0),
                "hypothesis=mean_reversion": 1.0,
                "f_noise": float(i % 3),
            }
        )
    model = train_robustness_model(pl.DataFrame(records), target=target, era_cut=_ERA_CUT)
    save_robustness_model(model, models_dir)
    return model.model_id


def _candidate(composite: float = 0.7) -> RankedCandidate:
    return RankedCandidate(
        report=PreFilterReport(
            config=minimal_strategy_config(),
            passed=True,
            filter_results={},
            diagnostic_notes=(),
        ),
        prior_promotion_score=0.0,
        composite_score=composite,
    )


def _insert_submission(db: duckdb.DuckDBPyConnection, *, batch_id: str, config_hash: str) -> str:
    candidate_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
        [candidate_id, batch_id, config_hash, _SCORED_AT, "submitted"],
    )
    return candidate_id


def test_shadow_scores_table_created_by_ensure_schema() -> None:
    with db_connection() as conn:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'shadow_scores'",
        ).fetchall()
    assert {c[0] for c in cols} == {
        "forge_candidate_id",
        "model_id",
        "model_score",
        "composite_score",
        "scored_at",
        "tail_score",
        "tail_model_id",
        "hygiene_score",
    }


def test_records_scores_for_submitted_candidates(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate(composite=0.7)
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        rows = conn.execute(
            "SELECT model_id, model_score, composite_score FROM shadow_scores",
        ).fetchall()

    assert recorded == 1
    assert len(rows) == 1
    model_id, model_score, composite_score = rows[0]
    assert len(model_id) == 16
    assert 0.0 <= model_score <= 1.0
    assert composite_score == 0.7


def test_hygiene_score_recorded_when_scorer_passed(tmp_path: Path) -> None:
    """The comparator fix: a hygiene scorer records the model-free §6.2 composite
    per row, giving the eval clocks an incumbent that is stable across lane-mode
    flips (under gate-tail the ranking score is the lane's own value)."""
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate(composite=0.7)
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
            hygiene_scorer=lambda _report: 0.42,
        )
        rows = conn.execute("SELECT hygiene_score FROM shadow_scores").fetchall()

    assert recorded == 1
    assert rows[0][0] == pytest.approx(0.42)


def test_one_unscoreable_report_does_not_discard_the_whole_batch(tmp_path: Path) -> None:
    """REGRESSION (2026-07-24): the D335 honest arm wraps prefilter-REJECTED reports,
    whose `filter_results` are incomplete because the prefilter short-circuits on the
    first failure. `Ranker.score` raises on such a report by design, the exception
    escaped to the batch-level handler, and the whole transaction ROLLED BACK — so a
    single honest-arm config silently discarded shadow scores for every RANKED row too.
    Shadow scoring went dark for ~11,600 submissions across two days before this was
    caught. A row the hygiene scorer cannot score must record hygiene_score NULL (the
    column's existing 'unavailable' value) and the batch must still commit."""
    models_dir = _toy_model_dir(tmp_path)
    good = _candidate(composite=0.7)
    bad = RankedCandidate(
        report=PreFilterReport(
            config=minimal_strategy_config(name="unscoreable_reject"),
            passed=False,  # a prefilter REJECT: short-circuited, incomplete results
            filter_results={},
            diagnostic_notes=(),
        ),
        prior_promotion_score=0.0,
        composite_score=0.0,
    )
    batch_id = str(uuid.uuid4())

    def _raises_on_bad(report: object) -> float:
        cfg_hash = report.config.config_hash  # type: ignore[attr-defined]
        if cfg_hash == bad.report.config.config_hash:
            msg = "Ranker.score: PreFilterReport missing filter result 'novelty'"
            raise ValueError(msg)
        return 0.42

    with db_connection() as conn:
        for c in (good, bad):
            _insert_submission(conn, batch_id=batch_id, config_hash=c.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[good, bad],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
            hygiene_scorer=_raises_on_bad,
        )
        rows = dict(
            conn.execute(
                "SELECT s.config_hash, sc.hygiene_score FROM shadow_scores sc "
                "JOIN submissions s ON s.forge_candidate_id = sc.forge_candidate_id"
            ).fetchall()
        )

    assert recorded == 2, "both rows must be recorded; the batch must not roll back"
    assert rows[good.report.config.config_hash] == pytest.approx(0.42)
    assert rows[bad.report.config.config_hash] is None, "unscoreable -> NULL, not a crash"


def test_hygiene_score_null_without_scorer(tmp_path: Path) -> None:
    """No hygiene scorer (pre-fix callers, historical rows) -> NULL, not a fabricated 0."""
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate(composite=0.7)
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        rows = conn.execute("SELECT hygiene_score FROM shadow_scores").fetchall()

    assert recorded == 1
    assert rows[0][0] is None


def test_shadow_scoring_rolls_back_and_never_raises_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # P3-4: the write is one transaction. A mid-batch failure must (a) never raise (telemetry
    # posture), (b) roll back so no partial rows land, and (c) leave the SHARED connection
    # usable — not stuck mid-transaction.
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())

    def _boom(*_args: object, **_kwargs: object) -> float:
        raise RuntimeError("scoring blew up mid-batch")

    monkeypatch.setattr("forge.ranking.shadow.score_features", _boom)
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        assert recorded == 0  # never raised — returned the failure sentinel
        assert conn.execute("SELECT COUNT(*) FROM shadow_scores").fetchone()[0] == 0  # rolled back
        # The connection is not wedged in an open transaction: a follow-up write succeeds.
        conn.execute(
            "INSERT INTO shadow_scores (forge_candidate_id, model_id, model_score, "
            "composite_score, scored_at) VALUES (?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), "m" * 16, 0.5, 0.5, _SCORED_AT],
        )
        assert conn.execute("SELECT COUNT(*) FROM shadow_scores").fetchone()[0] == 1


def test_no_models_dir_is_noop(tmp_path: Path) -> None:
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=tmp_path / "absent",
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        count = conn.execute("SELECT count(*) FROM shadow_scores").fetchone()

    assert recorded == 0
    assert count is not None
    assert count[0] == 0


def test_corrupt_only_models_dir_is_noop(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "verdict_model_v1_bad.json").write_text("{nope", encoding="utf-8")
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )

    assert recorded == 0


def test_rerun_does_not_duplicate(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        for _ in range(2):
            run_shadow_scoring(
                conn,
                models_dir=models_dir,
                candidates=[candidate],
                registry=_REGISTRY,
                batch_id=batch_id,
                scored_at=_SCORED_AT,
            )
        count = conn.execute("SELECT count(*) FROM shadow_scores").fetchone()

    assert count is not None
    assert count[0] == 1


def test_candidate_without_submission_row_is_skipped(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    with db_connection() as conn:
        recorded = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[_candidate()],
            registry=_REGISTRY,
            batch_id=str(uuid.uuid4()),
            scored_at=_SCORED_AT,
        )

    assert recorded == 0


def test_tail_score_populated_when_robustness_model_present(tmp_path: Path) -> None:
    models_dir = _toy_models_dir_with_tail(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        row = conn.execute("SELECT tail_score, tail_model_id FROM shadow_scores").fetchone()

    assert row is not None
    tail_score, tail_model_id = row
    assert tail_score is not None
    assert tail_model_id is not None
    assert len(tail_model_id) == 16


def test_shadow_targets_requested_robustness_model(tmp_path: Path) -> None:
    # R3: with both a cpcv (newest) and a wf_p25 robustness model in the dir, the shadow
    # must score with the REQUESTED target so the §8.6 streak measures the model the
    # quality lane actually uses — not whichever was retrained last.
    models_dir = _toy_models_dir_with_tail(tmp_path)  # adds the default cpcv model
    wf_id = _add_robustness_model(models_dir, target="target_wf_p25")
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
            robustness_target="target_wf_p25",
        )
        row = conn.execute("SELECT tail_score, tail_model_id FROM shadow_scores").fetchone()

    assert row is not None
    tail_score, tail_model_id = row
    assert tail_score is not None
    assert tail_model_id == wf_id


def test_tail_score_null_without_robustness_model(tmp_path: Path) -> None:
    # Only the logistic model present — tail columns stay NULL (the pre-train state).
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        row = conn.execute("SELECT tail_score, tail_model_id FROM shadow_scores").fetchone()

    assert row == (None, None)


def test_submissions_table_is_never_mutated(tmp_path: Path) -> None:
    models_dir = _toy_model_dir(tmp_path)
    candidate = _candidate()
    batch_id = str(uuid.uuid4())
    with db_connection() as conn:
        _insert_submission(conn, batch_id=batch_id, config_hash=candidate.report.config.config_hash)
        before = conn.execute("SELECT * FROM submissions ORDER BY forge_candidate_id").fetchall()
        run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=[candidate],
            registry=_REGISTRY,
            batch_id=batch_id,
            scored_at=_SCORED_AT,
        )
        after = conn.execute("SELECT * FROM submissions ORDER BY forge_candidate_id").fetchall()

    assert before == after
