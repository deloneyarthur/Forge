"""Search-multiplicity census — the freeze instrument (D1 of the freeze plan).

WHY: convergence toward a frozen grammar is a PRUNING problem, and pruning
needs a ledger. Crucible's DSR gate charges multiplicity per SLOT
(hypothesis x dte_bucket x xsect-vs-named, ``search_multiplicity.slot_key``);
inside a slot the mass spreads over CELLS ((directional, regime) —
``campaigns.config_cell_from_json``). This census reads the ``submissions``
table, decomposes it into slot x cell, joins ``verdicts`` for conversion, and
classifies every cell so the operator can see exactly how much enumeration
mass is dead-and-unprotected (the freeze metric) versus converting, protected
(a live farming campaign), or already-retired legacy.

This is the yield-audit pattern (``feedback.yield_audit``) generalized from
*names* to *cells*. It reuses the blessed registries so "protected" never
drifts from what the daemon actually farms:
  * ``ranking.campaigns.CAMPAIGNS`` — the D299 farming registry (member
    predicates over ``config_json`` dicts). A cell is PROTECTED iff it matches
    a ``status=="farming"`` campaign (today: ``mr-timer-duration`` +
    ``ve-exit-repair``).
  * ``enumeration.search_space.NON_ENUMERABLE_HYPOTHESES`` — regime_arbitrage
    (D098) + tail_hedge (D066): no longer generated, so their ``n_trials`` is
    DISABLED-LEGACY (historical, inert).

Read-only. Point it at a forge.db SNAPSHOT (the live DB holds an intermittent
RW lock — even read-only opens fail; ``cp`` it first, per the standing
pitfall). ``--snapshot-from`` will do the copy for you.

Usage:
    uv run python scripts/search_multiplicity_census.py --db /tmp/forge_snap.db
    uv run python scripts/search_multiplicity_census.py \
        --snapshot-from ~/forge_data/forge.db --out census.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import duckdb

from forge.enumeration.search_space import (
    _DIRECTIONAL_POOL_EXCLUDED_IDS,
    _REGIME_GATE_GLOBALLY_EXCLUDED_IDS,
    _VOL_EVENT_REGIME_EXCLUDED_IDS,
    NON_ENUMERABLE_HYPOTHESES,
)
from forge.ranking.campaigns import (
    CAMPAIGNS,
    campaign_member_fn,
    config_cell_from_json,
)
from forge.submission.search_multiplicity import _XSECT_COMBINER_TYPE

# Recent-window length for the conversion read. Derived from the data's own
# max(decided_at) so the census is reproducible off a snapshot (no clock).
_RECENT_DAYS = 14

# A cell is judged DEAD only with enough recent SUBMISSIONS to trust the zero —
# below this it is THIN (unclassifiable), never counted as dead mass. Mirrors
# yield_audit's DEFAULT_MIN_CELL_N intent (evidence before a verdict).
_MIN_SUBMITTED_FOR_DEAD = 200

# Liveness keys on SUBMISSION timing, not decision timing: Crucible re-gates
# old configs on a rolling window, so a no-longer-enumerated cell (e.g. the
# v34/D278 gamma_flip gate retirement) keeps producing recent *decisions* long
# after its last *submission*. Only submitted_recent tells us what the grammar
# still emits — the only thing a prune can act on.
_CONVERTING = "converting"
_PROTECTED = "protected"
_DISABLED_LEGACY = "disabled_legacy"  # regime_arbitrage / tail_hedge (not enumerated)
_ALREADY_PRUNED = "already_pruned"  # emission-excluded cell (v31/v33/v34); recent = aging tail
_LEGACY_INACTIVE = "legacy_inactive"  # 0 recent submissions — already gone, nothing to prune
_DEAD_UNPROTECTED = "dead_unprotected"  # still emitted, still not converting — the prune backlog
_THIN = "thin"


def _is_already_pruned(hypothesis: str, directional: str, regime: str) -> bool:
    """True if the cell is already suppressed emission-side, so its recent
    submissions are only the aging tail (never a fresh prune target). Mirrors
    the exclusion sets in ``enumeration.search_space`` — kept in sync by import,
    not by a hardcoded copy."""
    if regime in _REGIME_GATE_GLOBALLY_EXCLUDED_IDS:  # gamma_flip (v34/D278)
        return True
    if hypothesis == "volatility_event" and regime in _VOL_EVENT_REGIME_EXCLUDED_IDS:
        return True  # pre_earnings_setup (v33/D276)
    return directional in _DIRECTIONAL_POOL_EXCLUDED_IDS.get(hypothesis, frozenset())


@dataclass(slots=True)
class Cell:
    """One (slot, directional, regime) enumeration cell's census tally."""

    hypothesis: str
    dte_bucket: str
    axis: str
    directional: str
    regime: str
    n_trials: int = 0  # all-time distinct configs (== count; config_hash unique)
    submitted_recent: int = 0  # submissions in the recent window — the liveness signal
    decided_recent: int = 0
    comp_recent: int = 0
    comp_alltime: int = 0
    promote_alltime: int = 0
    protecting_campaigns: set[str] = field(default_factory=set)

    @property
    def slot(self) -> tuple[str, str, str]:
        return (self.hypothesis, self.dte_bucket, self.axis)

    def add_verdict(self, decision: str, *, recent: bool) -> None:
        if recent:
            self.decided_recent += 1
        if decision == "promote":
            self.promote_alltime += 1
        if decision in ("component", "promote"):
            self.comp_alltime += 1
            if recent:
                self.comp_recent += 1

    def classify(self) -> str:
        if self.hypothesis in NON_ENUMERABLE_HYPOTHESES:
            return _DISABLED_LEGACY
        if _is_already_pruned(self.hypothesis, self.directional, self.regime):
            return _ALREADY_PRUNED
        if self.protecting_campaigns:
            return _PROTECTED
        if self.comp_recent > 0 or self.promote_alltime > 0:
            return _CONVERTING
        if self.submitted_recent == 0:
            return _LEGACY_INACTIVE
        if self.submitted_recent >= _MIN_SUBMITTED_FOR_DEAD:
            return _DEAD_UNPROTECTED
        return _THIN


