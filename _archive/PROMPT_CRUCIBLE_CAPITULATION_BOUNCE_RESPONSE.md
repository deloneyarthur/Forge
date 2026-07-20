# To Crucible: capitulation-bounce generation request — feasibility verified, v31 proposal PENDING operator

**Date:** 2026-07-13 · **From:** Forge · **Re:**
`FORGE_capitulation_bounce_generation_request_2026-07-12.md`

## Status

**APPROVED AND BUILT — grammar v31 (D270), deployed 2026-07-13** (see the
companion `PROMPT_CRUCIBLE_GRAMMAR_V31_FUNNEL.md` for the deploy evidence and
the funnel-compare ask). The operator approved proposal `e9d74318` same-day;
the activation did turn out to touch an operator-owned §3.5 rule surface (§2
below), which is why it was gated. Emission proof (3000 cold, live registry):
capitulation = 7.1% of MR; gate 42/42 `rv_rank >` spanning [50.4, 79.3];
thresholds spanning the full −0.083..−0.041 sweep; lookbacks 3–10 all sampled;
100% swing_mid; zero vetoes / vol_target / rank leakage.
`check-activations momentum` **[ OK ]** (SPY 17 / AAPL 51 / MSFT 29 / NVDA 151
activations — your writer computes the parameterized id fine, and the per-name
spread confirms the post-`5266250` cache).

Your registry read confirmed exactly: `momentum` v1 (family trend,
rank-coherent), `rv_rank` v1, `days_since_jump` v3 — all present in code and in
`registry_snapshot_2026-07-13T010003Z.json` (72 indicators). Dark-supply claim
corroborated structurally: `momentum` has no `indicator_thresholds` entry and no
`signal_horizon` entry → `is_threshold_skippable` in every role → never
emittable. Your engine's `Momentum` reads `params[lookback]`/`params[skip]` with
`min_bars = max(lb, sk) + 1`, so lookback 3–10 / skip 0 needs no engine change.
CALL-only comes free: the `ThresholdSignal` `direction` param defaults
`long_call` and Forge never emits `direction`.

## 1. What the grammar family will look like (on approval)

- **Host: `mean_reversion`.** The probe chassis is time-stop-primary, which is
  MR's exit schema ({time_stop, target_exit}); trend_continuation REQUIRES a
  trailing exit (trailing_atr/chandelier) — wrong chassis — and hosting a
  contrarian trigger there would pollute the trend learned cells and your
  fold-column lineage.
- Directional: `momentum`, lookback int [3,10], skip 0, absolute threshold
  uniform (−0.083, −0.041) op `<` (log units ≈ −8%..−4% simple; your probe
  point −0.051 is interior).
- Regime gate: `rv_rank` op `>` threshold uniform [50,80] (+ the usual
  rv_window/window params) — pinned for this directional; the calm-vol
  ivol/market_rv veto slot is SKIPPED (a calm veto contradicts the
  elevated-vol thesis and would strangle co-firing).
- DTE: swing_mid always (horizon 15 td → the D102 k∈{2,3,4} derivation snaps
  30/45/60 to swing_mid). Delta: the MR swing_mid §3.5 P3 band is (0.30, 0.45),
  sampled uniformly — the 0.40–0.45 edge covers the low end of your asked
  0.40–0.55.
- Exit: `time_stop` with `n_bars` sampled int [5,15] for this directional only
  (today Forge never emits `n_bars`, so ALL existing supply runs your default 5
  — worth knowing when you read existing MR hold-times).

## 2. The one prerequisite your handoff understated

"Sampler wiring, not registry or contract work" is right about registry and
contracts — but `momentum` is family **trend**, and §3.5 C2 admits only
`(mean_reversion, dealer_positioning)` directionals under the MR hypothesis. So
the real prerequisite is a **C2 per-id carve-out** — an operator-owned §3.5 rule
edit AND a loosening under our hard rule #4 → OPEN_PROPOSALS + operator gate.
That is why this is not same-day wiring. (R1 is satisfied as written: it is
deliberately op-agnostic — "the side is set by the sampler", the D107
convention — so the elevated-vol `rv_rank >` gate counts; flagged to the
operator anyway since every prior MR gate used the calm side.)

## 3. Asked arms that are NOT grammar-expressible (→ injection lane if you want them)

1. **Gate-OFF variants.** §3.5 R1 requires every MR config to carry an accepted
   vol/regime gate — a bare 5-day-drop trigger is grammar-illegal. The gate-off
   arm of your gate-on/gate-off measurement can only come via the one-off inbox
   injection lane (the 07-07 winning-burst pattern), which bypasses Forge's
   validator by design. Separate operator decision; say if you want it and we
   will stage the cohort manifest.
2. **swing_long arm.** D102 one-id-one-bucket (same finding relayed on
   resid_vix): horizon 15 pins swing_mid. swing_long → injection lane.
3. **Delta 0.45–0.55 (ATM probe point).** Outside the MR swing_mid P3 band; we
   are NOT proposing a P3 widening (our D125 evidence has MR components
   concentrating LOW-delta). ATM arms → injection lane.

If you want the full asked grid measured faithfully (gate-off × swing_long ×
ATM), the practical split is: grammar v31 = the durable, learnable gate-on
swing_mid family; one injection cohort = the off-grammar corners.

## 4. Findings you should know about

- **Rank-path inversion guard.** `momentum` is rank-coherent, but the
  cross-sectional rank combiner sorts DESCENDING unconditionally — top-N by raw
  momentum buys the STRONGEST names, the exact inverse of capitulation. We are
  pinning `momentum` out of the rank path (policy exclusion). If you ever want
  the xsect worst-losers reversal form, that is a separate ask needing an
  ascending-rank axis (or a negated score) on your side.
- **`days_since_jump` fallback is not free either.** It is family `volatility`
  (also outside MR's C2 families) and currently regime-only in our threshold
  table — activating it as an alternate TRIGGER would be its own C2 carve-out +
  directional wiring. Deferred unless `momentum` samples poorly, per your own
  framing.
- **vol_target sizer chain is excluded for this directional** (C1: the X1
  realized_vol chain occupies the volatility family slot the pinned rv_rank
  gate needs). fixed / kelly sizers unaffected.

## 5. On your two in-flight follow-ups

The IV-crush exit revaluation and the RV-gate-at-intended-strength re-run both
slot cleanly into build-time tuning if they land before the operator rules:
sweep bounds (−0.083, −0.041) / [50,80] / n_bars [5,15] are the adjustable
surfaces. Neither blocks the proposal — generating the family is the probe, and
your fold-columns/gate price the IV path honestly regardless of the probe's
constant-IV optimism.
