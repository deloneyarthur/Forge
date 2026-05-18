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

import math
from typing import TYPE_CHECKING

import structlog

from forge.core.seed import SeedHierarchy
from forge.enumeration.sampler import SamplerError, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import validate

if TYPE_CHECKING:
    from collections import Counter
    from collections.abc import Iterator, Mapping

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar.models import Grammar


_logger = structlog.get_logger(__name__)

# Generous retry budget: most v1-fixture slices produce 0% rejections,
# but a sparser future registry may need headroom. Hitting the cap is a
# loud signal that the grammar / registry slice is too tight.
_MAX_ATTEMPTS_FACTOR = 100

# D037 — minimum-fraction floor for stratified hypothesis sampling. Pre-D037
# the Bayesian failure-bias sampler had no diversity floor: with 4020
# historical submissions, two of six hypotheses (`trend_continuation`,
# `mean_reversion`) had 0 and 1 picks respectively because the failure-
# weights compounded with CSP dead-end retries to silently exclude them.
# Default is 0.0 (legacy / test fixtures with sparse registries assume
# zero stratification); production CLI callers pass `min_hypothesis_fraction
# =_PRODUCTION_MIN_HYPOTHESIS_FRACTION` to opt in. At 0.02 against a
# 5000-candidate enumeration, each samplable hypothesis gets at least
# ~100 forced picks (capped at 50% of budget) before the weighted sampler
# takes over the remaining ~88%.
_DEFAULT_MIN_HYPOTHESIS_FRACTION: float = 0.0
_PRODUCTION_MIN_HYPOTHESIS_FRACTION: float = 0.02


class EnumerationCapped(RuntimeError):
    """Raised when the iterator exhausts its retry budget without yielding
    ``max_candidates`` configs. Indicates a sparsely-satisfiable
    grammar / registry slice — surface to the operator."""


def _compute_stratification_floor(
    max_candidates: int,
    min_hypothesis_fraction: float,
    n_samplable: int,
) -> int:
    """D037 — per-hypothesis forced-pick floor.

    Guarantees stratification never consumes more than 50% of the
    candidate budget (the remaining half is reserved for the weighted
    sampler). For ``max_candidates=5000`` with 6 samplable hypotheses
    and the default 0.02 fraction, returns 100 (i.e., 600 forced /
    4400 weighted). For tiny ``max_candidates`` (e.g., test fixtures
    with max=4) it returns 0 so the cap-on-budget isn't violated.
    """
    if min_hypothesis_fraction <= 0.0 or n_samplable <= 0:
        return 0
    requested = math.ceil(max_candidates * min_hypothesis_fraction)
    # Cap so total forced ≤ 50% of budget; the rest goes to weighted
    # sampling. For 6 hypotheses, cap = max_candidates // 12 per hyp.
    cap = max_candidates // (2 * n_samplable)
    return min(requested, cap)


def enumerate_candidates(  # noqa: PLR0912 — D037 stratification adds branches; refactor would be net harm
    grammar: Grammar,
    registry: RegistrySnapshot,
    seed: int,
    *,
    max_candidates: int,
    rejection_counter: Counter[str] | None = None,
    hypothesis_weights: Mapping[str, float] | None = None,
    min_hypothesis_fraction: float = _DEFAULT_MIN_HYPOTHESIS_FRACTION,
) -> Iterator[StrategyConfig]:
    """Yield up to ``max_candidates`` grammar-valid configs lazily.

    If ``rejection_counter`` is supplied, the iterator mutates it with
    rule-id-keyed counts as candidates are rejected. The counter survives
    iterator exhaustion so callers can read stats after consumption.

    ``min_hypothesis_fraction`` (D037): per-hypothesis floor. The first
    ``ceil(max_candidates * min_hypothesis_fraction) * n_hypotheses``
    yields are forced through a round-robin of samplable hypotheses,
    one per yield, so every hypothesis gets at least
    ``ceil(max_candidates * min_hypothesis_fraction)`` configs.
    After the floor is satisfied, the remaining yields follow
    ``hypothesis_weights`` (or uniform if None).

    Set ``min_hypothesis_fraction=0.0`` to disable stratification
    (legacy / test path).

    Raises ``ValueError`` if ``max_candidates <= 0`` or
    ``min_hypothesis_fraction`` is not in ``[0.0, 1.0]``.
    Raises ``EnumerationCapped`` if the retry budget is exhausted.
    """
    if max_candidates <= 0:
        msg = f"max_candidates must be > 0, got {max_candidates}"
        raise ValueError(msg)
    if not (0.0 <= min_hypothesis_fraction <= 1.0):
        msg = (
            f"min_hypothesis_fraction must be in [0.0, 1.0], "
            f"got {min_hypothesis_fraction}"
        )
        raise ValueError(msg)

    space = build_search_space(grammar, registry)
    rng = SeedHierarchy(seed).rng("enumeration")

    # D037 stratification setup: per-hypothesis quota, sorted name for
    # deterministic rotation order.
    samplable = sorted(
        h
        for h in space.hypotheses
        if space.directional_indicators_by_hypothesis[h]
        and space.regime_indicators_by_hypothesis[h]
    )
    floor_per_hyp = _compute_stratification_floor(
        max_candidates, min_hypothesis_fraction, len(samplable),
    )
    yielded_by_hyp: dict[str, int] = {h: 0 for h in samplable}
    # D037: forced-pick failure cap. If a hypothesis CSP-dead-ends this
    # many times when forced, blacklist it for the rest of the batch
    # so it doesn't starve the weighted-sample path. The hypothesis can
    # still be sampled via the natural weighted draw — it just stops
    # being a forced rotation target. Keeps sparse-registry test
    # fixtures yielding while still giving production batches their
    # diversity floor.
    forced_failures: dict[str, int] = {h: 0 for h in samplable}
    _FORCED_FAILURE_CAP = 20

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

        # D037 forced-hypothesis selection (only while quotas unmet and
        # the hypothesis hasn't tripped the per-batch failure cap).
        # Rotate by `attempts` (not `yielded`) so a hypothesis that CSP-
        # dead-ends doesn't lock the rotation — every retry moves on to
        # the next under-quota hypothesis instead of re-trying the failed
        # one indefinitely.
        forced_hypothesis: str | None = None
        if floor_per_hyp > 0:
            under_quota = [
                h for h in samplable
                if yielded_by_hyp[h] < floor_per_hyp
                and forced_failures[h] < _FORCED_FAILURE_CAP
            ]
            if under_quota:
                forced_hypothesis = under_quota[attempts % len(under_quota)]

        try:
            cfg = sample_config(
                space,
                registry,
                rng,
                hypothesis_weights=hypothesis_weights,
                forced_hypothesis=forced_hypothesis,
            )
        except SamplerError as exc:
            if forced_hypothesis is not None:
                forced_failures[forced_hypothesis] += 1
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
        if cfg.hypothesis in yielded_by_hyp:
            yielded_by_hyp[cfg.hypothesis] += 1
        yield cfg
