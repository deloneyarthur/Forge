"""Feature cache abstraction + synthetic implementation.

Filters 3 / 4 / 6 / 7 (DESIGN.md §5.3) need historical indicator activations,
returns, and per-day regime labels. Crucible's feature cache is the real
source but doesn't exist yet, so Forge defines the Protocol here and ships
a deterministic synthetic implementation. Phase 4/5 wires a concrete
Crucible-backed implementation against the same Protocol.

`SyntheticFeatureCache` is seeded via `forge.core.seed.SeedHierarchy` so all
randomness flows through the blessed RNG path (hard rule #8). The closure
plan calls this the "synthetic feature cache" mirror of D004's synthetic
Crucible runs DB.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Literal, Protocol, runtime_checkable

from forge.core.seed import SeedHierarchy

Regime = Literal["bull", "bear", "low_vol", "high_vol", "trending", "ranging"]

REGIMES: tuple[Regime, ...] = (
    "bull",
    "bear",
    "low_vol",
    "high_vol",
    "trending",
    "ranging",
)


@runtime_checkable
class FeatureCache(Protocol):
    """Read-only historical feature data for the pre-filter battery.

    Implementations: `SyntheticFeatureCache` for Phase 3 testing;
    Crucible-backed in Phase 4/5. Filter authors depend on this Protocol,
    not on either concrete class.
    """

    data_history_days: int

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        """Dates on which the signal would have fired over the cached window."""
        ...

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        """Daily total returns for the requested dates."""
        ...

    def regime_label(self, d: date) -> Regime:
        """One of the six §5.3.6 macro regimes for the given date."""
        ...


class SyntheticFeatureCache:
    """Deterministic synthetic feature cache seeded from a root seed.

    Every output is a pure function of `(root_seed, data_history_days,
    start_date)` and the requested key. Constructed once per batch in
    tests and in the `forge prefilter` CLI demo.
    """

    __slots__ = ("_seed", "_start", "data_history_days")

    def __init__(
        self,
        *,
        root_seed: int,
        data_history_days: int = 1008,
        start_date: date | None = None,
    ) -> None:
        if data_history_days < 1:
            msg = f"data_history_days must be >= 1; got {data_history_days}"
            raise ValueError(msg)
        self.data_history_days = data_history_days
        self._seed = SeedHierarchy(root_seed)
        self._start = start_date or date(2022, 1, 1)

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        rng = self._seed.rng(f"activations:{signal_id}")
        # Density is per-signal so two signals don't all fire at the same rate.
        density = rng.uniform(0.05, 0.40)
        return frozenset(
            self._start + timedelta(days=i)
            for i in range(self.data_history_days)
            if rng.random() < density
        )

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]:
        out: dict[date, float] = {}
        for d in dates:
            rng = self._seed.rng(f"return:{d.isoformat()}")
            out[d] = rng.gauss(0.0, 0.01)
        return out

    def regime_label(self, d: date) -> Regime:
        rng = self._seed.rng(f"regime:{d.isoformat()}")
        return rng.choice(REGIMES)


__all__ = ["REGIMES", "FeatureCache", "Regime", "SyntheticFeatureCache"]
