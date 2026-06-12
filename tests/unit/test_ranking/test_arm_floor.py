"""Tests for ``forge.ranking.arm_floor`` (D136 — per-arm exploration floor, data side).

An *arm* is ``(role, indicator_id)`` for role ∈ {directional, regime_filter}.
An arm is *mature* once it has accrued ≥ K honest-era verdicts (decided_at on
or after the D128 clean-era label cut); everything else — including arms never
seen — is young and floor-eligible. Design: `docs/proposals/learned-ranker.md`
§F3 (floor half), approved D132; pulled forward by the v18 GO doc item 5
(ranker-side starvation delivered v17's new arms at ~8x under raw emission).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import duckdb
from crucible_contracts import SignalSpec

from forge.persistence.db import db_connection
from forge.ranking.arm_floor import (
    YOUNG_ARM_VERDICT_THRESHOLD,
    compute_mature_arms,
    extract_arms,
)
from tests.fixtures.strategy_configs import minimal_strategy_config

# Naive-UTC by repo convention (DuckDB TIMESTAMP columns are naive-UTC).
_POST_CUT = datetime(2026, 6, 10, 18, 0, 0)  # noqa: DTZ001
_PRE_CUT = datetime(2026, 6, 10, 12, 0, 0)  # noqa: DTZ001


def _config_with(directional: str, regime: str, chain: str | None = None):
    signals = [
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=(directional,),
            params={"threshold": 1.0},
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=(regime,),
            params={"threshold": 1.0},
        ),
    ]
    if chain is not None:
        signals.append(
            SignalSpec(
                id=f"sig_chain_{chain}",
                type="passthrough",
                role="confluence",
                indicators=(chain,),
            )
        )
    return minimal_strategy_config(signals=tuple(signals))


def _seed_verdicts(
    conn: duckdb.DuckDBPyConnection,
    *,
    directional: str,
    regime: str,
    n: int,
    decided_at: datetime = _POST_CUT,
) -> None:
    """One submission + ``n`` verdict rows (refit rows share the hash)."""
    config_hash = uuid.uuid4().hex[:16]
    conn.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            _config_with(directional, regime).model_dump_json(),
            _PRE_CUT,
            "gated",
        ],
    )
    for _ in range(n):
        conn.execute(
            "INSERT INTO verdicts (crucible_run_id, config_hash, decision, decided_at, "
            "gate_results, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), config_hash, "reject", decided_at, json.dumps({}), decided_at],
        )


# ---------------------------------------------------------------------------
# extract_arms — the candidate side
# ---------------------------------------------------------------------------


def test_extract_arms_directional_and_regime_only() -> None:
    """Arms are (role, indicator_id) for the two thesis-bearing roles; the
    X1/X2 confluence chain signal is sizing plumbing, not an arm."""
    cfg = _config_with("rsi_2", "iv_rank", chain="realized_vol")
    assert extract_arms(cfg) == frozenset({("directional", "rsi_2"), ("regime_filter", "iv_rank")})


def test_extract_arms_covers_every_indicator_in_a_signal() -> None:
    cfg = minimal_strategy_config(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("rsi_2", "bb_pct"),
                params={"threshold": 1.0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 1.0},
            ),
        )
    )
    assert extract_arms(cfg) == frozenset(
        {("directional", "rsi_2"), ("directional", "bb_pct"), ("regime_filter", "iv_rank")}
    )


# ---------------------------------------------------------------------------
# compute_mature_arms — the verdict side
# ---------------------------------------------------------------------------


def test_mature_exactly_at_threshold() -> None:
    with db_connection(":memory:") as conn:
        _seed_verdicts(conn, directional="rsi_2", regime="iv_rank", n=YOUNG_ARM_VERDICT_THRESHOLD)
        _seed_verdicts(conn, directional="macd", regime="adx", n=YOUNG_ARM_VERDICT_THRESHOLD - 1)
        mature = compute_mature_arms(conn)
    assert ("directional", "rsi_2") in mature
    assert ("regime_filter", "iv_rank") in mature
    assert ("directional", "macd") not in mature
    assert ("regime_filter", "adx") not in mature


def test_pre_era_cut_rows_do_not_count() -> None:
    """The count mirrors the model's training window (the D128 clean-era
    label cut): pre-cut verdicts are not evidence the floor can retire on."""
    with db_connection(":memory:") as conn:
        _seed_verdicts(
            conn,
            directional="rsi_2",
            regime="iv_rank",
            n=YOUNG_ARM_VERDICT_THRESHOLD,
            decided_at=_PRE_CUT,
        )
        mature = compute_mature_arms(conn)
    assert mature == frozenset()


def test_counts_accumulate_across_distinct_configs() -> None:
    """The arm is the unit, not the config: two configs sharing a directional
    pool their verdict counts for that arm."""
    half = YOUNG_ARM_VERDICT_THRESHOLD // 2 + 1
    with db_connection(":memory:") as conn:
        _seed_verdicts(conn, directional="rsi_2", regime="iv_rank", n=half)
        _seed_verdicts(conn, directional="rsi_2", regime="adx", n=half)
        mature = compute_mature_arms(conn)
    assert ("directional", "rsi_2") in mature
    assert ("regime_filter", "iv_rank") not in mature
    assert ("regime_filter", "adx") not in mature


def test_empty_db_means_every_arm_young() -> None:
    with db_connection(":memory:") as conn:
        assert compute_mature_arms(conn) == frozenset()
