"""Stub for the calibration module.

Placeholder so `forge.prefilters.types.FilterContext`'s `TYPE_CHECKING` import
resolves under `mypy --strict`. Phase 3 module 3 (task #31) replaces this with
the full loader for `config/prefilter.yaml` + the `propose_adjustment` API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Calibration:
    """Pre-filter battery thresholds. Phase 3 module 3 fills the fields."""
