"""Tests for persistence.verdicts (D111) — durable per-candidate Crucible verdicts.

Crucible's gated-runs export is a rolling top-10k window; before D111 the
per-candidate decision (component/reject/promote), gate values, and realized
trade_count were lost once a row rolled off it — at the 2026-06-09 review only
13.2% of all submissions had a recoverable verdict. `record_verdicts` writes
Forge's durable copy at reconcile time, keyed by `crucible_run_id` so re-gates
of the same config append rather than overwrite.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from forge.feedback.consumer import reconcile_all_pending
from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _gated_run(
    *,
    config_hash: str,
    decision: str = "reject",
    run_id: str | None = None,
    decided_at: datetime | None = None,
    trade_count: int = 42,
    grammar_version: str | None = "v12",
    measurement_basis: str | None = None,
    fullhist_refit_of: str | None = None,
    refit_selection: str | None = None,
):
    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

    rid = run_id or str(uuid.uuid4())
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=trade_count,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version=grammar_version,
            measurement_basis=measurement_basis,
            fullhist_refit_of=fullhist_refit_of,
            refit_selection=refit_selection,
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results={
                "min_oos_trade_count": GateResult(
                    gate_name="min_oos_trade_count",
                    passed=trade_count >= 100,
                    value=float(trade_count),
                    threshold=100.0,
                ),
            },
            decided_at=decided_at or datetime(2026, 6, 9, 11, 37, 46),  # noqa: DTZ001 — export ships naive
            decided_by="runner.forge_minimal",
        ),
    )


def _insert_submission(
    db: duckdb.DuckDBPyConnection,
    *,
    config_hash: str,
    status: str = "submitted",
) -> None:
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            datetime(2026, 6, 9, 0, 55),  # noqa: DTZ001 — naive-UTC column convention
            status,
        ],
    )


def _verdict_rows(db: duckdb.DuckDBPyConnection) -> list[tuple]:
    return db.execute(
        "SELECT crucible_run_id, config_hash, decision, decided_at, trade_count, "
        "grammar_version, gate_results, recorded_at FROM verdicts ORDER BY decided_at",
    ).fetchall()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_verdicts_table_created_by_ensure_schema() -> None:
    with db_connection() as conn:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'verdicts'",
        ).fetchall()
    present = {c[0] for c in cols}
    assert present == {
        "crucible_run_id",
        "config_hash",
        "decision",
        "decided_at",
        "trade_count",
        "grammar_version",
        "gate_results",
        "recorded_at",
        # D316 (2c) — label provenance
        "source_export",
        "contracts_version",
        # D330 — LANE provenance. Crucible's two-stage design means the lane
        # decides whether a row CAN carry an honest label at all; without these
        # the D128 label cannot be scoped. On the wire since contracts 1.27.0.
        "measurement_basis",
        "fullhist_refit_of",
        "refit_selection",
    }


# ---------------------------------------------------------------------------
# record_verdicts
# ---------------------------------------------------------------------------


def test_record_verdicts_inserts_matched_run() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        run = _gated_run(config_hash="aaaa000011112222", decision="component", trade_count=435)
        n = record_verdicts(conn, [run])
        assert n == 1
        rows = _verdict_rows(conn)
        assert len(rows) == 1
        rid, chash, decision, _decided, tc, gv, gates_json, recorded = rows[0]
        assert str(rid) == run.run.run_id
        assert chash == "aaaa000011112222"
        assert decision == "component"
        assert tc == 435
        assert gv == "v12"
        gates = json.loads(gates_json)
        assert gates["min_oos_trade_count"]["passed"] is True
        assert gates["min_oos_trade_count"]["threshold"] == 100.0
        assert recorded is not None


def test_record_verdicts_skips_hashes_forge_never_submitted() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        n = record_verdicts(conn, [_gated_run(config_hash="ffff000011112222")])
        assert n == 0
        assert _verdict_rows(conn) == []


def test_record_verdicts_idempotent_on_rerun() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        run = _gated_run(config_hash="aaaa000011112222")
        assert record_verdicts(conn, [run]) == 1
        assert record_verdicts(conn, [run]) == 0
        assert len(_verdict_rows(conn)) == 1


def test_record_verdicts_regate_appends_second_row() -> None:
    """A Crucible re-gate is a NEW run_id for the same config_hash — both kept."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        first = _gated_run(
            config_hash="aaaa000011112222",
            decision="reject",
            decided_at=datetime(2026, 6, 1, 10, 0, 0),  # noqa: DTZ001 — intentional naive
        )
        regate = _gated_run(
            config_hash="aaaa000011112222",
            decision="component",
            decided_at=datetime(2026, 6, 9, 10, 0, 0),  # noqa: DTZ001 — intentional naive
        )
        record_verdicts(conn, [first])
        assert record_verdicts(conn, [first, regate]) == 1
        rows = _verdict_rows(conn)
        assert len(rows) == 2
        assert [r[2] for r in rows] == ["reject", "component"]


