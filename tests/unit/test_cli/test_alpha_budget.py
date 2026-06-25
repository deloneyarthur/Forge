"""Unit tests for `forge alpha-budget` (Tier-1a honesty ledger).

The benchmark math + aggregation live in `forge.feedback.alpha_budget` and are
tested there; here we cover the DB read, the readout formatting, and an end-to-end
smoke through the CLI.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge.cli.alpha_budget_cmd import format_budget, read_budget_rows
from forge.cli.main import app
from forge.feedback.alpha_budget import BatchRow, summarize_budget
from forge.persistence.db import db_connection

runner = CliRunner()


def _seed_batch(conn: object, *, gv: str, size: int, enumerated: int | None, idx: int) -> None:
    # Fixed UUIDs keep the fixture deterministic (no RNG; hard rule #8).
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO batch_summaries "
        "(forge_batch_id, batch_size, submitted_at, grammar_version, "
        "registry_version, enumerated_count) VALUES (?, ?, ?, ?, ?, ?)",
        [
            f"00000000-0000-0000-0000-{idx:012d}",
            size,
            "2026-06-20 00:00:00",
            gv,
            "reg1",
            enumerated,
        ],
    )


def test_read_budget_rows_roundtrips_counts_and_nulls() -> None:
    with db_connection(":memory:") as conn:
        _seed_batch(conn, gv="v22", size=100, enumerated=10_000, idx=1)
        _seed_batch(conn, gv="v22", size=200, enumerated=None, idx=2)
        rows = read_budget_rows(conn)
    assert sorted((r.batch_size, r.enumerated_count) for r in rows) == [
        (100, 10_000),
        (200, None),
    ]
    assert {r.grammar_version for r in rows} == {"v22"}


def test_format_budget_shows_bracket_and_the_charge_gap() -> None:
    budget = summarize_budget([BatchRow("v22", 100, 10_000)])
    out = format_budget(budget, source="snap.db")
    assert "snap.db" in out
    assert "n_trials=1" in out  # names the gap it is measuring
    assert "configs submitted" in out
    assert "configs scored" in out
    assert f"{budget.hurdle_scored:.2f}" in out  # the breadth-end hurdle is shown


def test_cmd_alpha_budget_smoke(tmp_path: Path) -> None:
    db_path = tmp_path / "forge.db"
    with db_connection(db_path) as conn:
        _seed_batch(conn, gv="v22", size=600, enumerated=60_000, idx=1)
    result = runner.invoke(app, ["alpha-budget", "--forge-db", str(db_path)])
    assert result.exit_code == 0, result.stdout
    assert "alpha-budget" in result.stdout
    assert "600" in result.stdout  # the submitted count surfaces
