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
    content_key = signal_content_key(spec)

    client.get_features.side_effect = [
        # Window data response (first call: returns + regime_label) — keyed
        # by content_key as Crucible's compute returns.
        _response(
            {
                content_key: {
                    "returns": {"2024-01-02": 0.01, "2024-01-03": -0.005},
                    "regime_label": {"2024-01-02": "bull", "2024-01-03": "bull"},
                }
            }
        ),
        # Activation dates response (second call)
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
    ]

    cache = CrucibleFeatureCache(client, data_history_days=4, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))

    assert client.get_features.call_count == 2
    # Activation_dates is served by `spec.id` (the display id consumers pass),
    # not by the content_key Crucible uses internally.
    assert cache.activation_dates(spec.id) == frozenset({date(2024, 1, 2)})
    # Returns resolves for prefetched dates.
    assert cache.returns([date(2024, 1, 2)])[date(2024, 1, 2)] == pytest.approx(0.01)
    # Regime label resolves.
    assert cache.regime_label(date(2024, 1, 2)) == "bull"


def test_second_prefetch_skips_already_cached_signals() -> None:
    """Calling prefetch_for_config twice with the same config doesn't re-fetch."""
    client = MagicMock()
    spec = _spec()
    content_key = signal_content_key(spec)
    client.get_features.side_effect = [
        _response(
            {
                content_key: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))
    # Second call: window already loaded, signal.id already in cache → no client calls.
    client.get_features.reset_mock()
    cache.prefetch_for_config(_config(spec))
    assert client.get_features.call_count == 0


def test_activation_dates_unprefetched_raises_keyerror() -> None:
    """Querying before prefetch surfaces a clear error rather than a silent fetch."""
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    with pytest.raises(KeyError, match="display-id index"):
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


def test_repeated_spec_id_across_configs_resolves_to_correct_activations() -> None:
    """Regression: the enumerator reuses `id="sig_directional"` across every
    config; the adapter MUST route each config's lookup to its own content
    key, not the first config's activations.
    """
    client = MagicMock()
    spec_a = SignalSpec(
        id="sig_directional",
        type="threshold",
        role="directional",
        indicators=("rsi_2",),
        params={"threshold": 30.0},
    )
    spec_b = SignalSpec(
        id="sig_directional",
        type="threshold",
        role="directional",
        indicators=("rsi_14",),
        params={"threshold": 30.0},
    )
    content_key_a = signal_content_key(spec_a)
    content_key_b = signal_content_key(spec_b)
    assert content_key_a != content_key_b

    client.get_features.side_effect = [
        # Config A: window data
        _response(
            {
                content_key_a: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        # Config A: activation_dates → fires on 2024-01-02 only
        _response({content_key_a: {"activation_dates": ["2024-01-02"]}}),
        # Config B: activation_dates → fires on 2024-01-03 only
        _response({content_key_b: {"activation_dates": ["2024-01-03"]}}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec_a))
    assert cache.activation_dates("sig_directional") == frozenset({date(2024, 1, 2)})
    cache.prefetch_for_config(_config(spec_b))
    # CRITICAL: the same display id MUST now resolve to spec_b's activations,
    # NOT spec_a's (which the pre-fix adapter cached and never overwrote).
    assert cache.activation_dates("sig_directional") == frozenset({date(2024, 1, 3)})


def test_two_distinct_configs_share_window_data() -> None:
    """Second config's prefetch only fetches its new signals, not window data again."""
    client = MagicMock()
    spec_a = _spec("rsi_2", "directional")
    spec_b = _spec("iv_rank", "regime_filter")
    content_key_a = signal_content_key(spec_a)
    content_key_b = signal_content_key(spec_b)
    client.get_features.side_effect = [
        # Config A: window data
        _response(
            {
                content_key_a: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        # Config A: activation_dates
        _response({content_key_a: {"activation_dates": ["2024-01-02"]}}),
        # Config B: activation_dates only (window already loaded)
        _response({content_key_b: {"activation_dates": ["2024-01-02"]}}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec_a))
    # Query inside config A's prefetch context.
    assert cache.activation_dates(spec_a.id) == frozenset({date(2024, 1, 2)})
    cache.prefetch_for_config(_config(spec_b))
    # 2 calls for config A (window + activations) + 1 for config B (activations only) = 3
    assert client.get_features.call_count == 3
    # spec_b resolves now that its config is the active prefetch context.
    assert cache.activation_dates(spec_b.id) == frozenset({date(2024, 1, 2)})
    # spec_a is intentionally no longer in the display-id index — the per-
    # config index is rebuilt each prefetch so spec.id collisions across
    # configs route to the right content_key.
    with pytest.raises(KeyError, match="display-id index"):
        cache.activation_dates(spec_a.id)
