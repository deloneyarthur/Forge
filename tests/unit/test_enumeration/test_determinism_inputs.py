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

    f = tmp_path / "universe.json"
    monkeypatch.setattr(s, "_UNIVERSE_EXPORT_PATH", f)

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
