"""Split resid x vix emission into the TWO constructs Crucible's Q57 query conflates.

Crucible measured "the resid_vix conditioner" as `vix_term_slope` in a `regime_filter` role
co-occurring with a `residual_momentum` directional, and asked us to confirm the mapping
before either side acts on it (relay 9357b7d §2). That predicate is a SUPERSET of two
distinct things Forge emits, governed by different constants:

  A. VIX-AS-PRIMARY -- `vix_term_slope` drawn as residual_momentum's PRIMARY regime gate.
     Governed by the D276 (v33) uniform coin over the two-member pool
     {vix_term_slope, hurst}, so its natural share is ~0.5, NOT 0.125. Pre-dates the pilot.

  B. VIX-AS-CONDITIONER -- the D317 (v44) Q46 pilot: `vix_term_slope` ANDed on as an
     OPTIONAL SECOND gate, on top of a trend-STRENGTH primary (hurst only since v45/D319),
     xsect trend arm only, MR excluded. This is what `_VIX_CONDITIONER_SHARE = 0.125`
     governs, and it shares its slot with the regime VETO (drawn first, mutually exclusive),
     so 0.125 is CONDITIONAL on the veto not being drawn -- an unconditional share of
     0.125 was never the specification.

Their single predicate counts A + B together, against a denominator of ALL residual_momentum
configs rather than the eligible xsect x hurst-primary pool B is drawn from. If the ~0.44
readings coincide with the D276 coin being live and the ~0.045 readings with it being
restricted, the version instability they flag as "something version-scoped on your side" is
construct A moving, not the pilot constant miscalibrating.

Usage: resid_vix_construct_split.py SNAPSHOT.db
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from forge.persistence.db import db_connection

_RESID = "residual_momentum"
_VIX = "vix_term_slope"
_TREND_STRENGTH = ("hurst", "adx")


def _roles(config: dict[str, object]) -> tuple[str, list[str], bool]:
    """(directional id, regime-gate ids in draw order, is_xsect)."""
    directional = ""
    gates: list[str] = []
    signals = config.get("signals")
    if not isinstance(signals, list):
        return directional, gates, False
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        role = sig.get("role")
        inds = sig.get("indicators")
        if not isinstance(inds, list) or not inds:
            continue
        # Signal list order is DRAW order, so the first regime_filter is the primary gate
        # and any later one is the optional second gate (conditioner or veto).
        if role == "directional":
            directional = str(inds[0])
        elif role == "regime_filter":
            gates.extend(str(i) for i in inds)
    combiner = config.get("combiner")
    ctype = combiner.get("type", "") if isinstance(combiner, dict) else ""
    is_xsect = "rank" in str(ctype).lower()
    return directional, gates, is_xsect


def main() -> int:
    snap = Path(sys.argv[1])
    with db_connection(snap) as conn:
        rows = conn.execute(
            """
            SELECT v.grammar_version, s.config_json
            FROM submissions s
            JOIN verdicts v ON v.config_hash = s.config_hash
            WHERE s.config_json LIKE '%residual_momentum%'
            """
        ).fetchall()

    # per version: [n_resid, n_their_predicate, n_A_primary, n_B_conditioner, n_eligible_B]
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for version, cfg_json in rows:
        try:
            cfg = json.loads(cfg_json)
        except (TypeError, json.JSONDecodeError):
            continue
        directional, gates, is_xsect = _roles(cfg)
        if directional != _RESID:
            continue
        cell = tally[str(version)]
        cell[0] += 1
        if _VIX not in gates:
            # Eligibility for construct B: a trend-strength primary is present but the
            # optional second gate did not land on vix (it may have gone to a veto).
            if gates and gates[0] in _TREND_STRENGTH and is_xsect:
                cell[4] += 1
            continue
        cell[1] += 1
        if gates[0] == _VIX:
            cell[2] += 1  # A: vix is the primary
        elif gates[0] in _TREND_STRENGTH:
            cell[3] += 1  # B: trend-strength primary, vix ANDed on as the conditioner
            if is_xsect:
                cell[4] += 1

    def _vkey(v: str) -> int:
        digits = "".join(c for c in v if c.isdigit())
        return int(digits) if digits else -1

    print(
        f"{'grammar':<9} {'n_resid':>8} {'their':>7} {'their%':>8} "
        f"{'A_prim':>7} {'A%':>7} {'B_cond':>7} {'B_elig':>7} {'B%_of_elig':>11}"
    )
    print("-" * 82)
    tot = [0] * 5
    for version in sorted(tally, key=_vkey):
        n_resid, their, a, b, elig = tally[version]
        for i, x in enumerate((n_resid, their, a, b, elig)):
            tot[i] += x
        print(
            f"{version:<9} {n_resid:>8} {their:>7} {their / max(n_resid, 1):>8.4f} "
            f"{a:>7} {a / max(n_resid, 1):>7.4f} {b:>7} {elig:>7} "
            f"{b / max(elig, 1):>11.4f}"
        )
    n_resid, their, a, b, elig = tot
    print("-" * 82)
    print(
        f"{'TOTAL':<9} {n_resid:>8} {their:>7} {their / max(n_resid, 1):>8.4f} "
        f"{a:>7} {a / max(n_resid, 1):>7.4f} {b:>7} {elig:>7} {b / max(elig, 1):>11.4f}"
    )
    print(
        "\ntheir% = Crucible's Q57 predicate (vix in ANY regime_filter role x resid "
        "directional)\nA% = vix drawn as the PRIMARY regime gate (D276 coin, ~0.5 natural)"
        "\nB%_of_elig = the D317/D319 CONDITIONER against its own eligible pool "
        "(_VIX_CONDITIONER_SHARE = 0.125, itself conditional on the veto not drawing)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
