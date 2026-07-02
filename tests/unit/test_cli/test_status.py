"""Unit tests for `forge status` (ops-sprint item 4, D198).

The streak-summary reduction (consecutive-PASS counting + trend) is the testable core;
the JSONL read + format is thin glue, smoke-tested end-to-end via the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.cli.status_cmd import summarize_streak

runner = CliRunner()


def _rec(metric: float, verdict: str, *, qualifies: bool = True, key: str = "auc_margin") -> dict:
    return {
        key: metric,
        "verdict": verdict,
        "qualifies": qualifies,
        "ts": "2026-06-23T12:00:00+00:00",
    }


def test_summarize_empty() -> None:
    s = summarize_streak([], label="x", metric_key="auc_margin", metric_name="AUC")
    assert s.n_records == 0
    assert s.consecutive_pass == 0
    assert s.latest_metric is None
    assert s.latest_verdict is None
    assert s.trend == ()


def test_consecutive_pass_counts_trailing_qualifying_pass() -> None:
    recs = [_rec(0.1, "PASS"), _rec(0.2, "FAIL"), _rec(0.3, "PASS"), _rec(0.4, "PASS")]
    s = summarize_streak(recs, label="x", metric_key="auc_margin", metric_name="AUC")
    assert s.consecutive_pass == 2  # only the trailing two PASS
    assert s.latest_verdict == "PASS"
    assert s.latest_metric == 0.4


def test_non_qualifying_rows_skipped_not_breaking() -> None:
    recs = [_rec(0.3, "PASS"), _rec(0.0, "INSUFFICIENT", qualifies=False), _rec(0.4, "PASS")]
    s = summarize_streak(recs, label="x", metric_key="auc_margin", metric_name="AUC")
    assert s.consecutive_pass == 2  # the non-qualifying row neither counts nor breaks


def test_qualifying_fail_breaks_streak() -> None:
    recs = [_rec(0.3, "PASS"), _rec(0.1, "FAIL"), _rec(0.4, "PASS")]
    s = summarize_streak(recs, label="x", metric_key="auc_margin", metric_name="AUC")
    assert s.consecutive_pass == 1  # newest PASS; the qualifying FAIL before it stops it


def test_trend_takes_last_k_metric_values() -> None:
    recs = [_rec(float(i), "PASS") for i in range(12)]
    s = summarize_streak(recs, label="x", metric_key="auc_margin", metric_name="AUC")
    assert s.trend == tuple(float(i) for i in range(4, 12))  # last 8, oldest -> newest


def test_spearman_metric_key() -> None:
    recs = [_rec(0.27, "FAIL", key="spearman")]
    s = summarize_streak(recs, label="tail", metric_key="spearman", metric_name="Spearman")
    assert s.latest_metric == 0.27
    assert s.consecutive_pass == 0


def test_delta_metric_key() -> None:
    recs = [_rec(0.16, "PASS", key="delta")]
    s = summarize_streak(recs, label="re-wire", metric_key="delta", metric_name="delta vs P")
    assert s.latest_metric == 0.16
    assert s.consecutive_pass == 1


def test_cmd_status_smoke(tmp_path: Path) -> None:
    eval_dir = tmp_path / "ranker_eval"
    eval_dir.mkdir()
    (eval_dir / "streak.jsonl").write_text(json.dumps(_rec(0.4, "PASS")) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "F3 verdict ranker" in result.stdout
    assert "wf_p25 tail" in result.stdout


def test_cmd_status_shows_rewire_clock(tmp_path: Path) -> None:
    eval_dir = tmp_path / "ranker_eval"
    eval_dir.mkdir()
    (eval_dir / "streak.jsonl").write_text(json.dumps(_rec(0.4, "PASS")) + "\n", encoding="utf-8")
    (eval_dir / "rewire_streak_wfp25.jsonl").write_text(
        json.dumps(_rec(0.16, "PASS", key="delta")) + "\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "re-wire gate-tail" in result.stdout


def test_cmd_status_shows_calibration_line(tmp_path: Path) -> None:
    # P1.3: the latest calibration verdict + max_ce (from streak.jsonl) and floor keep-rate
    # (from the rewire clock) render on the drift-guard line.
    eval_dir = tmp_path / "ranker_eval"
    eval_dir.mkdir()
    f3 = _rec(0.4, "PASS")
    f3["model_max_ce"] = 0.356
    f3["calibration_verdict"] = "FAIL"
    (eval_dir / "streak.jsonl").write_text(json.dumps(f3) + "\n", encoding="utf-8")
    rw = _rec(0.16, "PASS", key="delta")
    rw["eligible_fraction"] = 0.9869
    (eval_dir / "rewire_streak_wfp25.jsonl").write_text(json.dumps(rw) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "P calibration/floor" in result.stdout
    assert "FAIL" in result.stdout
    assert "0.356" in result.stdout
    assert "0.9869" in result.stdout


def test_cmd_status_calibration_line_tolerates_old_records(tmp_path: Path) -> None:
    # Records predating P1.3 lack the calibration fields — the line still renders (n/a).
    eval_dir = tmp_path / "ranker_eval"
    eval_dir.mkdir()
    (eval_dir / "streak.jsonl").write_text(json.dumps(_rec(0.4, "PASS")) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "P calibration/floor" in result.stdout
    assert "n/a" in result.stdout
