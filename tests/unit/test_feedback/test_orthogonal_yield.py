"""Tests for the H4 orthogonal-yield marginal-value discount.

NEW_HYPOTHESES_V11_PLAN.md H4. D105 re-aimed the feedback reward to raw
component-rate, which over-concentrates sampling into *correlated* vol_event
sleeves (122 components, 36 on AAPL alone — the marginal portfolio value of the
37th AAPL long-vol clone ~ 0; pod-shop uncorrelated-sleeve model). H4 discounts
each ``(hypothesis, directional, underlying-name)`` FACTOR CELL's draw weight by
a Grinold/pod-shop marginal-value factor ``(1 + m) ** -strength`` (m = the cell's
component count), so an over-mined name yields draw probability to its minting
peers (D108: name granularity — class granularity only dilutes toward the
non-minting diversified class).

Anti-Goodhart by construction (the property these tests pin): the discount is a
function of the COMPONENT count only, never the trade count — discount = 1.0 at
m = 0, so a heavily-traded-but-componentless cell is left untouched (never
inflated, never penalised for trading), and only over-represented cells bite.
"""

from __future__ import annotations

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
    COMPONENT_PRIOR_VERSION_WEIGHT,
    compute_orthogonal_yield_discounts,
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
    directional: str = "put_call_flow",
    underlying: str | None = "AAPL",
    dte_bucket: str = "swing_short",
) -> StrategyConfig:
    """A config whose factor cell is (hypothesis, directional, underlying-name)."""
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
                indicators=("realized_vol",),
                params={"threshold": 0.20, "op": "<"},
            ),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(delta_target=0.45, delta_tolerance=0.05, dte_min=14, dte_max=21),
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
    # A full slate of passed gates so the (irrelevant-to-H4) tiebreak signal is
    # strong — proving the discount keys on the component decision, not on
    # gate-progress or trades.
    gate_results = {
        "g0": GateResult(gate_name="g0", passed=True),
        "g1": GateResult(gate_name="g1", passed=True),
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


def _populate_cell(
    conn: Any,
    gated: list[GatedRun],
    *,
    hypothesis: str,
    directional: str,
    underlying: str,
    n_components: int,
    n_rejects: int = 0,
    batch_id: str | None = None,
    tag: str = "c",
) -> None:
    """Insert ``n_components`` component runs + ``n_rejects`` traded rejects into
    one factor cell."""
    for i in range(n_components):
        ch = f"{tag}_comp_{i:04d}"
        _insert_submission(
            conn,
            config=_config(hypothesis, ch, directional=directional, underlying=underlying),
            config_hash=ch,
            batch_id=batch_id,
        )
        gated.append(_gated_run(config_hash=ch, decision="component", trade_count=120))
    for i in range(n_rejects):
        ch = f"{tag}_rej_{i:04d}"
        _insert_submission(
            conn,
            config=_config(hypothesis, ch, directional=directional, underlying=underlying),
            config_hash=ch,
            batch_id=batch_id,
        )
        gated.append(_gated_run(config_hash=ch, decision="reject", trade_count=300))


# A vol_event x put_call_flow x AAPL name cell (D108: cells key on the NAME).
_VE = "volatility_event"
_PCF = "put_call_flow"
_CELL = (_VE, _PCF, "AAPL")


def test_empty_gated_runs_returns_empty(tmp_path: Path) -> None:
    """Cold-start contract: no gated runs -> {} -> the sampler applies no
    discount (byte-identical to the pre-H4 underlying draw)."""
    with db_connection(tmp_path / "forge.db") as conn:
        assert compute_orthogonal_yield_discounts(conn, []) == {}


def test_zero_component_cell_is_absent_anti_goodhart(tmp_path: Path) -> None:
    """THE core anti-Goodhart property: a cell that trades heavily but mints ZERO
    components is NOT in the discount map — H4 keys on component count, never on
    trades, so a dead-but-busy cell is left at discount 1.0 (not inflated, not
    penalised for trading). Contrast the D105 reward, which the trade term once
    Goodharted toward exactly such cells.
    """
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=0,
            n_rejects=40,
        )
        discounts = compute_orthogonal_yield_discounts(conn, gated)
    assert discounts == {}  # no component -> no cell -> consumer treats as 1.0


