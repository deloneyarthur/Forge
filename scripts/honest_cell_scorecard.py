"""Tier 0 — which cells actually PRODUCE, measured on the honest arm.

Two jobs, both prerequisites for the Tier-1 draw-weight A/B:

  1. RANK cells by what we care about. Cell centre is a weak guide to book-usable production
     (spearman(median, P(>=floor)) = +0.389 on 2026-07-31), while p90 is a much better one
     (+0.654). So the scorecard reports both and ranks on production, not on centre.

  2. PRICE A PRUNE without a second arm. For a TIGHTENING the post-prune grammar is a strict
     SUBSET of the current one, so its honest distribution is exactly this arm with the pruned
     cells removed. `--exclude` post-stratifies and reprints the aggregate, which answers "what
     would p90 have been without cell X" from data we already hold. Concurrent arms are only
     needed for LOOSENINGS, where the candidate produces configs the current grammar cannot.

BASIS DISCIPLINE. Stage one only (`measurement_basis != 'fullhist_refit'`). Stage two is the
refit lane, which only ADMITTED configs enter — a collider (D337/D338) — and pooling the two
mixes bases, which is how a 2026-07-31 read reported 2 gate-clearers where each stage holds 1.

Usage:
  honest_cell_scorecard.py SNAPSHOT.db [--min-n 40] [--exclude 'hypothesis/dte/dir/regime' ...]
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

BOOK_FLOOR = 0.9439
PROMOTION_GATE = 1.5


def _cell_key(cfg: dict[str, object]) -> tuple[str, str, str, str]:
    directional = ""
    gates: list[str] = []
    signals = cfg.get("signals")
    if isinstance(signals, list):
        for sig in signals:
            if not isinstance(sig, dict):
                continue
            inds = sig.get("indicators")
            if not isinstance(inds, list) or not inds:
                continue
            if sig.get("role") == "directional":
                directional = str(inds[0])
            elif sig.get("role") == "regime_filter":
                gates.extend(str(i) for i in inds)
    return (
        str(cfg.get("hypothesis", "")),
        str(cfg.get("dte_bucket", "")),
        directional,
        "+".join(sorted(gates)) or "(nogate)",
    )


def _summary(values: list[float]) -> tuple[int, float, float, float, float]:
    n = len(values)
    ordered = sorted(values)
    p90 = ordered[min(n - 1, int(0.90 * n))]
    floor_rate = sum(1 for v in values if v >= BOOK_FLOOR) / n
    gate_rate = sum(1 for v in values if v >= PROMOTION_GATE) / n
    return n, statistics.median(values), p90, floor_rate, gate_rate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--min-n", type=int, default=40)
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args()

    with db_connection(Path(args.snapshot)) as conn:
        rows = conn.execute(
            """
            SELECT s.config_json,
                   TRY_CAST(
                       json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
                   )
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.selection_mode = 'prefilter_sample'
              AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
            """
        ).fetchall()

    cells: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for cfg_json, cpcv in rows:
        if cpcv is None:
            continue
        try:
            cfg = json.loads(cfg_json)
        except (TypeError, json.JSONDecodeError):
            continue
        cells[_cell_key(cfg)].append(float(cpcv))

    excluded = set(args.exclude)
    kept = {k: v for k, v in cells.items() if "/".join(k) not in excluded}
    if excluded:
        dropped = {k: v for k, v in cells.items() if "/".join(k) in excluded}
        print(f"EXCLUDED {len(dropped)} cell(s), {sum(len(v) for v in dropped.values())} configs")

    everything = [v for vals in kept.values() for v in vals]
    if not everything:
        print("no rows")
        return 1
    n, med, p90, fr, gr = _summary(everything)
    print(f"\nHONEST ARM (stage one) AGGREGATE{'  [post-exclusion]' if excluded else ''}")
    print(
        f"  n={n:,}  median={med:.4f}  p90={p90:.4f}  "
        f"P(>={BOOK_FLOOR})={100 * fr:.3f}%  P(>={PROMOTION_GATE})={100 * gr:.4f}%"
    )

    big = {k: v for k, v in kept.items() if len(v) >= args.min_n}
    print(f"\nCELLS with n >= {args.min_n}: {len(big)} of {len(kept)}")
    # Labels are NOT truncated: several cells differ only in their regime tuple, and a
    # truncated label silently merges them into what looks like one repeated row.
    print(f"\n{'cell':<74}{'n':>6}{'median':>9}{'p90':>9}{'P(>=floor)':>12}{'P(>=1.5)':>10}")
    print("-" * 120)
    ranked = sorted(big.items(), key=lambda kv: -_summary(kv[1])[3])
    for key, vals in ranked:
        cn, cmed, cp90, cfr, cgr = _summary(vals)
        hyp = key[0][:5]
        label = f"{hyp}/{key[1]}/{key[2]}/{key[3]}"
        print(f"{label:<74}{cn:>6}{cmed:>9.4f}{cp90:>9.4f}{100 * cfr:>11.2f}%{100 * cgr:>9.3f}%")

    producers = [k for k, v in big.items() if _summary(v)[3] > 0]
    zero = [k for k, v in big.items() if _summary(v)[3] == 0]
    print(
        f"\nPRODUCERS (P(>=floor) > 0): {len(producers)} cells | "
        f"ZERO-PRODUCTION: {len(zero)} cells, {sum(len(big[k]) for k in zero):,} configs"
    )
    print("Zero-production cells are the Tier-1 re-weight-AWAY candidates:")
    for k in sorted(zero, key=lambda k: -len(big[k]))[:8]:
        print(f"  {'/'.join(k):<70} n={len(big[k])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
