"""H2 (v12 / D109) — event_momentum enumeration: thresholds, horizons, sampling.

event_momentum is PEAD as a directional long-options thesis: enter AFTER the
print, ride the 5-20 td drift. Directional = ``sue`` (standardized unexpected
earnings); timing gate = ``days_since_earnings`` (fire within N days after the
print). Grammar-predicate wiring is covered in
``tests/unit/test_grammar/test_event_momentum_grammar.py``; this file covers the
enumeration layer (threshold/horizon tables + the sampler producing valid configs).
"""

from __future__ import annotations

import random
from pathlib import Path

from forge.enumeration.indicator_thresholds import (
    is_threshold_skippable,
    sample_threshold_params,
)
from forge.enumeration.sampler import _K_MULTIPLIERS, _dte_target, sample_config
from forge.enumeration.search_space import build_search_space
from forge.grammar import load_grammar, validate
from forge.grammar.signal_horizon import horizon_class, signal_horizon_days
from tests.fixtures.strategy_configs import minimal_registry_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


def _grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


_TIER_1_ETFS = {"SPY", "QQQ", "IWM", "DIA"}

# ---------------------------------------------------------------------------
# Threshold table — sue (directional) + days_since_earnings (regime)
# ---------------------------------------------------------------------------


def test_sue_is_directional_only() -> None:
    """sue drives the drift direction; it is never a regime gate."""
    assert not is_threshold_skippable("sue", "directional")
    assert is_threshold_skippable("sue", "regime_filter")


def test_sue_directional_fires_on_a_strong_positive_surprise() -> None:
    params = sample_threshold_params("sue", "directional", random.Random(0))
    assert params["op"] == ">"  # large positive surprise → upward drift → long calls
    assert isinstance(params["threshold"], float)
    assert params["threshold"] > 0.0


def test_days_since_earnings_is_regime_only() -> None:
    """days_since_earnings is the post-event TIMING gate, never a directional."""
    assert not is_threshold_skippable("days_since_earnings", "regime_filter")
    assert is_threshold_skippable("days_since_earnings", "directional")


def test_days_since_earnings_regime_is_a_post_event_window() -> None:
    params = sample_threshold_params("days_since_earnings", "regime_filter", random.Random(0))
    assert params["op"] == "<"  # fire WITHIN N td after the print (the PEAD edge)
    assert 3.0 <= float(params["threshold"]) <= 10.0  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Signal-horizon table — sue ~drift window; days_since_earnings ~instant read
# ---------------------------------------------------------------------------


def test_sue_horizon_is_the_drift_window() -> None:
    """~10 td post-earnings drift → medium_lookback → swing_short/mid buckets."""
    assert signal_horizon_days("sue") == 10
    assert horizon_class("sue") == "medium_lookback"


def test_days_since_earnings_horizon_is_near_instant() -> None:
    assert signal_horizon_days("days_since_earnings") == 5


# ---------------------------------------------------------------------------
# DTE derivation — horizon-matched (k * the sue drift window)
# ---------------------------------------------------------------------------


def test_event_momentum_dte_target_is_k_times_drift_window() -> None:
    """event_momentum joins the horizon-matched set: DTE = k * horizon(sue),
    k in {2,3,4} → {20,30,40} td → swing_short/swing_mid (vs the uniform default
    it would otherwise get). Pins the §2.3.3 'derive the bucket sensibly' choice."""
    horizon = signal_horizon_days("sue")
    targets = {_dte_target("event_momentum", "sue", random.Random(s)) for s in range(60)}
    assert targets == {float(k * horizon) for k in _K_MULTIPLIERS}


# ---------------------------------------------------------------------------
# End-to-end sampling — valid configs, single-name, deterministic
# ---------------------------------------------------------------------------


