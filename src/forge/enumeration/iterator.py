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
from forge.enumeration.search_space import (
    NON_ENUMERABLE_HYPOTHESES,
    XSECT_ONLY_HYPOTHESES,
    build_search_space,
)
from forge.grammar import validate

if TYPE_CHECKING:
    from collections import Counter
    from collections.abc import Iterator, Mapping

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.enumeration.refutations import RefutationEffects
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

# v47 (D328) — single-name trend/MR retirement (emission-policy filter).
# Crucible's consumption read (FORGE_single_name_trend_mr_retirement_read): 0 of
# 106 assemblies ever selected a single-name trend or MR component (363 xsect-
# trend / 142 xsect-MR slots vs 0 single-name). Confluence combiner == single-
# name (a pinned underlying); cross_sectional_rank == xsect == the converting
# core, kept. The momentum/capitulation cell is EXEMPTED per
# FORGE_capitulation_exempt_v47 (single-name-only since `momentum` is rank-
# excluded; the program's only positive-slot-delta cell, an un-refuted named
# live successor candidate, with a defined close-out). This filters the DRAWN
# config, never the sampler — `sample_config` stays byte-identical (hard rule
# #6), so the sampler goldens hold; only the yielded set changes (and the
# version bump moves enumeration_inputs_hash). Retirement never touches
# `forced_failures`: trend/MR remain satisfiable via their xsect form, so
# stratification just retries — a confluence draw is not an unsatisfiable slot.
_SINGLE_NAME_EXEMPT_DIRECTIONALS: frozenset[str] = frozenset({"momentum"})  # capitulation
_XSECT_COMBINER_TYPE = "cross_sectional_rank"


def _is_retired_single_name(config: StrategyConfig) -> bool:
    """v47: True for a single-name (confluence) trend/MR config that is retired.

    Kept: xsect (cross_sectional_rank) trend/MR, and the momentum/capitulation
    single-name cell. Every other single-name config in these two hypotheses is
    dropped.
    """
    if config.hypothesis not in XSECT_ONLY_HYPOTHESES:
        return False
    if config.combiner.type == _XSECT_COMBINER_TYPE:
        return False
    directional = next((s.indicators[0] for s in config.signals if s.role == "directional"), None)
    return directional not in _SINGLE_NAME_EXEMPT_DIRECTIONALS


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


def enumerate_candidates(  # noqa: PLR0912, PLR0915 — D037 stratification + v47 filter; refactor would be net harm
    grammar: Grammar,
    registry: RegistrySnapshot,
    seed: int,
    *,
    max_candidates: int,
    rejection_counter: Counter[str] | None = None,
    hypothesis_weights: Mapping[str, float] | None = None,
    regime_weights: Mapping[str, float] | None = None,
    bucket_weights: Mapping[tuple[str, str], float] | None = None,
    directional_bucket_weights: Mapping[tuple[str, str, str], float] | None = None,
    underlying_class_weights: Mapping[str, float] | None = None,
    underlying_name_weights: Mapping[str, float] | None = None,
    rank_combiner_share: Mapping[str, float] | None = None,
    cohort_yield_weights: Mapping[tuple[str, str, str, str], float] | None = None,
    regime_gate_yield_weights: Mapping[tuple[str, str, str, str], float] | None = None,
    refutation_effects: RefutationEffects | None = None,
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

    ``regime_weights`` (D103) is forwarded to the sampler to bias the
    relative_value regime-gate pick toward feedback-learned-good gates;
    None/empty preserves the pre-D103 uniform pick.

    ``bucket_weights`` (D105) is forwarded to the sampler to bias the joint
    (directional, DTE-bucket) pick toward feedback-learned-good
    (hypothesis, dte_bucket) cells; None/empty preserves the pre-D105
    two-step draw byte-identically.

    ``underlying_class_weights`` (D105) is forwarded to the sampler to bias
    the underlying pick by learned class (high-idio-vol vs diversified);
    None/empty preserves the uniform pick byte-identically.

    ``directional_bucket_weights`` / ``underlying_name_weights`` (D106) are
    the hierarchical refinements of the two above — (hypothesis, directional,
    bucket) triples anchored on the pair cell, and per-name weights anchored
    on the class — forwarded to the sampler's fallback chains.

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
        msg = f"min_hypothesis_fraction must be in [0.0, 1.0], got {min_hypothesis_fraction}"
        raise ValueError(msg)

    space = build_search_space(grammar, registry)
    rng = SeedHierarchy(seed).rng("enumeration")

    # D037 stratification setup: per-hypothesis quota, sorted name for
    # deterministic rotation order. D066/D098: exclude non-enumerable
    # hypotheses (overlay-only tail_hedge + disabled regime_arbitrage) so the
    # forced-rotation floor never tries to enumerate them.
    samplable = sorted(
        h
        for h in space.hypotheses
        if h not in NON_ENUMERABLE_HYPOTHESES
        and space.directional_indicators_by_hypothesis[h]
        and space.regime_indicators_by_hypothesis[h]
    )
    floor_per_hyp = _compute_stratification_floor(
        max_candidates,
        min_hypothesis_fraction,
        len(samplable),
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
                h
                for h in samplable
                if yielded_by_hyp[h] < floor_per_hyp and forced_failures[h] < _FORCED_FAILURE_CAP
            ]
            if under_quota:
                forced_hypothesis = under_quota[attempts % len(under_quota)]

        try:
            cfg = sample_config(
                space,
                registry,
                rng,
                hypothesis_weights=hypothesis_weights,
                regime_weights=regime_weights,
                bucket_weights=bucket_weights,
                directional_bucket_weights=directional_bucket_weights,
                underlying_class_weights=underlying_class_weights,
                underlying_name_weights=underlying_name_weights,
                rank_combiner_share=rank_combiner_share,
                cohort_yield_weights=cohort_yield_weights,
                regime_gate_yield_weights=regime_gate_yield_weights,
                refutation_effects=refutation_effects,
                forced_hypothesis=forced_hypothesis,
            )
        except SamplerError as exc:
            if forced_hypothesis is not None:
                forced_failures[forced_hypothesis] += 1
            if rejection_counter is not None:
                rejection_counter["sampler"] += 1
            _logger.debug("sample_rejected", reason=str(exc))
            continue

        # v47 (D328) — drop retired single-name trend/MR (keep xsect + the
        # capitulation exemption). NOT a forced_failures event: the hypothesis
        # is satisfiable via its xsect form, so stratification retries.
        if _is_retired_single_name(cfg):
            if rejection_counter is not None:
                rejection_counter["retired_single_name"] += 1
            _logger.debug("retired_single_name_rejected", hypothesis=cfg.hypothesis)
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
