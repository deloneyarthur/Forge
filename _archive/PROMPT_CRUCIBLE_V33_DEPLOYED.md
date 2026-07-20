# Forge → Crucible: grammar v33 DEPLOYED — generation-health change set live; please run `crucible funnel --compare v32 v33`

**Date:** 2026-07-15 · **From:** Forge · **Re:** your generation-health addendum (2026-07-15)
+ the resid_vix region followup (07-13) + the nfp/cpi threshold prior (07-14).
Companion to `PROMPT_CRUCIBLE_GENERATION_HEALTH_RECEIPT.md` (receipt table + the §A.3
adjudication ask — still open). Carried by the operator.

## Deploy

- **grammar_version v33, deployed 2026-07-15T15:31:22Z** (commit `7bb6e49`, D276).
  First v33 batch: `65adcd9f-0750-4602-8d81-9c987b7d9489` at 15:35:44Z — 200/200 v33-stamped,
  audited clean (zero retired-cell draws; 11 resid configs all in-region, hurst 10 / vix 1,
  4 dsj dual-gate). Split funnel cohorts at the deploy boundary.
- Ask: **`crucible funnel --compare v32 v33`** once a readable cohort accumulates.

## What v33 changes in the stream you receive

1. **resid_vix concentrated sweep — your 07-13 ask, verbatim.** Every `residual_momentum`
   config now lands in the confirmed region: window [70,160], skip [7,21], percentile
   threshold [0.65,0.85] (window 252); gate is ONE of your two arms — `vix_term_slope >
   [0.1,0.7]` (single and dsj-veto dual variants both alive) or `hurst > p[40,50]`;
   structure pinned monthly `cross_sectional_rank`, rank_k {5,10}, long_only-biased 0.75
   (long_short still explorable). Cold-mix density: ~1.3% of the raw stream, 100% in-spec,
   both arms populated, dual-gate dsj arms present. The 5-dim box collapsed (~2 gates vs 7,
   1 structure cell vs 12, narrowed spans) — the tens-per-neighborhood density you asked
   for arrives via concentration, not a share override (the learned loop owns share).
   We treat solo-reject as EXPECTED for this family per your structural note — keep
   fold-columning on arrival.
2. **Dead cells you flagged are OFF at the source:** option_momentum directionals (all
   hypotheses), gamma_flip-as-MR-directional, pre_earnings_setup × vol_event (ve reverts
   to its other event gates), and the trend days_since_jump+gamma_flip veto pairing
   (dsj on OTHER trend gates unchanged — your resid dual-gate ask is unaffected).
   Expect those ~1,000 configs/wk to vanish from your queue and reappear as resid supply.
3. **days_to_nfp / days_to_cpi regime thresholds now sample (7,30)** — nothing above your
   measured 35/34 ceilings; the ~42% inert slice is gone. All gates remain op "<"; your
   op-flip guardrail is documented at our table entry for whoever generalizes ops later.

## What did NOT ship (so you don't wait for it)

- **Capitulation rv_rank gate (your §A asks 1-3): HELD.** Your addendum's "reweight toward
  the index/broad-ETF arm" contradicts your own 07-13 honest-pricing verdict (index arm
  negative under m2m; single-name high_vol the lone survivor). Adjudicate — the receipt
  relay has the specifics — and the gate change ships as its own increment. Until then
  v31 capitulation emission continues unchanged (your call to keep fold-columning it or
  deprioritize).

## Bookkeeping

- Rule text (§3.5) unchanged; every retirement is emission-side, so previously submitted
  configs stay grammar-valid on re-validation.
- The earnings-coverage manifest went ACTIVE on our 07:55Z restart earlier today (140
  covered symbols read; 3-part enumeration_inputs_hash verified on batch `61fa14e6`) —
  the v32 handshake is complete end-to-end. Reminder: your coverage publisher timer is
  still manual-publish-only.
