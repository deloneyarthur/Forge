"""Unit tests for `forge.prefilters.novelty` (§5.3.5).

Filter 5 of the §5.2 battery (cost_tier=5, O(M) prior configs). Jaccard
overlap between this config's directional firing dates and each prior
config's firing dates; rejects when max overlap exceeds
`calibration.novelty.max_jaccard_overlap` (default 0.80).

This is the filter that prevents Forge from flooding Crucible with minor
variations of already-tested ideas.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import pytest

from forge.prefilters.calibration import load_calibration
from forge.prefilters.feature_cache import REGIMES
from forge.prefilters.novelty import NoveltyFilter
from forge.prefilters.types import Filter, FilterContext
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


class _FixedActivationsCache:
    data_history_days = 1008

    def __init__(self, activations: frozenset[date]) -> None:
        self._activations = activations

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        del signal_id
        return self._activations

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        return {d: 0.0 for d in dates}

    def regime_label(self, d: date) -> str:
        del d
        return REGIMES[0]


def _ctx(
    activations: frozenset[date],
    prior_firing_dates: Mapping[str, frozenset[date]] | None = None,
) -> FilterContext:
    return FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=_FixedActivationsCache(activations),  # type: ignore[arg-type]
        prior_config_hashes=frozenset(prior_firing_dates or {}),
        prior_firing_dates=prior_firing_dates or {},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )


def _days(n: int, *, offset: int = 0) -> frozenset[date]:
    return frozenset(date.fromordinal(date(2022, 1, 1).toordinal() + offset + i) for i in range(n))


def test_satisfies_filter_protocol() -> None:
    f: Filter = NoveltyFilter()
    assert isinstance(f, Filter)


def test_name_and_cost_tier() -> None:
    f = NoveltyFilter()
    assert f.name == "novelty"
    # T1.3 (PROMPT_5_FORGE_V1_1_REVISED) inserted PredictedActivationsFilter at 5;
    # novelty bumped 5 -> 6.
    assert f.cost_tier == 6


def test_passes_with_no_priors() -> None:
    """First batch: nothing seen, every config is fully novel."""
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(_days(100)))
    assert result.passed
    assert result.score == 1.0


def test_passes_when_overlap_under_threshold() -> None:
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    # Candidate fires days 0..99; prior fires days 50..149.
    # Intersection = 50 (50..99); union = 150 (0..149). Jaccard = 50/150 ≈ 0.33.
    result = f.apply(
        cfg,
        _ctx(_days(100), prior_firing_dates={"prior_a": _days(100, offset=50)}),
    )
    assert result.passed
    # 1 - 0.333... ≈ 0.667
    assert 0.6 <= result.score <= 0.75


def test_rejects_when_overlap_above_threshold() -> None:
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    # Candidate fires days 0..99; prior fires days 0..89 (90 of 100 overlap).
    # Intersection = 90; union = 100. Jaccard = 0.90.
    result = f.apply(
        cfg,
        _ctx(_days(100), prior_firing_dates={"prior_a": _days(90)}),
    )
    assert not result.passed


def test_takes_max_overlap_across_priors() -> None:
    """Even if most priors are low-overlap, a single high-overlap
    prior rejects the config."""
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    priors = {
        "low_overlap": _days(100, offset=500),  # entirely disjoint
        "high_overlap": _days(95),  # 95/100 overlap with candidate's 0..99
    }
    result = f.apply(cfg, _ctx(_days(100), prior_firing_dates=priors))
    assert not result.passed
    # max_overlap reported should be from "high_overlap"
    assert result.details["max_overlap_with"] == "high_overlap"


def test_score_is_one_minus_max_overlap() -> None:
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    # 50/100 union via half-overlapping window: intersection=50, union=150
    prior = _days(100, offset=50)
    result = f.apply(cfg, _ctx(_days(100), prior_firing_dates={"prior_a": prior}))
    jaccard = 50 / 150
    assert abs(result.score - (1.0 - jaccard)) < 1e-9


def test_passes_when_candidate_has_no_activations() -> None:
    """An empty activation set has nothing to overlap. Treat as fully
    novel; signal_density would have already rejected it."""
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(frozenset(), prior_firing_dates={"prior_a": _days(100)}))
    assert result.passed
    assert result.score == 1.0


def test_passes_when_prior_has_no_activations() -> None:
    """A prior with no activations contributes 0 overlap regardless."""
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(cfg, _ctx(_days(100), prior_firing_dates={"prior_a": frozenset()}))
    assert result.passed
    assert result.score == 1.0


def test_identical_activations_produce_jaccard_one() -> None:
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    same = _days(100)
    result = f.apply(cfg, _ctx(same, prior_firing_dates={"prior_a": same}))
    assert not result.passed
    assert result.score == 0.0
    assert result.details["max_overlap"] == 1.0


def test_details_record_max_overlap_and_match_id() -> None:
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    result = f.apply(
        cfg,
        _ctx(_days(100), prior_firing_dates={"prior_a": _days(50, offset=25)}),
    )
    assert "max_overlap" in result.details
    assert "max_overlap_with" in result.details
    assert "n_priors_checked" in result.details


def test_pure() -> None:
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    priors = {"p1": _days(100, offset=10), "p2": _days(50, offset=200)}
    ctx = _ctx(_days(100), prior_firing_dates=priors)
    prior_keys = frozenset(ctx.prior_firing_dates)
    f.apply(cfg, ctx)
    assert frozenset(ctx.prior_firing_dates) == prior_keys


@pytest.mark.parametrize("n_priors", [0, 1, 10, 100])
def test_scales_with_prior_count(n_priors: int) -> None:
    """O(M) — completes in reasonable time for typical Forge DB sizes."""
    f = NoveltyFilter()
    cfg = minimal_strategy_config()
    priors = {f"p{i:04d}": _days(100, offset=i * 20) for i in range(n_priors)}
    result = f.apply(cfg, _ctx(_days(100), prior_firing_dates=priors))
    # n_priors_checked matches how many we passed in
    assert result.details["n_priors_checked"] == n_priors


# ---------------------------------------------------------------------------
# T2.7 / D043 — structural fingerprint check
# ---------------------------------------------------------------------------


def _make_param_cfg(
    threshold: float,
    *,
    delta_target: float = 0.45,
    risk_pct: float = 0.01,
):  # type: ignore[no-untyped-def]  # ruff-friendly; return-type is StrategyConfig
    from crucible_contracts import (
        CombinerSpec,
        ExitSpec,
        SelectorSpec,
        SignalSpec,
        SizerSpec,
        StrategyConfig,
    )

    return StrategyConfig(
        name=f"cfg_{threshold}_{delta_target}_{risk_pct}",
        hypothesis="mean_reversion",
        dte_bucket="swing_short",
        underlying="SPY",
        tier=1,
        signals=(
            SignalSpec(id="sig_directional", type="threshold", role="directional",
                       indicators=("rsi_2",), params={"threshold": threshold, "op": "<"}),
            SignalSpec(id="sig_regime", type="threshold", role="regime_filter",
                       indicators=("iv_rank",), params={"threshold": 50.0, "op": "<"}),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=delta_target, delta_tolerance=0.05, dte_min=14, dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct", per_trade_risk_pct=risk_pct),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
        ),
    )


def test_d069_structural_fingerprint_distinguishes_material_threshold_change() -> None:
    """D069 (replaces pre-D069 T2.7 param-blind behavior): same structural
    skeleton with materially different directional thresholds must now
    produce DIFFERENT fingerprints. Pre-D069 they collapsed to the same
    fingerprint, causing the iter 33-36 100% regime_arbitrage monoculture
    (constrained hypotheses sampled ~1000 candidates each but only
    differed in params, so the novelty filter killed 99% as intra-batch
    duplicates)."""
    from forge.prefilters.novelty import compute_structural_fingerprint

    fp_a = compute_structural_fingerprint(_make_param_cfg(20.0))
    fp_b = compute_structural_fingerprint(_make_param_cfg(30.0))
    assert fp_a != fp_b
    assert len(fp_a) == 16  # 16-hex-char short hash unchanged


def test_d069_structural_fingerprint_collapses_within_bucket() -> None:
    """D069: param differences SMALLER than the bucket precision still
    collapse to the same fingerprint. With 2dp default precision,
    threshold=30.001 and threshold=30.002 are the same bucket; with the
    delta_target rounding at 2dp, 0.451 and 0.452 collapse too.

    Catches over-fine bucketing that would defeat the dedup's purpose."""
    from forge.prefilters.novelty import compute_structural_fingerprint

    # Both round to 30.00 at 2dp.
    fp_a = compute_structural_fingerprint(_make_param_cfg(30.001))
    fp_b = compute_structural_fingerprint(_make_param_cfg(30.002))
    assert fp_a == fp_b

    # Both round to 0.45 at 2dp; same threshold.
    fp_c = compute_structural_fingerprint(_make_param_cfg(30.0, delta_target=0.451))
    fp_d = compute_structural_fingerprint(_make_param_cfg(30.0, delta_target=0.452))
    assert fp_c == fp_d


