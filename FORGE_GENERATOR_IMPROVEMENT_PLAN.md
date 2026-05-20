# Forge generator improvement plan

**Authored:** 2026-05-19 (post-D066/D067/D068 overnight cycle; refreshed against Crucible's full 3,829-cohort analysis later same day)
**Status:** Living document — update after each phase lands
**Inputs:** Crucible-side analysis at `../Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md` (3,829-config full-cohort result + per-gate fail/pass breakdown) + Forge-side iter 33-36 monitoring (4 consecutive iterations with 100% regime_arbitrage survivors post-D066/D067)

---

## Background

Two independent analyses converged on the same broad picture:

- **Crucible's view (full 3,829-cohort):** 3,829 configs evaluated through the single-period decision path, 0 promoted, 3,411 (89.1%) produced 0 trades, only 2 of 3,820 decisions cleared `min_oos_trade_count>=30` (even at the v2-1 relaxed floor — production threshold is stricter). Mean Sharpe of traded configs -0.18 (median -0.10, range -4.9 to +4.8). Two failure modes: (A) configs that never fire, (B) configs that fire but have no edge.
- **Forge-side view (iter 33-36 monitoring):** With D066 (no tail_hedge), D067 (0.05 exploration floor), D068 (pairs template params) all live, four consecutive iterations produced **100% regime_arbitrage survivors** (31 / 20 / 14 / 19 of 5,000 candidates each). The other 4 sampling hypotheses got zero past the pre-filter battery.

The two diagnoses are complementary, not contradictory. Crucible sees what reaches its gauntlet; Forge sees what gets killed inside the pre-filter battery before reaching Crucible.

### Per-gate fail/pass on Crucible's 3,820 decisions

The trade-count floor dominates everything else: 3,818 of 3,820 = **99.9% fail `min_oos_trade_count`** even at the v2-1 relaxed threshold of 30. Until configs reliably produce trades, the downstream Sharpe / PF / regime-stress gates are barely being exercised.

| Gate | Fails | Passes |
|---|---:|---:|
| `min_oos_trade_count` (>=30) | **3,818** | 2 |
| `walk_forward_sharpe_median` (>=2.0) | 3,805 | 15 |
| `cpcv_sharpe_p25` (>=1.0) | 3,805 | 15 |
| `regime_stress_p25_return` (>=0) | 3,701 | 119 |
| `deflated_sharpe` (>=0.95) | 3,664 | 156 |
| `profit_factor` (>=1.0) | 3,657 | 163 |
| `sharpe_baseline` (>=0.5) | 3,629 | 191 |
| `pbo` (<=0.5) | 2,535 | 1,285 |
| `ablation_arm` (>0) | 2,535 | 1,285 |
| `max_drawdown_ceiling` (<=0.3) | 0 | 3,820 |

---

## Combined gap analysis

### Agreed (high confidence — diagnosed independently)

| Gap | Forge framing | Crucible framing |
|---|---|---|
| Feedback is too narrow | Weighter only learns from `gated_runs`; misses pre-filter-killed / runner-failed / 0-trade outcomes | D031 threshold table never re-trained on actual gated outcomes |
| Sampler param space too tight | Coarse param sampling within hypothesis; many configs share the same structural fingerprint | Sizer-mode hardcoded (kelly_fraction=0.25, vol_target=0.20), DTE rigid within bucket, universe hardcoded |
| Combinatorial scarcity in constrained hypotheses | C2/R-rule combos collapse to 6-18 unique (directional, regime) pairs for non-regime_arbitrage hypotheses | Single-exit monoculture amplifies the collapse |

### Crucible-added (Forge missed)

- **Exit-rule monoculture** — every trend gets `trailing_atr`, every MR gets `time_stop`. Exits drive trade count more than entry signals. Probable dominant cause of the 70.6% zero-trade rate.
- **Trade-count-floor as sampler concern** — strategies firing 0.3x/session can't accumulate the 100-trade OOS floor across 14 walk-forward folds. The pre-filter could pre-estimate evaluability before submission.
- **GEX/VEX/CEX dead-weight** — passthrough-only because $-scale varies per underlying; the dealer-positioning family is half-deployed (3 of 6 indicators usable).

### Forge-added (Crucible didn't see)

- **Param-blind structural fingerprint** — T2.7's dedup hashes `(hypothesis, dte_bucket, indicator_ids, sizer_mode, exit_ids)`, NOT numeric params. With D067 forcing ~1,000 candidates per constrained hypothesis × only 6-18 (directional, regime) combos, the novelty filter correctly kills 99% as intra-batch duplicates. **This is the structural reason for the iter 33-35 100% regime_arbitrage monoculture.**
- **Implicit template-param contracts** (D068 pattern) — `pairs_convergence` reads hidden keys from `signals[0].params`; the other templates (`trend_rider`, `regime_mean_revert`, `cross_sectional_rank`) likely have analogous hidden contracts that Forge can't satisfy without auditing each template.
- **Per-hypothesis pre-filter calibration** — `expected_trades` / `signal_density` thresholds tuned for regime_arbitrage's broad activation rate starve `rsi_2 < 5`-style rare-firing entries.

---

## Answers to Crucible's asks

1. **Hypothesis-distribution audit (Crucible's highest-priority ask).** Verified against Forge's `submissions` table on 2026-05-19:

   ```
   ALL submissions (n=4,123):
     tail_hedge        1,851  (44.9%)   last submitted 2026-05-17
     relative_value    1,154  (28.0%)   last submitted 2026-05-17
     regime_arbitrage    961  (23.3%)   last submitted 2026-05-19 (current)
     volatility_event    156  (3.8%)    last submitted 2026-05-17
     mean_reversion        1  (0.02%)   last submitted 2026-05-13
     trend_continuation    0  (0%)

   Post-D066 submissions (since 2026-05-19 06:44 UTC, n=84):
     regime_arbitrage     84  (100%)
     tail_hedge            0
     all other            0
   ```

   **D066 IS firing.** Zero tail_hedge submissions since the filter shipped. Crucible's 47.6% tail_hedge in the gated cohort is the pre-D066 backlog (1,851 configs submitted 2026-05-14 to 2026-05-17) still draining through the gauntlet — those will age out over the next ~1-2 weeks of evaluation.

   **D067 IS firing,** but is overwhelmed by the pre-filter monoculture. The exploration floor correctly distributes the *sampling* budget across all 5 active hypotheses (~1,000 candidates each per 5,000-batch), but 4 of 5 are then killed inside the pre-filter battery by the param-blind structural fingerprint dedup (T2.7) — leaving only `regime_arbitrage` reaching submission. The 84 post-D066 submissions are all regime_arbitrage for that reason, not because D067 is broken. This is the iter 33-36 monoculture pattern documented above; **Phase 1 of this plan is the fix.**

   The 0/3,829 trend_continuation and 1/3,829 mean_reversion in Crucible's cohort = pre-D067-floor era when the Bayesian weighter starved them.

2. **Both fixes scope-appropriate.** No roadmap conflict. Crucible's Fix 1 (multi-exit) sits alongside D068's template-knob work. Crucible's Fix 2 (threshold feedback loop) extends D067's weighter-feedback infrastructure cleanly.

3. **Order: Fix 2 first, then Fix 1.** Fix 2 is purely additive (no grammar bump, no contracts change, no Crucible-side validation work). Fix 1 needs a grammar version bump (v3), §3.5 §5 rewrite, and synced Crucible `StrategySpec.exits` arity check. Land Fix 2 quickly to harvest training signal from the 3,829 existing gated runs, then take Fix 1 more carefully.

4. **Exit combinations fit existing `StrategySpec.exits: list[ExitSpec]`** — no new spec type needed. Contract already supports `len(exits) >= 1`. Crucible-side: the only check needed is "all listed exit_ids resolve to known ExitRules," which is already there.

5. **Auto-tightened table shadows D031, not replaces it.** Path: `config/auto_tightened_thresholds.yaml` written by the proposer; `indicator_thresholds.py` prefers it when present, falls back to D031. Two reasons: (a) D031 is operator-audited — we shouldn't silently overwrite operator-tuned values; (b) the shadow lets the operator diff "what auto-tuning wanted to do" against the audited baseline before approving.

---

## Sequenced implementation plan

| Phase | Item | Where | Cost | Why this order |
|---|---|---|---|---|
| **1** | Param-aware structural fingerprint (or widen constrained-hypothesis sampling) | `forge/feedback/` + `forge/enumeration/sampler.py` | Small | Immediate unblocker for iter 33-35 starvation; obscures all other diagnostics until fixed |
| **2** | Multi-class feedback: weighter consumes submission outcomes (gated / runner_failed / 0-trades / prefilter_killed) | `forge/feedback/rejection_weights.py` + CLI loader | Medium | Closes the silent-failure dynamic that produced tail_hedge AND relative_value starvation |
| **3** | Threshold auto-tightening (Crucible Fix 2): walk `gated_runs`, propose tightened per-(indicator, hypothesis) ranges; shadow D031 via `config/auto_tightened_thresholds.yaml` | `forge/feedback/proposer.py` extension | Medium | Crucible's strongest recommendation; harvests training signal from 3,829 existing gated runs. Directly attacks the `permutation_test` starvation of `trend_continuation` + `mean_reversion` (the dominant blocker now that registry + D069 unlocked them). |
| **3.5** | `relative_value` template + universe fix: bias `_sample_pairs_template_params` toward the aggressive end of D068's ranges (Forge-side, D072) AND draft Crucible prompt to expand `config/pair_candidates.yaml` (currently 15 pairs, only 2 viable on 2025-Q2 data per D068 diagnostic) | `forge/enumeration/sampler.py` + Crucible-side coordination doc | Small (Forge) + Crucible coordination | Cohort analysis: 309/317 = **97.5% of relative_value configs produce zero trades** — Phase 4 multi-exit cannot help configs that never open positions. Separate lever needed. |
| **4** | Multi-exit per hypothesis (Crucible Fix 1): grammar v3 §3.5 S5 rewrite — required-from-set + optional combination | `config/grammar.yaml` + `forge/grammar/custom_predicates.py` + sampler | Larger (grammar bump, archive, audit) | Highest expected impact on trade count for `volatility_event` (22+8 = 30/127 already trade) and `regime_arbitrage` (80/201 trade). Does NOT help `relative_value` (entry-side problem — Phase 3.5). |
| **5** | Sample sizer-mode params + DTE within bucket | `forge/enumeration/defaults.py` + sampler | Small | Quick win once Phase 4's grammar bump is in play |
| **6** | Trade-count-floor pre-filter: estimate "would this fire ≥100 OOS trades in 14 folds?" | `forge/prefilters/` | Larger (needs heuristic model) | Best as closing move once exit/sizer variation produces more diverse trade profiles to calibrate against |
| **7** | Resolve GEX/VEX/CEX dead-weight: either calibrate $-scale ranges or document as confluence-only | `indicator_thresholds.py` | Small | Cleanup; small expected impact |

---

## Current status

| Phase | Status | Decision Log |
|---|---|---|
| 1 | ✅ Landed + verified live (iters 37-41 stable at 200 ranked / 3-5 hypotheses producing) | D069 |
| 2 | Pending | — |
| 3 | ✅ Landed 2026-05-19 (operator-driven; auto-fire in production loop is Phase 3.x follow-up) | D073 |
| 3.5 | ✅ Forge-side landed (D072); ✅ Crucible-side landed (pair-universe 15 → 37, commit `fef53b3`) | D072 |
| 4 | **In progress** — Forge-side schema rewrite landed (D071); awaiting Crucible's `CRUCIBLE_NEW_EXITS_AGENT_PROMPT.md` (4 new ExitRule classes + contracts version bump) before the v3 grammar.yaml bump closes the phase | D071 (rewrite); D071-final pending |
| 5 | ✅ Landed 2026-05-19 — sampler-side DTE-within-bucket + sizer-mode knob sampling | D074 |
| 6 | Pending | — |
| 7 | Pending | — |

**Ops-related decisions landed this session (separate from the 7-phase plan):**
- **D070** — rate-limiter threshold restored 0.50 → 0.80 (D036's tactical drop reverted; submission rate now correctly matches gauntlet throughput).

### Live context (as of 2026-05-19 ~19:37 PT)

- **Recent commits:** D066-D070 + Phase 4 draft + multiple Crucible coordination prompts — all on origin/main.
- **forge.service:** active. Iter 42 in progress at the new ~7-8 min cadence (post-vectorization + warm cache). 5 iters of stable telemetry at `ranked_top_n=200`.
- **Crucible-side fixes shipped:** iv_rank vectorized (`compute_per_bar` for dealer family + put_call_flow), telemetry payload completed, registry-family fix (adx/hurst → `trend_strength`), pair-candidates already include cross-sector pairs.
- **Forge-side fixes shipped:** D066 (tail_hedge overlay-only), D067 (exploration floor 0.05), D068 (pairs template params), D069 (param-aware structural fingerprint), D070 (rate-limit 0.80).
- **Per-hypothesis sampler attempts (iter 41 D064 line):**

  | Hypothesis | Attempts | Killed by `permutation_test` | Other rejections | Survivors |
  |---|---:|---:|---:|---:|
  | trend_continuation | 1,534 | 1,313 (85.6%) | 221 | 0 |
  | mean_reversion | 978 | 838 (85.7%) | 140 | 0 |
  | volatility_event | 903 | 163 | 719 | 21 |
  | regime_arbitrage | 747 | 379 | 280 | 88 |
  | relative_value | 740 | 559 | 90 | 91 |

  Two hypotheses now sampling but blocked at `permutation_test` (Phase 3's target).

- **Gauntlet n_trades distribution from latest 1,000-cohort (cross-referenced with submissions):**

  | Hypothesis | 0 trades | 1-9 | 10-99 | 100+ | Total | % zero |
  |---|---:|---:|---:|---:|---:|---:|
  | `volatility_event` | 93 | 4 | 22 | 8 | 127 | 73.2% |
  | `regime_arbitrage` | 121 | 60 | 19 | 1 | 201 | 60.2% |
  | `tail_hedge` (pre-D066) | 175 | 169 | 11 | 0 | 355 | 49.3% |
  | `relative_value` | 309 | 8 | 0 | 0 | 317 | **97.5%** |

  `relative_value` 97.5% zero-trade — the case for Phase 3.5 (separate from Phase 4).

- **Throughput:** ~1,600 configs/hour submission (200 per ~7-min iter) vs ~24 configs/hour gauntlet. D070 (rate-limit 0.80) is the design-time response to this mismatch.

---

## Pointers for picking up

When this plan is resumed:

1. **Re-read `STATUS.md`** for the latest commit state and any cross-cutting context outside this plan.
2. **Check `git log --oneline -15`** for what's landed since this doc was last updated.
3. **Check the "Current status" table above** for which phase to claim next.
4. **Read Crucible's source doc** at `../Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md` if the cross-system context is needed.
5. **Each phase produces a D-numbered entry in `IMPLEMENTATION_DECISIONS.md`** — fold the entry's D-number back into the table above after landing.

### Update rules

- Append a row to the "Decision Log" column when a phase commits.
- Mark a phase "✅" once landed AND verified live in production.
- If a phase's design changes mid-implementation, edit its row in-place — don't add a parenthetical to the body. The body should always read as the current plan, not a history.
- Major scope changes (e.g., splitting a phase, adding a phase) should bump this doc's "Authored" date.

---

## References

- Crucible's analysis: `../Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md`
- D066 (tail_hedge): `IMPLEMENTATION_DECISIONS.md` D066 — overlay-only exclusion
- D067 (exploration floor): D067 — 0.05 weight floor across canonical sampling hypotheses
- D068 (pairs template params): D068 — `_sample_pairs_template_params` wiring
- D037 (stratification floor): the 2% forced-rotation that interacts with D067
- T2.7 (structural fingerprint dedup): see `D049` and `D060` in `IMPLEMENTATION_DECISIONS.md`
- Grammar v2: `config/grammar.yaml` (frozen at v2 as of D039)
