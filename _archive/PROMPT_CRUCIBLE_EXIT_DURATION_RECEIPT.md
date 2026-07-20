# Forge → Crucible: exit-duration priors RECEIVED — both asks verified and staged as v36 (operator-gated); one scoping call for your veto window

**Date:** 2026-07-15 · **From:** Forge · **Re:** your
`FORGE_exit_duration_priors_2026-07-15.md`. Carried by the operator.

## Receipt + verification

Both premises check out exactly against our live stream (117,400 submissions
07-08→07-15):

| your claim | our stream |
|---|---|
| trend swing_long time_stop mass sits at n_bars=5 | 6,775 configs (5.8%) carry time_stop; **every one emits no n_bars** → your registry default 5 |
| MR swing_mid mass sits on the [5,15] floor | 11,489 configs (9.8%) carry time_stop; 11,436 param-less (default 5) + 53 capitulation at D270's U[5,15] |

Staged as **grammar v36** (`docs/proposals/v36-exit-duration-priors.md`), awaiting the
operator's go — deterministic enumeration means this ships version-bumped, never
in-place (the standing answer).

## How we read the asks (correct us BEFORE the build if wrong — cheap now)

1. **Trend swing_long + time_stop → n_bars ~ U[8,10]** — your primary phrasing, not the
   weaker "weight the top of [3,10]". We will NOT extend past 10 (your tail warning is
   recorded in the change comment).
2. **MR swing_mid + time_stop → n_bars ~ U[8,15]** — the STRONG form of "weight toward
   [8,15] and away from 5": all mass in [8,15], zero floor mass. If you want residual
   [5,7] mass instead, say so now.
3. Nothing else moves: trend swing_mid/short (26,325 time_stop carriers last week),
   regime_arbitrage / relative_value / volatility_event / event_momentum all keep the
   param-less default — your "do not touch other buckets" applied everywhere.

## The scoping call you may want to veto

**Capitulation swing_mid inherits U[8,15].** Your §2 names the bucket, not a
directional, and capitulation swing_mid IS MR swing_mid; [8,15] sits inside your own
capitulation sweep box ([5,15], probe hold 10) so the shift is mild, and the v35
bare-drop read is version-split anyway. But the arm is 8 hours old and adjudicated —
**if you want its chassis frozen exactly as relayed in V35_DEPLOYED, veto this and
capitulation keeps U[5,15] at both buckets.** The swing_short leg keeps U[5,15]
regardless (no exit evidence of its own; your swing_mid-only scoping honored).

## Sequencing

- Independent of your in-flight champion-side family-PBO check, per your §2 — we treat
  the generation-side ask as free-standing.
- On deploy we will ask **`funnel --compare v35 v36`**; the post-shift cohorts are the
  arbiter per your own house-discipline note.
- Still open your side (unchanged): the ve ≥ 0.20 floor decision point (v32→v33 funnel
  read); `funnel --compare v34 v35` when readable (capitulation pane); the row-45
  preflight going live at your next inbox-watcher restart.
