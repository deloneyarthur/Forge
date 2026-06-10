"""Tests for the component-rate reward family (D105).

Crucible's 2026-06-07 yield-map handoff showed the D094/D101 trade-production
reward became a Goodhart proxy after the rv lookback fix (Crucible 5fd485a):
relative_value trades ~100% (weight 0.567) but yields 0.7-1.0% components,
while volatility_event (weight 0.169) yields 3.9-9.7%. The component-rate
family re-aims the estimand: a run's reward is 1.0 iff its decision is
``component`` / ``promote``, else an epsilon-scale tiebreak — so the weights
track WHAT CRUCIBLE ACCEPTS, not what merely trades.
"""

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
    COMPONENT_ALPHA,
    COMPONENT_BETA,
    COMPONENT_TIEBREAK_WEIGHT,
    FEEDBACK_GATED_RUNS_LIMIT,
    component_prior_mean,
    compute_hypothesis_bucket_weights,
    compute_hypothesis_component_weights,
    compute_hypothesis_reward_weights,
    compute_underlying_class_weights,
)
from forge.persistence.db import db_connection

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


def _config(
    hypothesis: str,
    name: str,
    *,
    underlying: str | None = "SPY",
    dte_bucket: str = "swing_short",
) -> StrategyConfig:
    return StrategyConfig(
        name=name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket=dte_bucket,  # type: ignore[arg-type]
        underlying=underlying,
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


def _insert_batch(conn: Any, *, grammar_version: str) -> str:
    """Insert a batch_summaries row; returns its forge_batch_id for submissions."""
    batch_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO batch_summaries
            (forge_batch_id, batch_size, submitted_at, grammar_version, registry_version)
        VALUES (?, ?, ?, ?, ?)
        """,
        [batch_id, 1, datetime.now(UTC), grammar_version, "r1"],
    )
    return batch_id


def _insert_submission(
    conn: Any,
    *,
    config: StrategyConfig,
    config_hash: str,
    batch_id: str | None = None,
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
            batch_id if batch_id is not None else str(uuid.uuid4()),
            config_hash,
            config.model_dump_json(),
            datetime.now(UTC),
            "submitted",
        ],
    )


def _gated_run(
    *,
    config_hash: str,
    decision: str = "reject",
    trade_count: int = 0,
    gates_passed: int = 0,
    gates_failed: int = 0,
    wf_sharpe: float | None = None,
) -> GatedRun:
    run_id = str(uuid.uuid4())
    gate_results: dict[str, GateResult] = {}
    # D128: the modern export carries a regime_coverage row on every run; an
    # honest pass on component rows keeps the binary event under the honesty
    # key. Added only for component/promote so reject-row gate_fraction
    # arithmetic in existing pins is untouched.
    if decision in ("component", "promote"):
        gate_results["regime_coverage"] = GateResult(gate_name="regime_coverage", passed=True)
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


_EPS = COMPONENT_TIEBREAK_WEIGHT


def test_component_prior_mean() -> None:
    assert component_prior_mean() == pytest.approx(
        COMPONENT_ALPHA / (COMPONENT_ALPHA + COMPONENT_BETA)
    )


def test_empty_gated_runs_returns_empty(tmp_path: Path) -> None:
    """Cold start contract: no gated runs → {} → caller falls back to floored prior."""
    with db_connection(tmp_path / "forge.db") as conn:
        assert (
            compute_hypothesis_component_weights(
                conn, [], hypotheses=("mean_reversion", "volatility_event")
            )
            == {}
        )


def test_anti_goodhart_component_class_beats_heavy_trader(tmp_path: Path) -> None:
    """THE core regression for the 2026-06-07 yield-map handoff.

    relative_value-like class: 20/20 runs trade, ZERO components.
    volatility_event-like class: 15/20 zero-trade, but 1 component.

    The OLD trade-production reward (D094/D101) ranks the heavy trader on top —
    that is the live Goodhart (rv weighted 0.567 at 0.7-1.0% yield vs vol_event
    0.169 at 3.9-9.7%). The component-rate weights must rank them the other way.
    """
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(20):  # rv-like: traded reject, 2/4 gates, no sharpe metric
            ch = f"rv_{i:04d}"
            _insert_submission(conn, config=_config("relative_value", f"rv_{i}"), config_hash=ch)
            gated.append(
                _gated_run(config_hash=ch, trade_count=150, gates_passed=2, gates_failed=2)
            )
        for i in range(15):  # ve-like: structurally silent
            ch = f"ve_z_{i:04d}"
            _insert_submission(conn, config=_config("volatility_event", f"vz_{i}"), config_hash=ch)
            gated.append(_gated_run(config_hash=ch, trade_count=0, gates_passed=0, gates_failed=4))
        for i in range(4):  # ve-like: traded reject
            ch = f"ve_t_{i:04d}"
            _insert_submission(conn, config=_config("volatility_event", f"vt_{i}"), config_hash=ch)
            gated.append(_gated_run(config_hash=ch, trade_count=30, gates_passed=2, gates_failed=2))
        # ve-like: ONE component
        _insert_submission(conn, config=_config("volatility_event", "vc"), config_hash="ve_comp")
        gated.append(
            _gated_run(
                config_hash="ve_comp",
                decision="component",
                trade_count=80,
                gates_passed=4,
                gates_failed=0,
                wf_sharpe=1.5,
            )
        )

        new = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("relative_value", "volatility_event")
        )
        old = compute_hypothesis_reward_weights(conn, gated)

    # OLD estimand: heavy trader on top (the Goodhart this family fixes).
    assert old["relative_value"] > old["volatility_event"]

    # NEW estimand: the component class wins, normalized to 1.0.
    assert new["volatility_event"] == pytest.approx(1.0)
    assert new["relative_value"] < new["volatility_event"]
    # Exact math: posterior = (alpha + sum(reward)) / (alpha + beta + n).
    # rv: 20 traded-rejects, each eps*(0.5 + 0)/2; ve: 1 component (1.0) + 4
    # traded-rejects at the same tiebreak + 15 zeros.
    post_rv = (1.0 + 20 * _EPS * 0.25) / (51.0 + 20)
    post_ve = (1.0 + 1.0 + 4 * _EPS * 0.25) / (51.0 + 20)
    assert new["relative_value"] == pytest.approx(post_rv / post_ve, rel=1e-9)


def test_promote_counts_as_component_event(tmp_path: Path) -> None:
    """A promote cleared component-level screening too — same 1.0 event reward."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("mean_reversion", "p"), config_hash="p_hash")
        _insert_submission(conn, config=_config("trend_continuation", "c"), config_hash="c_hash")
        gated = [
            _gated_run(
                config_hash="p_hash",
                decision="promote",
                trade_count=120,
                gates_passed=4,
                gates_failed=0,
            ),
            _gated_run(
                config_hash="c_hash",
                decision="component",
                trade_count=90,
                gates_passed=4,
                gates_failed=0,
            ),
        ]
        weights = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("mean_reversion", "trend_continuation")
        )
    # Both are single-event classes with n=1: identical posteriors → both 1.0.
    assert weights["mean_reversion"] == pytest.approx(weights["trend_continuation"])
    assert weights["mean_reversion"] == pytest.approx(1.0)


