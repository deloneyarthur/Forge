"""Phase 5 invariants — feedback (reconcile) + grammar-change discipline.

Each invariant maps to a CLAUDE.md hard rule or a §8/§13 spec contract.
Owned by Phase 5; new constraints add tests here.
"""

from __future__ import annotations

import ast
import inspect
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

import duckdb
import pytest

from forge.feedback.consumer import consume_batch_results
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

# ---------------------------------------------------------------------------
# CLAUDE.md hard rule #4 (no apply_loosening) — structural
# ---------------------------------------------------------------------------


_LOOSEN_FORBIDDEN_NAMES = ("apply_loosening", "apply_loosen", "auto_apply_loosen")


def _module_function_names(module: object) -> set[str]:
    return {n for n, _ in inspect.getmembers(module, inspect.isfunction)}


# ---------------------------------------------------------------------------
# Phase 5 proposer fires only tighten-direction proposals
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Consumer idempotency
# ---------------------------------------------------------------------------


def _insert_forge_sub(
    db: duckdb.DuckDBPyConnection, *, batch_id: uuid.UUID, config: object
) -> uuid.UUID:
    cid = uuid.uuid4()
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(cid),
            str(batch_id),
            config.config_hash,  # type: ignore[attr-defined]
            config.model_dump_json(),  # type: ignore[attr-defined]
            datetime(2026, 5, 13, tzinfo=UTC),
            "submitted",
        ],
    )
    return cid


def _insert_batch(db: duckdb.DuckDBPyConnection, *, batch_id: uuid.UUID, batch_size: int) -> None:
    db.execute(
        "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
        "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
        [str(batch_id), batch_size, datetime(2026, 5, 13, tzinfo=UTC), "v1", "abc"],
    )


def _insert_crucible_gated(
    crucible_db: Path, *, config_hash: str, decision: str = "promote"
) -> None:
    conn = duckdb.connect(str(crucible_db))
    try:
        run_id = str(uuid.uuid4())
        gates = (
            {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": True, "value": 1.2}}
            if decision == "promote"
            else {"sharpe_gate": {"gate_name": "sharpe_gate", "passed": False, "value": 0.4}}
        )
        conn.execute(
            "INSERT INTO runs (run_id, config_hash, source, status, period_start, "
            "period_end, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                config_hash,
                "forge",
                "gated",
                date(2022, 1, 1),
                date(2024, 12, 31),
                date(2026, 5, 13),
                date(2026, 5, 13),
            ],
        )
        conn.execute(
            "INSERT INTO promotion_decisions (run_id, decision, gate_results_json, "
            "decided_at, decided_by) VALUES (?, ?, ?, ?, ?)",
            [
                run_id,
                decision,
                json.dumps(gates),
                datetime(2026, 5, 13, 14, tzinfo=UTC),
                "gate_v1",
            ],
        )
    finally:
        conn.close()


def test_consume_batch_results_is_idempotent(tmp_path: Path) -> None:
    """Re-consuming the same batch returns equivalent BatchFeedback and
    leaves the DB state unchanged after the first run completes."""
    forge_db = tmp_path / "forge.db"
    crucible_db = tmp_path / "crucible.db"
    build_synthetic_crucible_db(crucible_db).close()
    cfg = minimal_strategy_config()
    _insert_crucible_gated(crucible_db, config_hash=cfg.config_hash)
    batch_id = uuid.uuid4()
    with db_connection(forge_db) as conn:
        _insert_batch(conn, batch_id=batch_id, batch_size=1)
        _insert_forge_sub(conn, batch_id=batch_id, config=cfg)
        a = consume_batch_results(conn, crucible_db, batch_id=batch_id)
        b = consume_batch_results(conn, crucible_db, batch_id=batch_id)
        rows = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    assert a.gated_count == b.gated_count
    assert a.promoted_count == b.promoted_count
    assert rows is not None
    assert rows[0] == 1  # no duplicate rows from re-consume


