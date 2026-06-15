# Long-options exhaustion assessment (consolidated) — can a long-premium book reach promotion-grade Sharpe/CPCV?

Status: **CONSOLIDATED FINDING, 2026-06-14.** Combines our Crucible data + the long-options inventory +
two adversarially-verified deep-research scans. Companion to `regime-orthogonal-arms.md`,
`edge-magnitude-levers.md`, [[promotion-gate-tiers-and-constraint]], [[exhaust-long-options-before-v2-spreads]].

## Verdict (up top)

**Long-options is EXHAUSTED for promotion-grade (CPCV-p25 ≈ 1.5) magnitude in the adverse regimes
(bear / ranging).** No lever — signal, book construction, sizing, strike/DTE/exit, signal-combination,
underlying-selection, or overfit-robust construction — closes the gap from a structurally net-negative
long-premium base to a robust ~1.5 net-of-cost. The honest path to adverse-regime magnitude is a
**scope expansion that harvests the VRP instead of paying it** — and the *minimal, least-risky* entry is
**long-debit verticals** (still net-debit, still defined-risk, covered short leg — NOT naked premium-
selling). Three cheap in-Forge checks remain before declaring it 100% closed (below).

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

## Three cheap in-Forge checks to fully close "exhausted" (before any scope change)

These are measurable from our own data/backtest — no scope change, no literature:
1. **Vol-targeting on the convex book** — does inverse-vol / vol-target sizing of the existing long-option
   arms lift the *book* CPCV-p25 (nuance #1)? Forge/Crucible backtest.
2. **Effective option spread** — is our single-name/ETF universe nearer Cao-Han's 50% (no-trade) or
   Muravyev-Pearson's ~20–25% (edge survives)? Measurable from our fill/quote data; gates the cost wall.
3. **Confirm `deflated_sharpe` uses effective-N deflation** — verify Crucible's gate deflates by trial
   count, not raw Sharpe (nuance #2). If yes, our enumeration method is vindicated.

If all three confirm the verdict (very likely), long-options is **definitively exhausted** and the next
move is the Path-C decision — starting with the minimal **debit-vertical** step, sized by the Crucible
magnitude/cost relay's part 3 (the net-of-cost per-regime magnitude of defined-risk structures).

## Bottom line for the roadmap
The producer's promotion unlock is **not** more long-premium search — that frontier is closed, and CPCV
guarantees weak long-option edges fail OOS. The unlock is a **defined-risk scope expansion that harvests
the VRP**, entered at its safest point (**debit verticals**), gated by the safety probe+test program in
`regime-orthogonal-arms.md`. Long-options stays the *base* (trend/ve/mr hygiene, now well-tuned via
D145–D151); the *growth* comes from the new defined-risk side. Hard rule 3 holds throughout (same §8.7 bar).
