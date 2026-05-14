"""Stub for the feature-cache module.

Placeholder so `forge.prefilters.types.FilterContext`'s `TYPE_CHECKING` import
resolves under `mypy --strict`. Phase 3 module 2 (task #30) replaces this with
the full `FeatureCache` Protocol + `SyntheticFeatureCache` implementation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class FeatureCache(Protocol):
    """Read-only historical feature data. Phase 3 module 2 fills the shape."""

    data_history_days: int

    def activation_dates(self, signal_id: str) -> frozenset[date]: ...

    def returns(self, dates: Iterable[date]) -> Mapping[date, float]: ...

    def regime_label(self, d: date) -> str: ...


__all__ = ["FeatureCache"]
