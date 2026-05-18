# Crucible — complete the gate-domain-correctness pattern (ship + port)

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-16 — operator approval to ship the 3 follow-up exemptions you audited in `CRUCIBLE_PROFIT_FACTOR_TAIL_HEDGE_AGENT_RESPONSE.md`, **plus** port the established pattern from the campaign path to the runner-daemon path.
**Status:** Two-part — Part 1 is a pattern repeat; Part 2 is the larger structural ask.

---

## Why this matters

Forge-side audit of `_build_forge_minimal_decision` (`src/optbt/data/runner.py:439-636`) confirmed that the gate-domain-correctness fixes you've shipped so far all live in `evaluate_gate` (campaign-only) and never reach Forge's runner-daemon submissions. Some gates (`profit_factor`, `cpcv_sharpe_p25`, `walk_forward_sharpe_median`) appear in *both* paths; others (`cross_ticker_min_passing`, `total_return_vs_spy`) live only in the campaign. To make the work actually reach Forge runs, the runner path needs the same `hypothesis` kwarg branching where the gates overlap.

Operator's net intent: complete the pattern across both paths so tail_hedge stops getting auto-rejected for reasons unrelated to strategy quality, in both eval surfaces.

---

## Part 1 — Three more campaign-path `tail_hedge` exemptions

Operator approves shipping `tail_hedge` exemptions for the 3 gates you specifically flagged in §"Audit of other gates":

| Gate | Threshold | Why exempt |
|---|---|---|
| `cpcv_sharpe_p25 > 1.5` | strongest case after PF | Worst-quartile Sharpe in cost-of-insurance quiet quarters is structurally negative; gate's intent ("consistent risk-adjusted return") doesn't apply to convex-tail strategies |
| `walk_forward_sharpe_median > 2.0` | second strongest | Median across folds is severe when most folds are quiet (no tail event); same domain-mismatch argument |
| `stability_max_yearly_decay_pct < 0.30` | third | Year-over-year Sharpe stability is pathological for tail_hedge — one event-year vs. one quiet-year is a huge ratio by design |

**Deferred per your recommendation**: `regime_stress_p25` (v3 synthetic stress should naturally include tail events that re-enable this gate honestly).

**Not exempted**: `bootstrap_ci_sharpe_lower > 0.5` — operator defers to your "Three gates I'd flag specifically" subset; the lower-CI gate's behavior on left-skewed distributions is similar in logic but you didn't put it in the strong-case bucket, and stopping at the 3 you flagged most-strongly keeps the exemption set minimal.

Apply the same pattern you used for PF: `evaluate_gate(..., hypothesis="tail_hedge")` short-circuits each gate to `passed=True` with `direction="skipped_tail_hedge"`. Extend the parametrized matrix test in `tests/unit/experiment/test_gate_domain_correctness.py` — your prior commit already iterates `(gate, hypothesis)` pairs, so the new cells should be a 3-row addition with the existing assertion shape.

---

## Part 2 — Port the pattern to `_build_forge_minimal_decision`

The runner-daemon path at `src/optbt/data/runner.py:439-636` evaluates a smaller, single-period gate cascade that Forge submissions actually face. It currently has **no per-hypothesis branching at all**. Where the gates overlap with the campaign path, the same `tail_hedge` exemptions should apply.

### Scope of the port

Threading:
- Add `hypothesis: str = "other"` kwarg to `_build_forge_minimal_decision` (line 439).
- Add the same kwarg to `_finalize_fresh_run` (line 106).
- The caller at line 138 (`_finalize_fresh_run` → `_build_forge_minimal_decision`) already has access to the run's `StrategyConfig` upstream — thread `config.hypothesis` through (mirroring how `dte_bucket` is already threaded for `default_min_oos_trades_for_dte_bucket`).
- Default `"other"` keeps existing test/CLI callers compatible.

Gates in the runner path that get the `tail_hedge` exemption:

