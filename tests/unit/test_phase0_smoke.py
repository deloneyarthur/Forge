"""Phase 0 smoke tests — skeleton imports and blessed primitives behave."""

from __future__ import annotations

from datetime import UTC

from forge import __version__
from forge.core.clock import utc_now
from forge.core.seed import SeedHierarchy


def test_version_present() -> None:
    assert __version__
    assert isinstance(__version__, str)


def test_utc_now_returns_tz_aware_utc() -> None:
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == UTC.utcoffset(now)


def test_seed_hierarchy_deterministic_across_instances() -> None:
    sh1 = SeedHierarchy(root=42)
    sh2 = SeedHierarchy(root=42)
    assert sh1.derive("enumerator") == sh2.derive("enumerator")


def test_seed_hierarchy_names_diverge() -> None:
    sh = SeedHierarchy(root=42)
    assert sh.derive("enumerator") != sh.derive("prefilter")


def test_seed_hierarchy_rng_reproducible() -> None:
    sh = SeedHierarchy(root=42)
    rng_a = sh.rng("foo")
    rng_b = sh.rng("foo")
    assert [rng_a.random() for _ in range(5)] == [rng_b.random() for _ in range(5)]


def test_seed_hierarchy_root_change_diverges() -> None:
    a = SeedHierarchy(root=42).derive("enumerator")
    b = SeedHierarchy(root=43).derive("enumerator")
    assert a != b
