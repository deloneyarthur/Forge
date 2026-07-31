"""Prereg `4d1fa832789f` quality leg: the trend arm vs the merit arm, TREND-RESTRICTED.

The registered comparison restricts BOTH arms to `trend_continuation` rows. Comparing the
trend lane's rate against the merit arm's all-hypothesis rate would be the "wrong population"
error class -- and would repeat the D339 defect, which was itself a population error.

Prediction: trend_lane strong-component rate >= 1.25x the concurrent merit arm's
trend-restricted rate, over a majority of batches with >=20 decided in both arms.

Usage: trend_lane_arm_read.py SNAPSHOT.db SINCE_ISO
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

BOOK_FLOOR = 0.9439
MIN_DECIDED_PER_ARM = 20


def main() -> int:
    snap, since = Path(sys.argv[1]), sys.argv[2]
    with db_connection(snap) as conn:
        rows = conn.execute(
            """
            SELECT CAST(s.forge_batch_id AS VARCHAR),
                   s.selection_mode,
                   v.decision,
                   TRY_CAST(
                       json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
                   )
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.submitted_at >= CAST(? AS TIMESTAMP)
              AND s.selection_mode IN ('trend_lane', 'ranked')
              AND json_extract_string(s.config_json, '$.hypothesis') = 'trend_continuation'
            """,
            [since],
        ).fetchall()

    agg: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for batch_id, arm, decision, cpcv in rows:
        cell = agg[(batch_id, arm)]
        cell[0] += 1
        if decision == "component":
            cell[1] += 1
            if cpcv is not None and cpcv >= BOOK_FLOOR:
                cell[2] += 1

    batches = sorted({b for b, _ in agg})
    pooled = [0] * 6
    ratios: list[float] = []
    wins = usable = 0
    for b in batches:
        t = agg.get((b, "trend_lane"), [0, 0, 0])
        m = agg.get((b, "ranked"), [0, 0, 0])
        for i in range(3):
            pooled[i] += t[i]
            pooled[3 + i] += m[i]
        if t[0] < MIN_DECIDED_PER_ARM or m[0] < MIN_DECIDED_PER_ARM:
            continue
        usable += 1
        t_rate, m_rate = t[2] / t[0], m[2] / m[0]
        if m_rate == 0:
            if t_rate > 0:
                wins += 1
                ratios.append(float("inf"))
            continue
        ratios.append(t_rate / m_rate)
        if t_rate / m_rate >= 1.25:
            wins += 1

    t_dec, t_comp, t_str, m_dec, m_comp, m_str = pooled
    print(f"TREND-RESTRICTED, both arms, since {since}   ({len(batches)} batches)\n")
    print(f"{'arm':<12} {'decided':>8} {'comps':>7} {'comp%':>8} {'strong':>7} {'strong%':>9}")
    print("-" * 56)
    for name, dec, comp, strong in (
        ("trend_lane", t_dec, t_comp, t_str),
        ("merit", m_dec, m_comp, m_str),
    ):
        print(
            f"{name:<12} {dec:>8} {comp:>7} {100 * comp / max(dec, 1):>7.1f}% "
            f"{strong:>7} {100 * strong / max(dec, 1):>8.3f}%"
        )
    t_rate, m_rate = t_str / max(t_dec, 1), m_str / max(m_dec, 1)
    print(f"\nPOOLED ratio: {t_rate / max(m_rate, 1e-12):.2f}x   (prereg bar: >= 1.25x)")
    finite = [r for r in ratios if r != float("inf")]
    med = statistics.median(finite) if finite else float("nan")
    print(
        f"PER-BATCH (the registered criterion): >=1.25x in {wins}/{usable} "
        f"batches with >={MIN_DECIDED_PER_ARM} decided in both arms; median ratio {med:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
