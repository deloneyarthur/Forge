"""Tests for the cohort-yield weighter — the §3 cohort axis of Crucible's
2026-06-17 yield-map refresh (`FORGE_structural_yield_map_refresh.md`).

The refreshed map shows the single largest within-stratum yield spread is COHORT
(cross-sectional vs single-name): the *identical* trend recipe
``momentum_252 | hurst | swing_long`` mints **40.4% cross-sectional vs 0.96%
single-name** — a 40x flip the existing ``(hyp x dte)`` (D105) and
``(hyp x directional x dte)`` (D106) maps are blind to, because cohort
(``combiner.type``) is drawn by a FIXED ``rank_combiner_share`` coin-flip, never
by yield.

This weighter learns the ``(hypothesis, directional, dte_bucket, cohort)``
component-rate, anchored on the ``(hypothesis, directional, dte_bucket)`` D106
triple, so the sampler's cohort draw becomes yield-driven. Same engine as
D105/D106/H4: component-rate estimand, version-scoped (D081), hierarchical
shrinkage toward the coarse triple (zero fine evidence -> the triple posterior
exactly). Empty gated_runs -> ``{}`` (cold-start; the sampler keeps the fixed
share, byte-identical — hard rule #6).

Cohort is a within-hypothesis reallocation (single<->xsect for a fixed
hypothesis), so it does NOT shift the cross-hypothesis mix — the monoculture
axis lives in the hypothesis weights, not here.
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
    compute_cohort_yield_weights,
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


def _combiner(cohort: str) -> CombinerSpec:
    """confluence (single-name) vs cross_sectional_rank (xsect), mirroring the
    sampler's two combiner constructions (sampler.py)."""
    if cohort == "xsect":
        return CombinerSpec(
            type="cross_sectional_rank",
            rank_k=10,
            rebalance_frequency="weekly",
            direction_mode="long_only",
        )
    return CombinerSpec()  # confluence


def _config(
    hypothesis: str,
    name: str,
    *,
    directional: str = _MOM,
    cohort: str = "single",
    dte_bucket: str = "swing_long",
) -> StrategyConfig:
    """A config whose cohort cell is (hypothesis, directional, dte_bucket, cohort).

    xsect carries underlying=None (the runner ranks ``universe.tickers``);
    single carries a pinned name — exactly the sampler's invariant.
    """
    return StrategyConfig(
        name=name,
        hypothesis=hypothesis,  # type: ignore[arg-type]
        dte_bucket=dte_bucket,  # type: ignore[arg-type]
        underlying=None if cohort == "xsect" else "AAPL",
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
                indicators=("hurst",),
                params={"threshold": 0.55, "op": ">"},
            ),
        ),
        combiner=_combiner(cohort),
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
    # Full slate of passed gates incl. an HONEST regime_coverage row (D128), so a
    # component decision grants the binary component reward under the honesty key.
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


def _populate_cohort(
    conn: Any,
    gated: list[GatedRun],
    *,
    hypothesis: str = _TREND,
    directional: str = _MOM,
    cohort: str,
    n_components: int,
    n_rejects: int = 0,
    dte_bucket: str = "swing_long",
    batch_id: str | None = None,
    tag: str = "c",
) -> None:
    """Insert ``n_components`` component runs + ``n_rejects`` traded rejects into
    one (hyp, directional, dte_bucket, cohort) cell."""
    for i in range(n_components):
        ch = f"{tag}_{cohort}_comp_{i:04d}"
        _insert_submission(
            conn,
            config=_config(
                hypothesis, ch, directional=directional, cohort=cohort, dte_bucket=dte_bucket
            ),
            config_hash=ch,
            batch_id=batch_id,
        )
        gated.append(_gated_run(config_hash=ch, decision="component", trade_count=120))
    for i in range(n_rejects):
        ch = f"{tag}_{cohort}_rej_{i:04d}"
        _insert_submission(
            conn,
            config=_config(
                hypothesis, ch, directional=directional, cohort=cohort, dte_bucket=dte_bucket
            ),
            config_hash=ch,
            batch_id=batch_id,
        )
        gated.append(_gated_run(config_hash=ch, decision="reject", trade_count=300))


