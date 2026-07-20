# Forge — Implementation Decisions Log

Append-only. Each entry: ID, date, spec section, decision, rationale, alternatives considered, action.

Order is chronological. Decisions are referenced from `STATUS.md`, `OPEN_QUESTIONS.md`, and `PHASE_N_HANDOFF.md`.

> **Note (D059 / P3-4 2026-05-18):** Older entries reference Crucible coordination prompts (`CRUCIBLE_*_AGENT_PROMPT.md` at repo root) that were deleted in commit `e85f0d4` ("docs: archive paired Crucible coordination docs + drop completed unpaired prompts") after their work shipped. The references are preserved in the historical narrative below; the prompt files themselves are recoverable via `git show e85f0d4^:CRUCIBLE_*_AGENT_PROMPT.md`. The 7 deleted prompts: `CRUCIBLE_FEATURE_CACHE_AGENT_PROMPT.md`, `CRUCIBLE_PHASE9_V3_AGENT_PROMPT.md`, `CRUCIBLE_STUB_IMPLEMENTATIONS_AGENT_PROMPT.md`, `CRUCIBLE_EV_DEADLOCK_AGENT_PROMPT.md`, `CRUCIBLE_EMPTY_THRESHOLD_AGENT_PROMPT.md`, `CRUCIBLE_DB_CHECKPOINT_ON_BATCH_AGENT_PROMPT.md`, `CRUCIBLE_TRADE_CONCENTRATION_METRIC_AGENT_PROMPT.md`.

---

> **Rotation (D242, 2026-07-05):** entries **D001–D200** live verbatim in
> `_archive/IMPLEMENTATION_DECISIONS_D001-D200.md` (the ledger crossed 1MB). Code/docs cite
> D-numbers, not paths — grep the archive for `## D0`/`## D1`/`## D200` entries. This file
> continues from D201.

## D201 — 2026-06-24 — DESIGN.md spec reconciled to as-built (doc-only): §7.3 three block reasons (D137 stall guard + D196/D200 `max_inflight`), §6.2 learned-ranking sourcing (D149 `P(component)` + D193 wf_p25 lane), §10.1 stale `contracts_version` literal redirected. No behavior change; not a deploy.

**The doc-refresh sweep surfaced that DESIGN.md (the source of truth) lagged three already-shipped behaviors. Proposed exact amendments to the operator → "approve". Spec-sync only — every behavior already has its own D-entry; this records the spec catching up, per the "spec deviations are proposed as Decision Log entries, never silent edits" rule.**

- **§7.3 Rate limiting** — was per-batch ≥80%-gated only; now documents the three independent block reasons the submitter actually applies: (1) per-batch completion, (2) the [[D137]] stall guard (Crucible idle while work pending → never feed a dead gate), (3) the [[D196]]/[[D200]] aggregate `max_inflight` in-flight-depth cap. **Closes the explicit D196 "operator to decide whether to amend §7.3" item.** Volatile thresholds (80%, stall interval, depth cap) stay in `config/forge.yaml`, not the spec.
- **§6.2 `prior_promotion_proximity_score`** — the spec described only the structural-Jaccard score and never mentioned the learned ranker (it predates the D132 shadow track). Appended a paragraph: the slot may be filled by a deterministic non-LLM model — the F3 verdict model's `P(component)` ([[D149]]) optionally × a monotone transform of a `target_wf_p25` robustness prediction (the [[D193]] quality lane) — both filling ONLY this term (§6.2 weights unchanged), each env-kill-switched (disabling restores the structural score byte-for-byte). Consistent with hard rules #5 (no LLM, ML OK) / #6 (determinism).
- **§10.1 `forge.yaml` example** — the illustrative block hard-coded `contracts_version: "1.0"` (stale value AND wrong location — the pin lives in `core/contracts_check.py`, not yaml). Replaced with a comment pointing at `FORGE_EXPECTED_CONTRACT_VERSION` / §13.5.
- **No-ops (verified by the read-only DESIGN.md validation):** meta-king never entered the spec; the "NaN stub" framing isn't in DESIGN.md; §13.5 is correctly version-agnostic; the §3.6 "25 vs 21 rules" gap is pre-existing and already tracked under [[D001]].

**Files:** `docs/DESIGN.md` (§6.2, §7.3, §10.1), `STATUS.md`, this entry. No `src/`/grammar/config change — not a deploy; reboot-safe (docs only).

**STATUS: DESIGN.md reconciled to the D200 as-built; the §7.3 amendment closes the standing D196 spec-decision. Remaining operator-gated doc-refresh items (walking through together): root archive, out-of-VCS units/scripts, config hygiene.**

---

## D202 — 2026-06-24 — Root-file cleanup sweep: archived 28 landed records (19 answered `PROMPT_CRUCIBLE_*` relays + 9 phase artifacts) to `_archive/` via `git mv`. Docs-only housekeeping; root `*.md` 85 → 57.

**Doc-refresh follow-through (operator-approved "all 28"). A read-only cleanup audit against the root-file taxonomy (`docs/architecture.md`) found ~46 archival candidates; moved the 28 HIGH-confidence ones — each self-declares done (ANSWERED/DEPLOYED/SUPERSEDED/CONFIRMED/complete) AND has a verified landing D-entry. `git mv` preserves history; the flat `_archive/` convention (was 15 files) followed; responses for the relays live in `../Crucible/docs/handoffs/FORGE_*` so the outgoing prompts archive prompt-only.**

- **Group A — 19 landed relays:** YIELD_MAP_RESPONSE ([[D105]]), V18_CUT_COMPLETE ([[D135]]), V19_OPTION_MOMENTUM_LIVE ([[D138]]), V22_EXIT_TIMECUT_FAIRTEST ([[D169]]), CONTRACTS_1_18_ADOPTED ([[D123]]), DEALER_SINGLE_NAME_RESTRICTION (v13), DEALER_REFERENCE_GATE_READMISSION, GRAMMAR_VERSION_RESOLVE ([[D096]]/[[D097]]), H2_DAYS_SINCE_EARNINGS_FAMILY ([[D107]]), EXIT_TAIL_ATTRIBUTION, LONG_OPTIONS_EXHAUSTION ([[D154]]/[[D161]]), MAGNITUDE_COST_DECOMPOSITION (superseded), OVERLAYSPEC_BEAR_COMPLEMENT, META_KING_{CONTRACT_BUMP_CONFIRM, MIN_MARGIN_ADOPTED ([[D180]]/[[D181]]), PROVENANCE_DSR}, MOMENTUM_{CHEAP_IV_REGISTRY, RECOMMENDATION_AND_INPUTS}, MR_RV_RANK_HURST_OVERLAP ([[D167]]).
- **Group B — 9 phase artifacts:** PHASE_0..6_HANDOFF, PHASE_1_RESUME_PROMPT, PHASE_4_MULTI_EXIT_DRAFT (phases 0–6 complete per CLAUDE.md). CLAUDE.md names `PHASE_N_HANDOFF.md` by pattern, not path → the reference still resolves from `_archive/`.
- **Deliberately LEFT at root:** the operator's in-flight files (2 modified + 4 untracked, incl. the live wf_p25/quality thread); `AUDIT.md` (cited historical); Tier-2 medium-confidence relays (skim-first); `PROMPT_CRUCIBLE_WORST_QUARTILE_REGIME_LABEL.md` (a valid candidate but operator-modified — don't entangle its uncommitted banner).

**Files:** 28× `git mv … _archive/`, `docs/architecture.md` (taxonomy rows), `STATUS.md`, this entry. No `src/`/grammar/config — reboot-safe.

**STATUS: root `*.md` 85 → 57. Doc-refresh items remaining (together): out-of-VCS units/scripts, config hygiene.**

---

## D203 — 2026-06-24 — New-box reproducibility: vendored the `forge-eod-check` timer (unit + script) into the repo + de-staled `setup_new_box.sh`/`stage_transfer.sh`. Docs/ops glue; no daemon or src-behavior change.

**Doc-refresh follow-through (operator "clean them all up"). The sweep found install-time artifacts that silently drift on a new-box rebuild — fixed so a clean bring-up reproduces the live system faithfully. These are install-time files (not read by the running daemon) → no restart/deploy.**

- **Vendored `forge-eod-check`:** `cp` of `forge-eod-check.{service,timer}` → `deploy/systemd/` and `~/.local/bin/forge-eod-check.sh` → `scripts/forge_eod_check.sh` (verbatim; the unit's `%h` specifiers keep it portable). It is a **report-only, out-of-loop** headless-Claude EOD reporter (writes a markdown report; explicitly forbidden from modifying/submitting/relaying) → hard rule #5 (no LLM in the production *loop*) is unaffected ([[ml-allowed-in-loop-not-llms]] reasoning). The live box is undisturbed (its installed unit still execs the same `~/.local/bin` path). Note: the script carries a fixed 2026-06-10/v17 baseline anchor (its internal logic; not refit here).
- **`setup_new_box.sh` de-staled:** removed the `EXPECTED_CONTRACTS="1.14.0"` literal — the contracts gate now derives the expected version from `FORGE_EXPECTED_CONTRACT_VERSION` in `contracts_check.py` (never re-stales on a bump); §8 now symlinks ALL `deploy/systemd/*.{service,timer}` (was `forge.service` only) + installs the eod helper + enables the four timers; dropped the uncommitted-v9 prose.
- **`stage_transfer.sh` de-staled:** the "traps" comment dropped the uncommitted-v9 trap (grammar committed at v22), promoted the multi-GB gitignored-open `forge.db` + non-portable `.venv` as the durable traps; removed the `1.27 GB`/`v1.14.0` literals.
- **`NEW_BOX_TRANSFER.md` reconciled:** removed the now-false "script is stale → install timers manually" + "eod-check not in repo, re-stand by hand" caveats; the unit table now lists all five units incl. `forge-eod-check`.

**Verify:** `bash -n` clean on both scripts; no stale literals remain (grep clean for `1.14.0`/`uncommitted v9`/`1.27 GB`/`EXPECTED_CONTRACTS`).

**Files:** `deploy/setup_new_box.sh`, `deploy/stage_transfer.sh`, `deploy/systemd/forge-eod-check.{service,timer}` (new), `scripts/forge_eod_check.sh` (new), `deploy/NEW_BOX_TRANSFER.md`, `STATUS.md`, this entry.

**STATUS: new-box scripts now reproduce the full live unit set (daemon + four timers + eod helper). Remaining doc-refresh items: config hygiene — dead `contracts_version` field (bundle into next deploy) + `grammar.yaml` R2 (defer to next bump, or confirm a dedicated v23).**

---

## D204 — 2026-06-24 — Removed the dead `CrucibleConfig.contracts_version` field (config-schema cruft). Behavior-neutral; the real contracts pin is `FORGE_EXPECTED_CONTRACT_VERSION`. Reboot-safe; takes effect on next daemon restart.

**Doc-refresh follow-through (operator "clean them all up"). `config/forge.yaml`'s `crucible.contracts_version: "1.6"` was a REQUIRED Pydantic field (`Field(min_length=1)`) whose VALUE nothing read — the actual contracts compatibility pin/check is `FORGE_EXPECTED_CONTRACT_VERSION` in `core/contracts_check.py`. Proof it was dead: the field sat at a wildly-stale `"1.6"` while the real pin moved to 1.20.0 and nothing ever errored. Removed as cruft.**

- **Removed:** the `contracts_version: str = Field(min_length=1)` field from `CrucibleConfig` (`forge_config.py`); the `contracts_version: "1.6"` line from `config/forge.yaml`; the field from the two config-test fixtures (`extra="forbid"` would otherwise reject it) + the lone assertion in `test_forge_config.py`. The `main.py` `contracts_version` LOCAL (the `forge version`/`check` echo of `check_contracts_version()`'s return) is unrelated and untouched.
- **Verified reboot-safe / behavior-neutral:** the real `config/forge.yaml` parses under the new model (smoke-checked); `mypy --strict` clean (92 files); ruff check+format clean; config + cli-threading + contracts-integration scope passes (27 tests). The RUNNING daemon already loaded its config and does not re-read `forge.yaml`, so it is unaffected; the change goes live on the next restart/reboot ([[D104]]) with zero behavior difference.
- **Not a deploy:** behavior-neutral, so no dedicated stop→suite→restart was spun up — it rides the next natural restart, and a deliberate deploy's preflight (full suite) covers it then.

**Files:** `src/forge/config/forge_config.py`, `config/forge.yaml`, `tests/unit/test_config/test_forge_config.py`, `tests/unit/test_cli/test_config_threading.py`, `STATUS.md`, this entry.

**STATUS: config schema de-crufted (dead `contracts_version` gone, reboot-safe). The ONLY remaining doc-refresh item is `grammar.yaml` R2 `evidence_to_relax` — a fix forces a v22→v23 grammar bump + live deploy + Crucible cohort-compare; HELD for explicit operator confirmation (cheap default: piggyback the next real grammar bump).**

## D205 — 2026-06-24 — Cleared a §7.3 depth-cap wedge: flushed 3,286 un-reconcilable Crucible-FAILED in-flight submissions (the 06-22 pool-crash cohort) that pinned `max_inflight`=600. Manual data-fix + restart; durable fix relayed to Crucible. PRODUCTION.

**Symptom (operator "why is Forge stuck"):** submitter blocked ~9h — every iteration logged `blocked: in-flight depth 3300 exceeds cap 600 (§7.3 backpressure)`; `forge healthcheck` WARN "no submission in 8.9h". The daemon itself was HEALTHY (looping, reconciling `batches=67`); the cap was working exactly as coded.

**Root cause:** Forge reconciles a `submitted` row only when its `config_hash` appears in Crucible's gated-runs export. **FAILED runs never enter that export** (`_evaluate_inflight_depth` / the consumer read are gated-only), so a failed submission lingers `submitted` until the 5d `STRANDED_AFTER` flush — counting as phantom in-flight depth the whole time. A 2026-06-22 Crucible runner-pool crash (`"A child process terminated abruptly, the process pool is not usable anymore"` ×77,686) failed ~73,795 forge runs; 3,200 of them, submitted 06-22, were still `submitted` in forge.db. [[D200]] then enabled `max_inflight=600` at the 06-23 23:47 restart on a depth (~3,300) its deploy note read as "genuine drainable" but which was ~99.6% dead failures → blocked from iteration 1, self-clearing only ~06-27 (5d after 06-22).

**Evidence:** runs snapshot `runs-20260624T110002Z.duckdb` (11:00:02Z) `source='forge'`: failed 124,278 / gated 86,065 / running 16; failures 06-22=73,795 vs ~50/day baseline. forge.db: 3,300 `submitted` → join by config_hash → **3,286 only-FAILED, 13 running, 1 gated** (= the reported depth 3300 exactly).

**Action (D104 stop/restart; NO code/grammar/config change → no suite spun up; backup mandatory):** stop service → `cp forge.db forge.db.bak-pre-flush-20260624` → targeted UPDATE mirroring `_flush_aged_out_submissions` (`consumer.py:402`: `status='gated', crucible_run_id=<nil sentinel>`) on the 3,286 `submitted` rows that, per the runs snapshot, have a terminal Crucible FAILED run, no gated run, and aren't in the live export → restart. Result: submitted **3,300 → 14** (depth < 600); post-restart iteration 1052 proceeded past `reconciled: batches=3` straight into the produce pipeline with **no depth-block**; daemon 34% CPU in prefetch. The sentinel write keeps these rows excluded from §7.3 completion (H-1) and `promotion_rate` (M-7), identical to a natural aged-out flush. Iteration-counter drop (1448→1052) is benign — `_next_iteration_number` counts distinct `forge_batch_id` (unchanged by the flush); the blocked daemon's in-memory counter resets to the last *persisted* batch on restart.

**Durable fix → relayed:** `PROMPT_CRUCIBLE_FAILED_RUN_FEEDBACK.md` — asks Crucible to expose terminal FAILED runs via contracts (read-path) so Forge reconciles failures promptly and excludes them from `_evaluate_inflight_depth`; plus root-cause the pool crash. Hard rule #2 blocks a Forge-only fix (no direct `runs.duckdb` read). Until then the 5d flush + the one-off script are the backstop. The §7.3 cap stays ON and unchanged — this was a one-time data correction, not a cap loosening; it now bounds only genuine in-flight (≤600).

**Files:** `STATUS.md`, `PROMPT_CRUCIBLE_FAILED_RUN_FEEDBACK.md`, this entry. One-off script: `scratchpad/flush_failed_inflight.py` (not vendored). Live data: `forge.db.submissions` (3,286 rows `submitted`→`gated`/sentinel); backup at `~/forge_data/forge.db.bak-pre-flush-20260624` (removable once stable).

**STATUS: submitter UNBLOCKED + producing; §7.3 cap healthy (bounds genuine in-flight only). Durable fix PENDING Crucible (relay ready to pass).**

---

## D206 — 2026-06-24 — Retire the D073 threshold auto-tightening path

**Spec section:** §5, §8.4, hard rule #4; lineage D073 / D031 / D085 / D171 / D034

**Decision:** Retire indicator-threshold auto-tightening. `config/auto_tightened_thresholds.yaml` is emptied to `tightenings: []` (with a retirement note), so `indicator_thresholds._auto_tightenings()` returns `{}` and the sampler falls back to the D031 audited baselines for every (indicator, role). Operator-approved loosening (hard rule #4) via OPEN_PROPOSALS proposal `c4d68531-af31-4ba2-89d8-04bad80c48a5` ("retire now (one deploy)", 2026-06-24).

**Rationale:** From the 2026-06-24 prefilter-tightening review ("helping or hurting?"). (1) FLAT AXIS — Q43→D171 confirmed the per-config threshold response is flat on the binding constraint (CPCV-p25): adx/momentum/hurst flat, rv_rank/iv_rank only faint CENTER effects, nothing on the tail. Tightenings cannot lift promotability and were not Goodharting (no edge gradient). (2) WASTE SOLVED — the live gated export (2026-06-24, 10k window) is 8,914/10,000 high-trade (≥10 trades); the zero-trade waste this path targeted is gone, owed to the D076 empirical-prior expected_trades filter + grammar maturation, not threshold selection. (3) MONOCULTURE RISK — the active set was a one-shot from 2026-05-27 (~v3-v5 cohort, never re-run); re-deriving per-(indicator,role) 5–95% bands off the current rolling 10k export (~3 days, all v21/v22, ~76% trend) would entrench the trend monoculture the pool must diversify away from (worst-quartile OOS is BEAR/RANGING-paid). The path was already inert (manual one-shot; the §5.5 calibration auto-tune never fired a tighten in the ~0% promotion regime — `prefilter.yaml` byte-frozen since D076).

**Alternatives considered:** (a) Refresh the proposer on the current cohort — rejected: flat axis → no lift, plus monoculture-entrenchment risk. (b) Leave frozen — viable (the 16 entries are near-inert) but keeps a dead moving part calibrated to an obsolete grammar. (c) Delete the file outright — equivalent (loader is defensive: missing file → {}), but a documented empty file is more discoverable.

**Action:** `tightenings: []` + retirement note in the YAML. `auto_tightenings_fingerprint()` → fixed empty-set hash `4f53cda18c2baa0c`; `enumeration_inputs_hash` shifts accordingly — a deliberate one-time enumeration-identity change, expected and tracked per D085 (no batch-id collision). Rebaselined two determinism goldens in `tests/unit/test_enumeration/test_sampler.py` (`_COHORT_GOLDEN_PRE_REFACTOR`, `_REGIME_GOLDEN_PRE`) to the post-retirement baseline-range sequence (captured under the tests' exact fixtures; now coupled to fixed D031 constants rather than the mutable YAML). Full suite 1698 passed. Deployed via the D104 ritual (preflight GO → stop → commit → restart → verify). Also in the same window: declined the 18 pre-D034 `gate_failure_concentration` proposal fossils — OPEN_PROPOSALS.md REJECTED in-file (commit b5038c5) + DB `grammar_proposals` rejected via `forge grammar reject-proposal` (the trigger is guarded off at source by the D034 `promoted_count==0` check, so they cannot regenerate). Reversible: restore the YAML from git (commit 85c1df5) + redeploy.

**STATUS: threshold auto-tightening RETIRED + live. Promotability frontier remains magnitude + diversity (ranker/quality lane D193, grammar Path C), not threshold selection.**

---

## D207 — 2026-06-25 — Alpha-budget / multiple-testing ledger (`forge alpha-budget`)

**Spec section:** §8 (feedback); hard rules #5/#6/#8 all satisfied (deterministic, no LLM, no naked RNG/clock). Addresses the LEARNED_SYSTEMS_AND_GENERATION_REVIEW B8 effective-N gap + GRAMMAR_REVIEW §5 "alpha budget" prerequisite, both of which flagged this as owned by no prior work.

**Decision:** Add a read-only `forge alpha-budget` command — Tier-1a of the honesty/loop-integrity program from the 2026-06-24 "unturned stones" audit. It measures the multiple-testing gap the production stream currently ignores: the standard sampler submits with `StrategyConfig.search_n_trials` unset, so `crucible_contracts` folds it to `n_trials=1` and Crucible's Deflated-Sharpe gate never deflates for search breadth — every gated candidate is judged as if it were the only strategy ever tried. The ledger quantifies what the gate *should* see.

**Design (deliberate):**
- **No new schema.** The two counts already exist per batch in `batch_summaries` (D085/D096): `batch_size` and `enumerated_count`. Pure read-side aggregation — sidesteps the "DB-schema = stop-and-ask" gate.
- **Bracket, don't assert, the trial count.** `n_submitted = Σ batch_size` (distinct gated configs, hard rule #9 — conservative floor) and `n_scored = Σ enumerated_count` (configs the ranker selected among — breadth ceiling; redundant, so an over-count of *independent* trials). Effective N lies between; the LdP-2019 clustering reduction is a scoped follow-up, NOT done here.
- **Headline = the Bailey-Lopez de Prado (2014) E[max] benchmark** `expected_max_sharpe(N) ≈ (1-γ)·Z⁻¹(1-1/N) + γ·Z⁻¹(1-1/(Ne))` — the Sharpe (cross-trial SR-stdev units) the best of N null strategies reaches by luck, computed at both bracket ends. Uses stdlib `statistics.NormalDist.inv_cdf` (deterministic; no scipy/numpy, no new dep). `N≤1 → 0` (no multiplicity, no haircut).
- **Boundary NOT pre-judged.** Per-grammar-version AND cumulative both reported; pinning the accounting boundary (and whether/how Crucible charges it) is the explicit Crucible-coordination half (LEARNED_SYSTEMS B8) — the ledger presents the candidates, it does not decide.

**Scope/safety:** Additive, NOT wired into the production loop (the daemon never reads it) → reboot-safe; committed but not deployed (a read-only command needs no restart). DB access mirrors `ranker-model --forge-db` (caller snapshots the live DB under its RW lock; friendly lock-error hint on failure). New files: `src/forge/feedback/alpha_budget.py` (pure math + aggregation), `src/forge/cli/alpha_budget_cmd.py` (DB read + format + glue), registered with one line in `cli/main.py`. Tests: `tests/unit/test_feedback/test_alpha_budget.py` (benchmark values vs LdP, aggregation, natural version sort) + `tests/unit/test_cli/test_alpha_budget.py` (DB round-trip, format, CLI smoke). 11 new tests; ruff + mypy --strict clean; CLI+feedback scope 372/0. MANPAGE updated.

**STATUS: shipped (committed, not deployed). First of the Tier-1 honesty/loop-integrity items; next — pre-registration registry (1a-ii), champion/challenger model-adoption gate (1c).**

---

## D208 — 2026-06-25 — Pre-registration registry + post-cut confirmation (`forge prereg`)

**Spec section:** §8.4 (auto-tightening triggers fire on the motivating cohort); hard rules #6/#8 satisfied (deterministic id from sha256; clock via `forge.core.clock`). Implements the GRAMMAR_REVIEW §5 "pre-register every prune/retarget and confirm payoff on a *later* time-cut cohort (never the cohort that motivated it)" prerequisite, owned by no prior work.

**Decision:** Add `forge prereg` (register/list/resolve) backed by `forge.feedback.preregistration` — Tier-1a, the post-selection-bias rung below the alpha budget (D207). §8.4 acts on the same cohort that revealed a pattern ("0 promotions in 200+ submissions with param Z above T → tighten Z", confirmed on that very batch) — guaranteed to look good. More importantly, Forge's *consequential* prunes/retargets (D158/159/160 lever scoping, the D191 wf_p25 retarget, the upcoming Q17 stub suppression) are manual operator decisions that never pass through `proposer.py`. Pre-registration records the claim with a cohort cut BEFORE the confirming data exists; confirmation reads only post-cut rows.

**Design (deliberate):**
- **Decision-agnostic registry, not an actuator.** The module stores claims and supplies `confirm_promotion_claim(rows, *, cohort_cut, predicted_max_rate, min_samples)`, whose single job is to structurally drop every row at-or-before the cut — the anti-cheat guard is the tested core. Predicate-matching (which configs a claim is *about*) is the caller's: claims are too varied to generalise, and the operator runs the post-cut query for `resolve`.
- **Git-tracked JSONL** (`config/preregistrations.jsonl`): the prediction is committed before its test, so version control supplies the tamper-evidence. `resolve` rewrites the entry's status (git diff preserves the original).
- **Proposer rewire deliberately deferred.** Changing `propose()` from act-now to register-then-confirm is a behaviour change to the feedback loop and a separate gated step; the standalone registry serves the manual decisions (the majority) now. D206 already retired the main threshold auto-path, lowering the urgency.

**Scope/safety:** Additive, not wired into the production loop → reboot-safe; not deployed (CLI + read/write of a tracked file). New files: `src/forge/feedback/preregistration.py`, `src/forge/cli/prereg_cmd.py`, registered with one `add_typer` line. Tests: `tests/unit/test_feedback/test_preregistration.py` (anti-post-selection guard incl. exactly-at-cut exclusion, registry round-trip) + `tests/unit/test_cli/test_prereg.py` (register/list/resolve, validation). 13 new tests; ruff + mypy --strict clean; CLI+feedback scope 385/0. MANPAGE updated.

**STATUS: shipped (committed, not deployed). Tier-1a (1a-i + 1a-ii) complete; next — champion/challenger model-adoption gate (1c), Q17 stub suppression.**

---

## D209 — 2026-06-25 — Learned-lane drift monitor in `forge healthcheck` (1c, drift half)

**Spec section:** §8.6 (learning clocks); implements LEARNED_SYSTEMS_REVIEW B6 (drift monitoring) and answers B5 (the streak gate is telemetry-only — nothing acts on a FAIL).

**Decision:** Add two learning-drift checks to `forge healthcheck`, one per learned lane (F3 verdict-ranker AUC margin; wf_p25 tail Spearman). They read the same `~/forge_data/ranker_eval/*.jsonl` clocks `forge status` prints (qualifying checkpoints only, no DB) and verdict: CRITICAL if the latest is at/below the anti-predictive floor (the lane is mis-ranking — worse than no model), WARN if it is merely weak (lost its edge over the §6.2 composite) or has dropped sharply from its own trailing median (drift). Surfaced hourly by the existing `forge-healthcheck` timer; CRITICAL marks the unit failed, so a bad model rotation is LOUD instead of silent.

**Why drift-monitor, NOT champion/challenger (the realignment):** audit item 1c proposed a champion/challenger adoption gate to replace blind newest-wins (`ranking/model.py` `load_latest_robustness_model` returns max-by-`trained_through`). But the operator's D192 continuous-training + D193 "HOLD, judge by per-model IC as data grows" stance *intentionally* adopts the newest model as the wf_p25 head matures — a hard champion/challenger gate would FIGHT that design (hold back the improvements it is accruing). The drift monitor is the half of 1c the operator's strategy actually wants: it catches regressions in the continuous path without gating improvements. Whether to add an off-by-default champion/challenger safety to the load path is a genuine model-lifecycle decision flagged for the operator, NOT silently wired.

**Thresholds (conservative, tunable):** F3 floor warn 0.0 / crit -0.05; wf_p25 floor warn 0.0 / crit -0.10; regression delta 0.25 (`--drift-regression-delta`); min-history 4 before the regression check fires. "No qualifying checkpoints yet" is WARN (informational, mirrors "no backup found"), not CRITICAL — a fresh box doesn't cry wolf.

**Verified live:** `forge healthcheck` on the running daemon reports `F3 ranker drift: ok (latest +0.230)` and `wf_p25 drift: ok (latest +0.064)` — both correctly OK (weak-but-positive, not regressing). Same run flagged contracts 1.21.0 un-adopted vs pin 1.20.0 (operator-gated adoption — relayed, not actioned here).

**Scope/safety:** Additive pure check (`check_learning_drift`) + JSONL reader in `cli/healthcheck_cmd.py`; no production-loop or model-adoption change. New test `test_learning_drift_levels`; ruff + mypy --strict clean; CLI scope 89/0. MANPAGE healthcheck section updated (Eight checks). The hourly `forge-healthcheck` timer runs `forge healthcheck` from this editable tree, so the new checks go live on the next tick after commit — no daemon restart.

**STATUS: drift monitor SHIPPED (committed). Champion/challenger adoption gate DEFERRED — flagged to operator as in-tension with D192 continuous training.**

---

## D210 — 2026-06-25 — Q17 closed as STALE — `relative_value` trades fine on the current pool; suppression declined

**Spec section:** §5 (pre-filters), hard rule #1 (don't silently change grammar); lineage Q14 / Q16 / D076 / D098 / D154.

**Decision:** Close Q17 (HIGH, 2026-05-20: "`pairs_zscore`/`expected_value_estimator` >93% zero-trade; `relative_value` non-functional") with NO grammar/filter change. The audit item "Forge-side suppression of zero-trade stub families" is DECLINED — its premise is stale.

**Why (measured):** Q17's 96–98.7% zero-trade was a pre-fix cohort — Crucible's pairs-loading bug (each run reached only 1–5 of 37 pairs; documented in `trade_rate_priors.py`'s `COLD_START_HYPOTHESES` comment), fixed in `4f5271f`. D098 cold-start then deliberately DROPPED that poisoned pre-fix cohort so v5+ is `relative_value`'s first fair test. A live `forge.db` snapshot (2026-06-25, read-only, removed after query) shows the fair test passed: `relative_value` zero-trade is 0.5% on v22 (1/218), 0.0% on v20/v21, ≤2.2% v17–v19 (n≈1000+ each) — now one of the best-trading hypotheses (max_trades 376) and the only `pairs`/cross-sectional diversity source. The highest current-era (v22) zero-rate is `volatility_event` at 10.1%, not `relative_value`. The global zero-trade-waste problem is independently solved (D206: 89% of gated runs trade ≥10).

**Why NOT suppress:** suppressing `relative_value` on the stale evidence would destroy a now-functional, diversity-providing hypothesis for zero gain — a direct "hurt our results" regression (the operator's explicit concern this session). Same stale-evidence shape as the iv_rank stub trap (D154): the root cause was upstream and since-fixed; the open question outlived its facts.

**Action:** `OPEN_QUESTIONS.md` Q17 banner-resolved (RESOLVED/STALE). No code, grammar, filter, or enumeration change → determinism untouched, stream unchanged. Method note: this is the measure-before-acting / pre-registration discipline (D208) in practice — the premise was tested against current data, refuted, and the action declined.

**STATUS: Q17 CLOSED-as-stale. No suppression. `relative_value` confirmed healthy + diversity-valuable on the current pool.**

---

## D211 — 2026-06-25 — Adopt `crucible_contracts` 1.21.0 (premium-R exit family) — validated NO-OP, pin-only

**Spec section:** §13.5 (contracts SemVer pin), hard rule #2; lineage D176 / D200.

**Decision:** Bump `FORGE_EXPECTED_CONTRACT_VERSION` 1.20.0 → 1.21.0 + adopt `uv.lock` (operator already staged the `uv.lock` bump). Operator-directed ("adopt contracts 1.21.0").

**What 1.21.0 adds (contracts `a13b354`, the D333 premium-R exit family):** `KNOWN_EXIT_IDS += delta_floor_stop / premium_r_target / premium_r_time_stop` (18→21); `STOP_LOSS_EXIT_IDS += delta_floor_stop`; `SelectorSpec.stop_atr_mult` (the underlying-R basis).

**Validated NO-OP for Forge (the critical pre-deploy check):**
- **config_hash byte-identical.** `stop_atr_mult` is a None-sentinel DROPPED from `StrategyConfig.config_hash` when unset (mirrors the 1.19.0 rank fields). Forge's sampler never sets it → it drops → no config re-keys. Contracts' golden-hash suite confirms byte-identity; Forge's own full determinism-golden suite confirms it independently.
- **MANDATORY_EXIT_IDS unchanged** → every `tuple(sorted(MANDATORY_EXIT_IDS))` usage + the `e1_mandatory` goldens are unaffected.
- **STOP_LOSS_EXIT_IDS grew by `delta_floor_stop`,** but no Forge config composes it (not enumerated), so the E2 `at_most_two_stop_loss_exits` count is unchanged for every Forge config.
- **KNOWN_EXIT_IDS is not imported by Forge;** the 3 new exit ids are grammar-gated (Forge S3.5 E2, unbuilt) → NOT auto-enumerated. They become a real lever only via a future, separate, operator-gated grammar bump that enumerates them.

**Gate:** FULL suite GREEN — **1723 passed** — with the pin bumped + `uv.lock` at 1.21.0. This empirically confirms the no-op: the pin-match test (`test_contracts_integration.py:56`) flips green and all determinism goldens pass.

**Deploy:** pin + comment + `uv.lock` committed. The running daemon (D206-era process, in-memory 1.20.0) is behaviorally identical under 1.21.0 (no-op); a reboot now starts cleanly (pin 1.21.0 == installed 1.21.0), and the §13.5 startup check + the healthcheck contracts WARN clear on commit. A proactive `forge.service` restart to load 1.21.0 in-memory is the only remaining step and is operator-gated — NOT auto-restarted (operator said "adopt", not "deploy/restart"); behaviorally moot since it is a pure no-op.

**STATUS: contracts 1.21.0 ADOPTED (pin + uv.lock committed, full suite 1723 green, validated no-op). Daemon in-memory restart left as the operator-gated final step (moot — pure no-op).**

---

## D212 — 2026-06-25 — Crucible PBO/dimensionality handoff: worldview shift + orthogonal-family supply scoped (HELD)

**Spec section:** §1.2/§1.3 (producer role — "succeeds when its stream becomes more likely to promote"), §6.2 (learned ranking / hypothesis weights), feedback lineage D103/D105; hard rules 3/4/6. Responds to Crucible `FORGE_decorrelated_supply_for_portfolio_pbo.md` (2026-06-25).

**Decision:** Record the worldview shift and **scope-and-hold** the producer-side response (operator: "scope as a measured proposal," not implement; "draft & hold the writeback"). No code, grammar, config, or determinism change.

**The shift (Crucible production-confirmed):** the edge-MAGNITUDE wall is **cleared at assembly** — assembled books reach WF-median 2.88 / cpcv-p25 1.79–1.95 (the single-config wall, 0/9398 clear 1.5, still holds; book-search assembles past it). The new binding portfolio gate is **PBO 0.578 > 0.4**, root-caused to **effective dimensionality ~1.5** (3 trend + ~4 mr strong components, ~0.78 correlated as bulk factors). This **supersedes** the "binding constraint = edge-MAGNITUDE, unmovable by any producer-side lever" framing and **inverts** the 06-14 `worst-quartile-complement-supply.md` caveat ("complement supply = breadth hygiene, not a promotion unlock") — orthogonal supply now targets the actual gate, and PBO (unlike magnitude) is partially producer-movable in v1 via the orthogonal-family mix.

**Live finding (grounded — 6 consecutive `forge.service` iterations, 2026-06-25):** the prior framing (trend 67% / mr 15% intake) is stale. The stream is **~85% `mean_reversion`** submitted (171/200), `trend_continuation` throttled to ~8% (15–23/200) — the learned loop + the relayed refit-lane prioritization over-corrected. The monoculture moved trend→mr, and mr is half the 0.78-correlated core → no dimensionality gain. The orthogonal families are suppressed: `volatility_event` learned weight 0.074 (lowest active; ~12 submitted), `relative_value` enumerated ~870/batch but ranker-zeroed (0/200) — the `regime_supply` 85%-ranging floor (D144/D150, magnitude-era calibration) crowds it out.

**Mechanism (verified):** no settable family dial — `hypothesis_weights` are learned each iteration from per-hypothesis component-rate (`sampler.py:549-555`; `compute_hypothesis_component_weights`, `rejection_weights.py:619-668`; `main.py:511-605`; D067 5% floor). That estimand is misaligned with PBO (rewards homogeneity). Forge has no return data at generation (D186) → decorrelation owned at assembly → the principled fix needs a Crucible portfolio-contribution signal.

**Rationale:** the one in-scope, positive-EV, no-bar-change producer lever the analysis leaves standing is to **re-aim our own selection so we stop suppressing the orthogonal families PBO needs** — not "more mr" (maxed, wrong axis). Scoped in two layers by gate: Layer 1 (re-aim the estimand to portfolio-contribution; Crucible-gated; connect to the in-flight `portfolio_contribution` relay, do not duplicate) + Layer 2 (bounded structural-diversity adjustment; versionless feedback-change; A/B-flag-OFF→byte-identical; pre-registered via D208 + alpha-budget-charged via D207; later-cohort-confirmed per §8.4; reverted if PBO does not improve). Priority-3 gate-wiring (`iv_term_slope`/`iv_minus_rv` as regime gates) noted as an operator-gated v23 bump with a *fresh* dimensionality rationale (the magnitude rationale was already refuted in `regime-orthogonal-arms.md`), lower priority, and naturally a Path-C-calendar item.

**Alternatives considered:** (a) **implement the reweight now** — rejected; operator chose scope-only, and it trades quality for dimensionality (needs determinism goldens + later-cohort confirmation; the rv-zeroing cause is not yet instrumented). (b) **"boost mr" per the stale framing** — rejected; mr is already 85% and is half the correlated core (zero dimensionality gain). (c) **pursue the Priority-3 grammar bump now** — deferred; operator-gated v23, term-structure gates belong with Path C, and "nearly free" is false (only `iv_rank` is a live gate). (d) **do nothing / treat as v2-only** — rejected; the orthogonal-family suppression is a real, in-scope, measurable producer-side miss worth correcting, contingent on the strong-band measurement (ask 1).

**Action:** authored `docs/proposals/orthogonal-family-supply-for-pbo.md` (proposal of record) + `PROMPT_CRUCIBLE_PBO_ORTHOGONAL_SUPPLY.md` (writeback: corrects Priority-3, sharpens Priority-2, two measurement asks — per-family strong-band counts for vol_event/rv + a portfolio-contribution signal), both **HELD pending operator relay** (`docs/tasks/crucible-handoff.md`). STATUS updated. No production change; docs-only, tree reboot-safe. Measure-first gate stands before any Layer-2 build (strong-band reach, rv-zeroing cause, loop self-correction). Honest cap (hard rule 6): the in-v1 lever narrows but does not close (0.78 trend~mr corr; vol_event single-leg VRP wall); the orthogonal third risk driver is v2/Path C; the 0.4 PBO gate stands — if supply can't reach the strong band, "nothing promotes" is correct.

**STATUS: scope-and-hold. Two docs authored + held. No code/grammar/config/determinism change.**

---

## D213 — 2026-06-25 — Crucible PBO answers (v2-likely) + the decisive in-v1 experiment: 300 cross-sectional relval released to the gate

**Spec section:** §1.2/§1.3 (producer role); §8.4 (pre-registration / post-selection bias); hard rules #2 (contracts write-path), #6/#8 (determinism/seed), #9 (idempotency). Responds to Crucible `FORGE_pbo_orthogonal_supply_answers.md` (2026-06-25), the answer to [[D212]]'s writeback.

**Crucible's answers (read-only census over `runs.duckdb`, 2026-06-25):**
- **Ask 1 — neither orthogonal family gives strong-band CROSS-SECTIONAL supply.** `volatility_event` reaches the band (max **1.514**) but is **100% single-name** (0/757) → structurally excluded from the cross-sectional book, and cross-sectional vol_event is already refuted (needs straddles → v2). `relative_value` is cross-sectional/assemblable but caps at **0.867 across 9,092 decided** (« the 1.3 strong band). The live honest pool (n=32) is cross-sectional-only, two-family (mr 12 / trend 20) — the ~1.5-dim core. **Per our own decision rule, the in-v1 lever is largely exhausted → v2/Path-C** unless current relval is materially stronger than its (bug-era) history.
- **Ask 2 — contribution signal exists, honestly bounded.** `marginal_contribution` shipped (`1926cbb`): returns `marginal_sharpe` + **`correlation_to_incumbent`** (the per-component decorrelation reward our misaligned component-rate estimand needs). NOT marginal-PBO (PBO is a family-level CSCV property, not per-component decomposable). Crucible will publish a daily per-family contribution+correlation map (structural_yield_map analog), **gated on Ask-1 being positive.** Both [[D212]] corrections (Priority-3 registry≠grammar; Priority-2 mr-dominated) accepted.

**Decision (operator: "run the experiment"):** the 0.867 ceiling is **bug-era** (predates the pairs-loading fix, D210/D098); current relval is ranker-zeroed (D145 floor exemption — it competes only in greedy fill and loses on composite score), so its **clean cross-sectional cpcv-p25 ceiling is UNMEASURED**. Crucible named this *the single measurement that decides in-v1 vs v2*, and it is ours to trigger. Released a sample to the gate.

**What was done:**
- **Pre-registered** (`forge prereg`, [[D208]]) prereg **`9b88966c446a`**, cohort_cut 2026-06-25T20:57:47Z: predicted `relval_cross_sectional_cpcv_sharpe_p25_max >= 1.3`. Action-if-confirmed = in-v1 lever alive (un-suppress relval / re-aim weights / relay to push supply); if refuted (caps ~0.867) = commit to v2/Path-C. (`config/preregistrations.jsonl` — NEW file, **commit pending operator** so the prediction is git-durable before the result.)
- **Released 300 cross-sectional (`underlying=None`) v22 `relative_value` configs** to Crucible's inbox via a one-shot script `scratchpad/release_relval_sample.py`. Verified: 300/300 landed in the inbox; all relval, all `underlying=None`, all new (deduped vs 217,989 already-submitted).
- **Hard-rule compliance:** writes ONLY to the inbox via `crucible_contracts.submit_candidate` (rule #2) → **no forge.db write → no lock contention with the running daemon** (the reason `submit_batch` was not used: DuckDB is single-writer and the service holds the lock). Idempotent (rule #9): within-run + best-effort snapshot-dedup of `submissions.config_hash`; `submit_candidate` is content-addressed. Deterministic (rules #6/#8): `SeedHierarchy(seed=20260625)`, `forced_hypothesis="relative_value"`. No battery (D210: current relval is 99.5% trade-viable → an unfiltered sample is a cleaner, unbiased ceiling read + avoids feature-cache wiring). No grammar/gate change.

**Rationale for the design:** a one-shot inbox-write experiment (the D205 flush / `requeue_high_value_configs.py` precedent) over a temporary daemon floor-un-exemption — the latter would need two deploys + restarts touching the production daemon, far more invasive for a measurement. Battery skipped because post-fix relval trades fine and an unbiased sample best measures the ceiling.

**Alternatives considered:** (a) `submit_batch` (forge.db-tracked) — rejected: contends with the daemon's DB write lock. (b) temporary daemon un-suppression of relval — rejected: 2× deploy/restart for a one-shot measurement. (c) run the prefilter battery first — rejected: moot for trade-viable post-fix relval + adds feature-cache contention/complexity; unbiased sample is the better ceiling read. (d) accept v2 now without the experiment — rejected by the operator (exhaust the last in-v1 lever first, per [[exhaust-long-options-before-v2-spreads]]).

**Action / status:** experiment LAUNCHED + verified; daemon + Crucible healthy (`forge healthcheck` OVERALL=OK, submission flowing) → the 300 will be gated over hours-to-days. The prereg resolves when Crucible's per-family census reports the relval cpcv-p25 on the post-cut sample (`forge prereg resolve 9b88966c446a --outcome … --evidence …`). **No production/grammar/determinism change; daemon untouched.** Pending operator: commit `config/preregistrations.jsonl` (+ the held [[D212]] writeback relay, already done — this is its answer).

**STATUS: in-v1 decisive experiment launched (300 relval → gate, prereg 9b88966c446a). Awaiting Crucible's census. v2/Path-C is the standing conclusion if relval caps near 0.867.**

---

## D214 — 2026-06-25 — Cross-sectional `volatility_event` is a 2nd candidate in-v1 lever — D109 exclusion is stale under PBO; clarification relayed, build held

**Spec section:** §1.2/§1.3 (producer role); enumeration policy (`search_space.py` `RANK_COMBINER_HYPOTHESES`); reverses-candidate [[D109]]. Operator-surfaced follow-up to [[D213]] / Crucible `FORGE_pbo_orthogonal_supply_answers.md` Ask 1.

**Trigger:** operator challenged Crucible's "volatility_event is 100% single-name → cross-sectional vol_event refuted → v2," reasoning that a universe-scan ("when a name hits the vol-event entry, trade it") should be expressible cross-sectionally.

**Finding (verified):** the challenge holds. vol_event is excluded from the `cross_sectional_rank` combiner by `RANK_COMBINER_HYPOTHESES = {trend_continuation, mean_reversion, event_momentum}` (`search_space.py:111`; `_cohort_xsect_probability` returns 0.0 for non-members → cross_sectional_rank never drawn → vol_event always gets a named underlying). Set by **[[D109]]** (v11→v12) with the rationale *"vol_event already clears breadth via recurring events"* — a **breadth-era** decision, **stale under the PBO/dimensionality reframe**: a single-name strategy is excluded from the cross-sectional book *regardless of breadth*. So "100% single-name" is Forge's enumeration policy, not a grammar rule or a law of nature — and it's **enumeration-policy-enableable** (add the hypothesis to the frozenset; by the D109 precedent a `grammar_version` bump for cohort-stamping + determinism-goldens + deploy; **no §3.5 rule, no gate change**).

**Why it's a candidate, not a settled v2:** single-name vol_event reaches cpcv-p25 **1.514** and is single-leg *directional* (iv_minus_rv-driven) → a directional vol-event edge demonstrably exists; whether it **generalizes cross-sectionally** has **never been measured here** (0/757). Crucible's "refuted" therefore can't be from Forge data — it's either Crucible's own probe or the **magnitude-vs-direction inference** (vol_event predicts magnitude not direction → cross-sectionally direction washes → straddle → v2). Sound but untested for the directional single-leg form — the exact "reasonable prior" the relval bug-era ceiling taught us to verify.

**Decision (operator: "yes" to draft + fold):** relay a clarification, **hold the build**. Authored `PROMPT_CRUCIBLE_XSECT_VOLEVENT_EVIDENCE.md` (held): asks whether the refutation is a tested probe (show the cpcv-p25 distribution) or the inference, and whether the tested form was directional. Folded into `docs/proposals/orthogonal-family-supply-for-pbo.md` §3b as the second candidate in-v1 lever.

**Alternatives considered:** (a) enable cross-sectional vol_event + test now — rejected: don't open a second enumeration change while the relval experiment is in flight, and the prior is lower than relval (magnitude-vs-direction is real); gate on Crucible's evidence first. (b) accept Crucible's "refuted" and concede to v2 — rejected: it can't be from Forge data (0/757) and the single-name 1.514 shows an edge exists; verify before conceding the whole third-driver question. (c) bypass the grammar to force-submit cross-sectional vol_event — rejected: that would submit configs the enumeration policy doesn't permit (violates the valid-by-construction premise); the legitimate path is the policy change, operator-gated.

**Action / status:** clarification + proposal §3b authored, both HELD. **No code/grammar/enumeration/determinism change.** Build (reverse D109 + release sample) sequenced after (a) Crucible's answer and (b) the relval result ([[D213]]). Honest prior: lower than relval; if Crucible holds decisive sub-band data, concede to v2 with no change.

**STATUS: cross-sectional vol_event scoped as candidate-#2; D109 flagged stale-under-PBO; Crucible evidence ask relayed (held); build held pending answer + relval result.**

## D215 — 2026-06-28 — Generation-levers handoff validated → Crucible concession + §1 correction; v1 KEPT OPEN (the in-v1 GICS-relval lever)

**Spec section:** §1.2/§1.3 (producer role; validate-first); enumeration policy; no §8.x/§3.5 change. Responds to Crucible `FORGE_generation_levers_2026-06-27.md`; round-trips with `FORGE_generation_levers_validation_response_2026-06-28.md`. Builds on [[D212]]/[[D213]]/[[D214]].

**Trigger:** Crucible's generation-levers handoff (3 levers: reallocate single→xsect; add non-OHLCV "Path C" tokens; ingest orthogonal data) with a headline reframe — "the portfolio path has PROMOTED (WF 2.806) → scale supply, not reach the wall once." The handoff itself asked for validate-first. Operator: process at max effort.

**Finding (3 parallel agents + a live measurement, `scratchpad/gen_levers_measure{,2}.py` over the 06-28T11:00Z validated backup ⋈ the gated export):**
- **The reframe is wrong.** Operator: the WF-2.806 book FAILED PBO and did not promote; both `promoted_*` exports are empty. Crucible CONCEDED: the promote *verdict* (5 `runner.portfolio_auto` rows, `470ebae4`/`a2c79f44`) cleared only a by-construction single-book `pbo=0` placeholder; the honest publish filter (`selection_pbo<0.4`) drops it; real CSCV PBO = **0.733**. **PBO binding & unbroken — pre-first-REAL-promotion; D212 stands.**
- **3 stale framings corrected (Crucible conceded all):** (Lever 2) all 11 listed tokens already LIVE+gating in v22 (`iv_rank`… since D031) — "add tokens" is a no-op; (Lever 3) earnings calendar live via `pre_earnings_setup` (D135) — real gap = sector/GICS; ("Path C" mislabel) Path C = structure/spreads, not signal tokens. (Lever 1) single→xsect already live (D182 cohort-yield; ~73% xsect & rising) — the "36% single" was cumulative-historical.
- **My §1 over-read, corrected by Crucible (owned):** I called the admit stream a `rv_rank`-mr-xsect monoculture (eff-dim ~1, citing D212's ~1.5). That was the **~1-day flow** (rolling top-10k ∩ decided≤backup); the standing admit stream is P&L-diverse (participation ratio ≈ **27–39**; full era 41% trend-xsect / 43% mr-xsect / 16% single). "~1.5" (D212's number) is a recipe-COUNT inverse-Herfindahl (1.48), not P&L dimensionality. **Conclusion survives:** redundancy is selection-side (within-MR-selected corr 0.724 vs supply 0.158); diversification doesn't clear PBO (`corr_aware` 1.89→1.38) → binding wall = the **quality×diversity frontier**.

**Decision (operator: "move forward, however I'm not ready to close out v1"):** record the round-trip; **keep v1 OPEN.** The converged ask is "raise the QUALITY of an orthogonal sleeve"; its **in-v1** form is **sector/GICS-relval** (sector-relative cross-sectional value — new DATA + in-paradigm long options, NOT a v2 spread). Plain xsect relval is refuted (0.88-MR-collinear), but sector-NEUTRAL value nets the price/sector factor and is **untried**. Drafted (held) `PROMPT_CRUCIBLE_GICS_RELVAL_INV1.md` asking Crucible to (1) scope/unblock GICS ingest, (2) measure whether sector-relative relval decorrelates from the price core AND reaches the strong band, (3) sketch the Forge-side consumption (a sector token → a v23 grammar consideration, operator-gated). The vol_event flag question ([[D214]], `PROMPT_CRUCIBLE_XSECT_VOLEVENT_EVIDENCE.md`) is the parallel in-v1 thread, still pending Crucible. **v2/Path-C stays the LAST resort** ([[exhaust-long-options-before-v2-spreads]]) — not opened. prereg `9b88966c446a` resolved refuted.

**Alternatives considered:** (a) close v1 → commit to v2/Path-C (the analysis's drift, and the 06-28 sibling block's lean) — REJECTED by operator: the GICS-relval in-v1 sleeve is in-paradigm and untried; exhaust it first. (b) chase the rank-excluded rich gates via a v23 rank-coherence bump — rejected: those gates live in the ~0-yield single-name cohort (measured); and on the corrected §1, the redundancy is selection-side, so this wouldn't move PBO. (c) treat magnitude as the lever (the handoff's claim) — rejected: magnitude buys the single-config center, not the binding PBO/dimensionality gate (Crucible agreed).

**Action / status:** validation writeback drafted, relayed by operator, conceded by Crucible; §1 annotated post-relay; memory `promotion-gate-tiers-and-constraint` folded; STATUS updated. GICS-relval in-v1 ask + this entry pending operator relay/commit. **No code / grammar / enumeration / determinism change; daemon untouched.**

**STATUS: round-trip CONVERGED (Crucible conceded; §1 mechanism corrected to selection-side quality×diversity frontier); v1 KEPT OPEN per operator — in-v1 GICS-relval ask drafted (held); vol_event flag still pending; v2/Path-C not opened.**

**Update 2026-06-28 (cont.) — GICS-relval ANSWERED No (Crucible `FORGE_gics_relval_inv1_2026-06-28.md`); operator chose A+B.** Sector/GICS was already built+tested 06-25 (the "blocked" flag was stale). Sector-neutral `relative_value` does NOT decorrelate (corr-to-MR 0.934→0.797, ~2.6× the 0.30 ceiling) + ZERO orthogonal residual-IC (≈0.000, t≈0) — because their `relative_value` is price-REVERSION, so sector grouping is a different GROUPING of the SAME mechanism → MR-collinear by construction. **Orthogonality needs a different MECHANISM, not a grouping** (my GICS-relval thesis refuted; owned). vol_event flag also answered (`FORGE_xsect_volevent_rank_coherence_2026-06-28.md`): fail-closed (flippable/certifiable) but directionally dead → v2 on edge. **Both in-v1 directional threads close negative on data.** Residual in-v1 surface = ONE front with a real prior: **fundamental value** (within-sector earnings-yield E/P *level* from the existing `financials.parquet`; **value⊥reversion** is the canonical factor split — distinct from the refuted regrouping AND from PEAD's surprise-direction null — but equity-factor-shaped). **Operator chose A+B:** **(A)** drafted `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md` (held) — the residual-IC pre-check, measured-not-asserted, NO Forge build, with a conditional §2 shape-gate (does the orthogonal edge survive long-only net-of-cost as a Forge leg, or route to QuantIQ?); **(B)** hold v1 **OPEN** as a posture — daemon keeps producing current supply, no new build, **v2/Path-C NOT opened.** No code/grammar/enumeration/determinism change.

---

## D216 — 2026-07-01 — Decorrelated supply, deeper (P3): built the Layer-2 orthogonal-family floor-lift (A/B flag, OFF) + relayed the contracts-export gap for the Layer-1 principled estimand

**Spec section:** §4.2/§6.2 (sampler + learned weighting); `docs/tasks/feedback-change.md`; hard rules 1/3/4/6. Builds on [[D212]]/[[D213]] + `docs/proposals/orthogonal-family-supply-for-pbo.md`. Responds to the operator P3 "generate genuinely decorrelated edges — Forge/generation work, not a quick probe."

**Diagnosis (verified live, 2026-07-01 journal + code read):** the learned `hypothesis_weights` estimand is per-hypothesis **component-rate** (`compute_hypothesis_component_weights`, `rejection_weights.py:619`) — it rewards "more of what already clears as a component," the across-book homogeneity PBO penalizes. Live proof: the monoculture **oscillates trend↔mr** (06-25 ~85% mr → 06-29 81% mr → 07-01 **trend=1.000 weight, ~50% submitted**), the two halves of the 0.78-correlated core, while the one Crucible-**validated** in-v1 orthogonal family (single-name `volatility_event`, PC1 load 0.10, book real CSCV PBO 0.107, `FORGE_volsurface_second_factor_RESULT_2026-06-29.md`) sits **pinned at exactly the D067 5% floor (weight 0.050)** — the estimand gives it ~zero organic weight; only the exploration floor keeps ~7% flowing. Reconciles with [[D215]]'s "redundancy is selection-side" (within-MR supply is diverse at 0.158): no selection decorrelates below 0.78 inside the core, so the only generation lever that adds a dimension is the **family mix** — supply more vol_event (the 06-29 winning book was 0→67% ve).

**Decision (operator: "both tracks"):**
- **Track A (Layer-1 principled fix, Crucible-gated):** the correct long-term fix re-aims the estimand from component-rate → **marginal portfolio contribution** (`correlation_to_incumbent` × `marginal_sharpe`). Crucible SHIPPED that signal internally (D213 Ask-2, commit `1926cbb`) but it is **NOT in `crucible_contracts`** (verified: no `marginal_contribution`/`correlation_to_incumbent`/`marginal_sharpe` in the package; the `GatedRun` read path carries no per-component contribution field). Per hard rule #2 that is a **contracts-export gap to surface, not work around** — Forge has no return data at generation ([[D186]]). Drafted (held) `PROMPT_CRUCIBLE_MARGINAL_CONTRIBUTION_EXPORT.md`.
- **Track B (Layer-2 interim, BUILT flag-OFF):** `FORGE_ORTHOGONAL_FAMILY_FLOOR` env knob — a bounded per-family floor-lift layered over the learned weights, applied at the `_load_hypothesis_weights` call site (`main.py`), lifting `volatility_event` off the 5% floor. `apply_orthogonal_family_floor()` (`rejection_weights.py`) + `_orthogonal_family_floors()` env parser. **OFF by default → byte-identical (hard rule 6):** empty map → the block is skipped, the enumeration sequence is unchanged (invariant `tests/invariants/test_orthogonal_family_floor_invariants.py`; determinism goldens intact). Manual check: `volatility_event=0.20` lifts vol_event's sampling share 2.9%→10.7% while trend eases 58%→54% — starves nothing (`max` semantics; every other family keeps its D067 budget). Only ever RAISES a named family (never lowers → no gate/loosening implication, hard rules 3/4).

**Alternatives considered:** (a) restructure `_load_hypothesis_weights` to fold the lift inside — rejected: ~10 test files monkeypatch that function (D065/D105/D106); wrap at the call site instead. (b) a CLI flag like `--quality-rank` (D193) — deferred to an env knob (no Typer plumbing through the monkeypatch-sensitive signature; matches `FORGE_QUALITY_RANKER`). (c) also lift `relative_value` (the 06-25 proposal's second target) — dropped: relval is REFUTED (0.88-MR-collinear, [[D215]]); vol_event is the sole validated orthogonal family. (d) ship Track B enabled — rejected: activation is an operator-gated deploy, pre-registered (D208) + alpha-budget-charged (D207) + later-cohort-confirmed (§8.4).

**Action / status:** Track A relay drafted (held, awaiting operator relay). Track B built + tested (10 new tests; affected scope 764 green; ruff + mypy clean on changed files; tree importable → reboot-safe since flag-OFF is behavior-neutral). **Daemon UNTOUCHED — no restart, flag not set.** Activation (set `FORGE_ORTHOGONAL_FAMILY_FLOOR` on `forge.service`) is the operator-gated deploy step: prereg the prediction ("lifting vol_event's share raises book dimensionality / lowers PBO"), charge the alpha budget, confirm on a later cohort, revert (drop the env) if PBO doesn't improve. Full uncontended suite + `docs/tasks/deploy.md` at deploy-prep time. **No grammar/gate/determinism change.**

**STATUS: P3 both-tracks — Layer-1 contracts-gap relay drafted (held); Layer-2 vol_event floor-lift BUILT flag-OFF (byte-identical), activation operator-gated. Honest ceiling unchanged (in-v1 narrows via the validated vol_event family; the third RISK driver is still v2).**

**Update 2026-07-01 (cont.) — Crucible DELIVERED the signal same-day (`FORGE_marginal_contribution_export_status.md`, commit `a7228f9`); operator chose loader→contracts + hold-the-re-aim.** Correction accepted (owned): `marginal_contribution` was **probe-only** (never in the live path), so exposing it was a small BUILD, not a read-side unblock — my "computed but not consumable" framing was wrong. Crucible shipped it as a **separate export** (`~/optbt_data/exports/component_contributions_<iso>.json`, schema `component_contributions/v1`, `{config_hash: {portfolio_id, correlation_to_incumbent, marginal_sharpe}}`, leave-one-out per promoted portfolio) — NO contracts model bump (they took the "new helper" option). **Verified live:** the publisher is running, export present but **`n_contributions: 0`** (empty) — exactly Crucible's caveat: the signal is **promotion-gated** and populates only as books promote. Corroboration: Crucible's honest-pool eff-N ≈ 6.5 / mr ~1.78 = the generation monoculture seen selection-side. **Two operator decisions:** **(1) loader → contracts** — per rule #2 + the established pattern (every export reader lives in `crucible_contracts`); a read-*helper*+schema-constant is NOT the model bump Crucible rightly avoided. Drafted (held) `PROMPT_CRUCIBLE_CONTRIB_LOADER_IN_CONTRACTS.md`. **(2) HOLD the Layer-1 estimand re-aim** — the export is empty (0 entries), so flipping the core learned estimand against a null signal is unvalidatable; build+flip once it carries real promoted-book data. Layer-2 (`FORGE_ORTHOGONAL_FAMILY_FLOOR`) carries supply meanwhile (Crucible concurs: "your interim can keep covering `volatility_event` until you cut over"). **Built now (cheap, no re-aim):** a **soft `forge healthcheck` line** for the `component_contributions` export — `check_component_contributions_export` (OK-when-absent, since absence is expected pre-promotion → never pollutes OVERALL; glob+mtime only, no typed read → doesn't pre-empt the contracts loader); TDD, healthcheck suite green, ruff+mypy clean; live `forge healthcheck` renders `[OK] component_contributions: present (0.2h old)`, OVERALL=OK. **Daemon UNTOUCHED. No grammar/gate/determinism change.** Sequenced next (post-contracts-loader + post-first-promotion): build the loader-consumer + the held estimand re-aim, flag-OFF, validated on real data as it populates.

**Update 2026-07-01 (cont. 2) — Crucible AGREED loader→contracts + shipped it (`FORGE_marginal_contribution_export_status.md` UPDATE; contracts `afbe737` = 1.22.0); Forge ADOPTED (pin-only).** The rule-#2 posture won: `crucible_contracts` **1.22.0** now hosts `load_component_contributions_from_export(exports_dir) -> dict[str, ComponentContribution]` + `ComponentContribution` (frozen: portfolio_id, correlation_to_incumbent, marginal_sharpe — **`marginal_sharpe` may be NEGATIVE, don't clamp**) + `COMPONENT_CONTRIBUTIONS_SCHEMA`. Cold-start `{}` on absent/empty/**unknown-schema** (a deliberate divergence from the other loaders — graceful version-skew for a learned-estimand input; only corrupt JSON raises QueryError). Verified importable + returns `{}` on the live empty export. **Adopted:** `FORGE_EXPECTED_CONTRACT_VERSION` 1.21.0→**1.22.0** (pin-match test green). **NO-OP** (additive; nothing in Forge imports the loader yet — the consumer + re-aim are HELD). **uv.lock UNCHANGED at 1.21.0** — Crucible bumped `_version.py` (`CONTRACT_VERSION`, the identity Forge validates) but NOT `crucible_contracts/pyproject.toml` (`version` still 1.21.0), so `uv lock` (reads pyproject) can't record 1.22.0; cosmetic for an editable path dep, but Crucible should bump pyproject to match `_version.py`. **Suite:** 1559 unit + 185 invariants/integration GREEN; the ONE failure (`test_every_command_is_mentioned_in_manpage` → `forge ranker-model eval-rewire`) is **pre-existing at HEAD** — the operator's committed gate-then-tail re-wire command lacks a MANPAGE row; independent of this work. **Daemon UNTOUCHED; commit + `forge.service` restart operator-gated** (the running daemon is 1.22.0-in-memory via the editable dep already; the pin bump just aligns the startup guard + healthcheck).

**Update 2026-07-01 (cont. 3) — 1.22.0 PUSHED + `forge check` OK; Crucible wired the SELECTION-side mirror (default-OFF); worldview sharpened to a magnitude×PBO TRADE-OFF (`FORGE_selection_robustness_and_contracts_1_22_0.md`, Crucible `a922f5f`/`73d7c2c`).** **(1)** `crucible_contracts` 1.22.0 pushed to origin/master (also published the finalized 1.21.0); `forge check` → `crucible_contracts: 1.22.0 OK` + schema OK. Crucible confirms **D124 non-issue** (1.22.0 adds a NEW model + NEW export file, changes no existing parsed model → no `extra_forbidden` fail-loop → no pre-restart sequencing). **uv.lock STILL 1.21.0** — re-verified: `crucible_contracts/pyproject.toml` `version` is still 1.21.0 (only `_version.py` bumped), so `uv lock` can't record 1.22.0; re-flag Crucible to bump pyproject. **(2) Crucible wired the selection-side of decorrelation, default-OFF/byte-identical (§20):** `cluster_preselect` (collapse corr≥0.6 near-dupes to one top-quality rep BEFORE selection — the assembly-side analogue of Forge's generation-side orthogonal-family rebalance) + `shrinkage` (de-noise the per-path IS-best pick). No gate change today; flipping either is a separate operator-gated activation. **Interaction caveat:** if Crucible dedups near-dup MR at assembly AND Forge rebalances supply away from the MR monoculture at generation, the two COMPOUND — don't attribute a future PBO shift entirely to one side. **(3) WORLDVIEW SHARPENED — magnitude and PBO TRADE OFF in the current pool:** on Crucible's best HONEST book, PBO is already **0.067** (NOT binding; shrinkage→0.0, dedup 12→5 reps→0.0) but the book stays REJECTED on **edge MAGNITUDE** (selected cpcv-p25 ≈ **1.0**, maxDD −0.12). Reconciles D212's "cpcv-p25 1.79–1.95 books" (those were the OVERFIT high-PBO ones; the anti-overfit hygiene that drops PBO to ~0 also drops honest magnitude to ~1.0). So the wall is neither "magnitude cleared, PBO binding" (D212) nor "PBO binding" alone — it is the **joint strong-AND-decorrelated frontier**: the current supply can't give BOTH. The ONLY lever both sides agree on = **more STRONG, decorrelated supply** (Forge's single-name vol_event = the decorrelated part; magnitude is the harder half). Tempers the 06-29 "first promotable book" (that was an n=8 PBO-only read; magnitude still short). **No new Forge action from this handoff beyond the completed adoption; re-aim + Layer-2 activation posture unchanged (both HELD/operator-gated).**

**Update 2026-07-01 (cont. 4) — GAPS CLOSED (operator: "close gaps").** **(1) uv.lock consistency:** root-caused to the contracts pyproject/`_version.py` mismatch — bumped `../crucible_contracts/pyproject.toml` `version` 1.21.0→**1.22.0** to match `_version.py`; `uv lock --refresh-package crucible-contracts` now records **crucible-contracts 1.22.0** (uv.lock updated); `forge check` → 1.22.0 OK. The contracts-repo pyproject edit is **uncommitted** — operator commits/pushes it in `crucible_contracts` per their release process (a one-line durability fix so a clean checkout doesn't re-break the lock). **(2) eval-rewire MANPAGE gap:** documented `forge ranker-model eval-rewire` (the operator's gate-then-tail re-wire telemetry command — §8.6, `--forge-db/--config/--since/--gate/--p-floor`) in `docs/MANPAGE.md` → `test_every_command_is_mentioned_in_manpage` GREEN → **full suite GREEN (1559 unit + 186 invariants/integration).** **(3) Relay housekeeping:** marked the two now-answered relays RESOLVED (`PROMPT_CRUCIBLE_MARGINAL_CONTRIBUTION_EXPORT.md`, `PROMPT_CRUCIBLE_CONTRIB_LOADER_IN_CONTRACTS.md`) so neither reads as a pending ask. **No held/operator-gated lever was flipped** — Layer-2 activation + the Layer-1 re-aim remain HELD by design (awaiting an operator deploy / export density). Daemon untouched; nothing committed in Forge.

**Update 2026-07-02 — Track B ACTIVATED (production deploy; operator: "activate Layer-2, deploy call, to chase the first promotion" + "commit and push the tree" + floor 0.20).** `Environment=FORGE_ORTHOGONAL_FAMILY_FLOOR=volatility_event=0.20` set on `deploy/systemd/forge.service` (committed → reboot-safe); daemon restarted via `docs/tasks/deploy.md` (single-folder in-tree, D104). Gate: full uncontended suite **1745 passed** on build commit `ce83584` (fixed 4 pre-existing `E501`s in `contracts_check.py`'s 1.22.0 comment block so the pre-commit hook passed — no behavior change). Ritual: stop 22:28:44Z (exit 143, normal `--loop` SIGTERM) → commit build → commit activation → restart. **Prereg (D208) `5c4ba16ff6cf`** (cohort_cut 2026-07-02T05:31:30Z): claim = the added decorrelated vol_event supply improves the assemblable book (CSCV PBO ≤0.40 + positive `volatility_event` marginal contribution) on post-cut data; action = make the floor standing if confirmed, else drop the env (byte-identical OFF). **Alpha-budget (D207) hurdle at activation: v22 = 4.38 (submitted) / 5.04 (enumerated) search-luck Sharpe.** **Caveat (cont. 3 magnitude×PBO):** PBO is NOT the binding wall now (best honest book 0.067) — the wall is edge MAGNITUDE (selected cpcv-p25 ~1.0); Layer-2 supplies the DECORRELATED half only (necessary, not sufficient), and must NOT be double-counted against Crucible's default-OFF `cluster_preselect` (they COMPOUND). **Layer-1 estimand re-aim stays HELD** (export still empty until the first promotion). REVERT = delete the env line + restart → byte-identical (hard rule 6). External warrant for the lever: the vol-event cross-sectional research verdict (`VOL_EVENT_CROSS_SECTIONAL_RESEARCH.md`) — single-name vol_event is the idiosyncratic/orthogonal supply; "cross-sectional" belongs at assembly, not generation.

## D217 — 2026-07-01 — Gate-then-tail quality-lane re-wire — retroactive record of the 2026-06-26 scorer (flag-OFF, `FORGE_QUALITY_RANK_MODE`)

**Spec section:** §6.2 (verdict_scorer prior) / §8.6 (shadow streak). Design: `docs/proposals/quality-lane-rewire.md`. Backfills the D-entry for commits `edb03e6`, `fdeed29`, `92e9061`, `ceeefa4` (2026-06-26), deferred at the time ("concurrent edits in IMPLEMENTATION_DECISIONS.md") and never written (learned-audit P0.2). Records only — the deployed lane ([[D193]]) is unchanged (default mode `blend`).

**Motivation — the 06-26 A/B.** The deployed wf_p25 quality lane blends `prior := P(component) × tail_norm` ([[D193]]). An offline A/B (2026-06-26) found that blend is a measured **no-op**: production `P(component)` (i) *anti-correlates* with the realized WF floor and (ii) dominates the product (~0.97-Spearman-identical to P alone), so the wf_p25 head's real signal is wasted — multiplying by a term that fights the target throws it away.

**The fix — two-part form `E[wf_p25 | clears]`.** `P(component)` **GATES eligibility**; the wf_p25 tail prediction **ORDERS** the survivors; P never enters the ordering score. `gate_tail_prior(p, tail_pred, p_floor)` (`ranking/model.py`) → `tail_norm` for eligible (P ≥ floor), `0.0` for gated-out. The shadow's `_rewire_topk` reuses the same `eligibility_floor` so it gates identically to production.

**Flags / defaults — all flag-OFF, byte-identical unset (hard rule 6):**
- `FORGE_QUALITY_RANK_MODE` = `blend` (default = D193 deployed) | `gate-tail` (the re-wire). `main.py` quality block dispatches. Parse now degrade-never-crash-guarded (`6f44d86`, learned-audit P0.3).
- `FORGE_REWIRE_P_FLOOR` = absolute P(component) eligibility floor, default `0.02`.

**Floor calibration (`ceeefa4`).** The initial gate was an in-batch P-quantile (`FORGE_REWIRE_KEEP_FRAC=0.5`). Calibration against the live registry + F3 model found production P is extremely skewed (enumerated median **~0.0004**), so keep_frac=0.5 floored at ~0.0004 — ~311× below the shadow's 0.136 and effectively a no-op gate (≈ tail-alone). Switched production + shadow to an **absolute** `FORGE_REWIRE_P_FLOOR` (0.02 → keeps the top ~8% by P), dropping the in-batch scan.

**Shadow evidence (accruing).** `forge ranker-model eval-rewire` prints gate-then-tail vs P-baseline top-K mean realized `wf_sharpe_p25`; `daily_ranker_eval.sh` appends a fresh-window Δ to `rewire_streak_wfp25.jsonl`, surfaced in `forge status` as the "re-wire gate-tail" clock. `_REWIRE_DELTA_CRITERION = 0.05` (PROVISIONAL) gates PASS; raw Δ recorded for re-judging. Latest (06-26): recent-window Δ **+0.19**, full-pool Δ **+0.03** (the first record FAILs on the full-pool window and climbs as recent windows accrue — same shape as the wf_p25 tail streak).

**Honest limit / flip gate.** The shadow cannot validate the gate's exclusion of low-P *passed* configs (censoring), so a flip is a **watched** experiment, not a proven win. The learned-audit (P1.1) additionally flags a shadow-vs-production fidelity note (the shadow ranks purely by the gate-tail score; in production the gate-tail prior enters the §6.2 composite at the prior's weight) — close that parity gap before flipping. Flip = set `FORGE_QUALITY_RANK_MODE=gate-tail` on `forge.service` (operator-gated deploy): prereg the Δ (D208), charge the alpha budget (D207), later-cohort-confirm (§8.4). REVERT = drop the env → byte-identical.

**STATUS: retroactive record only — no code/behavior change from this D-entry. The gate-then-tail scorer is BUILT + shadow-accruing, flag-OFF (default `blend` = D193 deployed); the flip is operator-gated on the streak. Related P0 hardening this session: env parse guarded (`6f44d86`), floor call-site integration tests (`a075147`), eval-robustness gate label fixed (`73d6637`).**

## D218 — 2026-07-02 — Disarm §5.5 auto-tune before first promotions (strategy-audit P0-1)

**Spec section:** §5.5 (auto-tune); hard rule #4 (this DISARMS an auto-loosen-capable path — safe direction); `docs/tasks/feedback-change.md`. Operator-approved (fable-audit review: "disarm now").

**Why.** `feedback/auto_tune.py` self-applies threshold TIGHTENINGS to the tracked `config/prefilter.yaml` (and writes loosen PROPOSALS to `OPEN_PROPOSALS.md`) when the rolling 2-batch **promotion rate** leaves the [0.5%, 5%] band. That estimand is **per-config verdict-level promotion** — a **dead signal under book-level promotion** ([[D212]]–[[D216]]: promotion is a portfolio/PBO property, not a per-config rate). Worse, the trigger becomes **reachable for the first time the day the first book promotes** — which the D216 activation is actively chasing — likely at **tiny denominators** (a 1/2 early promote reads as 50% ≫ 5% → an unattended tighten of the live prefilter). It is the only unattended tracked-file write path in the system (strategy-audit MET-H3/P0-1).

**Change.** `config/prefilter.yaml` `auto_tune.enabled: true → false`. `auto_tune()` short-circuits on `not calibration.auto_tune.enabled` (`auto_tune.py:271`) → no tighten write, no loosen proposal. prefilter.yaml is **hot-read each feedback cycle** (`main.py:1620` `load_calibration`), so the disarm takes effect on the next cycle — **no restart**. Guard test `test_auto_tune_disabled_does_not_fire_even_above_max` (promote-rate 6–7% + enabled=False → calibration unchanged, yaml byte-identical, no `OPEN_PROPOSALS` write); the `test_calibration.py` production-config pin updated to `enabled is False`.

**Not a loosening (hard rule #4).** Disabling auto-tune removes both an auto-**loosen**-proposal path and an auto-**tighten** path; it relaxes nothing at the gate (rule #3 untouched) and touches no grammar (no version bump). Re-arm = flip to `true` once the estimand is re-keyed to a book-level / marginal-contribution signal (the Track-A re-aim, [[D216]], still HELD on the empty `component_contributions` export).

**STATUS: §5.5 auto-tune DISARMED (config, hot-read, no restart). No grammar/gate/determinism change. Re-key + re-arm deferred to the Layer-1 estimand work.**

## D219 — 2026-07-02 — Stop writing per-row REJECTED `pre_filter_logs` (pipeline-perf P0-1)

**Spec section:** §9.1 (`pre_filter_logs`); `docs/tasks/feedback-change.md`; hard rule #6 (enumeration untouched). Operator-approved (fable-audit review: "recommended is good" — stop-writing over the CSV-rewrite alternative).

**Why.** The submit phase fsynced **~31k rejected-config rows/batch** into `pre_filter_logs` via `db.executemany` (duckdb autocommits + WAL-fsyncs every row) — **~190s of the ~197s submit phase** (pipeline-perf audit F1), plus ~200MB/day DB growth (F7/F8). The table has **zero live readers** (verified: no `SELECT … FROM pre_filter_logs` in `src/` or `scripts/`), and the same pass/reject breakdown already lives in `batch_summaries.prefilter_rejections{,_by_hypothesis}` (the D062/D064 aggregates, written on the same submit pass) plus the new `battery_survival_by_hypothesis` journal line (strategy P0-2, `c365d14`). So the per-row rejected telemetry is redundant AND the pipeline's single largest fsync cost.

**Change.** Removed `record_pre_filter_logs_for_rejected` (function + its `main.py` call site, the `forge.submission` re-export, and its 7 unit tests). The SURVIVOR-path writer (`record_pre_filter_logs`, ~200 candidates/batch) is unchanged — small, not the fsync problem, still carrying `config_hash`/`forge_batch_id` for join-back. `pre_filter_logs` is survivor-only again; the D076/Q16 "misleading 100% pass rate" concern is moot (nothing reads the table). No enumeration/gate/grammar change.

**Alternative considered + rejected.** The CSV bulk-staging rewrite (temp-CSV + `read_csv`, ~190s → ~6s) keeps the per-row telemetry but carries real byte-equality risk (timestamp/quoting coercion) for data nothing reads — worse effort/risk for no reader benefit. Stop-writing is smaller, safer, AND kills the growth.

**Retention.** Existing rejected rows (GBs already written) remain until a one-time offline compaction (DuckDB doesn't shrink on DELETE) — the P1-2 follow-up, an operator-scheduled deploy-window op; this only stops FUTURE growth.

**STATUS: per-row rejected `pre_filter_logs` write REMOVED — ~190s off the submit phase + ~95% of the table's growth. Survivor write + all `batch_summaries` aggregates intact. Takes effect at the P0-2/P0-3/P0-1 deploy. No enumeration/gate/grammar/determinism change.**

## D220 — 2026-07-02 — Prior-weight A/B: the 0.10 composite prior slot ranks components BELOW random (learned P1.4/B2)

**Spec section:** §6.2 (ranker composite) / §10.3 (weights); `config/ranker.yaml`. fable-audit learned-systems P1.4/B2. Built `evaluate_prior_weight_ab` + `forge ranker-model eval-prior-weight` (`cbdb232`) — an OFFLINE A/B re-scoring the submitted shadow rows under alternate composite prior weights (holding the four hygiene terms' relative proportions).

**Finding (live snapshot, n=131,187 decided verdicts / 6,326 components):**

| prior weight | precision@K (K=6326) | AUC |
|---|---|---|
| **0.10 (deployed)** | **0.032** | **0.488** |
| 0.30 | 0.164 | 0.703 |
| 0.50 | 0.197 | 0.809 |
| 0.70 | 0.208 | 0.832 |
| 1.00 (pure P) | 0.214 | 0.838 |

The deployed composite (prior at 0.10) ranks realized components at precision@K **0.032 — BELOW the 4.8% base rate** (AUC 0.488 ≈ slightly ANTI-correlated). The four hygiene terms (signal_density 0.30, novelty 0.25, regime_diversity 0.20, permutation_test 0.15 = 0.90 of the weight) are ~coin-flip-to-anti vs realized promotion and DROWN the learned F3 prior, which alone (w=1.0) separates components at AUC **0.838**. Independently corroborates the June-review B2 (incumbent composite ~0.45–0.53 AUC) at n=131k. The gain is steep to 0.30 (5× precision) and plateaus ~0.5–0.7.

**Recommendation (GATED — not applied).** Raise `prior_promotion_proximity` from 0.10 toward **~0.50** (renormalizing the other four to 0.50 total) — captures AUC 0.488→0.809 while retaining half the hygiene weight. Variety is NOT at risk: the diversifier (D103/D136 greedy-Jaccard + min-per-hypothesis floors) enforces family spread SEPARATELY, post-ranking. **Caveat:** this A/B is CENSORED (only submitted configs carry verdicts) → it measures re-ranking quality WITHIN the submitted set, not the counterfactual of what a prior-heavy weight would NEWLY submit; the magnitude (ΔAUC +0.32) makes the direction unambiguous, but confirm the winner on a live shadow lane + prereg the realized-component-yield prediction before the `ranker.yaml` change + deploy (ranking-policy change → operator-gated).

**STATUS: prior-weight A/B eval BUILT + measured (0.10 is a coin flip; pure-P is AUC 0.838). The `ranker.yaml` raise to ~0.50 is RECOMMENDED but operator-gated (prereg + deploy). No ranker behavior change from this D-entry — the eval is telemetry.**

**Update 2026-07-02 — APPLIED (operator: "raise to 0.50 now").** `config/ranker.yaml` `prior_promotion_proximity` **0.10 → 0.50** (hygiene renormalized: signal_density 0.30→0.17, novelty 0.25→0.14, regime_diversity 0.20→0.11, permutation_test 0.15→0.08; sum 1.0, loads+validates). **Prereg `b7ecc2d2e96f`** (cohort_cut 2026-07-02T08:02:09Z; metric `promotion_rate`, predicted ≥0.06 vs the ~0.048 pre-cut baseline; action: keep if the post-cut component-rate rises, else revert). Deployed via `docs/tasks/deploy.md` (restart #3 today; ranker.yaml is hot-read per-iteration + the restart makes it clean). REVERT = restore the 0.30/0.25/0.20/0.15/0.10 set + restart (byte-identical ranking). Ranking-policy change; **no grammar/gate/determinism change.** Honest caveat carried from the A/B: the offline signal is censored (within submitted set) → the later-cohort component-rate is the real test.

**Update 2026-07-02 — prereg `b7ecc2d2e96f` EARLY READ (+8.5h post-cut; strong, HELD OPEN).** Realized component-rate (`decision IN component,promote`) by `submitted_at`: **post-cut 0.1174 vs recent pre-cut windows 0.056–0.090** (all cleared) — prediction ≥0.06 holds. Sample is near-complete (7,314 of 7,400 post-cut submissions decided; not lag-censored). Confounder controls: (1) the D216 vol_event floor is **ruled out** (its component-rate ~0.002, share stable ~0.07); (2) **Kitagawa decomposition of the +0.0391 lift → rate effect (within-family ranker skill) +0.0283 (72%), mix effect +0.0109 (28%)** — within-family rates rose in BOTH cores (trend 0.121→0.164, mr 0.045→0.060), NOT explainable by the trend↔mr oscillation. Even discounting the entire mix effect, the residual → ~0.106 » 0.06. **NOT resolved** (disciplined: 8.5h is one partial window; re-run the decomposition ≥2026-07-04T08Z to confirm across a full oscillation cycle before the keep-vs-revert call). 0.50 stays live.

---

## D221 — 2026-07-02 — Calibrate P(component): floor-relevant ECE criterion + eligible-fraction monitor (learned P1.3/B3)

**Spec section:** §6.2 (P fills the prior slot) / §8.6 (gate-then-tail floor reads absolute P); fable-audit learned-systems P1.3/B3. The F3 `score_features` returns a raw logistic P that recent artifacts over-predict ~3-5× above p≈0.3 (audit §1: bin [0.4,0.5) mean 0.44 vs realized 0.099), with drift across artifacts. Harmless for RANKING (AUC is monotone-invariant, the blend's consumption) but wrong for the ABSOLUTE gate-then-tail eligibility floor, which reads P on its own scale.

**Decision.** Ship calibration as MEASUREMENT + a co-primary criterion + a keep-rate monitor, WITHOUT touching the live score path. Four commits:
1. `forge/ranking/calibration.py` (`20603f0`) — pure, dependency-free, deterministic: `reliability_table`, `expected_calibration_error` (ECE), `brier_decomposition` (Murphy), and a Platt `(a,b)` recalibrator reusing the verdict model's Newton-IRLS. 14 tests.
2. `evaluate_shadow`/`ShadowEvaluation` (`cc844c2`) gain `model_ece` (overall), **`model_max_ce`** (max calibration gap over bins with ≥20 rows — **the floor-relevant measure**), `model_ece_platt` (held-out Platt ECE — the reachable floor). Centralized `shadow_auc_verdict` + new `shadow_calibration_verdict` (`max_ce ≤ 0.20`). `forge ranker-model eval` + the daily timer print + JSONL-track both. 6 tests.
3. `RewireEvaluation.eligible_fraction` (`d255e4e`) — the fraction clearing the absolute floor (the gate-tail KEEP-RATE) in `eval-rewire` + the rewire streak JSONL. 2 tests.
4. `forge status` (`2ec6d51`) — a `P calibration/floor` drift-guard line (latest calibration verdict + `max_ce` + keep-rate). 2 tests.

**Rationale.** (a) **Why max_ce, not overall ECE:** the P distribution's mass sits in well-calibrated low-P bins (median ~0.0004), so a frequency-weighted overall ECE is toothless (live dominant model 0.0176) even while the high-P sliver the floor SELECTS runs 3-5× off — max_ce over populated bins captures exactly that (live 0.356 → calibration FAIL). (b) **Why two separate verdicts:** AUC blesses the model for the blend's RANKING; calibration blesses P for the floor's ABSOLUTE read — a well-ranking-but-miscalibrated model must not be failed for ranking, so they are kept distinct (the plan's "co-primary" = both gate, for their respective consumptions). (c) **Why measurement-only now:** recalibrating the P that fills the §6.2 prior slot would change the composite SUM's sort → confound the in-flight D220 prior-weight prereg; and the floor `FORGE_REWIRE_P_FLOOR=0.02` is on the raw-P scale, so re-deriving it is inseparable from applying the recalibrator (P1.1). The base model fit is **byte-identical** (same coefficients → same live P → live ranking unchanged, hard rule #6).

**Alternatives considered:** (1) apply the Platt recalibrator to live P now — REJECTED (confounds the D220 prereg + couples to the floor re-derivation); (2) a hard co-primary that flips the F3 AUC streak on miscalibration — REJECTED (conflates two consumptions; the AUC streak is operator-trusted); (3) overall-ECE criterion — REJECTED (toothless under the mass concentration).

**STATUS: P1.3 SHIPPED (4 commits, 24 tests). Telemetry only — gates no live behavior; daemon untouched; flag-OFF/base-fit byte-identical.** Live snapshot: dominant model AUC PASS + calibration FAIL (max_ce 0.356, ece_platt 0.006 → the miscalibration is RECOVERABLE), keep-rate 0.9869 at floor 0.02. **Deferred to P1.1:** persist the held-out `(a,b)` in the artifact + re-derive the gate-tail floor on the calibrated scale + wire calibrated-P into the gate-tail lane (all operator-gated at flip).

---

## D222 — 2026-07-02 — Gate-tail mode hard-gates at queue level, matching the shadow streak (learned P1.1)

**Spec section:** §6.2 / §8.6 (gate-then-tail); `docs/proposals/quality-lane-rewire.md`. fable-audit learned-systems P1.1, defect 1.

**The gap.** The `rewire_streak_wfp25` shadow validates the HARD-gate form `gate_tail_rank_score` (below-floor configs demoted by 1e9 → strictly beneath every eligible one; offline A/B Δ **+0.180**, CI [+0.060, +0.309], E-3). But production's `gate-tail` mode wired `gate_tail_prior` into the §6.2 composite SLOT (weight 0.50) — a SOFT gate: the composite is `0.50·prior + 0.50·hygiene`, so a below-floor config (prior 0.0) with strong hygiene can outrank an eligible one. Flipping `FORGE_QUALITY_RANK_MODE=gate-tail` would have shipped an intervention the evidence never measured.

**Decision (option A — make production match the shadow).** `rank_batch` gains `gate_tail_ordering: bool`; in `gate-tail` mode the composite **IS** the `gate_tail_prior` value (the §6.2 hygiene blend is BYPASSED): `composite = prior if gate_tail_ordering else ranker.score(report, prior)`. `gate_tail_prior` returns `tail_norm` for eligibles and **0.0** for ineligibles — and 0.0 is a fixed point of the diversifier's `score·(1-penalty)` multiply, so ineligibles can never be lifted above an eligible config (the hard gate survives §6.3 diversification, without needing the shadow's out-of-range −1e9 that would violate `RankedCandidate`'s [0,1] invariant). Eligibles order by `tail_norm`, which is monotone in the raw tail prediction the shadow ranks by → **identical order**. `main.py` sets `gate_tail_ordering=True` only in the gate-tail branch.

**Why this is faithful + safe.** Shadow and production consume the SAME F3 P model, the SAME `target_wf_p25` robustness model, and the SAME floor (`FORGE_REWIRE_P_FLOOR`, default 0.02 — the timer's rewire heredoc reads the identical env/default) → parity holds by construction. Flag-OFF (`blend`/unset, the live state) → `composite = ranker.score`, **byte-identical** (invariants + 396 tests green). A parity test asserts production's order == the shadow's `gate_tail_rank_score` order for the same (P, tail); a byte-identical test pins the blend path.

**Alternatives considered:** (1) store `gate_tail_rank_score` (−1e9) as the composite — REJECTED (violates the [0,1] invariant + inverts the diversifier's multiplicative penalty on negatives); (2) drop ineligibles from the pool before selection — a stricter hard gate but changes batch size and diverges from the shadow's <K-eligible fill; the 0.0-fixed-point approach is simpler and diversification-proof (eligible fraction ~0.99 makes the <K edge moot); (3) option B (make the shadow match production's soft blend) — REJECTED per the plan (just re-discovers §5, the muted 0.10 slot).

**STATUS: P1.1 fidelity fix SHIPPED (`d159b2d`, 2 tests). Flag-OFF byte-identical; gate-tail mode is NOT live (`FORGE_QUALITY_RANK_MODE` unset → blend). Daemon untouched.** REMAINING (the P1.1×P1.3 intersection, deferred to the flip): persist the P1.3 held-out `(a,b)` recalibrator in the artifact + re-derive `FORGE_REWIRE_P_FLOOR` on the calibrated P scale + switch both shadow and production to calibrated P together. That is a coupled change best done atomically at the operator flip (gated on P1.2's clean rewire streak); doing it now would add artifact-schema/determinism churn for a consumption that isn't live. **Operator-deploy note:** keep `FORGE_REWIRE_P_FLOOR` identical on `forge.service` and `forge-ranker-eval` or shadow≠production.

---

## D223 — 2026-07-02 — Numeric gate-tail flip gate + clean rewire streak; flip prediction pre-registered (learned P1.2)

**Spec section:** §8.6; `docs/proposals/quality-lane-rewire.md`. fable-audit learned-systems P1.2 (defect: the streak's first record is a contaminated full-pool "look"; "3 consecutive" alone has 12.5% null false-promotion, B5).

**Decision.** (1) **Clean the streak:** the daily timer's rewire heredoc marks the first-ever (no-prior) window — which spans the whole clean-era pool, not a fresh per-checkpoint window — as `qualifies: false` + `is_first_look: true`, so it can never count. (2) **Numeric flip gate:** `status_cmd.rewire_flip_gate()` (pure/tested) excludes full-pool looks (new records by `is_first_look`, old ones by `window_since == clean-era`), counts the trailing fresh-window PASS streak, and requires the pooled fresh-window Δ's 95% normal-approx CI to **exclude 0** — the flip needs BOTH `streak ≥ 3` AND `CI_low > 0` (the offline A/B already cleared Δ +0.180 CI [+0.060,+0.309], E-3). Surfaced in `forge status` (`gate-tail flip gate MET/NOT MET`). (3) **Pre-registered** the flip prediction (`forge prereg` **`9063b405750c`**): flipping raises the top-decile realized wf_p25 floor vs blend by Δ ≥ 0.05 on the POST-flip cohort, resolved only if the flip gate was MET at flip time; keep gate-tail if confirmed, else revert (unset the env, byte-identical).

**Why both arms.** "3 consecutive PASSes" alone is a weak bar (0.5³ under the null = 12.5% false-flip); pairing it with a pooled-Δ CI that excludes 0 forces the fresh-window evidence to be jointly significant, not just a lucky run. The daily verdict is recorded (not re-derived), so the gate reads exactly what the timer wrote.

**STATUS: P1.2 SHIPPED (`c0796e2`, 6 tests). Telemetry only — no live behavior; daemon untouched.** Live flip gate: **NOT MET (fresh-PASS 1/3, n=1, no CI yet)** — the contaminated 06-30 full-pool FAIL is now excluded, leaving the honest 07-01 fresh PASS. The gate accrues as the timer records fresh windows; the flip stays operator-gated (deploy ritual + the prereg). **Recommendation on the operator's "flip now?": NO** — the gate is 1/3 with no CI, the D220 prior-weight prereg is still open (stacking a second big ranking change would confound both), and the gate reads raw (un-recalibrated) P where the floor barely bites (eligible_fraction 0.9869). Flip after the gate is MET on clean fresh windows + D220 resolves.

---

## D224 — 2026-07-02 — permutation_test cumulative_trading forward-return mode (flag-OFF); flip pre-registered (strategy-audit P1-1)

**Spec section:** §5.3.7; fable-audit strategy-methodology P1-1 (PRE-H2 a+b). The permutation_test filter is the pipeline's dominant reject (~51.4% of all enumerated). Two bugs in how it reads the forward return: **(a)** it takes the return on the SINGLE calendar day at T+`horizon`, not the cumulative return over the T+1..T+`horizon` holding window; **(b)** it shifts activation dates by CALENDAR days (`timedelta`), so a Friday activation reads Saturday (dropped) — Mon/Tue activations silently lose ~40% of their sample to weekends, biasing every p-value.

**Decision.** New calibration knob `permutation_test.forward_return_mode` (`prefilter.yaml`): `single_day` (**default**, legacy — the two bugs, kept as default so an un-flipped tree is byte-identical) | `cumulative_trading` (the fix). Cumulative mode sums the return over the next `horizon` **trading** days via the returns-index (T+1..T+k, no calendar arithmetic → no weekend loss), and — critically — **builds the permutation null on the SAME statistic** (cumulative-forward-returns from every eligible trading-day start), because a k-day cumulative real sum compared against 1-day null sums is a scale mismatch that would itself bias the test. The field is **optional in the loader** (absent → `single_day`), so `prefilter.yaml` is unchanged and the tree stays byte-identical (hard rule #6; verified — invariants + 376 prefilter tests green). Implementation reuses the already-fetched window returns (one fewer `feature_cache` call than legacy) and draws RNG only in the permutation loop, so the legacy branch is byte-for-byte identical.

**Ritual.** Flipping (`forward_return_mode: cumulative_trading` in `prefilter.yaml`) changes the config population → **feedback-change** (`docs/tasks/feedback-change.md`): operator flip at a deploy window + prereg + later-cohort confirm. **Pre-registered `848a1f671392`**: post-flip, trend/leading-family permutation_test survival rises + the weekday-of-activation systematic vanishes, without lowering the submitted stream's component-rate; keep if confirmed, else revert (remove the key, byte-identical). Coordinates with pipeline-perf P2-3 (permutation_test memoization) — **land this semantics fix FIRST** so any memo pins the correct computation.

**Alternatives considered:** (1) env flag instead of a calibration field — REJECTED (the knob belongs with `forward_horizon_days` in the per-filter calibration; env is for cross-cutting A/B levers like D216); (2) fix the real side only, leave the single-day null — REJECTED (scale-mismatched test, a new bug); (3) flip it live now — REJECTED (population change under the D220 hold + operator-gated).

**STATUS: P1-1 SHIPPED flag-OFF (`639cd8b`, 7 tests). Byte-identical default; daemon untouched; NOT flipped.** The flip is teed up for the operator (feedback-change ritual + prereg `848a1f671392`), sequenced after D220 resolves. This is the first of the strategy-methodology P1 "un-throttle the validated family" chain; the remaining items (P1-2 vol_event battery A/B, P1-3/P1-4 grammar bumps) are operator/grammar-gated.

---

## D225 — 2026-07-02 — Vol-appropriate |move| permutation null for volatility_event (flag-OFF) (strategy-audit P1-2a)

**Spec section:** §5.3.7; fable-audit strategy-methodology P1-2 (PRE-H1). `volatility_event` configs profit from the MAGNITUDE of the post-activation move (a long straddle / long-vol payoff ≈ |move| − premium), NOT signed drift. The permutation_test — even after D224's cumulative_trading fix — tests SIGNED forward return, so a ve signal that reliably precedes big moves whose *net* drift is ~0 lands in the middle of the signed null and is wrongly rejected. This throttles the exact PBO-orthogonal family (single-name ve) that D216/D-2026-06-29 validated as the in-v1 second factor.

**Decision.** New calibration flag `permutation_test.volatility_event_absolute_move` (`prefilter.yaml`; default **False** → byte-identical). When True AND `forward_return_mode == cumulative_trading` AND `config.hypothesis == "volatility_event"`, the test uses **|cumulative forward move|** for BOTH the real notional (Σ |per-activation move|) and the null pool (|move| over every eligible trading-day start) — the vol-appropriate statistic. **Family-scoped** via `config.hypothesis`: every other family stays on signed returns. Implemented as an `absolute` kwarg on the two D224 helpers (`abs()` each per-start cumulative); default False → the legacy/signed paths are byte-for-byte identical (invariants + 380 prefilter tests green). Optional in the loader (absent → False) → `prefilter.yaml` unchanged.

**Ritual.** A population change on the ve slice → feedback-change (operator flip + prereg + later-cohort confirm). **Pre-registered `e1a43ba8ee14`**: post-flip ve permutation_test survival rises vs the signed baseline, lifting decorrelated single-name ve supply, without lowering component-rate or degrading assemblable book PBO; keep if confirmed, else revert (byte-identical). Pairs with the cumulative_trading flip (`848a1f671392`) — ve-absolute requires cumulative mode.

**Alternatives considered:** (1) realized-vol or a full straddle-payoff model as the statistic — DEFERRED (|cumulative move| is the sanctioned proxy, cheap + no new feed); (2) apply abs globally — REJECTED (wrong for trend/mr, whose edge IS signed drift); (3) a per-family `forward_return_mode` map — heavier plumbing than the single ve-scoped bool, deferred until more families need bespoke nulls.

**STATUS: P1-2a SHIPPED flag-OFF (`db309b0`, 5 tests). Byte-identical default; daemon untouched; NOT flipped.** Second in the "un-throttle the validated family" chain (after D224). The shadow-count the plan calls for (how many ve configs newly survive) needs live feature-cache data → a daemon shadow pass or Crucible-fed replay; the mechanism is now built + tested so that measurement (and the flip) is unblocked for the operator. Remaining P1-2 items (family-aware signal_correlation event-pair exemption, predicted_activations control) + P1-3/P1-4 grammar bumps stay operator/grammar-gated.

## D226 — 2026-07-02 — Null-correction shadow-count harness: measure the D224/D225 flips on live data BEFORE flipping (strategy-audit P1-2)

**Spec section:** §5.3.7; fable-audit strategy-methodology P1-2 ("shadow-count first"). D224 (`cumulative_trading`) and D225 (ve `|move|`) are flag-OFF and gated on the D220 hold (no submitted-stream population change until the prior-weight prereg `b7ecc2d2e96f` resolves ≥2026-07-04T08Z). Both preregs (`848a1f671392`, `e1a43ba8ee14`) predict a rise in per-family permutation_test survival, but that prediction was un-measured — the daemon runs only the production (single_day, signed) null. Flipping blind would confound "the correction works" with "the correction changed the wrong thing."

**Decision.** A read-only telemetry harness that measures both flips on real data without touching the daemon. `forge/prefilters/shadow_null.py` (pure): `ShadowNullRecord` per config that reached the last filter → per-family `FamilyShadowDelta` (`reached`/`pass_prod`/`pass_corr`/`gained`=prod-FAIL→corr-PASS/`lost`=reverse/`net_delta`), enforcing the identity `pass_corr − pass_prod == gained − lost`. `corrected_null_calibration(prod)` flips ONLY the two null knobs (`cumulative_trading` + ve `|move|`); every other calibration section is identity — so the set of configs reaching permutation_test is the SAME under both nulls (filters 1..8 read none of the changed knobs), making it a clean within-population A/B. `forge shadow-null run` runs the §5.2 battery under the production null over the LIVE cache, then re-scores ONLY permutation_test under the corrected null on the same configs, sharing the feature cache (reuses the battery prefetch) and the `rng_factory` (identical shuffles — the ONLY thing that moves a verdict is the null construction). Prints a per-family survival table + appends one JSONL record. Submits nothing, never writes `prefilter.yaml`.

**Why a standalone one-shot, not a daemon hook.** "This tree IS production" (D104): wiring a dual-evaluation into the daemon loop is operator-gated and risks the live pipeline. A separate process sharing Crucible's writer socket (read path only; never `forge.db`, never the inbox) achieves the "daemon shadow-count" intent with the daemon byte-identical — main.py change is +2 lines (import + `add_typer`); invariants (determinism/clock/seed) green. Fixed-seed enumeration with empty priors is the established diagnostic pattern (`cmd_prefilter`): the per-family **delta** is a filter property robust to how configs were sampled; absolute rates are diagnostic only (the harness prints this caveat).

**Ritual.** Telemetry-only — no ritual gate (submits nothing, no config write, no deploy). The FLIPS it informs remain feedback-change + operator-gated + prereg-confirmed, after the D220 hold clears.

**Alternatives considered:** (1) run permutation_test standalone on ALL enumerated configs — REJECTED: over-samples families rejected earlier in production and costs 2× perm-test on every config; running the full battery gives the production-faithful population reaching the filter AND is cheaper (perm-test twice only for the few survivors). (2) `/tmp` forge.db snapshot — INSUFFICIENT: the shadow-count needs the live feature cache (Crucible socket), not forge.db. (3) daemon dual-eval hook — REJECTED per D104 above.

**Refinement (`fed9575`, tri-arm).** The first live run (N=800) exposed a design gap: `corrected_null_calibration` bundles BOTH flips, so the ve row conflated flip-1 with flip-2. Since the operator flips them one at a time, added `cumulative_only_calibration` (flip-1 alone) and made the harness score THREE nulls per config — A=production, B=cumulative-signed, C=cumulative+ve|move| — printing two survival-delta tables: **FLIP-1 = B vs A** (all families), **FLIP-2 = C vs B** (marginal, non-zero only for ve since |move| is family-scoped). B and C differ only for ve → non-ve configs take `c:=b` (one fewer re-score). Also hardened `_collect_tri_null_rows` to skip-and-continue on `FeatureCacheUnavailableError` (`0565d45`): the writer socket is shared with the daemon and dropped a connection at N=3000; the client reconnects on its next call, so a blip shouldn't abort the pass (surfaced as `socket_skips`).

**RESULTS — live tri-arm, N=2000, seed 0, 1444 reached permutation_test, 0 socket-skips (`~/forge_data/shadow_null/shadow_null.jsonl`).**

*FLIP-1 `cumulative_trading` (848a1f67), before→after survival:* event_momentum 9→40 (**+31, 4.4×**), trend_continuation 98→128 (**+30, +31%**), volatility_event 25→55 (**+30, 2.2×**), mean_reversion 118→85 (**−33, −28%**), relative_value 14→0 (**−14, →0**); TOTAL 264→308 (**+44**). **CONFIRMS prereg 848a1f67 for its targets (trend/leading forward-drift families) AND lifts ve 2.2× on its own** — the cumulative-window fix alone delivers most of the D216 single-name-ve supply goal — while pruning the over-supplied mr-monoculture and the ~dead relval. Net effect is a **rebalance toward decorrelated supply** (more trend/event_momentum/ve, less mr). → **flip-1 = a win; flip after D220.** (Family-mix shifts materially → watch component-rate post-flip, which the prereg already commits to.)

*FLIP-2 ve `|move|` (e1a43ba8), marginal on the cumulative baseline:* volatility_event 55→21 (**−34, −62%**; 16 gained / 50 lost); every other family net 0 (family-scoped). **REFUTES the prereg's stated direction** (it predicted ve survival RISES). Mechanism: the `|move|` null pool is all-positive with a high mean, so it's a **STRICTER** bar, not looser — a ve config must select moves in the top decile of |cumulative move|, and at the 5-day horizon most ve activations don't. The D225 premise ("signed forward-return wrongly rejects ve whose net drift ≈ 0") is **empirically wrong here**: the signed-cumulative null already passes ve well (20.8%), and |move| roughly triples the failure rate. NOTE the quality-vs-quantity tension the count can't settle: |move| may be selecting the genuinely magnitude-driven (straddle-relevant) ve signals and rejecting directional-drift ve (trend-in-disguise) — i.e. flip-2 could be a QUALITY tightening even though it cuts QUANTITY. But survival counts don't measure downstream promotability. → **HOLD flip-2: do NOT flip on the current prereg** (its survival prediction is refuted); flip-1 already supplies ve, and flip-2's quality benefit is unverified. Refer the open question to a Crucible-side read (do |move|-selected ve configs contribute more to the PBO-0.107 long-vol book than signed-selected ones?) before reconsidering.

**STATUS: P1-2 harness SHIPPED + RUN (`392c029`/`fed9575`/`0565d45`, 12 tests). Daemon byte-identical; nothing flipped. The shadow-count did its job — it split the bundled hypothesis and (a) strengthened the case for flip-1 (848a1f67), (b) caught that flip-2 (e1a43ba8) would CUT ve survival, contrary to its prereg. NEXT (≥07-04, after D220 `b7ecc2d2` resolves + the hold lifts): flip 848a1f67 alone (feedback-change ritual), confirm prereg on a later cohort; SHELVE e1a43ba8 pending the Crucible quality read.**

## D227 — 2026-07-02 — signal_correlation excludes the regime_filter context gate (flag-OFF); un-throttles event families (strategy-audit P1-2b / PRE-H3)

**Spec section:** §5.3.6 (T2.6 signal_correlation); fable-audit strategy-methodology P1-2(b), finding PRE-H3. The filter kills **20% of multi-signal vol_event configs** vs 2-6% elsewhere (the disproportionate ve throttle). PRE-H3's step one is "measure the rejected-pair composition before changing the filter."

**Measurement (live data + a live-cache verification pass; no code change needed — `max_pair` was already logged in `pre_filter_logs.details_json`).** Across 293,926 live signal_correlation rejects: **55% are Jaccard ≥0.95** (near-perfect co-firing), only 22% marginal (0.85-0.90); **88% of kills involve the `sig_regime` signal**. A live-cache verification (N=1500, `scripts/signal_correlation_regime_pair_audit.py`) attributes by family + role: ve **65/320 multi-signal rejected (20.3%, matches the finding), of which 61 (94%) are regime-pairs** (median Jaccard 0.949); the regime indicators doing the killing are **event/macro-calendar gates** — `days_to_nfp` (28), `days_to_cpi` (21), `days_to_fomc` (15), `days_to_opex` (12). Genuine **content-pair** redundancy (directional↔confluence) is **rare (9/1500) and marginal (median 0.869)**. Cross-family: relval 100% regime-pair, trend 100%, mr 72% — a general regime-gate artifact, most severe for ve.

**Root cause = a category error, not a mis-tuned threshold.** `sig_regime` has role `regime_filter` — a CONTEXT GATE (its job is to restrict firing to a regime/event window), not an alpha signal being combined for confluence. signal_correlation exists to catch "two edges that are really one" (redundant *alpha* content, per its docstring's rsi↔stochastic example). A gate co-firing with the alpha signals it gates is STRUCTURAL — a non-binding gate, not redundant alpha — so penalizing it is a category error. The 0.85 Jaccard threshold, calibrated for continuous indicators, is spuriously killing event-gated configs where everything clusters near the sparse event dates.

**Decision.** New calibration flag `signal_correlation.exclude_regime_filter` (`prefilter.yaml`; default **False** → byte-identical). When True, only alpha-bearing signals (non-`regime_filter` role) are compared, so gate↔content co-firing no longer rejects while content↔content redundancy still does. `details` gains `compared_signals`. Optional in the loader (absent → False) → `prefilter.yaml` unchanged (invariants + 396 prefilter tests green). **Role-aware, NOT family-aware** — the workplan proposed a ve-scoped threshold or event-pair exemption; the measurement shows the mechanism is the regime gate across ALL families, so excluding the gate is the narrower, more principled fix (it restores the filter's intended content-redundancy semantics rather than special-casing one family). This is a proposed refinement of the workplan's (b), logged here per "deviations are Decision Log entries."

**Ritual.** Flipping admits more configs at signal_correlation → a population change + effectively a loosening → operator + prereg (feedback-change), NOT auto-applied. **Pre-registered `5082d332b26e`**: post-flip ve signal_correlation reject fraction falls from ~0.20 toward the content-only ~0.01-0.02, lifting ve survivors, with no downstream book-PBO degradation; keep if confirmed, else revert (byte-identical). Independent of the D224/D225 permutation flips (different filter) — can flip in the same or a separate window.

**Alternatives considered:** (1) family-aware threshold (ve → 0.95) — cruder proxy that leaves the same artifact in relval/trend/mr and risks admitting genuine ve content redundancy; REJECTED for the role-aware fix. (2) event-pair exemption (both signals event-anchored) — needs an event-anchored-signal registry classification; the role-based `regime_filter` exclusion is simpler and captures the same configs (the gate IS the event anchor). (3) exempt only when the gate is a calendar indicator — narrower but ad-hoc; the role distinction is the principled line. (4) drop signal_correlation for ve entirely — over-broad; content redundancy is real (rare but present) and still worth catching.

**STATUS: P1-2b SHIPPED flag-OFF (`902e04a`, 4 tests). Byte-identical default; daemon untouched; NOT flipped. Measurement done (mechanism confirmed at 94% ve regime-pair). Completes strategy-audit P1-2: (a)=D225 ve |move| [refuted by the D226 shadow-count], (b)=this [validated by measurement, ready to flip], (c)=predicted_activations control [no change]. Flip after D220 alongside/independent of 848a1f67; then P1-3/P1-4 are grammar bumps (operator-gated).**

## D228 — 2026-07-02 — SPRT sequential test replaces the ad-hoc "k consecutive PASS" flip gate (learned-audit P3.1 / B5)

**Spec section:** learned-systems audit B5 / plan P3.1. The gate-tail flip gate (D223) required "k≥3 fresh-window PASSes AND a fixed-sample 95% CI excluding 0." Both arms are statistically ad-hoc for a gate peeked at daily: "3 consecutive PASS" is a **0.5³ = 12.5% false-promote** under a coin-flip null with no explicit Type-I control, and a **fixed-sample CI re-examined every checkpoint inflates Type-I** (the classic optional-stopping problem). B5 asks for a paired, significance-based rule with explicit α and a minimum effect size; the plan sanctions "confidence-sequence / e-value / SPRT."

**Decision.** New pure module `forge/ranking/sequential_test.py`: a **Wald Sequential Probability Ratio Test** for the mean of per-checkpoint PAIRED deltas (challenger − incumbent, one per fresh window). H0: mean Δ = 0 (challenger no better); H1: mean Δ = `min_effect`. It accumulates the log-likelihood ratio of Normal(0,σ²) vs Normal(δ,σ²) — `(δ/σ²)·(Σx − nδ/2)` — and decides `promote` / `reject` / `continue` at the Wald boundaries `log((1−β)/α)` and `log(β/(1−α))`, which control the false-promote rate at ~α over the WHOLE sequential procedure (valid under daily peeking). `min_observations` defers a decision on 1–2 noisy checkpoints; σ is a plug-in sample std (a quasi-SPRT/GLR; pass a warmup σ for the exact guarantee). Pure + deterministic (rules #5/#6). `status_cmd.rewire_flip_gate` now gates on this (`met` == decision `"promote"`, α=0.05/β=0.20/min_effect=0.05) over the **data-sufficient** (`qualifies`) fresh-window deltas, replacing `_mean_ci95`; `FlipGateStatus` carries the SPRT verdict and `forge status` prints it. The per-checkpoint PASS margin (`_REWIRE_DELTA_CRITERION`) is demoted to a display-only label (no longer the gate) and de-provisionalized.

**Scope / what's NOT here.** This does the reusable SPRT machinery + the **rewire** gate (the D223 gate I own, which already carries proper paired deltas). The **§8.6 tail streak** still uses an ABSOLUTE Spearman ≥ 0.30 (not a paired challenger−incumbent delta), so converting it to the SPRT requires the eval to compute the incumbent's Spearman on the same rows — a separate `eval-robustness` change, tracked as the P3.1 follow-up. `_TAIL_SPEARMAN_CRITERION` stays PROVISIONAL until then.

**Ritual.** Telemetry only — the SPRT gate informs the operator's FLIP decision (`forge status`); it changes no daemon submission behavior (status/reporting path). The flip itself stays operator-gated + deploy-ritual. No prereg needed (this is the decision RULE, not a prediction); the flips it gates keep their own preregs (`9063b405` gate-tail).

**Alternatives considered:** (1) an anytime-valid confidence sequence (normal-mixture/empirical-Bernstein) — more rigorous under continuous monitoring but heavier to implement + verify correctly; SPRT is explicitly sanctioned by the plan, textbook, and directly testable, so chosen for this increment (a CS can supersede it later without changing the gate's interface). (2) keep the streak but raise k≥5 — still an absolute-margin coin-flip with no effect-size or α; rejected. (3) e-value/testing-by-betting — cleaner composite nulls but the deltas aren't naturally bounded; deferred.

**STATUS: P3.1 (rewire arm) SHIPPED (`e66a74b`, `forge/ranking/sequential_test.py` + 10 tests; status_cmd rewired + tests updated). Telemetry only; daemon untouched; 356 ranking+cli tests green. The gate-tail flip (`9063b405`) is now judged by a controlled-α SPRT instead of the 12.5%-FP streak. FOLLOW-UP: convert the §8.6 tail streak to the paired SPRT (needs the incumbent-Spearman-on-same-rows in `eval-robustness`); then P3.2 (drift/adoption gating) / P3.3 (exploration holdout, operator-gated).**

## D229 — 2026-07-02 — §8.6 tail streak becomes a PAIRED SPRT (learned-audit P3.1 follow-up / B5)

**Spec section:** learned-systems B5 / P3.1 (the second gate). The §8.6 tail-lane clock PASSed on an ABSOLUTE pooled Spearman ≥ 0.30 of `tail_score` vs the realized worst-quartile gate. That rewards a model for *tracking a signal the incumbent P(component) already ranks* — it isn't the paired challenger-vs-incumbent skill B5 asks for, and it can't feed P4.1's retire-or-keep decision honestly (the lane can "PASS" while adding zero marginal skill).

**Decision.** `TailEvaluation` gains `incumbent_spearman` (Spearman(composite, realized) on the SAME rows — the triples already carried `composite_score`) and `spearman_delta = spearman − incumbent_spearman` (None when either side is degenerate). New `shadow_tail_verdict(ev, *, delta_criterion)` PASSes only when the tail model beats the incumbent's Spearman by more than the margin. The §8.6 gate is now the **same Wald SPRT** as the rewire gate: `status_cmd._sprt_flip_gate(delta_key=...)` generalizes the D228 logic, `rewire_flip_gate` (delta_key `delta`) and the new `tail_flip_gate` (delta_key `spearman_delta`) both delegate, and `forge status` prints both gate lines (`FlipGateStatus` gained a `label`). The daily timer records `incumbent_spearman` + `spearman_delta` and derives its verdict via `shadow_tail_verdict`; `eval-robustness` reports tail/incumbent/Δ + the verdict. `_TAIL_SPEARMAN_DELTA_CRITERION = 0.05` is the display-only per-checkpoint margin (the gate is the SPRT); `_TAIL_SPEARMAN_CRITERION` (0.30, absolute) is retired from the gate.

**Transition.** Legacy streak rows carry `spearman` but not `spearman_delta`, so `tail_flip_gate` skips them (isinstance guard) and stays NOT MET (n=0) until the daily timer writes new paired rows — never a fabricated PASS. Verified live: `§8.6 tail flip gate  NOT MET  SPRT continue … n=0`.

**Ritual.** Telemetry only — the tail gate informs P4.1 (the lane's retire-or-keep decision), changing no daemon submission behavior. No prereg (a decision rule, not a prediction).

**STATUS: P3.1 follow-up SHIPPED (`463ed04`, 360 ranking+cli tests green; all 3 timer heredocs compile). Completes P3.1 — BOTH streak gates (rewire + §8.6) are now controlled-α paired SPRTs; `_TAIL_SPEARMAN_CRITERION`/`_REWIRE_DELTA_CRITERION` de-provisionalized to display-only. NEXT: P3.2 (feature-drift PSI/JS + adoption gating) then P3.3 / P4.1.**

## D230 — 2026-07-02 — Feature/score drift + model-adoption gating (learned-audit P3.2 / B6)

**Spec section:** learned-systems B6 / plan P3.2. Model adoption is blind newest-wins (the daemon loads the newest artifact by mtime): a bad daily retrain silently goes live, and there is no signal for the input distribution drifting away from what the model was trained on. B6 asks for a drift metric (PSI/JS) + adoption gating (at minimum: refuse to rotate to a model whose fresh-window paired IC is negative) + surfacing the `_load_hypothesis_weights` uniform-fallback silent-degrade.

**Decision.** New pure `forge/ranking/drift.py` (7 tests): `population_stability_index` (quantile-binned PSI, the standard drift metric, None on thin samples, eps-floored bins), `psi_severity` (stable <0.1 / moderate <0.25 / major), `adoption_verdict` (ADOPT/BLOCK/UNKNOWN — BLOCK a non-positive fresh signal, "gate adoption not training"). Wired as telemetry:
- **healthcheck** — `check_hypothesis_weights_fallback` WARNs when the journal shows `hypothesis_weights: degraded to uniform` (the §6.2 sampler stopped steering — feedback loop muted; WARN not CRITICAL because the daemon still produces). AND the `wf_p25 drift` check now reads the PAIRED `spearman_delta` (D229) instead of the absolute `spearman` — a negative delta means the lane is worse than the incumbent it would rotate over, which is the real adoption signal. `check_learning_drift` was already framed as the newest-wins adoption guard; this points it at the right metric.
- **`forge status`** — an `adoption guard` line: `adoption_verdict` per lane (F3 AUC margin, wf_p25 paired Δ Spearman). Verified live: `F3=ADOPT (+0.440)  wf_p25=UNKNOWN`.
- **`eval`** — a score-distribution PSI line (`--since` window vs the honest-era baseline) via a new `shadow_score_samples` helper (pooled `model_score` by `scored_at`, no verdict join — drift is about the input distribution).

**Transition note.** Pointing the healthcheck tail-drift at `spearman_delta` means it reads "no qualifying checkpoints yet" (a WARN) until the daily timer writes the first paired-delta row (D229) — self-healing after one timer run; WARN is informational (the timer's `SuccessExitStatus=1`).

**Scope / NOT here.** This surfaces the signals; the ACTUAL adoption block (the daemon refusing to load a BLOCK-verdict artifact) is a production change to the model-load path → operator-gated + flag-OFF, deferred (the plan's "at minimum … gate adoption" is satisfied as a loud signal first). Full feature-vector PSI (vs the score-distribution proxy shipped) needs per-scoring-row feature vectors persisted — not currently stored; deferred.

**Ritual.** Telemetry only — no daemon submission-path change. No prereg (diagnostics, not a prediction).

**STATUS: P3.2 SHIPPED (`156e523`, 368 ranking+cli tests green). Telemetry only; daemon untouched. Drift + adoption signals now surfaced in `forge status` / `forge healthcheck` / `eval`; the hypothesis-weights silent-degrade is no longer invisible. NEXT: P3.3 (randomized exploration holdout — operator-gated, flag-OFF build) or P4.1 (wf_p25 lane retire-or-keep, now that both its skill gate (D229) and drift guard read the paired signal).**

## D231 — 2026-07-02 — wf_p25 lane per-family skill probe → KEEP (not retire); the marginal pooled signal is the mean_reversion drag (learned-audit P4.1)

**Spec section:** learned-systems plan P4.1 ("decide the wf_p25 lane's fate on a clock; run the cheap wf_p25-IC-on-vol_event-subset probe — if the lane shows skill *specifically* on vol_event, that changes its value proposition even if pooled skill stays marginal"). The lane has been live since D193 with §8.6 0/3 forever and the honest defense had shrunk to "not harmful" — a retire candidate.

**Probe (built P4.1, telemetry).** `evaluate_tail_shadow_by_hypothesis` splits the paired Δ Spearman (tail − incumbent P(component), same verified-coverage rows) by `config.hypothesis` (`json_extract_string(config_json,'$.hypothesis')`), pooled across tail models; `eval-robustness` prints it ve-first. Live (honest era, `forge_snap2.db`):

| family | n | paired Δ Spearman | verdict (Δ>0.05) |
|---|---|---|---|
| **volatility_event** | 55 | **+0.080** | PASS |
| trend_continuation | 4702 | **+0.143** | PASS |
| mean_reversion | 3276 | −0.062 | FAIL |

**Finding.** The lane's weak POOLED skill is an aggregation artifact: `mean_reversion` (the dominant row count) drags the pool to ~0, MASKING real, criterion-clearing skill on the two families the lane exists to serve — **vol_event (+0.080, the promotable single-name-ve book) and trend_continuation (+0.143, robust at n=4702, a decorrelating family)**. The lane down-ranks mr — the OVERSUPPLIED monoculture D216/D220 are trying to REDUCE — which is arguably correct behaviour, not a defect. This inverts the "only not-harmful" read: the lane is actively HELPFUL where it matters. (Caveat: ve n=55 is thin — suggestive, not tight; trend is rock-solid.)

**Decision — the retire-or-keep RULE (set now, per P4.1).** Judge the lane on its PER-FAMILY paired Δ on the families it serves, NOT on pooled skill (which the mr mass distorts): **KEEP while `volatility_event` OR `trend_continuation` paired Δ clears the +0.05 criterion on fresh windows (the D228/D229 SPRT machinery, once per-family streaks accrue); RETIRE (demote to telemetry, `FORGE_QUALITY_RANKER=off`) only if BOTH lose skill.** The mr FAIL and the pooled §8.6 FAIL are NOT retire triggers — they're the expected shape of a lane that correctly de-prioritizes the monoculture. **Current verdict: KEEP** (ve + trend both PASS).

**Ritual.** Telemetry + a decision RULE — no daemon change, no prereg (the lane is already live from D193; this decides its fate, it doesn't predict). Retiring or the per-family streak wiring, if pursued, is the operator's call on this basis.

**STATUS: P4.1 probe SHIPPED (`e5ffc27`, 27 evaluation tests green) + the retire-or-keep rule set + KEEP recommended on the data. Completes the buildable P3/P4 learned-systems items (P3.1/D228, P3.1-followup/D229, P3.2/D230, P4.1/D231). REMAINING learned: P3.3 (exploration holdout — a core-submit-path + `submissions.selection_mode` schema change; bigger + byte-identical-sensitive, deferred to a dedicated increment, operator-gated activation) + P5 (Thompson/UCB, elite archive — mostly blocked/opportunistic). Still hold live-stream changes until D220 `b7ecc2d2` (≥07-04).**

## D232 — 2026-07-02 — Exploration holdout: a seeded ranking-bypass for unbiased labels (learned-audit P3.3 / B7, flag-OFF)

**Spec section:** learned-systems B7 / plan P3.3. Every learned component (F3 verdict model, the wf_p25 tail lane, the D076 estimand) trains on Forge-**selected** submissions — a textbook direct feedback loop: the ranker only ever sees labels for configs the ranker chose, so it can't learn where its selection is wrong. The D103/D136 diversity floors mitigate (they force some variety) but don't correct the bias. B7: reserve a small seeded fraction of each batch for configs drawn at RANDOM from the prefiltered survivors, bypassing the learned ranking, to give unbiased labels.

**Decision (flag-OFF / byte-identical).** New `FORGE_EXPLORATION_HOLDOUT_FRAC` (default 0.0 → OFF; degrade-never-crash parse; clamped `[0, 0.10]`). When >0, `rank_batch_with_holdout` (queue.py) rank-selects the top `n − holdout_n` as usual, then draws `holdout_n` at RANDOM from the survivors ranking did NOT pick (`sample_exploration_holdout`, config_hash-sorted then `rng.sample` for determinism; RNG from `SeedHierarchy(seed).rng("exploration_holdout")`, rule #8). Total submitted stays ≤ n — the holdout REPLACES rank slots, it doesn't add (no oversubscription). `submissions.selection_mode` (`'ranked'`|`'holdout'`, idempotent ALTER, NULL = ranked) is tagged per candidate by `submit_batch(holdout_hashes=...)`, so evals can later split biased-vs-unbiased labels. The scoring loop is shared (`_score_reports`) so the holdout path scores identically to the plain path; `rank_batch` is untouched.

**Byte-identical when OFF.** frac 0 → `holdout_n == 0` → the run cycle calls `rank_batch(n=batch_size)` exactly as before, `holdout_hashes` empty → every row tagged `'ranked'`. The submitted stream (inbox files + config_hashes) is unchanged; only forge.db gains the `selection_mode` column. **124 invariants green** (determinism/byte-identical); the holdout branch is dormant until the operator sets the env.

**Ritual.** Activation is a submission-mix change (a population change) → operator sign-off + deploy ritual + the D220 hold (≥07-04). The plan also says "charge it to the alpha budget" — deferred (the holdout replaces rank slots so total submissions/effective-N is unchanged in count; the accounting refinement rides the alpha-budget/B8 work). The eval split (selected vs holdout) is a follow-up consumer once holdout rows accrue.

**Alternatives considered:** (1) rank ALL survivors then split top-vs-random — REJECTED: `select_top_n` diversification depends on `n`, so it wouldn't be byte-identical when off. Reserving from the un-selected pool keeps the flag-OFF path a literal `rank_batch(n=batch_size)`. (2) additive holdout (submit exploration ON TOP of the ranked batch) — REJECTED: raises submission count / oversubscription, fights the §7.3 limiter. (3) a `holdout` boolean on RankedCandidate — the `holdout_hashes` set keeps RankedCandidate unchanged and the tagging localized to submit.

**STATUS: P3.3 SHIPPED flag-OFF (`fc9e8b0`, 10 tests incl. a dry-run integration test of the live branch; 124 invariants green). Byte-identical default; daemon untouched; NOT activated. Completes the buildable learned-systems audit (P3.1/P3.2/P3.3/P4.1 = D228–D232); P5 (Thompson/UCB, elite archive) is mostly blocked/opportunistic. Activation is operator-gated (submission-mix change) + waits on the D220 hold; then wire the eval selected-vs-holdout split.**

## D233 — 2026-07-02 — Honest out-of-sample R² for the ridge (learned-audit P5.5)

**Spec section:** learned-systems plan P5.5 / June-review §5 ("Report OOS R²/IC instead of train-R² at ridge train time"). `train_robustness_model` reports an IN-SAMPLE `r2` (fit and scored on the same rows) — the classic overfit-optimism metric; the daily ridge always looks decent, and the P4.1/D231 lane KEEP decision leans on the model's apparent skill.

**Decision.** New `robustness_oos_r2(frame, *, target, lambda_, holdout_frac=0.2)` (model.py, telemetry): a deterministic TEMPORAL holdout — order rows by `decided_at`, hold out the newest `holdout_frac`, fit the ridge on the older train split, score the newer test split, `R² = 1 - ss_res/ss_tot` vs the test mean (can go negative — honestly, a model worse than the mean OOS). Reuses `_standardize_design` + `_solve_ridge`; None below `_MIN_OOS_ROWS=20` (never a fabricated score). Temporal (not random-fold) because the model predicts FUTURE configs — train-old/test-new is the honest generalization question with no leakage. `train-robustness` prints `oos_r2=` next to `train_r2=`.

**Kept OUT of the artifact.** `train_metrics` is hashed into `model_id`; storing OOS R² there would churn every model_id and break the daily rotation / §8.6 streak-pooling continuity. So it's a computed telemetry print, not a stored field — the artifact is **byte-identical** (model-determinism invariants green). Standardization means/stds are taken over the full design (a negligible feature-distribution leak; the ridge COEFFICIENTS whose overfit the in-sample r2 hides are fit on the train split alone).

**STATUS: P5.5 (OOS R²) SHIPPED (`a6e40fa`, 3 tests; 388 invariants+ranking green). Telemetry only; artifact byte-identical. Part B of P5.5 (precision@N/NDCG@N ranking metrics at the submission cutoff) NOT done — a separate eval addition, deferred. Remaining P5 (Thompson/UCB P5.1 — best AFTER the D216/P2 floor settles to avoid confounding; elite archive P5.2 — blocked on the B8 effective-N handoff; dead-code sweep P5.3 — chore) stays low-priority/opportunistic.**

## D234 — 2026-07-02 — Pipeline-perf observability: phase_timings `weights` bucket + compact prefetch log (P3-1/F6 + P3-3/F19)

**Spec section:** fable-audit pipeline-performance P3-1 (F6) + P3-3 (F19). Started the pipeline-performance audit (the daemon burns ~11 avoidable CPU-h/day, taxing the Crucible compute it shares). Began with the two items that are **byte-identical to the submitted stream, persistence, AND feedback cadence** — pure observability — so they're safe to land under the D220 hold + D104 (a reboot just changes a journal field). The audit's big wins (P0-1/2/3, the DuckDB `executemany` autocommit/fsync rewrite; ~190s→6s submit) change persistence timing and thus feedback cadence, so their DEPLOY is deferred to the post-D220 window to keep the resolved prereg's attribution clean.

**Decision.** (1) **P3-1** — the learned-weight loaders between `reconcile` and the battery (promoted fetch + hypothesis/regime/bucket/underlying/directional/orthogonal/cohort/regime_gate/trade_rate weights), a ~28s stanza that sat in NO `phase_timings` bucket, are now wrapped with a `weights=` timer and added to the fixed key order (after `reconcile`, before `enumeration`). This is the audit's DO-FIRST item — it makes the later loader/parse fixes (P1-1/P2-4) journal-verifiable. (2) **P3-3** — `feature_cache_prefetch_batch` logged two full ~124-ticker coverage dicts (`returns_coverage` + `regime_coverage`) + the full sorted ticker list every iteration (~70% of journal volume); replaced with aggregates `max_coverage` / `n_full_coverage` / `below_full` (only the underlyings under the max returns window — the thin-data signal). Event name + `data_unavailable` kept verbatim (operator-grepped; M-5 intent).

**Ritual.** Observability only — no persistence/submission/cadence change; no deploy ritual required beyond the tree landing (the new journal fields appear on the next restart/reboot). No prereg.

**STATUS: P3-1 (`3acc66b`) + P3-3 (`0068f44`) SHIPPED. Byte-identical behavior; 46 run-cycle + 16 cache tests green. Pipeline-perf audit STARTED. NEXT (post-D220, deploy-gated, cadence-sensitive): P0-2/P0-3 (cheap reconcile), P0-1 (the submit-phase fsync rewrite, the big win), each with the ritual + equivalence tests. Remaining SAFE-NOW pipeline-perf hygiene: P3-4 (single-txn shadow scores), P3-5 (rate-limiter connection reuse), P3-2 (adaptive blocked sleep).**

**Follow-on — P3-4 SHIPPED (`af4b1a7`).** `run_shadow_scoring` (the telemetry-only shadow write, never touches submissions → safe under D220) did one autocommitting INSERT per candidate — DuckDB WAL-fsyncs each (~200 fsyncs/batch). Wrapped in one `BEGIN`/`COMMIT`: same rows, one commit; on failure `ROLLBACK` then re-raise into the outer handler, preserving the never-raises posture AND leaving the shared connection clean (not stuck mid-transaction). New test covers the failure path (returns 0, rolls back, connection usable after); output byte-identical; 11 shadow tests green. **P3-5** (rate-limiter connection reuse) NOT taken — it restructures `check_rate_limit`'s connection lifecycle across `_evaluate_stall_guard`/`_evaluate_inflight_depth`, the audit couples it with the deferred P1-1 `gated_runs=` kwarg, and it's the §7.3 limiter (block decisions must stay byte-identical) — a poorer risk/value; do it with P1-1.

## D235 — 2026-07-02 — ve `|move|` null (e1a43ba8) DROPPED — Crucible quality read finds no support + inverts the thesis; book-PBO baseline corrected 0.107 → 0.178

**Spec section:** §5.3.7; closes the ve `|move|` thread (D225 built it, D226 shadow-count refuted its survival prereg, `PROMPT_CRUCIBLE_VE_MOVE_NULL_SELECTION_QUALITY.md` posed the one open quality question). Crucible answered: `../Crucible/docs/handoffs/FORGE_ve_move_null_selection_quality_RESULT_2026-07-02.md`.

**The question.** The D226 shadow-count showed flip-2 (ve `|move|`) CUTS ve permutation survival 55→21 (−62%), refuting its prereg's "survival rises." The only thing keeping it *shelved* not *dropped*: was the cut a QUALITY tightening (selecting genuinely magnitude-driven, more-decorrelated ve — good) or a supply THROTTLE (bad)? That's a downstream book-contribution read only Crucible can do.

**Crucible's result (necessary-condition screen, 622 honest single-name ve comps).** (1) The cheap realized-P&L proxy **cannot** reproduce the signal-level partition — 100% of comps realize as directional (magnitude_share median 0.255, **0/622 reach 0.5**), because a `|move|`-selecting *signal* realized through a directional OTM *structure* converts the move into delta-$ P&L. Structure confound; the realized partition measures something different from the signal partition. (2) The weak within-band gradient **INVERTS Forge's un-shelve thesis**: the *more* magnitude-driven ve (Q5) is *more* correlated to the trend/MR pool (|corr| 0.070→0.118) and loads *higher* on PC1 (0.066→0.104) — i.e. *less* decorrelated; marginal_sharpe only mildly favors Q5. So magnitude-selected ve is NOT the higher-quality / more-decorrelated supply the thesis claimed. **Power caveat resolved favorably** — all 622 comps were classifiable, so the blocker is proxy dispersion (a structural confound), NOT sample size. Airtight resolution would need Forge to hand over the exact `config_hash → ve_null_profile` tag (route (a), a variant of the shadow-count); Crucible would then re-score #1/#2 and, only on a real contrast, the #3 book-PBO.

**Decision — DROP e1a43ba8.** Refuted on its own survival prereg (D226) AND unsupported / thesis-inverted on quality (this read) AND redundant — flip-1 (`848a1f67`, +2.2× ve survival) plus the D216 orthogonal-family floor already supply ve. The prior was low; dropping loses little (Crucible concurs). Prereg `e1a43ba8ee14` resolved **refuted** (disclosed exception to post-cut: the flip is dropped, so no post-flip cohort will exist; the refutation is the clean pre-flip shadow measurement + this quality read). The airtight route (a) stays available on request but is low-EV for a near-certain drop. This closes the LAST in-v1 orthogonal-*directional* ve thread (cf. the 06-28/06-29 closures); single-name ve supply (flip-1 + D216 floor) remains the producer job.

**Baseline correction (propagate).** The promotable book's CSCV PBO the 06-29 result reported as **0.107** was the 8-group / 28-path estimate; the clean **10-group / 45-path** confirm landed at **0.178** (`../Crucible/.../probe_results/mixed_book_pbo.json`; degradation slope −0.598; ve-heavy `tm4_ve8` won 36/45 paths). **Still clears the 0.40 gate and sits below the 0.50 noise floor — the book is still promotable**, less dramatically. Any future "book-PBO with/without a ve subset" anchors on 0.178, not 0.107. Corrected in STATUS + memory.

**STATUS: e1a43ba8 DROPPED (prereg `e1a43ba8ee14` → refuted). No code change — the flag was already OFF/byte-identical (D225); it stays in the tree as dead-but-inert, or can be removed in a later cleanup. Teed-up 07-04 levers now: `848a1f67` (flip), `5082d332` (flip), `9063b405` (flip, SPRT-gated), `FORGE_EXPLORATION_HOLDOUT_FRAC` (activate). Book baseline is 0.178 everywhere.**

## D237 — 2026-07-04 — D220 prior-weight prereg CONFIRMED (post-cut component-rate 0.1229 vs ≥0.06); the hold is LIFTED (D236 is the v23 worktree's)

**Date note:** the actual clock is 2026-07-04T17:09Z — the post-compaction session had been carrying a stale "2026-07-02" date from the summary; earlier entries D226–D235 are labelled 07-02 but the later ones landed 07-03/07-04 (content valid, date labels approximate). D236 is reserved by `../Forge-build-v23` (v23-trend-grammar, `ade3344`), so this is D237.

**Resolution.** D220's prereg `b7ecc2d2e96f` (cut 2026-07-02T08:02Z, ≥48h formal window) is now past its ≥2026-07-04T08:02Z resolution point. Measured the post-cut component-rate on a fresh snapshot (`scratchpad/forge_d220.db`): **0.1229** (6732 components / 54756 decided, submitted ≥ cut) vs the prereg's **≥0.06** threshold and the ~0.048 baseline anchor. **Durable across the full window** — by submit-day 07-02 0.117 / 07-03 0.122 / 07-04 0.128 (rising, not an early spike); +62% over the immediate pre-cut window (06-28..cut = 0.0757). Nothing else deployed in the window (all session work flag-OFF/byte-identical), so the lift is attributable to the 0.10→0.50 `prior_promotion_proximity` raise (the D149 F3 wiring); the early-read Kitagawa decomposition (72% within-family ranker skill, ve confounder ruled out) holds full-window. **Resolved CONFIRMED.**

**The D220 hold is LIFTED.** The self-imposed "no submitted-stream ranking/population change until D220 resolves" is satisfied. The teed-up flag-OFF levers are ready — all at OFF defaults, prereg'd, byte-identical when unset:
- `848a1f67` — permutation_test `cumulative_trading` (D224; shadow-validated D226: trend/em/ve survival ↑). The highest-value flip.
- `5082d332` — signal_correlation `exclude_regime_filter` (D227; 94% of ve kills are the regime gate co-firing).
- `9063b405` — gate-tail mode (D222/D228). **Flip gate now MET** (`forge status`: SPRT promote, logLR +41.66/2.77, fresh-PASS 4/3, mean Δ +0.299).
- `FORGE_EXPLORATION_HOLDOUT_FRAC` — exploration holdout (D232; operator sets the frac).
- `5c4ba16f` — D216 orthogonal-family floor (ve supply; separate prereg, still open).
- `e1a43ba8` — DROPPED (D235).

**Sequencing (recommendation, operator-owned).** Flip **one at a time**, each with its own cohort cut, so each prereg resolves cleanly — deploying several at once re-confounds attribution (the exact thing the hold avoided). Highest-value first: `848a1f67`. Each flip is a `prefilter.yaml`/env change → **feedback-change ritual + `docs/tasks/deploy.md`** (stop service → full uncontended suite → commit → restart → verify journal) — **operator-gated** (the daemon can't be restarted autonomously). The flip preregs resolve ONLY on their own post-flip cohorts.

**STATUS: D220 CONFIRMED (`b7ecc2d2e96f`); hold LIFTED. Levers ready + gate-tail gate MET. NEXT: operator runs the feedback-change deploy for `848a1f67` first (I can prepare the exact edit + ritual checklist), then the others one at a time. Also unblocked-for-deploy: the pipeline-perf P0 fsync rewrite (separate ritual). Daemon healthy (component-rate 0.123, submitting).**

## D238 — 2026-07-04 — FLIP #1: permutation_test `cumulative_trading` deployed (prereg 848a1f67; first post-D220 flip)

**Spec section:** §5.3.7; the first flip after the D220 hold lifted (D237). `prefilter.yaml` `permutation_test.forward_return_mode: cumulative_trading` (was absent → the buggy `single_day` default). The correction (D224 built, D226 shadow-validated: trend/event_momentum/ve survival ↑) fixes two bugs — point-in-time not cumulative, and calendar-day shift dropping ~40% of Mon/Tue samples to weekends.

**Deploy scope — bigger than a config value.** (1) The running daemon started 2026-07-02 01:11 PDT and had NOT restarted since, so all **57 session commits** (D221–D237, every flag-OFF lever) were committed-but-not-loaded — the flip's restart deploys all of them (behaviorally identical; they're flag-OFF/byte-identical) + the flip. The full-suite gate validates the whole tree. (2) `forward_return_mode` is hot-read but the running daemon lacks the D224 loader code (committed 11:24 PDT, after the 01:11 start), so a restart is MANDATORY — editing the yaml alone is a no-op on old code.

**Test updates (the flip changes deploy-state assertions).** Four tests asserted the pre-flip `single_day` default; updated to reflect the deployed state without weakening guarantees: `test_shipped_calibration_mode_is_cumulative_trading` (was `..._is_single_day`) + a NEW `test_absent_forward_return_mode_defaults_single_day` (back-compat: a keyless config still defaults single_day — the loader guarantee, now decoupled from the live config); the shadow-null builder test decoupled to a constructed single_day base; the CLI smoke test asserts `prod_null` MATCHES the live config (flip-agnostic); and the fragile `test_rerun_same_seed_is_idempotent` → `test_same_seed_is_deterministic` (two independent fresh-DB runs at the same seed submit the identical config set — the real hard-rule-#6 invariant; the old "second run all-dupes" form only passed because pre-flip `single_day` rejected every synthetic-noise config, which the flip exposed).

**Ritual.** feedback-change + `deploy.md`: full suite green (1842) → commit → stop → restart → verify journal. Resolve prereg `848a1f671392` on the POST-FLIP cohort (data after the actual restart timestamp, NOT the prereg's 07-02 registration cut — the flip is 07-04). Watch the per-family submission mix + component-rate.

**STATUS: flip committed + suite-green; restart pending (operator-gated). Post-restart: verify journal (contracts line, grammar_version, reconcile, no traceback), record the deploy timestamp in STATUS, then resolve 848a1f67 on the post-flip cohort. Next flips (5082d332, 9063b405, holdout) follow one at a time.**

## D239 — 2026-07-04 — FLIP #2: signal_correlation `exclude_regime_filter` deployed (prereg 5082d332)

**Spec section:** §5.3.6; the second post-D220 flip. `prefilter.yaml` `signal_correlation.exclude_regime_filter: true` — exclude the `regime_filter` context gate from the pairwise Jaccard overlap (D227: 94% of vol_event signal_correlation kills were the gate co-firing with the alpha signals it gates, median Jaccard 0.949 — structural, not the content redundancy the filter targets).

**Deploy nuance vs flip #1.** The daemon (restarted at flip #1) now HAS the D227 code and hot-reads `prefilter.yaml`, so editing the live config would activate the flip immediately, ungated. So the ritual STOPPED the daemon first (before the config edit), ran the full suite uncontended, committed, then restarted — the edit never reached a running daemon un-gated.

**Test prep (two commits).** (1) `c543120` — decoupled the base-mechanism signal_correlation tests from the live config by pinning the shared `_ctx` fixture to `exclude_regime_filter=False` (so "gate co-firing → rejected" still verifies the gate-included behaviour once the live config ships ON); the ON behaviour keeps `_ctx_exclude_regime`. (2) this flip — added `test_shipped_calibration_excludes_regime_filter` (asserts the live config is now ON). Full suite green (1843).

**Sequencing note.** Flipped ~30 min after flip #1 (`848a1f67`). Defensible because the two hit DIFFERENT filters (permutation_test vs signal_correlation) with SEPARABLE prereg primary metrics (permutation survival vs signal_correlation reject-fraction); only the shared component-rate guard is jointly attributed. Resolve prereg `5082d332b26e` on the POST-FLIP cohort (per-family signal_correlation reject fraction: ve ~0.20 → ~0.01-0.02; ve survivors up; no book-PBO harm).

**STATUS: flip committed + suite green (1843); restart + verify next. Post-restart record the deploy timestamp. Remaining teed-up levers: `9063b405` (gate-tail, gate MET), `FORGE_EXPLORATION_HOLDOUT_FRAC`.**

---

## D240 — 2026-07-05 — INCIDENT: §7.3 backpressure stall (601 phantom failed-runs) + durable failed-run reconciliation

**Spec section:** §7.3 (in-flight backpressure) / §8.2 (feedback consumer). Two parts: (A) a one-time flush that cleared a live production stall; (B) the durable fix so it never recurs. Contracts bump 1.22.0 → 1.23.0.

**The incident.** While reading the two flip preregs I found the daemon had stopped submitting for ~15h: every loop iteration logged `blocked: in-flight depth 601 exceeds cap 600 (§7.3 backpressure)` and reconciliation was frozen (`newly_gated_total` static). In-flight (`status='submitted'`) held 601 rows spread evenly ~150/day across 07-01→07-04, oldest 4.7 days — a phantom population, not a genuine Crucible backlog (Crucible was healthy: inbox drained, gated + failed exports fresh). All 601 were present in Crucible's `failed_runs` export (634 runner_failure + 52 pool_break in-window): runs Crucible accepted and executed but that died in the runner before a gate decision, so they never enter `gated_runs` and Forge's config_hash reconcile join can never match them. They therefore sat `submitted`, pinning §7.3 depth above cap 600 → all submission blocked. This is a recurrence of the D205 class (failed runs invisible to Forge) — but the ROOT was newly diagnosable: **Crucible had shipped the D205 durable-feedback export (`failed_runs_*.json`, per `PROMPT_CRUCIBLE_FAILED_RUN_FEEDBACK.md`), but neither `crucible_contracts` nor Forge consumed it.**

**(A) Immediate flush.** `scratchpad/flush_failed_inflight.py` (session scratchpad, not committed) reads the newest `failed_runs` export and retires matching `submitted` rows using the SAME proven terminal marker as the D052/D110 aged-out flush — `status='gated'` + `_AGED_OUT_SENTINEL_RUN_ID` (already excluded from the §7.3 depth count, rate-limiter H-1, and M-7 promotion_basis). Keyed on the authoritative failed list, so strictly more precise than an age-based flush (no risk of retiring genuinely-pending work). Ritual: stop daemon (free the RW lock) → dry-run vs live DB (601/601 in failed export, 0 genuine-pending) → `--apply` (retired 601, in-flight → 0) → restart. Verified: `submitted=200` batch, then the healthy per-batch §7.3 wait (`0.0% gated; waiting for >=80%`) — production flowing again.

**(B) Durable fix.** `crucible_contracts` 1.23.0 (additive; 303 tests / 100% cov): `FailedRun` model (frozen: `config_hash`, `finished_at`, `error_category` — an OPEN string so new failure taxonomies don't break the contract) + `load_recent_failed_runs_from_export` mirroring the gated loader. Forge: pin → 1.23.0; `feedback.consumer._flush_failed_runs` retires failed `submitted` rows (same sentinel mechanism as A) wired into `reconcile_all_pending` before the aged-out flush, so every poll retires runner-failed runs instead of letting them accumulate for 5 days. Silent (matches `_flush_aged_out_submissions`); the existing `blocked: depth` line remains the backstop signal if the flush ever falls behind.

**Design choices.** (1) Reused `_AGED_OUT_SENTINEL_RUN_ID` rather than minting a distinct failed-run marker — a second sentinel would have to be threaded through every exclusion site (rate_limiter H-1, M-7), and both states mean the same thing operationally ("not a real gate decision, exclude from analytics"). Audit-distinguishability, if ever wanted, belongs in a dedicated column. (2) Per hard rule #2, Forge reads the export ONLY via the new contracts helper — the raw-file read lives only in the throwaway flush script. (3) `error_category` left an open `str`, not a StrEnum, so a future Crucible taxonomy is a non-breaking change.

**Resolves** `PROMPT_CRUCIBLE_FAILED_RUN_FEEDBACK.md` (Crucible side shipped; Forge side now consumes). Related: D196 (depth cap), D205 (prior manual flush), D052/D110 (aged-out flush precedent).

**STATUS: DEPLOYED 2026-07-05 17:05:09 UTC (daemon PID 3010796).** Contracts `01da53b` (1.23.0), Forge `651ca6e`. Uncontended gate suite 1846 green; verify: active, NRestarts=0, clean startup (grammar_version=v22, no traceback), `reconciled: batches=1 newly_gated_total=195` (no depth block), `contracts: pin == installed (1.23.0)`, `submission: submitting` (the 15h-stall WARN cleared), `forge healthcheck` **OVERALL=OK (10 ok, 0 warn, 0 crit)**. The `_flush_failed_runs` path now runs every reconcile poll. Both flip preregs still unresolved (flip #2 confirmed on the Forge supply metric, flip #1 insufficient/read-compromised) — re-resolve on a clean post-fix cohort; then the teed-up levers `9063b405` (gate-tail) and `FORGE_EXPLORATION_HOLDOUT_FRAC`, one at a time.**

---

## D241 — 2026-07-05 — Full codebase-health review: ledgers reconciled to reality, stale docs swept, root archive sweep #2

**Spec section:** none — housekeeping/ledger-integrity increment (operator-requested full review: code health, stale-doc cleanup, prior-audit completion, new gaps). Read-only fan-out first (code health / docs accuracy / audit completion / repo hygiene), then docs-only fixes. No behavior change; daemon untouched throughout.

**Code health: fully clean.** ruff 0 violations; mypy --strict 0 (101 files); full suite 1846 passed / 0 failed (contended run, no flakes); zero TODO/FIXME/HACK in src+scripts+tests; hard rules #2 (no Crucible internals) and #8 (clock/seed) grep-clean; no silent exception swallows; contracts pin 1.23.0 == installed. Every finding was documentation or ledger drift, not code.

**Key ledger correction — pipeline-perf P0 was ALREADY DEPLOYED.** P0-1/2/3 shipped 2026-07-02 (D219; `18a30eb`/`2d601a0`/`bf822c3`) and the live journal proves the effect (submit 195–202s → 4.7s; reconcile 30–37s → 2.0s). The "P0 fsync rewrite unblocked / pending deploy" NEXT pointers carried in the D234/D237/D239/D240-era STATUS blocks were stale drift — nothing of P0 remains to build or deploy, and a future session following those pointers could have rebuilt the explicitly-rejected CSV path. Remaining perf levers in value order: P1-1 parse-export-once (weights=17s/iter) and P2-1 prefetch (141s/iter, now the dominant per-iteration cost; needs hit/miss telemetry + a Crucible relay).

**Landed (docs-only commits):**
- `64f794a` — archive sweep #2: 56 landed records → `_archive/` via git mv (root *.md 72→16; D202 criterion: self-declares done AND has a verified landing D-entry, or is a superseded draft). Also carried the repo-sync of the already-live `FORGE_BACKUP_KEEP=5` backup-retention override (the installed unit is a symlink into this tree, so the edit was already in effect; committing restores D104 cleanliness).
- `17b69bb` — tracked the 2026-07-05 generation-discipline F1+F3 relay (root-prompt convention).
- `5ccda63` — docs accuracy sweep. D240 (failed-run reconciliation) propagated everywhere it was missing: MANPAGE services table + submissions lifecycle, HOW-TO runbook (templated `crucible-runner@N`, failed-runs publisher, registry publisher timer-driven per D166, depth-cap guidance), investigate-live (third §7.3 block reason + the D205/D240 diagnostic join + the journalctl-local-vs-UTC tz trap), architecture data flow, glossary reconcile entry. Plus: healthcheck 8→10 checks; `forge status` flip-gate rewritten as the Wald SPRT (post-P3.1); train-robustness `--label`/`--label-col`/`oos_r2`; 6 missing script rows; glossary aged-out watermark 8d→5d (`STRANDED_AFTER`); NEW_BOX_TRANSFER pin literals → pointers to `contracts_check.py`; suite count ~1,400→~1,850 (CLAUDE.md + quality-gates); INDICATOR_THRESHOLDS fossils struck (v6-hold, SPY-only skip); architecture king/ row corrected to removed-at-D190; `battery.py` docstring "seven"→"nine".
- `69da7fe` — OPEN_QUESTIONS: Q10/Q18/Q25/Q35/Q36/Q37/Q38/Q42 RESOLVED with evidence; Q13/Q20 closed as superseded; Q19 annotated PARTIAL (contracts `universe_min_asof` landed; Forge-side clip still open). OPEN_PROPOSALS: fossil loosen `4b155abd` (2026-05-15, auto_tune_loosen 10%) REJECTED in-file per the D206 format — moot since D206 emptied auto-tightening and D218 disarmed auto_tune; declining is the conservative (rule-4-safe) direction. Residual: the DB-row half (`forge grammar reject-proposal --id 4b155abd-67f2-47a7-9d49-9996a70365cd`) at the next unlocked-DB window.
- `fc7f67d` — fable-audit four tracks reconciled (ticked checkboxes + dated annotations; the genuinely-open lists in each WORKPLAN are now trustworthy).

**Gaps flagged, NOT executed (operator calls):** (1) 72+ commits unpushed to origin — the repo itself has no off-box copy; a push or the held `FORGE_BACKUP_DEST` off-box target is the cheap DR fix. (2) IMPLEMENTATION_DECISIONS.md has crossed its own 1MB rotation trigger (codebase-quality item 16) — rotation changes the grep workflow, so operator-gated. (3) Two root relays need a skim: `PROMPT_CRUCIBLE_V22_FUNNEL_COMPARE.md` (likely overtaken by the v23 funnel ask), `PROMPT_CRUCIBLE_OPTIONS_PRIMARY_STANDALONE.md` (send-status never recorded). (4) One-shot probe scripts (`signal_correlation_regime_pair_audit.py`, `decorrelation_proxy_alignment.py`, `wf_quality_probe.py`) now labeled as such in MANPAGE — retire or keep. (5) Top open audit items: pipeline P1-1/P2-1; learned P3.4 (B8 effective-N relay + `confirm_promotion_claim` ritual-doc adoption); strategy P0-4a/c + P3-1 prereg-tooling hardening (non-atomic `resolve_preregistration` write, no double-resolve guard — the flip machinery leans on this); codebase-quality 5 (CI) / 6 (scripts under mypy) / 7 (one-off script guards); the stray 4.5GB `forge.db.bak-pre-flush-20260624`.

**STATUS: docs-only; nothing deployed; daemon untouched (healthy, submitting).**

**Follow-through (same day, operator-directed):** gap (1) pushed to origin; gap-4 residual done — `4b155abd` DB row rejected via `forge grammar reject-proposal` (verified `rejected`/aj); gap (4) three probe scripts + path-loaded tests retired (`git rm`; unit suite 1643 green; MANPAGE updated). Still open from the flagged list: ledger 1MB rotation (2), two-relay skim (3), stray 4.5GB bak (5).

---

## D242 — 2026-07-05 — Decision-ledger rotation #1 (D001–D200 → `_archive/`) + two outdated relays archived

**Spec section:** none — housekeeping (operator: "1. lets rotate, 2. these are outdated" — closing D241 gaps 2 and 3).

**(1) Ledger rotation.** `IMPLEMENTATION_DECISIONS.md` had crossed its own 1MB rotation trigger (codebase-quality item 16; 1,012,629 bytes). Rotated **D001–D200** (2026-05-13 → 2026-06-24, 859KB; content-verbatim modulo pre-commit whitespace trims — the old entries predate hook enforcement) to `_archive/IMPLEMENTATION_DECISIONS_D001-D200.md`; this file keeps the preamble + a rotation pointer + D201 onward (~153KB). Split integrity verified: the archive holds exactly 200 `## D` entries ending at D200; this file runs D201→current with one legitimate gap (**D236 lives on the `v23-trend-grammar` branch** in the build worktree, not on main). Code/docs cite D-numbers, never file offsets, so nothing breaks — grep the archive for pre-D201 entries. **Rotation rule going forward:** when this file crosses ~1MB again, rotate the next ~200-entry block the same way.

**(2) Hook exemption for archives.** `check-added-large-files` (200KB cap) would have blocked the 859KB archive slice; added `exclude: ^_archive/` with a comment. The cap's purpose (catching accidental binaries/data) is preserved everywhere else; future rotations need no bypass.

**(3) Relays archived as outdated (never sent).** `PROMPT_CRUCIBLE_V22_FUNNEL_COMPARE.md` (overtaken: the funnel-compare ask now rides the v23/D236 handoff; a v21→v22 compare on today's rolling window would be cohort-trap noise per D104) and `PROMPT_CRUCIBLE_OPTIONS_PRIMARY_STANDALONE.md` (framing predates D216/D235) → `_archive/` with ARCHIVED-unsent banners. Root `*.md` now 14.

**STATUS: docs/config-hygiene only; nothing deployed; daemon untouched.**

---

## D243 — 2026-07-05 — Crucible F1/F3/F4 generation-discipline design loop CLOSED (design-only; no code/contract change). Agreed coordinated contracts bump + 3 Forge builds DEFERRED behind ve-supply.

**Spec section:** cross-system coordination (`docs/tasks/crucible-handoff.md`); touches §5 prefilters / §6.2 learned ranking (the two raw-scalar training channels) and §13.4 idempotency (freeze ledger vs `config_hash`).

**Six-message round-trip with Crucible over recs F1 (mechanism-first trial budgets / hypothesis cards), F3 (coarsen the Crucible→Forge feedback channel), F4 (trial-count semantics), from Crucible's research pass `forge_crucible_pipeline_best_practices_2026-07-02.md`. Three Forge-side relays authored + relayed; design agreed end-to-end; NOTHING built or deployed. Both sides hold the framing: F1/F3/F4 are honesty/multiplicity hygiene, NOT promotion levers — only F2 (new mechanisms + new data) moves the CPCV-p25 wall.**

- **F3.1 finding (re-derived from Forge code/DB, not memory):** two production-loop learned paths ingest RAW Crucible gate scalars today, both reading `gate_results[*].value/.threshold` — the D114 joint-quality term in the enumerator sampling reward (`feedback/rejection_weights.py:332,443-452`; `cpcv_sharpe_p25` + `walk_forward_sharpe_median`, weight 0.25, on by default) and the `--quality-rank` wf_p25 lane label (`ranking/dataset.py:72,139`). The F3 `P(component)` ranker is already coarse-label-only (COMPLIANT). PBO/DSR ingested nowhere. A genuine deviation from F3's "coarse labels only," but non-urgent (family-level aggregation + D124 era-cut labels blunt the leak).
- **F4 settled:** Forge stamps `search_n_trials` unset (null) on 100% of 334,989 submissions; deterministic enumeration = no within-config search (breadth is cross-config, visible in Crucible's runs table). Crucible confirmed unset→`n_trials=1` (`_runner_gates.py:437`); fixed the failed-trial undercount (LM-P1-6, `2db9a10`) → campaign-scope DSR N is now exact, not a floor. Caveat A (a literal `0` coercing to 1) moot — Forge commits to null/`≥1`, never `0`.
- **Agreed — ONE coordinated `crucible_contracts` minor bump, all additive + hash-excluded, both-operator-gated, sequenced behind ve-supply:** (1) `failure_buckets: list[str]` on the gated-runs export (9-bucket taxonomy; the non-exclusive SET is source-of-truth); (2) `FAILURE_BUCKET_SEVERITY_ORDER` versioned constant (Forge derives `primary` locally + deterministically, rule #6); (3) `mechanism`/`regime` free-`str | None` fields on `StrategyConfig` (`None`-default, hash-excluded, `grammar_version`/`source` template). Crucible owns the producer half + ingest-validates `mechanism`/`regime` against Forge's published vocab (quarantines unknown labels from C3, never a hard failure).
- **Forge forward-obligations (each flag-OFF, operator-gated, built when ve-supply clears):** (a) migrate the two raw-scalar channels to `pass/fail + failure_buckets`, shadow ≥2wk preserving the D231 per-family steering skill (ve +0.080 / trend +0.143), THEN Crucible hardens by construction (training-facing export dropping `value`/`threshold` first, `metrics` second); (b) the `(family × data-era)` freeze ledger — Forge owns (option a), keyed on the published metric-era boundary NOT `grammar_version`, and must NOT reuse `COLD_START_HYPOTHESES`' grammar-bump reset (wrong semantics for a false-discovery budget); family-id = C3 realized cluster once published (interim `hypothesis`, over-freezes conservatively); (c) a version-stamped, machine-readable `mechanism`/`regime` vocabulary artifact on the grammar's version cadence, shipped with/before the field goes live.
- **Why the bump is NOT done now (operator asked "if we need it, do it"):** it is the agreed-deferred coordinated step — Crucible must ship the producer half; Forge adoption needs `FORGE_EXPECTED_CONTRACT_VERSION` bump + fixtures + `forge check` + a **daemon restart** (a deploy, operator-only, D124); and it is sequenced behind ve-supply by the agreement just relayed. Editing `crucible_contracts` alone would create a schema half nothing populates. TRIGGER: operator ratifies + coordinates the contracts owner + Crucible producer → Forge preps adoption → operator restarts.

**Alternatives considered:** (1) Crucible owns the freeze counter (option b) — rejected; the freeze is a generation-side action and belongs next to Forge's generation logic (preserves the filter-not-generator posture). (2) Closed `Literal` for `mechanism`/`regime` — rejected; forces a contract bump per new mechanism = friction on the F2 growth axis; chose free-string + Forge-published closed vocab, validated at Crucible ingest.

**Files:** `STATUS.md`, this entry, `PROMPT_CRUCIBLE_GENERATION_DISCIPLINE_F1_F3{,_CONFIRM,_ACK}.md` (the three Forge relays, tracked; stay LIVE at repo root until the bump ships, then archive per the `crucible-handoff.md` lifecycle). No `src/`/grammar/config/contract change — design-only; reboot-safe.

**STATUS: design loop closed both sides; nothing built/deployed; daemon untouched (healthy, submitting). The contract bump + 3 Forge builds await the operator-ratified coordinated bump, sequenced behind ve-supply. Priority unchanged: the two flip preregs on a clean post-stall cohort, then the teed-up levers.**

---

## D244 — 2026-07-05 — Adopt `crucible_contracts` 1.24.0 (version-pin ONLY; feature consumption stays deferred per D243). RESTART-PENDING: latent D124 `extra_forbidden` stall until the daemon reboots onto 1.24.0.

**Spec section:** §13.5 contracts version pin (`core/contracts_check.py`); cross-system (`docs/tasks/crucible-handoff.md`).

**Crucible landed the D243 coordinated F1/F3/F4 bump (`crucible_contracts` 1.24.0, `0a0cd1c`; Crucible adoption `2f53029`) and notified via `FORGE_contracts_1.24.0_landed_2026-07-05.md` ("adopt on your own schedule"). Adopted the version pin; verified a live-safety implication that handoff understated.**

- **Pin bumped** `FORGE_EXPECTED_CONTRACT_VERSION` 1.23.0 → 1.24.0 (`contracts_check.py:79`); `uv.lock` refreshed to 1.24.0 (editable path dep). `forge check` green (`crucible_contracts: 1.24.0 OK`); 12 version-adoption tests + 49 consumer/reconcile tests + ruff green; no fixture pinned the literal. **VERSION-ADOPTION ONLY** — Forge imports/consumes NONE of the new surface (`GatedRun.failure_buckets`, `FAILURE_BUCKET_SEVERITY_ORDER`, `StrategyConfig.mechanism`/`regime`, `FORGE_VOCABULARY_FILENAME_TEMPLATE`); the F1/F3 feature builds stay DEFERRED behind ve-supply per [[D243]].
- **Live-safety finding (corrects Crucible's "daemon unaffected"):** true only for the runtime version check (`validate_schema_version` is major-only). FALSE for the parse path — `GatedRun.failure_buckets` is a new field on a PARSED gated-runs-export model with `extra="forbid"`. The running daemon (booted 17:05Z on 1.23.0, `NRestarts=0`) holds 1.23.0 models in memory → the moment Crucible's exporter republishes carrying the `failure_buckets` key, every reconcile fail-loops on `extra_forbidden` → §7.3 depth stall (the D124 trap; same class as the ~15h stall earlier today, D240). **Latent, not firing:** verified the newest export (`gated_runs_2026-07-06T010136Z.json`) still lacks the key → Crucible's exporter is pre-1.24.0 → live daemon currently healthy.
- **Fix = restart the daemon onto 1.24.0 (operator-gated). CONFIRMED SAFE any time, no ordering race:** 1.24.0 `GatedRun` parses BOTH the current no-field exports AND future with-field exports — `failure_buckets` is `default_factory=list` + auto-computed from `gate_results` (verified: `model_validate` on a current no-field export row yields the computed buckets). So Forge restarts proactively; no need to synchronize with Crucible's republish.
- **Deploy status:** pin COMMITTED (reboot-safe: tree pin 1.24.0 == installed 1.24.0). The RESTART is operator-gated + TIME-SENSITIVE vs Crucible's exporter republish — this is stall-prevention, NOT deferrable behind ve-supply like the feature builds. Relay `PROMPT_CRUCIBLE_CONTRACTS_1_24_ADOPTED.md` flags the `extra_forbidden` gap back to Crucible + offers an optional hold-the-republish courtesy.

**Alternatives considered:** defer adoption entirely behind ve-supply (per D243) — REJECTED for the version pin: the `extra_forbidden` trap makes the restart a stall-prevention, not a feature. Feature consumption itself stays deferred.

**Files:** `src/forge/core/contracts_check.py` (pin + D124 comment), `uv.lock`, `STATUS.md`, this entry, `PROMPT_CRUCIBLE_CONTRACTS_1_24_ADOPTED.md`. RESTART PENDING (operator).

**STATUS: pin adopted + committed; daemon still 1.23.0-in-memory (healthy — current export lacks the field); restart onto 1.24.0 needed SOON to pre-empt the latent `extra_forbidden` stall when Crucible's exporter republishes.**

**Follow-through (same day) — DEPLOYED 2026-07-06T01:57:31Z.** Restarted the daemon onto 1.24.0 via `deploy.md` (preflight full suite 1829 green; new PID 47590). Verified: clean startup (grammar_version=v22, registry_loaded, no traceback/SchemaVersionMismatch), **reconciled batches=1 newly_gated_total=9 on 1.24.0 — no `extra_forbidden`**, `forge healthcheck` OVERALL=OK (`contracts: pin == installed 1.24.0`). Latent stall CLOSED. Crucible had proactively HELD their gated-runs publisher (long-poll loop still 1.23.0-in-memory; verified export `gated_runs_2026-07-06T015505Z.json` emits no `failure_buckets` key) pending Forge's "daemon live" confirm (`FORGE_contracts_1.24.0_parse_safety_2026-07-05.md` §2); relay `PROMPT_CRUCIBLE_CONTRACTS_1_24_DAEMON_LIVE.md` clears them to restart the publisher any time (no rush, D243; the §3 `Restart=on-failure` residual edge is now moot — Forge parses both no-field and with-field exports).

**Coordination CLOSED (`FORGE_contracts_1.24.0_closed_2026-07-05.md`; ack `PROMPT_CRUCIBLE_CONTRACTS_1_24_CLOSED_ACK.md`).** Crucible deliberately keeps the gated-runs publisher on old (1.23.0) code — no consumer until the F3 bucket-training migration (behind ve-supply, D243), and restarting the DBProxy client risks wedging the db-writer accept loop; so `failure_buckets` will NOT appear in the export file until a future coordinated restart. **KEY LEARNING (for the F3 build):** the 1.24.0 `mode="before"` validator auto-computes `failure_buckets` from `gate_results` **on read**, so the migration consumes buckets with NO publisher restart — no plumbing dependency to pre-stage; Forge flags a coordinated restart only if the key is ever literally wanted in the file. Nothing owed either side; the D243/D244 F1/F3/F4 thread is fully closed.

---

## D245 — 2026-07-06 — INCIDENT: 1.24.0 asymmetric-upgrade inbox stall (100% submissions rejected ~13h) — Crucible inbox-watcher restart + Forge rejected-flush

**Spec section:** §7.3 (per-batch limiter) / inbox submit path (`INBOX_LAYOUT`); cross-system (`docs/tasks/crucible-handoff.md`). The submit-direction mirror of the D244 read-path trap.

**The incident.** From the D244 restart (daemon onto 1.24.0 at 2026-07-06T01:57:31Z) the daemon produced **zero accepted submissions for ~13h**. First post-restart batch `b381a83d` (submitted 02:10:28Z, 200 configs) had **all 200 rejected at Crucible's inbox** → the §7.3 per-batch limiter wedged (`0/200 gated; waiting for >=80%`, never clears because rejected configs never run→never gate). Surfaced only as a `no submission in 13.3h` healthcheck WARN whose block reason read like ordinary backpressure.

**Root cause — asymmetric 1.24.0 upgrade (the mirror of D244).** 1.24.0 ADDS `StrategyConfig.mechanism`/`regime` (default `None`). Forge on 1.24.0 serializes via `model_dump_json()`, which emits defaulted fields → every submitted config now carries `"mechanism": null, "regime": null` (verified in `submissions.config_json`). Crucible's `crucible-inbox-watcher.service` was still running **pre-1.24.0** in memory (`extra="forbid"`, no such fields) → `extra_forbidden` on all of them (verified in `inbox/errors/*.reason.txt`; Crucible's journal `inbox_parse_error` at 02:11:03Z matches the cutover to the second). Same D124 stale-in-memory-model class as D244, opposite direction: D244 fixed Forge READING Crucible's export (`failure_buckets`); this is Forge WRITING to Crucible's inbox, where Crucible's consumer holds the stale model. D244's close reasoned about the publisher (emit side of the read path) and never considered the inbox watcher (consumer of Forge's writes) needed the same restart.

**Third failure category.** Inbox-REJECTED in-flight (never ran) are in NEITHER `gated_runs` NOR `failed_runs`, so neither the reconcile join, the D240 failed-flush, NOR (promptly) anything but the 5-day aged-out flush retires them. Distinct from D240 (failed RUNS) and D052/D110 (aged-out).

**Resolution.** (1) Relay `PROMPT_CRUCIBLE_INBOX_1_24_REJECTING_SUBMISSIONS.md` → Crucible restarted `crucible-inbox-watcher.service` onto 1.24.0 at **2026-07-06T15:49:54Z** (`FORGE_contracts_1.24.0_inbox_watcher_restarted_2026-07-06.md`), validated against a real rejected payload; declined the Forge-side `exclude_none` fallback (keep the 1.24.0 contract both sides). (2) Forge cleared the stranded batch — `scratchpad/flush_rejected_inflight.py` (keyed on `inbox/errors/` config_hashes ∩ `status='submitted'`) retired the 200 `b381a83d` rows to `gated`+`_AGED_OUT_SENTINEL_RUN_ID` (same terminal marker as D052/D240) → in-flight 0 → restart (PID 720197, 15:54:09Z). (3) Verified end-to-end: fresh batch `b2f228f4` submitted=200, `inbox/errors/` flat at 3106 (delta 0 — accepted, draining into the runs table), `forge healthcheck` OVERALL=OK, `submission: submitting`.

**Follow-ups (recommended, not built).** (a) **Deploy discipline:** a contracts bump must restart BOTH directions' processes — Forge's submitter AND Crucible's inbox watcher — not just the read path. (b) **Observability gap:** the wedge was silent for 13h because a 100%-rejected batch looks identical to normal §7.3 backpressure; a healthcheck signal distinguishing "submitting-but-rejected" (e.g. `inbox/errors/` growth vs submissions) from healthy would surface skew immediately. (c) A durable Forge-side retire-inbox-rejected reconcile is possible but would MASK the skew — prefer the alert (b) so rejections stay loud. Inbox rejection is a contract-skew symptom, ~never in steady state, so (a)+(b) beat a silent auto-retire.

**Files:** `PROMPT_CRUCIBLE_INBOX_1_24_REJECTING_SUBMISSIONS.md` (relay + RESOLVED banner), `STATUS.md`, this entry. No src change (the fix was cross-system + a one-off flush). Related: D244 (1.24.0 adopt), D240 (failed-run flush), D124 (stale-in-memory-model class).

**STATUS: RESOLVED + VERIFIED 2026-07-06. Production flowing (fresh batch accepted). Priority returns to the two flip preregs on a now-genuinely-clean cohort (submissions after 15:54:09Z — the earlier post-D244 "clean cohort" was 100%-rejected, so the flip-prereg reminder's cohort-start moves to this restart), then the teed-up levers.**

---

## D246 — 2026-07-06 — `forge healthcheck` gains an inbox-rejection check (D245 follow-up (b))

**Spec section:** ops instrumentation (`cli/healthcheck_cmd.py`, D197 lineage). Implements the D245 follow-up (b): the 'submitting-but-rejected' wedge was invisible for ~13h because a 100%-rejected batch reads identically to ordinary §7.3 backpressure (`check_submission_progress` → generic "no submission in Nh").

**Change.** New pure check `check_inbox_rejections(recent_reject_count, *, warn, critical)` + gather helper `_count_recent_files(dir, pattern, now, window_hours)`, wired into `cmd_healthcheck`: counts `~/optbt_data/inbox/errors/*.json` (rejected submissions) with mtime within `--inbox-reject-window-hours` (default 6.0); WARN at `--inbox-reject-warn` (25), CRITICAL at `--inbox-reject-critical` (100 — a batch-sized burst = a skew). CRITICAL message points at the D245 fix (read `errors/*.reason.txt`; a contracts bump must restart BOTH directions' processes). Filesystem-only, no DB — consistent with the module's design (the live DB's RW lock makes it unreliable for a health probe).

**Design note.** The wedge produces a ONE-TIME rejection burst then goes quiet (the daemon wedges on the limiter), so a recent-mtime *window* (not an instantaneous state) is what catches it; 6h surfaces it well within the 24h submission-CRITICAL horizon while the burst is still in-window. Not the DB join (in-flight ∩ errors) — that's the most direct signal but needs the lock-contended live DB. No daemon restart required (the `forge-healthcheck` timer / manual runs pick up the CLI fresh); committed = reboot-safe.

**Verify.** New unit test `test_inbox_rejections_levels` (threshold ladder + message); `tests/unit/test_cli` 115 green; ruff + mypy-strict clean. Live `forge healthcheck` → `[OK] inbox_rejections: no recent inbox rejections` (correct: the b381a83d burst is ~18h ago, outside the 6h window), OVERALL=OK (11 ok). Follow-up (a) (contract-bump deploy discipline) folded into `docs/tasks/crucible-handoff.md` next; (c) declined (would mask skew).

**Files:** `src/forge/cli/healthcheck_cmd.py`, `tests/unit/test_cli/test_healthcheck.py`, `docs/MANPAGE.md`, this entry. Related: D245, D197.

## D247 — 2026-07-06 — Tech-debt sweep: retire never-read `forge.yaml` keys (§10.1 deviation) + dead `with_overrides`; architecture.md module-map completion

**Spec section:** §10.1 (config), operator-approved deviation. A four-lane read-only inventory (entry points / pipeline stages / config surface / external interfaces) found the codebase essentially free of dead code — zero orphan modules, CLI↔MANPAGE in 1:1 sync — with one genuine pocket: dead config surface in `forge.config`.

**Change (commit `afeedb4`, runtime-inert, NO restart needed).** (1) Retired the never-read §10.1 keys from schema + `config/forge.yaml`: `data_root`, `log_root`, `feedback.light_consumption_after_every` / `full_analysis_after_every` / `deep_review_after_every`. Evidence: `_resolve_run_defaults` (`cli/main.py`) consumes only db_path/crucible/enumeration/submission; feedback cadence is actually `--consume-feedback` every iteration; status/healthcheck take `--data-root` as their own CLI option (independent default `~/forge_data`). (2) Removed `ForgeConfig.with_overrides` — zero production callers (the CLI-over-yaml merge lives in `_resolve_run_defaults`, D025/D6); its 4 tests removed, a parametrized `test_load_rejects_retired_keys` characterization added (`extra="forbid"` now rejects the keys loudly). (3) `docs/architecture.md` module-map completed (commit `c1da76f`): ranking/ row gained queue/prior_promotion/calibration/drift/sequential_test/signal_key; feedback/ row gained proposal_writer/trade_concentration/promoted_patterns/stuck_state/preregistration/alpha_budget/threshold_proposer. (4) Two orphaned `scripts/__pycache__/*.pyc` (sources retired in D241) deleted — untracked, no commit.

**DESIGN.md §10.1 is NOT edited** (frozen v1 spec); this entry is the deviation record. `forge.yaml` loads once at daemon boot and none of the removed keys were ever consumed, so the running daemon is unaffected; next restart parses the new yaml with the new schema (verified directly: production yaml loads, all live values intact — batch 200, max_inflight 600, seed 42).

**Deferred to operator (flagged, not executed):** (a) `pre_filter_logs` + `promoted_patterns` DB tables are write-only in code (no SELECT anywhere) — kept pending a ruling on whether ad-hoc forensics uses them (logged in `OPEN_QUESTIONS.md`); (b) three completed one-time scripts (`backfill_verdicts.py` D111, `migrate_verdicts_decided_at.py` D117, `requeue_high_value_configs.py`) could take the `_archive/` treatment; (c) unused `crucible_contracts` surface (e.g. `validate_config_against_registry`, refit/portfolio symbols) is shared-package territory — a handoff note at most. Explicitly NOT touched: all dormant-by-design flag paths (`--orthogonal-yield`, `FORGE_EXPLORATION_HOLDOUT_FRAC`, gate-tail mode, `auto_tune.enabled: false`, emptied auto-tightenings, grammar-v3 predicates) — staged operator levers, not debt.

**Verify.** Full suite **1829 green** post-change; ruff + mypy-strict clean; production `forge.yaml` parse-checked against the new schema.

**Files:** `src/forge/config/forge_config.py`, `src/forge/config/__init__.py`, `config/forge.yaml`, `tests/unit/test_config/test_forge_config.py`, `tests/unit/test_cli/test_config_threading.py`, `docs/MANPAGE.md`, `docs/architecture.md`, this entry. Related: D024/D8 (the schema's origin), D025/D6 (resolver), D241 (prior health sweep).

## D248 — 2026-07-06 — Dead-weight sweep (5-lane, symbol-level): safe tier landed — 5 never-referenced symbols removed + 4 answered 1.24.0 relays archived; deeper lanes confirm D247's clean verdict

**Spec section:** none — tech-debt hygiene, the symbol-level follow-on to D247's module-level sweep. Operator: "sweep this repository for dead weight … return a deletion manifest," then "clean up the Safe items."

**Sweep.** Five parallel audit lanes over the whole repo — symbol-level exports (754 symbols, AST + word-boundary grep + `.sh`-heredoc/string-reference checks), one-way flags (all 6 Python env reads, 10 shell env params, every forge/prefilter yaml key, all CLI booleans vs the production unit lines), services/scripts/deps (9 units, 12 scripts, 14 deps mapped to invokers), doc link-graph (74 non-archive `*.md`), tests + CLI surface — every candidate evidenced by the last git commit referencing it. Verdict confirms D247: zero orphan modules/units/fixtures; the only genuinely dead code is below.

**Landed (safe tier only — zero references anywhere; runtime-inert, NO restart needed).** (1) `ThresholdProposal.baseline_width`/`.proposed_width` (`feedback/threshold_proposer.py`) — dead since introduction `b75426e` (D073); no commit ever added a caller. (2) `_RULE_CATEGORIES`/`_COST_ESTIMATES` (`grammar/models.py`) — phase-1 scaffolding (`fce3ee0`) shadowing the inline `Literal`s that never read them. (3) `fixtures_dir` fixture + `FIXTURES_DIR` (`tests/conftest.py`) — bootstrap `74f0ffa`; zero consumers ever (checked bare-name params, `usefixtures`, `getfixturevalue`). (4) Untracked `__pycache__` ghosts of the D190 king retirement (`src/forge/king/`, `tests/unit/test_king/` — dirs held only bytecode of sources deleted in `f79394a`) removed; no commit (untracked). The 4 `scripts/__pycache__/*.pyc` were left alone — their sources still exist (legitimate cache, initially mis-flagged). (5) Four ANSWERED 1.24.0 relays moved root→`_archive/` with ARCHIVED banners per the architecture.md root-file taxonomy: `…CONTRACTS_1_24_ADOPTED/_DAEMON_LIVE/_CLOSED_ACK` (thread CLOSED both sides, D244 — DAEMON_LIVE's banner preserves the still-standing publisher-restart clearance) and `…INBOX_1_24_REJECTING_SUBMISSIONS` (RESOLVED same-day, D245).

**Deferred (needs-owner tier, NOT executed; evidence in the session manifest).** ve `|move|` flag path (`volatility_event_absolute_move` schema+branch+tests — D235 already pre-authorizes "removed in a later cleanup"); `compute_hypothesis_reward_weights` (superseded D094→D105, last prod caller removed `7955aae`, 19 test refs go with it); `is_percentile_emitting` (never wired, promised consumers never materialized, 13 test refs); `scripts/probe_option_momentum_min_months.py` + `probe_results/option_momentum_min_months_sweep.json` (one-shot probe, purpose fulfilled in `4390ef2` v19/Q39 — same `_archive/` class as the D247(b) trio); `pytest-cov` + `[tool.coverage.*]` (never invoked since bootstrap); `docs/handoffs/PROMPT_FORGE_NEXT_ACTIONS.md` + `docs/reviews/2026-06-14-sunday.md` (bannered-historical stragglers outside the root sweeps' scope); `PROMPT_CRUCIBLE_GEN_LEVERS_VALIDATION.md` (stale HELD banner on the D215-closed thread — fix banner, then archive); `TABLE_NAMES` (`persistence/schemas.py`, test-only — relocate into the test). Doc bugs found, unfixed: MANPAGE:135 documents the H1 kill-switch under a nonexistent spelling (`--no-cross-sectional` vs the real `--no-cross-sectional-rank`); `FORGE_F3_RANKER` missing from MANPAGE's env-knob list (sibling `FORGE_QUALITY_RANKER` is there); `docs/proposals/long-straddle-strangle-v1-sleeve.md` lacks a resolution banner (thread closed 06-28).

**Verify.** ruff + `ruff format --check` clean on the 3 changed files; mypy --strict clean (101 files); full suite **1828 green + 1 pre-existing UNRELATED failure**: `test_expected_contract_version_matches_installed` — `../crucible_contracts` working tree carries **UNCOMMITTED 1.25.0** (validators change in flight; contracts HEAD is still 1.24.0 `0a0cd1c`), so the editable install reports 1.25.0 against our 1.24.0 pin. Not this change's doing; 1.25.0 adoption is its own operator-gated event when Crucible hands it off (D244/D245 ritual — restart BOTH directions). Daemon unaffected (1.24.0-in-memory since the 15:54:09Z boot; journal healthy 17:35Z, reconciled 188 newly gated). D104-class hazard noted: the dirty editable contracts tree means a reboot would silently pick up 1.25.0.

**Files:** `src/forge/feedback/threshold_proposer.py`, `src/forge/grammar/models.py`, `tests/conftest.py`, 4 relay moves + banners under `_archive/`, this entry, `STATUS.md`. Related: D247 (module-level sweep), D241 (archive sweep #2), D190 (king retirement), D235 (ve `|move|` drop), D244/D245 (the relays' threads).

---

## D249 — 2026-07-06 — Adopt `crucible_contracts` 1.25.0 pin (forward-compat helper); runner-side `other`-failure spike RESOLVED by runner restart

**Spec section:** §13.5 contracts pin (`core/contracts_check.py`); cross-system (`crucible-handoff.md`). Sequel to D244/D245; RESOLVES the D248 side-finding (uncommitted 1.25.0 → failing `test_expected_contract_version_matches_installed`). Numbered D249 after a concurrent-work D247/D248 collision (the operator committed D247 tech-debt + D248 dead-weight-sweep while this was in flight).

**What 1.25.0 is.** Adds `parse_forward_compatible(model_cls, data)` to `validators.py` — a tolerant RE-READ: when strict `model_validate` fails with ONLY `extra_forbidden` errors, it prunes the purely-additive unknown keys (by pydantic error `loc`, nested-safe), warns once per key-set, and retries. Changes **NO parsed model** (validators.py only; contracts suite 326 green / 100%). It's the durable fix for the D244/D245 additive-field trap class — a process behind the contract tolerates a new minor field instead of failing.

**The `other`-failure spike (diagnosed + resolved).** After Forge went to 1.24.0 (emitting `StrategyConfig.mechanism`/`regime`=null) and the inbox watcher was fixed to ACCEPT them (D245, 15:49Z), configs flowed to Crucible's backtest runners — which still held a **pre-bump model** and failed re-reading those fields, marking runs FAILED as `error_category: other`. Timeline confirms: `other` failures ran **15:58Z → 23:49Z** (≈88% of the clean cohort, 8,463 configs), starting ~4 min after Forge's 1.24.0 flow began and **stopping the moment `crucible-runner@{1,2}` were restarted onto 1.25.0** (both restarted 00:38Z; zero `other` after 23:49Z). This is the RUNNER-side (re-read path) sibling of D245's inbox-side (ingest path) trap — the third face of the same D124 stale-in-memory-model class, now across all three: Forge submitter (D244 read path), Crucible inbox watcher (D245 ingest), Crucible runner (D247 re-read). Forge's D240 failed-flush absorbed all 8,463 so the depth cap never stalled — good, but it masked the spike (motivating the D246 inbox-rejection healthcheck; a runner-failure-rate signal would be the analogous next add).

**Forge adoption.** Pin `FORGE_EXPECTED_CONTRACT_VERSION` 1.24.0 → 1.25.0 (`contracts_check.py`). `forge check` green (1.25.0 OK); 93 version/contract tests pass; no fixture pins the literal. **Unlike D244, the Forge daemon restart is DEFERRABLE** — 1.25.0 changes no parsed model, so the running 1.24.0-in-memory daemon has no `extra_forbidden` trap; pin-adopt now (clears the healthcheck WARN, reboot-safe), restart at leisure. Forge does not yet CALL `parse_forward_compatible`; wiring it into `feedback.consumer` reconcile (so a future skew self-heals on Forge's read side too) is a separate build worth doing.

**Open (not Forge's):** the `crucible_contracts` 1.25.0 change is still uncommitted WIP in that repo (operator to commit for reboot-safety). Crucible's inbox watcher remains on 1.24.0-era code (accepting fine; restart onto 1.25.0 is future-proofing, not urgent).

**Files:** `src/forge/core/contracts_check.py`, `STATUS.md`, this entry. Related: D244, D245, D240, D246, D124.

**STATUS: pin adopted + committed (reboot-safe). Forge daemon restart onto 1.25.0 DEFERRED (safe — no model change). `other` spike resolved (runners on 1.25.0). Pipeline healthy: submitting, accepted, no stall.**

---

## D250 — 2026-07-06 — Wire `parse_forward_compatible` into the export read path (contracts 1.26.0) — Forge reconcile self-heals on future additive fields

**Spec section:** §8.2 feedback consumer read path; §13.5 pin. Completes the D244/D245/D249 forward-compat arc (the operator's ask: "build the parse_forward_compatible").

**The build.** 1.25.0 added the `parse_forward_compatible` helper but nothing called it. 1.26.0 (`crucible_contracts` `86c8515`) wires it into the two export loaders Forge's reconcile re-reads each poll — `load_recent_gated_runs_from_export` + `load_recent_failed_runs_from_export` now parse each row via `parse_forward_compatible(GatedRun/FailedRun, raw)` instead of strict `model_validate`. So when Crucible ships a FUTURE additive export field (e.g. it finally republishes with `failure_buckets`), Forge's long-running daemon — holding its boot-time model — prunes the unknown key + warns once instead of fail-looping on `extra_forbidden`. This is the read-side (Forge-consumer) analogue of the fixes to the other two faces of the D124 stale-in-memory trap: D245 (Crucible inbox ingest) and D249 (Crucible runner re-read). The loaders are the correct seam — `parse_forward_compatible`'s own docstring scopes it to the tolerant RE-READ of already-strictly-validated data (NOT first ingest), and Forge reads exports ONLY through these loaders (hard rule #2). Byte-identical today: tolerance only triggers on `extra_forbidden`, and no parsed model changed since 1.24.0, so enumeration/submission determinism is untouched; genuinely-invalid rows still raise `QueryError`.

**Forge adoption + deploy.** Pin `FORGE_EXPECTED_CONTRACT_VERSION` 1.25.0 → 1.26.0. Unlike D249 (deferred restart), this deploy DOES restart the daemon onto 1.26.0 — the tolerant loaders only take effect in a fresh process, and this also finally moves the daemon off its stale 1.24.0-in-memory state onto current code. Safe + byte-identical (models unchanged 1.24.0→1.26.0). `forge check` OK (1.26.0); contracts suite 328 green (2 new fwd-compat loader tests).

**Files:** `crucible_contracts/queries.py` + `tests/test_queries.py` (1.26.0), `src/forge/core/contracts_check.py`, `STATUS.md`, this entry. Related: D244, D245, D249, D124.

**STATUS: DEPLOYED 2026-07-06 (daemon PID 3101697, on 1.26.0). Verify: uncontended suite 1829 green; clean startup (grammar_version=v22, no traceback); reconciled batches=1 newly_gated_total=198 (tolerant loaders parsed the live gated export); healthcheck OVERALL=OK (11 ok, contracts pin==installed 1.26.0, WARN cleared). Trap-class arc fully closed (D245/D249/D250).**

---

## D251 — 2026-07-06 — Flip preregs resolved on the clean cohort: #2 (exclude_regime_filter) CONFIRMED, #1 (cumulative_trading) INSUFFICIENT (kept on correctness)

**Spec section:** §5.3.6 / §5.3.7 prereg discipline (D208). Resolves `5082d332b26e` + `848a1f671392` on the clean post-runner-fix cohort (submissions ≥2026-07-07T00:38Z — the 88%-`other`-failure window before the D249 runner restart was discarded as biased; post-fix the real-gate rate is 90%, 1,432 decided in ~2h).

**Flip #2 (`5082d332`, signal_correlation.exclude_regime_filter) → CONFIRMED.** ve signal_correlation reject 58.2%→4.5% (of reached), ve survival 5.5%→15.2% (~2.8×), content redundancy still fires (4.5%>0). No ve component regression — ve component-rate was ~0 PRE-flip too (0.0033), so the headline component-rate dip (0.127→0.097) is the INTENDED ve mix-shift (ve share of decided 7%→18%), not degradation. book-PBO stays Crucible-side/pending (contribution export empty until first promotion). Supply thesis confirmed; the ultimate book-value question is unchanged/pending.

**Flip #1 (`848a1f67`, permutation_test.cumulative_trading) → INSUFFICIENT (flip KEPT).** Two findings: (1) **METHODOLOGICAL** — the controlled shadow-count can't re-measure a flip AFTER deploy: `shadow_null_cmd` loads the DEPLOYED `prefilter.yaml` as its prod baseline (`:181`), which is now already `cumulative_trading`, so flip-1's prod→cumulative comparison is cumulative-vs-cumulative → a degenerate net-0 (NOT a result; the table's ve −81 is the tool's flip-2 = the dropped `e1a43ba8` |move|). The valid controlled read was the PRE-flip D226 (showed up). (2) The post-flip clean cohort does NOT show the predicted per-family survival lift: trend 41.9%→40.0% (flat), event_momentum 91.1%→95.0% (up, tiny n), **volatility_event 44.5%→38.6% (DOWN — opposite the prediction)**; confounded by enumeration-mix + a 2h-vs-2d regime gap, so not a clean refute, but clearly not confirming, and ve (the key family) moved the wrong way. **Kept anyway** — flip #1 is ALSO a correctness fix (trading-day + cumulative vs the old single-calendar-day mode that dropped ~40% of Mon/Tue samples to weekends); "survival-lift not confirmed" ≠ "revert the bug fix." Dropped the ve-supply-lift expectation.

**Lesson (recorded):** a permutation-null shadow-count must be run BEFORE the flip (prod=pre-flip); post-deploy it's degenerate. A definitive post-hoc flip-1 read would need a one-off script scoring single_day vs cumulative on the SAME configs (offered, not run).

**Next-lever gating.** flip #2 confirmed clears part of the path, but gate-tail (`9063b405`) stays HELD until flip #1's status is settled — stacking a ranker re-wire on an unresolved prefilter flip repeats the confounding this resolution had to fight through. Sequence unchanged: settle #1 (keep-as-correctness, done) → then gate-tail → then `FORGE_EXPLORATION_HOLDOUT_FRAC`, one at a time.

**Files:** `config/preregistrations.jsonl`, `STATUS.md`, this entry. Related: D238/D239 (the flips), D226 (pre-flip shadow-count), D249 (runner fix that unbiased the cohort), D208 (prereg discipline).

---

## D252 — 2026-07-06 — FLIP: gate-tail ranker re-wire (prereg 9063b405) — P(component) gates eligibility, wf_p25 tail orders

**Spec section:** §8.6 quality lane / P1.1 (the hard-gate form). The teed-up lever after the D251 flip-prereg resolutions (flip #2 confirmed, flip #1 settled kept-as-correctness) cleared the sequencing hold.

**The flip.** `FORGE_QUALITY_RANK_MODE=gate-tail` + `FORGE_REWIRE_P_FLOOR=0.02` on the systemd UNIT file. Selects the P1.1 hard-gate form of the `--quality-rank` lane: P(component) GATES eligibility at the floor (0.02, the coded default the flip-gate was validated against) and the wf_p25 tail model ORDERS the survivors — the §6.2 composite is bypassed, matching the shadow eval's `gate_tail_rank_score`. Default `blend` (D193: `prior := P × tail_norm`) stays the code default; the env selects the re-wire. REVERT = delete the two Environment lines + `daemon-reload` + restart (byte-identical to blend).

**Flip-gate satisfied (the prereg's pre-commitment).** 9063b405 required the P1.2 flip gate MET at flip time: SPRT promote logLR **+15.45 / 2.77**, mean Δ **+0.344**, fresh-PASS streak **6/3** (n=6) — MET and durable (last7 all positive). Verified immediately before the flip.

**Deploy.** UNIT-file env change ⇒ `daemon-reload` (not just restart), then the deploy.md ritual: stop → uncontended suite → daemon-reload → start → verify the journal prints the gate-tail lane line. It changes the RANKING (which survivors submit), so the submitted-stream composition shifts — resolve 9063b405 LATER on the POST-FLIP cohort (rewire Δ = top-decile realized worst-quartile WF floor vs the blend baseline; data AFTER this deploy only). Now that the flip preregs are resolved (D251), stacking this ranker change no longer confounds them.

**Files:** `deploy/systemd/forge.service`, `STATUS.md`, this entry. Related: D193 (quality-lane blend), D251 (flip resolutions that unblocked this), D208 (prereg), D216 (the ORTHOGONAL_FAMILY_FLOOR env it sits beside).

**STATUS: DEPLOYED 2026-07-06 (PID 3539733). Verify: uncontended suite 1829 green; daemon-reload; clean startup; journal "quality_rank: wf_p25 GATE-TAIL ACTIVE (p_floor=0.0200) hard-gate (composite bypassed)" — flip reached the iteration (not BLEND); healthcheck OVERALL=OK (11 ok). Resolve 9063b405 on the post-flip cohort later. Next teed-up lever: FORGE_EXPLORATION_HOLDOUT_FRAC.**

---

## D253 — 2026-07-06 — Services audit: `forge-eod-check` RETIRED (timer disabled, units + script removed); the other 7 Forge units confirmed live-and-earning

**Spec section:** none — ops hygiene (D195–D199 lineage). Operator: "look at all the services, timers, watchers under Forge. What's redundant or useless or dead? forge-eod-check can probably go." **Numbering note:** initially self-assigned D249; a concurrent session landed D249–D252 (1.25.0/1.26.0 adoption, prereg resolutions, the gate-tail flip) while this audit ran → renumbered D253 pre-commit.

**Audit.** Forge owned 9 units. Verdicts: `forge.service` (the daemon) / `forge-backup` (04:00, D195) / `forge-healthcheck` (hourly, D197+D246) — KEEP, all firing on schedule. `forge-ranker-eval` (05:00, D149/D191/D192) — KEEP: its two streak clocks (`streak.jsonl`, `robustness_streak_wfp25.jsonl`) fed the SPRT decision that D252 just flipped on, and they stay the shadow==production monitor while the 9063b405 post-flip cohort reads out; cadence could drop after that resolves (operator's call, not taken here). `forge-eod-check` (21:00) — RETIRED, below. Watchers: Forge owns none (the daemon polls; Crucible owns the inbox watcher). Cross-system flag for a future relay: `crucible-meta-king-publisher.timer` still publishes daily (07:00) for Forge's king arm retired in D190 — likely retirable on Crucible's side. Claude-side crons (flip-condition `057aadf1`, the 2-day prereg reminder) are session-external and not auditable from a fresh session; both remain documented in STATUS.

**The retire case (evidence, not vibes).** `forge-eod-check` was a nightly headless-Claude (Sonnet) report-only session created 2026-06-10. (1) Its prompt had fossilized on the v17/2026-06-10 baseline — grammar is v22; the "drift reference" weights (`em=1.000 tc=0.813 …`) are three eras stale; the session compensated by reading memory + prior reports, but the tasked queries were fossils. (2) Its alerting duties are superseded mechanically: the hourly healthcheck's submission-stall WARN (D197), failed-run flush (D240), and inbox-rejections check (D246) cover the incident axis ~24× faster. (3) **The one real incident test, failed:** the 07-04 21:06 report ran three hours INTO the D240 stall, saw the exact signature (841 depth-cap blocks in 24h, message mix shifted 100% to the depth-cap variant), and dismissed it as "the benign §7.3 limiter working as intended" per its standing guidance — the stall ran ~13 more hours until the operator's morning session caught it. (4) Nothing consumes the reports (zero repo references read `~/forge_data/eod_checks/`). (5) Cost: one headless LLM session nightly on the production box (out-of-loop, so hard rule #5 was never implicated — just spend without a reader).

**Executed.** `systemctl --user disable --now forge-eod-check.timer` (before its 21:00 fire); removed the installed copies (`~/.config/systemd/user/forge-eod-check.{service,timer}` — regular-file copies, the install-method inconsistency the D248 sweep noted — and the vendored `~/.local/bin/forge-eod-check.sh`); `daemon-reload`; verified `list-timers` clean and 7 forge units remaining. Repo: `git rm deploy/systemd/forge-eod-check.{service,timer}` + `scripts/forge_eod_check.sh`; docs updated in the same commit (MANPAGE scripts table + timers paragraph, architecture.md, NEW_BOX_TRANSFER.md ×3 incl. the unit table, setup_new_box.sh install/enable/warn lists + header, `forge-backup.timer`/`forge-ranker-eval.timer` scheduling comments, `daily_ranker_eval.sh` comment). **Kept:** the 26 daily reports at `~/forge_data/eod_checks/` (2026-06-10 → 07-05) as historical data. Daemon untouched throughout — the timer is orthogonal to `forge.service` (which D252 restarted separately the same evening).

**Revert:** restore the three files from git, re-symlink into `~/.config/systemd/user/` (symlink this time), `systemctl --user enable --now forge-eod-check.timer` — but refresh the prompt's baseline first if ever revived.

**Files:** `deploy/systemd/forge-eod-check.service` (deleted), `deploy/systemd/forge-eod-check.timer` (deleted), `scripts/forge_eod_check.sh` (deleted), `deploy/systemd/forge-backup.timer`, `deploy/systemd/forge-ranker-eval.timer`, `deploy/setup_new_box.sh`, `deploy/NEW_BOX_TRANSFER.md`, `docs/MANPAGE.md`, `docs/architecture.md`, `scripts/daily_ranker_eval.sh`, this entry, `STATUS.md`. Related: D195–D199 (ops sprint), D203 (vendored install), D240/D246 (the healthcheck coverage that supersedes it), D248 (the sweep that queued this audit), D252 (the concurrent flip).

## D254 — 2026-07-06 — v23→v24 grammar bump: admit `vol_regime<2` to R1 (MR regime-gate loosening) + reweight the MR ranging gates; MR slice of the corrected signal-quality handoff (§2b.1)

**Spec section:** §3.5 R1 (mean_reversion regime-gate rule) + §5 enumeration policy. Classification: **rules-touching grammar bump** (`docs/tasks/grammar-change.md` #2 + a §3.5 rule LOOSENING #3/#4) — the first `rules:`-touching change since v22. **Operator-approved** (hard rules #1 §3.5-rule + #4 loosening; "Build full MR slice (approve R1)"). Source: `../Crucible/docs/handoffs/FORGE_signal_quality_champions_2026-07-03.md` §2b.1 (cross-sectional MR champion-hunt, 2026-07-06 revision) + its R1 note. This is the "MR experiment" the operator held for at [[D236]] time (the hold was correct — §2b.1 *reversed* the single-name §2b conclusions for Forge's actual xsect-MR generation).

**The change.** (1) **R1 loosening — admit `vol_regime` as a fifth accepted mean_reversion regime gate** (`custom_predicates.py` `_R1_VOL_REGIME_INDICATOR` + accept clause; `search_space.py` MR regime pool; `grammar.yaml` R1 comment + `evidence_to_relax`; `GRAMMAR.md` R1). vol_regime is the discrete vol tercile, gated **`< 2`** (exclude the HIGH-vol tercile). Crucible's real WF+CPCV xsect-MR sweep (§2b.1 `gate_mr2.json`, n=6): **vol_regime<2 beats the `rv_rank` cost gate by +0.244 CPCV-p25 in ALL 6 components** (~2.4×) — the biggest MR lever, and the one place MR wants a **regime** gate over trend's `rv_rank` **cost** gate. Added per the D107/D150/D167 R1-widening precedent (ADD not replace; R1 stays an OR). **Encoding (⚠️):** RAW discrete Int8 tercile → `regime_range=(2.0, 2.0)` always emits threshold 2.0, op `<`, `use_percentile` NEVER set (degenerate on a 3-value series); `< 1` starves the book. (2) **Sampler reweight** (`sampler.py` `_MR_RANGING_GATES`): DROP `hurst` from the 3× ranging-gate boost (§2b.1: hurst is null-to-negative as an MR gate, −0.27 vs rv_rank, 0/6 folds) and ADD `vol_regime`; `rv_rank`/`gamma_flip` stay boosted. hurst stays **R1-accepted** (weight 1.0, still explorable) — bias AWAY, not remove. (3) **Keep `zscore_returns`** as an MR directional — §2b.1 ranks it **#2 by the xsect backtest (0.442)**, so the single-name §2b "drop zscore_returns" ask is SUPERSEDED (it was an IC artifact; delegating this was why the hold mattered). (4) **bb_pct ranker preference** (§2b.1 xsect champion, 0.478) is delegated to the learned D106 directional weight — no structural directional-weight knob exists, and inventing one is un-asked machinery (D236 restraint); the better signal surfaces via the loop. (5) **D204 fold** (rules block already open): `grammar.yaml` R2 `evidence_to_relax` updated `{adx, hurst, rv_rank}` → `{adx, hurst, rv_rank, gamma_flip_distance_pct, market_state}` to match R2's real accepted pool (v11/D107 + v17/D131; GRAMMAR.md R2 was already correct).

**Version.** `grammar_version` v23 → **v24**. v24 = the complete trend+MR grammar upgrade; **v23 (the trend-only D236 intermediate) never shipped**, so a deploy is `v22 → v24` (the v23/D236 trend slice — sma_slope/ad_slope, chandelier, days_to_fomc — is fully contained). Archived `config/grammar_archive/v24.yaml`.

**Rationale + HONEST SCOPE.** MR is a **secondary book** — its ceiling here is ~0.42–0.66 CPCV-p25 (gate-only ~0.42) vs trend's ~0.83 (§2b.1) — and it sits in the **correlated core** ([[promotion-gate-tiers-and-constraint]]: mr is half the correlated core, zero dimensionality gain). So this is a **stream-quality lift, not a promotion unlock** (same §0 caveat as the trend swap). The value is real: the "xsect MR is null" prior was an IC artifact — the gated backtest is positive, and the `vol_regime<2` gate is a genuine +0.244 component-quality lever. bb_pct + vol_regime are the two levers; the gate matters most.

**Design choices.** (a) vol_regime pinned to a single threshold `2.0` (not a range) — the sweep is unambiguous (2 optimal, 1 starves) and vol_regime is discrete; sampling a range would just emit the starving `<1`. (b) hurst kept in R1 (not pruned) — the handoff says "keep in the OR but bias away," and existing hurst configs stay valid. (c) bb_pct via the learned weight, not a hardcoded bias (no directional-weight mechanism exists; D236 precedent for momentum_252). (d) Single v24 bump for the whole MR slice; the D204 R2 fix rides it (avoids a separate rules-touching bump per grammar-change.md's piggyback guidance).

**Verification.** TDD: `tests/unit/test_enumeration/test_mr_grammar_v24.py` (10 tests) + `test_r1_mean_reversion_accepts_vol_regime_gate` in `test_custom_predicates.py` (red→green); existing `test_r1_mean_reversion_accepts_hurst_gate` still green (hurst stays R1-accepted). Re-pinned: `test_v1_grammar` v23→v24; `test_pick_regime_learned_preserves_d150_on_dead_triple` (hurst→vol_regime — the boosted gate moved); `test_sampler.py` goldens `_COHORT`(idx 4) + `_REGIME`(idx 14) — **none==empty re-verified** (D104 flag-OFF byte-identity intact). Emission proof (seed 0, 6000 cands, live registry): `grammar_version=v24`; MR regime gates `vol_regime 231 / rv_rank 237 / gamma_flip 296 / iv_rank 231 / hurst 207` (vol_regime enumerated + boosted; hurst deweighted to baseline); vol_regime samples `(threshold=2.0, op='<', use_percentile=None)` 231/231 (raw, correct); MR directionals include `zscore_returns 134` + `bb_pct 110` (kept). grammar+enum+invariants **702 green**; ruff + `mypy --strict` (101 files) + both grammar hooks clean.

**STATUS: DEPLOYED 2026-07-07T15:05:50Z (v22 → v24; combined trend D236 + MR D254 slices), operator: "fold it in and deploy".** New daemon **PID 1280850** (`NRestarts=0`, active); journal verified — `grammar_version=v24`, `grammar_versions: recorded manual_bump row for v24`, `registry_loaded_from_export` (registry_hash a34b5cf4d7ee9419), NO traceback/SchemaVersionMismatch/GrammarVersionError; `forge healthcheck` **OVERALL=OK (11 ok, 0 warn, 0 crit)** (`contracts: pin == installed 1.26.0`). Ritual per `deploy.md`: preflight GO (deploy-surface clean + full suite 1829 green on 1.26.0) → stop → ff-merge `5237d75..07c7aaf` in the live tree (branch⊇main, clean FF; operator's in-flight `fable-audit/README.md` + untracked docs left untouched) → restart. **This deploy also lands v23/D236 (the trend slice — sma_slope/ad_slope, chandelier, days_to_fomc window) which had never shipped** — so production goes straight `v22 → v24`. Numbering: authored as a working D247, **renumbered D254** (main had used D247 for its tech-debt sweep). **Also folded (`1df0dd9`, byte-identical): §2c.1 (2026-07-07)** — Crucible RETRACTED the vol-event DIRECTION ask (call_wall/put_wall refuted, triple-confirmed); no grammar change (Forge never built a VE-direction lever), only a days_to_fomc comment correction (the window rides the magnitude timer §2c.1 affirms, not direction). **⚠️ Strategy flag:** §2c.1 (single-name VE direction refuted, near-zero-trade) is in tension with the "single-name vol_event = the in-v1 promotion path" thesis — recorded for the roadmap, does not affect this trend+MR deploy. **NEXT:** relay `v22→v24` + this timestamp to Crucible for `crucible funnel --compare v22 v24`; watch the first UNBLOCKED batch's mix (vol_regime MR gate + chandelier trend exits should appear). Deploy landed mid-gate-tail cohort (D252) per operator's go — that cohort's attribution now also carries the grammar bump.

---

## D255 — 2026-07-06 — Probe: gate-tail does NOT starve useful ve → KEEP (no carve-out); light ve-supply monitor set

**Spec section:** ranking §8.6 / P1.1. Data-driven follow-up to the D252 gate-tail flip after the observation that ve submission share fell 18%→8%.

**The worry + the correction.** Initial read: gate-tail's `P(component) >= 0.02` eligibility gate excludes ve (I'd taken ve's *realized* component-rate ~0.003 as its *predicted* P). WRONG. Probe on `shadow_scores.model_score` (the logged per-config P): ve's PREDICTED P has real spread — median 0.024, p90 0.13, max 0.32; **54.7% of ve clears the 0.02 floor** (vs trend 84.6%, mr 64.3%). So gate-tail selects WITHIN ve, it doesn't exclude the family.

**Decisive probe — do the ve that MATTER clear the gate?** Of 485 realized ve COMPONENTS (joined to their predicted P), **90.3% clear the 0.02 gate** (median P 0.139); the 19,982 ve REJECTS have P median 0.0099, only 39% clearing. So P(component) is genuinely predictive of ve clearance — gate-tail keeps ~90% of the ve that become components and cuts the reject-bound ve. **The carve-out is NOT necessary; gate-tail is trimming ve that wouldn't have contributed, not the decorrelation supply.** (Also confirmed the gate's own rationale: `model.py` notes P is ANTI-correlated with the WF floor, so P gates eligibility and never orders — hence low weight on ve *volume* but preservation of ve *components*.)

**Decision: KEEP gate-tail. No carve-out. No revert.** My earlier revert recommendation was built on the wrong premise the probe overturned. Residual (weaker) concern: gate-tail's tail-ORDERING + the 200-slot cap still cut ve volume, and robustness ≠ decorrelation — but that's second-order on ve that would mostly clear anyway.

**Monitor (light, count-based).** `scratchpad/monitor_ve_supply.py` — tracks ve components/day (NOT rate: gate-tail keeps higher-P ve so the RATE may rise; the book wants ve component COUNT). **Baseline (blend era 07-02..04): 5.4 ve components/day** (13 comps / 3993 decided, rate 0.0033). Gate-tail window still too small to read (2 comps in ~hours). **Trigger: revisit the carve-out only if gate-tail-era ve components/day sits materially below ~5.4 once it has ~1-2 days of decided ve.** A scheduled nudge (~2-3 days) to re-run it accompanies this.

**Files:** `scratchpad/monitor_ve_supply.py` (untracked ops tool), `STATUS.md`, this entry. Related: D252 (the flip), D216 (ve supply), D251 (flip preregs), D193 (blend).

---

## D256 — 2026-07-07 — FLIP: exploration holdout MVP (FORGE_EXPLORATION_HOLDOUT_FRAC=0.05, prereg 61837dd2)

**Spec section:** §6 ranking / P3.3-B7 (learned-audit). The last teed-up lever; the natural partner to the D252 gate-tail flip.

**The flip.** `FORGE_EXPLORATION_HOLDOUT_FRAC=0.05` on the systemd unit. Reserves ~5% of each batch (10 of 200) as a SEEDED RANDOM draw from the prefilter-survivors the ranker did NOT pick — it REPLACES rank slots (total submitted unchanged), tagging those rows `selection_mode='holdout'`. Composes with gate-tail: gate-tail selects the top (n−holdout_n), the holdout adds holdout_n random non-selected. Clamped to [0, 0.10]; unset/0 = byte-identical. REVERT = delete the line + daemon-reload + restart.

**Why (the censored loop).** Every learned system (F3 P(component), wf_p25 tail, the estimand) trains on Forge's SUBMITTED configs — but Forge only submits what the ranker LIKED, so the models never get outcomes for the region they score low, and can't learn where they're wrong. Under gate-tail (a hard P-gate) this is sharper: if the F3 ve-P ever drifts low, gate-tail excludes ve → no fresh ve labels → the exclusion self-reinforces. The random holdout is the insurance: a trickle of ranker-bypassing submissions keeps unbiased labels flowing (and incidentally keeps some ve flowing regardless of the ranker). NOT decorrelation-targeted — biasing the draw would re-introduce the very bias it removes; targeting decorrelation is an enumeration-floor job (D216), targeting *uncertainty* would be the principled v2 (deferred).

**Fraction choice.** 0.05 (half the 0.10 cap) — conservative MVP: establish non-harm first; raise toward 0.10 later if the ranker-vs-random A/B wants more power. 10 held-out/batch accrues ~enough over 1-2 days for the component-rate comparison.

**Prereg 61837dd2 (cut 2026-07-07T22:49Z).** Predicts: ranked configs realize a HIGHER component-rate than the random held-out configs (the ranker beats random) AND the ~5% dilution keeps overall component-rate >= (baseline − ~0.006). Resolve on post-flip data by `selection_mode` (ranked vs holdout) + overall vs the pre-holdout baseline. If held-out >= ranked, the ranker is no better than random — a red flag worth surfacing.

**Deploy.** UNIT-env change ⇒ daemon-reload + restart (deploy.md ritual). Verify the journal prints `exploration_holdout: N of M submitted (frac=0.050, ...)` — flip reached the iteration (D185 anti-inert).

**Files:** `deploy/systemd/forge.service`, `config/preregistrations.jsonl`, `STATUS.md`, this entry. Related: D252 (gate-tail — the reason this matters now), D216 (ve supply / enumeration floor), D208 (prereg), the learned-systems review (the "censored loop" gap this closes).

**STATUS: DEPLOYED + VERIFIED 2026-07-07T22:54:22Z (PID 2404500). Journal shows the full chain — f3_ranker ACTIVE → GATE-TAIL ACTIVE → "exploration_holdout: 10 of 200 submitted (frac=0.050, seeded bypass of the ranker)" — so the batch is 190 gate-tail-ranked + 10 random holdout; flip reached the iteration (D185). healthcheck OVERALL=OK. NOTE: the deploy's uncontended suite surfaced 2 PRE-EXISTING v24 stale goldens (cohort/regime cold-start byte-identity, D254 fallout, NOT this change) — regenerated in a separate commit after verifying flag-inertness (none==empty) still holds; full suite 1862 green. Resolve prereg 61837dd2 on the post-flip cohort (ranked vs holdout component-rate). The teed-up lever program is now COMPLETE.**

---

## D257 — 2026-07-08 — v25: zscore_reversion_exit DROPPED from mean_reversion (inert pair exit; Crucible autopsy)

**Spec section:** §3.5 S5 (exit framework) — enumeration-policy bump (`grammar-change.md` #2, `rules:` text untouched). Source: Crucible handoff `FORGE_inert_pair_exits_2026-07-08.md`.

**The defect.** `zscore_reversion_exit` (and `convergence_exit`) read `ctx.pair_spread_zscore`, populated ONLY by the pairs backtester (`relative_value`). On single-name / xsect templates that field is None every bar, so the exit is STRUCTURALLY INERT — 0 firings, no threshold makes it fire. Crucible's trade autopsy: the top honest-pool MR component (`81178ab6e7…`, cpcv-p25 2.166) declared it with 0 firings in 314 trades; its positions closed by the monthly `overlay_roll` instead.

**Scope (narrower than the handoff's generic framing).** In Forge's `_S5_HYPOTHESIS_EXITS`, `convergence_exit` was ALREADY relative_value-only (no change). Only `zscore_reversion_exit` was mis-scoped — present in BOTH `relative_value` (correct) and `mean_reversion.required_from_set` (inert). Fix = drop it from mean_reversion only → `(time_stop, target_exit)`. It stays valid on relative_value.

**⚠️ Open caveat (target_exit share).** Removing it shifts its ~1/3 share onto `target_exit`, which Crucible's SAME handoff flags as HURTING the MR book (D333, "breaks the book" — caps the convex right tail). The "what should MR declare instead" question is left OPEN pending Crucible's `probe_results/exit_timestop_sweep.json` (trailing-stop + time_stop sweeps). This entry ships the correctness fix only; a follow-up may revisit MR's exit distribution on that evidence.

**Feedback invalidation (handoff ask #2) = no-op.** Forge's feedback keys on HYPOTHESIS, never exit-id (`rejection_weights.compute_hypothesis_*`), so there are no per-exit learned weights to null; the MR hypothesis reward stayed honest (the inert-exit configs really did trade via the roll).

**Goldens.** The exit-set change (3→2 options) alters the post-exit rng draw for MR configs, so `_REGIME_GOLDEN_PRE` moved at seq positions 11 & 14 (both MR). Re-pinned after re-verifying the flag-inertness invariant (`none_run == empty_run`) under v25 — only the absolute sequence moved, hard rule #6 intact (the v25 bump licenses it). Cohort golden unaffected.

**Files:** `grammar/custom_predicates.py` (_S5 table), `tests/unit/test_enumeration/test_sampler.py` (new `test_d257_*` invariant + golden re-pin), `docs/GRAMMAR.md` (MR exit row), grammar v25 bump + archive. Related: D071 (S5 schema), D236 (exit-drop precedent). Shipped with D258 under the single v25 bump.

**STATUS: DEPLOYED + VERIFIED 2026-07-09T00:14:11Z (ff-merge `0559239`; forge.service on grammar_version=v25, NRestarts=0, no traceback / SchemaVersionMismatch). `_REGIME_GOLDEN_PRE` moved as predicted; preflight ran 1866 green. Shipped with D258 + the folded contracts 1.27.0 pin under the single v25 bump.**

---

## D258 — 2026-07-08 — v25: days_since_jump event-frequency VETO — optional 2nd regime gate (Crucible; dormant-until-registry)

**Spec section:** §3.5 S3 (≥1 regime gate) + R2 — enumeration-policy bump (`rules:` untouched). Source: Crucible handoffs `FORGE_days_since_jump_indicator_2026-07-08.md` + `FORGE_dsj_v25_CONFIRMS_REPLY_2026-07-08.md` (all 3 confirms verified against their snapshot build).

**What.** `days_since_jump` = trading days since the underlying's last |c2c return| ≥ 0.05, saturated at 252. Wired as an OPTIONAL SECOND `regime_filter` on `trend_continuation` (single-name + xsect), op `<`, threshold on the confirmed flat plateau 30–65 td. It VETOES "dead tape" (no ≥5% move for N+ td) where the trend champion's theta-bleed losses cluster — a center-for-tail trade the worst-quartile gate rewards (engine probe: maxDD halves, CPCV-proxy p25 2.5×; known melt-up blindspot documented in the handoff).

**Structural: it required a 2nd regime gate (Forge emitted one).** The validated champion form is dsj ANDed on top of the hurst/adx trend gate. §3.5 R2 requires a trend-strength gate (dsj does NOT satisfy R2), and S3 permits "≥ 1" — so dsj must be ADDITIVE, not a replacement. Forge's sampler emitted exactly one `sig_regime`; the validators (R2, C1) were already plural-aware, so the change is localized to the sampler: an optional 2nd `sig_regime` drawn LAST.

**Confirms (Crucible, verified against `build_registry_snapshot()`):** family = `volatility` (so C1 gives the dsj-XOR-`rv_rank`/`vol_regime` exclusion automatically); version = 3 (`min_bars_required` 253); threshold set [30,45,65] = their probe arms → Forge sweeps the plateau continuously via `regime_range=(30,65)`, matching the day-count gate `days_to_fomc`.

**Dormant-until-registry (byte-identical cold path).** The veto pool intersects `_R2_TREND_VOLATILITY_VETO_INDICATORS = (days_since_jump,)` with `registry_ids`, so it is EMPTY until Crucible publishes the snapshot serving dsj. The sampler's `if veto_pool` guard then short-circuits BEFORE any `rng.random()` (the H1 rank-combiner pattern) → zero rng consumed, cold-start byte-identical (hard rule #6; verified — existing goldens unchanged after the wiring). When the registry serves it, registry_hash rolls (a legitimate sequence change) and the dsj-active goldens get re-pinned against Crucible's stated hash on their ping (~1 day).

**C1-safe by construction.** The veto is added only when NO existing signal is volatility-family — the primary regime gate (rv_rank/vol_regime) OR the vol_target X1 chain (realized_vol) — since dsj is volatility. (A first-cut guard checked only the regime gate; `test_d258_*` caught the realized_vol-chain collision.) `_DSJ_VETO_SHARE=0.5` mints both veto and non-veto arms so the honest campaign compares them; feedback-tunable later.

**Path B deferred to v26.** Crucible's `dsj_swap` research arm (dsj REPLACING the vol-level gate) is in their runner; if it wins, that is the evidence for a v26 arm where dsj competes as the PRIMARY volatility-slot gate. Nothing for Forge now.

**Files:** `grammar/custom_predicates.py` (veto table), `enumeration/indicator_thresholds.py` (dsj spec), `enumeration/search_space.py` (veto pool + SearchSpace field), `enumeration/sampler.py` (2nd-gate draw + C1 guard + share), `grammar/signal_horizon.py` (horizon entry), `tests/unit/test_enumeration/test_sampler.py` (`test_d258_*`: dormancy, active, scope), `docs/GRAMMAR.md` (R2 note), grammar v25 bump + archive. Relay: `PROMPT_CRUCIBLE_DSJ_V25_CONFIRMS.md`. Related: D077/D107/D131 (R2 gates), D254 (goldens process). Shipped with D257 under the single v25 bump.

**STATUS: DEPLOYED + VERIFIED 2026-07-09T00:14:11Z (v25 live; dsj DORMANT on `registry_hash=1456268f3db3995e` — correct, the live registry lacks the id, so the veto draws no rng and cold-start is byte-identical). EMISSION gated on Crucible's registry-live ping (~1 day), which states the registry_hash for re-pinning the dsj-active goldens. Path B (dsj-as-primary) deferred to v26.**

**ACTIVATED 2026-07-09 (no dormant window materialized).** Crucible's registry has served `days_since_jump` since `registry_snapshot_2026-07-09T00:06:43Z` (family `volatility`, version 3, lookback 252 — matches the `_v25_registry` test fixture); every snapshot since carries it. The live daemon's computed `registry_hash` rolled `1456268f3db3995e` (deploy, dsj-absent) → `2e2499a2b07947f9`, so the veto is emitting on `trend_continuation` (50% arm share) ~1 batch after deploy — Crucible had already published dsj by 00:06Z, so the expected "~1-day ping" never applied. **The "re-pin against Crucible's stated `registry_hash`" plan is VOID:** Crucible confirmed (`FORGE_ivol_lo_family_answer_2026-07-09.md`) they do **not** compute/publish a `registry_hash` — the canonical artifact is the timestamped snapshot file; Forge hashes the content. So the dsj-active golden is pinned against the **deterministic `_v25_registry` fixture** instead: `_REGIME_GOLDEN_DSJ_ACTIVE` + `test_d258_dsj_active_cold_start_golden` (`tests/unit/test_enumeration/test_sampler.py`), which legitimately diverges from the dormant `_REGIME_GOLDEN_PRE` (the veto eligibility rng draw is consumed on eligible trend configs — the licensed sequence change) while the dormant path stays byte-identical. Test-only; no daemon impact. The v26 `ivol_lo` MR gate touches the same veto block and will re-pin this golden.

---

## D259 — 2026-07-09 — INCIDENT: ranker-eval starved by full /tmp (58h stale models) → cleaned + retrained + healthcheck `tmp_headroom` guard; gate-tail prereg CONFIRMED

**Spec section:** ops instrumentation (`cli/healthcheck_cmd.py`, D197/D246 lineage); the daily ranker-eval (`scripts/daily_ranker_eval.sh`, D191/D192).

**Finalized gate-tail (the "flip it on" ask).** Resolved prereg `9063b405` → **confirmed**: flip-gate precondition MET at flip time (streak 5/3 at the 07-07T03:22Z flip; 7/3 now, mean Δ +0.351), post-deploy rewire Δ = +0.390 (the 07-07T12:19 checkpoint). Per the prereg's literal terms (post-deploy Δ>0; k≥3 was the *flip-gate* bar, not a resolution bar). Gate-tail stays live + kept (D255). Only 1 post-flip checkpoint exists because of the incident below.

**The incident.** `forge healthcheck` was **CRITICAL — models 58h stale**. Root cause: `forge-ranker-eval` (daily 05:00, trains F3 + wf_p25 AND appends the rewire/drift checkpoints) had **failed every run since 07-07** on `cp: error writing '/tmp/…': Disk quota exceeded` — it snapshots the live forge.db to /tmp (the DB holds an RW lock) and /tmp was full. That is also why there were no 07-08/09 rewire checkpoints. **The /tmp bloat was self-inflicted: four 5.5 GB forge.db snapshots I left behind during the D255 ve probing** (ad-hoc `cp forge.db /tmp/…` with no cleanup trap). `PrivateTmp=no` on the eval service confirms it shares /tmp with those leftovers. The eval script itself is clean (`trap cleanup EXIT` removes its own snapshot on every path); the daemon was unaffected (models load fine; only training was blocked).

**Fix.** Cleaned the 4 stale snapshots (/tmp 73%→37%, freed 22 GB) → `systemctl start forge-ranker-eval.service` to retrain immediately (the cp succeeds with room). Models refresh + the rewire clock resumes.

**Prevention (the operator's pick — proactive over reactive).** New healthcheck `check_tmp_headroom`: `/tmp` free as a MULTIPLE of the forge.db size (ratio, so it scales as the DB grows), WARN below `--tmp-warn-ratio` (5×), CRITICAL below `--tmp-critical-ratio` (3.5×). Generous defaults because the incident failed at ~3.3× raw free (a quota effect below the physical free). Filesystem-only, no daemon restart (the CLI/timer picks it up). This alerts on the CAUSE (thin headroom) *before* the eval breaks, vs the `model` check that only CRITs ~2 days later on the *symptom*. New unit test `test_tmp_headroom_levels`; MANPAGE → twelve checks. (Considered but declined: a self-cleaning snapshot helper for manual probes — the eval already self-cleans, so the only gap is human discipline, which the alert now backstops.)

**Process lesson (mine):** clean up large /tmp snapshots as I go — leaving them is what starved the eval. This check makes that failure loud instead of silent-for-2-days.

**Files:** `src/forge/cli/healthcheck_cmd.py`, `tests/unit/test_cli/test_healthcheck.py`, `docs/MANPAGE.md`, `config/preregistrations.jsonl` (gate-tail resolve), `STATUS.md`, this entry. Related: D246 (inbox_rejections check), D252/D255 (gate-tail), D197 (healthcheck), D191/D192 (ranker-eval).

**STATUS: RESOLVED. Retrain completed 2026-07-09T22:35Z (exit 0) → model FRESH, the 58h-stale CRITICAL cleared; tmp_headroom OK (6.6x); healthcheck committed a51d374 (suite 1867 green). gate-tail prereg confirmed. Residual: a MARGINAL wf_p25 drift WARN (latest -0.002 vs +0.252 trailing — one noisy checkpoint on the weak-IC lane after the 2-day eval gap; barely over the 0.25 threshold; watch the 07-10 eval, don't act). Holdout prereg (61837dd2) still deferred (07-09+ nudge).**

---

## D260 — 2026-07-09 — Vectorized the learned-model trainer with numpy (§8 F2/F3). The ~250k-row honest era outgrew D132's "10k-row" pure-Python premise → the daily ranker-eval spent ~15 min / 15 G single-core CPU in the IRLS fit alone. numpy makes it seconds with fp-identical math. A feedback-change (per `docs/tasks/feedback-change.md`), not a grammar/loosening.

**Trigger (operator: "ranker-eval is slow").** Profiled `forge-ranker-eval` (21 min CPU ≈ 21 min wall = single-core-bound, 15.4 G RAM peak). The cost is entirely the pure-Python model fits, and they grow with the dataset: the verdict IRLS runs on **N=250,533 rows × d=106 features**, so each Newton step's Hessian accumulation is O(N·d²/2) ≈ 1.4 B multiply-adds, ×~10 iters ≈ **14 B pure-Python ops**. D132 chose pure Python explicitly ("zero new deps") but sized it for a **10k-row window** — `build_dataset` never capped (just `ORDER BY decided_at`), so the honest era grew 25× past that premise. `build_dataset` itself is only ~18-22 s (NOT the bottleneck). 61/106 features are one-hot ids that standardization densifies, defeating the `xj==0` sparsity fast-path.

**Change (numpy = linear algebra only, NO RNG — rule #8 bans `np.random`, not BLAS; [[ml-allowed-in-loop-not-llms]]).**
- `_fit_irls` — the triple-loop Hessian/gradient → `Xaᵀ diag(w) Xa` / `Xaᵀ(y-p)` with a leading ones column for the unpenalized intercept; identical math, `_PROB_CLIP` weight floor unchanged.
- `_solve_ridge` — normal equations `(XᵀX+λI)β=Xᵀy` vectorized; `_standardize_design` now builds the `(N,d)` float64 **ndarray directly** (never the list-of-lists → the 15 G peak becomes ~0.3 G).
- `_solve_linear` (pure-Python Gaussian elimination) → `_solve` (`np.linalg.solve`); re-raises `ValueError("singular system…")` so callers' error handling is unchanged.
- **Scoring paths (`score_features` / `score_robustness`) UNTOUCHED** → the daemon (which only scores, never trains) is byte-identical; `calibration.platt_fit`'s `_fit_irls` signature preserved (list-in, tuple-out; converts internally).

**Determinism preserved.** Two trains on the same frame → byte-identical artifact (invariant `test_training_is_deterministic_byte_identical` green); numpy CPU matmul is deterministic on a fixed machine. No golden coefficient is pinned — the only change vs the old impl is fp-level summation-order drift, and models retrain daily anyway.

**Validation (old-vs-new on a live 251,141-row snapshot, identical `build_dataset` frame).** Verdict `max|Δcoef|=5.6e-13`, robustness `9.7e-10`; metrics identical to 11-13 sig figs (auc 0.906144899748 vs …919, etc.). **Full-frame fits: 17.6 s verdict + 2.6 s robustness** (was ~15-18 min pure-Python) → the eval's 21-min CPU collapses to ~1 min. Suite: 1866 pass (the lone red = concurrent contracts **1.28.0** `idiosyncratic_vol` bump vs Forge's 1.27.0 pin — minor, no runtime halt, operator's ivol work, NOT touched here).

**Deploy posture.** Training-only behavior; daemon scoring unchanged → **no restart required**. numpy added to the venv (`pyproject.toml` `numpy>=1.26,<3`, installed) so a reboot loads `model.py` cleanly. The next 05:00 `forge-ranker-eval` (or a manual `systemctl start`) picks up the fast path via editable install.

**Files:** `src/forge/ranking/model.py`, `pyproject.toml`, `STATUS.md`, this entry. Related: [[D132]] (F2 pure-Python origin), [[D191]]/[[D192]] (wf_p25 robustness head), [[D149]] (F3 wiring), [[D259]] (the /tmp-headroom guard from the same eval-slowness thread).

**STATUS: COMMITTED (`a66af5a`) + CONFIRMED IN PRODUCTION. Manual `forge-ranker-eval` at 2026-07-09T23:22Z ran in **1 min 30 s wall** (was ~21 min); CPU 1286 s → 243 s (numpy spreads across ~2.7 cores via BLAS); memory 15.4 G → 11.4 G (now dominated by `build_dataset`, not the fit). Trained+published verdict (251,342 rows, auc 0.833) + robustness (199,900 rows, r2 0.207) — matching the offline validation — streaks updated, no errors / no contracts halt (minor 1.28.0 gap doesn't halt). `model: fresh 0.0h` → the D259 staleness CRITICAL fully cleared. The residual `wf_p25 drift` WARN (latest -0.005) is the same known-weak-IC lane and is provably NOT from this change (models fp-identical, max|Δcoef| 9.7e-10).**

## D261 — 2026-07-09 — INCIDENT + FIX: adopt contracts 1.28.0 (`idiosyncratic_vol` family) — the daemon was failing every poll on the reclassified registry

**Spec section:** §13.5 (contracts pin) — a dependency-version adoption, NOT a grammar/enumeration change. Source: Crucible `FORGE_ivol_lo_family_answer_2026-07-09.md` (their reply to `PROMPT_CRUCIBLE_IVOL_LO_MR_GATE.md`).

**Incident.** Crucible published contracts 1.28.0 (adds the family-literal value `idiosyncratic_vol`) AND a registry snapshot USING it (`registry_snapshot_2026-07-09T234324Z.json`, `ivol → idiosyncratic_vol`, live 23:43Z) before Forge adopted 1.28.0. The running daemon held contracts **1.27.0** in memory, whose `family` Literal lacks `idiosyncratic_vol`, so from 23:43Z **every** enumeration poll failed: `ValidationError: RegistrySnapshot … Input should be 'trend', … 'post_event_drift' [literal_error, input_value='idiosyncratic_vol']; continuing next poll`. The daemon did not crash (the version check only raises on MAJOR mismatch, and the loop swallows per-iteration errors) — it was a SOFT outage: alive, healthcheck-green on process liveness, producing nothing. This is the asymmetric-upgrade trap (D245 class) on the **registry-read** face; `parse_forward_compatible` (D250) does NOT cover it because an unknown enum VALUE in a known field is a `literal_error`, not an `extra_forbidden` prunable field. (D260's 23:22Z "1.28.0 gap doesn't halt" was correct then — the offending snapshot went live 21 min later.)

**Fix.** Bump `FORGE_EXPECTED_CONTRACT_VERSION` 1.27.0 → 1.28.0 (`contracts_check.py`); restart so the daemon loads the installed 1.28.0 (Literal now accepts `idiosyncratic_vol`) → the live registry parses again. `uv.lock` already recorded `crucible-contracts 1.28.0` (editable path dep). **Purely additive, enumeration BYTE-IDENTICAL:** the only 1.28.0 delta is the one family value; `ivol` is not enumerated by Forge (absent from the threshold table + every regime/directional pool), and `rv_rank`/`vol_regime`/`realized_skew` stay `volatility`, so no config Forge builds changes and no C1/family-guard result moves — NO grammar bump (grammar stays v25). Precedent: D249 (1.25.0 adopt), D250 (1.26.0), D254 (1.27.0 fold).

**Scope boundary.** This adopts the pin ONLY. The `ivol_lo` MR grammar wiring (extend the D258 veto machinery to `mean_reversion`, generalize `_DSJ_VETO_FAMILY` to the veto's own family, add the `ivol` threshold spec, grammar v25→v26) remains deferred + operator-gated — deliberately NOT rushed into an incident hotfix. Bundled in the same restart: the D258 dsj-active golden (test-only) + docs.

**Files:** `src/forge/core/contracts_check.py`, `STATUS.md`, this entry. Related: [[D245]] (asymmetric-upgrade both-directions restart), [[D249]]/[[D250]] (prior contracts adoptions), D258 (dsj golden, same deploy).

**STATUS: DEPLOYED + VERIFIED 2026-07-10T00:24:57Z (commit `61fc821`).** Suite 1868 green (pin adopted) → stop (old PID 10235, exit 143) → commit → daemon-reload → start. New daemon PID 1768029, **NRestarts=0**; journal `grammar_version=v25 registry_hash=000d5a44d9c2ac9e` (grammar UNCHANGED — enumeration byte-identical), `registry_loaded_from_export` clean, the `idiosyncratic_vol` literal_error GONE, `reconciled batches=1 newly_gated_total=198`, full learned-weight maps + first unblocked iteration healthy, no traceback. `forge healthcheck` `contracts pin==installed 1.28.0` (skew cleared); OVERALL=WARN (11 ok, 1 warn, 0 crit) — the lone WARN = pre-existing `wf_p25 drift` (D260, unrelated). Incident RESOLVED.**

## D262 — 2026-07-09 — DURABLE HARDENING for the D261 trap face: adopt contracts 1.29.0 + wire `parse_skipping_unknown_literals` into the registry read (+ healthcheck surface)

**Spec section:** §13.5 read-path resilience + contracts pin (not a grammar/enumeration change). Relay `PROMPT_CRUCIBLE_IVOL_RECLASS_OUTAGE.md` → Crucible reply `FORGE_ivol_reclass_outage_response_2026-07-09.md` (both asks answered).

**Why.** D261 showed a family-literal addition Forge hasn't adopted makes the WHOLE registry snapshot fail `model_validate` (`literal_error`) → the daemon fails every poll (soft outage). `parse_forward_compatible` (D250) doesn't cover it — it prunes unknown FIELDS; this is an unknown VALUE in a known field.

**Convergence.** The relay asked Crucible to (Ask #1) sequence vocabulary additions and (Ask #2) optionally own the tolerance in contracts. Crucible did BOTH: adopted the sequencing (land contracts → consumer adopts → THEN land the value-bearing export; sharp nuance — their publisher timer republishes from the tree ~6h, so **the export-side commit IS the publish**, binding the rule at commit not trigger), and shipped **`parse_skipping_unknown_literals` in contracts 1.29.0** — the shared tolerant reader. So Forge WIRES the contracts primitive rather than hand-rolling the prune (hard rule #2, the D250 seam). (An interim Forge-side pruner was built + tested, then replaced by the 1.29.0 helper before commit.)

**What.** (1) Adopt the pin `FORGE_EXPECTED_CONTRACT_VERSION` 1.28.0 → **1.29.0** (`contracts_check.py`; installed already 1.29.0, `uv.lock` recorded it). 1.29.0 is PURELY ADDITIVE (a new function, no Literal/vocab change) → cannot reproduce the outage. (2) `registry_loader._parse_registry_tolerating_unknown_family` now calls `parse_skipping_unknown_literals(RegistrySnapshot, text, skip_in=("indicators",), logger=_LOG)` → `(snapshot, skipped)`: the helper drops `indicators` elements with an unknown `family` Literal (and prunes additive unknown fields in one pass), keeping the rest; every other error re-raises (module's "corruption surfaces loudly" contract intact — malformed-JSON + missing-field tests still red-line). Forge re-emits any `skipped` as its own structured `registry_unknown_family_skipped` WARN. **Byte-identical for a known-family registry.** Safe because Forge can't grammar-place an unknown-family indicator anyway (absent from the threshold table + pools), so dropping it changes no enumerated config; the drop just needs to be VISIBLE.

**Visibility (the WARN is load-bearing).** `check_registry_unknown_family` (fed by a new `JournalState.registry_unknown_family_at` marker parsed from the daemon journal) → healthcheck WARN `registry_family` pointing at the fix (adopt the new `crucible_contracts`). Mirrors the D246 `inbox_rejections` surface for the sibling ingest-side face. (Journal-parsed because healthcheck is a separate process from the daemon that holds the helper's returned `skipped`.)

**Honest limit.** Graceful-degrade, NOT a substitute for adoption: while an unknown family is skipped, the enumerable indicator set is silently reduced (benign for a non-enumerated indicator like `ivol`; a temporary capability loss if a currently-USED indicator is reclassified). The WARN/healthcheck is the signal to adopt. The clean fix stays the now-agreed sequencing discipline.

**Files:** `src/forge/core/contracts_check.py`, `src/forge/persistence/registry_loader.py`, `src/forge/cli/healthcheck_cmd.py`, `uv.lock`, `tests/unit/test_registry_loader.py`, `tests/unit/test_cli/test_healthcheck.py`, `STATUS.md`, this entry. Relay `PROMPT_CRUCIBLE_IVOL_RECLASS_OUTAGE.md`. Related: [[D261]] (the incident + 1.28.0 adopt), [[D250]] (parse_forward_compatible — the field-face sibling), [[D246]] (inbox_rejections healthcheck template), [[D245]] (asymmetric-upgrade both-directions rule).

**STATUS: DEPLOYED + VERIFIED 2026-07-10T01:19:14Z (commit `6b1f5b8`).** Preflight GO (1871 green) → stop (old PID 1768029, exit 143) → daemon-reload → start (operator: "for the contracts yes restart to arm it"). New daemon PID 2362816, **NRestarts=0**; journal `grammar_version=v25 registry_hash=b568bc7ad66ae3e5` (grammar UNCHANGED — byte-identical), `registry_loaded_from_export` clean, reconciling, no literal_error/traceback. `forge healthcheck` **`contracts pin==installed 1.29.0`** + **`registry_family` OK** (tolerant reader ARMED, nothing skipped); OVERALL=WARN (12 ok, 1 warn, 0 crit) — lone WARN = pre-existing `wf_p25 drift` (D260, unrelated). The v26 `ivol_lo` grammar wiring stays parked (operator: not needed — optional, no promotion unlock).**

## D263 — 2026-07-09 — v26: `ivol` name-selection VETO — optional 2nd regime gate on mean_reversion (the validated `ivol_lo` lever)

**Spec section:** §3.5 S3 (≥1 regime gate) + R1 — an enumeration-policy bump (`rules:` text untouched, like v25). Source: Crucible `FORGE_ivol_lo_mr_entry_gate_2026-07-09.md` (+0.163 mean cpcv-vs-base, 6/6 champions; book-level preview cpcv-p25 +0.087 "wall held"). Operator: "let's go to v26 so we can lock in the gains."

**What.** `ivol` (per-name CAPM-residual idiosyncratic vol, family `idiosyncratic_vol` as of contracts 1.28.0) wired as an OPTIONAL SECOND `regime_filter` on `mean_reversion` — a percentile veto (`op "<"`, plateau [0.2,0.3,0.4], **window 63**) that EXCLUDES the high-idio-vol oversold names (the "falling knives", Bhootra-Hur 2015). A name-**selection** refinement (which oversold name), orthogonal to the level gates already exhausted. Honest scope (Crucible): a TAIL effect (cuts knife losses in the worst CPCV windows), construction-quality — NOT a promotion unlock.

**Structural — STACKS on the volatility gate (the OPPOSITE of dsj).** The validated form is `ivol` ANDed on top of the MR champion's `vol_regime`/`rv_rank` gate. Because `ivol` is `idiosyncratic_vol` (distinct from the `volatility` level gates — the whole point of the 1.28.0 family split), §3.5 C1 PERMITS the stacking (verified: 80/191 sampled ivol configs stack on `rv_rank`). This is why the D258 veto machinery's C1 guard had to be GENERALIZED: `_DSJ_VETO_FAMILY` (hardcoded `volatility`) → a per-hypothesis veto family read from the registry (dsj→volatility skips a vol gate; ivol→idiosyncratic_vol never collides, so it stacks). R1 stays satisfied by the primary gate (plural-aware); C1 validator unchanged (generic family-distinctness). NO `rules:` change.

**Mechanism (extends D258).** New `_MR_IVOL_VETO_INDICATORS=("ivol",)`; `regime_veto_indicators_by_hypothesis` gains a `mean_reversion` key; new `SearchSpace.regime_veto_family_by_hypothesis` (registry-derived) feeds the generalized `_config_has_veto_family_indicator(signals, space, veto_family)`; `_DSJ_VETO_SHARE`→`_REGIME_VETO_SHARE` (0.5, both arms). `ivol` threshold spec added with a NEW `regime_percentile_window` field (None→252 default, so every existing spec is byte-identical; ivol=63). `ivol` horizon entry (63). Drawn LAST → activation shifts only the added signal.

**Byte-identity (hard rule #6).** The dsj path and both existing cold-start goldens (`_REGIME_GOLDEN_PRE`, `_REGIME_GOLDEN_DSJ_ACTIVE`) are UNCHANGED after the generalization (their fixtures don't serve ivol → the MR veto pool is empty → no perturbation; verified green). New `_REGIME_GOLDEN_V26_ACTIVE` (registry serving dsj + ivol; 3/15 configs carry ivol) pins the v26 sequence. Since `ivol` is ALREADY registry-live (contracts 1.28.0, D262), v26 emits immediately on deploy — no dormant window (unlike dsj's plan).

**Files:** `grammar/custom_predicates.py` (veto constant), `enumeration/search_space.py` (MR pool + family map), `enumeration/sampler.py` (generalized guard + share + emission), `enumeration/indicator_thresholds.py` (ivol spec + `regime_percentile_window`), `grammar/signal_horizon.py` (ivol horizon), `tests/unit/test_enumeration/test_sampler.py` (`test_d263_*` + `_REGIME_GOLDEN_V26_ACTIVE`), `tests/integration/test_v1_grammar.py` (version assert), `docs/GRAMMAR.md` (R1 v26 note), grammar v26 bump + `config/grammar_archive/v26.yaml`. Relay: `PROMPT_CRUCIBLE_GRAMMAR_V26_FUNNEL.md`. Related: [[D258]] (the veto machinery this extends), [[D254]] (vol_regime MR gate it stacks on), [[D262]] (the 1.28.0 family split that unblocked it).

**STATUS: DEPLOYED + VERIFIED 2026-07-10T01:57:19Z (commit `180087c`).** Grammar-change ritual: stop (v25 daemon) → bump v25→v26 + archive `v26.yaml` (byte-identical) + `test_v1_grammar` v26 → uncontended suite **1875 green** + both grammar hooks pass (committed via `uv run git commit` — the hook context needs the venv `python`) → restart. New daemon PID 2750088, **NRestarts=0**; journal `grammar_version=v26 registry_hash=b568bc7ad66ae3e5`, `recorded manual_bump row for v26`, reconciling, no traceback. **Emission proof (live cold mix, seed 0, 3000): MR=562, MR_with_ivol=273 (~49% ≈ the 0.5 share), sample = `ivol` STACKED on `rv_rank` — the validated form, C1-accepted.** `forge healthcheck` OVERALL=WARN (12 ok, 1 warn=pre-existing wf_p25 drift, 0 crit); contracts + registry_family OK. `check-activations ivol` = UNCHK (probes directionals only; ivol is a regime veto — N/A). Relay `PROMPT_CRUCIBLE_GRAMMAR_V26_FUNNEL.md` ready to carry (`crucible funnel --compare v25 v26`).**

## D264 — 2026-07-11 — v27: resid_vix activation — residual_momentum trend directional × vix_term_slope R2 calm gate (the first-ever walk-forward-gate passer becomes generable supply)

**Trigger:** Crucible handoff `FORGE_resid_vix_generation_request_2026-07-11.md` (HIGH). Their hand-built `probe_resid_vix_swing_mid` (residual_momentum percentile >0.8 directional + vix_term_slope >0 gate, on a Forge swing_mid trend chassis) blended at 20% into their closest book passed **walk_forward_sharpe_median 2.0611 vs gate 2.0 — the first object EVER over the WF bar** — seed-robust (2.071/2.061/2.057 across seeds 42/43/44) AND lifted cpcv_sharpe_p25 1.166→1.2987 (both binding axes). Honesty caveats recorded: raw CSCV 0.584 over the 15-arm family (near-dup-inflated; selected arm OOS rank median 11/15); solo WF quarterly median 1.10; component value is host/weight-dependent. Both ids long-registered, both DARK supply (0 of 430,563 submissions — corroborated structurally: no `indicator_thresholds` entry → `is_threshold_skippable` in every threshold role). Operator approved in-session ("Can we just put it in the next grammar?") via OPEN_PROPOSALS `0a4d8da8` (hard rule #4); the injection fast-lane was declined — grammar-only.

**The change (one activation + one pool add; `rules:` text untouched except R2's `evidence_to_relax` metadata listing):**
1. **residual_momentum ACTIVATED** as a trend_continuation directional via C2 (registry family `trend`, rank-coherent): PERCENTILE-ONLY `IndicatorThresholdSpec` (0.60, 0.90) op ">" (the sma_slope/option_momentum distribution-free precedent; the shared 252 percentile window IS the probe's ranking window), plus the computation knobs `window` int [63, 252] / `skip` int [0, 21] riding SignalSpec params via `_sample_residual_momentum_params` (the option_momentum/pairs pattern; probe won at 126/21; Crucible's writer reads them per-config — probe-confirmed).
2. **vix_term_slope joins R2's python-side pool** (`_R2_TREND_CONTINUATION_REGIME_INDICATORS`) as the calm-market (contango) gate: regime_range (0.0, 2.0) op ">". **REVERSES the v17/D131 deliberate exclusion** — its recorded rationale ("validated for vol returns, not trend conditioning") is directly superseded by Crucible's campaign-grade measurement of exactly this use; the relax clause's second firing (first: market_state, v17). Their measured failure mode (stale contango holds exposure into bear onsets, 2022-02/05) is covered by the tighter half of the uniform threshold draw (their explicit sweep ask). `evidence_to_relax` listing updated to the six-member pool.
3. **Horizons:** residual_momentum 63 td (the DRIFT horizon, not the formation window) → medium_lookback → the D102 k∈{2,3,4} derivation snaps every target (126/189/252) to **swing_mid — the validated probe chassis**. vix_term_slope 1 td, gate-only (coverage-invariant honesty, the market_state precedent). **Structural finding logged:** the handoff's swing_mid-VS-swing_long sweep axis is NOT expressible for one indicator id under D102 horizon-matched DTE (one horizon → exactly one bucket in practice); the swing_long arm was consciously dropped with the injection lane declined — reachable later via a D102-class change if funnel evidence asks.

**Deliberately NOT done:** gate debounce/confirmation (no engine axis exists — relayed back); the other seven dark indicators (Q45 — need per-id evidence); multi-gate generalization (Q46 — the veto machinery is the seam); a directional-pool prune or share knob (the learned D106 weight ranks residual_momentum against momentum_252/sma_slope organically).

**Byte-identity (hard rule #6).** All four pre-existing cold-start goldens (`_COHORT_GOLDEN_PRE_REFACTOR`, `_REGIME_GOLDEN_PRE`, `_REGIME_GOLDEN_DSJ_ACTIVE`, `_REGIME_GOLDEN_V26_ACTIVE`) UNCHANGED — their fixtures serve neither new id, so the base pools are unperturbed (verified green). New `_REGIME_GOLDEN_V27_ACTIVE` (registry serving dsj+ivol+both v27 ids; diverges from V26_ACTIVE at position 2, carriers at 2 and 4) pins the v27 sequence. Both ids are ALREADY registry-live → v27 emits immediately on deploy, no dormant window.

**Verification (pre-deploy):** TDD red→green (11 failing tests written first, failed for the expected reasons); `check-activations residual_momentum` = **[ OK ] 746 activations on 4/4 probed names** (the D254 layer-3 gate; was [UNCHK] pre-wiring — not enumerable, cannot probe); emission proof on the live registry (cold mix, seed 20260711, 2000): trend=380, resid directional=58 (~15% of trend), vix gate=59, exact pair=11, example config = the probe shape (swing_mid, percentile 0.6882, window 65/skip 0, gate >0.3968); ruff + mypy --strict clean; full suite **1891 green** pre-bump.

**Files:** `enumeration/indicator_thresholds.py` (2 specs), `grammar/signal_horizon.py` (2 horizons), `grammar/custom_predicates.py` (R2 pool), `enumeration/sampler.py` (`_sample_residual_momentum_params` + wire), `tests/unit/test_enumeration/test_resid_vix_v27.py` (new), `tests/unit/test_enumeration/test_sampler.py` (`test_d264_*` + `_REGIME_GOLDEN_V27_ACTIVE` + `_v27_registry`), `tests/unit/test_grammar/test_custom_predicates.py` (R2 accept), `tests/integration/test_v1_grammar.py` (v27 assert), `config/grammar.yaml` (v27 + header note + R2 evidence_to_relax) + `config/grammar_archive/v27.yaml`, `docs/GRAMMAR.md` (R2), `docs/tasks/grammar-change.md` (stale pending-note cleared), OPEN_PROPOSALS `0a4d8da8` APPROVED, OPEN_QUESTIONS Q45/Q46. Relay: `PROMPT_CRUCIBLE_GRAMMAR_V27_FUNNEL.md`. Related: [[D131]] (the exclusion reversed), [[D236]]/[[D138]] (percentile-only precedent), [[D258]]/[[D263]] (goldens process), [[D254]] (check-activations gate).

**STATUS: DEPLOYED + VERIFIED 2026-07-11T07:45:31Z (commit `ba1f2b2`).** Ritual: stop (old PID 2750088, v26) → bump v26→v27 + archive `v27.yaml` + `test_v1_grammar` v27 + R2 `evidence_to_relax` six-member listing → full uncontended suite **1891 green** + both grammar hooks (via `uv run git commit`) → restart. New daemon PID 4156062, **NRestarts=0**; journal `grammar_version=v27 registry_hash=c223fcfd62e5fade`, `recorded manual_bump row for v27`, all learned-weight maps loaded, 0 traceback/SchemaVersionMismatch/GrammarVersionError/literal_error. First v27 iteration: enumerated 5000 → `submitted=200 skipped_duplicate=0 failed=0` (batch `174e6d28`), exploration_holdout 10/200. **LIVE emission proof (inbox payloads): 15/200 carry `residual_momentum`, 18/200 `vix_term_slope`, incl. the exact pair `b2f9824a2afdf109` — v27-stamped, swing_mid, percentile >0.8194 / window 73 / skip 18, gate >0.6614 (the tighter band their failure analysis asked for).** `forge healthcheck` OVERALL=WARN (12 ok, 1 warn = pre-existing wf_p25 drift, 0 crit). Relay `PROMPT_CRUCIBLE_GRAMMAR_V27_FUNNEL.md` ready to carry (`crucible funnel --compare v26 v27`).

## D265 — 2026-07-12 — v28: realized_vol ABSOLUTE mean_reversion regime gate (the systematic-spike complement to the rv_rank percentile)

**Trigger:** Crucible handoff `FORGE_mr_absolute_vol_gate_request_2026-07-12.md` (MEDIUM-HIGH) + their same-day convention reply (`CRUCIBLE_activation_cache_fix_and_rv_convention_2026-07-12.md`). The champion MR leg (`forge_mean_reversion_swing_mid_1625fcfd`, the v26 ivol_lo descendant) is protected by `rv_rank < 62` — a PERCENTILE that NORMALIZES in regime-wide vol spikes (every name volatile → ranks mid-distribution) and passes exactly when it should bind. Its knife-catch entries (2022-12, 2025-03, 2025-04 at abs rv21 0.135–0.27, MARKET-level per their convention reply) dominate CPCV blocks 5+8 — two of the five bottom-quartile blocks. **Probe-verified on our own data pre-build (operator: "probe to make sure this actually works first"):** 2022-12 `rv_rank<62` open **21/21 days on ALL of HAL/CVX/SLB/TGT/BAC** while absolute rv held ≥ 0.25. Their honest counterfactual: a blanket absolute gate is P&L-NEGATIVE overall and GATE-positive (weak blocks decide cpcv_p25) — no gated config measured; generating the family IS the probe (the ivol_lo pattern). Operator green-lit in-session via OPEN_PROPOSALS `2121cafe` (hard rules #1+#4).

**The change (R1 widening + pool/weight/range edits; `rules:` text function reference untouched — the D167/D254 pattern):**
1. **R1 accepted OR += realized_vol** (`_R1_REALIZED_VOL_REGIME_INDICATOR`, custom_predicates): sixth gate, op-agnostic convention; failure detail + noqa listing updated.
2. **MR regime pool += realized_vol** (`_build_regime_pool`) — registered ≠ enumerable (D254 lesson).
3. **Threshold table:** `realized_vol.regime_range` (0.12, 0.25) → **(0.15, 0.30)** — the asked sweep, replacing the D031-era generic; ABSOLUTE by design (a percentile IS rv_rank, the diagnosed defect). Shared-range blast radius noted: relative_value's broad regime pool draws it rarely; shift licensed by the bump.
4. **`_MR_RANGING_GATES` += realized_vol** (weight 3.0 — same calm-vol thesis class as rv_rank/vol_regime).

**Semantics + C1 structure (recorded honestly):** PER-NAME gate (registry `market_wide_by_design=False`). Per-name pass rates are strongly heterogeneous (probe: `<0.20` passes HAL 4.0% / SLB 6.2% / TGT 21.2% / BAC 26.3% / CVX 32.5% / JPM 39.0% / SPY 77.0%) → tight arms zero-trade hot names; the expected_trades wall culls them pre-submission and the sweep's top half keeps hot names live. **Crucible's PREFERRED market-level variant (reference-underlying RV, where their 0.15–0.30 bounds translate 1:1) is NOT expressible today — no market-wide realized-vol id exists in the registry (vix_level is implied vol)** → registration ask relayed; future bump activates it (the dsj dormant pattern needs their id/family/lookback confirm first). C1: realized_vol shares family `volatility` with rv_rank/vol_regime → the absolute gate REPLACES the percentile in the vol slot (never both; a C1 carve-out was NOT proposed); the chain-family guard keeps it out of vol_target-sized configs; the v26 `ivol` veto (idiosyncratic_vol) STACKS on top — the asked both-gates shape, ~46% of the new variants (both arms measurable, ablation-friendly).

**Byte-identity (hard rule #6): version bump licenses the shift — and unlike v26/v27, the base test fixture ALREADY serves realized_vol (the X1 vol_target chain), so all five cold-start goldens legitimately moved and were deliberately re-pinned** (`_REGIME_GOLDEN_PRE` pos 14, `_COHORT_GOLDEN_PRE_REFACTOR` pos 4, `_REGIME_GOLDEN_DSJ_ACTIVE` pos 14, `_REGIME_GOLDEN_V26_ACTIVE` pos 6+ (ivol carriers 3,7,12 → 3,6,11), `_REGIME_GOLDEN_V27_ACTIVE` pos 12). Flag-inertness invariants (none_run == empty_run × 2) and all structural inter-golden relations re-verified BEFORE re-pinning.

**Pre-build probes (both PASS; scratchpad scripts, technique in the relay):** (1) emission simulation (in-memory constants): realized_vol primary on 314/2000 forced-MR (15.7%), ivol stack 46.2%, current grammar rejects all 314 on R1 and ONLY R1, widened R1 → 314/314 fully valid; (2) live-writer per-name data probe (post their `5266250` cache fix, which our probing triggered): mechanism confirmed + selectivity table above. `check-activations` N/A (directional-only; realized_vol is a gate, writer-computed today via live vol_target chains).

**Verification (pre-deploy):** TDD red→green (9 new tests failed first for the expected reasons: ImportError on the constant, R1 reject, pool absence ×2); ruff + mypy --strict clean; full suite **1900 green** (contended); emission proof on the live registry (enumerate_candidates, seed 0, 3000): hypothesis mix healthy, MR gates {gamma 132, vol_regime 98, iv_rank 94, rv_rank 90, hurst 89, **realized_vol 78** = 13.4% of MR}, ivol stacked 33/78 (42.3%), vol_target co-occurrence **0**, thresholds 0.1503–0.2939 all-absolute.

**Files:** `grammar/custom_predicates.py` (R1 constant + accept + detail), `enumeration/search_space.py` (MR pool), `enumeration/indicator_thresholds.py` (regime_range), `enumeration/sampler.py` (`_MR_RANGING_GATES`), `tests/unit/test_enumeration/test_mr_grammar_v28.py` (new), `tests/unit/test_grammar/test_custom_predicates.py` (R1 accept), `tests/unit/test_enumeration/test_sampler.py` (2 reachability tests + 5 golden re-pins + set updates), `tests/unit/test_enumeration/test_search_space.py` (pool assert), `config/grammar.yaml` (v28 + header note + R1 comment + evidence_to_relax) + `config/grammar_archive/v28.yaml`, `docs/GRAMMAR.md` (R1), OPEN_PROPOSALS `2121cafe` APPROVED. Relays: `PROMPT_CRUCIBLE_GRAMMAR_V28_FUNNEL.md` + the market-RV registration ask. Related: [[D167]]/[[D254]] (R1 widening pattern), [[D263]] (ivol stack), [[D258]] (dormant-wiring discipline — why market-level waits for their id), [[D261]] (vocabulary-race lesson).

## D266 — 2026-07-12 — v29: market_realized_vol — the MARKET-level absolute-RV MR gate (Crucible's preferred variant; R1 seventh gate + the two-member MR veto pool)

**Trigger:** Crucible confirm `CRUCIBLE_market_realized_vol_registered_2026-07-12.md` — the D258-pattern wire-against reply to our registration ask (`PROMPT_CRUCIBLE_MARKET_RV_REGISTRATION_ASK.md` §3), itself the recorded fast-follow to v28/D265. Their convention reply had established: the ledger's rv21 regime tag is **SPY market-level** vol; the knife-catch losses cluster in MARKET-wide spikes; the 0.15–0.30 sweep bounds translate 1:1 only at the market level. Registered strings (all independently verified pre-build): id `market_realized_vol`, family **`macro`** (DELIBERATE — C1 stacks the market gate with the vol-family primaries and the idio-family ivol veto; "Yes: we want coexistence with rv_rank"), v1, lookback 0 (writer-internal reference warmup), params reference="SPY"/window=21, `market_wide_by_design=true`, semantics byte-matching rv21 (pstdev ddof=0, c2c, sqrt(252)). Serving verified: snapshot `2026-07-12T053611Z` grep; writer probe 78.7% of SPY bars pass `<0.20`, identical sets across underlyings (market-wide BY DESIGN — distinct from the fixed cache bug), 2022-12 knife window mostly closed (7/21). Operator basis: the wire-against confirm attached in-session following the recorded fast-follow plan (OPEN_PROPOSALS `9f1c615b`, APPROVED).

**The change (R1 widening + the D263 veto-seam generalization, minimally widened):**
1. **R1 accepted OR += market_realized_vol** (seventh gate; op-agnostic convention).
2. **MR primary pool += id**; **`_MR_RANGING_GATES` += id** (3.0 — the preferred family gets at least equal supply).
3. **Threshold entry** regime_range (0.15, 0.30) op `<`, ABSOLUTE-only, gate-only; **horizon 1** (gate-only, the vix_term_slope/market_state precedent — warmup is writer-internal).
4. **MR veto pool widened to TWO members** — `_MR_IVOL_VETO_INDICATORS` → `_MR_REGIME_VETO_INDICATORS = ("ivol", "market_realized_vol")` — delivering their explicit "pair it with EITHER existing gate": market_rv rides as the ANDed second gate on a volatility primary. **C1 guard generalized PER-ID** (`SearchSpace.regime_veto_family_by_id` replaces `regime_veto_family_by_hypothesis`; the sampler filters the pool to C1-eligible ids before the share draw) — the Q46 seam D263 anticipated, widened only as far as the ask requires. One veto slot per config (never ivol AND market_rv; three-gate stacks stay Q46). Structural bonus recorded: family macro does NOT hit the vol_target chain guard, so market-gated MR configs MAY carry vol_target sizers (the per-name D265 family cannot) — this also boosts its primary share in chain configs where every volatility gate is excluded.

**Byte-identity (hard rule #6):** single-id pools consume rng IDENTICALLY under the per-id refactor (same guard semantics → same share-draw condition → same `rng.choice`), so — unlike v28 — **ALL pre-v29 goldens are UNCHANGED** (verified green; a dedicated regression test `test_d266_veto_generalization_leaves_single_id_pools_byte_identical` pins the reason). New `_REGIME_GOLDEN_V29_ACTIVE` (diverges from V26_ACTIVE at position 3; carriers 3+11). The id is ALREADY registry-live → v29 emits immediately on deploy, no dormant window.

**Verification (pre-deploy):** TDD red→green (10 new tests failed first for the expected reasons); ruff + mypy --strict clean; full suite **1912 green**; emission proof (live registry, 3000): MR primary gates {**market_realized_vol 163 (27.6%)**, gamma 99, rv_rank 76, vol_regime 72, realized_vol 70, hurst 58, iv_rank 52}; veto draws ivol 176 / market_rv 117; pairings **market_rv+ivol 86, rv_rank+market_rv 25, vol_regime+market_rv 19, realized_vol+market_rv 17** — every asked shape live; thresholds 0.1503–0.2995 all-absolute.

**Files:** `grammar/custom_predicates.py` (R1 constant+accept+detail; veto constant rename+widen), `enumeration/search_space.py` (primary pool; per-id veto family map; SearchSpace field), `enumeration/sampler.py` (per-id eligible filter; `_MR_RANGING_GATES`), `enumeration/indicator_thresholds.py`, `grammar/signal_horizon.py`, `tests/unit/test_enumeration/test_mr_grammar_v29.py` (new), `tests/unit/test_grammar/test_custom_predicates.py` (R1 accept), `tests/unit/test_enumeration/test_sampler.py` (`_v29_registry` + 3 reachability/regression tests + `_REGIME_GOLDEN_V29_ACTIVE`), `config/grammar.yaml` (v29 + header + R1 comment + evidence_to_relax) + archive, `docs/GRAMMAR.md` (R1 + veto-slot section), `tests/integration/test_v1_grammar.py` (v29), OPEN_PROPOSALS `9f1c615b`. Relay: `PROMPT_CRUCIBLE_GRAMMAR_V29_FUNNEL.md`. Related: [[D265]] (the per-name half), [[D263]] (the veto seam), [[D258]] (confirmed-vocabulary discipline), Q46 (the three-gate boundary, still open).

## D267 — 2026-07-12 — Adopt contracts 1.30.0 (`weighting_scheme "explicit"`) — pin-only, no-op for Forge

**Trigger:** operator FYI "Contracts 1.30.0 just pushed" (Crucible `253da67`). 1.30.0 adds ONE Literal value: `PromotedPortfolio.weighting_scheme += "explicit"` — operator-fixed maximin per-component weights queued verbatim, identity-bearing (feeds `compute_config_hash`). It is the publisher-side crossing-unblock for the FIRST full-gate portfolio promote (pure_sue175, Crucible run 79eb6d55): reconstruction was fail-looping on `literal_error` so `promoted_portfolios` exports stayed n=0 and the honest book could not cross to QuantIQ.

**Assessment (why pin-only):** the literal lives on `PromotedPortfolio`, a QuantIQ-facing model Forge NEVER constructs or parses. Forge's only Crucible reads are `get_recent_gated_runs` / `get_promoted_strategies` — both return `GatedRun` (verified: `rg` finds zero `PromotedPortfolio`/`weighting_scheme` parse sites in `src/`, only a doc comment). So — UNLIKE the D261 registry-family literal that Forge DOES read on `RegistrySnapshot` — there is **no read-face or inbox-face exposure in either direction**: the inbox is `StrategyConfig` (unchanged), the read faces are `RegistrySnapshot`/`GatedRun` (unchanged). The running 1.29.0 daemon was therefore never at risk from Crucible writing 1.30.0, and no D261-Ask-1 consumer-adoption handshake is owed (Forge is not a `weighting_scheme` consumer). Enumeration byte-identical (no consumed model changed). §13.5's `validate_schema_version` is MAJOR-only, so 1.29.0-pin vs 1.30.0-installed already passed (both major 1) — a reboot would NOT have halted.

**Why adopt now anyway:** the editable sibling bump left `uv.lock` dirty at 1.30.0 (last committed 1.29.0, D262) and flipped `test_expected_contract_version_matches_installed` (exact `CONTRACT_VERSION == pin`) RED — which would NO-GO the next `deploy_preflight.sh` (full-suite gate) and blemish the clean-tree invariant. Adopting clears both and keeps Forge↔Crucible on one contracts version (the standing D262 discipline; the healthcheck literally says "adopt it" at WARN).

**Change:** `FORGE_EXPECTED_CONTRACT_VERSION` "1.29.0" → "1.30.0" + the pin-history comment; `uv.lock` (already resolved). No other file — no wiring (nothing to consume).

**Verification:** the exact-match test flipped green (5/5 in test_contracts_integration); enumeration goldens unaffected (4/4); mypy --strict clean; full suite **1912 green** on 1.30.0.

**Deploy: DEPLOYED + VERIFIED 2026-07-12T07:14:57Z (commit `44b0441`).** Ritual: stop (old PID 2370575, exit 143) → commit (pin + uv.lock) → reset-failed → start. New daemon **PID 2604710/2604715, NRestarts=0**; journal `grammar_version=v29 registry_hash=56bd15d4e858fa19` (**v29 UNCHANGED** — enumeration byte-identical; the hash roll is a routine registry republish), `registry_loaded_from_export` clean, healthy reconcile, no traceback/SchemaVersionMismatch/literal_error. `forge healthcheck`: **`contracts: pin == installed (1.30.0)`**, OVERALL=**OK (13 ok, 0 warn, 0 crit)**. Related: [[D262]] (the 1.29.0 adoption playbook this mirrors), [[D261]] (the read-face literal trap this is NOT), [[D245]] (asymmetric-upgrade — N/A here, the changed model crosses neither Forge face).

## D268 — 2026-07-12 — v30: exclude no-earnings underlyings from earnings-dependent generation (the event_momentum degeneracy stopgap)

**Trigger:** Crucible relay `FORGE_event_momentum_no_earnings_underlying_degenerates_2026-07-12.md` (generation-side blind spot; not hypothetical — a live 17.5% component of the FIRST promoted book `664b137e5794fbf8`). `event_momentum` on `underlying=SOXL` (a leveraged semiconductor ETF with no EPS) promoted at cpcv 1.236, but **both its earnings signals are inert**: `sue` and `days_since_earnings` NaN-fill on SOXL, so `sue` directional → FLAT (no vote), `days_since_earnings` regime → the engine's no-data fallback `allow=True` (never gates), and the `realized_vol` confluence passthrough (`value>0`) always votes LONG_CALL → k_of_n k=1 → 233 naked-long-SOXL-call entries with ZERO PEAD/SUE contribution. The run's own diagnostic proves it: `regime_gated: 0, no_directional: 0`. The leg is mislabeled — its edge is unhedged long SOXL over a semi bull, not earnings drift. `expected_trades` can't catch it (it DOES trade); the pathology is orthogonal to trade count.

**Forge-side root cause (verified):** `_pick_underlying` already had the T1.4/D039 earnings-ETF guard — for an earnings-gated config it drops `_TIER_1_ETF_UNDERLYINGS`. But that set was frozen at the 4 broad-market ETFs `{SPY,QQQ,IWM,DIA}` while Crucible's universe export grew to include ~26 more no-earnings names (SOXL/SOXX/TQQQ/SQQQ, the XL* sector suite, GLD/SLV/TLT/USO/UNG, UVXY/VIX, ARKK/EEM/EFA/SMH/HYG/XBI). The universe grew; the exclusion list didn't. Measured live (v29): **22.5% of event_momentum emission (179/795) landed on a no-earnings underlying**, SOXL among them — a systematic ~1/5 waste of Crucible backtest budget + mislabeling. (Note the NaN-vs-sentinel asymmetry: `days_to_earnings` returns sentinel 999 on ETFs → vol_event zero-trades → `expected_trades` rejects benignly; `days_since_earnings` returns NaN → `allow=True` → the degenerate leg TRADES. Only the backward twin degenerates.)

**Decision (operator, AskUserQuestion 2026-07-12): stopgap now + accept the coverage manifest.** Forge cannot correctly determine earnings coverage on its own — the universe export is ticker-lists only (no `is_etf`/`has_earnings` metadata) and ticker heuristics are wrong at the margins (RTX *looks* ETF-ish but is RTX Corp, with EPS; excluding it would starve honest supply). So this v30 is a CONSERVATIVE Forge-only stopgap; the durable fix is the v31 coverage manifest (below).

**The change (generation TIGHTENING; no `rules:` text change):** `sampler.py` adds `_NO_EARNINGS_UNDERLYINGS` — a superset of `_TIER_1_ETF_UNDERLYINGS` covering the no-earnings names in the universe plus common ETF/leveraged/inverse/commodity/vol/bond/index products (every entry unambiguously EPS-less; earnings-covered single names deliberately ABSENT). `_pick_underlying` excludes it (instead of the 4-name set) for any earnings-gated config (`regime_indicators ∩ _EARNINGS_CALENDAR_ETF_INCOMPATIBLE`), covering event_momentum (`days_since_earnings`) and vol_event/pre_earnings (`days_to_earnings`/`pre_earnings_setup`) alike.

**Byte-identity (hard rule #6): version bump licenses it.** The earnings-gated pool shrinks (~120→~94 on the live universe), so `rng.choice` on it consumes rng differently, cascading the sequence from the first earnings-gated config onward. Non-earnings configs are individually unchanged. All six cold-start goldens re-pinned (`_REGIME_GOLDEN_{PRE,DSJ_ACTIVE,V26_ACTIVE,V27_ACTIVE,V29_ACTIVE}` + `_COHORT_GOLDEN_PRE_REFACTOR`); both flag-inertness invariants (`none_run == empty_run`) and all inter-golden prefix relations re-verified before pinning. (These slices read the LIVE universe via `_load_underlyings` — pre-existing, since earnings configs draw from it.)

**Verification:** TDD red→green (3 tests failed first: constant undefined + SOXL/XLK/TQQQ leaking the 4-name guard); a hermetic monkeypatched test pins that an earnings-gated draw excludes no-earnings names AND keeps RTX-type covered companies drawable; ruff + mypy --strict clean; full suite **1914 green**; emission proof (live registry, 4000): event_momentum degenerate rate **22.5% → 0**, ANY earnings-gated config on a no-earnings underlying **0**, event_momentum now all real companies.

**STOPGAP — the durable fix is v31 (the coverage manifest).** Accepted Crucible's offer: they publish the `financials.parquet` covered-symbol set (~140 names) as a contracted export; Forge intersects the earnings-gated pool with it and RETIRES `_NO_EARNINGS_UNDERLYINGS`. Self-maintaining + complete (a future universe add of a NEW no-earnings ticker not in this hardcoded list re-opens the blind spot for that name until the manifest lands). Relay `PROMPT_CRUCIBLE_EARNINGS_COVERAGE_MANIFEST.md` (D261 confirm-then-wire sequencing). Their separately-weighed Crucible-side admissibility guard (reject all-NaN directional) is a good complementary backstop.

**Deploy: DEPLOYED + VERIFIED 2026-07-12T15:52:12Z (commit `4a950ab`).** Ritual: stop (old PID 2604715, exit 143) → commit → reset-failed → start. New daemon **PID 3461554/3461559, NRestarts=0**; journal `grammar_version=v30 registry_hash=ce4f7def232cbcc7`, `recorded manual_bump row for v30`, `registry_loaded_from_export` clean, no traceback/GrammarVersionError. `forge healthcheck` OVERALL=**OK (13 ok, 0 warn, 0 crit)**, `contracts pin==installed 1.30.0`. Related: [[D039]]/[[T1.4]] (the R3 ETF guard this generalizes), [[D109]] (event_momentum), [[D078]] (universe read), [[D258]] (the confirm-then-wire pattern v31 will follow).

---

## D269 — 2026-07-12 — Sector-signal research verdict: DON'T-BUILD (a sector *grouping* is not a new mechanism) — no grammar change, no deploy

**Trigger:** operator prompt — "after seeing SOXL, is a sector-ETF play worth testing? use agents to research what indicators/signals make it work." Distinct from D268 (which fixed SOXL as a degenerate *underlying*); this asks whether a **sector-aware signal** supplies orthogonal alpha. It does not.

**Grounding (three read-only Explore sweeps).** (1) Sector ETFs are ALREADY enumerable — SOXL + 12/14 named sector ETFs (XLB/E/F/I/K/P/U/V/Y, SMH, SOXX, XBI) are live Crucible-universe underlyings (`universe_tickers`, Crucible-owned); "trading sector ETFs" needs no work. (2) The options-only rule is NOT a blocker: §13.6 / hard rule #7 ban only the literal `family=="equity"`; basket/market signals already exist (`cs_dispersion`, `market_realized_vol`, `market_state`, `residual_momentum`). (3) The *sector-signal* axis is the MOST-tested idea in the repo — sector-neutral/GICS `relative_value` was already refuted ([[D215]]: residual-IC ≈ 0, corr-to-MR 0.80; "grouping ≠ mechanism"), sector dispersion is on the GRAMMAR_REVIEW §4.2 do-NOT-add list (wrong sign for long-vol), and no sector taxonomy exists in the grammar.

**Method — decorrelation-first deep research (measure the literature before proposing a measurement).** A background research workflow (6 angles, 24 primary/peer-reviewed sources, 25 claims adversarially verified 3-vote: 8 confirmed, 9 refuted, 8 errored-unverified on a session limit). Question scoped to: sector signals whose *economic driver differs* from price trend/MR, expressible as a LONG-vega/defined-risk overlay, surviving VRP + ETF-option costs and post-publication decay. Full verdict + citations: `SECTOR_VOL_MECHANISM_RESEARCH.md`.

**Verdict: NEGATIVE — barren, not under-sampled (GRAMMAR_REVIEW §5 "stop" test).** Every candidate falls into one of four disqualifying buckets: (1) **already owned** — sector-ETF vol is VIX-dominated (Bouri et al. 2021, 3-0) → not orthogonal to `vix_level`/`vix_term_slope`/`market_realized_vol`; (2) **off-mandate short-vol** — sector IV overreaction/reversal (JoD 2017) is real IV-space alpha but the harvestable side is *selling* vol; the long leg is 0.11%/day at 10% sig, midpoint-priced, 1-day rebalance → dead net of spreads (3-0); (3) **already refuted** — the one long-leg-separable vol-surface signal (Goyal-Saretto IV−RV) IS the `iv_minus_rv`/`rv_rank` family measured and refuted at [[D214]] (`rv_rank` direction was backwards); (4) **momentum-adjacent + wrong universe** — sector lead-lag is directional (collapses toward trend), intra-industry, concentrated in small/neglected illiquid names (RFS 20(4), 3-0), absent in the liquid sector ETFs we'd trade. The deep lesson reinforces [[D215]] verbatim: a sector is a *grouping*; the genuinely-different mechanisms in vol-space are structurally short-vol, which a buy-premium-only book cannot express.

**Honest incompleteness.** The sweep hit a session limit before credit-implied-vol (CIV, Kelly-Manzo-Palhares FAJ 2025) and VRP-term-structure verification (8 claims unverified; synthesis step skipped). Extracted-but-unverified evidence already points negative (CIV level factor 81% VIX-correlated; both premia accrue to the seller). Resume-to-close available (`resumeFromRunId`, cached agents replay free); prior confirms the negative.

**Staged, not decided (no build, no bar move, daemon untouched; hard rules 3/4/6/7 intact).** (a) `SECTOR_VOL_MECHANISM_RESEARCH.md` — the DON'T-BUILD verdict doc (matches the `_archive/*_RESEARCH.md` pattern of [[strike-forecasting-research-verdict]] / [[vol-event-cross-sectional-research-verdict]]). (b) `PROMPT_CRUCIBLE_SECTOR_ETF_XSECT_PRECHECK.md` — trimmed to ONE optional cheap ask: a sector-ETF cross-sectional *trend* residual-IC probe (§1), low-prior (Moskowitz-Grinblatt 1999: industry momentum subsumes single-name → trend-collinear), but it *definitively closes* the last never-isolated sector door on data. Measurement on Crucible's side; held for operator relay. The un-refuted door remains a genuinely *different mechanism* (the held `PROMPT_CRUCIBLE_FUNDAMENTAL_VALUE_PRECHECK.md`), not a sector grouping. Related: [[D214]], [[D215]], [[exhaust-long-options-before-v2-spreads]], GRAMMAR_REVIEW §4.2/§5, [[D207]] (alpha budget — adding a barren primitive only raises the null hurdle).

---

## D270 — 2026-07-13 — v31: capitulation-bounce activation — `momentum` drop-trigger as a mean_reversion directional via the first §3.5 C2 per-id carve-out

**Trigger:** Crucible handoff `FORGE_capitulation_bounce_generation_request_2026-07-12.md` (MEDIUM — their "highest-upside / lowest-maturity" candidate). Trade-level probe (2018-2026, tier-2 PIT + 22 survivorship-free ETFs, 2% per-leg cost, BS at entry IV): trailing 5-day return ≤ −5% → long ATM call ~35 DTE, held 10 td → **pooled +0.107 net on premium (high_vol +0.127, n=898)**; the underlying arm shows the bounce is real where it matters (index:bear fwd-10d +1.13% vs −1.56% unconditional). It attacks the bear/high-vol cpcv-p25 crater as a worst-quartile COMPLEMENT (their framing: judge in-book via assembly, not solo — solo §8.7 will likely reject, as it has every regime-complement component). It is the CONVERSE of the bear-timing refutations (every bear signal was contrarian — `selloff_21d < -5%` was the single most contrarian trigger; instead of fighting the post-capitulation bounce, buy it), and the structural complement of the champion MR family (conditioned on rv_rank < 62 CHEAP vol; this occupies the vetoed elevated-vol corner → structurally decorrelated supply). Operator approved proposal `e9d74318` 2026-07-13 ("approve").

**Verified pre-build:** registry triple (`momentum` v1 family=trend rank-coherent / `rv_rank` v1 / `days_since_jump` v3) in code AND snapshot 2026-07-13T010003Z (72 inds). `momentum` dark structurally: NO threshold entry + NO horizon entry → `is_threshold_skippable` every role → never emittable (corroborates their 0/462,990). Crucible engine `Momentum.compute` reads `params[lookback]/[skip]`, `min_bars = max(lb,sk)+1` → lookback 3-10/skip 0 needs no engine change. **CALL-only is free**: engine `ThresholdSignal` `direction` param defaults `long_call`; Forge never emits `direction`. **`time_stop` reads `n_bars` default 5** (exits/registry.py:104) and Forge never sampled it — all existing supply holds 5 td.

**The change (one C2 rule-surface carve-out + scoped sampler policy; `rules:` text UNCHANGED):**
1. `custom_predicates.py`: `_C2_HYPOTHESIS_EXTRA_IDS = {"mean_reversion": ("momentum",)}` — the FIRST per-id C2 carve-out (family stays `trend`; the label follows the kernel, the thesis is reversion; MR's time-stop exit schema is the probe chassis — trend REQUIRES a trailing exit). Consulted by the C2 predicate + the pool builder.
2. `search_space.py`: MR directional pool ∪= carve-out ids (registry-gated); `_DIRECTIONAL_POOL_EXCLUDED_IDS` pins momentum OUT of trend_continuation's family-derived pool (label honesty + trend byte-identity); `_RANK_POLICY_EXCLUDED_IDS = {momentum}` unioned into `rank_excluded_indicator_ids` (the rank combiner sorts DESCENDING → top-N by raw momentum = the STRONGEST names = the inverse mechanism; policy tightening).
3. `indicator_thresholds.py`: momentum `directional_range=(-0.083, -0.041)` op `<` (log units ≈ −8%..−4% simple; probe point −0.051), regime_range None.
4. `sampler.py`: `_sample_momentum_params` (lookback randint 3-10, skip 0 — a skip would erase the print the family buys); gate PINNED to rv_rank in `_compatible_regimes` (composes with the D077 chain guard → vol_target draws drop momentum, C1-correct by construction); `_regime_signal_params` grows `directional_id` (default None = byte-identical) → emits op `>` threshold uniform[50, 80] — the D107 "opposite side" pattern scoped per-DIRECTIONAL (champion MR's calm side untouched); R1 accepts op-agnostically (documented D107 convention); veto slot SKIPPED for this directional (calm-side ivol/market_rv would strangle co-fire; short-circuit precedes rng.random()); `_build_exits` grows `directional_id` → time_stop emits `n_bars` randint[5, 15] for this directional ONLY (the D169 cross-hypothesis concern respected).
5. `signal_horizon.py`: momentum 15 (bounce thesis window, NOT the 504 warmup) → medium class → D102 k∈{2,3,4} targets 30/45/60 all snap swing_mid — the probe bucket.
6. `grammar.yaml` v30 → v31 + header note; archived `config/grammar_archive/v31.yaml`.

**NOT expressible → injection lane (offered in the response relay, separate operator decision):** gate-OFF arms (fail R1), swing_long (D102 one-id-one-bucket), delta 0.45-0.55 (MR swing_mid P3 band caps 0.45; no P3 widening — D125 evidence has MR concentrating LOW).

**Byte-identity (hard rule #6): licensed where changed, exact everywhere else.** MR's directional pool widens ONLY when the registry serves momentum → live MR draws reshuffle (licensed by the bump). ALL pre-v31 goldens byte-identical (fixtures never serve momentum; the trend pin + plumbing defaults keep every other path's rng consumption exact — `test_d270_v29_golden_byte_identical_without_momentum` pins the refactor). New `_REGIME_GOLDEN_V31_ACTIVE` (diverges from V29_ACTIVE at position 3 = the first MR config; first carrier at position 24, asserted over a 30-slice).

**Verification:** TDD red→green (import error + pool/reachability failures first, expected reasons); suite **1930 green** (tests: 10-test unit file + 7 flow/golden tests); ruff + mypy --strict clean. **Emission proof (live registry, 3000 cold):** capitulation = 42/591 MR (7.1%); gate 42/42 rv_rank op `>` thresholds [50.4, 79.3]; directional thresholds spanning [−0.0829, −0.0412], lookbacks 3-10 all sampled, skip 0; 42/42 swing_mid; sizers {kelly 19, fixed 23} — vol_target 0; combiners 42/42 confluence; vetoes 0; time_stop on 18/42 with n_bars spanning [5, 15]; underlyings single names + SPY; trend leakage 0, rank leakage 0. **`check-activations momentum` [ OK ] — max 151 activations (SPY 17 / AAPL 51 / MSFT 29 / NVDA 151)**, the D254 layer-3 gate, with per-name spread confirming the post-5266250 per-name cache.

**Honest scope:** probe is trade-level and IV-crush-OPTIMISTIC (their exit-revaluation follow-up in flight; their fold-columns/gate price the IV path honestly regardless); the +0.09..0.15 cells are upper bounds; right-tailed payoff (win ~0.45) → expect ugly solo fold columns — the value hypothesis is in-book complement. Construction/tail lever, NOT a promotion-unlock claim. Related: [[D264]] (the dark-supply activation pattern), [[D107]]/[[D150]] (opposite-side convention), [[D167]] (rv_rank admission), [[D268]] (v30), [[D215]]/[[D216]] (orthogonal-supply thread).

---

## D271 — 2026-07-13 — Adopt contracts 1.31.0 (`load_earnings_covered_symbols_from_export`) — pin-only, no-op for Forge; the D268 manifest loader has LANDED, wiring is a follow-on proposal

**1.31.0 (Crucible `cbb8671`) adds the earnings-coverage MANIFEST loader** promised in the D268 thread (`PROMPT_CRUCIBLE_EARNINGS_COVERAGE_MANIFEST.md`): `load_earnings_covered_symbols_from_export` + its format registration. PURELY ADDITIVE (verified diff 253da67..cbb8671: queries.py + formats.py + tests only; no model/Literal/vocab change) → NO-OP for the running daemon; Forge does not call it yet. Adopted (pin 1.30.0 → 1.31.0 + uv.lock) because the editable-sibling bump flipped `test_expected_contract_version_matches_installed` RED mid-v31-build (would NO-GO deploy-preflight) — the standing D262/D267 discipline. Note their pyproject.toml IS bumped this time (the D267 uv.lock complaint fixed). **WIRING the manifest — intersect the earnings-gated underlying pool with the covered-symbol set and RETIRE `_NO_EARNINGS_UNDERLYINGS` — is its OWN operator-gated grammar bump** (changes underlying-pool emission; proposal to follow per the D258 confirm-then-wire discipline: verify the export publishes + semantics before wiring). Rides the v31 deploy's stop window; separate commit. Related: [[D267]], [[D268]], [[D262]].

**Deploy: DEPLOYED + VERIFIED 2026-07-13T15:48:05Z (commits `7687e21` D271 pin + `c50be71` v31).** Ritual: stop 15:36:04Z (exit 143 normal) → uncontended full suite **1930 green** + ruff + mypy --strict clean → commit → reset-failed → start. New daemon **PID 1413824/1413829, NRestarts=0**; journal `grammar_version=v31 registry_hash=a2739d10a0596991`, `registry_loaded_from_export`, clean reconcile, **0** traceback/SchemaVersionMismatch/GrammarVersionError; `forge healthcheck` OVERALL=WARN (**12 ok, 1 warn** — the pre-existing wf_p25-drift lane warn, unrelated). **INCIDENT (disclosed, benign): the deploy.md hot-read hazard fired** — grammar.yaml was edited in the live tree while the v30-code daemon ran; it hot-read the bump and stamped iterations `grammar_version=v31` from 15:31:50Z, recording the `manual_bump` row early (changed_at = stamp-flip time, the documented artifact). **Zero pollution reached Crucible: every iteration in the 15:31:50→15:36:04Z window was §7.3-blocked** (oldest in-flight batch 73.5–75.5% gated < 80%) — no v31-stamped submission exists from before the restart. Lesson re-learned: even live-tree builds must defer the grammar.yaml byte-edit to the stop window (v26 pattern); the §7.3 limiter was the safety net this time. **First unblocked batch (live, ~16 min post-restart): `15d70291` submitted=200 failed=0 at 16:04:29Z — 200/200 v31-stamped, 5 capitulation configs / 74 MR (6.8%, matching the 7.1% cold-mix proof), every one on spec (drop triggers −0.0507..−0.0604 log, lookbacks 6–10/skip 0, gates rv_rank > 68.1–73.6 with window params, swing_mid, confluence, fixed_risk, n_bars 7/9 where time_stop drew). DB-verified zero pre-restart v31 submissions (snapshot query; last pre-stop submission v30 @ 15:23:25Z).**

---

## D272 — 2026-07-13 — v32: earnings-coverage MANIFEST wiring — the durable D268 fix; retires the `_NO_EARNINGS_UNDERLYINGS` stopgap as authority; ships DORMANT-until-publish (byte-identical to v31)

**The D268 durable fix, wired. The v30 `_NO_EARNINGS_UNDERLYINGS` frozen list is a stopgap with a documented blind spot — a FUTURE universe add of a no-earnings ticker NOT on the list re-opens the SOXL degenerate-leg pathology (`days_since_earnings` NaN-fill → `allow=True` + FLAT directional → confluence passthrough-backfilled naked call that TRADES) for that name until a human edits the list. v32 makes Crucible's authored earnings-coverage MANIFEST the authority, since coverage truth lives where `financials.parquet` is authored and Forge cannot classify coverage from a ticker (the RTX-looks-like-an-ETF problem). Operator-approved (OPEN_PROPOSALS `682e1abd`, in-session "let's enable v32 grammar"). A TIGHTENING (the manifested pool is a subset of universe-minus-list) — operator-gated per hard rule #4.**

- **Change (all Python-side sampler policy; `rules:` text UNCHANGED — the D268 pattern):**
  - `sampler.py` — `_load_earnings_covered_symbols()`: the blessed contracts loader `load_earnings_covered_symbols_from_export` (1.31.0, D271) from `_UNIVERSE_EXPORT_DIR` (= exports dir), **`max_age_days=None`**, `@lru_cache` (process-lifetime → activation at a restart boundary, journal-visible), `QueryError` → loud `earnings_coverage_export_unreadable` warn + `()` fallback (mirrors `_load_underlyings`/D078; `StaleExportError` subclasses `QueryError` but cannot fire with `None`). `_earnings_gated_pool()`: `(universe & covered) − _NO_EARNINGS_UNDERLYINGS` when covered is non-empty; **covered empty → exactly the v31 pool** (byte-identical); a present-but-DISJOINT covered set that would empty the pool → loud `earnings_coverage_empty_intersection` warn + v31-pool fallback (a bad manifest must never crash `rng.choice`). Universe order preserved (filter, not set ops) → deterministic (hard rule #6).
  - `enumeration/__init__.py` — H-3: `earnings_coverage_fingerprint()` folds into `enumeration_inputs_hash` **only when non-empty**, so the DORMANT identity stays byte-identical to v31 (an empty covered set shadows no draw). The `_NO_EARNINGS_UNDERLYINGS` frozen list is **retired from maintenance, retained as free defense-in-depth** (every entry unambiguously EPS-less; full deletion is a later cleanup bump once the manifest survives a funnel window).
  - `healthcheck_cmd.py` — `check_earnings_coverage_export`: OK-when-absent (dormant, never pollutes OVERALL — the `component_contributions` precedent), present & fresh → OK, > 45d → WARN (a dead publisher lets coverage ossify and re-opens the blind spot). The loader's `max_age_days=None` moves the staleness teeth here rather than halting generation on stale-but-usable coverage.
  - **Ride-along (Q49, docs/comments only):** `rv_rank`/`iv_rank` kernels compute a min-max RANGE-POSITION `(cur-lo)/(hi-lo)*100`, not a statistical percentile (verified in `crucible_engine_core`); relabeled at the two spec sites (`indicator_thresholds.py`) + one `docs/GRAMMAR.md` note. Calibrated gates UNAFFECTED (kernel-unit tuned through the funnel); matters only for cross-system threshold INTENT-mapping. The Crucible-side kernel-docstring fix is flagged for the next relay.
- **DORMANT-until-publish (state verified 2026-07-13):** Crucible has NOT yet published `earnings_covered_symbols*.json` to the exports dir → the loader cold-returns `()` → no intersection → **byte-identical to v31**. Emission proof (3000 cold, live registry): covered set `()`; `enumeration_inputs_hash` 2-part (v31 shape); 640 `event_momentum` configs over 94 real companies; **0 no-earnings leaks**. Activation is at Crucible's first publish + our next restart. The deploy relay nudges them to START the publisher.
- **TDD:** red first (ImportError on the new symbols) → green. New `tests/unit/test_enumeration/test_earnings_coverage_manifest.py` (dormancy == v31; blind-spot closure once a manifest is present; RTX-type covered names stay drawable; corrupt → warn+fallback; disjoint → v31-pool fallback; frozen-list composition; process cache) + fingerprint folds in `test_determinism_inputs` + `check_earnings_coverage_export` in `test_healthcheck`. All pre-v32 cold-start goldens UNCHANGED (dormant path byte-identical). NO contracts change (1.31.0 suffices). Related: [[D268]] (v30 stopgap), [[D271]] (loader adoption), [[D078]] (blessed-loader precedent).

**Deploy: DEPLOYED + VERIFIED 2026-07-13T22:30:46Z (commit `901479d`).** Ritual: stop 22:25:40Z (exit 143 normal) → v32 bump in the DOWN-window (grammar.yaml v31→v32 + header note + archive `v32.yaml` + `test_v1_grammar` v32) → uncontended full suite **1943 green** (v31 pre-stop AND v32 post-bump) + ruff + mypy --strict + both grammar hooks clean → commit → reset-failed → daemon-reload → start. New daemon **PID 2285486/2285491, NRestarts=0**; journal `grammar_version=v32 registry_hash=a85eb966fc81d47a`, `grammar_versions: recorded manual_bump row for v32`, `registry_loaded_from_export`, clean reconcile, **0** traceback/SchemaVersionMismatch/GrammarVersionError. **NO hot-read hazard** (the v31 deploy's lesson applied): the old v31 daemon stamped v31 to its last iteration (15:25:12 PDT); only the new daemon stamps v32 — the grammar.yaml byte-edit was deferred to the DOWN-window. `forge healthcheck` OVERALL=WARN (**12 ok, 2 warn, 0 crit**): the new **`earnings_coverage` line = OK** ("no export yet (dormant until Crucible starts the publisher)" — the OK-when-absent design), `contracts pin==installed 1.31.0`; both WARNs pre-existing/unrelated (`tmp_headroom` 4.4x, `wf_p25 drift`). DORMANT confirmed live: the daemon reads coverage `()` (no manifest published), so v32 emission is byte-identical to v31 until Crucible's first publish + our next restart.

---

## D273 — 2026-07-15 — Worst-quartile regime label CORRECTED to bear-only (Crucible per-block re-derivation): `regime_supply` complement headline narrowed; the un-shipped T2 ranging floor CLOSED. Telemetry + docs; daemon-inert

**Trigger:** Crucible handoff `../Crucible/docs/handoffs/FORGE_worst_quartile_regime_label_correction_2026-07-15.md` — a correction to the 06-13 T3a relay, the measured target behind the T2 regime-complement reservation ([[D144]]). The 06-13 label (bear 2.39× / ranging 1.33×) was computed from per-path Sharpes over convex-hull spans (36/45 paths ≈ near-full-period backtests through intervening TRAIN groups) — the exact pattern Crucible's 06-28 audit rated an integrity bug and fixed in the production portfolio campaign (`093b893`, live 07-02); the label's source artifact predated the fix and was never recomputed. Re-derived 07-15 per-block on the pinned era-C 342-component book (identical run_id/seed/weights/overlay, regime labeler unmodified): **bear 2.08× — the SOLE regime > 1; ranging 0.90 — at/below base rate** (hull bias reordered path ranks, Spearman 0.637 old-vs-new; ~half the worst-quartile membership changed). Their ask: narrow the complement target to bear-only; do NOT reduce the overall complement reservation or supply. Bear stays lift-not-share (~3.2% of worst-quartile session mass over a 1.6% base rate).

**Changed (versionless; no grammar byte, no enumeration change, submitted set byte-identical):**
1. `ranking/regime_supply.py` (the D144 shadow metric — the only executable T2 surface; the enforcement floor never shipped): `complement_selected`/`complement_pool` narrowed to bear-only; journal headline `complement(ranging+bear)` → **`complement(bear)`** (bear IS the headline; the separate bear callout dropped); docstrings record the corrected label + artifact pointers. Class names (`ranging_complement` et al.) FROZEN at their D144 spellings for journal grep/re-bucket continuity; ranging stays a visible CELL (mr's R1 ranging thesis is label-independent), no longer complement. `cli/main.py` call-site comment synced. TDD red→green (the 3 complement-semantics tests re-pinned first, failed for the expected reasons); `test_ranking` 265 green; ruff + mypy --strict clean. **Daemon-inert until the next restart** — the running v32 daemon imported the module at startup (same activation posture as D144 itself); rides the next deploy.
2. **The un-shipped T2 enforcement floor is CLOSED both ways:** the 06-16 [[D148]] re-scope made it RANGING-only (bear unsuppliable — Crucible's `tail_leg` overlay; no bearish stance in the grammar); this correction refutes ranging as a crater. A ranging reservation would spend batch slots on a regime the book is NOT disproportionately bad in. Docs: `t2-ranging-floor-and-supply.md` → CLOSED (do not ship); correction blocks in `tail-aware-ranker.md`, `worst-quartile-complement-supply.md` (Forge-suppliable complement now NIL — fully historical), `regime-orthogonal-arms.md` (the ranging/Path-C arm must stand on its own edge magnitude, no longer a crater fill; the bear half unchanged), `orthogonal-family-supply-for-pbo.md` (the ~85%-mr stream over-concentrates a no-crater regime bet — reinforces un-crowding).

**NOT changed (their explicit no-whiplash list + hard-rule discipline):** the shipped mr/ranging supply-growth levers ([[D150]]/[[D151]]/[[D167]] + successors) — also stream-quality/R1-thesis-justified, and Crucible asked for no supply reduction; `grammar.yaml` historical rationale comments (ANY byte change = a version bump per hard rule #10 — not warranted for prose); D103 `min_per_hypothesis`; capitulation-bounce v31 ([[D270]]) — **REINFORCED**, bear craters remain the confirmed and now sole over-represented regime; the 07-03 delta-hedged-straddle bear-crater directionality read (never depended on hull math); the [[D146]] magnitude worldview (the wall = edge MAGNITUDE) — orthogonal to which regime over-populates the tail.

**Calibration sweep (their caveat):** corrected era-C basket CPCV p25 = **0.88, not 1.14** — the pool-level wall is bigger than the stale figure suggested. Repo + memory scan: NO Forge calibration anchored on 1.14 (every `1.14` hit is a contracts-version literal). The 1.343 standard-basis honest wall is a different basis (refit re-gates) — unaffected. Ranker training targets unaffected: per-config gate numbers come from the production gate path, not the hull-biased artifact (Crucible: no promoted book affected).

**Pending Crucible-side (watch, no Forge action):** their L2 selective-de-gross re-check (triggers had inherited "bear,ranging") re-running on the fixed engine — separate relay if its verdict moves; their §20 correction entry pending their operator sign-off. Related: [[D144]], [[D146]], [[D148]], [[D270]].

---

## D274 — 2026-07-15 — Test hermeticity vs the now-LIVE earnings-coverage manifest: autouse dormant-`()` pin in conftest. Test-only; production untouched; unblocks the D273 deploy

**Trigger:** deploy-preflight NO-GO for the D273 deploy — 9 sampler cold-start goldens red (first-draw divergence) on an enumeration surface D273 never touched. Root cause: **Crucible started the earnings-coverage publisher 2026-07-13T23:32:11Z** (`earnings_covered_symbols_2026-07-13T233211Z.json`, ~1h after the v32 deploy — the activation the D272 relay nudged for). `sampler._UNIVERSE_EXPORT_DIR` is resolved at module IMPORT time, before `_isolated_home` patches `Path.home()`, so the v32 coverage loader read the operator's LIVE manifest inside the test run → the earnings-gated pool intersection activated mid-suite → every exact-hash golden diverged. A D272 test-hermeticity gap (its own manifest tests are hermetic; the pre-existing goldens silently gained a new live-file dependency), exposed the moment the publisher went live.

**Fix (tests only, no src byte):** (1) global autouse fixture `_dormant_earnings_coverage` (`tests/conftest.py`) pins `sampler._load_earnings_covered_symbols` to `()` — the dormant default the goldens are pinned under; manifest-behavior tests keep overriding per-test. (2) The 3 loader-path tests re-target `cache_clear` at the direct-import original (the module attr is now the patched stub). (3) Second interference class caught by the re-run preflight: the 3 `test_determinism_inputs` coverage-fingerprint tests exercise the REAL loader via a dir-patch — they now re-bind the original (captured at collection time, before fixtures run) over the autouse stub per test. Verified: sampler goldens + manifest + determinism + invariants green; full preflight GO (see D273 deploy note).

**Deliberately NOT fixed:** `_load_underlyings`' matching live-coupling (goldens currently pin against the LIVE universe export; re-pointing it means re-baselining every golden) → logged as **Q50** with the durable options; a separate, non-deploy-blocking test-infra decision. Production untouched BY DESIGN: the daemon SHOULD read the live manifest — activation-at-restart is the operator-approved D272 path, and the D273 deploy is the activating restart (manifest sanity-checked pre-restart: 140 covered symbols, universe∩covered = 87/124, excluded = ETFs/index products + a few genuinely uncovered names (ABNB, ARM, BRK.B, V, FCX, WBD, WDC) — non-empty, non-disjoint, no fallback warn expected). Related: [[D272]], [[D273]], [[D078]], Q50.

---

## D275 — 2026-07-15 — Generation-health addendum + late-relay batch folded: v33 change set STAGED (docs-only); receipt relay with one ledger correction + one contradiction flag

**Trigger:** operator carried `FORGE_generation_health_capitulation_addendum_2026-07-15.md` mid-D273-deploy. Its §C revealed a relay-publication failure on Crucible's side: a 07-12/07-14 batch (`FORGE_resid_vix_region_followup_2026-07-13.md`, `FORGE_days_to_nfp_cpi_threshold_prior_2026-07-14.md`, `FORGE_earnings_manifest_published_2026-07-13.md`) never reached Forge — explaining the "zero adoption" they measured. Verified receipt history against STATUS/git: the fourth relay they list as unreceived (`FORGE_capitulation_v31_followup_2026-07-13.md`) WAS received + folded 07-13 (`ab6a609`) — corrected in the response.

**Folded (docs/relay/proposal staging ONLY — no code, no grammar byte, no daemon touch):**
1. `docs/proposals/v33-generation-health.md` — SCOPING for one operator-gated v32→v33 bump, items independently strikeable: resid_vix concentrated sweep (HIGH — 3 pipeline-native in-book WF-gate passes confirm the region; density tens-per-neighborhood; solo-reject expected for the family), days_to_nfp/cpi regime_range (7,60)→(7,30) (~42% inert, ceilings 35/34), capitulation rv_rank gate drop (their clean sweep says unhelpful-to-harmful; 69/69 dead; BLOCKED on the contradiction below), retire pre_earnings_setup×vol_event, drop trend dsj+gamma_flip double-gate, retire option_momentum, remove gamma_flip-as-MR-directional. Reallocates ~1,000 structurally-dead configs/wk into the confirmed region.
2. `PROMPT_CRUCIBLE_GENERATION_HEALTH_RECEIPT.md` (held for carry) — receipt table + the in-place-adoption answer (NO — hard rule #6; stop expecting it) + the **§A.3 contradiction flag**: "reweight toward index/broad-ETF" cites the underlying-bounce probe, but their own 07-13 honest-pricing probe puts the option-arm index cell NEGATIVE (−0.046/−0.067; lone survivor single-name high_vol +0.036 m2m). Adjudication requested before moving emission share; §A.2 (gate-off split) noted as superseded by their own followup.
3. Q49 updated (Crucible kernel docstrings FIXED — both shim + engine-core relabeled range-position); earnings-coverage memory flipped to ACTIVATED (verification of the covered-set journal line rides the D273 deploy watcher); the process failure noted in the relay (4 of 5 relays reached us only via operator carry).

**Deliberately NOT done:** any v33 build (operator-gated; and item 3 additionally blocked on Crucible's §A.3 answer); any capitulation emission-share change (contradicted evidence); any reweighting toward the addendum's index ask. Related: [[D270]], [[D264]], [[D272]], [[D273]], [[D274]], Q45, Q49.

---

## D276 — 2026-07-15 — v33: generation-health change set — resid_vix CONFIRMED-region concentration + four structurally-dead-cell retirements + the nfp/cpi inert-threshold fix. Operator-approved ("go ahead with v33")

**Trigger:** operator go on `docs/proposals/v33-generation-health.md` ([[D275]] — Crucible's generation-health addendum + the late-published 07-13/07-14 relays). ~1,000 configs/wk were burning in cells that are structurally dead (>=90% WF=0.0, median OOS trades <=6 — below the trade floor by construction) while the highest-value confirmed ask had zero supply. One v32→v33 enumeration-policy bump; **`rules:` text UNCHANGED** — every retirement is EMISSION-side (sampler pools), so the submitted lineage stays grammar-valid under the untouched predicates (hard rule #1; the D270 pattern). **Item 3 of the proposal (capitulation rv_rank gate drop) did NOT ship** — blocked on Crucible adjudicating their index-vs-single contradiction (the receipt relay).

**The change set (all TDD red→green; new `tests/unit/test_enumeration/test_v33_generation_health.py`, 14 tests):**
1. **resid_vix concentrated sweep (the headline; their 07-13 followup: 3 pipeline-native in-book WF-gate passes, best cpcv carrier 1.4099).** All keyed on the `residual_momentum` directional (the D270 per-directional scoping): formation `window` (63,252)→**(70,160)**, `skip` (0,21)→**(7,21)** (converters 73/126/147 × 7/15/21; skip<7 never converted); directional percentile (0.60,0.90)→**(0.65,0.85)**; regime pool **PINNED to {vix_term_slope, hurst}** (`_compatible_regimes` — the density lever); gate bands per-directional in `_regime_signal_params` — vix_term_slope **[0.1,0.7]** absolute (converters 0.22/0.66), hurst **[0.40,0.50] percentile** (the cpcv carrier's p41-p46); structure pinned by evidence — `_cohort_xsect_probability` returns 1.0 for resid (every converter is monthly xsect-rank; the nearest confluence config trades 3×/8.5y) and `_rank_combiner` emits **monthly / rank_k {5,10} / long_only-biased 0.75** (2 of 3 WF passes long_only; long_short explorable); **CHAINED draws host no resid** (X1/X2 chain signals are rank-flag-excluded → would force the measured-dead confluence arm; the empty regime pool drops resid from candidates, C1-correct). dsj-veto dual-gate arms KEPT (explicitly requested). Solo-reject is EXPECTED for this family — never a kill signal.
2. **days_to_nfp / days_to_cpi `regime_range` (7,60)→(7,30)** — ceilings 35/34 (max inter-event gap), ~42% of old op-"<" draws provably inert (their 07-14 relay, n=22,508); mirrors days_to_opex. Their op-flip guardrail documented at the table entry.
3. *(HELD — see trigger.)*
4. **pre_earnings_setup retired from vol_event EMISSION** (`_VOL_EVENT_REGIME_EXCLUDED_IDS`, search_space) — ~450/wk at 91-100% dead; ve conversion 0.1%. R3 predicate untouched.
5. **trend dsj veto never stacks on a gamma_flip primary gate** (`_eligible_regime_vetoes` — pure filter, no rng) — the AND-pair 93-98% dead (~300/wk); other pairings keep the veto.
6. **option_momentum retired from directional EMISSION** (every hypothesis; `_DIRECTIONAL_POOL_EXCLUDED_IDS`) — 100% dead, ~0 conversions in the month since the v19 min_months fix. `tests/invariants/test_option_momentum_activation.py` FLIPPED from activation-honesty to a RETIREMENT invariant (re-admission must be a deliberate bump, never a pool-rebuild side effect); threshold-table entry kept (lineage interpretability).
7. **gamma_flip_distance_pct retired as a MEAN_REVERSION directional** (~100/wk dead in every gate combination) — MR-scoped; it remains the D107 R1 regime gate and the other dealer directionals keep their D062 admission.

**Byte-identity (hard rule #6): licensed where changed.** The v27 cold-start golden re-pinned — divergence exactly at the trend positions that can draw resid (2-8, 12-14); non-trend positions 0-1/9-11 byte-identical; every pre-v27 golden untouched. Legacy v18/v19 activation tests flipped to retirement pins (the vacuous ETF test deleted — T1.4 keeps its days_to_earnings coverage). Ride-alongs: Q49 range-position relabel in `custom_predicates.py` comments (closes the grammar-change.md pending list — Crucible fixed both kernel docstrings 07-13); GRAMMAR.md emission-status notes at C2/R3 (rule text unchanged, doc-sync clean).

**Verification:** scoped suite 789 green (enumeration+grammar+invariants); ruff + mypy --strict clean (102 files). **Emission proof (3000 cold, live registry):** option_momentum 0; MR gamma_flip directionals 0; pre_earnings_setup gates 0; trend gamma_flip+dsj pairs 0 (dsj vetoes alive on other gates: 138); nfp/cpi gates n=302, max threshold 29.9; **resid 39 configs, 100% in-spec** — gates {hurst 22, vix 17}, dual-gate dsj 20, rank_k {5:22, 10:17}, direction {long_only 28, long_short 11}, all monthly xsect-rank. Density: the box collapse (2 gates vs ~7, 1 structure cell vs 12, narrowed knob spans) delivers the tens-per-neighborhood ask at unchanged emission share; the learned loop owns any share lift (D186 — no manual weight override).

**Deploy:** see STATUS (the ritual + the v33 stamp verification). Relay owed: version string + deploy timestamp → Crucible for `crucible funnel --compare v32 v33`. Related: [[D275]], [[D264]], [[D270]], [[D138]], [[D135]], [[D107]], [[D258]], Q49 (closed), Q50/Q51 (test-infra).

---

## D277 — 2026-07-15 — Census #2 (dead dimensions) triaged: v34 staged (2 items), 1 ask already shipped (D257), 1 name not ours, 2 blocked on Crucible adjudications. Docs-only

**Trigger:** operator carried `FORGE_grammar_census_dead_dimensions_2026-07-15.md` (companion to the [[D275]] addendum; 228,021 configs decided 07-01→07-15; healthy baseline 8-14% gate / 7-23% directional component rates). Every ask verified against our side before staging — three of five resolve without a build:

- **Ask 2 (retire `zscore_reversion_exit`): ALREADY SHIPPED** — [[D257]]/v25 (2026-07-08, on their own inert-pair-exits relay) dropped it from mean_reversion; it remains only on `relative_value` (the pair template — their suggested fence IS the as-built state). Their 13,947 declares are pre-v25 queue backlog (the census counts DECIDED, which straddles submission eras). Verification offered: re-census split by `grammar_version >= v25` → ~0; post-v25 counterexamples are a real bug, send hashes.
- **Ask 1, ASML: NOT IN OUR UNIVERSE** (tier lists verified) — our single-name draws cannot produce it; their 236 ASML configs are rank-basket legs or stale cohort. Also flagged: generation exclusion can never cover rank baskets (underlying=None trades THEIR universe) — their contemplated queue-time liquidity preflight is the complete fix.
- **Asks 4+5 (event-proximity family share / vol_event share): BLOCKED.** Ask 4 deferred on their own condition (revisit after the nfp/cpi prior fix — which is v33, deployed today; read that cohort first); structurally it collapses into ask 5 (R3's pool is exclusively event-proximity). Ask 5 contradicts their OWN active ask: the [[D216]] orthogonal-family floor (`volatility_event >= 0.20`, ACTIVE in today's journal) exists because their PBO relay named single-name ve the sole validated PBO-orthogonal family; the census now calls the same arm edge-absent (0.1-0.3% across all directionals). Adjudication requested — the second open one in the thread (with §A.3 capitulation). The floor is operator-owned either way; no unilateral change.

**Staged for v34 (`docs/proposals/v34-census-dead-dimensions.md`, operator-gated):** (1) BKNG + BRK.B single-name exclusion (100% WF=0.0 at n=703/431 — per-contract volume never clears the selector liquidity floor; frozen list acceptable because the mechanism is Crucible-measured per-name, retirable when their preflight ships; re-admission on their relay). (2) `gamma_flip_distance_pct` retired as a regime gate from EMISSION globally (12,088 uses, 0.1% component rate, 79% WF=0.0 — supersedes v33's narrower assumption that single-gated cells were alive; D107 lineage noted; predicates/rule text untouched; capitulation unaffected — its gate is pinned rv_rank).

**Outbound (held for carry):** `PROMPT_CRUCIBLE_CENSUS_RESPONSE.md`. No code, no grammar byte, no daemon touch this fold. Related: [[D276]], [[D257]], [[D107]], [[D216]], [[D275]].

---

## D278 — 2026-07-15 — v34: census dead-dimension retirements — BKNG/BRK.B excluded from single-name sampling + gamma_flip_distance_pct retired as a regime gate globally. Operator-approved ("go ahead with v34")

**Trigger:** operator go on `docs/proposals/v34-census-dead-dimensions.md` ([[D277]] — Crucible census #2, 228,021 configs decided 07-01→07-15). Both items EMISSION-side; `rules:` text UNCHANGED (submitted lineage stays valid). The census's other three asks resolved without a build (D277: zscore already retired at v25/[[D257]]; ASML not in our universe; event-family/ve share blocked on the v33 cohort read + Crucible's orthogonal-floor contradiction).

**The change set (TDD red→green; new `tests/unit/test_enumeration/test_v34_census_retirements.py`, 6 tests):**
1. **`_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS = {BKNG, BRK.B}`** filtered from `_pick_underlying`'s pool AFTER the earnings-gated branch (covers both pools; order-preserving, #6). 100% WF=0.0 at n=703/431 — zero contracts clear the v1 selector's OI/volume floor (BKNG additionally: one ATM contract's premium exceeds the 2%-of-equity budget). Frozen list BY DESIGN (Crucible-measured per-name against their chain data); re-admission on their relay; the list retires when their queue-time liquidity preflight ships. Cannot cover rank baskets (their universe) — flagged in the census response.
2. **`_REGIME_GATE_GLOBALLY_EXCLUDED_IDS = {gamma_flip_distance_pct}`** applied uniformly to every hypothesis's regime pool at the END of `_build_regime_pool` (one application point — a future pool rebuild cannot silently re-admit). 12,088 uses, 0.1% component rate, 79% WF=0.0 in EVERY pairing — supersedes v33's narrower assumption that single-gated cells were alive (D276 test re-pinned to record the supersession). The D107 R1/R2 predicates still accept it; its vol_event DIRECTIONAL use untouched (census §5 = Crucible's open adjudication); capitulation unaffected (gate pinned rv_rank); relative_value already excluded it (rank-flag exclusion). The v33 dsj×gamma_flip veto filter KEPT as defense-in-depth (unit-pinned — the emission path can no longer exercise it).

**Byte-identity (hard rule #6): licensed where changed — this bump's re-pin is BROAD by nature:** the underlying-pool filter shifts the underlying draw on (nearly) every position, so all 7 cold-start golden constants re-pinned in one sweep (regenerated under the D274 dormant-coverage condition; every relational split assert between goldens re-verified true; the d270 carrier-in-30 and v27 carrier-in-15 asserts re-verified). 4 search_space exact-tuple tests flipped to retirement pins; the vacuous v33 dsj-emission test replaced by the unit-level filter pin.

**Verification:** scoped suite 794 green; ruff + mypy --strict clean; **emission proof (3000 cold, live registry):** BKNG/BRK.B 0 of 2,356 single-name draws; gamma_flip regime gates 0 everywhere; gamma_flip ve DIRECTIONALS alive (83); MR gate mix intact at 6 gates (market_rv 213 / rv_rank 113 / vol_regime 73 / realized_vol 71 / hurst 66 / iv_rank 53); trend at 5 (hurst 149 / vix 133 / market_state 127 / adx 124 / rv_rank 70).

**Deploy:** stop 16:47:15Z (exit 143) → v34 bump in the down-window + archive + `test_v1_grammar` pin → both grammar hooks Passed → uncontended full suite **1959 green** → commit → start (evidence in STATUS). Relay owed: `crucible funnel --compare v33 v34`. Related: [[D277]], [[D276]], [[D257]], [[D107]], [[D268]] (frozen-list precedent).

---

## D279 — 2026-07-15 — Both Crucible adjudications ANSWERED and folded: capitulation gate-drop GREENLIT (staged as the v35 loosening proposal `4d35a046`, operator-gated); ve floor STANDS with a named decision point. Docs-only

**Trigger:** operator carried `FORGE_adjudications_capitulation_ve_floor_2026-07-15.md` — answers to the two contradictions Forge flagged (receipt relay §A.3; census response item 5), with new book-margin evidence (`probe_results/bear_margin_sweep.json`: each arm margin-evaluated at the proven 0.175 slot on the champion-shape 2-leg book).

**§A adjudicated — Forge's refusal VALIDATED, and the path is now unambiguous:**
- **Index/broad-ETF reweight WITHDRAWN** ("a drafting error against our own evidence"): triple-refuted — the 07-13 honest pricing we cited, plus new slot evidence (QQQ/SPY bare-drop legs return the baseline byte-identically; 10-14 solo trades/8.4y = book-level no-op).
- **Single-name bare-drop arm KEPT, value hypothesis CORRECTED: "marginal center lever," NOT a bear-crater complement.** Slot test = the FIRST positive slot delta of the program (cpcv +0.0267 → 1.4573, wf +0.0794) but bear-block delta exactly 0.0 (8 of 13 trades in 2025, zero in 2022).
- **Ship ask 1 (drop the rv_rank gate)** — last blocker removed. §A.2 nuance recorded: the 07-13 "bare-drop arm IS the gate-off cohort" applied to the legacy-INERT probe cohort; v31's [50,80] kernel-unit gates BIND harmfully, so NO gate-off cohort exists anywhere until the drop ships. **NO replacement gate** (market_rv>0.20 AND drop co-fires 2×/8.4y — born-dead). swing_short rider optional, low stakes.
- **Bear-block FYI (reinforces D148/D273):** nothing in v1 moves the bear block without paying more elsewhere — the one candidate that lifted 2022 (+0.0345, stress-gated GLD call) costs net cpcv −0.035: hedge-shaped, overlay/construction-axis, not generation. All bear-block numbers are n=1-episode (2022) evidence under the corrected label.
- **Staged: OPEN_PROPOSALS `4d35a046` (PENDING, v35)** — the gate-drop is a LOOSENING with a §3.5 rule-surface component (R1 requires a regime gate on MR; the bare-drop arm needs an R1 per-directional carve-out, the D270 C2-carve-out pattern one level deeper) → hard rules #1/#4: operator approval required. Sampler side: drop the `_CAPITULATION_REGIME_ID` pin, emit no gate for this directional, keep the veto skip; optional scoped D102 exception for swing_short.

**Census item 5 — the ve ≥ 0.20 floor STANDS (no whiplash):** their grounds — (1) the floor's justification is survivor PBO-orthogonality, which conversion rate does not measure; (2) the 0.1-0.3% figure is a v32-era number about an emission mix v33 already replaced (pre_earnings×ve retired, nfp/cpi prior fixed). **Named decision point: the `funnel --compare v32 v33` read** — if the fixed-gate v33 ve cohort still converts at noise AND resid_vix supplies comparable PBO-orthogonal components, they revisit the floor as a proper decision-log entry. Watch item; no Forge action.

**Bookkeeping, both census verifications resolved Forge's way:** ASML = stale v22/v24 cohort drained by 07-07 (ask withdrawn; our tier lists clean); `zscore_reversion_exit` = ZERO post-v25 declares outside relative_value (the D257 retirement VERIFIED by their re-census). **Their §25 row-45 queue-time preflight SHIPPED** (`UnderlyingChainStarvedError`: outcome-based trailing-30d, ≥25 decided, ≥95% WF-median 0.0, self-healing; flags exactly BKNG/BRK.B/ASML, passes healthy names) — live at their next inbox-watcher restart. **Watch: once its rejects appear in our telemetry, the v34 `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` frozen list is retirable on our schedule** (a small versionless-adjacent cleanup bump).

No code, no grammar byte, no daemon touch. v35 awaits the operator verdict on `4d35a046`. Related: [[D270]], [[D275]], [[D276]], [[D277]], [[D278]], [[D148]], [[D273]].

---

## D280 — 2026-07-15 — v35: capitulation BARE-DROP — the rv_rank pin dropped; the FIRST R1 per-directional gate exemption (enforced at BOTH gate surfaces incl. the S3 cardinality, discovered at build time); swing_short rider. Operator-approved loosening (OPEN_PROPOSALS `4d35a046`)

**Trigger:** operator "approve" on `4d35a046` ([[D279]] — Crucible's 2026-07-15 adjudication: ship the gate-drop, NO replacement gate, index arm withdrawn, value hypothesis corrected to "marginal center lever": the bare-drop single-name arm posted the program's FIRST positive slot delta, cpcv +0.0267 / wf +0.0794 at the proven 0.175 slot, bear-block delta exactly 0.0). The v31 pinned [50,80] kernel-unit gate bound harmfully — 69/69 decided dead, median 4 OOS trades — and until the drop, NO gate-off cohort existed anywhere (their §A.2 nuance).

**The change set (TDD red→green; new `tests/unit/test_enumeration/test_v35_capitulation_bare_drop.py`, 5 tests):**
1. **R1 carve-out** (`custom_predicates._R1_GATE_EXEMPT_DIRECTIONALS = {("momentum",)}`) — keyed on the directional's EXACT indicator tuple; every other MR directional still requires its gate (pinned by test).
2. **S3 carve-out — the build-time discovery.** The R1 exemption alone was INSUFFICIENT: §3.5 S3's generic min-1 `regime_filter` cardinality rejected every gate-less config at the validator (`S3: count 0 below min 1`). The gate REQUIREMENT lives at two rule surfaces; the same exemption now applies in `predicates.evaluate_cardinality`, scoped to exactly the S3 shape (that field, a min bound, count 0) + the exempt tuple set. **Rules: yaml text UNTOUCHED at both** (the D270 carve-out convention) — but this IS a two-surface rule-surface change, disclosed as such; the approved proposal named only R1, and the S3 half is the same approved intent (bare-drop emittable) discovered mechanically.
3. **Sampler:** `_compatible_regimes` momentum → `()` (pin dropped); `_directional_candidates` admits momentum with no regime partner (chain shape preserved from v31: vol_target never hosts capitulation — previously a C1 side effect, now explicit policy; kelly may); `_select_bucket_directional_regime` returns `regime_id=None` for the exempt id (keyed on the ID, not pool emptiness — a genuinely-broken empty pool elsewhere still fails loudly), consuming NO regime rng; `_base_signals` (extracted) appends the gate only when `regime_id` is not None. The calm-side veto skip stays. The v31 pin constants retained for lineage interpretability.
4. **swing_short rider** (their "still fine, low stakes"): `_CAPITULATION_K_MULTIPLIERS = (1,2,3,4)` for this directional only, in BOTH `_dte_target` and `_directional_bucket_options` (structural mass ~1:3 short:mid); every other directional keeps D102's k∈{2,3,4} exactly.

**Byte-identity (hard rule #6): the cleanest bump of the day — ZERO golden re-pins.** Per-index candidate seeding means only capitulation configs' own draws changed; the v31 golden slice (no carrier in 15) is byte-identical, the carrier stays at position 24, and every relational assert holds. Legacy flip: `test_d270_capitulation_reachable_and_grammar_valid` re-pinned to the bare-drop shape.

**Verification:** scoped suite 799 green; ruff + mypy --strict clean; full suite **1964 green** post-bump uncontended; both grammar hooks Passed. **Emission proof (3000 cold, live registry):** 52 capitulation configs (8.6% of MR), 100% in-spec — ALL gate-less, drop triggers in the audited band, buckets swing_mid 42 / swing_short 10, sizers kelly 29 / fixed 23 (vol_target 0), time_stop n_bars [6,15]; **zero gate-less leaks on other MR directionals**. GRAMMAR.md carve-out notes at S3 + R1 (doc-sync clean); proposal `4d35a046` flipped APPROVED with decided_at.

**Deploy:** evidence in STATUS. Relay owed: v35 + `funnel --compare v34 v35` (capitulation cohort split; solo-reject EXPECTED — in-book fold-column judging per the adjudication). Related: [[D279]], [[D270]], [[D276]], Q49 (the [50,80] mis-calibration this finally repairs).

## D281 — 2026-07-15 — Exit-duration priors relay triaged: both time_stop n_bars asks VERIFIED against the live stream and staged as v36 (trend swing_long → U[8,10]; MR swing_mid → U[8,15]). Docs-only; build awaits operator go

**Trigger:** inbound `FORGE_exit_duration_priors_2026-07-15.md` (prior-concentration ask, the resid_vix/nfp-cpi class; probe-grade evidence, funnel-arbitrated). Their two findings: (1) trend swing_long's day-5 time_stop takes 84-88% of exits and CUTS WINNERS (win-rate 0.45→0.74 with longer holds); n_bars=10 improves cpcv 6/6, wf 5/6, AND maxDD inside their §6.5.2 [3,10] box — with an explicit do-NOT-pass-10 tail warning (n=21: comp0 maxDD -44%). (2) MR swing_mid's [5,15] box is right but its floor HURTS the bounce (plateau 8-20, peak 12; baseline median hold 31d) — shift mass to [8,15].

**Verification (live DB snapshot, 117,400 submissions 07-08→07-15):** their premises are exact. Trend swing_long w/ time_stop = 6,775 (5.8%), ALL param-less → Crucible registry default 5 (the D270 comment already documents the default; Forge has only ever emitted n_bars on the capitulation directional). MR swing_mid w/ time_stop = 11,489 (9.8%) — 11,436 param-less + 53 capitulation at D270's U[5,15]. Trend swing_mid w/ time_stop = 26,325 — NOT touched (their explicit "do not touch other buckets on this evidence").

**Staged (`docs/proposals/v36-exit-duration-priors.md`):** two emission-side items, one v35→v36 bump, ZERO rule surfaces (cleaner than v35 — no predicate change, pools untouched). Mechanism = the D270 tail-draw pattern widened to a (hypothesis × bucket) range table in `_build_exits` (which gains a `bucket` param, already in scope at sampler.py:940): (MR, swing_mid) → U[8,15]; else capitulation directional → U[5,15] (the swing_short leg keeps D270); else (trend, swing_long) → U[8,10]; else no emission. **Two disclosed scoping calls, veto window open via the receipt relay:** (1) capitulation swing_mid INHERITS U[8,15] — their §2 names the bucket, not a directional; [8,15] ⊂ their own capitulation sweep box, center 11.5 ≈ probe hold 10; the v35 bare-drop pane is version-split and the gate axis is orthogonal — but the arm is 8h old, so Crucible may freeze its chassis instead. (2) Both asks implemented in their STRONG form (uniform ranges, zero floor mass) — flagged for correction pre-build. Legacy flip queued: `test_d270_non_momentum_time_stop_params_unchanged` narrows to the new scoping; the D270 chassis [5,15] assertion survives ([8,15] ⊂ [5,15]). Goldens re-pin licensed where changed (~15.6% of draws gain one randint).

**Sequencing:** independent of their in-flight champion-side family-PBO swap check (their §2 states the generation-side ask is free-standing). Deploy relay will ask `funnel --compare v35 v36`. **Outbound held for carry: `PROMPT_CRUCIBLE_EXIT_DURATION_RECEIPT.md`** (verification table + the strong-form readings + the capitulation-overlap veto). No code, no grammar byte, no daemon touch this fold. Related: [[D270]], [[D169]], [[D280]], [[D257]] (their §2 sweep finally addresses the D257 "what should MR declare instead" CAVEAT — the answer their evidence points to: time_stop at [8,15], not target_exit).

## D282 — 2026-07-16 — v36: exit-duration prior concentration BUILT — time_stop n_bars: trend swing_long U[8,10], MR swing_mid U[8,15]; capitulation VETO-frozen at D270's U[5,15] (both buckets). Awaiting operator deploy go

**Trigger:** Crucible's scoping response (`FORGE_v36_scoping_response_2026-07-15.md`, "Build on."): readings 1+2 CONFIRMED as staged in [[D281]] (strong forms — n_bars=5 measured actively harmful, -0.382 p25-proxy vs +0.161 at 8; [6,7] unsampled interpolation, zero floor mass intended); **capitulation inheritance VETOED on cohort hygiene, not merits** (the v35 bare-drop pane accumulates ~50/day and needs a few hundred configs; [8,15] inheritance re-opens after the v34-vs-v35 pane read, their relay).

**The change set (TDD red→green; new `tests/unit/test_enumeration/test_v36_exit_duration_priors.py`, 5 tests):**
1. **`_time_stop_nbars_range(hypothesis, directional_id, bucket)`** — the D270 tail-draw pattern widened to a range table. Resolution order per the veto: capitulation directional → `_CAPITULATION_TIME_STOP_NBARS_RANGE` U[5,15] FIRST (both buckets — must not fall through to the MR swing_mid cell); else (mean_reversion, swing_mid) → U[8,15]; else (trend_continuation, swing_long) → U[8,10]; else None (param-less, Crucible registry default 5). `_build_exits` gains a `bucket` param (threaded from `sample_config`'s already-selected bucket); the extra randint stays AFTER the standard exit draws.
2. **Legacy flip:** `test_d270_non_momentum_time_stop_params_unchanged` re-pinned from "params == {} everywhere non-momentum" to the new cell scoping (bare cells still asserted bare).

**Byte-identity (hard rule #6) — the shared-stream licensing discovery.** `enumerate_candidates` draws every attempt (accepted AND rejected) from ONE stream (`SeedHierarchy(seed).rng("enumeration")`), so a scoped attempt's extra randint cascade-shifts everything after it — the v35 "zero re-pins" experience was a per-seed-tests artifact, NOT the enumerate-golden model. All 7 cold-start goldens re-pinned under a mechanical license (`license_v36_goldens.py`, scratchpad): OLD-behavior monkeypatch reproduces every prior pin byte-exact (harness fidelity), and every variant's first divergence == its first scoped attempt (cohort golden: attempt 5; PRE/DSJ/V26/V29/V31: attempt 2; V27: attempt 9). Positions BETWEEN scoped attempts heal via `_randbelow` rejection variance (variable word consumption re-aligns the stream) — e.g., V31 diverges [2..8], heals [9-11], re-diverges exactly at its second scoped attempt 12. One relational assert legitimately moved: the DSJ-vs-PRE split 3 → 2 (position 2 is the first scoped attempt in BOTH; the dsj-serving registry's larger pools offset the stream so the same config draws its n_bars word at a different index) — re-pinned `active[:3]` → `active[:2]` with the cause in the comment. All other inter-golden prefix relations preserved (V27[:2]==V26[:2]; V29[:3]==V26[:3]; V31[:3]==V29[:3]; mutual splits moved 3→5/3→6 under the cascade, asserted).

**Verification:** enumeration scope 436 green; unit+invariants **1907 green**; ruff + ruff format + mypy --strict clean. **Emission proof (3000 cold, live registry, 0 validator rejects, 0 violations):** trend swing_long 38 carriers all in [8,10] (full coverage 12/10/16); MR swing_mid non-cap 163 carriers all in [8,15] (~uniform, ZERO <8); capitulation swing_mid 15 in [6,15] WITH floor mass <8 (veto honored), swing_short 6 in [5,14]; all other carriers bare (event_momentum 606, relative_value 301, vol_event 274, MR swing_short 113, trend swing_mid 250) — zero unscoped leaks.

**NOT in this build (deploy down-window items):** grammar.yaml v36 bump + header note + archive `v36.yaml` + `test_v1_grammar` pin. Deploy ritual per `docs/tasks/deploy.md` (ruff format BEFORE commit, commit BEFORE start — the v35-proven order). Deploy relay will ask `funnel --compare v35 v36`. Related: [[D281]], [[D270]], [[D169]], [[D280]] (the veto protects its pane), Q50 (the goldens' live-export coupling — unchanged by this build).

**Deploy-time addendum — Q50 bit MID-DEPLOY (the second environment-caused preflight NO-GO in two days).** The first `deploy_preflight.sh` run (operator "deploy it") failed the same 9 golden tests at **position 0** — impossible for the v36 draw. Cause verified: **Crucible's July tier export (`universe_tickers_2026-07-16T082754Z.json`, landed 08:27:54Z — ~17 min before the preflight) removed FCX/WBD/WDC/VIX/BKNG/XLY/XLB and added APH/MDT (118 names)**, exactly as pre-announced in their cohort-read relay §2; `_load_underlyings` reads the live export (the OPEN half of Q50; the earnings half was pinned dormant in D274). All 7 goldens re-pinned a SECOND time under the new universe with the licensing harness re-run environment-matched (old-code vs new-code BOTH under the new export): every variant's first divergence == its first scoped attempt, same attempt positions as before (cohort 5; PRE/DSJ/V26/V29/V31 2; V27 9). The DSJ-vs-PRE relational split returned to position 3 under the new pins (the first-re-pin's 3→2 move was a word-index coincidence of the OLD universe) — assert restored to `[:3]`. Post-bump uncontended suite **1969 green**. Consequences: (1) the RUNNING v35 daemon held the OLD universe until this restart, so the v35→v36 funnel boundary carries BOTH the exit-prior shift AND the universe shrink — flagged in the deploy relay (their own announced change); (2) Q50 escalated — the durable fix (a D274-style conftest universe pin) is proposed as part of the v37 build, where the goldens re-pin anyway for their 4-name exclusion ask.

## D283 — 2026-07-16 — Cohort-read follow-ups triaged: §4 arm-share question ANSWERED with data (1.3% submitted == 1.3% decided — nothing eaten; 8.6% was enumeration-basis); both asks staged as v37 (+Q50 durable fix); ve decision point re-anchored to v32-vs-v35. Docs-only

**Inbound `FORGE_cohort_read_followups_2026-07-16.md`** (first v33/v35 cohort reads; "nothing here gates v36" — v36 deployed first, same session, D282). Dispositions:

1. **§1 (good news, recorded):** the v35 bare-drop repair CONVERTS — capitulation median 13 OOS trades (gated era: 4), WF-zero 70% vs 97.3%, real WF spread (max +0.645), CPCV computing for the first time in the family. Structurally-dead criterion no longer met. Solo-reject discipline unchanged.
2. **§4 (ANSWERED, no build): the 8.6% was enumeration basis.** Measured on the live DB (submissions since the v35 deploy): capitulation = **23/1,741 = 1.3% of submitted MR — matching their decided 1.3% EXACTLY**. Nothing is lost between submission and decision; the compression is generation-side learned-lane composition on a no-history family (cold mix is unweighted). Their fair-read pace (mid-day 07-17) stands — no slip. **DTE mix:** submitted 10 short/13 mid (~1:1.3) vs structural 1:3 — the D105 fallback composes MR-wide learned bucket weights onto a no-history directional; drifts toward structural as the family mints cells. NOT noise, NOT a bug, NO manual boost (that would thumb the pane being read).
3. **§2 (staged, v37 item 1):** SOXX/LLY/GS/MSTR → `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` on v34 terms (96.1-99.8% WF-zero at n≈1,000 each on their row-45 guard; all four verified in our July universe; ~4.4k wasted draws/wk). Their guard telemetry also confirms the v34 exclusion holds (zero BKNG/BRK.B stragglers).
4. **§3 (staged, v37 item 2): resid gate mix 50/50 pin.** Diagnosis VERIFIED in `_pick_regime` (sampler.py:1471-86): the learned regime-gate posteriors compose onto the v33-pinned two-member pool — hurst's minted history vs vix_term_slope's sparse prior ≈ the observed ~94% hurst. Fix = per-directional bypass of the composition (uniform coin on the pinned pair) — the D119 precedent (experimental draws must not be yield-weighted). Trend-wide learning elsewhere untouched.
5. **v37 item 3 (ours): the Q50 durable fix** — conftest autouse universe pin (D274 shape) + one final golden re-baseline, after the July export broke 9 goldens mid-deploy (D282 addendum). Q50 closes when v37 ships.
6. **§5 (folded):** the ve-floor decision point re-anchored to **`funnel --compare v32 v35 --hypothesis vol_event`** (~1 day) — the v33 stamp lived only ~5.3h before v34/v35 superseded it, so the agreed v32-vs-v33 read can never mature. Early directional signal: component conversion 7.6% → 11.1%. Floor stands until the read. Memory updated.

**Outbound (held for carry):** `PROMPT_CRUCIBLE_V36_DEPLOYED.md` (deploy + funnel ask + the universe-boundary confound flag) and `PROMPT_CRUCIBLE_COHORT_FOLLOWUPS_RESPONSE.md` (the §4 answer + staging receipts). **v37 build awaits operator go** (`docs/proposals/v37-cohort-followups.md`). Related: [[D282]], [[D278]], [[D276]], [[D270]], [[D119]], Q50.

## D284 — 2026-07-16 — Shadow-eval comparator fix: `hygiene_score` column records the model-free §6.2 composite — the gate-tail flip had silently turned the eval clocks' "incumbent" into the lane's own score

**Finding (max-effort audit of the F3 margin slide, +0.35→+0.06 over 07-09→07-16):**
`rank_batch` stores the ORDERING score in `RankedCandidate.composite_score`
(`queue.py`: `composite = prior if gate_tail_ordering else ranker.score(...)`), and
`run_shadow_scoring` records that as `shadow_scores.composite_score`. Since the gate-tail
flip (2026-07-06T20:26:50Z, D252) every shadow row's "composite" is therefore the
GATE-TAIL value, not the §6.2 composite — and every eval that reads `composite_score` as
"the incumbent" became self-referential. Verified in data: spearman(stored composite,
tail_score) jumped ~0 → +0.6–0.9 on post-flip ranked rows; the §8.6 streak's
`incumbent_top_k_mean` equals the rewire streak's `gate_top_k_mean` exactly, every day.

**Decomposition of the F3 slide (none of it is model decay):** (1) incumbent identity
change — the gate-tail score is a stronger baseline vs component labels (AUC 0.52–0.65
vs the old composite's 0.43–0.57); onset lagged the flip to ~07-12 because the streak
buckets by DECISION time (verdict latency). (2) P-range restriction — the hard P≥0.02
gate truncates the ranked cohort (median P 0.036 vs holdout 0.0007); pooled post-flip
model AUC: ranked 0.737 vs **holdout 0.801** (n=5,812, 13 pos) ≈ pre-flip 0.828 —
unconditional skill intact. (3) Stream concentration + mix — newer grammar cohorts read
lower AUC (v24–v27 0.75–0.78 → v35/v36 0.62–0.64) with P-score IQR halved (0.052→0.024)
and MR share 11%→42% (F3 reads MR 0.625 vs trend 0.739) while positive rates HOLD ~5%:
a deliberately narrower, better stream is intrinsically harder to separate within.
Expect the legacy F3 margin to keep compressing toward the 0.05 bar — an artifact, not
a revert signal.

**Fix (this increment, TDD):** `shadow_scores.hygiene_score` (idempotent ALTER) records
the model-free §6.2 hygiene composite — `ranker.score(report, 0.0)`, prior slot zeroed —
per submitted row (`run_shadow_scoring(hygiene_scorer=...)`, wired in `main.py` at the
existing telemetry call site; ranking/submission byte-identical, invariants green).
`evaluate_shadow(incumbent="hygiene")` judges model-vs-hygiene on paired (non-NULL)
rows; `ranker-model eval` prints the hygiene block; the daily F3 streak judges on the
hygiene incumbent as soon as its fresh window qualifies (≥150), recording
`margin_source` + both margins (`ranking_auc_margin`, `hygiene_auc_margin`) for
continuity. Until the next operator-gated restart the column stays NULL and the streak
falls back to `margin_source="ranking"` (verified against a live snapshot).

**Interim guidance:** judge F3 skill on holdout-only pooled AUC, not the streak margin.
Related: [[D252]], [[D193]], [[D132]]; the §8.6 clock retirement is D285.

## D285 — 2026-07-16 — §8.6 wf_p25 tail clock RETIRED (streak + SPRT + adoption arm + drift arm): self-referential since the gate-tail flip; the re-wire clock is the lane's monitor

**Why:** per the D284 finding, every §8.6 comparison read `shadow_scores.composite_score`
as "the incumbent" — which post-flip IS the gate-tail lane's own score, ≈ the tail
ordering (P-floor keep-rate 0.97–0.99). The paired delta pinned to ≈0 BY CONSTRUCTION
the moment post-flip verdicts dominated (07-09: incumbent_sp jumped 0.10–0.29 → 0.49–0.54
= tail_sp, after 6 consecutive PASSes at +0.14…+0.38 vs the true composite through
07-07), its SPRT froze at logLR +2.66 (≈0-mean increments — could never resolve), and
`forge status` "adoption guard wf_p25=BLOCK" + healthcheck "wf_p25 drift" WARN read the
same broken series. The question the clock existed to answer ("should the tail wire
in?") was answered by the flip itself; the LIVE lane's monitor is the re-wire clock
(gate-tail vs P-alone: +0.44…+0.68, 16/3 PASS, SPRT promote +22.4). **The tail model is
NOT retired** — it is the live lane's ordering engine, and stays trained/published daily.

**Changes (TDD):** `daily_ranker_eval.sh` drops the §8.6 streak block (history JSONL
stays on disk; `eval-robustness` stays as the observational per-model tail readout —
NOTE its printed spearman_delta pairs against the recorded ranking score, so read its
ABSOLUTE spearman, not the delta, until hygiene rows accrue). `forge status` drops the
clock line + the `§8.6 tail flip gate` SPRT line (`tail_flip_gate` removed), prints a
tombstone, and the adoption guard's second arm re-points to the re-wire clock's latest
Δ (`gate-tail-lane=`). `forge healthcheck` re-points "wf_p25 drift" → "gate-tail drift"
(rewire `delta` series, same thresholds) — this also clears the standing near-WARN the
broken series caused (verified live: gate-tail drift OK +0.596, OVERALL=OK 14/14).
MANPAGE updated in all four places. Effective at the next 05:00 timer fire (editable
install; no service restart needed for script/CLI). Related: [[D284]], [[D252]],
[[D229]], [[D147]].

## D286 — 2026-07-16 — v37: cohort-read follow-ups BUILT+DEPLOYED — SOXX/LLY/GS/MSTR out of single-name sampling; resid gate draw un-starved (uniform coin, D119 precedent); Q50 durable test-side universe pin. Deploy also ACTIVATES the D284 hygiene-score recording

**Operator go:** "deploy v37 so the hygiene column starts populating" (the staged D283
items + the D284 activation ride one restart). Scope per
`docs/proposals/v37-cohort-followups.md`; emission-side only, `rules:` untouched
(classification #2, enumeration-policy bump). All three items TDD'd.

1. **Exclusions (sampler):** `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` += SOXX/LLY/GS/MSTR
   (Crucible row-45 trailing-window guard: 96.1–99.8% WF-zero on ~1,000-run samples
   each; their queue-time guard already eats them, so our draws were ~4.4k wasted
   draws/wk). Same v34/D278 terms: frozen list, re-admission on their relay, retires
   whole when their liquidity preflight ships. Emission proof: 0 draws for all six
   excluded names over a 3,000-config cold mix; 114 distinct names drawn (118-pool − 4;
   BKNG/BRK.B already left the July universe).
2. **Resid 50/50 (sampler):** the learned regime-gate posteriors (minted when hurst
   carried the cpcv config) composed onto the D276-pinned two-member pool and starved
   vix_term_slope to ~94% hurst — on an EXPERIMENTAL two-arm sweep whose spec wants both
   arms fed (vix is the WF-conversion carrier). Fix: skip the learned-slice for
   `residual_momentum` at the `_pick_regime` call site → the uniform coin on the pinned
   pair (the D119 relative_value precedent). Test reproduces the starvation adversarially
   (4/518 vix pre-fix → ~50/50 post-fix); learned weighting for every other directional
   untouched.
3. **Q50 durable fix (test-only):** conftest autouse `_pinned_universe` binds
   `sampler._load_underlyings` to `tests/fixtures/universe_snapshot.py` (the 07-16 July
   export, 118 names, fingerprint 260321aaaad60241) — the exact D274 earnings-pin shape,
   incl. the import-time `_UNIVERSE_EXPORT_DIR` gotcha; `real_universe_loader` re-binds
   the real cached loader for the 13 loader/fingerprint tests. Live tier exports can no
   longer move test draws (the class that broke 9 goldens at position 0 in BOTH the v34
   and v36 deploys). Daemon's live read untouched.

**Golden re-pin (licensed, environment-matched):** all 7 cold-start goldens re-pinned
via the v36 harness method — OLD code under the pinned environment reproduced every
constant EXACTLY (environment clean), then NEW code's first divergence per golden was
verified to be a scoped draw (a single-name underlying; position 0's BMY maps
identically by index — pool 118→114 shifts index→ticker mapping only from the first
removed name). The d105/d106 byte-identity baselines now compare against the
post-exclusion pool (the fallback list carries GS/MSTR — pre-D286 the pools coincided
by luck). Relational splits re-asserted green.

**Ritual:** v36→v37 bump + archive + integration test pin in the down-window; deploy
evidence + first-batch audit in STATUS. The restart ALSO activates D284's
`hygiene_score` recording (first non-NULL rows expected in the first post-restart
batch) — the F3 streak's hygiene incumbent starts accruing from decided verdicts on
those rows (~1–2 days). Related: [[D283]], [[D278]], [[D276]], [[D119]], [[D274]],
[[D284]], Q50 (CLOSES at this deploy).

## D287 — 2026-07-16 — Experiment-cell selection floor: the hard P-gate starved the resid x vix arm AT SELECTION after D286 fixed its draw — pinned (directional, regime) cells now get reserved batch slots (the D119/D136 principle at the ranking layer)

**Finding (first two v37 batches):** ranked-lane resid submissions ran 14 hurst / 0 vix
(p≈0.006% under the now-uniform generation coin) while batch 2's single vix-resid config
arrived via the exploration HOLDOUT — generation fixed, selection still starving the arm.
Offline diagnosis (enumerate 6k + live P/tail models): generation balanced (31/32), but
only **16% of vix-resid clear the P≥0.02 hard gate vs 87% of hurst-resid** (median P
0.011 vs 0.033) — the F3 model, trained on history where hurst carried every resid
config, gates the experimental arm out at eligibility; below-floor priors pin to 0.0 and
are unreachable for the greedy fill. Tail ordering adds only mild secondary skew. The
D136 arm floor cannot help: its key is (role, indicator) — `("regime_filter",
"vix_term_slope")` matured within days of v27, and even young it wouldn't scope to the
resid pair.

**Change (operator "lets do 2"; TDD):** `forge/ranking/experiment_cells.py` —
`EXPERIMENT_CELLS = {("residual_momentum", "vix_term_slope")}` +
`EXPERIMENT_CELL_SLOTS = 4` (~2% of a batch; same order as hurst's organic ~7) +
`config_cell()`. Diversifier gains reservation phase 0b (`_reserve_experiment_cells`,
sorted/deterministic, same §6.3 greedy `_take`, members-already-selected counted, empty
pool reserves nothing so generation-side starvation stays visible); threaded through
`rank_batch`/`rank_batch_with_holdout`; production wired in `main.py` `_rank_kwargs` +
a per-batch journal audit line `experiment_cell_floor: {...}`. `None` default keeps
every legacy path byte-identical (asserted). The `_select_top_n_floored` phases 0/0b
extracted to helpers (PLR limits). VERSIONLESS ranking change (no grammar edit — the
D193/D252 precedent), deploy ritual still applies.

**Terms:** hand-pinned, retires on Crucible's relay when the two-arm read concludes —
never from learned feedback. If more experiment cells appear later, add to the constant.
Related: [[D286]], [[D276]], [[D136]], [[D119]], [[D103]].

## D288 — 2026-07-16 — v38: trend swing_long exit-CLASS mix shift — the time_stop optional draw drops 0.5 → 0.15 in that cell only (Crucible census: exit class orders the conversion surface; timers convert at 0.43x chandelier-only)

**Relay:** `FORGE_trend_swinglong_exit_mix_2026-07-16.md` — companion to the v36
duration prior (COMPOSES: mix share vs duration-given-carried). Their weekly-census
read (n=45,850 decided trend/swing_long/xsect, 07-02→07-16): chandelier-only 39.1%
component rate > other-discretionary 30.7% > timer-carrying 16.9%, monotone,
replicating in the confluence stratum and at swing_mid; 46% of the cell carried a
timer. **Verified on OUR verdicts before building** (all strata, same window,
n=50,906): 46.4% / 21.6% / 32.0% shares and 15.1% / 35.5% / 27.5% component rates —
the mechanism is exactly our S5 draw (time_stop = the lone trend optional at p=0.5;
chandelier = half the required_from_set pick → predicted 50%/25%).

**Change (TDD, operator "deploy when complete"):** `_optional_exit_pick_p()` — the S5
optional-additions Bernoulli, 0.5 everywhere except (trend_continuation, swing_long,
time_stop) → **0.15** (`_TREND_SWING_LONG_TIME_STOP_PICK_P`). One knob:
chandelier-only rises mechanically (0.5 × 0.85 ≈ 42%; emission proof 46.9% at n=96)
and trailing_atr (D236: not refuted) keeps its required-pick share. NOT 0: their
census window mostly predates the v36 U[8,10] prior, so the surviving ~15% keeps
feeding the funnel's read of it (their §2 explicitly keeps the prior for remaining
draws — verified: all surviving carriers emit n_bars ∈ [8,10]). rng consumption
identical on every path (one random() per optional) — unscoped cells byte-identical
(hard rule #6); MR's timer is a required_from_set pick, structurally untouched
(tested). "Do not touch other buckets": swing_mid verified unchanged (48.0% timer).

**Goldens:** 6 of 7 re-pinned via the environment-matched harness (OLD code reproduced
every constant exactly; first divergences verified as trend swing_long exit draws —
PRE@2, V27@11); the cohort golden (seed 4242) hosts no scoped flip and is untouched.
v37→v38 bump + archive + test pin in the deploy down-window. Related: [[D282]],
[[D286]], [[D236]], [[D169]].

## D289 — 2026-07-19 — ve program relay TRIAGED: their §3 bug CONFIRMED in our emission (fallback-mode event_passed, required in every ve config; the v22/D169 ladder put 60% of ve batches in the cratered region); §5.1 + §5.4 ANSWERED with data; v39 staged (operator-gated). Docs-only

**Relay:** `FORGE_ve_program_relay_2026-07-19.md` (their 3-day ve program close-out:
23/25 stored-cpcv ve components were GHOSTS — a data-provenance bug on
put_wall/gex/vex/cex staleness scanning, fixed their-side v3→v4 c86bfcc).

1. **§3 CONFIRMED:** ve `required_always = (iv_crush_exit, event_passed_exit)`;
   `_exit_params` emits NO `event_indicator` → every ve config ever submitted ran
   their FALLBACK mode (hard cut at entry+n_bars). D169 (v22, 2026-06-15) began
   sampling the ladder {3,5,8,13,21} — built in good faith off the D168 "loosen early
   time-cuts" fair-test, but under fallback semantics it widened a truncation, not a
   hold, and put 60% of every ve batch at n_bars ∈ {8,13,21} = their sweep's cratered
   region (time_stop 13/16/21 → cpcv 0.81/0.42/0.29).
2. **§5.1 ANSWERED (archive + DB):** v22's ve-cell delta was EXACTLY the D169 ladder
   (v21↔v22 archive diff; D167 is MR-only). Our funnel: ve conversion v21 5.9% →
   v22 0.7% → 0.0–0.4% v24+; the ep≥8 share goes 0% → 60% at the same boundary and
   never moves again. Levels ghost-caveated both sides; the cliff timing is the
   evidence.
3. **§5.4 ANSWERED (DB + code):** AMD ve-supply peaked 39% at v20 (ghost-yield era,
   v19–v21 ~20–39%), ~2% since v22; current v33+ ve supply near-uniform (top name
   3%). `factor_cell_discounts` is DORMANT — the sampler accepts it, production never
   passes it.
4. **§6 ANSWERED (code):** Forge persists no put_wall/gex/vex/cex — the feature cache
   is a live client to their writer socket, rebuilt per iteration; their re-key
   reaches us automatically. The REAL Forge-side exposure is training labels:
   **34,273 ve verdicts / 657 "components" decided in [2026-06-10, 2026-07-18) ≈ 10%
   of all positive labels** feeding F3/tail/yield-map/name-weight/trade-rate
   trainers. Fix staged as the ve ghost-label cut (v39 item 4).
5. **Staged (`docs/proposals/v39-ve-program.md`, operator-gated):** ve exit-schema
   fix (event_passed OUT of the ve set — an S5 set edit, D236/D257 precedent, flagged;
   time_stop required with U[4,7]), ref_trailing_return veto SAMPLING (registry-live,
   macro family, no contracts gap; params sampled never pinned per their honesty
   block), iv_term_slope ×1.3 loosening, the ghost-label cut. NOT built: genome
   ports, stabilization filters, veto pins (their honesty block); the ve floor holds
   (their #5).

**Memory corrected:** the ve orthogonality pillar — mixed-book PBO 0.178 was a
ghost-era measure; clean-cache re-validation = **0.40, real but marginal, no solo
promotion case** (sleeve route reopens only with diverse honest supply). Outbound
held for carry: `PROMPT_CRUCIBLE_VE_PROGRAM_RESPONSE.md`. Related: [[D169]],
[[D168]], [[D257]], [[D236]], [[D128]], [[D287]].

## D290 — 2026-07-19 — v39 BUILT+DEPLOYED: ve exit-schema repair (event_passed OUT, time_stop U[4,7] required), ref_trailing_return veto SAMPLING, iv_term_slope x1.3 loosening + the ve ghost-label training cut (operator "approved, build v39 and deploy when complete")

Implements `docs/proposals/v39-ve-program.md` (the D289 triage's staging; Crucible
`FORGE_ve_program_relay_2026-07-19.md` asks #2/#3 + §1/§6 actioning). All TDD.

1. **ve exit schema (S5 set edit, the D236/D257 precedent — operator-approved
   explicitly):** ve `required_always` = (iv_crush_exit, time_stop);
   event_passed_exit REMOVED and FORBIDDEN (it always ran their fallback mode — we
   never emitted `event_indicator` — a hard cut at entry+n_bars; with a timer present
   true-event mode fires 0/68). `_time_stop_nbars_range` gains (volatility_event, *)
   → U[4,7] (their sweep: ~5 sweet spot; 13/16/21 crater 0.81/0.42/0.29). The
   D169 `_EVENT_PASSED_NBARS_LADDER` + its `_exit_params` branch RETIRED (tombstone).
2. **ref_trailing_return ve veto (SAMPLED, never pinned):**
   `_VE_REGIME_VETO_INDICATORS` + the "volatility_event" pool in search_space
   (registry-gated dormancy, D258 convention; live registry serves it — macro,
   market-wide); threshold table entry regime_range=(-0.03, -0.02) op ">";
   `_sample_veto_params` merges reference ∈ {SPY, QQQ} + window ∈ [3,10] on this
   id's path only. Rides the generic ~0.5 veto-share draw with the per-id C1 macro
   guard. signal_horizon entry added (gate-only, the market_realized_vol precedent).
   NB `check-activations` cannot probe a regime-role id ([UNCHK] expected); liveness
   evidence = Crucible's own certified probe runs (the honest recipe's veto, 96317de).
3. **iv_term_slope directional floor 0.01 → 0.0077** (x1.3 loosening; +0.21 cpcv on
   their honest chassis; ceiling 0.04 kept; sampled never pinned).
4. **ve ghost-label cut (versionless companion):** `VE_GHOST_LABEL_CUT = 2026-07-18`
   + `is_ve_ghost_label()` in rejection_weights; enforced at every trainer choke
   point — `_iter_hypothesis_outcomes` (hypothesis weights), `_component_rate_sums`
   (all D105/D106 weighters), trade_rate_priors, `build_dataset` (F3 + tail
   training), `compute_mature_arms` (arm maturity). 34,273 ghost ve verdicts / 657
   fictional components (~10% of positive labels) stop feeding the learners.

**Emission proof (live registry, 4k configs):** ve 784: event_passed 0, time_stop
784/784 with n_bars uniform {4:189, 5:191, 6:182, 7:222}; veto share 48%
(SPY 192 / QQQ 188); iv_term_slope min 0.0080 (loosened floor reached), max 0.0393;
all hypotheses reachable. **NOT built (their honesty block):** genome ports,
stabilization filters, veto pins; the ve floor + D287 protections untouched.

**Goldens:** all 7 re-pinned environment-matched (OLD code reproduced every constant
exactly; every first divergence = a ve config carrying the new exit stack; two
cross-golden prefix asserts tightened to the new mutual split at position 1 — the
position-0 ve config's rng shifted). Full suite 1999 green. Related: [[D289]],
[[D169]], [[D168]], [[D257]], [[D236]], [[D128]], [[D287]].

## D291 — 2026-07-20 — v40: MR timer cell goes first-class — required pick weighted to time_stop 0.65 + n_bars U[8,12] bucket-wide (Crucible combined relay: the timer-MR family CONVERTED; operator "let's fix this")

Implements §1 of Crucible `FORGE_combined_relay_2026-07-20.md`. Their evidence:
the timer-MR cell produced 1,087 components in 5 days (68 at cpcv>=1.0, 20 at
>=1.2), genome-diverse across n_bars 8-12; head 65316ca4 (11-bar hold) lifts the
2-leg book to cpcv_p25 1.7236 / WF 2.3407 raw, honest decorrelation 0.347,
selection PBO 0.156, DSR 0.9993 @ N=85 — duration is the measured decorrelation
axis. **Their "15% timer-share" premise is a mis-attribution** (v38's 0.15 is
trend/swing_long's OPTIONAL draw; MR's timer is a required_from_set pick at
uniform ~50%) — corrected in our response relay; the intent ships.

**Reproduced on OUR verdicts before building** (decided >= 07-14, MR excl.
capitulation): timer 10.7% vs target_exit 9.9% component rate overall; within
timers, n_bars 8-12 converts **15.0%** vs 13-15 at 11.9% vs param-less default-5
at **5.3%** (the worst MR exit cell, n~5,000). Both knobs are evidence-backed on
both sides of the pipe.

Two changes, BOTH scoped to mean_reversion EXCLUDING the capitulation
directional (its v35 bare-drop pane stays veto-frozen mid-trial, D282):

1. **Weighted required pick** (`_pick_required_exit`): time_stop at p=0.65
   (was uniform 0.5 via `rng.choice`); share moves AWAY from target_exit — the
   direction D257 established as safe (share moving TO target_exit "breaks the
   book"). A membership guard (`set == {time_stop, target_exit}`) deactivates
   the bias back to uniform if the MR required set ever changes shape.
2. **n_bars ~ U[8,12] at ALL MR buckets** (`_MR_TIME_STOP_NBARS_RANGE`):
   v36's swing_mid U[8,15] narrows to the measured family box and the
   param-less default-5 emission is retired for MR (supersedes D282's
   swing_mid-only scoping on the new evidence). Capitulation keeps D270's
   U[5,15] at both buckets (resolution order unchanged).

**Goldens:** all 7 re-pinned environment-matched (OLD code reproduced every
constant exactly; every sequence's first divergence = its first mean_reversion
config — positions 4/4/5/5/6/5/5; non-MR configs at unchanged stream positions
are byte-identical). The stream re-pin moved two cross-golden landmarks: the
first ivol-veto carrier to position 16 (d263 scan widened 15 -> 25) and the
first capitulation genome to position 30 (d270's v29-vs-v31 divergence now
asserted on a live 40-window pair; the 15-length goldens coincide). Two v36-era
assertions superseded in place (swing_mid [8,15] -> [8,12]; swing_short bare
timer -> family box). GRAMMAR.md S5 table also repaired for the MISSED v39 ve
row (event_passed forbidden / time_stop required — doc drift from D290).

NOT done: §3's tier unpin (the universe read is structurally tier-2-only:
their tier_1 export = the 4 broad ETFs we exclude by T1.4 design; tier_3 is
absent from the contracted export shape entirely; `tier=2` hardcoded at config
construction). That needs a contracts gap fill first — proposed in the response
relay (tier_3 key in universe_tickers.json + a contracts reader, or blessing
the new PIT `all_eligible_tickers.parquet` as a contracted surface), with the
D245 both-side restart sequencing flagged. §2 needed no build: the
ref_trailing_return starvation self-heal VERIFIED in our stream (veto carriers
0/0/0 -> 3-11/batch from f49c554c 07-19T22:51Z; ~40% of submitted ve).
Related: [[D290]], [[D288]], [[D282]], [[D270]], [[D257]], [[D245]], [[D254]].

## D292 — 2026-07-20 — Tier-unpin reply TRIAGED (docs-only): the 2-leg PROMOTED (2nd portfolio ever, 1st via auto-campaign); our "tier-3 never reaches the pool" claim CORRECTED (folded tier_2 key — we draw all 94; the pin is the STAMP and its cost is cross-sectional); contracts 1.32.0 verified; v41 staged operator-gated

Crucible `FORGE_tier_unpin_and_promote_2026-07-20.md` (their D291 reply). All
claims verified on our side before recording:

1. **PROMOTION (their §0):** the frozen 2-leg (trend 6bec53b4 + timer-MR
   65316ca4, spec b36f49a4fe230f96) passed ALL 13 §8.7 gates (run de00e099:
   cpcv_p25 1.7236 / WF median 2.3063 / DSR 0.9991 @ charged n=99 / PBO 0.156 /
   min_oos 840 / leg corr 0.065). Second promoted portfolio ever; first through
   the portfolio auto-campaign lane; live sizing deflated ~1.3-1.45. The
   timer-MR leg is the exact cell v40 now farms.
2. **Record correction (their §3, VERIFIED):** our D291/relay claim "94 July
   tier-3 names never reach our pool" was WRONG. Since their ca51d35 publisher,
   tier-3 is FOLDED into the export's `tier_2` key — export tier_2 n=114 = 20
   curated + 94 tier-3 (verified: tier_3 ⊂ tier_2, subtraction = 20). We have
   been drawing all of them; our own funnel shows the cited names heavily drawn
   and structurally DEAD single-name: ASML 641 decided/0 comp, BKNG 1,254/0,
   COST 1,544/1, LLY 1,372/0, SOXX 1,367/0 (BKNG/SOXX/LLY already v37-excluded;
   **ASML/COST are candidate additions** — staged in v41, flagged for their
   row-45 cross-check). What IS pinned: the literal `tier=2` stamp. Its real
   cost is CROSS-SECTIONAL: their engine resolves xsect ranking pools from the
   STAMP against PIT membership — every xsect config we ever emitted ranks the
   TRUE 20-name curated tier-2 pool, so rank_k=20 cells rank-then-take the
   whole pool (no selectivity), and the 94-name tier-3 xsect pool has literally
   never been sampled. That axis, not single-name breadth, is the unpin payoff.
3. **Contracts 1.32.0 VERIFIED** (their commit 0bc45a8, live at
   ../crucible_contracts): `load_universe_tiers_from_export` -> UniverseTiers
   (4/20/94 on the live export `universe_tickers_2026-07-20T160525Z.json`);
   old reader returns the identical 118-name union (checked both) — so the NEW
   export changes nothing at our next restart, and the minor pin gap
   (1.31.0 pinned vs 1.32.0 installed) does not hard-fail
   (`validate_schema_version` raises on MAJOR only). The fold stays until we
   confirm adoption — no time bomb, but adoption must precede their fold
   retirement (the old reader would shrink the pool 118 -> 24).
4. **v39 -> v40 attribution hygiene (their §1):** premise correction accepted
   on their side; null-control run — v38 vs v39 MR component rate 14.4% ->
   15.0% (flat) — any MR movement in the v40 read attributes to D291. Their
   census independently confirms the v40 scoping boundary (timer WORST in
   trend/swing_long at 16.8% vs chandelier 38.5%; the timer is an MR-only
   edge). §2: their writer restart was ONE event at 22:27:21Z (their ~23:30Z
   was a logging error); our 22:51Z first-carriage observation consistent.
5. **v41 STAGED (operator-gated; `docs/proposals/v41-tier3-xsect.md`):**
   contracts pin 1.31.0 -> 1.32.0 + reader switch (pool unchanged) + true-tier
   stamping + a 15% xsect tier=3 exploration share (their xsect-first
   suggestion adopted — single-name tier-3 coverage already exists and is
   mostly dead) + the ASML/COST exclusion rider. One deploy window covers pin
   adopt + v41; on verify we confirm adoption so they retire the fold.

Related: [[D291]], [[D290]], [[D286]], [[D267]], [[D245]], [[D078]].

## D293 — 2026-07-20 — v41 BUILT+DEPLOYED: tier unpin — contracts 1.32.0 adopted with wiring (tiered reader + true-tier stamping + 15% xsect tier-3 exploration share) + the ASML/COST dead-name rider (operator "go on building and deploying v41")

Implements `docs/proposals/v41-tier3-xsect.md` (the D292 triage's staging). All TDD.

1. **Reader switch:** `_load_underlyings` moves to `load_universe_tiers_from_export`
   via a single shared cache (`_load_universe_tiers_cached`); union identical by
   contract (verified both readers on the live export). `_tier3_symbols` exposes
   TRUE tier-3. The pre-v41 `cache_clear` contract survives via an alias onto the
   one true cache (a dozen test call sites; no stale-split hazard — the dual-cache
   version poisoned cross-test state and was rejected). `StaleExportError`
   subclasses `QueryError`, so the fallback catch is unchanged.
2. **True-tier stamping:** `_stamp_tier(underlying, combiner, rng)` at config
   construction, drawn LAST — single-name = pure lookup (3 for tier-3 members,
   2 otherwise); xsect = tier=3 at `_XSECT_TIER3_SHARE=0.15` with the empty-set
   short-circuit BEFORE rng (export-gated dormancy, D258 convention);
   relative_value keeps the literal 2 (stamp inert on pairs).
3. **`universe_fingerprint` folds the tier split** (H-3: emission now depends on
   membership; empty-tier-3 payload byte-identical to pre-v41 for continuity).
4. **Exclusion rider:** ASML/COST join `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS`
   (our funnel: 641 decided/0 comp, 1,544/1; same terms as v37 — re-admission on
   their relay, row-45 cross-check requested).
5. **Contracts pin 1.31.0 → 1.32.0** — adopted WITH wiring (unlike the D267/D271
   pin-only precedents); required before Crucible retires the transition fold.

**Test surface:** `UNIVERSE_TIER3_SNAPSHOT_2026_07_20` (94 names, all inside the
07-16 union snapshot) + the conftest tier pin (the D274-pattern third leg);
5 new tests (true-tier stamp, xsect share, dormancy, exclusion, fingerprint
split). **Goldens:** 7/7 re-pinned environment-matched (OLD code reproduced every
constant; onset = the first POOL-TAPPING config — cohort positions 0-1 are
relative_value and survive untouched, everything else moves at 0 via the
118→116 pool shift, the v37 signature). Full suite 2008 green.

Deploy + first-batch audit in STATUS. The deploy relay addendum carries the
ADOPTION CONFIRMATION that licenses their fold retirement.
Related: [[D292]], [[D291]], [[D286]], [[D278]], [[D267]], [[D262]], [[D078]].

## D294 — 2026-07-20 — v42 BUILT+DEPLOYED: xsect-union correction — the v41 tier=3 xsect share DROPPED (their same-day ledger retraction: xsect always ranked the all-tier union; the stamp is a SPREAD-COST class), single-name true-tier + ASML/COST STAND, contracts pin 1.33.0

Crucible `FORGE_xsect_union_correction_2026-07-20.md` — a ledger-verified
retraction of their own tier-unpin relay's §3 framing, which D292/D293 adopted.
Corrected truth: the composable xsect template ranks the ALL-TIER union by
construction (`_ALL_TIERS = (1,2,3)` + bulk superset; the promoted trend leg
trades 89 underlyings incl. tier-1 and 66 outside curated 1+2; QuantIQ's D417
"ranks 48 names" smoke was the missed tell). The tier stamp's ONLY engine
effect on an xsect config is the FillModel spread-table class (tier=3 charges
tier_3_base x 1.5). Therefore:

1. **v41's 15% xsect tier=3 share DROPPED** (`_stamp_tier` xsect branch =
   constant 2, no rng; `_XSECT_TIER3_SHARE` tombstoned). It bought duplicate
   books at strictly worse charged costs — 58 such configs emitted in the ~5h
   v41 window (b9e00eff 28, 9d8d642e 30); grammar_version splits them.
2. **Single-name TRUE-tier stamp STANDS** (their words: a tier-3 single-name
   charged tier-2 spreads was mispriced-cheap — v41 fixed a real cost bug).
3. **ASML/COST rider STANDS** — their row-45/census read confirms (ASML n=375
   100% wf-zero; COST n=1,166 91% wf-zero, med OOS 5).
4. **Contracts pin 1.32.0 -> 1.33.0** (their 150e368: StrategyConfig.tier
   ge=0 — tier=0 = explicit union scope, their §20 fix for the emergent-pool
   defect the correction disclosed). Purely permissive; Forge never emits 0.
   The exact-match pin test was RED at triage (installed 1.33.0) — the D267
   forcing function working; adopted riding this bump. An xsect tier=0 stamp
   is a QUESTION in the relay (waits on their §20 engine pin + an explicit
   ask), never guessed at.
5. **Their relabeled ablation recorded:** the deltas measure COST sensitivity
   — trend 6bec53b4 is spread-cost SENSITIVE (dWF -0.206 at 1.5x), timer-MR
   65316ca4 is FLAT (11-bar holds amortize entry costs — a gate-relevant
   robustness datum for the promoted book).
6. **QuantIQ D418 rider ask logged (Q51, LOW):** a generation-time
   expected_trades-under-integer-floor check at a declared reference NAV
   (the trend leg's 0.0075 fixed_risk = $187.50/trade at $25K NAV vs
   $530-6,000/contract). Needs a per-contract premium estimate at emission —
   a data-source question relayed back before any build.

**Goldens:** verify clean under v41 code; under v42 the six regime goldens are
BYTE-IDENTICAL (their sequences host no xsect draws — the removed Bernoulli
touches nothing) and only the cohort golden re-pins (first divergence = its
first rank-combiner config, position 12). The xsect share test superseded in
place (`test_xsect_stamps_tier2_since_v42`). Full suite 2008 green twice.
Related: [[D293]], [[D292]], [[D291]], [[D267]], [[D169]].

## D295 — 2026-07-20 — Post-promotion cleanup sweep #3 (docs/ops only, zero code-behavior change): 33 answered root relays archived, 4 completed one-off scripts retired, STATUS.md rotated (May–June blocks → `_archive/`), 7 stale May Q-headers bannered, forge_data leftovers cleared

Operator-directed ("lets do A") after a four-survey cleanup review of the whole
repo (root files, src dead code, scripts/ops, docs/tests) run post-first-auto-
campaign-promotion. Everything here is the review's zero-risk bucket; code
retirements (the orphaned capitulation rv_rank branch, the D287 cell-pin
retire-on-relay, the auto_tune re-arm-or-delete decision) were deliberately NOT
executed and remain staged for separate decisions.

1. **Root relay sweep #3 (the D202 pattern; root PROMPT count 44 → 10 + 1
   research note):** 33 answered/superseded relays moved to `_archive/` — all
   deploy/funnel relays ≤ v38, the answered response/receipt/ack/bug set
   (capitulation, census, cohort-followups, exit-duration, dsj, ivol thread,
   earnings-manifest pair, generation-discipline thread, cache-poisoning
   report, winning-burst FYI, market-rv ask), the v22-era
   `PROMPT_PROMOTION_STRATEGY_HANDOFF.md` ("Promotions to date: ZERO"), and two
   stale never-sent drafts whose premises are dead: `GEN_LEVERS_VALIDATION`
   (argues from pre-first-promotion) and `VOLEVENT_GATE_CLASS_EVIDENCE`
   (premise = ghost-era ve PBO 0.107, re-litigated by their 07-19 close-out).
   KEPT in root (live/held): TIER_UNPIN + XSECT_CORRECTION (current cycle),
   VE_PROGRAM + COMBINED_RELAY (one more cycle — v39/v40 funnel reads pending),
   ALPHA_BUDGET_DSR + STALE_VOLUME (prereg `098ea730` resolves ≤07-21),
   SMA_SLOPE (Crucible-side fix unverified), FUNDAMENTAL_VALUE_PRECHECK (held
   live), PATHC_DEBIT_VERTICAL_SIZING (parked with Path C),
   SECTOR_ETF_XSECT_PRECHECK + `SECTOR_VOL_MECHANISM_RESEARCH.md` (operator
   call pending — companion research was a D269 DON'T-BUILD).
2. **Scripts retired (the D241 pattern — deleted, recoverable from git
   history, MANPAGE note updated):** `backfill_verdicts.py` (D111 completed),
   `migrate_verdicts_decided_at.py` (D117 completed),
   `requeue_high_value_configs.py` (one-off recovery, completed),
   `probe_option_momentum_min_months.py` + `probe_results/` (Q39 resolved at
   v19/D138). Their three dedicated integration tests removed with them
   (`test_backfill_verdicts.py`, `test_migrate_verdicts_decided_at.py`,
   `test_requeue_high_value_configs.py` — they tested completed one-time
   migrations). `docs/tasks/investigate-live.md` pointer annotated.
3. **STATUS.md rotated (the D242 ledger pattern):** 2026-05-29 → 2026-06-29
   blocks (incl. the Phase-0 scaffolding/session log) moved verbatim to
   `_archive/STATUS_2026-05_2026-06.md`; live file 2,522 → 756 lines with a
   pointer at the bottom.
4. **OPEN_QUESTIONS hygiene:** Q7/Q8/Q11/Q12/Q15/Q16/Q17 carried closure text
   in their bodies since May–June but never got header banners — banners added
   (no content changed). The scary "BLOCKING PHASE 1/2" headers no longer read
   as open.
5. **forge_data leftovers:** top-level `king_submissions.db` deleted
   (byte-identical to `archive/king_retired_20260619/` copy, cmp-verified;
   `NEW_BOX_TRANSFER.md` already said don't carry it);
   `backfill_source_gated_runs_20260609.json` (46M, the completed D117
   migration's input) moved into `~/forge_data/archive/`.
6. **Committed alongside (not sweep content):** `fable-audit/reliability/`
   (untracked since 07-06 — OPEN P0/P1 findings REL-1..21, the opposite of
   cruft) + the README index row; the daemon's 07-18 OPEN_PROPOSALS append
   (two PENDING gate-failure-concentration tighten proposals — the proposer
   woke post-promotion; operator review pending, NOT decided here).

**Daemon untouched** (nothing removed is imported by production code; no
restart). Suite impact: only the three retired-script tests leave the count.
Related: [[D202]], [[D241]], [[D242]], [[D294]].