# ---------------------------------------------------------------------------
# Proposer never emits more proposals than triggers fire
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Refresh: the `GrammarProposal.is_loosen` property structurally distinguishes
# tighten from loosen — proposers/CLIs key off this not raw text comparison
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Hard rule #8 — feedback modules use blessed clock (no datetime.now())
# ---------------------------------------------------------------------------


def test_feedback_modules_do_not_call_naive_clock() -> None:
    """Scan feedback module source for forbidden datetime.now()/utcnow()."""
    import forge.feedback as fb_pkg

    fb_root = Path(fb_pkg.__file__).parent
    forbidden = ("datetime.now(", "datetime.utcnow(")
    for py_file in fb_root.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{py_file.name} uses {token}"


# ---------------------------------------------------------------------------
# CLAUDE.md hard rule #4 — structural, post-freeze form (Batch 5 G3, D420)
# ---------------------------------------------------------------------------
# The daemon-era guarantee was "no apply_loosening path in analyzer / proposer /
# proposal_writer / calibration". Those modules are gone; the guarantee that
# replaces it is that NO code under src/forge writes config/grammar.yaml at
# runtime — every grammar change is a preregistered, operator-signed commit that
# the pre-commit hooks guard (`freeze-governance`, `grammar-version-bump`; their
# wiring is asserted in test_phase6_invariants). This test pins the code half.

_GRAMMAR_FILENAME = "grammar.yaml"


def _file_writes(tree: ast.AST) -> list[str]:
    """Every write-shaped call in a module: Path.write_text/write_bytes, or open(..., mode
    containing w/a/x). Read-only opens and `.read_text()` do not count."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"write_text", "write_bytes"}:
            hits.append(func.attr)
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if isinstance(mode, str) and any(m in mode for m in ("w", "a", "x")):
                hits.append(f"open(mode={mode!r})")
    return hits


def test_no_src_module_writes_grammar_yaml_at_runtime() -> None:
    """Hard rule #4 (post-freeze form): a module that names `config/grammar.yaml` may read it
    (loader, archive check, version audit, the CLI paths) but must contain no file-write call at
    all — the only way the grammar changes is a preregistered commit through the hooks."""
    import ast as _ast

    src_root = Path(__file__).resolve().parents[2] / "src" / "forge"
    offenders: dict[str, list[str]] = {}
    for py in sorted(src_root.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        if _GRAMMAR_FILENAME not in text:
            continue
        writes = _file_writes(_ast.parse(text))
        if writes:
            offenders[str(py.relative_to(src_root))] = writes
    assert not offenders, f"modules naming grammar.yaml that also write files: {offenders}"


# ---------------------------------------------------------------------------
# Soft sanity: pytest sanity that grammar_proposals indexes work
# ---------------------------------------------------------------------------


def test_grammar_proposals_table_accepts_loosen_and_tighten(tmp_path: Path) -> None:
    """The schema must allow both proposal types in the same DB."""
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        for ptype in ("loosen", "tighten", "add_rule", "remove_rule"):
            conn.execute(
                """
                INSERT INTO grammar_proposals
                    (proposal_id, proposed_at, proposal_type, proposal_yaml,
                     rationale, evidence_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    datetime(2026, 5, 13, tzinfo=UTC),
                    ptype,
                    "",
                    "r",
                    "{}",
                    "pending",
                ],
            )
        row = conn.execute("SELECT COUNT(*) FROM grammar_proposals").fetchone()
    assert row is not None
    assert row[0] == 4


# ---------------------------------------------------------------------------
# MappingProxyType use sentinel — defensive
# ---------------------------------------------------------------------------


def test_outcomes_tuple_is_iterable() -> None:
    """Defensive: BatchFeedback.outcomes uses a tuple, not a list, so
    `MappingProxyType` references in tests stay stable."""
    from forge.feedback.types import BatchFeedback

    bf = BatchFeedback(batch_id=uuid.uuid4(), submitted_count=0, outcomes=())
    assert isinstance(bf.outcomes, tuple)
    # No MappingProxyType used here yet, but the assertion guards the shape.
    _ = MappingProxyType({})


