"""Tests for the regime-gate-yield weighter — increment 2 of Crucible's
2026-06-17 yield-map refresh (`FORGE_structural_yield_map_refresh.md`, §2/§4).

Within a fixed (hypothesis, directional, dte_bucket) triple, the regime GATE
moves the component rate: on live Forge data `trend|momentum_252|swing_long`
mints hurst 8.1% / adx 5.4% / rv_rank 4.9% / **gamma_flip 0.0%** (an 8.1pp
spread; the §4 "gamma_flip regime gate is a near-universal yield sink"
replicates). This weighter learns the
``(hypothesis, directional, dte_bucket, regime_gate)`` component-rate, anchored
on the ``(hypothesis, directional, dte_bucket)`` D106 triple, so the sampler's
regime draw can avoid the sink gates and favour the minting ones.

D119 GUARD: relative_value is EXCLUDED — its `pairs_convergence` runner evaluates
NO regime filter (the gate is a dead label there; weighting it would repeat the
D119 mistake). Every other hypothesis's runner (composable_long_options /
cross_sectional_rank) DOES evaluate the gate, so the yield differences are
causal. Same engine/estimand/version-scoping as the D105/D106/cohort weighters;
empty gated_runs -> {} (cold-start; the sampler keeps its D150/uniform regime
draw, byte-identical).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

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
    COMPONENT_HIER_PRIOR_STRENGTH,
    COMPONENT_PRIOR_VERSION_WEIGHT,
    compute_regime_gate_yield_weights,
)
from forge.persistence.db import db_connection

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)

_TREND = "trend_continuation"
_MOM = "momentum_252"


def _config(
    hypothesis: str,
    name: str,
    *,
    directional: str = _MOM,
    regime: str = "hurst",
    dte_bucket: str = "swing_long",
    underlying: str | None = "AAPL",
) -> StrategyConfig:
    """A config whose regime cell is (hypothesis, directional, dte_bucket, regime)."""
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
                indicators=(directional,),
                params={"threshold": 0.5, "op": ">"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=(regime,),
                params={"threshold": 0.55, "op": ">"},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(delta_target=0.30, delta_tolerance=0.05, dte_min=30, dte_max=45),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )


def _insert_batch(conn: Any, *, grammar_version: str) -> str:
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
    conn: Any, *, config: StrategyConfig, config_hash: str, batch_id: str | None = None
) -> None:
    conn.execute(
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json, submitted_at, status)
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


def _gated_run(*, config_hash: str, decision: str = "reject", trade_count: int = 0) -> GatedRun:
    run_id = str(uuid.uuid4())
    gate_results = {
        "g0": GateResult(gate_name="g0", passed=True),
        "g1": GateResult(gate_name="g1", passed=True),
        "regime_coverage": GateResult(gate_name="regime_coverage", passed=True),
    }
    return GatedRun(
        run=RunResult(
            run_id=run_id,
            config_hash=config_hash,
            metrics={"walk_forward_sharpe_median": 1.9},
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


def _populate_regime(
    conn: Any,
    gated: list[GatedRun],
    *,
    hypothesis: str = _TREND,
    directional: str = _MOM,
    regime: str,
    n_components: int,
    n_rejects: int = 0,
    dte_bucket: str = "swing_long",
    batch_id: str | None = None,
    tag: str = "c",
) -> None:
    """Insert ``n_components`` component runs + ``n_rejects`` rejects into one
    (hyp, directional, dte_bucket, regime) cell."""
    for i in range(n_components):
        ch = f"{tag}_{regime}_comp_{i:04d}"
        _insert_submission(
            conn,
            config=_config(
                hypothesis, ch, directional=directional, regime=regime, dte_bucket=dte_bucket
            ),
            config_hash=ch,
            batch_id=batch_id,
        )
        gated.append(_gated_run(config_hash=ch, decision="component", trade_count=120))
    for i in range(n_rejects):
        ch = f"{tag}_{regime}_rej_{i:04d}"
        _insert_submission(
            conn,
            config=_config(
                hypothesis, ch, directional=directional, regime=regime, dte_bucket=dte_bucket
            ),
            config_hash=ch,
            batch_id=batch_id,
        )
        gated.append(_gated_run(config_hash=ch, decision="reject", trade_count=300))


_HURST = (_TREND, _MOM, "swing_long", "hurst")
_GAMMA = (_TREND, _MOM, "swing_long", "gamma_flip_distance_pct")


def test_empty_gated_runs_returns_empty(tmp_path: Path) -> None:
    """Cold-start: no gated runs -> {} -> the sampler keeps its D150/uniform
    regime draw (byte-identical)."""
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_regime_gate_yield_weights(conn, []) == {}


def test_regimes_separated_within_triple(tmp_path: Path) -> None:
    """The key is the full (hyp, directional, bucket, regime) quad: different
    regime gates in the same triple are independent cells (the axis the pair and
    triple weighters cannot express)."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_regime(conn, gated, regime="hurst", n_components=5, n_rejects=10, tag="h")
        _populate_regime(
            conn, gated, regime="gamma_flip_distance_pct", n_components=0, n_rejects=15, tag="g"
        )
        weights = compute_regime_gate_yield_weights(conn, gated)
    assert _HURST in weights
    assert _GAMMA in weights