def test_sample_config_event_momentum_is_grammar_valid() -> None:
    grammar = _grammar()
    registry = minimal_registry_snapshot()
    space = build_search_space(grammar, registry)
    for seed in range(100):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="event_momentum"
        )
        result = validate(cfg, grammar, registry)  # type: ignore[arg-type]
        assert result.valid, f"seed={seed}: {result.errors}"
        assert cfg.hypothesis == "event_momentum"
        directional = next(s for s in cfg.signals if s.role == "directional")
        regime = next(s for s in cfg.signals if s.role == "regime_filter")
        assert directional.indicators == ("sue",)
        assert regime.indicators == ("days_since_earnings",)
        assert cfg.dte_bucket in ("swing_short", "swing_mid")


def test_event_momentum_is_single_name_never_etf() -> None:
    """PEAD is an earnings-event thesis: days_since_earnings NaN-fills on ETFs
    (no earnings), so the gate never blocks and a confluence passthrough backfills
    a naked long-call — the degenerate leg Crucible flagged 2026-07-12 (SOXL). The
    sampler must pick an earnings-covered single name, never a no-earnings ETF/
    leveraged/index product, over the LIVE universe (D268)."""
    from forge.enumeration.sampler import _NO_EARNINGS_UNDERLYINGS

    grammar = _grammar()
    registry = minimal_registry_snapshot()
    space = build_search_space(grammar, registry)
    for seed in range(200):
        cfg = sample_config(
            space, registry, random.Random(seed), forced_hypothesis="event_momentum"
        )
        assert cfg.underlying is not None
        assert cfg.underlying not in _NO_EARNINGS_UNDERLYINGS, cfg.name


def test_no_earnings_set_covers_the_flagged_etfs_but_not_real_companies() -> None:
    """D268: the stopgap exclusion superset must contain the no-earnings names
    the T1.4 4-name set missed (SOXL — the promoted degenerate leg — plus the
    leveraged/sector/commodity/vol suite), and must NOT contain earnings-covered
    single names (the fragility guard: RTX *looks* ETF-ish but is RTX Corp, with
    EPS; excluding it would silently starve honest supply)."""
    from forge.enumeration.sampler import _NO_EARNINGS_UNDERLYINGS, _TIER_1_ETF_UNDERLYINGS

    assert _TIER_1_ETF_UNDERLYINGS <= _NO_EARNINGS_UNDERLYINGS  # superset of the T1.4 set
    for etf in ("SOXL", "SOXX", "TQQQ", "SQQQ", "GLD", "TLT", "UVXY", "VIX", "SMH", "XLK", "XLE"):
        assert etf in _NO_EARNINGS_UNDERLYINGS, etf
    for company in ("RTX", "AAPL", "NVDA", "JPM", "COIN", "MSTR"):
        assert company not in _NO_EARNINGS_UNDERLYINGS, company


def test_pick_underlying_excludes_no_earnings_for_earnings_gated_configs(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Hermetic (patched universe): for an earnings-gated regime draw, a no-earnings
    name is never picked and a covered single-name still is — over the controlled
    pool {AAPL, RTX (covered) | SOXL, XLK, SPY, TQQQ (no-earnings)}."""
    import forge.enumeration.sampler as sampler_mod
    from forge.enumeration.sampler import _pick_underlying

    pool = ("AAPL", "RTX", "SOXL", "XLK", "SPY", "TQQQ")
    monkeypatch.setattr(sampler_mod, "_load_underlyings", lambda: pool)
    drawn = {
        _pick_underlying(random.Random(s), "event_momentum", ("days_since_earnings",))
        for s in range(300)
    }
    assert drawn <= {"AAPL", "RTX"}, drawn  # only covered single-names
    assert "RTX" in drawn  # the ETF-lookalike company IS still drawable
    # non-earnings-gated hypothesis: the full pool stays available (no exclusion)
    unfiltered = {_pick_underlying(random.Random(s), "mean_reversion", ()) for s in range(300)}
    assert unfiltered & {"SOXL", "XLK", "SPY", "TQQQ"}, unfiltered


def test_event_momentum_sampling_is_deterministic() -> None:
    grammar = _grammar()
    registry = minimal_registry_snapshot()
    space = build_search_space(grammar, registry)
    a = sample_config(space, registry, random.Random(42), forced_hypothesis="event_momentum")
    b = sample_config(space, registry, random.Random(42), forced_hypothesis="event_momentum")
    assert a == b
