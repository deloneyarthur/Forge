# Forge — Open Questions

Append-only. Each entry: date, question, what I did instead, severity (low / medium / high).
Operator reviews at every phase boundary.

> **Note (D059 / P3-4 2026-05-18):** Some entries reference Crucible coordination prompts (`CRUCIBLE_*_AGENT_PROMPT.md` at repo root) that were deleted in commit `e85f0d4` after their work shipped. The references are preserved as historical narrative; the prompt files are recoverable via `git show e85f0d4^:<filename>`. See the matching D059 entry in `IMPLEMENTATION_DECISIONS.md` for the deleted-file list.

---

> **Rotation (2026-08-06, Step A3):** resolved/closed entries (31, Q7→Q61 era) live
> verbatim in `_archive/OPEN_QUESTIONS_RESOLVED.md`. This file holds OPEN questions
> only; move an entry to the archive in the same commit that resolves it.

---

## 2026-05-13 — Q9 — §8.4 trigger (c) cross-batch param-no-promotion — DEFERRED to Phase 7+

**Question:** §8.4's third trigger example ("0 promotions in 200+ submissions with parameter X above threshold T") requires a multi-batch rolling window. Phase 5 shipped current-batch-only — the trigger only fires on batches that themselves contain 200+ submissions. The spec example reads as a cross-batch aggregate over recent history.

**What's needed:** extend `forge.feedback.proposer.propose(report, feedback, *, at)` with a `forge_db` argument (or pre-computed `history: ParamPromotionHistory` object), then issue a query joining `submissions` × `gated_runs` over the last N batches grouped by `(hypothesis, dte_bucket, signal-param-bucket)`. The 200-submission threshold then aggregates across that history.

