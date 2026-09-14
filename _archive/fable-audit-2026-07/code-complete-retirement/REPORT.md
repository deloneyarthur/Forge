# Code-complete retirement plan — prioritized candidates

> **⚠️ CONDITIONAL PLAN — trigger NOT met.** This is the answer to the operator's hypothetical
> (2026-07-06): *"If I were going to close Forge and Crucible pipelines as code complete, what
> would we retire, in what order?"* The roadmap is NOT there: the v23 trend-grammar branch is
> deploy-ready, `FORGE_EXPLORATION_HOLDOUT_FRAC` is teed up, the gate-tail post-flip cohort
> (prereg `9063b405`) is accruing, and the D243 F1/F3 contract obligations wait behind ve-supply.
> **Nothing in this document is executable until the operator declares the freeze (§0).**
> Written by the session that produced D248 (dead-weight sweep) and D253 (services audit); every
> claim about "who consumes what" traces to those audits' evidence.

## 0. What "code complete" must mean before any of this fires

The assumption throughout: **the pipeline keeps producing** — daemon, feedback learning inside
the frozen grammar, model refresh, monitoring, backup all continue. "Code complete" = the
*evolution* machinery stops: no grammar changes ever again, no new levers, no flips, no research
arms, no contract growth. (Full decommission is a different, trivial list: everything goes.)

Preconditions — all operator declarations, none inferable from code:

1. **Grammar frozen permanently** — v23 branch either deployed-then-frozen or abandoned; §3.5
   rules final; no Path C ever.
2. **All in-flight decisions resolved** — prereg `9063b405` (gate-tail post-flip) read out;
   `FORGE_EXPLORATION_HOLDOUT_FRAC` flipped-or-declined; the D243 forward obligations
   (failure-buckets migration, freeze ledger, mechanism/regime vocab) shipped-or-voided.
3. **Contracts frozen** — Crucible agrees no further minor bumps (else the adoption machinery
   in §3-KEEP stays).
4. Each tranche below is an **operator-gated D-entry** of its own; tests retire with their code;
   the suite stays green after every tranche.

## 1. Priority logic

Ordered by (steady-state value ≈ zero) × (removal risk low) × (weight reclaimed). P0 has no
production role the day the freeze lands; P1 becomes dead the moment its pending decision
resolves; P2 is dormant-lever and dead-branch cleanup; P3 has residual incident-diagnosis value
and is optional. §3 is the explicit KEEP list — the line past which retirement becomes breakage.

Line counts measured 2026-07-06 (src + dedicated tests).

## 2. The prioritized list

### P0 — grammar-change machinery (dead the day the freeze is declared)

The largest coherent block: everything that exists to *change* the grammar or its thresholds.
The grammar loader, validator, and the frozen `grammar.yaml` itself all stay (§3).

| # | Item | Where | Size | Notes |
|---|---|---|---|---|
| P0-1 | `forge grammar` command group (list/approve/reject/apply-proposal, revert, tighten) | `src/forge/cli/grammar_cmd.py` | 422 + 565 test | The whole proposal lifecycle. `revert` (D040) is disaster-recovery for grammar *deploys* — no deploys, no revert target. |
| P0-2 | Threshold-tightening proposer | `src/forge/feedback/threshold_proposer.py` + `scripts/propose_threshold_tightenings.py` | 328 + 177 + 276 test | The quoted "next retirement candidate." Dormant since D206 already; kept today only as a staged lever. |
| P0-3 | Auto-tune apply path | `src/forge/feedback/auto_tune.py` + `prefilter.auto_tune` schema keys + `config/auto_tightened_thresholds.yaml` | 307 + 604 test | Already `enabled: false` (D206/D218). Retire the module, the config keys, and the (emptied) yaml + its loader read. |
| P0-4 | Grammar-v3 predicate types | `src/forge/grammar/` (the predicates no v22 rule uses) | small | Built for future grammar versions that will never exist. Verify per-predicate against `grammar.yaml` before cutting. |
| P0-5 | Change-ritual docs | `docs/tasks/grammar-change.md`, `docs/tasks/feedback-change.md` | docs | Archive with banners, don't delete — they explain the D-history. |
| P0-6 | `OPEN_PROPOSALS.md` / `OPEN_QUESTIONS.md` flows | repo root | docs | Freeze-banner both; the daemon's proposal WRITER stays (§3 — hard-rule #4 mechanism + a choking-grammar signal). |

