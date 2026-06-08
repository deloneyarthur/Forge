"""Unit tests for `forge.prefilters.expected_trades` (§5.3.4).

Filter 4 of the §5.2 battery (cost_tier=4, O(N) feature rows). Combines
the directional signal's activation count with the DTE bucket's typical
hold time to estimate trades over the cached window; rejects below
`calibration.expected_trade_count.min_trades` (default 50).
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from types import MappingProxyType

import pytest

from forge.feedback.trade_rate_priors import BucketKey, BucketStats
from forge.prefilters.calibration import load_calibration
from forge.prefilters.expected_trades import (
    _HOLD_DAYS_BY_BUCKET,
    _MAX_CONCURRENT_POSITIONS,
    ExpectedTradesFilter,
)
from forge.prefilters.feature_cache import REGIMES
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


class _FixedActivationsCache:
    data_history_days = 1008

    def __init__(self, n: int) -> None:
        self._activations = frozenset(
            date.fromordinal(date(2022, 1, 1).toordinal() + i) for i in range(n)
        )

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return self._activations

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.0 for d in dates}

    def regime_label(self, d: date) -> str:
        del d
        return REGIMES[0]


def _ctx(
    n_activations: int,
    *,
    trade_rate_priors: dict[BucketKey, BucketStats] | None = None,
) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=_FixedActivationsCache(n_activations),  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
        trade_rate_priors=MappingProxyType(trade_rate_priors or {}),
    )


def test_satisfies_filter_protocol() -> None:
    f: Filter = ExpectedTradesFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = ExpectedTradesFilter()
    assert f.name == "expected_trades"
    assert f.cost_tier == 4


def test_passes_with_dense_short_bucket() -> None:
    """swing_short, 100 activations -> easily clears the 50-trade floor."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=100))
    assert result.passed


def test_rejects_when_activations_below_min_trades() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=40))
    assert not result.passed


def test_swing_long_high_density_capped_by_concurrency() -> None:
    """A swing_long config (hold ~75d) can hold at most ~MAX_SLOTS *
    (history/hold) concurrent positions; an extremely dense signal is
    capped by that ceiling even if activations are far above min_trades."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_long")
    # 1000 activations would naively imply 1000 trades; concurrency caps it.
    result = f.apply(cfg, _ctx(n_activations=1000))
    capacity = _MAX_CONCURRENT_POSITIONS * (1008 / _HOLD_DAYS_BY_BUCKET["swing_long"])
    assert result.details["estimated_trades"] <= int(capacity) + 1


def test_swing_short_high_density_not_capped() -> None:
    """swing_short hold ~15d allows many concurrent / sequential trades;
    typical activation counts are well under capacity."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=200))
    # min(200, 5 * 1008/15) = 200
    assert result.details["estimated_trades"] == 200


def test_score_monotone_in_estimated_trades() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    a = f.apply(cfg, _ctx(60)).score
    b = f.apply(cfg, _ctx(150)).score
    assert a < b


def test_score_clamped_to_unit_interval() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(10_000))
    assert 0.0 <= result.score <= 1.0


def test_subthreshold_score_is_zero() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(20))
    assert result.score == 0.0


def test_details_record_all_relevant_numbers() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_mid")
    result = f.apply(cfg, _ctx(80))
    assert result.details["n_activations"] == 80
    assert result.details["min_trades"] == 50
    assert result.details["dte_bucket"] == "swing_mid"
    assert "hold_days" in result.details
    assert "estimated_trades" in result.details


def test_pure() -> None:
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config()
    ctx = _ctx(100)
    prior = ctx.prior_config_hashes
    f.apply(cfg, ctx)
    assert ctx.prior_config_hashes is prior


@pytest.mark.parametrize("bucket", ["swing_short", "swing_mid", "swing_long"])
def test_each_bucket_has_a_hold_days_entry(bucket: str) -> None:
    assert bucket in _HOLD_DAYS_BY_BUCKET
    assert _HOLD_DAYS_BY_BUCKET[bucket] > 0


def test_hold_days_are_increasing_across_buckets() -> None:
    """swing_short < swing_mid < swing_long; sanity-check the table."""
    s = _HOLD_DAYS_BY_BUCKET["swing_short"]
    m = _HOLD_DAYS_BY_BUCKET["swing_mid"]
    long_h = _HOLD_DAYS_BY_BUCKET["swing_long"]
    assert s < m < long_h


