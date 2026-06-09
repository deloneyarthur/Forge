"""D116 — one-time repair of mixed-era `verdicts.decided_at` values.

Context: Crucible's decided_at storage carried mixed timezone eras (old-box
PDT-naive; UTC-naive for half of 06-07; PDT-naive again) until their
2026-06-09T22:55Z fix, which migrated storage to uniform UTC and made exports
emit tz-aware UTC (`FORGE_runner_capacity_stability_response.md` §3). Verdicts
rows Forge ingested BEFORE that fix carry the stale naive-local values —
measured 2026-06-09: 8,044 of 10,182 rows exactly +7h late. Era-cut analyses
(e.g. the Q32 enforcement boundary) silently mis-split on them.

Repair, in trust order:

1. Rows whose run_id is in the CORRECTED export: set decided_at to the
   export's value (authoritative — Crucible resolved each row against the
   runner journal).
2. Rows that rolled off the window: shift +7h ONLY when the current value
   still equals the value in the supplied PRE-FIX snapshot (the file the
   D111 backfill ingested) — so the shift is provably "as ingested" and a
   re-run cannot double-shift. All such rows observed are old-box PDT-era.
3. Anything else: reported and left untouched.

Idempotent. MUST run while `forge.service` is stopped (single-writer DB) —
slot into the next deploy stop-window. New rows the live loop ingests after
Crucible's fix are already correct (aware UTC → naive UTC at write).

USAGE:
    uv run python scripts/migrate_verdicts_decided_at.py \\
        [--export-json /path/gated_runs_*.json]   # corrected (post-fix) export
        [--prefix-snapshot ~/forge_data/backfill_source_gated_runs_20260609.json]
        [--forge-db ~/forge_data/forge.db] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

_SHIFT = timedelta(hours=7)


def _newest_export(exports_dir: Path) -> Path:
    candidates = sorted(exports_dir.glob("gated_runs_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        msg = f"no gated_runs_*.json under {exports_dir}"
        raise FileNotFoundError(msg)
    return candidates[-1]


def _decided_at_by_run_id(export_json: Path, *, require_aware: bool) -> dict[str, datetime]:
    payload = json.loads(export_json.read_text(encoding="utf-8"))
    out: dict[str, datetime] = {}
    for row in payload.get("gated_runs", []):
        raw = str(row["decision"]["decided_at"])
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if require_aware and dt.tzinfo is None:
            msg = (
                f"{export_json} carries naive decided_at ({raw}) — this is a PRE-fix "
                "export; pass a post-2026-06-09T22:55Z file as --export-json"
            )
            raise ValueError(msg)
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        out[str(row["decision"]["run_id"])] = dt
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-json",
        type=Path,
        default=None,
        help="corrected (tz-aware) export; default: newest in ~/optbt_data/exports",
    )
    default_snapshot = Path.home() / "forge_data" / "backfill_source_gated_runs_20260609.json"
    parser.add_argument(
        "--prefix-snapshot",
        type=Path,
        default=default_snapshot,
        help="the pre-fix export snapshot the D111 backfill ingested",
    )
    parser.add_argument(
        "--forge-db",
        type=Path,
        default=Path.home() / "forge_data" / "forge.db",
        help="Forge DB path (service must be stopped)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = parser.parse_args(argv)

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from forge.persistence.db import db_connection

    export_json = args.export_json or _newest_export(Path.home() / "optbt_data" / "exports")
    corrected = _decided_at_by_run_id(export_json, require_aware=True)
    prefix: dict[str, datetime] = {}
    if args.prefix_snapshot.exists():
        prefix = _decided_at_by_run_id(args.prefix_snapshot, require_aware=False)
    print(
        f"corrected export: {export_json} ({len(corrected)} rows); "
        f"pre-fix snapshot: {args.prefix_snapshot if prefix else 'ABSENT'} ({len(prefix)} rows)"
    )

    fixed_export = shifted = already_ok = untouched = 0
    with db_connection(args.forge_db) as conn:
        rows = conn.execute("SELECT crucible_run_id, decided_at FROM verdicts").fetchall()
        updates: list[tuple[datetime, str]] = []
        leftovers: list[str] = []
        for rid_raw, current in rows:
            rid = str(rid_raw)
            target = corrected.get(rid)
            if target is not None:
                if current == target:
                    already_ok += 1
                else:
                    updates.append((target, rid))
                    fixed_export += 1
                continue
            ingested = prefix.get(rid)
            if ingested is not None and current == ingested:
                updates.append((current + _SHIFT, rid))
                shifted += 1
            else:
                untouched += 1
                leftovers.append(rid)
        if not args.dry_run and updates:
            conn.executemany(
                "UPDATE verdicts SET decided_at = ? WHERE crucible_run_id = ?", updates
            )
    mode = "DRY RUN — would have" if args.dry_run else "done:"
    print(
        f"{mode} set-from-export={fixed_export} shifted+7h={shifted} "
        f"already-correct={already_ok} untouched={untouched}"
    )
    if untouched and untouched <= 20:
        print("untouched run_ids:", ", ".join(leftovers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