_XSECT = (_TREND, _MOM, "swing_long", "xsect")
_SINGLE = (_TREND, _MOM, "swing_long", "single")


def test_empty_gated_runs_returns_empty(tmp_path: Path) -> None:
    """Cold-start contract: no gated runs -> {} -> the sampler keeps its fixed
    rank_combiner_share (byte-identical to the pre-cohort-yield draw)."""
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_cohort_yield_weights(conn, []) == {}


def test_cohort_separates_single_from_xsect(tmp_path: Path) -> None:
    """The key is the full (hyp, directional, bucket, cohort) quad: the SAME
    recipe in two cohorts is two independent cells — this is the axis the D105
    pair and D106 triple cannot express."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cohort(conn, gated, cohort="xsect", n_components=4, n_rejects=6, tag="x")
        _populate_cohort(conn, gated, cohort="single", n_components=1, n_rejects=9, tag="s")
        weights = compute_cohort_yield_weights(conn, gated)
    assert _XSECT in weights
    assert _SINGLE in weights


def test_xsect_outweighs_single_for_momentum_the_40x_flip(tmp_path: Path) -> None:
    """THE headline (§3): cross-sectional momentum mints ~40x single-name. With
    xsect minting and single near-zero on the same recipe, the xsect cohort cell
    must carry the higher component-rate posterior -> the sampler tilts the
    cohort draw toward xsect for momentum configs."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        # xsect: 20 components / 30 decided (~40%); single: 1 / 50 (~0.96%)
        _populate_cohort(conn, gated, cohort="xsect", n_components=20, n_rejects=30, tag="x")
        _populate_cohort(conn, gated, cohort="single", n_components=1, n_rejects=49, tag="s")
        weights = compute_cohort_yield_weights(conn, gated)
    assert weights[_XSECT] > weights[_SINGLE]
    # and the gap is material, not a rounding artifact of the shared anchor
    assert weights[_XSECT] > 3.0 * weights[_SINGLE]


def test_thin_cohort_cell_shrinks_toward_triple(tmp_path: Path) -> None:
    """Hierarchical anchor (D106): a thin cohort cell is pulled toward its
    (hyp, directional, bucket) triple rate, so it cannot ride its own noise. A
    single-component xsect cell sits strictly between the global prior and its
    own raw rate, anchored by the triple's aggregated evidence."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        # triple is dominated by a big single-name cohort at a low rate; the thin
        # xsect cell (1 comp / 1 decided, raw 100%) must be shrunk toward it.
        _populate_cohort(conn, gated, cohort="single", n_components=2, n_rejects=98, tag="s")
        _populate_cohort(conn, gated, cohort="xsect", n_components=1, n_rejects=0, tag="x")
        weights = compute_cohort_yield_weights(conn, gated)
    # raw xsect rate is 1.0; the shrunk posterior must be far below it (pulled to
    # the triple, which is dominated by the ~2% single cohort).
    assert weights[_XSECT] < 0.5
    # but still above the heavily-rejected single cohort (it has the only comp at
    # 100% raw vs single's 2%): the fine evidence still moves it up off the anchor
    assert weights[_XSECT] > weights[_SINGLE]


def test_component_count_drives_weight_not_trades_anti_goodhart(tmp_path: Path) -> None:
    """Anti-Goodhart (the D105-lineage property): a cohort that trades heavily but
    mints ZERO components does not out-weigh a cohort with components. Trades
    cannot manufacture cohort weight; only Crucible-accepted components do."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        # single: busy but dead (0 comp, 200 traded rejects); xsect: 5 comp
        _populate_cohort(conn, gated, cohort="single", n_components=0, n_rejects=200, tag="s")
        _populate_cohort(conn, gated, cohort="xsect", n_components=5, n_rejects=5, tag="x")
        weights = compute_cohort_yield_weights(conn, gated)
    assert weights[_XSECT] > weights[_SINGLE]