# ---------------------------------------------------------------------------
# D076 / Q16 — empirical-prior path
# ---------------------------------------------------------------------------


# rsi_2 lives in `mean_reversion` family per `minimal_registry_snapshot`.
_MR_BUCKET: BucketKey = ("mean_reversion", "swing_short", "mean_reversion")


def _stats(*, n_total: int, n_pass: int, posterior: float, n_zero: int = 0) -> BucketStats:
    return BucketStats(
        n_total=n_total,
        n_pass=n_pass,
        n_zero_trade=n_zero,
        posterior_p_pass=posterior,
    )


def test_empirical_prior_path_rejects_low_posterior() -> None:
    """Bucket with 50 gated samples + posterior 0.02 < default 0.10 → reject."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    priors = {_MR_BUCKET: _stats(n_total=50, n_pass=1, posterior=0.02, n_zero=40)}
    result = f.apply(cfg, _ctx(n_activations=100, trade_rate_priors=priors))
    assert not result.passed
    assert result.details["mode"] == "empirical_prior"
    assert result.score == 0.0


def test_empirical_prior_path_passes_high_posterior() -> None:
    """Bucket with 50 gated samples + posterior 0.40 ≥ 0.10 → pass."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    priors = {_MR_BUCKET: _stats(n_total=50, n_pass=20, posterior=0.40)}
    result = f.apply(cfg, _ctx(n_activations=100, trade_rate_priors=priors))
    assert result.passed
    assert result.details["mode"] == "empirical_prior"
    assert result.score == pytest.approx(0.40)


