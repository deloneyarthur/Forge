# Long-options exhaustion assessment (consolidated) — can a long-premium book reach promotion-grade Sharpe/CPCV?

Status: **CONSOLIDATED FINDING, 2026-06-14 → CRUCIBLE-CONFIRMED 2026-06-15 → QUALIFIED 2026-06-15
(`../Crucible/docs/handoffs/FORGE_long_options_exhaustion_consolidated.md`).** Combines our Crucible data +
the long-options inventory + two adversarially-verified deep-research scans, now confirmed by Crucible's
empirical 4-check battery + an independent 22-source literature sweep. Companion to `regime-orthogonal-arms.md`,
`edge-magnitude-levers.md`, `path-a-rich-conditioning.md`, [[promotion-gate-tiers-and-constraint]],
[[exhaust-long-options-before-v2-spreads]].

> **⚠ NOTE 2026-06-15 — a brief D153 "reopening" was largely RETRACTED the same day ([[D154]]); the verdict
> below STANDS, reinforced.** Timeline: (1) the operator asked to brainstorm before declaring long-options a
> failure; (2) an audit (reading a *stale* doc) claimed the vega/IV-cost axis was dark — `iv_rank` a NaN stub,
> §3.5 R1 "unsatisfiable" — and [[D153]] reopened the search/magnitude claim on that basis; (3) **Crucible
> refuted it** (`../Crucible/docs/handoffs/FORGE_iv_rank_already_live_coverage.md`): `iv_rank` has been **live
> since D031 (2026-05-15)**, non-NaN ~100%, used in 3,998 runs / 77 components — the "stub" was a stale-doc
> artifact, since corrected. **The structural/sign claim was never in question.** And the search/magnitude
> claim is **reinforced, not reopened:** the vega axis *was* live and used (vol_event), and its **strongest
> near-miss — `iv_rank × days_to_opex`, WF 1.43 / CPCV-p25 0.70 — craters on CPCV.** The only genuinely
> un-swept dimensions are **joint conditioning** and a **learned conditioner** (both real, both **low-EV** given
> the above) — tracked in `path-a-rich-conditioning.md` as residual threads pending an operator decision, **not**
> as an active reopening. **Path-C's provability gate ([[D152]]) stands SATISFIED** (the D153 "pending"
> qualifier is withdrawn). Rule-#5 aside (still true): ML *is* allowed in-loop; only LLMs are banned.

## Verdict (up top) — CONFIRMED by Crucible (empirical 4/4 + independent literature sweep; QUAD-convergent). One standing reopener: the population-growth monitor (gross 1.40 is a thin margin).

**Verdict: long-options is EXHAUSTED for promotion-grade (CPCV-p25 ≈ 1.5) magnitude in the adverse regimes
(bear / ranging).** No lever — signal, book construction, sizing, strike/DTE/exit, signal-combination,
underlying-selection, or overfit-robust construction — closes the gap from a structurally net-negative
long-premium base to a robust ~1.5 net-of-cost. The honest path to adverse-regime magnitude is a **scope
expansion that harvests the VRP instead of paying it**, entered at its *minimal, least-risky* point — a
**long-debit vertical** (still net-debit, still defined-risk, covered short leg — NOT naked premium-selling).

