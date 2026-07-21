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

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from crucible_contracts import GatedRun, StrategyConfig
from crucible_contracts.models import GateResult, PromotionDecision, RunResult

from forge.feedback.rejection_weights import (
    CLEAN_ERA_LABEL_CUT,
    _honest_regime_coverage,
    honest_regime_coverage_row,
)
from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.dataset import build_dataset
from forge.ranking.features import extract_features
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
    rid = str(uuid.uuid4())
    return GatedRun(
        run=RunResult(
            run_id=rid,
            config_hash=config_hash,
            metrics={"total_return": 0.1},
            trade_count=120,
            period_start=date(2021, 6, 2),
            period_end=date(2026, 6, 1),
            grammar_version="v17",
        ),
        decision=PromotionDecision(
            run_id=rid,
            decision=decision,  # type: ignore[arg-type]
            gate_results=gate_results or {},
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )


def _insert_submission(db: duckdb.DuckDBPyConnection, *, config_hash: str) -> None:
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            minimal_strategy_config().model_dump_json(),
            datetime(2026, 6, 10, 11, 0),  # noqa: DTZ001 — naive-UTC column convention
            "gated",
        ],
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
  auto_tune:
    adjustment_pct_per_step: 0.10
"""


def test_shadow_scoring_never_changes_the_submitted_set(tmp_path: Path) -> None:
    """Same seed, model artifact present vs absent → identical submitted
    config_hash sets; the only difference is shadow_scores telemetry.

    The hermetic sandbox runs on the synthetic feature cache, which the
    production battery rightly rejects wholesale — so the battery is
    loosened to the floor here to get real submissions through the full
    rank → submit → shadow path.
    """
    import polars as pl
    from typer.testing import CliRunner

    from forge.cli.main import app
    from forge.ranking.model import save_model, train_verdict_model
    from tests.fixtures.synthetic_crucible_db import build_synthetic_crucible_db

    runner = CliRunner()
    hashes: dict[str, list[str]] = {}
    shadow_counts: dict[str, int] = {}
    for label in ("absent", "present"):
        root = tmp_path / label
        root.mkdir()
        forge_db = root / "forge.db"
        build_synthetic_crucible_db(root / "crucible.db").close()
        prefilter_yaml = root / "prefilter.yaml"
        prefilter_yaml.write_text(_LOOSE_PREFILTER_YAML, encoding="utf-8")
        if label == "present":
            records = []
            for i in range(30):
                records.append(
                    {
                        "crucible_run_id": f"run-{i:04d}",
                        "config_hash": f"hash{i:012d}",
                        "decided_at": datetime(2026, 6, 10, 18, 0, i),  # noqa: DTZ001
                        "decision": "component" if i % 5 == 0 else "reject",
                        "label": int(i % 5 == 0),
                        "hypothesis=mean_reversion": 1.0,
                        "f_noise": float(i % 3),
                    }
                )
            save_model(
                train_verdict_model(pl.DataFrame(records), era_cut=CLEAN_ERA_LABEL_CUT),
                root / "models",
            )
        result = runner.invoke(
            app,
            [
                "run",
                "--no-config",
                "--seed",
                "7",
                "--batch-size",
                "2",
                "--max",
                "200",
                "--forge-db",
                str(forge_db),
                "--inbox",
                str(root / "inbox"),
                "--crucible-db",
                str(root / "crucible.db"),
                "--prefilter-yaml",
                str(prefilter_yaml),
            ],
        )
        assert result.exit_code == 0, result.output
        with db_connection(forge_db) as conn:
            hashes[label] = sorted(
                h for (h,) in conn.execute("SELECT config_hash FROM submissions").fetchall()
            )
            row = conn.execute("SELECT count(*) FROM shadow_scores").fetchone()
            assert row is not None
            shadow_counts[label] = row[0]

    assert hashes["absent"] == hashes["present"]
    assert len(hashes["present"]) > 0
    assert shadow_counts["absent"] == 0
    assert shadow_counts["present"] == len(hashes["present"])
