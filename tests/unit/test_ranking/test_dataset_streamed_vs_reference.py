"""`build_dataset` featurises per CONFIG and streams both passes (Batch 6B, D426). This module
pins the streamed frame against a verbatim copy of the implementation it replaced (the
per-verdict-row `fetchall()` build) with `polars.testing.assert_frame_equal`, which checks rows,
row order, column order, dtypes and nulls together. The fixture carries the shapes where the
two builds could plausibly diverge: refit rows on one hash, out-of-order decided_at, a
ghost-era ve verdict beside a live one on the same config, a config whose ONLY verdict is
ghost-era (its one-hots must not become columns), a config whose only verdicts are dishonest
(same, under honest_scope), and a target gate with no value. The reference lives here and not
in src so the production module carries one implementation.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import duckdb
import polars as pl
import pytest
from crucible_contracts import GatedRun, StrategyConfig, parse_forward_compatible
from crucible_contracts.models import GateResult, PromotionDecision, RunResult
from polars.testing import assert_frame_equal

from forge.feedback.eras import (
    CLEAN_ERA_LABEL_CUT,
    VE_GHOST_LABEL_CUT,
    honest_regime_coverage_row,
    is_ve_ghost_label,
)
from forge.persistence.db import open_db
from forge.persistence.verdicts import record_verdicts
from forge.ranking.dataset import (
    _IDENTITY_SCHEMA,
    _TARGET_GATE,
    COVERAGE_FEATURE,
    TARGET_COLUMNS,
    _gate_value,
    build_dataset,
    label_for,
    parse_gate_results,
)
from forge.ranking.features import extract_features
from tests.fixtures.strategy_configs import minimal_registry_snapshot, minimal_strategy_config

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot

_REGISTRY = minimal_registry_snapshot()
_POST = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# the reference: the per-row implementation replaced in D426, verbatim
# ---------------------------------------------------------------------------


def reference_build_dataset(
    conn: duckdb.DuckDBPyConnection,
    registry: RegistrySnapshot,
    *,
    era_cut: datetime = CLEAN_ERA_LABEL_CUT,
    honest_scope: bool = False,
) -> pl.DataFrame:
    cut = era_cut
    if cut.tzinfo is not None:
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT v.crucible_run_id, v.config_hash, v.decision, v.decided_at,
               v.gate_results, s.config_json
        FROM verdicts v
        JOIN submissions s ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ?
        ORDER BY v.decided_at, v.crucible_run_id
        """,
        [cut],
    ).fetchall()
    records: list[dict[str, object]] = []
    feature_names: set[str] = set()
    for run_id, config_hash, decision, decided_at, gate_results_json, config_json in rows:
        config = parse_forward_compatible(StrategyConfig, json.loads(config_json))
        if is_ve_ghost_label(config.hypothesis, decided_at):
            continue
        gate_results = parse_gate_results(gate_results_json)
        if honest_scope and not honest_regime_coverage_row(gate_results):
            continue
        features = extract_features(config, registry).as_dict()
        feature_names.update(features)
        records.append(
            {
                "crucible_run_id": str(run_id),
                "config_hash": config_hash,
                "decided_at": decided_at,
                "decision": decision,
                "label": label_for(decision, gate_results),
                COVERAGE_FEATURE: float(honest_regime_coverage_row(gate_results)),
                **{col: _gate_value(gate_results, gate) for col, gate in _TARGET_GATE},
                **features,
            }
        )
    leading = [*_IDENTITY_SCHEMA, *TARGET_COLUMNS, COVERAGE_FEATURE]
    target_floats: dict[str, pl.DataType | type[pl.DataType]] = {
        c: pl.Float64 for c in (*TARGET_COLUMNS, COVERAGE_FEATURE)
    }
    if not records:
        return pl.DataFrame(schema={**_IDENTITY_SCHEMA, **target_floats})
    ordered_features = sorted(feature_names)
    for record in records:
        for name in ordered_features:
            record.setdefault(name, 0.0)
    return pl.DataFrame(records, schema_overrides=target_floats).select(
        [*leading, *ordered_features]
    )


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


def _submit(conn: duckdb.DuckDBPyConnection, config: StrategyConfig) -> str:
    conn.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, 'gated')",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config.config_hash,
            config.model_dump_json(),
            (_POST - timedelta(days=40)).replace(tzinfo=None),
        ],
    )
    return config.config_hash


def _run(
    config_hash: str,
    *,
    decision: str = "reject",
    decided_at: datetime = _POST,
    honest: bool = True,
    cpcv: float | None = 0.8,
    wf: float | None = 1.2,
) -> GatedRun:
    rid = str(uuid.uuid4())
    gates: dict[str, GateResult] = {
        "min_oos_trade_count": GateResult(
            gate_name="min_oos_trade_count", passed=True, value=120.0, threshold=100.0
        ),
        "regime_coverage": GateResult(
            gate_name="regime_coverage",
            passed=True,
            value=None,
            threshold=None,
            detail="" if honest else "coverage_unverified: legacy admission",
        ),
    }
    for name, val, thr in (
        ("cpcv_sharpe_p25", cpcv, 1.5),
        ("walk_forward_sharpe_median", wf, 2.0),
    ):
        if val is not None:
            gates[name] = GateResult(gate_name=name, passed=val >= thr, value=val, threshold=thr)
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=datetime(2021, 6, 2, tzinfo=UTC).date(),
            period_end=datetime(2026, 6, 1, tzinfo=UTC).date(),
            grammar_version="v55",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results=gates,
            decided_at=decided_at.replace(tzinfo=None),
            decided_by="runner.fixture",
        ),
    )


