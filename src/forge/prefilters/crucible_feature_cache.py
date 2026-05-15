"""Crucible-backed FeatureCache — closes Q10 / Phase 3 D1.

`CrucibleFeatureCache` implements the `FeatureCache` Protocol against
the real Crucible feature-cache surface in `crucible_contracts` v1.9.0
(`FeatureCacheClient` over the writer's socket).

History:
  - Phase 3 D1 (`SyntheticFeatureCache`): Crucible's feature cache didn't
    exist; Forge defined the Protocol + a deterministic stub.
  - Contracts v1.9.0 (2026-05-14) shipped that surface. This module is
    the consumer-side adapter.

The Protocol takes `signal_id: str`; Crucible needs the full `SignalSpec`
to compute features. `prefetch_for_config(config)` bridges the gap:
the battery orchestrator calls it before each config's filter pass to
pre-populate the cache, then the Protocol methods serve from in-memory
state. Calls that miss cache raise `KeyError` rather than performing
silent per-call round-trips — the design intent is per-config batching.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
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


class CrucibleFeatureCache:
    """`FeatureCache` Protocol implementation backed by Crucible's writer socket.

    Construction:
        cache = CrucibleFeatureCache(client, data_start_date=date(2022, 1, 1))

    Per-config flow (run_battery calls this for us):
        cache.prefetch_for_config(config)
        # then per-filter calls (activation_dates, returns, regime_label)
        # are served from prefetched state.
    """

    __slots__ = (
        "_activations_by_content_key",
        "_client",
        "_data_history_days",
        "_data_start_date",
        "_display_id_index",
        "_regimes",
        "_returns",
        "_underlying",
        "_window_loaded",
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
        self._underlying = underlying
        # Protocol attribute — pre-filters read this directly.
        self.data_history_days = data_history_days
        # Cache by signal_content_key — survives across configs; two configs
        # whose directional spec is semantically identical hit cache.
        self._activations_by_content_key: dict[str, frozenset[date]] = {}
        # display_id → content_key index, rebuilt per prefetch_for_config.
        # The enumerator reuses spec.id="sig_directional"/"sig_regime" across
        # every config (forge.enumeration.sampler:132/138), so keying the
        # activation cache by spec.id directly would collide all 5000
        # configs per batch onto a single bucket. The index is what bridges
        # the Protocol's `signal_id: str` (spec.id) to the content key.
        self._display_id_index: dict[str, str] = {}
        self._returns: dict[date, float] = {}
        self._regimes: dict[date, Regime] = {}
        self._window_loaded = False

    def probe(self) -> None:
        """Test-fetch a minimal request to verify the writer supports the protocol.

        Raises `FeatureCacheUnavailableError` if the writer rejects the
        `feature_batch` request kind (Crucible writer-side may not have
        shipped the handler yet). Callers use this at startup to decide
        whether to fall back to `SyntheticFeatureCache`.
        """
        self._client.get_features(
            signals=(),
            feature_names=("returns",),
            dates=(self._data_start_date,),
            data_history_days=self._data_history_days,
            underlying=self._underlying,
        )

    def _fetch_activation_dates_chunked(self, specs: list[SignalSpec]) -> None:
        """Fetch + cache `activation_dates` for `specs` in size-bounded chunks."""
        for i in range(0, len(specs), _BATCH_PREFETCH_CHUNK):
            chunk = specs[i : i + _BATCH_PREFETCH_CHUNK]
            response = self._client.get_features(
                signals=tuple(chunk),
                feature_names=("activation_dates",),
                data_history_days=self._data_history_days,
                underlying=self._underlying,
            )
            for content_key, feature_map in response.features.items():
                if "activation_dates" not in feature_map:
                    continue
                raw_dates = feature_map["activation_dates"]
                self._activations_by_content_key[content_key] = frozenset(
                    date.fromisoformat(d) for d in raw_dates
                )

    def _fetch_window_for_dates(
        self,
        dates_to_fetch: tuple[date, ...],
        sentinel: SignalSpec,
    ) -> None:
        """Fetch + cache `returns` + `regime_label` for `dates_to_fetch`."""
        response = self._client.get_features(
            signals=(sentinel,),
            feature_names=("returns", "regime_label"),
            dates=dates_to_fetch,
            data_history_days=self._data_history_days,
            underlying=self._underlying,
        )
        for feature_map in response.features.values():
            if "returns" in feature_map:
                for date_str, value in feature_map["returns"].items():
                    self._returns[date.fromisoformat(date_str)] = float(value)
            if "regime_label" in feature_map:
                for date_str, label in feature_map["regime_label"].items():
                    self._regimes[date.fromisoformat(date_str)] = cast(
                        "Regime",
                        str(label),
                    )
            break  # one signal entry is enough — values are global
        self._window_loaded = True

    def prefetch_for_batch(self, configs: Iterable[StrategyConfig]) -> None:
        """One-shot prefetch across an entire batch — amortises round-trips.

        The per-config `prefetch_for_config` makes up to 2 socket round-trips
        per config. With 5000 configs per batch and a sampler that mints
        fresh thresholds per spec (so `signal_content_key` is unique per
        spec, defeating the cross-config cache), that is ~10k round-trips.

        This method fetches the same data in 2 chunked passes:
          1. `activation_dates` for all uncached unique specs, batched in
             chunks of `_BATCH_PREFETCH_CHUNK` signals to bound the writer's
             per-request work and JSON envelope size.
          2. `returns` + `regime_label` for the union of activation dates
             across the whole batch, in a single round-trip.

        After this runs, `prefetch_for_config` does only the per-config
        index rebuild (no I/O).
        """
        configs_list = list(configs)
        seen_keys: set[str] = set()
        new_specs: list[SignalSpec] = []
        for cfg in configs_list:
            for spec in cfg.signals:
                key = signal_content_key(spec)
                if key in self._activations_by_content_key or key in seen_keys:
                    continue
                seen_keys.add(key)
                new_specs.append(spec)

        self._fetch_activation_dates_chunked(new_specs)

        all_activations: set[date] = set()
        for cfg in configs_list:
            for spec in cfg.signals:
                cached = self._activations_by_content_key.get(signal_content_key(spec))
                if cached is not None:
                    all_activations.update(cached)
        missing_dates = tuple(sorted(all_activations - self._returns.keys()))
        if missing_dates and configs_list and configs_list[0].signals:
            self._fetch_window_for_dates(missing_dates, configs_list[0].signals[0])

    def prefetch_for_config(self, config: StrategyConfig) -> None:
        """Pre-populate the cache for one config's signals.

        Per-config flow:
          1. Rebuild `_display_id_index` from this config's specs so
             `activation_dates(spec.id)` resolves to the right content key
             (the enumerator reuses spec.id strings across configs).
          2. Fetch activation_dates for any spec whose content_key isn't in
             the cross-config cache.
          3. Fetch returns + regime_label for the union of all activation
             dates discovered (this config + the cross-config cache),
             skipping any date already loaded. This is precise — only the
             dates Crucible's compute actually produced are queried, and we
             avoid the window-mismatch issue where data_start_date <
             actual_first_activation (lookback-period activations) or
             data_history_days underestimates the calendar span.
        """
        # 1) Rebuild the per-config index. content_keys collide across
        # configs only when the spec is semantically identical, which is
        # the cache-hit case we want.
        self._display_id_index = {spec.id: signal_content_key(spec) for spec in config.signals}
        new_specs = [
            spec
            for spec in config.signals
            if signal_content_key(spec) not in self._activations_by_content_key
        ]

        # 2) Fetch activation_dates for new specs (batched).
        if new_specs:
            self._fetch_activation_dates_chunked(new_specs)

        # 3) Fetch returns + regime_label for the union of THIS config's
        # activation dates (only the dates we'll actually query). Skip any
        # date already loaded.
        config_keys = (signal_content_key(s) for s in config.signals)
        all_activations: set[date] = set()
        for key in config_keys:
            cached = self._activations_by_content_key.get(key)
            if cached is not None:
                all_activations.update(cached)
        missing_dates = tuple(sorted(all_activations - self._returns.keys()))
        if missing_dates and config.signals:
            self._fetch_window_for_dates(missing_dates, config.signals[0])

    # ------------------------------------------------------------------
    # FeatureCache Protocol methods
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
        if content_key not in self._activations_by_content_key:
            msg = (
                f"activation_dates: content_key={content_key!r} for "
                f"signal_id={signal_id!r} missing from Crucible response; "
                "the prefetch may have failed silently."
            )
            raise KeyError(msg)
        return self._activations_by_content_key[content_key]

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        """Return whatever returns we have for the requested dates.

        Missing dates are silently dropped (not all calendar days are
        trading days; not all queried dates have been prefetched). The
        callers (permutation_test passes the full window; regime_exposure
        passes only activations) tolerate shorter result maps.
        """
        return {d: self._returns[d] for d in dates if d in self._returns}

    def regime_label(self, d: date) -> Regime:
        """Return the regime for `d`; default to "low_vol" when not loaded.

        Crucible's regime classifier produces labels for trading days only.
        Activation dates that fall on non-classified days (rare) get the
        defensive "low_vol" default rather than crashing the filter.
        """
        return self._regimes.get(d, "low_vol")


__all__ = ["CrucibleFeatureCache"]
