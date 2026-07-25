"""Tests for forge.ranking.features (D132 / F1) — config → feature vector.

One extraction codepath serves both training (configs rehydrated from
``submissions.config_json``) and scoring (in-memory configs); the learned-ranker
design is `docs/proposals/learned-ranker.md` §4 F1. Extraction is featurization,
not validation — it must never raise on a grammar-invalid config.
"""

from __future__ import annotations

import pytest
from crucible_contracts import CombinerSpec, ExitSpec, SelectorSpec, SignalSpec, SizerSpec

from forge.ranking.features import (
    FEATURE_SCHEMA_VERSION,
    FeatureVector,
    extract_features,
)
from tests.fixtures.strategy_configs import (
    minimal_registry_snapshot,
    minimal_strategy_config,
)

_REGISTRY = minimal_registry_snapshot()


def _features(**overrides: object) -> dict[str, float]:
    config = minimal_strategy_config(**overrides)
    return extract_features(config, _REGISTRY).as_dict()


# ---------------------------------------------------------------------------
# Schema + shape
# ---------------------------------------------------------------------------


def test_schema_version_is_pinned() -> None:
    assert FEATURE_SCHEMA_VERSION == 1


def test_feature_vector_carries_schema_version_and_sorted_names() -> None:
    vec = extract_features(minimal_strategy_config(), _REGISTRY)
    assert isinstance(vec, FeatureVector)
    assert vec.schema_version == FEATURE_SCHEMA_VERSION
    names = [name for name, _ in vec.features]
    assert names == sorted(names)


def test_extraction_is_deterministic() -> None:
    a = extract_features(minimal_strategy_config(), _REGISTRY)
    b = extract_features(minimal_strategy_config(), _REGISTRY)
    assert a == b


# ---------------------------------------------------------------------------
# Identity one-hots
# ---------------------------------------------------------------------------


def test_identity_one_hots_default_fixture() -> None:
    feats = _features()
    assert feats["hypothesis=mean_reversion"] == 1.0
    assert feats["dte_bucket=swing_short"] == 1.0
    # SPY is in the D106 diversified index.
    assert feats["underlying_class=diversified"] == 1.0
    assert "hypothesis=trend_continuation" not in feats


def test_single_name_underlying_classes_high_idio_vol() -> None:
    feats = _features(underlying="AAPL")
    assert feats["underlying_class=high_idio_vol"] == 1.0


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def test_directional_family_and_id() -> None:
    feats = _features()
    assert feats["dir_family=mean_reversion"] == 1.0  # rsi_2 per registry
    assert feats["dir_id=rsi_2"] == 1.0


def test_directional_indicator_missing_from_registry_is_unknown_family() -> None:
    signals = (
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("not_in_registry",),
            params={"threshold": 1.0},
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("iv_rank",),
            params={"threshold": 50},
        ),
    )
    feats = _features(signals=signals)
    assert feats["dir_family=unknown"] == 1.0
    assert feats["dir_id=not_in_registry"] == 1.0


def test_regime_gates_multi_hot_and_counts() -> None:
    feats = _features()
    assert feats["regime_id=iv_rank"] == 1.0
    assert feats["n_regime_gates"] == 1.0
    assert feats["n_signals"] == 2.0
    assert feats["has_filter"] == 0.0
    assert feats["has_confluence"] == 0.0


# ---------------------------------------------------------------------------
# Selector normalizations
# ---------------------------------------------------------------------------


def test_delta_normalized_within_base_band() -> None:
    # swing_short band is (0.40, 0.55); fixture delta_target = 0.45.
    feats = _features()
    assert feats["delta_in_band"] == pytest.approx((0.45 - 0.40) / 0.15)


def test_delta_normalized_within_v16_trend_override_band() -> None:
    # trend_continuation x swing_mid band is (0.30, 0.55) per D125 — NOT the
    # base (0.30, 0.45). delta 0.50 sits at 0.8 of the override band and
    # outside the base band entirely.
    feats = _features(
        hypothesis="trend_continuation",
        dte_bucket="swing_mid",
        selector=SelectorSpec(
            delta_target=0.50,
            delta_tolerance=0.05,
            dte_min=30,
            dte_max=45,
        ),
    )
    assert feats["delta_in_band"] == pytest.approx((0.50 - 0.30) / 0.25)


def test_dte_normalized_within_p2_window() -> None:
    # swing_short window is (14, 21); fixture dte_min=14, dte_max=21.
    feats = _features()
    assert feats["dte_min_in_window"] == pytest.approx(0.0)
    assert feats["dte_max_in_window"] == pytest.approx(1.0)


def test_threshold_quantile_native_units() -> None:
    # rsi_2's directional_range is (5.0, 15.0) in the sampler table;
    # threshold 10.0 sits at the midpoint.
    signals = (
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"period": 2, "threshold": 10.0},
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("iv_rank",),
            params={"threshold": 50},
        ),
    )
    feats = _features(signals=signals)
    assert feats["dir_threshold_q"] == pytest.approx(0.5)


def test_threshold_quantile_percentile_passthrough() -> None:
    # Percentile-emitting params carry threshold already in [0, 1] (D099);
    # the quantile is the threshold itself, not a native-range projection.
    signals = (
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("rsi_2",),
            params={"threshold": 0.12, "use_percentile": True},
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("iv_rank",),
            params={"threshold": 50},
        ),
    )
    feats = _features(signals=signals)
    assert feats["dir_threshold_q"] == pytest.approx(0.12)


