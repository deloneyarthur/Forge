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
    DEFAULT_EXPLORATION_FLOOR,
    apply_exploration_floor,
    apply_orthogonal_family_floor,
    compute_hypothesis_reward_weights,
    compute_hypothesis_weights,
    compute_relative_value_regime_weights,
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


# ---------------------------------------------------------------------------
# D067 — exploration floor (cold-start death-spiral guard)
# ---------------------------------------------------------------------------

_CANONICAL = (
    "trend_continuation",
    "mean_reversion",
    "regime_arbitrage",
    "relative_value",
    "volatility_event",
)


def test_d067_floor_bumps_observed_below_floor() -> None:
    """Observed-but-low hypotheses get floored. The 0.003/0.004 weights
    that starved relative_value + regime_arbitrage become 0.05 floor."""
    raw = {
        "regime_arbitrage": 0.004,
        "relative_value": 0.003,
        "volatility_event": 0.048,
    }
    out = apply_exploration_floor(raw, hypotheses=_CANONICAL)
    assert out["regime_arbitrage"] == DEFAULT_EXPLORATION_FLOOR
    assert out["relative_value"] == DEFAULT_EXPLORATION_FLOOR
    assert out["volatility_event"] == DEFAULT_EXPLORATION_FLOOR


def test_d067_floor_preserves_observed_above_floor() -> None:
    """A hypothesis whose posterior is above the floor passes through."""
    raw = {"trend_continuation": 0.123}
    out = apply_exploration_floor(raw, hypotheses=_CANONICAL)
    assert out["trend_continuation"] == pytest.approx(0.123)


def test_d067_unobserved_uses_fallback_then_floor() -> None:
    """Hypotheses missing from `weights` take the fallback (typically the
    Beta prior ~0.091, which is above the floor). The floor still applies
    if the fallback is below it."""
    raw: dict[str, float] = {}
    out_prior = apply_exploration_floor(
        raw,
        hypotheses=_CANONICAL,
        fallback=prior_mean(),
    )
    # prior_mean() = 1/11 ≈ 0.0909 > floor 0.05, so the prior wins.
    for h in _CANONICAL:
        assert out_prior[h] == pytest.approx(prior_mean())

    out_floor_only = apply_exploration_floor(raw, hypotheses=_CANONICAL)
    for h in _CANONICAL:
        assert out_floor_only[h] == DEFAULT_EXPLORATION_FLOOR


def test_d067_all_canonical_hypotheses_always_present() -> None:
    """Even when `weights` is sparse, the returned dict contains every
    canonical hypothesis. This is the property the cold-start spiral
    relied on being violated: with raw `compute_hypothesis_weights`,
    unobserved hypotheses were silently absent — D063 surfaced this and
    D067 ensures they're always represented in the sampler input."""
    sparse = {"volatility_event": 0.05}
    out = apply_exploration_floor(
        sparse,
        hypotheses=_CANONICAL,
        fallback=prior_mean(),
    )
    assert set(out) == set(_CANONICAL)


def test_d067_custom_floor_threshold() -> None:
    """Floor is a tunable parameter; pin the math at non-default values."""
    raw = {"regime_arbitrage": 0.001}
    out = apply_exploration_floor(
        raw,
        hypotheses=_CANONICAL,
        floor=0.10,
        fallback=prior_mean(),
    )
    # regime_arbitrage floored from 0.001 → 0.10
    assert out["regime_arbitrage"] == pytest.approx(0.10)
    # prior_mean ≈ 0.091 < 0.10, so unobserved gets the higher floor.
    assert out["trend_continuation"] == pytest.approx(0.10)


# --- Layer-2 orthogonal-family floor-lift (decorrelated-supply lever) ---
# docs/proposals/orthogonal-family-supply-for-pbo.md §3 Layer 2. The learned
# component-rate estimand starves the one PBO-orthogonal family (single-name
# volatility_event, Crucible-validated 2026-06-29 as the in-v1 second factor)
# to the D067 5% floor while the 0.78-correlated trend~mr core oscillates at
# the top. This lever lifts a bounded, explicit floor for the named families.


