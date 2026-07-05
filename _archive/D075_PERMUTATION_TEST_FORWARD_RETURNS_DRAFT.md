# D075 (DRAFT) — permutation_test compares same-day returns, biases against leading indicators

**Status:** DRAFT — proposal awaiting operator review.
**Date:** 2026-05-19
**Authored:** overnight diagnostic, Forge-side response to Crucible's `PROMPT_FORGE_GENERATOR_GAPS.md` Ask #1.

---

## The finding (one sentence)

`trend_continuation` has never passed `permutation_test` in 9,308 historical Forge submissions because the test scores signals on **same-day** underlying returns, and every trend-family indicator (ema_cross, macd, donchian breakout, supertrend, momentum_252, …) is a **leading** indicator whose activation dates don't coincide with unusually high T+0 returns.

## Evidence

**Historical pass rate across all 9,308 submitted configs** (`pre_filter_logs` cross-referenced with `submissions.config_json -> hypothesis`):

| Hypothesis        | Configs that ever passed `permutation_test` | Avg p-value | Avg n_activations |
|---|---:|---:|---:|
| `relative_value`     | 3,332 | 0.066    |  180 |
| `regime_arbitrage`   | 3,265 | 0.022    |  546 |
| `tail_hedge` (pre-D066) | 1,851 | 4e-5  |  539 |
| `volatility_event`   |   859 | 0.015    |  474 |
| `mean_reversion`     |     1 | 0.040    |   60 |
| **`trend_continuation`** | **0** | — | — |

**Live iter telemetry (iters 62-63, post-D074):**

| Iter | enumerated | trend_cont rejected by permutation_test | trend_cont survived to ranked_top_n |
|---|---:|---:|---:|
| 62 | 5,000 | 1,250 (of 1,500 trend enumerated) | **0** |
| 63 | 5,000 | ~1,300 | **0** |

Every iteration since D071/D074 shipped: 1,500 trend_continuation configs enumerated, 100% rejected, ~83% by `permutation_test` specifically (the rest by `predicted_activations` and minor filters).

## The mechanism

`forge/prefilters/permutation_test.py:51-76`:

```python
real_returns = ctx.feature_cache.returns(activations)    # T+0 returns on activation dates
real_notional = sum(real_returns.values())

for _ in range(n_permutations):                          # 100 random subsamples
    sampled = rng.sample(all_returns, n_activations)     # of size n_activations
    if sum(sampled) >= real_notional:
        ge_real += 1
p_value = ge_real / n_permutations
```

Pass iff `p_value <= 0.10`. Translation: "the strategy's activation dates produce a sum-of-T+0-returns higher than 90% of equally-sized random date subsets from the data window."

### Why trend indicators systematically fail this

The §3.5 C2 directional-family mapping pins `trend_continuation` to the `trend` family. The 10 registry entries in that family are:

```
donchian, ema, ema_50, ema_cross, macd, momentum_252,
returns_12m_skip1, rolling_sharpe, sma, supertrend
```

All are **leading / regime-state** indicators. They fire on:
- Crossover events (ema_cross, macd) — sparse activations; today's return is the cross trigger but not necessarily unusual
- Breakouts (donchian) — today's return moved price past a band, but the strategy thesis is the *follow-through*, not the breakout day's return
- Trend-state continuations (supertrend, ema_50, momentum_252) — these flag *regimes*, not *outlier days*

Compare `mean_reversion`'s family (bb_pct, keltner_pct, rsi, rsi_14, rsi_2, zscore_returns) — these are **concurrent** indicators that fire *because* today's return was extreme. By construction their activation dates correlate with high |T+0 return| → real_notional is unusually high → p_value low → pass.

`permutation_test` rewards concurrent indicators and penalizes leading ones. The pass-rate table above is exactly what you'd predict from that mechanism: mean_reversion has 1 historical pass (the family includes rsi_2 which barely qualifies as leading); trend_continuation has zero.

## Proposed fix

Add a forward-horizon parameter to permutation_test calibration. Compare returns on `T+k` (or aggregated `T+1..T+k`) instead of `T+0`.

**Concretely** — config side (`config/prefilter.yaml`):

```yaml
prefilter:
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
    forward_horizon_days: 5    # NEW: 0 = current behavior (same-day); 5 = test on T+5 close
```

**Code side** (`forge/prefilters/permutation_test.py`):

```python
horizon = ctx.calibration.permutation_test.forward_horizon_days
if horizon == 0:
    target_dates = activations
else:
    target_dates = [d + timedelta(days=horizon) for d in activations]
real_returns = ctx.feature_cache.returns(target_dates)
# … rest unchanged
```

