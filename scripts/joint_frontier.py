"""The JOINT (cpcv, walk-forward) frontier — the ceiling on the axis promotion actually needs.

WHY. Every ceiling instrument Forge owns reads `cpcv_sharpe_p25` alone: both legs of freeze
condition (C), the record test, and the quality lane's training target. Promotion needs cpcv AND
`walk_forward_sharpe_median`, and stage-one pass rates say which of those binds:

    cpcv_sharpe_p25              0.00%   (11 of 198,360 ever cleared 1.5)
    walk_forward_sharpe_median   0.49%
    wf_sharpe_p25 / wf_sharpe_p10  100%   <- the NON-binding enrichment labels, easy to confuse

Of the 11 configs that ever cleared cpcv >= 1.5, SEVEN failed walk-forward; the single one that
promoted failed nothing. So "the quality ceiling is flat" has only ever been asserted about one
coordinate of a two-coordinate wall. This measures the wall.

WHAT IS MEASURED. A config is a FRONTIER ADVANCE if, when it arrived, no earlier config dominated
it — i.e. nothing before it was better on BOTH axes. The running Pareto set is the achievable
frontier; advances are the times it moved outward.

THE NULL IS A PERMUTATION, NOT A FORMULA, AND THAT MATTERS. For d=2 with INDEPENDENT coordinates
the expected advance count is ~(ln n)^2 / 2. Our coordinates are positively dependent (WF pass
rate rises with cpcv rank, 0.7% overall -> 38% in the top 100), and dependence reduces the Pareto
count on its own — so the independent formula would understate the null and manufacture a
"saturation" finding. Instead the arrival ORDER is shuffled while the point set is held fixed.
That preserves both marginals and the exact joint dependence, and isolates the only thing at
issue: whether the frontier moved outward over TIME more or less than chance.

    observed >> null  -> the frontier is still advancing; the ceiling is not reached
    observed ~= null  -> stationary: we are resampling a fixed distribution, neither
                         improving nor exhausting it
    observed <<  null  -> we peaked early and later work is dominated by earlier work

Note the middle case is NOT "we hit the ceiling". A stationary search of a bounded space that has
not yet been saturated looks exactly like this; so does one that has. Distinguishing those needs
the frontier's SHAPE over time, printed below, not the count alone.

BASIS, non-negotiable:
  * STAGE ONE only (`measurement_basis IS DISTINCT FROM 'fullhist_refit'`) — never pooled with the
    refit lane (D337/D338: stage-two admission is the refit trigger, a collider).
  * RANKED lane is the primary read, because the question is what our best effort can REACH, and
    ranked is our best effort. Its confound (the ranker improved over the window) is one-directional
    and safe here: better selection reaches a ceiling FASTER, it cannot exceed one.
  * The honest arm (`prefilter_sample`, unselected by prefilter and ranker) is reported as a
    contrast. It samples prefilter-REJECTED configs, so its frontier is expected to sit lower;
    it answers "is the underlying supply distribution shifting", not "what can we reach".
  * RNG via `SeedHierarchy` (hard rule #8), so the same snapshot reproduces the same p-value.

Usage: joint_frontier.py SNAPSHOT.db [--perms 400]
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from forge.core.seed import SeedHierarchy
from forge.persistence.db import db_connection

_QUERY = """
    SELECT TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE) cp,
           TRY_CAST(json_extract_string(v.gate_results,
                    '$.walk_forward_sharpe_median.value') AS DOUBLE) wf,
           s.submitted_at,
           json_extract_string(s.config_json,'$.grammar_version') gv,
           json_extract_string(s.config_json,'$.hypothesis') hyp,
           v.decision
    FROM submissions s JOIN verdicts v ON v.config_hash = s.config_hash
    WHERE s.selection_mode = ?
      AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
      AND TRY_CAST(json_extract_string(v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE)
          IS NOT NULL
      AND TRY_CAST(json_extract_string(v.gate_results,
                   '$.walk_forward_sharpe_median.value') AS DOUBLE) IS NOT NULL
    ORDER BY s.submitted_at
"""


def _advances(points: list[tuple[float, float]]) -> list[int]:
    """Indices of points not dominated by ANY earlier point (dominance = better on both axes).

    O(n * |frontier|). The running frontier stays small (log-sized in expectation), so this is
    fast in practice and exact — no approximation.
    """
    frontier: list[tuple[float, float]] = []
    out: list[int] = []
    for i, (x, y) in enumerate(points):
        if any(fx >= x and fy >= y for fx, fy in frontier):
            continue
        out.append(i)
        frontier = [(fx, fy) for fx, fy in frontier if not (x >= fx and y >= fy)]
        frontier.append((x, y))
    return out


def _report(label: str, rows: list[tuple], perms: int, seed: int) -> None:
    n = len(rows)
    if n < 500:
        print(f"\n=== {label} ===\n  n={n} — too thin to read")
        return
    pts = [(float(r[0]), float(r[1])) for r in rows]
    adv = _advances(pts)

    rng = SeedHierarchy(seed).rng("joint_frontier_permutation")
    null: list[int] = []
    for _ in range(perms):
        shuffled = list(pts)
        rng.shuffle(shuffled)
        null.append(len(_advances(shuffled)))
    mu, sd = statistics.fmean(null), statistics.pstdev(null)
    z = (len(adv) - mu) / sd if sd else float("nan")
    # one-sided empirical p for "more advances than chance"
    p_more = (sum(1 for v in null if v >= len(adv)) + 1) / (perms + 1)

    print(f"\n=== {label} ===")
    print(f"  n = {n:,}   window {rows[0][2]} .. {rows[-1][2]}")
    print(f"  frontier advances observed : {len(adv)}")
    print(
        f"  permutation null            : {mu:.1f} (sd {sd:.1f}, {perms} shuffles)   z = {z:+.2f}"
    )
    print(f"  P(advances >= observed | no time trend) = {p_more:.3f}")

    last = adv[-1]
    dry = 100 * (n - last - 1) / n
    print(f"  last advance : draw {last + 1:,} of {n:,}  ({dry:.1f}% dry tail)")
    q = n - n // 4
    recent = sum(1 for i in adv if i >= q)
    print(f"  advances in the most recent 25% of draws: {recent} of {len(adv)}")

    print("  the CURRENT Pareto frontier (cpcv, wf) — what we can actually reach:")
    front = sorted(((pts[i][0], pts[i][1], rows[i]) for i in adv), key=lambda t: -t[0])
    keep: list[tuple[float, float, tuple]] = []
    best_y = float("-inf")
    for x, y, r in front:
        if y > best_y:
            keep.append((x, y, r))
            best_y = y
    for x, y, r in keep[:12]:
        print(
            f"      cpcv {x:+.4f}  wf {y:+.4f}   {str(r[2])[:10]}  {r[3]:<5} "
            f"{str(r[4])[:16]:<16} {r[5]}"
        )
    if len(keep) > 12:
        print(f"      ... {len(keep) - 12} more frontier points")

    verdict = (
        "STILL ADVANCING — frontier moved outward more than chance"
        if p_more < 0.05
        else "PEAKED EARLY — later work is dominated by earlier work"
        if z < -2
        else "STATIONARY — resampling a fixed distribution; NOT the same as a proven ceiling"
    )
    print(f"  >>> {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--perms", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    with db_connection(Path(args.snapshot)) as conn:
        for lane, label in (
            ("ranked", "RANKED LANE — our best effort; what the ceiling can REACH"),
            ("prefilter_sample", "HONEST ARM — unselected supply; contrast only"),
        ):
            _report(label, conn.execute(_QUERY, [lane]).fetchall(), args.perms, args.seed)
    print(
        "\nREAD WITH THE VERDICT: 'stationary' is not 'ceiling reached'. A bounded space that\n"
        "is nowhere near saturated looks identical to one that is. Use the frontier SHAPE above —\n"
        "whether recent points extend it or merely re-find it — and remember cpcv alone has been\n"
        "setting records (ceiling_record_test.py) while this joint frontier is the binding surface."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
