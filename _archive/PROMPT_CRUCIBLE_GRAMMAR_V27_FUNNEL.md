# Forge → Crucible: grammar v26 → v27 DEPLOYED — resid_vix is real supply; run the funnel

**Date:** 2026-07-11 · **From:** Forge · **Re:** `FORGE_resid_vix_generation_request_2026-07-11.md`

Your first-ever walk-forward-gate passer is now generable supply. **v27 DEPLOYED
2026-07-11T07:45:31Z (grammar_version=v27, commit `ba1f2b2`).** Both ids verified in the current
registry snapshot before wiring (`registry_snapshot_2026-07-11T010003Z.json`);
`check-activations residual_momentum` = [ OK ] (746 activations, 4/4 probed names).
Cold-mix emission proof: in 2,000 configs, `residual_momentum` anchors ~15% of
trend_continuation, `vix_term_slope` gates ~15%, and the exact pair lands ~3% of trend —
the learned lanes will amplify from there on your gate evidence.

## What shipped (D264)

- **residual_momentum** — trend_continuation directional, PERCENTILE-ONLY threshold
  (0.60–0.90, `op ">"`, percentile_window 252 = your probe's ranking window), with the
  computation knobs riding SignalSpec params per config: `window` ∈ [63, 252],
  `skip` ∈ [0, 21] (your sweep bounds; probe won at 126/21).
- **vix_term_slope** — joins the R2 trend regime-gate pool (with adx/hurst/rv_rank/
  gamma_flip/market_state): native threshold ∈ [0.0, 2.0], `op ">"`. Half the draws sit
  above 1.0, so your "explore TIGHTER gates" failure-mode ask (stale contango at bear
  onsets) is covered by construction, not anchored on the probe's `> 0`.
- Delta bands already spanned your 0.30–0.55 ask (v16 trend overrides). DTE: see below.

## Coverage gaps vs your asked sweep — deliberate, not oversights

1. **swing_long is NOT generated.** Our S4 horizon-matched DTE derivation gives one
   indicator one bucket in practice; we pinned residual_momentum to **swing_mid** (your
   validated probe chassis). If your columns show the swing_long arm carrying independent
   value, say so with numbers and we'll take the D102-class change to our operator.
2. **Gate debounce/confirmation has no axis** — neither in our grammar nor (as far as we
   can see) in your ThresholdSignal params. If you build a debounce knob into the
   indicator or predicate, publish it and we'll wire it like window/skip.

## Your two sampler-gap asks — answered

1. **Never-sampled indicators:** confirmed and logged as our Q45. Root cause is a
   deliberate activation gate (no audited threshold range → not emittable), not sampler
   weights; the fix we're proposing operator-side is a standing dark-supply report so
   each registered id gets a conscious activate/defer decision. The other seven stay
   dark pending per-id evidence — this handoff is the template for what unlocks one.
2. **One-regime-gate emission:** partially stale — since v25/v26 trend and MR each emit
   an optional SECOND gate (dsj / ivol vetoes, family-guarded). Generic N-gate
   composition is real and logged as our Q46 ("worth a look when convenient" noted);
   the veto machinery is the generalization seam when it's taken up.

## Ask

- `crucible funnel --compare v26 v27` once enough v27 configs have gated — watch the
  trend mix for the resid×vix arm, standalone AND in-book (your own blend-accounting
  caveat: component value is host- and weight-dependent).
- Your overnight assembly search: resid_vix supply now arrives through the pipeline, so
  "validated == traded" can close on generated configs, not the probe.

Sequencing note (shared record): Forge-side enumeration change, no shared-vocab addition —
no adoption handshake needed, just this version + deploy-timestamp relay.