def test_tiebreak_gradient_among_zero_component_classes(tmp_path: Path) -> None:
    """No components anywhere: gate-progress/sharpe still order classes (the
    D094 gradient survives at epsilon scale)."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(10):  # strong tiebreak: traded, all gates, sharpe at ceiling
            ch = f"a_{i:04d}"
            _insert_submission(conn, config=_config("volatility_event", f"a_{i}"), config_hash=ch)
            gated.append(
                _gated_run(
                    config_hash=ch,
                    trade_count=60,
                    gates_passed=4,
                    gates_failed=0,
                    wf_sharpe=2.0,
                )
            )
        for i in range(10):  # zero tiebreak: silent, no gates passed
            ch = f"b_{i:04d}"
            _insert_submission(conn, config=_config("mean_reversion", f"b_{i}"), config_hash=ch)
            gated.append(_gated_run(config_hash=ch, trade_count=0, gates_passed=0, gates_failed=4))
        weights = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("volatility_event", "mean_reversion")
        )
    assert weights["volatility_event"] > weights["mean_reversion"]
    post_a = (1.0 + 10 * _EPS) / (51.0 + 10)
    post_b = 1.0 / (51.0 + 10)
    assert weights["mean_reversion"] == pytest.approx(post_b / post_a, rel=1e-9)


def test_tiebreak_cannot_reorder_one_component_difference() -> None:
    """The epsilon bound: across the whole feedback window, the maximum total
    tiebreak mass (limit x eps) must stay at or below HALF of one component
    event's reward — so no amount of trading/gate-passing can ever outrank a
    single real component."""
    assert COMPONENT_TIEBREAK_WEIGHT * FEEDBACK_GATED_RUNS_LIMIT <= 0.5


def test_unobserved_hypothesis_gets_prior_and_all_keys_present(tmp_path: Path) -> None:
    """Requested-but-unobserved hypotheses fill at the component prior (an
    average-class weight) — present in the output so the floored-sampling
    pipeline sees every enumerable hypothesis."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("volatility_event", "v"), config_hash="v_hash")
        gated = [
            _gated_run(
                config_hash="v_hash",
                decision="component",
                trade_count=80,
                gates_passed=4,
                gates_failed=0,
            )
        ]
        weights = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("volatility_event", "trend_continuation")
        )
    assert set(weights) == {"volatility_event", "trend_continuation"}
    post_ve = 2.0 / 52.0
    assert weights["volatility_event"] == pytest.approx(1.0)
    assert weights["trend_continuation"] == pytest.approx(
        component_prior_mean() / post_ve, rel=1e-9
    )


