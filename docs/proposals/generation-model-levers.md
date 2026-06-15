# Generation-Side Learned Levers — Scoping (selection → generation)

**Status: SCOPING (2026-06-15, [[D155]] follow-up). Nothing ships off this doc.** It maps the levers for a
*generation* (config-shaping) learned model — distinct from the *selection* models (verdict / tail) audited in
[[D155]] — the constraints they must live under, and the honest EV ceiling. Each lever, if elected, is its own
operator-gated increment + D-entry.

**Origin:** operator — "[the verdict/tail models] are good for selection; what levers can we build a model off
of for *creating* the strategy that goes to Crucible?"

**Spec anchors:** §1.2 (Forge computes no strategy metrics — it consumes Crucible's), §3.5/§3.6 (the grammar +
the single-gate enumeration collapse ~10^15→10^6), §6.2/§8.3 (the learned-weighting sanction), hard rules
#1/#3/#4/#5/#6/#8.

**Cross-refs:** [[D155]] (the audit dating this), `tail-aware-ranker.md` (the selection layer + T1/T2/T3),
`path-a-rich-conditioning.md` Threads 2–3 (the conditioner, long-options-scoped, judged LOW-EV by [[D154]]),
[[promotion-gate-tiers-and-constraint]], [[exhaust-long-options-before-v2-spreads]], [[ml-allowed-in-loop-not-llms]].

## 0. Frame — we have librarians; this is about a trader

The verdict model (P(component), live/F3) and the tail model (`cpcv_p25`, shadow/T1) are **selection** models:
they take a finished config and rank it. As `path-a-rich-conditioning.md` §1 Thread 3 puts it, the ranker "is a
librarian ranking configs, not a trader picking entries — we have **no market-aware learned bet-signal
anywhere**." A *generation* model shapes the config **before** Crucible sees it.

One already exists, coarsely: `feedback/rejection_weights` → `enumeration/sampler.py` biases enumeration by
learned per-hypothesis / per-`(hypothesis,dte)` / per-indicator / per-underlying-class weights. So "a learned
model on the generation side" is not new ground — the question is which **better** levers to build on.

## 1. The grammar surface a generation model can set

A config (`StrategyConfig`) is: a **hypothesis**, a **directional signal** + its **threshold-quantile**, **one
regime gate** + its threshold (*the conditioner*), a **dte_bucket** (≈ theta/delta exposure band), a
**selector** (delta band), a **sizer** (e.g. `vol_target` — the M2 convex-book lever), **exits**, and a
**combiner** (`confluence` / `cross_sectional_rank` + `rank_k`). A generation model is a learned policy over
some subset of these knobs, conditioned on state.

## 2. Three insertion points (increasing leverage and risk)

### 2.1 Composition — *what mix* enumerates (the sampler). IN-SCOPE; extends a live mechanism.
- **Lever:** move the learned sampler weights from per-hypothesis to the **regime-bet cell**
  (`hypothesis × regime-gate × op-direction` — the orthogonality unit from `tail-aware-ranker.md` §4), and add a
  **tail-orthogonal** bias toward regime-bets that complement the assembled pool's worst quartile (bear/ranging).
- **Why:** attacks the confirmed trend-monoculture promotion threat ([[promotion-gate-tiers-and-constraint]]) at
  the *source* (generation) instead of hoping selection repairs it post-hoc.
- **Posture:** deterministic, no grammar change. Bounded — reweights *within* the grammar; cannot create edge
  that is not expressible. **Risk: low.**

### 2.2 Conditioning — *what gate(s)/thresholds* attach to a bet (the "trader"). Grammar-gated.
- **Lever:** today a config attaches **one** regime gate at a sampled quantile. Learn the **joint** entry
  condition — a market-aware model on `{IV-rank, skew, term-slope, regime, days-to-event, realized-vol, the
  directional trigger}` → Crucible's **conditioned-return labels** → pick the conditioner(s)/thresholds, or
  register its output as a grammar-gated indicator. (= `path-a-rich-conditioning.md` Threads 2–3.)
