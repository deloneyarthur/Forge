# Crucible response — profit_factor tail_hedge exemption

**From:** Crucible-side agent, 2026-05-16.
**To:** Forge `CRUCIBLE_PROFIT_FACTOR_TAIL_HEDGE_AGENT_PROMPT.md`.
**Status:** Shipped. Commit pending.

---

## Fix shipped

Mirrored the `total_return_vs_spy` pattern. `evaluate_gate` already had the `hypothesis: str = "other"` kwarg from the prior commit; the PF block now branches on `hypothesis == "tail_hedge"` and emits `GateResult(passed=True, value=pf, threshold=thresholds.profit_factor_min, direction="skipped_tail_hedge")`. Audit-trail marker preserved.

5 new tests (4 cases + a parametrized matrix guard) appended to `tests/unit/experiment/test_gate_domain_correctness.py`. The matrix iterates the 6 Forge hypotheses × the now-2-gate exempt set and asserts the right outcome per cell — adding a new hypothesis or a new gate that should be domain-conditional now requires a deliberate update there. 52/52 in the full gate scope green. Lint + mypy strict clean.

§20 Decision Log: `2026-05-16 (gate-domain-correctness-pf)`.

## Audit of other gates that might need a `tail_hedge` exemption (NOT shipped — operator decision)

Reading each gate against tail_hedge's left-skewed return distribution (many small decay losses, rare large convex winners):

| Gate | tail_hedge concern | My recommendation |
|---|---|---|
| `cpcv_sharpe_p25 > 1.5` | Worst-quartile Sharpe is naturally negative in quiet quarters with no tail event — this measures the strategy's *cost-of-insurance* periods | **Surface for operator** — strongest candidate after PF |
| `walk_forward_sharpe_median > 2.0` | Median across multi-fold is severe if most folds are quiet | Surface for operator — median is more forgiving than p25 but still pressured |
| `bootstrap_ci_sharpe_lower > 0.5` | Lower CI bound on a left-skewed distribution penalizes the rare-win shape | Surface for operator |
| `regime_stress_p25 > 0.0` | MC trade-bootstrap P25 on a tail_hedge ledger reflects quiet-regime decay; the strategy's value is in the *non-bootstrapped* tail | **Strongest case** for exemption — but this gate is already getting upgraded to §9.2 synthetic stress in v3 which should naturally include tail events; defer until v3 lands |
| `walk_forward_calmar_median > 3.0` | tail_hedge's DD-during-good-times is low; Calmar could actually be HIGH | Likely fine strict |
| `walk_forward_max_drawdown_worst < 0.15`, `cpcv_max_drawdown_p75 < 0.20` | Equity DD on a 2%-per-trade / 15%-concurrent-capped hedge should stay bounded | Strict OK |
| `pbo < 0.4`, `deflated_sharpe > 0.95` | Hypothesis-agnostic statistical machinery | Strict OK |
| `min_oos_trade_count` (per bucket) | Sample-size meaningfulness | Strict OK |
| `stability_max_yearly_decay_pct < 0.30` | Year-over-year Sharpe stability is pathological for tail_hedge (one event-year vs. one quiet-year is a huge ratio) | Surface for operator |

**Three gates I'd flag specifically**: `cpcv_sharpe_p25`, `walk_forward_sharpe_median`, `stability_max_yearly_decay_pct`. All three measure "consistent risk-adjusted return," which is exactly what tail_hedge *isn't* — its value is in the rare event. `regime_stress_p25` belongs in the same bucket but the v3 synthetic-stress upgrade may naturally include tail events that fix this, so I'd defer it until that lands.

If you want me to ship any of these, drop another prompt with the operator approval and I'll mirror the same pattern + extend the matrix test.

## Verification

```
tests/unit/experiment/test_gate_domain_correctness.py ............      [ 23%]
tests/integration/test_gate.py ...................                      [ 59%]
tests/integration/test_gate_phase_d_ports.py ...........                [ 80%]
tests/integration/test_gate_phase_e_ports.py ..........                 [100%]
52 passed in 1.25s
```

TDD red-first: 2 of the 5 new tests red before patch (PF branch + matrix's tail_hedge row); after patch all green.

## Restart required

None. `evaluate_gate` is still only imported by the on-demand `scripts/run_campaign.py` CLI.

## What I did NOT do

- Did not exempt `volatility_event` from PF (consistent with prior decision; alpha-seeking).
- Did not lower the global `profit_factor_min` threshold.
- Did not ship exemptions for `cpcv_sharpe_p25` / `walk_forward_sharpe_median` / `stability_max_yearly_decay_pct` — surfaced as candidates above, awaiting operator decision.
- Did not change Forge code.
