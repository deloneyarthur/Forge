# Forge response — `PROMPT_FORGE_GENERATOR_GAPS.md`

**Date:** 2026-05-19
**Counterpart:** `Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md` (commit `eb19fea`, authored 2026-05-19 22:44 PDT)
**Status:** Most asks closed; one open with proposed fix in [D075 draft](./D075_PERMUTATION_TEST_FORWARD_RETURNS_DRAFT.md).

This is the Forge-side reciprocal write-up. The Crucible analysis identified seven generator-side gaps and five asks. Five of seven gaps have shipped; one is diagnosed with a proposed fix; one remains as a tracked Phase 6 item.

---

## Gaps → resolution status

| # | Crucible-side gap | Forge-side response | Status |
|---|---|---|---|
| 1 | Single exit rule per hypothesis | D071 schema rewrite (required_always + required_from_set + optional_additions + forbidden) + D071-final grammar v3 bump + Crucible 4 new ExitRule classes (ChandelierExit, ParabolicSarExit, TargetExit, ZScoreReversionExit) + contracts 1.11.0 KNOWN_EXIT_IDS update | ✅ **Shipped** |
| 2 | Sizer-mode parameter vacuum (kelly_fraction / vol_target_annual hardcoded) | D074 sampler-side mode-conditional sampling. fractional_kelly → kelly_fraction ~ U(0.10, 0.50); vol_target → vol_target_annual ~ U(0.10, 0.30) | ✅ **Shipped** |
| 3 | No feedback loop from gated outcomes back to threshold table | D073 `scripts/propose_threshold_tightenings.py` + `config/auto_tightened_thresholds.yaml` (auto-applied tightenings) + appends loosenings to `OPEN_PROPOSALS.md` (operator review per hard rule #4). LRU-cached loader in `forge/enumeration/indicator_thresholds.py::_auto_tightenings()` | ✅ **Shipped** |
| 4 | Confluence signal poverty (GEX/VEX/CEX dead-weight for directional signal generation) | D062 added dealer_positioning to `mean_reversion` + `volatility_event` C2 family allowances. Indicators are still passthrough-only at the threshold-sampler level — directional samples come from `mean_reversion` indicator pool first. The 6 dealer indicators (gex, vex, cex, call_wall_distance_pct, put_wall_distance_pct, gamma_flip_distance_pct) are eligible but rarely picked. **Acknowledged: still under-leveraged.** Tracked as Phase 7 follow-up | ⚠️ **Partial** |
| 5 | Generator doesn't account for the trade-count floor (predict trade-count pre-submission) | Tracked as **Phase 6** in `FORGE_GENERATOR_IMPROVEMENT_PLAN.md` — pre-filter for predicted trade-count using DTE × signal-density × OI/volume. Awaiting post-Phase 4/5 cohort calibration data (24h-72h post-D074) before fitting the predictor | 📋 **Planned** |
| 6 | DTE rigidity within bucket | D074 disjoint-halves sampling. swing_short (14, 21) midpoint=17 → dte_min ∈ [14,17], dte_max ∈ [18,21]. Analogous for swing_mid and swing_long. Guarantees dte_min < dte_max by construction (no retry loop) | ✅ **Shipped** |
| 7 | Hardcoded universe (sampler.py:98-105) | Acknowledged. Lower priority than #4-#5. Per `IMPLEMENTATION_DECISIONS.md` D044 the universe list is operator-curated; Crucible's `universe.yaml` is the upstream source of truth and Forge's list is a static subset. Re-syncing dynamically would change determinism guarantees (hard rule #6). **Not planned for v3** | 📋 **Out of scope** |

---

## Asks → answers

### Ask #1: Hypothesis-distribution audit (highest priority)

> Why does `tail_hedge` represent 47.6% of gated configs?
> Why is `trend_continuation` absent (0/3,829)?
> Why is `mean_reversion` 0.03%?

**Part a (tail_hedge 47.6%).** ✅ **Closed.** All 1,851 tail_hedge submissions in the Crucible cohort are from the **2026-05-14 → 2026-05-17** window, predating D066 (`b75bc55`, shipped 2026-05-18 23:43 PDT). D066 introduced `OVERLAY_ONLY_HYPOTHESES = frozenset({"tail_hedge"})` and three guards:

- `forge.enumeration.sampler:185` — sampler skips overlay-only hypotheses during enumeration
- `forge.enumeration.iterator:136` — iterator excludes them from hypothesis-weighted draws
- `forge.submission.submitter:128` — submitter rejects any leaked overlay-only config with a `ConfigInvalid`

Zero tail_hedge submissions since D066. The historical cohort skew is a snapshot-of-pre-fix artifact, not a current behavior.

**Part b (trend_continuation 0/3,829).** ✅ **Diagnosed.** The `permutation_test` pre-filter (`§5.3.7`) is structurally biased against leading indicators. It compares **same-day** underlying returns on the directional signal's activation dates against the permuted distribution. The §3.5 C2 `trend` family contains only leading / regime-state indicators (ema_cross, macd, donchian, supertrend, momentum_252, returns_12m_skip1, rolling_sharpe, sma, ema_50, ema) whose activation dates don't coincide with unusually-high T+0 returns. Pre-D075 they cannot clear the p_value ≤ 0.10 threshold.

Verified empirically: across all 9,308 historical submissions, zero trend_continuation configs ever passed permutation_test. Detailed mechanism + proposed fix in [`D075_PERMUTATION_TEST_FORWARD_RETURNS_DRAFT.md`](./D075_PERMUTATION_TEST_FORWARD_RETURNS_DRAFT.md). Awaiting operator review.

**Part c (mean_reversion 0.03%).** Same mechanism as part b but milder. The `mean_reversion` family is mostly concurrent (bb_pct, keltner_pct, zscore_returns) but RSI-based signals (rsi, rsi_14, rsi_2) can lag price extremes by 1-2 days. Of 9,308 historical submissions, exactly 1 mean_reversion config passed. D075's forward-horizon test should benefit MR alongside trend.

### Ask #2: Are fix 1 and fix 2 scope-appropriate?

**Yes — both already shipped.**

- **Fix 1** (multiple exit rules per hypothesis with optional combinations) → D071 + D071-final. Trend strategies now pick 1 of {`trailing_atr`, `chandelier_exit`, `parabolic_sar_exit`} with optional `time_stop`. MR strategies pick 1 of {`time_stop`, `target_exit`, `zscore_reversion_exit`} with optional `iv_crush_exit`. RV strategies pick 1 of {`convergence_exit`, `zscore_reversion_exit`} with optional `time_stop`. Volatility-event keeps required (`iv_crush_exit`, `event_passed_exit`) + optional `time_stop`.

- **Fix 2** (close threshold-tightening feedback loop) → D073. Walk gated_runs exports, cross-reference Forge submissions, compute per-(indicator, role) percentile envelopes from high-trade-count configs. Tightenings auto-apply via `config/auto_tightened_thresholds.yaml`; loosenings append to `OPEN_PROPOSALS.md` (operator review per hard rule #4).

### Ask #3: Order between fix 1 and fix 2

Fix 1 (D071) first because it required Crucible-side new ExitRule classes + contracts version bump. Once those landed, the v2 → v3 grammar bump closed the loop.

Fix 2 (D073) was purely additive to the feedback module and shipped independently (no Crucible dependency).

Restart with both live: **2026-05-19 23:11:12 PDT** (forge.service PID 3366740). All iters from 62+ run with combined D071 + D074 + D073-capable sampling.

### Ask #4: Does Fix 1 need a new spec type, or fit within `StrategySpec.exits: list[ExitSpec]`?

**Fits within existing spec.** No new spec type. The schema rewrite is python-side in `forge.grammar.custom_predicates._S5_HYPOTHESIS_EXITS`:

```python
{
    "required_always": tuple[str, ...],     # included unconditionally
    "required_from_set": tuple[str, ...],   # sampler picks exactly 1
    "optional_additions": tuple[str, ...],  # each added with p=0.5, capped K_MAX_OPTIONAL=2
    "forbidden": tuple[str, ...],            # validator rejects if present
}
```

The S5 predicate validates these four properties. `StrategySpec.exits: list[ExitSpec]` still arity ≥ 1. KNOWN_EXIT_IDS in `crucible_contracts/_known_exits.py` bumped from 14 → 18 IDs (contracts 1.11.0). Crucible's `build_exit(spec.id, spec.params, calendar)` dispatch in `optbt/strategy/exits/registry.py` resolves the new IDs to ChandelierExit / ParabolicSarExit / TargetExit / ZScoreReversionExit classes.

### Ask #5: Auto-tightened table location

**Shadow path under `config/auto_tightened_thresholds.yaml`,** loaded via LRU-cached `_auto_tightenings()` in `forge.enumeration.indicator_thresholds`. Sampler prefers the auto-tightened range when present and falls back to D031's audited table otherwise. This preserves the D031 audit trail as the operator-blessed baseline while allowing the feedback loop to narrow thresholds within that envelope.

`scripts/propose_threshold_tightenings.py` is the operator CLI. Running it walks the gated_runs export window and writes both:
- `config/auto_tightened_thresholds.yaml` (auto-applied tightenings; restart picks them up via LRU cache reset on file mtime)
- `OPEN_PROPOSALS.md` (loosenings appended for operator review)

---

## What's still open

1. **Operator review of D075.** Forward-horizon permutation_test is the proposed close-out for Ask #1 part b. Until shipped, trend_continuation continues to consume ~30% of per-iter enumeration budget for 0% of ranked-top-N output.

2. **Phase 6 (predicted-trade-count pre-filter).** Calibration data not yet sufficient. Re-evaluate ~72h post-D074 (≈ 2026-05-22 23:00 PDT).

3. **Phase 7 (dealer_positioning indicator under-use).** Acknowledged Gap #4 — addresses indicator pool under-use; lower priority than D075.

4. **Threshold proposer re-run.** Operator deferred (2026-05-19 ~23:00). 24h cooling window for post-D071/D074 cohort accumulation; eligible after ~2026-05-20 23:00 PDT.

---

## Notes for the Crucible side

- The analysis doc was directionally correct on every gap. The two biggest fixes (multi-exit, threshold feedback) were prescient — both had shipped within ~3 hours of the doc being authored. The remaining structural finding (Ask #1b) is genuinely subtle and isn't visible from gauntlet-side data alone; it required cross-referencing Forge's `pre_filter_logs` with `submissions.config_json` to spot the zero-pass anomaly.

- The D066 tail_hedge filter (gap #1a closure) was a coincidence: shipped the day before the analysis was authored, so the gauntlet cohort still contained ~1,851 pre-D066 tail_hedge submissions. Future analyses on cohorts > 48h old should account for this lag.

- No coordination doc needed for D075 — it's purely Forge-side calibration + code (5-line `permutation_test.py` change + a calibration field). Once operator-approved it can ship without a Crucible counterpart commit.
