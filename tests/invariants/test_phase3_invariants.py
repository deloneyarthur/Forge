"""Phase 3 invariants — pre-filter discipline checks.

Each invariant maps to a CLAUDE.md hard rule, a §13 production-quality
requirement, or a §5 spec contract. Owned by the pre-filter phase; new
rules add tests here.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from forge.core.seed import SeedHierarchy
from forge.enumeration import enumerate_candidates
from forge.enumeration._demo_registry import demo_registry
from forge.grammar import Grammar, load_grammar
from forge.prefilters import (
    SyntheticFeatureCache,
    default_filters,
    load_calibration,
    run_battery,
)
from forge.prefilters import calibration as calibration_module
from forge.prefilters.types import FilterContext, FilterResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"
_PREFILTER_YAML = _REPO_ROOT / "config" / "prefilter.yaml"


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


def _ctx(seed: int) -> FilterContext:
    hierarchy = SeedHierarchy(seed)
    return FilterContext(
        registry=demo_registry(),
        feature_cache=SyntheticFeatureCache(root_seed=seed),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=load_calibration(_PREFILTER_YAML),
        rng_factory=hierarchy.rng,
    )


# ---------------------------------------------------------------------------
# §13.1 / CLAUDE.md hard rule #6 — battery determinism
# ---------------------------------------------------------------------------


def test_battery_is_deterministic_for_same_triple(grammar: Grammar) -> None:
    """Two runs with the same (grammar, registry, seed) triple produce
    byte-identical battery verdicts and per-filter scores."""
    filters = default_filters()
    a_verdicts: list[tuple[str, bool, float]] = []
    b_verdicts: list[tuple[str, bool, float]] = []
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=42, max_candidates=20):
        report = run_battery(cfg, _ctx(seed=42), filters)
        for name, result in report.filter_results.items():
            a_verdicts.append((name, result.passed, result.score))
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=42, max_candidates=20):
        report = run_battery(cfg, _ctx(seed=42), filters)
        for name, result in report.filter_results.items():
            b_verdicts.append((name, result.passed, result.score))
    assert a_verdicts == b_verdicts


def test_battery_diverges_when_seed_changes(grammar: Grammar) -> None:
    """Compare per-filter scores (not just pass/fail) — pass/fail
    booleans can coincide across seeds even when the underlying
    distributions differ."""
    filters = default_filters()
    a: list[tuple[float, ...]] = []
    b: list[tuple[float, ...]] = []
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=1, max_candidates=10):
        report = run_battery(cfg, _ctx(seed=1), filters)
        a.append(tuple(r.score for r in report.filter_results.values()))
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=2, max_candidates=10):
        report = run_battery(cfg, _ctx(seed=2), filters)
        b.append(tuple(r.score for r in report.filter_results.values()))
    assert a != b


# ---------------------------------------------------------------------------
# §5.2 — short-circuit invariant: a failed filter prevents later filters
# from running. Verified at the unit level too; this re-anchors at the
# invariant level so we catch any future battery refactor that breaks it.
# ---------------------------------------------------------------------------


def test_short_circuit_no_later_filters_run_after_failure(grammar: Grammar) -> None:
    """If filter k fails, no filter with cost_tier > k appears in the
    report's filter_results."""
    filters = default_filters()
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=7, max_candidates=30):
        report = run_battery(cfg, _ctx(seed=7), filters)
        if report.passed:
            continue
        # Find the failing filter; ensure no higher-tier filter is in results.
        failing = next(
            (
                f
                for f in filters
                if f.name in report.filter_results and not report.filter_results[f.name].passed
            ),
            None,
        )
        assert failing is not None, "report.passed=False but no failing filter recorded"
        for f in filters:
            if f.cost_tier > failing.cost_tier:
                assert f.name not in report.filter_results, (
                    f"short-circuit violated: {f.name} (cost_tier={f.cost_tier}) "
                    f"ran after {failing.name} (cost_tier={failing.cost_tier}) failed"
                )


# ---------------------------------------------------------------------------
# CLAUDE.md hard rule #4 — calibration module must not auto-loosen
# ---------------------------------------------------------------------------


def test_calibration_module_does_not_expose_apply_loosening() -> None:
    """Structural enforcement: `forge.prefilters.calibration` exposes
    `apply_tightening` but NOT `apply_loosening`. Loosenings must go
    through `write_loosening_proposal` -> operator review."""
    assert not hasattr(calibration_module, "apply_loosening")
    assert "apply_loosening" not in calibration_module.__all__
    # The structural counterpart that we DO expose:
    assert hasattr(calibration_module, "apply_tightening")
    assert hasattr(calibration_module, "write_loosening_proposal")


# ---------------------------------------------------------------------------
# §5.4 / D021/D2 — composite_score remains None at Phase 3
# ---------------------------------------------------------------------------


def test_composite_score_is_none_for_every_battery_report(grammar: Grammar) -> None:
    """Phase 3 ships the per-filter score; the §6.2 weighted composite
    is Phase 4's job. A report with composite_score != None at Phase 3
    means the line was crossed."""
    filters = default_filters()
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=0, max_candidates=20):
        report = run_battery(cfg, _ctx(seed=0), filters)
        assert report.composite_score is None


# ---------------------------------------------------------------------------
# §12 Phase 3 — 10K candidates / 30 min budget
# ---------------------------------------------------------------------------


def test_perf_1000_candidates_well_under_phase3_budget(grammar: Grammar) -> None:
    """§12 Phase 3 budget: 10K candidates through full battery in < 30
    min (1800s). We run 1K here and require < 180s — a 1/10 scale at
    a 1/10 budget; if this exceeds, the full 10K extrapolation likely
    busts the spec deadline."""
    filters = default_filters()
    t0 = time.perf_counter()
    n_ran = 0
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=0, max_candidates=1000):
        run_battery(cfg, _ctx(seed=0), filters)
        n_ran += 1
    elapsed = time.perf_counter() - t0
    assert n_ran == 1000
    assert elapsed < 180.0, f"perf regression: 1K candidates took {elapsed:.1f}s (budget 180s)"


# ---------------------------------------------------------------------------
# §5.4 — every yielded report references the input config (no swap)
# ---------------------------------------------------------------------------


def test_report_config_identity_matches_input(grammar: Grammar) -> None:
    """The battery must not silently swap configs — each report's
    .config field is the exact instance that was passed in."""
    filters = default_filters()
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=3, max_candidates=20):
        report = run_battery(cfg, _ctx(seed=3), filters)
        assert report.config is cfg


# ---------------------------------------------------------------------------
# §5 — every per-filter score is in [0, 1] (FilterResult invariant)
# ---------------------------------------------------------------------------


def test_every_per_filter_score_is_in_unit_interval(grammar: Grammar) -> None:
    """The §5.4 contract: each FilterResult.score is in [0, 1]. The
    FilterResult constructor enforces it; this is the integration-level
    confirmation that no filter sneaks a NaN / out-of-range value past
    type-checking (e.g., via float division surprises)."""
    filters = default_filters()
    for cfg in enumerate_candidates(grammar, demo_registry(), seed=9, max_candidates=50):
        report = run_battery(cfg, _ctx(seed=9), filters)
        for result in report.filter_results.values():
            assert isinstance(result, FilterResult)
            assert 0.0 <= result.score <= 1.0
