"""v31 capitulation-bounce activation — Crucible generation request (2026-07-12).

Enforces the enumeration-policy changes that ride grammar_version v31
(`docs/tasks/grammar-change.md` classification #2/#3; the §3.5 `rules:` text is
untouched; loosening operator-approved via OPEN_PROPOSALS `e9d74318`). Refs:
`IMPLEMENTATION_DECISIONS.md` D270, the handoff
`../Crucible/docs/handoffs/FORGE_capitulation_bounce_generation_request_2026-07-12.md`
— buy-the-panic-print long calls: trailing 5-day drop trigger in ELEVATED vol,
pooled +0.107 net on premium at 2% per-leg cost (high_vol +0.127), the
worst-quartile bear/high-vol complement no existing supply covers.

  * `momentum` (the parameterized id — dark, 0 of 462,990 submissions) becomes
    an enumerable MEAN_REVERSION directional via a §3.5 C2 per-id carve-out:
    its registry family is `trend`, but the capitulation trigger is a
    contrarian reversion thesis and the probe chassis is time-stop-primary —
    MR's exit schema, not trend's (trailing-exit-required). Absolute threshold
    (-0.083, -0.041) op "<" (log-return units ≈ -8%..-4% simple; probe point
    -0.051), computation knobs `lookback` [3, 10] / `skip` 0 riding the
    SignalSpec params (their sweep bounds; probe used 5/0).
  * The regime gate is PINNED to `rv_rank` op ">" threshold [50, 80] — the
    intended-strength elevated-vol condition the probe's own coding bug left
    inert (their §"Trigger as MEASURED vs as intended"). R1 accepts it as
    written (op-agnostic by the D107 convention); every prior MR gate used the
    calm "<" side — this family deliberately occupies the vetoed corner.
  * Horizon: momentum 15 td (3-10 d formation + ~10 td bounce) →
    medium_lookback; the D102 k∈{2,3,4} derivation snaps every target
    (30/45/60) to swing_mid — the probe chassis. (swing_long is not
    expressible for one id under horizon-matched DTE; gate-OFF arms fail R1;
    delta 0.45-0.55 exceeds MR's P3 band — all three are injection-lane
    arms, see the proposal.)
  * Guards: momentum is pinned OUT of trend_continuation's directional pool
    (the threshold entry would otherwise auto-admit it there with contrarian
    semantics and the wrong exit chassis) and OUT of the rank path (the
    cross-sectional combiner sorts DESCENDING — top-N by raw momentum buys the
    STRONGEST names, the inverse mechanism).
"""

from __future__ import annotations

import random

from crucible_contracts import IndicatorMetadata, SignalSpec

from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.sampler import _directional_signal_params
from forge.enumeration.search_space import rank_excluded_indicator_ids
from forge.grammar import evaluate
from forge.grammar.custom_predicates import _C2_HYPOTHESIS_EXTRA_IDS
from forge.grammar.models import CustomPythonPredicate
from forge.grammar.signal_horizon import (
    _DEFAULT_HORIZON_DAYS,
    buckets_for_horizon_class,
    horizon_class,
    nearest_bucket,
    signal_horizon_days,
)
from tests.fixtures.strategy_configs import (
    grammar_valid_baseline,
    minimal_registry_snapshot,
)

# --- momentum: absolute drop-trigger MR directional ----------------------------


def test_momentum_is_enumerable_directional() -> None:
    assert not is_threshold_skippable("momentum", "directional")


def test_momentum_is_not_a_regime_gate() -> None:
    """Directional-only: the drop trigger anchors the config, it never gates
    one (C4 keeps it single-role; the vol condition is rv_rank's job)."""
    assert is_threshold_skippable("momentum", "regime_filter")


def test_momentum_directional_params_absolute_drop_trigger() -> None:
    """Native-unit LOG-return threshold in (-0.083, -0.041), op '<' — fires on
    the capitulation print (trailing drop at least ~4-8% simple). Never
    percentile: the probe validated an absolute drop floor, and momentum's
    output is a log return whose economic cut is the drop size itself."""
    for seed in range(50):
        params = sample_threshold_params("momentum", "directional", random.Random(seed))
        assert params.get("op") == "<"
        assert "use_percentile" not in params
        threshold = params["threshold"]
        assert isinstance(threshold, float)
        assert -0.083 <= threshold <= -0.041


