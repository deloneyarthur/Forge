"""End-to-end test of the real ``config/grammar.yaml`` v1 ruleset.

Loads the on-disk grammar via ``load_grammar``, validates the
``grammar_valid_baseline`` fixture against it, and asserts:

- All 21 §3.5 rules are present.
- Categories and ids match §3.5 expectations.
- The baseline config passes every active rule.
- Each rule's `rationale_ref` points at the matching `docs/GRAMMAR.md` heading.

This is the regression guard for `config/grammar.yaml` + `docs/GRAMMAR.md`
+ the predicate dispatch chain.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from forge.grammar import load_grammar, validate
from tests.fixtures.strategy_configs import (
    grammar_valid_baseline,
    minimal_registry_snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRAMMAR_PATH = _REPO_ROOT / "config" / "grammar.yaml"
_GRAMMAR_DOC = _REPO_ROOT / "docs" / "GRAMMAR.md"
_ARCHIVE_DIR = _REPO_ROOT / "config" / "grammar_archive"


_EXPECTED_RULE_IDS = (
    # Structural
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    # Composition
    "C1",
    "C2",
    "C3",
    "C4",
    # Parameter
    "P1",
    "P2",
    "P3",
    "P4",
    # Exit
    "E1",
    "E2",
    "E3",
    # Regime
    "R1",
    "R2",
    "R3",
    # Risk
    "X1",
    "X2",
)


@pytest.fixture(scope="module")
def grammar() -> object:
    return load_grammar(_GRAMMAR_PATH, archive_dir=_ARCHIVE_DIR)


def test_v1_grammar_loads(grammar: object) -> None:
    # D039 / T1.4 bumped grammar v1 -> v2 (R3 expanded with macro-event
    # indicators + ETF compatibility).
    # D071-final bumped v2 -> v3 (§3.5 S5 multi-exit schema).
    # D077 bumped v3 -> v4 (R2 expanded with rv_rank regime gate).
    # D098 bumped v4 -> v5 (enumeration-policy only: regime_arbitrage dropped +
    # relative_value re-tested; the 21 `rules:` are textually unchanged).
    # D099 bumped v5 -> v6 (enumeration-layer only: percentile-parameterized
    # signal thresholds for the firing-starved binding-constraint indicators;
    # the 21 `rules:` are again textually unchanged).
    # D100 bumped v6 -> v7 (hurst regime-op fix + mean_reversion cold-start;
    # again enumeration-layer/feedback, the 21 `rules:` unchanged).
    # D102 bumped v7 -> v8 (horizon-matched DTE: §3.5 S4's horizon input moves
    # from registry lookback to the Forge-owned signal_horizon table + the
    # sampler derives DTE from it; enumeration-layer only, the 21 `rules:`
    # unchanged).
    # D103 bumped v8 -> v9 (relative_value quality-bias: pairs pvalue/zscore
    # sampling ranges tightened; enumeration-policy only, the 21 `rules:`
    # again textually unchanged).
    # D105 bumped v9 -> v10 (pairs lookback drops the dead >280 band per
    # Crucible's yield map; enumeration-policy only, the 21 `rules:`
    # again textually unchanged).
    # D107 bumped v10 -> v11 (H3 dealer-gamma regime switch — R2's predicate
    # constant adds gamma_flip_distance_pct; the 21 `rules:` again unchanged).
    # D109 bumped v11 -> v12 (H1 cross_sectional_rank combiner + H2 event_momentum
    # hypothesis; both are Python-side enumeration policy — S1 is `cardinality`,
    # the hypothesis Literal + CombinerSpec live in contracts — so the 21 `rules:`
    # are again textually unchanged).
    # D112 bumped v12 -> v13 (dealer_positioning indicators single-name only —
    # rank-branch skip + relative_value regime-pool exclusion; enumeration-policy
    # only, the 21 `rules:` again textually unchanged).
    # D116 bumped v13 -> v14 (chain-reading indicators join the single-name-only
    # set — iv_rank/put_call_flow never rank, rv pool excludes them; same two
    # enforcement points as v13, the 21 `rules:` again textually unchanged).
    # D118 bumped v14 -> v15 (re-keyed on Crucible's indicator→mode map: the
    # per-name event/DB ids — sue/days_since_earnings/days_to_earnings any-role,
    # expected_value_estimator as gate/directional — join the set; em never
    # ranks; same two enforcement points, the 21 `rules:` textually unchanged).
    # D125 bumped v15 -> v16 (two changes, one boundary: (1) rank/universe
    # exclusion keyed on the contracts-1.18.0 registry flags — explicit id sets
    # retired, confluence role included, new indicators auto-inherit exclusion;
    # (2) P3 trend-scoped delta widening — swing_long/mid upper edges to 0.55,
    # the first hypothesis-scoped P3 override; operator-approved loosening,
    # OPEN_PROPOSALS 343e71fd. The 21 `rules:` textually unchanged).
    # D131 bumped v16 -> v17 (activation + rule edit, operator-approved
    # loosening OPEN_PROPOSALS 2d0d68ca: (1) iv_minus_rv threshold/horizon
    # entries → ve directional via C2, 21d medium horizon → ve x swing_mid
    # reachable; (2) R2 pool += market_state — the rule's own
    # evidence_to_relax clause fired. The 21 `rules:` textually unchanged).
    # D135 bumped v17 -> v18 (the operator-directed adoption cut:
    # (1) iv_term_slope threshold/horizon entries → ve directional via C2,
    # 21d medium horizon — the second medium ve anchor, A2 → full Q28 lift;
    # (2) R3 pool += pre_earnings_setup incl. the ETF-incompatible sets;
    # (3) option_momentum held back — data-starved, Q39. The 21 `rules:`
    # textually unchanged).
    # D138 bumped v18 -> v19 (option_momentum ACTIVATED — Q39 resolved: the v18
    # zeros were min_months=6 sparsity, not coverage. smart_money joins
    # trend_continuation's C2 families; percentile-only directional, min_months=3;
    # EV pinned out of the directional path. The 21 `rules:` textually unchanged).
    # D150 bumped v19 -> v20 (mean_reversion ranging supply: hurst joins R1 as a
    # third ranging gate + regime-gate bias toward ranging; MR rank suppressed
    # pending Q33. Enumeration-policy widening; the 21 `rules:` textually unchanged).
    # D151 bumped v20 -> v21 (Q33 answered YES — hurst per-name-coherent; the MR-rank
    # hold removed, hurst-gated MR now ranks. Enumeration-policy; rules unchanged).
    # D167+D169 bumped v21 -> v22 (two enumeration-policy changes on disjoint slices:
    # (A) rv_rank joins R1 as a fourth mean_reversion ranging gate — Crucible-validated
    # dominant over hurst; (B) event_passed_exit.n_bars_after_entry samples the loosening
    # ladder {3,5,8,13,21}, the D168 time-cut fair test. The 21 `rules:` textually
    # unchanged — R1's accepted-gate set widens in custom_predicates, not the rule text).
    # D236 bumped v22 -> v23 (trend_continuation directional-pool hygiene, Crucible
    # signal-quality handoff: +sma_slope/+ad_slope (percentile-only), prune
    # returns_12m_skip1/macd/ema_cross/supertrend. Threshold+horizon tables only;
    # the 21 `rules:` textually unchanged).
    # D254 bumped v23 -> v24 (MR slice: rv_rank/vol_regime R1 widening + folds the
    # deferred D204 R2 evidence_to_relax metadata fix. rules text unchanged).
    # D257+D258 bumped v24 -> v25 (two enumeration-policy changes: D257 drops the
    # inert zscore_reversion_exit from mean_reversion's S5 set; D258 adds the
    # days_since_jump volatility veto as an optional 2nd trend regime gate; D263
    # (v26) adds the ivol idiosyncratic-vol veto as an optional 2nd MR regime gate.
    # The 21 `rules:` textually unchanged).
    # D264 bumped v26 -> v27 (resid_vix activation: residual_momentum percentile-only
    # trend directional + vix_term_slope R2 calm gate — reverses the v17/D131
    # exclusion on Crucible's first-ever walk-forward-gate pass. Threshold/horizon
    # tables + R2 python-side pool only; the 21 `rules:` textually unchanged).
    # D265 bumped v27 -> v28 (realized_vol absolute MR regime gate: R1 accepted-set
    # widening + MR pool/boost + regime_range (0.15, 0.30); the 21 `rules:`
    # textually unchanged).
    # D266 bumped v28 -> v29 (market_realized_vol: R1 seventh gate + two-member MR
    # veto pool with per-id C1 guard; the 21 `rules:` textually unchanged).
    # D268 bumped v29 -> v30 (earnings-gated underlying exclusion widened to the full
    # no-earnings set; a generation tightening, the 21 `rules:` textually unchanged).
    # D270 bumped v30 -> v31 (capitulation-bounce: momentum drop-trigger MR directional
    # via the first C2 per-id carve-out + pinned rv_rank elevated-vol gate + scoped
    # time_stop n_bars; the 21 `rules:` textually unchanged).
    # D272 bumped v31 -> v32 (earnings-coverage manifest wiring; dormant-until-publish,
    # byte-identical to v31 until Crucible publishes earnings_covered_symbols.json; the
    # 21 `rules:` textually unchanged).
    assert grammar.grammar_version == "v33"  # type: ignore[attr-defined]
    assert len(grammar.rules) == 21  # type: ignore[attr-defined]


def test_v1_grammar_contains_all_21_rule_ids(grammar: object) -> None:
    ids = tuple(r.id for r in grammar.rules)  # type: ignore[attr-defined]
    assert set(ids) == set(_EXPECTED_RULE_IDS)


def test_v1_grammar_rule_order_matches_expected(grammar: object) -> None:
    """Order matters: validator emits errors in declaration order, and
    DESIGN.md §3.5 reads top-to-bottom. Drifting from S→C→P→E→R→X would
    surprise reviewers."""
    ids = tuple(r.id for r in grammar.rules)  # type: ignore[attr-defined]
    assert ids == _EXPECTED_RULE_IDS


def test_v1_grammar_categories_match_id_prefix(grammar: object) -> None:
    prefix_to_category = {
        "S": "structural",
        "C": "composition",
        "P": "parameter",
        "E": "exit",
        "R": "regime",
        "X": "risk",
    }
    for rule in grammar.rules:  # type: ignore[attr-defined]
        expected_cat = prefix_to_category[rule.id[0]]
        assert rule.category == expected_cat, f"{rule.id}: {rule.category} != {expected_cat}"


def test_v1_grammar_all_rules_active(grammar: object) -> None:
    inactive = [r.id for r in grammar.rules if not r.active]  # type: ignore[attr-defined]
    assert inactive == []


def test_v1_grammar_baseline_validates_cleanly(grammar: object) -> None:
    cfg = grammar_valid_baseline()
    registry = minimal_registry_snapshot()
    result = validate(cfg, grammar, registry)  # type: ignore[arg-type]
    assert result.valid, f"baseline should validate; errors: {result.errors}"
    assert result.errors == ()


def test_v1_grammar_rationale_refs_resolve_to_doc_headings(grammar: object) -> None:
    """Every rule's `rationale_ref` (``GRAMMAR.md#{id}``) must point at a
    matching heading in `docs/GRAMMAR.md`. Pre-commit hook (module 11)
    enforces this on every commit; this test runs at unit-level."""
    doc_text = _GRAMMAR_DOC.read_text(encoding="utf-8")
    # Headings of the form `### S1: …` or `## C1: …`
    heading_ids = set(re.findall(r"^#{2,4}\s+([SCPERX]\d+):\s", doc_text, re.MULTILINE))
    grammar_ids = {r.id for r in grammar.rules}  # type: ignore[attr-defined]
    missing = grammar_ids - heading_ids
    assert not missing, f"docs/GRAMMAR.md missing headings for rule ids: {sorted(missing)}"


def test_v1_grammar_archive_in_sync(grammar: object) -> None:
    """The archive entry for v1 must match the on-disk grammar.yaml
    byte-for-byte. The loader already enforces this; the explicit test
    prevents anyone from disabling check_archive and silently drifting."""
    archived = _ARCHIVE_DIR / f"{grammar.grammar_version}.yaml"  # type: ignore[attr-defined]
    assert archived.exists(), f"missing archive entry for {grammar.grammar_version}"  # type: ignore[attr-defined]
    assert _GRAMMAR_PATH.read_bytes() == archived.read_bytes()


def test_v1_grammar_invalid_config_reports_named_rule_errors(grammar: object) -> None:
    """Negative path through the validator: mutate the baseline so a
    specific rule fails, confirm the error list names that rule."""
    cfg = grammar_valid_baseline(dte_bucket="swing_long")  # breaks S4 + P2 + P3
    registry = minimal_registry_snapshot()
    result = validate(cfg, grammar, registry)  # type: ignore[arg-type]
    assert not result.valid
    failing_ids = {e.split(":", 1)[0] for e in result.errors}
    assert "S4" in failing_ids
    assert "P2" in failing_ids
    assert "P3" in failing_ids


# NOTE (D057 / P3-2 2026-05-18): `test_v1_grammar_rule_count_per_category`
# was moved to `tests/invariants/test_phase1_invariants.py`. Hard rule #1
# ("the 21 v1 grammar rules in §3.5 are operator-owned") is a structural
# invariant, not an end-to-end integration property. See D057 in
# IMPLEMENTATION_DECISIONS.md for the rationale.
