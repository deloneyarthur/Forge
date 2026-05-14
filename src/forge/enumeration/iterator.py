"""Phase 2 public enumeration API.

``enumerate_candidates(grammar, registry, seed, *, max_candidates)`` is a
lazy generator that yields grammar-valid ``StrategyConfig``s by sampling
the §4.2 CSP coordinate space. Each candidate is built by the sampler
and validated by the Phase 1 validator as a safety net (closure-plan
path (a)).

Determinism contract — §13.1 / CLAUDE.md hard rule #6: the sequence
yielded for ``(grammar_version, registry_hash, seed)`` is byte-identical
across runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from forge.core.seed import SeedHierarchy
from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import validate

if TYPE_CHECKING:
    from collections import Counter
    from collections.abc import Iterator

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar.models import Grammar


_logger = structlog.get_logger(__name__)

# Generous retry budget: most v1-fixture slices produce 0% rejections,
# but a sparser future registry may need headroom. Hitting the cap is a
# loud signal that the grammar / registry slice is too tight.
_MAX_ATTEMPTS_FACTOR = 100


class EnumerationCapped(RuntimeError):
    """Raised when the iterator exhausts its retry budget without yielding
    ``max_candidates`` configs. Indicates a sparsely-satisfiable
    grammar / registry slice — surface to the operator."""


def enumerate_candidates(
    grammar: Grammar,
    registry: RegistrySnapshot,
    seed: int,
    *,
    max_candidates: int,
    rejection_counter: Counter[str] | None = None,
) -> Iterator[StrategyConfig]:
    """Yield up to ``max_candidates`` grammar-valid configs lazily.

    If ``rejection_counter`` is supplied, the iterator mutates it with
    rule-id-keyed counts as candidates are rejected. The counter survives
    iterator exhaustion so callers can read stats after consumption.

    Raises ``ValueError`` if ``max_candidates <= 0``.
    Raises ``EnumerationCapped`` if the retry budget is exhausted.
    """
    if max_candidates <= 0:
        msg = f"max_candidates must be > 0, got {max_candidates}"
        raise ValueError(msg)

    space = build_search_space(grammar, registry)
    rng = SeedHierarchy(seed).rng("enumeration")

    yielded = 0
    attempts = 0
    max_attempts = max_candidates * _MAX_ATTEMPTS_FACTOR

    while yielded < max_candidates:
        if attempts >= max_attempts:
            msg = (
                f"enumeration capped at {yielded}/{max_candidates} after "
                f"{attempts} attempts; grammar/registry slice may be too sparse"
            )
            _logger.warning(
                "enumeration_capped",
                yielded=yielded,
                target=max_candidates,
                attempts=attempts,
            )
            raise EnumerationCapped(msg)
        attempts += 1

        try:
            cfg = sample_config(space, registry, rng)
        except SamplerError as exc:
            if rejection_counter is not None:
                rejection_counter["sampler"] += 1
            _logger.debug("sample_rejected", reason=str(exc))
            continue

        result = validate(cfg, grammar, registry)
        if not result.valid:
            if rejection_counter is not None:
                for err in result.errors:
                    # Validator error format: "RULE_ID: detail"; rule id is
                    # the prefix before the first colon.
                    rule_id = err.split(":", 1)[0].strip()
                    rejection_counter[rule_id] += 1
            _logger.debug("validator_rejected", errors=result.errors)
            continue

        yielded += 1
        yield cfg
