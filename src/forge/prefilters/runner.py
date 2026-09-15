"""One battery builder for every caller (Batch 6 A1).

WHY: the weekly campaign (`campaign/run.py`) and the `forge prefilter` diagnosis command each
assembled a `FilterContext` by hand — same fields, same seed-derivation, same prefetch idiom —
so a change to what the battery reads (a new prior, a calibration key) had to land twice and
could drift. This module is the single place that knows how a context is built and how a batch
is run through the filters. Byte-identical to both former call sites: the same `rng_factory`
(`SeedHierarchy(seed).rng`), the same empty priors when no DB is given, the same
`prefetch_for_batch` then per-config `run_battery` order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from forge.core.seed import SeedHierarchy
from forge.feedback.trade_rate_priors import load_trade_rate_priors
from forge.persistence.fingerprints import load_prior_structural_fingerprints
from forge.prefilters.battery import default_filters, run_battery
from forge.prefilters.types import FilterContext

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.feedback.trade_rate_priors import BucketKey, BucketStats
    from forge.prefilters.calibration import Calibration
    from forge.prefilters.types import Filter, PreFilterReport


def build_filter_context(
    *,
    registry: RegistrySnapshot,
    seed: int,
    calibration: Calibration,
    feature_cache: object,
    forge_db_path: Path | None = None,
) -> FilterContext:
    """The per-batch `FilterContext`.

    With a `forge_db_path` the context carries what the production battery needs from Forge's
    own ledger: prior structural fingerprints (the novelty dedup, D043) and the expected-trades
    priors (D076). Without one (the offline `forge prefilter` preview) both are empty, exactly as
    that command always built them.
    """
    if forge_db_path is None:
        fingerprints: frozenset[str] = frozenset()
        priors: Mapping[BucketKey, BucketStats] = MappingProxyType({})
    else:
        fingerprints = load_prior_structural_fingerprints(forge_db_path)
        priors = MappingProxyType(
            dict(
                load_trade_rate_priors(
                    forge_db_path,
                    registry,
                    min_trades=calibration.expected_trade_count.min_trades,
                )
            )
        )
    return FilterContext(
        registry=registry,
        feature_cache=feature_cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=SeedHierarchy(seed).rng,
        prior_structural_fingerprints=fingerprints,
        trade_rate_priors=priors,
    )


def run_battery_over(
    configs: Sequence[StrategyConfig],
    ctx: FilterContext,
    filters: Iterable[Filter] | None = None,
) -> list[PreFilterReport]:
    """Prefetch the batch when the cache supports it, then run every config through the
    battery in order. One report per config, in the caller's order."""
    prefetch = getattr(ctx.feature_cache, "prefetch_for_batch", None)
    if callable(prefetch):
        prefetch(list(configs))
    chosen = tuple(filters) if filters is not None else default_filters()
    return [run_battery(cfg, ctx, chosen) for cfg in configs]


__all__ = ["build_filter_context", "run_battery_over"]
