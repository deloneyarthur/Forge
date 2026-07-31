"""Tier 1 (c+d) — production statistics sliced by any grouping key.

One instrument, two jobs, because they are the same query with a different `--by`:

  --by arm       RESOLVES THE GENERATION A/B. p90 and book-usable rate per `generation_arm`,
                 concurrent within the same batches, so the drift that makes version-over-time
                 reads unusable cancels.

  --by category  TRACKS CATEGORIES ACROSS GRAMMARS. hypothesis x dte_bucket per grammar
                 version -- the operator's standing question, "are the categories improving".

WHY THOSE TWO METRICS AND NOT THE CENTRE. Promotion is a tail event, and the honest-arm centre
is a weak guide to it: spearman(cell median, cell P(>=floor)) = +0.389 against p90's +0.654.
The 1.5 gate itself is unusable as a tracking metric -- detecting a doubling of its exceedance
rate needs ~183 days per arm -- while p90 resolves a +0.05 move in ~3 days and the book-floor
rate a doubling in ~4. So the reported statistics are the ones that can actually move within a
decision horizon.

WHY hyp x bucket AND NOT hypothesis. A dispersion test over the honest arm found hypothesis
alone is NOT distinguishable from a common rate (z=+1.14) while hyp x bucket IS (z=+2.02):
trend/swing_long produces at 0.94% against trend/swing_mid's 0.28%. Tracking "trend" as one
category would average a 3.4x difference into nothing.

BASIS DISCIPLINE. Honest arm, stage one, never pooled with the refit lane -- see the module
docstring of `exhaustion_power_assessment.py` for what pooling cost us once already.

Usage: production_by_group.py SNAPSHOT.db [--by arm|category|regime] [--min-n 100]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

BOOK_FLOOR = 0.9439


def _parse(config_json: str) -> tuple[str, str, str] | None:
    """(hypothesis, dte_bucket, regime-gate tuple)."""
    try:
        cfg = json.loads(config_json)
    except (TypeError, ValueError):
        return None
    gates: list[str] = []
    signals = cfg.get("signals")
    if isinstance(signals, list):
        for sig in signals:
            if isinstance(sig, dict) and sig.get("role") == "regime_filter":
                inds = sig.get("indicators")
                if isinstance(inds, list):
                    gates.extend(str(i) for i in inds)
    return (
        str(cfg.get("hypothesis", "")),
        str(cfg.get("dte_bucket", "")),
        "+".join(sorted(gates)) or "(nogate)",
    )


def _stats(values: list[float]) -> tuple[int, float, float, float]:
    n = len(values)
    ordered = sorted(values)
    return (
        n,
        statistics.median(values),
        ordered[min(n - 1, int(0.90 * n))],
        sum(1 for v in values if v >= BOOK_FLOOR) / n,
    )


def _two_prop_z(k1: int, n1: int, k2: int, n2: int) -> float:
    if not n1 or not n2:
        return float("nan")
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (p1 - p2) / se if se else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--by", choices=("arm", "category", "regime"), default="arm")
    ap.add_argument("--min-n", type=int, default=100)
    args = ap.parse_args()

    with db_connection(Path(args.snapshot)) as conn:
        rows = conn.execute(
            """
            SELECT s.config_json,
                   s.generation_arm_tag,
                   v.grammar_version,
                   TRY_CAST(
                       json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
                   )
            FROM (
                SELECT config_json,
                       json_extract_string(config_json, '$.generation_arm') AS generation_arm_tag,
                       config_hash,
                       selection_mode
                FROM submissions
            ) s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.selection_mode = 'prefilter_sample'
              AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
            """
        ).fetchall()

    groups: dict[str, list[float]] = defaultdict(list)
    for config_json, arm_tag, version, cpcv in rows:
        if cpcv is None:
            continue
        parsed = _parse(config_json)
        if parsed is None:
            continue
        hypothesis, bucket, regime = parsed
        if args.by == "arm":
            key = arm_tag or "(unset — no A/B running)"
        elif args.by == "regime":
            key = regime
        else:
            key = f"{hypothesis}/{bucket} @ {version}"
        groups[key].append(float(cpcv))

    big = {k: v for k, v in groups.items() if len(v) >= args.min_n}
    if not big:
        largest = max((len(v) for v in groups.values()), default=0)
        print(f"no group reaches n >= {args.min_n} (largest: {largest})")
        return 0

    print(f"HONEST ARM (stage one), grouped by {args.by.upper()}, n >= {args.min_n}\n")
    print(f"{'group':<52}{'n':>7}{'median':>9}{'p90':>9}{'P(>=floor)':>12}")
    print("-" * 89)
    for key, vals in sorted(big.items(), key=lambda kv: -_stats(kv[1])[3]):
        n, med, p90, fr = _stats(vals)
        print(f"{key:<52}{n:>7}{med:>9.4f}{p90:>9.4f}{100 * fr:>11.2f}%")

    if args.by == "arm" and len(big) == 2:
        (ka, va), (kb, vb) = sorted(big.items())
        ka_k = sum(1 for v in va if v >= BOOK_FLOOR)
        kb_k = sum(1 for v in vb if v >= BOOK_FLOOR)
        z = _two_prop_z(ka_k, len(va), kb_k, len(vb))
        print(f"\nA/B READ  {ka} vs {kb}")
        print(f"  book-usable rate: z = {z:+.2f}")
        print(f"  p90: {_stats(va)[2]:.4f} vs {_stats(vb)[2]:.4f}")
        print(
            "  NOTE: concurrent arms, so this is NOT drift-confounded — unlike any "
            "version-over-version comparison of the same quantity."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