def _axis(config: dict[str, Any]) -> str:
    """Mirror of ``search_multiplicity.slot_key``'s xsect test on a dict."""
    combiner = config.get("combiner") or {}
    return "xsect" if combiner.get("type") == _XSECT_COMBINER_TYPE else "named"


def _cell_key(config: dict[str, Any]) -> tuple[str, str]:
    """(directional, regime) via the canonical extractor, with a gate-free
    fallback so xsect/rank configs (no regime_filter) still get a cell."""
    canonical = config_cell_from_json(config)
    if canonical is not None:
        return canonical
    directional = "-"
    for signal in config.get("signals", ()):
        if signal.get("role") == "directional":
            inds = signal.get("indicators") or ()
            directional = inds[0] if inds else "-"
            break
    return (directional, "(nogate)")


def _load_cells(db: duckdb.DuckDBPyConnection) -> list[Cell]:
    """One pass over submissions (+ verdict join) → per-cell tallies."""
    decided_row = db.execute("SELECT max(decided_at) FROM verdicts").fetchone()
    submitted_row = db.execute("SELECT max(submitted_at) FROM submissions").fetchone()
    if not decided_row or decided_row[0] is None or not submitted_row or submitted_row[0] is None:
        print("empty snapshot — nothing to census", file=sys.stderr)
        return []
    decided_cutoff = decided_row[0] - timedelta(days=_RECENT_DAYS)
    submitted_cutoff = submitted_row[0] - timedelta(days=_RECENT_DAYS)

    verdicts: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for config_hash, decision, decided_at in db.execute(
        "SELECT config_hash, decision, decided_at FROM verdicts"
    ).fetchall():
        verdicts[config_hash].append((decision, decided_at))

    member_fns = [(c.name, campaign_member_fn(c)) for c in CAMPAIGNS if c.status == "farming"]

    cells: dict[tuple[str, str, str, str, str], Cell] = {}
    for config_hash, config_json, submitted_at in db.execute(
        "SELECT config_hash, config_json, submitted_at FROM submissions"
    ).fetchall():
        config = json.loads(config_json)
        directional, regime = _cell_key(config)
        key = (
            config["hypothesis"],
            config["dte_bucket"],
            _axis(config),
            directional,
            regime,
        )
        cell = cells.get(key)
        if cell is None:
            cell = Cell(*key)
            for name, fn in member_fns:
                if fn is not None and fn(config):
                    cell.protecting_campaigns.add(name)
            cells[key] = cell
        cell.n_trials += 1
        if submitted_at >= submitted_cutoff:
            cell.submitted_recent += 1
        for decision, decided_at in verdicts.get(config_hash, ()):
            cell.add_verdict(decision, recent=decided_at >= decided_cutoff)
    return list(cells.values())


