"""Unit tests for `forge.prefilters.structural_redundancy` (§5.3.1).

Filter 1 of the §5.2 battery (O(1), cost_tier=1). Rejects configs whose
`config_hash` has already been submitted in a prior batch.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from pathlib import Path

import pytest

from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import SyntheticFeatureCache
from forge.prefilters.structural_redundancy import StructuralRedundancyFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


def _ctx(prior_hashes: frozenset[str]) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=SyntheticFeatureCache(root_seed=0),
        prior_config_hashes=prior_hashes,
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def test_satisfies_filter_protocol() -> None:
    f: Filter = StructuralRedundancyFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = StructuralRedundancyFilter()
    assert f.name == "structural_redundancy"
    assert f.cost_tier == 1


def test_passes_when_hash_not_in_prior_set() -> None:
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(prior_hashes=frozenset({"some_other_hash"})))
    assert result.passed
    assert result.score == 1.0


def test_passes_with_empty_prior_set() -> None:
    """First batch: nothing seen yet, every config is novel."""
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(prior_hashes=frozenset()))
    assert result.passed


def test_rejects_when_hash_already_seen() -> None:
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(prior_hashes=frozenset({cfg.config_hash})))
    assert not result.passed
    assert result.score == 0.0


def test_details_record_hash_on_rejection() -> None:
    """Operator reviewing the rejection should see *which* hash collided."""
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(prior_hashes=frozenset({cfg.config_hash})))
    assert result.details["config_hash"] == cfg.config_hash


def test_details_empty_on_pass() -> None:
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(prior_hashes=frozenset()))
    assert isinstance(result.details, Mapping)
    # Pass results don't need to carry anything beyond passed/score.
    assert "config_hash" not in result.details


def test_is_pure_does_not_mutate_context() -> None:
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    prior = frozenset({"x", "y"})
    ctx = _ctx(prior_hashes=prior)
    f.apply(cfg, ctx)
    assert ctx.prior_config_hashes == prior


@pytest.mark.parametrize("n_prior", [0, 1, 100, 10_000])
def test_constant_time_irrespective_of_prior_set_size(n_prior: int) -> None:
    """O(1) cost_tier=1 contract: time is dominated by frozenset lookup,
    not by `len(prior_config_hashes)`. We can't reliably assert wall-time
    here but we can confirm the filter still returns correctly at scale."""
    f = StructuralRedundancyFilter()
    cfg = minimal_strategy_config()
    prior = frozenset(f"hash_{i:032x}" for i in range(n_prior))
    result = f.apply(cfg, _ctx(prior_hashes=prior))
    assert result.passed  # cfg.config_hash isn't among the synthetic ones


# Tests for what happens when the same config is shown to the filter twice
# (without registering it as prior between calls) belong to the battery
# orchestrator (module 11). This filter only consumes the
# `prior_config_hashes` view it is given.
