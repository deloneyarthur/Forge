"""Unit tests for ``forge.prefilters.types``.

Covers the four pre-filter value types and the Filter Protocol:

- ``FilterResult`` — frozen, score in [0, 1], read-only details.
- ``PreFilterReport`` — §5.4 shape, ``composite_score`` defaults to ``None``
  per Phase 3 closure D2 (ranker populates in Phase 4).
- ``FilterContext`` — frozen bundle of per-batch state read by every filter.
- ``Filter`` Protocol — ``name: str``, ``cost_tier: int``,
  ``apply(config, ctx) -> FilterResult``. Structural typing, ``@runtime_checkable``.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import pytest

from forge.prefilters.types import (
    Filter,
    FilterContext,
    FilterResult,
    PreFilterReport,
)
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig


# ---------------------------------------------------------------------------
# FilterResult
# ---------------------------------------------------------------------------


def test_filter_result_is_frozen() -> None:
    """FilterResult must be immutable so battery results can't be tampered
    with post-hoc."""
    r = FilterResult(passed=True, score=0.7)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.passed = False  # type: ignore[misc]


def test_filter_result_uses_slots() -> None:
    """slots=True keeps the per-result memory footprint flat — there will
    be 10K of these per batch."""
    r = FilterResult(passed=True, score=0.5)
    assert not hasattr(r, "__dict__")


@pytest.mark.parametrize("score", [0.0, 0.001, 0.5, 0.999, 1.0])
def test_filter_result_accepts_score_in_unit_interval(score: float) -> None:
    r = FilterResult(passed=True, score=score)
    assert r.score == score


@pytest.mark.parametrize("score", [-0.001, -1.0, 1.0001, 2.0, float("inf"), float("nan")])
def test_filter_result_rejects_score_out_of_unit_interval(score: float) -> None:
    """§5.4 contract: ``score`` is in [0, 1]. NaN / inf also rejected so
    composite-score math in Phase 4 can't produce NaN."""
    with pytest.raises(ValueError, match="score"):
        FilterResult(passed=True, score=score)


def test_filter_result_default_details_is_empty_mapping() -> None:
    r = FilterResult(passed=True, score=0.5)
    assert isinstance(r.details, Mapping)
    assert len(r.details) == 0


def test_filter_result_details_is_read_only() -> None:
    """A filter that supplies details cannot have them mutated by a later
    stage — pre-filter logs would diverge from the in-memory report."""
    r = FilterResult(passed=True, score=0.5, details={"n_activations": 42})
    with pytest.raises(TypeError):
        r.details["n_activations"] = 0  # type: ignore[index]


def test_filter_result_accepts_arbitrary_details_values() -> None:
    """Filter authors store filter-specific diagnostics. The type is
    intentionally ``Mapping[str, Any]`` — strict typing would force each
    filter into a dataclass."""
    r = FilterResult(
        passed=False,
        score=0.0,
        details={"reason": "max_lookback_exceeds_data_history", "needed": 200, "have": 100},
    )
    assert r.details["reason"] == "max_lookback_exceeds_data_history"
    assert r.details["have"] == 100


# ---------------------------------------------------------------------------
# PreFilterReport
# ---------------------------------------------------------------------------


def test_pre_filter_report_composite_score_defaults_to_none() -> None:
    """Phase 3 closure D2: composite_score stays None until the Phase 4
    ranker fills it via §6.2 weights. The default makes it impossible to
    accidentally treat a pre-filter run as ranked output."""
    cfg = minimal_strategy_config()
    report = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results={},
        diagnostic_notes=(),
    )
    assert report.composite_score is None


def test_pre_filter_report_is_frozen() -> None:
    cfg = minimal_strategy_config()
    report = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results={},
        diagnostic_notes=(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.passed = False  # type: ignore[misc]


def test_pre_filter_report_filter_results_indexed_by_filter_name() -> None:
    cfg = minimal_strategy_config()
    results = {
        "structural_redundancy": FilterResult(passed=True, score=1.0),
        "resource_feasibility": FilterResult(passed=True, score=0.8),
    }
    report = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results=results,
        diagnostic_notes=(),
    )
    assert "structural_redundancy" in report.filter_results
    assert report.filter_results["resource_feasibility"].score == 0.8


