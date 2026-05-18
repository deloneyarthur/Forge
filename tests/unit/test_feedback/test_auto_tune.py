"""Tests for feedback.auto_tune (Phase 5 module 7, D024/D4).

§5.5 auto-tune rule:
  - Rolling 2-batch promotion rate <0.5% → propose loosen (NOT applied;
    writes to OPEN_PROPOSALS.md per hard rule #4).
  - Rolling 2-batch promotion rate >5% → apply tighten, write yaml,
    write grammar_versions row.
  - Cumulative cap: 30% per direction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from forge.feedback.auto_tune import (
    auto_tune,
    ensure_grammar_version_recorded,
    write_calibration_yaml,
)
from forge.persistence.db import db_connection
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


def _default_calibration() -> Calibration:
    return Calibration(
        signal_density=SignalDensityCalibration(min_activations=30),
        expected_trade_count=ExpectedTradeCountCalibration(min_trades=50),
        predicted_activations=PredictedActivationsCalibration(min_entries=10),
        novelty=NoveltyCalibration(max_jaccard_overlap=0.80),
        signal_correlation=SignalCorrelationCalibration(max_jaccard_overlap=0.85),
        regime_exposure=RegimeExposureCalibration(max_single_regime_concentration=0.80),
        permutation_test=PermutationTestCalibration(n_permutations=100, p_value_threshold=0.10),
        auto_tune=AutoTuneCalibration(
            enabled=True,
            min_promotion_rate=0.005,
            max_promotion_rate=0.05,
            adjustment_pct_per_step=0.10,
            max_cumulative_adjustment=0.30,
        ),
    )


def _insert_batch_summary(
    db: object,
    *,
    promotion_rate: float,
    submitted_at: datetime,
    batch_id: uuid.UUID | None = None,
) -> uuid.UUID:
    bid = batch_id or uuid.uuid4()
    db.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO batch_summaries
            (forge_batch_id, batch_size, submitted_at, completed_at,
             promotion_rate, grammar_version, registry_version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [str(bid), 100, submitted_at, submitted_at, promotion_rate, "v1", "abc"],
    )
    return bid


_AT = datetime(2026, 5, 13, 12, tzinfo=UTC)


# ---------------------------------------------------------------------------
# No data → no action
# ---------------------------------------------------------------------------


def test_auto_tune_no_batches_returns_unchanged(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    with db_connection(forge_db) as conn:
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
    assert new_cal == cal


def test_auto_tune_single_batch_below_min_does_not_fire(tmp_path: Path) -> None:
    """Rolling window default is 2 batches — single batch isn't enough."""
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, promotion_rate=0.001, submitted_at=_AT)
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
    assert new_cal == cal


# ---------------------------------------------------------------------------
# Tighten path (auto-applies)
# ---------------------------------------------------------------------------


def test_auto_tune_tightens_when_rolling_rate_above_max(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, promotion_rate=0.06, submitted_at=_AT)
        _insert_batch_summary(conn, promotion_rate=0.07, submitted_at=_AT)
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
    # min_activations goes up by 10% (rounded)
    assert new_cal.signal_density.min_activations > cal.signal_density.min_activations
    # max_jaccard_overlap goes down by 10%
    assert new_cal.novelty.max_jaccard_overlap < cal.novelty.max_jaccard_overlap


def test_auto_tune_tighten_writes_yaml_back(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, promotion_rate=0.06, submitted_at=_AT)
        _insert_batch_summary(conn, promotion_rate=0.07, submitted_at=_AT)
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert (
        data["prefilter"]["signal_density"]["min_activations"]
        == new_cal.signal_density.min_activations
    )


