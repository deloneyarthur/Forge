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

from forge.core.clock import utc_now
from forge.enumeration.sampler import _NO_EARNINGS_UNDERLYINGS
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

# Earnings-event regime gates: on a NO-EARNINGS underlying they NaN/sentinel-fill
# and never gate (the D268 SOXL degenerate — days_since_earnings -> allow=True ->
# a passthrough backfills a naked long call). Such a config is (a) unreproducible
# post-D268/v32 (the sampler excludes _NO_EARNINGS_UNDERLYINGS from earnings-gated
# draws) and (b) a mislabeled leg if it sits in a promoted book.
_EARNINGS_GATE_IDS = frozenset({"days_to_earnings", "days_since_earnings", "pre_earnings_setup"})
_DEFAULT_EXPORTS_DIR = Path.home() / "optbt_data" / "exports"

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


def _is_degenerate_leg(config: dict[str, Any]) -> bool:
    """True for a D268-class degenerate: an earnings-event gate on a no-earnings
    underlying (e.g. the pure_sue175 SOXL leg). Its earnings signals are inert, so
    a passthrough backfills a naked long call — mislabeled alpha, and unreproducible
    since the sampler now excludes these underlyings from earnings-gated draws."""
    underlying = config.get("underlying")
    if underlying not in _NO_EARNINGS_UNDERLYINGS:
        return False
    return any(
        signal.get("role") in ("regime_filter", "directional")
        and any(ind in _EARNINGS_GATE_IDS for ind in (signal.get("indicators") or ()))
        for signal in config.get("signals", ())
    )


def _load_promoted_cells(exports_dir: Path) -> set[tuple[str, str, str, str, str]]:
    """The (hypothesis, dte_bucket, axis, directional, regime) cells of every
    component in a currently-promoted book — GROUND-TRUTH protection (a live book
    leg is never a prune target). Read via the blessed contracts loader; fail-open
    (an absent/unreadable export just yields no promoted protections)."""
    try:
        from datetime import UTC, datetime

        from crucible_contracts import load_promoted_portfolios_from_export

        portfolios = load_promoted_portfolios_from_export(
            exports_dir, datetime(2020, 1, 1, tzinfo=UTC)
        )
    except Exception:
        return set()
    cells: set[tuple[str, str, str, str, str]] = set()
    for portfolio in portfolios:
        for component in portfolio.components:
            config = component.strategy_config.model_dump()
            directional, regime = _cell_key(config)
            cells.add(
                (config["hypothesis"], config["dte_bucket"], _axis(config), directional, regime)
            )
    return cells


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
    degenerate_recent: int = 0  # recent submissions that are D268-class degenerate legs
    decided_recent: int = 0
    comp_recent: int = 0
    comp_alltime: int = 0
    promote_alltime: int = 0
    promoted_book: bool = False  # a component of this cell sits in a live promoted book
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

    @property
    def live_recent(self) -> int:
        """Recent submissions minus D268-class degenerate legs — the latter are
        already excluded emission-side, so they are an aging tail, never live dead."""
        return self.submitted_recent - self.degenerate_recent

    def classify(self) -> str:
        if self.hypothesis in NON_ENUMERABLE_HYPOTHESES:
            return _DISABLED_LEGACY
        if _is_already_pruned(self.hypothesis, self.directional, self.regime):
            return _ALREADY_PRUNED
        if self.promoted_book or self.protecting_campaigns:
            return _PROTECTED  # ground truth: a live book leg / farming cell — never a prune target
        if self.comp_recent > 0 or self.promote_alltime > 0:
            return _CONVERTING
        if self.live_recent <= 0:
            return _LEGACY_INACTIVE
        if self.live_recent >= _MIN_SUBMITTED_FOR_DEAD:
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


def _load_cells(
    db: duckdb.DuckDBPyConnection,
    promoted_cells: set[tuple[str, str, str, str, str]] | None = None,
) -> list[Cell]:
    """One pass over submissions (+ verdict join) → per-cell tallies."""
    promoted_cells = promoted_cells or set()
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
            cell.promoted_book = key in promoted_cells
            for name, fn in member_fns:
                if fn is not None and fn(config):
                    cell.protecting_campaigns.add(name)
            cells[key] = cell
        cell.n_trials += 1
        if submitted_at >= submitted_cutoff:
            cell.submitted_recent += 1
            if _is_degenerate_leg(config):
                cell.degenerate_recent += 1
        for decision, decided_at in verdicts.get(config_hash, ()):
            cell.add_verdict(decision, recent=decided_at >= decided_cutoff)
    return list(cells.values())