def test_d069_structural_fingerprint_distinguishes_delta_target() -> None:
    """D069: same skeleton + threshold, different `delta_target` →
    different fingerprints (each picks a different option contract on
    the chain). Was previously elided as 'an Optuna knob' in the pre-
    D069 fingerprint."""
    from forge.prefilters.novelty import compute_structural_fingerprint

    fp_low = compute_structural_fingerprint(_make_param_cfg(30.0, delta_target=0.30))
    fp_high = compute_structural_fingerprint(_make_param_cfg(30.0, delta_target=0.55))
    assert fp_low != fp_high


def test_d069_structural_fingerprint_distinguishes_risk_pct() -> None:
    """D069: `per_trade_risk_pct` uses 3dp precision since its native
    range is 0.005-0.020 (2dp would collapse to only 4 buckets). A
    factor-of-2 risk difference must produce different fingerprints."""
    from forge.prefilters.novelty import compute_structural_fingerprint

    fp_safe = compute_structural_fingerprint(_make_param_cfg(30.0, risk_pct=0.005))
    fp_aggro = compute_structural_fingerprint(_make_param_cfg(30.0, risk_pct=0.020))
    assert fp_safe != fp_aggro


def test_d069_structural_fingerprint_distinguishes_d068_pairs_params() -> None:
    """D069: D068's `signals[0].params.get("zscore_entry"|"halflife_min"|...)`
    keys must enter the fingerprint so the sampler's pairs-template
    variation isn't deduped away. Without this, every relative_value
    config with the same (directional, regime) pair would re-collapse
    to a single fingerprint despite the D068 widening."""
    from crucible_contracts import (
        CombinerSpec,
        ExitSpec,
        SelectorSpec,
        SignalSpec,
        SizerSpec,
        StrategyConfig,
    )

    from forge.prefilters.novelty import compute_structural_fingerprint

    def _make_rv(zscore_entry: float, halflife_min: int) -> StrategyConfig:
        return StrategyConfig(
            name=f"rv_{zscore_entry}_{halflife_min}",
            hypothesis="relative_value",
            dte_bucket="swing_mid",
            underlying=None,  # pairs picks its own
            tier=2,
            signals=(
                SignalSpec(
                    id="sig_directional", type="threshold", role="directional",
                    indicators=("pairs_zscore",),
                    params={
                        "threshold": -1.2, "op": "<",
                        "lookback": 252, "pvalue_max": 0.10,
                        "zscore_entry": zscore_entry,
                        "halflife_min": halflife_min, "halflife_max": 30,
                    },
                ),
                SignalSpec(
                    id="sig_regime", type="threshold", role="regime_filter",
                    indicators=("realized_vol",), params={"threshold": 0.15, "op": "<"},
                ),
            ),
            combiner=CombinerSpec(),
            selector=SelectorSpec(
                delta_target=0.40, delta_tolerance=0.05, dte_min=30, dte_max=45,
            ),
            sizer=SizerSpec(mode="fixed_risk_pct", per_trade_risk_pct=0.01),
            exits=(
                ExitSpec(id="expiry_exit"),
                ExitSpec(id="theta_cliff_exit"),
                ExitSpec(id="earnings_exit"),
                ExitSpec(id="liquidity_exit"),
                ExitSpec(id="convergence_exit"),
            ),
        )

    fp_loose = compute_structural_fingerprint(_make_rv(1.0, 3))
    fp_strict = compute_structural_fingerprint(_make_rv(2.0, 8))
    assert fp_loose != fp_strict


