"""Cell keys, the promoted book, and per-cell verdict evidence.

WHY three reads in one module: the triggers and the gate reason about cells,
and a cell's three facts (is it a book leg? what has Crucible said about it?
has it ever been sampled?) come from three places, all read-only here: the
config itself, Crucible's exports via the contracts loaders (hard rule #2),
and Forge's own verdict ledger. Keeping the three extractors together means
one definition of "cell" everywhere the campaign looks.

Absent exports are not errors: the loaders return nothing and the run's boot
checks decide whether that is acceptable. Corrupt exports ARE errors (the
contracts loaders raise), and they propagate, never swallowed (the CLAUDE.md
rule that `QueryError` is never caught silently outside test fixtures).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from crucible_contracts import (
    StrategyConfig,
    load_component_contributions_from_export,
    load_promoted_portfolios_from_export,
)

from forge.campaign.types import Book, BookLeg, CampaignConfig, CellKey, CellStats
from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT, VE_GHOST_LABEL_CUT
from forge.feedback.yield_audit import CONVERTING_DECISIONS
from forge.ranking.campaigns import config_cell_from_json
from forge.ranking.diversifier import _signal_keys
from forge.submission.search_multiplicity import _XSECT_COMBINER_TYPE

_ABSENT: str = "-"
_NO_GATE: str = "(nogate)"
_VE_HYPOTHESIS: str = "volatility_event"
_CPCV_GATE: str = "cpcv_sharpe_p25"
_PROMOTED_SINCE: datetime = datetime(2020, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# cell key (the census key)
# ---------------------------------------------------------------------------


def cell_key_from_json(config: Mapping[str, Any]) -> CellKey:
    """The census cell of a ``submissions.config_json`` payload.

    Mirrors ``scripts/search_multiplicity_census.py`` exactly so protection,
    evidence, and the freeze census all speak the same key: the canonical
    (directional, regime) pair from the campaign registry, with the gate-free
    fallback for xsect/rank configs that carry no regime filter.
    """
    hypothesis = str(config.get("hypothesis") or _ABSENT)
    dte_bucket = str(config.get("dte_bucket") or _ABSENT)
    combiner = config.get("combiner") or {}
    axis = "xsect" if combiner.get("type") == _XSECT_COMBINER_TYPE else "named"
    canonical = config_cell_from_json(config)
    if canonical is not None:
        directional, regime = canonical
        return (hypothesis, dte_bucket, axis, directional, regime)
    directional = _ABSENT
    for signal in config.get("signals", ()):
        if signal.get("role") == "directional":
            indicators = signal.get("indicators") or ()
            directional = indicators[0] if indicators else _ABSENT
            break
    return (hypothesis, dte_bucket, axis, directional, _NO_GATE)


def cell_key(config: StrategyConfig) -> CellKey:
    """Model-shaped twin of ``cell_key_from_json``; equality pinned by test."""
    return cell_key_from_json(config.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# the book
# ---------------------------------------------------------------------------


def _read_designation(exports_dir: Path) -> tuple[str | None, str | None]:
    """Newest ``designation_history_*.json``: the book QuantIQ trades.

    Read with ``json`` because the contracts package has no loader for this
    stream yet; the shape is Crucible's (``designated.portfolio_id`` /
    ``designated_at``). Daily since 2026-09-14 (their `5b3aa42`); an absent
    file means "no designation known", never "no champion".
    """
    files = sorted(exports_dir.glob("designation_history_*.json"))
    if not files:
        return None, None
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    designated = payload.get("designated") or {}
    portfolio_id = designated.get("portfolio_id")
    designated_at = designated.get("designated_at")
    return (
        str(portfolio_id) if portfolio_id else None,
        str(designated_at) if designated_at else None,
    )


def load_book(exports_dir: Path) -> Book:
    """The designated book plus every promoted book's legs and cells.

    Protection spans ALL promoted books: a live leg is never a target unless a
    replacement campaign names its cell. Marginals are kept only for the
    designated book because the contributions payload files a config that sits
    in several books under the last-iterated one (Crucible 09-13 §1), so a row
    filed under another book says nothing about the designated one.
    """
    designated_id, designated_at = _read_designation(exports_dir)
    portfolios = load_promoted_portfolios_from_export(exports_dir, _PROMOTED_SINCE)
    legs: list[BookLeg] = []
    for portfolio in portfolios:
        for component in portfolio.components:
            cfg = component.strategy_config
            legs.append(
                BookLeg(
                    config_hash=cfg.config_hash,
                    portfolio_id=portfolio.portfolio_id,
                    hypothesis=cfg.hypothesis,
                    cell=cell_key(cfg),
                    signal_ids=_signal_keys(cfg),
                    weight=component.weight,
                )
            )
    marginal: dict[str, float] = {}
    if designated_id is not None:
        contributions = load_component_contributions_from_export(exports_dir)
        marginal = {
            config_hash: contribution.marginal_sharpe
            for config_hash, contribution in contributions.items()
            if contribution.portfolio_id == designated_id
        }
    return Book(
        designated_id=designated_id,
        designated_at=designated_at,
        legs=tuple(legs),
        protected_cells=frozenset(leg.cell for leg in legs),
        marginal_sharpe=marginal,
    )


# ---------------------------------------------------------------------------
# verdict evidence per cell
# ---------------------------------------------------------------------------


def _naive_utc(moment: datetime) -> datetime:
    """DuckDB stores the ledger's timestamps as naive UTC (the D110 convention)."""
    return moment.astimezone(UTC).replace(tzinfo=None)


