"""Phase 5 invariants — feedback + grammar-refinement discipline.

Each invariant maps to a CLAUDE.md hard rule or a §8/§13 spec contract.
Owned by Phase 5; new constraints add tests here.
"""

from __future__ import annotations

import inspect
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

import duckdb
import pytest

from forge.feedback import analyzer, proposal_writer, proposer
from forge.feedback import auto_tune as auto_tune_mod
from forge.feedback.consumer import consume_batch_results
from forge.feedback.types import GrammarProposal
from forge.persistence.db import db_connection
from forge.prefilters import calibration as calibration_mod
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

# ---------------------------------------------------------------------------
# CLAUDE.md hard rule #4 (no apply_loosening) — structural
# ---------------------------------------------------------------------------


_LOOSEN_FORBIDDEN_NAMES = ("apply_loosening", "apply_loosen", "auto_apply_loosen")


def _module_function_names(module: object) -> set[str]:
    return {n for n, _ in inspect.getmembers(module, inspect.isfunction)}


def test_no_apply_loosening_in_prefilters_calibration() -> None:
    names = _module_function_names(calibration_mod)
    for forbidden in _LOOSEN_FORBIDDEN_NAMES:
        assert forbidden not in names, f"calibration exposes {forbidden}"


def test_no_apply_loosening_in_proposal_writer() -> None:
    names = _module_function_names(proposal_writer)
    for forbidden in _LOOSEN_FORBIDDEN_NAMES:
        assert forbidden not in names, f"proposal_writer exposes {forbidden}"


def test_no_apply_loosening_in_auto_tune() -> None:
    names = _module_function_names(auto_tune_mod)
    for forbidden in _LOOSEN_FORBIDDEN_NAMES:
        assert forbidden not in names, f"auto_tune exposes {forbidden}"


def test_no_apply_loosening_in_proposer() -> None:
    names = _module_function_names(proposer)
    for forbidden in _LOOSEN_FORBIDDEN_NAMES:
        assert forbidden not in names, f"proposer exposes {forbidden}"


def test_no_apply_loosening_in_analyzer() -> None:
    names = _module_function_names(analyzer)
    for forbidden in _LOOSEN_FORBIDDEN_NAMES:
        assert forbidden not in names, f"analyzer exposes {forbidden}"


# ---------------------------------------------------------------------------
# Phase 5 proposer fires only tighten-direction proposals
# ---------------------------------------------------------------------------


def test_phase5_proposer_only_emits_tighten_direction() -> None:
    """Loosening is reserved for the auto_tune module's calibration path
    (which writes to OPEN_PROPOSALS.md without applying). The proposer
    must never emit a loosen-direction GrammarProposal."""
    from forge.feedback.proposer import propose
    from forge.feedback.types import (
        AnalysisReport,
        BatchFeedback,
        GateFailureRow,
        PromotedPattern,
    )

    failures = (GateFailureRow(gate_name="g1", failure_count=20, failure_rate=1.0),)
    pattern = PromotedPattern(
        pattern_type="hypothesis_dominance",
        pattern={"hypothesis": "mean_reversion"},
        promoted_count=8,
        sample_size=8,
    )
    report = AnalysisReport(
        batch_id=uuid.uuid4(),
        promotion_rate=0.5,
        gate_failures=failures,
        hypothesis_metrics=(),
        promoted_patterns=(pattern,),
    )
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=20, outcomes=())
    proposals = propose(report, feedback, at=datetime(2026, 5, 13, tzinfo=UTC))
    assert proposals  # fixture should fire at least one
    assert all(p.is_loosen is False for p in proposals)


# ---------------------------------------------------------------------------
# §13.3 — every grammar.yaml-touching change writes a grammar_versions row
# ---------------------------------------------------------------------------


def test_auto_tune_tighten_writes_grammar_versions_audit_row(tmp_path: Path) -> None:
    """Hard rule #3: the auto-tune tighten path must write a
    grammar_versions row. Without that row the audit trail is broken."""
    from forge.feedback.auto_tune import auto_tune, write_calibration_yaml
    from forge.prefilters.calibration import (
        AutoTuneCalibration,
        Calibration,
        ExpectedTradeCountCalibration,
        NoveltyCalibration,
        PermutationTestCalibration,
        PredictedActivationsCalibration,
        RegimeExposureCalibration,
        SignalCorrelationCalibration,
        SignalDensityCalibration,
    )

    cal = Calibration(
        signal_density=SignalDensityCalibration(min_activations=30),
        expected_trade_count=ExpectedTradeCountCalibration(min_trades=50),
        predicted_activations=PredictedActivationsCalibration(min_entries=10),
        novelty=NoveltyCalibration(max_jaccard_overlap=0.80),
        signal_correlation=SignalCorrelationCalibration(max_jaccard_overlap=0.85),
        regime_exposure=RegimeExposureCalibration(max_single_regime_concentration=0.80),
        permutation_test=PermutationTestCalibration(
            n_permutations=100, p_value_threshold=0.10, forward_horizon_days=0
        ),
        auto_tune=AutoTuneCalibration(
            enabled=True,
            min_promotion_rate=0.005,
            max_promotion_rate=0.05,
            adjustment_pct_per_step=0.10,
            max_cumulative_adjustment=0.30,
        ),
    )
    yaml_path = tmp_path / "prefilter.yaml"
    write_calibration_yaml(cal, yaml_path)
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        # 2 batches > 5% promotion rate
        for _ in range(2):
            conn.execute(
                "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
                "grammar_version, registry_version, promotion_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    str(uuid.uuid4()),
                    100,
                    datetime(2026, 5, 13, tzinfo=UTC),
                    "v1",
                    "abc",
                    0.07,
                ],
            )
        auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=datetime(2026, 5, 13, tzinfo=UTC),
        )
        rows = conn.execute(
            "SELECT change_type, operator_initials FROM grammar_versions "
            "WHERE change_type = 'auto_tighten_calibration'"
        ).fetchall()
    assert len(rows) == 1
    # §13.3: auto changes have NULL operator_initials
    assert rows[0][1] is None


