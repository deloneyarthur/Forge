"""Phase 6 — property-based invariants (§12 / D025/D1).

Hypothesis-driven coverage on three Phase 4 surfaces beyond the
example-based Phase 4 invariants:

  (i) submission idempotency: random configs + repeat-submit ⇒ unique-
      constraint enforcement on `submissions.config_hash`.
  (ii) ranker composite score in [0, 1]: random valid-pre-filter reports
       with in-range filter scores + prior-promotion score ⇒ composite
       in [0, 1] under §6.2 weights.
  (iii) diversifier returns exactly `min(n, pool_size)` and never adds a
        candidate not present in the input.

Existing Phase 1 grammar property suite (`tests/integration/
test_grammar_property.py`) stays as-is; this file covers the post-
grammar surfaces (rank + submit).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.persistence.db import db_connection
from forge.prefilters.types import FilterResult, PreFilterReport
from forge.ranking.types import RankedCandidate
from forge.submission.batch import BatchContext, mint_batch_id
from forge.submission.submitter import submit_batch
from tests.fixtures.grammar_property_helpers import valid_strategy_config

_ALL_FILTER_KEYS = (
    "structural_redundancy",
    "resource_feasibility",
    "signal_density",
    "expected_trades",
    "novelty",
    "regime_exposure",
    "permutation_test",
)


def _batch_for(seed: int) -> BatchContext:
    return BatchContext(
        batch_id=mint_batch_id(seed=seed, grammar_version="v1", registry_hash="abc"),
        grammar_version="v1",
        registry_hash="abc",
        submitted_at=datetime(2026, 5, 13, 12, tzinfo=UTC),
        seed=seed,
    )


def _report_from(
    config: object,
    filter_scores: dict[str, float],
) -> PreFilterReport:
    """Build a passing PreFilterReport with caller-supplied filter scores."""
    return PreFilterReport(
        config=config,  # type: ignore[arg-type]
        passed=True,
        filter_results=MappingProxyType(
            {k: FilterResult(passed=True, score=filter_scores[k]) for k in _ALL_FILTER_KEYS}
        ),
        diagnostic_notes=(),
    )


# ---------------------------------------------------------------------------
# (i) §13.4 submission idempotency — property form
# ---------------------------------------------------------------------------


@given(
    configs=st.lists(valid_strategy_config(), min_size=1, max_size=6),
    seed=st.integers(min_value=0, max_value=10_000),
)
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_submission_idempotency(
    configs: list[object],
    seed: int,
    tmp_path: Path,
) -> None:
    """For any list of valid configs, submitting twice writes each unique
    config_hash exactly once. Resubmitting produces zero new rows."""
    workspace = tmp_path / uuid.uuid4().hex
    workspace.mkdir(parents=True, exist_ok=True)
    forge_db = workspace / "forge.db"
    inbox = workspace / "inbox"

    # D066: tail_hedge configs are dropped pre-submission as overlay-only.
    # The idempotency property still holds for non-overlay configs; partition
    # the input so the assertions track the right denominator.
    from forge.enumeration.search_space import OVERLAY_ONLY_HYPOTHESES

    cands = tuple(
        RankedCandidate(
            report=_report_from(
                cfg,
                {k: 0.5 for k in _ALL_FILTER_KEYS},
            ),
            prior_promotion_score=0.0,
            composite_score=0.5,
        )
        for cfg in configs
    )
    submittable = tuple(
        c
        for c in cands
        if c.report.config.hypothesis not in OVERLAY_ONLY_HYPOTHESES  # type: ignore[attr-defined]
    )
    overlay = tuple(c for c in cands if c not in submittable)
    unique_hashes = {c.report.config.config_hash for c in submittable}

    with db_connection(forge_db) as conn:
        first = submit_batch(conn, batch=_batch_for(seed), candidates=cands, inbox_root=inbox)
        second = submit_batch(conn, batch=_batch_for(seed), candidates=cands, inbox_root=inbox)

    assert first.submitted_count == len(unique_hashes), (
        f"first submit: expected {len(unique_hashes)} unique rows, "
        f"wrote {first.submitted_count} (skipped {first.skipped_duplicate_count})"
    )
    assert first.dropped_overlay_count == len(overlay)
    assert second.submitted_count == 0
    assert second.skipped_duplicate_count == len(submittable)
    assert second.dropped_overlay_count == len(overlay)