def _cpcv_p25(gate_results: object) -> float | None:
    """``verdicts.gate_results`` is ``{gate_name: {value, passed, threshold, ...}}``."""
    payload = json.loads(gate_results) if isinstance(gate_results, str) else gate_results
    if not isinstance(payload, dict):
        return None
    entry = payload.get(_CPCV_GATE)
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return float(value) if isinstance(value, int | float) else None


def load_cell_stats(
    conn: duckdb.DuckDBPyConnection,
    *,
    since: datetime | None = None,
) -> dict[CellKey, CellStats]:
    """Per-cell evidence from Forge's own ledger, with the yield auditor's honesty cuts.

    ``submitted`` counts every submission ever (so a cell with none is dark);
    ``decided``/``converting``/``best_cpcv_p25``/``newest_decided_at`` count only
    verdicts inside the clean era (``CLEAN_ERA_LABEL_CUT`` unless ``since`` is
    given) and, for volatility_event, after the ghost-label cut: pre-07-18 ve
    verdicts are fiction (D273/D290), never evidence. Timestamps come back
    tz-aware UTC so callers can compare them with ``utc_now()``.
    """
    since_naive = _naive_utc(since or CLEAN_ERA_LABEL_CUT)
    ghost_cut = _naive_utc(VE_GHOST_LABEL_CUT)
    submitted: dict[CellKey, int] = {}
    decided: dict[CellKey, int] = {}
    converting: dict[CellKey, int] = {}
    best: dict[CellKey, float] = {}
    newest: dict[CellKey, datetime] = {}
    for (config_json,) in conn.execute("SELECT config_json FROM submissions").fetchall():
        key = cell_key_from_json(json.loads(config_json))
        submitted[key] = submitted.get(key, 0) + 1
    rows = conn.execute(
        """
        SELECT s.config_json, v.decision, v.decided_at, v.gate_results
        FROM verdicts v
        JOIN submissions s USING (config_hash)
        WHERE v.decided_at >= ?
        """,
        [since_naive],
    ).fetchall()
    for config_json, decision, decided_at, gate_results in rows:
        key = cell_key_from_json(json.loads(config_json))
        if key[0] == _VE_HYPOTHESIS and decided_at < ghost_cut:
            continue
        decided[key] = decided.get(key, 0) + 1
        if decision in CONVERTING_DECISIONS:
            converting[key] = converting.get(key, 0) + 1
        value = _cpcv_p25(gate_results)
        if value is not None and value > best.get(key, float("-inf")):
            best[key] = value
        if key not in newest or decided_at > newest[key]:
            newest[key] = decided_at
    keys = set(submitted) | set(decided)
    return {
        key: CellStats(
            key=key,
            submitted=submitted.get(key, 0),
            decided=decided.get(key, 0),
            converting=converting.get(key, 0),
            best_cpcv_p25=best.get(key),
            newest_decided_at=(newest[key].replace(tzinfo=UTC) if key in newest else None),
        )
        for key in sorted(keys)
    }


def classify_dead(
    stats: Mapping[CellKey, CellStats],
    config: CampaignConfig,
) -> frozenset[CellKey]:
    """The yield auditor's dead-cell rule at the census-cell level.

    A cell is dead only above the volume floor (zero conversions in a thin
    cell is luck, not structure) and only when its hypothesis converts at all
    somewhere: a zero-baseline hypothesis is a hypothesis-level story and flags
    no cell (the D302 honesty guard, kept verbatim).
    """
    decided_by_h: dict[str, int] = {}
    converting_by_h: dict[str, int] = {}
    for cell in stats.values():
        decided_by_h[cell.key[0]] = decided_by_h.get(cell.key[0], 0) + cell.decided
        converting_by_h[cell.key[0]] = converting_by_h.get(cell.key[0], 0) + cell.converting
    dead: set[CellKey] = set()
    for cell in stats.values():
        if cell.decided < config.dead_min_decided:
            continue
        total = decided_by_h[cell.key[0]]
        baseline = converting_by_h[cell.key[0]] / total if total else 0.0
        if baseline <= 0.0:
            continue
        if cell.converting == 0:
            dead.add(cell.key)
            continue
        if cell.converting / cell.decided < config.dead_ratio_to_baseline * baseline:
            dead.add(cell.key)
    return frozenset(dead)


__all__ = [
    "cell_key",
    "cell_key_from_json",
    "classify_dead",
    "load_book",
    "load_cell_stats",
]
