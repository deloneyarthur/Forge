"""Publish `forge_generation_by_version` for the joint freeze programme (D331 item 4).

Charter §4 commitment: Crucible observes ONLY post-ranker submissions. Our enumeration
mix, prefilter survival and ranker are structurally invisible to them, so any divergence
between what we generate and what they receive can be decomposed only from our side. That
asymmetry produced a real misdiagnosis on 2026-07-22 — they asked us to boost
`momentum_252` emission on the evidence that 0.62% of trend-xsect arrived, when
enumeration was supplying it at 28% and the loss was entirely at our ranker.

The pair that makes the selection layer auditable by them is **ranked vs holdout**: the
5% exploration holdout (D256) is an unbiased sample of post-prefilter supply drawn from
survivors the ranker did NOT pick, so `holdout_share - ranked_share` IS our selection
effect per cell, with no model and no assumption. It is the number that would have
short-circuited the momentum_252 round-trip.

Emits machine-readable JSON per freeze-repo rule 2 (prose tables in relays cannot be
reproduced without retyping, which is how a wrong number survives).

Usage:
    python scripts/export_generation_by_version.py --db <snapshot> [--out <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

_XSECT = "cross_sectional_rank"
_POSITIVE = frozenset({"component", "promote"})

# Only these are meaningful selection arms. `None` predates D256 (2026-07-07); mixing it
# in would silently pool a pre-holdout era with a post-holdout one — the basis error the
# programme keeps re-learning.
_ARMS = ("ranked", "holdout")


def _cell_key(config: dict[str, Any]) -> str:
    combiner = config.get("combiner") or {}
    axis = "xsect" if combiner.get("type") == _XSECT else "named"
    directional = next(
        (s["indicators"][0] for s in config.get("signals", []) if s.get("role") == "directional"),
        None,
    )
    return f"{config.get('hypothesis')}|{config.get('dte_bucket')}|{axis}|{directional}"


def _honest(gate_results: str | None) -> bool:
    """D128 honesty on the stored payload (see census `_honest_coverage`)."""
    if not gate_results:
        return False
    row = (json.loads(gate_results) or {}).get("regime_coverage")
    if row is None:
        return False
    return bool(row.get("passed")) and "coverage_unverified" not in (row.get("detail") or "")


def _shares(counts: Counter[str]) -> dict[str, dict[str, float]]:
    total = sum(counts.values())
    return {
        k: {"n": v, "share_pct": round(100 * v / total, 3) if total else 0.0}
        for k, v in counts.most_common()
    }


def build(db: duckdb.DuckDBPyConnection, grammar_version: str) -> dict[str, Any]:
    # --- enumeration + prefilter: batch_summaries is the only record of what was
    # enumerated; per-CELL enumeration counts are not stored (they would require
    # re-running enumeration), so this block is hypothesis-level by construction.
    enum_by_hyp: Counter[str] = Counter()
    rej_by_reason: Counter[str] = Counter()
    enumerated = survived = batches = 0
    for enum_c, surv_c, rej, by_hyp in db.execute(
        """SELECT enumerated_count, survived_count, prefilter_rejections,
                  enumerated_by_hypothesis
           FROM batch_summaries WHERE grammar_version = ?""",
        [grammar_version],
    ).fetchall():
        batches += 1
        enumerated += int(enum_c or 0)
        survived += int(surv_c or 0)
        for k, v in (json.loads(rej) if rej else {}).items():
            rej_by_reason[k] += int(v)
        for k, v in (json.loads(by_hyp) if by_hyp else {}).items():
            enum_by_hyp[k] += int(v)

    # --- ranked vs holdout, per cell: the selection-loss signal
    arms: dict[str, Counter[str]] = {a: Counter() for a in _ARMS}
    for cfg_json, mode in db.execute(
        """SELECT config_json, selection_mode FROM submissions
           WHERE json_extract_string(config_json, '$.grammar_version') = ?
             AND selection_mode IN ('ranked', 'holdout')""",
        [grammar_version],
    ).fetchall():
        arms[mode][_cell_key(json.loads(cfg_json))] += 1

    ranked_sh = _shares(arms["ranked"])
    holdout_sh = _shares(arms["holdout"])
    selection_loss = {
        cell: {
            "holdout_share_pct": holdout_sh.get(cell, {}).get("share_pct", 0.0),
            "ranked_share_pct": ranked_sh.get(cell, {}).get("share_pct", 0.0),
            "delta_pp": round(
                ranked_sh.get(cell, {}).get("share_pct", 0.0)
                - holdout_sh.get(cell, {}).get("share_pct", 0.0),
                3,
            ),
        }
        for cell in set(ranked_sh) | set(holdout_sh)
    }

    # --- F3 label block, with its basis stated (charter §4 makes this mandatory)
    n = pos = honest_pos = 0
    for decision, gate_results in db.execute(
        """SELECT v.decision, v.gate_results FROM verdicts v
           JOIN submissions s ON v.config_hash = s.config_hash
           WHERE v.grammar_version = ?""",
        [grammar_version],
    ).fetchall():
        n += 1
        if decision in _POSITIVE:
            pos += 1
            if _honest(gate_results):
                honest_pos += 1

    return {
        "artifact": "forge_generation_by_version",
        "schema_version": "1.0",
        "grammar_version": grammar_version,
        "enumeration": {
            "note": (
                "Hypothesis-level only: per-CELL enumeration counts are not persisted "
                "(they would require re-running enumeration). The cell-level selection "
                "signal lives in `ranked`/`holdout`/`selection_loss` below."
            ),
            "by_hypothesis": _shares(enum_by_hyp),
        },
        "prefilter": {
            "batches": batches,
            "total_enumerated": enumerated,
            "passed": survived,
            "survival_pct": round(100 * survived / enumerated, 3) if enumerated else None,
            "rejections_by_reason": dict(rej_by_reason.most_common()),
        },
        "ranked": ranked_sh,
        "holdout": holdout_sh,
        "selection_loss": {
            "note": (
                "delta_pp = ranked_share - holdout_share, the per-cell selection "
                "effect - measured, not modelled. "
                "READ THE SIGN, NOT THE MAGNITUDE. Two reasons the magnitude overstates: "
                "(1) the holdout is drawn from survivors the ranker did NOT pick (D256), "
                "so the residual pool is DEPLETED of cells the ranker likes and ENRICHED "
                "in ones it avoids - this inflates |delta| in both directions, and the "
                "inflation is concentrated in exactly the cells with the largest deltas; "
                "(2) the holdout is 5% of a batch, so per-cell n is small. "
                "A pool-relative correction is (n_unselected / n_pool) ~ 0.90 in "
                "aggregate, but per-cell it is not a constant and we do not apply it here."
            ),
            "by_cell": selection_loss,
        },
        "f3_label": {
            "basis": "standard_window+fullhist_refit (MIXED - see note)",
            "note": (
                "Forge's D128 label is computed over BOTH Crucible lanes. The "
                "`standard_window` screen structurally cannot produce an honest-coverage "
                "component (~0.077% honest), so the label is DILUTED by a lane that "
                "cannot supply it. Re-scoping is measured but not shipped (D331 Part B) - "
                "this flag stays MIXED until it is, and any consumer should treat the "
                "prevalence below as contaminated."
            ),
            "n": n,
            "positives": pos,
            "honest_positives": honest_pos,
            "prevalence_pct": round(100 * honest_pos / n, 4) if n else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db", required=True, type=Path, help="forge.db SNAPSHOT (never the live file)"
    )
    ap.add_argument(
        "--versions", nargs="*", help="grammar versions (default: all with submissions)"
    )
    ap.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    args = ap.parse_args(argv)

    con = duckdb.connect(str(args.db), read_only=True)
    versions = args.versions or [
        r[0]
        for r in con.execute(
            """SELECT DISTINCT json_extract_string(config_json, '$.grammar_version') gv
               FROM submissions WHERE gv IS NOT NULL ORDER BY gv"""
        ).fetchall()
    ]
    payload = {v: build(con, v) for v in versions}
    text = json.dumps(payload, indent=1)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out} ({len(versions)} versions)", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