def test_pre_filter_report_records_failure_reason_via_notes() -> None:
    """When the battery short-circuits, ``diagnostic_notes`` records why."""
    cfg = minimal_strategy_config()
    report = PreFilterReport(
        config=cfg,
        passed=False,
        filter_results={"resource_feasibility": FilterResult(passed=False, score=0.0)},
        diagnostic_notes=("short-circuited at cost_tier=2 (resource_feasibility)",),
    )
    assert not report.passed
    assert "resource_feasibility" in report.diagnostic_notes[0]


def test_pre_filter_report_composite_score_can_be_set_for_phase4_handoff() -> None:
    """Phase 4 ranker constructs a *new* report with composite_score
    filled. The field is plain ``float | None`` — no type-level lock."""
    cfg = minimal_strategy_config()
    report = PreFilterReport(
        config=cfg,
        passed=True,
        filter_results={},
        diagnostic_notes=(),
        composite_score=0.42,
    )
    assert report.composite_score == 0.42


# ---------------------------------------------------------------------------
# FilterContext
# ---------------------------------------------------------------------------


def test_filter_context_is_frozen() -> None:
    """Battery builds the context once per batch and every filter reads
    from it; mutability would invite subtle filter-order coupling."""
    registry = minimal_registry_snapshot()

    ctx = FilterContext(
        registry=registry,
        feature_cache=_StubFeatureCache(),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=_StubCalibration(),
        rng_factory=lambda name: random.Random(0),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.prior_config_hashes = frozenset({"x"})  # type: ignore[misc]


def test_filter_context_holds_required_state() -> None:
    """The five fields every filter needs: registry, feature cache, prior
    submission hashes, prior firing dates, calibration; plus the seeded
    rng_factory (hard rule #8)."""
    registry = minimal_registry_snapshot()
    ctx = FilterContext(
        registry=registry,
        feature_cache=_StubFeatureCache(),
        prior_config_hashes=frozenset({"abc123"}),
        prior_firing_dates={"abc123": frozenset()},
        calibration=_StubCalibration(),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )
    assert ctx.registry is registry
    assert "abc123" in ctx.prior_config_hashes
    # rng_factory is callable
    r = ctx.rng_factory("permutation_test")
    assert hasattr(r, "random")


# ---------------------------------------------------------------------------
# Filter Protocol
# ---------------------------------------------------------------------------


class _GoodFilter:
    """A class satisfying the Filter Protocol structurally."""

    name = "good"
    cost_tier = 1

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        del config, ctx
        return FilterResult(passed=True, score=1.0)


def test_filter_protocol_is_satisfied_by_structurally_matching_class() -> None:
    """Filter is @runtime_checkable so isinstance() works."""
    f: Filter = _GoodFilter()
    assert isinstance(f, Filter)


def test_filter_protocol_rejects_class_missing_apply() -> None:
    class _BadFilter:
        name = "bad"
        cost_tier = 1
        # no .apply method

    assert not isinstance(_BadFilter(), Filter)


def test_filter_protocol_rejects_class_missing_cost_tier() -> None:
    class _BadFilter:
        name = "bad"

        def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
            del config, ctx
            return FilterResult(passed=True, score=1.0)

    assert not isinstance(_BadFilter(), Filter)


# ---------------------------------------------------------------------------
# Stubs for the cross-module forward refs used by FilterContext
# ---------------------------------------------------------------------------


class _StubFeatureCache:
    """Placeholder until feature_cache module ships in Phase 3 module 2."""

    data_history_days = 1008

    def activation_dates(self, *args: Any, **kwargs: Any) -> frozenset:
        del args, kwargs
        return frozenset()


class _StubCalibration:
    """Placeholder until calibration module ships in Phase 3 module 3."""
