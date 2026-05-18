# Option B — Cross-Sectional Rank Combiner: scoping doc

**Status:** Scoping / discussion. NOT a green-light to ship.
**Audience:** Operator (primary), Forge agent (Forge-side scope), Crucible agent (Crucible-side scope), contracts (schema change).
**Date:** 2026-05-16.

---

## 0. Why this doc exists

D032 just flipped `tier=1 → tier=2` in Forge's sampler. That mechanically multiplies cross-ticker breadth ~6× without grammar change and may resolve the trade-count cascade on its own. We should run a few post-D032 batches before committing to deeper work.

This doc scopes the next-bigger move *if* D032 alone is insufficient: replace v1's "fire-when-signal-AND-regime-permits" Boolean combiner with a **cross-sectional rank top-K** combiner for directional hypotheses. Per the research summary (SSRN Poh/Lim/Zohren/Roberts 2020 — "~3× Sharpe boost"), this is the academically-grounded path. Per Crucible's `config/universe.yaml`, the concept is already named (`cross_sectional_rank` is a `use_for` value on Tier 2) — meaning Crucible's design anticipated this.

---

## 1. What "cross-sectional rank top-K" means concretely

Today (v1):
```
trade_if = (directional[0] ∨ directional[1] ∨ ...)
         ∧ (regime_filter[0] ∧ regime_filter[1] ∧ ...)
         ∧ (confluence[0] ∧ confluence[1] ∧ ...)
```
At each bar, on each ticker independently, evaluate Boolean → trade or not.

Proposed (v2, rank top-K):
```
score(ticker, t) = Σ wᵢ · signalᵢ(ticker, t)
At each bar t:
  rank tickers in universe by score(ticker, t)
  open long position on top-K-ranked tickers (or top-K long + bottom-K short)
  close position when ticker drops out of top-K
```
Trade count becomes **deterministic** — K positions × N rebalances ≈ K × N_rebalances trades per backtest period. The 100-trade floor for swing_short stops being a binding constraint.

---

## 2. Forge-side scope (Forge agent owns)

### 2.1 New CombinerSpec branch
`crucible_contracts` package: extend `CombinerSpec`:
```python
type: Literal["confluence", "passthrough", "rank_top_k"]   # new value
k: int = Field(default=1, ge=1)                            # already exists; reused
score_function: Literal["weighted_sum", "z_score"] = "weighted_sum"  # new
signal_weights: dict[str, float] = Field(default_factory=dict)        # new — keyed by signal.id
ranking_universe: Literal["tier_1", "tier_2", "tier_3", "tier_2_3"] = "tier_2"  # new
long_short: Literal["long_only", "long_short", "short_only"] = "long_only"     # new
```
Contracts version bump 1.10 → 1.11. Hard rule #10 doesn't apply (this isn't a `grammar.yaml` edit), but contracts gets its own bump.

### 2.2 Enumerator changes (sampler + grammar.yaml v2)
- New v2 grammar.yaml with rule additions:
  - **C5** (composition): "rank_top_k combiner only for directional hypotheses (`trend_continuation`, `mean_reversion`, `regime_arbitrage`, `relative_value`); `tail_hedge` + `volatility_event` continue using confluence"
  - **C6** (composition): "rank_top_k requires `k ∈ {3, 5, 7, 10}` — fixed grid; not free-range to limit search space"
  - **C7** (composition): "signal_weights must sum to 1.0; weights enumerated in {0.2, 0.3, 0.5} grid per signal"