def test_prior_version_components_downweighted(tmp_path: Path) -> None:
    """D081 version scoping: a prior-version component contributes
    COMPONENT_PRIOR_VERSION_WEIGHT (0.25), so an all-prior-version xsect cohort
    carries less effective evidence than the same count on the current version —
    its posterior shrinks harder toward the triple anchor."""
    with db_connection(tmp_path / "forge.db") as conn:
        cur = _insert_batch(conn, grammar_version="v22")
        old = _insert_batch(conn, grammar_version="v21")
        gated_cur: list[GatedRun] = []
        gated_old: list[GatedRun] = []
        # identical raw shape, only the batch version differs
        _populate_cohort(
            conn, gated_cur, cohort="xsect", n_components=4, n_rejects=4, batch_id=cur, tag="cur"
        )
        _populate_cohort(
            conn, gated_old, cohort="xsect", n_components=4, n_rejects=4, batch_id=old, tag="old"
        )
        # add a single cohort to each so the triple anchor exists
        _populate_cohort(
            conn, gated_cur, cohort="single", n_components=1, n_rejects=20, batch_id=cur, tag="cur"
        )
        _populate_cohort(
            conn, gated_old, cohort="single", n_components=1, n_rejects=20, batch_id=old, tag="old"
        )
        w_cur = compute_cohort_yield_weights(conn, gated_cur, current_grammar_version="v22")
        w_old = compute_cohort_yield_weights(conn, gated_old, current_grammar_version="v22")
    # the prior-version xsect cell has 0.25x the effective evidence -> shrunk
    # harder toward the (lower) triple anchor -> a smaller posterior.
    assert w_old[_XSECT] < w_cur[_XSECT]


def test_cold_start_hypothesis_drops_prior_version_rows(tmp_path: Path) -> None:
    """A cold-start hypothesis drops its prior-version rows entirely. With only
    prior-version evidence under a cold-start hypothesis, the cells vanish."""
    with db_connection(tmp_path / "forge.db") as conn:
        old = _insert_batch(conn, grammar_version="v21")
        gated: list[GatedRun] = []
        _populate_cohort(
            conn,
            gated,
            hypothesis="mean_reversion",
            directional="rsi_2",
            cohort="xsect",
            n_components=5,
            batch_id=old,
            tag="cs",
        )
        weights = compute_cohort_yield_weights(
            conn,
            gated,
            current_grammar_version="v22",
            cold_start_hypotheses=frozenset({"mean_reversion"}),
        )
    assert weights == {}


def test_absent_cohort_is_omitted_for_sampler_fallback(tmp_path: Path) -> None:
    """The fallback contract the sampler's chain relies on: a cohort with no rows
    is simply ABSENT from the map (never synthesised at the prior). The sampler
    then falls back to the triple / fixed share for that cohort — the
    scale-coherent chain cohort -> triple -> share. Here only xsect has evidence,
    so single is omitted rather than invented."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cohort(conn, gated, cohort="xsect", n_components=3, n_rejects=7, tag="x")
        weights = compute_cohort_yield_weights(conn, gated)
    assert _XSECT in weights
    assert _SINGLE not in weights  # absent -> sampler falls back, not a prior cell
    assert COMPONENT_HIER_PRIOR_STRENGTH > 0.0  # anchor strength is configured


def test_determinism_same_inputs_same_output(tmp_path: Path) -> None:
    """Hard rule #6: a pure function of (submissions, gated_runs)."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cohort(conn, gated, cohort="xsect", n_components=7, n_rejects=20, tag="x")
        _populate_cohort(conn, gated, cohort="single", n_components=2, n_rejects=40, tag="s")
        a = compute_cohort_yield_weights(conn, gated)
        b = compute_cohort_yield_weights(conn, gated)
    assert a == b
    assert COMPONENT_PRIOR_VERSION_WEIGHT == 0.25  # the scoping constant is wired