def test_below_sample_floor_falls_back_to_activations() -> None:
    """A bucket with `n_total < min_bucket_samples` (default 20) is
    ignored; the activations heuristic runs even with a low posterior."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    # Posterior says reject, but only 5 samples — below the floor.
    priors = {_MR_BUCKET: _stats(n_total=5, n_pass=0, posterior=0.01, n_zero=5)}
    # 100 activations clears the activations floor → pass via fallback.
    result = f.apply(cfg, _ctx(n_activations=100, trade_rate_priors=priors))
    assert result.passed
    assert result.details["mode"] == "activations_heuristic"
    assert result.details["fallback_reason"] == "below_sample_floor"


def test_no_bucket_data_falls_back_to_activations() -> None:
    """Config's bucket isn't in trade_rate_priors → activations heuristic."""
    f = ExpectedTradesFilter()
    cfg = minimal_strategy_config(dte_bucket="swing_short")
    result = f.apply(cfg, _ctx(n_activations=100, trade_rate_priors={}))
    assert result.passed
    assert result.details["mode"] == "activations_heuristic"
    assert result.details["fallback_reason"] == "no_bucket_data"


def test_relative_value_pairs_bucket_q16_smoke() -> None:
    """The Q16 motivating example: relative_value x swing_short x pairs
    with 370/375 zero-trade. Smoothed posterior is ~0.003 → rejected
    even with strong activation density."""
    f = ExpectedTradesFilter()
    # pairs_zscore family is `pairs` per the registry fixture.
    from crucible_contracts import CombinerSpec, SelectorSpec, SignalSpec, SizerSpec

    from tests.fixtures.strategy_configs import _MANDATORY_EXITS

    cfg = minimal_strategy_config(
        hypothesis="relative_value",
        dte_bucket="swing_short",
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("pairs_zscore",),
                params={"threshold": -1.26, "op": "<"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
        combiner=CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )

    # 596/616 zero-trade ≈ posterior (1+20) / (1+10+616) ≈ 0.033 < 0.10
    pairs_bucket: BucketKey = ("relative_value", "swing_short", "pairs")
    priors = {pairs_bucket: _stats(n_total=616, n_pass=20, posterior=21 / 627, n_zero=596)}
    result = f.apply(cfg, _ctx(n_activations=1000, trade_rate_priors=priors))
    assert not result.passed
    assert result.details["mode"] == "empirical_prior"
    assert result.details["bucket_n_zero_trade"] == 596


# ---------------------------------------------------------------------------
# H1 (v12 / D109) — cross_sectional_rank structural estimate (the load-bearing fix)
# ---------------------------------------------------------------------------


def _rank_combiner(rank_k: int = 5, rebalance: str = "monthly", direction: str = "long_only"):
    from crucible_contracts import CombinerSpec

    return CombinerSpec(
        type="cross_sectional_rank",
        rank_k=rank_k,
        rebalance_frequency=rebalance,  # type: ignore[arg-type]
        direction_mode=direction,  # type: ignore[arg-type]
    )


def test_rank_config_passes_despite_poisoned_single_name_prior() -> None:
    """THE load-bearing H1 correctness point. A cross_sectional_rank config trades
    a DETERMINISTIC ~rank_k*rebalances (≫100) by construction, so it must NOT be
    killed on the stale SINGLE-NAME empirical prior of its (hypothesis, bucket,
    family) bucket. The identical confluence config IS killed by that prior — which
    proves the structural branch is exactly what saves the rank config (and that
    defeating the single-name trade floor is the whole point of the rank combiner)."""
    f = ExpectedTradesFilter()
    # A prior that kills the single-name (confluence) mean_reversion config.
    priors = {_MR_BUCKET: _stats(n_total=50, n_pass=1, posterior=0.02, n_zero=40)}

    confluence = minimal_strategy_config(dte_bucket="swing_short")
    killed = f.apply(confluence, _ctx(n_activations=0, trade_rate_priors=priors))
    assert not killed.passed
    assert killed.details["mode"] == "empirical_prior"

    rank = minimal_strategy_config(
        dte_bucket="swing_short", combiner=_rank_combiner(), underlying=None
    )
    result = f.apply(rank, _ctx(n_activations=0, trade_rate_priors=priors))
    assert result.passed
    assert result.details["mode"] == "structural_rank"
    assert result.details["estimated_trades"] >= result.details["min_trades"]


def test_rank_structural_estimate_scales_with_k_and_direction() -> None:
    """expected ~= directions x rank_k x rebalances; long_short doubles long_only,
    and 2*rank_k doubles again. The estimate is honest (bounded by the window),
    not a blanket pass."""
    f = ExpectedTradesFilter()
    ctx = _ctx(n_activations=0)

    base = f.apply(
        minimal_strategy_config(
            combiner=_rank_combiner(rank_k=5, direction="long_only"), underlying=None
        ),
        ctx,
    )
    long_short = f.apply(
        minimal_strategy_config(
            combiner=_rank_combiner(rank_k=5, direction="long_short"), underlying=None
        ),
        ctx,
    )
    double_k = f.apply(
        minimal_strategy_config(
            combiner=_rank_combiner(rank_k=10, direction="long_only"), underlying=None
        ),
        ctx,
    )
    assert base.details["mode"] == "structural_rank"
    assert long_short.details["estimated_trades"] == 2 * base.details["estimated_trades"]
    assert double_k.details["estimated_trades"] == 2 * base.details["estimated_trades"]


def test_rank_weekly_rebalances_more_than_monthly() -> None:
    """Denser rebalancing → more rebalances → more trades (deterministic)."""
    f = ExpectedTradesFilter()
    ctx = _ctx(n_activations=0)
    weekly = f.apply(
        minimal_strategy_config(combiner=_rank_combiner(rebalance="weekly"), underlying=None), ctx
    )
    monthly = f.apply(
        minimal_strategy_config(combiner=_rank_combiner(rebalance="monthly"), underlying=None), ctx
    )
    assert weekly.details["estimated_trades"] > monthly.details["estimated_trades"]


def test_unknown_directional_indicator_falls_back_to_activations() -> None:
    """Directional points at an indicator not in the registry → no bucket
    key → activations heuristic, but `bucket_key` in details is None."""
    f = ExpectedTradesFilter()
    from crucible_contracts import CombinerSpec, SelectorSpec, SignalSpec, SizerSpec

    from tests.fixtures.strategy_configs import _MANDATORY_EXITS

    cfg = minimal_strategy_config(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("nonexistent_indicator",),
                params={"threshold": 0.5, "op": "<"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
        combiner=CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )
    result = f.apply(cfg, _ctx(n_activations=100))
    assert result.details["mode"] == "activations_heuristic"
    assert result.details["bucket_key"] is None
