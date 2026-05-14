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
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast

from crucible_contracts import (
    DEFAULT_DATA_HISTORY_DAYS,
    DEFAULT_UNDERLYING,
    FeatureCacheClient,
    StrategyConfig,
    signal_content_key,
)

if TYPE_CHECKING:
    from crucible_contracts import Regime


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

    def _window_dates(self) -> tuple[date, ...]:
        return tuple(
            self._data_start_date + timedelta(days=i) for i in range(self._data_history_days)
        )

    def prefetch_for_config(self, config: StrategyConfig) -> None:
        """Pre-populate the cache for one config's signals.

        Per-config flow:
          1. Rebuild `_display_id_index` from this config's specs so
             `activation_dates(spec.id)` resolves to the right content key
             (the enumerator reuses spec.id strings across configs).
          2. Fetch any specs whose content_key isn't in the cross-config
             cache — a Crucible round-trip per new semantic spec, not per
             enumeration.
          3. On first call only, fetch window-wide returns + regime_label
             (signal-independent; reused for the lifetime of the cache).
        """
        # 1) Rebuild the per-config index. content_keys collide across
        # configs only when the spec is semantically identical, which is
        # the cache-hit case we want.
        self._display_id_index = {
            spec.id: signal_content_key(spec) for spec in config.signals
        }
        new_specs = [
            spec
            for spec in config.signals
            if signal_content_key(spec) not in self._activations_by_content_key
        ]

        # Window data (returns + regime_label) is signal-independent; load once.
        if not self._window_loaded and config.signals:
            sentinel = (config.signals[0],)
            window_response = self._client.get_features(
                signals=sentinel,
                feature_names=("returns", "regime_label"),
                dates=self._window_dates(),
                data_history_days=self._data_history_days,
                underlying=self._underlying,
            )
            # Returns/regimes are global; take whichever signal entry is present.
            for feature_map in window_response.features.values():
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

        if not new_specs:
            return

        # Per-signal activation_dates fetch (batched across new specs).
        response = self._client.get_features(
            signals=tuple(new_specs),
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
        out: dict[date, float] = {}
        for d in dates:
            if d not in self._returns:
                msg = (
                    f"returns: date={d.isoformat()} not prefetched; "
                    "window data is loaded on first prefetch_for_config call."
                )
                raise KeyError(msg)
            out[d] = self._returns[d]
        return out

    def regime_label(self, d: date) -> Regime:
        if d not in self._regimes:
            msg = (
                f"regime_label: date={d.isoformat()} not prefetched; "
                "window data is loaded on first prefetch_for_config call."
            )
            raise KeyError(msg)
        return self._regimes[d]


__all__ = ["CrucibleFeatureCache"]
