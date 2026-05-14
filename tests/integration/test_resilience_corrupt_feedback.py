"""Phase 6 — resilience scenario: corrupt feedback (§12 / D025/D3.ii).

The spec scenario: a row in Crucible's gated_runs lacks expected fields
⇒ skip that row, others process.

The realistic corruption that Crucible may ship in production: a `runs`
row exists with ``status='gated'`` but the matching
``promotion_decisions`` row is missing (orphaned run — a Crucible
process killed mid-gate, partial write, schema migration left it).

`crucible_contracts.get_recent_gated_runs` JOINs `runs` against
`promotion_decisions` — orphaned runs silently drop from the result.
This test verifies that:

  (1) the orphaned-row case does not block processing of the valid
      rows in the same batch;
  (2) Forge's consumer correctly leaves the orphan's submission at
      ``status='submitted'`` (no spurious gating);
  (3) the CLI exits 0 and reports the partial-feedback gated_count
      honestly.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

runner = CliRunner()


def _insert_crucible_gated_with_decision(
    crucible_db: Path,
    *,
    config_hash: str,
    decision: str = "promote",
) -> str:
    """Insert a `runs` row + matching `promotion_decisions` row. Returns run_id."""
    conn = duckdb.connect(str(crucible_db))
    try:
        run_id = str(uuid.uuid4())
        gates = (
            {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": True, "value": 1.2}}
            if decision == "promote"
            else {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": False, "value": 0.4}}
        )
        conn.execute(
            "INSERT INTO runs (run_id, config_hash, source, status, period_start, "
            "period_end, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                config_hash,
                "forge",
                "gated",
                date(2022, 1, 1),
                date(2024, 12, 31),
                date(2026, 5, 13),
                date(2026, 5, 13),
            ],
        )
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [
                run_id,
                decision,
                json.dumps(gates),
                datetime(2026, 5, 13, 14, tzinfo=UTC),
                "gate_v1",
            ],
        )
    finally:
        conn.close()
    return run_id


def _insert_crucible_orphaned_run(crucible_db: Path, *, config_hash: str) -> str:
    """Insert a `runs` row WITHOUT a matching `promotion_decisions` row."""
    conn = duckdb.connect(str(crucible_db))
    try:
        run_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO runs (run_id, config_hash, source, status, period_start, "
            "period_end, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                config_hash,
                "forge",
                "gated",
                date(2022, 1, 1),
                date(2024, 12, 31),
                date(2026, 5, 13),
                date(2026, 5, 13),
            ],
        )
    finally:
        conn.close()
    return run_id


def _seed_forge_batch(forge_db: Path, configs: list[object]) -> uuid.UUID:
    """Insert a batch_summaries row + one submission per config; return batch_id."""
    batch_id = uuid.uuid4()
    submitted_at = datetime(2026, 5, 13, 12, tzinfo=UTC)
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
            "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
            [str(batch_id), len(configs), submitted_at, "v1", "abc"],
        )
        for cfg in configs:
            conn.execute(
                "INSERT INTO submissions (forge_candidate_id, forge_batch_id, "
                "config_hash, config_json, submitted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    str(uuid.uuid4()),
                    str(batch_id),
                    cfg.config_hash,  # type: ignore[attr-defined]
                    cfg.model_dump_json(),  # type: ignore[attr-defined]
                    submitted_at,
                    "submitted",
                ],
            )
    return batch_id


def _read_status_by_hash(forge_db: Path) -> dict[str, str]:
    with db_connection(forge_db) as conn:
        rows = conn.execute("SELECT config_hash, status FROM submissions").fetchall()
    return {str(r[0]): str(r[1]) for r in rows}


def test_orphaned_run_does_not_block_valid_runs(tmp_path: Path) -> None:
    """Mixed batch — A valid (gated), B orphan (no PromotionDecision), C valid."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()

    cfg_a = minimal_strategy_config().model_copy(update={"name": "valid_a"})
    cfg_b = minimal_strategy_config().model_copy(update={"name": "orphan_b"})
    cfg_c = minimal_strategy_config().model_copy(update={"name": "valid_c"})

    _insert_crucible_gated_with_decision(
        crucible_db, config_hash=cfg_a.config_hash, decision="promote"
    )
    _insert_crucible_orphaned_run(crucible_db, config_hash=cfg_b.config_hash)
    _insert_crucible_gated_with_decision(
        crucible_db, config_hash=cfg_c.config_hash, decision="reject"
    )

    batch_id = _seed_forge_batch(forge_db, [cfg_a, cfg_b, cfg_c])

    result = runner.invoke(
        app,
        [
            "feedback",
            "--no-config",
            "--forge-db",
            str(forge_db),
            "--crucible-db",
            str(crucible_db),
            "--batch-id",
            str(batch_id),
            "--open-proposals",
            str(tmp_path / "OPEN_PROPOSALS.md"),
        ],
    )
    assert result.exit_code == 0, f"feedback should exit 0 despite orphan; stdout={result.stdout!r}"

    by_hash = _read_status_by_hash(forge_db)
    assert by_hash[cfg_a.config_hash] == "gated", "valid run A should be marked gated"
    assert by_hash[cfg_b.config_hash] == "submitted", "orphaned run B should stay submitted"
    assert by_hash[cfg_c.config_hash] == "gated", "valid run C should be marked gated"
    assert "gated_count=2" in result.stdout
    assert "promoted_count=1" in result.stdout


