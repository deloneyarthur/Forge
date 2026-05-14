"""Content-hash similarity key for SignalSpecs — re-exported from contracts.

The implementation lived here through Phase 5; contracts v1.9.0 promoted it
to `crucible_contracts.signal_content_key` so Forge (enumerator + ranker)
and Crucible (feature-cache lookup) compute identical keys.

This module remains as a thin alias for backward compatibility — Forge's
existing callers (`prior_promotion.py`, `diversifier.py`) keep importing
`content_key` from here without churn.
"""

from __future__ import annotations

from crucible_contracts import signal_content_key as content_key

__all__ = ["content_key"]