def _flow_summary(cells: list[Cell]) -> dict[str, Any]:
    """The metric row shared by the report, the --out JSON, and the daily JSONL.

    Freeze metric B lives here: dead-unprotected share of CURRENT FLOW (recent
    submissions) — the only mass a prune can act on.
    """
    total = sum(c.n_trials for c in cells)
    by_class: dict[str, int] = defaultdict(int)
    for c in cells:
        by_class[c.classify()] += c.n_trials
    # Flow is over LIVE submissions (degenerate D268-class legs are excluded — they
    # are an aging tail the sampler no longer emits).
    flow_total = sum(c.live_recent for c in cells)
    flow_dead = sum(c.live_recent for c in cells if c.classify() == _DEAD_UNPROTECTED)
    return {
        "recent_days": _RECENT_DAYS,
        "total_n_trials": total,
        "class_mass": dict(by_class),
        "flow_total_recent": flow_total,
        "flow_dead_unprotected_recent": flow_dead,
        "freeze_metric_dead_flow_fraction": flow_dead / flow_total if flow_total else 0.0,
        "n_dead_cells": sum(1 for c in cells if c.classify() == _DEAD_UNPROTECTED),
        "n_promoted_book_cells": sum(1 for c in cells if c.promoted_book),
        "degenerate_flow_recent": sum(c.degenerate_recent for c in cells),
        "dead_unprotected_share": (by_class.get(_DEAD_UNPROTECTED, 0) / total) if total else 0.0,
        "converting_share": (by_class.get(_CONVERTING, 0) / total) if total else 0.0,
        "farming_campaigns": [c.name for c in CAMPAIGNS if c.status == "farming"],
    }


def _append_jsonl(cells: list[Cell], path: Path) -> None:
    """One compact metric-B row per run — the standing freeze series the daily
    timer appends and `forge healthcheck` reads."""
    summ = _flow_summary(cells)
    row = {
        "ts": utc_now().isoformat(),
        "metric_b_flow": summ["freeze_metric_dead_flow_fraction"],
        "flow_dead": summ["flow_dead_unprotected_recent"],
        "flow_total": summ["flow_total_recent"],
        "n_dead_cells": summ["n_dead_cells"],
        "n_promoted_book_cells": summ["n_promoted_book_cells"],
        "degenerate_flow_recent": summ["degenerate_flow_recent"],
        "dead_unprotected_share": summ["dead_unprotected_share"],
        "converting_share": summ["converting_share"],
        "farming_campaigns": summ["farming_campaigns"],
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    print(f"appended census row to {path}: metric_b_flow={row['metric_b_flow']:.4f}")


def _report(cells: list[Cell], out_path: Path | None) -> None:
    summ = _flow_summary(cells)
    total = summ["total_n_trials"]
    by_class = summ["class_mass"]

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
    flow_total = summ["flow_total_recent"]
    flow_dead = summ["flow_dead_unprotected_recent"]
    flow_frac = summ["freeze_metric_dead_flow_fraction"]
    print(
        f"\n>>> FREEZE METRIC (B): dead-unprotected share of CURRENT LIVE FLOW "
        f"(last {_RECENT_DAYS}d submissions, degenerate excluded) = {100 * flow_frac:.2f}%  "
        f"({flow_dead}/{flow_total}; target: below an operator-set bar, stable)"
    )
    print(
        f"    promoted-book-protected cells: {summ['n_promoted_book_cells']}  |  "
        f"D268-degenerate legs in recent flow: {summ['degenerate_flow_recent']} (excluded from B)"
    )

    degenerate = sorted(
        (c for c in cells if c.degenerate_recent > 0), key=lambda c: -c.degenerate_recent
    )
    if degenerate:
        print("\nDEGENERATE LEGS (D268-class: earnings gate on a no-earnings underlying; top 10)")
        print(
            f"{'hypothesis':20s} {'axis':6s} {'directional':16s} {'regime':18s} "
            f"{'degen14d':>8s} {'promoted?':>9s}"
        )
        for c in degenerate[:10]:
            print(
                f"{c.hypothesis:20s} {c.axis:6s} {c.directional:16s} {c.regime:18s} "
                f"{c.degenerate_recent:8d} {'YES' if c.promoted_book else '-':>9s}"
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
            **summ,
            "cells": [
                {
                    "hypothesis": c.hypothesis,
                    "dte_bucket": c.dte_bucket,
                    "axis": c.axis,
                    "directional": c.directional,
                    "regime": c.regime,
                    "n_trials": c.n_trials,
                    "submitted_recent": c.submitted_recent,
                    "live_recent": c.live_recent,
                    "degenerate_recent": c.degenerate_recent,
                    "decided_recent": c.decided_recent,
                    "comp_recent": c.comp_recent,
                    "comp_alltime": c.comp_alltime,
                    "promote_alltime": c.promote_alltime,
                    "promoted_book": c.promoted_book,
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
    parser.add_argument(
        "--jsonl-out",
        type=Path,
        help="append one compact metric-B row here (the daily freeze series)",
    )
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=_DEFAULT_EXPORTS_DIR,
        help="Crucible exports dir (for promoted-book-component protection)",
    )
    args = parser.parse_args(argv)

    db_path = args.db or Path("forge_snap.db")
    if args.snapshot_from is not None:
        print(f"snapshotting {args.snapshot_from} -> {db_path} ...", file=sys.stderr)
        shutil.copy2(args.snapshot_from, db_path)
    if not db_path.exists():
        parser.error(f"snapshot not found: {db_path} (use --snapshot-from to make one)")

    promoted_cells = _load_promoted_cells(args.exports_dir)
    print(f"promoted-book cells for protection: {len(promoted_cells)}", file=sys.stderr)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        cells = _load_cells(con, promoted_cells)
    finally:
        con.close()
    _report(cells, args.out)
    if args.jsonl_out is not None:
        _append_jsonl(cells, args.jsonl_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
