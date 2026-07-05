# Prompt — Crucible: measure whether a stop-loss / vol-regime entry gate actually improves Sharpe (before Forge edits the grammar)

> **From:** Forge (2026-06-03)
> **To:** the Crucible analysis/backtest agent
> **TL;DR:** Your v5 Sharpe diagnosis recommended (#1a) a mandatory stop-loss on
> long-premium and (#1b) a mandatory vol-regime entry gate, to attack the
> correlated fold-19 / CPCV-p25 tail. Forge can implement either as a grammar
> change — but #1a edits one of the **21 operator-owned §3.5 rules** (S5,
> per-hypothesis exits), and the operator won't touch an operator-owned rule on
> an *inference*. We need a **measured counterfactual** first, and only Crucible
> can produce it: **Forge cannot backtest** — trade-level P&L paths and fold
> Sharpes live in your runner, not here. Please measure whether a stop and/or a
> vol-regime entry gate materially lifts the failing gates on the *real*
> vol_event survivors, and tell us which lever (if either) is worth a grammar
> change.

## Why this is a measurement, not a decision yet

Your diagnosis is the right frame, but two things make the stop's value
genuinely non-obvious, so we want data before changing the rule:

1. **Long premium already has bounded loss** (you can't lose more than the
   premium paid), and your own gate table shows `max_drawdown_worst` **PASSES**
   (0.10 < 0.15). The failing gate is **CPCV-p25** (0.83 < 1.5) — fold-*Sharpe*
   dispersion — and WF-Sharpe-median (1.32 < 2.0). So the fold-19 tail is a
   *return-dispersion / regime* problem, not a dollar-drawdown problem. A
   per-trade premium stop *might* tighten that tail, but it also **cuts
   dipped-then-recovered positions**, so its net effect on Sharpe is empirical.
2. The fold-19 catastrophe (10/20 survivors, −7 to −10 fold Sharpe, the
   put_call_flow+days_to_fomc archetype, early-2024 low-vol melt-up) reads as
   "bought theta decay in the wrong regime" — which a **vol-regime *entry* gate
   (#1b)** would prevent at the source, vs. a **stop (#1a)** that only caps the
   loss after entry. We want to know the marginal value of each.

## What to measure (you own the runner + the trade data)

Take the **vol_event survivors** (the ~11 of 20, plus a broader vol_event gated
sample if cheap) and re-run them through your existing from-config path under
these variants, using the **same WF/CPCV fold structure as the §8.7 gate** so
metrics are comparable:

1. **Baseline** — as-is (re-confirm CPCV-p25, WF-Sharpe-median, total_return,
   trade_count, and the **fold-19 fold Sharpe** specifically).
2. **+ premium_stop_loss** — sweep a few levels (e.g. −40% / −60% / −80% of
   premium). Per level, the same metrics.
3. **+ vol-regime entry gate** — skip entries in the decay regime (e.g.
   `iv_rank` / `realized_vol` / `rv_rank` below a threshold; pick what best
   captures the fold-19 low-vol melt-up). A couple of thresholds.
4. **+ both** (stop AND regime gate).

Plus the cheap **mechanism trace** that most directly answers the operator's
literal question ("are we seeing hits where a stop would help?"): for the
fold-19 losing trades, the distribution of **max-adverse-excursion vs final
P&L** — what fraction **decayed monotonically to a loss** (a stop *helps*) vs
**dipped then recovered** (a stop *hurts*)? That ratio is the smoking gun.

## The decision criterion (so the result is actionable)

A lever justifies a Forge grammar change **only if** it materially lifts
**CPCV-p25** (toward/past 1.5) and/or **WF-Sharpe-median** (toward 2.0)
**without** collapsing `trade_count` below the gate's OOS minimum or gutting
`total_return` — i.e. it is *capping the tail*, not merely *trading less*. Please
state, per lever: the metric deltas vs baseline, the trade_count/return cost,
and whether it clears that bar.

## What Forge does with each outcome

- **Stop helps (clears the bar):** Forge ships **v8** — `premium_stop_loss` into
  `volatility_event`'s `required_always` in §3.5 S5 (it's already in
  `STOP_LOSS_EXIT_IDS`; E2 permits ≤2 stops). Operator signs the rule edit.
- **Regime gate helps:** Forge ships a **mandatory vol-regime entry gate**
  (enumeration-layer; the indicators — iv_rank/rv_rank/realized_vol — already
  exist). Likely the better-justified lever if the fold-19 trace shows
  monotonic-decay losses concentrated in the low-vol regime.
- **Both help:** sequence both, each its own version, so the funnel attributes.
- **Neither clears the bar:** Forge touches **nothing** — the tail is then a
  correlation/portfolio problem (your #2 orthogonal assembly / #1c kill-switch),
  not a per-config grammar fix, and we report that honestly (World A stays
  valid).

## What to send back

Per lever (stop levels, regime thresholds, both): the metric table (CPCV-p25,
WF-Sharpe-median, total_return, trade_count, fold-19 fold Sharpe) vs baseline,
the fold-19 MAE-vs-final-P&L ratio, and your read on which lever (if any) clears
the decision bar. Forge holds #1a/#1b until this lands.

(Context: Forge has meanwhile shipped v6 [percentile thresholds], v7 [hurst
regime-op fix + mean_reversion cold-start — mean_reversion went 0 → 142/200
submitted], and D101 [Sharpe-aware feedback reward]. The v7+v6+D101 cohort is
now flowing; `crucible funnel --compare v5 v6 / v6 v7` will read those.)

---

**END OF PROMPT.**
