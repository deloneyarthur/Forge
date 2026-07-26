"""Tests for forge.ranking.dataset (D132 / F1) — honest-era training frame.

``build_dataset`` joins ``verdicts ⋈ submissions`` on config_hash, hard-cuts
rows at the clean-era boundary, labels with the D128 honesty predicate, and
keeps every refit row (same config_hash, new crucible_run_id — independent
gate evaluations per D124). Design: `docs/proposals/learned-ranker.md` §4 F1.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import duckdb

from forge.persistence.db import db_connection
from forge.persistence.verdicts import record_verdicts
from forge.ranking.dataset import build_dataset
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()

# Naive-UTC datetimes throughout: the verdicts/export era is uniformly UTC
# post-D117 and DuckDB TIMESTAMP columns are naive by convention.
_POST_CUT = datetime(2026, 6, 10, 18, 0, 0)  # noqa: DTZ001
_PRE_CUT = datetime(2026, 6, 10, 12, 0, 0)  # noqa: DTZ001


def _insert_submission(db: duckdb.DuckDBPyConnection, *, config_hash: str) -> None:
    db.execute(
        "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
        "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config_hash,
            minimal_strategy_config().model_dump_json(),
            datetime(2026, 6, 10, 11, 0),  # noqa: DTZ001
            "gated",
        ],
    )


def _gated_run(
    *,
    config_hash: str,
    decision: str = "reject",
    decided_at: datetime = _POST_CUT,
    honest_coverage: bool = True,
    coverage_row: bool = True,
    run_id: str | None = None,
    cpcv: float | None = 0.8,
    wf: float | None = 1.2,
    regime_stress: float | None = 0.5,
    sharpe_baseline: float | None = 0.9,
):
    from datetime import date

    from crucible_contracts import GatedRun
    from crucible_contracts.models import GateResult, PromotionDecision, RunResult

    rid = run_id or str(uuid.uuid4())
    gate_results = {
        "min_oos_trade_count": GateResult(
            gate_name="min_oos_trade_count",
            passed=True,
            value=120.0,
            threshold=100.0,
        ),
    }
    for _name, _val, _thr in (
        ("cpcv_sharpe_p25", cpcv, 1.5),
        ("walk_forward_sharpe_median", wf, 2.0),
        ("regime_stress_p25_return", regime_stress, 0.0),
        ("sharpe_baseline", sharpe_baseline, 1.0),
    ):
        if _val is not None:
            gate_results[_name] = GateResult(
                gate_name=_name, passed=_val >= _thr, value=_val, threshold=_thr
            )
    if coverage_row:
        gate_results["regime_coverage"] = GateResult(
            gate_name="regime_coverage",
            passed=True,
            value=None,
            threshold=None,
            detail="" if honest_coverage else "coverage_unverified: legacy admission",
        )
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
            gate_results=gate_results,
            decided_at=decided_at,
            decided_by="runner.forge_minimal",
        ),
    )


def test_joins_labels_and_orders_rows() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        _insert_submission(conn, config_hash="bbbb000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="bbbb000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 18, 30),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 2
    # Ordered by (decided_at, crucible_run_id): the reject decided first.
    assert frame["config_hash"].to_list() == ["bbbb000011112222", "aaaa000011112222"]
    assert frame["label"].to_list() == [0, 1]
    # Feature columns rode along.
    assert frame["hypothesis=mean_reversion"].to_list() == [1.0, 1.0]


def test_stored_config_with_since_removed_field_does_not_kill_the_build() -> None:
    """REGRESSION (2026-07-25): the trainer died for ~2 days on `extra_forbidden`.

    D334 all over again, one module across: contracts 1.36.0 stamped a
    `prefilter_sample` bool onto StrategyConfig, 1.37.0 REMOVED it, and our stored
    `config_json` from that era still carries it. A strict `model_validate_json` here
    raised on the first such row and took the whole dataset build with it — so
    `forge ranker-model train` and BOTH `train-robustness` targets failed every night at
    05:00, logged benignly as "non-zero ... continuing". The live cpcv model froze at its
    2026-07-23 fit, which is also the model carrying the rank_k collider (Q59): it was
    biased AND could not be retrained.

    Re-reading our OWN history must be forward-compatible; strict validation still guards
    first ingest at submit time. This is a RE-read.
    """
    stale = json.loads(minimal_strategy_config().model_dump_json())
    stale["prefilter_sample"] = None  # the 1.36.0 field that 1.37.0 removed
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "stale000011112222",
                json.dumps(stale),
                datetime(2026, 6, 10, 11, 0),  # noqa: DTZ001
                "gated",
            ],
        )
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="stale000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
                )
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 1, "a since-removed field must not drop the row or raise"


def test_era_cut_excludes_pre_boundary_rows() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=_PRE_CUT,
                ),
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=_POST_CUT,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 1
    assert frame["label"].to_list() == [0]


def test_refit_children_kept_as_independent_rows() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    decided_at=datetime(2026, 6, 10, 21, 0),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 2
    assert frame["label"].to_list() == [0, 1]


def test_dishonest_component_labels_zero() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    honest_coverage=False,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["label"].to_list() == [0]


def test_component_without_coverage_row_labels_zero() -> None:
    # Absent regime_coverage row = cannot verify = fail-closed (D124 key 2).
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    coverage_row=False,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["label"].to_list() == [0]


def test_verdict_without_submission_is_skipped() -> None:
    with db_connection() as conn:
        record_verdicts(
            conn,
            [_gated_run(config_hash="cccc000011112222", decision="component")],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame.height == 0


def test_emits_continuous_targets_from_gate_values() -> None:
    # T1: the worst-quartile regression targets ride along, read from
    # gate_results[...].value (Forge consumes Crucible's computed metrics, §1.2).
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    cpcv=0.74,
                    wf=1.30,
                    regime_stress=0.82,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["target_cpcv_p25"].to_list() == [0.74]
    assert frame["target_wf_median"].to_list() == [1.30]
    assert frame["target_regime_stress"].to_list() == [0.82]


def test_emits_sharpe_baseline_target() -> None:
    """Crucible's 2026-07-26 ASK-3 lead, validated in our nested design (prereg
    `8cfe95f4a6e9`): ordering by `P(sharpe_baseline >= top-N)` delivers 307 strong
    components per 4,520 selected against the incumbent's 131. It has to reach the
    training frame before any of that can be fitted."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="reject",
                    sharpe_baseline=1.37,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["target_sharpe_baseline"].to_list() == [1.37]


