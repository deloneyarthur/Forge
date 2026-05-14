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

from forge.enumeration.iterator import EnumerationCapped, enumerate_candidates
from forge.enumeration.registry_fingerprint import registry_hash
from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import SearchSpace, build_search_space

__all__ = [
    "EnumerationCapped",
    "SamplerError",
    "SearchSpace",
    "build_search_space",
    "enumerate_candidates",
    "registry_hash",
    "sample_config",
]