def test_prior_version_runs_are_downweighted(tmp_path: Path) -> None:
    """D081 semantics at the reward layer: a component minted under a prior
    grammar version counts at 0.25 weight, so a current-version component
    outranks it."""
    with db_connection(tmp_path / "forge.db") as conn:
        v9_batch = _insert_batch(conn, grammar_version="v9")
        v8_batch = _insert_batch(conn, grammar_version="v8")
        _insert_submission(
            conn, config=_config("volatility_event", "cur"), config_hash="cur", batch_id=v9_batch
        )
        _insert_submission(
            conn, config=_config("trend_continuation", "old"), config_hash="old", batch_id=v8_batch
        )
        gated = [
            _gated_run(
                config_hash="cur",
                decision="component",
                trade_count=80,
                gates_passed=4,
                gates_failed=0,
            ),
            _gated_run(
                config_hash="old",
                decision="component",
                trade_count=80,
                gates_passed=4,
                gates_failed=0,
            ),
        ]
        weights = compute_hypothesis_component_weights(
            conn,
            gated,
            hypotheses=("volatility_event", "trend_continuation"),
            current_grammar_version="v9",
        )
    post_cur = (1.0 + 1.0) / (51.0 + 1.0)
    post_old = (1.0 + 0.25) / (51.0 + 0.25)
    assert weights["volatility_event"] == pytest.approx(1.0)
    assert weights["trend_continuation"] == pytest.approx(post_old / post_cur, rel=1e-9)
    assert weights["trend_continuation"] < 1.0


