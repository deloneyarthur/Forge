"""Filter 7: signal correlation. T2.6 (PROMPT_5_FORGE_V1_1_REVISED).

Computes pairwise Jaccard overlap of activation dates across the config's
signals; rejects when any pair exceeds
`calibration.signal_correlation.max_jaccard_overlap` (default 0.85).

**The failure mode this catches**: §3.5 C1 blocks two indicators from
the same family (mean_reversion ∩ mean_reversion). But cross-family
indicators can still be empirically redundant — `rsi_14` (mean_reversion
family) and `stochastic_k` (momentum family) compute different things by
the registry's family classification but fire on near-identical days.
This filter is the empirical complement to C1's structural rule.

Jaccard is used (not Pearson) for two reasons:
  1. Activation_dates is naturally a frozenset; Jaccard is the natural
     set-similarity metric.
  2. Matches the existing `NoveltyFilter` semantic (which computes
     Jaccard across configs); operators see one consistent metric.

Cost: O(N²) over N signals per config, each pair O(|A| + |B|) for
the set intersection/union. Typical N=2-4 signals so per-config cost
is small; placed at cost_tier=7 because it must follow Novelty (6) which
already loaded the directional signal's activations into cache.
"""

from __future__ import annotations

from itertools import combinations
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters._similarity import jaccard
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from datetime import date

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


class SignalCorrelationFilter:
    """T2.6 — reject configs with empirically-redundant signals."""

    name = "signal_correlation"
    cost_tier = 7

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        signals = config.signals
        if len(signals) < 2:
            # Nothing to correlate; trivially passes.
            return FilterResult(
                passed=True,
                score=1.0,
                details=MappingProxyType({"n_signals": len(signals), "max_jaccard": 0.0}),
            )

        # Cache activations once per signal — avoids re-fetching for each
        # pair. The feature cache deduplicates anyway, but the dict
        # avoids redundant lookups.
        activations: dict[str, frozenset[date]] = {
            sig.id: ctx.feature_cache.activation_dates(sig.id) for sig in signals
        }

        max_overlap = 0.0
        max_pair: tuple[str, str] | None = None
        for a, b in combinations(signals, 2):
            j = jaccard(activations[a.id], activations[b.id])
            if j > max_overlap:
                max_overlap = j
                max_pair = (a.id, b.id)

        threshold = ctx.calibration.signal_correlation.max_jaccard_overlap
        passed = max_overlap < threshold
        score = 1.0 - max_overlap if passed else 0.0

        details: dict[str, object] = {
            "n_signals": len(signals),
            "max_jaccard": max_overlap,
            "threshold": threshold,
        }
        if max_pair is not None:
            details["max_pair"] = list(max_pair)

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(details),
        )


__all__ = ["SignalCorrelationFilter"]
