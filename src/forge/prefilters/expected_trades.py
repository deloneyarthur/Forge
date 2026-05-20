"""Filter 4: expected trade count. DESIGN.md §5.3.4.

Two-mode filter. When the gated-cohort prior for a config's
`(hypothesis, dte_bucket, directional_family)` bucket has reached
`min_bucket_samples` observations, reject when the Beta-smoothed
posterior `P(n_trades >= min_trades)` is below `min_pass_probability`
(D076 / Q16 — empirical-prior mode). Otherwise fall back to the
legacy activations heuristic — directional signal's activation count
combined with the DTE bucket's typical hold time vs `min_trades`.

§5.3.4 motivation: Crucible requires 100 OOS trades for promotion, so
Forge wants 50+ trades of headroom in the cached window before paying
the cost of a full backtest. The original activations heuristic was
the v1 implementation; Q16 (2026-05-20) showed it caught only ~3% of
configs while 77% of survivors produced 0 trades — the empirical-prior
mode is the structural fix and cold-start configs still use the
heuristic so unexplored buckets aren't strangled.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.prefilters.signal_density import _directional_signal
from forge.prefilters.types import FilterResult

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, SignalSpec, StrategyConfig

    from forge.feedback.trade_rate_priors import BucketKey
    from forge.prefilters.types import FilterContext

# Approximate hold time per DTE bucket — midpoint of §3.5 P2 entry-DTE
# windows. Used to convert activation count to expected trade count
# under a concurrency cap.
_HOLD_DAYS_BY_BUCKET: dict[str, int] = {
    "swing_short": 15,
    "swing_mid": 35,
    "swing_long": 75,
}

# How many concurrent positions a single strategy can hold. The grammar
# doesn't model this directly; 5 is a sensible default that lets
# swing_long strategies clear the trade-count floor without forcing
# every strategy into the same shape.
_MAX_CONCURRENT_POSITIONS = 5


def _bucket_key_for_config(
    config: StrategyConfig,
    registry: RegistrySnapshot,
    directional: SignalSpec,
) -> BucketKey | None:
    """Resolve the `(hypothesis, dte_bucket, directional_family)` bucket.

    Returns None when the directional signal points at an indicator the
    registry doesn't know about (the bucket can't be keyed without a
    family). The empirical-prior path treats None like "no stats" and
    falls back to the activations heuristic.
    """
    if not directional.indicators:
        return None
    indicator_id = directional.indicators[0]
    for ind in registry.indicators:
        if ind.id == indicator_id:
            return (config.hypothesis, config.dte_bucket, ind.family)
    return None


def _apply_activations_heuristic(
    config: StrategyConfig,
    ctx: FilterContext,
    bucket_key: BucketKey | None,
    *,
    fallback_reason: str,
) -> FilterResult:
    """Legacy activations-vs-min_trades path. Pre-D076 behaviour.

    Used when the config's bucket has no posterior yet (cold-start) or
    when the directional indicator isn't in the registry. `bucket_key`
    + `fallback_reason` are recorded in details so audit queries can
    trace which configs landed in this branch.
    """
    directional = _directional_signal(config)
    n_activations = len(ctx.feature_cache.activation_dates(directional.id))

    hold = _HOLD_DAYS_BY_BUCKET[config.dte_bucket]
    capacity = _MAX_CONCURRENT_POSITIONS * (ctx.registry.data_history_days / hold)
    estimated = min(n_activations, int(capacity))

    min_required = ctx.calibration.expected_trade_count.min_trades
    passed = estimated >= min_required
    if passed:
        denominator = math.log1p(10 * min_required)
        score = min(1.0, math.log1p(estimated) / denominator) if denominator > 0 else 0.0
    else:
        score = 0.0

    return FilterResult(
        passed=passed,
        score=score,
        details=MappingProxyType(
            {
                "mode": "activations_heuristic",
                "fallback_reason": fallback_reason,
                "bucket_key": list(bucket_key) if bucket_key is not None else None,
                "n_activations": n_activations,
                "estimated_trades": estimated,
                "min_trades": min_required,
                "dte_bucket": config.dte_bucket,
                "hold_days": hold,
            },
        ),
    )


class ExpectedTradesFilter:
    """§5.3.4 — reject configs unlikely to produce enough real trades."""

    name = "expected_trades"
    cost_tier = 4

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult:
        directional = _directional_signal(config)
        bucket_key = _bucket_key_for_config(config, ctx.registry, directional)
        cal = ctx.calibration.expected_trade_count

        stats = ctx.trade_rate_priors.get(bucket_key) if bucket_key else None
        if stats is None:
            return _apply_activations_heuristic(
                config,
                ctx,
                bucket_key,
                fallback_reason="no_bucket_data",
            )
        if stats.n_total < cal.min_bucket_samples:
            return _apply_activations_heuristic(
                config,
                ctx,
                bucket_key,
                fallback_reason="below_sample_floor",
            )

        # `stats is not None` implies the earlier `.get(bucket_key)` was
        # called with a truthy key — narrow for mypy.
        assert bucket_key is not None
        passed = stats.posterior_p_pass >= cal.min_pass_probability
        score = stats.posterior_p_pass if passed else 0.0
        return FilterResult(
            passed=passed,
            score=min(1.0, max(0.0, score)),
            details=MappingProxyType(
                {
                    "mode": "empirical_prior",
                    "bucket_key": list(bucket_key),
                    "bucket_n_total": stats.n_total,
                    "bucket_n_pass": stats.n_pass,
                    "bucket_n_zero_trade": stats.n_zero_trade,
                    "posterior_p_pass": stats.posterior_p_pass,
                    "min_pass_probability": cal.min_pass_probability,
                    "min_bucket_samples": cal.min_bucket_samples,
                    "min_trades": cal.min_trades,
                },
            ),
        )


__all__ = ["ExpectedTradesFilter"]
