"""Phase 4 invariants — ranking + submission discipline checks.

Each invariant maps to a CLAUDE.md hard rule, a §13 production-quality
requirement, or a §6/§7 spec contract. Owned by the Phase 4 build;
new constraints add tests here.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import pytest

from forge.persistence.db import db_connection
from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.diversifier import select_top_n
from forge.ranking.queue import rank_batch
from forge.ranking.scorer import Ranker
from forge.ranking.types import RankedCandidate, RankerWeights
from forge.submission.batch import BatchContext, mint_batch_id
from forge.submission.submitter import submit_batch
from tests.fixtures.strategy_configs import minimal_strategy_config


def _default_weights() -> RankerWeights:
    return RankerWeights(
        signal_density=0.30,
        novelty=0.25,
        regime_diversity=0.20,
        permutation_test=0.15,
        prior_promotion_proximity=0.10,
    )


def _named_config(name: str, signal_ids: tuple[str, ...]) -> object:
    from crucible_contracts import SignalSpec

    signals = (
        SignalSpec(
            id=signal_ids[0],
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"threshold": 30.0},
        ),
        *tuple(
            SignalSpec(
                id=sid,
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50.0},
            )
            for sid in signal_ids[1:]
        ),
    )
    return minimal_strategy_config().model_copy(update={"name": name, "signals": signals})


def _passing_report(name: str, signal_ids: tuple[str, ...]) -> PreFilterReport:
    return PreFilterReport(
        config=_named_config(name, signal_ids),  # type: ignore[arg-type]
        passed=True,
        filter_results=MappingProxyType(
            {
                "structural_redundancy": FilterResult(passed=True, score=1.0),
                "resource_feasibility": FilterResult(passed=True, score=0.95),
                "signal_density": FilterResult(passed=True, score=0.80),
                "expected_trades": FilterResult(passed=True, score=0.70),
                "novelty": FilterResult(passed=True, score=0.90),
                "regime_exposure": FilterResult(passed=True, score=0.60),
                "permutation_test": FilterResult(passed=True, score=0.85),
            }
        ),
        diagnostic_notes=(),
    )


def _candidate(name: str, signals: tuple[str, ...], score: float) -> RankedCandidate:
    return RankedCandidate(
        report=_passing_report(name, signals),
        prior_promotion_score=0.0,
        composite_score=score,
    )


def _batch(seed: int) -> BatchContext:
    return BatchContext(
        batch_id=mint_batch_id(seed=seed, grammar_version="v1", registry_hash="abc"),
        grammar_version="v1",
        registry_hash="abc",
        submitted_at=datetime(2026, 5, 13, 12, tzinfo=UTC),
        seed=seed,
    )


# ---------------------------------------------------------------------------
# §13.4 / CLAUDE.md hard rule #9 — submission idempotency
# ---------------------------------------------------------------------------


def test_resubmitting_same_batch_is_a_no_op(tmp_path: Path) -> None:
    """Per §13.4, `submissions.config_hash` is unique-indexed. Re-running
    the exact same batch twice must produce zero new submissions and zero
    new inbox files (the contracts atomic-rename overwrites with the same
    bytes)."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    batch = _batch(seed=1)
    cands = (
        _candidate("a", ("X", "Y"), 0.9),
        _candidate("b", ("P", "Q"), 0.7),
    )
    with db_connection(forge_db) as conn:
        first = submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
        second = submit_batch(conn, batch=batch, candidates=cands, inbox_root=inbox)
    assert first.submitted_count == 2
    assert second.submitted_count == 0
    assert second.skipped_duplicate_count == 2


# ---------------------------------------------------------------------------
# §13.1 — batch_id determinism for the same triple
# ---------------------------------------------------------------------------


def test_batch_id_is_deterministic_for_same_triple() -> None:
    a = mint_batch_id(seed=42, grammar_version="v1", registry_hash="abcd1234")
    b = mint_batch_id(seed=42, grammar_version="v1", registry_hash="abcd1234")
    assert a == b


def test_batch_id_changes_when_any_triple_field_changes() -> None:
    base = mint_batch_id(seed=1, grammar_version="v1", registry_hash="abc")
    seed_diff = mint_batch_id(seed=2, grammar_version="v1", registry_hash="abc")
    grammar_diff = mint_batch_id(seed=1, grammar_version="v2", registry_hash="abc")
    registry_diff = mint_batch_id(seed=1, grammar_version="v1", registry_hash="def")
    assert base not in {seed_diff, grammar_diff, registry_diff}
    assert len({base, seed_diff, grammar_diff, registry_diff}) == 4


# ---------------------------------------------------------------------------
# Ranker composite_score is in [0, 1]
# ---------------------------------------------------------------------------


