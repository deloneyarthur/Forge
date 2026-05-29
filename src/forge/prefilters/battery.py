"""Pre-filter battery orchestrator. DESIGN.md §5.2.

`run_battery(config, ctx, filters) -> PreFilterReport` iterates filters
in cost_tier order with short-circuit on the first `passed=False`.
`default_filters()` returns the seven canonical filters from §5 in cost
order — what production code uses.

`PreFilterReport.composite_score` stays `None` (D021/D2); the Phase 4
ranker fills it via §6.2 weights from `filter_results`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge.prefilters.expected_trades import ExpectedTradesFilter
from forge.prefilters.novelty import NoveltyFilter
from forge.prefilters.permutation_test import PermutationTestFilter
from forge.prefilters.predicted_activations import PredictedActivationsFilter
from forge.prefilters.regime_exposure import RegimeExposureFilter
from forge.prefilters.resource_feasibility import ResourceFeasibilityFilter
from forge.prefilters.signal_correlation import SignalCorrelationFilter
from forge.prefilters.signal_density import SignalDensityFilter
from forge.prefilters.structural_redundancy import StructuralRedundancyFilter
from forge.prefilters.types import (
    FeatureDataUnavailable,
    Filter,
    FilterResult,
    PreFilterReport,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


def default_filters() -> tuple[Filter, ...]:
    """The nine §5 filters in cost_tier order (1..9).

    Insertions over v1.0:
      - T1.3 (D038): PredictedActivationsFilter at cost_tier=5
      - T2.6 (D042): SignalCorrelationFilter at cost_tier=7
    RegimeExposureFilter and PermutationTestFilter bumped accordingly.
    """
    return (
        StructuralRedundancyFilter(),
        ResourceFeasibilityFilter(),
        SignalDensityFilter(),
        ExpectedTradesFilter(),
        PredictedActivationsFilter(),
        NoveltyFilter(),
        SignalCorrelationFilter(),
        RegimeExposureFilter(),
        PermutationTestFilter(),
    )


def run_battery(
    config: StrategyConfig,
    ctx: FilterContext,
    filters: Iterable[Filter],
) -> PreFilterReport:
    """Run filters in cost_tier order, short-circuiting on the first
    failure. Returns a `PreFilterReport` with one `FilterResult` per
    filter that actually ran.

    composite_score is left as `None` — the Phase 4 ranker computes
    §6.2's weighted sum.
    """
    ordered: list[Filter] = sorted(filters, key=lambda f: f.cost_tier)
    results: dict[str, FilterResult] = {}
    notes: list[str] = []
    overall_passed = True

    # If the feature cache supports per-config prefetch (CrucibleFeatureCache),
    # batch-load this config's features before iterating filters. The
    # SyntheticFeatureCache has no prefetch and serves per-call; the duck-type
    # check keeps both implementations compatible.
    prefetch = getattr(ctx.feature_cache, "prefetch_for_config", None)
    if callable(prefetch):
        prefetch(config)

    # M-5: if the active underlying's feature window came back empty, short-circuit
    # to an explicit data_unavailable verdict — distinct from a signal-quality FAIL
    # — BEFORE any filter runs. Otherwise regime_exposure/permutation_test would
    # mislabel a thin-data underlying as a genuine rejection (the D080 class).
    unavailable_check = getattr(
        ctx.feature_cache, "active_underlying_data_unavailable", None,
    )
    if callable(unavailable_check) and unavailable_check():
        return _data_unavailable_report(config, results)

    try:
        for f in ordered:
            result = f.apply(config, ctx)
            results[f.name] = result
            if not result.passed:
                overall_passed = False
                notes.append(f"short-circuited at cost_tier={f.cost_tier} (filter {f.name!r})")
                break
    except FeatureDataUnavailable:
        # Safety net: a feature accessor raised mid-pass even though the proactive
        # check didn't fire (e.g. a cache impl that flags lazily). Treat it as a
        # data_unavailable verdict rather than crashing the batch.
        return _data_unavailable_report(config, results)

    return PreFilterReport(
        config=config,
        passed=overall_passed,
        filter_results=results,
        diagnostic_notes=tuple(notes),
        composite_score=None,
    )


def _data_unavailable_report(
    config: StrategyConfig,
    results: dict[str, FilterResult],
) -> PreFilterReport:
    """Build the M-5 data_unavailable verdict, preserving any filter results
    that completed before the short-circuit."""
    return PreFilterReport(
        config=config,
        passed=False,
        filter_results=results,
        diagnostic_notes=("data_unavailable: feature-cache window empty for underlying",),
        composite_score=None,
        data_unavailable=True,
    )


__all__ = ["default_filters", "run_battery"]