def test_orthogonal_family_floor_empty_map_is_identity() -> None:
    """Flag OFF (empty floor map) → the returned weights equal the input
    exactly. Hard rule 6 cold path: the sampler draw is a pure function of the
    numeric weights, so identical values ⇒ byte-identical emitted sequence."""
    raw = {"trend_continuation": 1.0, "mean_reversion": 0.17, "volatility_event": 0.05}
    out = apply_orthogonal_family_floor(raw, {})
    assert out == raw
    assert out is not raw  # a copy — never mutate the caller's learned map


def test_orthogonal_family_floor_lifts_named_family() -> None:
    """A named family below its floor is raised to it; the correlated core is
    untouched (only its sampling SHARE drops, via rng.choices normalization)."""
    raw = {"trend_continuation": 1.0, "mean_reversion": 0.17, "volatility_event": 0.05}
    out = apply_orthogonal_family_floor(raw, {"volatility_event": 0.20})
    assert out["volatility_event"] == pytest.approx(0.20)
    assert out["trend_continuation"] == pytest.approx(1.0)
    assert out["mean_reversion"] == pytest.approx(0.17)


def test_orthogonal_family_floor_never_lowers_a_family() -> None:
    """`max` semantics: a family already above its floor passes through
    unchanged — the lever only ever RAISES an orthogonal family, never starves."""
    raw = {"volatility_event": 0.42}
    out = apply_orthogonal_family_floor(raw, {"volatility_event": 0.20})
    assert out["volatility_event"] == pytest.approx(0.42)


def test_orthogonal_family_floor_ignores_unknown_family() -> None:
    """A floor for a family absent from the learned weights is ignored — the
    lever never introduces a non-samplable hypothesis into the draw."""
    raw = {"trend_continuation": 1.0}
    out = apply_orthogonal_family_floor(raw, {"not_a_hypothesis": 0.5})
    assert out == raw


def test_orthogonal_family_floor_multiple_families() -> None:
    """Several orthogonal families can be lifted at once; each independent."""
    raw = {"trend_continuation": 1.0, "volatility_event": 0.05, "relative_value": 0.05}
    out = apply_orthogonal_family_floor(raw, {"volatility_event": 0.20, "relative_value": 0.10})
    assert out["volatility_event"] == pytest.approx(0.20)
    assert out["relative_value"] == pytest.approx(0.10)
    assert out["trend_continuation"] == pytest.approx(1.0)


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


# ---------------------------------------------------------------------------
# Multi-class reward weighting — improvement-plan Phase 2 (item 3 / D094).
#
# `compute_hypothesis_weights` learns ONLY from promotions; with 0 promotions
# across the cohort it returns a flat trial-count decay (every hypothesis
# ~equal), so the enumerator has no gradient toward configs that even trade.
# `compute_hypothesis_reward_weights` generalizes the Beta-posterior mean to a
# graded per-run reward from the signals that DO vary today: trade-production
# (the binding `min_oos_trade_count` constraint) and gate-progress. Promotion
# stays the ceiling (reward 1.0) so the signal transitions smoothly once
# promotions appear.
# ---------------------------------------------------------------------------


def _gated_run_graded(
    *,
    config_hash: str,
    trade_count: int,
    gates_passed: int,
    gates_failed: int,
    decision: str = "reject",
    wf_sharpe: float | None = None,
) -> GatedRun:
    """Build a GatedRun with explicit trade_count + gate pass/fail counts.

    ``decision='promote'`` requires ``gates_failed == 0`` — the contracts
    PromotionDecision validator forbids a promote with any failed gate.

    ``wf_sharpe`` (D101): when set, populates
    ``metrics['walk_forward_sharpe_median']`` so the Sharpe-aware reward term
    is exercised; ``None`` leaves ``metrics`` empty (no Sharpe credit).
    """
    run_id = str(uuid.uuid4())
    gate_results: dict[str, GateResult] = {}
    for i in range(gates_passed):
        gate_results[f"gate_pass_{i}"] = GateResult(gate_name=f"gate_pass_{i}", passed=True)
    for i in range(gates_failed):
        gate_results[f"gate_fail_{i}"] = GateResult(gate_name=f"gate_fail_{i}", passed=False)
    metrics = {} if wf_sharpe is None else {"walk_forward_sharpe_median": wf_sharpe}
    return GatedRun(
        run=RunResult(
            run_id=run_id,
            config_hash=config_hash,
            metrics=metrics,
            trade_count=trade_count,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
        ),
        decision=PromotionDecision(
            run_id=run_id,
            decision=decision,  # type: ignore[arg-type]
            gate_results=gate_results,
            decided_at=datetime.now(UTC),
            decided_by="test_evaluator/v1",
        ),
    )


