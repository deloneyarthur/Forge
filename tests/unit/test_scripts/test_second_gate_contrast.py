"""The second-gate contrast must not pool across `measurement_basis`.

The D360 defect, sitting in a committed instrument and named as open in the freeze declaration
§7. The tool compares component RATES across three gate structures; its query filtered
`selection_mode` and `hypothesis` and never `measurement_basis`, so a config with both a
stage-one verdict and a later `fullhist_refit` verdict contributed TWICE, on two different
bases, to the same rate.

That is not a rounding problem. Stage-one and full-history `decision` values answer different
questions, and the refit population is *selected* -- it is the configs someone chose to refit.
Pooling them makes the denominator a mixture whose composition varies by cell, which is exactly
the confound that makes a controlled contrast uncontrolled. The tool's whole claim is that its
three arms "share the SAME base and differ only in what occupies the optional second slot"; an
unfiltered basis silently breaks that.

Two properties:

  1. Rows on the `fullhist_refit` basis are EXCLUDED.
  2. Rows whose basis is NULL are KEPT -- `IS DISTINCT FROM` semantics, matching
     `freeze_tail_reading._QUERY`. A filter that dropped NULLs would silently shrink the honest
     arm, which is the opposite defect and just as quiet.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import duckdb

_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "second_gate_contrast", _ROOT / "scripts" / "second_gate_contrast.py"
)
assert _spec is not None
assert _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["second_gate_contrast"] = _mod
_spec.loader.exec_module(_mod)


def _cfg(gate: str | None) -> str:
    gates = [{"indicator_id": "hurst"}]
    if gate:
        gates.append({"indicator_id": gate})
    return json.dumps({"hypothesis": "trend_continuation", "regime_gates": gates})


def _db(tmp_path: Path, rows: list[tuple[str, str, str | None, str]]) -> Path:
    """rows = (config_hash, selection_mode, measurement_basis, decision)."""
    p = tmp_path / "snap.db"
    con = duckdb.connect(str(p))
    con.execute(
        "CREATE TABLE submissions (config_hash TEXT, selection_mode TEXT, config_json TEXT)"
    )
    con.execute(
        "CREATE TABLE verdicts (config_hash TEXT, grammar_version TEXT, decision TEXT, "
        "gate_results TEXT, measurement_basis TEXT)"
    )
    seen: set[str] = set()
    for h, mode, basis, decision in rows:
        if h not in seen:
            con.execute("INSERT INTO submissions VALUES (?, ?, ?)", [h, mode, _cfg(None)])
            seen.add(h)
        con.execute(
            "INSERT INTO verdicts VALUES (?, ?, ?, ?, ?)",
            [h, "v55", decision, json.dumps({"cpcv_sharpe_p25": {"value": 1.0}}), basis],
        )
    con.close()
    return p


def test_fullhist_refit_rows_are_excluded(tmp_path: Path) -> None:
    """Property 1: the same config on two bases must contribute once, not twice."""
    db = _db(
        tmp_path,
        [
            ("aaa", "holdout", None, "component"),
            ("aaa", "holdout", "fullhist_refit", "component"),
            ("bbb", "prefilter_sample", "fullhist_refit", "component"),
        ],
    )
    with _mod.db_connection(db) as conn:
        rows = _mod.fetch_rows(conn)
    assert len(rows) == 1, f"expected only the stage-one row for aaa, got {rows}"


def test_null_basis_rows_are_kept(tmp_path: Path) -> None:
    """Property 2: IS DISTINCT FROM semantics — a NULL basis is stage one, not a reject."""
    db = _db(tmp_path, [("aaa", "holdout", None, "component")])
    with _mod.db_connection(db) as conn:
        rows = _mod.fetch_rows(conn)
    assert len(rows) == 1


def test_the_query_carries_the_basis_filter() -> None:
    """Belt-and-braces against a future edit silently dropping the clause: the instrument and
    the freeze reads must agree on what the honest population is."""
    assert "measurement_basis" in _mod._QUERY
    assert "fullhist_refit" in _mod._QUERY
