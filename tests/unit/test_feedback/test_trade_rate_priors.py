"""Tests for `forge.feedback.trade_rate_priors` (D076 / Q16).

Per-(hypothesis, dte_bucket, directional_family) Beta-smoothed posterior
P(n_trades >= min_trades), computed from the gated_runs cohort. Powers
the empirical-prior `expected_trades` filter rewrite.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from crucible_contracts import (
    GatedRun,
    GateResult,
    PromotionDecision,
    RunResult,
)

from forge.feedback.trade_rate_priors import (
    BucketStats,
    compute_trade_rate_priors,
)
from forge.persistence.db import db_connection
from tests.fixtures.strategy_configs import minimal_registry_snapshot


def _gated_run(*, config_hash: str, trade_count: int) -> GatedRun:
    run_id = str(uuid.uuid4())
    return GatedRun(
        run=RunResult(
            run_id=run_id,
            config_hash=config_hash,
            metrics={"n_trades": float(trade_count)},
            trade_count=trade_count,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 6, 30),
        ),
        decision=PromotionDecision(
            run_id=run_id,
            decision="reject",
            gate_results={
                "min_oos_trade_count": GateResult(
                    gate_name="min_oos_trade_count",
                    passed=trade_count >= 30,
                    value=float(trade_count),
                    threshold=30.0,
                ),
            },
            decided_at=datetime.now(UTC),
            decided_by="test/v1",
        ),
    )


def _config_json(
    *,
    hypothesis: str,
    dte_bucket: str,
    directional_indicator: str,
) -> str:
    return json.dumps(
        {
            "name": f"cfg_{hypothesis}_{dte_bucket}_{directional_indicator}",
            "hypothesis": hypothesis,
            "dte_bucket": dte_bucket,
            "signals": [
                {
                    "id": "sig_directional",
                    "type": "threshold",
                    "role": "directional",
                    "indicators": [directional_indicator],
                    "params": {"threshold": 30.0, "op": "<"},
                },
                {
                    "id": "sig_regime",
                    "type": "threshold",
                    "role": "regime_filter",
                    "indicators": ["iv_rank"],
                    "params": {"threshold": 0.50, "op": ">"},
                },
            ],
        },
    )


def _insert(conn: Any, *, config_hash: str, config_json: str) -> None:
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
            config_json,
            datetime.now(UTC),
            "submitted",
        ],
    )


def test_empty_gated_runs_returns_empty(tmp_path: Path) -> None:
    """Cold start: no gated cohort → empty dict → filter falls back to activations."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
        out = compute_trade_rate_priors(conn, [], registry)
    assert out == {}


