# Crucible — profit_factor exemption for tail_hedge (follow-up)

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-16 — operator approval after your PF/tail_hedge flag in `CRUCIBLE_GATE_DOMAIN_CORRECTNESS_AGENT_RESPONSE.md` §"What I did NOT do".
**Status:** Single-fix follow-up. Same pattern as the `total_return_vs_spy` exemption you just shipped.

---

## TL;DR

You flagged that `profit_factor`'s `_check_gt(pf, thresholds.profit_factor_min)` is unconditional, while `direction_balance` and (now) `total_return_vs_spy` both have `tail_hedge` exemptions. Operator agrees: ship the same exemption for `profit_factor`. The reasoning is identical — `tail_hedge` is long-premium / convex-tail / negative-carry by design; PF = Σwins / Σlosses is structurally < 1 even when the strategy is correctly providing tail protection, because the strategy expects many small decayed-premium losses punctuated by occasional large convex winners.

This is **not** a gate-strictness relaxation (Forge hard rule #3 forbids that). It's the same gate-domain-correctness pattern: the gate's intent ("winners outweigh losers in raw dollar terms") doesn't apply to insurance hypotheses whose claim is *convex* protection rather than positive expected return.

## 1. Background

From your prior response (verbatim):

> Forge's prompt cited "PF and direction_balance" as having existing exemptions. Direction_balance does (`quality_bar.py:61`). **PF does not** — `_check_gt(pf, thresholds.profit_factor_min)` is unconditional today. If PF should also exempt tail_hedge (the "long-premium can have PF < 1 by design" case), that's a separate fix worth surfacing.

(Forge-side audit-agent error: misattributed the PF exemption that does not exist. Apologies; the rest of the structural-capacity audit still holds.)

## 2. Why this is the same fix shape as `total_return_vs_spy`

| Gate | What it claims | Why `tail_hedge` is wrongly rejected |
|---|---|---|
| `total_return_vs_spy > 1.5×` | Strategy beats buy-and-hold | tail_hedge is *paying for insurance*, not seeking alpha-vs-SPY |
| `profit_factor > 1.4` | Σwins > 1.4×Σlosses in raw $ | tail_hedge has many small premium-decay losses + rare large convex winners → PF < 1 typical, even when CVaR / max-DD-during-stress profile is correct |
| `direction_balance` (already exempted) | Both long+short represented | tail_hedge by design is one-sided protection |

Same operator-level claim as the prior two: a `tail_hedge` strategy that scores *well on its own merits* (e.g., Sharpe on tail-event-period subsets, max-DD reduction during VIX spikes, hedge-cost-per-event-protection ratio) shouldn't be auto-rejected by a gate that was designed to filter alpha-seeking directional strategies.

## 3. Proposed fix shape

Mirror what you just did for `total_return_vs_spy`:

1. The `evaluate_gate` `hypothesis: str = "other"` kwarg you just added is already in place — use it.
2. When `hypothesis == "tail_hedge"`, the `profit_factor` evaluation short-circuits to `passed=True` with `direction="skipped_tail_hedge"` (matching your `direction="skipped_tail_hedge"` convention on `total_return_vs_spy`).
3. `scripts/run_campaign.py:1177` already passes `hypothesis=best_trial.config.hypothesis` through — should be no campaign-side change required.
4. **TDD red-first**: write the invariant test first that constructs a synthetic `tail_hedge` run with PF=0.7 and asserts `evaluate_gate(..., hypothesis="tail_hedge")` returns the gate as `skipped_tail_hedge`, while the same metrics with `hypothesis="mean_reversion"` still fail. Then implement.

## 4. What you should NOT do

- **Do not lower** the global `profit_factor_min` threshold. Only the `tail_hedge` per-hypothesis branch should skip.
- **Do not apply the exemption to** other hypotheses unless the same negative-carry argument holds. `volatility_event` is alpha-seeking per your prior reading; do not exempt it from PF (consistent with you leaving its `total_return_vs_spy` strict).
- **Do not skip the test.** The pattern is now load-bearing — three gates have per-hypothesis branches; a regression on one would silently let bad candidates through. The invariant test guards against future "I added a new hypothesis and forgot to think about which gates exempt it" mistakes — write it parametrized over the (gate, hypothesis) matrix if cheap.
- **Do not change Forge code.**

## 5. Output expected

1. Confirmation diagnosis is right (or pushback with citation)
2. Fix shipped — should be a ~10-line change + a parametrized invariant test
3. Decision Log entry citing this prompt + the prior gate-domain-correctness prompt
4. Note in the response: any other quality-bar gate that currently lacks a `tail_hedge` exemption you think *should* have one. Easier to bundle now than re-litigate later.

Brief is fine. Under 200 words of report unless something surfaces.