def test_record_verdicts_stages_only_new_runs() -> None:
    """P0-2 (pipeline-perf): the delta-first insert serializes + stages ONLY the new
    runs, not the already-recorded ones that INSERT OR IGNORE would drop (the
    reconcile json.dumps cost on a ~10k-row rolling window). A mixed pass stages
    exactly the new run — the old path staged both, then dropped one."""
    from collections.abc import Iterable

    class _SpyConn:
        def __init__(self, real: duckdb.DuckDBPyConnection) -> None:
            self._real = real
            self.staged_counts: list[int] = []

        def execute(self, *args: object, **kwargs: object) -> object:
            return self._real.execute(*args, **kwargs)

        def executemany(self, sql: str, rows: Iterable[object]) -> object:
            materialized = list(rows)
            self.staged_counts.append(len(materialized))
            return self._real.executemany(sql, materialized)

    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        existing = _gated_run(
            config_hash="aaaa000011112222",
            decided_at=datetime(2026, 6, 1, 10, 0, 0),  # noqa: DTZ001 — export ships naive
        )
        assert record_verdicts(conn, [existing]) == 1
        spy = _SpyConn(conn)
        new = _gated_run(
            config_hash="aaaa000011112222",
            decided_at=datetime(2026, 6, 9, 10, 0, 0),  # noqa: DTZ001 — export ships naive
        )
        n = record_verdicts(spy, [existing, new])  # type: ignore[arg-type]
        assert n == 1
        assert spy.staged_counts == [1]  # only `new` staged; `existing` skipped pre-serialization


def test_record_verdicts_normalizes_aware_decided_at_to_naive_utc() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        aware = datetime(2026, 6, 9, 13, 30, 0, tzinfo=UTC)
        record_verdicts(conn, [_gated_run(config_hash="aaaa000011112222", decided_at=aware)])
        (decided,) = [r[3] for r in _verdict_rows(conn)]
        assert decided == datetime(2026, 6, 9, 13, 30, 0)  # noqa: DTZ001 — stored naive
        assert decided.tzinfo is None


def test_record_verdicts_naive_decided_at_stored_verbatim() -> None:
    """Naive export timestamps pass through unchanged (D061 convention: the
    column is naive; the export's current PDT-skew is documented in
    docs/tasks/investigate-live.md and fixed Crucible-side, not coerced here —
    a +7h shift would double-shift the moment Crucible emits aware UTC)."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        naive = datetime(2026, 6, 9, 11, 37, 46)  # noqa: DTZ001 — the case under test
        record_verdicts(conn, [_gated_run(config_hash="aaaa000011112222", decided_at=naive)])
        (decided,) = [r[3] for r in _verdict_rows(conn)]
        assert decided == naive


# ---------------------------------------------------------------------------
# Consumer wiring — reconcile_all_pending records verdicts as a side effect
# ---------------------------------------------------------------------------


def _setup_reconcile(tmp_path: Path) -> tuple[Path, Path]:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    return forge_db, crucible_db


def test_reconcile_all_pending_records_verdicts(tmp_path: Path) -> None:
    from tests.unit.test_feedback.test_consumer import (
        _insert_batch_summary,
        _insert_crucible_gated,
        _insert_forge_submission,
    )

    forge_db, crucible_db = _setup_reconcile(tmp_path)
    cfg = minimal_strategy_config()
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_forge_submission(conn, config=cfg, batch_id=batch_id)
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=1)
        run_id = _insert_crucible_gated(
            crucible_db,
            config_hash=cfg.config_hash,
            decision="reject",
            failed_gate="min_oos_trade_count",
        )
        reconcile_all_pending(conn, crucible_db, exports_dir=tmp_path / "no_exports")
        rows = _verdict_rows(conn)
        assert len(rows) == 1
        assert str(rows[0][0]) == run_id
        assert rows[0][2] == "reject"


def test_reconcile_flushed_sentinel_rows_get_no_verdict(tmp_path: Path) -> None:
    """Aged-out D052/D110 flushes never saw a Crucible decision — no verdict row."""
    from forge.feedback.consumer import STRANDED_AFTER
    from tests.unit.test_feedback.test_consumer import (
        _insert_batch_summary,
        _insert_crucible_gated,
        _insert_forge_submission,
    )

    forge_db, crucible_db = _setup_reconcile(tmp_path)
    stale_cfg = minimal_strategy_config(underlying="QQQ")
    fresh_cfg = minimal_strategy_config(underlying="IWM")
    batch_id = uuid.uuid4()
    newest_decision = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        # Stale row: submitted far beyond the margin, absent from the export.
        _insert_forge_submission(
            conn,
            config=stale_cfg,
            batch_id=batch_id,
            submitted_at=newest_decision - STRANDED_AFTER - (STRANDED_AFTER / 2),
        )
        # Fresh row: present in the export with a real decision.
        _insert_forge_submission(
            conn, config=fresh_cfg, batch_id=batch_id, submitted_at=newest_decision
        )
        _insert_batch_summary(conn, batch_id=batch_id, batch_size=2)
        _insert_crucible_gated(
            crucible_db,
            config_hash=fresh_cfg.config_hash,
            decision="component",
            decided_at=newest_decision,
        )
        reconcile_all_pending(conn, crucible_db, exports_dir=tmp_path / "no_exports")
        rows = _verdict_rows(conn)
        assert [r[1] for r in rows] == [fresh_cfg.config_hash]
        sentinel = conn.execute(
            "SELECT crucible_run_id FROM submissions WHERE config_hash = ?",
            [stale_cfg.config_hash],
        ).fetchone()
        assert str(sentinel[0]) == "00000000-0000-0000-0000-000000000000"


def test_provenance_columns_stamped(tmp_path: Path) -> None:
    """D316 (2c): verdicts rows carry label provenance — the source export
    filename + the installed contracts version — so a future era cut (the ve
    ghost class) is a filter flip, not archaeology. Optional param: None
    leaves source_export NULL (the DB-fallback path)."""
    from crucible_contracts import CONTRACT_VERSION

    db = tmp_path / "forge.db"
    with db_connection(db) as conn:
        _insert_submission(conn, config_hash="p" * 16)
        n = record_verdicts(
            conn,
            [_gated_run(config_hash="p" * 16)],
            source_export="gated_runs_2026-07-21T020000Z.json",
        )
        assert n == 1
        row = conn.execute("SELECT source_export, contracts_version FROM verdicts").fetchone()
    assert row is not None
    assert row[0] == "gated_runs_2026-07-21T020000Z.json"
    assert row[1] == CONTRACT_VERSION


def test_provenance_source_export_nullable(tmp_path: Path) -> None:
    db = tmp_path / "forge.db"
    with db_connection(db) as conn:
        _insert_submission(conn, config_hash="q" * 16)
        record_verdicts(conn, [_gated_run(config_hash="q" * 16)])
        row = conn.execute("SELECT source_export, contracts_version FROM verdicts").fetchone()
    assert row is not None
    assert row[0] is None
    assert row[1] is not None  # contracts version always known locally


# ---------------------------------------------------------------------------
# D330 — lane provenance (measurement_basis / fullhist_refit_of)
# ---------------------------------------------------------------------------


def test_records_lane_provenance_from_the_run() -> None:
    """Crucible's two-stage design: `standard_window` is a cheap SCREEN that
    structurally cannot produce an honest-coverage component; `fullhist_refit`
    is the validator. 94% of our gated feed is the screen, and 98%+ of honest
    labels come from the 6% that is not — so the D128 label is DILUTED, not
    starved. Scoping it requires the lane on the row, and until D330 Forge
    dropped both fields on the floor (they existed only in a comment)."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="bbbb000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="bbbb000011112222",
                    measurement_basis="fullhist_refit",
                    fullhist_refit_of="parent-run-id-0001",
                )
            ],
        )
        row = conn.execute("SELECT measurement_basis, fullhist_refit_of FROM verdicts").fetchone()
    assert row == ("fullhist_refit", "parent-run-id-0001")


