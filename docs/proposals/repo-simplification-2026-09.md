# Repo simplification 2026-09 — cleanup and simplification plan (post-freeze)

**Status:** PLAN ONLY. Nothing has been deleted, modified, restarted, or committed. This file is
untracked; commit or discard it. It supersedes `repo-simplification-2026-08.md` (Steps 0–C, E1–E3,
E6 landed; D, E5, E7, F and the §4 regrowth rules are carried forward below) and re-cuts
`fable-audit/code-complete-retirement/REPORT.md` (its trigger — a signed freeze — fired 2026-08-14,
D390; several of its rows are now wrong, see §7 item 2).
**Basis:** five-track read-only audit on 2026-09-13 at HEAD `db1172f` (source reachability +
symbol census over 629 defs; complexity; tests incl. one niced full-suite run; scripts/timers/config/
runtime data incl. journal reads; docs/records). Every claim carries a `file:line`, a command
result, or a journal fact. Suite at HEAD: **2,156 passed / 1 failed / 1 skipped in 232 s** — the
failure is the contracts-pin equality test (deliberate, see §0).
**Final state decided 2026-09-13 (operator): Route C, automated** — see §12. §12 supersedes
Batches 3–6 of §10; Batches 0–2 stand as written.
**Test for every item** (operator's): does it make the strategy more profitable, the system more
robust/reliable, or improvement faster? If not → remove or simplify. Uncertain → §8 (ambiguous).

---

## 0. Summary

1. **Forge has no equities strategy.** The only `equity` references are the §13.6 invariant that
   *forbids* it and two comments. The equities arm is QuantIQ's PTS paper runner (user crontab:
   `paper_runner_daily.py --options-mode off`, `equity_fill_diagnostic.sh`); removing it is a QuantIQ
   repo task, out of this repo's scope. §1 documents the (empty) inventory and the cross-repo pointers.
2. **The production core is small and healthy.** The weight is (a) experiment apparatus that outlived
   its decision — flip gates, A/B plumbing, freeze instruments; (b) telemetry nobody reads; (c) records
   and docs that regrew (no sweep in 38 days, ledger 472 KB, 40+ stale doc statements).
3. **The tree is un-deployable today**: pin `1.44.0` vs installed `1.47.0` → pin test RED, preflight
   NO-GO, healthcheck WARN for 11 days (264 of 354 runs). Batch 0 unblocks every later batch.
4. **Two record corrections**: D401's "F3 ran a 15-day-stale model" is false (models load per
   iteration — `main.py:1968/2377`; four model ids rolled today with zero restarts); the docs' "~10 test
   files monkeypatch main" is 24 (22 of them only import `app`).
5. **Impact if everything below lands** (§9): src 28.5k → ~22–24k LOC; tests 46.7k → ~37k; scripts
   18 → 11; CLI surface 32 → ~21 commands; healthcheck 17 → 11 checks; docs 7.4k → ~4.6k lines;
   session read-path 633 KB → ~280 KB; `_archive/` −1.2 MB; timers 4 → 4 (one slimmed, one
   memory-capped); dependencies dropped: 0.
6. **Final state (§12):** no daemon. One weekly, zero-input `forge campaign` run that reads the
   champion book and Crucible's verdict ledger, decides on its own whether anything is worth
   generating, and submits at most a few hundred challengers a week instead of ~80,000. Two
   timers, ~9 commands, ~17k LOC.

---

## 1. Equities removal inventory

