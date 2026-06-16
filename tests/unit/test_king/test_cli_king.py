"""Smoke test for `forge king` (dry-run preview) + the --out artifact."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app

runner = CliRunner()

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "king"
_ORACLE_FIXTURE = _FIXTURES / "oracle_published_2026-06-16T215346Z.json"


def test_king_dry_run_smoke() -> None:
    result = runner.invoke(
        app,
        ["king", "--oracle", str(_ORACLE_FIXTURE), "--search", "30", "--top-k", "5", "--seed", "1"],
    )
    assert result.exit_code == 0, result.output
    assert "DRY RUN" in result.output
    assert "score=" in result.output


def test_king_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "kings.json"
    result = runner.invoke(
        app,
        [
            "king",
            "--oracle",
            str(_ORACLE_FIXTURE),
            "--search",
            "30",
            "--top-k",
            "5",
            "--seed",
            "2",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["n_searched"] == 30
    # The trial count the future DSR guard must account for is surfaced.
    assert payload["dsr_trial_count_n"] == 30
    assert 1 <= len(payload["kings"]) <= 5
    assert payload["kings"][0]["predicted_score"] >= payload["kings"][-1]["predicted_score"]


def test_king_submit_to_tmp_inbox(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    forge_db = tmp_path / "forge.db"
    result = runner.invoke(
        app,
        [
            "king",
            "--oracle",
            str(_ORACLE_FIXTURE),
            "--search",
            "30",
            "--top-k",
            "3",
            "--seed",
            "1",
            "--per-cell",
            "2",
            "--submit",
            "--inbox",
            str(inbox),
            "--forge-db",
            str(forge_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "SUBMITTED meta_king" in result.output
    # kings were written to the inbox as {config_hash}.json
    assert list(inbox.glob("*.json"))


def test_king_submit_without_inbox_errors() -> None:
    result = runner.invoke(
        app, ["king", "--oracle", str(_ORACLE_FIXTURE), "--search", "20", "--submit"]
    )
    assert result.exit_code != 0
    assert "needs an inbox" in result.output
