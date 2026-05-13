"""§12 Phase 1 acceptance: validate < 10 ms / config.

Runs the validator across 100 sampled configs and asserts the mean wall
clock time per validation is under 10 ms. Uses ``perf_counter`` (not
``time.monotonic``) for the highest-resolution timer available; uses a
fixed Hypothesis seed for reproducibility (and to keep CI variance low).

This is a smoke-level perf test: the validator is pure-Python and the
21 rules are all O(N) over signals/exits, so 10 ms is a generous bound.
A regression that pushes this past 10 ms suggests a quadratic loop or
an unnecessary repeated registry walk — surface that immediately rather
than silently slowing the producer.
"""

from __future__ import annotations

import time
import warnings
from pathlib import Path

import pytest
from hypothesis.errors import NonInteractiveExampleWarning

from forge.grammar import load_grammar, validate
from tests.fixtures.grammar_property_helpers import valid_strategy_config
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"

_VALIDATE_TIME_BUDGET_S = 0.010  # 10 ms per §12 acceptance
_PERF_SAMPLE_SIZE = 100


@pytest.fixture(scope="module")
def grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


def test_validate_under_10ms_mean(grammar: object) -> None:
    registry = minimal_registry_snapshot()

    # Pull the configs deterministically — we want a reproducible sample.
    # `strategy.example()` warns about non-interactive use; the warning is
    # for property tests, not perf benchmarks where one-shot draws are
    # the point.
    strategy = valid_strategy_config()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NonInteractiveExampleWarning)
        configs = [strategy.example() for _ in range(_PERF_SAMPLE_SIZE)]

    start = time.perf_counter()
    for cfg in configs:
        result = validate(cfg, grammar, registry)  # type: ignore[arg-type]
        assert result.valid, f"perf sample wasn't valid: {result.errors}"
    elapsed = time.perf_counter() - start

    mean_per_config = elapsed / _PERF_SAMPLE_SIZE
    assert mean_per_config < _VALIDATE_TIME_BUDGET_S, (
        f"validate() too slow: {mean_per_config * 1000:.2f} ms / config "
        f"over {_PERF_SAMPLE_SIZE} samples (budget: 10 ms)"
    )
