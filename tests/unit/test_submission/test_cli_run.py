"""Tests for `forge run` (D023/D6.a, Phase 4 CLI module 11).

Single-batch end-to-end: dry-run prints rank summary; full run writes
inbox + submissions + batch_summaries + pre_filter_logs.
"""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection

runner = CliRunner()


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def test_dry_run_prints_rank_summary() -> None:
    result = runner.invoke(
        app,
        ["run", "--no-config", "--seed", "0", "--batch-size", "3", "--max", "30", "--dry-run"],
    )
    assert result.exit_code == 0, result.stdout
    assert "dry-run" in result.stdout
    assert "ranked_top_n=" in result.stdout
    # Up to 3 candidate lines numbered [   1]..[   3]
    lines = [line for line in result.stdout.splitlines() if re.match(r"^\[\s*\d+\]", line)]
    assert len(lines) <= 3


def test_dry_run_does_not_require_inbox() -> None:
    result = runner.invoke(
        app,
        ["run", "--no-config", "--seed", "0", "--batch-size", "2", "--max", "20", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "error" not in result.stdout.lower()


def test_dry_run_is_deterministic_for_same_seed() -> None:
    a = runner.invoke(
        app, ["run", "--no-config", "--seed", "7", "--batch-size", "2", "--max", "20", "--dry-run"]
    )
    b = runner.invoke(
        app, ["run", "--no-config", "--seed", "7", "--batch-size", "2", "--max", "20", "--dry-run"]
    )
    assert a.exit_code == 0
    assert b.exit_code == 0
    assert a.stdout == b.stdout


# ---------------------------------------------------------------------------
# Missing --inbox without --dry-run
# ---------------------------------------------------------------------------


def test_missing_inbox_without_dry_run_exits_with_code_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "--no-config", "--seed", "0", "--batch-size", "2", "--max", "20"],
    )
    assert result.exit_code == 2
    # Typer routes err=True output to stdout by default in CliRunner with
    # `mix_stderr=True`.
    combined = (result.stdout or "") + (result.stderr or "")
    assert "inbox" in combined.lower()


# ---------------------------------------------------------------------------
# Full submit path — inbox files + DB rows
# ---------------------------------------------------------------------------


def test_full_submit_writes_inbox_and_db(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
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
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert inbox.is_dir()
    # Flat layout per INBOX_LAYOUT — top-level *.json files.
    json_files = list(inbox.glob("*.json"))
    assert len(json_files) >= 1
    with db_connection(forge_db) as conn:
        sub_row = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
        assert sub_row is not None
        sub_count = int(sub_row[0])
        bs_row = conn.execute("SELECT COUNT(*) FROM batch_summaries").fetchone()
        assert bs_row is not None
        bs_count = int(bs_row[0])
        pfl_row = conn.execute("SELECT COUNT(*) FROM pre_filter_logs").fetchone()
        assert pfl_row is not None
        pfl_count = int(pfl_row[0])
    assert sub_count >= 1
    assert bs_count == 1
    assert pfl_count >= 7  # at least one candidate * 7 filters


def test_summary_line_shows_counts(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
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
        ],
    )
    assert result.exit_code == 0
    assert "submitted=" in result.stdout
    assert "skipped_duplicate=" in result.stdout
    assert "failed=" in result.stdout


# ---------------------------------------------------------------------------
# Idempotency: rerunning the same seed produces no new submissions
# ---------------------------------------------------------------------------


def test_rerun_same_seed_is_idempotent(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    args = [
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
    ]
    first = runner.invoke(app, args)
    second = runner.invoke(app, args)
    assert first.exit_code == 0
    assert second.exit_code == 0
    # First run: at least one submitted. Second: all skipped.
    # We don't pin exact counts (depends on prefilter pass-rate)
    # but the second invocation should report submitted=0.
    second_lines = [line for line in second.stdout.splitlines() if "submitted=" in line]
    assert any("submitted=0" in line for line in second_lines)
