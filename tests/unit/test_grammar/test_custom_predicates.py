"""Tests for the §3.5 custom_python predicate functions, table-driven per rule id.

Each rule has at least one positive and one negative row. The baseline is
``grammar_valid_baseline()`` (mean_reversion swing_short, rsi_2 directional, iv_rank <= 50 gate,
time_stop exit); every row changes one thing to satisfy or provoke the rule and is evaluated
through the top-level ``evaluate`` dispatcher, the production call path. Rows keep the setup of
the tests they replaced (exits included) even where the rule under test ignores it, so each row
still means what its D-entry meant.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from crucible_contracts import ExitSpec, SelectorSpec, SignalSpec, SizerSpec

from forge.enumeration.search_space import build_search_space
from forge.grammar import custom_predicates as cp
from forge.grammar import evaluate, load_grammar
from forge.grammar.custom_predicates import _S5_HYPOTHESIS_EXITS
from forge.grammar.models import CustomPythonPredicate, PredicateResult
from tests.fixtures.contexts import REPO_ROOT
from tests.fixtures.sampling import sample_configs
from tests.fixtures.strategy_configs import grammar_valid_baseline, minimal_registry_snapshot

_REGISTRY = minimal_registry_snapshot()
_MANDATORY = tuple(
    ExitSpec(id=i) for i in ("expiry_exit", "theta_cliff_exit", "earnings_exit", "liquidity_exit")
)
_TRAILING = ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.30})
_IV50 = {"threshold": 50}


def _run(rule: str, **overrides: Any) -> PredicateResult:
    predicate = CustomPythonPredicate(type="custom_python", function=rule)
    return evaluate(predicate, grammar_valid_baseline(**overrides), _REGISTRY)


def _check(result: PredicateResult, passed: bool, needles: tuple[str, ...]) -> None:
    assert bool(result.passed) is passed, result.detail
    for needle in needles:
        assert needle in (result.detail or ""), (needle, result.detail)


def _sig(
    role: str,
    indicator: str,
    *,
    params: dict[str, Any] | None = None,
    sig_id: str | None = None,
    kind: str = "threshold",
) -> SignalSpec:
    default_id = {"directional": "sig_directional", "regime_filter": "sig_regime"}.get(role)
    return SignalSpec(
        id=sig_id or default_id or f"sig_{role}",
        type=kind,
        role=role,
        indicators=(indicator,),
        params=params or {},
    )


def _signals(
    directional: str,
    regime: str,
    regime_params: dict[str, Any] | None = None,
    *extra: SignalSpec,
) -> tuple[SignalSpec, ...]:
    return (
        _sig("directional", directional),
        _sig("regime_filter", regime, params=regime_params),
        *extra,
    )


def _exits(*extra: ExitSpec | str) -> tuple[ExitSpec, ...]:
    return (*_MANDATORY, *(e if isinstance(e, ExitSpec) else ExitSpec(id=e) for e in extra))


_TREND = {"hypothesis": "trend_continuation", "signals": _signals("ema_50", "adx")}
_VE_EXITS = _exits("iv_crush_exit", "event_passed_exit")


def _ve(underlying: str, regime: str) -> dict[str, Any]:
    return {
        "underlying": underlying,
        "hypothesis": "volatility_event",
        "signals": _signals("put_call_flow", regime),
        "exits": _VE_EXITS,
    }


def _selector(delta: float, dte_min: int, dte_max: int) -> SelectorSpec:
    return SelectorSpec(delta_target=delta, delta_tolerance=0.05, dte_min=dte_min, dte_max=dte_max)


# --- S4: lookback class matches the DTE bucket ---------------------------------------------

_S4 = [
    pytest.param({}, True, (), id="short_lookback_matches_swing_short"),
    pytest.param(
        {"signals": _signals("momentum_252", "iv_rank", _IV50)},
        False,
        ("long_lookback", "swing_short"),
        id="long_lookback_with_swing_short_fails",
    ),
    pytest.param(
        {"signals": _signals("not_in_registry", "iv_rank", _IV50)},
        False,
        ("not present in registry",),
        id="unknown_indicator_reported",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _S4)
def test_s4_lookback_class_matches_dte_bucket(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("lookback_class_matches_dte_bucket", **overrides), passed, needles)


# --- S5 / D071: exit framework consistent with the hypothesis -------------------------------

_S5 = [
    pytest.param({}, True, (), id="mean_reversion_with_time_stop_passes"),
    pytest.param(
        {"exits": _exits()},
        False,
        ("required_from_set", "time_stop"),
        id="mean_reversion_without_time_stop_fails",
    ),
    pytest.param(
        {**_TREND, "exits": _exits(_TRAILING, "hard_profit_target")},
        False,
        ("forbidden exits present", "hard_profit_target"),
        id="trend_with_hard_profit_target_fails",
    ),
    # D290/v39: event_passed_exit is OUT; iv_crush_exit AND time_stop are required_always.
    pytest.param(
        {
            "hypothesis": "volatility_event",
            "signals": _signals("put_call_flow", "days_to_earnings"),
            "exits": _exits("iv_crush_exit"),
        },
        False,
        ("required_always", "time_stop"),
        id="volatility_event_missing_time_stop_fails",
    ),
    pytest.param(
        {"exits": _exits("time_stop", "trailing_atr")},
        False,
        ("foreign", "trailing_atr"),
        id="d071_foreign_exit_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _S5)
def test_s5_exits_match_hypothesis(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("exits_match_hypothesis", **overrides), passed, needles)


def test_m15_grammar_md_s5_documents_every_exit_in_source_table() -> None:
    """M-15 (audit 2026-05-29): content-aware S5 doc-sync. The pre-commit hook only checks
    heading existence, so GRAMMAR.md §S5 must name the v3 schema terms AND every exit id in
    `_S5_HYPOTHESIS_EXITS` here, where the Python table is importable."""
    grammar_md = (REPO_ROOT / "docs" / "GRAMMAR.md").read_text()
    match = re.search(r"### S5:.*?(?=\n### |\n## |\Z)", grammar_md, re.DOTALL)
    assert match, "GRAMMAR.md is missing the ### S5 section"
    s5 = match.group(0)
    keys = ("required_always", "required_from_set", "optional_additions", "forbidden")
    for kw in keys:
        assert kw in s5, f"GRAMMAR.md §S5 missing v3 schema term {kw!r}"
    missing = [
        (hyp, key, exit_id)
        for hyp, table in _S5_HYPOTHESIS_EXITS.items()
        for key in keys
        for exit_id in table[key]
        if exit_id not in s5
    ]
    assert not missing, f"GRAMMAR.md §S5 omits exit ids from _S5_HYPOTHESIS_EXITS: {missing}"


def test_d071_too_many_optional_additions_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """M-16 (audit 2026-05-29): the K_MAX_OPTIONAL=2 cap is a hard-rule-#1 rejection branch.
    No shipped hypothesis has >2 optional_additions, so the pool is extended to three here
    (all inside the allow-set, so only the cap branch can fire)."""
    synthetic = {
        "required_always": (),
        "required_from_set": ("regime_flip_exit",),
        "optional_additions": ("time_stop", "iv_crush_exit", "target_exit"),
        "forbidden": (),
    }
    monkeypatch.setitem(cp._S5_HYPOTHESIS_EXITS, "regime_arbitrage", synthetic)
    result = _run(
        "exits_match_hypothesis",
        hypothesis="regime_arbitrage",
        exits=_exits("regime_flip_exit", "time_stop", "iv_crush_exit", "target_exit"),
    )
    assert not result.passed
    assert "too many optional_additions" in result.detail
    assert f"K_MAX_OPTIONAL={cp.K_MAX_OPTIONAL}" in result.detail


def test_d071_sampler_optional_additions_can_fire_over_seeds() -> None:
    """The rng-driven p=0.5 optional picks are not pinned to never-fire: across 120 seeds an
    optional_additions exit appears for some hypothesis with a non-empty pool."""
    grammar = load_grammar(
        REPO_ROOT / "config" / "grammar.yaml", archive_dir=REPO_ROOT / "config" / "grammar_archive"
    )
    e1 = set(build_search_space(grammar, _REGISTRY).e1_mandatory)
    fired: set[str] = set()
    for cfg in sample_configs(grammar, _REGISTRY, n=120):
        rules = _S5_HYPOTHESIS_EXITS[cfg.hypothesis]
        optional_pool = set(rules["optional_additions"])
        if not optional_pool:
            continue
        required = e1 | set(rules["required_always"]) | set(rules["required_from_set"])
        fired |= ({e.id for e in cfg.exits} & optional_pool) - required
    assert fired, "No optional_additions fired across 120 seeds"


# --- C1: no two indicators from the same family ---------------------------------------------

_C1 = [
    pytest.param({}, True, (), id="baseline_passes"),
    pytest.param(
        {"signals": _signals("rsi_2", "iv_rank", _IV50, _sig("confluence", "rsi_14"))},
        False,
        ("share family", "mean_reversion"),
        id="two_mean_reversion_indicators_fail",
    ),
    pytest.param(
        {"signals": _signals("rsi_2", "not_in_registry")},
        False,
        ("not in registry",),
        id="unknown_indicator_reported",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _C1)
def test_c1_no_duplicate_indicator_families(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("no_duplicate_indicator_families", **overrides), passed, needles)


# --- C2: directional family matches the hypothesis (D062 dealer_positioning allowlist) ------

_C2 = [
    pytest.param({}, True, (), id="mean_reversion_matches"),
    pytest.param(
        {"hypothesis": "trend_continuation", "signals": _signals("rsi_2", "adx")},
        False,
        ("trend", "mean_reversion"),
        id="trend_with_mean_reversion_directional_fails",
    ),
    pytest.param(
        {
            "hypothesis": "volatility_event",
            "signals": _signals("gex", "iv_rank", _IV50),
            "exits": _exits("regime_flip_exit"),
        },
        True,
        (),
        id="volatility_event_accepts_dealer_positioning",
    ),
    pytest.param(
        {
            "hypothesis": "mean_reversion",
            "signals": _signals("call_wall_distance_pct", "iv_rank", _IV50),
        },
        True,
        (),
        id="mean_reversion_accepts_dealer_positioning",
    ),
    pytest.param(
        {"hypothesis": "trend_continuation", "signals": _signals("gex", "adx")},
        False,
        ("dealer_positioning",),
        id="trend_continuation_rejects_dealer_positioning",
    ),
    pytest.param(
        {
            "hypothesis": "regime_arbitrage",
            "signals": _signals("pairs_zscore", "iv_rank", _IV50),
            "exits": _exits("regime_flip_exit"),
        },
        True,
        (),
        id="regime_arbitrage_accepts_any_family",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _C2)
def test_c2_directional_family_matches_hypothesis(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("directional_family_matches_hypothesis", **overrides), passed, needles)


# --- C4: regime gate disjoint from the directional indicator --------------------------------

_C4 = [
    pytest.param({}, True, (), id="disjoint_indicators_pass"),
    pytest.param(
        {"signals": _signals("rsi_2", "rsi_2")}, False, ("rsi_2",), id="shared_indicator_fails"
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _C4)
def test_c4_regime_indicators_disjoint_from_directional(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("regime_indicators_disjoint_from_directional", **overrides), passed, needles)


# --- P1: indicator params within the registry schema keys -----------------------------------

_P1 = [
    pytest.param({}, True, (), id="baseline_passes"),
    pytest.param(
        {"signals": _signals("rsi_2", "iv_rank", {"bogus_param": 1})},
        False,
        ("bogus_param",),
        id="unknown_param_key_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _P1)
def test_p1_indicator_params_within_registry_ranges(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("indicator_params_within_registry_ranges", **overrides), passed, needles)


# --- P2: DTE window per bucket ---------------------------------------------------------------

_P2 = [
    pytest.param({}, True, (), id="swing_short_window_passes"),
    pytest.param(
        {"selector": _selector(0.45, 5, 12)},
        False,
        ("swing_short",),
        id="swing_short_dte_outside_window_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _P2)
def test_p2_dte_window_matches_bucket(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("dte_window_matches_bucket", **overrides), passed, needles)


# --- P3: delta target in the DTE band (D125/v16 trend-scoped widening) -----------------------

_P3 = [
    pytest.param({}, True, (), id="baseline_passes"),
    pytest.param(
        {"selector": _selector(0.20, 14, 21)},
        False,
        ("swing_short", "0.4"),
        id="delta_target_outside_band_fails",
    ),
    pytest.param(
        {
            "hypothesis": "trend_continuation",
            "dte_bucket": "swing_long",
            "selector": _selector(0.50, 60, 90),
        },
        True,
        (),
        id="trend_widened_swing_long_band_passes",
    ),
    pytest.param(
        {
            "hypothesis": "mean_reversion",
            "dte_bucket": "swing_long",
            "selector": _selector(0.50, 60, 90),
        },
        False,
        ("swing_long", "0.35"),
        id="non_trend_swing_long_band_unchanged",
    ),
    pytest.param(
        {
            "hypothesis": "trend_continuation",
            "dte_bucket": "swing_mid",
            "selector": _selector(0.55, 30, 45),
        },
        True,
        (),
        id="trend_swing_mid_widened",
    ),
    pytest.param(
        {
            "hypothesis": "trend_continuation",
            "dte_bucket": "swing_short",
            "selector": _selector(0.30, 14, 21),
        },
        False,
        (),
        id="trend_swing_short_unchanged",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _P3)
def test_p3_delta_target_in_dte_band(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("delta_target_in_dte_band", **overrides), passed, needles)


# --- E1: mandatory exits present -------------------------------------------------------------
# The negative path cannot be constructed: StrategyConfig enforces the four mandatory exits at
# instance creation, so the predicate is defence in depth and only its positive path is testable.


def test_e1_all_four_present() -> None:
    assert _run("mandatory_exits_present").passed


# --- E2: at most two stop-loss exits ---------------------------------------------------------

_E2 = [
    pytest.param({}, True, (), id="zero_stop_loss_passes"),
    pytest.param(
        {"exits": _exits("time_stop", "premium_stop_loss", "atr_underlying_stop_loss", _TRAILING)},
        False,
        ("3 stop-loss",),
        id="three_stop_loss_fails",
    ),
    pytest.param(
        {"exits": _exits("time_stop", "premium_stop_loss", "atr_underlying_stop_loss")},
        True,
        (),
        id="two_stop_loss_at_limit_passes",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _E2)
def test_e2_at_most_two_stop_loss_exits(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("at_most_two_stop_loss_exits", **overrides), passed, needles)


# --- E3: trailing_atr requires an activation threshold --------------------------------------

_E3 = [
    pytest.param({}, True, (), id="baseline_without_trailing_atr_passes"),
    pytest.param({"exits": _exits("time_stop", _TRAILING)}, True, (), id="with_threshold_passes"),
    pytest.param(
        {"exits": _exits("time_stop", "trailing_atr")},
        False,
        ("activate_after_gain_pct",),
        id="without_threshold_fails",
    ),
    pytest.param(
        {
            "exits": _exits(
                "time_stop", ExitSpec(id="trailing_atr", params={"activate_after_gain_pct": 0.20})
            )
        },
        False,
        ("0.3",),
        id="below_min_threshold_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _E3)
def test_e3_trailing_atr_has_activation_threshold(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("trailing_atr_has_activation_threshold", **overrides), passed, needles)


# --- R1: mean_reversion requires a calm-regime gate ------------------------------------------
# iv_rank <= 50 was the v1 rule; the accepted alternatives widened it as an OR, ADD not replace:
# gamma_flip (D107/v11), hurst (D150/v20), rv_rank (D167/v22), vol_regime (D254/v24),
# realized_vol (D265/v28), market_realized_vol (D266/v29). Op '<' is the ranging/calm side.


def _mr_gate(regime: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"signals": _signals("rsi_2", regime, params)}


_R1 = [
    pytest.param({}, True, (), id="baseline_iv_rank_50_passes"),
    pytest.param(_TREND, True, (), id="non_mean_reversion_passes_vacuously"),
    pytest.param(_mr_gate("adx", {}), False, ("iv_rank",), id="missing_calm_gate_fails"),
    pytest.param(_mr_gate("iv_rank", {"threshold": 75}), False, (), id="iv_rank_above_50_fails"),
    pytest.param(
        _mr_gate("gamma_flip_distance_pct", {"threshold": 0.0, "op": "<"}),
        True,
        (),
        id="d107_gamma_flip",
    ),
    pytest.param(_mr_gate("hurst", {"threshold": 0.45, "op": "<"}), True, (), id="d150_hurst"),
    pytest.param(_mr_gate("rv_rank", {"threshold": 25.0, "op": "<"}), True, (), id="d167_rv_rank"),
    pytest.param(
        _mr_gate("vol_regime", {"threshold": 2.0, "op": "<"}), True, (), id="d254_vol_regime"
    ),
    pytest.param(
        _mr_gate("realized_vol", {"threshold": 0.20, "op": "<"}), True, (), id="d265_realized_vol"
    ),
    pytest.param(
        _mr_gate("market_realized_vol", {"threshold": 0.20, "op": "<"}),
        True,
        (),
        id="d266_market_realized_vol",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _R1)
def test_r1_mean_reversion_requires_iv_rank_gate(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("mean_reversion_requires_iv_rank_gate", **overrides), passed, needles)


# --- R2: trend_continuation requires a trend-strength gate -----------------------------------
# adx/hurst (v1), rv_rank (D077), gamma_flip op '>' (D107), vix_term_slope contango (D264).


def _trend_gate(regime: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "hypothesis": "trend_continuation",
        "signals": _signals("ema_50", regime, params),
        "exits": _exits(_TRAILING),
    }


_R2 = [
    pytest.param({}, True, (), id="baseline_mean_reversion_passes_vacuously"),
    pytest.param(_trend_gate("adx", {}), True, (), id="adx"),
    pytest.param(
        _trend_gate("rv_rank", {"threshold": 50, "op": "<", "rv_window": 21, "window": 252}),
        True,
        (),
        id="d077_rv_rank",
    ),
    pytest.param(
        _trend_gate("gamma_flip_distance_pct", {"threshold": 0.0, "op": ">"}),
        True,
        (),
        id="d107_gamma_flip",
    ),
    pytest.param(
        _trend_gate("vix_term_slope", {"threshold": 0.0, "op": ">"}),
        True,
        (),
        id="d264_vix_term_slope",
    ),
    pytest.param(
        {"hypothesis": "trend_continuation", "signals": _signals("ema_50", "iv_rank", _IV50)},
        False,
        (),
        id="without_trend_strength_gate_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _R2)
def test_r2_trend_requires_trend_strength_gate(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("trend_requires_trend_strength_gate", **overrides), passed, needles)


# --- R3: volatility_event requires an event-proximity gate -----------------------------------
# T1.4 / D039: days_to_earnings is sentinel 999 on ETFs (silent zero-trade), so R3 v2 rejects
# it there; macro countdowns are fine on ETFs. D135/v18: pre_earnings_setup composes
# days_to_earnings and inherits the same ETF rejection.

_R3 = [
    pytest.param({}, True, (), id="baseline_passes_vacuously"),
    pytest.param(_ve("AAPL", "days_to_earnings"), True, (), id="days_to_earnings_on_single_name"),
    pytest.param(
        _ve("SPY", "days_to_earnings"),
        False,
        ("ETF", "days_to_earnings"),
        id="days_to_earnings_on_etf_rejects",
    ),
    pytest.param(_ve("SPY", "days_to_fomc"), True, (), id="days_to_fomc_on_etf"),
    pytest.param(
        {"hypothesis": "volatility_event", "signals": _signals("put_call_flow", "iv_rank", _IV50)},
        False,
        (),
        id="without_event_gate_fails",
    ),
    pytest.param(
        _ve("AAPL", "pre_earnings_setup"), True, (), id="d135_pre_earnings_setup_on_single_name"
    ),
    pytest.param(
        _ve("SPY", "pre_earnings_setup"),
        False,
        ("ETF", "pre_earnings_setup"),
        id="d135_pre_earnings_setup_on_etf_rejects",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _R3)
def test_r3_volatility_event_requires_event_proximity_gate(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("volatility_event_requires_event_proximity_gate", **overrides), passed, needles)


# --- X1 / X2: sizer mode requires its estimator indicator -----------------------------------


def _with_filter(sig_id: str, indicator: str, mode: str) -> dict[str, Any]:
    extra = _sig("filter", indicator, sig_id=sig_id, kind="passthrough")
    return {"signals": _signals("rsi_2", "iv_rank", _IV50, extra), "sizer": SizerSpec(mode=mode)}


_X1 = [
    pytest.param({}, True, (), id="non_vol_target_passes_vacuously"),
    pytest.param(
        _with_filter("sig_vol", "realized_vol", "vol_target"),
        True,
        (),
        id="vol_target_with_realized_vol",
    ),
    pytest.param(
        {"sizer": SizerSpec(mode="vol_target")},
        False,
        ("realized_vol",),
        id="vol_target_without_realized_vol_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _X1)
def test_x1_vol_target_requires_realized_vol_indicator(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("vol_target_requires_realized_vol_indicator", **overrides), passed, needles)


_X2 = [
    pytest.param({}, True, (), id="non_kelly_passes_vacuously"),
    pytest.param(
        _with_filter("sig_ev", "expected_value_estimator", "fractional_kelly"),
        True,
        (),
        id="kelly_with_estimator",
    ),
    pytest.param(
        {"sizer": SizerSpec(mode="fractional_kelly")},
        False,
        ("expected_value_estimator",),
        id="kelly_without_estimator_fails",
    ),
]


@pytest.mark.parametrize(("overrides", "passed", "needles"), _X2)
def test_x2_kelly_requires_expected_value_estimator(
    overrides: dict[str, Any], passed: bool, needles: tuple[str, ...]
) -> None:
    _check(_run("kelly_requires_expected_value_estimator", **overrides), passed, needles)