def test_gamma_flip_sink_downweighted_vs_minting_gate(tmp_path: Path) -> None:
    """THE §4 finding: the gamma_flip regime gate is a yield sink. Within the
    minting trend triple, gamma_flip (0 components) must carry a lower posterior
    than hurst (minting) -> the sampler draws the sink gate less."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        # hurst 26/322 (~8%) vs gamma_flip 0/260 (the live shape)
        _populate_regime(conn, gated, regime="hurst", n_components=26, n_rejects=296, tag="h")
        _populate_regime(
            conn, gated, regime="gamma_flip_distance_pct", n_components=0, n_rejects=260, tag="g"
        )
        weights = compute_regime_gate_yield_weights(conn, gated)
    assert weights[_HURST] > weights[_GAMMA]
    assert weights[_HURST] > 3.0 * weights[_GAMMA]  # a material, not marginal, gap


def test_relative_value_excluded_d119_guard(tmp_path: Path) -> None:
    """D119: relative_value's pairs_convergence runner evaluates NO regime gate —
    so an rv regime label is dead and must NEVER be learned (weighting it repeats
    the D119 sampling-artifact mistake). rv configs contribute no cell."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        # rv components on a regime gate — must be ignored entirely
        for i in range(6):
            ch = f"rv_{i:04d}"
            _insert_submission(
                conn,
                config=_config("relative_value", ch, regime="rv_rank", underlying=None),
                config_hash=ch,
            )
            gated.append(_gated_run(config_hash=ch, decision="component", trade_count=120))
        # plus a real non-rv cell so the result isn't trivially empty
        _populate_regime(conn, gated, regime="hurst", n_components=3, tag="h")
        weights = compute_regime_gate_yield_weights(conn, gated)
    assert all(hyp != "relative_value" for (hyp, _d, _b, _r) in weights)
    assert _HURST in weights


def test_thin_regime_cell_shrinks_toward_triple(tmp_path: Path) -> None:
    """Hierarchical anchor (D106): a thin regime cell is pulled toward its
    (hyp, directional, bucket) triple rate, so a single lucky component cannot
    make a regime look dominant."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_regime(conn, gated, regime="adx", n_components=2, n_rejects=98, tag="a")
        _populate_regime(conn, gated, regime="hurst", n_components=1, n_rejects=0, tag="h")
        weights = compute_regime_gate_yield_weights(conn, gated)
    # raw hurst rate is 1.0 (1/1); shrunk far below it, pulled to the triple
    assert weights[_HURST] < 0.5
    assert weights[_HURST] > weights[(_TREND, _MOM, "swing_long", "adx")]


def test_component_count_drives_weight_not_trades_anti_goodhart(tmp_path: Path) -> None:
    """Anti-Goodhart: a regime gate that trades heavily but mints ZERO components
    does not out-weigh a minting one. Only Crucible-accepted components count."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_regime(
            conn, gated, regime="gamma_flip_distance_pct", n_components=0, n_rejects=200, tag="g"
        )
        _populate_regime(conn, gated, regime="hurst", n_components=5, n_rejects=5, tag="h")
        weights = compute_regime_gate_yield_weights(conn, gated)
    assert weights[_HURST] > weights[_GAMMA]


def test_prior_version_components_downweighted(tmp_path: Path) -> None:
    """D081 version scoping: a prior-version component contributes 0.25, so an
    all-prior-version regime cell shrinks harder toward the triple anchor than the
    same count on the current version."""
    with db_connection(tmp_path / "forge.db") as conn:
        cur = _insert_batch(conn, grammar_version="v22")
        old = _insert_batch(conn, grammar_version="v21")
        gated_cur: list[GatedRun] = []
        gated_old: list[GatedRun] = []
        _populate_regime(
            conn, gated_cur, regime="hurst", n_components=4, n_rejects=4, batch_id=cur, tag="cur"
        )
        _populate_regime(
            conn, gated_old, regime="hurst", n_components=4, n_rejects=4, batch_id=old, tag="old"
        )
        _populate_regime(
            conn, gated_cur, regime="adx", n_components=1, n_rejects=20, batch_id=cur, tag="cur"
        )
        _populate_regime(
            conn, gated_old, regime="adx", n_components=1, n_rejects=20, batch_id=old, tag="old"
        )
        w_cur = compute_regime_gate_yield_weights(conn, gated_cur, current_grammar_version="v22")
        w_old = compute_regime_gate_yield_weights(conn, gated_old, current_grammar_version="v22")
    assert w_old[_HURST] < w_cur[_HURST]


def test_cold_start_hypothesis_drops_prior_version_rows(tmp_path: Path) -> None:
    """A cold-start hypothesis drops its prior-version rows entirely."""
    with db_connection(tmp_path / "forge.db") as conn:
        old = _insert_batch(conn, grammar_version="v21")
        gated: list[GatedRun] = []
        _populate_regime(
            conn,
            gated,
            hypothesis="mean_reversion",
            directional="rsi_2",
            regime="rv_rank",
            n_components=5,
            batch_id=old,
            tag="cs",
        )
        weights = compute_regime_gate_yield_weights(
            conn,
            gated,
            current_grammar_version="v22",
            cold_start_hypotheses=frozenset({"mean_reversion"}),
        )
    assert weights == {}


def test_determinism_same_inputs_same_output(tmp_path: Path) -> None:
    """Hard rule #6: a pure function of (submissions, gated_runs)."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_regime(conn, gated, regime="hurst", n_components=7, n_rejects=20, tag="h")
        _populate_regime(conn, gated, regime="adx", n_components=2, n_rejects=40, tag="a")
        a = compute_regime_gate_yield_weights(conn, gated)
        b = compute_regime_gate_yield_weights(conn, gated)
    assert a == b
    assert COMPONENT_HIER_PRIOR_STRENGTH > 0.0
    assert COMPONENT_PRIOR_VERSION_WEIGHT == 0.25
