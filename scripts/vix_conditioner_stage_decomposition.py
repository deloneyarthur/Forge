"""Where do the vix-conditioner configs go? A stage-by-stage decomposition.

The D317/v44 conditioner (`vix_term_slope` ANDed onto a hurst primary on the xsect trend arm)
is specified at `_VIX_CONDITIONER_SHARE = 0.125` of its eligible pool but SUBMITS at
0.0014-0.084 depending on grammar version (D339). Submitted configs cannot say whether the
loss is at the sampler, the prefilter, or the ranker -- but three of our selection arms are
random draws from different stages, so together they pin it without running the battery:

  prefilter_sample  uniform random from prefilter-REJECTED configs (D335)   -> share among rejects
  holdout           seeded random from survivors the ranker did NOT pick    -> share among survivors
  ranked/tail_lane  the ranker's picks                                      -> share post-ranker

Reading the three:
  * rejects >> survivors            -> the PREFILTER is eating the cell (which one, from the
                                       per-hypothesis rejection tallies)
  * survivors ~ 0.125 but ranked << -> the RANKER de-selects it (the D287/momentum_252 pattern)
  * all three low                   -> the SAMPLER is not emitting at spec

Both eligibility and firing are read off the emitted config, so the classification matches
`_vix_conditioner_eligible` post-hoc: eligible = xsect trend, non-capitulation directional,
hurst primary, at most one further gate; fired = that further gate is vix_term_slope.

Usage: vix_conditioner_stage_decomposition.py SNAPSHOT.db [MIN_GRAMMAR_VERSION]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

_VIX = "vix_term_slope"
_PRIMARY_GATES = ("hurst",)  # v45/D319 narrowed the conditioner to a hurst primary
_CAPITULATION = "momentum"
_ARMS = ("prefilter_sample", "holdout", "ranked", "tail_lane", "trend_lane")


def _classify(cfg: dict[str, object]) -> tuple[bool, bool]:
    """(eligible_for_conditioner, conditioner_fired)."""
    if cfg.get("hypothesis") != "trend_continuation":
        return False, False
    combiner = cfg.get("combiner")
    if not isinstance(combiner, dict) or combiner.get("type") != "cross_sectional_rank":
        return False, False
    directional = ""
    gates: list[str] = []
    signals = cfg.get("signals")
    if not isinstance(signals, list):
        return False, False
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
    if directional == _CAPITULATION:
        return False, False
    if gates[:1] not in ([g] for g in _PRIMARY_GATES):
        return False, False
    if len(gates) > 2:
        return False, False
    return True, len(gates) == 2 and gates[1] == _VIX


def main() -> int:
    snap = Path(sys.argv[1])
    min_version = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    with db_connection(snap) as conn:
        rows = conn.execute(
            """
            SELECT s.selection_mode, v.grammar_version, s.config_json
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.selection_mode IS NOT NULL
            """
        ).fetchall()

    # arm -> [eligible, fired]
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for arm, version, cfg_json in rows:
        digits = "".join(c for c in str(version) if c.isdigit())
        if not digits or int(digits) < min_version:
            continue
        if arm not in _ARMS:
            continue
        try:
            cfg = json.loads(cfg_json)
        except (TypeError, json.JSONDecodeError):
            continue
        eligible, fired = _classify(cfg)
        if not eligible:
            continue
        cell = tally[arm]
        cell[0] += 1
        cell[1] += fired

    label = {
        "prefilter_sample": "prefilter REJECTS (random)",
        "holdout": "prefilter SURVIVORS (random)",
        "ranked": "ranker picks (merit lane)",
        "tail_lane": "ranker picks (MR tail lane)",
        "trend_lane": "ranker picks (trend lane)",
    }
    print(f"grammar >= v{min_version}    spec = 0.125 of the eligible pool\n")
    print(f"{'arm':<18} {'stage':<28} {'eligible':>9} {'fired':>6} {'share':>8} {'vs spec':>9}")
    print("-" * 84)
    for arm in _ARMS:
        eligible, fired = tally.get(arm, [0, 0])
        if not eligible:
            continue
        share = fired / eligible
        vs = f"{0.125 / share:.1f}x under" if share else "ZERO"
        print(f"{arm:<18} {label[arm]:<28} {eligible:>9} {fired:>6} {share:>8.4f} {vs:>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
