"""Tests for `forge run --loop` and `--consume-feedback` (Phase 5 module 11).

D024/D6 + D7:
- `--loop` runs the cycle repeatedly, sleeping `--poll-interval-seconds`
  between iterations. For testing, `--max-iterations N` caps to N.
- `--consume-feedback` triggers the feedback chain after submit (or
  before, on subsequent iterations, since the previous batch's results
  may have arrived by now).
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import _effective_seed, _next_iteration_number, app
from forge.persistence.db import db_connection
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

runner = CliRunner()


# ---------------------------------------------------------------------------
# --loop runs N iterations and exits cleanly
# ---------------------------------------------------------------------------


def test_effective_seed_is_deterministic() -> None:
    """Same (root, iteration) returns the same effective seed."""
    assert _effective_seed(42, 1) == _effective_seed(42, 1)
    assert _effective_seed(42, 7) == _effective_seed(42, 7)


def test_effective_seed_differs_across_iterations() -> None:
    """Different iterations yield different effective seeds.

    This is the load-bearing property of plan C: without it, batch N+1
    enumerates the same configs as batch N and submitter dedup rejects
    them all as duplicates.
    """
    assert _effective_seed(42, 1) != _effective_seed(42, 2)
    assert _effective_seed(42, 1) != _effective_seed(42, 100)


def test_effective_seed_differs_across_roots() -> None:
    """Different root seeds for the same iteration yield different effective seeds."""
    assert _effective_seed(42, 1) != _effective_seed(43, 1)


def test_next_iteration_number_fresh_db_returns_1(tmp_path: Path) -> None:
    """Empty Forge DB → next iteration is 1."""
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db):
        pass  # schema-ensure
    assert _next_iteration_number(forge_db) == 1


def test_next_iteration_number_memory_db_returns_1() -> None:
    """In-memory DB always returns 1 — no persistence, no resume."""
    assert _next_iteration_number(Path(":memory:")) == 1


def test_next_iteration_number_counts_distinct_batch_ids(tmp_path: Path) -> None:
    """Persisted counter equals distinct batch_ids in submissions + 1.

    Restart resilience: a service restart should resume from where it
    left off rather than replaying batch_1 (which would re-enumerate
    the same configs).
    """
    import uuid
    from datetime import UTC, datetime

    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        now = datetime.now(UTC)
        for batch_idx in range(3):
            batch_id = uuid.uuid4()
            # Each batch has at least one submission row
            conn.execute(
                """
                INSERT INTO submissions
                    (forge_candidate_id, forge_batch_id, config_hash,
                     config_json, submitted_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    str(batch_id),
                    f"hash_{batch_idx:016d}",
                    "{}",
                    now,
                    "submitted",
                ],
            )
    assert _next_iteration_number(forge_db) == 4


def test_run_loop_with_max_iterations_exits_cleanly(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
            "--loop",
            "--max-iterations",
            "2",
            "--poll-interval-seconds",
            "0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Loop runs at least once (after first iter the rate limiter may block;
    # the loop should exit cleanly either way after max-iterations)
    assert (
        "submitted=" in result.stdout
        or "blocked" in result.stdout
        or "stopped" in result.stdout.lower()
    )


# ---------------------------------------------------------------------------
# --consume-feedback triggers the feedback chain
# ---------------------------------------------------------------------------


def test_run_with_consume_feedback_runs_chain(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
            "--consume-feedback",
            "--open-proposals",
            str(tmp_path / "OPEN_PROPOSALS.md"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Feedback chain emits its own summary line
    assert "feedback:" in result.stdout.lower() or "gated_count" in result.stdout


# ---------------------------------------------------------------------------
# --loop without rate-limiter-clear still respects max-iterations
# ---------------------------------------------------------------------------


def test_loop_exits_on_max_iterations_even_when_blocked(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    # Pre-populate forge_db with a "pending" batch so the rate limiter blocks
    import uuid
    from datetime import UTC, datetime

    from forge.persistence.db import db_connection

    bid = uuid.uuid4()
    cid = uuid.uuid4()
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
            "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
            [str(bid), 1, datetime(2026, 5, 13, tzinfo=UTC), "v1", "abc"],
        )
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                str(cid),
                str(bid),
                "blocking_hash_xx",
                "{}",
                datetime(2026, 5, 13, tzinfo=UTC),
                "submitted",
            ],
        )
    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "200",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--crucible-db",
            str(crucible_db),
            "--loop",
            "--max-iterations",
            "3",
            "--poll-interval-seconds",
            "0",
        ],
    )
    assert result.exit_code == 0
    # Should be blocked all 3 iterations
    assert result.stdout.count("blocked") >= 1
