"""`load_cell_stats` moved from Python row parsing into DuckDB (Batch 6B, D426). This module
pins the SQL implementation against a verbatim copy of the Python one it replaced, over the
shapes where the two could plausibly diverge: missing roles, empty indicator lists, an xsect
config without a regime gate, two directionals (the FIRST wins), ghost-era ve rows, absent or
null gate values, a stringified value (Python rejected it; so must the SQL), a boolean value
(Python's ``isinstance(True, int)`` accepted it; so must the SQL), an empty hypothesis string,
and refit rows sharing one config_hash. The reference copy lives here, not in src, so the
production module carries one implementation."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb
import pytest

from forge.campaign.cell_key import config_cell_from_json
from forge.campaign.cells import load_cell_stats
from forge.campaign.types import CellKey, CellStats
from forge.feedback.eras import CLEAN_ERA_LABEL_CUT, VE_GHOST_LABEL_CUT
from forge.persistence.db import open_db
from forge.persistence.verdicts import CONVERTING_DECISIONS
from tests.fixtures.strategy_configs import minimal_strategy_config

_NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
_XSECT = "cross_sectional_rank"


# ---------------------------------------------------------------------------
# the reference: the Python implementation replaced in D426, verbatim
# ---------------------------------------------------------------------------


def _ref_cell_key(config: Mapping[str, Any]) -> CellKey:
    hypothesis = str(config.get("hypothesis") or "-")
    dte_bucket = str(config.get("dte_bucket") or "-")
    combiner = config.get("combiner") or {}
    axis = "xsect" if combiner.get("type") == _XSECT else "named"
    canonical = config_cell_from_json(config)
    if canonical is not None:
        directional, regime = canonical
        return (hypothesis, dte_bucket, axis, directional, regime)
    directional = "-"
    for signal in config.get("signals", ()):
        if signal.get("role") == "directional":
            indicators = signal.get("indicators") or ()
            directional = indicators[0] if indicators else "-"
            break
    return (hypothesis, dte_bucket, axis, directional, "(nogate)")


def _ref_cpcv_p25(gate_results: object) -> float | None:
    payload = json.loads(gate_results) if isinstance(gate_results, str) else gate_results
    if not isinstance(payload, dict):
        return None
    entry = payload.get("cpcv_sharpe_p25")
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return float(value) if isinstance(value, int | float) else None


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


def reference_load_cell_stats(
    conn: duckdb.DuckDBPyConnection, *, since: datetime | None = None
) -> dict[CellKey, CellStats]:
    since_naive = _naive_utc(since or CLEAN_ERA_LABEL_CUT)
    ghost_cut = _naive_utc(VE_GHOST_LABEL_CUT)
    submitted: dict[CellKey, int] = {}
    decided: dict[CellKey, int] = {}
    converting: dict[CellKey, int] = {}
    best: dict[CellKey, float] = {}
    newest: dict[CellKey, datetime] = {}
    for (config_json,) in conn.execute("SELECT config_json FROM submissions").fetchall():
        key = _ref_cell_key(json.loads(config_json))
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
        key = _ref_cell_key(json.loads(config_json))
        if key[0] == "volatility_event" and decided_at < ghost_cut:
            continue
        decided[key] = decided.get(key, 0) + 1
        if decision in CONVERTING_DECISIONS:
            converting[key] = converting.get(key, 0) + 1
        value = _ref_cpcv_p25(gate_results)
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


# ---------------------------------------------------------------------------
# fixture DB with the tricky shapes
# ---------------------------------------------------------------------------


def _insert(
    conn: duckdb.DuckDBPyConnection,
    payload: Mapping[str, Any],
    *,
    verdicts: list[tuple[str, datetime, object]] = (),  # type: ignore[assignment]
    config_hash: str | None = None,
) -> str:
    """One submission (config_json as given) plus zero or more verdict rows
    ``(decision, decided_at, gate_results_json_or_dict)``."""
    config_hash = config_hash or uuid.uuid4().hex[:16]
    conn.execute(
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status, crucible_run_id, selection_mode)
        VALUES (?, ?, ?, ?, ?, 'submitted', NULL, 'ranked')
        """,
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            json.dumps(payload),
            (_NOW - timedelta(days=30)).replace(tzinfo=None),
        ],
    )
    for decision, decided_at, gate_results in verdicts:
        conn.execute(
            """
            INSERT INTO verdicts
                (crucible_run_id, config_hash, decision, decided_at, trade_count,
                 grammar_version, gate_results, recorded_at)
            VALUES (?, ?, ?, ?, NULL, 'v55', ?, ?)
            """,
            [
                str(uuid.uuid4()),
                config_hash,
                decision,
                decided_at.replace(tzinfo=None),
                gate_results if isinstance(gate_results, str) else json.dumps(gate_results),
                decided_at.replace(tzinfo=None),
            ],
        )
    return config_hash


def _base(**overrides: Any) -> dict[str, Any]:
    return minimal_strategy_config(**overrides).model_dump(mode="json")  # type: ignore[no-any-return]


def _cpcv(value: object) -> dict[str, Any]:
    return {"cpcv_sharpe_p25": {"value": value, "passed": False}}


