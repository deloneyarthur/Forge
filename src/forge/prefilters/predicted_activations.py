"""Filter 5: predicted activations. PROMPT_5_FORGE_V1_1_REVISED §T1.3.

Counts the intersection of the directional signal's activations with the
regime gates' activations. Rejects below
`calibration.predicted_activations.min_entries` (default 10).

**The silent-failure mode this catches**: a config can pass the existing
7 pre-filters (structural / resource / signal_density / expected_trades /
novelty / regime_exposure / permutation_test) yet still produce zero
trades during the full backtest because the directional signal and the
regime gate **never co-fire** on the chosen underlying. The most
diagnostic instance from the translation corpus: `days_to_earnings <= 3`
regime gate on a SPY config — `days_to_earnings` returns the sentinel
value 999 for ETFs (no earnings), so the regime is *never* "approved"
and the intersection is structurally empty. Pre-PromptV1.1, that config
ate 1-2 hours of Crucible compute and contributed zero learning. This
filter rejects it before submission.

Mechanism (Phase 1 implementation):
  1. Load directional signal's `activation_dates` from the feature cache
     (set of dates where the threshold predicate is True).
  2. Load each `regime_filter` signal's `activation_dates` (set of dates
     where the regime gate is open).
  3. Intersect: `combined = directional ∩ regime_a ∩ regime_b ∩ ...`
  4. Reject if `len(combined) < min_entries`.

**T1.1 / T1.2 forward-compatibility**: when `SignalSpec` later grows
`direction` (T1.1) and `entry_cadence` (T1.2) fields, this filter will
be updated to:
  - Honor `direction="long_put"` for `op="<"` semantics (currently
    transparent because activation_dates already incorporates op).
  - Distinguish `on_edge` (count transitions) from `on_each_bar` (count
    every-bar activations) — currently always treats as on_each_bar,
    which is the conservative over-count direction (fewer false-rejects).

Score is `min(1.0, log1p(combined) / log1p(10 * min_entries))` — graceful
at low counts, saturates near 10x the threshold, matches the pattern
established by SignalDensityFilter / ExpectedTradesFilter.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


class PredictedActivationsFilter:
    """T1.3 — reject configs whose directional x regime intersection is too sparse."""

    name = "predicted_activations"
    cost_tier = 5

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directionals = [s for s in config.signals if s.role == "directional"]
        if len(directionals) != 1:
            # §3.5 S2 guarantees exactly one. Defensive guard mirrors
            # SignalDensityFilter's pattern.
            msg = (
                "predicted_activations: expected exactly one directional "
                f"signal (grammar S2); got {len(directionals)}"
            )
            raise ValueError(msg)
        regime_gates = [s for s in config.signals if s.role == "regime_filter"]

        directional_firings: frozenset[object] = ctx.feature_cache.activation_dates(
            directionals[0].id,
        )

        # Intersect with every regime gate. §3.5 S3 mandates ≥1 regime;
        # without one the intersection is just the directional set (which
        # the existing SignalDensityFilter already covers, so this would
        # be a no-op rather than a behavior change).
        combined = set(directional_firings)
        for gate in regime_gates:
            gate_firings = ctx.feature_cache.activation_dates(gate.id)
            combined.intersection_update(gate_firings)

        n_entries = len(combined)
        min_required = ctx.calibration.predicted_activations.min_entries

        passed = n_entries >= min_required
        if passed:
            denominator = math.log1p(10 * min_required)
            score = min(1.0, math.log1p(n_entries) / denominator) if denominator > 0 else 0.0
        else:
            score = 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "predicted_n_entries": n_entries,
                    "min_entries": min_required,
                    "n_directional_firings": len(directional_firings),
                    "n_regime_gates": len(regime_gates),
                },
            ),
        )


__all__ = ["PredictedActivationsFilter"]
