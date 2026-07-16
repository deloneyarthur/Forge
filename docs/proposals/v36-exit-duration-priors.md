# Proposal: v36 — exit-duration prior concentration: time_stop n_bars for trend swing_long → U[8,10]; MR swing_mid → U[8,15]

Status: **SCOPING — operator-gated grammar bump; nothing ships off this doc.**
Date: 2026-07-15. Source: `FORGE_exit_duration_priors_2026-07-15.md` (prior-concentration
ask, same class as the resid_vix / nfp-cpi relays; evidence
`probe_results/exit_timestop_chandelier.json` + `probe_results/mr_timestop_swap.json`).
Response relay: `PROMPT_CRUCIBLE_EXIT_DURATION_RECEIPT.md` (held for carry).
Relates to: [[D270]] (the only existing n_bars emission — capitulation, [5,15]),
[[D169]] (the cross-hypothesis-scoping concern this design honors), [[D280]] (the v35
capitulation arm one build item overlaps — see scoping call 1), [[D257]] (the MR exit-mix
CAVEAT their §2 champion-proxy sweep finally addresses).

## Their evidence (verified against our live stream, 117,400 submissions 07-08→07-15)

1. **Trend swing_long**: 18 real WF+CPCV evals, top-6 stored trend components, champion
   exit stack, ONLY n_bars varied. The day-5 timer takes 84-88% of exits and cuts WINNERS
   (time_stop-bucket win-rate 0.45→0.74 with longer holds). n_bars=10 improves cpcv 6/6,
   wf 5/6, AND maxDD (-18.8%→-15.2%) — inside their declared §6.5.2 [3,10] box. Their
   explicit warning: do NOT extend past 10 (n=21 buys cpcv by re-opening the tail, comp0
   maxDD -44%). **Our side verified: 6,775 trend swing_long configs carry time_stop
   (5.8% of the stream) and EVERY one emits no n_bars → Crucible's registry default 5.**
   Their "today's mass" premise is exactly right.
2. **MR swing_mid**: champion-proxy sweep (replacing the dead pair exit; baseline median
   hold 31d): n_bars 8-20 is a broad improvement plateau (peak 12: SR 0.978→1.281,
   p25-proxy 0.359→0.863, maxDD -17.9→-11.4); n_bars=5 HURTS the bounce. The [5,15] box
   is right — shift mass off its floor. **Our side verified: 11,489 MR swing_mid configs
   carry time_stop (9.8% of the stream) — 11,436 param-less (default 5) + 53 capitulation
   at D270's U[5,15].** Their §2 note: the ask is generation-side only and does NOT
   depend on their in-flight champion-side family-PBO check.

## Build items (the v36 bump, if approved)

1. **Trend swing_long + time_stop → `n_bars` ~ U[8,10]** (their primary phrasing of the
   ask; the alternative "weight the top of [3,10]" is weaker and they led with the range).
2. **MR swing_mid + time_stop → `n_bars` ~ U[8,15]** (the strong form of "weight toward
   [8,15] and away from 5": ALL mass in [8,15], zero floor mass — flagged in the receipt
   so they can ask for residual floor mass before the build if they want it).

Everything else is untouched: trend swing_mid/swing_short (26,325 time_stop carriers —
their explicit "do not touch other buckets on this evidence"), regime_arbitrage /
relative_value / volatility_event / event_momentum time_stops all stay param-less
(registry default 5).

## Scoping calls (disclosed for veto in the receipt relay)

1. **Capitulation swing_mid INHERITS U[8,15].** Their §2 names the BUCKET, not a
   directional, and capitulation swing_mid IS MR swing_mid. [8,15] ⊂ the D270
   capitulation sweep box [5,15] and its center (11.5) sits next to the probe hold
   (10 td), so the shift is mild; the v35 bare-drop pane is unharmed — v36 splits
   cohorts, and the gate axis is orthogonal to the exit prior. If Crucible wants the
   just-launched v35 arm's chassis frozen instead, they veto via the receipt and
   capitulation keeps [5,15] at both buckets.
2. **Capitulation swing_short keeps D270's U[5,15].** The ask names swing_mid only;
   the swing_short rider is 8 days old and has no exit-duration evidence of its own.

## Mechanism

`_build_exits` gains a `bucket` parameter (already in scope at the call site,
`sampler.py:940`); the D270 tail-draw pattern extends to a scoped range table —
resolution order: (MR, swing_mid) → U[8,15]; else capitulation directional → U[5,15]
(the swing_short leg); else (trend, swing_long) → U[8,10]; else no emission. The extra
`randint` is drawn AFTER the standard exit draws, only on scoped paths. Two new
constants (`_TREND_SWING_LONG_TIME_STOP_NBARS_RANGE`, `_MR_SWING_MID_TIME_STOP_NBARS_RANGE`).
No rule surface: `rules:` text, predicates, and pools all untouched — emission-side only
(cleaner than v35: zero rule surfaces).

Tests: new `test_v36_exit_duration_priors.py` (both scoped ranges; other-bucket /
other-hypothesis non-emission; capitulation swing_short floor retention). One legacy
flip: `test_d270_non_momentum_time_stop_params_unchanged` (its "params == {} everywhere
else" premise narrows to the new scoping). The D270 chassis test's [5,15] assertion
stays valid ([8,15] ⊂ [5,15]). Goldens: re-pin licensed where changed — configs hitting
the new branches consume one extra randint, shifting their own downstream draws only
(per-index seeding).

## Budget / impact

~15.6% of the stream (18,264/117,400 at last week's mix) gains a real n_bars param; no
share, pacing, or §7.3 change. The funnel on post-shift cohorts is the arbiter (their
own house-discipline note) — ask `funnel --compare v35 v36` in the deploy relay.

## Ritual

One v35→v36 bump; emission-side only; full deploy ritual per `docs/tasks/deploy.md`
(ruff format changed files BEFORE commit; commit BEFORE start — the v35-proven order).
