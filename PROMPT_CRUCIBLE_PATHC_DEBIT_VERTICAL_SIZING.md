# Prompt — Crucible: Path-C VIABILITY SIZING — net-of-cost per-regime CPCV magnitude + SAFETY/tail of defined-risk structures, rung by rung (debit-verticals first)

> **From:** Forge (Path-C viability sizing — the deferred "part 3" of the magnitude/cost decomposition, now
> ACTIVATED because the long-options exhaustion gate is satisfied). Companion to
> `docs/proposals/regime-orthogonal-arms.md` (the gated Path-C probe+test program — this is its
> *viability-sizing* step) and `docs/proposals/long-options-exhaustion-assessment.md`.
> **To:** the Crucible agent (the only side that can measure this — Forge computes no metrics, §1.2).
> **Trigger:** your `FORGE_long_options_exhaustion_consolidated.md` CONFIRMED long-options is exhausted
> (M1 gross max 1.40 < 1.5, IC-bound; quad-convergent) → the operator's Path-C provability gate
> ("only open v2 if long-options provably can't clear the bar") is **SATISFIED**. You noted the documented
> edge is structurally on the SELL side (`vrp_short_premium_by_regime.json`: short-vol positive every regime,
> strongest in low-vol/calm) and that debit-vertical **sizing is already in flight** — please surface it.
>
> **TL;DR.** Size the **upside** of a possible scope expansion to defined-risk multi-leg structures, so the
> operator can decide whether the magnitude justifies the (multi-quarter, cross-system) build. This is
> **informational only — no gate/threshold/promotion-bar change (hard rules 3/6), no build commitment.** The
> operator's frame is strict: **start at the minimal, safest rung (net-debit, defined-risk) and only climb if
> the magnitude isn't there lower down**; full premium-selling is the **true last resort**. So we need
> **magnitude AND tail/safety, rung by rung**, and the **lowest rung that clears the SAME §8.7 bar** per
> adverse regime.

## 0. The decision this sizes (and the operator's non-negotiables)

The promotion unlock is a promotion-grade (CPCV-p25 ≈ 1.5, full §8.7 battery) per-regime edge in the adverse
regimes — **bear (worst-quartile 2.39×) and ranging (1.33×)** — which long premium provably cannot supply.
The natural high-Sharpe adverse-regime edge harvests the VRP instead of paying it, which requires multi-leg /
short-premium structure (out of v1's net-debit single-leg long-premium scope, hard rule 9). Before the
operator will even consider a hard-rule-9 scope expansion, two things must be true and **sized**, not assumed:

1. **The magnitude must actually clear the bar — net of cost, OOS-robust.** Not a higher gross per-slice
   Sharpe; the **full §8.7 battery (CPCV-p25 + WF + DSR) at portfolio scope** (hard rule 3 — same gate
   long-options failed). Spreads have **2–4 legs → more cost surface**; the short leg harvests VRP but the
   long leg(s) still pay it, so the net is genuinely uncertain and must be measured, not inferred.
2. **It must be SAFE.** "Defined-risk" caps loss *per trade*, but a **book** of short-vol-exposed spreads can
   lose *together* in a vol spike (the Feb-2018 "volmageddon" pattern). The operator's words: a scope
   expansion needs "a massive probe and test to see how viable and **safe** risk-defined spreads would be."
   A high Sharpe with a fat correlated left tail does not pass.

## 1. The ask — magnitude AND tail/safety, RUNG BY RUNG (risk-ordered)

For each adverse regime (bear, ranging), walk **up** the defined-risk spectrum and report, per rung:
**(a)** net-of-cost per-regime **CPCV-p25** (+ does it clear the full §8.7 battery, WF + DSR included);
**(b)** **gross-vs-net** (the multi-leg cost wedge — how much does the extra leg cost vs the VRP the short
leg harvests); **(c)** the **safety/tail read** — worst-case correlated-book drawdown in a vol spike, left-tail
shape, max-loss realization frequency. Then name the **lowest rung that clears the bar** for that regime.

The rungs, lowest-risk first (map your structure taxonomy onto these):

- **Rung 1 — net-debit, defined-risk (the minimal, safest step; the operator's preferred entry).**
  - **BEAR → bear put spread** (long higher-strike put + *covered* short lower-strike put): net-debit,
    max-loss = the debit, no naked short. This is the clean minimal structure for the bear adverse regime —
    does it reach ~1.5 net-of-cost, and how does its tail compare to the long-put it replaces?
  - **RANGING → long butterfly / long condor** (net-debit, defined-risk, range-profiting — the net-debit way
    to express theta/mean-reversion without writing naked premium). Does a net-debit ranging structure exist
    that clears the bar, or does ranging *structurally* require net-credit (rung 2)?
- **Rung 2 — net-credit, defined-risk (iron condor / put-credit spread; harvests more VRP, carries the
  correlated short-vol tail).** Magnitude *and* the tail cost — this is where the volmageddon risk enters.
- **Rung 3 — naked premium-selling (short strangle/straddle; the TRUE last resort).** Size it only as the
  *ceiling* — what magnitude are we leaving on the table by refusing the uncapped tail? We do not expect to go
  here; it bounds the trade-off.

## 2. The verdict we need from you (one line per regime)

Per adverse regime: **what is the lowest rung whose net-of-cost magnitude clears the §8.7 bar with an
acceptable tail** — and is that magnitude advantage over the (exhausted) long-premium base **large enough to
justify a multi-quarter, cross-system, hard-rule-9 scope expansion?** If the bar is only cleared at rung 2+
(correlated short-vol tail), say so explicitly — that materially raises the operator's safety threshold.

## 3. What Forge does with each answer
- **Rung 1 clears (bear put spread / net-debit ranging) →** the minimal, safest scope expansion is on the
  table; we bring the operator a scoped hard-rule-9 proposal entered at debit verticals, and the
  `regime-orthogonal-arms.md` SAFETY probe+test program runs *before* any grammar v2 build.
- **Only rung 2+ clears →** the operator weighs the (larger) magnitude against the correlated short-vol tail;
  the safety probe becomes the gating artifact, and naked selling (rung 3) stays off the table.
- **No rung clears the full battery net-of-cost →** Path C is *also* not the unlock; we report that and the
  producer's promotion frontier is genuinely capped at current scope (a major finding in itself).

## 4. What Forge is NOT asking
No gate / threshold / promotion-bar change (hard rules 3/6). No build commitment, no grammar change — nothing
ships off this. This **sizes the upside** so the operator can make the scope-expansion call on evidence. And
it is **parallel to**, not a replacement for, the standing **M1/M2 long-options monitor** (re-run as the
decided-CPCV population grows — gross 1.40 is a thin margin); if that monitor reopens long-options, this is
moot.

---

*Relay status: drafted 2026-06-15, awaiting operator relay (`docs/tasks/crucible-handoff.md`). Activates the
deferred part-3 of `PROMPT_CRUCIBLE_MAGNITUDE_COST_DECOMPOSITION.md` (superseded) now that
`PROMPT_CRUCIBLE_LONG_OPTIONS_EXHAUSTION.md` is ANSWERED + the Path-C gate is satisfied.*