- **Why:** edge in options is *made in the conditioning*; this is the only lever that targets edge *magnitude*.
- **Posture:** needs Crucible conditioned-return labels (§1.2 coordination) + a grammar change (operator-gated,
  version bump, archive). **Risk: higher.** **EV: LOW for long premium now** ([[D154]]: the best vega-conditioned
  config already craters on CPCV 0.70; conditioning cannot flip long premium's sign) — its real payoff is
  **post-Path-C**, where a seller's edge exists to condition toward. Building it now is an *investment* gated on
  scope expansion.

### 2.3 Exploration — *where to probe next* (active learning). Extends D136.
- **Lever:** generate toward the grammar cells the models are most *uncertain* about (deterministic UCB /
  Thompson over under-sampled cells), enriching the feedback data the other models learn from. The D136 per-arm
  floor is the hand-coded version. **Risk: low-medium**; improves the loop rather than chasing edge directly.

## 3. The box — what makes a generation model *allowed*

| Rule | Posture |
|---|---|
| #1 grammar | Composition (2.1) + exploration (2.3) leave `grammar.yaml` untouched; conditioning (2.2) is a grammar change → operator + version bump + archive. |
| #3 gate | Shapes generation only; never touches Crucible's §8.7 gate. |
| #4 no auto-loosen | Reweights / composes / explores; relaxes nothing (tightening-direction). |
| #5 no LLM / deterministic | Frozen artifact, convex / gradient-boosted fit, **never an LLM** (rule corrected per [[ml-allowed-in-loop-not-llms]]). |
| #6 deterministic enumeration | The model is a **frozen artifact** feeding the seeded sampler; same `(grammar, registry, seed, artifact)` → byte-identical sequence; artifact id is part of batch identity (the ranker already cohort-keys this way). Property-tested. |
| #8 seeded RNG | `SeedHierarchy` only; no naked RNG. |
| §1.2 no metric compute | Trains on Crucible's returned `gate_results` / conditioned-return labels — Forge runs no backtests. |

## 4. The target lesson (from [[D155]]) — optimize the *right* objective

Whatever a generation model optimizes, it must be **verified worst-quartile robustness (`cpcv_p25`), not
gate-pass.** D155 measured that P(component) is family-tilted toward trend/ve — the low-`cpcv`, redundant
sleeve — so a generation model trained on gate-pass would *breed* the trend monoculture that threatens
promotion. The existing sampler reward is a blend (trade-production + gate-progress + Sharpe-proximity, D101) —
**not** the binding constraint. The `cpcv` target is trustworthy **only on verified-coverage rows** (D155: the
unverified majority inverts the ordering) — train and evaluate on that slice, which is growing.

## 5. Honest ceiling

Generation is higher-leverage than selection *in principle* (it shapes the pool; the binding constraint is pool
quality, not selection). **But within v1's long-premium grammar the edge magnitude is exhausted ([[D152]]/[[D154]]),
so no generation model unlocks promotion — same ceiling the selection models hit.** The promotion *unlock*
remains grammar expressivity (**Path C**, parked by operator choice); no model substitutes for it. In-scope
generation work is **pool-quality / anti-monoculture hygiene** — real, World-A-capped, honestly pitched.

## 6. Sequencing + the cheapest increment, scoped

1. **Retarget the sampler reward toward verified `cpcv`-robustness (2.1).** The one positive-EV in-scope lever.
   TDD increment: add a `cpcv_p25`-robustness reward term (verified-coverage rows only) to
   `feedback/rejection_weights`, composed with the existing reward; surface a shadow diff of the resulting
   `(hypothesis × regime-gate × direction)` sampling distribution before any enumeration change. Enumeration-
   affecting → operator-gated deploy ritual; determinism property-test required. **Honest cap: hygiene, not a
   p25 unlock.**
2. **Hold the conditioner (2.2)** as Path-C tooling — build only if Path C un-parks or a conditional pocket
   appears (`path-a-rich-conditioning.md` §0-decision).
3. **Exploration (2.3)** is optional polish on the feedback loop; defer behind (1).

## 7. Operator decisions (open)

- **(a)** Build increment §6.1 now (sampler-reward retarget — in-scope hygiene), or hold all generation work?
- **(b)** Does the "no in-scope model unlocks promotion" ceiling re-open the parked Path-C decision, or do we
  accept the World-A cap and keep the stream-quality hygiene incremental?
- **(c)** Sequence the conditioner (2.2) only as Path-C tooling, confirmed?

**Decision (2026-06-15, operator): HOLD (a)** — build nothing now; accrue the §8.6 tail streak and revisit the
§6.1 sampler-reward retarget + the T1 BLEND wiring when it clears 3/3. (b) Path-C reconsideration and (c) the
conditioner are deferred with it. The `forge-ranker-eval` daily timer accrues the streak automatically;
`scripts/tail_verified_alignment.py` tracks the verified slice on demand.

**Nothing ships off this doc** (mirrors `path-a-rich-conditioning.md`). Each elected lever is its own
operator-gated increment with a D-entry; the standing M1/M2 long-options monitor and the §8.6 tail streak run
regardless.