@pytest.fixture
def tricky_db() -> duckdb.DuckDBPyConnection:
    conn = open_db(":memory:")
    d1 = _NOW - timedelta(days=3)
    d2 = _NOW - timedelta(days=1)
    # 1. ordinary cell, refit rows share one hash; best is the max, newest the latest
    _insert(conn, _base(), verdicts=[("reject", d1, _cpcv(0.4)), ("component", d2, _cpcv(1.7))])
    # 2. xsect combiner without a regime gate -> the gate-free fallback
    p = _base()
    p["combiner"] = {"type": _XSECT}
    p["signals"] = [s for s in p["signals"] if s["role"] == "directional"]
    _insert(conn, p, verdicts=[("reject", d1, _cpcv(0.9))])
    # 3. two directionals: the FIRST wins; regime present
    p = _base()
    d_sig = next(s for s in p["signals"] if s["role"] == "directional")
    second = dict(d_sig, id="sig_second", indicators=["second_dir"])
    p["signals"] = [*p["signals"], second]
    _insert(conn, p, verdicts=[("reject", d1, _cpcv(1.1))])
    # 4. regime signal listed BEFORE the directional
    p = _base()
    p["signals"] = list(reversed(p["signals"]))
    _insert(conn, p, verdicts=[("promote", d2, _cpcv(2.2))])
    # 5. directional with an EMPTY indicator list -> canonical None, directional '-'
    p = _base()
    for s in p["signals"]:
        if s["role"] == "directional":
            s["indicators"] = []
    _insert(conn, p, verdicts=[("reject", d1, _cpcv(0.2))])
    # 6. regime with an empty indicator list -> canonical None, gate-free fallback
    p = _base()
    for s in p["signals"]:
        if s["role"] == "regime_filter":
            s["indicators"] = []
    _insert(conn, p, verdicts=[("reject", d1, _cpcv(0.3))])
    # 7. no signals at all; empty hypothesis string; no dte_bucket
    _insert(conn, {"hypothesis": "", "signals": []}, verdicts=[("reject", d1, {})])
    # 8. ve rows before and after the ghost cut (only the later one is evidence)
    ve = _base(hypothesis="volatility_event")
    _insert(
        conn,
        ve,
        verdicts=[
            ("component", VE_GHOST_LABEL_CUT - timedelta(hours=1), _cpcv(3.0)),
            ("reject", VE_GHOST_LABEL_CUT + timedelta(hours=1), _cpcv(0.5)),
        ],
    )
    # 9. gate value shapes: null, stringified, boolean, integer, missing gate, scalar entry
    p = _base(dte_bucket="swing_mid")
    _insert(
        conn,
        p,
        verdicts=[
            ("reject", d1, _cpcv(None)),
            ("reject", d1, _cpcv("1.2")),
            ("reject", d1, _cpcv(True)),
            ("reject", d1, _cpcv(3)),
            ("reject", d1, {"other_gate": {"value": 9.9}}),
            ("reject", d1, {"cpcv_sharpe_p25": "x"}),
        ],
    )
    # 10. pre-clean-era verdict: submitted counts, decided does not
    _insert(
        conn,
        _base(dte_bucket="swing_long"),
        verdicts=[("reject", CLEAN_ERA_LABEL_CUT - timedelta(days=1), _cpcv(5.0))],
    )
    # 11. submitted, never decided (a dark-side cell)
    _insert(conn, _base(hypothesis="trend_continuation"))
    return conn


def test_sql_matches_the_python_reference_on_tricky_shapes(
    tricky_db: duckdb.DuckDBPyConnection,
) -> None:
    assert load_cell_stats(tricky_db) == reference_load_cell_stats(tricky_db)


def test_sql_matches_the_python_reference_with_since_override(
    tricky_db: duckdb.DuckDBPyConnection,
) -> None:
    since = _NOW - timedelta(days=2)
    assert load_cell_stats(tricky_db, since=since) == reference_load_cell_stats(
        tricky_db, since=since
    )


def test_the_tricky_shapes_actually_exercise_the_corners(
    tricky_db: duckdb.DuckDBPyConnection,
) -> None:
    """Guard the fixture itself: the corners must be present, or the differential
    test proves nothing."""
    stats = load_cell_stats(tricky_db)
    keys = set(stats)
    assert ("-", "-", "named", "-", "(nogate)") in keys  # empty hypothesis, no signals
    assert any(k[2] == "xsect" and k[4] == "(nogate)" for k in keys)  # xsect, gate-free
    assert any(k[3] == "-" and k[4] == "(nogate)" for k in keys)  # empty directional list
    ve = next(k for k in keys if k[0] == "volatility_event")
    assert stats[ve].decided == 1  # the ghost-era row is not evidence
    mid = next(k for k in keys if k[1] == "swing_mid")
    # null/"1.2"/absent/scalar -> None; True -> 1.0; 3 -> 3.0: the max is 3.0
    assert stats[mid].best_cpcv_p25 == pytest.approx(3.0)
    assert stats[mid].decided == 6
    long = next(k for k in keys if k[1] == "swing_long")
    assert (stats[long].submitted, stats[long].decided) == (1, 0)
    dark = next(k for k in keys if k[0] == "trend_continuation")
    assert (stats[dark].submitted, stats[dark].decided) == (1, 0)


def test_load_cell_stats_restores_the_callers_memory_limit(
    tricky_db: duckdb.DuckDBPyConnection,
) -> None:
    """The 2 GB cap is scoped to the two stats scans: the trainer shares the connection
    and must not inherit it."""
    tricky_db.execute("SET memory_limit = '7.5 GiB'")
    (before,) = tricky_db.execute("SELECT current_setting('memory_limit')").fetchone()  # type: ignore[misc]
    load_cell_stats(tricky_db)
    (after,) = tricky_db.execute("SELECT current_setting('memory_limit')").fetchone()  # type: ignore[misc]
    assert after == before
