"""In-run training: publishes atomically, records model ids, refuses on thin data without
crashing, and prunes each artifact family to the newest few (REL-12)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from forge.campaign.train import MIN_TRAIN_ROWS, prune_models, train_models
from forge.enumeration._demo_registry import demo_registry
from forge.persistence.db import db_connection


def _touch(models_dir: Path, name: str, **payload: object) -> Path:
    p = models_dir / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_prune_keeps_newest_per_family_and_reads_robustness_target(tmp_path: Path) -> None:
    for i in range(6):
        _touch(tmp_path, f"verdict_model_v1_2026090{i}T000000Z_{i:08x}.json")
        _touch(tmp_path, f"tail_model_v1_target_wf_p10_n200_2026090{i}T000000Z_{i:08x}.json")
        _touch(
            tmp_path,
            f"robustness_model_v1_2026090{i}T000000Z_{i:08x}.json",
            target="target_cpcv_p25",
        )
    for i in range(3):
        _touch(
            tmp_path, f"robustness_model_v1_2026091{i}T000000Z_{i:08x}.json", target="target_wf_p25"
        )
    _touch(tmp_path, "unrelated.json")
    deleted = prune_models(tmp_path, keep=4)
    assert deleted == 2 + 2 + 2  # verdict, tail, robustness:cpcv; the wf_p25 family had 3
    names = sorted(p.name for p in tmp_path.glob("*.json"))
    assert "unrelated.json" in names
    assert [n for n in names if n.startswith("verdict")] == [
        f"verdict_model_v1_2026090{i}T000000Z_{i:08x}.json" for i in range(2, 6)
    ]
    assert sum(1 for n in names if n.startswith("robustness")) == 4 + 3


def test_prune_is_a_noop_below_keep_and_on_missing_dir(tmp_path: Path) -> None:
    assert prune_models(tmp_path / "absent", keep=4) == 0
    _touch(tmp_path, "verdict_model_v1_20260901T000000Z_00000001.json")
    assert prune_models(tmp_path, keep=4) == 0
    assert prune_models(tmp_path, keep=0) == 0


def test_thin_data_refuses_without_crashing_and_keeps_old_artifacts(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    old = _touch(models, "verdict_model_v1_20260901T000000Z_00000001.json")
    with db_connection(tmp_path / "forge.db") as conn:
        outcome = train_models(
            conn, demo_registry(), models_dir=models, keep=4, echo=lambda _line: None
        )
    assert outcome.models == {}
    assert any("refused" in n for n in outcome.notes)
    assert old.exists()
    assert (
        not list((models / ".staging").glob("*.json")) if (models / ".staging").exists() else True
    )


def test_injected_frame_trains_publishes_atomically_and_records_ids(tmp_path: Path) -> None:
    """A synthetic frame with enough rows/positives exercises the success path end to end."""
    from forge.ranking.model import load_latest_model, load_latest_robustness_model

    n = max(MIN_TRAIN_ROWS, 60)
    base = datetime(2026, 8, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "crucible_run_id": [f"run-{i}" for i in range(n)],
            "config_hash": [f"{i:016x}" for i in range(n)],
            "decided_at": [base + timedelta(hours=i) for i in range(n)],
            "decision": ["component" if i % 4 == 0 else "reject" for i in range(n)],
            "label": [1 if i % 4 == 0 else 0 for i in range(n)],
            "target_cpcv_p25": [0.5 + (i % 7) * 0.1 for i in range(n)],
            "f_a": [float(i % 5) for i in range(n)],
            "f_b": [float((i * 3) % 11) for i in range(n)],
        }
    )
    models = tmp_path / "models"
    with db_connection(tmp_path / "forge.db") as conn:
        outcome = train_models(
            conn,
            demo_registry(),
            models_dir=models,
            keep=4,
            build_frame=lambda: frame,
            echo=lambda _line: None,
        )
    assert set(outcome.models) == {"verdict", "robustness:target_cpcv_p25"}
    assert load_latest_model(models) is not None
    assert load_latest_robustness_model(models, target="target_cpcv_p25") is not None
    assert not list((models / ".staging").glob("*.json"))
