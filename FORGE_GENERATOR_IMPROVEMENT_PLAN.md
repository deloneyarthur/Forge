# Forge generator improvement plan

**Authored:** 2026-05-19 (post-D066/D067/D068 overnight cycle)
**Status:** Living document — update after each phase lands
**Inputs:** Crucible-side analysis at `../Crucible/docs/handoffs/PROMPT_FORGE_GENERATOR_GAPS.md` (1,000-config gauntlet result) + Forge-side iter 33-35 monitoring (3 consecutive iterations with 100% regime_arbitrage survivors post-D066/D067)

---

## Background

Two independent analyses converged on the same broad picture:

- **Crucible's view (from the post-gauntlet evaluation):** 1,000 configs ran, 0 promoted, 706 (70.6%) produced 0 trades, mean Sharpe of traded configs -0.42. Two failure modes: (A) configs that never fire, (B) configs that fire but have no edge.
- **Forge-side view (from iter 33-35 monitoring):** With D066 (no tail_hedge), D067 (0.05 exploration floor), D068 (pairs template params) all live, three consecutive iterations produced **100% regime_arbitrage survivors** (31 / 20 / 14 of 5,000 candidates each). The other 4 sampling hypotheses got zero past the pre-filter battery.

The two diagnoses are complementary, not contradictory. Crucible sees what reaches its gauntlet; Forge sees what gets killed inside the pre-filter battery before reaching Crucible.

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

1. **Both fixes scope-appropriate.** No roadmap conflict. Crucible's Fix 1 (multi-exit) sits alongside D068's template-knob work. Crucible's Fix 2 (threshold feedback loop) extends D067's weighter-feedback infrastructure cleanly.

2. **Order: Fix 2 first, then Fix 1.** Fix 2 is purely additive (no grammar bump, no contracts change, no Crucible-side validation work). Fix 1 needs a grammar version bump (v3), §3.5 §5 rewrite, and synced Crucible `StrategySpec.exits` arity check. Land Fix 2 quickly to harvest training signal from the 1,000 existing gated runs, then take Fix 1 more carefully.

3. **Exit combinations fit existing `StrategySpec.exits: list[ExitSpec]`** — no new spec type needed. Contract already supports `len(exits) >= 1`. Crucible-side: the only check needed is "all listed exit_ids resolve to known ExitRules," which is already there.

4. **Auto-tightened table shadows D031, not replaces it.** Path: `config/auto_tightened_thresholds.yaml` written by the proposer; `indicator_thresholds.py` prefers it when present, falls back to D031. Two reasons: (a) D031 is operator-audited — we shouldn't silently overwrite operator-tuned values; (b) the shadow lets the operator diff "what auto-tuning wanted to do" against the audited baseline before approving.

---

## Sequenced implementation plan

| Phase | Item | Where | Cost | Why this order |
|---|---|---|---|---|
| **1** | Param-aware structural fingerprint (or widen constrained-hypothesis sampling) | `forge/feedback/` + `forge/enumeration/sampler.py` | Small | Immediate unblocker for iter 33-35 starvation; obscures all other diagnostics until fixed |
| **2** | Multi-class feedback: weighter consumes submission outcomes (gated / runner_failed / 0-trades / prefilter_killed) | `forge/feedback/rejection_weights.py` + CLI loader | Medium | Closes the silent-failure dynamic that produced tail_hedge AND relative_value starvation |
| **3** | Threshold auto-tightening (Crucible Fix 2): walk `gated_runs`, propose tightened per-(indicator, hypothesis) ranges; shadow D031 via `config/auto_tightened_thresholds.yaml` | `forge/feedback/proposer.py` extension | Medium | Crucible's strongest recommendation; harvests training signal from 1,000 existing gated runs |
| **4** | Multi-exit per hypothesis (Crucible Fix 1): grammar v3 §3.5 S5 rewrite — required-from-set + optional combination | `config/grammar.yaml` + `forge/grammar/custom_predicates.py` + sampler | Larger (grammar bump, archive, audit) | Highest expected impact on trade count; biggest blast radius; do AFTER feedback loops so we can measure |
| **5** | Sample sizer-mode params + DTE within bucket | `forge/enumeration/defaults.py` + sampler | Small | Quick win once Phase 4's grammar bump is in play |
| **6** | Trade-count-floor pre-filter: estimate "would this fire ≥100 OOS trades in 14 folds?" | `forge/prefilters/` | Larger (needs heuristic model) | Best as closing move once exit/sizer variation produces more diverse trade profiles to calibrate against |
| **7** | Resolve GEX/VEX/CEX dead-weight: either calibrate $-scale ranges or document as confluence-only | `indicator_thresholds.py` | Small | Cleanup; small expected impact |

---

## Current status

| Phase | Status | Decision Log |
|---|---|---|
| 1 | **Not started** — about to begin | D069 (TBD) |
| 2 | Pending | — |
| 3 | Pending | — |
| 4 | Pending | — |
| 5 | Pending | — |
| 6 | Pending | — |
| 7 | Pending | — |

### Live context (as of 2026-05-19 ~07:30 PT)

- **Recent commits:** D066 (`b75bc55`), D067 (`2aa96f0`), D068 (`f2290d4`) — all on origin/main.
- **forge.service:** active, iter 36 mid-prefetch retry after a transient Crucible-restart-induced crash earlier this morning.
- **Operator state:** Crucible-side speed-up and DB-writer restarts are done; no more anticipated restarts in this session.
- **Latest gauntlet outcome:** 1,000 configs run, 0 promoted, 706 zero-trade. Mean Sharpe -0.42 for traded configs.
- **Forge-side symptom:** 3 consecutive iters at 100% regime_arbitrage survivors (31 / 20 / 14 of 5,000); declining trend as the regime_arbitrage corpus eats its own novelty budget.

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