def test_orphaned_run_does_not_corrupt_batch_summary(tmp_path: Path) -> None:
    """batch_summaries.promotion_rate must reflect submitted_count (3), not
    the partial gated_count (2). i.e. the rate is `promoted / submitted`,
    not `promoted / gated` — a Crucible-side gap doesn't artificially
    inflate the promotion rate."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()

    cfg_a = minimal_strategy_config().model_copy(update={"name": "valid_a"})
    cfg_b = minimal_strategy_config().model_copy(update={"name": "orphan_b"})
    cfg_c = minimal_strategy_config().model_copy(update={"name": "valid_c"})

    _insert_crucible_gated_with_decision(
        crucible_db, config_hash=cfg_a.config_hash, decision="promote"
    )
    _insert_crucible_orphaned_run(crucible_db, config_hash=cfg_b.config_hash)
    _insert_crucible_gated_with_decision(
        crucible_db, config_hash=cfg_c.config_hash, decision="reject"
    )

    batch_id = _seed_forge_batch(forge_db, [cfg_a, cfg_b, cfg_c])

    runner.invoke(
        app,
        [
            "feedback",
            "--no-config",
            "--forge-db",
            str(forge_db),
            "--crucible-db",
            str(crucible_db),
            "--batch-id",
            str(batch_id),
            "--open-proposals",
            str(tmp_path / "OPEN_PROPOSALS.md"),
        ],
    )

    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT promotion_rate, completed_at FROM batch_summaries WHERE forge_batch_id = ?",
            [str(batch_id)],
        ).fetchone()
    assert row is not None
    rate, completed_at = row
    # 1 promoted / 3 submitted = 0.333…; not 1/2 = 0.5
    assert rate is not None
    assert abs(float(rate) - (1.0 / 3.0)) < 1e-9, f"expected 1/3; got {rate}"
    # Batch is not 100% gated (only 2/3) so completed_at must remain NULL
    assert completed_at is None, "completed_at must stay NULL when gated_count < submitted_count"


def test_orphan_does_not_block_when_appears_in_arbitrary_position(tmp_path: Path) -> None:
    """The orphan-skip behaviour holds regardless of insertion order.
    Phase 5 consumer iterates `submission_rows` in (submitted_at,
    candidate_id) order; a defensive guard that the orphan being the
    first, middle, or last row in that iteration doesn't change the
    outcome for the other rows."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()

    cfg_orphan = minimal_strategy_config().model_copy(update={"name": "orphan_first"})
    cfg_valid_1 = minimal_strategy_config().model_copy(update={"name": "valid_after_1"})
    cfg_valid_2 = minimal_strategy_config().model_copy(update={"name": "valid_after_2"})

    _insert_crucible_orphaned_run(crucible_db, config_hash=cfg_orphan.config_hash)
    _insert_crucible_gated_with_decision(
        crucible_db, config_hash=cfg_valid_1.config_hash, decision="promote"
    )
    _insert_crucible_gated_with_decision(
        crucible_db, config_hash=cfg_valid_2.config_hash, decision="promote"
    )

    batch_id = _seed_forge_batch(forge_db, [cfg_orphan, cfg_valid_1, cfg_valid_2])

    result = runner.invoke(
        app,
        [
            "feedback",
            "--no-config",
            "--forge-db",
            str(forge_db),
            "--crucible-db",
            str(crucible_db),
            "--batch-id",
            str(batch_id),
            "--open-proposals",
            str(tmp_path / "OPEN_PROPOSALS.md"),
        ],
    )
    assert result.exit_code == 0

    by_hash = _read_status_by_hash(forge_db)
    assert by_hash[cfg_orphan.config_hash] == "submitted"
    assert by_hash[cfg_valid_1.config_hash] == "gated"
    assert by_hash[cfg_valid_2.config_hash] == "gated"
    # Note: deeper corruptions (malformed gate_results_json, decision out of
    # Literal) cannot reach this code path — DuckDB's JSON column refuses
    # malformed JSON at INSERT time, and Pydantic-side validation lives
    # inside contracts. Those scenarios are the contracts package's tests
    # to own.