This is a 5-line code change in `permutation_test.py` + a calibration field + tests.

### Forward horizon to use

The trade thesis for `trend_continuation` swing_short (DTE 14-21) is a multi-day directional follow-through. Conservative pick: `forward_horizon_days = 5` (one trading week post-signal). Optionally aggregate returns across `[T+1, T+5]` to capture cumulative drift rather than a single forward day.

### Determinism + reproducibility

No new RNG call. Same `n_permutations`, same `p_value_threshold`. The `feature_cache.returns(dates)` interface already handles arbitrary date lists. **Hard rule #6 preserved.**

### What this is NOT

- Not a gate-strictness change. Crucible's promotion gate is untouched (hard rule #3 preserved).
- Not a grammar change. No `grammar_version` bump required. The §3.5 ruleset is unchanged.
- Not a behavioral relaxation. Strategies still need their forward-horizon real_notional to beat the 90th percentile of random forward-window subsamples. **It's a re-grounding of WHAT we test, not WHETHER we test.**

## Counter-arguments / risks

1. **"Maybe trend_continuation just isn't profitable in this regime and the test is correctly rejecting it."** Plausible but inconsistent with the data. Crucible's gauntlet shows 0/3,829 promotions across ALL hypotheses, including 3,265 regime_arbitrage configs that pass permutation_test cleanly. The bottleneck isn't trend specifically — it's trade-count + edge across the board. But trend_continuation being **structurally pre-excluded** from even reaching the gauntlet wastes the 30% of enumeration budget allocated to it (1,500 of 5,000 per iter).

2. **"Forward-horizon look-ahead in a backtest filter is risky."** Permutation_test is a pre-filter that operates on registry-resolved feature cache data, not future-aware data. The "forward horizon" here is forward *within the historical window*, not forward of the registry's `data_start_date + history`. No leakage; the comparison is still strictly historical.

3. **"k=5 is arbitrary."** Yes. Could parameterize by dte_bucket (swing_short → 5, swing_mid → 10, swing_long → 21). Or sweep multiple horizons and require pass at any one. Worth operator input on the right shape before shipping.

4. **"What if it just lets more bad trend strategies through?"** The Crucible gauntlet still gates everything. Letting more candidates *reach* the gauntlet is a producer-side correction; the gauntlet's authority over promotion is unchanged.

## What this resolves vs doesn't

| Question | Status |
|---|---|
| Crucible Ask #1 part a: why is tail_hedge 47.6% of historical cohort? | ✅ Closed (B-task). All 1,851 tail_hedge submissions predate D066 (b75bc55, 2026-05-18 23:43). Post-D066, OVERLAY_ONLY_HYPOTHESES filter in submitter.py:128 + sampler.py:185 excludes tail_hedge from enumeration AND submission. Zero tail_hedge submissions since 2026-05-17. |
| Crucible Ask #1 part b: why is trend_continuation 0/3,829? | ✅ **Diagnosed.** Mechanism above. Proposed fix: D075. |
| Crucible Ask #1 part c: why is mean_reversion 0.03%? | Partially. Same mechanism applies to a lesser degree — the mean_reversion family is *mostly* concurrent but RSI-based signals can also lag price moves. D075's forward-horizon fix should also benefit MR. |
| Crucible Ask #2: is fix scope-appropriate? | Open — operator decision. |
| Crucible Ask #3: ordering between D071/D074 (already shipped) and D075 (proposed) | Open — operator decision. |

## Recommended next step

Operator: review this draft. If concept approved, three followups:

1. Decide `forward_horizon_days` value (5? horizon-by-bucket? sweep-any?).
2. Greenlight implementation as D075.
3. After ship + restart, watch iter telemetry for two indicators:
   - `trend_continuation` non-zero in `ranked_top_n_by_hypothesis`
   - `prefilter_rejections_by_hypothesis[trend_continuation][permutation_test]` drops materially

If the fix lands: ~30% of enumeration budget (currently wasted on guaranteed-rejection trend configs) returns to productive use. Crucible's `trend_continuation` cohort goes from 0/3,829 to a measurable share.

**Hard rules check:**

- #1 (grammar operator-owned): untouched. No grammar.yaml change.
- #3 (never lower Crucible gate): untouched. Pre-filter behavior, not gate.
- #4 (auto-tightening can ship; auto-loosening cannot): N/A — calibration change, neither tightening nor loosening in the grammar sense.
- #6 (determinism): preserved. Same RNG semantics.
- #8 (blessed clock / RNG): preserved.

No restart-required side effects beyond the standard `systemctl --user restart forge.service` to pick up the new calibration + code.