def test_d069_structural_fingerprint_is_deterministic() -> None:
    """Same config built twice → same fingerprint. Required for
    hard rule #6 and for the prior_structural_fingerprints lookup to
    work across iterations."""
    from forge.prefilters.novelty import compute_structural_fingerprint

    cfg = _make_param_cfg(25.0, delta_target=0.40, risk_pct=0.012)
    assert compute_structural_fingerprint(cfg) == compute_structural_fingerprint(cfg)


def test_t27_structural_fingerprint_distinguishes_indicator_swap() -> None:
    """Different directional indicator -> different fingerprint."""
    from crucible_contracts import (
        CombinerSpec,
        ExitSpec,
        SelectorSpec,
        SignalSpec,
        SizerSpec,
        StrategyConfig,
    )

    from forge.prefilters.novelty import compute_structural_fingerprint

    def _make_cfg(directional_id: str) -> StrategyConfig:
        return StrategyConfig(
            name="x",
            hypothesis="mean_reversion",
            dte_bucket="swing_short",
            underlying="SPY",
            tier=1,
            signals=(
                SignalSpec(id="sig_directional", type="threshold", role="directional",
                           indicators=(directional_id,), params={"threshold": 30.0}),
                SignalSpec(id="sig_regime", type="threshold", role="regime_filter",
                           indicators=("iv_rank",), params={"threshold": 50.0}),
            ),
            combiner=CombinerSpec(),
            selector=SelectorSpec(delta_target=0.45, delta_tolerance=0.05, dte_min=14, dte_max=21),
            sizer=SizerSpec(mode="fixed_risk_pct"),
            exits=(
                ExitSpec(id="expiry_exit"),
                ExitSpec(id="theta_cliff_exit"),
                ExitSpec(id="earnings_exit"),
                ExitSpec(id="liquidity_exit"),
            ),
        )

    fp_rsi2 = compute_structural_fingerprint(_make_cfg("rsi_2"))
    fp_rsi14 = compute_structural_fingerprint(_make_cfg("rsi_14"))
    assert fp_rsi2 != fp_rsi14


