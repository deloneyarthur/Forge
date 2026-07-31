"""Arm-B weights — regime gates scored by BOOK-USABLE rate, on the honest arm only.

The estimator's shape is forced by a dispersion test, not chosen: per-CELL book-usable rates
on the honest arm are not distinguishable from a single common rate (X2=38.9, df=37, z=+0.29),
while the REGIME-GATE marginal is (z=+2.16). So a thin cell must fall back to its regime's
marginal instead of trusting its own point estimate, or the weighting chases noise.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest

from forge.core.clock import utc_now
from forge.feedback.book_usable_weights import (
    BOOK_FLOOR,
    compute_book_usable_regime_weights,
)
from forge.persistence.db import db_connection


def _config(regime: str, *, directional: str = "sma_slope", hypothesis: str = "trend_continuation"):
    return json.dumps(
        {
            "hypothesis": hypothesis,
            "dte_bucket": "swing_long",
            "signals": [
                {"role": "directional", "indicators": [directional]},
                {"role": "regime_filter", "indicators": [regime]},
            ],
        }
    )


def _seed(conn, rows, *, selection_mode="prefilter_sample", basis=None) -> None:
    """rows: (config_json, cpcv)."""
    now = utc_now()
    for config_json, cpcv in rows:
        h = uuid.uuid4().hex[:16]
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status, selection_mode) VALUES (?,?,?,?,?,?,?)",
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                h,
                config_json,
                (now - timedelta(days=1)).replace(tzinfo=None),
                "gated",
                selection_mode,
            ],
        )
        conn.execute(
            "INSERT INTO verdicts (crucible_run_id, config_hash, decision, decided_at, "
            "gate_results, measurement_basis, recorded_at) VALUES (?,?,?,?,?,?,?)",
            [
                str(uuid.uuid4()),
                h,
                "component",
                (now - timedelta(hours=1)).replace(tzinfo=None),
                json.dumps({"cpcv_sharpe_p25": {"value": cpcv}}),
                basis,
                (now - timedelta(hours=1)).replace(tzinfo=None),
            ],
        )


def test_cold_start_returns_empty() -> None:
    """No honest rows -> {} so the caller keeps the incumbent map and the arm is inert."""
    with db_connection() as conn:
        assert compute_book_usable_regime_weights(conn) == {}


def test_a_producing_gate_outweighs_a_barren_one() -> None:
    with db_connection() as conn:
        _seed(conn, [(_config("rv_rank"), 1.2)] * 30 + [(_config("rv_rank"), 0.1)] * 90)
        _seed(conn, [(_config("market_state"), 0.1)] * 120)
        w = compute_book_usable_regime_weights(conn)
    good = w[("trend_continuation", "sma_slope", "swing_long", "rv_rank")]
    barren = w[("trend_continuation", "sma_slope", "swing_long", "market_state")]
    assert good > barren


def test_a_barren_gate_is_de_emphasised_but_never_zeroed() -> None:
    """Zeroing a gate removes it from the draw, which is a PRUNE — a grammar decision that
    belongs in an operator-gated version bump, not in a map that reloads every batch."""
    with db_connection() as conn:
        _seed(conn, [(_config("rv_rank"), 1.2)] * 40 + [(_config("rv_rank"), 0.1)] * 80)
        _seed(conn, [(_config("vix_term_slope"), 0.1)] * 200)
        w = compute_book_usable_regime_weights(conn)
    assert w[("trend_continuation", "sma_slope", "swing_long", "vix_term_slope")] > 0.0


def test_thin_cells_on_one_regime_get_the_SAME_weight() -> None:
    """The dispersion result made structural. Two thin cells sharing a regime differ wildly on
    their own point estimates (5% vs 0%), and neither has earned that number — at n<100 the
    honest arm cannot distinguish a cell from the pooled rate. Both must therefore land on the
    shared regime marginal, i.e. identical weights, or the map is ranking noise."""
    with db_connection() as conn:
        # 1-of-20 -> a 5% point estimate it has not earned.
        _seed(
            conn,
            [(_config("hurst", directional="donchian"), 1.2)]
            + [(_config("hurst", directional="donchian"), 0.1)] * 19,
        )
        # 0-of-20 on the same regime -> a 0% point estimate it has not earned either.
        _seed(conn, [(_config("hurst", directional="ema"), 0.1)] * 20)
        w = compute_book_usable_regime_weights(conn)
    lucky = w[("trend_continuation", "donchian", "swing_long", "hurst")]
    unlucky = w[("trend_continuation", "ema", "swing_long", "hurst")]
    assert lucky == pytest.approx(unlucky)


def test_a_well_measured_cell_does_move_off_the_marginal() -> None:
    """The counterpart: past `_MIN_CELL_N` a cell IS allowed its own estimate, or the map could
    never learn anything the regime marginal does not already say."""
    with db_connection() as conn:
        _seed(
            conn,
            [(_config("adx", directional="donchian"), 1.2)] * 60
            + [(_config("adx", directional="donchian"), 0.1)] * 60,
        )
        _seed(conn, [(_config("adx", directional="ema"), 0.1)] * 120)
        w = compute_book_usable_regime_weights(conn)
    producing = w[("trend_continuation", "donchian", "swing_long", "adx")]
    barren = w[("trend_continuation", "ema", "swing_long", "adx")]
    assert producing > barren * 2


def test_selected_and_refit_rows_are_excluded() -> None:
    """Only `prefilter_sample` stage-one rows count. Ranked rows are ranker-selected and the
    refit lane is admitted-only — both collider-conditioned (D337/D338)."""
    with db_connection() as conn:
        _seed(conn, [(_config("rv_rank"), 1.2)] * 50, selection_mode="ranked")
        _seed(conn, [(_config("adx"), 1.2)] * 50, basis="fullhist_refit")
        assert compute_book_usable_regime_weights(conn) == {}


def test_book_floor_is_the_admission_time_figure() -> None:
    assert BOOK_FLOOR == 0.9439