def test_momentum_lookback_skip_ride_directional_params() -> None:
    """The Crucible computation knobs ride the same params dict as the
    threshold (the residual_momentum/D264 precedent). Sweep bounds are the
    handoff's: lookback 3-10, skip pinned 0 (the trigger reads the raw
    trailing drop INCLUDING the most recent bar — a reversal-avoidance skip
    would erase the capitulation print itself)."""
    for seed in range(50):
        params = _directional_signal_params("momentum", random.Random(seed))
        lookback = params.get("lookback")
        skip = params.get("skip")
        assert isinstance(lookback, int)
        assert 3 <= lookback <= 10
        assert skip == 0
        assert "threshold" in params


def test_momentum_params_deterministic() -> None:
    """Hard rule #6: same seed → same params, draw for draw."""
    a = _directional_signal_params("momentum", random.Random(1234))
    b = _directional_signal_params("momentum", random.Random(1234))
    assert a == b


def test_momentum_horizon_snaps_to_swing_mid() -> None:
    """15 td (formation 3-10 d + ~10 td bounce hold) → medium_lookback → S4
    permits swing_short/swing_mid, and the D102 derivation (k in {2,3,4} x 15
    = 30/45/60) snaps every target to swing_mid — the probe's 25-45 DTE band.
    swing_long is structurally out (one id, one horizon — the v27 finding)."""
    assert signal_horizon_days("momentum") == 15
    assert signal_horizon_days("momentum") != _DEFAULT_HORIZON_DAYS
    assert horizon_class("momentum") == "medium_lookback"
    allowed = buckets_for_horizon_class("medium_lookback")
    assert allowed == ("swing_short", "swing_mid")
    for k in (2, 3, 4):
        assert nearest_bucket(allowed, float(k * 15)) == "swing_mid"


# --- §3.5 C2 per-id carve-out ---------------------------------------------------


def _registry_with_momentum() -> object:
    base = minimal_registry_snapshot()
    momentum = IndicatorMetadata(
        id="momentum",
        version=1,
        family="trend",
        lookback=504,
        params_schema={},
        rank_per_name_coherent=True,
        market_wide_by_design=False,
    )
    return base.model_copy(update={"indicators": (*base.indicators, momentum)})


def _c2() -> CustomPythonPredicate:
    return CustomPythonPredicate(
        type="custom_python", function="directional_family_matches_hypothesis"
    )


def test_c2_carveout_is_momentum_on_mean_reversion_only() -> None:
    """The carve-out is PER-ID and minimal: exactly momentum, exactly under
    mean_reversion. Widening it is a §3.5 C2 edit (operator-owned)."""
    assert _C2_HYPOTHESIS_EXTRA_IDS == {"mean_reversion": ("momentum",)}


def test_c2_momentum_passes_under_mean_reversion() -> None:
    """The carve-out: a trend-family `momentum` directional is C2-legal under
    mean_reversion — the capitulation trigger is a reversion thesis; the
    family label follows the kernel (a momentum measurement), not the use."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("momentum",),
                params={"threshold": -0.051, "op": "<", "lookback": 5, "skip": 0},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(_c2(), cfg, _registry_with_momentum())
    assert result.passed


def test_c2_other_trend_family_ids_still_fail_under_mean_reversion() -> None:
    """The carve-out does NOT open the trend family: any other trend-family id
    (here ema_50) as an MR directional still fails C2."""
    cfg = grammar_valid_baseline(
        signals=(
            SignalSpec(
                id="sig_directional",
                type="threshold",
                role="directional",
                indicators=("ema_50",),
                params={"threshold": 0.5, "op": ">"},
            ),
            SignalSpec(
                id="sig_regime",
                type="threshold",
                role="regime_filter",
                indicators=("iv_rank",),
                params={"threshold": 50},
            ),
        ),
    )
    result = evaluate(_c2(), cfg, _registry_with_momentum())
    assert not result.passed


def test_momentum_rank_policy_excluded() -> None:
    """The rank guard: momentum never enters a universe-wide rank config. The
    cross_sectional_rank combiner sorts DESCENDING unconditionally — top-N by
    raw momentum = the STRONGEST names = the inverse of the capitulation
    mechanism. Policy exclusion (a tightening), not registry-flag-derived
    (momentum IS rank_per_name_coherent)."""
    assert "momentum" in rank_excluded_indicator_ids(_registry_with_momentum())
