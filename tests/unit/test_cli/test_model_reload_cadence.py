"""Pin the model-reload cadence: the verdict model is (re)loaded EVERY iteration.

WHY: D401 recorded that F3 "loads once at loop start" and had run a 15-day-stale
model. That was wrong at HEAD — `load_latest_model` sits inside
`_run_one_iteration` (`main.py`), and the journal shows model ids rolling with
no restart. The daily trainer therefore changes what Forge submits the same
day. Nothing asserted this, which is how the wrong claim survived a D-entry.
This test makes the contract explicit: N iterations -> N loads.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli.main import app

runner = CliRunner()


def test_verdict_model_is_loaded_once_per_iteration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import forge.ranking.model as model_mod

    calls: list[Path] = []
    real_loader = model_mod.load_latest_model

    def _counting(models_dir: Path) -> object:
        calls.append(models_dir)
        return real_loader(models_dir)

    # `_run_one_iteration` imports the loader at call time, so patching the module
    # attribute is the seam (same pattern as test_feature_cache_fallback).
    monkeypatch.setattr(model_mod, "load_latest_model", _counting)
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)

    result = runner.invoke(
        app,
        [
            "run",
            "--no-config",
            "--loop",
            "--max-iterations",
            "2",
            "--dry-run",
            "--seed",
            "0",
            "--batch-size",
            "2",
            "--max",
            "20",
            "--forge-db",
            str(tmp_path / "forge.db"),
            "--inbox",
            str(tmp_path / "inbox"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert len(calls) == 2, f"expected one model load per iteration, saw {len(calls)}"
    assert all(p == tmp_path / "models" for p in calls)