def test_crowded_cell_discounted_exact_grinold_math(tmp_path: Path) -> None:
    """A cell with m components is discounted by (1 + m) ** -strength. At
    strength=0.5 (the pure Grinold/pod-shop sqrt form), 3 components -> 1/2."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=3,
            n_rejects=10,
        )
        discounts = compute_orthogonal_yield_discounts(conn, gated, strength=0.5, min_discount=0.0)
    assert set(discounts) == {_CELL}
    assert discounts[_CELL] == pytest.approx((1.0 + 3.0) ** -0.5)  # = 0.5


def test_discount_monotone_decreasing_in_component_count(tmp_path: Path) -> None:
    """More components in a cell -> a smaller discount (the m-th correlated
    sleeve is worth less). Crowded cells bite harder."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(  # 3 comps on the (ve, pcf, AAPL) name cell
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=3,
            tag="a",
        )
        _populate_cell(  # 15 comps on the (mr, rsi_2, NVDA) name cell
            conn,
            gated,
            hypothesis="mean_reversion",
            directional="rsi_2",
            underlying="NVDA",
            n_components=15,
            tag="b",
        )
        discounts = compute_orthogonal_yield_discounts(conn, gated, strength=0.5, min_discount=0.0)
    light = discounts[(_VE, _PCF, "AAPL")]
    heavy = discounts[("mean_reversion", "rsi_2", "NVDA")]
    assert heavy < light
    assert heavy == pytest.approx((1.0 + 15.0) ** -0.5)  # 16^-0.5 = 0.25


def test_factor_cell_separates_directional_and_name(tmp_path: Path) -> None:
    """The cell key is the full (hypothesis, directional, underlying-NAME) triple
    (D108): same hypothesis but a different directional, or a different NAME, is
    a DIFFERENT (independent) sleeve — this is what lets H4 spread an over-mined
    name across its peers instead of toward the non-minting diversified class."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        # same hyp+name, different directional
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional="put_call_flow",
            underlying="AAPL",
            n_components=3,
            tag="pcf",
        )
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional="iv_rank",
            underlying="AAPL",
            n_components=3,
            tag="ivr",
        )
        # same hyp+directional, different NAME (the under-mined peer)
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional="put_call_flow",
            underlying="NVDA",
            n_components=1,
            tag="peer",
        )
        discounts = compute_orthogonal_yield_discounts(conn, gated, strength=0.5, min_discount=0.0)
    assert (_VE, "put_call_flow", "AAPL") in discounts
    assert (_VE, "iv_rank", "AAPL") in discounts
    assert (_VE, "put_call_flow", "NVDA") in discounts
    # the under-mined peer (NVDA, 1 component) is discounted less than the
    # over-mined name (AAPL, 3 components) on the same hypothesis+directional
    assert discounts[(_VE, "put_call_flow", "NVDA")] > discounts[(_VE, "put_call_flow", "AAPL")]


def test_min_discount_caps_the_cut(tmp_path: Path) -> None:
    """``min_discount`` is a hard floor on the discount itself — a hugely
    over-mined cell can't be cut past it, so H4 can never starve a productive
    cell to ~0 (the sampler's exploration floor is a second guard on top)."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=15,
            tag="big",
        )
        # raw 16^-0.5 = 0.25, but min_discount=0.4 caps it
        discounts = compute_orthogonal_yield_discounts(conn, gated, strength=0.5, min_discount=0.4)
    assert discounts[_CELL] == pytest.approx(0.4)