def test_cold_start_hypotheses_drop_prior_version_evidence(tmp_path: Path) -> None:
    """D098 semantics at the reward layer: for cold-start hypotheses,
    prior-version rows are DROPPED (not down-weighted) — their poisoned legacy
    cohort cannot inflate (or deflate) the component rate. Without the
    cold-start set the same data ranks relative_value on top; with it,
    relative_value falls back to the prior."""
    with db_connection(tmp_path / "forge.db") as conn:
        v8_batch = _insert_batch(conn, grammar_version="v8")
        v9_batch = _insert_batch(conn, grammar_version="v9")
        gated: list[GatedRun] = []
        for i in range(5):  # rv: five PRIOR-version components (poisoned-era signal)
            ch = f"rv_{i:04d}"
            _insert_submission(
                conn,
                config=_config("relative_value", f"rv_{i}"),
                config_hash=ch,
                batch_id=v8_batch,
            )
            gated.append(
                _gated_run(
                    config_hash=ch,
                    decision="component",
                    trade_count=80,
                    gates_passed=4,
                    gates_failed=0,
                )
            )
        _insert_submission(
            conn, config=_config("volatility_event", "ve"), config_hash="ve", batch_id=v9_batch
        )
        gated.append(
            _gated_run(
                config_hash="ve",
                decision="component",
                trade_count=80,
                gates_passed=4,
                gates_failed=0,
            )
        )

        without = compute_hypothesis_component_weights(
            conn,
            gated,
            hypotheses=("relative_value", "volatility_event"),
            current_grammar_version="v9",
        )
        with_cold = compute_hypothesis_component_weights(
            conn,
            gated,
            hypotheses=("relative_value", "volatility_event"),
            current_grammar_version="v9",
            cold_start_hypotheses=frozenset({"relative_value"}),
        )

    # Without cold-start: rv's five down-weighted components still beat one
    # current component: (1 + 5*0.25)/(51 + 1.25) vs (1+1)/(51+1).
    assert without["relative_value"] == pytest.approx(1.0)
    # With cold-start: rv's v8 evidence vanishes → prior fill; ve's current
    # component makes it the max.
    assert with_cold["volatility_event"] == pytest.approx(1.0)
    post_ve = 2.0 / 52.0
    assert with_cold["relative_value"] == pytest.approx(component_prior_mean() / post_ve, rel=1e-9)


