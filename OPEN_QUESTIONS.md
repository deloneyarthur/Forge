# Forge — Open Questions

Append-only. Each entry: date, question, what I did instead, severity (low / medium / high).
Operator reviews at every phase boundary.

> **Note (D059 / P3-4 2026-05-18):** Some entries reference Crucible coordination prompts (`CRUCIBLE_*_AGENT_PROMPT.md` at repo root) that were deleted in commit `e85f0d4` after their work shipped. The references are preserved as historical narrative; the prompt files are recoverable via `git show e85f0d4^:<filename>`. See the matching D059 entry in `IMPLEMENTATION_DECISIONS.md` for the deleted-file list.

---

> **Rotation (2026-08-06, Step A3):** resolved/closed entries (46, Q7→Q62 era; +Q23/Q34/Q40/Q49/Q62 swept 2026-09-13 Batch 1, +Q51 Batch 2, +Q44 Batch 5 G4, +Q21/Q22/Q27/Q45/Q47/Q48/Q52/Q60 Batch 5 G7) live
> verbatim in `_archive/OPEN_QUESTIONS_RESOLVED.md`. This file holds OPEN questions
> only; move an entry to the archive in the same commit that resolves it.

---

## 2026-05-13 — Q9 — §8.4 trigger (c) cross-batch param-no-promotion — DEFERRED to Phase 7+ — **MOOT under D390 (grammar frozen at v55) unless a §5 reopener fires**

**Question:** §8.4's third trigger example ("0 promotions in 200+ submissions with parameter X above threshold T") requires a multi-batch rolling window. Phase 5 shipped current-batch-only — the trigger only fires on batches that themselves contain 200+ submissions. The spec example reads as a cross-batch aggregate over recent history.

**What's needed:** extend `forge.feedback.proposer.propose(report, feedback, *, at)` with a `forge_db` argument (or pre-computed `history: ParamPromotionHistory` object), then issue a query joining `submissions` × `gated_runs` over the last N batches grouped by `(hypothesis, dte_bucket, signal-param-bucket)`. The 200-submission threshold then aggregates across that history.

