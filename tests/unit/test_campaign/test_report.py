"""Run records must round-trip losslessly: they are the replay key for a weekly decision
and Crucible's digest reads them, so a datetime, a set of cell keys, or a nested campaign
must come back exactly as written. Unknown keys are tolerated so a newer writer never
breaks an older reader."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from forge.campaign.report import (
    baseline_cells,
    baseline_families,
    baseline_ids,
    baseline_str,
    format_status,
    load_latest_record,
    load_records,
    record_from_json,
    record_to_json,
    write_record,
)
from forge.campaign.types import (
    CAMPAIGN_RUN_SCHEMA,
    BootCheck,
    CampaignSpec,
    CellKey,
    RunRecord,
    TriggerOutcome,
)
from forge.persistence.db import open_db

_CELL_A: CellKey = ("mean_reversion", "swing_short", "named", "rsi_2", "iv_rank")
_CELL_B: CellKey = ("trend_continuation", "swing_long", "xsect", "momentum_252", "hurst")


def _record(run_id: str, started: datetime, *, status: str = "ok") -> RunRecord:
    spec = CampaignSpec(
        trigger="exploration_floor",
        cells=frozenset({_CELL_A, _CELL_B}),
        budget=20,
        reason="dark cells rotation",
        indicator_ids=frozenset({"rsi_2"}),
    )
    return RunRecord(
        schema_version=CAMPAIGN_RUN_SCHEMA,
        run_id=run_id,
        started_at=started,
        finished_at=started,
        dry_run=False,
        status=status,  # type: ignore[arg-type]
        grammar_version="v55",
        registry_hash="abc",
        enumeration_inputs_hash="x|y",
        seed=123,
        iso_week="2026-W38",
        watermarks={"registry": "registry_snapshot_1.json@deadbeefdead"},
        boot=(BootCheck("contracts", True, "1.47.0"),),
        designated_id="7f2a697ec6c1b119",
        triggers=(
            TriggerOutcome("leg_health", False, "no baseline"),
            TriggerOutcome("exploration_floor", True, "2 dark cells", spec),
        ),
        campaigns=(spec,),
        enumerated=200,
        kept_in_cells=40,
        survived_battery=12,
        gated_out={"dead_cell": 1},
        submitted=2,
        submitted_hashes=("aaaa", "bbbb"),
        batch_id="batch-1",
        models={"verdict": "abcdef12", "robustness:target_cpcv_p25": "12345678"},
        baselines={
            "book_cells": [list(_CELL_A)],
            "refutation_hash": "h1",
            "refutation_ids": ["e1"],
            "registry_ids": ["rsi_2", "hurst"],
            "registry_families": {"rsi_2": "momentum"},
        },
        notes=("reconciled 3",),
    )


def test_round_trip_is_lossless() -> None:
    rec = _record("2026-W38-20260920T030000Z", datetime(2026, 9, 20, 3, tzinfo=UTC))
    again = record_from_json(record_to_json(rec))
    assert again.triggers == rec.triggers
    assert again.campaigns == rec.campaigns
    assert again.started_at == rec.started_at
    assert again.submitted_hashes == rec.submitted_hashes
    assert baseline_cells(again) == frozenset({_CELL_A})
    assert baseline_ids(again, "refutation_ids") == frozenset({"e1"})
    assert baseline_families(again) == {"rsi_2": "momentum"}
    assert baseline_str(again, "refutation_hash") == "h1"


def test_unknown_keys_are_ignored_on_read() -> None:
    rec = _record("r1", datetime(2026, 9, 20, 3, tzinfo=UTC))
    raw = json.loads(record_to_json(rec))
    raw["future_field"] = {"anything": 1}
    assert record_from_json(json.dumps(raw)).run_id == "r1"


def test_write_and_latest_are_ordered_by_start(tmp_path: Path) -> None:
    records = tmp_path / "campaigns"
    early = _record("2026-W37-a", datetime(2026, 9, 13, 3, tzinfo=UTC))
    late = _record("2026-W38-b", datetime(2026, 9, 20, 3, tzinfo=UTC))
    write_record(records, late)
    path = write_record(records, early)
    assert path.suffix == ".json"
    assert not list(records.glob("*.tmp"))
    assert [r.run_id for r in load_records(records)] == ["2026-W37-a", "2026-W38-b"]
    latest = load_latest_record(records)
    assert latest is not None
    assert latest.run_id == "2026-W38-b"
    assert load_latest_record(tmp_path / "missing") is None


def test_status_joins_verdicts_when_a_db_is_given() -> None:
    rec = _record("r1", datetime(2026, 9, 20, 3, tzinfo=UTC))
    conn = open_db(":memory:")
    conn.execute(
        "INSERT INTO verdicts (crucible_run_id, config_hash, decision, decided_at, "
        "trade_count, grammar_version, gate_results, recorded_at) VALUES "
        "(gen_random_uuid(), 'aaaa', 'component', now(), 5, 'v55', '{}', now()), "
        "(gen_random_uuid(), 'bbbb', 'reject', now(), 5, 'v55', '{}', now())"
    )
    text = format_status([rec], conn)
    assert "fired=exploration_floor" in text
    assert "verdicts=2 converting=1" in text
    assert "submitted=2" in text
    assert format_status([], None) == "no campaign runs recorded yet"
