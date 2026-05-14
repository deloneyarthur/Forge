"""Unit tests for `forge prefilter` CLI command.

Smoke + determinism + summary flag, mirroring the Phase 2 enumerate CLI
tests. The CLI itself is thin: it composes enumerate -> battery and
prints results.
"""

from __future__ import annotations

import re

from typer.testing import CliRunner

from forge.cli.main import app

runner = CliRunner()


def test_prefilter_runs_and_prints_per_candidate_lines() -> None:
    result = runner.invoke(app, ["prefilter", "--seed", "0", "--max", "3"])
    assert result.exit_code == 0
    # Header line
    assert "grammar_version=" in result.stdout
    assert "registry_hash=" in result.stdout
    assert "seed=0" in result.stdout
    # 3 candidate lines numbered [   1]..[   3]
    lines = [line for line in result.stdout.splitlines() if re.match(r"^\[\s*\d+\]", line)]
    assert len(lines) == 3


def test_prefilter_summary_flag_emits_section() -> None:
    result = runner.invoke(app, ["prefilter", "--seed", "0", "--max", "5", "--summary"])
    assert result.exit_code == 0
    assert "-- battery summary --" in result.stdout
    assert "candidates: 5" in result.stdout


def test_prefilter_is_deterministic_for_same_seed() -> None:
    """Same seed -> identical output. Hard rule #6 / D021/D1."""
    a = runner.invoke(app, ["prefilter", "--seed", "11", "--max", "5"])
    b = runner.invoke(app, ["prefilter", "--seed", "11", "--max", "5"])
    assert a.exit_code == 0
    assert b.exit_code == 0
    assert a.stdout == b.stdout


def test_prefilter_different_seeds_differ() -> None:
    a = runner.invoke(app, ["prefilter", "--seed", "1", "--max", "5"])
    b = runner.invoke(app, ["prefilter", "--seed", "2", "--max", "5"])
    assert a.exit_code == 0
    assert b.exit_code == 0
    assert a.stdout != b.stdout