def test_bucket_key_is_hypothesis_dte_bucket_family(tmp_path: Path) -> None:
    """One config → one bucket keyed by (hypothesis, dte_bucket, directional_family)."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
        _insert(
            conn,
            config_hash="h0",
            config_json=_config_json(
                hypothesis="mean_reversion",
                dte_bucket="swing_short",
                directional_indicator="rsi_2",
            ),
        )
        out = compute_trade_rate_priors(
            conn,
            [_gated_run(config_hash="h0", trade_count=100)],
            registry,
        )
    # rsi_2 belongs to mean_reversion family in the minimal_registry_snapshot fixture
    assert ("mean_reversion", "swing_short", "mean_reversion") in out


def test_posterior_beta_smoothed(tmp_path: Path) -> None:
    """3 pass / 7 fail with Beta(1, 10) prior → (1+3) / (11+10) = 4/21 ≈ 0.190."""
    registry = minimal_registry_snapshot()
    gated = []
    with db_connection(tmp_path / "forge.db") as conn:
        for i, n_trades in enumerate(
            # 3 above min_trades (50) + 7 below
            [60, 80, 200, 0, 0, 10, 20, 30, 40, 45],
        ):
            ch = f"h_{i:03d}"
            _insert(
                conn,
                config_hash=ch,
                config_json=_config_json(
                    hypothesis="mean_reversion",
                    dte_bucket="swing_short",
                    directional_indicator="rsi_2",
                ),
            )
            gated.append(_gated_run(config_hash=ch, trade_count=n_trades))
        out = compute_trade_rate_priors(
            conn,
            gated,
            registry,
            min_trades=50,
            alpha=1.0,
            beta=10.0,
        )

    key = ("mean_reversion", "swing_short", "mean_reversion")
    stats = out[key]
    assert stats.n_total == 10
    assert stats.n_pass == 3  # n_trades >= 50
    assert stats.n_zero_trade == 2
    # Posterior = (alpha + n_pass) / (alpha + beta + n_total) = 4 / 21
    assert stats.posterior_p_pass == pytest.approx(4 / 21, rel=1e-6)


def test_unknown_indicator_silently_skipped(tmp_path: Path) -> None:
    """A directional signal pointing at an indicator not in the registry
    is skipped (the bucket can't be keyed without a family)."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
        _insert(
            conn,
            config_hash="h0",
            config_json=_config_json(
                hypothesis="mean_reversion",
                dte_bucket="swing_short",
                directional_indicator="totally_made_up_indicator",
            ),
        )
        out = compute_trade_rate_priors(
            conn,
            [_gated_run(config_hash="h0", trade_count=100)],
            registry,
        )
    assert out == {}


def test_corrupt_config_json_skipped(tmp_path: Path) -> None:
    """A submission with non-dict / missing-fields config_json doesn't crash."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
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
        out = compute_trade_rate_priors(
            conn,
            [_gated_run(config_hash="corrupt", trade_count=100)],
            registry,
        )
    assert out == {}


def test_gated_run_without_submission_is_ignored(tmp_path: Path) -> None:
    """A gated_run whose config_hash isn't in submissions can't be bucketed."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
        out = compute_trade_rate_priors(
            conn,
            [_gated_run(config_hash="orphan", trade_count=100)],
            registry,
        )
    assert out == {}


def test_different_buckets_isolated(tmp_path: Path) -> None:
    """Configs in different (hypothesis, dte_bucket, family) buckets are
    not blended."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
        gated = []
        # mean_reversion / swing_short / mean_reversion family: 5 pass / 0 fail
        for i in range(5):
            ch = f"mr_{i}"
            _insert(
                conn,
                config_hash=ch,
                config_json=_config_json(
                    hypothesis="mean_reversion",
                    dte_bucket="swing_short",
                    directional_indicator="rsi_2",
                ),
            )
            gated.append(_gated_run(config_hash=ch, trade_count=100))
        # trend_continuation / swing_short / trend family: 0 pass / 5 fail
        for i in range(5):
            ch = f"tc_{i}"
            _insert(
                conn,
                config_hash=ch,
                config_json=_config_json(
                    hypothesis="trend_continuation",
                    dte_bucket="swing_short",
                    directional_indicator="momentum_252",
                ),
            )
            gated.append(_gated_run(config_hash=ch, trade_count=0))
        out = compute_trade_rate_priors(conn, gated, registry, min_trades=50)

    mr_key = ("mean_reversion", "swing_short", "mean_reversion")
    tc_key = ("trend_continuation", "swing_short", "trend")
    assert out[mr_key].n_pass == 5
    assert out[mr_key].n_zero_trade == 0
    assert out[tc_key].n_pass == 0
    assert out[tc_key].n_zero_trade == 5
    # Mean_reversion posterior is much higher
    assert out[mr_key].posterior_p_pass > out[tc_key].posterior_p_pass


def test_deterministic_given_same_inputs(tmp_path: Path) -> None:
    """Same gated_runs + same submissions + same registry → same output."""
    registry = minimal_registry_snapshot()
    with db_connection(tmp_path / "forge.db") as conn:
        gated = []
        for i in range(10):
            ch = f"h_{i:03d}"
            _insert(
                conn,
                config_hash=ch,
                config_json=_config_json(
                    hypothesis="mean_reversion",
                    dte_bucket="swing_short",
                    directional_indicator="rsi_2",
                ),
            )
            gated.append(_gated_run(config_hash=ch, trade_count=i * 10))
        a = compute_trade_rate_priors(conn, gated, registry, min_trades=50)
        b = compute_trade_rate_priors(conn, gated, registry, min_trades=50)
    assert a == b


def test_bucket_stats_frozen() -> None:
    """BucketStats is a frozen dataclass — instance mutation raises."""
    s = BucketStats(n_total=10, n_pass=3, n_zero_trade=2, posterior_p_pass=0.19)
    with pytest.raises((AttributeError, TypeError)):
        s.n_total = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# D081 — grammar-version weighting
#
# A config submitted under grammar vN should be judged by the trade behaviour
# of vN configs: grammar changes (e.g. D077-D079) are exactly what shift trade
# rates. `current_grammar_version` up-weights current-version runs; prior
# versions are DOWN-weighted (not discarded), so a thin bucket with no
# current-version data yet — e.g. relative_value with 0 v4 gated runs — keeps
# its legacy signal instead of going inert and re-flooding Crucible.
# ---------------------------------------------------------------------------

_V3_BATCH = "33333333-3333-3333-3333-333333333333"
_V4_BATCH = "44444444-4444-4444-4444-444444444444"


def _seed_batch(conn: Any, *, batch_id: str, grammar_version: str) -> None:
    conn.execute(
        "INSERT INTO batch_summaries (forge_batch_id, batch_size, submitted_at, "
        "grammar_version, registry_version) VALUES (?, ?, ?, ?, ?)",
        [batch_id, 200, datetime.now(UTC), grammar_version, "reg"],
    )


def _insert_in_batch(conn: Any, *, config_hash: str, config_json: str, batch_id: str) -> None:
    conn.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), batch_id, config_hash, config_json, datetime.now(UTC), "submitted"],
    )


def test_version_weighting_upweights_current_grammar(tmp_path: Path) -> None:
    """Bucket all-zero under v3 but passing under v4: scoping to v4 RAISES the
    posterior (v4 evidence up-weighted) without discarding the v3 runs."""
    registry = minimal_registry_snapshot()
    cj = _config_json(
        hypothesis="mean_reversion", dte_bucket="swing_short", directional_indicator="rsi_2"
    )
    gated = []
    with db_connection(tmp_path / "forge.db") as conn:
        _seed_batch(conn, batch_id=_V3_BATCH, grammar_version="v3")
        _seed_batch(conn, batch_id=_V4_BATCH, grammar_version="v4")
        for i in range(5):  # v3 legacy — all zero-trade
            ch = f"v3_{i}"
            _insert_in_batch(conn, config_hash=ch, config_json=cj, batch_id=_V3_BATCH)
            gated.append(_gated_run(config_hash=ch, trade_count=0))
        for i in range(4):  # v4 — all pass (100 trades)
            ch = f"v4_{i}"
            _insert_in_batch(conn, config_hash=ch, config_json=cj, batch_id=_V4_BATCH)
            gated.append(_gated_run(config_hash=ch, trade_count=100))
        unscoped = compute_trade_rate_priors(
            conn, gated, registry, min_trades=50, alpha=1.0, beta=10.0
        )
        scoped = compute_trade_rate_priors(
            conn, gated, registry, min_trades=50, alpha=1.0, beta=10.0,
            current_grammar_version="v4", prior_version_weight=0.25,
        )
    key = ("mean_reversion", "swing_short", "mean_reversion")
    # Unscoped: all weight 1.0 -> (1+4)/(11+9) = 5/20.
    assert unscoped[key].posterior_p_pass == pytest.approx(5 / 20, rel=1e-6)
    # Scoped v4: v4 weight 1.0 (4 pass), v3 weight 0.25 (5 fail).
    # weighted_pass=4, weighted_n=4 + 5*0.25=5.25 -> (1+4)/(11+5.25) = 5/16.25.
    assert scoped[key].posterior_p_pass == pytest.approx(5 / 16.25, rel=1e-6)
    assert scoped[key].posterior_p_pass > unscoped[key].posterior_p_pass
    # Raw counts are unchanged — they feed the cold-start sample floor + telemetry.
    assert (scoped[key].n_total, scoped[key].n_pass, scoped[key].n_zero_trade) == (9, 4, 5)


def test_version_weighting_downweights_stale_good_bucket(tmp_path: Path) -> None:
    """Bucket good under v3 but bad under v4: scoping to v4 LOWERS the posterior."""
    registry = minimal_registry_snapshot()
    cj = _config_json(
        hypothesis="mean_reversion", dte_bucket="swing_short", directional_indicator="rsi_2"
    )
    gated = []
    with db_connection(tmp_path / "forge.db") as conn:
        _seed_batch(conn, batch_id=_V3_BATCH, grammar_version="v3")
        _seed_batch(conn, batch_id=_V4_BATCH, grammar_version="v4")
        for i in range(8):  # v3 legacy — all pass
            ch = f"v3_{i}"
            _insert_in_batch(conn, config_hash=ch, config_json=cj, batch_id=_V3_BATCH)
            gated.append(_gated_run(config_hash=ch, trade_count=100))
        for i in range(2):  # v4 — all zero
            ch = f"v4_{i}"
            _insert_in_batch(conn, config_hash=ch, config_json=cj, batch_id=_V4_BATCH)
            gated.append(_gated_run(config_hash=ch, trade_count=0))
        unscoped = compute_trade_rate_priors(
            conn, gated, registry, min_trades=50, alpha=1.0, beta=10.0
        )
        scoped = compute_trade_rate_priors(
            conn, gated, registry, min_trades=50, alpha=1.0, beta=10.0,
            current_grammar_version="v4", prior_version_weight=0.25,
        )
    key = ("mean_reversion", "swing_short", "mean_reversion")
    # Unscoped: (1+8)/(11+10) = 9/21.
    assert unscoped[key].posterior_p_pass == pytest.approx(9 / 21, rel=1e-6)
    # Scoped v4: v3 weight 0.25 (8 pass -> 2.0), v4 weight 1.0 (2 fail).
    # weighted_pass=2.0, weighted_n=8*0.25 + 2=4.0 -> (1+2)/(11+4) = 3/15.
    assert scoped[key].posterior_p_pass == pytest.approx(3 / 15, rel=1e-6)
    assert scoped[key].posterior_p_pass < unscoped[key].posterior_p_pass


def test_version_none_matches_unweighted(tmp_path: Path) -> None:
    """Back-compat: current_grammar_version=None weights every run 1.0,
    reproducing the plain count-based posterior regardless of batch version."""
    registry = minimal_registry_snapshot()
    cj = _config_json(
        hypothesis="mean_reversion", dte_bucket="swing_short", directional_indicator="rsi_2"
    )
    gated = []
    with db_connection(tmp_path / "forge.db") as conn:
        _seed_batch(conn, batch_id=_V3_BATCH, grammar_version="v3")
        _seed_batch(conn, batch_id=_V4_BATCH, grammar_version="v4")
        for i in range(3):
            ch = f"v3_{i}"
            _insert_in_batch(conn, config_hash=ch, config_json=cj, batch_id=_V3_BATCH)
            gated.append(_gated_run(config_hash=ch, trade_count=100))
        for i in range(7):
            ch = f"v4_{i}"
            _insert_in_batch(conn, config_hash=ch, config_json=cj, batch_id=_V4_BATCH)
            gated.append(_gated_run(config_hash=ch, trade_count=0))
        out = compute_trade_rate_priors(
            conn, gated, registry, min_trades=50, alpha=1.0, beta=10.0,
            current_grammar_version=None,
        )
    key = ("mean_reversion", "swing_short", "mean_reversion")
    # 3 pass / 10 total, all weight 1.0 -> (1+3)/(11+10) = 4/21.
    assert out[key].posterior_p_pass == pytest.approx(4 / 21, rel=1e-6)
