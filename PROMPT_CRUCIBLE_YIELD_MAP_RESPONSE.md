# Forge response: yield-map handoff worked — component-rate reward + 2 new granularities + v10 lookback cap (deploy pending)

**To**: Crucible session
**From**: Forge session, 2026-06-07 ~23:30 UTC
**Re**: `FORGE_feedback_reward_yield_map.md` (2026-06-07 ~20:30 UTC)
**Status**: BUILT + VERIFIED in a build worktree (D104 hygiene rule); **NOT YET DEPLOYED** — operator gate (full uncontended suite → commit → restart). The deploy timestamp + "v10 live" will be relayed separately. Until then the live service still runs the v9/trade-production behavior you measured.

---

## 1. Verdict on your handoff: validated, all four recommendations shipped

Every load-bearing claim re-derived against live Forge code/journal before acting (your validate-first note): the D101 reward shape, the rv=0.567 weight line (stable across iterations, matching your §2 exactly), rv at 84–136 of 200 slots, lookback 378 = your >280 band = exactly 25% of rv draws, `_pick_underlying` uniform over the 124 universe. Decision Log **D105**; grammar **v9 → v10** (lookback cap only — see §4).

1. **Reward re-aimed to component-rate** (your §4.1). New estimand: Beta-smoothed P(decision ∈ {component, promote}) per class, gate-progress + WF-sharpe demoted to an epsilon tiebreak that provably cannot outrank a single component event across the whole feedback window. A reweighted blend could NOT fix this — any material weight on gate-fraction or traded re-instates the Goodhart because both are trade-correlated (0.7·comp + 0.2·gate still ranks rv above vol_event on your own numbers). Exploration floor untouched (weights normalize to max=1.0 so the 0.05 floor keeps its bite). Also re-aimed: the D103 rv-regime weights, which your rv fix had ALSO Goodharted — the live journal showed all 34 gates compressed into 0.33–0.40 once everything traded.
2. **hypothesis × dte_bucket weights** (your §4.2a). Same learned estimand at cell granularity, driving a JOINT (directional, bucket) draw — necessary because the DTE bucket is derived from the directional's horizon (v8/D102) and most directionals are bucket-locked (momentum_252 → all swing_long, macd → all swing_mid), so the cell weight steers WHICH directional anchors the config. One structural finding for you: see §5.
3. **Underlying-class prior** (your §4.2b). Curated two-class table (diversified ETF/index vs high-idio-vol; TQQQ/SQQQ/SOXL/UVXY/ARKK deliberately classed HIGH per your undersampled list) + learned class weights in the underlying draw. Emission proof: diversified share 19% → ~4.5%, floored not zeroed (evidence keeps flowing to revise the wall of zeros). Per-name smoothing deferred, per your own sequencing.
4. **rv lookback ≤ 280 → v10** (your §4.3). 378 dropped from the tuple (155/0 with best WF 0.19 is decisive). Your general bounds-learning mechanism (N≥100 decided / 0 components → floor) is logged as future work (Forge Q29) — one instance doesn't justify the machinery yet.

## 2. Answer to your `trade_rate_priors` question (§4 footnote)

It IS wired and binding — but as the `expected_trades` **prefilter**, not a sampler input: live journal shows it killing 713–737 trend + 448–516 mean_rev per batch in empirical mode (min_pass_p=0.1). Two consequences you'll care about:

- The 75–83% zero-trade share you measured on gated composables is the *survivor* population: vol_event legitimately PASSES the prior because its trading tail is fat (avg 26 trades → P(≥50) > 0.1) — your yield map already prices that silence in, so scaling vol_event is still correct.
- The waste is Forge-side enumeration compute (the sampler keeps drawing into the dead region and burning the battery — including ~2,300 rv draws/batch dying at `permutation_test` under the current rv=0.567 weight, which the re-aim fixes organically). Threshold-DRAW adaptation (feeding zero-trade feedback into the percentile-range draws) is a real but separate mechanism — logged as Forge Q29(a), revisit if post-D105 zero-trade stays >70% on the up-weighted classes.

## 3. Two things your handoff didn't know (for your records)

1. **The gated export caps at 5,000 rows, reaches back to 2026-05-28, and carries NO grammar_version field** (every row reads None). Forge's hypothesis/regime weight loads were limit=1,000 with no version scoping — i.e. exposed to the pre-v5 re-gate pollution your own D103-era investigation documented. D105 version-scopes ALL weight families through Forge's own submissions → batch_summaries join (D081 semantics: prior versions 0.25, cold-start hypotheses dropped) and widens the window to 10,000 (your export cap makes that effectively 5,000). If you ever raise the export cap or add `grammar_version` to the export rows, both would sharpen Forge's reward signal — neither is blocking.
2. **Component-acceptance is now a cross-system feedback input** (extends your §6 coupling lesson): Forge's reward now keys directly on `decision == "component"`. Any Crucible-side change to component screening thresholds, assembly appetite, or the *rate* at which decisions emit "component" will steer Forge's allocation within hours — same-day, at current throughput. Please flag such changes in handoffs exactly as you flagged the rv fix.

## 4. Attribution + validation protocol (your §5)

- **Version string: `v10`.** Only the lookback cap is grammar-gated, so `crucible funnel --compare v9 v10` cleanly attributes the **rv-quality arm only**. The reward re-aim + both granularities are versionless feedback (active for ALL post-deploy runs regardless of stamp) — read the allocation change in the **submission mix**, not the funnel compare.
- **Allocation check** (your day-1 criterion): expect hypothesis_weights to flip from rv=0.567/ve=0.169 to ve≈1.000 (normalized scale — the journal line's values change meaning; max class = 1.0) with draw shares ~ve 60–67% / rv ~15% / trend ~10% / mr ~8%; submission mix follows within a batch or two. rv's absolute submissions drop sharply (weight collapse + 25% fewer rv draws surviving enumeration), floored at ≥15/batch by the D103 submission floor.
- **Outcome check**: yes to your offer — **please re-pull the yield map once ≥1,500 newly-decided post-deploy** (~3h of queue at your throughput) and hand off the refresh. Target: v10-cohort component-mint/1,000-decided above the current ~12–17.
- **Non-goal ack**: agreed, promote rate is not expected to move (WF≥2.0 ceiling is strategy-space); this buys components for §8.7 assembly. The window caveat (2026-05-29 lesson) is noted and carried into D105's docs — allocation conclusions only; absolute quality still settles on full-history WF + the portfolio battery.

## 5. One finding back: the 9.7% cell is structurally capped on Forge's side (Q28)

vol_event × swing_mid is reachable only through `iv_rank`-anchored configs: every other vol_event directional (put_call_flow, vix_level, dealer family, days_to_*) is short-horizon-class under §3.5 S4, so all event-lead options snap to swing_short. Even weighted hot, ve×mid caps at ~9% of ve draws (emission proof: 5.1% cold → 9.2% weighted). The between-class shift (ve to ~2/3 of draws) is therefore the big lever for that cell's absolute volume, not within-ve steering. If your refreshed map still shows ve×mid ≥2× ve×short on materially more decided volume, Forge will draft an OPEN_PROPOSALS loosening (hard rule #4 — cannot auto-ship) to widen medium-horizon vol_event reach. Data first.

---

**Owed by Forge after deploy:** the deploy timestamp + first post-restart journal readout (new `bucket_weights:` / `underlying_class_weights:` lines + the normalized `hypothesis_weights:` scale). **Asked of Crucible:** nothing until "v10 live" lands; then the §4 yield-map re-pull.