def test_reward_weights_empty_returns_empty(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_hypothesis_reward_weights(conn, []) == {}


def test_reward_weights_trading_beats_zero_trading_at_zero_promotions(tmp_path: Path) -> None:
    """THE core behavior: with 0 promotions, a hypothesis whose runs TRADE must
    outweigh one whose runs all ZERO-TRADE. The promotion-only weighter rates
    them equal — that flat gradient is the bug this fixes."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated_runs: list[GatedRun] = []
        for i in range(10):  # regime_arbitrage: trades (50), reject, 1/2 gates
            cfg = _config("regime_arbitrage", f"ra_{i}")
            chash = f"ra_hash_{i:04d}"
            _insert_submission(conn, config=cfg, config_hash=chash)
            gated_runs.append(
                _gated_run_graded(config_hash=chash, trade_count=50, gates_passed=1, gates_failed=1)
            )
        for i in range(10):  # relative_value: zero-trade, reject, 0/2 gates
            cfg = _config("relative_value", f"rv_{i}")
            chash = f"rv_hash_{i:04d}"
            _insert_submission(conn, config=cfg, config_hash=chash)
            gated_runs.append(
                _gated_run_graded(config_hash=chash, trade_count=0, gates_passed=0, gates_failed=2)
            )
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
        promo_only = compute_hypothesis_weights(conn, gated_runs)

    # trading run reward = 0.5*1 + 0.2*0.5 + 0.3*0(no sharpe metric) = 0.6 → Σ=6
    assert reward["regime_arbitrage"] == pytest.approx(7 / 21, rel=1e-6)
    # zero-trade run reward = 0 → (1+0)/21
    assert reward["relative_value"] == pytest.approx(1 / 21, rel=1e-6)
    assert reward["regime_arbitrage"] > reward["relative_value"]
    # contrast: the promotion-only weighter rates the two identically (both 1/21)
    assert promo_only["regime_arbitrage"] == pytest.approx(promo_only["relative_value"])


def test_reward_weights_promotion_is_ceiling(tmp_path: Path) -> None:
    """A promoted run scores the max reward (1.0); a trading-but-failing run
    scores less, so a promoting hypothesis outweighs a merely-trading one."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(
            conn, config=_config("volatility_event", "ve_p"), config_hash="promo_hash"
        )
        _insert_submission(
            conn, config=_config("trend_continuation", "tc_t"), config_hash="trade_hash"
        )
        gated_runs = [
            _gated_run_graded(
                config_hash="promo_hash",
                decision="promote",
                trade_count=100,
                gates_passed=4,
                gates_failed=0,
            ),
            _gated_run_graded(
                config_hash="trade_hash",
                decision="reject",
                trade_count=100,
                gates_passed=1,
                gates_failed=3,
            ),
        ]
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    # promoted reward 1.0 → (1+1)/12 ; trading-partial 0.5+0.2*0.25+0=0.55 → (1+0.55)/12
    assert reward["volatility_event"] == pytest.approx(2 / 12, rel=1e-6)
    assert reward["trend_continuation"] == pytest.approx(1.55 / 12, rel=1e-6)
    assert reward["volatility_event"] > reward["trend_continuation"]


