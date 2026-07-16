# Proposal: v37 — cohort-read follow-ups: 4 outcome-starved names out of single-name sampling + resid gate-mix 50/50 pin (+ test-side universe pin, Q50 durable fix)

Status: **SCOPING — operator-gated grammar bump; nothing ships off this doc.**
Date: 2026-07-16. Source: `FORGE_cohort_read_followups_2026-07-16.md` (their first v33/v35
cohort reads + row-45 guard telemetry). Response relay:
`PROMPT_CRUCIBLE_COHORT_FOLLOWUPS_RESPONSE.md` (held for carry; includes the §4
arm-share answer — data, no build needed).
Relates to: [[D278]] (the v34 frozen-list mechanism + terms), [[D276]] (the v33 resid
two-arm spec this repairs), [[D282]]/Q50 (the universe-export coupling the test pin
ends), [[D119]] (the "learned weights must not bias an experimental draw" precedent).

## Build items (the v37 bump, if approved)

1. **Add SOXX, LLY, GS, MSTR to `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS`** (their row-45
   trailing-window guard: 96.1-99.8% WF-zero on ~1,000-run samples each; all clear their
   ≥25-runs/≥95%-exact-zero bar; the guard eats them at queue time but our draws are
   wasted budget). Same terms as v34: re-admission on their relay; their queue-time
   guard stays the durable authority. All four verified present in our current (July)
   universe. ~4.4k wasted draws/wk saved at current cadence.
2. **Pin the resid_vix regime-gate draw to 50/50** vix_term_slope/hurst, this directional
   only. Their read: emission is ~94% hurst-gated; the 07-13 two-arm spec wanted BOTH
   arms populated (vix_term_slope is the WF-conversion carrier). Cause (verified in the
   draw path): the v33 pool pin is correct, but the learned regime-gate yield weights —
   minted when hurst carried the cpcv config — compose onto the pinned two-member pool
   and starve the vix arm. The two-arm sweep is an EXPERIMENT; yield-weighting inside it
   defeats the design (the D119 precedent: relative_value's regime draw ignores learned
   weights for the same reason). Mechanism: bypass the learned composition when the
   directional is resid and the pool is the pinned pair — uniform coin instead.
   Trend-wide learned weighting elsewhere untouched.
3. **Test-side universe pin (Q50 durable fix, D274 pattern).** Crucible's July tier
   export landed 17 minutes before the v36 deploy preflight and broke 9 goldens at
   position 0 (the second live-export bite in two days — the earnings half was pinned
   in D274, the universe half was left open as Q50). Add a conftest autouse fixture
   pinning `_load_underlyings` to a frozen snapshot tuple; loader/fingerprint tests
   re-bind the real loader (exactly the D274 shape). The daemon's live read is
   untouched. Goldens re-pin ONE more time under the frozen tuple — the last
   environment-driven re-pin, ending the class.

## No-build item (answered in the response relay)

- **§4 arm-share/dte-mix question:** measured — capitulation = 23/1,741 = **1.3% of
  submitted MR since v35, matching their decided 1.3% exactly**; the 8.6% was cold-mix
  enumeration basis; the compression is learned-lane composition on a no-history family
  (nothing eaten pipeline-side; their fair-read timing stands). DTE mix 10:13 submitted
  = the structural 1:3 composed with MR-wide learned bucket weights (D105 fallback);
  expect drift toward structural as the family mints cells. NO manual boost — that
  would thumb the pane being read.

## Watch (their side, no build)

- §5 correction: the ve-floor decision point is now **v32 vs v35 `--hypothesis
  vol_event`** (~1 day out) — the v33 stamp lived only ~5.3h. Early signal: component
  conversion 7.6% → 11.1%.
- Their July export FYI is live (07-16T08:27:54Z); BKNG already left the universe, so
  the v34 frozen list is now partially redundant — fold its retirement into the same
  future bump that re-admits names, not before.

## Ritual

One v36→v37 bump; items 1-2 emission-side (`rules:` unchanged), item 3 test-only.
Goldens re-pin licensed (items 1+3 shift underlying draws; item 2 shifts resid gate
draws). Full deploy ritual per `docs/tasks/deploy.md`.
