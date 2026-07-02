"""Invariant guards for the Layer-2 orthogonal-family floor-lift.

The decorrelated-supply lever (docs/proposals/orthogonal-family-supply-for-pbo.md
§3 Layer 2) is an A/B feedback-change that MUST be byte-identical when OFF
(hard rule #6: same grammar_version/registry_hash/seed → same emitted sequence).
Two independent guards enforce OFF-by-default:

  1. The env flag `FORGE_ORTHOGONAL_FAMILY_FLOOR` defaults to empty → the parse
     helper returns `{}` → the loop skips the lift call entirely.
  2. Even if the lift IS called with an empty map, it returns weights whose
     numeric values equal the input exactly. The sampler's family draw is a
     pure function of those values (`rng.choices(..., weights=…)`), so an
     identical-valued map preserves the byte-identical draw sequence.

A regression that flips the default ON, mutates the caller's map, or perturbs
values on the empty-map path breaks one of these and fails here before it can
silently change production enumeration.
"""

from __future__ import annotations

import pytest

from forge.cli.main import _orthogonal_family_floors
from forge.feedback.rejection_weights import apply_orthogonal_family_floor


def test_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the env unset, the lever is inert (empty floor map)."""
    monkeypatch.delenv("FORGE_ORTHOGONAL_FAMILY_FLOOR", raising=False)
    assert _orthogonal_family_floors() == {}


def test_empty_map_is_byte_identical_cold_path() -> None:
    """Empty floor map → value-identical weights (a copy, never a mutation).

    This is the rule-#6 guard: identical numeric weights ⇒ identical sampler
    family-draw sequence for the same seed."""
    raw = {
        "trend_continuation": 1.0,
        "mean_reversion": 0.172,
        "regime_arbitrage": 0.091,
        "relative_value": 0.197,
        "volatility_event": 0.050,
        "event_momentum": 0.210,
    }
    out = apply_orthogonal_family_floor(raw, {})
    assert out == raw
    assert out is not raw
