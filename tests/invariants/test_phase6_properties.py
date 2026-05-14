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
from forge.ranking.diversifier import select_top_n
from forge.ranking.scorer import Ranker
from forge.ranking.types import RankedCandidate, RankerWeights
from forge.submission.batch import BatchContext, mint_batch_id
from forge.submission.submitter import submit_batch
from tests.fixtures.grammar_property_helpers import valid_strategy_config

_RANKER_FILTER_KEYS = ("signal_density", "novelty", "regime_exposure", "permutation_test")
_ALL_FILTER_KEYS = (
    "structural_redundancy",
    "resource_feasibility",
    "signal_density",
    "expected_trades",
    "novelty",
    "regime_exposure",
    "permutation_test",
)


def _default_weights() -> RankerWeights:
    return RankerWeights(
        signal_density=0.30,
        novelty=0.25,
        regime_diversity=0.20,
        permutation_test=0.15,
        prior_promotion_proximity=0.10,
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
    unique_hashes = {c.report.config.config_hash for c in cands}

    with db_connection(forge_db) as conn:
        first = submit_batch(conn, batch=_batch_for(seed), candidates=cands, inbox_root=inbox)
        second = submit_batch(conn, batch=_batch_for(seed), candidates=cands, inbox_root=inbox)

    assert first.submitted_count == len(unique_hashes), (
        f"first submit: expected {len(unique_hashes)} unique rows, "
        f"wrote {first.submitted_count} (skipped {first.skipped_duplicate_count})"
    )
    assert second.submitted_count == 0
    assert second.skipped_duplicate_count == len(cands)


# ---------------------------------------------------------------------------
# (ii) §6.2 ranker composite score stays in [0, 1]
# ---------------------------------------------------------------------------


@given(
    config=valid_strategy_config(),
    filter_scores=st.fixed_dictionaries(
        {k: st.floats(min_value=0.0, max_value=1.0, allow_nan=False) for k in _ALL_FILTER_KEYS}
    ),
    prior_promotion=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_ranker_score_in_unit_interval(
    config: object,
    filter_scores: dict[str, float],
    prior_promotion: float,
) -> None:
    """For any in-range filter scores + prior-promotion score, the §6.2
    composite is in [0, 1]. RankerWeights sum to 1.0 by invariant; the
    scorer also clamps to absorb float drift."""
    r = Ranker(weights=_default_weights())
    report = _report_from(config, filter_scores)
    score = r.score(report, prior_promotion_score=prior_promotion)
    assert 0.0 <= score <= 1.0, (
        f"ranker score out of [0, 1]: got {score!r} for filter_scores={filter_scores!r}, "
        f"prior={prior_promotion!r}"
    )


# ---------------------------------------------------------------------------
# (iii) Diversifier returns exactly min(n, pool_size) candidates
# ---------------------------------------------------------------------------


@given(
    configs=st.lists(valid_strategy_config(), min_size=0, max_size=12),
    composite_scores=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=0, max_size=12
    ),
    n=st.integers(min_value=0, max_value=20),
)
@settings(
    max_examples=75,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_property_diversifier_returns_exactly_min_n_pool(
    configs: list[object],
    composite_scores: list[float],
    n: int,
) -> None:
    """`select_top_n(pool, n)` returns exactly `min(n, len(pool))` items.
    No selected candidate is absent from the input pool."""
    pair_count = min(len(configs), len(composite_scores))
    pool = tuple(
        RankedCandidate(
            report=_report_from(
                configs[i],
                {k: 0.5 for k in _ALL_FILTER_KEYS},
            ),
            prior_promotion_score=0.0,
            composite_score=composite_scores[i],
        )
        for i in range(pair_count)
    )
    selected = select_top_n(pool, n=n)
    expected_size = min(n, len(pool))
    assert len(selected) == expected_size, (
        f"diversifier returned {len(selected)} for pool={len(pool)}, n={n}; "
        f"expected min={expected_size}"
    )
    pool_ids = {id(c) for c in pool}
    for s in selected:
        assert id(s) in pool_ids, "diversifier returned a candidate not in the input pool"