# ---------------------------------------------------------------------------
# §5.5 — cumulative cap structurally enforced
# ---------------------------------------------------------------------------


def test_auto_tune_does_not_exceed_cumulative_cap(tmp_path: Path) -> None:
    from forge.feedback.auto_tune import auto_tune, write_calibration_yaml
    from forge.prefilters.calibration import (
        AutoTuneCalibration,
        Calibration,
        ExpectedTradeCountCalibration,
        NoveltyCalibration,
        PermutationTestCalibration,
        PredictedActivationsCalibration,
        RegimeExposureCalibration,
        SignalCorrelationCalibration,
        SignalDensityCalibration,
    )

    cal = Calibration(
        signal_density=SignalDensityCalibration(min_activations=30),
        expected_trade_count=ExpectedTradeCountCalibration(min_trades=50),
        predicted_activations=PredictedActivationsCalibration(min_entries=10),
        novelty=NoveltyCalibration(max_jaccard_overlap=0.80),
        signal_correlation=SignalCorrelationCalibration(max_jaccard_overlap=0.85),
        regime_exposure=RegimeExposureCalibration(max_single_regime_concentration=0.80),
        permutation_test=PermutationTestCalibration(
            n_permutations=100, p_value_threshold=0.10, forward_horizon_days=0
        ),
        auto_tune=AutoTuneCalibration(
            enabled=True,
            min_promotion_rate=0.005,
            max_promotion_rate=0.05,
            adjustment_pct_per_step=0.10,
            max_cumulative_adjustment=0.30,
        ),
    )
    yaml_path = tmp_path / "prefilter.yaml"
    write_calibration_yaml(cal, yaml_path)
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        # Pre-populate 3 prior auto_tighten rows -> already at cap (0.30)
        for i in range(3):
            conn.execute(
                "INSERT INTO grammar_versions "
                "(version, rule_count, yaml_sha256, changed_at, change_type, "
                "change_description, operator_initials) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    f"calib_v{i}",
                    0,
                    "0" * 64,
                    datetime(2026, 5, 13, tzinfo=UTC),
                    "auto_tighten_calibration",
                    "step_pct=0.10",
                    None,
                ],
            )
        for _ in range(2):
            conn.execute(
                "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
                "grammar_version, registry_version, promotion_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    str(uuid.uuid4()),
                    100,
                    datetime(2026, 5, 13, tzinfo=UTC),
                    "v1",
                    "abc",
                    0.10,
                ],
            )
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=datetime(2026, 5, 13, tzinfo=UTC),
        )
        # No new auto_tighten row written (cap already met)
        rows = conn.execute(
            "SELECT COUNT(*) FROM grammar_versions WHERE change_type = 'auto_tighten_calibration'"
        ).fetchone()
    assert new_cal == cal
    assert rows is not None
    assert rows[0] == 3  # unchanged from pre-populated


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


def test_proposer_emits_one_proposal_per_trigger() -> None:
    """A sanity ceiling: number of proposals ≤ number of triggers in
    the input (one gate_failure row + one promoted_pattern + one cell)."""
    from forge.feedback.proposer import propose
    from forge.feedback.types import (
        AnalysisReport,
        BatchFeedback,
        GateFailureRow,
    )

    failures = (GateFailureRow(gate_name="g1", failure_count=10, failure_rate=1.0),)
    report = AnalysisReport(
        batch_id=uuid.uuid4(),
        promotion_rate=0.0,
        gate_failures=failures,
        hypothesis_metrics=(),
        promoted_patterns=(),
    )
    feedback = BatchFeedback(batch_id=report.batch_id, submitted_count=10, outcomes=())
    proposals = propose(report, feedback, at=datetime(2026, 5, 13, tzinfo=UTC))
    assert len(proposals) <= len(failures) + 0 + 0


