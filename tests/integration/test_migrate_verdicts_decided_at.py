"""D117 — `scripts/migrate_verdicts_decided_at.py` one-time era repair.

Crucible's decided_at storage carried mixed timezone eras until their
2026-06-09T22:55Z fix (FORGE_runner_capacity_stability_response.md §3);
verdicts rows Forge ingested BEFORE the fix carry those stale naive-local
values (+7h late vs true UTC for the PDT eras). The migration:

- matched rows (run_id in the corrected, tz-aware export): set decided_at to
  the export's value — authoritative, journal-resolved on Crucible's side;
- unmatched rows (rolled off the window): shift +7h ONLY when the current
  value still equals the pre-fix snapshot's value for that run_id (so a
  re-run cannot double-shift);
- anything else: reported, untouched.

Idempotent by construction; safe to re-run.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import datetime
from pathlib import Path

from forge.persistence.db import db_connection

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "migrate_verdicts_decided_at.py"


def _load_script() -> object:
    spec = importlib.util.spec_from_file_location("migrate_decided_at_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _insert_verdict(db_path: Path, run_id: str, decided_at: datetime) -> None:
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO verdicts (crucible_run_id, config_hash, decision, decided_at, "
            "trade_count, grammar_version, gate_results, recorded_at) "
            "VALUES (?, 'aaaa000011112222', 'reject', ?, 7, 'v9', '{}', ?)",
            [run_id, decided_at, datetime(2026, 6, 9, 19, 0, 0)],  # noqa: DTZ001 — naive-UTC column
        )


def _export_payload(entries: dict[str, str]) -> dict:
    return {
        "schema_version": "1.0",
        "exported_at": "2026-06-09T23:14:53+00:00",
        "gated_runs": [
            {
                "run": {
                    "run_id": rid,
                    "config_hash": "aaaa000011112222",
                    "metrics": {},
                    "trade_count": 7,
                    "period_start": "2021-06-02",
                    "period_end": "2026-06-01",
                    "grammar_version": "v9",
                },
                "decision": {
                    "run_id": rid,
                    "decision": "reject",
                    "gate_results": {},
                    "decided_at": ts,
                    "decided_by": "runner.forge_minimal",
                },
            }
            for rid, ts in entries.items()
        ],
    }


def test_migration_repairs_all_three_classes_and_is_idempotent(tmp_path: Path) -> None:
    mod = _load_script()
    forge_db = tmp_path / "forge.db"

    rid_stale = str(uuid.uuid4())  # in export, stored 7h late (PDT era)
    rid_ok = str(uuid.uuid4())  # in export, already correct
    rid_rolled = str(uuid.uuid4())  # rolled off; pre-fix snapshot has it
    rid_unknown = str(uuid.uuid4())  # rolled off; nowhere — must be untouched

    _insert_verdict(forge_db, rid_stale, datetime(2026, 6, 9, 11, 37, 46))  # noqa: DTZ001
    _insert_verdict(forge_db, rid_ok, datetime(2026, 6, 9, 23, 0, 0))  # noqa: DTZ001
    _insert_verdict(forge_db, rid_rolled, datetime(2026, 5, 28, 1, 8, 38))  # noqa: DTZ001
    _insert_verdict(forge_db, rid_unknown, datetime(2026, 5, 28, 2, 0, 0))  # noqa: DTZ001

    export = tmp_path / "gated_runs_corrected.json"
    export.write_text(
        json.dumps(
            _export_payload(
                {
                    rid_stale: "2026-06-09T18:37:46Z",  # true UTC (+7h vs stored)
                    rid_ok: "2026-06-09T23:00:00Z",  # agrees with stored
                }
            )
        ),
        encoding="utf-8",
    )
    snapshot = tmp_path / "gated_runs_prefix_snapshot.json"
    snapshot.write_text(
        json.dumps(
            _export_payload(
                {
                    rid_rolled: "2026-05-28T01:08:38",  # the value as ingested (naive PDT)
                }
            )
        ),
        encoding="utf-8",
    )

    argv = [
        "--export-json",
        str(export),
        "--prefix-snapshot",
        str(snapshot),
        "--forge-db",
        str(forge_db),
    ]
    assert mod.main(argv) == 0

    def decided(rid: str) -> datetime:
        with db_connection(forge_db) as conn:
            row = conn.execute(
                "SELECT decided_at FROM verdicts WHERE crucible_run_id = ?", [rid]
            ).fetchone()
            assert row is not None
            return row[0]

    assert decided(rid_stale) == datetime(2026, 6, 9, 18, 37, 46)  # noqa: DTZ001
    assert decided(rid_ok) == datetime(2026, 6, 9, 23, 0, 0)  # noqa: DTZ001
    assert decided(rid_rolled) == datetime(2026, 5, 28, 8, 8, 38)  # noqa: DTZ001 — +7h
    assert decided(rid_unknown) == datetime(2026, 5, 28, 2, 0, 0)  # noqa: DTZ001 — untouched

    # idempotency: second run changes nothing (rolled row no longer equals snapshot value)
    assert mod.main(argv) == 0
    assert decided(rid_stale) == datetime(2026, 6, 9, 18, 37, 46)  # noqa: DTZ001
    assert decided(rid_rolled) == datetime(2026, 5, 28, 8, 8, 38)  # noqa: DTZ001


def test_migration_dry_run_writes_nothing(tmp_path: Path) -> None:
    mod = _load_script()
    forge_db = tmp_path / "forge.db"
    rid = str(uuid.uuid4())
    _insert_verdict(forge_db, rid, datetime(2026, 6, 9, 11, 37, 46))  # noqa: DTZ001
    export = tmp_path / "gated_runs_corrected.json"
    export.write_text(json.dumps(_export_payload({rid: "2026-06-09T18:37:46Z"})), encoding="utf-8")

    rc = mod.main(["--export-json", str(export), "--forge-db", str(forge_db), "--dry-run"])
    assert rc == 0
    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT decided_at FROM verdicts WHERE crucible_run_id = ?", [rid]
        ).fetchone()
        assert row is not None
        assert row[0] == datetime(2026, 6, 9, 11, 37, 46)  # noqa: DTZ001 — unchanged
