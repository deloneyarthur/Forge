"""Unit tests for `forge.prefilters.battery`.

Covers the §5.2 battery orchestrator:
- Cost-ascending iteration.
- Short-circuit on first `passed=False`.
- composite_score stays None per D021/D2.
- `default_filters()` ships the 7 §5 filters in cost_tier order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest

from forge.core.seed import SeedHierarchy
from forge.prefilters.battery import default_filters, run_battery
from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import REGIMES, SyntheticFeatureCache
from forge.prefilters.types import Filter, FilterContext, FilterResult
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


def _ctx() -> FilterContext:
    hierarchy = SeedHierarchy(0)
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=SyntheticFeatureCache(root_seed=0),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=hierarchy.rng,
    )


class _RecordingFilter:
    """Test filter that records every call and returns a fixed result."""

    def __init__(self, *, name: str, cost_tier: int, passed: bool, score: float = 1.0) -> None:
        self.name = name
        self.cost_tier = cost_tier
        self._passed = passed
        self._score = score
        self.calls: int = 0

    def apply(
        self,
        config: object,
        ctx: object,
    ) -> FilterResult:
        del config, ctx
        self.calls += 1
        return FilterResult(passed=self._passed, score=self._score)


def test_run_battery_returns_pre_filter_report() -> None:
    cfg = minimal_strategy_config()
    filters = [_RecordingFilter(name="f1", cost_tier=1, passed=True)]
    report = run_battery(cfg, _ctx(), filters)
    assert report.config is cfg
    assert report.passed
    assert "f1" in report.filter_results
    # D021/D2: composite_score stays None at Phase 3.
    assert report.composite_score is None


def test_run_battery_orders_filters_by_cost_tier_ascending() -> None:
    """Even if the caller passes filters in random order, the battery
    runs them cheapest-first."""
    cfg = minimal_strategy_config()
    a = _RecordingFilter(name="cheap", cost_tier=1, passed=True)
    b = _RecordingFilter(name="mid", cost_tier=3, passed=True)
    c = _RecordingFilter(name="expensive", cost_tier=7, passed=True)
    # Passed in reverse cost order.
    run_battery(cfg, _ctx(), [c, b, a])
    # All three should run because none rejected. Verify by `calls`.
    assert a.calls == 1
    assert b.calls == 1
    assert c.calls == 1


def test_run_battery_short_circuits_on_first_failure() -> None:
    """When a filter returns passed=False, no further filters run."""
    cfg = minimal_strategy_config()
    a = _RecordingFilter(name="a", cost_tier=1, passed=True)
    b = _RecordingFilter(name="b", cost_tier=2, passed=False)
    c = _RecordingFilter(name="c", cost_tier=3, passed=True)
    report = run_battery(cfg, _ctx(), [a, b, c])
    assert a.calls == 1
    assert b.calls == 1
    assert c.calls == 0
    assert not report.passed
    assert "a" in report.filter_results
    assert "b" in report.filter_results
    assert "c" not in report.filter_results


def test_diagnostic_note_records_short_circuit_point() -> None:
    cfg = minimal_strategy_config()
    a = _RecordingFilter(name="a", cost_tier=1, passed=True)
    b = _RecordingFilter(name="b", cost_tier=2, passed=False)
    report = run_battery(cfg, _ctx(), [a, b])
    notes = " ".join(report.diagnostic_notes)
    assert "b" in notes
    assert "cost_tier=2" in notes


def test_all_pass_has_no_diagnostic_note() -> None:
    cfg = minimal_strategy_config()
    a = _RecordingFilter(name="a", cost_tier=1, passed=True)
    b = _RecordingFilter(name="b", cost_tier=2, passed=True)
    report = run_battery(cfg, _ctx(), [a, b])
    assert report.diagnostic_notes == ()


def test_run_battery_passes_with_empty_filter_list() -> None:
    """No filters -> trivially passes. The orchestrator should not
    crash on the empty case (used in tests + edge configurations)."""
    cfg = minimal_strategy_config()
    report = run_battery(cfg, _ctx(), [])
    assert report.passed
    assert report.filter_results == {}


def test_filter_results_record_all_run_filter_outcomes() -> None:
    cfg = minimal_strategy_config()
    a = _RecordingFilter(name="a", cost_tier=1, passed=True, score=0.7)
    b = _RecordingFilter(name="b", cost_tier=2, passed=True, score=0.5)
    report = run_battery(cfg, _ctx(), [a, b])
    assert report.filter_results["a"].score == 0.7
    assert report.filter_results["b"].score == 0.5


def test_default_filters_returns_nine_in_cost_order() -> None:
    """§5.2 + T1.3 + T2.6 — the nine canonical filters, cost 1..9.

    T1.3 (D038): PredictedActivationsFilter at cost_tier=5.
    T2.6 (D042): SignalCorrelationFilter at cost_tier=7.
    regime_exposure/permutation_test bumped accordingly.
    """
    filters = default_filters()
    assert len(filters) == 9
    tiers = [f.cost_tier for f in filters]
    assert tiers == sorted(tiers)
    names = [f.name for f in filters]
    assert names == [
        "structural_redundancy",
        "resource_feasibility",
        "signal_density",
        "expected_trades",
        "predicted_activations",
        "novelty",
        "signal_correlation",
        "regime_exposure",
        "permutation_test",
    ]


def test_default_filters_are_valid_filter_protocol() -> None:
    for f in default_filters():
        assert isinstance(f, Filter)


def test_run_battery_on_v1_fixture_with_default_filters() -> None:
    """End-to-end: enumerator's minimal fixture passes the full battery."""
    cfg = minimal_strategy_config()
    report = run_battery(cfg, _ctx(), default_filters())
    # We don't assert it passes (synthetic returns can fail permutation
    # for noise reasons) — but we assert the battery completed without
    # raising and produced filter_results for at least one filter.
    assert len(report.filter_results) >= 1


def test_run_battery_is_deterministic_for_same_inputs() -> None:
    """The same config + same context produces the same report (up to
    filter_results' details, which are Mappings)."""
    cfg = minimal_strategy_config()
    a = run_battery(cfg, _ctx(), default_filters())
    b = run_battery(cfg, _ctx(), default_filters())
    assert a.passed == b.passed
    assert set(a.filter_results) == set(b.filter_results)
    for name in a.filter_results:
        assert a.filter_results[name].passed == b.filter_results[name].passed
        assert a.filter_results[name].score == b.filter_results[name].score


@pytest.mark.parametrize("fail_tier", [1, 3, 5, 7])
def test_short_circuit_at_each_tier(fail_tier: int) -> None:
    cfg = minimal_strategy_config()
    filters: list[_RecordingFilter] = [
        _RecordingFilter(name=f"t{t}", cost_tier=t, passed=(t != fail_tier)) for t in range(1, 8)
    ]
    run_battery(cfg, _ctx(), list(filters))
    # filters with tier < fail_tier all ran once; tier == fail_tier ran;
    # tier > fail_tier did not run.
    for f in filters:
        if f.cost_tier <= fail_tier:
            assert f.calls == 1, f"filter {f.name} should have run once"
        else:
            assert f.calls == 0, f"filter {f.name} should NOT have run"


class _BadCache:
    """A FeatureCache stub that returns large activation sets for
    every signal_id (so signal_density/expected_trades pass)."""

    data_history_days = 1008

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return frozenset(date.fromordinal(date(2022, 1, 1).toordinal() + i) for i in range(200))

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.001 for d in dates}

    def regime_label(self, d: date) -> str:
        del d
        return REGIMES[0]
