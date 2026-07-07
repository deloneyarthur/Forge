"""Deploy-time activation smoke-test: does the writer actually COMPUTE a directional?

Motivation (D254 post-mortem). Adopting an indicator clears three gates, and
D236's emission proof only checked the first two:

  1. registered in Crucible's snapshot,
  2. enumerable in Forge (threshold + horizon tables),
  3. **actually computed by Crucible's feature-cache writer** — i.e.
     `get_features(activation_dates)` returns real firings.

`sma_slope`/`ad_slope` passed 1+2 but failed 3 (the §2.1a class: the writer
returns None for every name), so they zero-traded silently — 0/2800 submitted
for ~5h post-deploy, invisible because the sampler DID draw them (the floor
guarantees it) and the prefilter killed 100% at the zero-activation wall.

This module probes gate 3 against the live writer: for a set of directional
indicators, find one enumerated config each, run it on a few high-history names,
and count activations. A directional that fires 0 on EVERY name is INERT and a
grammar bump adopting it is NO-GO. An indicator no enumerated config used is
`unchecked` (we could not probe it — NOT a hard failure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from forge.enumeration import enumerate_candidates
from forge.enumeration.indicator_thresholds import is_threshold_skippable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar import Grammar


class _PrefetchableCache(Protocol):
    """The cache surface this probe needs — prefetch a config's signals, then read
    the directional's activation dates. Both `CrucibleFeatureCache` (live) and a
    test double satisfy it structurally; the read-only `FeatureCache` Protocol the
    filters use does NOT expose `prefetch_for_config` (a concrete lifecycle method)."""

    def prefetch_for_config(self, config: StrategyConfig, /) -> None: ...

    def activation_dates(self, signal_id: str, /) -> frozenset[date]: ...


# The enumerator reuses this spec id for the directional signal of every config
# (`forge.enumeration.sampler`); the feature cache keys activations off it after
# `prefetch_for_config`.
_DIRECTIONAL_SIGNAL_ID = "sig_directional"


@dataclass(frozen=True, slots=True)
class ActivationCheck:
    """One directional indicator's activation-liveness verdict."""

    indicator: str
    # name -> activation count on that underlying (empty when `unchecked`).
    per_name: Mapping[str, int] = field(default_factory=dict)
    ok: bool = False
    # True when no enumerated config used this indicator, so it could not be
    # probed — distinct from a genuine zero-activation INERT verdict.
    unchecked: bool = False

    @property
    def max_activations(self) -> int:
        return max(self.per_name.values(), default=0)


def directional_indicators_to_check(registry: RegistrySnapshot) -> tuple[str, ...]:
    """Registry indicators that Forge can emit as a directional signal (role
    `directional` not threshold-skippable). This is the smoke-test's default
    target set — any of these going inert is a silent-zero-trade hazard."""
    return tuple(
        sorted(
            ind.id
            for ind in registry.indicators
            if not is_threshold_skippable(ind.id, "directional")
        )
    )


def summarize_activation_checks(
    per_indicator: Mapping[str, Mapping[str, int]],
    *,
    indicators: Sequence[str],
    min_activations: int = 1,
) -> list[ActivationCheck]:
    """Turn raw per-(indicator, name) activation counts into verdicts.

    An indicator is OK iff it produced `>= min_activations` on at least one probed
    name. An indicator absent from `per_indicator` (no config found to probe) is
    `unchecked` — reported, but not a hard failure (`has_inert` ignores it).
    """
    checks: list[ActivationCheck] = []
    for ind in indicators:
        counts = per_indicator.get(ind)
        if counts is None:
            checks.append(ActivationCheck(ind, {}, ok=False, unchecked=True))
            continue
        max_acts = max(counts.values(), default=0)
        checks.append(
            ActivationCheck(ind, dict(counts), ok=max_acts >= min_activations, unchecked=False)
        )
    return checks


def has_inert(checks: Sequence[ActivationCheck]) -> bool:
    """True iff any indicator was probed and fired 0 (a genuine writer-inert
    failure). `unchecked` indicators are excluded — they are a WARN, not a NO-GO."""
    return any((not c.ok) and (not c.unchecked) for c in checks)


def probe_directional_activations(
    cache: _PrefetchableCache,
    registry: RegistrySnapshot,
    grammar: Grammar,
    *,
    indicators: Sequence[str],
    names: Sequence[str],
    seed: int = 0,
    max_enumerate: int = 8000,
) -> dict[str, dict[str, int]]:
    """Find one enumerated config per target indicator, run it on each name, and
    count the directional signal's activations from `cache`.

    Enumeration (not hand-built configs) guarantees each probe config is
    grammar-valid; the sampler's exploration floor makes every enumerable
    directional appear within `max_enumerate`. Indicators no config used are
    simply absent from the result (→ `unchecked` in `summarize_activation_checks`).
    """
    targets = set(indicators)
    found: dict[str, StrategyConfig] = {}
    for cfg in enumerate_candidates(grammar, registry, seed=seed, max_candidates=max_enumerate):
        for sig in cfg.signals:
            if sig.role == "directional" and len(sig.indicators) == 1:
                ind = sig.indicators[0]
                if ind in targets and ind not in found:
                    found[ind] = cfg
        if len(found) == len(targets):
            break

    result: dict[str, dict[str, int]] = {}
    for ind, cfg in found.items():
        per_name: dict[str, int] = {}
        for name in names:
            probe_cfg = cfg.model_copy(update={"underlying": name})
            cache.prefetch_for_config(probe_cfg)
            try:
                per_name[name] = len(cache.activation_dates(_DIRECTIONAL_SIGNAL_ID))
            except Exception:
                per_name[name] = 0
        result[ind] = per_name
    return result


__all__ = [
    "ActivationCheck",
    "directional_indicators_to_check",
    "has_inert",
    "probe_directional_activations",
    "summarize_activation_checks",
]