# ---------------------------------------------------------------------------
# Pytest fixture wiring — pytest's import of duckdb still works
# ---------------------------------------------------------------------------


def test_duckdb_constraint_exception_imports() -> None:
    """Defensive: the `submissions.config_hash` unique index relies on
    duckdb.ConstraintException being importable. If duckdb's surface
    changes this fails loud at import time, not at the first duplicate."""
    assert hasattr(duckdb, "ConstraintException")


# ---------------------------------------------------------------------------
# D051 — grammar_versions audit row landed for the active grammar
# ---------------------------------------------------------------------------


def test_ensure_grammar_version_recorded_lands_active_grammar(tmp_path: Path) -> None:
    """D051 / hard rule #10: after one round of self-healing, the
    `grammar_versions` table contains exactly one row for the active
    `config/grammar.yaml`. The D035 stuck-state-floor mechanism depends
    on this row existing; before D051 the table stayed empty under
    manual operator yaml bumps and the floor never reset on a grammar
    change."""
    from pathlib import Path as _Path

    from forge.grammar import load_grammar
    from forge.grammar.version_audit import ensure_grammar_version_recorded

    yaml_path = _Path(__file__).resolve().parents[2] / "config" / "grammar.yaml"
    archive_dir = yaml_path.parent / "grammar_archive"
    grammar = load_grammar(yaml_path, archive_dir=archive_dir)
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        ensure_grammar_version_recorded(
            conn,
            grammar=grammar,
            yaml_path=yaml_path,
            at=datetime(2026, 5, 18, tzinfo=UTC),
        )
        rows = conn.execute("SELECT version, rule_count FROM grammar_versions").fetchall()
    assert len(rows) == 1
    version, rule_count = rows[0]
    assert str(version) == grammar.grammar_version
    assert int(rule_count) == len(grammar.rules)


def test_campaign_run_calls_audit_row_helper() -> None:
    """D051: the production path must invoke the audit-row self-healer so manual operator yaml
    bumps don't silently skip the `grammar_versions` table. Re-targeted (Batch 5 G1) from the
    daemon's `_run_one_iteration` to `campaign/run.run_campaign` — the weekly run is the
    production loop now. Hard rule #10 + D035: the stuck-state floor reads
    `MAX(grammar_versions.changed_at)`; if the production path stops recording audit rows, the
    floor goes blind on the next manual bump."""
    import inspect

    from forge.campaign import run

    source = inspect.getsource(run.run_campaign)
    assert "ensure_grammar_version_recorded_silently" in source, (
        "run_campaign no longer calls ensure_grammar_version_recorded_silently; "
        "the D051 audit-row self-heal has been silently removed."
    )


# ---------------------------------------------------------------------------
# D052 — aged-out flush sentinel discipline
# ---------------------------------------------------------------------------


def test_aged_out_sentinel_is_nil_uuid() -> None:
    """D052: the sentinel `crucible_run_id` written by the aged-out flush
    must be the RFC-4122 nil UUID. The nil UUID is reserved by spec and
    cannot collide with a randomly generated Crucible run_id, so audit
    queries can filter aged-out rows via a single literal comparison.

    If this constant ever drifts to a different sentinel, callers that
    distinguish 'reached-via-join' from 'flushed-via-watermark' will
    silently break.
    """
    from forge.feedback.consumer import _AGED_OUT_SENTINEL_RUN_ID

    assert _AGED_OUT_SENTINEL_RUN_ID == "00000000-0000-0000-0000-000000000000"
    # Must parse as a valid UUID so the `crucible_run_id UUID` column
    # accepts it without coercion errors.
    assert uuid.UUID(_AGED_OUT_SENTINEL_RUN_ID).int == 0


