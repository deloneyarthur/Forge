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


def test_t27_structural_fingerprint_is_stable_across_param_changes() -> None:
    """T2.7: same structural skeleton + different thresholds → same fingerprint."""
    from crucible_contracts import (
        CombinerSpec,
        ExitSpec,
        SelectorSpec,
        SignalSpec,
        SizerSpec,
        StrategyConfig,
    )

    from forge.prefilters.novelty import compute_structural_fingerprint

    def _make_cfg(threshold: float) -> StrategyConfig:
        return StrategyConfig(
            name=f"cfg_{threshold}",
            hypothesis="mean_reversion",
            dte_bucket="swing_short",
            underlying="SPY",
            tier=1,
            signals=(
                SignalSpec(id="sig_directional", type="threshold", role="directional",
                           indicators=("rsi_2",), params={"threshold": threshold}),
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

    fp_a = compute_structural_fingerprint(_make_cfg(20.0))
    fp_b = compute_structural_fingerprint(_make_cfg(30.0))
    assert fp_a == fp_b  # parameter difference, identical structure
    assert len(fp_a) == 16  # 16-hex-char short hash


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
