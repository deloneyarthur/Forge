"""Unit tests for `forge prereg` (Tier-1a pre-registration, D207).

The registry + post-cut confirmation guard are tested in
`tests/unit/test_feedback/test_preregistration.py`; here we cover the CLI
register/list/resolve round-trip and the input validation.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.feedback.preregistration import load_preregistrations

runner = CliRunner()


def test_register_list_resolve_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "pr.jsonl"
    reg = runner.invoke(
        app,
        [
            "prereg",
            "register",
            "--claim",
            "adx<10 never promotes",
            "--predicted",
            "<= 0.005",
            "--action",
            "tighten adx lower bound",
            "--cohort-cut",
            "2026-06-25T00:00:00",
            "--path",
            str(path),
        ],
    )
    assert reg.exit_code == 0, reg.stdout
    entries = load_preregistrations(path)
    assert len(entries) == 1
    assert entries[0].status == "registered"
    pid = entries[0].prereg_id

    listed = runner.invoke(app, ["prereg", "list", "--path", str(path)])
    assert listed.exit_code == 0
    assert pid in listed.stdout
    assert "adx<10" in listed.stdout

    resolved = runner.invoke(
        app,
        [
            "prereg",
            "resolve",
            pid,
            "--outcome",
            "confirmed",
            "--evidence",
            "post-cut rate 0.002 (n=120)",
            "--path",
            str(path),
        ],
    )
    assert resolved.exit_code == 0, resolved.stdout
    reloaded = load_preregistrations(path)
    assert reloaded[0].status == "confirmed"
    assert reloaded[0].evidence == "post-cut rate 0.002 (n=120)"


def test_resolve_unknown_id_exits_nonzero(tmp_path: Path) -> None:
    path = tmp_path / "pr.jsonl"
    runner.invoke(
        app,
        [
            "prereg",
            "register",
            "--claim",
            "x",
            "--predicted",
            "<0",
            "--action",
            "y",
            "--path",
            str(path),
        ],
    )
    r = runner.invoke(
        app,
        [
            "prereg",
            "resolve",
            "deadbeefcafe",
            "--outcome",
            "confirmed",
            "--evidence",
            "z",
            "--path",
            str(path),
        ],
    )
    assert r.exit_code == 1


def test_invalid_outcome_rejected(tmp_path: Path) -> None:
    path = tmp_path / "pr.jsonl"
    r = runner.invoke(
        app,
        [
            "prereg",
            "resolve",
            "anyid",
            "--outcome",
            "maybe",
            "--evidence",
            "z",
            "--path",
            str(path),
        ],
    )
    assert r.exit_code == 2


def test_open_only_hides_resolved(tmp_path: Path) -> None:
    path = tmp_path / "pr.jsonl"
    runner.invoke(
        app,
        [
            "prereg",
            "register",
            "--claim",
            "claim-a",
            "--predicted",
            "<0",
            "--action",
            "a",
            "--path",
            str(path),
        ],
    )
    pid = load_preregistrations(path)[0].prereg_id
    runner.invoke(
        app,
        [
            "prereg",
            "resolve",
            pid,
            "--outcome",
            "refuted",
            "--evidence",
            "rate 0.3",
            "--path",
            str(path),
        ],
    )
    r = runner.invoke(app, ["prereg", "list", "--open-only", "--path", str(path)])
    assert r.exit_code == 0
    assert "(no pre-registrations)" in r.stdout
