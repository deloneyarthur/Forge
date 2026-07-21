"""Tests for `forge run` (D023/D6.a, Phase 4 CLI module 11).

Single-batch end-to-end: dry-run prints rank summary; full run writes
inbox + submissions + batch_summaries + pre_filter_logs.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRODUCTION_PREFILTER = _REPO_ROOT / "config" / "prefilter.yaml"


def _permissive_prefilter(tmp_path: Path) -> Path:
    """Materialize a tmp prefilter.yaml that admits any config.

    The end-to-end submission tests need at least one config to survive the
    pre-filter battery and reach the submitter. The synthetic feature cache
    produces uniform p-values under permutation_test (~50% mean), so the
    production `p_value_threshold=0.10` rarely admits anything; whether
    Crucible's real cache is reachable is also unstable when production
    Forge is running. This fixture sets `p_value_threshold: 1.0` so the
    test asserts the submission plumbing, not the filter calibration.
    """
    dst = tmp_path / "prefilter.yaml"
    shutil.copy(_PRODUCTION_PREFILTER, dst)
    text = dst.read_text(encoding="utf-8")
    text = text.replace("p_value_threshold: 0.10", "p_value_threshold: 1.0")
    text = text.replace("forward_horizon_days: 5", "forward_horizon_days: 0")
    dst.write_text(text, encoding="utf-8")
    return dst


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
# D216 Layer-2 floor — call-site integration (learned-audit P0.4b)
# ---------------------------------------------------------------------------


def test_orthogonal_family_floor_active_line_prints(monkeypatch: pytest.MonkeyPatch) -> None:
    """FORGE_ORTHOGONAL_FAMILY_FLOOR must actually REACH the iteration and lift the
    family — a real dry-run batch prints the 'floor ACTIVE' line. Guards the D185
    inert-call-site failure mode (a wired-but-unreached flag that passes the
    parser unit tests yet silently no-ops in production)."""
    monkeypatch.setenv("FORGE_ORTHOGONAL_FAMILY_FLOOR", "volatility_event=0.20")
    result = runner.invoke(
        app,
        ["run", "--no-config", "--seed", "0", "--batch-size", "3", "--max", "30", "--dry-run"],
    )
    assert result.exit_code == 0, result.stdout
    assert "orthogonal-family floor ACTIVE" in result.stdout
    assert "volatility_event>=0.20" in result.stdout


def test_orthogonal_family_floor_unset_prints_no_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Byte-identical OFF (hard rule 6): env unset → the block is skipped and no
    floor line prints, so the emitted sequence is unchanged."""
    monkeypatch.delenv("FORGE_ORTHOGONAL_FAMILY_FLOOR", raising=False)
    result = runner.invoke(
        app,
        ["run", "--no-config", "--seed", "0", "--batch-size", "3", "--max", "30", "--dry-run"],
    )
    assert result.exit_code == 0, result.stdout
    assert "floor ACTIVE" not in result.stdout


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
    prefilter_yaml = _permissive_prefilter(tmp_path)
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
            "--prefilter-yaml",
            str(prefilter_yaml),
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


def test_same_seed_is_deterministic(tmp_path: Path) -> None:
    # Hard rule #6: same (seed, grammar, registry) → byte-identical enumeration/submission.
    # Two INDEPENDENT fresh-DB runs at the same seed must submit the identical config set
    # (compared via inbox filenames = config_hash.json). Flip-agnostic — the property holds
    # under any prefilter mode; the earlier "second run all-dupes" form only passed when the
    # pre-flip null happened to reject every synthetic-noise config (D237 flip exposed that).
    def run(tag: str) -> list[str]:
        inbox = tmp_path / f"{tag}_inbox"
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
                str(tmp_path / f"{tag}.db"),
                "--inbox",
                str(inbox),
            ],
        )
        assert result.exit_code == 0, result.stdout
        return sorted(p.name for p in inbox.glob("*.json")) if inbox.exists() else []

    assert run("a") == run("b")


# ---------------------------------------------------------------------------
# D310 — search_n_trials stamping (self-gated on Crucible's marker)
# ---------------------------------------------------------------------------


def _seed_marker_verdict(forge_db: Path) -> None:
    """Insert a verdict row carrying Crucible's record-not-bind marker."""
    import json as _json
    import uuid as _uuid

    gate_results = _json.dumps(
        {
            "deflated_sharpe": {
                "gate_name": "deflated_sharpe",
                "passed": True,
                "value": 1.0,
                "threshold": 0.0,
                "detail": "DSR at stamped multiplicity (recorded_not_binding).",
            }
        }
    )
    with db_connection(forge_db) as conn:
        conn.execute(
            "INSERT INTO verdicts VALUES (?, ?, 'reject', '2026-07-21 01:00:00', 5, 'v42', ?,"
            " '2026-07-21 01:00:00')",
            [str(_uuid.uuid4()), "0" * 16, gate_results],
        )


def _run_and_read_inbox(tmp_path: Path, forge_db: Path) -> tuple[str, list[dict[str, object]]]:
    import json as _json

    inbox = tmp_path / "inbox"
    prefilter_yaml = _permissive_prefilter(tmp_path)
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
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    assert result.exit_code == 0, result.stdout
    configs = [_json.loads(p.read_text(encoding="utf-8")) for p in inbox.glob("*.json")]
    assert configs
    return result.stdout, configs


def test_search_n_trials_dormant_without_marker(tmp_path: Path) -> None:
    stdout, configs = _run_and_read_inbox(tmp_path, tmp_path / "forge.db")
    assert "search_n_trials: dormant" in stdout
    assert all(c["search_n_trials"] is None for c in configs)


def test_search_n_trials_stamps_when_marker_live(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    _seed_marker_verdict(forge_db)
    stdout, configs = _run_and_read_inbox(tmp_path, forge_db)
    assert "search_n_trials: stamped" in stdout
    values = [c["search_n_trials"] for c in configs]
    assert all(isinstance(v, int) and v >= 1 for v in values)
