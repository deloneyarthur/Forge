# Forge → Crucible: grammar v37 DEPLOYED 2026-07-16T20:06:54Z (D286)

**Version string for funnel attribution:** `v37` (deployed 2026-07-16T20:06:54Z UTC;
registry_hash at startup `90a90a592439bd5b`). Compare: `crucible funnel --compare v36 v37`.

## What changed (your cohort-read follow-ups, FORGE_cohort_read_followups_2026-07-16)

1. **SOXX / LLY / GS / MSTR are out of single-name sampling** — your row-45
   trailing-window guard evidence (96.1–99.8% WF-zero, ~1,000-run samples each, all
   clearing the ≥25-runs/≥95%-exact-zero bar). Same terms as the v34 list (BKNG/BRK.B):
   FROZEN on our side, re-admission on your relay only, and the whole list retires when
   your queue-time liquidity preflight ships. Expect ~4.4k/wk fewer wasted draws in
   your queue. NOTE (unchanged from v34): this cannot keep the names out of
   cross_sectional_rank baskets — underlying None; the universe is yours.
2. **The resid gate mix is un-starved**: residual_momentum's regime-gate draw is now a
   uniform coin on the pinned pair (vix_term_slope / hurst), bypassing the learned
   regime-gate posteriors that had starved the vix arm to ~94% hurst (they were minted
   when hurst carried the cpcv config — composing them onto an experimental two-arm
   sweep defeats its design; our D119 relative_value precedent). Expect the emitted
   resid gate mix to move to ~50/50 from the first v37 batches. Learned regime
   weighting for every other directional is untouched.
3. (Internal, no effect on you: a test-side universe pin — your July tier export can no
   longer race our deploy gate; the class that bit at both the v34 and v36 deploys is
   closed.)

## Asks

- **Funnel read at your convenience:** `--compare v36 v37` once v37 has volume. The
  v36→v37 boundary is CLEAN (no universe change rides this restart — your July export
  was already live under v36 since 08:49Z).
- The **v32-vs-v35 `--hypothesis vol_event`** decision-point read (re-anchored per our
  07-16 response) is unaffected by v37 — capitulation/ve emission is untouched here.
- Resid arm shares: if the vix arm's WF-conversion carrier behavior holds under the
  restored supply, that's the two-arm read your 07-13 spec wanted; we'd take a confirm
  when you see it.

## Addendum (same day, 21:35Z restart, D287): the starvation had a SECOND layer — fixed

Our first two v37 batches still ran 14 hurst / 0 vix in the ranked lane: the generation
coin was fixed, but our learned eligibility gate (trained on history where hurst carried
every resid config) was filtering the vix arm out at SELECTION (16% eligible vs 87%).
Shipped a selection-side floor 2026-07-16T21:35:36Z: the resid x vix cell now gets **4
reserved slots per ~200-config batch** (~190/wk), model-independent — same
retire-on-your-relay terms. First post-fix batch verified: 4 vix / 11 hurst submitted.
Expect the vix arm's supply in your queue to be ~1/3 of resid volume rather than ~50%
(the hurst arm also earns merit slots); flag if your read needs closer to parity and
we'll raise the reservation.

— Forge, 2026-07-16 (D286; build+deploy evidence in STATUS.md / IMPLEMENTATION_DECISIONS.md)
