"""Crucible-backed FeatureCache — closes Q10 / Phase 3 D1.

`CrucibleFeatureCache` implements the `FeatureCache` Protocol against
the real Crucible feature-cache surface in `crucible_contracts` v1.9.0+
(`FeatureCacheClient` over the writer's socket).

History:
  - Phase 3 D1 (`SyntheticFeatureCache`): Crucible's feature cache didn't
    exist; Forge defined the Protocol + a deterministic stub.
  - Contracts v1.9.0 (2026-05-14) shipped that surface. This module is
    the consumer-side adapter.
  - D033 (2026-05-16): made the cache underlying-aware. Pre-D033 the
    cache locked one underlying at construction (default SPY) and used
    it for every config — Forge's D032 Tier 1→Tier 2 expansion would
    have produced AAPL/NVDA/etc. configs whose pre-filters were all
    scored against SPY's activation history, silently miscalibrating
    the entire battery. Activations/returns/regimes are now keyed by
    underlying; the active underlying is set per `prefetch_for_config`.

The Protocol takes `signal_id: str`; Crucible needs the full `SignalSpec`
to compute features. `prefetch_for_config(config)` bridges the gap:
the battery orchestrator calls it before each config's filter pass to
pre-populate the cache, then the Protocol methods serve from in-memory
state. Calls that miss cache raise `KeyError` rather than performing
silent per-call round-trips — the design intent is per-config batching.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast

from crucible_contracts import (
    DEFAULT_DATA_HISTORY_DAYS,
    DEFAULT_UNDERLYING,
    FeatureCacheClient,
    SignalSpec,
    StrategyConfig,
    signal_content_key,
)

if TYPE_CHECKING:
    from crucible_contracts import Regime


# Chunk size for `prefetch_for_batch`. Bounds the writer's per-request work
# and the connection-message envelope size. 500 splits a typical
# unique-spec count (~2k-10k per batch) into 4-20 round-trips.
_BATCH_PREFETCH_CHUNK = 500

# M-2 (audit 2026-05-29): mirror `permutation_test._full_window`'s trading->calendar
# conversion (D082) so prefetch loads exactly the dates that filter reads back as its
# null pool. 366/252 over-covers (holidays/leap years); the writer returns only the
# trading days within, and `returns()` silently drops the surplus.
_CALENDAR_DAYS_PER_TRADING_DAY = 366 / 252


def _resolve_underlying(config: StrategyConfig, default: str) -> str:
    """Per-config underlying resolution mirroring Crucible's fallback.

    Crucible's `inbox.py:_FALLBACK_UNDERLYING = "SPY"` is the
    authoritative behavior when `config.underlying is None`. We mirror
    it here so the cache's view matches what Crucible will actually
    backtest. The `default` constructor arg controls the same fallback
    here (kept settable for tests; defaults to SPY).
    """
    return config.underlying or default


class CrucibleFeatureCache:
    """`FeatureCache` Protocol implementation backed by Crucible's writer socket.

    Construction:
        cache = CrucibleFeatureCache(client, data_start_date=date(2022, 1, 1))

    Per-config flow (run_battery calls this for us):
        cache.prefetch_for_config(config)
        # then per-filter calls (activation_dates, returns, regime_label)
        # are served from prefetched state, scoped to config.underlying.
    """

    __slots__ = (
        "_activations",
        "_active_underlying",
        "_client",
        "_data_history_days",
        "_data_start_date",
        "_default_underlying",
        "_display_id_index",
        "_regimes",
        "_returns",
        "_window_loaded_for",
        "data_history_days",
    )

    def __init__(
        self,
        client: FeatureCacheClient,
        *,
        data_history_days: int = DEFAULT_DATA_HISTORY_DAYS,
        data_start_date: date | None = None,
        underlying: str = DEFAULT_UNDERLYING,
    ) -> None:
        self._client = client
        self._data_history_days = data_history_days
        self._data_start_date = data_start_date or date(2022, 1, 1)
        # Default underlying — used by `probe()` and as the fallback when
        # a config's `underlying` is None. Mirrors Crucible's
        # `_FALLBACK_UNDERLYING = "SPY"` (D033).
        self._default_underlying = underlying
        # Protocol attribute — pre-filters read this directly.
        self.data_history_days = data_history_days
        # Activations cache keyed by (underlying, content_key) — two configs
        # with the same signal spec but different underlyings produce
        # different activation date sets and must not collide.
        self._activations: dict[tuple[str, str], frozenset[date]] = {}
        # display_id → content_key index, rebuilt per prefetch_for_config.
        # The enumerator reuses spec.id="sig_directional"/"sig_regime" across
        # every config (forge.enumeration.sampler), so keying the
        # activation cache by spec.id directly would collide all 5000
        # configs per batch onto a single bucket. The index is what bridges
        # the Protocol's `signal_id: str` (spec.id) to the content key.
        self._display_id_index: dict[str, str] = {}
        # Returns + regimes — keyed by underlying, then by date. Returns
        # / regime labels are computed per-ticker so they cannot share a
        # single global dict (the D033 bug).
        self._returns: dict[str, dict[date, float]] = defaultdict(dict)
        self._regimes: dict[str, dict[date, Regime]] = defaultdict(dict)
        # Per-underlying flag set after the first window-fetch lands.
        self._window_loaded_for: set[str] = set()
        # Currently active underlying — set during prefetch_for_config so
        # the Protocol methods (activation_dates / returns / regime_label)
        # know which slice to serve.
        self._active_underlying: str = underlying

    def probe(self) -> None:
        """Test-fetch a minimal request to verify the writer supports the protocol.

        Raises `FeatureCacheUnavailableError` if the writer rejects the
        `feature_batch` request kind (Crucible writer-side may not have
        shipped the handler yet). Callers use this at startup to decide
        whether to fall back to `SyntheticFeatureCache`. Uses the default
        underlying for the probe (typically SPY).
        """
        self._client.get_features(
            signals=(),
            feature_names=("returns",),
            dates=(self._data_start_date,),
            data_history_days=self._data_history_days,
            underlying=self._default_underlying,
        )

    def _fetch_activation_dates_chunked(
        self,
        specs: list[SignalSpec],
        underlying: str,
    ) -> None:
        """Fetch + cache `activation_dates` for `specs` under `underlying`."""
        for i in range(0, len(specs), _BATCH_PREFETCH_CHUNK):
            chunk = specs[i : i + _BATCH_PREFETCH_CHUNK]
            response = self._client.get_features(
                signals=tuple(chunk),
                feature_names=("activation_dates",),
                data_history_days=self._data_history_days,
                underlying=underlying,
            )
            for content_key, feature_map in response.features.items():
                if "activation_dates" not in feature_map:
                    continue
                raw_dates = feature_map["activation_dates"]
                self._activations[(underlying, content_key)] = frozenset(
                    date.fromisoformat(d) for d in raw_dates
                )

    def _fetch_window_for_dates(
        self,
        dates_to_fetch: tuple[date, ...],
        sentinel: SignalSpec,
        underlying: str,
    ) -> None:
        """Fetch + cache `returns` + `regime_label` for `(underlying, dates)`."""
        response = self._client.get_features(
            signals=(sentinel,),
            feature_names=("returns", "regime_label"),
            dates=dates_to_fetch,
            data_history_days=self._data_history_days,
            underlying=underlying,
        )
        ret_map = self._returns[underlying]
        reg_map = self._regimes[underlying]
        for feature_map in response.features.values():
            if "returns" in feature_map:
                for date_str, value in feature_map["returns"].items():
                    ret_map[date.fromisoformat(date_str)] = float(value)
            if "regime_label" in feature_map:
                for date_str, label in feature_map["regime_label"].items():
                    reg_map[date.fromisoformat(date_str)] = cast(
                        "Regime",
                        str(label),
                    )
            break  # one signal entry is enough — values are global per underlying
        self._window_loaded_for.add(underlying)

    def _permutation_window_dates(self) -> list[date]:
        """M-2: the calendar dates `permutation_test` requests as its null pool
        (`data_start_date` spanning `data_history_days` TRADING sessions). Mirrors
        `permutation_test._full_window` so prefetch loads what that filter reads
        back — otherwise the null pool is just the signal's activation-date returns
        and the permutation test (plus D082/D075) is meaningless."""
        n_cal = math.ceil(self._data_history_days * _CALENDAR_DAYS_PER_TRADING_DAY)
        return [self._data_start_date + timedelta(days=i) for i in range(n_cal)]

    def prefetch_for_batch(self, configs: Iterable[StrategyConfig]) -> None:
        """One-shot prefetch across an entire batch — amortises round-trips.

        The per-config `prefetch_for_config` makes up to 2 socket round-trips
        per config. With 5000 configs per batch and a sampler that mints
        fresh thresholds per spec (so `signal_content_key` is unique per
        spec, defeating the cross-config cache), that is ~10k round-trips.

        Post-D033: configs are partitioned by `underlying` first. Per
        partition, this method fetches the same data in 2 chunked passes:
          1. `activation_dates` for all uncached unique specs (for that
             underlying), batched in chunks of `_BATCH_PREFETCH_CHUNK`.
          2. `returns` + `regime_label` for the union of activation dates
             across the partition, in a single round-trip per underlying.

        After this runs, `prefetch_for_config` does only the per-config
        index rebuild + `_active_underlying` swap (no I/O).
        """
        configs_list = list(configs)
        configs_by_underlying: dict[str, list[StrategyConfig]] = defaultdict(list)
        for cfg in configs_list:
            configs_by_underlying[_resolve_underlying(cfg, self._default_underlying)].append(cfg)

        for underlying, group in configs_by_underlying.items():
            seen_keys: set[str] = set()
            new_specs: list[SignalSpec] = []
            for cfg in group:
                for spec in cfg.signals:
                    key = signal_content_key(spec)
                    cache_key = (underlying, key)
                    if cache_key in self._activations or key in seen_keys:
                        continue
                    seen_keys.add(key)
                    new_specs.append(spec)

            self._fetch_activation_dates_chunked(new_specs, underlying)

            all_activations: set[date] = set()
            for cfg in group:
                for spec in cfg.signals:
                    cached = self._activations.get((underlying, signal_content_key(spec)))
                    if cached is not None:
                        all_activations.update(cached)
            # M-2: on first touch of this underlying, load the FULL permutation
            # window's returns (the null pool) — not just activation dates;
            # afterward only any new activation dates (keeps re-prefetch io-light).
            if underlying not in self._window_loaded_for:
                returns_targets = all_activations | set(self._permutation_window_dates())
            else:
                returns_targets = all_activations
            missing_dates = tuple(
                sorted(returns_targets - self._returns[underlying].keys()),
            )
            if missing_dates and group and group[0].signals:
                self._fetch_window_for_dates(
                    missing_dates, group[0].signals[0], underlying,
                )

    def prefetch_for_config(self, config: StrategyConfig) -> None:
        """Pre-populate the cache for one config's signals.

        Per-config flow:
          1. Resolve underlying (config.underlying or default) and set as
             the active underlying. Subsequent Protocol-method calls serve
             from this underlying's slice.
          2. Rebuild `_display_id_index` from this config's specs so
             `activation_dates(spec.id)` resolves to the right content key
             (the enumerator reuses spec.id strings across configs).
          3. Fetch activation_dates for any (underlying, content_key) not
             already in the cache.
          4. Fetch returns + regime_label for the union of all activation
             dates discovered (this config + the per-underlying cross-config
             cache), skipping any date already loaded for this underlying.
        """
        underlying = _resolve_underlying(config, self._default_underlying)
        self._active_underlying = underlying

        # 2) Rebuild the per-config index. content_keys collide across
        # configs only when the spec is semantically identical AND the
        # underlying matches — keyed lookup handles that automatically.
        self._display_id_index = {
            spec.id: signal_content_key(spec) for spec in config.signals
        }
        new_specs = [
            spec
            for spec in config.signals
            if (underlying, signal_content_key(spec)) not in self._activations
        ]

        # 3) Fetch activation_dates for new specs (batched).
        if new_specs:
            self._fetch_activation_dates_chunked(new_specs, underlying)

        # 4) Fetch returns + regime_label for the union of THIS config's
        # activation dates. Skip any date already loaded for this
        # underlying.
        config_keys = (signal_content_key(s) for s in config.signals)
        all_activations: set[date] = set()
        for key in config_keys:
            cached = self._activations.get((underlying, key))
            if cached is not None:
                all_activations.update(cached)
        # M-2: on first touch of this underlying load the full permutation window;
        # afterward only new activations (so a prior batch-prefetch stays io-free).
        if underlying not in self._window_loaded_for:
            returns_targets = all_activations | set(self._permutation_window_dates())
        else:
            returns_targets = all_activations
        missing_dates = tuple(
            sorted(returns_targets - self._returns[underlying].keys()),
        )
        if missing_dates and config.signals:
            self._fetch_window_for_dates(
                missing_dates, config.signals[0], underlying,
            )

    # ------------------------------------------------------------------
    # FeatureCache Protocol methods — serve from the active underlying
    # ------------------------------------------------------------------

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        content_key = self._display_id_index.get(signal_id)
        if content_key is None:
            msg = (
                f"activation_dates: signal_id={signal_id!r} not in the current "
                "config's display-id index; call prefetch_for_config(config) "
                "before querying the cache."
            )
            raise KeyError(msg)
        cache_key = (self._active_underlying, content_key)
        if cache_key not in self._activations:
            msg = (
                f"activation_dates: ({self._active_underlying}, {content_key!r}) "
                f"for signal_id={signal_id!r} missing from Crucible response; "
                "the prefetch may have failed silently."
            )
            raise KeyError(msg)
        return self._activations[cache_key]

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        """Return whatever returns we have for the requested dates.

        Missing dates are silently dropped (not all calendar days are
        trading days; not all queried dates have been prefetched). The
        callers (permutation_test passes the full window; regime_exposure
        passes only activations) tolerate shorter result maps.

        Served from `_active_underlying`'s returns slice (D033).
        """
        ret_map = self._returns[self._active_underlying]
        return {d: ret_map[d] for d in dates if d in ret_map}

    def regime_label(self, d: date) -> Regime:
        """Return the regime for `d`; default to "low_vol" when not loaded.

        Crucible's regime classifier produces labels for trading days only.
        Activation dates that fall on non-classified days (rare) get the
        defensive "low_vol" default rather than crashing the filter.

        Served from `_active_underlying`'s regimes slice (D033).
        """
        return self._regimes[self._active_underlying].get(d, "low_vol")


__all__ = ["CrucibleFeatureCache"]
