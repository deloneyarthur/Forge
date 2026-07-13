"""H-3 (audit 2026-05-29) — the recorded enumeration identity must track the
inputs that actually shadow the sampler's draws.

Hard rule #6 requires `(grammar_version, registry_snapshot, seed)` to reproduce
the same config sequence. Two external files also steer enumeration but were
excluded from the identity: `config/auto_tightened_thresholds.yaml` (D073, feeds
`rng.uniform`) and the universe export (D078, feeds `rng.choice`). These tests
prove the fingerprints fold them back in — toggling either file (with a cache
clear, simulating a fresh process) changes the fingerprint, so `mint_batch_id`
and `batch_summaries` no longer collide across genuinely different populations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_auto_tightenings_fingerprint_reflects_active_tightenings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.enumeration import indicator_thresholds as it

    f = tmp_path / "tight.yaml"
    monkeypatch.setattr(it, "_AUTO_TIGHTENINGS_PATH", f)

    # Derive a VALID tightening from the real table so the loader accepts it
    # (range must sit inside the indicator's directional baseline).
    ind, spec = next(
        (i, s)
        for i, s in it._INDICATOR_THRESHOLD_TABLE.items()
        if s.directional_range is not None and not s.is_skip
    )
    lo, hi = spec.directional_range  # type: ignore[misc]

    it._auto_tightenings.cache_clear()
    fp_absent = it.auto_tightenings_fingerprint()  # file missing -> empty set

    f.write_text(
        f"tightenings:\n  - indicator_id: {ind}\n    role: directional\n"
        f"    proposed_range: [{lo}, {(lo + hi) / 2}]\n"
    )
    it._auto_tightenings.cache_clear()
    fp_present = it.auto_tightenings_fingerprint()

    it._auto_tightenings.cache_clear()  # restore real-config state for other tests
    assert fp_absent != fp_present, "fingerprint must change when tightenings change"
    assert len(fp_present) == 16


def test_universe_fingerprint_reflects_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.enumeration import sampler as s

    # contracts 1.13.0: the loader globs `universe_tickers*.json` in the dir.
    f = tmp_path / "universe_tickers.json"
    monkeypatch.setattr(s, "_UNIVERSE_EXPORT_DIR", tmp_path)

    f.write_text(json.dumps({"tier_1": ["AAA"], "tier_2": ["BBB"]}))
    s._load_underlyings.cache_clear()
    fp1 = s.universe_fingerprint()

    f.write_text(json.dumps({"tier_1": ["AAA"], "tier_2": ["CCC"]}))
    s._load_underlyings.cache_clear()
    fp2 = s.universe_fingerprint()

    s._load_underlyings.cache_clear()  # restore for other tests
    assert fp1 != fp2, "fingerprint must change when the universe pool changes"
    assert len(fp1) == 16


def test_enumeration_inputs_hash_combines_both_and_is_deterministic() -> None:
    from forge.enumeration import enumeration_inputs_hash

    a = enumeration_inputs_hash()
    b = enumeration_inputs_hash()
    assert a == b  # deterministic within a process
    assert "|" in a  # combines the two sub-fingerprints


# v32 (D268): the earnings-coverage manifest is a THIRD enumeration-shadowing input
# — once Crucible publishes it, the covered set steers `_pick_underlying`'s
# earnings-gated draws (an `rng.choice`), so it must fold into the recorded identity
# or same-seed reproductions silently diverge (hard rule #6). It folds in ONLY when
# non-empty: dormant (pre-publish) the covered set is empty, applies no intersection,
# shadows no draw, and so contributes nothing — the dormant identity stays
# byte-identical to v31.


def test_earnings_coverage_fingerprint_empty_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.enumeration import sampler as s

    monkeypatch.setattr(s, "_UNIVERSE_EXPORT_DIR", tmp_path)  # no manifest
    s._load_earnings_covered_symbols.cache_clear()
    try:
        assert s.earnings_coverage_fingerprint() == ""  # dormant → contributes nothing
    finally:
        s._load_earnings_covered_symbols.cache_clear()


def test_earnings_coverage_fingerprint_reflects_covered_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.enumeration import sampler as s

    f = tmp_path / "earnings_covered_symbols.json"
    monkeypatch.setattr(s, "_UNIVERSE_EXPORT_DIR", tmp_path)

    f.write_text(json.dumps({"covered_symbols": ["AAA", "BBB"]}))
    s._load_earnings_covered_symbols.cache_clear()
    fp1 = s.earnings_coverage_fingerprint()

    f.write_text(json.dumps({"covered_symbols": ["AAA", "CCC"]}))
    s._load_earnings_covered_symbols.cache_clear()
    fp2 = s.earnings_coverage_fingerprint()

    s._load_earnings_covered_symbols.cache_clear()  # restore for other tests
    assert fp1 != fp2, "fingerprint must change when the covered set changes"
    assert len(fp1) == 16


def test_enumeration_inputs_hash_folds_coverage_only_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dormant (no manifest) → the hash carries only auto|universe (v31 shape). A
    published covered set folds in a third part and changes the hash (hard rule #6)."""
    from forge.enumeration import enumeration_inputs_hash
    from forge.enumeration import sampler as s

    monkeypatch.setattr(s, "_UNIVERSE_EXPORT_DIR", tmp_path)
    s._load_earnings_covered_symbols.cache_clear()
    try:
        dormant = enumeration_inputs_hash()
        assert dormant.count("|") == 1  # auto|universe only — dormant identity == v31 shape

        (tmp_path / "earnings_covered_symbols.json").write_text(
            json.dumps({"covered_symbols": ["AAPL", "RTX"]})
        )
        s._load_earnings_covered_symbols.cache_clear()
        published = enumeration_inputs_hash()
        assert published.count("|") == 2  # + coverage fingerprint
        assert published != dormant
    finally:
        s._load_earnings_covered_symbols.cache_clear()
