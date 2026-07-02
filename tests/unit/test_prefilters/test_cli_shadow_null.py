"""Smoke tests for `forge shadow-null run` (P1-2).

The command is thin: enumerate -> battery under the production null -> re-score
permutation_test under the corrected null -> per-family survival table + a JSONL
telemetry record. These run on `--synthetic-cache` so they're hermetic (no writer
socket) and fast; the survival numbers are meaningless noise (as the command warns)
but the wiring, table shape, JSONL record, and determinism are what's asserted.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app

runner = CliRunner()


def test_shadow_null_runs_and_writes_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "shadow.jsonl"
    result = runner.invoke(
        app, ["shadow-null", "run", "--synthetic-cache", "-n", "30", "--out", str(out)]
    )
    assert result.exit_code == 0, result.stdout
    assert "cache=synthetic" in result.stdout
    assert "reached permutation_test" in result.stdout
    assert "family" in result.stdout  # table header
    assert "TOTAL" in result.stdout

    assert out.exists()
    record = json.loads(out.read_text(encoding="utf-8").strip())
    assert record["cache_kind"] == "synthetic"
    # The two teed-up corrections are recorded as ON in the corrected null.
    assert record["corrected_null"]["forward_return_mode"] == "cumulative_trading"
    assert record["corrected_null"]["volatility_event_absolute_move"] is True
    # Production null recorded as the un-flipped default.
    assert record["prod_null"]["forward_return_mode"] == "single_day"
    # Net-delta identity holds at the totals level.
    t = record["totals"]
    assert t["net_delta"] == t["pass_corr"] - t["pass_prod"] == t["gained"] - t["lost"]


def test_shadow_null_table_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    """Same seed -> identical survival table (hard rule #6). The JSONL `ts` differs
    run-to-run, so determinism is asserted on the printed table, not the file."""
    a = runner.invoke(
        app,
        [
            "shadow-null",
            "run",
            "--synthetic-cache",
            "--seed",
            "7",
            "-n",
            "25",
            "--out",
            str(tmp_path / "a.jsonl"),
        ],
    )
    b = runner.invoke(
        app,
        [
            "shadow-null",
            "run",
            "--synthetic-cache",
            "--seed",
            "7",
            "-n",
            "25",
            "--out",
            str(tmp_path / "b.jsonl"),
        ],
    )
    assert a.exit_code == 0
    assert b.exit_code == 0
    # Compare the per-family table region (header row through the TOTAL line),
    # excluding the trailing "appended ... <path>" line whose path differs.
    a_table = a.stdout[a.stdout.index("family") : a.stdout.index("\nappended")]
    b_table = b.stdout[b.stdout.index("family") : b.stdout.index("\nappended")]
    assert a_table == b_table
