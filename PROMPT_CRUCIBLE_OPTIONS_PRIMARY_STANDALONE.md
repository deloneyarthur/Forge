# Crucible relay — the options arm is the PRIMARY, STANDALONE vehicle (NOT the WORLD_A §6.1 overlay)

**Status: DRAFT for operator review — not sent.** Informational/coordination only: no gate change (hard rule 3), no grammar change in this relay (Path C = grammar v2 = operator+grammar-gated, rule 1), no build commitment.

## 0. The operator's position (explicit — this corrects a framing)

Crucible's `WORLD_A_EVIDENCE_PACKAGE.md` §6.1 (2026-06-08) recommends repurposing Forge's long-vol edge as a **diversifying overlay to the PTS equity alpha**, valuable "even at standalone ~1.0." **The operator declines that route.** The intended frame:

- **The options arm (Forge → Crucible) is the PRIMARY vehicle, judged as STANDALONE as possible.** It is *not* an overlay to the equity arm; its success is its own options P&L against the §8.7 gate, not marginal contribution to a PTS-anchored book.
- **PTS / QuantIQ equities are a REFERENCE for data and info** — and the *only* channel by which the equity arm may inform the options arm is **a variation of ENTRY** (an entry/regime/momentum *signal*), never a portfolio/sizing dependency.

This relay asks Crucible to confirm what that mandate implies for the path and the success criterion.

## 1. The tension to resolve

Crucible has **CONFIRMED** (D152/D154; the 4-check + 22-source sweep) that standalone **long-options** edge is exhausted: honest-era max **gross CPCV-p25 = 1.40 < 1.5**, **IC-bound** (cost ratio ~1.0), and every documented high-Sharpe option signal is a **short-leg / writing** edge. So a standalone-primary options vehicle that must clear §8.7 **cannot get there with long premium alone** — the standalone-options edge that is *not* exhausted lives in **defined-risk / short-premium** structures (Path C, grammar v2), currently parked.

## 2. Questions for Crucible

**Q1 — The standalone path.** Under a standalone-primary mandate (no overlay credit), and given your confirmed long-options exhaustion, do you agree the standalone-options frontier **requires Path C** (defined-risk / short-premium)? Or do you see any standalone **long**-options route to the §8.7 bar we have not exhausted? If Path C, name the **cheapest, safest rung** that could plausibly clear the standalone bar per adverse regime (risk-ordered: net-debit defined-risk → net-credit defined-risk → naked = last resort).

**Q2 — The standalone success criterion.** Confirm the criterion for the options arm is the full **§8.7 battery at portfolio scope, judged STANDALONE** — i.e. NOT the §6.1 overlay / marginal-contribution-to-PTS credit, and NOT a relaxed bar. Is **CPCV-p25 ≥ 1.5** the right standalone bar, or does "primary standalone vehicle" change how you'd define success (e.g. a portfolio of options components rather than single-config)?

**Q3 — The entry-signal channel (the one permitted equities → options link).** The operator is open to the equity arm informing the options arm **only** via a *variation of entry*. Are any equity-derived signals — e.g. the PTS regime gate, a cross-sectional / risk-adjusted momentum construction, or QuantIQ's HMM regime state — worth publishing as a Crucible **indicator** that the options arm can gate/trigger on for ENTRY (directional or regime), within the standalone frame? (Hard rule 7: no `equity` as a traded family; an equity-price-derived directional/regime indicator on the underlying is in-bounds — Forge already uses momentum_252 etc.)

**Q4 — Path-C sizing (conditional on Q1 = Path C).** If you confirm Path C is the standalone path, this activates the held `PROMPT_CRUCIBLE_PATHC_DEBIT_VERTICAL_SIZING.md`: per-regime **net-of-cost** CPCV magnitude **and** tail/safety **rung by rung**, and the **lowest rung that clears the standalone §8.7 bar** per adverse regime — **debit-verticals-first**, safety-program-gated.

## 3. What this is / isn't

- **Is:** a strategic-frame clarification + a request for Crucible's read on the standalone-options path and criterion. Forge consumes Crucible's verdict; computes nothing (§1.2).
- **Isn't:** a gate change (rule 3), a grammar change (rule 1 — Path C stays operator+grammar-gated), or a build commitment. Un-parking / building Path C is a separate operator decision this relay only informs.
- **Standing items unaffected:** the M1/M2 long-options monitor; the §8.6 tail-shadow streak.
