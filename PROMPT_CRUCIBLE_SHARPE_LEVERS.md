# Prompt — Crucible: Forge's response to the v5-grammar Sharpe diagnosis

> **From:** Forge (2026-06-03, after re-deriving the two levers you flagged for us)
> **To:** the Crucible analysis agent
> **TL;DR:** Excellent diagnosis — Artifacts 1–3 and the 1.911<2.0 ceiling are the
> right frame, and we're acting on the in-scope levers (ship-as-ready). Two
> corrections on the items you (correctly) marked "Forge must re-derive," and two
> ownership clarifications. **We are NOT writing off long-premium scope (#5)** —
> the operator's call is "not verified; need far more data first." Keep gating
> in-scope; don't enshrine 1.911 as a scope verdict yet.

## On the two things you asked Forge to re-derive

**#4 "objective alignment" — your mechanism was a misread, but the gap is real and we're fixing it.** Forge has **no NSGA-II, no Pareto, no `(return, max_drawdown)` objective, no sweeper** — that's *your* demo `sweeper.py`, not Forge. Forge is enumerate → pre-filter → rank → feedback-weight; nothing in it optimizes a return/DD objective. **But** the underlying point holds, reframed: Forge's feedback reward (`compute_hypothesis_reward_weights`, D094) is **Sharpe-blind** — it's `0.6·traded + 0.4·(generic fraction of gates passed)`. And `walk_forward_sharpe_median` is **already in the gated-run export and already extracted** (`analyzer.HypothesisMetrics.avg_sharpe`) — then never used. So Forge's gradient currently rewards "fires + passes the *easy* gates (Calmar/DD)" and is indifferent to the Sharpe axis that's failing — the Forge analog of your Calmar-passes/Sharpe-fails fingerprint. **Fix (in progress):** wire WF-Sharpe into the feedback gradient (no contract change — the data's already there), with a diversity guard so it doesn't just collapse onto vol_event (which would worsen the monoculture you flagged in Artifact 2).

**#3 "k≥2 confluence" — confirmed k=1, but it's not a combiner one-liner.** Forge does hardcode `CombinerSpec(k_of_n, k=1)`. But the combiner's `k` applies **only to confluence signals**; directional ∧ regime_filter are already AND-ed separately (the activation-date intersection). So entries are *not* pure OR — they already require directional AND regime. Every config is `1 directional + 1 regime + 0–1 passthrough` (S2 forbids a 2nd directional), so there's nothing to raise `k` *over*. The tractable, equivalent lever is **a mandatory 2nd (vol-)regime gate** — which is exactly your #1b. We'll do that (entry = directional ∧ event-proximity ∧ vol-regime), drawing the 2nd gate from the existing iv_rank/rv_rank/realized_vol pool. That attacks both your "inert single threshold" (#3) and "buys decay in low-vol" (#1b) at once.

## Ownership clarifications (these are yours, not Forge's)

- **#2 orthogonality-aware assembly** is Crucible-side — Forge emits individual candidates; you assemble/gate the portfolio. **Key dependency, from your own Artifact 1:** Forge's *emission* is already balanced (trend 33% / vol_event 29% / mean_rev 19% / rel_value 19%); the monoculture appears only **after your gate** — it's a *survival* artifact, not a generation one. So orthogonal assembly only has material once **survival** widens. Forge's #1a (stops) + #1b/#3 (2nd vol-regime gate) are aimed exactly at making the non-vol_event archetypes survive — so the sequencing is: Forge widens survival → then your correlation-cap/HRP assembly has ≥1 real archetype to diversify across. Until then, capping correlation on a pool that's ~3.6 independent bets can't manufacture diversity.
- **#1c portfolio kill-switch** (de-gross long-premium on a vol spike) is Crucible-side runtime — Forge has no portfolio view. It's the right tool for the *correlated* fold-19 tail that per-strategy stops can't reach; worth building alongside Forge's per-config stops (#1a), which attack the same tail from the single-strategy side.

## What Forge is shipping (ship-as-ready, each its own grammar version where it changes emission)

1. **hurst regime-op fix (v7, now):** trend_continuation's `hurst` regime gate was `op="<"` (allowed the *mean-reverting* regime — backwards). Flipped to `op=">"` (allow when trending). Complements v6's percentile-izing of the same gate. This may itself be part of trend_continuation's "most-emitted, barely-survives" problem (Artifact 1) — a regime gate pointed at the wrong regime suppresses co-firing with the trend directional signal.
2. **Sharpe-aware feedback (#4):** as above.
3. **mandatory stop on vol_event (#1a, a §3.5 S5 grammar-rule change):** vol_event's exit set carries no stop-loss (`iv_crush_exit + event_passed_exit` only) — it rides losers to expiry. `premium_stop_loss` is in `crucible_contracts` + `STOP_LOSS_EXIT_IDS` and within E2's ≤2-stop cap; we'll make it mandatory on long-premium templates.
4. **mandatory 2nd vol-regime gate (#1b/#3):** as above.

## On #5 (scope ceiling) — explicitly NOT being written off

Your 1.911<2.0 ceiling across 52,593 runs is noted and is the honest framing for *why* in-scope levers may not reach 2.0. But the operator's decision is: **this is not verified enough to make a scope call** — single-leg long-premium stays the v1 scope (hard rule #9), and we gather far more data (post-v6/v7, post-stops, post-2nd-gate) before anyone entertains spreads/premium-selling. Please **keep gating in-scope and keep reporting honestly** (World A — no edge in scope — remains a valid outcome we report, not tune to); do **not** treat 1.911 as a settled ceiling or push the scope-expansion narrative yet. If the in-scope levers move the ceiling materially, that itself is data on the scope question.

## What would help from your side

- Confirm the **per-run Sharpe fields** Forge should weight on: we'll use `walk_forward_sharpe_median` (and consider `cpcv_sharpe_p25` to punish the left tail). If there's a better single field for "this candidate is closer to passing," name it.
- As Forge's #1/#3 land, watch whether **non-vol_event survival** widens (the precondition for your #2). That's the shared success metric.

---

**END OF PROMPT.**
