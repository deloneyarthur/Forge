"""Integration: a full `forge run` emits the funnel export (D096 — slice 4).

End-to-end wiring check: the run loop refreshes `forge_funnel.json` and
`forge_submission_versions.json` under `<forge-db-dir>/exports/`, and they
reflect the batch's pre-filter outcomes sliced by grammar version.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from forge.cli.main import app
from forge.persistence.db import db_connection

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRODUCTION_PREFILTER = _REPO_ROOT / "config" / "prefilter.yaml"


def _permissive_prefilter(tmp_path: Path) -> Path:
    """A prefilter.yaml admissive enough that ≥1 config reaches the submitter."""
    dst = tmp_path / "prefilter.yaml"
    shutil.copy(_PRODUCTION_PREFILTER, dst)
    text = dst.read_text(encoding="utf-8")
    text = text.replace("p_value_threshold: 0.10", "p_value_threshold: 1.0")
    text = text.replace("forward_horizon_days: 5", "forward_horizon_days: 0")
    dst.write_text(text, encoding="utf-8")
    return dst


def test_full_run_emits_funnel_export(tmp_path: Path) -> None:
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
            "5",
            "--max",
            "300",
            "--forge-db",
            str(forge_db),
            "--inbox",
            str(inbox),
            "--prefilter-yaml",
            str(prefilter_yaml),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "funnel_export:" in result.stdout

    exports = forge_db.parent / "exports"
    funnel_path = exports / "forge_funnel.json"
    vm_path = exports / "forge_submission_versions.json"
    assert funnel_path.exists()
    assert vm_path.exists()

    funnel = json.loads(funnel_path.read_text())
    assert funnel["schema_version"] == "1.0"
    assert "exported_at" in funnel
    per_version = funnel["per_grammar_version"]
    assert len(per_version) == 1  # one run => one grammar version
    ((version, stage_counts),) = per_version.items()

    enumerated = stage_counts["enumerated"]
    survived = stage_counts["survived_prefilters"]
    submitted = stage_counts["submitted"]
    assert enumerated >= survived >= 1
    assert submitted >= 1
    # The load-bearing funnel invariant, on real exported data.
    assert sum(stage_counts["rejection_breakdown"].values()) == enumerated - survived

    # Join-map (Part A interim) covers the submitted configs, all under this version.
    vm = json.loads(vm_path.read_text())["config_hash_grammar_version"]
    with db_connection(forge_db) as conn:
        hashes = [
            row[0]
            for row in conn.execute(
                "SELECT config_hash FROM submissions WHERE status = 'submitted'"
            ).fetchall()
        ]
    assert hashes
    for config_hash in hashes:
        assert vm[config_hash] == version