def test_threshold_quantile_omitted_when_unknowable() -> None:
    signals = (
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("not_in_registry",),
            params={"threshold": 3.0},
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("iv_rank",),
            params={"threshold": 50},
        ),
    )
    feats = _features(signals=signals)
    assert "dir_threshold_q" not in feats


# ---------------------------------------------------------------------------
# Sizer + exits
# ---------------------------------------------------------------------------


def test_sizer_mode_and_risk_band() -> None:
    feats = _features()
    assert feats["sizer=fixed_risk_pct"] == 1.0
    # Default per_trade_risk_pct = 0.02 == the P4 upper bound.
    assert feats["risk_pct_in_band"] == pytest.approx(1.0)


def test_exits_multi_hot_excludes_mandatory() -> None:
    feats = _features()
    assert feats["n_optional_exits"] == 0.0
    assert not any(name.startswith("exit=") for name in feats)

    with_time_stop = minimal_strategy_config()
    exits = (*with_time_stop.exits, ExitSpec(id="time_stop"))
    feats = _features(exits=exits)
    assert feats["exit=time_stop"] == 1.0
    assert feats["n_optional_exits"] == 1.0
    assert "exit=expiry_exit" not in feats


# ---------------------------------------------------------------------------
# Rank arm + combiner
# ---------------------------------------------------------------------------


def test_rank_arm_flag_and_rank_k() -> None:
    feats = _features(
        combiner=CombinerSpec(
            type="cross_sectional_rank",
            direction_strategy="k_of_n",
            k=1,
            rank_k=5,
            rebalance_frequency="weekly",
            direction_mode="long_only",
        ),
        underlying=None,
    )
    assert feats["is_rank_arm"] == 1.0
    # Q59/arm F: rank_k is one-hot, not a slope — the linear encoding mis-signed it
    # (non-monotonic: k=20 converts 0% on the D004 breadth floor).
    assert feats["rank_k_is_5"] == 1.0
    assert feats["rank_k_is_10"] == 0.0
    assert feats["combiner=cross_sectional_rank"] == 1.0
    # No underlying on the rank arm → no underlying_class feature at all.
    assert not any(name.startswith("underlying_class=") for name in feats)


def test_single_name_default_is_not_rank_arm() -> None:
    feats = _features()
    assert feats["is_rank_arm"] == 0.0
    assert feats["combiner=confluence"] == 1.0


# ---------------------------------------------------------------------------
# Featurization never validates
# ---------------------------------------------------------------------------


def test_grammar_invalid_config_still_featurizes() -> None:
    # mean_reversion with a trend directional violates C2 — extraction is
    # not a grammar check and must featurize it anyway.
    signals = (
        SignalSpec(
            id="sig_directional",
            type="threshold",
            role="directional",
            indicators=("momentum_252",),
            params={"threshold": 0.1},
        ),
        SignalSpec(
            id="sig_regime",
            type="threshold",
            role="regime_filter",
            indicators=("iv_rank",),
            params={"threshold": 50},
        ),
    )
    feats = _features(signals=signals)
    assert feats["dir_family=trend"] == 1.0


def test_rank_k_is_CATEGORICAL_not_a_slope() -> None:
    """Q59/arm F: `rank_k`'s relation to outcome is NON-MONOTONIC, so a linear feature
    cannot represent it and comes out with the WRONG SIGN.

    Measured P(F3 label=1): k=5 0.0735, k=10 0.1336, **k=20 0.0000** — the D004 breadth
    floor (`n_min = 2*rank_k` is unresolvable from a 20-name tier-2 pool; Crucible
    reproduce the zero exactly at 0/55,981 against our 0/55,820). A single slope through
    a peak-then-cliff is dragged negative by the cliff, which is what produced the
    -0.33/-0.51 coefficient both sides first mis-read as pure collider bias.

    One-hot is the encoding that stops caring about the middle ordering — which matters
    because the k5-vs-k10 ordering is itself window-specific (Crucible: all-time reverses
    it). Validated OOS: no-drop+one-hot 0.6936 vs no-drop+linear 0.6550 AUC, with an
    unchanged overfit gap, so the gain is not bought with parameters.
    """
    cfg = minimal_strategy_config(
        combiner=CombinerSpec(type="cross_sectional_rank", rank_k=10, rebalance_frequency="monthly")
    )
    feats = extract_features(cfg, _REGISTRY).as_dict()

    assert "rank_k" not in feats, "a linear rank_k slope must not exist — it mis-signs"
    assert feats["rank_k_is_10"] == 1.0
    assert feats["rank_k_is_5"] == 0.0
    assert feats["rank_k_is_20"] == 0.0


def test_confluence_config_has_no_rank_k_indicators() -> None:
    """Non-rank configs must not carry rank_k indicators at all — pooling them as
    `rank_k=0` is what made the arm-C composition question look plausible."""
    feats = extract_features(minimal_strategy_config(), _REGISTRY).as_dict()
    assert not any(k.startswith("rank_k") for k in feats)


def test_vol_target_sizer_one_hot() -> None:
    feats = _features(sizer=SizerSpec(mode="vol_target", per_trade_risk_pct=0.005))
    assert feats["sizer=vol_target"] == 1.0
    assert feats["risk_pct_in_band"] == pytest.approx(0.0)
