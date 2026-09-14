"""End-to-end weekly run on a hermetic tree: temp DB, demo registry as a fresh export,
synthetic feature cache, permissive prefilter, empty book. Pins the contract that matters
most for a zero-input tool — the same inputs give the same plan, boot failures submit
nothing and leave a record, and a live run's inbox equals its record."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from crucible_contracts import GatedRun
from crucible_contracts.models import PromotionDecision, RunResult

from forge.campaign.run import run_campaign
from forge.campaign.types import CampaignConfig, RunRecord
from forge.core.clock import utc_now
from forge.enumeration._demo_registry import demo_registry
from forge.persistence.db import db_connection
from forge.prefilters.feature_cache import SyntheticFeatureCache

_REPO = Path(__file__).resolve().parents[3]
_CFG = CampaignConfig(
    weekly_cap=30,
    exploration_min=10,
    enumeration_attempts=300,
    oversample_factor=2,
    dead_min_decided=1000,
    min_hypothesis_fraction=0.0,
)


def _write_registry(exports_dir: Path, *, age_days: int = 0) -> None:
    taken = utc_now() - timedelta(days=age_days)
    snap = demo_registry().model_copy(update={"snapshot_taken_at": taken})
    target = exports_dir / "registry_snapshot_0001.json"
    target.write_text(snap.model_dump_json(), encoding="utf-8")


def _one_gated_run() -> dict[str, object]:
    """The export must carry >= 1 row: an EMPTY gated export makes the consumer fall back
    to a direct DuckDB read (a test-fixture path), which is not what production sees."""
    rid = str(uuid.uuid4())
    run = GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash="0000000000000000",
            metrics={"total_return": 0.0},
            trade_count=1,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v55",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision="reject",
            gate_results={},
            decided_at=utc_now(),
            decided_by="runner.forge_minimal",
        ),
    )
    return json.loads(run.model_dump_json())


def _env(tmp_path: Path) -> dict[str, Path]:
    exports = tmp_path / "exports"
    exports.mkdir()
    _write_registry(exports)
    (exports / "universe_tickers_0001.json").write_text(
        json.dumps({"tier_1": ["SPY", "QQQ"], "tier_2": ["AAPL"], "tier_3": []}), encoding="utf-8"
    )
    gated = json.dumps({"gated_runs": [_one_gated_run()]})
    (exports / "gated_runs_0001.json").write_text(gated, encoding="utf-8")
    (exports / "failed_runs_0001.json").write_text(
        json.dumps({"failed_runs": []}), encoding="utf-8"
    )
    config_root = tmp_path / "config"
    config_root.mkdir()
    shutil.copy(_REPO / "config" / "grammar.yaml", config_root / "grammar.yaml")
    (config_root / "grammar_archive").symlink_to(_REPO / "config" / "grammar_archive")
    prefilter = (_REPO / "config" / "prefilter.yaml").read_text(encoding="utf-8")
    prefilter = prefilter.replace("p_value_threshold: 0.10", "p_value_threshold: 1.0")
    prefilter = prefilter.replace("forward_horizon_days: 5", "forward_horizon_days: 0")
    (config_root / "prefilter.yaml").write_text(prefilter, encoding="utf-8")
    shutil.copy(
        _REPO / "config" / "auto_tightened_thresholds.yaml",
        config_root / "auto_tightened_thresholds.yaml",
    )
    data = tmp_path / "forge_data"
    data.mkdir()
    return {
        "forge_db": data / "forge.db",
        "exports": exports,
        "inbox": tmp_path / "inbox",
        "models": data / "models",
        "records": data / "campaigns",
        "config_root": config_root,
        "crucible_db": tmp_path / "absent-runs.duckdb",
    }


def _run(
    env: dict[str, Path], *, dry_run: bool, cfg: CampaignConfig = _CFG, **kw: object
) -> RunRecord:
    lines: list[str] = []
    record = run_campaign(
        forge_db_path=env["forge_db"],
        exports_dir=env["exports"],
        inbox_root=env["inbox"],
        models_dir=env["models"],
        records_dir=env["records"],
        config_root=env["config_root"],
        crucible_db=env["crucible_db"],
        cfg=cfg,
        dry_run=dry_run,
        feature_cache_factory=lambda _registry, seed: SyntheticFeatureCache(root_seed=seed),
        echo=lines.append,
        **kw,  # type: ignore[arg-type]
    )
    assert any(line.startswith("campaign ") for line in lines)
    return record


def test_first_dry_run_fires_only_the_exploration_floor(tmp_path: Path) -> None:
    env = _env(tmp_path)
    record = _run(env, dry_run=True)
    assert record.status == "ok"
    assert all(c.ok for c in record.boot)
    fired = {t.trigger for t in record.triggers if t.fired}
    assert fired == {"exploration_floor"}
    assert [c.trigger for c in record.campaigns] == ["exploration_floor"]
    assert record.enumerated > 0
    assert record.submitted == 0
    assert 0 < len(record.submitted_hashes) <= _CFG.weekly_cap
    assert not env["inbox"].exists()
    assert (env["records"] / f"{record.run_id}.json").exists()
    assert "registry" in record.watermarks
    assert record.baselines["registry_ids"]


def test_second_dry_run_on_the_same_inputs_reproduces_the_plan(tmp_path: Path) -> None:
    env = _env(tmp_path)
    first = _run(env, dry_run=True)
    second = _run(env, dry_run=True)
    assert second.seed == first.seed
    assert second.campaigns == first.campaigns
    assert second.submitted_hashes == first.submitted_hashes
    assert not any(t.fired for t in second.triggers if t.trigger != "exploration_floor")


def test_live_run_submits_within_cap_and_tags_campaign_rows(tmp_path: Path) -> None:
    env = _env(tmp_path)
    record = _run(env, dry_run=False)
    assert record.status == "ok"
    assert record.batch_id is not None
    assert 0 < record.submitted <= _CFG.weekly_cap
    inbox_hashes = sorted(p.stem for p in env["inbox"].glob("*.json"))
    assert inbox_hashes == sorted(record.submitted_hashes)
    with db_connection(env["forge_db"]) as conn:
        modes = conn.execute("SELECT DISTINCT selection_mode FROM submissions").fetchall()
        rows = conn.execute("SELECT config_json FROM submissions").fetchall()
    assert modes == [("campaign:exploration_floor",)]
    assert {json.loads(r[0])["selection_arm"] for r in rows} == {"ranked"}
    assert (env["forge_db"].parent / "exports" / "forge_funnel.json").exists()


def test_budget_override_caps_the_plan(tmp_path: Path) -> None:
    env = _env(tmp_path)
    record = _run(env, dry_run=True, budget_override=3)
    assert sum(c.budget for c in record.campaigns) <= 3
    assert len(record.submitted_hashes) <= 3


def test_boot_failure_records_and_submits_nothing(tmp_path: Path) -> None:
    env = _env(tmp_path)
    (env["exports"] / "registry_snapshot_0001.json").unlink()
    record = _run(env, dry_run=False)
    assert record.status == "boot_failed"
    failed = {c.name for c in record.boot if not c.ok}
    assert "registry" in failed
    assert not env["inbox"].exists()
    assert (env["records"] / f"{record.run_id}.json").exists()


def test_stale_registry_fails_boot(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_registry(env["exports"], age_days=_CFG.registry_max_age_days + 5)
    record = _run(env, dry_run=True)
    assert record.status == "boot_failed"
    detail = next(c.detail for c in record.boot if c.name == "registry")
    assert "old" in detail


@pytest.mark.parametrize("missing", ["gated_runs_0001.json", "failed_runs_0001.json"])
def test_missing_verdict_exports_fail_boot(tmp_path: Path, missing: str) -> None:
    env = _env(tmp_path)
    (env["exports"] / missing).unlink()
    record = _run(env, dry_run=True)
    assert record.status == "boot_failed"
