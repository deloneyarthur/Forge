"""Tests for ``forge.submission.search_multiplicity`` (D309).

Per-slot cumulative ``search_n_trials`` stamping, self-gated on Crucible's
record-not-bind deployment marker (their (a) resolution to the D306
interaction finding). Slot = hypothesis x dte_bucket x xsect-vs-named,
their Q1 measure, counted from OUR submissions table (deliberately
slightly ahead of their decided-count).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from crucible_contracts import CombinerSpec, StrategyConfig

from forge.persistence.db import open_db
from forge.prefilters.types import PreFilterReport
from forge.ranking.types import RankedCandidate
from forge.submission.search_multiplicity import (
    crucible_record_not_bind_live,
    slot_counts,
    slot_key,
    stamp_search_n_trials,
)
from tests.fixtures.strategy_configs import minimal_strategy_config

_XSECT_COMBINER = CombinerSpec(
    type="cross_sectional_rank",
    direction_strategy="k_of_n",
    k=1,
    rank_k=20,
    rebalance_frequency="monthly",
    direction_mode="long_only",
)


def _config(
    hypothesis: str = "mean_reversion",
    dte: str = "swing_short",
    *,
    xsect: bool = False,
    name: str = "c",
) -> StrategyConfig:
    overrides: dict[str, object] = {"name": name, "hypothesis": hypothesis, "dte_bucket": dte}
    if xsect:
        overrides["combiner"] = _XSECT_COMBINER
        overrides["underlying"] = None
    return minimal_strategy_config(**overrides)


def _insert_submission(conn: object, config: StrategyConfig) -> None:
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            config.config_hash,
            config.model_dump_json(),
            datetime(2026, 7, 20, 12, tzinfo=UTC).replace(tzinfo=None),
            "submitted",
            None,
            "ranked",
        ],
    )


def _insert_verdict(conn: object, *, detail: str, decided_at: datetime) -> None:
    gate_results = {
        "deflated_sharpe": {
            "gate_name": "deflated_sharpe",
            "passed": True,
            "value": 1.0,
            "threshold": 0.0,
            "detail": detail,
        },
    }
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO verdicts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            str(uuid.uuid4()),
            "abcdef0123456789",
            "reject",
            decided_at.replace(tzinfo=None),
            10,
            "v42",
            json.dumps(gate_results),
            decided_at.replace(tzinfo=None),
        ],
    )


def _candidate(config: StrategyConfig) -> RankedCandidate:
    return RankedCandidate(
        report=PreFilterReport(
            config=config,
            passed=True,
            filter_results={},
            diagnostic_notes=(),
            composite_score=0.5,
        ),
        prior_promotion_score=0.5,
        composite_score=0.5,
    )


class TestSlotKey:
    def test_named_config_slots_by_hypothesis_dte_named(self) -> None:
        assert slot_key(_config("mean_reversion", "swing_short")) == (
            "mean_reversion",
            "swing_short",
            "named",
        )

    def test_xsect_config_slots_as_xsect(self) -> None:
        assert slot_key(_config("trend_continuation", "swing_mid", xsect=True)) == (
            "trend_continuation",
            "swing_mid",
            "xsect",
        )


class TestSlotCounts:
    def test_counts_group_by_slot(self) -> None:
        conn = open_db(":memory:")
        _insert_submission(conn, _config(name="a"))
        _insert_submission(conn, _config(name="b"))
        _insert_submission(conn, _config("trend_continuation", "swing_long", name="c"))
        _insert_submission(conn, _config(xsect=True, name="d"))
        counts = slot_counts(conn)
        assert counts[("mean_reversion", "swing_short", "named")] == 2
        assert counts[("trend_continuation", "swing_long", "named")] == 1
        assert counts[("mean_reversion", "swing_short", "xsect")] == 1

    def test_empty_table_gives_empty_counts(self) -> None:
        conn = open_db(":memory:")
        assert slot_counts(conn) == {}


class TestMarkerPredicate:
    """The self-gate: stamping arms only once Crucible's record-not-bind
    code is OBSERVED live (the D306 hazard — stamping against their old
    binding predicate would flip the component stream to reject)."""

    def test_empty_verdicts_not_live(self) -> None:
        conn = open_db(":memory:")
        assert crucible_record_not_bind_live(conn) is False

    def test_old_detail_string_not_live(self) -> None:
        conn = open_db(":memory:")
        _insert_verdict(
            conn,
            detail="Single-config DSR (n_trials=1). Deflation lands in Step 4.",
            decided_at=datetime(2026, 7, 21, 1, tzinfo=UTC),
        )
        assert crucible_record_not_bind_live(conn) is False

    def test_marker_row_is_live(self) -> None:
        conn = open_db(":memory:")
        _insert_verdict(
            conn,
            detail="DSR at stamped multiplicity (recorded_not_binding).",
            decided_at=datetime(2026, 7, 21, 1, tzinfo=UTC),
        )
        assert crucible_record_not_bind_live(conn) is True

    def test_pre_ship_marker_rows_ignored(self) -> None:
        # Defensive: the marker only counts on rows decided at/after their
        # ship date — a stray older string can never arm the stamp.
        conn = open_db(":memory:")
        _insert_verdict(
            conn,
            detail="recorded_not_binding",
            decided_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        assert crucible_record_not_bind_live(conn) is False


class TestStamp:
    def test_stamps_position_aware_within_batch(self) -> None:
        base = {("mean_reversion", "swing_short", "named"): 100}
        cands = [
            _candidate(_config(name="a")),
            _candidate(_config(name="b")),
            _candidate(_config("trend_continuation", "swing_long", name="c")),
        ]
        stamped = stamp_search_n_trials(cands, base)
        values = [c.report.config.search_n_trials for c in stamped]
        # Same slot: 101 then 102; unseen slot starts at 1.
        assert values == [101, 102, 1]

    def test_input_counts_mapping_not_mutated(self) -> None:
        base = {("mean_reversion", "swing_short", "named"): 5}
        stamp_search_n_trials([_candidate(_config(name="a"))], base)
        assert base == {("mean_reversion", "swing_short", "named"): 5}

    def test_stamp_preserves_everything_else(self) -> None:
        cand = _candidate(_config(name="keepme"))
        (stamped,) = stamp_search_n_trials([cand], {})
        assert stamped.report.config.search_n_trials == 1
        assert stamped.report.config.name == "keepme"
        assert stamped.report.config.signals == cand.report.config.signals
        assert stamped.composite_score == cand.composite_score
        assert stamped.prior_promotion_score == cand.prior_promotion_score
        assert stamped.report.passed is True

    def test_unstamped_config_carries_none(self) -> None:
        # The dormant path submits configs untouched — their gate then takes
        # the n_trials=1 branch, today's behavior.
        assert _config().search_n_trials is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
