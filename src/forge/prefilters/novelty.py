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


# D069 — per-key float bucket precision for the fingerprint. Default is
# 2 decimal places (most params live in a 0-100 range where 2dp = 1%
# granularity). per_trade_risk_pct gets 3dp because its native range is
# 0.005-0.020 — 2dp would collapse to ~4 buckets and erase Phase 4's
# sampling variation. Keys not in this table fall through to default.
_FINGERPRINT_FLOAT_PRECISION_DEFAULT: int = 2
_FINGERPRINT_FLOAT_PRECISION_BY_KEY: dict[str, int] = {
    "per_trade_risk_pct": 3,
}


def _bucket_value(key: str, value: object) -> object:
    """D069: discretize a single param value for fingerprinting.

    Floats round to `_FINGERPRINT_FLOAT_PRECISION_BY_KEY[key]` if present,
    otherwise `_FINGERPRINT_FLOAT_PRECISION_DEFAULT`. Ints, strs, bools,
    and None pass through. Anything else stringifies for stable hashing.
    """
    if isinstance(value, bool):  # bool is an int subclass; check first
        return value
    if isinstance(value, float):
        precision = _FINGERPRINT_FLOAT_PRECISION_BY_KEY.get(
            key, _FINGERPRINT_FLOAT_PRECISION_DEFAULT,
        )
        return round(value, precision)
    if isinstance(value, int) or value is None or isinstance(value, str):
        return value
    return str(value)


def _canonical_params(params: object) -> list[list[object]]:
    """D069: render a params mapping as a sorted, bucketed list-of-pairs.

    Returns `[[key, bucketed_value], ...]` sorted by key so JSON
    serialization is canonical. Non-mapping inputs produce `[]` —
    defensive for SignalSpec / ExitSpec subclasses that might evolve.
    """
    if not isinstance(params, dict):
        return []
    return [
        [k, _bucket_value(k, v)]
        for k, v in sorted(params.items())
    ]


def compute_structural_fingerprint(config: StrategyConfig) -> str:
    """T2.7 + D069 — 16-hex-char SHA-256 hash of the config's structural
    skeleton AND its bucketed numeric params.

    Structural fields: hypothesis, sorted indicator IDs by role, sorted
    exit IDs, dte_bucket, sizer_mode.

    D069 additions: bucketed `selector.delta_target` / `selector.dte_min`
    / `selector.dte_max`, bucketed `sizer.per_trade_risk_pct` /
    `kelly_fraction` / `vol_target_annual`, per-signal bucketed params
    (threshold / op / D068 pairs keys), per-exit bucketed params.

    The bucketing (typically 2-3 decimal places per key) collapses near-
    identical configs while distinguishing materially different ones. Pre-
    D069 the fingerprint was param-blind — two `mean_reversion` configs
    with `threshold=20` vs `threshold=30` produced the same fingerprint,
    so a batch with 1,000 mean_reversion candidates collapsed to ~6
    fingerprints and the novelty filter killed 99% as intra-batch
    duplicates. That was the structural cause of the iter 33-36 100%
    regime_arbitrage monoculture documented in
    `FORGE_GENERATOR_IMPROVEMENT_PLAN.md`.

    Backwards compatibility: existing `submissions` rows are re-hashed
    on every `_load_prior_structural_fingerprints` call (they're never
    persisted), so the new algorithm derives a richer historical
    fingerprint set from the same DB without migration.
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
        # D069 — bucketed numeric params
        "signal_params": [
            [sig.id, _canonical_params(sig.params)]
            for sig in sorted(config.signals, key=lambda s: s.id)
        ],
        "exit_params": [
            [e.id, _canonical_params(e.params)]
            for e in sorted(config.exits, key=lambda e: e.id)
        ],
        "selector": [
            ["delta_target", _bucket_value("delta_target", config.selector.delta_target)],
            ["dte_min", config.selector.dte_min],
            ["dte_max", config.selector.dte_max],
        ],
        "sizer_params": [
            [
                "per_trade_risk_pct",
                _bucket_value("per_trade_risk_pct", config.sizer.per_trade_risk_pct),
            ],
            ["kelly_fraction", _bucket_value("kelly_fraction", config.sizer.kelly_fraction)],
            [
                "vol_target_annual",
                _bucket_value("vol_target_annual", config.sizer.vol_target_annual),
            ],
        ],
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
