"""Filter 6: novelty (temporal + structural). DESIGN.md §5.3.5 + T2.7.

Two checks:
1. **Temporal Jaccard** (pre-T2.7): for each prior tested config in
   `ctx.prior_firing_dates`, compute the Jaccard overlap of historical
   directional-signal firing dates. Reject when max overlap exceeds
   `calibration.novelty.max_jaccard_overlap` (default 0.80).
2. **Structural fingerprint** (T2.7 / D043): hash the config's
   `(hypothesis, signal_families, regime_gate_set, exit_set)` tuple. If
   the candidate's fingerprint exactly matches a prior tested candidate's
   fingerprint, reject — Optuna already explores parameter variations
   within a structure; we don't need Forge to redundantly enumerate them.

`cost_tier=6` in the §5.2 battery (post-T1.3 insertion at 5). O(M) priors
with constant work per prior (frozenset intersection + union + hash
membership check).
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from datetime import date

    from crucible_contracts import StrategyConfig

    from forge.prefilters.types import FilterContext


def _jaccard(a: frozenset[date], b: frozenset[date]) -> float:
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def compute_structural_fingerprint(config: StrategyConfig) -> str:
    """T2.7 — 16-hex-char SHA-256 hash of the config's structural skeleton.

    Includes: hypothesis, sorted set of directional/regime/confluence
    signal indicator IDs (NOT thresholds — those are parameters), sorted
    set of exit IDs. Excludes: selector params, sizer params, threshold
    values, delta targets — anything Optuna would tune within a fixed
    structural shape.

    Two configs with the same fingerprint encode the same idea (Forge's
    structural enumeration unit); their parameter differences are
    Optuna's job to optimize, not Forge's to re-enumerate.
    """
    components = {
        "hypothesis": config.hypothesis,
        "directional_indicators": sorted({
            ind
            for sig in config.signals
            if sig.role == "directional"
            for ind in sig.indicators
        }),
        "regime_indicators": sorted({
            ind
            for sig in config.signals
            if sig.role == "regime_filter"
            for ind in sig.indicators
        }),
        "confluence_indicators": sorted({
            ind
            for sig in config.signals
            if sig.role == "confluence"
            for ind in sig.indicators
        }),
        "exit_ids": sorted({e.id for e in config.exits}),
        "dte_bucket": config.dte_bucket,
        "sizer_mode": config.sizer.mode,
    }
    canonical = json.dumps(components, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class NoveltyFilter:
    """§5.3.5 + T2.7 — reject configs duplicating a prior candidate's
    temporal firings OR structural skeleton."""

    name = "novelty"
    cost_tier = 6

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        # T2.7: structural-fingerprint check first (cheaper, exact match).
        fingerprint = compute_structural_fingerprint(config)
        if fingerprint in ctx.prior_structural_fingerprints:
            return FilterResult(
                passed=False,
                score=0.0,
                details=MappingProxyType(
                    {
                        "reject_reason": "structural_fingerprint_match",
                        "structural_fingerprint": fingerprint,
                        "max_overlap": None,
                        "max_overlap_with": None,
                        "n_priors_checked": len(ctx.prior_firing_dates),
                    },
                ),
            )

        # Temporal Jaccard check (existing).
        directional = _directional_signal(config)
        candidate = ctx.feature_cache.activation_dates(directional.id)

        max_overlap = 0.0
        max_overlap_with: str | None = None
        for prior_hash, prior_dates in ctx.prior_firing_dates.items():
            overlap = _jaccard(candidate, prior_dates)
            if overlap > max_overlap:
                max_overlap = overlap
                max_overlap_with = prior_hash

        threshold = ctx.calibration.novelty.max_jaccard_overlap
        passed = max_overlap <= threshold
        # Score: 1.0 = fully novel; 0.0 = identical to a prior.
        score = 1.0 - max_overlap if passed else 0.0

        return FilterResult(
            passed=passed,
            score=score,
            details=MappingProxyType(
                {
                    "max_overlap": max_overlap,
                    "max_overlap_with": max_overlap_with,
                    "n_priors_checked": len(ctx.prior_firing_dates),
                    "max_jaccard_overlap_threshold": threshold,
                    "structural_fingerprint": fingerprint,
                }
            ),
        )


__all__ = ["NoveltyFilter", "compute_structural_fingerprint"]