@pytest.fixture
def frame_db() -> duckdb.DuckDBPyConnection:
    conn = open_db(":memory:")
    a = _submit(conn, minimal_strategy_config())
    b = _submit(conn, minimal_strategy_config(dte_bucket="swing_mid"))
    c = _submit(conn, minimal_strategy_config(hypothesis="trend_continuation"))
    ve_live = _submit(conn, minimal_strategy_config(hypothesis="volatility_event"))
    # The only swing_long config: its `dte_bucket=swing_long` one-hot exists nowhere else, so
    # if its single ghost-era verdict leaked a column the differential would catch it.
    ve_ghost_only = _submit(
        conn, minimal_strategy_config(hypothesis="volatility_event", dte_bucket="swing_long")
    )
    # The only event_momentum config, evaluated dishonestly only: under honest_scope its
    # `hypothesis=event_momentum` one-hot must vanish with its rows.
    dishonest_only = _submit(conn, minimal_strategy_config(hypothesis="event_momentum"))
    runs = [
        # refit rows on one hash, out of decided_at order, so the canonical order is exercised
        _run(a, decision="component", decided_at=_POST + timedelta(hours=2), cpcv=1.9),
        _run(a, decision="reject", decided_at=_POST, cpcv=0.4),
        _run(b, decision="reject", decided_at=_POST + timedelta(hours=1), wf=None),
        _run(c, decision="promote", decided_at=_POST + timedelta(hours=3), cpcv=2.5, wf=2.4),
        # a dishonest positive (label 0) and a dishonest reject, on configs with honest rows too
        _run(b, decision="component", decided_at=_POST + timedelta(hours=4), honest=False),
        _run(c, decision="reject", decided_at=_POST + timedelta(hours=5), honest=False),
        _run(
            dishonest_only,
            decision="component",
            decided_at=_POST + timedelta(hours=6),
            honest=False,
        ),
        # ve: a ghost-era row (dropped) and a live row (kept) on one config
        _run(ve_live, decision="component", decided_at=VE_GHOST_LABEL_CUT - timedelta(hours=1)),
        _run(ve_live, decision="reject", decided_at=VE_GHOST_LABEL_CUT + timedelta(hours=1)),
        _run(
            ve_ghost_only, decision="component", decided_at=VE_GHOST_LABEL_CUT - timedelta(days=2)
        ),
        # pre-clean-era row: excluded by the cut
        _run(a, decision="component", decided_at=CLEAN_ERA_LABEL_CUT - timedelta(days=1)),
    ]
    record_verdicts(conn, runs, source_export="fixture")
    return conn


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("honest_scope", [False, True])
def test_streamed_frame_equals_the_reference(
    frame_db: duckdb.DuckDBPyConnection, honest_scope: bool
) -> None:
    new = build_dataset(frame_db, _REGISTRY, honest_scope=honest_scope)
    ref = reference_build_dataset(frame_db, _REGISTRY, honest_scope=honest_scope)
    assert_frame_equal(new, ref)


def test_streamed_frame_equals_the_reference_with_an_era_cut_override(
    frame_db: duckdb.DuckDBPyConnection,
) -> None:
    cut = _POST + timedelta(hours=2, minutes=30)
    assert_frame_equal(
        build_dataset(frame_db, _REGISTRY, era_cut=cut),
        reference_build_dataset(frame_db, _REGISTRY, era_cut=cut),
    )


def test_the_fixture_actually_exercises_the_corners(frame_db: duckdb.DuckDBPyConnection) -> None:
    """Guard the fixture: a differential over shapes that never diverge proves little."""
    frame = build_dataset(frame_db, _REGISTRY)
    assert frame.height == 8  # 11 verdicts, minus two ghost-era and one pre-era
    assert frame["decided_at"].is_sorted()
    assert "hypothesis=volatility_event" in frame.columns  # the live ve row survives
    assert "dte_bucket=swing_long" not in frame.columns  # the ghost-only config leaves no column
    assert frame["config_hash"].n_unique() == 5
    assert frame["target_wf_median"].null_count() == 1  # the wf=None row
    assert set(frame["label"].to_list()) == {0, 1}
    assert frame[COVERAGE_FEATURE].to_list().count(0.0) == 3  # the three dishonest rows

    scoped = build_dataset(frame_db, _REGISTRY, honest_scope=True)
    assert scoped.height == 5
    assert "hypothesis=event_momentum" in frame.columns
    assert "hypothesis=event_momentum" not in scoped.columns  # dropped with its only rows


def test_empty_ledger_gives_the_empty_schema_frame() -> None:
    conn = open_db(":memory:")
    new = build_dataset(conn, _REGISTRY)
    assert_frame_equal(new, reference_build_dataset(conn, _REGISTRY))
    assert new.height == 0
    assert list(new.columns) == [*_IDENTITY_SCHEMA, *TARGET_COLUMNS, COVERAGE_FEATURE]
