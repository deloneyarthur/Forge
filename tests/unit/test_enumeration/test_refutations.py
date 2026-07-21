"""Tests for ``forge.enumeration.refutations`` (D320) — the refutation-registry
consumer that routes generation mass away from Crucible-proven-dead cells.

Split of authority (hard rule #2): the EXPORT is the live authority on whether
an entry is still active and its effect verb; the hand-authored BINDINGS table
is the authority on which Forge DRAW each entry binds to (our D313 mapping).
An entry with no binding is unmappable-to-generation and produces no effect;
an entry downgraded to ``none`` or withdrawn self-heals to no effect.
"""

from __future__ import annotations

import pytest

from forge.enumeration.refutations import (
    BINDINGS,
    DEPRIORITIZE_WEIGHT,
    RefutationEffects,
    refutation_fingerprint,
    resolve_effects,
)


def _entry(entry_id: str, effect: str, status: str = "refuted") -> dict[str, object]:
    return {
        "id": entry_id,
        "status": status,
        "generation_effect": effect,
        "scope": "test",
        "unlock": "",
    }


# ---------------------------------------------------------------------------
# The binding table — our D313 mapping, its three live-mass entries
# ---------------------------------------------------------------------------


def test_binding_table_covers_the_three_class_b_entries() -> None:
    ids = {b.entry_id for b in BINDINGS}
    assert ids == {
        "hurst-mr-conditioner",
        "deep-itm-directional",
        "broad-index-vol-event",
    }


def test_hurst_binding_is_mr_scoped() -> None:
    """The scope guard that matters: hurst deprioritize must be MR-ONLY —
    trend x hurst is ABOVE baseline and one of our top yield cells."""
    b = next(b for b in BINDINGS if b.entry_id == "hurst-mr-conditioner")
    assert b.kind == "deprioritize_regime_gate"
    assert b.hypothesis == "mean_reversion"
    assert b.gate_id == "hurst"


# ---------------------------------------------------------------------------
# resolve_effects — the export is the live authority
# ---------------------------------------------------------------------------


def _resolve(entries: list[dict[str, object]]) -> RefutationEffects:
    return resolve_effects(entries=tuple(entries))


def test_all_three_active_produces_all_effects() -> None:
    eff = _resolve(
        [
            _entry("hurst-mr-conditioner", "deprioritize"),
            _entry("deep-itm-directional", "blocklist"),
            _entry("broad-index-vol-event", "deprioritize"),
        ]
    )
    assert eff.deprioritized_regime_gates == {"mean_reversion": frozenset({"hurst"})}
    assert eff.delta_upper_clip is not None
    assert eff.delta_upper_clip < 0.50
    assert eff.deprioritize_diversified_hypotheses == frozenset({"volatility_event"})
    assert set(eff.active_entry_ids) == {
        "hurst-mr-conditioner",
        "deep-itm-directional",
        "broad-index-vol-event",
    }
    assert not eff.is_empty()


def test_effect_none_or_withdrawn_self_heals() -> None:
    # downgraded to 'none' -> inactive
    assert _resolve([_entry("hurst-mr-conditioner", "none")]).is_empty()
    # withdrawn entirely (absent from export) -> inactive
    assert _resolve([]).is_empty()
    # unknown vocabulary -> fail-open to inactive (the 1.28.0 literal_error scar)
    assert _resolve([_entry("hurst-mr-conditioner", "quarantine")]).is_empty()


def test_unbound_entry_produces_no_effect() -> None:
    """A Class-A / unmapped entry, even refuted+blocklist, routes nothing —
    it has no Forge cell binding."""
    eff = _resolve([_entry("sector-relval", "blocklist")])
    assert eff.is_empty()
    assert eff.active_entry_ids == ()


def test_only_index_half_of_ve_maps() -> None:
    """broad-index-vol-event: the SINGLE-NAME half is deferred (ve-solo-density
    interaction) — the binding only ever deprioritizes the diversified class."""
    eff = _resolve([_entry("broad-index-vol-event", "deprioritize")])
    assert eff.deprioritize_diversified_hypotheses == frozenset({"volatility_event"})
    # never a blanket ve suppression
    assert eff.deprioritized_regime_gates == {}
    assert eff.delta_upper_clip is None


def test_partial_activation() -> None:
    eff = _resolve([_entry("deep-itm-directional", "blocklist")])
    assert eff.delta_upper_clip is not None
    assert eff.deprioritized_regime_gates == {}
    assert eff.deprioritize_diversified_hypotheses == frozenset()
    assert eff.active_entry_ids == ("deep-itm-directional",)


def test_deprioritize_weight_is_a_quarter_share() -> None:
    assert DEPRIORITIZE_WEIGHT == 0.25


# ---------------------------------------------------------------------------
# Fingerprint — stable, changes only when the DRAW changes
# ---------------------------------------------------------------------------


def test_fingerprint_empty_when_no_effects() -> None:
    assert refutation_fingerprint(entries=()) == ""
    assert refutation_fingerprint(entries=(_entry("sector-relval", "blocklist"),)) == ""


def test_fingerprint_changes_with_active_set() -> None:
    fp1 = refutation_fingerprint(entries=(_entry("deep-itm-directional", "blocklist"),))
    fp2 = refutation_fingerprint(
        entries=(
            _entry("deep-itm-directional", "blocklist"),
            _entry("hurst-mr-conditioner", "deprioritize"),
        )
    )
    assert fp1
    assert fp2
    assert fp1 != fp2


def test_fingerprint_stable_under_prose_only_amendment() -> None:
    """An amendment that doesn't change the bound effect (claim/evidence prose)
    must NOT change our fingerprint — only the DRAW-affecting fields do."""
    a = _entry("deep-itm-directional", "blocklist")
    b = dict(a, claim="reworded claim", evidence="new refs")
    assert refutation_fingerprint(entries=(a,)) == refutation_fingerprint(entries=(b,))


# ---------------------------------------------------------------------------
# Live export — resolves against the real published registry
# ---------------------------------------------------------------------------


def test_resolves_against_live_export() -> None:
    """Smoke: the live export resolves to a RefutationEffects without error
    (fail-open on missing/stale). At least the three Class-B entries should be
    active on the current published registry (all refuted, deprioritize/block)."""
    from pathlib import Path

    exports = Path.home() / "optbt_data" / "exports"
    if not any(exports.glob("refutations*.json")):
        pytest.skip("no live refutations export")
    eff = resolve_effects(exports_dir=exports)
    assert isinstance(eff, RefutationEffects)
    # not asserting exact set (Crucible may amend) — just that resolution works
    # and the fingerprint is derivable.
    assert isinstance(refutation_fingerprint(exports_dir=exports), str)