def test_strength_zero_disables_the_discount(tmp_path: Path) -> None:
    """strength=0 -> (1+m)**0 = 1.0 for every cell -> a no-op discount (the
    'A' arm of the A/B at the curve level)."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=10,
            tag="z",
        )
        discounts = compute_orthogonal_yield_discounts(conn, gated, strength=0.0, min_discount=0.0)
    assert discounts[_CELL] == pytest.approx(1.0)


def test_default_strength_is_gentler_than_pure_sqrt(tmp_path: Path) -> None:
    """STATUS.md flagged the pure 1/sqrt(1+37)~0.16 (6x cut to the top cell) as
    too aggressive for 'yield roughly flat'. The shipped default must cut the
    top live cell (~37 components) by clearly LESS than the sqrt form."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=37,
            tag="top",
        )
        default = compute_orthogonal_yield_discounts(conn, gated)
        sqrt_form = compute_orthogonal_yield_discounts(conn, gated, strength=0.5, min_discount=0.0)
    assert default[_CELL] > sqrt_form[_CELL]  # gentler
    assert default[_CELL] < 1.0  # but still bites the top cell


def test_relative_value_contributes_no_cell(tmp_path: Path) -> None:
    """relative_value carries underlying=None (pairs legs are Crucible-resolved,
    D098) and has no single-name underlying draw -> it contributes no factor
    cell and H4 never touches it."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        for i in range(5):
            ch = f"rv_{i:04d}"
            _insert_submission(
                conn,
                config=_config("relative_value", ch, underlying=None),
                config_hash=ch,
            )
            gated.append(_gated_run(config_hash=ch, decision="component", trade_count=120))
        # plus one real single-name cell so the result isn't trivially empty
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=2,
            tag="ve",
        )
        discounts = compute_orthogonal_yield_discounts(conn, gated)
    assert all(hyp != "relative_value" for (hyp, _d, _c) in discounts)
    assert _CELL in discounts


def test_prior_version_components_downweighted(tmp_path: Path) -> None:
    """D081 version scoping: a prior-version component contributes
    COMPONENT_PRIOR_VERSION_WEIGHT (0.25) to the count, so a cell of 4
    prior-version components counts as 1.0 effective -> a gentler discount than
    4 current-version ones."""
    with db_connection(tmp_path / "forge.db") as conn:
        cur = _insert_batch(conn, grammar_version="v11")
        old = _insert_batch(conn, grammar_version="v10")
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=4,
            batch_id=old,
            tag="old",
        )
        discounts = compute_orthogonal_yield_discounts(
            conn, gated, strength=0.5, min_discount=0.0, current_grammar_version="v11"
        )
        # 4 prior-version components -> count = 4 * 0.25 = 1.0 -> (1+1)^-0.5
        assert discounts[_CELL] == pytest.approx((1.0 + 4 * COMPONENT_PRIOR_VERSION_WEIGHT) ** -0.5)
        assert cur  # (batch row exists; current-version cell intentionally empty)


def test_cold_start_hypothesis_drops_prior_version_rows(tmp_path: Path) -> None:
    """A cold-start hypothesis drops its prior-version rows entirely (not just
    down-weights) — mirrors the trade_rate_priors / component-rate engine. With
    only prior-version components in a cold-start hypothesis, the cell vanishes."""
    with db_connection(tmp_path / "forge.db") as conn:
        old = _insert_batch(conn, grammar_version="v10")
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis="mean_reversion",
            directional="rsi_2",
            underlying="AAPL",
            n_components=5,
            batch_id=old,
            tag="cs",
        )
        discounts = compute_orthogonal_yield_discounts(
            conn,
            gated,
            strength=0.5,
            min_discount=0.0,
            current_grammar_version="v11",
            cold_start_hypotheses=frozenset({"mean_reversion"}),
        )
    assert discounts == {}  # all rows dropped -> no cell


def test_determinism_same_inputs_same_output(tmp_path: Path) -> None:
    """Hard rule #6: a pure function of (submissions, gated_runs) — identical
    inputs give identical discounts across calls."""
    with db_connection(tmp_path / "forge.db") as conn:
        gated: list[GatedRun] = []
        _populate_cell(
            conn,
            gated,
            hypothesis=_VE,
            directional=_PCF,
            underlying="AAPL",
            n_components=7,
            n_rejects=20,
            tag="d",
        )
        a = compute_orthogonal_yield_discounts(conn, gated)
        b = compute_orthogonal_yield_discounts(conn, gated)
    assert a == b