**Not in P0 despite appearances:** the pre-commit hooks (`check_grammar_version_bump.py`,
`check_grammar_doc_sync.py`) — they are the tripwire against *accidental* grammar edits, which a
freeze makes more valuable, not less. KEEP (§3).

### P1 — experiment/flip decision apparatus (dead once its pending decision resolves)

Each item is load-bearing for exactly one open decision today. Retire in the order the
decisions close; do not front-run them.

| # | Item | Where | Size | Blocked on |
|---|---|---|---|---|
| P1-1 | Shadow-null harness | `src/forge/prefilters/shadow_null.py` + `cli/shadow_null_cmd.py` | 239 + 295 + 92 test | Nothing — its flips are done (D238/D239) or dropped (D235). Retirable **now** even without the freeze; listed here for completeness. |
| P1-2 | Preregistration machinery | `src/forge/feedback/preregistration.py` + `cli/prereg_cmd.py` + `config/preregistrations.jsonl` (7 records) | 192 + 122 + 122 test | `9063b405` resolving. The jsonl archives as a record; the register/resolve code retires. |
| P1-3 | SPRT flip gate + streak clocks | `src/forge/ranking/sequential_test.py` + the eval/eval-robustness halves of `scripts/daily_ranker_eval.sh` + `~/forge_data/ranker_eval/*.jsonl` clocks | 125 + 97 test + script halves | `9063b405` resolving. The **train** halves of the timer stay (§3 — models must refresh). After retirement the `forge-ranker-eval` timer slims to train-only; consider dropping cadence to weekly. |
| P1-4 | `eval-rewire` / `eval-prior-weight` subcommands | `src/forge/cli/ranker_model_cmd.py:370,429` | portions | Same — they exist to compare modes; post-freeze there is one mode. |
| P1-5 | Alpha-budget charging | `src/forge/feedback/alpha_budget.py` + `cli/alpha_budget_cmd.py` | 162 + 105 + 68 test | The freeze itself — the budget charges *grammar changes*; zero changes = nothing to charge. |
| P1-6 | Verified-alignment monitor | `scripts/tail_verified_alignment.py` | 150 | Quality-lane research instrument (D155); its question closes with the lane frozen. |

### P2 — dormant levers, dead branches, superseded symbols

Cheap, scattered, each its own micro-tranche. Several are already operator-queued regardless of
the freeze (D247(b)/D248 needs-owner manifest) — the freeze just removes their last excuse.

| # | Item | Where | Notes |
|---|---|---|---|
| P2-1 | `--orthogonal-yield` + `_load_orthogonal_yield_discounts` | `cli/main.py` | D108 A/B, never activated in 4 weeks; under freeze, never will be. |
| P2-2 | Exploration holdout (if declined) | `ranking/queue.py` (`rank_batch_with_holdout`, `sample_exploration_holdout`) + `FORGE_EXPLORATION_HOLDOUT_FRAC` resolver | ONLY if the pending flip is declined; if flipped, it's production (§3). |
| P2-3 | ve `|move|` null path | `prefilters/calibration.py:110,344` + `permutation_test.py:158` + D225 tests | D235 pre-authorizes: "stays in the tree as dead-but-inert, or can be removed in a later cleanup." |
| P2-4 | Blend-mode collapse | the `blend` branch of `FORGE_QUALITY_RANK_MODE` | Only after the gate-tail post-flip cohort CONFIRMS (else blend is the rollback). Keep the env kill-switches either way (§3). |
| P2-5 | Superseded/never-wired exports | `compute_hypothesis_reward_weights` (rejection_weights.py:222, +19 test refs, superseded D105), `is_percentile_emitting` (indicator_thresholds.py:544, +13 test refs, never wired) | D248 needs-owner items. |
| P2-6 | `_RV_REGIME_WEIGHTS_FROZEN` dead body | `rejection_weights.py:1229+` | Its documented unfreeze condition (Crucible pairs-path regime evaluation) can never fire under a frozen contract. |
| P2-7 | One-shot scripts + artifact | `scripts/backfill_verdicts.py`, `migrate_verdicts_decided_at.py`, `requeue_high_value_configs.py`, `probe_option_momentum_min_months.py` + `probe_results/*.json` + their 4 integration tests | Already queued (D247(b)/D248) — `_archive/` treatment. |
| P2-8 | Write-only tables | `pre_filter_logs`, `promoted_patterns` writers | Pending the Q44 forensics ruling — the freeze strengthens retire-writes. |
| P2-9 | `pytest-cov` + `[tool.coverage.*]` | `pyproject.toml` | Never invoked since bootstrap (D248). |

