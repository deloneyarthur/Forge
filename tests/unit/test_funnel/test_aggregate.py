"""Tests for ``forge.funnel.aggregate`` (D096 Part B — pure aggregation).

`build_funnel_export` rolls `batch_summaries` up per grammar version into the
two upstream funnel stages; `build_version_map` produces the
config_hash -> grammar_version join-map that is Forge's interim source for
Crucible's funnel Stage 0. Both are pure DB reads (no clock, no filesystem).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from forge.funnel.aggregate import build_funnel_export, build_version_map
from forge.persistence.db import db_connection


def _insert_batch(
    conn: object,
    *,
    grammar_version: str,
    batch_size: int,
    enumerated: int | None,
    survived: int | None,
    rejections: Mapping[str, int] | None,
    by_hyp: Mapping[str, int] | None = None,
    seed: int = 0,
) -> uuid.UUID:
    bid = uuid.uuid4()
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO batch_summaries
            (forge_batch_id, batch_size, submitted_at, grammar_version,
             registry_version, prefilter_rejections, enumerated_count,
             survived_count, enumerated_by_hypothesis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            str(bid),
            batch_size,
            datetime(2026, 5, 29, 12, tzinfo=UTC),
            grammar_version,
            "reg",
            json.dumps(dict(rejections)) if rejections is not None else None,
            enumerated,
            survived,
            json.dumps(dict(by_hyp)) if by_hyp is not None else None,
        ],
    )
    return bid


def _insert_submission(conn: object, *, batch_id: uuid.UUID, config_hash: str) -> None:
    conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO submissions
            (forge_candidate_id, forge_batch_id, config_hash, config_json,
             submitted_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            str(uuid.uuid4()),
            str(batch_id),
            config_hash,
            "{}",
            datetime(2026, 5, 29, 12, tzinfo=UTC),
            "submitted",
        ],
    )


# ---------------------------------------------------------------------------
# build_funnel_export
# ---------------------------------------------------------------------------


def test_aggregates_counts_per_grammar_version(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=200,
            enumerated=1000,
            survived=50,
            rejections={"expected_trades": 950},
            by_hyp={"regime_arbitrage": 800, "mean_reversion": 200},
            seed=1,
        )
        _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=100,
            enumerated=500,
            survived=30,
            rejections={"expected_trades": 400, "novelty": 70},
            by_hyp={"regime_arbitrage": 500},
            seed=2,
        )
        _insert_batch(
            conn,
            grammar_version="v3",
            batch_size=10,
            enumerated=80,
            survived=8,
            rejections={"permutation_test": 72},
            seed=3,
        )
        export = build_funnel_export(conn)

    assert set(export.per_grammar_version) == {"v4", "v3"}
    v4 = export.per_grammar_version["v4"]
    assert v4.batches == 2
    assert v4.enumerated == 1500
    assert v4.survived_prefilters == 80
    assert v4.submitted == 300
    assert v4.rejection_breakdown == {"expected_trades": 1350, "novelty": 70}
    assert v4.enumerated_by_hypothesis == {"regime_arbitrage": 1300, "mean_reversion": 200}

    v3 = export.per_grammar_version["v3"]
    assert v3.enumerated == 80
    assert v3.rejection_breakdown == {"permutation_test": 72}


def test_aggregate_invariant_sum_rejections_eq_enum_minus_survived(tmp_path: Path) -> None:
    """The exported product re-satisfies the funnel invariant per version."""
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=200,
            enumerated=1000,
            survived=50,
            rejections={"expected_trades": 900, "novelty": 50},
            seed=1,
        )
        _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=100,
            enumerated=500,
            survived=30,
            rejections={"expected_trades": 470},
            seed=2,
        )
        export = build_funnel_export(conn)
    for funnel in export.per_grammar_version.values():
        assert sum(funnel.rejection_breakdown.values()) == (
            funnel.enumerated - funnel.survived_prefilters
        )


def test_skips_pre_instrumentation_batches_without_counts(tmp_path: Path) -> None:
    """Batches predating D096 have NULL enumerated/survived. Including their
    rejection_breakdown without the matching counts would break the invariant,
    so they are excluded — and the exclusion is reported, not silent."""
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=200,
            enumerated=1000,
            survived=50,
            rejections={"expected_trades": 950},
            seed=1,
        )
        # Pre-instrumentation: counts NULL but rejections present.
        _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=200,
            enumerated=None,
            survived=None,
            rejections={"expected_trades": 999},
            seed=2,
        )
        export = build_funnel_export(conn)

    v4 = export.per_grammar_version["v4"]
    assert v4.enumerated == 1000  # only the instrumented batch
    assert v4.batches == 1
    assert sum(v4.rejection_breakdown.values()) == v4.enumerated - v4.survived_prefilters
    # Coverage honesty: the dropped batch is counted, not hidden.
    assert export.coverage["batches_total"] == 2
    assert export.coverage["batches_with_funnel_counts"] == 1


def test_empty_db_returns_empty_export(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        export = build_funnel_export(conn)
    assert export.per_grammar_version == {}
    assert export.coverage == {"batches_total": 0, "batches_with_funnel_counts": 0}
    assert export.schema_version == "1.0"


# ---------------------------------------------------------------------------
# build_version_map (Part A interim join-map)
# ---------------------------------------------------------------------------


def test_version_map_maps_each_config_hash_to_its_grammar_version(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        b_v4 = _insert_batch(
            conn,
            grammar_version="v4",
            batch_size=2,
            enumerated=10,
            survived=2,
            rejections={"novelty": 8},
            seed=1,
        )
        b_v3 = _insert_batch(
            conn,
            grammar_version="v3",
            batch_size=1,
            enumerated=5,
            survived=1,
            rejections={"novelty": 4},
            seed=2,
        )
        _insert_submission(conn, batch_id=b_v4, config_hash="aaa1")
        _insert_submission(conn, batch_id=b_v4, config_hash="aaa2")
        _insert_submission(conn, batch_id=b_v3, config_hash="bbb1")
        version_map = build_version_map(conn)

    assert version_map == {"aaa1": "v4", "aaa2": "v4", "bbb1": "v3"}


def test_version_map_empty_when_no_submissions(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        version_map = build_version_map(conn)
    assert version_map == {}
