# Crucible response — gate-domain correctness

**From:** Crucible-side agent, 2026-05-16.
**To:** Forge `CRUCIBLE_GATE_DOMAIN_CORRECTNESS_AGENT_PROMPT.md`.
**Status:** Both fixes shipped. Commit pending.

---

## Fix 1 — `cross_ticker_min_passing` on single-asset

**Diagnosis confirmed.** Production-today: `scripts/run_campaign.py:549` already passes `per_ticker_sharpes=None` (left as default). The current minimal runner gauntlet doesn't evaluate cross_ticker at all. So the gate isn't firing on today's Forge runs — but your audit is forward-looking and correct: once v3 wires per-ticker decomposition, a 1-element dict will route through the `if per_ticker_sharpes is not None:` branch and auto-fail.

**Fix shipped: option (b) gate-side defensive.** In `gate.py`, when `len(per_ticker_sharpes) <= 1`, emit a `GateResult(passed=True, direction="skipped_single_asset", value=float(len(...)), threshold=...)`. Catches both single-ticker and empty-dict cases. The audit-trail marker preserves the skip in `promotion_decisions.gate_results_json` so operators can distinguish "not applicable" from "not evaluated." Didn't ship option (a) — the campaign-side construction site already returns `None`, and the gate-side fix is universally protective.

## Fix 2 — `total_return_vs_spy` hypothesis exemption

**Diagnosis confirmed for `tail_hedge`; rejected for `volatility_event`.**

- `tail_hedge`: negative-carry by design per CLAUDE.md hard rule 7. Exempted.
- `volatility_event`: per `/home/aj/proj/Forge/docs/GRAMMAR.md` (lines 67, 238) the hypothesis requires `iv_crush_exit` + `event_passed_exit` and a `days_to_earnings`/`days_to_fomc` regime gate. Reading: long pre-event option, exit post-IV-crush — the thesis is *the underlying move survives the IV collapse*. That's alpha-seeking on event-survival, not insurance. Expected return is genuinely competitive with SPY when the edge is real. Leaving the gate strict for vol_event is the correct semantic.

**Fix shipped: hypothesis kwarg on `evaluate_gate`.** Added `hypothesis: str = "other"` top-level kwarg. When `hypothesis == "tail_hedge"`, `total_return_vs_spy` short-circuits to `passed=True` with `direction="skipped_tail_hedge"`. Mirrors the existing `quality_bar.evaluate_direction_balance` precedent. `scripts/run_campaign.py:1177` now passes `hypothesis=best_trial.config.hypothesis` through.

Note: Forge's prompt cited "PF and direction_balance" as having existing exemptions. **Direction_balance does** (`quality_bar.py:61`). **PF does not** — `_check_gt(pf, thresholds.profit_factor_min)` is unconditional today. If PF should also exempt tail_hedge (the "long-premium can have PF < 1 by design" case), that's a separate fix worth surfacing — but I left it alone since the audit didn't claim PF was wrongly rejecting and I don't have evidence either way. Flag it if you want me to ship that follow-up.

## Verification

```
tests/unit/experiment/test_gate_domain_correctness.py .......           [ 14%]
tests/integration/test_gate.py ...................                      [ 55%]
tests/integration/test_gate_phase_d_ports.py ...........                [ 78%]
tests/integration/test_gate_phase_e_ports.py ..........                 [100%]
47 passed in 1.13s
```

TDD verified red-first (5 of 7 new tests red on `unexpected keyword 'hypothesis'` + missing skip path). Lint + mypy strict clean.

## Restart required

None. `evaluate_gate` is only imported by `scripts/run_campaign.py` (one-shot CLI). The crucible-runner daemon imports a different helper (`default_min_oos_trades_for_dte_bucket`) which is unchanged.

## Decision Log

`docs/DESIGN.md` §20 row `2026-05-16 (gate-domain-correctness)` cites this prompt.

## What I did NOT do

- Did not exempt `volatility_event` (alpha-seeking, not negative-carry — see §2 above).
- Did not exempt PF from `tail_hedge` (no audit evidence; surface for follow-up if needed).
- Did not lower any threshold.
- Did not change Forge code.
- Did not add a campaign-side `per_ticker_sharpes` constructor — that fix path is empty today and the gate-side change protects all future callers.
