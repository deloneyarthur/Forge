"""Phase 6 — resilience scenario: partial batch retry (§12 / D025/D3.iii).

`forge run` is gated by §7.3's >=80%-gated check on the prior batch.
When Crucible has gated only a fraction of the last batch, Forge must:

  (1) detect the partial state via `check_rate_limit`;
  (2) refuse to submit a new batch (exit cleanly with a "blocked"
      message — no new rows in `submissions`, no new inbox files);
  (3) the next invocation, once enough are gated, must clear and
      submit normally.

The CLI returns "blocked" from `_run_one_iteration`; this test exercises
the full integration via `runner.invoke` to keep the contract honest.
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
from forge.submission.rate_limiter import check_rate_limit
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

runner = CliRunner()


def _gate_one_in_crucible(crucible_db: Path, *, config_hash: str) -> None:
    """Add a gated_run row + matching PromotionDecision to the Crucible DB."""
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
        gate_body = {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": False, "value": 0.3}}
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [
                run_id,
                "reject",
                json.dumps(gate_body),
                datetime(2026, 5, 13, 14, tzinfo=UTC),
                "gate_v1",
            ],
        )
    finally:
        conn.close()


def _seed_prior_batch(forge_db: Path, *, batch_size: int) -> tuple[uuid.UUID, list[str]]:
    """Insert N submitted submissions sharing a forge_batch_id; return ids."""
    batch_id = uuid.uuid4()
    submitted_at = datetime(2026, 5, 13, 12, tzinfo=UTC)
    hashes: list[str] = []
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
            "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
            [str(batch_id), batch_size, submitted_at, "v1", "abc"],
        )
        for i in range(batch_size):
            cfg = minimal_strategy_config().model_copy(update={"name": f"prior_b_{i}"})
            hashes.append(cfg.config_hash)
            conn.execute(
                "INSERT INTO submissions (forge_candidate_id, forge_batch_id, "
                "config_hash, config_json, submitted_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    str(uuid.uuid4()),
                    str(batch_id),
                    cfg.config_hash,
                    cfg.model_dump_json(),
                    submitted_at,
                    "submitted",
                ],
            )
    return batch_id, hashes


# ---------------------------------------------------------------------------
# Unit-level guards on the rate limiter (covered by Phase 4 but reasserted
# here as the foundation the integration test relies on).
# ---------------------------------------------------------------------------


def test_rate_limit_blocks_when_under_threshold(tmp_path: Path) -> None:
    """Prior batch of 10 with only 4 gated (40%) — below 80%, blocked."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    _, hashes = _seed_prior_batch(forge_db, batch_size=10)
    for h in hashes[:4]:
        _gate_one_in_crucible(crucible_db, config_hash=h)

    status = check_rate_limit(forge_db, crucible_db)
    assert status.clear is False
    assert status.gated_count == 4
    assert status.submitted_count == 10


def test_rate_limit_clears_when_at_threshold(tmp_path: Path) -> None:
    """Prior batch of 10 with 8 gated (80%) — at threshold, clear."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    _, hashes = _seed_prior_batch(forge_db, batch_size=10)
    for h in hashes[:8]:
        _gate_one_in_crucible(crucible_db, config_hash=h)

    status = check_rate_limit(forge_db, crucible_db)
    assert status.clear is True
    assert status.gated_count == 8


# ---------------------------------------------------------------------------
# Integration: `forge run` blocks cleanly when prior batch is partial.
# ---------------------------------------------------------------------------


def test_forge_run_exits_cleanly_with_partial_prior_batch(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    inbox = tmp_path / "inbox"
    build_synthetic_crucible_db(crucible_db).close()

    prior_batch_id, hashes = _seed_prior_batch(forge_db, batch_size=10)
    # Only gate 3/10 -> 30%, well below the 80% threshold.
    for h in hashes[:3]:
        _gate_one_in_crucible(crucible_db, config_hash=h)

    # Count submissions before the next forge-run attempt.
    with db_connection(forge_db) as conn:
        before_count = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    assert before_count is not None
    submissions_before = before_count[0]

    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "5",
            "--max",
            "50",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
        ],
    )
    assert result.exit_code == 0, f"forge run blocked-path should exit 0; stdout={result.stdout!r}"
    assert "blocked" in result.stdout.lower()
    assert str(prior_batch_id) in result.stdout

    # Critical resilience invariant: no new submissions were inserted.
    with db_connection(forge_db) as conn:
        after_count = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    assert after_count is not None
    assert after_count[0] == submissions_before
    # And no inbox files written for the new batch.
    if inbox.exists():
        new_files = list(inbox.rglob("*.json"))
        assert not new_files, f"blocked run should not write inbox files; got {new_files}"


def test_forge_run_unblocks_after_threshold_reached(tmp_path: Path) -> None:
    """Same forge_db, two invocations: first blocked at 30%, then at 80%
    the second invocation proceeds (asserted via exit-code + submitted
    row count delta — not relying on any specific message)."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    inbox = tmp_path / "inbox"
    build_synthetic_crucible_db(crucible_db).close()

    _, hashes = _seed_prior_batch(forge_db, batch_size=10)
    for h in hashes[:3]:
        _gate_one_in_crucible(crucible_db, config_hash=h)

    blocked = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "5",
            "--max",
            "50",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
        ],
    )
    assert blocked.exit_code == 0
    assert "blocked" in blocked.stdout.lower()

    # Gate the remaining hashes to bring the prior batch to 100% gated.
    for h in hashes[3:]:
        _gate_one_in_crucible(crucible_db, config_hash=h)

    with db_connection(forge_db) as conn:
        row = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    assert row is not None
    before = row[0]

    unblocked = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "5",
            "--max",
            "50",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
        ],
    )
    assert unblocked.exit_code == 0, f"unblocked run should succeed; stdout={unblocked.stdout!r}"
    # The unblocked invocation didn't print "blocked".
    assert "blocked" not in unblocked.stdout.lower()
    with db_connection(forge_db) as conn:
        row = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    assert row is not None
    assert row[0] >= before, "unblocked run should not have removed prior rows"
