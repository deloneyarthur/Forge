"""Smoke tests for `forge shadow-null run` (P1-2).

The command is thin: enumerate -> battery under the production null -> re-score
permutation_test under the flip-1 null -> per-family survival table + a JSONL
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
    # The flip-1 table prints (the flip-2 arm was removed at D301).
    assert "FLIP-1 cumulative_trading" in result.stdout
    assert "FLIP-2" not in result.stdout
    assert "TOTAL" in result.stdout

    assert out.exists()
    record = json.loads(out.read_text(encoding="utf-8").strip())
    assert record["cache_kind"] == "synthetic"
    # prod_null mirrors the LIVE prefilter.yaml (cumulative_trading since the D237 flip) — assert
    # it matches whatever is shipped rather than pinning a mode, so the smoke survives the flip.
    from forge.prefilters.calibration import load_calibration

    live = load_calibration(Path(__file__).resolve().parents[3] / "config" / "prefilter.yaml")
    assert record["prod_null"]["forward_return_mode"] == live.permutation_test.forward_return_mode
    # flip-1 is recorded with per_family + totals; the flip-2 key is gone (D301).
    t = record["flip1_cumulative_trading"]["totals"]
    # Net-delta identity holds at the totals level.
    assert t["net_delta"] == t["pass_corr"] - t["pass_prod"] == t["gained"] - t["lost"]
    assert "flip2_ve_absolute_move" not in record


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
