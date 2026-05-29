"""Pre-filter battery value types and Filter Protocol.

These shapes are the foundation of every Phase 3 filter and the battery
orchestrator. See DESIGN.md §5.4 (PreFilterReport), §5.2 (cost ordering),
and `IMPLEMENTATION_DECISIONS.md` D021 (closure D2 / D5).

- `FilterResult` — one filter's verdict + a unit-interval score + diagnostics.
- `PreFilterReport` — §5.4. `composite_score` stays `None` in Phase 3
  (D021/D2); the Phase 4 ranker fills it via §6.2 weights.
- `FilterContext` — the per-batch bundle every filter reads. Built once,
  immutable, so filter ordering can't leak state between filters.
- `Filter` — `@runtime_checkable` Protocol the battery iterates over in
  `cost_tier` order with short-circuit on first `passed=False`.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.feedback.trade_rate_priors import BucketKey, BucketStats
    from forge.prefilters.calibration import Calibration
    from forge.prefilters.feature_cache import FeatureCache


class FeatureDataUnavailable(RuntimeError):
    """Raised when a feature-cache window is structurally unavailable for the
    active underlying (M-5, audit 2026-05-29).

    Distinguishes a *data-availability* failure (thin Tier-2 underlying, transient
    writer state, empty window response) from a *signal-quality* FAIL. The battery
    catches this and produces a `PreFilterReport(data_unavailable=True)` so the
    config isn't mislabeled as a genuine rejection — which would pollute
    `pre_filter_logs` and the D076 empirical-prior buckets (same silent-degradation
    class as the D080 incident, at per-underlying granularity).
    """


def _empty_details() -> Mapping[str, Any]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class FilterResult:
    """One filter's output for one config.

    `score` is in `[0, 1]`: higher means "more confident this is a healthy
    candidate against this filter's criterion." `details` carries
    filter-specific diagnostics for `pre_filter_logs` (Phase 4 wires the
    write).
    """

    passed: bool
    score: float
    details: Mapping[str, Any] = field(default_factory=_empty_details)

    def __post_init__(self) -> None:
        if math.isnan(self.score) or math.isinf(self.score) or not (0.0 <= self.score <= 1.0):
            msg = f"FilterResult.score must be in [0, 1]; got {self.score!r}"
            raise ValueError(msg)
        if not isinstance(self.details, MappingProxyType):
            # Freeze user-supplied dicts so post-hoc mutation can't drift
            # the report from what the filter actually computed.
            object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True, slots=True)
class PreFilterReport:
    """Full pre-filter battery output for one config. §5.4.

    `composite_score` is `None` until the Phase 4 ranker computes the
    §6.2 weighted sum from `filter_results`. Treating a Phase 3 report
    as if it were ranker output is therefore a type-level mistake.
    """

    config: StrategyConfig
    passed: bool
    filter_results: Mapping[str, FilterResult]
    diagnostic_notes: tuple[str, ...]
    composite_score: float | None = None
    # M-5 (audit 2026-05-29): True when the battery short-circuited because the
    # feature-cache window was unavailable for this config's underlying — a
    # data-availability verdict distinct from a signal-quality FAIL. These
    # reports are bucketed separately in the rejection histogram and excluded
    # from `pre_filter_logs` so thin-data false-rejections don't pollute the
    # D076 priors.
    data_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class FilterContext:
    """Per-batch state read by every filter. Built by the battery once.

    `rng_factory` returns a `random.Random` seeded by name; filter authors
    request named children (e.g. `ctx.rng_factory("permutation_test")`) so
    seed-derivation stays inside `forge.core.seed` per hard rule #8.

    `prior_firing_dates` maps a prior config's hash to the set of dates
    on which its directional signal fired. The novelty filter (§5.3.5)
    consumes this to compute Jaccard overlap against the candidate.

    `prior_structural_fingerprints` (T2.7 / D043) is the set of
    structural-fingerprint hashes of prior tested candidates. NoveltyFilter
    rejects the candidate when its fingerprint exactly matches a prior —
    catches "parameter-only variations" that the temporal Jaccard check
    misses (different threshold, same structure → identical firings on
    some bars, different on others; structural fingerprint captures the
    intent that's invariant to parameter scan). Defaults to empty
    frozenset for back-compat with callers that don't yet wire structural
    history.
    """

    registry: RegistrySnapshot
    feature_cache: FeatureCache
    prior_config_hashes: frozenset[str]
    prior_firing_dates: Mapping[str, frozenset[date]]
    calibration: Calibration
    rng_factory: Callable[[str], random.Random]
    prior_structural_fingerprints: frozenset[str] = field(default_factory=frozenset)
    # D076 / Q16 — per-(hypothesis, dte_bucket, directional_family)
    # gated-cohort posteriors consumed by `ExpectedTradesFilter`. Empty
    # mapping (default) → filter falls back to legacy activations
    # heuristic for every config. Populated by `cli/main.py` from the
    # gated_runs export, mirroring `_load_hypothesis_weights`.
    trade_rate_priors: Mapping[BucketKey, BucketStats] = field(
        default_factory=lambda: MappingProxyType({}),
    )


@runtime_checkable
class Filter(Protocol):
    """A pre-filter battery member.

    `cost_tier` is the §5.2 ordinal (1..7 ascending). The battery sorts
    on it and short-circuits on the first `passed=False` result.
    """

    name: str
    cost_tier: int

    def apply(self, config: StrategyConfig, ctx: FilterContext) -> FilterResult: ...


__all__ = [
    "FeatureDataUnavailable",
    "Filter",
    "FilterContext",
    "FilterResult",
    "PreFilterReport",
]
