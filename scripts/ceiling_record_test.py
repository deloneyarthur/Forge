"""Have we HIT the grammar's ceiling, or merely stopped measuring movement?

"The ceiling is flat" and "we have reached the ceiling" are different claims and the freeze
criterion only tests the first. Condition (C) asks whether a composition-standardised top-decile
statistic has stopped RISING over a ~2-week window. A bounded distribution and an unbounded one
that happens to be quiet both produce that reading. This script tests the second claim directly.

THE TEST — record progression, the classical extreme-value signature.

In n i.i.d. draws from ANY continuous distribution, the number of running-maximum RECORDS is
distributed with mean the harmonic number H_n ~= ln(n) + 0.5772, INDEPENDENT of the distribution.
That distribution-free property is what makes it usable here: we do not need to know the shape of
the cpcv distribution, only whether records are still arriving at the rate an unbounded search
would produce.

  records ~= H_n   -> consistent with a search still finding new territory
  records <<  H_n   -> the maximum has saturated: draws are piling up under a bound we have reached
  records >>  H_n   -> the distribution is IMPROVING over time (grammar changes are working)

The third case matters as much as the second: our draws are NOT i.i.d. across the window because
the grammar changed underneath them. That makes the test CONSERVATIVE in a useful direction — if
our prunes had been lifting the achievable maximum, we would expect an EXCESS of records, not a
deficit. A deficit therefore cannot be explained away by version churn.

WHAT A DEFICIT WOULD AND WOULD NOT LICENCE. It would say the reachable maximum on the CURRENTLY
SAMPLED surface has saturated. It would NOT say the grammar is exhausted, because the sampled
surface is not the representable surface: the 2026-08-06 indicator audit found 19 of 72 registered
indicators dark and the largest single trend cell (rv_rank-primaried, 77,416 configs) unable to
carry a second regime gate at all. A saturated search over a surface with known holes is evidence
about the search, not about the grammar.

BASIS, non-negotiable and the same as every other decision statistic here:
  * HONEST ARM only (`selection_mode='prefilter_sample'`) for the primary read — the population
    unselected by both the prefilter and the ranker. The ranked lane is selected by a ranker that
    itself improved over the window, which would manufacture records.
  * STAGE ONE only (`measurement_basis IS DISTINCT FROM 'fullhist_refit'`) — never pooled with the
    refit lane (D337/D338: stage-two admission is the refit trigger, a collider).
  * The ranked lane is reported SEPARATELY as a contrast, never merged.

Usage: ceiling_record_test.py SNAPSHOT.db
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from forge.persistence.db import db_connection

_EULER = 0.5772156649

_QUERY = """
    SELECT TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE) cp,
           s.submitted_at
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    WHERE s.selection_mode = ?
      AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
      AND TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE)
          IS NOT NULL
    ORDER BY s.submitted_at
"""


def _harmonic(n: int) -> float:
    """H_n, the expected record count in n i.i.d. draws. Exact for small n, asymptotic beyond."""
    if n <= 0:
        return 0.0
    if n < 10_000:
        return sum(1.0 / k for k in range(1, n + 1))
    return math.log(n) + _EULER + 1.0 / (2 * n)


def _records(values: list[float]) -> list[tuple[int, float]]:
    """(index, value) of every running maximum."""
    out: list[tuple[int, float]] = []
    best = float("-inf")
    for i, v in enumerate(values, start=1):
        if v > best:
            best = v
            out.append((i, v))
    return out


def _report(label: str, values: list[float], stamps: list[object]) -> None:
    n = len(values)
    if n < 200:
        print(f"\n{label}: n={n} — too thin to read")
        return
    recs = _records(values)
    expected = _harmonic(n)
    # Var(records) = H_n - H_n^(2); the second-order harmonic. sd ~ sqrt(ln n) for large n.
    var = expected - sum(1.0 / (k * k) for k in range(1, min(n, 100_000) + 1))
    sd = math.sqrt(max(var, 1e-9))
    z = (len(recs) - expected) / sd

    print(f"\n=== {label} ===")
    print(f"  n = {n:,}   window {stamps[0]} .. {stamps[-1]}")
    print(f"  records observed : {len(recs)}")
    print(f"  expected (i.i.d.): {expected:.2f}  (sd {sd:.2f})   z = {z:+.2f}")
    last_idx, last_val = recs[-1]
    print(f"  last record      : draw {last_idx:,} of {n:,} (value {last_val:+.4f})")
    print(f"  draws since      : {n - last_idx:,}  ({100 * (n - last_idx) / n:.1f}% of the sample)")

    # Under the null the last record's position is ~Uniform on the sample in log-space:
    # P(no record in the final f fraction) = 1 - f, so a long dry tail is itself the signal.
    frac_dry = (n - last_idx) / n
    print(f"  P(dry tail this long | no ceiling) = {1 - frac_dry:.3f}")

    print("  record progression (draw -> value):")
    shown = recs if len(recs) <= 14 else recs[:7] + recs[-7:]
    for i, (idx, val) in enumerate(shown):
        if len(recs) > 14 and i == 7:
            print(f"      ... {len(recs) - 14} more ...")
        print(f"      {idx:>8,}  {val:+.4f}")

    verdict = (
        "SATURATED — records well below the i.i.d. rate"
        if z < -2
        else "IMPROVING — records above the i.i.d. rate"
        if z > 2
        else "CONSISTENT WITH AN UNBOUNDED SEARCH — cannot claim a ceiling"
    )
    print(f"  >>> {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    args = ap.parse_args()
    with db_connection(Path(args.snapshot)) as conn:
        for lane, label in (
            ("prefilter_sample", "HONEST ARM (unselected) — the primary read"),
            ("ranked", "RANKED LANE (selected by our own ranker) — contrast only"),
        ):
            rows = conn.execute(_QUERY, [lane]).fetchall()
            _report(label, [float(r[0]) for r in rows], [r[1] for r in rows])
    print(
        "\nNOTE: a deficit would show the SAMPLED surface has saturated, not that the grammar is\n"
        "exhausted — 19 of 72 indicators are dark and the largest trend cell cannot carry a\n"
        "second gate. Saturation of a search with known holes is evidence about the search."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