- Sampler: hypothesis-conditional combiner choice. For directional hypotheses, pick from `rank_top_k`. For tail_hedge/vol_event, keep `confluence`.
- grammar_version bump v1 → v2; archive v1.yaml under `config/grammar_archive/v1.yaml`; Decision Log entry (hard rule #10).

### 2.3 Pre-filter adjustments
- **signal_density** filter: predicts trade frequency. For rank_top_k, trade frequency = K × rebalance_freq (deterministic). Filter logic needs a branch on combiner type.
- **expected_trades** filter: same — trivial for rank-based since trade count is deterministic.
- **structural_redundancy**: should still work; no change expected.
- **novelty**: existing signature should differentiate rank_top_k combiners from confluence ones; may need signature-hash extension.

### 2.4 Tests
- Invariant test: `tail_hedge` + `volatility_event` configs never get `rank_top_k` combiner (enforced by C5).
- Determinism test: same seed produces same configs (existing reproducibility test should cover; just needs new sampler branches in fixture).
- Schema test: `rank_top_k` configs validate against contracts.

### 2.5 Estimated effort
~3-5 days for Forge agent. Most of the work is in pre-filter adjustments and tests, not the sampler change itself.

---

## 3. Crucible-side scope (Crucible agent owns)

### 3.1 New cross-sectional dispatcher in the runner
`src/optbt/data/runner.py` needs a branch: if `config.combiner.type == "rank_top_k"`, dispatch a different evaluation path:
- Iterate all tickers in `config.combiner.ranking_universe`
- At each bar, compute per-ticker `score(ticker, t)`
- Rank, take top-K (or top-K long + bottom-K short)
- Open / close positions based on rank-in / rank-out
- Hold-out semantic: when a ticker drops out of top-K, exit position (vs DTE-bucket-based exit in v1)

### 3.2 Backtest engine extension
The current engine (per Crucible §6) assumes single-underlying configs. Cross-sectional dispatch needs:
- Load all tier-N bars in parallel
- Per-bar synchronization (all tickers must have a bar at time t before ranking)
- Holiday/missing-data handling for individual tickers
- Position book that tracks N concurrent positions

This is the biggest unknown. May be a major refactor or may be a thin wrapper around the existing engine running N times.

### 3.3 Gate evaluator adjustments
- `min_oos_trade_count`: trade count is now deterministic. Either set floor=K×N_rebalances exactly (no slack), or raise threshold (e.g., K×N_rebalances × 0.9) to penalize configs that exit early too often.
- `walk_forward_sharpe_median > 2.0`: stays. **This is where the real test lives.** Rank-based on Tier 2 should plausibly hit ≥2.0 Sharpe based on published cross-sectional results.
- `total_return_vs_spy`: comparison underlying could be the equal-weighted Tier 2 portfolio rather than SPY for rank-based strategies — or stays at SPY. Operator decision.

### 3.4 Tests
- Invariant: trade_count exactly equals expected K × N for synthetic rank_top_k config.
- Cross-ticker integrity: when a ticker has missing data, position book handles gracefully.
- Comparison: same v1 config (confluence) produces same results pre- and post-refactor (regression guard).

### 3.5 Estimated effort
**1-2 weeks** for Crucible agent. Cross-sectional dispatch in the engine is the biggest unknown; could be a week alone if the engine assumes single-underlying everywhere.

---

## 4. Hybrid model — when NOT to use rank top-K

Cross-sectional ranking doesn't fit every hypothesis. Per the brainstorm, two should stay Boolean:

| Hypothesis | Combiner | Reason |
|---|---|---|
| trend_continuation | rank_top_k | rank by trend strength → buy strongest |
| mean_reversion | rank_top_k | rank by oversold strength → buy most-stretched |
| regime_arbitrage | rank_top_k | rank by regime-mismatch score |
| relative_value (pairs) | rank_top_k | rank pairs by z-score divergence |
| **tail_hedge** | **confluence** | absolute event-trigger; "fire when VIX rises" isn't a ranking |
| **volatility_event** | **confluence** | absolute event-trigger (earnings, FOMC) |

C5 enforces this in grammar. Forge agent + Crucible agent both need to honor it.

---

## 5. Risks & unknowns

### 5.1 The Sharpe wall doesn't move
Rank-based fixes trade-count but the gate is still `walk_forward_sharpe_median > 2.0`. Per Poh/Lim/Zohren/Roberts (SSRN), ML-ranked strategies hit ~3× Sharpe of threshold approaches — but their baseline was already producing trades. Our v1 baseline is mostly producing zero trades, so the "3× boost" benchmark may not apply directly. **Honest expectation: trade-count cascade dies; Sharpe wall likely still binds for some/most configs.**

### 5.2 Cross-sectional dispatch may be a major Crucible refactor
The current engine is built around single-underlying assumptions. If those assumptions are deep, the work is closer to 2-4 weeks. Crucible agent should scope this first before any commit.

### 5.3 Grammar v2 is a one-way door for the rules listed
Once v1.yaml is archived and v2.yaml ships, rolling back to v1 means a v3.yaml — not a revert. Hard rule #10 + the version-bump invariant make this explicit. Operator should be confident that rank_top_k is the right combiner archetype before committing.

### 5.4 Calibration debt compounds
D031 threshold ranges were calibrated for SPY. D032 (Tier 2) introduces calibration debt for AAPL/NVDA/etc. Adding rank semantics on top introduces *another* calibration layer (score_function, signal_weights). Three layers of calibration debt without operator review is risky.

### 5.5 Existing pre-filters may not apply
The `expected_trades` and `signal_density` pre-filters are predicated on Boolean fire-rate logic. Their predictions become trivial / wrong for rank_top_k. Forge agent needs to think through which pre-filters apply, which need branches, which should be skipped for rank configs.

---

## 6. Open questions for operator

1. **Should we wait for post-D032 data before committing?** Recommended yes — 2-3 batches of Tier 2 data may reveal that the trade-count cascade resolves without Option B at all.

2. **Universe for ranking**: just Tier 2 (24 tickers), or include Tier 3 ranked window (25-100 by volume, ~75 more tickers)? Tier 3 was explicitly designed for cross-sectional rank per `universe.yaml`.

3. **Long-only vs long-short**: long-only is simpler and lower-risk; long-short doubles the implementation cost but can produce market-neutral strategies that promote more easily on Sharpe.

4. **K value**: fixed (e.g., 5)? Enumerated grid `{3, 5, 7, 10}`? Free range?

5. **Rebalance frequency**: daily? Per-DTE-bucket (swing_short = weekly, swing_mid = bi-weekly, swing_long = monthly)?

6. **Holding period**: exit-on-rank-out, OR fixed DTE-bucket holds (current v1 behavior)? If the latter, ranking is just an entry filter, not a hold rule.

7. **Score function**: weighted_sum (simple, enumerable) only, or also z_score (normalizes across ranking universe)? More options = more grammar to enumerate.

8. **Phase naming**: Phase 7? v2 grammar? Both? CLAUDE.md §12 has phase plan; this work spans Forge + Crucible + contracts — likely deserves a named phase.

---

## 7. Honest recommendation

**Wait 2-3 batches of post-D032 data before committing.**

Reasoning:
- D032 alone is a low-risk change with high expected upside on the trade-count cascade (~6× cross-ticker breadth multiplier).
- Option B is high-effort (3-5 days Forge + 1-2 weeks Crucible + contracts version + grammar v2 + calibration layer) for a hypothesis that *may* be unnecessary if D032 solves the binding constraint.
- The structural-capacity audit's pessimism was based on SPY-only data. Tier 2 is a different problem — single names have higher idiosyncratic volatility, more frequent regime shifts, more diverse signal distributions. The "v1 grammar can't promote on SPY" finding doesn't transfer one-to-one.
- If D032 is insufficient *and* Option B is the right move, this scoping doc is the starting point; if D032 is sufficient, the work is avoided entirely.

**Decision point**: 2-3 batches post-D032 = ~6-12 hours of pipeline time (at current 15-min/run cadence with 125 configs/batch). Re-read the data, compare to the scoping cost-benefit, then decide.

---

## 8. If we DO commit, ordering

The dependency chain is:
1. **Contracts schema** (CombinerSpec v1.11) — both agents need this published first
2. **Crucible engine** (cross-sectional dispatch) — bigger lift, on critical path
3. **Forge enumerator** (sampler + grammar.yaml v2) — depends on contracts; can land before Crucible engine is complete by submitting to a feature branch
4. **Forge pre-filter adjustments** — depends on enumerator; mostly mechanical
5. **Integration test** — end-to-end with synthetic rank_top_k config

Phase work; each step lands its own Decision Log entry + tests.
