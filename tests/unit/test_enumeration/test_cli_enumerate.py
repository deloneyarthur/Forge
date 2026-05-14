"""Smoke tests for ``forge enumerate`` CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from forge.cli.main import app


def test_enumerate_runs_default_args() -> None:
    """``forge enumerate`` with no flags produces 10 configs and exits 0."""
    runner = CliRunner()
    result = runner.invoke(app, ["enumerate"])
    assert result.exit_code == 0, result.output
    # Header line + 10 config lines
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert any(line.startswith("grammar_version=") for line in lines)
    config_lines = [line for line in lines if line.startswith("[")]
    assert len(config_lines) == 10


def test_enumerate_respects_max_and_seed() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["enumerate", "--seed", "42", "--max", "3"])
    assert result.exit_code == 0, result.output
    config_lines = [line for line in result.stdout.splitlines() if line.startswith("[")]
    assert len(config_lines) == 3


def test_enumerate_determinism_via_cli() -> None:
    """Two invocations with the same seed produce identical config lines."""
    runner = CliRunner()
    a = runner.invoke(app, ["enumerate", "--seed", "5", "--max", "4"])
    b = runner.invoke(app, ["enumerate", "--seed", "5", "--max", "4"])
    assert a.exit_code == 0
    assert b.exit_code == 0
    a_configs = [line for line in a.stdout.splitlines() if line.startswith("[")]
    b_configs = [line for line in b.stdout.splitlines() if line.startswith("[")]
    assert a_configs == b_configs


def test_enumerate_summary_flag_prints_rejection_block() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["enumerate", "--max", "2", "--summary"])
    assert result.exit_code == 0
    assert "rejection summary" in result.stdout
