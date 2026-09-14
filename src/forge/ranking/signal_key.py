"""Content-hash similarity key for SignalSpecs — re-exported from contracts.

The implementation lived here through Phase 5; contracts v1.9.0 promoted it
to `crucible_contracts.signal_content_key` so Forge (enumerator + ranker)
and Crucible (feature-cache lookup) compute identical keys.

This module remains as a thin alias for backward compatibility — Forge's
existing callers (`prior_promotion.py`, `diversifier.py`) keep importing
`content_key` from here without churn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crucible_contracts import signal_content_key as content_key

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig


def signal_keys(config: StrategyConfig) -> frozenset[str]:
    """Content-hash keys of a config's signals — the similarity vocabulary (D024/D10).

    Content keys, not `signal.id`, so signals with identical content but
    different id strings count as the same (honest cross-batch proximity).
    One home for the diversifier, the prior-promotion factor, and the weekly
    campaign's book legs and challenger gate (Batch 5 prep).
    """
    return frozenset(content_key(s) for s in config.signals)


def jaccard_signal_keys(a: StrategyConfig, b: StrategyConfig) -> float:
    """Jaccard overlap of two configs' signal content-keys (D024/D10).

    `1.0` for identical sets, `0.0` for disjoint sets or when either config has
    no signals (pre-filters reject those, but the metric stays defined).
    """
    a_keys = signal_keys(a)
    b_keys = signal_keys(b)
    if not a_keys or not b_keys:
        return 0.0
    return len(a_keys & b_keys) / len(a_keys | b_keys)


__all__ = ["content_key", "jaccard_signal_keys", "signal_keys"]
