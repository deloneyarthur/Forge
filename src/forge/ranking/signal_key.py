"""Content-hash similarity key for SignalSpecs (D024/D10).

Phase 3 OQ-4 carried `signal.id` as the similarity key for `jaccard_signal_ids`
and `compute_prior_promotion_proximity`. Phase 5 closes that question:
`content_key(signal)` returns a deterministic SHA-256 prefix derived from
`(type, role, sorted(indicators), canonical(params))`. Two signals with
identical content but different `id` strings produce the same key — which
is what we want for cross-batch diversity / proximity scoring.

The hash output is a 16-char hex prefix (8 bytes, 64 bits). That's the same
truncation `StrategyConfig.config_hash` uses, so the magnitude of collision
risk is identical.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crucible_contracts import SignalSpec


def content_key(signal: SignalSpec) -> str:
    """Deterministic 16-char hex hash of the signal's content fields."""
    payload = {
        "type": signal.type,
        "role": signal.role,
        "indicators": sorted(signal.indicators),
        "params": signal.params,
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


__all__ = ["content_key"]
