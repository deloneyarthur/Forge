#!/usr/bin/env python3
"""Watch open preregistrations for a read that has come due — and refuse to be a claim.

D389 is why this exists. `3b0cbca7ae17` reached its registered trigger and nothing fired;
`STATUS.md` said a watcher was armed and there was no unit and no cron behind the sentence.
Because a preregistration forbids extension, a read that drifts past its trigger is not a
scheduling annoyance: the sample keeps growing away from the one that was registered, and the
longer it drifts the less the eventual read is the read that was promised.

WHAT IT CHECKS. For each preregistration still `registered`:

  * with a machine-readable clock (`watch: {n, basis_fp}`) — count qualifying rows IN THAT
    BASIS since the cohort cut, and report DUE or the remaining count.
  * without one — report **UNWATCHABLE**, loudly, and exit non-zero.

That second case is the D389 defect itself. The failure was never a broken watcher; it was a
claim no watcher could have checked. Crucible hit the same class twice in the same week ("a
revisit trigger with no observable"), and the agreed disposition is **arm it or delete the
claim**. A registration that cannot be watched should be re-registered with a clock, not
watched harder.

WHAT IT DELIBERATELY DOES NOT DO. It never computes the metric. It counts rows and compares
fingerprints; deciding whether to page by peeking at the answer would BE the read. It also
never resolves anything — `freeze_registered_read.py --resolve` does that, once, when a human
or a timer takes the actual read.

Exit codes, chosen so a systemd timer surfaces both conditions:
    0  nothing open, or nothing due
    1  a read is DUE — take it
    2  an open preregistration is UNWATCHABLE — fix the registration
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "config" / "preregistrations.jsonl"

EXIT_OK = 0
EXIT_DUE = 1
EXIT_UNWATCHABLE = 2

CountRows = Callable[[str, str], int]


def _open_entries(registry: Path) -> list[dict]:
    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if row.get("status") == "registered":
            out.append(row)
    return out


def assess(registry: Path, count_rows: CountRows) -> tuple[int, str]:
    """Pure assessment. Returns (exit_code, human-readable report)."""
    entries = _open_entries(registry)
    if not entries:
        return EXIT_OK, "no open preregistrations — nothing to watch."

    lines: list[str] = []
    any_due = False
    any_unwatchable = False

    for row in entries:
        pid = str(row.get("prereg_id", "?"))
        watch = row.get("watch")
        if not isinstance(watch, dict) or "n" not in watch or "basis_fp" not in watch:
            any_unwatchable = True
            lines.append(
                f"UNWATCHABLE  {pid}  — registered with no machine-readable clock "
                f"(needs `watch: {{n, basis_fp}}`). A claim with no observable cannot be "
                f"watched; re-register it with a clock or withdraw it (D389)."
            )
            continue
        required = int(watch["n"])
        basis_fp = str(watch["basis_fp"])
        since = str(row.get("cohort_cut", ""))
        have = count_rows(basis_fp, since)
        if have >= required:
            any_due = True
            lines.append(
                f"DUE          {pid}  — {have:,} rows in basis {basis_fp} since {since[:19]} "
                f"(required {required:,}). Take the read; it must not be extended."
            )
        else:
            lines.append(
                f"waiting      {pid}  — {have:,}/{required:,} in basis {basis_fp}, "
                f"{required - have:,} to go."
            )

    report = "\n".join(lines)
    if any_due:
        return EXIT_DUE, report
    if any_unwatchable:
        return EXIT_UNWATCHABLE, report
    return EXIT_OK, report


def _duckdb_counter(snapshot: Path) -> CountRows:
    """Row counter over a Forge DB snapshot, scoped to a basis and a cut.

    Mirrors the honest-arm/stage-one population the freeze reads use, and applies the basis
    filter in SQL so a foreign-basis backlog can never inflate the clock (D387/D391).
    """
    import duckdb

    def _count(basis_fp: str, since: str) -> int:
        con = duckdb.connect(str(snapshot), read_only=True)
        try:
            row = con.execute(
                """
                SELECT COUNT(*)
                FROM submissions s
                JOIN verdicts v ON v.config_hash = s.config_hash
                LEFT JOIN batch_summaries b ON b.forge_batch_id = s.forge_batch_id
                WHERE s.selection_mode = 'prefilter_sample'
                  AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
                  AND TRY_CAST(json_extract_string(
                        v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE) IS NOT NULL
                  AND split_part(b.enumeration_inputs_hash,'|',2) = ?
                  AND s.submitted_at > TRY_CAST(? AS TIMESTAMP)
                """,
                [basis_fp, since],
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()

    return _count


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "usage: freeze_read_watcher.py SNAPSHOT.db\n"
            "  (obtain one with scripts/live_db_snapshot.sh — never cp the live DB to /tmp)",
            file=sys.stderr,
        )
        return 2
    code, report = assess(REGISTRY_PATH, _duckdb_counter(Path(args[0])))
    stream = sys.stderr if code else sys.stdout
    print(report, file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
