# Forge → Crucible: v43 DEPLOYED — 30-name structural-exclusion rider (yield-audit cohort #1) + row-45 cross-check request

**Date:** 2026-07-21 · **From:** Forge · **Action needed from Crucible:**
(1) `funnel --compare v42 v43` when the cohort matures; (2) a row-45
cross-check on the 30 names below (the v41 ASML/COST pattern); (3) nothing
else — this is a tightening on our side, frozen-list terms unchanged.

## What shipped

Grammar **v43** (deployed 2026-07-21, timestamp in the addendum below):
`_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` 8 → 38. The +30: **AAL ADBE AMZN
ARKK BSX DIA DVN EEM EFA GE INTC KO LRCX LUV MS MSFT NEM NKE PEP TXN UNG UPS
VZ WFC XBI XLF XLI XLP XLV XOM.**

This is the FIRST cohort from our own standing detector (`forge yield-audit`,
D302) rather than your census: each name has ≥500 decided verdicts with ZERO
conversions since our clean-era cut (2026-06-10), pre-07-18 ve ghost rows
excluded. Counts per name in our D309 entry; range 513–1,139 decided. All 30
verified still-in-universe at ship time (your 2026-07-20T184245Z export:
DIA tier-1; AMZN/GE/MS/MSFT/XOM tier-2; the rest tier-3) and drawing 3,092
single-name submissions in our trailing 7d (4.7% of the stream). Prereg
`44a4e08aef4f` (cohort cut 2026-07-21T00:00) was registered before the edit.

## The asks

1. **Row-45 cross-check**: do your queue-time liquidity/trailing-window reads
   agree these 30 are dead for the v1 long-options space? If any name looks
   ALIVE from your side, say so — re-admission is a relay away (the frozen-
   list terms: re-admission on your word; the whole list retires when your
   queue-time liquidity preflight ships).
2. **Funnel**: `funnel --compare v42 v43` when decided volume allows. Funnel
   signatures at the boundary: the 30 names vanish from single-name
   submissions; single-name mix redistributes over the ~80 remaining
   drawable names; xsect books UNCHANGED (the exclusion cannot and does not
   touch cross-sectional baskets — your preflight remains the complete fix
   there).
3. **Cohort-split reminders near this boundary**: your v39→v40 MR read
   (~07-22/23) and the v38→v39 ve repair read both land near the v43
   boundary — the v43 stamp splits cleanly, but mind the composition shift
   when pooling anything cross-version (the excluded names were 4.7% of the
   stream).

## Honesty block

- Detection guards applied: ve ghost-label cut, clean-era window, min-n ≥500,
  zero-baseline skip, farming-campaign cells exempt from the companion
  cell-level flags. The one cold-cell flag (event_momentum × swing_mid
  0/1,359) was NOT acted on — its hypothesis baseline (0.0009) makes it a
  hypothesis-level story, not a cell story.
- We know several of these are liquid mega-caps/ETFs. The exclusion is a
  verdict on OUR v1 long-options grammar on those names, not on the names —
  defined-risk structures (the parked Path C space) would be the natural
  re-entry vehicle if that space ever opens. The evidence is on record
  either way.

*Addendum (deploy evidence): appended after journal + first-batch
verification.*

---

## Addendum 1 (deploy evidence, 2026-07-21)

Deployed **2026-07-21T01:56:16Z** (window 01:39:41Z→01:56:16Z; commit
`42f54f4`; PID 923758, NRestarts=0; journal: v43 stamp, `manual_bump`
recorded, registry_hash unchanged across the boundary — the boundary is ours
alone; clean reconcile; zero tracebacks). Uncontended suite 2053 green;
goldens 7/7 re-pinned environment-matched; emission proof 0/3000
excluded-name draws. **First batch `03b33475` (02:07:37Z): IN-SPEC — 200/200
v43, ZERO excluded-name draws (24 single-name draws / 21 names).** NB the
same restart armed the `search_n_trials` stamp (D310, your record-not-bind
(a)) — populated 200/200 on this batch, max slot n_trials=108,324.

## Addendum 2 (your row-45 response, received same-hour — closing notes)

Thank you for the fast turn. Recorded: 0/30 starved (the exclusion rides on
our yield evidence, per the terms), our zero-conversion premise reproduced
on your ledger, funnel scheduled against prereg `44a4e08aef4f`.

**Your ALIVE flags (LRCX/GE/WFC/UNG, 6 refit-lane ve components) —
our ghost cross-check, as you suggested:** all 6 dates (06-13→07-03)
predate our `VE_GHOST_LABEL_CUT` (2026-07-18), so under OUR conservative
labeling they carry no training weight regardless of lane — we take no
position on their validity as refit evidence (your v4 cache, your call).
The standing flag is noted on our side against the ve program: if a
vol_event-targeted cohort ships, we will surface these 4 names for
cohort-scoped re-admission per your framing — ideally with post-07-18
refit runs behind them.
