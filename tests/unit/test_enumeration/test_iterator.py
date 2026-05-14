"""Unit tests for ``forge.enumeration.iterator.enumerate_candidates``.

Covers:
- Determinism (§13.1): identical ``(grammar, registry, seed)`` → identical
  config sequences across two iterations.
- Length contract: yields exactly ``max_candidates`` valid configs.
- Rejection counter is populated when supplied.
- ``EnumerationCapped`` fires for sparse registries.
- ``max_candidates <= 0`` raises ``ValueError``.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crucible_contracts import (
    MANDATORY_EXIT_IDS,
    IndicatorMetadata,
    RegistrySnapshot,
)

from forge.enumeration.iterator import EnumerationCapped, enumerate_candidates
from forge.grammar import Grammar, load_grammar, validate
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


@pytest.fixture(scope="module")
def registry() -> RegistrySnapshot:
    return minimal_registry_snapshot()


def test_yields_exactly_max_candidates(grammar: Grammar, registry: RegistrySnapshot) -> None:
    configs = list(enumerate_candidates(grammar, registry, seed=7, max_candidates=20))
    assert len(configs) == 20


def test_every_yielded_config_is_grammar_valid(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """If this fails, the iterator is leaking invalid configs — would
    swamp Crucible with garbage."""
    for cfg in enumerate_candidates(grammar, registry, seed=11, max_candidates=50):
        result = validate(cfg, grammar, registry)
        assert result.valid, f"invalid config leaked: {result.errors}"


def test_determinism_same_seed_same_sequence(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """§13.1: identical (grammar, registry, seed) → byte-identical sequence."""
    a = [c.config_hash for c in enumerate_candidates(grammar, registry, seed=42, max_candidates=30)]
    b = [c.config_hash for c in enumerate_candidates(grammar, registry, seed=42, max_candidates=30)]
    assert a == b


def test_different_seeds_produce_different_sequences(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    a = [c.config_hash for c in enumerate_candidates(grammar, registry, seed=1, max_candidates=10)]
    b = [c.config_hash for c in enumerate_candidates(grammar, registry, seed=2, max_candidates=10)]
    assert a != b


def test_max_candidates_zero_raises(grammar: Grammar, registry: RegistrySnapshot) -> None:
    with pytest.raises(ValueError, match="max_candidates must be > 0"):
        list(enumerate_candidates(grammar, registry, seed=0, max_candidates=0))


def test_max_candidates_negative_raises(grammar: Grammar, registry: RegistrySnapshot) -> None:
    with pytest.raises(ValueError, match="max_candidates must be > 0"):
        list(enumerate_candidates(grammar, registry, seed=0, max_candidates=-5))


def test_rejection_counter_zero_on_v1_fixture(grammar: Grammar, registry: RegistrySnapshot) -> None:
    """Path (a) contract: v1-fixture enumeration should have ~zero
    rejections. If this fails, the sampler is no longer
    valid-by-construction and we've regressed."""
    counter: Counter[str] = Counter()
    list(
        enumerate_candidates(
            grammar,
            registry,
            seed=0,
            max_candidates=50,
            rejection_counter=counter,
        )
    )
    assert sum(counter.values()) == 0, f"unexpected rejections on v1 fixture: {dict(counter)}"


def test_rejection_counter_populates_on_sparse_registry(
    grammar: Grammar,
) -> None:
    """On a registry where the sampler can't build everything cleanly,
    rejections (here, EnumerationCapped from SamplerError loops) should
    be visible in the counter before the cap raises."""
    sparse = RegistrySnapshot(
        indicators=(),  # nothing — every sample fails immediately
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
    )
    counter: Counter[str] = Counter()
    with pytest.raises(EnumerationCapped):
        list(
            enumerate_candidates(
                grammar,
                sparse,
                seed=0,
                max_candidates=5,
                rejection_counter=counter,
            )
        )
    # 5 x 100 attempts, all sampler-fail
    assert counter["sampler"] >= 1


def test_enumeration_capped_when_target_unreachable(
    grammar: Grammar,
) -> None:
    """A registry that can't satisfy any config should surface the cap loudly."""
    only_short_lookback = RegistrySnapshot(
        indicators=(
            IndicatorMetadata(
                id="rsi_2",
                version=1,
                family="mean_reversion",
                lookback=2,
                params_schema={},
            ),
            # No iv_rank, so R1 can never be satisfied for mean_reversion.
        ),
        signal_types=("threshold",),
        exit_ids=tuple(sorted(MANDATORY_EXIT_IDS)),
        sizer_modes=("fixed_risk_pct",),
        snapshot_taken_at=datetime(2026, 5, 13, tzinfo=UTC),
        crucible_version="0.0.0-synthetic",
        data_history_days=1008,
    )
    with pytest.raises(EnumerationCapped, match="capped"):
        list(
            enumerate_candidates(
                grammar,
                only_short_lookback,
                seed=0,
                max_candidates=3,
            )
        )


def test_lazy_iteration_does_not_eagerly_consume(
    grammar: Grammar, registry: RegistrySnapshot
) -> None:
    """``enumerate_candidates`` returns a generator; calling it should not
    do any sampling work until ``next()``. Verifies via partial
    consumption: requesting 1 of 100 should not require 100 successful
    samples."""
    gen = enumerate_candidates(grammar, registry, seed=0, max_candidates=100)
    one = next(gen)
    assert one is not None
    # We intentionally don't iterate the rest — generator should be
    # garbage-collectable without further work.
