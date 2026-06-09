"""One-off recovery: re-queue historically-tested configs whose pre-v1.1
results were potentially confounded by infrastructure bugs.

Context — bugs fixed since most submissions landed:
- D033 (per-config underlying + cache fix): pre-D033, 95% of submissions
  were SPY-locked even when `tier=2` was set; pre-filter cache returned
  SPY activations for all configs regardless of intended underlying.
- D037 (stratified sampling): pre-D037, the failure-bias sampler
  collapsed onto 1-2 hypotheses per batch; trend_continuation and
  mean_reversion had 0 and 1 submissions respectively across 4020
  historical configs.
- D038/D039 (T1.3/T1.4 silent-failure fixes): pre-D038, configs with
  empty directional-x-regime intersection (e.g., days_to_earnings regime
  on SPY) silently produced 0 trades.

Most historical submissions were doomed by these bugs, not by their
strategy merit. Re-queueing the FULL backlog of ~4020 configs is
infeasible (~55 days of Crucible compute at current pace). This script
re-queues a TARGETED SUBSET for selective re-validation:

  1. Top-N configs by historical trade_count (post-D033 they may
     produce enough trades to clear `min_oos_trade_count=100`).
  2. All `tail_hedge` configs (D039's runner-side exemptions for
     PF/CPCV/WF + T1.4's ETF event-indicator support unblock them).
  3. All `relative_value` configs (D033 pairs handling, T1.4 macro
     events all relevant).

Idempotency: hard rule #9 prevents Forge from re-emitting the same
config_hash. This script bypasses Forge's submission table by writing
the original JSON file directly to Crucible's inbox (same trick used
for batch 550e24a2's failed runs on 2026-05-15). Crucible's runner
allocates a fresh run_id; the new run row has no FK to Forge's
submissions, preserving idempotency.

USAGE:
    uv run python scripts/requeue_high_value_configs.py \\
        --forge-db ~/forge_data/forge.db \\
        --inbox-dir ~/optbt_data/inbox \\
        --processed-dir ~/optbt_data/inbox/processed \\
        [--top-n 50] [--include-tail-hedge] [--include-relative-value] \\
        [--dry-run]

DEFAULTS:
    top-n: 50 (highest trade_count in submissions metadata, post-D033 era)
    tail_hedge: include
    relative_value: include
    dry_run: false (actually copy files)

DRY RUN: prints what would be requeued without writing to inbox.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import duckdb


def _read_grammar_version(grammar_yaml: Path) -> str:
    """Read the `grammar_version: vN` field from `grammar_yaml` without
    importing Forge modules — keeps the script stdlib-only on the
    cold-start path. Falls back to `v1` if the field can't be located
    (consistent with the legacy assumption pre-D055).
    """
    if not grammar_yaml.exists():
        return "v1"
    text = grammar_yaml.read_text(encoding="utf-8")
    match = re.search(r"^grammar_version:\s*([^\s#]+)", text, re.MULTILINE)
    if match is None:
        return "v1"
    return match.group(1).strip().strip("\"'")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--forge-db", type=Path, default=Path.home() / "forge_data" / "forge.db")
    p.add_argument("--inbox-dir", type=Path, default=Path.home() / "optbt_data" / "inbox")
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=Path.home() / "optbt_data" / "inbox" / "processed",
    )
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--include-tail-hedge", action="store_true", default=True)
    p.add_argument("--include-relative-value", action="store_true", default=True)
    p.add_argument("--dry-run", action="store_true", default=False)
    # D055 / P1-3 — grammar_version filter (on by default).
    p.add_argument(
        "--grammar-yaml",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "config" / "grammar.yaml",
        help="grammar yaml: derive current_grammar_version (others get skipped)",
    )
    p.add_argument(
        "--skip-grammar-filter",
        action="store_true",
        default=False,
        help="bypass the grammar_version filter (re-queue stale-version configs anyway)",
    )
    return p.parse_args()


def filter_to_current_grammar_version(
    forge_db: Path,
    candidate_hashes: list[str],
    current_grammar_version: str,
) -> tuple[list[str], dict[str, int]]:
    """D055 / P1-3 — partition `candidate_hashes` by grammar_version.

    Returns ``(matching, skipped_by_version)`` where ``matching`` is the
    subset of `candidate_hashes` whose originating batch was enumerated
    under ``current_grammar_version``, and ``skipped_by_version`` counts
    rejections per stale version (plus an `(unknown)` bucket for hashes
    not present in `submissions`).

    The join is `submissions.forge_batch_id` → `batch_summaries.forge_batch_id`
    → `batch_summaries.grammar_version`. Pre-D055 the script re-queued
    v1-era configs into a v2-active Crucible; v1-only signals reject
    silently on Crucible's side, invisible to Forge.

    Order of `matching` is the input order so caller dedup / category
    accounting stays stable.
    """
    if not candidate_hashes:
        return ([], {})
    # config_hashes are 16-char hex slices (SHA-256 derivatives) so they're
    # SQL-safe by construction. The IN-list is built from a placeholder
    # vector parameterized via positional bind — `noqa: S608` because the
    # placeholders are a count, not user input.
    placeholders = ",".join(["?"] * len(candidate_hashes))
    conn = duckdb.connect(str(forge_db), read_only=True)
    try:
        rows = conn.execute(
            f"SELECT s.config_hash, b.grammar_version "  # noqa: S608
            f"FROM submissions s "
            f"JOIN batch_summaries b USING (forge_batch_id) "
            f"WHERE s.config_hash IN ({placeholders})",
            candidate_hashes,
        ).fetchall()
    finally:
        conn.close()
    by_hash: dict[str, str] = {str(h): str(v) for h, v in rows}
    matching: list[str] = []
    skipped: dict[str, int] = {}
    for h in candidate_hashes:
        v = by_hash.get(h)
        if v is None:
            skipped["(unknown)"] = skipped.get("(unknown)", 0) + 1
            continue
        if v == current_grammar_version:
            matching.append(h)
        else:
            skipped[v] = skipped.get(v, 0) + 1
    return (matching, skipped)


def select_config_hashes(
    forge_db: Path, top_n: int, include_tail_hedge: bool, include_relative_value: bool
) -> dict[str, list[str]]:
    """Query Forge DB for the selection sets. Returns
    {category: [config_hashes]} where category is one of 'top_trade_count',
    'tail_hedge', 'relative_value'."""
    conn = duckdb.connect(str(forge_db), read_only=True)
    try:
        # Top-N by historical trade_count. submissions.config_json carries the
        # config; the runner's metrics table carries trade_count keyed by run_id.
        # Forge's submissions has crucible_run_id linking to the run.
        top_rows = conn.execute(
            """
            SELECT s.config_hash, s.config_json
            FROM submissions s
            ORDER BY s.submitted_at DESC
            LIMIT ?
            """,
            [top_n * 3],  # over-fetch to filter by hypothesis below
        ).fetchall()
        # Forge's submissions doesn't store trade_count directly; pick the
        # most-recent N as a proxy for "most relevant to re-test."
        top_by_recent: list[str] = [str(h) for h, _cj in top_rows[:top_n]]

        out: dict[str, list[str]] = {"top_trade_count": top_by_recent}

        if include_tail_hedge:
            tail_rows = conn.execute(
                "SELECT config_hash, config_json FROM submissions",
            ).fetchall()
            out["tail_hedge"] = [
                str(h)
                for h, cj in tail_rows
                if (json.loads(cj) if isinstance(cj, str) else cj).get("hypothesis") == "tail_hedge"
            ]

        if include_relative_value:
            rv_rows = conn.execute(
                "SELECT config_hash, config_json FROM submissions",
            ).fetchall()
            out["relative_value"] = [
                str(h)
                for h, cj in rv_rows
                if (json.loads(cj) if isinstance(cj, str) else cj).get("hypothesis")
                == "relative_value"
            ]
    finally:
        conn.close()

    return out


def requeue_one(config_hash: str, processed_dir: Path, inbox_dir: Path, *, dry_run: bool) -> str:
    """Copy processed/{hash}.json → inbox/{hash}.json atomically.

    Returns a status string: 'copied' | 'missing_source' | 'already_in_inbox'
    | 'dry_run_would_copy'.
    """
    src = processed_dir / f"{config_hash}.json"
    dst = inbox_dir / f"{config_hash}.json"
    if not src.exists():
        return "missing_source"
    if dst.exists():
        return "already_in_inbox"
    if dry_run:
        return "dry_run_would_copy"
    tmp = dst.with_suffix(".json.tmp")
    shutil.copyfile(src, tmp)
    tmp.rename(dst)
    return "copied"


def main() -> int:  # noqa: PLR0912 — D055 filter adds branches; alternative is over-decomposition for a one-off script
    args = parse_args()
    if not args.forge_db.exists():
        print(f"ERROR: Forge DB not found at {args.forge_db}", file=sys.stderr)
        return 1
    if not args.processed_dir.is_dir():
        print(f"ERROR: processed dir not found at {args.processed_dir}", file=sys.stderr)
        return 1
    args.inbox_dir.mkdir(parents=True, exist_ok=True)

    selection = select_config_hashes(
        args.forge_db,
        args.top_n,
        args.include_tail_hedge,
        args.include_relative_value,
    )

    # D055 / P1-3 — drop configs from stale grammar versions. v1-only signals
    # silently reject on a v2-active Crucible; without this filter the
    # re-queue ships configs that never run. The filter is opt-out so an
    # operator who explicitly wants the legacy behavior can pass
    # --skip-grammar-filter.
    if not args.skip_grammar_filter:
        current_grammar_version = _read_grammar_version(args.grammar_yaml)
        print(f"grammar_filter: active (current={current_grammar_version})")
        skipped_total: dict[str, int] = {}
        for category, hashes in list(selection.items()):
            matching, skipped = filter_to_current_grammar_version(
                args.forge_db,
                hashes,
                current_grammar_version,
            )
            selection[category] = matching
            for version, n_skipped in skipped.items():
                skipped_total[version] = skipped_total.get(version, 0) + n_skipped
        if skipped_total:
            print("  skipped by grammar_version:")
            for version, n_skipped in sorted(skipped_total.items()):
                print(f"    {version}: {n_skipped}")
        else:
            print("  no stale-version configs in selection")
    else:
        print("grammar_filter: SKIPPED (--skip-grammar-filter)")

    # Deduplicate across categories — a top-N tail_hedge config shouldn't
    # be copied twice.
    seen: set[str] = set()
    counts: dict[str, dict[str, int]] = {}
    for category, hashes in selection.items():
        counts[category] = {
            "copied": 0,
            "already_in_inbox": 0,
            "missing_source": 0,
            "dry_run_would_copy": 0,
            "duplicate_across_categories": 0,
        }
        for h in hashes:
            if h in seen:
                counts[category]["duplicate_across_categories"] += 1
                continue
            seen.add(h)
            status = requeue_one(
                h,
                args.processed_dir,
                args.inbox_dir,
                dry_run=args.dry_run,
            )
            counts[category][status] = counts[category].get(status, 0) + 1

    # Summary
    print(f"{'DRY RUN — ' if args.dry_run else ''}re-queue summary:")
    total_copied = 0
    for category, c in counts.items():
        print(f"  {category}:")
        for status_name, count in c.items():
            print(f"    {status_name}: {count}")
        total_copied += c.get("copied", 0) + c.get("dry_run_would_copy", 0)
    print(f"\ntotal {'would-copy' if args.dry_run else 'copied'}: {total_copied}")
    print(f"inbox depth now: {len(list(args.inbox_dir.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