**Severity:** **low** — current-batch behaviour is a strict subset of the spec; it under-fires rather than mis-fires. No grammar safety issue (hard rule #3 untouched).

**Resolution 2026-05-13 (Phase 6 closure):** **D025/D8 — deferred**. Phase 6's charter is polish + operational discipline (§12). Cross-batch wiring needs a new history-query module and is closer to Phase 7 / future-operational-phase work than polish. Filing here for traceability; revisit when Crucible has > 1 batch of real promotion data and the operator wants the trigger to fire on the longer baseline.

**Tag:** `phase-7-candidate`

---

## 2026-05-14 — Q14 — Threshold semantics + stub-indicator implications

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

## 2026-05-28 — Q21 — `permutation_test._full_window` treats a trading-day count as calendar days — **LOW SEVERITY (latent)**

**Question:** `permutation_test.py:_full_window(data_start_date, data_history_days)` builds the null-distribution window as `data_history_days` *calendar* days from `data_start_date`. But `data_history_days` is a *trading*-day count (~252/yr). On the long window exposed 2026-05-28 (`data_start_date=2018-01-02`, `data_history_days=2118`), the generated window only reaches **2023-10-20** instead of ~2026 — so the permutation null pool silently excludes ~2.5 years of the most recent returns.

**Why it surfaced:** Diagnosing the post-reboot stall (D080). The window doubled when the registry-publisher re-exported Crucible's 2018 Polygon backfill (`data_start_date` 2022→2018, `data_history_days` 1109→2118). Direct instrumentation on real-cache configs showed `permutation_test` still passes a healthy fraction (~454/5000 at the service level), so this is **not** an outage — it was a red herring during the D080 RCA. But the null pool being truncated by ~2.5y biases every config's p-value.

**What I did instead:** Did NOT fix under the outage pressure (the outage was D080's synthetic fallback, not this). Logged for a clean TDD fix. Fix is small: span `data_start_date` → `utc_now()` (blessed clock, hard rule #8) by calendar days, or convert `data_history_days` to a calendar span (×365/252). A regression test must assert the pool's last date is near "today", not `start + data_history_days` calendar days.

**Severity:** **low** — latent correctness wart; biases permutation p-values but does not block submission. Pre-2026-05-28 it was masked because the 3-year window happened to cover the activation domain.

**Tag:** `permutation-test`, `calendar-vs-trading-day`, `latent`, `relates-to-D080`

**Resolution 2026-05-28 — D082:** Fixed. `_full_window` now spans `ceil(n_trading_days × 366/252)` calendar days. Chose the calendar-conversion approach over the `utc_now()` anchor floated above — it keeps the window a pure function of the registry (deterministic per hard rule #6, no clock dependency) and over-covers safely (`returns()` drops surplus dateless days). TDD: +2 tests; full prefilter suite (230) green. Deploys on next `forge.service` restart.

## 2026-05-28 — Q22 — prefetch is 17-38 min/batch — dominated by unique-spec count + writer load, not window size — **MEDIUM SEVERITY**

**Question:** `phase_timings` shows `prefetch` (the `CrucibleFeatureCache.prefetch_for_batch` socket round-trips) costs 17-38 min/batch, dwarfing every other phase (battery 5-30s, submit 2-4min). At 1 batch / ~25-40 min plus the §7.3 ≥80%-gated wait, Forge throughput is heavily bottlenecked. Can Forge mitigate?

**Investigation (2026-05-28):** Pulled the prefetch time-series. It was ALREADY 1000-2200s (17-36 min) on the OLD 3-year window (May 23-27, `data_history_days=1109`), and grew ~16× over May 21→25 (134s → 2181s) on a roughly fixed window. Today's window doubling (1109→2118) added only ~36% (pre-change avg ~1357s → post ~1852s), **sub-linear** — so window size is a MINOR lever. Large intraday variance (136s-682s on May 22 alone) points to **writer contention with the runner** (single-writer socket). Root cost: the sampler mints fresh thresholds per spec, so ~10k unique specs/batch are near-100% cache-miss every batch → ~10k indicator computations over the socket, no cross-batch amortization.

**What I did instead:** characterized only; did NOT change enumeration behavior or batch size (operator-owned tuning / cross-system design per CLAUDE.md "stop and ask"). Candidate levers, each needing operator/Crucible decision:
1. **Threshold quantization** (Forge-side): round sampled thresholds so specs repeat across batches → `signal_content_key` cache hits → fewer computations. Cost: reduces enumeration diversity.
2. **Persistent feature cache** (Crucible-side): memoize activations by `content_key` across batches / a cheaper bulk estimation endpoint. Biggest win; their side.
3. **Reduce `max_candidates`** (5000→smaller): fewer specs → faster prefetch; trades coverage for throughput.
4. Narrowing Forge's analysis window: only ~36% win (window is not the driver) — low priority, but composes with Q21's fix.

**Severity:** **medium** — no correctness break, but throughput is degraded enough to matter for the feedback-loop cadence (fewer batches gated/day = slower threshold learning).

**Tag:** `prefetch-perf`, `feature-cache`, `writer-contention`, `throughput`, `relates-to-D080`

## 2026-05-29 — Q23 — enumerator reads `universe_tickers.json` directly — hard-rule-#2 deviation pending a contracts helper — **MEDIUM SEVERITY**

**Question:** `sampler._load_underlyings` (D078) reads `~/optbt_data/exports/universe_tickers.json` via raw `json.loads(path.read_text())`. That file is NOT on the `crucible_contracts.EXPORT_LAYOUT` surface (verified: `EXPORT_LAYOUT.files == ('registry_snapshot_*.json', 'gated_runs_*.json', 'promoted_strategies_*.json', 'promoted/')`), so this is an inter-system data dependency that bypasses `crucible_contracts` — a hard-rule-#2 deviation. The contrast is explicit: `registry_loader` reads the contract-listed `registry_snapshot_*.json` through `RegistrySnapshot.model_validate_json` (the blessed pattern). Surfaced by the 2026-05-29 audit (H-5).

**What I did instead (D087):** did NOT revert D078 (its dynamic-universe value is real — the operator-requested ticker expansion). Per the audit's sanctioned interim, kept the dynamic read but made the deviation observable (`_logger.warning("universe_uncontracted_read", hard_rule="2", open_question="Q23")`, once per process) and surfaced the contracts gap via `Crucible/docs/handoffs/PROMPT_CRUCIBLE_UNIVERSE_CONTRACTS.md`. The proper fix is a `crucible_contracts.load_universe_tickers_from_export` helper (or a `tier_tickers` field on `RegistrySnapshot`) — the Q19/`universe_min_asof` precedent — after which Forge routes the read through contracts and the warning is removed.

**Severity:** **medium** — every produced candidate's underlying is chosen via this uncontracted read (hot path), but there is no correctness break and the fallback to the D033 hardcoded list is safe. It is a contract-surface purity violation + a determinism input (now folded into the batch identity by D085), not a data bug.

**Tag:** `hard-rule-2`, `contracts-gap`, `universe`, `D078`, `relates-to-H5`, `relates-to-D085`

**RESOLVED 2026-05-29 (D093):** contracts **1.13.0** shipped `load_universe_tickers_from_export` + added `universe_tickers*.json` to `EXPORT_LAYOUT.files` (commit `45f2ea0`). Forge's `_load_underlyings` now routes through that blessed helper (`_UNIVERSE_EXPORT_DIR` + glob), `FORGE_EXPECTED_CONTRACT_VERSION` bumped to `1.13.0`, and the `universe_uncontracted_read` warning is removed — the read is on the contracts surface, so the hard-rule-#2 deviation is closed. The M-13 drift logging is preserved via the helper's `QueryError` (malformed export → `universe_export_unreadable` warning + fallback). `universe_fingerprint()` (D085) is retained (Option A keeps Forge's separate identity fold; only the unbuilt Option B `RegistrySnapshot.tier_tickers` would let it ride `registry_hash` and retire). **CLOSED.**

---

## 2026-05-29 — Q24 — Non-pairs template "hidden param contract" audit REFUTED; residual risk is the un-contracted pairs entry-key schema — **LOW SEVERITY (latent)**

**Hypothesis investigated:** the generator improvement plan (`FORGE_GENERATOR_IMPROVEMENT_PLAN.md:56`) flagged that `trend_rider` / `regime_mean_revert` / `cross_sectional_rank` "likely have analogous hidden [entry-param] contracts that Forge can't satisfy" — the same trap D068/D072 fixed for `pairs_convergence` — potentially silently zero-trading whole hypotheses (a candidate explanation for the ~60% zero-trade rate).

**What I found (read-only audit of Crucible `src/optbt/`):** **REFUTED.** Crucible's router `_detect_strategy_name` (`runner.py:459-515`) maps every `forge_*` config via `_HYPOTHESIS_TO_TEMPLATE` to exactly TWO templates: `composable_long_options` (mean_reversion / trend_continuation / regime_arbitrage / volatility_event) and `pairs_convergence` (relative_value). The three suspect templates only run for configs literally named after them (YAML/Optuna fixtures); Forge never reaches them. `composable_long_options` reads entries from the declarative `signals[].params` (`threshold`/`op`), which Forge always populates (+ the leak-guard assert at `sampler.py:301-309`). So there is no hidden-key trap on Forge's path; an analogous sampler fix would be dead code. The real zero-trade levers are entry-threshold *strictness* (D031/D073 calibration) and the relative_value pair-universe size (Crucible-side), not missing keys.

**Residual risk surfaced (the real finding):** the pairs entry-key names (`pvalue_max`, `zscore_entry`, `halflife_min/max`, `lookback`) are duplicated as bare string literals on BOTH sides — Crucible `pairs_convergence.py:91-96` and Forge `sampler.py:_sample_pairs_template_params` — with no shared schema in `crucible_contracts`. If Crucible renames or adds a required entry key, Forge silently regresses to template defaults and relative_value quietly returns to ~99% zero-trade, undetectable until a gauntlet diagnostic — exactly the D068 failure mode. Soft violation of hard-rule-#2's spirit (inter-system coupling via contracts).

**What I did instead of code:** logged it; no Forge bug to fix. Recommended (needs operator priority; both cross-repo): (a) promote the pairs entry-key schema (names + default-when-missing semantics) into `crucible_contracts` so both sides import one source of truth, + a contracts test that the template's `params.get(...)` keys match the schema; (b) a Crucible-side invariant test asserting `forge_*` configs only ever dispatch to `{composable_long_options, pairs_convergence}` — the routing table is the sole safety net today.

**Severity:** **low (latent)** — no current trade loss; it is a future-silent-regression guard. Both fixes are cross-repo (contracts + Crucible), not Forge.

**Tag:** `hard-rule-2`, `contracts-gap`, `pairs`, `zero-trade`, `crucible-coordination`, `relates-to-D068`, `relates-to-D072`

---

## 2026-06-07 — Q27 — `forge_funnel.json` buckets by grammar-version STAMP, so the v9 bucket contains v8-code batches — re-bucket by the D104 cutover? — **LOW SEVERITY**

**Symptom:** `funnel/aggregate.build_funnel_export` groups `batch_summaries` purely on `grammar_version`, and `build_version_map` likewise labels each `config_hash` by stamp. Per D104, 27 v9-stamped batches (06-05 07:52 → 06-06 04:40Z) ran v8 code, so the export's v9 upstream stages (enumerated / survived / rejection breakdown) blend two code generations. Crucible flagged it (`FORGE_v9_timecut_response.md` §2, "optional ask") and currently annotates around it — their gating stages cohort correctly via their own `grammar_cutovers.yaml` relabel.

**Proposed fix (if/when wanted):** a Forge-side cutover config (mirroring Crucible's: `version`, `live_at`, `effective_prior`) consumed by `build_funnel_export`/`build_version_map` as a read-time relabel on `batch_summaries.submitted_at` — never rewriting stored stamps, always reporting the relabel count in `coverage`. Needs TDD (unit tests on the relabel + the never-silent count) + a schema_version note for the export consumers. ~Half-day.

**Why not now:** Crucible-side stages are the ones that gate, and they already cohort correctly; the D104 hygiene rule (clean live tree) makes recurrence unlikely. Revisit if a third labeling incident happens or if Crucible upgrades the ask from "optional."

**Tag:** `funnel`, `exports`, `relates-to-D104`, `relates-to-D096`, `low`

## 2026-06-07 — Q29 — Deferred D105 mechanisms: (a) threshold-DRAW adaptation for the 75-83% zero-trade composables; (b) general parameter-band bounds-learning — **(a) PARTIALLY RESOLVED 2026-06-09 (D113): prefilter-tightening arm refuted by measurement; sampler-side arm deprioritized**

**Update 2026-06-09 (D113):** the prefilter-tightening half of (a) was investigated counterfactually against the new `verdicts` table ⋈ `pre_filter_logs` join (10,130 rows) and REFUTED — every candidate knob (raise `min_pass_probability`, a new bucket-P(zero) cut, finer +underlying cells) either kills most of the component frontier (the [0.15,0.25) posterior bands hold 115/140 empirical-mode components alongside the ~60% zero-trade waste — the fat-tail pass-through D105 noted, now quantified) or captures ≤14% of v9-era waste. Decisive: the v12-cohort waste rate is already 1% zero-trade / 10% sub-10-trade vs v9's 40%/49% — the allocation re-aim + H1 rank + D112 fixed this at the sampler. The sampler-side threshold-draw mechanism stays deferred; re-open if a ≥500-decided post-v13 cohort shows sub-10-trade share >~25% (one query against `verdicts`, recipe in D113). Original entry below.

**(a) Threshold-draw adaptation.** The yield-map handoff asked whether `trade_rate_priors` reaches the composable threshold draws. Answer (D105): it is wired and BINDING — as the `expected_trades` prefilter (713-737 trend + 448-516 mean_rev kills per batch in empirical mode), not as a sampler input. So the sampler keeps drawing thresholds in the dead region and burns battery compute, and the survivors still go ~75-83% zero-trade at gate (vol_event legitimately passes the prior via its fat trading tail). A real fix feeds zero-trade feedback into the PERCENTILE-RANGE draws (`indicator_thresholds`' directional/regime ranges) — per-(indicator, role, band) attribution, a substantially new mechanism. Deferred: D105's allocation re-aim shrinks the waste organically (mr/trend/rv draw share falls toward their yield), and the prefilter already blocks most dead submissions. Revisit if post-D105 zero-trade share stays >70% on the up-weighted classes.

**(b) General bounds-learning.** The handoff's proposed mechanism — any sampled parameter band with N ≥ ~100 decided and 0 components becomes a floor-weight/drop candidate — needs per-band outcome attribution over `submissions.config_json` params x gated outcomes, plus proposer integration (auto-tighten path for drops, OPEN_PROPOSALS for widenings). D105 ships only the one decisive instance by hand (rv lookback 378: 155/0). Build the general mechanism when a second instance shows up — one data point doesn't justify the machinery.

**Tag:** `feedback`, `prefilters`, `thresholds`, `relates-to-D105`, `relates-to-D076`, `relates-to-D099`, `deferred`

## 2026-06-09 — Q34 — R1's iv_rank gate direction vs the published single-name premium evidence: the rule's own "Why" argues both sides, and the literature's validated conditioner is the IV−RV *spread*, not the IV-rank *level* — **MEDIUM**

**Update (2026-06-09, operator walkthrough):** local verdicts readout RUN (single-name MR×iv_rank, n=2,376 verdict-joined, v9-dominated; /tmp snapshot; value eras split at the D124 cost-floor cut): **inconclusive** — component rate 1.5%/1.6%/0.9% across threshold terciles (25 vs 7 components low+mid vs high, Fisher-fragile); zero-slippage-era conditional CPCV medians decline monotonically toward high thresholds (0.29→0.23→0.18, but on only 34–62 tradable rows); components-vs-rejects threshold medians barely separate (28.9 vs 30.4); the gate does not modulate tradability (tc>0 share flat across bands; 53% of cohort never trades; CPCV NULL on 94%). Gamma-flip control unreadable (n=59). Note: only the `{threshold, op}` param form exists in emission — zero percentile-form iv_rank rows. **Both asks queued in `PROMPT_CRUCIBLE_INDICATOR_GAPS.md` §1–§2 (operator: pass when convenient)**: MR template net-premium sign per DTE bucket + `iv_minus_rv`. Rule discussion waits on the answer.

**Question:** R1 (GRAMMAR.md §R1) gates mean_reversion on `iv_rank` with `threshold ≤ 50, op "<"` — fire only when IV-rank is LOW. But the rule's own rationale text is internally two-sided: it opens "mean-reversion strategies make money by **selling rich premium** that mean-reverts" and "selling premium when IV is already low … is selling lottery tickets — there's no premium to capture," then concludes the gate forces firing "only when IV is **cheap**." Those argue opposite gate directions. Which direction the evidence supports depends on a fact Forge does not control: whether Crucible's MR position templates are net SHORT premium (credit spreads — then the documented edge wants IV **rich**) or net LONG premium (debit structures betting on underlying reversion — then cheap-IV entry is right).

**What the literature says (deep-research session, this date; sources verified):**
- Goyal & Saretto (JFE 2009): sorting single names on log(12-month realized vol / ATM IV) predicts option returns — long premium where IV is *cheap vs the name's own realized*, short where *rich*; long-short straddle deciles earned 21.9%/mo gross, ~4.1%/mo at quoted-spread costs (costs, not decay, are the binding constraint). The conditioner is the **IV-vs-own-realized spread**, not the IV level/percentile alone.
- Israelov & Nielsen (JPM 2015, "Still Not Cheap"): absolute IV level is explicitly NOT a valid timing signal — low IV typically accompanies even lower realized; the implied-minus-subsequent-realized spread is what prices.
- Bakshi & Kapadia (JoD 2003): single-name VRP is thin (~1.5%/yr vs ~3.3% index) and conditions on **market** vol level, not firm vol — short-premium MR earns more when market RV is high.
- Carr & Wu (RFS 2009): raw single-name variance premia insignificant for 32/35 names — unconditioned single-name premium selling has little documented edge; conditioning is everything.

**Why this is a Q-entry, not a fix:** R1 is operator-owned (§3.5, hard rule #1); any pool/direction change is a rule edit, and admitting a new conditioner is a loosening (OPEN_PROPOSALS path). R1's own "Evidence to relax" line already anticipates exactly this: "custom realized-vs-implied ratio."

**Asks:** (1) confirm with Crucible what the MR position templates' net premium sign actually is per DTE bucket (determines which side of the iv_rank gate the evidence supports); (2) contracts/indicator gap candidate for the next round-trip: an `iv_minus_rv`-class spread indicator (ATM IV minus trailing realized, per-name) — the single best-validated single-name premium conditioner in the literature; Crucible already computes both inputs (iv_rank needs ATM IV history; realized_vol ships).

**What I did instead:** logged; no grammar/code change. MR single-name emission continues under R1 as written.

**Update (2026-06-10): RESOLVED — R1 stands as written.** Crucible's `FORGE_indicator_gaps_response.md` §1: every MR template is **net DEBIT at entry, every DTE bucket** — structural, not empirical (long-only by type: `Direction={LONG_CALL,LONG_PUT,FLAT}`, `qty>=0`, spreads banned; the DTE bucket never flips premium direction). Per the cited literature, net-LONG premium wants IV cheap → `iv_rank < threshold` is the evidence-supported side. NO rule edit. The local readout (n=2,376) is RETIRED with prejudice — their §2 found single-name chain gates were SPY-decoupled (every non-SPY iv_rank gate evaluated SPY's chain at the name's spot, finite garbage), so the readout was thresholding noise. The IV−RV spread conditioner shipped as `iv_minus_rv` (Q36 update); gate direction for the net-debit book: `iv_minus_rv < threshold`. Any R1-sibling discussion re-opens only on post-fix evidence (iv_rank v4 era — D126 boundary watch).

**Tag:** `grammar`, `R1-tension`, `literature-priors`, `contracts-gap`, `operator-action`, `relates-to-Q33`, `resolved`

---

## 2026-06-13 — Q40 — `relative_value` is structurally weak, not a defect: 0 components in 2,383 honest-era decided, because long-options-only can't express market-neutral relative value — **LOW–MEDIUM, grammar-adjacent (operator-gated)**

**Symptom (Phase 2 defect-hunt, 06-13 snapshot):** rv is 0-for across the honest era
(0 / 2,383 decided). It has flow and trades (98% non-zero `trade_count`), so it dies at
Crucible's gate, not upstream. Per-gate PASS-rate among rv rejects vs the component bar
(which requires ~100% on each): `regime_coverage` 1.4%, `deflated_sharpe` 3.3%,
`sharpe_baseline` 8.5%, `regime_stress_p25_return` 15.4%, `profit_factor` 44%,
`min_oos_trade_count` 46% — i.e. rv fails 5–6 required gates simultaneously, deeply. Not a
single-plumbing-gate (defect) signature.

**Root cause:** rv is ALWAYS expressed as `directional: pairs_zscore` + a regime_filter.
`pairs_zscore` identifies a relative mispricing between two names, but the grammar can only
BUY options (no shorting the rich leg, spreads banned). So the expression takes directional
long-options risk and pays premium/theta while waiting for reversion — it never captures the
market-neutral RV edge. Hence broadly weak risk-adjusted returns + narrow `regime_coverage`
(pairs divergences are rare and regime-clustered). This is a STRUCTURAL limit of options-only
(hard rule 7), not fixable in Forge without spread structures (currently banned).

**Cost:** rv is ~2,383 / ~12k honest-era decided ≈ **18% of Crucible's scarce decision
capacity for 0 components.** Already weight-buried (rv hypothesis weight 0.050, lowest), so
the feedback loop is correctly de-emphasizing it — but the family-agnostic prefilter still
emits it at ~7–15% of the stream.

**Question:** keep emitting a known-0% family at ~15% share, or de-emphasize it (prefilter
calibration is auto-tighten-eligible per hard rule 4; a grammar-level de-scope is
operator-gated) to reclaim capacity for diversifying families that serve the portfolio
CPCV-p25 / worst-quartile bar (the real promotion constraint, see
`FORGE_portfolio_promotion_wiring_status.md`)? Mean_reversion (1.55%) and event_momentum
(0%, signal-sparse on `sue`) are weaker-but-not-dead neighbors to decide alongside.

**RESOLVED 2026-06-14 (Sunday review) → de-emphasize, via [[D145]].** Operator chose "exempt rv
only." The review corrected the mechanism in this question: rv's ~7.5%/batch share is NOT
prefilter emission — its learned weight is already crushed (0.050) — it is the **D103
per-hypothesis submission floor** (`queue._PRODUCTION_MIN_SUBMIT_PER_HYPOTHESIS=15`), the floor
originally built to *protect* rv as the orthogonal sleeve. D145 exempts `relative_value` from
that floor (`_PRODUCTION_FLOOR_EXEMPT_HYPOTHESES`), reclaiming ~6%/batch for the merit-ranked
pool while rv still competes on merit. Ranking-stage only (enumeration byte-identity intact, no
grammar bump). `em` kept on the floor (data-sparse, not structural). The grammar de-scope half
(spreads / bear-paying expressivity) stays operator-gated and is now folded into
`docs/proposals/worst-quartile-complement-supply.md` + the OverlaySpec relay to Crucible.

**Tag:** `grammar-adjacent`, `phase-2-defect-hunt`, `relates-to-Q39`, `options-only-limit`, `operator-gated`, `RESOLVED-D145`

---

## 2026-06-15 — Q41 — Strategy generation UNDER-COVERS the live volatility/options indicator inventory: ~9 live, mostly threshold-ready measures have no enumeration path — **LOW (breadth-only; long-premium is IC-bound so EV is low), enum/grammar lane, operator-gated**

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

## 2026-07-06 — Q44 — Two forge.db tables are write-only in code (`pre_filter_logs`, `promoted_patterns`): keep as forensic sinks or stop writing? — **LOW, persistence lane, operator ruling wanted**

**Question:** The D247 tech-debt inventory found two tables that every code path writes and NO code path reads:
- `pre_filter_logs` (written `submission/pre_filter_logger.py:91` via `record_pre_filter_logs`, called from `submitter.py`) — the D076 schema comment describes an intended per-filter pass-rate use that no query ever implemented.
- `promoted_patterns` (written `feedback/promoted_patterns.py:43`, called from the daemon feedback chain + `feedback_cmd.py`) — §9.1 pattern rows, zero SELECTs anywhere.

Absence of a code reader does not prove absence of a consumer: ad-hoc DB forensics on `/tmp` snapshots is a documented workflow (`docs/tasks/investigate-live.md`). Do these tables earn their write cost + DB growth as audit trails, or should the writes be retired (schema kept for history)?

**What I did instead:** kept both untouched (removal is the irreversible direction for accumulated rows); logged here per the confirm-with-maintainer rule. If the operator confirms neither is used in investigations, retiring the writes is a small, restart-requiring change (both writers are on the daemon path).

**Severity:** low (storage/complexity only; no correctness impact either way). **Tag:** `persistence`, `write-only-tables`, `D247-followup`

---

## 2026-07-10 — Q45 — Nine never-sampled registry indicators (dark supply): no standing triage loop — **MEDIUM**

**Question:** Crucible's resid_vix handoff (FORGE_resid_vix_generation_request_2026-07-11) audited
nine registered indicators with zero Forge submissions ever: `residual_momentum`, `linreg_slope`,
`vix_term_slope`, `pct_off_52w_high`, `days_to_cover`, `trend_confirmation`, `overnight_drift`,
`cs_dispersion`, `market_sma_cross` (all nine verified present in
`registry_snapshot_2026-07-11T010003Z.json`). The mechanism is Forge's DELIBERATE activation gate:
an indicator without an `indicator_thresholds.py` entry is `is_threshold_skippable` in every
threshold role (defensive since D030 — no audited range means no honest threshold, and an
empty-params emission would zero-trade). Registered ≠ enumerable is by design; the gap is that
nothing SURFACES the dark set — a registry id that never gets an activation decision stays dark
forever, and the learned sampler can never gather evidence on it (their columns killed
`linreg_slope x trend_confirmation`, but zero-sampling means Forge could never find that out
itself).

**What I did instead:** two of the nine (`residual_momentum`, `vix_term_slope`) now ride the v27
activation proposal (OPEN_PROPOSALS `0a4d8da8`, Crucible-evidenced). The other seven remain dark.
Proposed fix (operator review): a periodic dark-supply report — registry ids lacking threshold
entries + per-id submission counts — as a healthcheck INFO line or a scheduled script, so each new
registry id gets a conscious activate/defer/reject decision instead of silence. Activation itself
should stay evidence-gated (D254: `check-activations` INERT = NO-GO); the fix is visibility, not
auto-activation.

**Severity:** medium — supply-side blind spot, but every activation still needs per-id evidence.

---

## 2026-07-12 — Q47 — Trend lane lookback mix: `rolling_sharpe` (63d) warms up ~9 months earlier than `momentum_252` — **LOW, watch item, no action until Crucible's carry note**

**Question:** Crucible's absolute-vol handoff (`FORGE_mr_absolute_vol_gate_request_2026-07-12`,
secondary observation, "no action required yet") reports that `rolling_sharpe`-ranked trend configs
(63d lookback) warm up ~9 months earlier than `momentum_252`-ranked ones — relevant to early-window
coverage in their fold evaluation. d36b1cb1-style configs are being evaluated in-book on their side;
a note will follow on whether the trend lane's lookback mix deserves deliberate weight.

**What I did instead:** logged only, per the handoff's own framing. If their note carries, the
Forge-side axis is the trend directional mix (D105/D106 learned directional/bucket weights already
adapt on evidence; a deliberate mix shift beyond that would be an enumeration-policy change with its
own proposal). Nothing to build until their in-book evaluation lands.

**Severity:** low — coverage observation, explicitly non-blocking, their measurement in flight.

---

## 2026-07-12 — Q48 — Forge prefilter battery consumed cross-name activation dates since ~06-24 (Crucible writer cache bug): impact assessment pending their fix — **HIGH visibility, MEDIUM likely impact**

**Question:** Crucible's `66a616d` (2026-06-24) keyed the writer feature-cache `activation_dates`
rows on `(signal_content_key, sha256(first_dt))` — no underlying — so every underlying collides
onto one row per spec content, first-writer-wins (verified live 2026-07-12: SPY/HAL/TGT/NVDA
identical activation sets; non-monotonic threshold responses from poisoned rows; per-name data
returns clean once cache-busted). Forge's prefilter battery reads exactly this layer per config
underlying: since ~06-24, activation-count prefilters (expected_trades wall, signal density) have
evaluated an unknown fraction of single-name configs against another name's firing dates. How much
did stream quality (gate pass rate) degrade, and is any post-06-24 prefilter-derived signal
(rejection weights on prefilter kills?) contaminated?

**Scope bounds (verified):** value_series / returns / regime_label layers are keyed correctly —
only activation_dates collides. Crucible's own gate/engine computes independently — gated_runs
outcomes, learned feedback weights (gated-run-keyed), and all promotion evidence are CLEAN.
`check-activations` INERT detection still works (no row exists for a never-computed spec); its
per-name breakdown was decorative since 06-24, but past GO verdicts stand.

**What I did instead:** relayed the bug with repro + suggested fix + cache-purge ask
(`PROMPT_CRUCIBLE_FEATURE_CACHE_ACTIVATION_POISONING.md`); worked around it for the v28 probe via
threshold-epsilon cache-busting. Impact assessment deferred until their fix + purge lands (funnel
gate-pass-rate compare pre/post 06-24 vs pre/post fix would separate the noise floor).

**Severity:** high-visibility incident, medium likely impact — prefilter precision only; the gate
is the authority and its evidence is clean.

## 2026-07-13 — Q49 — `rv_rank` (and `iv_rank`) are min-max RANGE-POSITIONS, not percentile ranks, despite kernel docstrings + Forge docs saying "percentile" — **MEDIUM (semantic drift; no behavior bug in calibrated gates; future intent-mapping hazard)**

Surfaced by Crucible's capitulation stress-test follow-up (`FORGE_capitulation_v31_followup_2026-07-13` §3),
**independently verified in `crucible_engine_core/features/realized_vol/rv_rank.py`**: the kernel computes
`(cur − rolling_min)/(rolling_max − rolling_min) × 100` — a min-max range-position — while its own docstring
says "trailing percentile rank." The docstring also states it shares semantics with `iv_history.iv_rank`, so
**`iv_rank` has the same drift**. Consequences, split carefully:

- **NOT affected:** every empirically-calibrated threshold (champion MR `rv_rank < 62`, trend's rv_rank cost
  gate, R1's iv_rank ≤ 50, the v28/v29 absolute gates — different ids entirely). These were tuned in KERNEL
  units through the funnel; behavior and evidence are self-consistent regardless of the label.
- **Affected:** any threshold mapped from a PERCENTILE INTENT (v31's `[50,80]` was mapped from the handoff's
  "intended `>= 60th pct`" framing — index drop-day median lands ~50 in kernel units, not the ~88 a percentile
  reading implied), and any future cross-system threshold translation that trusts the "percentile" name.
  Note Crucible's own gate SWEEP (§2) ran in kernel units on clean data, so its verdict (gate hurts the clean
  index arm at every level 50–70, helps single names) already prices v31's band correctly — the LEVEL
  miscalibration is moot for v31's fate; the lesson is for the NEXT mapping.
- **Action queued:** relabel Forge-side references ("percentile" → "range-position" for rv_rank/iv_rank in
  `indicator_thresholds.py` comments, `custom_predicates.py` R1/R2 comments, `docs/GRAMMAR.md`) — piggybacked
  on the next grammar bump (added to `grammar-change.md`'s pending list; docs-only, no emission change).
  Kernel docstring fix is Crucible's (flagged in the relay-back). `use_percentile` mode
  (`snap.indicator_percentile`, a real trailing-window rank) is SEPARATE machinery — unaffected, but the
  name collision is part of the hazard.

- **RESOLVED both sides 2026-07-15:** Forge relabel shipped as the v32/D272 ride-along
  (`indicator_thresholds.py` spec sites + `docs/GRAMMAR.md`); Crucible relabeled BOTH kernel docstrings
  (shim + engine-core, formula spelled out; docstring-only, no compute change / no cache re-key —
  `FORGE_earnings_manifest_published_2026-07-13.md` §Q49) and their capitulation RV-gate probe
  independently corroborated (index drop-day median ~50, not 88). Residual teeth: v31 capitulation's
  [50,80] band was mapped on the percentile reading and is now measured co-fire-strangling (69/69 dead)
  → the gate-drop is item 3 of `docs/proposals/v33-generation-health.md`. CLOSED as a question; the
  lesson (reconcile metric definition before mapping cross-system thresholds) stands in
  `grammar-change.md`'s pending list.

## 2026-07-15 — Q51 — `test_held_out_platt_reduces_ece_vs_raw` flaky in full-suite runs (DuckDB scan-order-dependent even/odd Platt split) — **LOW (test flake; diagnostic lane only)**

Failed once (of 3 full-suite runs) during the D273 deploy preflights; passes in isolation and in its
own file. `_held_out_platt_ece` (`evaluation.py`) splits fit/eval halves by ROW INDEX (even/odd), and
the row order comes from the shadow-eval SELECT — DuckDB gives NO order guarantee without ORDER BY and
can vary across runs (parallel scans, load-dependent), so the split — and occasionally the assertion
`ece_platt <= ece + 1e-9` — wobbles. Durable fix (next ranking-lane touch, not mid-deploy): ORDER BY a
stable key in the eval query (or sort rows before the split) — deterministic split, unchanged
semantics; then re-check the test's margin. Production impact: none on submissions (diagnostic
telemetry); the same scan-order wobble technically touches the LIVE `model_ece_platt` journal number.

## 2026-07-20 — Q52 — QuantIQ D418 rider ask (via Crucible's xsect-union correction relay): generation-time `expected_trades`-under-INTEGER-CONTRACT-floor check at a declared reference NAV — **LOW (their words; detect-at-generation half only)**

The promoted book's paper shadow found contract INDIVISIBILITY bites at small
NAV: the trend leg's `fixed_risk_pct 0.0075` = $187.50/trade at $25K NAV vs
~$530–6,000 per in-band contract (fillable-in-top-10 counts: 1 @ $25K / 2 @
$100K / 2 @ $200K). Backtests' fractional sizing hides the integer floor. The
ask: flag structurally-unfillable sizing at EMISSION instead of at the shadow.

Why not built yet: the check needs a PER-CONTRACT PREMIUM estimate at
emission time, and no current prefilter input carries one (`expected_trades`
consumes activations, not prices; the feature-cache reads we make are
indicator activations). Options, relayed back as a question before any build:
(a) Crucible serves a per-name "typical in-band contract premium" surface
(feature-cache or export) and Forge adds a cheap prefilter
`min_contracts_at_reference_nav >= 1`; (b) the check lives Crucible-side at
queue time next to the row-45 liquidity preflight (where chain truth already
lives — arguably the right home by the D278 principle "the mechanism is
Crucible-measured per-name against THEIR chain data"); (c) drop — the capital
side is the operator's and the shadow already detects it. Parked until their
answer; the reference-NAV declaration itself is an operator choice.

**↳ ANSWERED 2026-07-20 (same day, `FORGE_v42_ack_and_answers_2026-07-20.md`): shape (b), narrowed to an ANNOTATION.** The check lives Crucible-side at queue time next to the row-45 liquidity preflight (chain truth already in hand; (a) declined — no new cross-system surface for a LOW item). It will be an exported annotation (`min_contracts_at_reference_nav` on the verdict surface), NOT a reject — fractional sizing at engine capital is legitimate research; a non-statistical reject-class is not added quietly. **Build is gated on the OPERATOR declaring the reference NAV** (ties to the live-deposit decision); until then shape (c) is the operating truth — the shadow detects. Nothing Forge-side; Q52 stays open only as the operator-NAV tickler.

## Q60 — `forge grammar reject-proposal` cannot run while the daemon holds the DB (2026-07-26, severity: low)

**What.** Q58's recommended action (1) is to DECLINE proposal `f59812c7`. The command is
`forge grammar reject-proposal --id … --initials …`, which does a `db_connection()` **write**
(`UPDATE grammar_proposals SET status …`). The live `~/forge_data/forge.db` is held RW by
`forge.service`, where even read-only opens fail intermittently (standing pitfall,
`docs/tasks/investigate-live.md`). So the operator audit row cannot be written while the
daemon runs.

**Not urgent.** There is no auto-apply path (verified in Q58: `apply-proposal` is a separate
CLI command, called zero times from the run loop), so a PENDING proposal is inert. The
important half of Q58 — the **guard at source** — is shipped and prevents recurrence.

**Staged.** Run `reject-proposal` inside the next stop→restart window, alongside any other
DB-write chores. Pairs naturally with the `FORGE_PREFILTER_SAMPLE_N` 300 → 40 ramp.

**Worth considering later, not now.** Every other operator DB-write command has the same
constraint. A `--defer` mode that queues the audit row to a file the daemon folds in on its
next loop would remove the coupling, but that is a design increment, not a fix for today.

## Q62 — QuantIQ's 08-03 training-signals relay: six new streams need a feature/label/era-split triage (2026-08-06, severity: medium)

**What.** QuantIQ's enrichment relay (filed at
`~/proj/freeze/relays/QUANTIQ_new_training_signals_for_the_rankers_six_streams_triage_open_2026-08-03.md`;
it sat untracked and unreferenced at Forge root for 3 days — found during the repo-simplification
audit) lists six streams the rankers do not train on: (1) wire-accurate execution ground truth
(`live_arrival_spread_pct` in `spread_feedback/`, live 08-04); (2) `selector_spread_bind`
(contracts 1.41.0) — a measurement-basis flag; pooling verdict training across the pre/post-bind
boundary without it as a feature or era split changes what the gate-pass label means; (3)
`deployment_sizer_modes` (contracts 1.42.0) — the overlay, not the certified config, is what
trades; (4) designation WIN/LOSS as a label source (sharper than promotion PASS/FAIL); (5) live
fill/abandon labels (first negative fill labels, small N); (6) wings-quote staleness caveat for
any future spread feature.

**The ask (theirs, our call):** which of these earn features / labels / era splits in the two
rankers. Nothing blocks on their side. Item (2) is the time-sensitive one — it is a D337/D338
collider-class hazard for verdict training the day the first `true`-era campaigns appear in our
labels; the others accumulate value passively.

**Next action.** A dedicated triage pass over `ranking/features.py` + `dataset.py` against the
six streams, answered via `freeze/relays/`. Not done during the simplification sweep — it is
ranker design work, not hygiene.