def test_every_ranker_score_is_in_unit_interval() -> None:
    """The §6.2 weighted sum of unit-interval components with weights
    summing to 1.0 is mathematically in [0, 1]; the scorer also clamps
    to absorb float drift. This is the integration-level guard."""
    r = Ranker(weights=_default_weights())
    reports = [_passing_report(f"r{i}", (f"sig_{i}",)) for i in range(20)]
    for rep in reports:
        score = r.score(rep, prior_promotion_score=0.5)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Diversifier returns exactly N (or all if pool < N) and no repeats
# ---------------------------------------------------------------------------


def test_diversifier_returns_exactly_n_when_pool_is_large() -> None:
    cands = tuple(_candidate(f"c{i}", (f"sig_{i}",), 0.5 + i * 0.01) for i in range(20))
    out = select_top_n(cands, n=5)
    assert len(out) == 5


def test_diversifier_returns_all_when_pool_smaller_than_n() -> None:
    cands = tuple(_candidate(f"c{i}", (f"sig_{i}",), 0.5 + i * 0.05) for i in range(3))
    out = select_top_n(cands, n=100)
    assert len(out) == 3


def test_diversifier_never_repeats_a_candidate() -> None:
    cands = tuple(_candidate(f"c{i}", (f"sig_{i}",), 0.5) for i in range(10))
    out = select_top_n(cands, n=10)
    names = [r.report.config.name for r in out]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# rank_batch is deterministic for the same inputs
# ---------------------------------------------------------------------------


def test_rank_batch_is_deterministic() -> None:
    r = Ranker(weights=_default_weights())
    reports = tuple(_passing_report(f"r{i}", (f"sig_{i}",)) for i in range(8))
    a = rank_batch(r, reports, promoted_strategies=(), n=3)
    b = rank_batch(r, reports, promoted_strategies=(), n=3)
    a_names = [c.report.config.name for c in a]
    b_names = [c.report.config.name for c in b]
    assert a_names == b_names


# ---------------------------------------------------------------------------
# Submitter: every submitted candidate produces a submissions row with the
# correct config_hash + status
# ---------------------------------------------------------------------------


def test_submitter_writes_consistent_config_hashes(tmp_path: Path) -> None:
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    cands = (
        _candidate("a", ("X",), 0.9),
        _candidate("b", ("Y",), 0.7),
        _candidate("c", ("Z",), 0.5),
    )
    expected_hashes = {c.report.config.config_hash for c in cands}
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=_batch(seed=0), candidates=cands, inbox_root=inbox)
        rows = conn.execute(
            "SELECT config_hash FROM submissions WHERE status = 'submitted'"
        ).fetchall()
    written_hashes = {str(r[0]) for r in rows}
    assert written_hashes == expected_hashes


# ---------------------------------------------------------------------------
# §13.4 — submissions.config_hash UNIQUE INDEX is enforced
# ---------------------------------------------------------------------------


def test_unique_index_on_config_hash_is_enforced(tmp_path: Path) -> None:
    """Direct INSERT of duplicate config_hash should raise. This is the
    structural enforcement of hard rule #9."""
    import duckdb

    forge_db = tmp_path / "forge.db"
    with db_connection(forge_db) as conn:
        bid = uuid.uuid4()
        ts = datetime(2026, 5, 13, tzinfo=UTC)
        conn.execute(
            "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
            "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), str(bid), "duplicate_hash", "{}", ts, "pending"],
        )
        with pytest.raises(duckdb.ConstraintException):
            conn.execute(
                "INSERT INTO submissions (forge_candidate_id, forge_batch_id, config_hash, "
                "config_json, submitted_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                [str(uuid.uuid4()), str(bid), "duplicate_hash", "{}", ts, "pending"],
            )


# ---------------------------------------------------------------------------
# Perf — full small batch end-to-end well under spec budget
# ---------------------------------------------------------------------------


def test_perf_rank_and_submit_30_candidates_under_5s(tmp_path: Path) -> None:
    """§12 Phase 4 budget is implicit (it's a 5-7 day phase, not perf-
    constrained). This is a regression guard: ranking + submitting 30
    candidates shouldn't take more than 5 seconds. Anything slower
    points to per-candidate work that should have been batched."""
    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    r = Ranker(weights=_default_weights())
    reports = tuple(_passing_report(f"r{i}", (f"sig_{i}",)) for i in range(30))
    t0 = time.perf_counter()
    ranked = rank_batch(r, reports, promoted_strategies=(), n=10)
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=_batch(seed=0), candidates=ranked, inbox_root=inbox)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"perf regression: 30-candidate batch took {elapsed:.2f}s"