def test_no_version_scoping_when_current_is_none(tmp_path: Path) -> None:
    """current_grammar_version=None → every run weighs 1.0 (pre-D081 behaviour)."""
    with db_connection(tmp_path / "forge.db") as conn:
        v8_batch = _insert_batch(conn, grammar_version="v8")
        _insert_submission(
            conn, config=_config("volatility_event", "x"), config_hash="x", batch_id=v8_batch
        )
        gated = [
            _gated_run(
                config_hash="x",
                decision="component",
                trade_count=80,
                gates_passed=4,
                gates_failed=0,
            )
        ]
        weights = compute_hypothesis_component_weights(
            conn, gated, hypotheses=("volatility_event",)
        )
    assert weights["volatility_event"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# hypothesis x dte_bucket cells (D105 change B) — the granularity the yield map
# showed structure at (vol_event x swing_mid 9.7% vs mean_reversion x swing_mid
# 0/628). Keying tests only: the engine semantics (version scoping, tiebreak,
# cold start) are pinned above and shared.
# ---------------------------------------------------------------------------


def test_bucket_weights_key_by_hypothesis_and_bucket(tmp_path: Path) -> None:
    """A component in (ve, swing_mid) lifts that CELL — not (ve, swing_short),
    which only trades — and not any other hypothesis's cells."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _insert_submission(
            conn,
            config=_config("volatility_event", "m", dte_bucket="swing_mid"),
            config_hash="ve_mid",
        )
        gated.append(
            _gated_run(
                config_hash="ve_mid",
                decision="component",
                trade_count=70,
                gates_passed=4,
                gates_failed=0,
            )
        )
        for i in range(5):
            ch = f"ve_short_{i}"
            _insert_submission(
                conn,
                config=_config("volatility_event", f"s_{i}", dte_bucket="swing_short"),
                config_hash=ch,
            )
            gated.append(_gated_run(config_hash=ch, trade_count=40, gates_passed=2, gates_failed=2))
        weights = compute_hypothesis_bucket_weights(conn, gated)
    assert set(weights) == {
        ("volatility_event", "swing_mid"),
        ("volatility_event", "swing_short"),
    }
    assert weights[("volatility_event", "swing_mid")] > weights[("volatility_event", "swing_short")]
    assert weights[("volatility_event", "swing_mid")] == pytest.approx(2.0 / 52.0, rel=1e-9)
    tb = COMPONENT_TIEBREAK_WEIGHT * 0.25
    assert weights[("volatility_event", "swing_short")] == pytest.approx(
        (1.0 + 5 * tb) / 56.0, rel=1e-9
    )


def test_bucket_weights_empty_and_deterministic(tmp_path: Path) -> None:
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_hypothesis_bucket_weights(conn, []) == {}
        _insert_submission(
            conn,
            config=_config("trend_continuation", "t", dte_bucket="swing_long"),
            config_hash="t1",
        )
        gated = [
            _gated_run(
                config_hash="t1",
                decision="component",
                trade_count=60,
                gates_passed=3,
                gates_failed=0,
            )
        ]
        first = compute_hypothesis_bucket_weights(conn, gated)
        second = compute_hypothesis_bucket_weights(conn, gated)
    assert first == second == {("trend_continuation", "swing_long"): pytest.approx(2.0 / 52.0)}


# ---------------------------------------------------------------------------
# Underlying-class weights (D105 change C) — high-idio-vol single names minted
# 12.8-27.9% in the yield map while diversified ETF/index sat at 0/~390.
# ---------------------------------------------------------------------------


def test_underlying_class_weights_key_by_class_and_skip_rv_none(tmp_path: Path) -> None:
    """Components on AAPL/NVDA aggregate into the high_idio_vol class; SPY's
    trading rejects land in diversified; relative_value (underlying=None) is
    skipped — pairs legs are Crucible-resolved, no class to learn."""
    from forge.enumeration.underlying_class import DIVERSIFIED, HIGH_IDIO_VOL

    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i, name in enumerate(("AAPL", "NVDA")):
            ch = f"hi_{i}"
            _insert_submission(
                conn, config=_config("volatility_event", f"h{i}", underlying=name), config_hash=ch
            )
            gated.append(
                _gated_run(
                    config_hash=ch,
                    decision="component",
                    trade_count=70,
                    gates_passed=4,
                    gates_failed=0,
                )
            )
        for i in range(6):
            ch = f"div_{i}"
            _insert_submission(
                conn,
                config=_config("trend_continuation", f"d{i}", underlying="SPY"),
                config_hash=ch,
            )
            gated.append(_gated_run(config_hash=ch, trade_count=40, gates_passed=2, gates_failed=2))
        # relative_value with underlying=None — must contribute to NO class
        _insert_submission(
            conn, config=_config("relative_value", "rv", underlying=None), config_hash="rv"
        )
        gated.append(
            _gated_run(
                config_hash="rv",
                decision="component",
                trade_count=90,
                gates_passed=4,
                gates_failed=0,
            )
        )
        weights = compute_underlying_class_weights(conn, gated)
    assert set(weights) == {HIGH_IDIO_VOL, DIVERSIFIED}
    assert weights[HIGH_IDIO_VOL] > weights[DIVERSIFIED]
    # high: 2 components over n=2 (the rv component must NOT inflate this)
    assert weights[HIGH_IDIO_VOL] == pytest.approx(3.0 / 53.0, rel=1e-9)
    tb = COMPONENT_TIEBREAK_WEIGHT * 0.25
    assert weights[DIVERSIFIED] == pytest.approx((1.0 + 6 * tb) / 57.0, rel=1e-9)


def test_deterministic_and_orphans_and_corrupt_skipped(tmp_path: Path) -> None:
    """Hard rule #6: pure function of (submissions, gated_runs) snapshot; orphan
    runs and corrupt config_json rows are skipped."""
    with db_connection(tmp_path / "forge.db") as conn:
        _insert_submission(conn, config=_config("mean_reversion", "m"), config_hash="real")
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
                "corrupt",
                json.dumps({"not_a_config": True}),
                datetime.now(UTC),
                "submitted",
            ],
        )
        gated = [
            _gated_run(
                config_hash="real",
                decision="component",
                trade_count=60,
                gates_passed=4,
                gates_failed=0,
            ),
            _gated_run(
                config_hash="corrupt",
                decision="component",
                trade_count=60,
                gates_passed=4,
                gates_failed=0,
            ),
            _gated_run(
                config_hash="orphan",
                decision="component",
                trade_count=60,
                gates_passed=4,
                gates_failed=0,
            ),
        ]
        first = compute_hypothesis_component_weights(conn, gated, hypotheses=("mean_reversion",))
        second = compute_hypothesis_component_weights(conn, gated, hypotheses=("mean_reversion",))
    assert first == second
    # Only the real submission contributes: posterior (1+1)/(51+1), alone → 1.0.
    assert first["mean_reversion"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# D106 — hierarchical granularities. Two findings drove these:
# (1) per-name yield is extreme INSIDE the high-idio class (AAPL 36.6% vs
#     SHOP 0/85 at comparable n) — the two-class prior is leaky both ways;
# (2) a flat directional weight multiplied into the bucket cell would
#     double-count correlated effects (iv_rank's edge is partly its
#     swing_mid reach), so the directional signal lives in a
#     (hypothesis, directional, bucket) cell shrunk toward its
#     (hypothesis, bucket) pair.
# Both use the same empirical-Bayes shrinkage: fine posterior =
# (S * coarse_posterior + fine_reward_sum) / (S + fine_n).
# ---------------------------------------------------------------------------


def test_name_weights_strong_evidence_escapes_class_prior(tmp_path: Path) -> None:
    """A heavily-minting name (AAPL-like) must rise far above its class
    posterior; a well-sampled dead name (SHOP-like) must sink below it;
    and unseen names are ABSENT (the sampler falls back to the class)."""
    from forge.feedback.rejection_weights import (
        COMPONENT_HIER_PRIOR_STRENGTH,
        compute_underlying_class_weights,
        compute_underlying_name_weights,
    )

    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(20):  # AAPL: 8/20 components
            ch = f"aapl_{i}"
            _insert_submission(
                conn, config=_config("volatility_event", f"a{i}", underlying="AAPL"), config_hash=ch
            )
            gated.append(
                _gated_run(
                    config_hash=ch,
                    decision="component" if i < 8 else "reject",
                    trade_count=80,
                    gates_passed=4 if i < 8 else 2,
                    gates_failed=0 if i < 8 else 2,
                )
            )
        for i in range(20):  # SHOP: 0/20, all trading rejects
            ch = f"shop_{i}"
            _insert_submission(
                conn, config=_config("volatility_event", f"s{i}", underlying="SHOP"), config_hash=ch
            )
            gated.append(_gated_run(config_hash=ch, trade_count=60, gates_passed=2, gates_failed=2))
        names = compute_underlying_name_weights(conn, gated)
        classes = compute_underlying_class_weights(conn, gated)

    from forge.enumeration.underlying_class import HIGH_IDIO_VOL

    p_class = classes[HIGH_IDIO_VOL]
    assert set(names) == {"AAPL", "SHOP"}
    assert names["AAPL"] > p_class > names["SHOP"]
    # Exact shrinkage math: S*p_class anchors, evidence moves.
    s = COMPONENT_HIER_PRIOR_STRENGTH
    tb = COMPONENT_TIEBREAK_WEIGHT * 0.25
    assert names["AAPL"] == pytest.approx((s * p_class + 8.0 + 12 * tb) / (s + 20), rel=1e-9)
    assert names["SHOP"] == pytest.approx((s * p_class + 20 * tb) / (s + 20), rel=1e-9)


def test_name_weights_thin_name_stays_near_class(tmp_path: Path) -> None:
    """One observation barely moves a name off its class posterior — the
    hierarchy protects thin names from their own noise."""
    from forge.feedback.rejection_weights import (
        compute_underlying_class_weights,
        compute_underlying_name_weights,
    )

    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(30):  # class context: NVDA minting
            ch = f"nvda_{i}"
            _insert_submission(
                conn, config=_config("volatility_event", f"n{i}", underlying="NVDA"), config_hash=ch
            )
            gated.append(
                _gated_run(
                    config_hash=ch,
                    decision="component" if i < 3 else "reject",
                    trade_count=70,
                    gates_passed=3 if i < 3 else 1,
                    gates_failed=0 if i < 3 else 3,
                )
            )
        # F: a single zero-trade reject
        _insert_submission(
            conn, config=_config("trend_continuation", "f0", underlying="F"), config_hash="f_0"
        )
        gated.append(_gated_run(config_hash="f_0", trade_count=0, gates_passed=0, gates_failed=4))
        names = compute_underlying_name_weights(conn, gated)
        classes = compute_underlying_class_weights(conn, gated)

    from forge.enumeration.underlying_class import HIGH_IDIO_VOL

    p_class = classes[HIGH_IDIO_VOL]
    # F moved less than 3% off the class posterior by a single observation.
    assert abs(names["F"] - p_class) / p_class < 0.03


def test_directional_bucket_weights_shrink_toward_pair_cell(tmp_path: Path) -> None:
    """The (hypothesis, directional, bucket) triple shrinks toward its
    (hypothesis, bucket) pair — so a minting directional rises above the
    pair cell and a dead one sinks below, WITHOUT double-counting the
    bucket effect."""
    from forge.feedback.rejection_weights import (
        COMPONENT_HIER_PRIOR_STRENGTH,
        compute_hypothesis_bucket_weights,
        compute_hypothesis_directional_bucket_weights,
    )

    def _cfg_dir(name: str, directional: str) -> StrategyConfig:
        base = _config("mean_reversion", name, dte_bucket="swing_short")
        sigs = list(base.signals)
        sigs[0] = SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=(directional,),
            params={"threshold": 30.0, "op": "<"},
        )
        return base.model_copy(update={"signals": tuple(sigs)})

    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(10):  # put_wall: 2/10 components
            ch = f"pw_{i}"
            _insert_submission(
                conn, config=_cfg_dir(f"pw{i}", "put_wall_distance_pct"), config_hash=ch
            )
            gated.append(
                _gated_run(
                    config_hash=ch,
                    decision="component" if i < 2 else "reject",
                    trade_count=60,
                    gates_passed=4 if i < 2 else 2,
                    gates_failed=0 if i < 2 else 2,
                )
            )
        for i in range(10):  # rsi_2: 0/10
            ch = f"rs_{i}"
            _insert_submission(conn, config=_cfg_dir(f"rs{i}", "rsi_2"), config_hash=ch)
            gated.append(_gated_run(config_hash=ch, trade_count=40, gates_passed=2, gates_failed=2))
        triples = compute_hypothesis_directional_bucket_weights(conn, gated)
        pairs = compute_hypothesis_bucket_weights(conn, gated)

    pair = pairs[("mean_reversion", "swing_short")]
    hot = triples[("mean_reversion", "put_wall_distance_pct", "swing_short")]
    cold = triples[("mean_reversion", "rsi_2", "swing_short")]
    assert hot > pair > cold
    s = COMPONENT_HIER_PRIOR_STRENGTH
    tb = COMPONENT_TIEBREAK_WEIGHT * 0.25
    assert hot == pytest.approx((s * pair + 2.0 + 8 * tb) / (s + 10), rel=1e-9)
    assert cold == pytest.approx((s * pair + 10 * tb) / (s + 10), rel=1e-9)


def test_sharpe_reward_reads_gate_value_with_metrics_fallback(tmp_path: Path) -> None:
    """D106 fix: the live export carries walk_forward_sharpe_median in
    gate_results[].value, NOT in run.metrics — D101's metrics-only read made
    the sharpe term silently 0 for every run. Gate value wins; metrics is
    the fallback; zero-trade still gets no credit."""
    from crucible_contracts import GateResult

    from forge.feedback.rejection_weights import _sharpe_reward

    def _run_with(wf_gate: float | None, wf_metric: float | None, trades: int) -> GatedRun:
        gr = _gated_run(config_hash="x", trade_count=trades, gates_passed=1, gates_failed=1)
        if wf_metric is not None:
            gr.run.metrics["walk_forward_sharpe_median"] = wf_metric
        if wf_gate is not None:
            gr.decision.gate_results["walk_forward_sharpe_median"] = GateResult(
                gate_name="walk_forward_sharpe_median",
                passed=False,
                value=wf_gate,
                threshold=2.0,
            )
        return gr

    # gate value only (the live-export shape): half the 2.0 ceiling -> 0.5
    assert _sharpe_reward(_run_with(1.0, None, trades=50), traded=True) == pytest.approx(0.5)
    # gate value wins over a stale metrics entry
    assert _sharpe_reward(_run_with(2.0, 0.0, trades=50), traded=True) == pytest.approx(1.0)
    # metrics fallback when the gate row is absent
    assert _sharpe_reward(_run_with(None, 1.0, trades=50), traded=True) == pytest.approx(0.5)
    # zero-trade: no credit regardless of source
    assert _sharpe_reward(_run_with(2.0, 2.0, trades=0), traded=False) == 0.0
