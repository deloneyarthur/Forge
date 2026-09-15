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
    # Pinned to midnight UTC: the run's seed derives from the registry hash, which covers
    # `snapshot_taken_at`, so a per-call `utc_now()` re-seeded every run and made the tiny
    # 300-attempt sample flake (some seeds leave the synthetic battery zero survivors).
    taken = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=age_days)
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
        cfg=cfg,
        dry_run=dry_run,
        feature_cache_factory=lambda _registry, seed: SyntheticFeatureCache(root_seed=seed),
        echo=lines.append,
        **{"skip_train": True, **kw},  # type: ignore[arg-type]
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


def _write_forge_stream(env: dict[str, Path], *, truncated: bool) -> None:
    """Crucible's forge-scoped 14-day stream (contracts 1.48.0): the envelope the loader
    validates, carrying the same GatedRun rows as the all-source export."""
    payload = {
        "schema_version": "1.0",
        "exported_at": utc_now().isoformat(),
        "lookback_days": 14,
        "cap": 10000,
        "truncated": truncated,
        "gated_runs": [_one_gated_run()],
    }
    (env["exports"] / "forge_gated_runs_0001.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@pytest.mark.parametrize("truncated", [True, False])
def test_reconcile_reads_the_forge_stream_and_records_truncation(
    tmp_path: Path, truncated: bool
) -> None:
    """D412: the campaign reconciles from `forge_gated_runs_*` (never the all-source glob)
    and records whether the window was truncated — the rule that decides the aged-out flush."""
    env = _env(tmp_path)
    _write_forge_stream(env, truncated=truncated)
    record = _run(env, dry_run=True)
    assert record.status == "ok"
    assert "forge_gated_runs" in record.watermarks
    note = next(n for n in record.notes if n.startswith("forge_gated_runs:"))
    assert f"truncated={truncated}" in note
    assert "1 rows, lookback 14 d, cap 10000" in note
    assert not any("absent" in n for n in record.notes)


def test_reconcile_falls_back_when_the_forge_stream_is_absent(tmp_path: Path) -> None:
    """An ABSENT forge stream is at least as blind as a truncated one (Crucible 09-14 §3): the
    fallback reconciles from the ~24 h all-source export, whose floating watermark would stamp
    the whole previous run aged-out, so the flush must be off on this path too."""
    env = _env(tmp_path)
    record = _run(env, dry_run=True)
    assert record.status == "ok"
    assert "forge_gated_runs" not in record.watermarks
    note = next(n for n in record.notes if n.startswith("forge_gated_runs: absent"))
    assert "aged-out flush skipped" in note


def test_training_on_a_thin_db_refuses_gracefully_and_the_run_continues(tmp_path: Path) -> None:
    """G0: in-run training degrades, never crashes. The fixture DB has no verdicts, so both
    fits refuse; the run ranks on whatever artifacts exist (none) and still completes."""
    env = _env(tmp_path)
    record = _run(env, dry_run=True, skip_train=False)
    assert record.status == "ok"
    assert record.models == {}
    assert any(n.startswith("train verdict: refused") for n in record.notes)
    assert any(n.startswith("train robustness[") and "refused" in n for n in record.notes)
    assert not (env["models"] / ".staging").exists() or not list(
        (env["models"] / ".staging").glob("*.json")
    )


def test_skip_train_is_recorded(tmp_path: Path) -> None:
    env = _env(tmp_path)
    record = _run(env, dry_run=True)
    assert "train: skipped (--skip-train)" in record.notes
    assert record.models == {}


def _write_preregs(env: dict[str, Path], entries: list[dict[str, object]]) -> None:
    (env["config_root"] / "preregistrations.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8"
    )


def test_boot_fails_on_an_unwatchable_open_prereg(tmp_path: Path) -> None:
    """D389 in code: a registration nothing can watch must not let the run proceed quietly."""
    env = _env(tmp_path)
    _write_preregs(env, [{"prereg_id": "bbbbbbbbbbbb", "status": "registered", "claim": "x"}])
    record = _run(env, dry_run=True)
    assert record.status == "boot_failed"
    check = next(c for c in record.boot if c.name == "preregistrations")
    assert not check.ok
    assert "UNWATCHABLE" in check.detail


def test_boot_fails_when_a_registered_read_is_due(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_preregs(
        env,
        [
            {
                "prereg_id": "aaaaaaaaaaaa",
                "status": "registered",
                "claim": "x",
                "cohort_cut": "2026-08-10T16:25:55+00:00",
                "watch": {"n": 0, "basis_fp": "e1adced727678c8f"},
            }
        ],
    )
    record = _run(env, dry_run=True)
    assert record.status == "boot_failed"
    check = next(c for c in record.boot if c.name == "preregistrations")
    assert "DUE" in check.detail


def test_boot_passes_with_an_open_prereg_still_waiting(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_preregs(
        env,
        [
            {
                "prereg_id": "aaaaaaaaaaaa",
                "status": "registered",
                "claim": "x",
                "cohort_cut": "2026-08-10T16:25:55+00:00",
                "watch": {"n": 7200, "basis_fp": "e1adced727678c8f"},
            }
        ],
    )
    record = _run(env, dry_run=True)
    assert record.status == "ok"
    check = next(c for c in record.boot if c.name == "preregistrations")
    assert check.ok
    assert "7,200 to go" in check.detail


def test_sigterm_mid_batch_stops_between_candidates_and_records_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REL-4 contract at the run level: a stop requested while the first candidate is in
    flight lets that candidate finish (inbox file AND committed row), submits nothing more,
    writes an `error` record naming the stop, and raises so the unit exits non-zero."""
    import forge.submission.submitter as submitter_mod
    from forge.campaign import stop
    from forge.campaign.stop import CampaignStopped

    env = _env(tmp_path)
    plan = _run(env, dry_run=True)
    assert len(plan.submitted_hashes) >= 2, "fixture must plan at least two candidates"
    real_submit = submitter_mod.submit_candidate

    def stopping_submit(config: object, inbox_root: Path) -> object:
        receipt = real_submit(config, inbox_root)  # type: ignore[arg-type]
        stop.request_stop()  # the signal lands while this candidate is in flight
        return receipt

    monkeypatch.setattr(submitter_mod, "submit_candidate", stopping_submit)
    lines: list[str] = []
    with pytest.raises(CampaignStopped):
        run_campaign(
            forge_db_path=env["forge_db"],
            exports_dir=env["exports"],
            inbox_root=env["inbox"],
            models_dir=env["models"],
            records_dir=env["records"],
            config_root=env["config_root"],
            cfg=_CFG,
            dry_run=False,
            skip_train=True,
            feature_cache_factory=lambda _registry, seed: SyntheticFeatureCache(root_seed=seed),
            echo=lines.append,
        )
    assert stop.stop_requested() is False, "the guard must clear the flag on exit"
    from forge.campaign.report import load_records

    record = [r for r in load_records(env["records"]) if not r.dry_run][-1]
    assert record.status == "error"
    assert record.submitted == 1
    assert record.batch_id is not None
    assert any("stopped by SIGTERM after 1 submission" in n for n in record.notes)
    inbox_files = sorted(p.stem for p in env["inbox"].glob("*.json"))
    with db_connection(env["forge_db"]) as conn:
        rows = conn.execute(
            "SELECT config_hash FROM submissions WHERE status = 'submitted'"
        ).fetchall()
    assert len(inbox_files) == 1
    assert [str(r[0]) for r in rows] == inbox_files
