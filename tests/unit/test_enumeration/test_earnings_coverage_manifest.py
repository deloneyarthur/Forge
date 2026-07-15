"""v32 (D268 durable fix) — earnings-coverage manifest wiring.

The v30 `_NO_EARNINGS_UNDERLYINGS` frozen list is a stopgap with a documented
blind spot (D268): a FUTURE universe add of a no-earnings ticker NOT on the list
re-opens the SOXL degenerate-leg pathology for that name until a human edits the
list. v32 replaces the list-as-authority with Crucible's authored earnings-coverage
manifest — the earnings-gated underlying pool becomes `(universe & covered) -
frozen list` (the frozen list retained as free defense-in-depth, every entry
unambiguously EPS-less).

Ships DORMANT-until-publish: absent manifest → the covered set is empty → no
intersection → v31 behaviour EXACTLY (byte-identical). These tests pin that
dormancy, the blind-spot closure once a manifest is present, the corrupt /
disjoint fallbacks (a bad manifest must NEVER halt generation), and the
process-lifetime cache. The fingerprint fold lives in `test_determinism_inputs`.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

import forge.enumeration.sampler as sampler_mod
from forge.enumeration.sampler import (
    _load_earnings_covered_symbols,
    _pick_underlying,
)

# event_momentum's post-print timing gate — the earnings-gated draw path.
_EARNINGS_GATE = ("days_since_earnings",)

# A no-earnings name that is NOT on the frozen `_NO_EARNINGS_UNDERLYINGS` list —
# stands in for the v30 blind spot (a future no-earnings universe add).
_BLIND_SPOT = "ZZZZ"


# ---------------------------------------------------------------------------
# _pick_underlying pool logic — dormancy, blind-spot closure, fallbacks
# ---------------------------------------------------------------------------


def test_dormant_when_manifest_absent_is_v31_behaviour(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent manifest → covered=() → no intersection → exactly v31 (frozen-list-only).
    The blind-spot name ZZZZ (not on the frozen list) stays drawable — the v30 hole,
    still open — proving dormancy changes nothing until Crucible publishes."""
    pool = ("AAPL", "RTX", "SOXL", "XLK", _BLIND_SPOT)
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    monkeypatch.setattr(sampler_mod, "_load_earnings_covered_symbols", lambda: ())
    drawn = {
        _pick_underlying(random.Random(s), "event_momentum", _EARNINGS_GATE) for s in range(400)
    }
    # SOXL + XLK dropped by the frozen list; ZZZZ (not on it) is STILL drawable.
    assert drawn == {"AAPL", "RTX", _BLIND_SPOT}


def test_manifest_closes_the_blind_spot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Present manifest → the pool intersects `covered`, excluding a no-earnings name
    the frozen list MISSED (ZZZZ — the closed blind spot) while an RTX-type covered
    single-name (looks ETF-ish, real EPS) stays drawable."""
    pool = ("AAPL", "RTX", "SOXL", "XLK", _BLIND_SPOT)
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    monkeypatch.setattr(sampler_mod, "_load_earnings_covered_symbols", lambda: ("AAPL", "RTX"))
    drawn = {
        _pick_underlying(random.Random(s), "event_momentum", _EARNINGS_GATE) for s in range(400)
    }
    assert drawn == {"AAPL", "RTX"}  # ZZZZ excluded by coverage though absent from the frozen list
    assert "RTX" in drawn  # the ETF-lookalike company stays drawable


def test_non_earnings_hypothesis_unaffected_by_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only earnings-gated draws intersect coverage — a non-earnings hypothesis keeps the
    FULL universe (byte-identical to today; the intersection is scoped to the gate branch)."""
    pool = ("AAPL", "RTX", "SOXL", "XLK", _BLIND_SPOT)
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    monkeypatch.setattr(sampler_mod, "_load_earnings_covered_symbols", lambda: ("AAPL",))
    drawn = {_pick_underlying(random.Random(s), "mean_reversion", ()) for s in range(400)}
    assert drawn == set(pool)  # no exclusion at all


def test_empty_intersection_falls_back_to_v31_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present-but-DISJOINT covered set would empty the pool and crash `rng.choice`.
    Guard: fall back to the v31 (frozen-list-only) pool — a bad manifest must not halt
    generation. The draw stays non-empty and never raises."""
    pool = ("AAPL", "RTX", "SOXL")
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    # covered is disjoint from (universe - frozen) → intersection is empty
    monkeypatch.setattr(sampler_mod, "_load_earnings_covered_symbols", lambda: ("TSLA", "NFLX"))
    drawn = {
        _pick_underlying(random.Random(s), "event_momentum", _EARNINGS_GATE) for s in range(200)
    }
    assert drawn == {"AAPL", "RTX"}  # v31 pool (SOXL dropped by the frozen list); never empty


def test_intersection_composes_with_the_frozen_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """The frozen list stays live as defense-in-depth: a name on BOTH the manifest and
    the frozen list is still excluded (a manifest-publisher bug can't reintroduce an
    unambiguously EPS-less name)."""
    pool = ("AAPL", "RTX", "SOXL")
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    # SOXL wrongly present in the covered set → the frozen list still drops it
    monkeypatch.setattr(
        sampler_mod, "_load_earnings_covered_symbols", lambda: ("AAPL", "RTX", "SOXL")
    )
    drawn = {
        _pick_underlying(random.Random(s), "event_momentum", _EARNINGS_GATE) for s in range(200)
    }
    assert drawn == {"AAPL", "RTX"}
    assert "SOXL" not in drawn


# ---------------------------------------------------------------------------
# _load_earnings_covered_symbols — the blessed read path
# ---------------------------------------------------------------------------


def test_load_covered_absent_returns_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No `earnings_covered_symbols*.json` → () (the contract's cold semantics), so a
    cold consumer applies no intersection — exactly as before the export existed."""
    monkeypatch.setattr(sampler_mod, "_UNIVERSE_EXPORT_DIR", tmp_path)
    _load_earnings_covered_symbols.cache_clear()
    try:
        assert _load_earnings_covered_symbols() == ()
    finally:
        _load_earnings_covered_symbols.cache_clear()


def test_load_covered_reads_manifest_sorted_deduped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "earnings_covered_symbols.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "exported_at": "2026-07-13T00:00:00Z",
                "covered_symbols": ["RTX", "AAPL", "AAPL"],
            }
        )
    )
    monkeypatch.setattr(sampler_mod, "_UNIVERSE_EXPORT_DIR", tmp_path)
    _load_earnings_covered_symbols.cache_clear()
    try:
        assert _load_earnings_covered_symbols() == ("AAPL", "RTX")  # deduped + sorted
    finally:
        _load_earnings_covered_symbols.cache_clear()


def test_load_covered_corrupt_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A malformed manifest raises QueryError inside the loader → we log loudly and fall
    back to () (no intersection), NEVER raise — a corrupt file must not halt the daemon
    (mirrors `_load_underlyings`' `universe_export_unreadable`)."""
    (tmp_path / "earnings_covered_symbols.json").write_text("{ this is not valid json")
    monkeypatch.setattr(sampler_mod, "_UNIVERSE_EXPORT_DIR", tmp_path)
    _load_earnings_covered_symbols.cache_clear()
    try:
        assert _load_earnings_covered_symbols() == ()
    finally:
        _load_earnings_covered_symbols.cache_clear()


def test_load_covered_is_process_cached() -> None:
    """Cached for the process lifetime (like `_load_underlyings`) — restart to pick up a
    publish, so activation happens at a restart boundary, never mid-run."""
    assert hasattr(_load_earnings_covered_symbols, "cache_clear")