def test_lane_provenance_is_nullable_for_legacy_and_stage_one_rows() -> None:
    """Pre-1.27.0 rows and any run whose producer omits the fields stay NULL —
    a missing lane must not be silently read as a lane."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="cccc000011112222")
        record_verdicts(conn, [_gated_run(config_hash="cccc000011112222")])
        row = conn.execute("SELECT measurement_basis, fullhist_refit_of FROM verdicts").fetchone()
    assert row == (None, None)


# ---------------------------------------------------------------------------
# D375 — refit_selection: Crucible's REFIT-LANE tag, persisted
# ---------------------------------------------------------------------------


def test_refit_selection_is_persisted_and_legacy_rows_stay_null() -> None:
    """The lane tag must survive the writer, or the field is decorative.

    Crucible built `RunResult.refit_selection` (contracts 1.44.0) as a first-class field in
    answer to our D370 ask, and it arrives on every exported row — but a field we parse and
    then drop at the writer is a field we cannot filter on. The point of the tag is that its
    ABSENCE marks the like-conditioned newest-first cohort, which is the yardstick our
    version-delta reads depend on; reconstructing that split from timestamps is exactly what
    the tag exists to replace.

    Wire vocabulary: None = the unconditioned newest-first drain, 'quality_margin' = the
    reserved quality sub-lane (live 2026-08-06 17:10 PDT), 'promote_stamp_recovery' = the
    31-config requeue batch.
    """
    with db_connection(Path(":memory:")) as conn:
        for h in ("aaaa000011112222", "bbbb000011112222", "cccc000011112222"):
            _insert_submission(conn, config_hash=h)
        runs = [
            _gated_run(config_hash="aaaa000011112222", refit_selection="quality_margin"),
            _gated_run(config_hash="bbbb000011112222", refit_selection="promote_stamp_recovery"),
            _gated_run(config_hash="cccc000011112222"),  # newest-first drain: tag absent
        ]
        assert record_verdicts(conn, runs) == 3
        rows = dict(conn.execute("SELECT config_hash, refit_selection FROM verdicts").fetchall())
    assert rows["aaaa000011112222"] == "quality_margin"
    assert rows["bbbb000011112222"] == "promote_stamp_recovery"
    assert rows["cccc000011112222"] is None, (
        "the newest-first cohort must stay NULL — its ABSENCE is the cohort marker"
    )
