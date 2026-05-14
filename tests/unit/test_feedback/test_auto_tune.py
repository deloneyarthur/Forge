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

from forge.feedback.auto_tune import auto_tune, write_calibration_yaml
from forge.persistence.db import db_connection
from forge.prefilters.calibration import (
    AutoTuneCalibration,
    Calibration,
    ExpectedTradeCountCalibration,
    NoveltyCalibration,
    PermutationTestCalibration,
    RegimeExposureCalibration,
    SignalDensityCalibration,
)


def _default_calibration() -> Calibration:
    return Calibration(
        signal_density=SignalDensityCalibration(min_activations=30),
        expected_trade_count=ExpectedTradeCountCalibration(min_trades=50),
        novelty=NoveltyCalibration(max_jaccard_overlap=0.80),
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