| Layer | Finding | Evidence |
|---|---|---|
| Backend (strategy/signal/model code) | **None.** Options-only by design (§13.6, hard rule #7). | `grep -rIiE '\bequit(y|ies)\b' src` → 2 comment hits (`enumeration/underlying_class.py:37` "broad equity index"; `sampler.py:803` "2%-of-equity per-trade budget") |
| Data feeds / loaders | None. Inputs are Crucible's options registry, universe, gated/failed exports. | `docs/architecture.md` pipeline section; `persistence/registry_loader.py` |
| Execution / broker adapters / risk rules | None in Forge (Forge submits configs; QuantIQ executes). | no broker/IB/order code in `src/` |
| Configs / env vars / DB tables / API routes / UI | None. | `config/*.yaml`, `persistence/schemas.py` (8 tables, all options-pipeline) |
| Cron / scheduled | **0 Forge crontab entries.** The user crontab is QuantIQ's (30 jobs), incl. the equities paper runner and `equity_fill_diagnostic.sh` at 06:15. | `crontab -l` |
| Tests | `tests/invariants/test_phase1_invariants.py` (15 hits) **enforces** the equity ban — KEEP. | §13.6 |
| Docs | `DESIGN.md` (3), `CLAUDE.md` (1), `GRAMMAR.md` (1), `grammar.yaml` (1) all state the ban — KEEP. | grep |
| Shared code with QuantIQ that must not break | QuantIQ reads: `OPEN_PROPOSALS.md` (`contracts/forge_proposals_v1.py`, `list-proposals`), `~/forge_data/exports/forge_funnel.json`, `ranker_eval/streak.jsonl` + `rewire_streak_wfp25.jsonl` (`pipeline_queries.py:617-618`), `models/` series, `forge.db` `submissions` read-only (`forge_queries.py:100`). Nothing equities-specific. | read-only grep of `~/proj/QuantIQ` |

**Untangling proposal:** none needed here. If the equities removal in QuantIQ drops its Forge
readers (streak files, models series, OPEN_PROPOSALS parser), several "externally load-bearing"
KEEPs in §5 (the two streak clocks, the proposal file) become removable — re-check after that work.

---

## 2. Scheduled tasks and hooks

| Unit / hook | When | Does | Reads → writes | Last run / result | Serves the goal? | Verdict |
|---|---|---|---|---|---|---|
| `forge.service` | always | the loop | grammar, registry, exports → `forge.db`, Crucible inbox, `exports/forge_funnel.json` + `forge_submission_versions.json` (36 MB rewritten every iteration, `main.py:2708`) | up since 09-12 12:05 PDT (box reboot; 12 boots since 08-15), NRestarts=0 | yes | **KEEP** |
| `forge-healthcheck.timer` | hourly | 17 checks (`healthcheck_cmd.py:142-648, 859-1001`) | journal 48 h, `models/`, `backups/`, `exports/`, `inbox/errors`, 5 `ranker_eval/*.jsonl`, `/tmp` | 17:00 today → WARN (contracts pin only) | yes | **KEEP, SIMPLIFY** to 11 checks (§4 #5); `check_tmp_headroom` measures `/tmp` (`:396`) but snapshots moved to `~/forge_data/.snapshots` on 08-02 — mis-aimed |
| `forge-backup.timer` | 04:00 | cp + validate `forge.db`, tar `models/` | → `backups/` (45 G; KEEP=5 honoured, pruned 09-08) | 04:00 today, 11 s, OK | yes | **KEEP** (off-box DR target still operator-gated) |
| `forge-ranker-eval.timer` | 05:00 | 5 model fits, 2 streak evals, 4 audits (`daily_ranker_eval.sh`, 616 lines) | 8.9 G snapshot → `models/` (338 artifacts, no pruning), `ranker_eval/` | 05:00–05:18 today; 23 min CPU; **30.6 G peak RSS (20–34 G every run since 08-25)** on a box whose Crucible services OOM'd twice (D399/D401) | core yes: **models ARE hot-loaded per iteration** | **KEEP core, SIMPLIFY** (table below); add `MemoryMax=` |
| `forge-prereg-watch.timer` | 06:30 | DUE / waiting / UNWATCHABLE on open preregs | `config/preregistrations.jsonl`; refreshes `.snapshots/forge_live.db` | 06:30 today, "no open preregistrations" | yes (freeze §6 governance) | **KEEP**; installed units are file *copies*, the other 7 are symlinks (`~/.config/systemd/user/`) → re-symlink; `setup_new_box.sh:147` enables only 3 timers |
| pre-commit: `grammar-version-bump`, `grammar-doc-sync`, `freeze-governance` | commit | hard rule #10 / doc sync / signed-freeze guard | `grammar.yaml`, `GRAMMAR.md`, `preregistrations.jsonl` (`check_freeze_governance.py:43`) | n/a | yes | **KEEP all** |
| pre-commit: ruff, ruff-format, mypy, 6 hygiene hooks | commit | lint | — | — | yes | **KEEP** |
| user crontab | — | 30 QuantIQ jobs, 0 Forge | — | — | out of scope | note only |
| Crucible → Forge readers (not ours, but constrain us) | 06:00 daily / on demand | `crucible-morning-digest` regex-parses our journal (`loop iteration (\d+)`, `sampler_attempts:`, `phase_timings:` — `morning_digest.py:68-80`); `crucible funnel --compare` reads `forge_funnel.json` (`forge_source.py:47-48`) | — | — | de-facto contracts | **journal line formats and the funnel export are frozen interfaces** |

### `daily_ranker_eval.sh` by section

| Section (lines) | Output | Consumer | Verdict |
|---|---|---|---|
| train verdict (77-88) | `verdict_model_v1_*` | daemon F3, every iteration (`main.py:2377`); QuantIQ dashboard | KEEP |
| train-robustness `target_cpcv_p25` (90-116) | `robustness_model_v1_*` | daemon quality lane (`main.py:2411`, `_QUALITY_LANE_TARGET`) | KEEP |
| train-robustness `target_wf_p25` (same block, L100-104 "keep the retarget revertible") | second daily artifact | **nothing** | REMOVE (high) — one fewer 8.9 G read |
| train-tail ×2 `sharpe_baseline_n800`, `wf_p10_n200` (118-150) | `tail_model_v1_*` | daemon tail/trend lanes (`main.py:2498-2510`) | KEEP (verify the trend lane's base target string before touching either) |
| eval + F3 streak heredoc (152-296) | `streak.jsonl` | healthcheck `learning_drift`, `forge status`, QuantIQ `pipeline_queries.py:617` | KEEP the one AUC/calibration row (model-decay alarm); drop the ~95 lines/day of per-model cumulative prints |
| eval-robustness (297-303) | journal only (~90 lines) | nothing | REMOVE (medium) |
| re-wire streak heredoc (305-421) | `rewire_streak_wfp25.jsonl` | healthcheck, `forge status` SPRT gate, QuantIQ `:618` | REMOVE with the flip apparatus (§4 #2) — but QuantIQ reads the file: confirm, or keep appending a minimal row |
| campaign carriage audit (423-466) | `campaign_audit.jsonl` | healthcheck `check_campaign_carriage` | REMOVE with the audit (registry stays for `cell_floor` membership) |
| writer-activation probe (468-506) | `activation_probe.jsonl` | healthcheck | KEEP (the D290 INERT-writer class is a real supply failure) |
| freeze metric-B census (508-518) | `search_multiplicity_census.jsonl` (0.0% daily) | healthcheck `freeze census` | **§8 decision** (freeze signed; hook enforces structurally) |
| vix-conditioner share (520-614) | `vix_conditioner_share.jsonl` | nothing (by design) | REMOVE (high) — v55 zeroed the cell (D366); prints `0.0/0.0` forever |

---

## 3. Complexity reduction proposals

Cross-cutting fact: the daemon runs `FORGE_QUALITY_RANK_MODE=gate-tail`, where `composite = prior`
(`ranking/queue.py:170`, journal "hard-gate (composite bypassed)" every iteration). The §6.2 composite
ranker (`ranker.yaml`, `scorer.py`, `ranking/config.py`, `ranking/types.py`) is live only for one
telemetry column (`_hygiene_score`, `main.py:2722-2723`). The merit ("ranked") arm is **55 of 200
slots**; twelve D-justified mechanisms shape the rest (tail 95, trend 40, holdout 10, prefilter_sample
40 on top, arm floor, cell floor, min-per-hypothesis 15, F3 gate p≥0.02, tail_norm ordering, Jaccard
penalty, refutation ×0.25, learned draw weights) — all live, all KEEP; the finding is representation.

| # | Where | Finding | Simpler form | LOC | Risk | Conf | Deploy? |
|---|---|---|---|---|---|---|---|
| 1 | `cli/main.py` (3,168) | `_run_one_iteration` = 826 lines (L1968-2794); 9 near-identical `_load_*` loaders (L847-1494) + 9 `_format_*_line` twins, each re-parsing the 57 MB gated export (9 calls + `rate_limiter.py:218` + `consumer.py:244` = **11 parses/iteration**, the `weights≈18 s` phase bucket); 8 env resolvers (L657-922); ~35 echo stanzas | Do NOT split wholesale (D065/D105/D106; July dependency audit agreed). (a) parse the export once per iteration, table-drive the 9 loaders (`_WEIGHT_FAMILIES`), keep old names bound in `main` for the 20 private seams tests import; (b) move the 8 resolvers to `cli/knobs.py`, re-exported; (c) dead-flag stanzas leave with their flags | −800 | low | high | (a) versionless deploy; (b)(c) refactor |
| 2 | flip-decision apparatus: `ranking/evaluation.py` (730), `ranker_model_cmd.py` (714), `sequential_test.py` (125), `status_cmd.py` (347), `ranking/calibration.py`, two bash heredocs (~270 lines) | SPRT flip gates + streak clocks decided flips already made (gate-tail D252, holdout D256); `eval-rewire`/`eval-prior-weight` compare modes that are now fixed; `evaluate_tail_shadow_pooled` has 0 callers; `PriorWeightEvaluation`/`RewireEvaluation` exist for them | Keep train + one AUC/calibration row; delete `eval-rewire`, `eval-prior-weight`, `evaluate_tail_shadow_pooled`, `sequential_test.py`, status flip gates (`status_cmd.py:118-174`), both heredocs, wf_p25 training | −~1,000 src, −~1,200 tests, −~300 bash | low (timer + status only) | high | timer only |
| 3 | §6.2 composite scorer: `ranker.yaml`, `scorer.py` (87), `ranking/config.py` (131), `ranking/types.py` (105) | bypassed in gate-tail; only feeds `hygiene_score` for the D284 "hygiene incumbent" streak judge, retired by #2; `ranker.yaml` documents `method: greedy|dpp` — no `dpp` exists (`_VALID_METHODS=("greedy",)`, `config.py:30`) | delete all four (+ `test_scorer` 256, `test_config` 309, `test_types` 261); if a hygiene column is still wanted, 4 constants in `shadow.py` | −323 src, −826 tests | low after #2 | high | restart |
| 4 | parked experiment plumbing | arm-B: `feedback/book_usable_weights.py` (162) + `iterator._draw_arm:125` + `_resolve_generation_arm_b_share:817` + `_load_book_usable_regime_weights:847` + unit env (`generation_arm` NULL on all 160,952 submissions of the last 14 d; prereg REFUTED D351); orthogonal floor: `_orthogonal_family_floors:657` + `rejection_weights.apply_orthogonal_family_floor:1099` (RETIRED D367, env absent from live environ); `_RV_REGIME_WEIGHTS_FROZEN` body `rejection_weights.py:1007-1048` returns `{}` unconditionally **and** `_load_regime_weights` (`main.py:1045-1098`) re-reads the export every iteration to compute it; `relative_value` is disabled anyway (`search_space.py:96-98`) | delete all; thread `None` for `regime_weights` (sampler `_pick_regime` treats `{}`/`None` alike → uniform `rng.choice`, `sampler.py:1915`: byte-identical) | −~550 src | low (each is the code's own documented OFF path: "iterator draws no arm coin" `main.py:2209`; floor `{}` → block skipped `:2135`) | high | restart + unit `daemon-reload` |
| 5 | `cli/healthcheck_cmd.py` (1,031), 17 checks | retired-programme checks: `search_multiplicity_census` (freeze metric B, signed), `learning_drift(rewire)` (flip made), `campaign_carriage` (registry does not reshape a batch), `component_contributions_export` (nothing in `src/` reads that export), `tmp_headroom` (wrong disk) | steady-state 11: service_active, loop_liveness, submission_progress, deployed_code_staleness, contracts_pin, inbox_rejections, exports freshness, models freshness, learning_drift(F3), activation_probe, registry_unknown_family (+ hypothesis_weights_fallback) | −400 src, −130 tests | low | high | timer only |
| 6 | predicate engine: `grammar/models.py:74-173`, `predicates.py:226-374`, `path_resolver.py` (187), `custom_predicates.py` (1,231) | 6 predicate types; v55 uses `custom_python`×16, `cardinality`×4, `numerical_range`×1; **`requires`/`forbids`/`compatibility` are used by zero rules in v55 and in all 55 archived grammars** (grep = 0). Hardcoding the 21 rules as Python would remove ~500 LOC but breaks the operator-owned YAML provenance chain (hard rule #1, config_hash lineage) | KEEP the YAML + `custom_python` dispatch + `path_resolver`; **delete the three unused predicate types** (models, evaluators, `__all__`, `test_predicates_requires_forbids.py` + `test_predicates_compatibility.py` = 306 lines). The loader then refuses a grammar using them — under a freeze that is a feature | −200 src, −300 tests | low (archives verified; `loader.py:122` archive check is a byte hash) | high | restart; **operator sign-off** (grammar package, §8) |
| 7 | config sprawl: 4 yaml + 8 live env + 3 commented env + ~14 `run` flags + hardcoded | `_RUN_DEFAULT_*` (`main.py:2776-2791`: seed 0 / batch 10 / max 1000 / poll 600) silently diverge from `forge.yaml` (42/200/5000/60) behind `--no-config`; `prefilter.yaml` `auto_tune.adjustment_pct_per_step` is *required* by the loader (`calibration.py:256`) but read only by `grammar apply-proposal` (`grammar_cmd.py:275,291`) — `feedback/auto_tune.py` no longer exists; `~/optbt_data/exports` hand-built 13× in 7 files next to two named constants; `_DEFAULT_FORGE_DB` in 3 CLI files | one `forge.yaml` `{paths, enumeration, submission, lanes, ranking, prefilter}` under one Pydantic model; drop `--no-config` (tests use a fixture yaml); env reduced to the two kill-switches + `FORGE_FREEZE_REOPENER`; lane knobs (tail/trend slots, holdout frac, p_floor, sample_n) move to `lanes:` (hot-read like `forge.yaml` already is) | −250 src; unit env stanza gone | medium (`test_config_threading.py` 242 + resolver tests rewrite; live-behaviour change) | med-high | deploy ritual + unit edit |
| 8 | lanes: `ObjectiveLane` (`queue.py:55`) covers tail/trend; holdout via `sample_exploration_holdout:181`; prefilter_sample inline `main.py:2571-2603`; submitter re-derives tags from 3 hash sets (`submitter.py:309-311, 359-372`) | three ways to say "subset carries tag X from pool Y with rng stream Z" | one `Lane(tag, slots, pool, order, filter)` table iterated in the current draw order (lanes → merit → holdout last); submitter takes one `{config_hash: tag}` map; the "55 merit slots" fact becomes visible | −190 | medium (golden a fixed batch → identical tags/ranks) | med-high | versionless deploy |
| 9 | duplicate utilities | newest-file-by-mtime ×5 (`chain_inception.py:99`, `healthcheck_cmd.py:668`, `registry_loader.py:44`, `freeze_tail_reading.py:142`); JSONL append/read ×8; config-key extractors ×7 (`campaigns.config_cell:78` vs `book_usable_weights._cell_of:68`; `diversifier._signal_keys:40` ≡ `prior_promotion._signal_keys:27`); `_check_unit_interval` ×3 | `core/paths.py`, `core/jsonl.py`, `core/config_keys.py` | −150 | low | high | refactor |
| 10 | `enumeration/sampler.py` (2,473) | `sample_config` 357 lines orchestrating 30+ stage helpers; 24 hypothesis-conditional branches; zeroed retirement shims (v55 vix `_VIX_CONDITIONER_SHARE=0.0` L291-314, v48 resid weight L329, tombstones L214/424/712/2447) | delete each shim **in its own commit, accepted only if the cold-start goldens stay green** (a shim that draws `rng` before comparing to 0.0 moves the golden → grammar-version event → leave it under the freeze); fold tombstones to one D-link each | −250–400 | medium | medium | restart |
| 11 | `grammar/{loader,archive,version_audit,validator}.py` (391 in 4 files); `funnel/` (289 in 3) | cosmetic fragmentation | merge to 2 files / 1 file | 0 | low | high | refactor (optional) |
| 12 | performance (July audit) | **mostly fixed**: submit 7.3–7.8 s (was 195–202), reconcile 2.2–4.1 s (was 30–37); per-candidate `BEGIN/COMMIT` (`submitter.py:207-277`) is the M-10 crash-safety txn — KEEP; the 11× export parse (#1) is the only remaining self-inflicted cost; `prefetch=335–357 s` is Crucible-side | no perf-motivated change (binding constraint is Crucible refit triage, D368/D393); bank ~16 s/iteration as a side effect of #1 | — | — | high | — |

**Explicit KEEP (complex for a documented reason):** prefilter `Filter` Protocol + cost-tier battery
(9 implementations); per-candidate submit transaction; `auto_tightened_thresholds.yaml` + fingerprint
(`enumeration_inputs_hash` identity, hard rule #6); `refutations.py` (fingerprint in the same hash);
YAML `rules:` + `custom_python` dispatch (hard rule #1); `FORGE_F3_RANKER` / `FORGE_QUALITY_RANKER`
kill-switches and `prior_promotion.py` (the no-artifact path, `queue.py:166`); all twelve batch-shaping
mechanisms; `funnel/` (Crucible contract D096); `feedback/preregistration.py` + `forge prereg` (the
freeze hook's data source — the July plan's P1-2 "retire" is now wrong); `SyntheticFeatureCache` +
`_demo_registry` (fixtures + `forge enumerate/prefilter` diagnosis); the daily trainer at daily cadence.

---

## 4. Dead / unused code — grouped by category and confidence

Legend: **H/M/L** confidence. "Byte-identical" = removal provably changes no draw, hash, or
submission (§3.1 F of the reachability report); everything so marked is a restart, not a grammar event.

### 4a. Dead code (unreachable under the live flags/env)

| Path | What | Why it doesn't serve the goal | Conf | Risk |
|---|---|---|---|---|
| `feedback/book_usable_weights.py` (162); `enumeration/iterator.py:125-134, 211-212, 290-291, 329-344`; `cli/main.py:817-863, 2235-2246`; unit `FORGE_GENERATION_ARM_B_SHARE=0` | arm-B generation A/B | share 0; prereg REFUTED D351 ("revert to a single map"); `generation_arm` NULL on 160,952 rows/14 d; no journal `generation_arm_ab:` line in 60 iterations | H | none (byte-identical); tests `test_generation_arm_ab.py` 133, `test_generation_arm_flag.py` 56, `test_book_usable_weights.py` 143 go with it; `contracts_check.py:209-216` comment about the free `generation_arm` field may stay |
| `cli/main.py:657-689, 2129-2138`; `feedback/rejection_weights.py:1099-1142`; `docs/proposals/orthogonal-family-supply-for-pbo.md` | D216 orthogonal family floor | RETIRED D367 (founding evidence retracted); env absent from `/proc/<pid>/environ` (only in unit comments) | H | none (byte-identical); `test_orthogonal_family_floor_invariants.py` 49 + 5 tests in `test_cli_run.py`/`test_run_loop.py` |
| `feedback/rejection_weights.py:1007-1048` (`compute_relative_value_regime_weights`, `_RV_REGIME_WEIGHTS_FROZEN=True`) + `cli/main.py:1045-1098` (`_load_regime_weights`, `_format_regime_weights_line`) + `regime_weights` kwarg through `iterator.py:145` / `sampler.py:1168,1301,1761` | curated relative_value regime weights | always `{}`; `relative_value` in `DISABLED_HYPOTHESES` (`search_space.py:96-98`) so `sampler.py:1915` never fires; costs one export parse per iteration | H | byte-identical (`_pick_regime` uniform for `{}`/`None`); kwarg removal touches draw-path files → separate no-op commit proven by goldens |
| `cli/main.py:2441-2453` (`_blend_score`, `_DEFAULT_QUALITY_RANK_MODE="blend"`) | pre-rewire multiplicative blend | live mode `gate-tail` since 07-06 (D252); documented rollback lever | M | §8 decision — collapsing removes the env var and the rollback |
| `ranking/queue.py:181-231` (`sample_exploration_holdout`, `rank_batch_with_holdout`) + `ranking/__init__.py:8,28` | older holdout entry point | 0 src callers; superseded by `rank_batch_with_exploration` | H | none; `test_queue.py` cases |
| `ranking/evaluation.py:405-415` (`evaluate_tail_shadow_pooled`) | pooled tail eval | 0 callers anywhere except 4 tests | H | none |
| `ranking/evaluation.py:640-730` (`prior_weighted_composite`, `PriorWeightEvaluation`, `evaluate_prior_weight_ab`) + `ranker_model_cmd.py:463-521` (`eval-prior-weight`) | B2 prior-weight A/B | nothing invokes the subcommand; read is spent | H | none; tests in `test_evaluation.py`, `test_ranker_model_cmd.py` |
| `prefilters/calibration.py:442-460` (`write_loosening_proposal`) | loosening writer stub | 0 callers (docstring L6 + `__init__` export only) | H | none |
| `ranking/campaigns.py:172` (`active_selection_slots`) + `selection_cell/selection_slots` fields | D287 slot reservation consumer | consumer deleted D376 | H | none |
| `grammar/models.py:104-150` + `predicates.py:202-367` (`requires`/`forbids`/`compatibility` types) | 3 predicate types | 0 uses in v55 and all 55 archives | H (fact) / operator (policy) | §8 — grammar-package schema, hard rule #1 adjacency |

### 4b. Unused (defined, never called in production)

| Path | What | Why | Conf | Risk |
|---|---|---|---|---|
| `cli/feedback_cmd.py` (153) — `forge feedback` | manual feedback pass | exact duplicate of `_consume_feedback_after_submit` (`main.py:1863-1871` vs `feedback_cmd.py:93-99`); loop consumes every cycle | H | low (`_has_identical_pending_proposal:191` dedups); `test_feedback_cmd.py` 325 |
| `ranker_model_cmd.py:370-460` (`eval-rewire`) and `eval` | mode comparisons | timer re-implements the verdict inline (`daily_ranker_eval.sh:153-176, 313-325`) → two copies of the F3 verdict logic; keep ONE (the CLI `eval`, and have the script call it) | H | low |
| `ranking/sequential_test.py` (125) + `status_cmd.py:91-174` | SPRT flip gates | sole importer is `forge status` (operator-only); the flips are made | M | `test_sequential_test.py` 97, `test_status.py` 217 |
| `prefilters/calibration.py:112-117` (`AutoTuneCalibration`) + `prefilter.yaml` `auto_tune:` | dead key | only `grammar apply-proposal` reads it; loader *requires* it (L256) — remove key and loader requirement together | H | must change together or startup breaks |
| `ranking/evaluation.py:297-310` (`spearman_corr`) | helper | test-only per census; check `_average_ranks` duplication first | L | ambiguous |
| `FORGE_REFUTATION_GUARD` (`enumeration/refutations.py:142-145`) | kill-switch, undocumented (0 MANPAGE hits) | live and determinism-load-bearing; env var is the undocumented part; newest refutations export is 2026-07-31 — effects frozen at that snapshot | H | document or drop the env var, not the module |
| `config/forge.yaml` `crucible.db_path` → `consumer.py:224-251` | direct `runs.duckdb` read fallback when no gated export exists | "never direct DB access" (architecture); hard-rule-#2-adjacent latent path; comment says test fixtures | M | §8 — remove fallback + key, or keep for fixtures |

### 4c. Stale experiments / one-off artifacts

| Path | What | Why | Conf | Risk |
|---|---|---|---|---|
| `scripts/ceiling_record_test.py` (147), `joint_frontier.py` (177) | freeze ceiling instruments | 0 tests, 0 wired; conclusions in D368/declaration | H | none — MANPAGE retirement-ledger row |
| `scripts/second_gate_contrast.py` (154) + `tests/unit/test_scripts/test_second_gate_contrast.py` (102) | D339 conditioner contrast | D395 closed "the last §7 item" | H | none |
| `scripts/threshold_resolution_value.py` (262), `promoted_leg_recall.py` (181), `production_by_group.py` (220), `tail_verified_alignment.py` (150) | spent research reads | 0 wired, 0 tests; D353 / D-cited / prereg `4e369b779ca9` REFUTED / D155 monitor with 0 STATUS mentions | H (first three) / M (alignment) | none |
| `scripts/freeze_tail_reading.py` (522), `freeze_registered_read.py` (405) + 3 test files (~500 lines) | registered-read instruments | 31/31 preregs resolved; touched 09-05 only as an instrument repair (D403); needed again only for a §5 reopener within-basis read; `--resolve` is the only writer of a resolved prereg outside `forge prereg resolve` | M | §8 — keep for reopeners or archive |
| `scripts/search_multiplicity_census.py` (530) + healthcheck check + `test_census_classification.py` (98) | freeze metric B | signed; reads 0.0% daily; hook enforces structurally | M | §8 |
| `sampler.py` zeroed shims (L291-314, 329, 214, 424, 712, 2447) | version tombstones | see §3 #10 | M | golden-gated, one per commit |
| `docs/proposals/`: `grammar-freeze-criterion.md` (554), `ceiling-saturation-experiment.md`, `v50-winner-neighborhood-priors.md` (385; only a comment cites it), `generation-model-levers.md`, `regime-orthogonal-arms.md`, `prereg-honest-scope-ab.md` (WITHDRAWN D402), `ops-debt-roundup-2026-07.md` (extract item 5a first), `repo-simplification-2026-08.md` (after carry-forward) | terminal proposals | not cited from code; sweep-on-land missed them | H | none — `git mv` to `_archive/` |
| `fable-audit/` (7 folders, 368 KB) | July audits | 0 live-ledger citations except D300/retirement plan; executed items ticked; live items extracted into §6 (reliability) and §3 | H | none — `git mv fable-audit _archive/fable-audit-2026-07/` |
| root `GRAMMAR_REVIEW_AND_EXPANSION.md`, `LEARNED_SYSTEMS_AND_GENERATION_REVIEW.md` | expansion roadmaps | `architecture.md:151` "re-verdict due at the freeze declaration"; freeze signed 08-14, no re-verdict recorded; expansion vs frozen grammar | H | none — archive; `path-c-scope-expansion.md` keeps the §5 thread |
| `docs/INDICATOR_THRESHOLDS.md` (180) | 2026-05 snapshot, self-bannered stale | 0 citers in src/tests/scripts; caused D153 mis-derivation | H | repoint `grammar-change.md` + `CLAUDE.md:138` at `enumeration/indicator_thresholds.py` |
| `~/forge_data/forge.db.pre_arm_cleanup_20260731_230544` (6.3 G) | D342 pre-repair copy | 5 validated nightly backups supersede it | H | §8 — delete after operator confirms |
| `~/forge_data/{alpha_budget,shadow_null,eod_checks,winning_cohort}/`, `archive/king_retired_20260619`, `archive/backfill_source_gated_runs_20260609.json` (50 M), `logs/` (empty) | outputs of retired programmes (D373, D235-239, D253, D190, D111) | 0 refs in docs/src/scripts | H | archive off-disk or delete |
| `~/forge_data/ranker_eval/robustness_streak.jsonl` (06-19), `robustness_streak_wfp25.jsonl` (07-16) | dead clocks | no appender since those dates; QuantIQ `pipeline_queries.py:18` documents the death | H | archive |
| `~/forge_data/approvals/*.json` | QuantIQ dashboard → Forge approvals (08-11/13) | **no reader in Forge** | M | §8 — a channel we never consume |
| `_archive/PROMPT_*` (133 files, 1.1 MB) + `CRUCIBLE_*` (17) | answered relays | live channel is `freeze/relays/`; no live reference into them | H | `git rm` (history keeps them) |

### 4d. Lingering modules (wired in, not contributing)

| Path | What it does | Last evidence of use | Verdict | Conf | Risk |
|---|---|---|---|---|---|
| `ranking/regime_supply.py` (191) | D144 journal line only; result unused (`main.py:2620-2626`) | journal ×59/day | REMOVE | H | one journal line + `test_regime_supply.py` 168 |
| `feedback/stuck_state.py` (138) | zero-promotion streak → `stuck_state:` journal line; nothing consumes it | ×59/day | REMOVE (or fix): under book-level promotion `promoted_count` stays 0 so the WARN is permanent noise (`OPEN_PROPOSALS.md:1170-1176`) | M | none |
| `feedback/promoted_patterns.py` (61) + table | writes `promoted_patterns` | 8 rows ever (all 2026-08); 0 readers anywhere | REMOVE writer (Q44); leave DDL additive | H | `test_promoted_patterns.py` 130 |
| `submission/pre_filter_logger.py` (101) + `pre_filter_logs` table | per candidate×filter rows | **45,751,165 rows**; 0 SQL readers in Forge/Crucible/QuantIQ (QuantIQ `forge_queries.py:17` names it in a docstring; its only SQL is `FROM submissions`) | STOP WRITING (Q44) after QuantIQ confirms; keep DDL | H | §8 |
| `ranking/campaign_audit.py` (196) + `cli/campaigns_cmd.py audit` + eval section + healthcheck check | carriage audit | `campaign_audit.jsonl` daily; registry has 2 FARMING entries but the registry does not reshape a batch | REMOVE audit; KEEP `campaigns.py` (`config_cell`, membership for `cell_floor`) | H | none |
| `feedback/yield_audit.py` (248) + `cli/yield_audit_cmd.py` (100) | dead-name/cold-cell printout | D309 (07-21); a rider = grammar change = prereg + bump | REMOVE (§8 if operator wants the read) | M | `test_yield_audit.py` 274 |
| `feedback/proposer.py` (457), `proposal_writer.py` (387), `trade_concentration.py` (175), part of `types.py` (328); `cli/grammar_cmd.py` list/approve/reject/apply (423) | §8.5 proposal lifecycle → `OPEN_PROPOSALS.md` + `grammar_proposals` | 500 proposals in May (all rejected), 3 in July, 1 on 08-07 (a `deflated_sharpe` tighten no prefilter models); only `tighten` triggers remain (`proposer.py:91,154,190,270`); Q58 guard returns `[]` while `promoted_count==0`; `apply-proposal` writes `grammar.yaml` at runtime with no freeze awareness (only the pre-commit hook guards) | **§8 operator decision** (hard rule #4 wording). Recommendation: retire writer + CLI group, keep `analyzer.py` (feeds `feedback_gates`/`feedback_hypotheses` lines), keep `OPEN_PROPOSALS.md` as a static machine-parsed file | M | `test_phase5_invariants.py` HR#4 structure tests, `test_grammar_cmd.py` 561, `test_proposer.py` 550, `test_proposal_writer.py` 364, `test_trade_concentration.py` 242; QuantIQ parses the file |
| `cli/grammar_cmd.py revert` | re-bump from an archived grammar | dead-by-policy (hook fires on any `grammar.yaml` change without a prereg); `git revert` + bump does the same | §8 | M | `test_grammar_cmd.py` |
| `cli/healthcheck_cmd.py` 5 checks (§3 #5) | retired programmes / wrong disk | hourly | REMOVE 5, retarget 1 | H | none |
| `train-robustness target_wf_p25`, eval-robustness print, vix share section (script) | see §2 table | daily | REMOVE | H | none |
| `ranking/shadow.py` (150) + `shadow_scores` table (1,064,171 rows) | post-submit shadow scores | read by the timer's eval and the drift checks | KEEP | H | — |

### 4e. Dead dependencies, configs, docs

| Item | Finding | Verdict | Conf |
|---|---|---|---|
| Python deps | all 8 runtime deps imported (numpy: one src import; demotion would need a polars rewrite — not worth it); dev deps all used; `pytest-cov` already absent | **0 to drop** | H |
| `config/ranker.yaml` | see §3 #3 (`dpp` phantom; weights bypassed) | delete with the scorer | H |
| `config/prefilter.yaml` `auto_tune:` | see §4b | delete with the loader requirement | H |
| `config/forge.yaml` `crucible.db_path` | see §4b | §8 | M |
| unit env: `FORGE_GENERATION_ARM_B_SHARE=0` (live), `FORGE_ORTHOGONAL_FAMILY_FLOOR` / `FORGE_QUALITY_RANKER` (comment-only lines) | dead / retired | remove with §4a; 219 of 249 unit lines are comments narrating D080→D359 (August Step D) → move history to D-entries, keep the per-variable ⚠️ lines | H |
| `_RUN_DEFAULT_*` + `--no-config` (`main.py:2776-2791`) | second silent config surface | see §3 #7 | H |
| Docs with wrong facts (12 files, ~40 statements) — full table in the docs report; headline rows: `CLAUDE.md:28` ("~1,850"), `:38-39` ("§3.6 says 25" — DESIGN already says 21), `:87-88` (teaches `cp` to /tmp — the 62 GB tmpfs trap), `:92` ("~10" → 24), `:100` (`PHASE_N_HANDOFF.md` lives in `_archive/`), `:99-101` (no mention the grammar is FROZEN — the single most load-bearing missing fact), `:124` (§12 is historical), `:138` (INDICATOR_THRESHOLDS row); `architecture.md:16,77` (`auto_tune.py` deleted), `:51` (23 → 21 files), `:110-121` (omits `forge-prereg-watch`, `check_freeze_governance.py`, `freeze_read_watcher.py`); `MANPAGE.md:126,256,766` (auto-tune), `:136-142` (7 lines on the retired floor), `:182,223`, `:746,810` (missing timer/hooks; "symlinked" is false for prereg-watch); `HOW-TO.md:210-222` ("Changing the grammar" with no freeze/hook mention), `:59-84` (no prereg-watch row); `quality-gates.md:27-28` (freeze-governance hook missing); `feedback-change.md:15`, `deploy.md:32,8-10`, `config/README.md:12`, `DESIGN.md:42,505-507,641-654,664-668,709,768,744-824`, `proposals/v39-ve-program.md` + `v41-tier3-xsect.md` (say SCOPING/staged; both DEPLOYED), `deploy/NEW_BOX_TRANSFER.md:111,141,200` + `setup_new_box.sh:160` ("three timers" → four), `stage_transfer.sh:21,86` ("v22"), `README.md:16` (`pytest` → `uv run pytest`), `tests/README.md:18` (24 files; the phase0 clock scan covers `src/` only, not tests — `test_phase0_invariants.py:16,63-87`) | fix in place | H |
| `docs/GRAMMAR.md` (402) | 51 version-mention lines, 8 lines >600 chars (1,613 at L331); current-rule content ≈150–180 lines | shrink to ~200; keep every rule-id heading + S5 terms (test-enforced) | H |
| `docs/DESIGN.md` (883) | §2.1 diagram wrong as-built (L63-120), §5.5 auto-tune stated live, §8.4 auto-edit fiction, §8.5 dashboard/Slack bullets never built, §9.3 "YAML inbox" (JSON per D006), §12 80 lines historical | shrink to ~600 as an operator-reviewed diff (§3.5 bodies untouched, hard rule #1) | H |
| `docs/MANPAGE.md` (816) | env-knob essays L136-230 quote values/dates | ~650 | H |
| Caches / strays | `.mypy_cache` 25 M, `.hypothesis` 2.8 M, `__pycache__` for deleted modules (`experiment_cells`, `winner_prior`, `alpha_budget*`, `test_young_explore`, …), 5 stray `cpython-314` pyc, root `scratchpad/` (empty), `~/forge_data/logs/` (empty) | delete | H |

---

## 5. Test suite audit

Baseline: 191 files / 46,729 lines / 2,158 tests / 232 s; 0 orphaned imports (AST check); 2
conditional skips, 0 xfail; the `slow` marker is declared and used by 0 tests.

### Remove (code-first where noted)

| File | Subject | Why | Conf | Risk |
|---|---|---|---|---|
| `tests/unit/test_enumeration/test_v44_vix_conditioner.py` (358, 12 tests, ~12 s) | v44/v45 conditioner under a forced non-zero share | retired at v55 (`sampler.py:311`); **first move `_v44_registry` into `test_v55_vix_conditioner_retired.py:38`** | H | low |
| `test_generation_arm_ab.py` (133) + `test_cli/test_generation_arm_flag.py` (56) + `test_book_usable_weights.py` (143) | arm-B | with §4a code | M | code-first |
| `tests/invariants/test_orthogonal_family_floor_invariants.py` (49) + 5 tests in `test_cli_run.py`/`test_run_loop.py` | orthogonal floor | with §4a code | M | code-first |
| `test_sampler.py` golden cluster (~500 lines: `test_d258…`, `test_d263…`, `test_d264…`, `test_d266…`, `test_d270…` ×2 + the three `_GOLDEN_*` literal lists at L1599/1848/2104) | per-activation cold-start goldens, several for retired levers | one v55 golden over one seed (`test_phase2_invariants::test_enumeration_byte_identical_for_same_triple` exists) + one per still-live OFF/ON lever | M | re-pinning is a D-entry event (hard rule #6) |
| `test_ranking/test_evaluation.py::test_held_out_platt_reduces_ece_vs_raw` (L230) | Q51 flake | even/odd split on unordered DuckDB rows; fix the ORDER BY or delete — never keep a known flake on the deploy gate | H | none |
| tests of everything retired in §3/§4: `test_scorer` 256, `test_config` 309, `test_types` 261, `test_sequential_test` 97, `test_status` 217, parts of `test_evaluation` 792 / `test_ranker_model_cmd` 383, `test_regime_supply` 168, `test_promoted_patterns` 130, `test_pre_filter_logger` 296, `test_yield_audit` 274, `test_feedback_cmd` 325, `test_predicates_requires_forbids` + `test_predicates_compatibility` 306, healthcheck ~130, `test_second_gate_contrast` 102, (operator-gated) `test_grammar_cmd` 561, `test_proposer` 550, `test_proposal_writer` 364, `test_trade_concentration` 242 | — | retire in the same commit as the code | H | — |

### Keep but simplify

| File | What | Proposal |
|---|---|---|
| version-retirement guards: `test_v55_vix_conditioner_retired`, `test_v52_capitulation_retirement`, `test_v47_single_name_retirement`, `test_v34_census_retirements`, `test_option_momentum_activation`, `test_v1_grammar` | silent re-admission tripwires for **Python-side emission policy** the freeze hook cannot see | KEEP as-is |
| `test_v33_generation_health` (12), `test_v36_exit_duration_priors`, `test_v38_exit_mix`, `test_v39_ve_program`, `test_v40_mr_timer_cell`, `test_v41_tier3_xsect`, `test_mr_grammar_v24/28/29`, `test_resid_vix_v27`, `test_trend_grammar_v23(+_exits)`, `test_event_momentum` | one D-entry each, ~30 lines/test, narrative docstrings | fold into one `test_v55_emission_policy.py` organised by hypothesis; ~1,500 → ~600 lines, behaviour pinned unchanged |
| `test_sampler.py` (3,042, 107 tests) | per-D-entry groups (`d103_pick`×4, `d105_bucket`×5, `d258_dsj`×4, `d263_ivol`×4, `pick_regime`×5) | parametrize the 5 lever OFF/ON pairs; target ~1,800 |
| `test_custom_predicates.py` (1,702, 71) | `r1_mean`×7, `r3_volatility`×6, `r2_trend`×5 | table-driven parametrize per rule id |
| `test_consumer.py` (1,001, 29) | `reconcile_all`×8 | parametrize the reconcile matrix |
| helper duplication | `_insert_submission` ×16 files, `_gated_run` ×14, `_ctx` ×14, `_registry` ×9, `_config` ×8, `_candidate` ×7, `_insert_batch` ×6 | promote to `tests/fixtures/forge_db_rows.py`; ~400 lines, no behaviour change |
| `test_cli/test_run_loop.py` (956, 38) | resolver unit tests mixed with loop behaviour | split resolvers to `test_env_resolvers.py`; the D185 anti-inertness pair (`test_loop_forwards_yield_map_flags_to_iteration`, `test_loop_and_single_iteration_forward_identical_flags`) MUST survive any `main.py` change |
| 3 perf tests (14.1 s, 11.8 s + `test_same_seed_is_deterministic` 12.2 s) and 5 full-loop boots (6–9 s each) | ~85 s of the 232 | mark `slow`; share one module-scoped loop boot → suite ≈180 s |

### Implementation-coupled (the "24 files")

22 only `from forge.cli.main import app` and drive `CliRunner` — behaviour tests, safe under any
decomposition that keeps `app`. Real private coupling: `test_run_loop.py` (imports 8 privates,
patches `_run_one_iteration` ×4, `_time.sleep` ×4, two `_LOGGED` flags); `test_generation_arm_flag.py`,
`test_cell_floor_flag.py`, `test_config_threading.py` + `test_phase6_invariants.py`
(`_resolve_run_defaults`), `test_feature_cache_fallback.py` (string-patches `_build_feature_cache`),
`invariants/test_enumeration_inputs_reach_the_battery.py` (AST-reads `_run_one_iteration` source,
D352 — the strongest argument for keeping it one function or re-targeting the test when it splits).
§3 #1 keeps every seam bound in `main` by re-export.

### Invariants map (19 files, 121 tests)

phase0 HR#8/#5/D061 · phase1 §13.6 · phase2 §13.1 + OFF-byte-identical · phase3 §5 ranges + perf ·
phase4 §13.4 · phase5 HR#4 structure + consumer idempotency (**still needed while the proposal writer
stays; re-cut if §8 retires it**) · phase6 = grab bag (networkx ×2, doc needles ×4 — the only
load-bearing part — Q9/Q10 log lines, a docstring check, `_resolve_run_defaults` exposure) ·
phase6_properties Hypothesis · learned_ranker + features_are_performance_blind · inflight_depth +
stall_guard §7.3 · funnel, inbox_layout, search_n_trials_hash_excluded, enumeration_inputs_reach_the_battery ·
orthogonal_family_floor + option_momentum_activation (retired-lever OFF guards → §4a).

Test-enforced doc strings (survive every cut): MANPAGE `## COMMANDS` + `forge <name>` per registered
command + `### forge <top>` per top-level (`test_cli_help.py:88-121`, `test_phase6_invariants.py:64-66`);
HOW-TO `## Common situations` + `Crucible offline`, `rate limiter`, `Changing the grammar`;
architecture `§13.1`…`§13.6`; DESIGN §6.2 formula block mentions `regime_exposure_score` and not
`regime_diversity_score`; GRAMMAR rule-id headings + `### S5` terms; `OPEN_QUESTIONS.md` must contain
`Q9` + `param-no-promotion` **in the live file** (`test_phase6_invariants.py:124-127`) — amend the test
to consult the archive (like Q10) before sweeping Q9; root `STATUS.md`, `IMPLEMENTATION_DECISIONS.md`,
`OPEN_QUESTIONS.md`, `CLAUDE.md` must exist; `grammar_cmd.py` must contain `cmd_approve_proposal` +
`§13.2` (`test_phase6_invariants.py:147-152` — re-cut with §8 item 2); no `networkx` in pyproject.

### Gaps — close BEFORE any daemon-side removal (Batch 2)

| Path | Risk if broken | Proposed minimal test |
|---|---|---|
| `scripts/daily_ranker_eval.sh` (616 lines bash, 0 test refs) | silent model-publish failure; streak files stop; healthcheck reads its outputs | smoke run against a tiny fixture DB with `forge` stubbed on PATH; assert atomic publish + one JSONL row per clock |
| `scripts/live_db_snapshot.sh`, `deploy_preflight.sh` (0 refs) | prereg-watch `ExecStart` depends on the snapshot; preflight is the deploy gate | subprocess: snapshot of a temp DuckDB prints a readable path; preflight NO-GO on a dirty deploy-surface file |
| SIGTERM mid-submit | systemd sends SIGTERM; `main.py:3130-3148` handles only `KeyboardInterrupt`; no `signal.signal(SIGTERM, …)` in src; `submitter.py:199-242` writes the inbox file inside the DB txn → a SIGTERM between `submit_candidate` and commit leaves an inbox file with no row (July REL-4) | SIGTERM a `forge run` subprocess mid-batch; assert inbox files ⊆ committed rows (or that a handler raises `KeyboardInterrupt`) |
| hot grammar re-read + version flip mid-loop | `load_grammar` per iteration (`main.py:118/282/396`); a yaml edit stamps submissions before code deploys (D104); 0 tests pin the flip or a refusal | rewrite `grammar.yaml` between iterations; pin the intended behaviour |
| model reload cadence | per-iteration today (`main.py:2377`); nothing asserts it | assert `load_latest_model` is called once per iteration |
| export-outage swallow | `rate_limiter.py:224` and 13 `except (QueryError, OSError)` sites in `main.py:1004-1813` (`:1813` returns `()` unlogged — July REL-1); the "benign" `blocked … N% gated` line masks a dead export (D205/D240/D245 class) | exports dir unreadable → journal carries an explicit `export_unreadable` line, not just `blocked` |
| `healthcheck_cmd.py` `check_hypothesis_weights_fallback` (L497), `check_registry_unknown_family` (L648) | parse-only tests exist, no level tests | two `_levels` tests mirroring the other 16 |

Covered already (verified): contracts pin equality (`test_contracts_integration.py:56`, RED on purpose
now), `enumeration_inputs_hash` 3-part composition, `config_hash` uniqueness (3 tests),
`backup_forge_db.sh` (3), `freeze_read_watcher.py` (5), hooks (13).

### Fixtures

`conftest.py` 3 autouse fixtures; two (`_dormant_earnings_coverage`, `_pinned_universe`) exist only
because `sampler._UNIVERSE_EXPORT_DIR` resolves at import (August Step F3 removes both — a
sampler-module edit, bugfix-class deploy). `fixtures/strategy_configs.py` (347) is imported by 82
files — the real shared core. The DB-row builders are the missing shared fixture.

---

## 6. Reliability findings never actioned (July `fable-audit/reliability/`, 0 D-entries cite any REL item)

| Item | Where | Fix (one line) |
|---|---|---|
| REL-1 unlogged `QueryError` swallow | `main.py:1813` `except QueryError: return ()` | log at WARN with the export path; healthcheck check on the line |
| REL-2 rate-limiter swallow | `rate_limiter.py:224` | same |
| REL-4 SIGTERM inbox-vs-DB tear | `main.py:3130-3148`, `submitter.py:199-242` | install a SIGTERM→`KeyboardInterrupt` handler; write inbox after commit, or record the hash before the inbox write |
| REL-5 universe fallback | `sampler.py:511-581` | fail loud when the universe export is missing instead of falling back |
| REL-8 `OPEN_PROPOSALS.md` lost-update | `proposal_writer.py` read-modify-write | moot if §8 retires the writer; else write via tmp+rename with a lock |
| REL-12 unbounded `models/` | 338 artifacts; every loader parses every file every iteration (`model.py:420,768,980`, ~340 JSON parses/iteration) | prune to newest N per family in the trainer, or write a `latest_<family>.json` pointer |
| NEW: `forge-ranker-eval` memory | 20–34 G peak RSS daily (journal), 5 sequential fits each re-reading the 8.9 G snapshot | `MemoryMax=` + `MemoryHigh=` on the unit; drop the wf_p25 fit; consider one DuckDB read shared across fits |
| NEW: D401 correction | ledger claims load-once-at-start | D-entry retracting it (`main.py:1968/2377`; journal model-id rolls without restart) |

---

## 7. Corrections to earlier plans (so nobody executes a stale row)

1. **August plan** `repo-simplification-2026-08.md`: Steps 0–C, E1–E3, E6 landed. Carried forward
   here: Step D (unit-file comment move → Batch 1), E5 (arm-B → Batch 4), E7 (Q44 write-only tables →
   Batch 4), Step F (post-freeze retirement → Batches 3–5), §4 regrowth rules 1/3/4/6 (not adopted —
   §10). Archive the August plan when Batch 1 lands.
2. **July retirement plan** `fable-audit/code-complete-retirement/REPORT.md`: P0-1 (`forge grammar`) →
   §8 decision, not automatic; P0-2/P1-5/E1 already done (D298/D373/D372); **P1-2 (prereg machinery)
   is now KEEP** — the freeze hook reads `preregistrations.jsonl`; P1-3 (SPRT + eval halves) → §3 #2;
   P2-1 already gone; P2-3 already gone (D235); P2-5 already gone (D301); P2-7 done (D295); P2-9 moot.
   Its §3 KEEP list still holds, with the prereg addition.
3. **D401**: the stale-model finding is false (§0.4).
4. **`tests/README.md` / `CLAUDE.md`**: "~10 monkeypatch files" → 24 (22 import only `app`); the
   phase0 clock scan covers `src/` only.

---

## 8. Ambiguous items needing your decision

Ordered by how much they block.

1. **Contracts pin adoption (blocks all deploys).** `contracts_check.py:258` pins `1.44.0`; installed
   `1.47.0`; `uv.lock` dirty with exactly that line; `forge check` passes (MAJOR-only); the pin test
   is RED; `deploy_preflight.sh` NO-GO; healthcheck WARN 11 days; the trainer logs `reader behind
   contract: pruned unknown field(s) ['prefilter_sample']` on every fit. STATUS 09-06 says the dirty
   lock is yours. Adopt (pin bump + commit `uv.lock` + both-directions restart plan, D245 class) or
   revert the lock.
2. **Proposal machinery + `forge grammar` group** (§4d): hard rule #4 says "structurally enforced";
   the code now emits only tightens, the last four were noise, and under the signed freeze nothing
   can be applied without a prereg. Recommendation: retire `proposer`/`proposal_writer`/
   `trade_concentration` + the CLI group, keep `analyzer.py` and `OPEN_PROPOSALS.md` (QuantIQ parses
   it), and reword hard rule #4 to "grammar changes require a preregistration + operator signature
   (pre-commit `freeze-governance`)". If you keep it: fix REL-8 and add freeze awareness to
   `apply-proposal`/`revert` (they write `grammar.yaml` at runtime with only the commit hook guarding).
3. **`pre_filter_logs` stop-writing** (45.7 M rows; Q44): 0 SQL readers, but QuantIQ's
   `forge_queries.py:17` docstring names the table — confirm with the QuantIQ side first.
4. **`search_multiplicity_census.py` + healthcheck check + daily run**: metric B is signed at 0.0%;
   recommendation: retire (the hook enforces the freeze structurally). Keep only if you want a daily
   "grammar is choking" number.
5. **`blend` branch / `FORGE_QUALITY_RANK_MODE`**: collapsing makes gate-tail the only mode and
   removes the rollback env var. Gate-tail has been live 2+ months. Recommendation: collapse.
6. **Three unused predicate types** (`requires`/`forbids`/`compatibility`): fact is clean (0 uses in
   v55 + 55 archives); it is a grammar-package schema change, so it gets your sign-off.
   Recommendation: delete.
7. **`freeze_tail_reading.py` / `freeze_registered_read.py` + 3 test files**: keep as the §5-reopener
   within-basis read instrument, or archive (git holds them). Recommendation: archive; a reopener
   brings its own prereg and can restore from history.
8. **`grammar revert`**: dead-by-policy; keep only if a runtime grammar rollback (vs `git revert` +
   bump) is a real scenario. Recommendation: retire with item 2.
9. **`forge yield-audit`** (348 LOC + 274 test): cannot act under the freeze. Recommendation: retire.
10. **`~/forge_data/approvals/`**: QuantIQ's dashboard writes approvals Forge never reads. Is a
    reader planned? If not, tell QuantIQ to stop writing.
11. **`forge.db.pre_arm_cleanup_20260731_230544` (6.3 G)**: delete after you confirm the D342 repair
    is closed (5 validated backups exist).
12. **`forge-ranker-eval` memory**: set `MemoryMax=` (what ceiling?), drop the wf_p25 fit, and decide
    whether the rewire streak keeps appending a minimal row for QuantIQ.
13. **`_archive/` relays (133 + 17 files, 1.2 MB)**: `git rm` (history keeps them) vs move the whole
    `_archive/` to a sibling repo. Recommendation: `git rm` the relays, keep ledger slices + resolved
    OQ (tests/docs point at them).
14. **Single config surface** (§3 #7: env → yaml, drop `--no-config`): a live-behaviour change through
    the deploy ritual and unit edit. Worth it? Recommendation: yes, after Batches 3–5, as its own
    D-entry.
15. **`stuck_state`**: permanent-noise WARN under book-level promotion. Retire, or re-key on
    component rate. Recommendation: retire.
16. **`crucible.db_path` direct-DB fallback** (`consumer.py:224-251`): remove the key + path (hard rule
    #2) or keep for fixtures. Recommendation: remove; fixtures inject the export.
17. **`FORGE_REFUTATION_GUARD`**: document in MANPAGE or drop the env var (module stays; it is in the
    determinism hash). Also: the refutations export has not changed since 2026-07-31 — is that expected?
18. **`docs/DESIGN.md` shrink** (883 → ~600): §3.5 bodies untouched; everything else is an
    operator-reviewed diff (hard rule #1 adjacency).
19. **CLAUDE.md worktree rule** (L16-18) vs your single-folder preference: reconcile the text
    (worktree for grammar bumps only).
20. **The equities scope**: Forge has nothing to remove. Do you want the same audit run on
    `~/proj/QuantIQ` (PTS paper runner, 30 crontab jobs, five `QuantIQ-*` worktrees)?
21. **Your second item**: the message said "two things" and listed one.

---

## 9. Impact estimate

| Surface | Now | After (all batches, with §8 recommendations) |
|---|---|---|
| `src/` LOC | 28,563 | ~22,000–24,000 (−4,800 without the operator-gated proposal machinery / config rewrite; −6,500 with) |
| `src/` files | 107 | ~92 |
| `tests/` | 191 files / 46,729 lines / 2,158 tests / 232 s | ~170 files / ~37,000 lines / ~1,950 tests / ~180 s (+7 new gap tests) |
| `scripts/` | 18 | 11 (8 wired/ritual + `search_multiplicity_census` and the two freeze readers if kept) |
| CLI commands (top + sub) | 32 | ~21 (−`feedback`, −`yield-audit`, −`grammar`×5, −`eval-rewire`, −`eval-prior-weight`, −`campaigns audit`; `enumerate`/`prefilter` kept for diagnosis) |
| Healthcheck checks | 17 | 11 |
| Timers / units | 4 + 1 | 4 + 1 (ranker-eval slimmed 9 → 5 sections, memory-capped) |
| Unit-file lines | 249 (27 directives) | ~60 |
| Env vars in the unit | 8 live + 3 commented | 5 (or 3 after §3 #7) |
| Config files | 4 yaml + preregs + archive | 3 yaml (`ranker.yaml` gone) + preregs + archive |
| `docs/` lines | 7,352 | ~4,600 (DESIGN 883→~600, GRAMMAR 402→~200, MANPAGE 816→~650, INDICATOR 180→0, proposals 21→~12 files) |
| Root `.md` | 9 | 7 |
| Session read-path (STATUS + ledger + OQ) | 633 KB | ~280 KB |
| `fable-audit/` + `_archive/` in the read path | 368 KB + 4.1 MB | 0 + ~2.9 MB |
| Docs with wrong facts | 12 files | 0 |
| DB write-only rows | 45.7 M (`pre_filter_logs`) growing per batch | frozen |
| Disk under `~/forge_data` | ~68 G (incl. 6.3 G dead copy, 45 G backups) | ~61 G |
| Dependencies | 8 runtime + 6 dev | unchanged |

**Architecture before:** loop + 12 batch-shaping mechanisms + learned weights, wrapped in three
generations of experiment apparatus (A/B plumbing, flip gates and streak clocks, freeze instruments)
and a composite ranker that is bypassed; four config surfaces; 17 health checks, 6 of them for settled
questions; docs that describe two machines (the designed one and the built one).

**Architecture after:** the same loop and the same twelve mechanisms, one trainer that refreshes the
four models the loop actually loads, one config surface, 11 health checks that each map to a way the
frozen pipeline can fail, a freeze that is enforced by a hook and a watcher, and docs that describe
one machine. Everything that remains is reachable from `forge.service`, a timer, a hook, or a
documented incident ritual.

---

## 10. Batched execution plan

One tranche = one commit (or a few small ones), suite green after each, D-entry per
behaviour-touching batch, STATUS block ≤ ~800 chars. Batches 3+ follow `docs/tasks/deploy.md`
when they touch the daemon: preflight → stop → commit → `daemon-reload` if the unit changed →
start → verify journal. Same-day D-number races have hit three times — grep for your own heading
before and after committing.

### Batch 0 — unblock (operator items, no cleanup)
1. §8.1 contracts pin: bump `FORGE_EXPECTED_CONTRACT_VERSION` to `1.47.0`, commit `uv.lock`, both-directions restart plan; or revert the lock.
2. D-entry retracting D401's stale-model claim (§0.4).
3. Confirm §8 items 2–6 so Batches 4–5 can be cut.
**Verify:** `uv run pytest tests/integration/test_contracts_integration.py` green; `scripts/deploy_preflight.sh` → GO; `forge healthcheck` → OK; journal startup line shows `1.47.0`.

### Batch 1 — records, docs, unit comments, hygiene (zero production risk)
1. Rotate: STATUS blocks 08-01→08-14 → `_archive/STATUS_2026-08.md`; ledger D301–D350 →
   `_archive/IMPLEMENTATION_DECISIONS_D301-D350.md` (fix the four out-of-order headings D302/303,
   D315/316, D329–338, D375/377 while slicing); OQ: sweep Q23/Q34/Q40/Q49/Q62 to
   `_archive/OPEN_QUESTIONS_RESOLVED.md`, banner Q9/Q14/Q29/Q41/Q45/Q47 "MOOT under D390 unless §5
   reopens" (amend `test_phase6_invariants.py:124-127` first if Q9 moves).
2. `git mv` to `_archive/`: the 8 terminal proposals (§4c), `fable-audit/` →
   `_archive/fable-audit-2026-07/`, the two root reviews, `docs/INDICATOR_THRESHOLDS.md`; `git rm`
   `_archive/PROMPT_*` + `CRUCIBLE_*` (§8.13); mark `v39`/`v41` proposals DEPLOYED.
3. Docs truth fixes (§4e table; every row is a one-line edit) incl. the CLAUDE.md line list and the
   "grammar FROZEN at v55; prereg required" banner in CLAUDE.md, HOW-TO, `grammar-change.md`.
4. `deploy/systemd/forge.service`: move the 219 comment lines' history to D-pointers, keep the
   per-variable ⚠️ lines (August Step D); re-symlink the prereg-watch units; `setup_new_box.sh` /
   `NEW_BOX_TRANSFER.md` / `stage_transfer.sh` → four timers, version-agnostic. (`daemon-reload` at
   the next planned restart; no dedicated restart for comments.)
5. Hygiene: `rm -r` orphan `__pycache__`, `.mypy_cache`, root `scratchpad/`; `~/forge_data`:
   archive/delete the retired-programme dirs (§4c), the two dead clocks, `logs/`; the 6.3 G DB copy
   after §8.11.
6. Archive the August plan with a pointer to this file.
**Verify:** `uv run pytest tests/invariants tests/integration/test_cli_help.py` (doc needles);
`uv run pytest` full; `git status` clean; `systemctl --user list-timers` shows 4 Forge timers;
`ls -la ~/.config/systemd/user | grep forge` all symlinks.

### Batch 2 — coverage first (tests only; no src change)
1. The 7 gap tests (§5); fix Q51 (ORDER BY) or delete the assertion.
2. Shared `tests/fixtures/forge_db_rows.py`; mark the 3 perf tests `slow`; move `_v44_registry` into
   the v55 guard.
3. `tests/README.md` corrections.
**Verify:** full suite green; `uv run pytest -m "not slow"` runs in < 3 min; new gap tests fail when
their guarded behaviour is broken (mutate once, observe RED, revert).

### Batch 3 — timer-side retirements (no daemon restart)
1. `daily_ranker_eval.sh`: drop the wf_p25 fit, the eval-robustness print, the vix-share section,
   the campaign-audit section, the per-model cumulative prints; replace the two heredocs with one
   `forge ranker-model eval` call that appends the AUC/calibration row (keep the `streak.jsonl` shape
   QuantIQ reads; §8.12 for the rewire row); add `MemoryMax=`/`MemoryHigh=` to the unit; add
   models-dir retention (REL-12).
2. Retire `eval-rewire`, `eval-prior-weight`, `evaluate_tail_shadow_pooled`, `sequential_test.py`,
   the SPRT half of `status_cmd.py`, `campaign_audit.py` + `campaigns audit`, the 5 healthcheck checks,
   retarget `check_tmp_headroom`.
3. Scripts: MANPAGE retirement-ledger rows + delete `ceiling_record_test`, `joint_frontier`,
   `second_gate_contrast` (+test), `threshold_resolution_value`, `promoted_leg_recall`,
   `production_by_group`, `tail_verified_alignment`; §8.4/§8.7 outcomes for the census and the freeze
   readers.
**Verify:** `systemctl --user start forge-ranker-eval.service` by hand → journal shows 5 sections,
peak RSS < cap (`systemctl --user show -p MemoryPeak`), new artifacts for the 4 loaded families,
one new row in `streak.jsonl`; `forge healthcheck` → OK with 11 checks; `forge status` still prints;
next 05:00 run clean; QuantIQ dashboard still reads the streak file.

### Batch 4 — daemon dead code, byte-identical (deploy ritual)
1. arm-B, orthogonal floor, `_RV_REGIME_WEIGHTS_FROZEN` body + `_load_regime_weights` chain (thread
   `None`; kwarg removal as a separate no-op commit), `rank_batch_with_holdout` pair,
   `write_loosening_proposal`, `active_selection_slots`, `regime_supply`, `stuck_state` (§8.15),
   `promoted_patterns` writer, `pre_filter_logs` writer (after §8.3), `forge feedback`, `blend` branch
   (§8.5); unit env line(s) removed; tests retire in the same commits.
2. REL-1/REL-2 explicit logging; REL-4 SIGTERM handler; REL-5 fail-loud universe (each its own commit).
**Verify (the byte-identity proof):** before stopping, capture one iteration's `enumeration_inputs_hash`,
`registry_hash`, and the ranked/lane `config_hash` list for the current seed from the journal + a DB
snapshot; after restart, the first UNBLOCKED iteration must show identical `enumeration_inputs_hash`
for the same `(grammar_version=v55, registry_hash, seed)`; goldens green (`tests/unit/test_enumeration`,
`tests/integration/test_batch_reproducibility.py`); journal lines `tail_lane: 95 of 200`,
`trend_lane: 40 of 200`, `exploration_holdout: 10 of 200`, `arm_floor`, `cell_floor`,
`refutation_guard: active`, `search_n_trials: stamped` all present; NO `generation_arm_ab:` /
`regime_weights:` lines; `forge_funnel.json` still written; `NRestarts=0` after 1 h; `forge healthcheck`
OK; Crucible morning digest still parses (`loop iteration`, `sampler_attempts:`, `phase_timings:` unchanged).

### Batch 5 — operator-gated retirements (deploy ritual)
1. §6.2 composite scorer + `ranker.yaml` + `hygiene_score` (after Batch 3).
2. Three unused predicate types (§8.6).
3. Proposal machinery + `forge grammar` group + `auto_tune` key/loader + `crucible.db_path` fallback
   (§8.2/8.8/8.16); hard rule #4 wording; re-cut `test_phase5_invariants.py` and
   `test_phase6_invariants.py:147-152`.
4. `forge yield-audit` (§8.9).
**Verify:** as Batch 4, plus: `load_grammar` parses v55 and `_verify_archive_consistency` passes;
`OPEN_PROPOSALS.md` unchanged and QuantIQ `list-proposals` still parses it; `grammar_versions` audit
row still written at startup; `forge check` green.

### Batch 6 — structural simplification (refactors; versionless deploys where noted)
1. Parse-once + table-driven loaders + `cli/knobs.py` (§3 #1) — golden-test that every weight family
   line in the journal is byte-identical before/after.
2. Shared helpers (§3 #9); grammar-package file merge (§3 #11).
3. `Lane` table (§3 #8) — golden a fixed batch's tags/ranks.
4. Single config surface (§3 #7, §8.14) — D-entry; unit edit + `daemon-reload`.
5. Sampler shims one per commit, goldens as the accept gate (§3 #10).
6. Test consolidation (version-guard merge, parametrize, `test_run_loop` split).
**Verify:** full suite; goldens; the Batch 4 journal checklist; suite time ≈ 180 s.

### Batch 7 — regrowth rules (adopt, don't remember)
Sweep-on-land in the resolving commit; STATUS block ≤ ~800 chars; ledger rotation at 400 KB;
scripts die with their D-entry; monthly root/`docs/proposals/` sweep + ledger-size check on the
standing review agenda. Add a `tests/invariants` check that `STATUS.md` < 150 KB and the ledger
< 450 KB so the rule is checked, not remembered.

---

## 11. Verification checklist (run at every batch boundary)

```bash
uv run ruff check src tests scripts
uv run mypy --strict src
uv run pytest                                   # full; uncontended for daemon batches (service stopped)
uv run pytest tests/unit/test_enumeration tests/integration/test_batch_reproducibility.py   # goldens / hard rule #6
uv run pytest tests/invariants                  # hard rules + doc needles
scripts/deploy_preflight.sh                     # GO before any restart
git status --short                              # clean at every stopping point
```

After a daemon restart (Batches 4–6):

```bash
journalctl --user -u forge.service -n 80 --no-pager      # contracts line, grammar_version=v55, registry_loaded_from_export, reconcile, no traceback
systemctl --user show forge.service -p NRestarts -p Environment
uv run forge check && uv run forge healthcheck            # OK
systemctl --user list-timers --all | grep forge           # 4 timers armed
ls -la ~/forge_data/exports/forge_funnel.json             # rewritten this iteration
```

Behaviour invariants to compare before/after on the first unblocked iteration: `enumeration_inputs_hash`
for the same `(v55, registry_hash, seed)`; the lane/floor journal lines listed in Batch 4; submission
mix per `selection_mode` (`ranked` 55, `tail_lane` 95, `trend_lane` 40, `holdout` 10, `prefilter_sample`
40); `search_n_trials: stamped`; `weights` phase time (expect ~18 s → ~2 s after Batch 6.1); no new
`inbox/errors`. Cross-system: Crucible `crucible funnel --compare v55 v55` still runs; QuantIQ
dashboard reads `streak.jsonl`, `OPEN_PROPOSALS.md`, `forge.db` `submissions` unchanged.

---

## 12. Final state — Route C, automated (decided 2026-09-13)

**Operator's brief:** Forge becomes an on-demand challenger tool, not a 24/7 generator. Generating
strategies that are duplicative of the champion or that cannot threaten it is wasted compute
(mostly Crucible's). Running it must be easy and automated; the operator supplies no input.

### 12.1 What the evidence says Forge is for now

- Both promotions came through directed cells, not the broad sweep; Crucible's un-consumed
  above-floor supply is 3; their quality lane finds 0–3 eligible per pass (D393). The sweep is spent.
- The champion is machine-readable: `designation_history*.json` names the book QuantIQ trades —
  **`7f2a697ec6c1b119`, designated 2026-08-06, 6 legs (4 trend, 2 MR)**. (The 2026-08-02 file that
  named `f52a05c8` was a hand-run one-off; Crucible's 09-13 answer republished it and armed a daily
  07:00 PT publisher — nothing in Forge code had read the old file.) Eleven promoted books
  (08-04 → 08-08) span ~11 distinct (directional, regime) cells. `component_contributions*.json`
  carries per-leg `marginal_sharpe` + `correlation_to_incumbent` (18 rows; 6 filed under the
  designated book) but is **FROZEN at assembly** (recomputed from stored ledgers only) and a config in
  several books carries the last-iterated book's score — filter on `portfolio_id == designated`, treat
  other-book legs as unknown. No live or paper per-leg performance is published, none planned
  (paper P&L is QuantIQ's). All three are
  readable through blessed contracts helpers (`load_promoted_portfolios_from_export`,
  `load_component_contributions_from_export`); nothing in `src/` reads the last two yet. The census
  script already derives "protected cells" from the book (`search_multiplicity_census.py:130-152`).
- Standing obligations that bound the design: decorrelation is owned at assembly (D186/D187);
  never tune generation against `IC(cpcv, corr_to_book)` (freeze §6). So "duplicative" must be
  **structural** (same cell as a book leg; Jaccard signal-key overlap), never their corr label.
  "Threatening" must rest on **realized cell evidence** (Crucible verdicts), never on Forge's
  predictions alone (F3 AUC is modest; the tail model's OOS fit is weak).
- Enumeration is cheap (100k configs < 300 s, `test_phase2_invariants.py:353`); the expensive
  parts are Crucible's feature fetch and backtests. Cell targeting by **rejection sampling over the
  unchanged v55 population** keeps hard rule #6 and the signed freeze intact — the population does
  not change, only which members are submitted (the D287 selection-floor precedent, versionless).

### 12.2 The operator's experience

Nothing weekly. `forge-campaign.timer` fires once a week. The run decides on its own whether there
is anything worth generating; most weeks it will find nothing and say so in one journal block. The
only page is a **failed systemd unit** (boot check, contracts drift, export missing) — no
`SuccessExitStatus`, so every problem surfaces. When curious: `forge campaign status` (last runs,
what was submitted, what came back). After a box move: `deploy/setup_new_box.sh` (two timers).
Operator-owned knobs live in `config/forge.yaml` `campaign:` with defaults; none are required.

### 12.3 `forge campaign` — one command, no arguments

```
forge campaign             # the weekly run (also what the timer executes)
forge campaign --dry-run   # same decision path, submits nothing, prints the plan
forge campaign status      # last N run records + verdict outcomes of their submissions
```

Run steps, all deterministic given the export watermarks recorded in the run record:

0. **Boot checks** (any failure → exit 2, nothing submitted): contracts pin; grammar v55 + archive
   hash; registry snapshot ≤ 7 d old; universe + gated + failed exports present; inbox backlog below
   a ceiling (the §7.3 depth cap survives only as this guard); open preregistrations not DUE
   (absorbs `forge-prereg-watch`).
1. **Reconcile**: consume gated/failed exports for prior campaign submissions (existing consumer,
   aged-out flush); write verdict rows; update the derived campaign table (status per cell:
   discover → farming → converted / retired — a table in `forge.db`, no longer code).
   **Blocking fact (Crucible 09-13 §4.1, measured here 09-14):** `gated_runs_*.json` is the newest
   10,000 decisions across ALL sources — one file spans ~14 h and the 60 retained files reach ~24 h
   (Crucible refits alone decide ~5k/day). A weekly boot reconcile sees none of last week's verdicts.
   Resolution = a **forge-scoped, 14-day gated stream** (`source='forge'`) beside the existing one,
   loader-first in contracts then emission (Crucible's option 2) — **LIVE 2026-09-14** (contracts
   1.48.0 `load_forge_gated_runs_from_export`, glob `forge_gated_runs_*`; wired D412, truncated
   windows skip the aged-out flush) — the weekly run must boot cold after
   any outage and still see two full weeks; a poller (their option 1) is a second moving part whose
   failure is a silent label gap. `failed_runs` already looks back 14 days (their `5b3aa42`, live,
   verified `lookback_days: 14`). Until the stream ships the daemon reconciles per iteration, so the
   dry-run weeks are unaffected; cutover waits on it.
2. **Read the book**: designated champion + all promoted portfolios → PROTECTED cells (5-tuple key:
   hypothesis, dte_bucket, axis, directional, regime) + per-leg `marginal_sharpe` /
   `correlation_to_incumbent` + the designation stamp.
3. **Evaluate triggers** (priority order; each names cells + a budget):

| Trigger | Fires when | Campaign | Default budget |
|---|---|---|---|
| T1 leg health | the designated `portfolio_id` flips in `designation_history` (daily 07:00 PT). **Not** `marginal_sharpe` decay — the contributions export is frozen at assembly (Crucible 09-13 §1); a live per-leg signal would have to come from QuantIQ (Route D, none planned) | REPLACEMENT: the legs the new book dropped → their cells + neighbours (same hypothesis; adjacent dte bucket; sibling directional ids) | 200 |
| T2 refutation retraction | an effect present in the previous `refutations` file is absent from a NEW file (content-diff; the export publishes on content change only — hash-deduped, checked daily 07:00 PT — so never key on file age) | RELEASE: the released cell | 100 |
| T3 registry change | a new indicator **id** within an existing grammar family appears in the registry snapshot | EXPLORE: cells containing it | 100 |
| T3' new family | a new indicator **family** appears | no campaign; journal "reopener 2 candidate" (a family needs a grammar bump + prereg) | 0 |
| T4 basis refresh | a non-protected, non-dead cell whose newest verdict is > 90 d old and whose best historical `cpcv_p25` ≥ 1.2 (near the 1.5 floor); the chain basis moved three times since 07-17 (D404/D405) so old evidence goes stale | REFRESH: ≤ 2 such cells per run | 50 each |
| T5 exploration floor | always | never-sampled ("dark") cells, deterministic rotation by `(cell_key, ISO week)`; Q45's standing triage loop | 10% of the run, min 20 |
| none | — | dry enumeration of 200 (the boot test), submit 0, journal "no trigger; boot OK" | 0 |

   Hard cap: **400 submissions per run, one run per week** (today ≈ 80,000/week → ≥ 200× cut).
4. **Generate for the chosen cells**: run the unchanged v55 sampler with `seed =
   hash(grammar_version, registry_hash, ISO week)`; keep members of the target cells (rejection
   sampling); prefilter battery (the existing 9 filters); **challenger gate**: drop any candidate in
   a PROTECTED cell unless this is a T1 REPLACEMENT for that cell; drop candidates with Jaccard
   signal-key similarity ≥ 0.85 to any book leg (existing `_signal_keys`); drop candidates in DEAD
   cells (the `yield_audit` rule: ≥ 1,000 decided and 0 converting, or < 0.25× the hypothesis
   baseline). Rank in-cell by F3 `P(component)` then `tail_norm` (models retrained at run start
   from `forge.db` — seconds; no daemon lock → no snapshot → the 20–34 GB trainer problem
   disappears). Submit ≤ budget; stamp `selection_mode = campaign:<trigger>:<cell>`; `search_n_trials`
   stamp unchanged.
5. **Report**: one journal block + `~/forge_data/campaigns/<run_id>.json` (triggers evaluated with
   their inputs, cells chosen, n submitted, export watermarks) — replayable; **publish its schema to
   Crucible** (their morning digest will read it once it exists). Keep `forge_funnel.json` in its
   aggregate `per_grammar_version` shape (their loader raises `ForgeFunnelError` on any other shape;
   an absent file degrades) — the run updates the same aggregate, per-run detail lives in the run
   record. `selection_arm` stays `ranked` (their §3): the relayed cutover instant is the boundary
   between ranker-selected and campaign-sampled `ranked` rows — no contracts change.
   **Weekday: Sunday 03:00 UTC** (Saturday 20:00 PT) — their Monday 06:00 PT generation census reads
   cohorts ≥ 14 days old, so a Sunday cohort is 15 days old at the first census that can include it
   and its stage-one verdicts (1–3 days) are long done; proposed to Crucible for confirmation.

What automation can and cannot judge, stated plainly: Forge stops sending what cannot matter
(duplicates of the book, dead cells, cells with no trigger). It does **not** claim to know which
challenger will beat a leg — Crucible's gates and assembly remain the arbiter, and a REPLACEMENT
campaign is a supply of candidates, not a verdict.

### 12.4 What remains (the final repo)

| Area | Keeps | Goes |
|---|---|---|
| Entry points | `forge campaign` (+ `status`, `--dry-run`), `check`, `version`, `enumerate`, `prefilter` (diagnosis), `prereg` (freeze hook data) | `run --loop`, `feedback`, `healthcheck`, `status` (SPRT), `yield-audit`, `campaigns` (registry becomes a table), `grammar` group, `ranker-model` group (train is internal to the run), `check-activations` (folded into boot checks) |
| Timers | `forge-campaign.timer` (weekly), `forge-backup.timer` (weekly, after the run) | `forge-healthcheck`, `forge-ranker-eval`, `forge-prereg-watch` (absorbed) |
| Hooks | `grammar-version-bump`, `grammar-doc-sync`, `freeze-governance`, ruff/mypy/hygiene | — |
| `src/` | `enumeration/` (v55 sampler unchanged; dead shims out), `grammar/` (minus 3 unused predicate types, §8.6), `prefilters/` (9 filters), `ranking/{features,dataset,model,queue-in-cell,diversifier,signal_key}`, `feedback/{consumer,verdicts side,rejection_weights posterior core as the cell scorer}`, `submission/{submitter,batch,search_multiplicity}`, `persistence/`, `core/`, `config/` (single `forge.yaml`), `funnel/` (per-run), **new `campaign/` (~900 LOC: triggers, cells, gate, run, report)** | the loop + lanes + §7.3 limiter, 9 learned-weight loaders (posteriors stay), `regime_supply`, `stuck_state`, `promoted_patterns`, `pre_filter_logger`, `shadow` (keep only per-submission features for retraining), `proposer`/`proposal_writer`/`trade_concentration`/`analyzer`, `calibration` Platt/`drift`/`sequential_test`/`evaluation`, `campaign_audit`, `arm_floor`/`cell_floor` (the campaign is the floor), `book_usable_weights`, `activation_smoke` (folded), `healthcheck_cmd` |
| `scripts/` | `backup_forge_db.sh`, `deploy_preflight.sh`, the 3 hooks, `live_db_snapshot.sh` (reads during a run) | everything else (§4c) |
| Config | `forge.yaml` (+ `campaign:` section), `grammar.yaml` + archive, `preregistrations.jsonl`, `auto_tightened_thresholds.yaml` (fingerprint) | `ranker.yaml`, `prefilter.yaml` `auto_tune:`, the unit env stanza |
| Docs | DESIGN (shrunk, + "final state" banner), GRAMMAR (~200), MANPAGE (~250), HOW-TO (campaign + cold start), architecture (rewritten to this table), `tasks/{deploy,quality-gates,crucible-handoff,grammar-change (reopener ritual)}` | `feedback-change.md`, `investigate-live.md` (merge the eras table into HOW-TO), INDICATOR_THRESHOLDS, all terminal proposals |
| External interfaces | Crucible inbox (`submit_candidate`), gated (forge-scoped 14-day stream once it ships) / failed / registry / universe / refutations / `promoted_portfolios` / `designation_history` / `component_contributions` / `chain_inception_floors` / `earnings_covered_symbols` exports (read), `forge_funnel.json` aggregate (write, shape kept), run records `~/forge_data/campaigns/*.json` (write, schema published), `OPEN_PROPOSALS.md` as a static file | `promoted_strategies` (RETIRING on Crucible's side, 09-13 — the prior-promotion-proximity read at `main.py:1549` has returned `[]` since 07-06, verified: 0 rows in 90 d; drop the read + `prior_promotion.py` in Batch 5); journal-line regex contract with `crucible-morning-digest` (goes silent gracefully); `streak.jsonl`/`rewire_streak_wfp25.jsonl` for QuantIQ (replaced by the run record) |

Size estimate: `src/` ≈ 17k LOC / ~85 files (from 28.5k / 107); tests ≈ 30k lines; CLI ≈ 9
commands; timers 2; scripts 6. Hard rules #1–#10 all still hold; #4's wording changes to "grammar
changes require a preregistration + operator signature (pre-commit `freeze-governance`)".

### 12.5 Cross-system notice (before cutover, via `freeze/relays/`) — SENT 2026-09-13 (`480fe72`); ANSWERED same day (Crucible `5b3aa42`): §1 contributions frozen → T1 = designation flips; §2 no live drift; §3 stamp `ranked` + relay the cutover instant; §4 no timer assumes a daily stream, but **§4.1 blocks cutover** (gated window ~24 h — forge-scoped 14-day stream requested); §4.2 `failed_runs` 14-day lookback live; §5 `promoted_strategies` retiring (ACK), `designation_history` was never published (fixed, daily), `refutations` content-change only; §6 digest goes quiet, keep the funnel shape. Reply relay 2026-09-14.

To Crucible: (1) Forge volume goes from ~11k/day to ≤ 400/week, bursty, starting <date>; keep the
inbox watcher + gated/failed/registry/universe publishers (all cheap); (2) `selection_mode` gains
`campaign:*` values; (3) their morning digest's Forge regexes will stop matching — read the run
record instead or drop the section; (4) ask: confirm `component_contributions` semantics as a leg
health signal, and whether they will publish live leg drift (Route D upgrade) — otherwise T1 rests
on assembly-time marginals and designation flips only; (5) under-supply is their stated failure
mode: this is a deliberate stop, not an outage. To QuantIQ: the two streak files stop; dashboard
reads `~/forge_data/campaigns/*.json`; `OPEN_PROPOSALS.md` stays parseable and static.

### 12.6 Remapped batches (replace §10 Batches 3–6)

- **Batch 0, 1, 2** — as written in §10. Batch 2 shrinks to the gap tests that still matter:
  SIGTERM mid-submit (REL-4), explicit export-outage logging (REL-1/2), snapshot + preflight
  subprocess tests; the hot-grammar, model-reload and daily-eval tests are moot.
- **Batch 3 — BUILT 2026-09-14 (D410; `96b8ab5`→`2211d47`); dry-run weeks AUTOMATED by `forge-campaign.timer` in dry-run mode (D411).** Originally: build `forge campaign` beside the daemon (TDD, no daemon change). `campaign/`
  package: `cells.py` (protected / dead / dark from exports + `forge.db`), `triggers.py` (T1–T5,
  pure functions of export contents), `gate.py` (challenger gate), `run.py` (steps 0–5),
  `report.py`. Run records + `status`. Two hand-run `--dry-run` weeks: compare its chosen cells with
  what the daemon actually submitted and with Crucible's verdicts; tune the defaults once.
  D-entry. Send the §12.5 relays.
- **Batch 4 — DONE: cutover RAN 2026-09-14T23:52:05Z (D416; planned 07:00Z, moved earlier on Crucible's
  written waiver). `forge.service` disabled; `forge campaign` live; first live run no_trigger / 0 submitted.
  ranker-eval and prereg-watch stay until Batch 5 (deviation, for cause).**
  Originally: stop `forge.service`; disable `forge-healthcheck`,
  `forge-ranker-eval`, `forge-prereg-watch`; flip `forge-campaign.service`'s
  `FORGE_CAMPAIGN_MODE` from `dry-run` to `live` + `daemon-reload` (the timer is already installed,
  D411; the wrapper refuses `live` while the daemon runs); re-time backup after it; first live run by
  hand; then leave it to the timer.
  **Verify:** journal block shows boot OK + triggers + n ≤ 400; `~/forge_data/campaigns/<run>.json`
  written and replayable (`--dry-run` on the same watermarks reproduces the plan); Crucible's next
  gated export contains `campaign:*` rows; no `inbox/errors`; backup timer fires after the run;
  `systemctl --user list-timers` shows exactly 2 Forge timers; break the contracts pin once in
  `--dry-run` and confirm the unit goes **failed** (the paging path works).
- **Batch 5 — remove the daemon era (deploy ritual; one D-entry per group).** Everything in §12.4's
  "Goes" column that the campaign path does not import, plus §4a–4d rows, plus the scripts (§4c),
  plus the operator-gated items already decided (§8.2 proposal machinery, §8.6 predicate types).
  Tests retire with their code; the version-retirement guards and goldens stay.
  **Verify:** goldens green (the v55 population is untouched — `test_enumeration_byte_identical…`,
  `test_batch_reproducibility.py`); a `--dry-run` before and after produces the identical plan for
  the same watermarks; full suite; ruff; mypy; `forge check`.
- **Batch 6 — consolidate.** Single config surface (`forge.yaml` only); shared helpers (§3 #9);
  test consolidation (§5); `architecture.md` rewritten to §12.4; DESIGN "final state" banner;
  MANPAGE to the 9 commands; HOW-TO = weekly run, `status`, cold start, reopener ritual.
- **Batch 7** — regrowth rules (§10), plus one invariant: `forge campaign --dry-run` must succeed
  in the test suite against the fixture registry (so the path can never rot silently).

### 12.7 Decisions folded into defaults (change in `forge.yaml`, not by asking)

Weekly cadence (Sunday 03:00 UTC); cap 400/run; T1 threshold 0.25× first-recorded `marginal_sharpe`;
T4 staleness 90 d and near-floor 1.2; T5 share 10% (min 20); Jaccard duplicate threshold 0.85; dead-cell
rule as `yield_audit` (≥ 1,000 decided, 0 converting, or < 0.25× baseline). All recorded per run so a
later reader knows which defaults produced which plan.

---

## 13. Batch 5 — removal checklist (prepared 2026-09-14, executes after the cutover fires)

**Ground truth used:** an AST dependency map over `src/forge` (2026-09-14): the campaign path imports
five helpers from `cli/main.py` and one-off constants from four doomed modules; every other survivor
dependency is already in a module that stays. The Batch 5 PREP commit moves those into permanent homes
and adds `tests/invariants/test_batch5_prep_seams.py` (the campaign imports nothing from the doomed
modules) so every deletion below is import-safe by construction.

**Survivors the map forces us to KEEP (corrections to §12.4):** `ranking/types.py` keeps
`RankedCandidate` (submitter, `search_multiplicity`, the campaign); `ranking/shadow.py` stays
(retraining data); `ranking/{features,dataset,model,signal_key}.py`; `feedback/{consumer,
preregistration,trade_rate_priors,eras}.py`; `persistence/*`; `submission/{submitter,batch,
search_multiplicity}.py`; `prefilters/*` minus `activation_smoke`; `enumeration/*` incl.
`_demo_registry` (fixtures); `grammar/*` minus the three unused predicate types.

**Order (one D-entry per group; full suite + `forge campaign --dry-run` plan-identity after each;
the `ranked`/campaign timer untouched; no daemon exists to restart):**

| # | Group | Removes | Notes / verification |
|---|---|---|---|
| G0 **DONE 09-15 (D417; `ddcbfc8`, `1e87329`)** | fold the last two timers into the run | `scripts/daily_ranker_eval.sh` + `forge-ranker-eval.{service,timer}` (train verdict + robustness cpcv + tail ×2 move INTO `campaign/run.py` step 0.5, from `forge.db` directly — no snapshot, no 20–34 GB peak; keep newest N artifacts per family = REL-12); `scripts/freeze_read_watcher.py` + `forge-prereg-watch.{service,timer}` (the DUE judge moves into the campaign boot check: an open prereg past its clock = boot FAIL); `forge-backup.timer` re-timed Sunday 04:00 UTC (after the run); `forge-cutover.{service,timer}`, `scripts/{cutover_campaign,arm_cutover}.sh` (done their job) | Verify: `systemctl --user list-timers` = `forge-campaign` + `forge-backup` only; a hand `forge campaign --dry-run` shows the 4 trained artifacts + the prereg check line |
| G1 **DONE 09-15 (D418; `124b002`, `fd112fc`)** | the daemon loop + its CLI | `cli/main.py` shrinks to the Typer app + `check`/`version`/`enumerate`/`prefilter` (the loop, `cmd_run`, the 9 weight loaders, 8 env resolvers, formatters, `_run_one_iteration` go); `cli/{feedback,healthcheck,status,grammar,yield_audit,campaigns,ranker_model}_cmd.py`; `deploy/systemd/{forge,forge-healthcheck}.{service,timer}`; `scripts/deploy_preflight.sh` keeps but loses the daemon steps | Tests: the 24 `main`-importing files re-target `app`; `test_run_loop`, `test_cli_run`, `test_healthcheck`, `test_status`, `test_grammar_cmd`, `test_feedback_cmd`, `test_ranker_model_cmd`, `test_generation_arm_flag`, `test_cell_floor_flag`, `test_config_threading` (resolvers), `test_enumeration_inputs_reach_the_battery` (re-target to `campaign/run.py`), `test_sigterm_handler` + `test_export_outage_signal` (REL-1 moot → delete; REL-4 re-targets the campaign, see G6) |
| G2 **DONE 09-15 (D419; `3feab56`, `61b1a67`; `yield_audit` folded in)** | ranking, daemon era | `queue.py`, `diversifier.py`, `arm_floor.py`, `cell_floor.py`, `scorer.py`, `config.py`, `prior_promotion.py`, `calibration.py`, `drift.py`, `sequential_test.py`, `evaluation.py`, `campaign_audit.py`, `campaigns.py` (registry; `config_cell` lives in `campaign/cells.py` after prep), `regime_supply.py`; `config/ranker.yaml`; `ranking/types.py` trimmed to `RankedCandidate` | Tests: `test_queue`, `test_diversifier`, `test_arm_floor`, `test_cell_floor`, `test_scorer`, `test_config`, `test_types` (partial), `test_prior_promotion`, `test_calibration`, `test_drift`, `test_sequential_test`, `test_evaluation`, `test_campaign_audit`, `test_campaigns`, `test_regime_supply`, `test_tail_lane`, `test_shadow` (keep), `test_learned_ranker_invariants` (re-target) |
| G3 **DONE 09-15 (D420; `5c44190`, `1671bf1`, `556d86f`)** | feedback, daemon era | `analyzer.py`, `proposer.py`, `proposal_writer.py`, `trade_concentration.py`, `stuck_state.py`, `promoted_patterns.py`, `book_usable_weights.py`, `rejection_weights.py` (1,170 LOC — the era cuts moved to `eras.py`), `yield_audit.py` (`CONVERTING_DECISIONS` moved to `persistence/verdicts.py`), `types.py` trimmed to what `consumer` uses; `OPEN_PROPOSALS.md` stays as a STATIC machine-parsed file | CLAUDE.md hard rule #4 reworded ("grammar changes require a preregistration + operator signature — pre-commit `freeze-governance`"); `test_phase5_invariants.py` HR#4 structure tests re-cut; `test_phase6_invariants.py:147-152` (`grammar_cmd` needle) removed |
| G4 **DONE 09-15 (D421; `5b20d8a`, `4ec5ce7`, `9dcea1a`; `record_prefilter_rejections` kept for the funnel contract)** | submission / prefilters / grammar | `submission/rate_limiter.py` (+ `__init__` export; `test_rate_limiter*`, `test_inflight_depth_invariants`, `test_stall_guard_invariants`); `submission/pre_filter_logger.py` + the `record_prefilter_rejections` call in `submitter.py` (Q44: 45.7 M write-only rows stop; DDL stays); `prefilters/activation_smoke.py`; the three unused predicate types (`grammar/models.py`, `predicates.py`, `test_predicates_requires_forbids`, `test_predicates_compatibility`) | Goldens + `test_batch_reproducibility` prove the population unchanged; `load_grammar` parses v55 and the archive check passes |
| G5 | config surface | `_RUN_DEFAULT_*` + the daemon's `--no-config` (gone with G1); `prefilter.yaml` `auto_tune:` key + `AutoTuneCalibration` + `write_calibration_yaml`; `forge.yaml` `crucible.db_path` + `consumer._fetch_crucible_runs`'s direct-DuckDB fallback (the campaign reads the forge stream; fixtures inject runs); unit env stanza already gone with `forge.service` | `test_config_threading` rewrite; `campaign_config` tests stay |
| G6 | reliability fixes still relevant | REL-4: `submitter.py` writes the inbox file AFTER the DB commit (or records the hash first) + a SIGTERM handler on the campaign oneshot; `test_sigterm_handler` re-targeted and un-xfailed. REL-5: `sampler.py:511-581` universe fallback → fail loud (a sampler-module edit that touches no draw path; goldens prove it). REL-12: done in G0. REL-1/REL-2 tests deleted with their subjects | Suite: 0 xfails remaining |
| G7 | scripts + docs + records | Scripts: retire `search_multiplicity_census.py` (§8.4), `freeze_tail_reading.py` + `freeze_registered_read.py` + their 3 test files (§8.7, archive), `tail_verified_alignment.py`, `production_by_group.py`, `promoted_leg_recall.py`, `threshold_resolution_value.py`, `ceiling_record_test.py`, `joint_frontier.py`, `second_gate_contrast.py` (+test) — MANPAGE retirement-ledger rows. Docs: `architecture.md` rewritten to §12.4's table; MANPAGE to the ~9 commands; HOW-TO = Monday check, `status`, cold start, reopener ritual; CLAUDE.md pitfalls about the limiter/daemon dropped; `tests/README.md`; `deploy/NEW_BOX_TRANSFER.md` + `setup_new_box.sh` to two timers; `docs/tasks/deploy.md` → "the campaign unit" ritual; D-entry per group; STATUS ≤ 800 chars each | `test_cli_help`, `test_phase6_invariants` doc needles; `_archive/` sweep in the same commits (sweep-on-land) |

**Expected end state (re-estimate after prep):** `src/` ≈ 17k LOC / ~80 files; tests ≈ 30k lines;
scripts 6 (`backup_forge_db.sh`, `live_db_snapshot.sh`, `campaign_run.sh`, `deploy_preflight.sh`,
`check_grammar_version_bump.py`, `check_grammar_doc_sync.py`, `check_freeze_governance.py` = 7);
CLI = `campaign` (+`status`), `check`, `version`, `enumerate`, `prefilter`, `prereg` (3); timers 2;
env flags 0 (the mode line is the unit's, not an env knob of the code); config files `forge.yaml`,
`grammar.yaml` + archive, `preregistrations.jsonl`, `auto_tightened_thresholds.yaml`.
