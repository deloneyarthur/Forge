"""The ve ghost-label cut (D290 / v39 companion) — Crucible's 2026-07-19 relay §1/§6.

23/25 stored-cpcv ve components were GHOSTS (their put_wall/gex/vex/cex staleness
blind spot, fixed their-side 2026-07-18). 34,273 ve verdicts / 657 fictional
components sit inside our clean-era training window — ~10% of ALL positive labels.
Their ask: treat pre-2026-07-18 ve stored scores as unrankable.

The cut: ``volatility_event`` rows decided before ``VE_GHOST_LABEL_CUT``
(2026-07-18) are excluded from every learned trainer — the CLEAN_ERA_LABEL_CUT
precedent (D128) scoped to one hypothesis. Choke points covered here:
hypothesis weights, the D105/D106 component-rate weighters, the ranker dataset
(F3 + tail training), and arm-floor maturity. Non-ve rows and post-cut ve rows
are untouched.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import duckdb
import pytest

from forge.feedback.rejection_weights import (
    VE_GHOST_LABEL_CUT,
    is_ve_ghost_label,
)
from forge.persistence.db import db_connection
from forge.ranking.arm_floor import compute_mature_arms
from forge.ranking.dataset import build_dataset
from tests.fixtures.strategy_configs import minimal_registry_snapshot, minimal_strategy_config

_PRE_CUT = datetime(2026, 7, 10, 12, 0)  # noqa: DTZ001 — naive-UTC convention
_POST_CUT = datetime(2026, 7, 18, 12, 0)  # noqa: DTZ001
_ERA = datetime(2026, 6, 10, 0, 0)  # noqa: DTZ001 — inside the clean era


def _gated_run(*, config_hash: str, decision: str, decided_at: datetime):
    from datetime import date

    from crucible_contracts import GatedRun
    from crucible_contracts.models import PromotionDecision, RunResult

    rid = str(uuid.uuid4())
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v20",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results={},
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )


def _seed_submission(conn: duckdb.DuckDBPyConnection, *, hypothesis: str, config_hash: str) -> None:
    cfg = minimal_strategy_config().model_copy(update={"hypothesis": hypothesis})
    payload = json.loads(cfg.model_dump_json())
    payload["hypothesis"] = hypothesis
    conn.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), str(uuid.uuid4()), config_hash, json.dumps(payload), _PRE_CUT, "gated"],
    )


def _seed_verdict(
    conn: duckdb.DuckDBPyConnection,
    *,
    config_hash: str,
    decision: str,
    decided_at: datetime,
) -> None:
    conn.execute(
        "INSERT INTO verdicts (crucible_run_id, config_hash, decision, decided_at, "
        "gate_results, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), config_hash, decision, decided_at, json.dumps({}), decided_at],
    )


def test_is_ve_ghost_label_boundary() -> None:
    assert is_ve_ghost_label("volatility_event", _PRE_CUT)
    assert not is_ve_ghost_label("volatility_event", _POST_CUT)
    assert not is_ve_ghost_label("volatility_event", VE_GHOST_LABEL_CUT.replace(tzinfo=None))
    assert not is_ve_ghost_label("trend_continuation", _PRE_CUT)


def test_label_frame_excludes_ghost_ve_rows() -> None:
    """The ranker dataset (F3 + tail training) drops pre-cut ve verdicts; the
    same-day trend verdict and the post-cut ve verdict survive."""
    with db_connection() as conn:
        _seed_submission(conn, hypothesis="volatility_event", config_hash="ve_ghost_hash")
        _seed_submission(conn, hypothesis="volatility_event", config_hash="ve_clean_hash")
        _seed_submission(conn, hypothesis="trend_continuation", config_hash="tc_hash")
        _seed_verdict(conn, config_hash="ve_ghost_hash", decision="component", decided_at=_PRE_CUT)
        _seed_verdict(conn, config_hash="ve_clean_hash", decision="reject", decided_at=_POST_CUT)
        _seed_verdict(conn, config_hash="tc_hash", decision="component", decided_at=_PRE_CUT)
        frame = build_dataset(conn, minimal_registry_snapshot(), era_cut=_ERA)

    hashes = set(frame["config_hash"].to_list())
    assert "ve_ghost_hash" not in hashes
    assert "ve_clean_hash" in hashes
    assert "tc_hash" in hashes


def test_mature_arms_ignore_ghost_ve_verdicts() -> None:
    """Ghost ve verdicts must not mature an arm: 30 pre-cut ve verdicts leave the
    arm YOUNG; 30 post-cut ve verdicts mature it."""
    from forge.ranking.arm_floor import YOUNG_ARM_VERDICT_THRESHOLD

    n = YOUNG_ARM_VERDICT_THRESHOLD + 5
    with db_connection() as conn:
        _seed_submission(conn, hypothesis="volatility_event", config_hash="ve_ghost_hash")
        for _ in range(n):
            _seed_verdict(conn, config_hash="ve_ghost_hash", decision="reject", decided_at=_PRE_CUT)
        mature_pre = compute_mature_arms(conn, era_cut=_ERA)

    with db_connection() as conn:
        _seed_submission(conn, hypothesis="volatility_event", config_hash="ve_clean_hash")
        for _ in range(n):
            _seed_verdict(
                conn, config_hash="ve_clean_hash", decision="reject", decided_at=_POST_CUT
            )
        mature_post = compute_mature_arms(conn, era_cut=_ERA)

    assert not mature_pre  # ghost rows matured nothing
    assert mature_post  # honest rows mature normally


@pytest.mark.parametrize("hypothesis", ["mean_reversion", "trend_continuation"])
def test_non_ve_rows_never_cut(hypothesis: str) -> None:
    with db_connection() as conn:
        _seed_submission(conn, hypothesis=hypothesis, config_hash="h1")
        _seed_verdict(conn, config_hash="h1", decision="component", decided_at=_PRE_CUT)
        frame = build_dataset(conn, minimal_registry_snapshot(), era_cut=_ERA)
    assert "h1" in set(frame["config_hash"].to_list())
