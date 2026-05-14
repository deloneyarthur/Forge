"""Unit tests for `forge.prefilters.crucible_feature_cache.CrucibleFeatureCache`.

The adapter wraps `crucible_contracts.FeatureCacheClient`. These tests use a
stub client that records calls + returns canned `FeatureBatchResponse`s, so
no real writer socket is needed.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest
from crucible_contracts import (
    CombinerSpec,
    ExitSpec,
    FeatureBatchResponse,
    SelectorSpec,
    SignalSpec,
    SizerSpec,
    StrategyConfig,
    signal_content_key,
)

from forge.prefilters.crucible_feature_cache import CrucibleFeatureCache

_MANDATORY_EXITS = (
    ExitSpec(id="expiry_exit"),
    ExitSpec(id="theta_cliff_exit"),
    ExitSpec(id="earnings_exit"),
    ExitSpec(id="liquidity_exit"),
)


def _spec(indicator: str = "rsi_2", role: str = "directional") -> SignalSpec:
    return SignalSpec(
        id=f"sig_{indicator}_{role}",
        type="threshold",
        role=role,  # type: ignore[arg-type]
        indicators=(indicator,),
        params={"threshold": 30.0},
    )


def _config(*signals: SignalSpec) -> StrategyConfig:
    return StrategyConfig(
        name="test_cfg",
        hypothesis="mean_reversion",
        dte_bucket="swing_short",
        underlying="SPY",
        tier=1,
        signals=signals,
        combiner=CombinerSpec(),
        selector=SelectorSpec(
            delta_target=0.45,
            delta_tolerance=0.05,
            dte_min=14,
            dte_max=21,
        ),
        sizer=SizerSpec(mode="fixed_risk_pct"),
        exits=_MANDATORY_EXITS,
    )


def _response(features: dict[str, dict[str, Any]]) -> FeatureBatchResponse:
    return FeatureBatchResponse(features=features)


def test_prefetch_for_config_calls_client_for_signals_and_window() -> None:
    """First config triggers two client calls: window data + activation_dates."""
    client = MagicMock()
    spec = _spec()
    sig_id = signal_content_key(spec)

    client.get_features.side_effect = [
        # Window data response (first call: returns + regime_label)
        _response(
            {
                sig_id: {
                    "returns": {"2024-01-02": 0.01, "2024-01-03": -0.005},
                    "regime_label": {"2024-01-02": "bull", "2024-01-03": "bull"},
                }
            }
        ),
        # Activation dates response (second call)
        _response({sig_id: {"activation_dates": ["2024-01-02"]}}),
    ]

    cache = CrucibleFeatureCache(client, data_history_days=4, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))

    assert client.get_features.call_count == 2
    # Activation_dates resolves from cache.
    assert cache.activation_dates(sig_id) == frozenset({date(2024, 1, 2)})
    # Returns resolves for prefetched dates.
    assert cache.returns([date(2024, 1, 2)])[date(2024, 1, 2)] == pytest.approx(0.01)
    # Regime label resolves.
    assert cache.regime_label(date(2024, 1, 2)) == "bull"


def test_second_prefetch_skips_already_cached_signals() -> None:
    """Calling prefetch_for_config twice with the same config doesn't re-fetch."""
    client = MagicMock()
    spec = _spec()
    sig_id = signal_content_key(spec)
    client.get_features.side_effect = [
        _response(
            {
                sig_id: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        _response({sig_id: {"activation_dates": ["2024-01-02"]}}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))
    # Second call: window already loaded, signal already in cache → no client calls.
    client.get_features.reset_mock()
    cache.prefetch_for_config(_config(spec))
    assert client.get_features.call_count == 0


def test_activation_dates_unprefetched_raises_keyerror() -> None:
    """Querying before prefetch surfaces a clear error rather than a silent fetch."""
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    with pytest.raises(KeyError, match="not prefetched"):
        cache.activation_dates("nonexistent_signal_id")


def test_returns_unprefetched_date_raises_keyerror() -> None:
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    with pytest.raises(KeyError, match="not prefetched"):
        cache.returns([date(2024, 6, 1)])


def test_regime_label_unprefetched_date_raises_keyerror() -> None:
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    with pytest.raises(KeyError, match="not prefetched"):
        cache.regime_label(date(2024, 6, 1))


def test_two_distinct_configs_share_window_data() -> None:
    """Second config's prefetch only fetches its new signals, not window data again."""
    client = MagicMock()
    spec_a = _spec("rsi_2", "directional")
    spec_b = _spec("iv_rank", "regime_filter")
    sig_id_a = signal_content_key(spec_a)
    sig_id_b = signal_content_key(spec_b)
    client.get_features.side_effect = [
        # Config A: window data
        _response(
            {
                sig_id_a: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        # Config A: activation_dates
        _response({sig_id_a: {"activation_dates": ["2024-01-02"]}}),
        # Config B: activation_dates only (window already loaded)
        _response({sig_id_b: {"activation_dates": ["2024-01-02"]}}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec_a))
    cache.prefetch_for_config(_config(spec_b))
    # 2 calls for config A (window + activations) + 1 for config B (activations only) = 3
    assert client.get_features.call_count == 3
