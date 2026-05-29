"""forge.enumeration — Phase 2 grammar-valid config enumeration.

Public API:

- ``enumerate_candidates(grammar, registry, seed, *, max_candidates)`` —
  lazy generator; yields ``StrategyConfig`` instances grammar-valid by
  construction (§4.2's CSP).
- ``build_search_space(grammar, registry)`` — pre-resolves the CSP
  coordinate space (variables + domains). Useful for callers that want
  to inspect the resolved enumeration scope without iterating.
- ``registry_hash(snapshot)`` — content hash of a ``RegistrySnapshot``;
  the registry-side identifier in the §13.1 determinism triple
  ``(grammar_version, registry_hash, seed)``.
- ``EnumerationCapped`` — raised when the iterator can't reach
  ``max_candidates`` within its retry budget.
- ``SamplerError`` — raised by the inner sampler when no grammar-valid
  config can be built from the current registry slice.
"""

from __future__ import annotations

from forge.enumeration.indicator_thresholds import auto_tightenings_fingerprint
from forge.enumeration.iterator import EnumerationCapped, enumerate_candidates
from forge.enumeration.registry_fingerprint import registry_hash
from forge.enumeration.sampler import SamplerError, sample_config, universe_fingerprint
from forge.enumeration.search_space import SearchSpace, build_search_space


def enumeration_inputs_hash() -> str:
    """H-3: combined fingerprint of the enumeration-shadowing inputs that
    `registry_hash`/`grammar_version` don't capture — the auto-tightenings YAML
    (D073) and the universe pool (D078). Folded into `mint_batch_id` +
    `batch_summaries` so the recorded identity tracks everything that determines
    the enumerated config sequence (hard rule #6)."""
    return f"{auto_tightenings_fingerprint()}|{universe_fingerprint()}"


__all__ = [
    "EnumerationCapped",
    "SamplerError",
    "SearchSpace",
    "auto_tightenings_fingerprint",
    "build_search_space",
    "enumerate_candidates",
    "enumeration_inputs_hash",
    "registry_hash",
    "sample_config",
    "universe_fingerprint",
]