**Severity:** **low** — current-batch behaviour is a strict subset of the spec; it under-fires rather than mis-fires. No grammar safety issue (hard rule #3 untouched).

**Resolution 2026-05-13 (Phase 6 closure):** **D025/D8 — deferred**. Phase 6's charter is polish + operational discipline (§12). Cross-batch wiring needs a new history-query module and is closer to Phase 7 / future-operational-phase work than polish. Filing here for traceability; revisit when Crucible has > 1 batch of real promotion data and the operator wants the trigger to fire on the longer baseline.

**Tag:** `phase-7-candidate`

---

## 2026-05-14 — Q14 — Threshold semantics + stub-indicator implications — **MOOT under D390 (grammar frozen at v55) unless a §5 reopener fires**

**Question:** Real Crucible feature cache (commit `b447597`) revealed two coupled issues:

1. **Threshold semantics mismatch:** Forge enumerator emitted threshold-style SignalSpecs with empty `params` (`indicators=(id,)` only). Crucible's `ThresholdSignal._compare` requires `params.get("threshold")`; absent → predicate `lambda _v: False` → 0 activations. Same for `params.get("op", "<")`. Most directional signals never fire under real cache.

2. **Stub indicators:** 5 of the 10 indicators registered in Crucible's v3 work return NaN on real data (`iv_rank`, `expected_value_estimator`, `vix_level`, `pairs_zscore`, `put_call_flow`). Their value distribution from audit (`docs/INDICATOR_THRESHOLDS.md`, 2026-05-14) is all-NaN. Forge's grammar §3.5 R1 (mean_reversion → iv_rank) and §3.5 X2 (fractional Kelly → expected_value_estimator) become structurally unsatisfiable.

**What I did instead:** Two-track fix:

- **Forge-side (this session):** Added `forge.enumeration.indicator_thresholds` module with audited per-indicator threshold ranges. Sampler now emits `params={"threshold": <audited>, "op": <"<" or ">">}` for every threshold-style signal. P1 grammar updated to whitelist `threshold` + `op` as signal-type predicate params (not indicator params). Price-scale indicators (`ema`, `ema_50`, `sma`) skipped from directional/regime threshold roles via `is_threshold_skippable` filter in `_pick_directional_regime_pair`. Stubs included in enumeration with educated defaults (will fire 0 until Crucible v4 implements them).

- **Crucible-side (separate workstream):** Authored `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md` for a Crucible agent to implement the 5 stubs properly. Operator-decided "long-term hold" approach (option 2) — include stubs in enumeration honestly while waiting for upstream fix.

**Severity:** **medium-high** — pipeline closure works but is structurally honest about most candidates failing until stubs are real. §3.5 R1 + X2 grammar rules effectively disabled until upstream fix.

**Resolution 2026-05-14:** Logged + Forge-side thresholds fixed; awaiting Crucible stub-impl follow-up. See **D030**.

**Tag:** `crucible-v4-prerequisite`, `threshold-semantics`

---

## 2026-05-20 — Q19 — `RegistrySnapshot` exposes `data_start_date` but not `universe_min_asof` — contracts gap — **MEDIUM SEVERITY** — **PARTIAL 2026-07-05: contracts half landed; Forge-side clip still open**

**Question:** On 2026-05-15, 125 Crucible runs failed with `No universe snapshot at or before 2021-01-04` after D031 widened backtest windows to 5y/7y. The universe table only covered 2024–2025 at the time. Forge had no defensive clip because the only date floor `RegistrySnapshot` exposes today is `crucible_contracts.RegistrySnapshot.data_start_date` — the feature-cache anchor, not the universe-coverage floor. The fix that actually landed was Crucible-side: `scripts/ingest_universe.py` back-extended snapshots to 2019-01-02 (Forge commit `a4e5d2f` documents the recovery). The two floors are independent and can drift again whenever Crucible's feature cache and universe table are widened on different cadences.

**What I did instead:** wrote up the diagnosis in the reply to Crucible's `PROMPT_FORGE_POST_D066_FINDINGS.md` (see `/home/aj/proj/Crucible/docs/handoffs/REPLY_FORGE_POST_D066_FINDINGS.md`). No code change Forge-side yet — per hard rule #2, Forge cannot read universe coverage by importing Crucible internals; the surface has to come through `crucible_contracts`.

**Severity:** **medium** — wasted ~20 min runner throughput last time it fired (125 slots × ~10s reject). Self-healed when Crucible's universe backfill landed, no recurrence in the 5 days since. But the structural gap is durable: any future widening of cache vs universe on different cadences re-opens the bug.

**Options:**

1. **Extend `crucible_contracts`** — add `universe_min_asof: date | None` to `RegistrySnapshot` (next to `data_start_date`). Forge then clips submissions against `max(data_start_date, universe_min_asof)` at submitter or pre-filter time. Minor version bump (additive). This is the option that matches the precedent set by Q7/Q8/Q12 contracts-gap resolutions.
2. **Treat as operational** — accept "Crucible's universe coverage is the source of truth; if it's behind, runs fail and Crucible patches the universe table." No Forge-side guard. Cheaper but the same bug will recur whenever cache and universe drift.
3. **Forge-side `OPTBT_HOME/universe/` peek** — Forge could read the universe table directly via DuckDB. Violates hard rule #2 (Crucible internals).

**Recommendation:** option 1. Same precedent as Q7 / Q8 / Q12 — contracts gap surfaced from Forge, fixed by additive contracts bump. Waiting on operator agreement to file the contracts ticket.

**Tag:** `contracts-gap`, `universe-coverage`, `defensive-clip`

**Update 2026-07-05 (code-health review) — PARTIAL:** the contracts half of option 1 landed — `crucible_contracts.RegistrySnapshot` now carries `universe_min_asof: date | None` (models.py, next to `data_start_date`, exactly as proposed). The Forge-side defensive clip (clip submission windows against `max(data_start_date, universe_min_asof)` at submitter or pre-filter time) remains unbuilt — no Forge code reads the field yet (verified: zero references in `src/` + `tests/`). **Entry stays OPEN, scoped to the Forge half only.**

---

## 2026-05-29 — Q24 — Non-pairs template "hidden param contract" audit REFUTED; residual risk is the un-contracted pairs entry-key schema — **LOW SEVERITY (latent)**

**Hypothesis investigated:** the generator improvement plan (`FORGE_GENERATOR_IMPROVEMENT_PLAN.md:56`) flagged that `trend_rider` / `regime_mean_revert` / `cross_sectional_rank` "likely have analogous hidden [entry-param] contracts that Forge can't satisfy" — the same trap D068/D072 fixed for `pairs_convergence` — potentially silently zero-trading whole hypotheses (a candidate explanation for the ~60% zero-trade rate).

**What I found (read-only audit of Crucible `src/optbt/`):** **REFUTED.** Crucible's router `_detect_strategy_name` (`runner.py:459-515`) maps every `forge_*` config via `_HYPOTHESIS_TO_TEMPLATE` to exactly TWO templates: `composable_long_options` (mean_reversion / trend_continuation / regime_arbitrage / volatility_event) and `pairs_convergence` (relative_value). The three suspect templates only run for configs literally named after them (YAML/Optuna fixtures); Forge never reaches them. `composable_long_options` reads entries from the declarative `signals[].params` (`threshold`/`op`), which Forge always populates (+ the leak-guard assert at `sampler.py:301-309`). So there is no hidden-key trap on Forge's path; an analogous sampler fix would be dead code. The real zero-trade levers are entry-threshold *strictness* (D031/D073 calibration) and the relative_value pair-universe size (Crucible-side), not missing keys.

**Residual risk surfaced (the real finding):** the pairs entry-key names (`pvalue_max`, `zscore_entry`, `halflife_min/max`, `lookback`) are duplicated as bare string literals on BOTH sides — Crucible `pairs_convergence.py:91-96` and Forge `sampler.py:_sample_pairs_template_params` — with no shared schema in `crucible_contracts`. If Crucible renames or adds a required entry key, Forge silently regresses to template defaults and relative_value quietly returns to ~99% zero-trade, undetectable until a gauntlet diagnostic — exactly the D068 failure mode. Soft violation of hard-rule-#2's spirit (inter-system coupling via contracts).

**What I did instead of code:** logged it; no Forge bug to fix. Recommended (needs operator priority; both cross-repo): (a) promote the pairs entry-key schema (names + default-when-missing semantics) into `crucible_contracts` so both sides import one source of truth, + a contracts test that the template's `params.get(...)` keys match the schema; (b) a Crucible-side invariant test asserting `forge_*` configs only ever dispatch to `{composable_long_options, pairs_convergence}` — the routing table is the sole safety net today.

**Severity:** **low (latent)** — no current trade loss; it is a future-silent-regression guard. Both fixes are cross-repo (contracts + Crucible), not Forge.

**Tag:** `hard-rule-2`, `contracts-gap`, `pairs`, `zero-trade`, `crucible-coordination`, `relates-to-D068`, `relates-to-D072`

---

## 2026-06-07 — Q29 — Deferred D105 mechanisms: (a) threshold-DRAW adaptation for the 75-83% zero-trade composables; (b) general parameter-band bounds-learning — **(a) PARTIALLY RESOLVED 2026-06-09 (D113): prefilter-tightening arm refuted by measurement; sampler-side arm deprioritized** — **MOOT under D390 (grammar frozen at v55) unless a §5 reopener fires**

**Update 2026-06-09 (D113):** the prefilter-tightening half of (a) was investigated counterfactually against the new `verdicts` table ⋈ `pre_filter_logs` join (10,130 rows) and REFUTED — every candidate knob (raise `min_pass_probability`, a new bucket-P(zero) cut, finer +underlying cells) either kills most of the component frontier (the [0.15,0.25) posterior bands hold 115/140 empirical-mode components alongside the ~60% zero-trade waste — the fat-tail pass-through D105 noted, now quantified) or captures ≤14% of v9-era waste. Decisive: the v12-cohort waste rate is already 1% zero-trade / 10% sub-10-trade vs v9's 40%/49% — the allocation re-aim + H1 rank + D112 fixed this at the sampler. The sampler-side threshold-draw mechanism stays deferred; re-open if a ≥500-decided post-v13 cohort shows sub-10-trade share >~25% (one query against `verdicts`, recipe in D113). Original entry below.

**(a) Threshold-draw adaptation.** The yield-map handoff asked whether `trade_rate_priors` reaches the composable threshold draws. Answer (D105): it is wired and BINDING — as the `expected_trades` prefilter (713-737 trend + 448-516 mean_rev kills per batch in empirical mode), not as a sampler input. So the sampler keeps drawing thresholds in the dead region and burns battery compute, and the survivors still go ~75-83% zero-trade at gate (vol_event legitimately passes the prior via its fat trading tail). A real fix feeds zero-trade feedback into the PERCENTILE-RANGE draws (`indicator_thresholds`' directional/regime ranges) — per-(indicator, role, band) attribution, a substantially new mechanism. Deferred: D105's allocation re-aim shrinks the waste organically (mr/trend/rv draw share falls toward their yield), and the prefilter already blocks most dead submissions. Revisit if post-D105 zero-trade share stays >70% on the up-weighted classes.

**(b) General bounds-learning.** The handoff's proposed mechanism — any sampled parameter band with N ≥ ~100 decided and 0 components becomes a floor-weight/drop candidate — needs per-band outcome attribution over `submissions.config_json` params x gated outcomes, plus proposer integration (auto-tighten path for drops, OPEN_PROPOSALS for widenings). D105 ships only the one decisive instance by hand (rv lookback 378: 155/0). Build the general mechanism when a second instance shows up — one data point doesn't justify the machinery.

**Tag:** `feedback`, `prefilters`, `thresholds`, `relates-to-D105`, `relates-to-D076`, `relates-to-D099`, `deferred`

## 2026-06-15 — Q41 — Strategy generation UNDER-COVERS the live volatility/options indicator inventory: ~9 live, mostly threshold-ready measures have no enumeration path — **LOW (breadth-only; long-premium is IC-bound so EV is low), enum/grammar lane, operator-gated** — **MOOT under D390 (grammar frozen at v55) unless a §5 reopener fires**

**Question (for the enum/grammar lane + operator):** D152 holds the long-premium conditioner *taxonomy* is complete (52 indicators; Crucible's 22-source sweep). A hypothesis-layer exploration this session (code-verified against the live registry + `grammar/custom_predicates.py` C2/R-rule pools + `enumeration/search_space.py` + `enumeration/indicator_thresholds.py`) found that Forge's *generator* nonetheless leaves ~9 live measures with **no enumeration path** — a generation-COVERAGE gap distinct from taxonomy completeness. Should any be wired (regime gate / directional)?

**The gap (live = in the registry; ready = has an audited threshold range):**
- **Orphaned `volatility` family — the main one.** 9 members, only 2 reachable (`realized_vol` via the X1 sizer chain; `rv_rank` as the trend R2 gate). The other 7 — `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol`, `atr_pct`, `vol_regime`, `amihud`, `atr` — have NO enumeration path (the `volatility` family is in no C2 directional map; only rv_rank/realized_vol are pinned into R-rule/X1 pools); 6 carry audited ranges (ready). Only `vol_regime` (a regime classifier) and a realized-vol *cheapness* gate are non-redundant; the rest are correlated estimators of vol that rv_rank/realized_vol already express.
- **`vix_term_slope`, `cs_dispersion`** — live but threshold-table-absent → used nowhere (vix_term_slope is one of D152's "6 untried levers," low-EV long-only; cs_dispersion is a breadth measure with no home).
- **`amihud`** (liquidity) — audited range but no family slot → unreachable. **`vix_level`** — reachable only via the non-enumerable `tail_hedge` → effectively dark.

**What I did instead (logged, not acted):** nothing wired. (1) Long premium is **IC-bound, not conditioner-bound** (D152: gross CPCV-p25 1.40; best vega-conditioned near-miss `iv_rank×days_to_opex` craters at 0.70) → more/better vol gates don't lift the book over 1.5; (2) more conditioning = fewer trades = fights CPCV (D156); (3) most orphans are redundant. So this is a **breadth/diversity hygiene** lever, not a promotion path. The one candidate with a rationale: give **mean_reversion a realized-vol cheapness gate** (e.g. `vol_regime`) to fix the D150 problem where its `iv_rank` "buy-cheap-vol" gate fires too sparsely (D154's live concern) — a sampler/pool edit (D150/D151 class; no rules-gate or promotion-bar change; hard rules 3/6 intact).

**Severity:** LOW. Models-lane is on HOLD (accrue the §8.6 streak); this is enum/grammar-lane (D156, also held). Surfaced so D152's "inventory complete" reads precisely as "*taxonomy* complete; *generation* under-covers." Cross-ref `docs/proposals/generation-model-levers.md` §2.1.

**Reconciliation folded in (2026-06-15 — operator-relayed Crucible answer + code-verified):** the "combine momentum × vol_event" question reduces to this same sampling-coverage issue. **C2 restricts only the DIRECTIONAL signal's family to the hypothesis** (`grammar/custom_predicates.py:154`, `:551-586` filter to `role=='directional'`); confluence/regime signals are NOT C2-restricted — so a momentum-directional × vol-event-as-confluence config is **expressible today** (Crucible confirmed; an earlier "needs a grammar change" read was too strong — that applies only to the hypothesis-keyed *regime-gate* R-rule pools). The open question is whether the **sampler emits** such cross-family-confluence configs. **Economic caveat:** a long-premium momentum bet timed *into* a vol-event buys *elevated* IV = pays the seller's premium (D152) → wrong side for long premium; the right form is the inverse — momentum gated to *cheap* vol (the realized-vol cheapness gate above). **Portfolio-level** hypothesis mixing already works but only on the WF gate (Crucible: WF-median 1.385→1.746, mean corr 0.079); it lifts the center, **not** the binding CPCV-p25 worst-quartile (D146) — necessary-not-sufficient.

**Tag:** `enum-grammar-lane`, `generation-coverage`, `low-EV`, `breadth-not-magnitude`, `operator-gated`, `relates-to-D152/D154/D156`

---
