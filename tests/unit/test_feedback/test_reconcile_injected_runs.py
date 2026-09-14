"""`reconcile_all_pending` with injected runs (D412): the weekly campaign reads Crucible's
forge-scoped 14-day stream itself and hands the rows in with their provenance. A TRUNCATED
window must NOT drive the D052 aged-out flush — the missing verdicts are the oldest ones, so an
absent config_hash is not evidence that Crucible never decided it (Crucible 09-14 §1.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from crucible_contracts import get_recent_gated_runs

from forge.feedback.consumer import reconcile_all_pending
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db
from tests.unit.test_feedback.test_consumer import (
    AGED_OUT_SENTINEL,
    _insert_batch_summary,
    _insert_crucible_gated,
    _insert_forge_submission,
    _setup_paths,
)


def _seed(tmp_path: Path) -> tuple[Path, Path, str, str]:
    forge_db, crucible_db = _setup_paths(tmp_path)
    build_synthetic_crucible_db(crucible_db).close()
    stranded = minimal_strategy_config().model_copy(update={"name": "stranded"})
    visible = minimal_strategy_config().model_copy(update={"name": "visible"})
    _insert_crucible_gated(crucible_db, config_hash=visible.config_hash)
    with db_connection(forge_db) as conn:
        for cfg, day in ((stranded, 1), (visible, 13)):
            batch = uuid.uuid4()
            ts = datetime(2026, 5, day, tzinfo=UTC)
            _insert_batch_summary(conn, batch_id=batch, batch_size=1, submitted_at=ts)
            _insert_forge_submission(conn, config=cfg, batch_id=batch, submitted_at=ts)
    return forge_db, crucible_db, stranded.config_hash, visible.config_hash


def _statuses(forge_db: Path) -> dict[str, tuple[str, str | None]]:
    with db_connection(forge_db) as conn:
        rows = conn.execute(
            "SELECT config_hash, status, crucible_run_id FROM submissions"
        ).fetchall()
        provenance = conn.execute("SELECT DISTINCT source_export FROM verdicts").fetchall()
    out = {str(r[0]): (str(r[1]), None if r[2] is None else str(r[2])) for r in rows}
    out["__provenance__"] = (",".join(str(p[0]) for p in provenance), None)
    return out


def test_injected_runs_reconcile_with_their_provenance_and_no_flush(tmp_path: Path) -> None:
    forge_db, crucible_db, stranded, visible = _seed(tmp_path)
    runs = get_recent_gated_runs(crucible_db, limit=100)
    assert runs
    with db_connection(forge_db) as conn:
        feedbacks = reconcile_all_pending(
            conn,
            crucible_db,
            exports_dir=tmp_path / "noexports",
            runs=runs,
            source_export="forge_gated_runs_0001.json",
            flush_aged_out=False,
        )
    by_hash = _statuses(forge_db)
    assert by_hash[visible][0] == "gated"
    assert by_hash[visible][1] != AGED_OUT_SENTINEL
    # truncated window: the stranded row is NOT declared aged-out
    assert by_hash[stranded] == ("submitted", None)
    assert by_hash["__provenance__"][0] == "forge_gated_runs_0001.json"
    assert len(feedbacks) >= 1


def test_injected_runs_with_flush_age_out_the_stranded_row(tmp_path: Path) -> None:
    forge_db, crucible_db, stranded, visible = _seed(tmp_path)
    runs = get_recent_gated_runs(crucible_db, limit=100)
    with db_connection(forge_db) as conn:
        reconcile_all_pending(
            conn,
            crucible_db,
            exports_dir=tmp_path / "noexports",
            runs=runs,
            source_export="forge_gated_runs_0002.json",
            flush_aged_out=True,
        )
    by_hash = _statuses(forge_db)
    assert by_hash[visible][0] == "gated"
    assert by_hash[stranded] == ("gated", AGED_OUT_SENTINEL)