**Crucible empirically AGREED (2026-06-15, `FORGE_long_options_exhaustion_consolidated.md`) — all four
confirm/refute checks confirm, and their own independent 22-source literature sweep converges with ours
(now QUAD-convergent: our 2 deep-dives + Crucible's empirical battery + Crucible's literature sweep):**
- **M1 (decisive, gross-vs-net):** honest-era max **gross CPCV-p25 = 1.40 < 1.5**, cost ratio 1.00–1.10 →
  **IC-bound, not cost-bound** (Path B does NOT unlock it — the raw edge isn't there). The only ≥1.5
  "components" are `$0-slippage` WF-failing pre-cost-floor artifacts (filter `avg_slippage > 0`).
- **M2 (vol-target the convex book):** lifts p25 only **+0.07** (→ ~1.27), tail-shape; the real effect is
  drawdown (DD-p75 +0.27–0.33). The one residual lever is a **risk/shape lever, not a 1.5 path** — closed.
- **M3 (effective spread):** Crucible can't measure true spread (`bid==ask==mark`, no NBBO), but their §7.2
  model sits at Cao-Han's **pessimistic** end → net is if anything *over*-costed; **gross (1.40) is the clean
  read and is unchanged**. Best-execution can't lift net above gross, so it can't reopen M1 either.
- **M4 (deflation):** §8.7 DSR deflates by **selection-campaign size + PBO**, not raw enumeration → **our
  enumeration method is sound** (vindicated); the edge is simply absent, not hidden by overfitting.

**The one standing reopener (operator's "more decided items", now a defined monitor):** honest max gross is
**1.40 — Crucible flags this as "not a comfortable margin."** Their instruction: **re-run M1/M2 as the
decided-CPCV population grows** — if a bear/ranging cell's gross creeps to ≥1.5 with more data, the verdict
flips back into long-options. This is the *sole* thing that reopens it. Until then, the verdict stands.

## The evidence chain (triple-convergent, one-directional)

1. **Our Crucible data:** the assembled honest pool's CPCV-p25 maxes ~1.15, median 0.53, **0/264 clear
   the 1.5 bar**; the worst quartile is **bear 2.39× / ranging 1.33×**; per-family per-regime best is
   **1.10 on any slice** (`cpcv_crater_by_regime.json`). Trend goes negative in stress (−0.13); ve is
   positive in stress (0.65) but caps at 1.10.
2. **Deep-research #1 (signals):** NO documented net-of-cost, bear/ranging-conditional, single-leg
   long-premium **signal** near 1.5. The VRP is dominated by left-jump-tail "fear" comp that accrues to
   the **seller**; **ranging has no long-premium support — it's a short-premium problem.**
3. **Deep-research #2 (everything else):** the structural *why*, verified —
   - **Long premium is net-negative at the source** (Bakshi-Kapadia: delta-hedged long "significantly
     underperforms zero", loss > spread so not a cost artifact; Bondarenko: long index puts −39%/mo ATM
     to −95%/mo deep-OTM). The bear instrument (long puts) is the *most* net-negative.
   - **The cross-sectional long-option "edges" are short-leg edges:** Cao-Han (IVOL) and Frazzini-Pedersen
     (embedded leverage) are delta-hedged long-**short** constructions whose profit is "swamped" by the
     **short** leg; the convex **OTM/low-delta strike is the WORST** region (−125 bps/mo drag).
   - **Costs are first-order:** 44–88% erosion at 25–50% effective spread → "no-trade region."
   - **Construction (vol-targeting) is too small:** ~+0.1 Sharpe, and only for linear leverage-effect
     assets; its real gift is **tail/drawdown reduction** (helps worst-quartile *shape*, not the ~1.5 mean).
   - **CPCV is doubly fatal to weak long-option signals** (the operator's emphasis): the IS→OOS haircut is
     ~2× and **largest for low-true-Sharpe signals**, so a backtested 1.5 long-option book is presumed
     **~0.75 OOS** — below the wall. And a broad enumeration of weak signals manufactures spurious IS
     Sharpes (E[max SR] ≈ √(2 ln N); N=10 → 1.57 at zero skill) that CPCV/DSR correctly kill.

## Three honest nuances (what's NOT 100% closed — and a softer Path C)

1. **The one under-explored lever: vol-targeting / inverse-vol sizing on a CONVEX book.** The vol-targeting
   evidence is on *linear* assets; for convex long premium the transfer is uncertain (it truncates BOTH
   tails symmetrically, but the right tail IS the long-option edge, and IV is already high when you'd buy).
   It plausibly improves the worst-quartile *shape* but is **unproven for options** — and it's **cheaply
   testable in Forge's own backtest** on the existing long-option arms. This is the only residual lever.
   **→ MEASURED & CLOSED (Crucible M2, 2026-06-15): +0.07 to p25 (→ ~1.27), tail-shape only; the real effect
   is drawdown (DD-p75 +0.27–0.33). Confirmed a risk/shape lever, NOT a 1.5 path.**
2. **Forge's enumeration is NOT condemned — it needs deflation, which we already have.** The overfitting
   indictment bites on *raw* trial count; Forge's grammar variants are highly **correlated** → much smaller
   *effective N*. The fix is DSR / effective-N (ONC) deflation — which **Crucible's `deflated_sharpe` gate
   already applies (§8.7).** So the *method* is sound; what's absent is the long-premium *edge*, not the
   search. (CPCV itself is validated as the best OOS test — Arian 2024 — so the binding wall is well-chosen.)
3. **The minimal Path-C step is far less scary than "premium selling."** A **long-debit vertical** (bull
   call / bear put spread) is **net-debit** (you pay to enter), **defined-risk** (max loss = the debit),
   and the short far-leg is **covered** (no naked short) — yet it **harvests some VRP** (sells the
   overpriced far-OTM leg), cutting the long-option bleed. That is the *least*-scope, *lowest*-risk way to
   stop paying the VRP — categorically safer than the short-strangle/iron-condor premium-selling the
   operator flagged as last resort (which carries the correlated short-vol-crash tail). So "Path C" is a
   *spectrum*: debit verticals (minimal) → … → naked premium-selling (true last resort).

## Three cheap in-Forge checks — ANSWERED by Crucible (2026-06-15); verdict closed on current data

These were the residual measurements before declaring "closed." Crucible has now run all three (Forge
computes no metrics, §1.2):
1. **Vol-targeting on the convex book →** +0.07 to p25 (M2): a risk/drawdown lever, not a 1.5 path. Closed.
2. **Effective option spread →** unmeasurable on their data (`bid==ask==mark`, no NBBO), but their §7.2 model
   sits at Cao-Han's *pessimistic* end → net is *over*-costed; gross (1.40) is the clean read (M3).
3. **`deflated_sharpe` effective-N →** confirmed: deflates by selection-campaign size + PBO, not raw
   enumeration (M4) → our enumeration method is vindicated.

**Inventory is also complete (Crucible §3):** their 52 indicators span the documented conditioner taxonomy
— no missing long-premium conditioner surfaced. The six "untried" levers do NOT reopen the case:
`iv_term_slope` / `vix_term_slope` / `iv_minus_rv` are **low-EV as long-only gates** (their real edge is the
L/S straddle's *short* leg); skew/risk-reversal are seller signals; **VOV and IVOL are ADVERSE for long
premium** → Crucible **withdrew** its earlier "buy cheap-vol names" long-trigger framing and reframed them as
**exclusion filters** (avoid high-VOV/high-IVOL long buys), not triggers; constant-maturity construction
expresses a signal but creates no long-side edge.

## The only remaining IN-SCOPE long-options actions (both very-low-EV; operator-gated)

Crucible's "cheap residual" — the literal last exhaustion steps, **expectations now very low**:
1. **Enumerate the 3 published conditioners (`iv_term_slope`/`vix_term_slope`/`iv_minus_rv`) as gates** — a
   near-free *confirmation* that our single-name net-debit book agrees with the index-level literature (NOT
   an edge hunt). Costs a grammar bump + a cohort + funnel-compare; do only if we want airtight closure.
2. **VOV/IVOL as EXCLUSION filters** on the existing long book (screen out the worst long buys) — hygiene,
   not a new arm; needs Crucible to publish the indicators first. Lower priority.
Neither is a promotion path. Do **not** build skew/VOV/IVOL as long *triggers* (wrong-signed).

## Bottom line for the roadmap
The producer's promotion unlock is **not** more long-premium search — that frontier is closed, and CPCV
guarantees weak long-option edges fail OOS. The unlock is a **defined-risk scope expansion that harvests
the VRP**, entered at its safest point (**debit verticals**), gated by the safety probe+test program in
`regime-orthogonal-arms.md`. Long-options stays the *base* (trend/ve/mr hygiene, now well-tuned via
D145–D151); the *growth* comes from the new defined-risk side. Hard rule 3 holds throughout (same §8.7 bar).

**The Path-C provability gate the operator set is now SATISFIED** (long-options provably can't clear the bar
— confirmed on both the empirical and theoretical axes, inventory complete). The Path-C *decision* is
unblocked — but it stays the operator's call, **debit-verticals-first**, gated by the safety probe+test
program. Crucible's sell-side VRP probe (`vrp_short_premium_by_regime.json`: short-vol positive *every*
regime, strongest in low-vol/calm) corroborates the direction and their sizing is in flight. **Standing
monitor:** re-run M1/M2 as the decided-CPCV population grows (gross 1.40 is thin) — the sole reopener.
