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
from forge.prefilters.regime_exposure import RegimeExposureFilter
from forge.prefilters.resource_feasibility import ResourceFeasibilityFilter
from forge.prefilters.signal_density import SignalDensityFilter
from forge.prefilters.structural_redundancy import StructuralRedundancyFilter
from forge.prefilters.types import Filter, FilterResult, PreFilterReport

if TYPE_CHECKING:
    from collections.abc import Iterable

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


def default_filters() -> tuple[Filter, ...]:
    """The seven §5 filters in cost_tier order (1..7)."""
    return (
        StructuralRedundancyFilter(),
        ResourceFeasibilityFilter(),
        SignalDensityFilter(),
        ExpectedTradesFilter(),
        NoveltyFilter(),
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

    for f in ordered:
        result = f.apply(config, ctx)
        results[f.name] = result
        if not result.passed:
            overall_passed = False
            notes.append(f"short-circuited at cost_tier={f.cost_tier} (filter {f.name!r})")
            break

    return PreFilterReport(
        config=config,
        passed=overall_passed,
        filter_results=results,
        diagnostic_notes=tuple(notes),
        composite_score=None,
    )


__all__ = ["default_filters", "run_battery"]
