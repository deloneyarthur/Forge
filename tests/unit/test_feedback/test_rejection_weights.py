"""Tests for `forge.feedback.rejection_weights` (long-term #1)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
)

from forge.feedback.rejection_weights import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    compute_hypothesis_weights,
    prior_mean,
)
from forge.persistence.db import db_connection

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


def _config(hypothesis: str, name: str) -> StrategyConfig:
    return StrategyConfig(
        name=name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket="swing_short",
        underlying="SPY",
        tier=1,
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2",),
                params={"threshold": 30.0, "op": "<"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("realized_vol",),
                params={"threshold": 0.20, "op": "<"},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )


def _insert_submission(
    conn: Any,
    *,
    config: StrategyConfig,
    config_hash: str,
) -> None:
    conn.execute(
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            config.model_dump_json(),
            datetime.now(UTC),
            "submitted",
        ],
    )


def _gated_run(*, config_hash: str, promoted: bool) -> GatedRun:
    run_id = str(uuid.uuid4())
    gate_results = {
        "min_oos_trade_count": GateResult(
            gate_name="min_oos_trade_count",
            passed=True,
            value=42.0,
            threshold=30.0,
        ),
    }
    if not promoted:
        gate_results["sharpe_baseline"] = GateResult(
            gate_name="sharpe_baseline",
            passed=False,
            value=0.1,
            threshold=0.5,
        )
    return GatedRun(
        run=RunResult(
            run_id=run_id,
            config_hash=config_hash,
            metrics={"walk_forward_sharpe_median": 0.3 if not promoted else 1.2},
            trade_count=42,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
        ),
        decision=PromotionDecision(
            run_id=run_id,
            decision="promote" if promoted else "reject",
            gate_results=gate_results,
            decided_at=datetime.now(UTC),
            decided_by="test_evaluator/v1",
        ),
    )


def test_prior_mean_is_alpha_over_alpha_plus_beta() -> None:
    expected = DEFAULT_ALPHA / (DEFAULT_ALPHA + DEFAULT_BETA)
    assert prior_mean() == pytest.approx(expected)


def test_empty_gated_runs_returns_empty(tmp_path: Path) -> None:
    """Cold start: no gated_runs → empty weights → uniform sampling."""
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_hypothesis_weights(conn, []) == {}


def test_weights_track_promotion_rate(tmp_path: Path) -> None:
    """A hypothesis with 1/10 promotions gets higher weight than one with 0/10."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated_runs: list[GatedRun] = []
        # mean_reversion: 1 promoted / 10 total
        for i in range(10):
            cfg = _config("mean_reversion", f"mr_{i}")
            chash = f"mr_hash_{i:04d}"
            _insert_submission(conn, config=cfg, config_hash=chash)
            gated_runs.append(_gated_run(config_hash=chash, promoted=(i == 0)))
        # trend: 0 promoted / 10 total
        for i in range(10):
            cfg = _config("trend_continuation", f"tr_{i}")
            chash = f"tr_hash_{i:04d}"
            _insert_submission(conn, config=cfg, config_hash=chash)
            gated_runs.append(_gated_run(config_hash=chash, promoted=False))

        weights = compute_hypothesis_weights(conn, gated_runs)

    assert "mean_reversion" in weights
    assert "trend_continuation" in weights
    # mean_reversion = (1+1) / (1+10+10) = 2/21 ≈ 0.0952
    # trend = (1+0) / (1+10+10) = 1/21 ≈ 0.0476
    assert weights["mean_reversion"] > weights["trend_continuation"]
    assert weights["mean_reversion"] == pytest.approx(2 / 21, rel=1e-6)
    assert weights["trend_continuation"] == pytest.approx(1 / 21, rel=1e-6)


def test_submissions_without_gated_runs_are_ignored(tmp_path: Path) -> None:
    """A submission that hasn't been backtested yet contributes nothing."""
    with db_connection(tmp_path / "forge.db") as conn:
        for i in range(5):
            cfg = _config("mean_reversion", f"mr_{i}")
            _insert_submission(conn, config=cfg, config_hash=f"hash_{i}")
        # Only 2 of 5 have gated runs
        gated_runs = [
            _gated_run(config_hash="hash_0", promoted=True),
            _gated_run(config_hash="hash_1", promoted=False),
        ]
        weights = compute_hypothesis_weights(conn, gated_runs)
    # (1+1) / (1+10+2) = 2/13
    assert weights["mean_reversion"] == pytest.approx(2 / 13, rel=1e-6)


def test_gated_runs_without_matching_submission_are_ignored(tmp_path: Path) -> None:
    """A gated_run whose config_hash isn't in submissions contributes nothing."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated_runs = [_gated_run(config_hash="orphan_hash", promoted=True)]
        weights = compute_hypothesis_weights(conn, gated_runs)
    assert weights == {}


def test_alpha_beta_override(tmp_path: Path) -> None:
    """Caller can override the Bayesian prior for sensitivity analysis."""
    with db_connection(tmp_path / "forge.db") as conn:
        cfg = _config("mean_reversion", "mr_1")
        _insert_submission(conn, config=cfg, config_hash="hash_1")
        gated_runs = [_gated_run(config_hash="hash_1", promoted=True)]
        # No prior: 1/1 = 1.0
        weights = compute_hypothesis_weights(conn, gated_runs, alpha=0.0, beta=0.0)
        assert weights["mean_reversion"] == pytest.approx(1.0)
        # Strong prior: (1+1)/(1+9+1) = 2/11
        weights = compute_hypothesis_weights(conn, gated_runs, alpha=1.0, beta=9.0)
        assert weights["mean_reversion"] == pytest.approx(2 / 11, rel=1e-6)


def test_handles_corrupt_config_json_gracefully(tmp_path: Path) -> None:
    """A submission with non-dict / missing-hypothesis config_json is skipped."""
    with db_connection(tmp_path / "forge.db") as conn:
        # Real config
        cfg = _config("mean_reversion", "mr_1")
        _insert_submission(conn, config=cfg, config_hash="real_hash")
        # Corrupt config (missing hypothesis field)
        conn.execute(
            """
            INSERT INTO submissions
                (forge_candidate_id, forge_batch_id, config_hash, config_json,
                 submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "corrupt_hash",
                json.dumps({"not_a_config": True}),
                datetime.now(UTC),
                "submitted",
            ],
        )
        gated_runs = [
            _gated_run(config_hash="real_hash", promoted=True),
            _gated_run(config_hash="corrupt_hash", promoted=True),
        ]
        weights = compute_hypothesis_weights(conn, gated_runs)
    # Only the real config contributes
    assert weights == {"mean_reversion": pytest.approx(2 / 12, rel=1e-6)}