### P3 — dev/diagnostic surface (optional; retains incident value — retire last or never)

| # | Item | Where | Why it might stay anyway |
|---|---|---|---|
| P3-1 | `forge enumerate` / `forge prefilter` | `cli/main.py` | Incident diagnosis ("what would the grammar produce right now?") — cheap to keep. |
| P3-2 | Synthetic cache + demo registry | `SyntheticFeatureCache`, `enumeration/_demo_registry.py` (247) | Tests depend on both; retiring means reworking fixtures for zero runtime win. Likely KEEP. |
| P3-3 | `forge ranker-model dataset` | `cli/ranker_model_cmd.py` | Offline dataset builder; train path may still want it for debugging a bad model refresh. |
| P3-4 | Historical doc archival | `docs/proposals/` (bannered records), `fable-audit/` workplans (banner unexecuted items CLOSED-ON-FREEZE), `PHASE_*_HANDOFF.md`, `docs/reviews/`, `docs/handoffs/` | Archive-in-place or move to `_archive/`; provenance, not weight. |
| P3-5 | `config/grammar_archive/` (23 versions) | config/ | KEEP — it is the provenance chain for every config_hash ever submitted. |

## 3. Explicit KEEP — the steady-state core (the overreach line)

Retiring anything below breaks a *running* system, not a developing one:

- **The loop:** enumeration → prefilters → ranking → submission → persistence → funnel →
  feedback consumer/analyzer/weights (learning within the frozen grammar is production, not
  development — hard rule #5's determinism constraint, not a research arm), reconcile + failed-run
  flush (D240) + aged-out flush.
- **CLI:** `run`, `feedback`, `check`, `version`, `status`, `healthcheck`; `ranker-model
  train`/`train-robustness`/`eval` (model refresh + basic skill read).
- **Units:** `forge.service`, `forge-backup` (04:00), `forge-healthcheck` (hourly, D197/D246),
  `forge-ranker-eval` (slimmed to train-only per P1-3).
- **Safety levers:** env kill-switches (`FORGE_F3_RANKER`, `FORGE_QUALITY_RANKER`), the §7.3
  limiter, `contracts_check` + version pin (tripwire even under a frozen contract), grammar
  version-bump + doc-sync pre-commit hooks (accident tripwires), the daemon's loosening-proposal
  writer (`feedback/proposal_writer.py`, 387 — hard-rule #4 mechanism; post-freeze its output is
  the "frozen grammar is choking" telemetry).
- **Ops:** `deploy_preflight.sh` + `docs/tasks/deploy.md` (code-complete ≠ bug-free; bugfix
  deploys still follow the ritual), `backup_forge_db.sh`, drift monitor (`ranking/drift.py` —
  model-decay detection is ops), investigate-live/quality-gates/crucible-handoff task docs.
- **Tests:** the entire suite, including Hypothesis property tests and `tests/invariants/` —
  they are the safety net for every bugfix patch the frozen system will still need.

## 4. Cross-system notes (not this repo; relay-worthy at freeze time)

- `crucible-meta-king-publisher.timer` publishes daily for Forge's king arm retired in D190 —
  already flagged (D253); retirable on Crucible's side today, freeze or no freeze.
- Unused `crucible_contracts` surface (`validate_config_against_registry`, refit/portfolio
  symbols — D247(c)): a freeze converts the "handoff note at most" into an actual trim ticket
  for the contracts repo.
- Crucible's own dev machinery (refit watchers, portfolio search, enforcement checks) needs the
  mirror-image of this audit on their side; this report covers Forge only.

## 5. Rough reclaim

P0+P1 alone: ~2,600 src lines + ~2,400 dedicated test lines + 12 of the ~28 CLI
commands/subcommands, one script, and the eval half of one timer. P2 adds ~500 scattered lines
and closes every D247/D248 deferred item. The remaining repo is the production loop plus its
safety rails — roughly the shape a cold operator would need to run, monitor, back up, and
bugfix the frozen pipeline indefinitely.

## 6. Execution discipline (when the trigger fires)

One tranche = one operator-gated D-entry, smallest first (P2-7 style micro-tranches are fine to
batch). Tests retire in the same commit as their code; docs routing-table rows update in the
same commit; full suite green after every tranche; no daemon restart is needed for any P0/P1
item except the `daily_ranker_eval.sh` slim-down (timer-only) and the P2-2/P2-4 branch
collapses (deploy ritual). Sequence P1 strictly behind its pending decisions (§0.2).