def test_reward_weights_gate_progress_gradient(tmp_path: Path) -> None:
    """Two trading, non-promoting hypotheses: more gates passed → higher weight."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(
            conn, config=_config("regime_arbitrage", "ra_more"), config_hash="more_hash"
        )
        _insert_submission(
            conn, config=_config("mean_reversion", "mr_less"), config_hash="less_hash"
        )
        gated_runs = [
            _gated_run_graded(
                config_hash="more_hash", trade_count=50, gates_passed=3, gates_failed=1
            ),
            _gated_run_graded(
                config_hash="less_hash", trade_count=50, gates_passed=1, gates_failed=3
            ),
        ]
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    # more: 0.5+0.2*0.75+0=0.65 → (1+0.65)/12 ; less: 0.5+0.2*0.25+0=0.55 → (1+0.55)/12
    assert reward["regime_arbitrage"] == pytest.approx(1.65 / 12, rel=1e-6)
    assert reward["mean_reversion"] == pytest.approx(1.55 / 12, rel=1e-6)
    assert reward["regime_arbitrage"] > reward["mean_reversion"]


def test_reward_weights_in_unit_interval(tmp_path: Path) -> None:
    """Reward-smoothed weights stay in (0, 1) like the promotion-only version,
    so apply_exploration_floor's semantics are unchanged."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated_runs: list[GatedRun] = []
        for i in range(5):
            chash = f"ra_{i:04d}"
            _insert_submission(
                conn, config=_config("regime_arbitrage", f"ra_{i}"), config_hash=chash
            )
            gated_runs.append(
                _gated_run_graded(
                    config_hash=chash,
                    decision="promote",
                    trade_count=99,
                    gates_passed=5,
                    gates_failed=0,
                )
            )
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    assert 0.0 < reward["regime_arbitrage"] < 1.0


def test_reward_weights_orphan_runs_ignored(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        gated_runs = [
            _gated_run_graded(config_hash="orphan", trade_count=50, gates_passed=2, gates_failed=0)
        ]
        assert compute_hypothesis_reward_weights(conn, gated_runs) == {}


def test_reward_weights_alpha_beta_override(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("mean_reversion", "mr_1"), config_hash="hash_1")
        gated_runs = [
            _gated_run_graded(
                config_hash="hash_1",
                decision="promote",
                trade_count=100,
                gates_passed=3,
                gates_failed=0,
            )
        ]
        # No prior, one max-reward run → 1.0 / 1.0 = 1.0
        weights = compute_hypothesis_reward_weights(conn, gated_runs, alpha=0.0, beta=0.0)
        assert weights["mean_reversion"] == pytest.approx(1.0)


def test_reward_weights_custom_knobs(tmp_path: Path) -> None:
    """Trade-production / gate-progress split is tunable; pin the math."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("regime_arbitrage", "ra_1"), config_hash="hash_1")
        # trade-only weighting: a trading reject with 0 gates passed → reward 1.0
        gated_runs = [
            _gated_run_graded(config_hash="hash_1", trade_count=10, gates_passed=0, gates_failed=4)
        ]
        weights = compute_hypothesis_reward_weights(
            conn, gated_runs, trade_production_weight=1.0, gate_progress_weight=0.0
        )
    # reward = 1.0*1 + 0.0*0 = 1.0 → (1+1)/(1+10+1) = 2/12
    assert weights["regime_arbitrage"] == pytest.approx(2 / 12, rel=1e-6)


def test_reward_weights_deterministic(tmp_path: Path) -> None:
    """Hard rule #6: same (submissions, gated_runs) snapshot → identical weights."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated_runs: list[GatedRun] = []
        for i in range(6):
            chash = f"ve_{i:04d}"
            _insert_submission(
                conn, config=_config("volatility_event", f"ve_{i}"), config_hash=chash
            )
            gated_runs.append(
                _gated_run_graded(
                    config_hash=chash,
                    trade_count=i * 7,
                    gates_passed=i % 3,
                    gates_failed=3 - (i % 3),
                )
            )
        first = compute_hypothesis_reward_weights(conn, gated_runs)
        second = compute_hypothesis_reward_weights(conn, gated_runs)
    assert first == second


def test_reward_weights_corrupt_config_skipped(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("mean_reversion", "mr_1"), config_hash="real_hash")
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
            _gated_run_graded(
                config_hash="real_hash",
                decision="promote",
                trade_count=100,
                gates_passed=2,
                gates_failed=0,
            ),
            _gated_run_graded(
                config_hash="corrupt_hash",
                decision="promote",
                trade_count=100,
                gates_passed=2,
                gates_failed=0,
            ),
        ]
        weights = compute_hypothesis_reward_weights(conn, gated_runs)
    assert weights == {"mean_reversion": pytest.approx(2 / 12, rel=1e-6)}


# ---------------------------------------------------------------------------
# D101 — Sharpe-aware reward: the reward gradient now climbs the gate's failing
# axis (walk_forward_sharpe_median), not just trade-production + generic
# gate-progress. Default split is 0.5 trade + 0.2 gate + 0.3 sharpe (Σ=1.0).
# ---------------------------------------------------------------------------


