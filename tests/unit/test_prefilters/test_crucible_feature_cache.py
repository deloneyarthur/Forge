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
    """First config triggers two client calls: activations first, then returns/regime."""
    client = MagicMock()
    spec = _spec()
    content_key = signal_content_key(spec)

    client.get_features.side_effect = [
        # Call 1: activation_dates
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
        # Call 2: returns + regime_label for the discovered activation dates
        _response(
            {
                content_key: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
    ]

    cache = CrucibleFeatureCache(client, data_history_days=4, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))

    assert client.get_features.call_count == 2
    assert cache.activation_dates(spec.id) == frozenset({date(2024, 1, 2)})
    assert cache.returns([date(2024, 1, 2)])[date(2024, 1, 2)] == pytest.approx(0.01)
    assert cache.regime_label(date(2024, 1, 2)) == "bull"


def test_second_prefetch_skips_already_cached_signals() -> None:
    """Calling prefetch_for_config twice with the same config doesn't re-fetch."""
    client = MagicMock()
    spec = _spec()
    content_key = signal_content_key(spec)
    client.get_features.side_effect = [
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
        _response(
            {
                content_key: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))
    # Second call: signal.id already in cache + all activation dates loaded → no fetch.
    client.get_features.reset_mock()
    cache.prefetch_for_config(_config(spec))
    assert client.get_features.call_count == 0


def test_activation_dates_unprefetched_raises_keyerror() -> None:
    """Querying before prefetch surfaces a clear error rather than a silent fetch."""
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    with pytest.raises(KeyError, match="display-id index"):
        cache.activation_dates("nonexistent_signal_id")


def test_returns_silently_skips_missing_dates() -> None:
    """`returns(dates)` returns only the dates we have — no KeyError on misses.

    The permutation_test filter passes the full data_history window; the
    cache only loaded dates Crucible's compute produced. The result map is
    shorter; the filter tolerates that.
    """
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    result = cache.returns([date(2024, 6, 1), date(2024, 7, 1)])
    assert result == {}


def test_regime_label_defaults_to_low_vol_for_missing_dates() -> None:
    """`regime_label(d)` returns "low_vol" default when not loaded.

    Crucible's regime classifier may not produce labels for every date the
    filter queries; returning a defensive default beats raising.
    """
    client = MagicMock()
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    assert cache.regime_label(date(2024, 6, 1)) == "low_vol"


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
        # Config A: activation_dates → fires on 2024-01-02 only
        _response({content_key_a: {"activation_dates": ["2024-01-02"]}}),
        # Config A: returns + regime for activation dates
        _response(
            {
                content_key_a: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        # Config B: activation_dates → fires on 2024-01-03 only
        _response({content_key_b: {"activation_dates": ["2024-01-03"]}}),
        # Config B: returns + regime for new date 2024-01-03
        _response(
            {
                content_key_b: {
                    "returns": {"2024-01-03": -0.005},
                    "regime_label": {"2024-01-03": "low_vol"},
                }
            }
        ),
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
        # Config A: activation_dates
        _response({content_key_a: {"activation_dates": ["2024-01-02"]}}),
        # Config A: returns + regime for those activation dates
        _response(
            {
                content_key_a: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        # Config B: activation_dates only — same date 2024-01-02 already in returns cache.
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
