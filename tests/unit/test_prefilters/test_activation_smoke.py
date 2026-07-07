"""Deploy-time activation smoke-test — catch a newly-adopted directional indicator
that Crucible's feature-cache writer does not actually compute (the §2.1a class).

Layer-3 gate: D236 verified sma_slope was (1) in the registry snapshot and
(2) enumerable in Forge, but not (3) actually computed by the writer — so it
zero-traded silently (0/2800 submitted) for ~5h post-deploy. This module asserts
layer 3 before deploy: a directional that produces 0 activations on every probed
high-history name is INERT and blocks the bump.
"""

from __future__ import annotations

from datetime import date, timedelta

from forge.prefilters.activation_smoke import (
    has_inert,
    probe_directional_activations,
    summarize_activation_checks,
)

# --- decision logic (the bug-prone part) --------------------------------------


def test_ok_when_any_name_fires() -> None:
    checks = summarize_activation_checks(
        {"momentum_252": {"AAPL": 1067, "MSFT": 0}},
        indicators=["momentum_252"],
        min_activations=1,
    )
    assert len(checks) == 1
    c = checks[0]
    assert c.ok
    assert not c.unchecked
    assert c.max_activations == 1067


def test_inert_when_zero_everywhere() -> None:
    checks = summarize_activation_checks(
        {"sma_slope": {"AAPL": 0, "MSFT": 0}},
        indicators=["sma_slope"],
        min_activations=1,
    )
    assert not checks[0].ok
    assert not checks[0].unchecked
    assert checks[0].max_activations == 0


def test_unchecked_when_no_config_found() -> None:
    """No enumerated config used the indicator → we could not probe it. That is a
    distinct 'unchecked' state — NOT a hard inert failure (avoids blocking on a
    legitimately-rare indicator we simply didn't sample)."""
    checks = summarize_activation_checks({}, indicators=["rare_ind"], min_activations=1)
    assert checks[0].unchecked
    assert not checks[0].ok


def test_has_inert_flags_inert_but_not_unchecked() -> None:
    # 'a' fires 0 (inert), 'b' never sampled (unchecked)
    checks = summarize_activation_checks({"a": {"X": 0}}, indicators=["a", "b"], min_activations=1)
    assert has_inert(checks) is True  # 'a' is a genuine inert failure
    only_unchecked = summarize_activation_checks({}, indicators=["b"], min_activations=1)
    assert has_inert(only_unchecked) is False  # unchecked alone must not NO-GO


def test_min_activations_threshold_respected() -> None:
    checks = summarize_activation_checks({"x": {"AAPL": 5}}, indicators=["x"], min_activations=10)
    assert not checks[0].ok  # 5 < 10


# --- probe orchestration (enumerate → find config → count via cache) ----------


class _FakeCache:
    """Minimal FeatureCache: returns `counts[underlying]` activation dates."""

    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts
        self._active = ""

    def prefetch_for_config(self, config: object) -> None:
        self._active = getattr(config, "underlying", "")

    def activation_dates(self, signal_id: str) -> frozenset[date]:
        n = self._counts.get(self._active, 0)
        base = date(2024, 1, 1)
        return frozenset(base + timedelta(days=i) for i in range(n))


def test_probe_counts_per_name_from_cache() -> None:
    """End-to-end (real grammar + whatever registry loads + fake cache): the probe
    finds a config using a real directional, overrides the underlying per name, and
    reports the cache's activation count for each. The directional is discovered
    dynamically so the test is registry-agnostic (demo fallback or live)."""
    from pathlib import Path

    from forge.enumeration import enumerate_candidates
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry

    root = Path(__file__).resolve().parents[2].parent
    grammar = load_grammar(
        root / "config" / "grammar.yaml", archive_dir=root / "config" / "grammar_archive"
    )
    registry = load_registry(allow_demo_fallback=True)

    directional = None
    for cfg in enumerate_candidates(grammar, registry, seed=0, max_candidates=2000):
        for sig in cfg.signals:
            if sig.role == "directional" and len(sig.indicators) == 1:
                directional = sig.indicators[0]
                break
        if directional is not None:
            break
    assert directional is not None, "no enumerable directional found in the registry"

    cache = _FakeCache({"AAPL": 42, "MSFT": 0})
    out = probe_directional_activations(
        cache,
        registry,
        grammar,
        indicators=[directional],
        names=["AAPL", "MSFT"],
        seed=0,
        max_enumerate=3000,
    )
    assert out[directional] == {"AAPL": 42, "MSFT": 0}
    checks = summarize_activation_checks(out, indicators=[directional], min_activations=1)
    assert checks[0].ok  # fired 42 on AAPL


def test_probe_marks_unfound_indicator_absent() -> None:
    from pathlib import Path

    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry

    root = Path(__file__).resolve().parents[2].parent
    grammar = load_grammar(
        root / "config" / "grammar.yaml", archive_dir=root / "config" / "grammar_archive"
    )
    registry = load_registry(allow_demo_fallback=True)
    out = probe_directional_activations(
        _FakeCache({}),
        registry,
        grammar,
        indicators=["definitely_not_an_indicator"],
        names=["AAPL"],
        seed=0,
        max_enumerate=500,
    )
    assert "definitely_not_an_indicator" not in out  # never enumerated → absent → 'unchecked'
