"""Unit tests for `forge status` (ops-sprint item 4, D198).

The streak-summary reduction (consecutive-PASS counting + trend) is the testable core;
the JSONL read + format is thin glue, smoke-tested end-to-end via the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.cli.status_cmd import rewire_flip_gate, summarize_streak

runner = CliRunner()

_CLEAN_ERA_ISO = "2026-06-10T17:17:13"


def _rec(metric: float, verdict: str, *, qualifies: bool = True, key: str = "auc_margin") -> dict:
    return {
        key: metric,
        "verdict": verdict,
        "qualifies": qualifies,
        "ts": "2026-06-23T12:00:00+00:00",
    }


def _rewire_rec(
    delta: float, verdict: str, *, window_since: str = "2026-07-01T00:00:00", qualifies: bool = True
) -> dict:
    return {
        "delta": delta,
        "verdict": verdict,
        "qualifies": qualifies,
        "window_since": window_since,
        "ts": "2026-07-01T12:00:00+00:00",
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
    # D285: the §8.6 wf_p25 tail clock is RETIRED (self-referential after the gate-tail
    # flip made the recorded incumbent the lane's own score) — no clock line (its unique
    # metric label), no SPRT line; a tombstone note points at the history file instead.
    assert "Δ Spearman vs P" not in result.stdout
    assert "§8.6 tail flip gate" not in result.stdout
    assert "retired" in result.stdout


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


def test_flip_gate_excludes_full_pool_look() -> None:
    # P1.2: the contaminated full-pool first-look (window_since == clean-era) never counts,
    # whether tagged is_first_look or identified by window_since.
    records = [
        {**_rewire_rec(0.007, "FAIL", window_since=_CLEAN_ERA_ISO), "is_first_look": True},
        _rewire_rec(0.333, "PASS"),
    ]
    g = rewire_flip_gate(records, clean_era_iso=_CLEAN_ERA_ISO)
    assert g.fresh_pass_streak == 1  # only the fresh PASS; the full-pool FAIL is excluded
    assert g.n_fresh_qualifying == 1
    assert not g.met  # 1 < k=3 (SPRT min_observations) -> continue, never met


def test_flip_gate_met_when_sprt_promotes() -> None:
    # P3.1: three fresh checkpoints with tight positive deltas >> min_effect -> the SPRT
    # log-LR crosses the upper Wald boundary -> promote -> MET.
    records = [_rewire_rec(d, "PASS") for d in (0.30, 0.33, 0.31)]
    g = rewire_flip_gate(records, clean_era_iso=_CLEAN_ERA_ISO)
    assert g.fresh_pass_streak == 3
    assert g.sprt_decision == "promote"
    assert g.sprt_log_lr >= g.sprt_upper
    assert g.met


def test_flip_gate_not_met_when_evidence_inconclusive() -> None:
    # Three fresh checkpoints but the deltas straddle 0 (high variance) -> the SPRT stays
    # between the boundaries -> continue -> NOT MET.
    records = [_rewire_rec(d, "PASS") for d in (0.40, -0.30, 0.35)]
    g = rewire_flip_gate(records, clean_era_iso=_CLEAN_ERA_ISO)
    assert g.fresh_pass_streak == 3
    assert g.sprt_decision == "continue"
    assert not g.met


def test_flip_gate_streak_breaks_on_qualifying_fail() -> None:
    records = [_rewire_rec(0.3, "PASS"), _rewire_rec(0.01, "FAIL"), _rewire_rec(0.33, "PASS")]
    g = rewire_flip_gate(records, clean_era_iso=_CLEAN_ERA_ISO)
    assert g.fresh_pass_streak == 1  # trailing PASS only; the qualifying FAIL breaks it
    assert not g.met


def test_cmd_status_adoption_guard_reads_rewire_lane(tmp_path: Path) -> None:
    # D285: with the §8.6 clock retired, the adoption guard's second arm reads the
    # LIVE lane's signal — the rewire clock's latest delta (gate-tail vs P-alone) —
    # instead of the self-referential wf_p25 paired delta.
    eval_dir = tmp_path / "ranker_eval"
    eval_dir.mkdir()
    (eval_dir / "streak.jsonl").write_text(json.dumps(_rec(0.4, "PASS")) + "\n", encoding="utf-8")
    (eval_dir / "rewire_streak_wfp25.jsonl").write_text(
        json.dumps(_rewire_rec(0.333, "PASS")) + "\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "gate-tail-lane=ADOPT" in result.stdout
    assert "wf_p25=" not in result.stdout


def test_cmd_status_shows_flip_gate_line(tmp_path: Path) -> None:
    eval_dir = tmp_path / "ranker_eval"
    eval_dir.mkdir()
    (eval_dir / "streak.jsonl").write_text(json.dumps(_rec(0.4, "PASS")) + "\n", encoding="utf-8")
    (eval_dir / "rewire_streak_wfp25.jsonl").write_text(
        json.dumps(_rewire_rec(0.333, "PASS")) + "\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["status", "--data-root", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "gate-tail flip gate" in result.stdout
    assert "NOT MET" in result.stdout  # 1/3, no CI yet


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
