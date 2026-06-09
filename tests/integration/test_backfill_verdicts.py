"""D111 — `scripts/backfill_verdicts.py` ingests an export snapshot into `verdicts`.

The consumer populates `verdicts` forward-looking; the backfill script is the
one-time catch-up that preserves the current export window (the only deep v9
cohort evidence) before it rolls off. Must be idempotent — it can race nothing
(deploy stop-window), but re-running it or following it with the consumer's
own sweep must not duplicate rows.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from forge.persistence.db import db_connection

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "backfill_verdicts.py"


def _load_script() -> object:
    spec = importlib.util.spec_from_file_location("backfill_verdicts_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _export_row(config_hash: str, *, decision: str = "reject") -> dict:
    rid = str(uuid.uuid4())
    return {
        "run": {
            "run_id": rid,
            "config_hash": config_hash,
            "metrics": {"total_return": 0.1},
            "trade_count": 7,
            "period_start": str(date(2021, 6, 2)),
            "period_end": str(date(2026, 6, 1)),
            "grammar_version": "v9",
        },
        "decision": {
            "run_id": rid,
            "decision": decision,
            "gate_results": {
                "min_oos_trade_count": {
                    "gate_name": "min_oos_trade_count",
                    "passed": False,
                    "value": 7.0,
                    "threshold": 100.0,
                },
            },
            "decided_at": "2026-06-09T11:37:46.484550",
            "decided_by": "runner.forge_minimal",
        },
    }


def _write_export(path: Path, rows: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "exported_at": "2026-06-09T18:51:30+00:00",
                "gated_runs": rows,
            }
        ),
        encoding="utf-8",
    )


def _insert_submission(db_path: Path, config_hash: str) -> None:
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, '{}', ?, 'gated')",
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                config_hash,
                datetime(2026, 6, 9, 0, 55, tzinfo=UTC),
            ],
        )


def _verdict_count(db_path: Path) -> int:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()
        assert row is not None
        return int(row[0])


def test_backfill_inserts_only_submitted_hashes(tmp_path: Path) -> None:
    mod = _load_script()
    export = tmp_path / "gated_runs_2026-06-09T185130Z.json"
    _write_export(export, [_export_row("aaaa000011112222"), _export_row("ffff000011112222")])
    forge_db = tmp_path / "forge.db"
    _insert_submission(forge_db, "aaaa000011112222")

    rc = mod.main(["--export-json", str(export), "--forge-db", str(forge_db)])
    assert rc == 0
    assert _verdict_count(forge_db) == 1


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    mod = _load_script()
    export = tmp_path / "gated_runs_2026-06-09T185130Z.json"
    _write_export(export, [_export_row("aaaa000011112222")])
    forge_db = tmp_path / "forge.db"
    _insert_submission(forge_db, "aaaa000011112222")

    argv = ["--export-json", str(export), "--forge-db", str(forge_db)]
    assert mod.main(argv) == 0
    assert mod.main(argv) == 0
    assert _verdict_count(forge_db) == 1


def test_backfill_dry_run_writes_nothing(tmp_path: Path) -> None:
    mod = _load_script()
    export = tmp_path / "gated_runs_2026-06-09T185130Z.json"
    _write_export(export, [_export_row("aaaa000011112222")])
    forge_db = tmp_path / "forge.db"
    _insert_submission(forge_db, "aaaa000011112222")

    rc = mod.main(["--export-json", str(export), "--forge-db", str(forge_db), "--dry-run"])
    assert rc == 0
    assert _verdict_count(forge_db) == 0
