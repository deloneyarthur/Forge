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
from forge.prefilters.types import FeatureDataUnavailable

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


def test_prefetch_for_batch_fetches_all_signals_then_one_window() -> None:
    """`prefetch_for_batch` does N chunked activation calls + 1 window call.

    With 3 configs x 1 spec each = 3 unique specs, we expect:
      - 1 activations call (chunk size = 500 default; well above 3)
      - 1 returns+regime call covering the union of activation dates
    """
    client = MagicMock()
    spec_a = _spec("rsi_2", "directional")
    spec_b = _spec("rsi_14", "directional")
    spec_c = _spec("adx_14", "directional")
    ck_a = signal_content_key(spec_a)
    ck_b = signal_content_key(spec_b)
    ck_c = signal_content_key(spec_c)
    client.get_features.side_effect = [
        # Call 1: activation_dates for all 3 specs
        _response(
            {
                ck_a: {"activation_dates": ["2024-01-02"]},
                ck_b: {"activation_dates": ["2024-01-03"]},
                ck_c: {"activation_dates": ["2024-01-04"]},
            }
        ),
        # Call 2: returns + regime for the union
        _response(
            {
                ck_a: {
                    "returns": {
                        "2024-01-02": 0.01,
                        "2024-01-03": -0.005,
                        "2024-01-04": 0.02,
                    },
                    "regime_label": {
                        "2024-01-02": "bull",
                        "2024-01-03": "low_vol",
                        "2024-01-04": "bull",
                    },
                }
            }
        ),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_batch([_config(spec_a), _config(spec_b), _config(spec_c)])

    assert client.get_features.call_count == 2
    # D033 — activations are keyed by (underlying, content_key); _config() uses underlying="SPY".
    assert cache._activations[("SPY", ck_a)] == frozenset({date(2024, 1, 2)})
    assert cache._activations[("SPY", ck_b)] == frozenset({date(2024, 1, 3)})
    assert cache._activations[("SPY", ck_c)] == frozenset({date(2024, 1, 4)})
    # Set active underlying so regime_label resolves to the right slice.
    cache._active_underlying = "SPY"
    assert cache.regime_label(date(2024, 1, 3)) == "low_vol"


def test_prefetch_for_batch_loads_full_window_returns_for_null_pool() -> None:
    """M-2 (audit 2026-05-29): permutation_test's null pool is
    `returns(full_window)`. Prefetch must load the FULL permutation window's
    returns per underlying — not just activation-date returns — or the pool
    degenerates to the signal's own fire-day returns, and D082 (full window) +
    D075 (forward horizon) become prod no-ops. Returns are per-underlying (one
    series), so this is a single bounded window fetch, not per-spec."""
    client = MagicMock()
    spec = _spec()
    ck = signal_content_key(spec)
    client.get_features.side_effect = [
        _response({ck: {"activation_dates": ["2024-01-02"]}}),
        _response({ck: {"returns": {}, "regime_label": {}}}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=10, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_batch([_config(spec)])

    returns_calls = [
        c
        for c in client.get_features.call_args_list
        if "returns" in (c.kwargs.get("feature_names") or ())
    ]
    assert returns_calls, "expected a returns/regime fetch"
    requested = returns_calls[0].kwargs["dates"]
    # window = ceil(10 * 366/252) = 15 calendar dates from data_start_date;
    # pre-fix only the single activation date (2024-01-02) was requested.
    assert len(requested) >= 14
    assert date(2024, 1, 1) in requested  # window start — NOT an activation date


def test_prefetch_for_batch_then_config_is_io_free() -> None:
    """After batch prefetch, `prefetch_for_config` does NO socket calls.

    The display-id index rebuild is the only per-config work; the cross-
    config content_key cache and the returns+regime cache are warm.
    """
    client = MagicMock()
    spec = _spec("rsi_2", "directional")
    ck = signal_content_key(spec)
    client.get_features.side_effect = [
        _response({ck: {"activation_dates": ["2024-01-02"]}}),
        _response(
            {
                ck: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cfg = _config(spec)
    cache.prefetch_for_batch([cfg])
    assert client.get_features.call_count == 2

    client.get_features.reset_mock()
    cache.prefetch_for_config(cfg)
    assert client.get_features.call_count == 0
    assert cache.activation_dates(spec.id) == frozenset({date(2024, 1, 2)})


def test_prefetch_for_batch_skips_already_cached_content_keys() -> None:
    """Specs whose content_key is in the cache from a prior batch aren't refetched."""
    client = MagicMock()
    spec = _spec("rsi_2", "directional")
    ck = signal_content_key(spec)
    client.get_features.side_effect = [
        # Initial batch loads spec
        _response({ck: {"activation_dates": ["2024-01-02"]}}),
        _response(
            {
                ck: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_batch([_config(spec)])
    assert client.get_features.call_count == 2

    # Second batch with the same spec: no new specs, no new dates → 0 calls.
    client.get_features.reset_mock()
    cache.prefetch_for_batch([_config(spec)])
    assert client.get_features.call_count == 0


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


def _config_with_underlying(underlying: str, *signals: SignalSpec) -> StrategyConfig:
    """`_config` variant for per-underlying tests (D033)."""
    return StrategyConfig(
        name=f"test_cfg_{underlying}",
        hypothesis="mean_reversion",
        dte_bucket="swing_short",
        underlying=underlying,
        tier=2,
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


def test_d033_two_configs_different_underlyings_do_not_collide() -> None:
    """D033 invariant: same signal spec on two underlyings must NOT share cache.

    Pre-D033 the activations cache keyed by `signal_content_key(spec)` alone,
    so an SPY config's activations for `rsi_2 < 30` would be returned to an
    AAPL config asking for `rsi_2 < 30` — silently miscalibrating every
    per-filter score for the second config. Post-D033 the key is
    `(underlying, content_key)` so the same spec under two underlyings gets
    two independent fetches and two independent activation sets.
    """
    client = MagicMock()
    spec = _spec()
    content_key = signal_content_key(spec)
    client.get_features.side_effect = [
        # Config A (SPY): activation_dates fetch
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
        # Config A: returns + regime fetch
        _response(
            {
                content_key: {
                    "returns": {"2024-01-02": 0.01},
                    "regime_label": {"2024-01-02": "bull"},
                }
            }
        ),
        # Config B (AAPL): activation_dates fetch — same spec, different
        # ticker, DIFFERENT activation dates.
        _response({content_key: {"activation_dates": ["2024-01-03", "2024-01-04"]}}),
        # Config B: returns + regime fetch
        _response(
            {
                content_key: {
                    "returns": {"2024-01-03": 0.02, "2024-01-04": -0.01},
                    "regime_label": {"2024-01-03": "high_vol", "2024-01-04": "high_vol"},
                }
            }
        ),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=2, data_start_date=date(2024, 1, 1))

    # Config A — SPY
    spy_cfg = _config_with_underlying("SPY", spec)
    cache.prefetch_for_config(spy_cfg)
    spy_activations = cache.activation_dates(spec.id)
    assert spy_activations == frozenset({date(2024, 1, 2)})
    assert cache.regime_label(date(2024, 1, 2)) == "bull"

    # Config B — AAPL with the SAME spec. Pre-D033 would have hit the SPY
    # cache and returned `{2024-01-02}`. Post-D033 it must hit Crucible
    # again and produce `{2024-01-03, 2024-01-04}`.
    aapl_cfg = _config_with_underlying("AAPL", spec)
    cache.prefetch_for_config(aapl_cfg)
    aapl_activations = cache.activation_dates(spec.id)
    assert aapl_activations == frozenset({date(2024, 1, 3), date(2024, 1, 4)})
    assert cache.regime_label(date(2024, 1, 3)) == "high_vol"
    # Total client calls: 4 (2 per config) — proves no cross-underlying cache hit.
    assert client.get_features.call_count == 4

    # Switching back to SPY context should re-serve the SPY slice.
    cache.prefetch_for_config(spy_cfg)
    assert cache.activation_dates(spec.id) == frozenset({date(2024, 1, 2)})
    assert cache.regime_label(date(2024, 1, 2)) == "bull"


def test_d033_underlying_none_falls_back_to_default() -> None:
    """`config.underlying is None` should fall back to the cache's default
    underlying (mirrors Crucible's `inbox.py:_FALLBACK_UNDERLYING = "SPY"`).
    Pre-D033 the cache held a single underlying at construction; this test
    pins the new fallback semantic for None.
    """
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
    cache = CrucibleFeatureCache(
        client,
        data_history_days=2,
        data_start_date=date(2024, 1, 1),
        underlying="SPY",
    )
    # underlying=None on the config — should resolve to "SPY" (the cache default).
    none_cfg = _config_with_underlying("SPY", spec)
    none_cfg = none_cfg.model_copy(update={"underlying": None})
    cache.prefetch_for_config(none_cfg)
    # Cache stored the activations under ("SPY", content_key) — proves
    # the fallback applied.
    assert ("SPY", content_key) in cache._activations
    assert cache.activation_dates(spec.id) == frozenset({date(2024, 1, 2)})


# ----------------------------------------------------------------------
# M-5 / M-6 (audit 2026-05-29): degraded-response detection + observability.
# A valid FeatureBatchResponse may carry activations but an empty window
# (thin Tier-2 underlying / transient writer state). Silently, returns() = {}
# and regime_label() defaults every date to "low_vol", which downstream looks
# like a genuine signal-quality REJECT. We instead mark the underlying
# data_unavailable and raise a typed sentinel so the verdict is distinct.
# ----------------------------------------------------------------------


def test_window_empty_marks_active_underlying_data_unavailable() -> None:
    """Activations present but the window fetch returns nothing → data_unavailable."""
    client = MagicMock()
    spec = _spec()
    content_key = signal_content_key(spec)
    client.get_features.side_effect = [
        # activation_dates: the signal DOES fire (so this isn't a density reject)
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
        # window (returns + regime_label): empty — Crucible has no data for it
        _response({}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=4, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))

    # Activations still resolve — only the window is unavailable.
    assert cache.activation_dates(spec.id) == frozenset({date(2024, 1, 2)})
    assert cache.active_underlying_data_unavailable() is True


def test_returns_and_regime_label_raise_when_data_unavailable() -> None:
    """returns()/regime_label() raise the typed sentinel rather than mislabel."""
    client = MagicMock()
    spec = _spec()
    content_key = signal_content_key(spec)
    client.get_features.side_effect = [
        _response({content_key: {"activation_dates": ["2024-01-02"]}}),
        _response({}),
    ]
    cache = CrucibleFeatureCache(client, data_history_days=4, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))

    with pytest.raises(FeatureDataUnavailable):
        cache.returns([date(2024, 1, 2)])
    with pytest.raises(FeatureDataUnavailable):
        cache.regime_label(date(2024, 1, 2))


def test_populated_window_underlying_stays_available() -> None:
    """A normal response (returns + regimes present) is NOT flagged unavailable."""
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
    cache = CrucibleFeatureCache(client, data_history_days=4, data_start_date=date(2024, 1, 1))
    cache.prefetch_for_config(_config(spec))

    assert cache.active_underlying_data_unavailable() is False
    assert cache.returns([date(2024, 1, 2)])[date(2024, 1, 2)] == pytest.approx(0.01)
    assert cache.regime_label(date(2024, 1, 2)) == "bull"