def test_auto_tune_tighten_writes_grammar_versions_row(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, promotion_rate=0.06, submitted_at=_AT)
        _insert_batch_summary(conn, promotion_rate=0.07, submitted_at=_AT)
        auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
        row = conn.execute(
            "SELECT change_type, operator_initials FROM grammar_versions "
            "ORDER BY changed_at DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row[0] == "auto_tighten_calibration"
    # §13.3: auto changes have NULL operator_initials
    assert row[1] is None


# ---------------------------------------------------------------------------
# Loosen path (does NOT apply; writes to OPEN_PROPOSALS.md)
# ---------------------------------------------------------------------------


def test_auto_tune_loosen_writes_proposal_but_does_not_apply(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    open_proposals = tmp_path / "OPEN_PROPOSALS.md"
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, promotion_rate=0.001, submitted_at=_AT)
        _insert_batch_summary(conn, promotion_rate=0.002, submitted_at=_AT)
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=open_proposals,
            at=_AT,
        )
    # Calibration unchanged
    assert new_cal == cal
    # Proposal markdown exists
    assert open_proposals.exists()
    content = open_proposals.read_text(encoding="utf-8")
    assert "loosen" in content
    # And a row in grammar_proposals
    with db_connection(forge_db) as conn:
        row = conn.execute(
            "SELECT proposal_type, status FROM grammar_proposals ORDER BY proposed_at DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row[0] == "loosen"
    assert row[1] == "pending"


# ---------------------------------------------------------------------------
# In-band (no action)
# ---------------------------------------------------------------------------


def test_auto_tune_no_action_when_in_band(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    with db_connection(forge_db) as conn:
        _insert_batch_summary(conn, promotion_rate=0.02, submitted_at=_AT)
        _insert_batch_summary(conn, promotion_rate=0.02, submitted_at=_AT)
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
    assert new_cal == cal


# ---------------------------------------------------------------------------
# Cumulative cap
# ---------------------------------------------------------------------------


def test_auto_tune_respects_cumulative_cap(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    yaml_path = tmp_path / "prefilter.yaml"
    cal = _default_calibration()
    write_calibration_yaml(cal, yaml_path)
    # Pre-populate grammar_versions with 3 prior auto_tighten rows (3 * 0.10 = 0.30)
    with db_connection(forge_db) as conn:
        for i in range(3):
            conn.execute(
                "INSERT INTO grammar_versions "
                "(version, rule_count, yaml_sha256, changed_at, change_type, "
                "change_description, operator_initials) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    f"calib_v{i}",
                    0,
                    "0" * 64,
                    _AT,
                    "auto_tighten_calibration",
                    "step_pct=0.10",
                    None,
                ],
            )
        _insert_batch_summary(conn, promotion_rate=0.06, submitted_at=_AT)
        _insert_batch_summary(conn, promotion_rate=0.07, submitted_at=_AT)
        new_cal = auto_tune(
            db=conn,
            calibration=cal,
            prefilter_yaml_path=yaml_path,
            open_proposals_path=tmp_path / "OPEN_PROPOSALS.md",
            at=_AT,
        )
    # At-cap: should be a no-op (cumulative already 0.30; next step would
    # exceed max_cumulative_adjustment)
    assert new_cal == cal


# ---------------------------------------------------------------------------
# Hard rule #4 analogue
# ---------------------------------------------------------------------------


def test_no_apply_loosening_function_in_module() -> None:
    """The auto_tune module must not expose a loosen-direction
    application path. Loosenings only ever route through proposal_writer."""
    import inspect

    from forge.feedback import auto_tune as at_mod

    members = inspect.getmembers(at_mod, inspect.isfunction)
    names = {n for n, _ in members}
    assert "apply_loosening" not in names
    assert "apply_loosen" not in names


# ---------------------------------------------------------------------------
# D051 — ensure_grammar_version_recorded self-healing audit row
# ---------------------------------------------------------------------------


def _real_grammar() -> tuple[object, Path]:
    """Load the project's actual `config/grammar.yaml` for D051 tests.

    The helper needs a real `Grammar` object (with `grammar_version` +
    `rules`) and the matching on-disk yaml file for the sha256 hash.
    Using the production yaml keeps the test honest — if the grammar
    archive becomes inconsistent, this test fails alongside the loader.
    """
    from forge.grammar import load_grammar

    yaml_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = yaml_path.parent / "grammar_archive"
    grammar = load_grammar(yaml_path, archive_dir=archive_dir)
    return grammar, yaml_path


def test_ensure_grammar_version_writes_row_when_missing(tmp_path: Path) -> None:
    """D051: an empty `grammar_versions` table gets a `manual_bump` row
    matching the active grammar on first call."""
    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    with db_connection(forge_db) as conn:
        # Pre-condition: table is empty.
        rows = conn.execute("SELECT COUNT(*) FROM grammar_versions").fetchone()
        assert rows[0] == 0
        wrote = ensure_grammar_version_recorded(
            conn,
            grammar=grammar,
            yaml_path=yaml_path,
            at=_AT,
        )
        assert wrote is True
        # Post-condition: exactly one row, matching the active grammar.
        result = conn.execute(
            "SELECT version, change_type, rule_count, yaml_sha256 FROM grammar_versions"
        ).fetchall()
    assert len(result) == 1
    version, change_type, rule_count, sha = result[0]
    assert str(version) == grammar.grammar_version
    assert str(change_type) == "manual_bump"
    assert int(rule_count) == len(grammar.rules)
    # sha256 is 64 lowercase hex chars and matches the on-disk yaml.
    import hashlib

    expected_sha = hashlib.sha256(yaml_path.read_bytes()).hexdigest()
    assert str(sha) == expected_sha


def test_ensure_grammar_version_is_idempotent(tmp_path: Path) -> None:
    """D051: a second call after the row exists is a SELECT-only no-op."""
    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    with db_connection(forge_db) as conn:
        first = ensure_grammar_version_recorded(
            conn, grammar=grammar, yaml_path=yaml_path, at=_AT
        )
        second = ensure_grammar_version_recorded(
            conn, grammar=grammar, yaml_path=yaml_path, at=_AT
        )
        count = conn.execute("SELECT COUNT(*) FROM grammar_versions").fetchone()
    assert first is True
    assert second is False
    assert count[0] == 1


def test_ensure_grammar_version_skips_when_existing_row_present(tmp_path: Path) -> None:
    """D051: an existing row for the active grammar (e.g. written by an earlier
    apply-proposal) is left intact — the self-healing helper never overwrites."""
    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    with db_connection(forge_db) as conn:
        conn.execute(
            """
            INSERT INTO grammar_versions
                (version, rule_count, yaml_sha256, changed_at, change_type,
                 change_description, operator_initials)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                grammar.grammar_version,
                42,
                "f" * 64,
                _AT,
                "apply_proposal",
                "explicit operator-driven entry",
                "AJ",
            ],
        )
        wrote = ensure_grammar_version_recorded(
            conn, grammar=grammar, yaml_path=yaml_path, at=_AT
        )
        rows = conn.execute(
            "SELECT change_type, rule_count, operator_initials FROM grammar_versions"
        ).fetchall()
    assert wrote is False
    assert len(rows) == 1
    change_type, rule_count, initials = rows[0]
    # The pre-existing row is untouched — not overwritten with manual_bump.
    assert str(change_type) == "apply_proposal"
    assert int(rule_count) == 42
    assert str(initials) == "AJ"


# ---------------------------------------------------------------------------
# D058 / P3-3 — ensure_grammar_version_recorded idempotency under writer race
# ---------------------------------------------------------------------------


def test_d058_ensure_grammar_version_no_duplicate_under_concurrent_writers(
    tmp_path: Path,
) -> None:
    """D058 / P3-3: two concurrent processes (autonomous loop +
    operator-driven `cmd_apply_proposal`/`cmd_revert`) could in principle
    both observe an empty `grammar_versions` table for the active version,
    then both INSERT — producing two rows. The `version VARCHAR(20)
    PRIMARY KEY` constraint catches that and raises ConstraintException
    on the loser's INSERT. This test pins the contract:

      Outcome A — winner-loser sequence: exactly one row lands; the
      loser either returns False (SELECT-then-INSERT but the row exists)
      OR raises a ConstraintException (race on INSERT). Either way the
      DB stays consistent.

      Outcome B — table never grows beyond 1 row for the version.

    Pre-D058 the helper had no race-condition test — D051's idempotency
    test was sequential. A future refactor that switched from
    SELECT-then-INSERT to a different idempotency mechanism (e.g.,
    INSERT-OR-IGNORE) would risk silently dropping the audit row; this
    test ensures the contract holds whichever mechanism is chosen.
    """
    import threading

    import duckdb

    forge_db = tmp_path / "forge.db"
    grammar, yaml_path = _real_grammar()
    # Initialize schema with one ephemeral connection so concurrent
    # writers don't race on schema creation.
    with db_connection(forge_db):
        pass

    barrier = threading.Barrier(2)
    results: list[tuple[bool | None, str | None]] = [(None, None), (None, None)]

    def _worker(idx: int) -> None:
        try:
            conn = duckdb.connect(str(forge_db))
            try:
                barrier.wait(timeout=5.0)
                wrote = ensure_grammar_version_recorded(
                    conn, grammar=grammar, yaml_path=yaml_path, at=_AT,
                )
                results[idx] = (wrote, None)
            finally:
                conn.close()
        except duckdb.ConstraintException as exc:
            results[idx] = (None, f"constraint: {exc}")
        except duckdb.Error as exc:
            results[idx] = (None, f"duckdb: {exc}")

    t0 = threading.Thread(target=_worker, args=(0,))
    t1 = threading.Thread(target=_worker, args=(1,))
    t0.start()
    t1.start()
    t0.join(timeout=10.0)
    t1.join(timeout=10.0)

    with db_connection(forge_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM grammar_versions WHERE version = ?",
            [grammar.grammar_version],
        ).fetchone()[0]
    assert count == 1, f"expected exactly 1 row for {grammar.grammar_version}, got {count}"
    # At least one writer succeeded (wrote=True OR rolled-back via
    # ConstraintException). Both returning (False, None) would mean
    # neither thought it needed to insert — which only happens if the
    # row already existed when both started, contradicting our fresh-db
    # setup.
    saw_success = any(r[0] is True for r in results)
    saw_constraint = any(r[1] is not None and "constraint" in r[1] for r in results)
    saw_loser_noop = any(r[0] is False for r in results)
    assert saw_success, f"no writer reported success: {results}"
    assert saw_constraint or saw_loser_noop, (
        f"expected one writer to either skip (False) or hit constraint, got: {results}"
    )
