"""Refutation-registry consumer — routes generation mass off proven-dead cells (D320).

WHY: Crucible maintains a refutation registry (`docs/refutations.yaml`, published
to `~/optbt_data/exports/refutations_*.json`) of regions its gate has proven
dead for the v1 long-options grammar. Until now Forge kept enumerating those
regions — it never consumed the refutations — so the two systems could sweep the
same dead cell forever, and the wasted draws inflated the search-multiplicity tax
(the D310 `search_n_trials` stamp → a higher DSR hurdle). This module closes the
loop: it reads the registry and produces sampler-ready effects that deprioritize
or blocklist the bound cells, freeing budget for live regions.

SPLIT OF AUTHORITY (hard rule #2 — we never invent Crucible's semantics):

  * the EXPORT is the live authority on whether an entry is still active and what
    its `generation_effect` verb is (blocklist / deprioritize / none). We read it
    via ``crucible_contracts.load_refutations_from_export`` (the blessed path) and
    fail OPEN — a missing / stale / corrupt registry, or an unknown effect verb
    (the 1.28.0 `literal_error` scar), yields NO effect (byte-identical);
  * the hand-authored ``BINDINGS`` table is the authority on which Forge DRAW each
    entry maps to (our D313 mapping). Edited ONLY with a D-entry, like the sampler
    pins and the campaign registry. An entry with no binding routes nothing.

Self-healing: if Crucible downgrades an entry to `none` or withdraws it, the
effect vanishes at the next read. Only three of the 28 entries have live
suppressible mass and a binding; the rest are Class-A (already structural our
side, mass 0) and map to nothing.

The resolved ``RefutationEffects`` is threaded into ``sample_config`` /
``enumerate_candidates`` as an optional input (None = byte-identical, like the
yield-map weights); the daemon reads the export and passes it. A stable
``refutation_fingerprint`` (over the ACTIVE effects, not the raw file) folds into
``enumeration_inputs_hash`` so each batch's identity tracks what shaped its draw
(hard rule #6). Kill-switch: ``FORGE_REFUTATION_GUARD=off`` → empty effects.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from crucible_contracts import load_refutations_from_export

# ---------------------------------------------------------------------------
# Tunables (operator-facing)
# ---------------------------------------------------------------------------

# A `deprioritize` cell keeps this fraction of its natural draw share — still
# explorable (the sampler's exploration floors keep it alive; `blocklist` is the
# hard version). Quarter-share matches the exploration-floor philosophy.
DEPRIORITIZE_WEIGHT: float = 0.25

# `deep-itm-directional` (blocklist): the refuted region is delta_target >= 0.50
# (P3 caps at 0.55; the ladder is sampled at exactly 0.50). Clip the P3 upper
# bound to strictly below 0.50 — the 0.23-0.35 default/interior is untouched.
_DELTA_CLIP_UPPER: float = 0.499

# Effect verbs that ROUTE supply. Anything else (`none`, unknown, missing) is
# inactive — the fail-open posture (the 1.28.0 literal_error scar).
_ACTIONABLE_EFFECTS: frozenset[str] = frozenset({"blocklist", "deprioritize"})

_MR_HYPOTHESIS = "mean_reversion"
_VE_HYPOTHESIS = "volatility_event"
_HURST_GATE = "hurst"

_GUARD_ENV = "FORGE_REFUTATION_GUARD"


BindingKind = Literal[
    "deprioritize_regime_gate",
    "clip_delta",
    "deprioritize_underlying_class",
]


@dataclass(frozen=True, slots=True)
class RefutationBinding:
    """One entry-id → Forge-draw binding. Hand-authored (D313 mapping), edited
    only with a D-entry. ``kind`` selects the mechanism; the other fields
    parameterize it."""

    entry_id: str
    kind: BindingKind
    hypothesis: str | None = None
    gate_id: str | None = None
    delta_clip_upper: float | None = None


# THE BINDING TABLE — our D313 mapping. Only the three Class-B entries with live
# suppressible mass. Edit ONLY with a D-entry.
BINDINGS: tuple[RefutationBinding, ...] = (
    # hurst-mr-conditioner: MR x hurst converts at ~1/7th the MR baseline.
    # SCOPE GUARD (load-bearing): MR-ONLY — trend x hurst is ABOVE its baseline
    # and one of our top yield cells; a blanket hurst blocklist would destroy it.
    RefutationBinding(
        entry_id="hurst-mr-conditioner",
        kind="deprioritize_regime_gate",
        hypothesis=_MR_HYPOTHESIS,
        gate_id=_HURST_GATE,
    ),
    # deep-itm-directional (blocklist): the delta_target >= 0.50 sliver, any
    # hypothesis. Wiring = clip the P3 upper bound below 0.50.
    RefutationBinding(
        entry_id="deep-itm-directional",
        kind="clip_delta",
        delta_clip_upper=_DELTA_CLIP_UPPER,
    ),
    # broad-index-vol-event: INDEX/ETF half only. The single-name half is
    # DEFERRED — it feeds Crucible's ve-solo-density unlock, which needs the
    # single-name ve supply this would otherwise suppress. So this only ever
    # deprioritizes the DIVERSIFIED underlying class for ve.
    RefutationBinding(
        entry_id="broad-index-vol-event",
        kind="deprioritize_underlying_class",
        hypothesis=_VE_HYPOTHESIS,
    ),
)


@dataclass(frozen=True, slots=True)
class RefutationEffects:
    """Resolved, sampler-ready refutation effects. Every field defaults to the
    no-op value, so an empty instance is byte-identical when threaded."""

    deprioritized_regime_gates: Mapping[str, frozenset[str]] = field(default_factory=dict)
    delta_upper_clip: float | None = None
    deprioritize_diversified_hypotheses: frozenset[str] = frozenset()
    deprioritize_weight: float = DEPRIORITIZE_WEIGHT
    active_entry_ids: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (
            self.deprioritized_regime_gates
            or self.delta_upper_clip is not None
            or self.deprioritize_diversified_hypotheses
        )


def _guard_enabled() -> bool:
    """``FORGE_REFUTATION_GUARD`` kill-switch — default ON; exactly ``off``
    disables (empty effects, byte-identical)."""
    return os.environ.get(_GUARD_ENV, "on").strip().lower() != "off"


def _load_entries(exports_dir: Path | None) -> tuple[dict[str, Any], ...]:
    """Read the newest refutations export, fail OPEN (empty) on any error —
    missing / stale / corrupt registry must never crash or alter the draw."""
    if exports_dir is None:
        exports_dir = Path.home() / "optbt_data" / "exports"
    try:
        return load_refutations_from_export(exports_dir)
    except Exception:  # fail-open is the whole point (missing / stale / corrupt)
        return ()


def _active_bindings(
    entries: Sequence[Mapping[str, Any]],
) -> list[RefutationBinding]:
    """Bindings whose export entry is present AND carries an actionable effect
    verb. Order follows ``BINDINGS`` (deterministic)."""
    by_id = {str(e.get("id")): e for e in entries}
    active: list[RefutationBinding] = []
    for binding in BINDINGS:
        entry = by_id.get(binding.entry_id)
        if entry is None:
            continue
        if str(entry.get("generation_effect")) in _ACTIONABLE_EFFECTS:
            active.append(binding)
    return active


def _effects_from_bindings(active: Sequence[RefutationBinding]) -> RefutationEffects:
    regime: dict[str, frozenset[str]] = {}
    delta_clip: float | None = None
    diversified: set[str] = set()
    for binding in active:
        if binding.kind == "deprioritize_regime_gate" and binding.hypothesis and binding.gate_id:
            regime[binding.hypothesis] = regime.get(binding.hypothesis, frozenset()) | frozenset(
                {binding.gate_id}
            )
        elif binding.kind == "clip_delta" and binding.delta_clip_upper is not None:
            delta_clip = (
                binding.delta_clip_upper
                if delta_clip is None
                else min(delta_clip, binding.delta_clip_upper)
            )
        elif binding.kind == "deprioritize_underlying_class" and binding.hypothesis:
            diversified.add(binding.hypothesis)
    return RefutationEffects(
        deprioritized_regime_gates=regime,
        delta_upper_clip=delta_clip,
        deprioritize_diversified_hypotheses=frozenset(diversified),
        active_entry_ids=tuple(b.entry_id for b in active),
    )


def resolve_effects(
    *,
    exports_dir: Path | None = None,
    entries: Sequence[Mapping[str, Any]] | None = None,
) -> RefutationEffects:
    """Resolve the live refutation registry into sampler-ready effects.

    Reads the newest export (fail-open) unless ``entries`` is supplied (tests).
    Respects the ``FORGE_REFUTATION_GUARD`` kill-switch. Empty result =
    byte-identical draw.
    """
    if not _guard_enabled():
        return RefutationEffects()
    if entries is None:
        entries = _load_entries(exports_dir)
    return _effects_from_bindings(_active_bindings(entries))


def refutation_fingerprint(
    *,
    exports_dir: Path | None = None,
    entries: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Stable fingerprint over the ACTIVE effects (not the raw file), for
    ``enumeration_inputs_hash`` (hard rule #6). Empty string when no effect is
    active — so the recorded batch identity stays byte-identical to the
    guard-off / cold-registry case. Prose-only amendments (claim/evidence) that
    do not change any bound effect do NOT change this."""
    eff = resolve_effects(exports_dir=exports_dir, entries=entries)
    if eff.is_empty():
        return ""
    parts = [f"refutations:w={eff.deprioritize_weight}"]
    for hyp in sorted(eff.deprioritized_regime_gates):
        gates = ",".join(sorted(eff.deprioritized_regime_gates[hyp]))
        parts.append(f"regime:{hyp}:{gates}")
    if eff.delta_upper_clip is not None:
        parts.append(f"delta_clip:{eff.delta_upper_clip}")
    for hyp in sorted(eff.deprioritize_diversified_hypotheses):
        parts.append(f"diversified:{hyp}")
    canonical = "|".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "BINDINGS",
    "DEPRIORITIZE_WEIGHT",
    "BindingKind",
    "RefutationBinding",
    "RefutationEffects",
    "refutation_fingerprint",
    "resolve_effects",
]
