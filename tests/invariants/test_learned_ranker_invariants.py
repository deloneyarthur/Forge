"""Learned-ranker invariants (D132 / F1) — era cut, honesty reuse, skew-proof.

The design (`docs/proposals/learned-ranker.md` §5) pins three F1 failure modes
before production code:

1. Training rows are hard-cut at the composite clean-era boundary
   2026-06-10T17:17:13Z (earnings-exit live + chain-fixed registry + v17,
   D130/D131) — a model must never learn labels from the polluted engine.
2. The label reuses the D128 honesty predicate from the feedback module —
   one source of truth, drift impossible.
3. Feature extraction is one codepath: a config rehydrated from
   ``submissions.config_json`` extracts byte-identically to the in-memory
   object (train/serve skew-proof).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
from crucible_contracts import GatedRun, StrategyConfig
from crucible_contracts.models import GateResult

from forge.feedback.eras import (
    CLEAN_ERA_LABEL_CUT,
    _honest_regime_coverage,
    honest_regime_coverage_row,
)
from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.dataset import build_dataset
from forge.ranking.features import extract_features
from tests.fixtures.forge_db_rows import insert_submission, make_gated_run
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()


def _gated_run(
    *,
    config_hash: str,
    decision: str,
    decided_at: datetime,
    gate_results: dict[str, GateResult] | None = None,
) -> GatedRun:
    return make_gated_run(
        config_hash=config_hash,
        decision=decision,
        decided_at=decided_at,
        gate_results=gate_results,
        grammar_version="v17",
    )


def _insert_submission(db: duckdb.DuckDBPyConnection, *, config_hash: str) -> None:
    insert_submission(
        db,
        config_hash=config_hash,
        config_json=minimal_strategy_config().model_dump_json(),
        status="gated",
    )


def _coverage(passed: bool, detail: str) -> dict[str, GateResult]:
    return {
        "regime_coverage": GateResult(
            gate_name="regime_coverage",
            passed=passed,
            value=None,
            threshold=None,
            detail=detail,
        ),
    }


# ---------------------------------------------------------------------------
# 1 — era cut
# ---------------------------------------------------------------------------


def test_clean_era_label_cut_is_the_composite_boundary() -> None:
    """The constant is the exit-era runner restart, byte-exact (D130/D131)."""
    assert datetime(2026, 6, 10, 17, 17, 13, tzinfo=UTC) == CLEAN_ERA_LABEL_CUT


def test_era_cut_is_inclusive_at_the_boundary_second() -> None:
    """17:17:12 is the polluted engine; 17:17:13 is the clean one."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 17, 17, 12),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 17, 17, 13),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 1
    assert frame["decided_at"].to_list()[0] == datetime(2026, 6, 10, 17, 17, 13)  # noqa: DTZ001


# ---------------------------------------------------------------------------
# 2 — honesty predicate is single-sourced
# ---------------------------------------------------------------------------


def test_honesty_row_helper_and_feedback_predicate_cannot_drift() -> None:
    """The row helper IS the predicate `_honest_regime_coverage` delegates to."""
    cases = [
        _coverage(passed=True, detail=""),
        _coverage(passed=True, detail="coverage_unverified: legacy admission"),
        _coverage(passed=False, detail=""),
        {},  # absent row — fail-closed
    ]
    for gate_results in cases:
        run = _gated_run(
            config_hash="aaaa000011112222",
            decision="component",
            decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
            gate_results=dict(gate_results),
        )
        assert _honest_regime_coverage(run) == honest_regime_coverage_row(run.decision.gate_results)


def test_dishonest_component_never_labels_positive() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
                    gate_results=_coverage(
                        passed=True, detail="coverage_unverified: legacy admission"
                    ),
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["label"].to_list() == [0]


# ---------------------------------------------------------------------------
# 3 — train/serve skew-proof
# ---------------------------------------------------------------------------


def test_feature_extraction_roundtrips_through_config_json() -> None:
    config = minimal_strategy_config()
    rehydrated = StrategyConfig.model_validate_json(config.model_dump_json())
    assert extract_features(config, _REGISTRY) == extract_features(rehydrated, _REGISTRY)


# ---------------------------------------------------------------------------
# 4 — training determinism (F2): same DB snapshot → byte-identical artifact
# ---------------------------------------------------------------------------


def test_training_is_deterministic_byte_identical(tmp_path: Path) -> None:
    """No RNG exists in the train path: two trains on the same frame must
    produce byte-identical artifacts (hard-rule #5 posture, D132 decision 2)."""
    import polars as pl

    from forge.ranking.model import save_model, train_verdict_model

    records = []
    for i in range(30):
        records.append(
            {
                "crucible_run_id": f"run-{i:04d}",
                "config_hash": f"hash{i:012d}",
                "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                "decision": "component" if i % 5 == 0 else "reject",
                "label": int(i % 5 == 0),
                "f_signal": float(i % 5 == 0),
                "f_noise": float(i % 3),
            }
        )
    frame = pl.DataFrame(records)
    path_a = save_model(train_verdict_model(frame, era_cut=CLEAN_ERA_LABEL_CUT), tmp_path / "a")
    path_b = save_model(train_verdict_model(frame, era_cut=CLEAN_ERA_LABEL_CUT), tmp_path / "b")
    assert path_a.name == path_b.name
    assert path_a.read_bytes() == path_b.read_bytes()


# ---------------------------------------------------------------------------
# 5 — shadow no-op (F2): a model artifact must not change what gets submitted
# ---------------------------------------------------------------------------


_LOOSE_PREFILTER_YAML = """\
prefilter:
  signal_density:
    min_activations: 1
  expected_trade_count:
    min_trades: 1
    min_pass_probability: 0.0
    min_bucket_samples: 1000000
  predicted_activations:
    min_entries: 1
  novelty:
    max_jaccard_overlap: 1.0
  signal_correlation:
    max_jaccard_overlap: 1.0
  regime_exposure:
    max_single_regime_concentration: 1.0
  permutation_test:
    n_permutations: 10
    p_value_threshold: 1.0
    forward_horizon_days: 5
"""
