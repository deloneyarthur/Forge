"""Standing yield auditor — self-serve dead-cell detection (D302, Theme 4).

WHY: every structural exclusion so far (v34, v37, the v41 ASML/COST rider) was
found by CRUCIBLE's census reading OUR verdicts — we shipped the frozen-list
mechanism four times without ever owning the detector. This module runs those
reads locally: per-name conversion (the "641 decided / 0 components" class)
and per-(hypothesis, dte_bucket) cell conversion vs the hypothesis baseline,
min-n guarded.

Honesty guards (the D273 lesson — bad labels make confident wrong calls):

  * the ve ghost-label cut applies (``VE_GHOST_LABEL_CUT``): pre-07-18
    volatility_event verdicts are unrankable fiction, never evidence;
  * the clean-era window applies by default (``CLEAN_ERA_LABEL_CUT``);
  * hypotheses claimed by FARMING campaigns are exempt from cell flags — a
    young concentrated sweep looks exactly like a dead cell until its funnel
    read matures (the v33 resid sweep would have flagged in week one);
  * names already in the sampler's structural exclusion are reported for
    retire-review, never re-flagged;
  * a zero-baseline hypothesis yields no cell flags (that is a name- or
    hypothesis-level story).

DETECTION ONLY. This module never writes grammar.yaml, OPEN_PROPOSALS.md, or
the DB — the CLI prints staged rider drafts; shipping an exclusion stays
behind the operator-gated grammar-bump ritual (hard rule #4 licenses the
tightening; the deploy gate stays human). Run against a /tmp snapshot of the
live DB (RW-lock pitfall).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

# The sampler owns "already structurally excluded" — a drifting copy here
# would silently re-flag or silently skip; import the single source of truth.
from forge.enumeration.sampler import (
    _STRUCTURALLY_UNTRADEABLE_UNDERLYINGS as STRUCTURALLY_EXCLUDED,
)
from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT, VE_GHOST_LABEL_CUT
from forge.ranking.campaigns import CAMPAIGNS, Campaign

if TYPE_CHECKING:
    import duckdb

# Verdict decisions that count as conversion. Observed live literals:
# 'component' / 'reject' / 'promote' (forge campaigns audit, 2026-07-20).
CONVERTING_DECISIONS: frozenset[str] = frozenset({"component", "promote"})

_VE_HYPOTHESIS = "volatility_event"

# The census bar (their tier-unpin reply: ASML 641/0, BKNG 1,254/0, ...):
# enough decided volume that zero conversions is structure, not luck.
DEFAULT_MIN_NAME_N: int = 500

# Cell flags need more volume than name flags — the baseline comparison adds
# a second estimated quantity.
DEFAULT_MIN_CELL_N: int = 1000

# Flag a cell converting below this fraction of its hypothesis baseline.
DEFAULT_CELL_RATIO: float = 0.25


@dataclass(frozen=True, slots=True)
class DeadName:
    underlying: str
    decided: int
    converted: int


@dataclass(frozen=True, slots=True)
class ExcludedNameActivity:
    """Decided volume on an already-excluded name — retire-review input, not
    a flag (stale rows predate the exclusion; fresh rows would mean a leak)."""

    underlying: str
    decided: int
    converted: int


@dataclass(frozen=True, slots=True)
class ColdCell:
    hypothesis: str
    dte_bucket: str
    decided: int
    converted: int
    cell_rate: float
    baseline_rate: float


@dataclass(frozen=True, slots=True)
class YieldAuditReport:
    since: str
    rows_considered: int
    ghost_rows_cut: int
    dead_names: tuple[DeadName, ...]
    excluded_names: tuple[ExcludedNameActivity, ...]
    cold_cells: tuple[ColdCell, ...]
    exempt_hypotheses: tuple[str, ...]


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


@dataclass(slots=True)
class _Tallies:
    considered: int = 0
    ghost_cut_count: int = 0
    name_decided: Counter[str] = field(default_factory=Counter)
    name_converted: Counter[str] = field(default_factory=Counter)
    cell_decided: Counter[tuple[str, str]] = field(default_factory=Counter)
    cell_converted: Counter[tuple[str, str]] = field(default_factory=Counter)


def _tally_rows(rows: Sequence[tuple[str, str, datetime]]) -> _Tallies:
    """One pass over decided rows: name + cell counts, ghost rows cut."""
    ghost_cut = _naive_utc(VE_GHOST_LABEL_CUT)
    t = _Tallies()
    for config_json, decision, decided_at in rows:
        config = json.loads(config_json)
        hypothesis = str(config.get("hypothesis") or "")
        if hypothesis == _VE_HYPOTHESIS and decided_at < ghost_cut:
            t.ghost_cut_count += 1
            continue
        t.considered += 1
        converting = decision in CONVERTING_DECISIONS
        underlying = config.get("underlying")
        if underlying:
            t.name_decided[str(underlying)] += 1
            if converting:
                t.name_converted[str(underlying)] += 1
        bucket = str(config.get("dte_bucket") or "")
        if hypothesis and bucket:
            t.cell_decided[(hypothesis, bucket)] += 1
            if converting:
                t.cell_converted[(hypothesis, bucket)] += 1
    return t


def _name_flags(
    t: _Tallies, min_name_n: int
) -> tuple[tuple[DeadName, ...], tuple[ExcludedNameActivity, ...]]:
    dead: list[DeadName] = []
    excluded: list[ExcludedNameActivity] = []
    for underlying in sorted(t.name_decided):
        decided = t.name_decided[underlying]
        converted = t.name_converted[underlying]
        if underlying in STRUCTURALLY_EXCLUDED:
            excluded.append(
                ExcludedNameActivity(underlying=underlying, decided=decided, converted=converted)
            )
        elif decided >= min_name_n and converted == 0:
            dead.append(DeadName(underlying=underlying, decided=decided, converted=converted))
    return tuple(dead), tuple(excluded)


def _cell_flags(
    t: _Tallies, min_cell_n: int, cell_ratio: float, exempt: tuple[str, ...]
) -> tuple[ColdCell, ...]:
    hyp_decided: Counter[str] = Counter()
    hyp_converted: Counter[str] = Counter()
    for (hypothesis, _bucket), decided in t.cell_decided.items():
        hyp_decided[hypothesis] += decided
    for (hypothesis, _bucket), converted in t.cell_converted.items():
        hyp_converted[hypothesis] += converted

    flags: list[ColdCell] = []
    for cell in sorted(t.cell_decided):
        hypothesis, bucket = cell
        decided = t.cell_decided[cell]
        if hypothesis in exempt or decided < min_cell_n:
            continue
        baseline = hyp_converted[hypothesis] / hyp_decided[hypothesis]
        if baseline <= 0.0:
            continue  # hypothesis-level story, not a cell flag
        rate = t.cell_converted[cell] / decided
        if rate < cell_ratio * baseline:
            flags.append(
                ColdCell(
                    hypothesis=hypothesis,
                    dte_bucket=bucket,
                    decided=decided,
                    converted=t.cell_converted[cell],
                    cell_rate=rate,
                    baseline_rate=baseline,
                )
            )
    return tuple(flags)


def audit_yield(
    conn: duckdb.DuckDBPyConnection,
    *,
    since: datetime = CLEAN_ERA_LABEL_CUT,
    min_name_n: int = DEFAULT_MIN_NAME_N,
    min_cell_n: int = DEFAULT_MIN_CELL_N,
    cell_ratio: float = DEFAULT_CELL_RATIO,
    campaigns: Sequence[Campaign] | None = None,
) -> YieldAuditReport:
    """Run the dead-name + cold-cell reads over decided verdicts since ``since``.

    Counts VERDICT rows (a re-gated config counts each decision), matching the
    census basis. ``campaigns`` defaults to the live registry; farming
    campaigns' hypotheses are exempt from cell flags.
    """
    registry = CAMPAIGNS if campaigns is None else campaigns
    exempt = tuple(
        sorted({c.hypothesis for c in registry if c.status == "farming" and c.hypothesis})
    )
    rows = conn.execute(
        """
        SELECT s.config_json, v.decision, v.decided_at
        FROM verdicts v
        JOIN submissions s USING (config_hash)
        WHERE v.decided_at >= ?
        """,
        [_naive_utc(since)],
    ).fetchall()

    t = _tally_rows(rows)
    dead_names, excluded_activity = _name_flags(t, min_name_n)
    return YieldAuditReport(
        since=_naive_utc(since).isoformat(),
        rows_considered=t.considered,
        ghost_rows_cut=t.ghost_cut_count,
        dead_names=dead_names,
        excluded_names=excluded_activity,
        cold_cells=_cell_flags(t, min_cell_n, cell_ratio, exempt),
        exempt_hypotheses=exempt,
    )


__all__ = [
    "CONVERTING_DECISIONS",
    "DEFAULT_CELL_RATIO",
    "DEFAULT_MIN_CELL_N",
    "DEFAULT_MIN_NAME_N",
    "ColdCell",
    "DeadName",
    "ExcludedNameActivity",
    "YieldAuditReport",
    "audit_yield",
]