# ---------------------------------------------------------------------------
# Refresh: the `GrammarProposal.is_loosen` property structurally distinguishes
# tighten from loosen — proposers/CLIs key off this not raw text comparison
# ---------------------------------------------------------------------------


def test_grammar_proposal_is_loosen_property_is_authoritative() -> None:
    """Defensive: future code that checks `p.proposal_type == 'loosen'`
    should use `p.is_loosen` instead so remove_rule is also caught."""
    for ptype, expected_loosen in (
        ("tighten", False),
        ("add_rule", False),
        ("loosen", True),
        ("remove_rule", True),
    ):
        p = GrammarProposal(
            proposal_id=uuid.uuid4(),
            proposed_at=datetime(2026, 5, 13, tzinfo=UTC),
            proposal_type=ptype,  # type: ignore[arg-type]
            target="grammar",
            proposal_yaml="",
            rationale="r",
            evidence_json={},
        )
        assert p.is_loosen is expected_loosen


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

    from forge.feedback.auto_tune import ensure_grammar_version_recorded
    from forge.grammar import load_grammar

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
        rows = conn.execute(
            "SELECT version, rule_count FROM grammar_versions"
        ).fetchall()
    assert len(rows) == 1
    version, rule_count = rows[0]
    assert str(version) == grammar.grammar_version
    assert int(rule_count) == len(grammar.rules)


def test_run_one_iteration_calls_audit_row_helper() -> None:
    """D051: `_run_one_iteration` in `cli/main.py` must invoke the audit-row
    self-healer so manual operator yaml bumps don't silently skip the
    `grammar_versions` table. This is the structural assertion that the
    contract is wired — pulling the call out without replacement would
    re-introduce the regression that D051 fixed.

    Hard rule #10 + D035: the stuck-state floor reads
    `MAX(grammar_versions.changed_at)`; if the production loop stops
    recording audit rows, the floor goes blind on the next manual bump.
    """
    import inspect

    from forge.cli import main

    source = inspect.getsource(main._run_one_iteration)
    assert "_ensure_grammar_version_recorded_silently" in source, (
        "_run_one_iteration no longer calls _ensure_grammar_version_recorded_silently"
        "; the D051 audit-row self-heal has been silently removed."
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


def test_enrich_and_append_proposals_writes_counterfactual_phase() -> None:
    """D053 / D054: the shared enrichment helper must stamp the phase +
    the phase-1 note into each proposal's evidence_json so operators
    reading OPEN_PROPOSALS.md know `counterfactual_rejection_rate=1.0`
    is a binary safety floor, not a real per-strategy measurement.

    Pulled out of `_consume_feedback_after_submit` in D054 — both the
    autonomous loop and manual `forge feedback` share one helper, so a
    single structural assertion here covers both call sites. A future
    refactor that drops the stamping would silently re-introduce the
    operator-facing noise that D053 fixed."""
    import inspect

    from forge.feedback import proposal_writer

    source = inspect.getsource(proposal_writer.enrich_and_append_proposals)
    assert "counterfactual_phase" in source, (
        "enrich_and_append_proposals no longer writes counterfactual_phase"
        " to evidence_json; D053 stamp has been removed."
    )
    assert "counterfactual_note" in source, (
        "enrich_and_append_proposals no longer writes counterfactual_note"
        " to evidence_json; D053 disclaimer has been removed."
    )


def test_forge_run_and_forge_feedback_share_enrichment_helper() -> None:
    """D054 / P1-2: `_consume_feedback_after_submit` (autonomous loop) and
    `cmd_feedback` (manual) must both call `enrich_and_append_proposals`.
    If either drifts to a direct `append_proposal` loop without the
    enrichment, the operator-facing diagnostic output silently diverges
    from the autonomous output."""
    import inspect

    from forge.cli import feedback_cmd, main

    loop_src = inspect.getsource(main._consume_feedback_after_submit)
    manual_src = inspect.getsource(feedback_cmd.cmd_feedback)
    assert "enrich_and_append_proposals" in loop_src, (
        "_consume_feedback_after_submit no longer calls "
        "enrich_and_append_proposals; loop bypasses D053+T2.5."
    )
    assert "enrich_and_append_proposals" in manual_src, (
        "cmd_feedback no longer calls enrich_and_append_proposals; "
        "manual `forge feedback` bypasses D053+T2.5."
    )


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
        grammar, registry, seed=0xD056, max_candidates=50,
    ):
        assert cfg.sizer.per_trade_risk_pct <= ABSOLUTE_MAX_PER_TRADE_RISK_PCT
        assert cfg.sizer.max_concurrent_risk_pct <= ABSOLUTE_MAX_CONCURRENT_RISK_PCT
        n_checked += 1
    # Guard: the test should actually exercise the property, not silently
    # pass on an empty enumeration.
    assert n_checked > 0, "enumerate_candidates produced no configs to check"


# Suppress unused-import lint
_ = pytest