| Gate in runner | Line in runner.py | Same exemption as campaign-side? |
|---|---|---|
| `profit_factor` (threshold `_MIN_PROFIT_FACTOR = 1.0`) | 512-518 | **Yes** — mirror campaign PF exemption |
| `cpcv_sharpe_p25` (threshold `_MIN_CPCV_SHARPE_P25 = 1.0`) | 537-549 | **Yes** — mirror Part 1 exemption |
| `walk_forward_sharpe_median` (threshold `_MIN_WALK_FORWARD_SHARPE_MEDIAN = 2.0`) | 523-535 | **Yes** — mirror Part 1 exemption |

Gates **not present** in the runner path (no porting needed): `cross_ticker_min_passing`, `total_return_vs_spy`, `bootstrap_ci_sharpe_lower`, `stability_max_yearly_decay_pct`, `walk_forward_calmar_median`, `walk_forward_max_drawdown_worst`, `cpcv_max_drawdown_p75`, `pbo` (single-config = trivially passes), `regime_stress_p25_return` (different shape via trade-bootstrap; defer along with campaign-side per your recommendation).

### Test discipline

TDD red-first: extend or duplicate the matrix-test pattern from `tests/unit/experiment/test_gate_domain_correctness.py` to cover `_build_forge_minimal_decision`. The cells should be (3 gates × tail_hedge → passed=True with `direction="skipped_tail_hedge"`) plus (3 gates × non-tail_hedge → original threshold behavior). Run red first, then patch, then green.

### Note: the runner thresholds are intentionally more permissive

The runner uses `_MIN_PROFIT_FACTOR = 1.0` (campaign 1.4) and `_MIN_CPCV_SHARPE_P25 = 1.0` (campaign 1.5). This is intentional — single-period eval vs. multi-fold campaign. **Do not change the thresholds** as part of this port; only add the per-hypothesis exemption branch. The threshold differences are correct.

### Minor cleanup (optional)

The docstring at `runner.py:465-475` says:

> "Decision is always 'reject' until the full gauntlet is wired"
> "Phase 9 v3 wires WF/CPCV/PBO/DSR, the structural reject lifts and `passed=all(...)` becomes the real promotion path"

Reading the code, the gauntlet **is** wired — `walk_forward` and `cpcv` are called at lines 737-756 and the resulting median/p25 are threaded through to the gate. The docstring is stale. Update to reflect current behavior ("promotion is structurally possible but tight; the threshold-vs-real-data realities discussed in §X are the binding constraints") — small cleanup, not blocking.

---

## What you should NOT do

- **Do not lower any thresholds**. Forge hard rule #3 stands. This work is exemption (gate-domain-correctness) not relaxation (gate-strictness).
- **Do not align runner and campaign thresholds**. They're correct as different surfaces.
- **Do not port `regime_stress_p25` exemption**. Per your prior recommendation, defer until v3 synthetic stress lands.
- **Do not change Forge code.**
- **Do not skip the test-first discipline.** The matrix-test pattern you've established is now load-bearing across two paths; the invariant of "adding a new hypothesis or a new gate that should be domain-conditional requires a deliberate update there" must extend to the runner path test cases.

## Output expected

For each part:

1. Diagnosis confirmation (or pushback)
2. Fix shipped — Part 1 should be ~3× a copy of the PF pattern; Part 2 is the larger structural change with the threading + matrix-test extension
3. Verification: both campaign-side and runner-side tests green; mypy strict + ruff clean on both modules
4. Decision Log entries — separate row each part is fine, or one row covering both with a "Parts 1+2" note
5. **Restart required**: yes for Part 2 since `_build_forge_minimal_decision` is in the runner-daemon process. Note this in the response so we know to restart `crucible-runner.service` after the merge

Brief is OK. Aim for under 500 words of report. The pattern is established; you mostly need to confirm the diagnosis (especially Part 2's threading) and ship.
