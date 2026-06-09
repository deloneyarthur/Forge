"""D111 — one-time backfill of the `verdicts` table from a gated-runs export.

Context: `verdicts` (durable per-candidate Crucible decisions) ships with
D111; `reconcile_all_pending` populates it forward-looking on every poll.
This script is the catch-up step: it ingests an export snapshot so the
current rolling window's ~10k verdicts — including the only deep v9-cohort
evidence (202 components) — are preserved before they roll off. Re-running
it, or following it with the consumer's own sweep, inserts nothing twice
(PK `crucible_run_id`).

MUST run while `forge.service` is stopped (DuckDB is single-writer; slot
this into the deploy stop-window per docs/tasks/deploy.md), or against a
DB copy.

USAGE:
    uv run python scripts/backfill_verdicts.py \\
        [--export-json /path/to/gated_runs_*.json] \\
        [--forge-db ~/forge_data/forge.db] \\
        [--dry-run]

DEFAULTS:
    export-json: newest gated_runs_*.json in ~/optbt_data/exports
    forge-db:    ~/forge_data/forge.db
    dry-run:     false

DRY RUN: reports how many rows would be inserted without writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def _newest_export(exports_dir: Path) -> Path:
    candidates = sorted(exports_dir.glob("gated_runs_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        msg = f"no gated_runs_*.json under {exports_dir}"
        raise FileNotFoundError(msg)
    return candidates[-1]


def _load_runs(export_json: Path) -> list:
    from crucible_contracts import GatedRun

    payload = json.loads(export_json.read_text(encoding="utf-8"))
    raw = payload.get("gated_runs", [])
    if not isinstance(raw, list):
        msg = f"export at {export_json} has a malformed `gated_runs` field"
        raise ValueError(msg)
    return [GatedRun.model_validate(r) for r in raw]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-json",
        type=Path,
        default=None,
        help="gated_runs export snapshot (default: newest in ~/optbt_data/exports)",
    )
    parser.add_argument(
        "--forge-db",
        type=Path,
        default=Path.home() / "forge_data" / "forge.db",
        help="Forge DB path (service must be stopped)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = parser.parse_args(argv)

    from forge.persistence.db import db_connection
    from forge.persistence.verdicts import record_verdicts

    export_json = args.export_json or _newest_export(Path.home() / "optbt_data" / "exports")
    runs = _load_runs(export_json)
    print(f"export: {export_json} ({len(runs)} gated runs)")

    with db_connection(args.forge_db) as conn:
        if args.dry_run:
            known_row = conn.execute(
                "SELECT COUNT(DISTINCT config_hash) FROM submissions"
            ).fetchone()
            existing_row = conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()
            known_hashes = {
                str(h)
                for (h,) in conn.execute("SELECT DISTINCT config_hash FROM submissions").fetchall()
            }
            existing_ids = {
                str(r) for (r,) in conn.execute("SELECT crucible_run_id FROM verdicts").fetchall()
            }
            would = sum(
                1
                for gr in runs
                if gr.run.config_hash in known_hashes and gr.run.run_id not in existing_ids
            )
            print(
                f"DRY RUN: would insert {would} verdicts "
                f"(submissions hashes known: {known_row[0] if known_row else 0}; "
                f"verdicts already present: {existing_row[0] if existing_row else 0})"
            )
            return 0
        inserted = record_verdicts(conn, runs)
        total_row = conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()
        total = int(total_row[0]) if total_row else 0
        print(f"inserted {inserted} verdicts (table now holds {total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