def test_reward_weights_higher_sharpe_outweighs_lower(tmp_path: Path) -> None:
    """Among trading, equally-gated, non-promoting runs, higher
    walk_forward_sharpe_median earns a higher reward → the enumerator tilts
    toward the gate's failing axis."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("volatility_event", "hi"), config_hash="hi_hash")
        _insert_submission(conn, config=_config("trend_continuation", "lo"), config_hash="lo_hash")
        gated_runs = [
            _gated_run_graded(
                config_hash="hi_hash",
                trade_count=50,
                gates_passed=2,
                gates_failed=2,
                wf_sharpe=2.0,
            ),
            _gated_run_graded(
                config_hash="lo_hash",
                trade_count=50,
                gates_passed=2,
                gates_failed=2,
                wf_sharpe=0.0,
            ),
        ]
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    # hi: 0.5 + 0.2*0.5 + 0.3*clamp(2.0/2.0)=0.5+0.1+0.3=0.9 → (1+0.9)/12
    # lo: 0.5 + 0.2*0.5 + 0.3*clamp(0.0/2.0)=0.5+0.1+0.0=0.6 → (1+0.6)/12
    assert reward["volatility_event"] == pytest.approx(1.9 / 12, rel=1e-6)
    assert reward["trend_continuation"] == pytest.approx(1.6 / 12, rel=1e-6)
    assert reward["volatility_event"] > reward["trend_continuation"]


def test_reward_weights_sharpe_only_credited_when_traded(tmp_path: Path) -> None:
    """A zero-trade run gets no Sharpe credit even if a (stale) metric is present
    — the Sharpe of a non-trading strategy is meaningless."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("mean_reversion", "z"), config_hash="z_hash")
        gated_runs = [
            _gated_run_graded(
                config_hash="z_hash",
                trade_count=0,
                gates_passed=0,
                gates_failed=2,
                wf_sharpe=2.0,  # present but must NOT be credited (zero-trade)
            )
        ]
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    # not traded → 0.5*0 + 0.2*0 + 0.3*0 = 0 → (1+0)/12
    assert reward["mean_reversion"] == pytest.approx(1 / 12, rel=1e-6)


def test_reward_weights_missing_sharpe_metric_no_credit(tmp_path: Path) -> None:
    """A traded run lacking walk_forward_sharpe_median gets 0 Sharpe credit (no
    crash, no default credit) — the Sharpe term simply drops out."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("trend_continuation", "m"), config_hash="m_hash")
        gated_runs = [
            _gated_run_graded(
                config_hash="m_hash", trade_count=50, gates_passed=2, gates_failed=2
            )  # no wf_sharpe → metrics {}
        ]
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    # traded, 2/4 gates, no sharpe → 0.5 + 0.2*0.5 + 0 = 0.6 → (1+0.6)/12
    assert reward["trend_continuation"] == pytest.approx(1.6 / 12, rel=1e-6)


def test_reward_weights_sharpe_clamped_to_unit(tmp_path: Path) -> None:
    """walk_forward_sharpe_median above the ceiling clamps to 1.0; the blended
    reward stays in [0,1] (weights sum to 1.0, so floor semantics hold)."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("volatility_event", "x"), config_hash="x_hash")
        gated_runs = [
            _gated_run_graded(
                config_hash="x_hash",
                trade_count=99,
                gates_passed=3,
                gates_failed=1,
                wf_sharpe=5.0,  # >> ceiling 2.0 → clamps to 1.0
            )
        ]
        reward = compute_hypothesis_reward_weights(conn, gated_runs)
    # 0.5 + 0.2*0.75 + 0.3*clamp(5/2)=0.5+0.15+0.3=0.95 → (1+0.95)/12
    assert reward["volatility_event"] == pytest.approx(1.95 / 12, rel=1e-6)
    assert 0.0 < reward["volatility_event"] < 1.0