def test_t27_novelty_rejects_matching_structural_fingerprint() -> None:
    """T2.7 invariant: candidate whose fingerprint matches a prior is rejected
    even when its temporal Jaccard is zero (no temporal overlap)."""
    from crucible_contracts import (
        CombinerSpec,
        ExitSpec,
        SelectorSpec,
        SignalSpec,
        SizerSpec,
        StrategyConfig,
    )

    from forge.prefilters.novelty import NoveltyFilter, compute_structural_fingerprint

    cfg = StrategyConfig(
        name="x",
        hypothesis="mean_reversion",
        dte_bucket="swing_short",
        underlying="SPY",
        tier=1,
        signals=(
            SignalSpec(id="sig_directional", type="threshold", role="directional",
                       indicators=("rsi_2",), params={"threshold": 30.0}),
            SignalSpec(id="sig_regime", type="threshold", role="regime_filter",
                       indicators=("iv_rank",), params={"threshold": 50.0}),
        ),
        combiner=CombinerSpec(),
        selector=SelectorSpec(delta_target=0.45, delta_tolerance=0.05, dte_min=14, dte_max=21),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=(
            ExitSpec(id="expiry_exit"),
            ExitSpec(id="theta_cliff_exit"),
            ExitSpec(id="earnings_exit"),
            ExitSpec(id="liquidity_exit"),
        ),
    )
    fp = compute_structural_fingerprint(cfg)
    ctx = FilterContext(
        registry=minimal_registry_snapshot(),
        feature_cache=_FixedActivationsCache(_days(30)),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},  # no temporal overlap to find
        prior_structural_fingerprints=frozenset({fp}),  # but fingerprint matches!
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=lambda name: random.Random(hash(name) & 0xFFFFFFFF),
    )
    f = NoveltyFilter()
    result = f.apply(cfg, ctx)
    assert result.passed is False
    assert result.details["reject_reason"] == "structural_fingerprint_match"