def _report(cells: list[Cell], out_path: Path | None) -> None:
    total = sum(c.n_trials for c in cells)
    by_class: dict[str, int] = defaultdict(int)
    for c in cells:
        by_class[c.classify()] += c.n_trials

    # Slot-level rollup.
    slots: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"n_trials": 0, "comp_recent": 0, "decided_recent": 0}
    )
    for c in cells:
        s = slots[c.slot]
        s["n_trials"] += c.n_trials
        s["comp_recent"] += c.comp_recent
        s["decided_recent"] += c.decided_recent

    print(f"\nSLOTS (n_trials all-time; conversion over last {_RECENT_DAYS}d)")
    print(
        f"{'hypothesis':22s} {'dte':10s} {'axis':6s} {'n_trials':>9s} "
        f"{'%mult':>6s} {'dec':>7s} {'comp':>6s} {'cr':>6s}"
    )
    for slot, s in sorted(slots.items(), key=lambda kv: -kv[1]["n_trials"]):
        cr = 100 * s["comp_recent"] / s["decided_recent"] if s["decided_recent"] else 0.0
        print(
            f"{slot[0]:22s} {slot[1]:10s} {slot[2]:6s} {s['n_trials']:9d} "
            f"{100 * s['n_trials'] / total:5.1f}% {s['decided_recent']:7d} "
            f"{s['comp_recent']:6d} {cr:5.1f}%"
        )

    print("\nCLASS BREAKDOWN (share of all-time multiplicity)")
    for cls in (
        _CONVERTING,
        _PROTECTED,
        _DISABLED_LEGACY,
        _ALREADY_PRUNED,
        _LEGACY_INACTIVE,
        _DEAD_UNPROTECTED,
        _THIN,
    ):
        m = by_class.get(cls, 0)
        print(f"  {cls:18s} {m:9d}  {100 * m / total:5.1f}%")

    # Freeze metric — computed over CURRENT FLOW (recent submissions), the only
    # mass a prune can act on: what share of what we emit today is dead.
    flow_total = sum(c.submitted_recent for c in cells)
    flow_dead = sum(c.submitted_recent for c in cells if c.classify() == _DEAD_UNPROTECTED)
    flow_frac = flow_dead / flow_total if flow_total else 0.0
    print(
        f"\n>>> FREEZE METRIC (B): dead-unprotected share of CURRENT FLOW "
        f"(last {_RECENT_DAYS}d submissions) = {100 * flow_frac:.2f}%  "
        f"({flow_dead}/{flow_total}; target: below an operator-set bar, stable)"
    )

    dead = sorted(
        (c for c in cells if c.classify() == _DEAD_UNPROTECTED),
        key=lambda c: -c.submitted_recent,
    )
    print(
        f"\nDEAD-MASS LEDGER (still emitted, ~0 conversion; top 25 of {len(dead)}) "
        f"— the prune backlog, by current flow"
    )
    print(
        f"{'hypothesis':20s} {'dte':10s} {'axis':6s} {'directional':16s} "
        f"{'regime':16s} {'sub14d':>7s} {'n_trials':>9s} {'compAll':>7s}"
    )
    for c in dead[:25]:
        print(
            f"{c.hypothesis:20s} {c.dte_bucket:10s} {c.axis:6s} "
            f"{c.directional:16s} {c.regime:16s} {c.submitted_recent:7d} "
            f"{c.n_trials:9d} {c.comp_alltime:7d}"
        )

    if out_path is not None:
        payload = {
            "recent_days": _RECENT_DAYS,
            "total_n_trials": total,
            "class_mass": dict(by_class),
            "flow_total_recent": flow_total,
            "flow_dead_unprotected_recent": flow_dead,
            "freeze_metric_dead_flow_fraction": flow_frac,
            "farming_campaigns": [c.name for c in CAMPAIGNS if c.status == "farming"],
            "cells": [
                {
                    "hypothesis": c.hypothesis,
                    "dte_bucket": c.dte_bucket,
                    "axis": c.axis,
                    "directional": c.directional,
                    "regime": c.regime,
                    "n_trials": c.n_trials,
                    "submitted_recent": c.submitted_recent,
                    "decided_recent": c.decided_recent,
                    "comp_recent": c.comp_recent,
                    "comp_alltime": c.comp_alltime,
                    "promote_alltime": c.promote_alltime,
                    "classification": c.classify(),
                    "protecting_campaigns": sorted(c.protecting_campaigns),
                }
                for c in cells
            ],
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwrote {out_path} ({len(cells)} cells)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="path to a forge.db SNAPSHOT")
    parser.add_argument(
        "--snapshot-from",
        type=Path,
        help="cp this live DB to --db first (default target: <db> or ./forge_snap.db)",
    )
    parser.add_argument("--out", type=Path, help="write the full cell JSON here")
    args = parser.parse_args(argv)

    db_path = args.db or Path("forge_snap.db")
    if args.snapshot_from is not None:
        print(f"snapshotting {args.snapshot_from} -> {db_path} ...", file=sys.stderr)
        shutil.copy2(args.snapshot_from, db_path)
    if not db_path.exists():
        parser.error(f"snapshot not found: {db_path} (use --snapshot-from to make one)")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        cells = _load_cells(con)
    finally:
        con.close()
    _report(cells, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