def test_missing_target_gate_is_null() -> None:
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        record_verdicts(
            conn,
            [_gated_run(config_hash="aaaa000011112222", decision="reject", cpcv=None)],
        )
        frame = build_dataset(conn, _REGISTRY)

    assert frame["target_cpcv_p25"].to_list() == [None]


def test_coverage_verified_flag_tracks_honesty_predicate() -> None:
    # §8.2: a coverage-verified flag (=the D128 honesty predicate) rides along so
    # the regression head can discount the noisier coverage_unverified cpcv values.
    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        _insert_submission(conn, config_hash="bbbb000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
                    honest_coverage=True,
                ),
                _gated_run(
                    config_hash="bbbb000011112222",
                    decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
                    honest_coverage=False,
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    # Ordered by decided_at: verified (18:00) then unverified (19:00).
    assert frame["coverage_verified"].to_list() == [1.0, 0.0]


def test_logistic_model_does_not_ingest_targets_or_coverage_flag() -> None:
    # Safety invariant: the new regression targets are labels and coverage_verified
    # is collinear with the honesty label — none may leak into the existing
    # P(component) logistic model's feature set. Keeps F2 byte-identical.
    from forge.ranking.model import train_verdict_model

    with db_connection() as conn:
        _insert_submission(conn, config_hash="aaaa000011112222")
        _insert_submission(conn, config_hash="bbbb000011112222")
        record_verdicts(
            conn,
            [
                _gated_run(
                    config_hash="aaaa000011112222",
                    decision="component",
                    honest_coverage=True,
                    decided_at=datetime(2026, 6, 10, 18, 0),  # noqa: DTZ001
                ),
                _gated_run(
                    config_hash="bbbb000011112222",
                    decision="reject",
                    honest_coverage=False,
                    decided_at=datetime(2026, 6, 10, 19, 0),  # noqa: DTZ001
                ),
            ],
        )
        frame = build_dataset(conn, _REGISTRY)

    model = train_verdict_model(frame, era_cut=_POST_CUT)
    assert not any(name.startswith("target_") for name in model.feature_names)
    assert "coverage_verified" not in model.feature_names


# ---------------------------------------------------------------------------
# D331 Part B — honest-scope population filter (A/B flag, default OFF)
# ---------------------------------------------------------------------------


def _two_configs_one_honest(conn: object) -> None:
    """A stage-one-shaped row (dishonest coverage) and a stage-two-shaped one."""
    _insert_submission(conn, config_hash="aaaa000011112222")
    _insert_submission(conn, config_hash="bbbb000011112222")
    record_verdicts(
        conn,
        [
            # Structurally unable to carry a positive: the screen lane.
            _gated_run(config_hash="aaaa000011112222", decision="component", honest_coverage=False),
            # Honestly evaluated: the validator lane.
            _gated_run(config_hash="bbbb000011112222", decision="component", honest_coverage=True),
        ],
    )


def test_honest_scope_off_is_byte_identical() -> None:
    """Ritual requirement 1 (hard rule #6): flag OFF must change nothing."""
    with db_connection() as conn:
        _two_configs_one_honest(conn)
        default = build_dataset(conn, _REGISTRY)
        explicit_off = build_dataset(conn, _REGISTRY, honest_scope=False)
    assert default.equals(explicit_off)
    assert sorted(default["label"].to_list()) == [0, 1]
    assert default.height == 2


def test_honest_scope_on_drops_rows_that_cannot_carry_a_positive() -> None:
    """The defect: a screen-lane row is labelled NEGATIVE regardless of quality,
    because its lane structurally cannot produce an honest coverage row. 91.0% of
    the live frame is in that state, and the same config_hash can appear in both
    lanes with OPPOSITE labels. Scoping removes the mislabelled mass rather than
    trying to learn from it."""
    with db_connection() as conn:
        _two_configs_one_honest(conn)
        scoped = build_dataset(conn, _REGISTRY, honest_scope=True)
    assert scoped.height == 1
    assert scoped["label"].to_list() == [1]
    assert scoped["config_hash"].to_list() == ["bbbb000011112222"]


def test_honest_scope_keeps_honest_rejects_as_negatives() -> None:
    """Scoping is a POPULATION filter, not a positives-only filter: a config that
    WAS honestly evaluated and rejected is real negative evidence and must stay."""
    with db_connection() as conn:
        _insert_submission(conn, config_hash="cccc000011112222")
        record_verdicts(
            conn,
            [_gated_run(config_hash="cccc000011112222", decision="reject", honest_coverage=True)],
        )
        scoped = build_dataset(conn, _REGISTRY, honest_scope=True)
    assert scoped.height == 1
    assert scoped["label"].to_list() == [0]