def test_reconcile_all_pending_calls_aged_out_flush() -> None:
    """D052: `reconcile_all_pending` must invoke the aged-out flush before
    the per-batch join loop. Removing the call would re-introduce the
    P0-1 condition where D046's oldest-batch policy pins the loop forever
    on rows whose decisions have rolled off Crucible's export window."""
    import inspect

    from forge.feedback import consumer

    source = inspect.getsource(consumer.reconcile_all_pending)
    assert "_flush_aged_out_submissions" in source, (
        "reconcile_all_pending no longer calls _flush_aged_out_submissions"
        "; the D052 export-window low-watermark fallback has been removed."
    )


# ---------------------------------------------------------------------------
# D053 — counterfactual phase labeling at the proposer call site
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# D056 / P3-1 — hard rule #3 direct invariant: Crucible's promotion gate floors
# ---------------------------------------------------------------------------


def test_grammar_p4_per_trade_risk_max_within_contracts_ceiling() -> None:
    """D056 / hard rule #3: the grammar's P4 `sizer.per_trade_risk_pct.max`
    must never exceed `crucible_contracts.ABSOLUTE_MAX_PER_TRADE_RISK_PCT`.

    Before D056 this was only tested indirectly via rule #4's
    `apply_loosening` ban. The ban prevents an automated path from
    increasing the upper bound; it does NOT structurally enforce that
    the static grammar.yaml respects the contracts ceiling. A manual
    operator edit could in principle bump P4's max above 0.02 — the
    contracts validator would catch it on submission, but the rule-#3
    spirit ("never propose relaxations that lower the gate") asks us
    to floor it structurally at the grammar layer too."""
    import yaml as _yaml
    from crucible_contracts import ABSOLUTE_MAX_PER_TRADE_RISK_PCT

    yaml_path = Path(__file__).resolve().parents[2] / "config" / "grammar.yaml"
    raw = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    p4 = next(
        (r for r in raw["rules"] if r["id"] == "P4"),
        None,
    )
    assert p4 is not None, "grammar P4 (per_trade_risk_pct range) is missing"
    assert p4["predicate"]["type"] == "numerical_range"
    assert p4["predicate"]["field"] == "sizer.per_trade_risk_pct"
    assert p4["predicate"]["max"] <= ABSOLUTE_MAX_PER_TRADE_RISK_PCT, (
        f"grammar P4.max={p4['predicate']['max']} exceeds contracts cap "
        f"{ABSOLUTE_MAX_PER_TRADE_RISK_PCT}; violates hard rule #3"
    )


def test_enumerated_configs_respect_absolute_risk_caps(tmp_path: Path) -> None:
    """D056 / hard rule #3: every config Forge enumerates from the active
    grammar must respect both contracts ceilings (per-trade + concurrent).

    This is a roundtrip property test — the sampler produces a config,
    Pydantic validates against the SizerSpec field_validators, and we
    assert neither cap was exceeded. Pre-D056 the only check was the
    sampler-side bound on per-trade range (which depended on grammar.yaml
    being correct); if a grammar edit drifted, no test caught it."""
    from crucible_contracts import (
        ABSOLUTE_MAX_CONCURRENT_RISK_PCT,
        ABSOLUTE_MAX_PER_TRADE_RISK_PCT,
    )

    from forge.enumeration import enumerate_candidates
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry

    yaml_path = Path(__file__).resolve().parents[2] / "config" / "grammar.yaml"
    archive_dir = yaml_path.parent / "grammar_archive"
    grammar = load_grammar(yaml_path, archive_dir=archive_dir)
    registry = load_registry()
    n_checked = 0
    for cfg in enumerate_candidates(
        grammar,
        registry,
        seed=0xD056,
        max_candidates=50,
    ):
        assert cfg.sizer.per_trade_risk_pct <= ABSOLUTE_MAX_PER_TRADE_RISK_PCT
        assert cfg.sizer.max_concurrent_risk_pct <= ABSOLUTE_MAX_CONCURRENT_RISK_PCT
        n_checked += 1
    # Guard: the test should actually exercise the property, not silently
    # pass on an empty enumeration.
    assert n_checked > 0, "enumerate_candidates produced no configs to check"


# Suppress unused-import lint
_ = pytest