# ---------------------------------------------------------------------------
# D103 (v9) — dynamic relative_value regime-gate curation — FROZEN by D119.
# D103 learned per-regime-indicator component rewards because the most-sampled
# rv gates (rsi_2, rv_rank) looked like the WORST performers. Crucible's
# class-map response (2026-06-09, §3) proved the pairs runner never evaluates
# regime filters at all, so those "performances" were sampling artifacts and
# the engine was noise-fitting. `compute_relative_value_regime_weights` now
# returns `{}` unconditionally (`_RV_REGIME_WEIGHTS_FROZEN`). The D103 learning
# tests (component-gate-outweighs, rv-scoping, determinism/orphans) were
# deliberately REMOVED with the freeze — restore them from git history at the
# D119 commit if the freeze is ever lifted. The regime POOL is unchanged.
# ---------------------------------------------------------------------------


def _cfg_with_regime(
    hypothesis: str,
    regime_indicator: str,
    name: str,
    *,
    directional: str = "pairs_zscore",
) -> StrategyConfig:
    """A config of `hypothesis` whose regime_filter gate is `regime_indicator`."""
    return StrategyConfig(
        name=name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket="swing_mid",
        underlying=None if hypothesis == "relative_value" else "SPY",
        tier=2,
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=(directional,),
                params={"threshold": -0.6, "op": "<"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=(regime_indicator,),
                params={"threshold": 40.0, "op": "<"},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=33,
            dte_max=45,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )


def test_d103_regime_weights_empty_returns_empty(tmp_path: Path) -> None:
    """Cold start: no gated_runs → empty → sampler falls back to uniform."""
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_relative_value_regime_weights(conn, []) == {}


def test_d119_regime_weights_frozen_returns_empty_despite_component_evidence(
    tmp_path: Path,
) -> None:
    """D119: the rv-regime granularity is FROZEN — `{}` regardless of evidence.

    Crucible's class-map response (2026-06-09, `FORGE_rank_gate_class_map.md`
    §3) proved from code that the `pairs_convergence` runner evaluates NO
    regime filters: `propose_actions` gates purely on cointegration
    pvalue/zscore/halflife; `config.signals` is read only for pairs parameters.
    Every relative_value regime gate ever submitted (15,960/15,960 confluence
    → all routed to that path) was a dead label. The D103 posterior was
    therefore fit to noise — gate-id vs outcome correlations with no causal
    path — and applying it tilts rv emission toward gates that "performed" by
    sampling accident. Frozen until Crucible threads regime gates into the
    pairs path (revert: drop the early return in
    `compute_relative_value_regime_weights`; restore the D103 learning tests
    from git history at the D119 commit).

    The fixture is the strongest evidence the old engine accepted (a component
    on one gate vs trading rejects on another) — it must now move nothing."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(10):
            ch = f"good_{i:04d}"
            _insert_submission(
                conn,
                config=_cfg_with_regime("relative_value", "put_call_flow", f"g_{i}"),
                config_hash=ch,
            )
            gated.append(
                _gated_run_graded(
                    config_hash=ch,
                    trade_count=80,
                    gates_passed=4 if i == 0 else 3,
                    gates_failed=0 if i == 0 else 1,
                    decision="component" if i == 0 else "reject",
                    wf_sharpe=1.5,
                )
            )
        assert compute_relative_value_regime_weights(conn, gated) == {}


def test_d119_regime_weights_frozen_for_heterogeneous_inputs(tmp_path: Path) -> None:
    """D119: `{}` over mixed evidence too — rv rejects, a cross-hypothesis
    promote, un-gated submissions, and orphan runs all produce the same frozen
    result (and trivially deterministically, hard rule #6)."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(
            conn, config=_cfg_with_regime("relative_value", "adx", "rv1"), config_hash="rv_hash"
        )
        _insert_submission(
            conn,
            config=_cfg_with_regime("trend_continuation", "adx", "tc1", directional="rsi_2"),
            config_hash="tc_hash",
        )
        _insert_submission(
            conn, config=_cfg_with_regime("relative_value", "hurst", "rv2"), config_hash="ungated"
        )
        gated = [
            _gated_run_graded(
                config_hash="rv_hash", trade_count=50, gates_passed=2, gates_failed=2
            ),
            _gated_run_graded(
                config_hash="tc_hash",
                decision="promote",
                trade_count=100,
                gates_passed=4,
                gates_failed=0,
            ),
            _gated_run_graded(config_hash="orphan", trade_count=99, gates_passed=4, gates_failed=0),
        ]
        first = compute_relative_value_regime_weights(conn, gated)
        second = compute_relative_value_regime_weights(conn, gated)
    assert first == {}
    assert second == {}
