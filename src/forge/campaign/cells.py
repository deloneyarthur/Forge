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

from forge.campaign.cell_key import config_cell_from_json
from forge.campaign.types import Book, BookLeg, CampaignConfig, CellKey, CellStats
from forge.feedback.eras import CLEAN_ERA_LABEL_CUT, VE_GHOST_LABEL_CUT
from forge.persistence.verdicts import CONVERTING_DECISIONS
from forge.ranking.signal_key import signal_keys
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

    Mirrors the retired ``search_multiplicity_census.py`` (git history) exactly so protection,
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
                    signal_ids=signal_keys(cfg),
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


_CELL_KEY_SQL: str = f"""
    CASE WHEN json_extract_string(config_json, '$.hypothesis') IS NULL
           OR json_extract_string(config_json, '$.hypothesis') = '' THEN '{_ABSENT}'
         ELSE json_extract_string(config_json, '$.hypothesis') END AS hypothesis,
    CASE WHEN json_extract_string(config_json, '$.dte_bucket') IS NULL
           OR json_extract_string(config_json, '$.dte_bucket') = '' THEN '{_ABSENT}'
         ELSE json_extract_string(config_json, '$.dte_bucket') END AS dte_bucket,
    CASE WHEN json_extract_string(config_json, '$.combiner.type') = '{_XSECT_COMBINER_TYPE}'
         THEN 'xsect' ELSE 'named' END AS axis,
    json_extract_string(
        list_filter(json_extract(config_json, '$.signals[*]'),
                    x -> json_extract_string(x, '$.role') = 'directional')[1],
        '$.indicators[0]') AS d0,
    json_extract_string(
        list_filter(json_extract(config_json, '$.signals[*]'),
                    x -> json_extract_string(x, '$.role') = 'regime_filter')[1],
        '$.indicators[0]') AS r0
"""
"""The census cell key computed inside DuckDB — the SQL twin of ``cell_key_from_json``.

WHY SQL: the Python version parsed every ``submissions.config_json`` (1.19 M rows) and
every clean-era verdict's config in the run process, a 16 GB peak for a few hundred
cells (D417/D425). DuckDB's JSON functions do the same extraction in a streaming scan.
The two twins are pinned equal by a differential test over the tricky shapes (missing
roles, empty indicator lists, xsect without a gate, ghost-era ve rows, absent or null
gate values) and were cross-checked over the full live snapshot when this landed (D426).
Precedence, mirrored from the Python: ``d0`` = first indicator of the FIRST directional
signal; ``r0`` = first indicator of the FIRST regime_filter signal; the canonical pair
needs both, otherwise the gate-free fallback keeps the directional and marks the gate.
"""

_CELL_COLUMNS_SQL: str = f"""
    hypothesis, dte_bucket, axis,
    coalesce(d0, '{_ABSENT}') AS directional,
    CASE WHEN d0 IS NOT NULL AND r0 IS NOT NULL THEN r0 ELSE '{_NO_GATE}' END AS regime
"""

# ``_cpcv_p25`` accepted int/float/bool (Python's ``isinstance(x, int | float)`` is true
# for bool) and rejected strings; the JSON type gate mirrors that exactly — a stored
# ``"1.2"`` stays None, ``true`` becomes 1.0, an absent or null value stays None.
_CPCV_VALUE_SQL: str = f"""
    CASE WHEN json_type(v.gate_results, '$.{_CPCV_GATE}.value')
              IN ('DOUBLE', 'UBIGINT', 'BIGINT', 'BOOLEAN')
         THEN TRY_CAST(json_extract(v.gate_results, '$.{_CPCV_GATE}.value') AS DOUBLE)
    END
"""

_STATS_MEMORY_LIMIT: str = "2GB"
"""DuckDB's default memory_limit is 80% of RAM; unbounded, the two stats scans take ~8.7 GB
of process RSS (live snapshot, D426). Capped at 2 GB DuckDB spills and finishes in ~5 s at
~3.5 GB RSS. Scoped to the call; the caller's setting is restored on exit."""


def _cell_stats_rows(
    conn: duckdb.DuckDBPyConnection,
    since_naive: datetime,
    ghost_cut: datetime,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    """The two DuckDB aggregations behind ``load_cell_stats`` — one row per cell each."""
    converting_list = ", ".join(f"'{d}'" for d in sorted(CONVERTING_DECISIONS))
    submitted_rows = conn.execute(
        f"""
        WITH keyed AS (SELECT {_CELL_KEY_SQL} FROM submissions),
             cells AS (SELECT {_CELL_COLUMNS_SQL} FROM keyed)
        SELECT hypothesis, dte_bucket, axis, directional, regime, count(*)
        FROM cells
        GROUP BY ALL
        """  # noqa: S608 -- constants only, no user input
    ).fetchall()
    verdict_rows = conn.execute(
        f"""
        WITH keyed AS (SELECT config_hash, {_CELL_KEY_SQL} FROM submissions),
             cells AS (SELECT config_hash, {_CELL_COLUMNS_SQL} FROM keyed)
        SELECT c.hypothesis, c.dte_bucket, c.axis, c.directional, c.regime,
               count(*) AS decided,
               count_if(v.decision IN ({converting_list})) AS converting,
               max({_CPCV_VALUE_SQL}) AS best,
               max(v.decided_at) AS newest
        FROM verdicts v
        JOIN cells c USING (config_hash)
        WHERE v.decided_at >= ?
          AND NOT (c.hypothesis = '{_VE_HYPOTHESIS}' AND v.decided_at < ?)
        GROUP BY ALL
        """,  # noqa: S608 -- constants only, no user input
        [since_naive, ghost_cut],
    ).fetchall()
    return submitted_rows, verdict_rows


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

    Both aggregates run inside DuckDB over the SQL cell key (``_CELL_KEY_SQL``); the
    process only ever holds one row per cell.
    """
    since_naive = _naive_utc(since or CLEAN_ERA_LABEL_CUT)
    ghost_cut = _naive_utc(VE_GHOST_LABEL_CUT)
    (previous_limit,) = conn.execute("SELECT current_setting('memory_limit')").fetchone()  # type: ignore[misc]
    conn.execute(f"SET memory_limit = '{_STATS_MEMORY_LIMIT}'")
    try:
        submitted_rows, verdict_rows = _cell_stats_rows(conn, since_naive, ghost_cut)
    finally:
        conn.execute(f"SET memory_limit = '{previous_limit}'")
    submitted: dict[CellKey, int] = {
        (h, d, a, di, r): int(n) for h, d, a, di, r, n in submitted_rows
    }
    evidence: dict[CellKey, tuple[int, int, float | None, datetime]] = {
        (h, d, a, di, r): (int(dec), int(conv), best, newest)
        for h, d, a, di, r, dec, conv, best, newest in verdict_rows
    }
    keys = set(submitted) | set(evidence)
    out: dict[CellKey, CellStats] = {}
    for key in sorted(keys):
        dec, conv, best, newest = evidence.get(key, (0, 0, None, None))
        out[key] = CellStats(
            key=key,
            submitted=submitted.get(key, 0),
            decided=dec,
            converting=conv,
            best_cpcv_p25=None if best is None else float(best),
            newest_decided_at=None if newest is None else newest.replace(tzinfo=UTC),
        )
    return out


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
