"""Is the vix conditioner bad, or is ANY second regime gate bad? The controlled contrast.

D339 found that `vix_term_slope` ANDed onto a hurst primary (xsect trend) converts far below
its eligible pool. The natural worry is that double-gating is generically harmful -- which
would matter far more than the conditioner itself, because the regime VETO shares the same
optional slot at `_REGIME_VETO_SHARE = 0.5`, four times the conditioner's 0.125.

The contrast is clean because all three arms share the SAME base (xsect trend, hurst primary,
non-capitulation directional) and differ only in what occupies the optional second slot:

    hurst alone            -- the slot went unused
    hurst + <veto>         -- the veto won the slot
    hurst + vix_term_slope -- the conditioner won the slot

Measured on the two ranker-unbiased arms only (`holdout` = random from prefilter survivors,
`prefilter_sample` = random from prefilter rejects), so the learned ranker's own preference
cannot manufacture the difference.

Usage: second_gate_contrast.py SNAPSHOT.db [MIN_GRAMMAR_VERSION]
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

BOOK_FLOOR = 0.9439
_BASELINE = "hurst ALONE (slot unused)"
_MIN_CELL = 15


def _gate_structure(cfg: dict[str, object]) -> str | None:
    """The second-slot occupant, or None if the config is outside the contrast base."""
    combiner = cfg.get("combiner")
    if not isinstance(combiner, dict) or combiner.get("type") != "cross_sectional_rank":
        return None
    directional = ""
    gates: list[str] = []
    signals = cfg.get("signals")
    if not isinstance(signals, list):
        return None
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
    if directional == "momentum":  # capitulation is excluded from conditioner eligibility
        return None
    if gates[:1] != ["hurst"] or len(gates) > 2:
        return None
    return _BASELINE if len(gates) == 1 else f"hurst + {gates[1]}"


def main() -> int:
    snap = Path(sys.argv[1])
    min_version = int(sys.argv[2]) if len(sys.argv) > 2 else 49

    with db_connection(snap) as conn:
        rows = conn.execute(
            """
            SELECT v.grammar_version, s.config_json, v.decision,
                   TRY_CAST(
                       json_extract_string(v.gate_results, '$.cpcv_sharpe_p25.value') AS DOUBLE
                   )
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.selection_mode IN ('holdout', 'prefilter_sample')
              AND json_extract_string(s.config_json, '$.hypothesis') = 'trend_continuation'
            """
        ).fetchall()

    tally: dict[str, list[float]] = defaultdict(lambda: [0, 0, 0, 0.0])
    for version, cfg_json, decision, cpcv in rows:
        digits = "".join(c for c in str(version) if c.isdigit())
        if not digits or int(digits) < min_version:
            continue
        try:
            cfg = json.loads(cfg_json)
        except (TypeError, json.JSONDecodeError):
            continue
        key = _gate_structure(cfg)
        if key is None:
            continue
        cell = tally[key]
        cell[0] += 1
        if decision == "component":
            cell[1] += 1
            if cpcv is not None and cpcv >= BOOK_FLOOR:
                cell[2] += 1
        if cpcv is not None:
            cell[3] += cpcv

    base = tally.get(_BASELINE)
    if not base or not base[0]:
        print("no baseline rows — nothing to contrast")
        return 1
    base_p = base[1] / base[0]

    print(f"UNBIASED ARMS ONLY, xsect TREND, hurst PRIMARY, grammar >= v{min_version}\n")
    header = f"{'second-slot occupant':<34}{'n':>6}{'comp':>6}{'comp%':>8}"
    print(header + f"{'strong':>7}{'mean_cpcv':>11}{'z vs baseline':>14}")
    print("-" * 86)
    for key in sorted(tally, key=lambda k: (k != _BASELINE, -tally[k][0])):
        n, comp, strong, cpcv_sum = tally[key]
        if n < _MIN_CELL:
            continue
        p = comp / n
        if key == _BASELINE:
            z_str = "(baseline)"
        else:
            pooled = (comp + base[1]) / (n + base[0])
            se = math.sqrt(pooled * (1 - pooled) * (1 / n + 1 / base[0]))
            z_str = f"{(p - base_p) / se:+.2f}"
        print(
            f"{key:<34}{int(n):>6}{int(comp):>6}{100 * p:>7.1f}%"
            f"{int(strong):>7}{cpcv_sum / n:>11.4f}{z_str:>14}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
