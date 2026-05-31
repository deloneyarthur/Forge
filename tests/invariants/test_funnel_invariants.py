"""Funnel-export invariants (D096 — FUNNEL_INSTRUMENTATION_FORGE.md Part B).

The pre-filter funnel export reports, per grammar version, three counts:
`enumerated` (configs run through the battery), `survived` (configs that
passed it), and a `rejection_breakdown` (first-failing filter per rejected
config). For the funnel to be self-consistent — and for Crucible's combined
funnel to trust Forge's two upstream stages — the breakdown MUST account for
exactly the configs that did not survive:

    sum(rejection_breakdown) == enumerated - survived

This file locks that invariant at the recording layer (the two writers that
populate `batch_summaries`) so a future change to either writer can't silently
desync the funnel. The aggregation layer re-checks it on the exported product.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from forge.persistence.db import db_connection
from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.types import RankedCandidate
from forge.submission.batch import BatchContext, mint_batch_id
from forge.submission.submitter import record_prefilter_rejections, submit_batch
from tests.fixtures.strategy_configs import minimal_strategy_config


def _ctx(seed: int) -> BatchContext:
    bid = mint_batch_id(seed=seed, grammar_version="v4", registry_hash="reg")
    return BatchContext(
        batch_id=bid,
        grammar_version="v4",
        registry_hash="reg",
        submitted_at=datetime(2026, 5, 29, 12, tzinfo=UTC),
        seed=seed,
    )


def _report(name: str, *, passed: bool, failing_filter: str | None = None) -> PreFilterReport:
    cfg = minimal_strategy_config().model_copy(update={"name": name})
    if passed:
        results = MappingProxyType({"signal_density": FilterResult(passed=True, score=0.9)})
    else:
        assert failing_filter is not None
        results = MappingProxyType({failing_filter: FilterResult(passed=False, score=0.0)})
    return PreFilterReport(
        config=cfg,
        passed=passed,
        filter_results=results,
        diagnostic_notes=(),
    )


def test_rejection_breakdown_sums_to_enumerated_minus_survived(tmp_path: Path) -> None:
    """The load-bearing funnel invariant, on real recorded DB state.

    Feed a mixed report set through the two writers exactly as the run loop
    does (submit_batch records enumerated/survived; record_prefilter_rejections
    records the breakdown), then read all three back and assert they reconcile.
    """
    survivors = [_report(f"ok{i}", passed=True) for i in range(4)]
    rejected = [
        _report("r1", passed=False, failing_filter="expected_trades"),
        _report("r2", passed=False, failing_filter="expected_trades"),
        _report("r3", passed=False, failing_filter="expected_trades"),
        _report("r4", passed=False, failing_filter="novelty"),
        _report("r5", passed=False, failing_filter="signal_density"),
    ]
    all_reports = [*survivors, *rejected]
    candidates = tuple(
        RankedCandidate(report=r, prior_promotion_score=0.0, composite_score=0.5) for r in survivors
    )
    batch = _ctx(seed=4096)

    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    with db_connection(forge_db) as conn:
        submit_batch(
            conn,
            batch=batch,
            candidates=candidates,
            inbox_root=inbox,
            enumerated_count=len(all_reports),
            survived_count=sum(1 for r in all_reports if r.passed),
        )
        record_prefilter_rejections(conn, batch_id=batch.batch_id, reports=all_reports)
        row = conn.execute(
            "SELECT enumerated_count, survived_count, prefilter_rejections "
            "FROM batch_summaries WHERE forge_batch_id = ?",
            [str(batch.batch_id)],
        ).fetchone()

    assert row is not None
    enumerated, survived, rejections_json = row
    import json

    rejections = (
        json.loads(rejections_json) if isinstance(rejections_json, str) else rejections_json
    )
    assert int(enumerated) == 9
    assert int(survived) == 4
    assert sum(rejections.values()) == int(enumerated) - int(survived)


def test_grammar_version_stamp_preserves_config_hash(tmp_path: Path) -> None:
    """D097 hard-rule-#9 guard: stamping grammar_version on a submission must
    NOT change config_hash.

    config_hash is the cross-system identity key: it names the inbox file
    (idempotent re-submission), keys the `submissions` unique index (hard rule
    #9 -- no double submit), and keys the config_hash -> grammar_version
    join-map. crucible_contracts (>= 1.14.0) excludes grammar_version from the
    hash; this pins the property Forge's submission path relies on, so a future
    contracts change that re-included it fails loudly here instead of silently
    breaking dedup and the join-map.
    """
    cand = RankedCandidate(
        report=_report("gvkeep", passed=True),
        prior_promotion_score=0.0,
        composite_score=0.5,
    )
    expected_hash = cand.report.config.config_hash  # computed pre-stamp
    batch = _ctx(seed=9701)  # grammar_version="v4"

    forge_db = tmp_path / "forge.db"
    inbox = tmp_path / "inbox"
    with db_connection(forge_db) as conn:
        submit_batch(conn, batch=batch, candidates=(cand,), inbox_root=inbox)
        row = conn.execute(
            "SELECT config_hash FROM submissions WHERE forge_batch_id = ?",
            [str(batch.batch_id)],
        ).fetchone()

    files = list(inbox.glob("*.json"))
    assert len(files) == 1
    assert files[0].stem == expected_hash
    assert row is not None
    assert row[0] == expected_hash
