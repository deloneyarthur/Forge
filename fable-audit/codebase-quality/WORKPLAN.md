# Workplan — prioritized items 1–18 (2026-07-01)

Each item: what/why, exact action, effort (S/M/L), gating, verification, pitfalls.
Cross-references (SRC-/TEST-/OPS-/HYG-) point into `FINDINGS.md`. Re-verify each item's
premise against the live tree before starting — especially anything touching the files that
were dirty at audit time (`main.py`, `healthcheck_cmd.py`, `rejection_weights.py` + tests):
the in-flight D216 work may have landed or changed line numbers.

General loop for every code item: failing test first → minimum code → `uv run ruff check
src tests scripts` → `uv run ruff format <changed files only>` → `uv run mypy --strict src`
→ scoped pytest → small commit (one module + tests) → D-entry + STATUS.md block if the
change is an increment of record.

> Status reconciled 2026-07-05 against D-entries through D240, the code, and the live
> journal. P0 items 1–3 DONE, item 4 PARTIAL-with-deviation, item 15 swept 2026-07-05,
> item 16 now URGENT (the ledger has crossed its own 1MB trigger); items 5–14, 17, 18
> remain OPEN (no code traces). Annotations inline.

---

## P0 — do first (small, high stakes; the tree is red/exposed at audit time)

### 1. Clean the dirty production tree (HYG-H1) — S; code portion OPERATOR-GATED

— DONE (commits `63d7bfe`/`0ee6b5c`/`ce83584`, 2026-07-01; verified 2026-07-05).

- Why: reboot deploys the working tree (D104). ~6 days of ledger records
  (`STATUS.md` +117, `IMPLEMENTATION_DECISIONS.md` +108) exist only uncommitted; untracked
  records date to Jun 16.
- Action:
  a. Commit the record/doc files (ledgers, answered `PROMPT_CRUCIBLE_*`, proposals,
     research docs). Committing does not touch the running service. Respect the operator's
     concurrent work: re-run `git status` immediately before committing; commit only files
     you can attribute (see memory: operator edits the live tree in parallel).
  b. The D216 code diff (`main.py`, `rejection_weights.py`, `healthcheck_cmd.py` + tests +
     the untracked invariant test) lands via the deploy ritual (`docs/tasks/deploy.md`) or
     gets reverted — OPERATOR decision. It is flag-OFF/byte-identical per STATUS, so a
     commit-without-restart may be acceptable, but that call is the operator's.
- Verify: `git status --short` empty (or only known operator-in-flight files); suite green.
- Pitfall: do NOT `git add -A` blindly; `scratchpad/` is handled separately (item 4).
- Suggested standing rule to propose: no record older than 48h uncommitted.

### 2. Fix the failing MANPAGE-sync test (HYG-M3) — S; safe now

— DONE (verified 2026-07-05): the MANPAGE-sync test is GREEN; full suite 1846 passing at
D240. The "is red" below described the 2026-07-01 audit-time state.

- Why: the suite is a deploy precondition and is red:
  `tests/integration/test_cli_help.py::test_every_command_is_mentioned_in_manpage`.
- Action: add to `docs/MANPAGE.md`: (a) `forge ranker-model eval-rewire` (see
  `src/forge/cli/ranker_model_cmd.py`, commits `edb03e6`/`fdeed29` for semantics);
  (b) the `FORGE_QUALITY_RANK_MODE` env knob (commit `92e9061`; semantics in
  `docs/proposals/quality-lane-rewire.md`).
- Verify: `uv run pytest tests/integration/test_cli_help.py -q` green.

### 3. Make the pre-commit hook set satisfiable (OPS-H1, format half) — S; OPERATOR DECISION

— DONE (commit `038cb46`, 2026-07-02 — one-time tree-wide format normalization as specced;
verified 2026-07-05).

- Why: 28 files fail the repo's own `ruff-format` hook, so commits land with `--no-verify`,
  which ALSO skips the grammar-version-bump hook (hard rule #10's pre-commit half).
- Action: ONE deliberate format-only commit:
  `uv run ruff format src tests scripts` → verify `--check` clean → verify suite green
  (format must not change behavior; the golden determinism pins will catch any real change)
  → commit as `style: one-time ruff-format normalization (fable-audit item 3)`.
- This intentionally overrides the "format only changed files" convention ONCE, to remove
  the standing excuse for `--no-verify`. Get operator sign-off first.
- Verify: `uv run ruff format --check src tests scripts` clean; full suite green;
  `git diff` shows whitespace/formatting only.
- Pitfall: do it in a moment with no other dirty code (after item 1) so the diff is pure.

### 4. Resolve `scratchpad/` (OPS-M4 / HYG-L1) — S

— PARTIAL-with-DEVIATION (verified 2026-07-05): `scratchpad/` was gitignored (`0b2018c`,
2026-07-01) but the three cited probe scripts (`release_relval_sample.py`,
`release_volevent_sample.py`, `diag_volsurface_feasibility.py`) were NEVER committed — the
gitignore landed BEFORE the provenance half, exactly the pitfall below warned about. The
provenance half is still OPEN.

- Why: untracked+unignored, but `STATUS.md` and prereg `9b88966c446a` cite its contents as
  evidence (`release_relval_sample.py`, `release_volevent_sample.py`,
  `diag_volsurface_feasibility.py`, `relval_experiment_submitted.txt`).
- Action: commit the cited probes/records (either in-place or promoted to `scripts/` with a
  one-off/RETIRED header per item 7's convention), then add `scratchpad/` to `.gitignore`
  for genuinely disposable work.
- Verify: `git check-ignore scratchpad/somefile` passes after; the cited files are tracked;
  STATUS references still resolve.
- Pitfall: gitignoring BEFORE committing the cited files would break provenance.

---

## P1 — near term (process gaps)

### 5. Add minimal CI (OPS-H1, CI half) — M

- Why: there is no CI anywhere; the whole gate is local discipline in a tree that IS
  production. `.pre-commit-config.yaml:17` references a CI that doesn't exist.
- Action: one workflow (GitHub Actions if the repo has/gets a remote; otherwise a
  post-commit/pre-push local runner is a fallback):
  `uv venv && uv pip install -e ".[dev]"` with `crucible_contracts` checked out as the
  sibling `../crucible_contracts` (editable path dep — the workflow must clone/copy it);
  then `uv run ruff check src tests scripts` + `uv run ruff format --check src tests scripts`
  (only after item 3) + `uv run mypy --strict src scripts` (after item 6) +
  `uv run pytest -q`.
- Verify: a deliberately-broken branch fails CI.
- Pitfall: the contracts sibling is the hard part — if there is no remote for it, document
  the pin (`FORGE_EXPECTED_CONTRACT_VERSION`, `src/forge/core/contracts_check.py:62`).
  Ask the operator where `crucible_contracts` canonically lives before building.

### 6. Bring `scripts/` under mypy (OPS-M1) — S

- Action: fix the 22 errors (`scripts/decorrelation_proxy_alignment.py:167,341–357`,
  `scripts/backfill_verdicts.py:48`, +1 file — mechanical: `list` type-args,
  `object`-typed dict access); update the documented gate command in `CLAUDE.md` +
  `docs/tasks/quality-gates.md` to `mypy --strict src scripts`; widen the pre-commit mypy
  hook scope (`.pre-commit-config.yaml:26`, currently `files: ^src/`).
- Verify: `uv run mypy --strict src scripts` → 0 issues.

### 7. Guard/retire the dangerous one-off scripts (OPS-M2, OPS-M3, OPS-L5) — S

- Action:
  a. `scripts/backfill_verdicts.py` + `scripts/migrate_verdicts_decided_at.py`: add a
     refusal guard (`systemctl --user is-active forge.service` → exit with message) and/or
     flip dry-run to default-on.
  b. `scripts/requeue_high_value_configs.py`: RETIRED banner in header (it bypasses
     `submit_candidate` + the §7.3 limiter; D179 flood lesson) + a retirement note at
     `docs/MANPAGE.md:475–493`.
  c. Adopt a standard `STATUS: RETIRED (D###, executed <date>)` header line for the 5
     executed one-offs (`backfill_verdicts` D111, `migrate_verdicts_decided_at` D117,
     `requeue_high_value_configs` D048, `probe_option_momentum_min_months` Q39,
     `propose_threshold_tightenings` D206) — or move them to `scripts/archive/`.
- Verify: the guard refuses while the service is active (test with a fake `systemctl` shim
  in an integration test, mirroring `tests/integration/test_backfill_verdicts.py` patterns).
- Pitfall: these scripts HAVE integration tests — keep them green; if you move files,
  update test imports.

### 8. Tighten pytest config (TEST-M1, TEST-M2/OPS-L2) — S–M

- Action:
  a. Markers: add a `pytest_collection_modifyitems` hook in `tests/conftest.py` applying
     dir-based markers (`tests/unit/**`→unit, `tests/integration/**`→integration,
     `tests/invariants/**`→invariants); mark slow tests
     (`tests/invariants/test_phase2_invariants.py:372`,
     `tests/integration/test_grammar_perf.py`,
     `tests/integration/test_grammar_property.py:41,62`) with `slow`.
     Alternative if the operator prefers zero machinery: delete the unused marker
     declarations (`pyproject.toml:112–117`) so config stops lying.
  b. Warnings: add `filterwarnings = ["error"]` + targeted ignores to
     `[tool.pytest.ini_options]`; run the full suite and triage whatever surfaces
     (budget for a handful of Pydantic/Polars deprecation allowlist lines).
- Verify: `uv run pytest -m "not slow" -q` skips the perf tests; full suite green with
  warnings-as-errors.

---

## P2 — structural refactors (each independent, small increments; land via normal commit flow; OPERATOR-GATED where noted since they touch live-daemon modules)

### 9. Consolidate the nine learned-weight loaders in `cli/main.py` (SRC-M1) — M; OPERATOR-GATED (live daemon module)

- Precondition: item 1 done (D216 landed or reverted; `main.py` clean).
- Action: introduce one private helper, e.g.
  `_load_weights_from_export(runs, compute_fn, log_label, ...)`; keep ALL nine existing
  names bound in `forge.cli.main` as thin delegators (README rule 4). Then hoist the export
  parse: load `load_recent_gated_runs_from_export(...)` ONCE per `_run_one_iteration` and
  pass the parsed runs into the nine call sites (:1761–1867) + `_fetch_promoted_configs`
  (:1148) — ~10× fewer parses of the ~10k-row export per daemon cycle.
- Tests first: existing `tests/unit/test_cli/test_run_loop.py` must stay green untouched
  (it patches only `_run_one_iteration`); add a test pinning that each loader produces
  identical output to before (feed a small synthetic export fixture through old-vs-new —
  or simply rely on the existing per-loader unit tests if they exist; check
  `tests/unit/test_cli/` first).
- Verify: full suite; then at the next deploy window, journal shows identical weight lines.
- Pitfalls: hard rule #6 — the weights feed enumeration; identical outputs required, so no
  reordering of dict iteration or float accumulation inside `compute_*` calls. Keep log
  lines byte-compatible if anything greps the journal for them (check
  `healthcheck_cmd.py` and `docs/MANPAGE.md` journal-line references).

### 10. Delete the dead weighting stratum in `rejection_weights.py` (SRC-M4) — M; OPERATOR-GATED

- Precondition: item 1 (file is dirty with D216 work at audit time).
- Action: remove `compute_hypothesis_weights` (:77), `compute_hypothesis_reward_weights`
  (:222), `_run_reward` (:201), `_iter_hypothesis_outcomes` (:53) + their `__all__` entries
  (:1389–1390) + the 2 test files' coverage of them. KEEP `_sharpe_reward` (:172) — live
  via `_component_run_reward` (:484). Log a D-entry (deletion of legacy generation).
  Optional follow-up commit: split floor policies (`apply_exploration_floor`,
  `apply_orthogonal_family_floor`) into `feedback/floors.py` with re-exports.
- Verify: `grep -rn "compute_hypothesis_weights\|compute_hypothesis_reward_weights" src scripts`
  → 0 hits before deleting tests; full suite green; mypy clean.

### 11. Dedup model persistence in `ranking/model.py` (SRC-M2) — S–M

- Action FIRST: add a golden byte-identity test — save a verdict model and a robustness
  model from fixed inputs, pin the serialized bytes (and thus `model_id`) as goldens. THEN
  refactor `_payload`/`_robustness_fields` + the save/load/load-latest pairs
  (:355/:486, :374/:665, :397/:689, :417/:709) behind one generic artifact save/load
  parameterized by prefix + field spec.
- Verify: goldens unchanged; `load_latest_robustness_model(..., target=)` behavior intact
  (the D193 R1 target-aware loader) — check its tests in `tests/unit/test_ranking/`.
- Pitfall: `model_id` is a content hash of artifact bytes; ANY serialization drift breaks
  model identity in production rotation. The golden test is non-negotiable.

### 12. Fix the prefilters→feedback type inversion (SRC-M3) — S

- Action: move `BucketKey`/`BucketStats` from `feedback/trade_rate_priors` into
  `prefilters` (or `forge.core`); re-export from `feedback.trade_rate_priors` so existing
  imports keep working; flip the TYPE_CHECKING imports in `prefilters/types.py:29` and
  `prefilters/expected_trades.py:32` to the new home.
- Verify: import graph has no `prefilters → feedback` edge
  (`grep -rn "from forge.feedback" src/forge/prefilters/`); suite green.

### 13. Single exports-dir constant (SRC-M5) — S

- Action: promote `DEFAULT_EXPORTS_DIR` (`persistence/registry_loader.py:33`) to a shared,
  env-overridable location (`forge.core` or keep in persistence and import it); replace the
  16 hand-built sites (list in FINDINGS SRC-M5), including the differently-spelled
  `enumeration/sampler.py:228`.
- Verify: `grep -rn "optbt_data/exports" src/forge` → only the constant's definition.
- Pitfall: `sampler.py` is determinism-critical — the change is path-construction only,
  but run the golden pins (`tests/unit/test_enumeration/test_sampler.py`) to be sure.

### 14. Hoist the `GatedRun` test factory (TEST-M3) — M

- Action: one parameterized factory in `tests/fixtures/` (extend
  `strategy_configs.py` or add `gated_runs.py`); migrate the 7+ call sites listed in
  FINDINGS TEST-M3 file-by-file (each its own small commit is fine).
- Verify: suite green after each migration; no behavior-bearing defaults silently changed
  (diff each local factory against the shared one before deleting).

---

## P3 — hygiene backlog (batch into housekeeping commits)

### 15. Root-file archive sweep + cadence (HYG-M1) — S per sweep

— DONE (2026-07-05 second sweep, in progress today: 56 records → `_archive/`, root .md
count 72→16). Cadence proposal still pending operator.

- Action: move answered `PROMPT_CRUCIBLE_*` relays and landed plans to `_archive/`
  (convention already exists, D202; last sweep `b1d3b79` 06-24). Candidates: the ≥10
  answered relays (relval, GICS-relval, volsurface, xsect-volevent, gen-levers) + the 12
  pre-Jun-1 stragglers (`PROMPT_5_FORGE_V1_1_*`, `FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md`,
  `CONTRACTS_V1_2_AGENT_PROMPT.md`, …). Move `FORGE_THROTTLE_BACKPRESSURE_PROPOSAL.md` to
  `docs/proposals/`. Confirm each relay is actually answered (check STATUS/D-entries)
  before archiving.
- Propose a cadence trigger to the operator: sweep every 10 D-entries or weekly.
- Optional: `_archive/` month subfolders once it passes ~100 files.

### 16. Ledger rotation convention (HYG-M2) — M one-time; OPERATOR sign-off on the convention

— **DONE 2026-07-05 (D242, operator-approved):** D001–D200 → `_archive/IMPLEMENTATION_DECISIONS_D001-D200.md`
(859KB verbatim; live file keeps preamble + pointer + D201+, ~153KB). Heading formats
byte-identical so `grep '^## D'` works across both. `check-added-large-files` now excludes
`_archive/`. Deviations from the sketch below: cut at D200 (not D150); STATUS.md monthly
rotation NOT adopted (defer until STATUS itself becomes a problem).

- Action: before `IMPLEMENTATION_DECISIONS.md` hits ~1MB (920KB now): split to
  `_archive/IMPLEMENTATION_DECISIONS_D001-D150.md` + keep D151+ live, with a 5-line index
  header in the live file mapping D-ranges→files. Periodically move `STATUS.md` blocks
  older than ~30 days to `_archive/STATUS_<month>.md`. Keep heading formats byte-identical
  (`## D### — `, `## <date> — `) so `grep '^## D'` works across files. Update the routing
  table in `CLAUDE.md`/`docs/architecture.md` to mention the archive files.
- Pitfall: many docs/memories reference "IMPLEMENTATION_DECISIONS.md (D###)" — the live
  file must keep resolving for recent entries; never renumber.

### 17. Small code cleanups (SRC-L1..L4) — S each, batchable

- a. Public-ize cross-package privates: `_INDICATOR_THRESHOLD_TABLE`
     (`enumeration/indicator_thresholds.py`, imported at `ranking/features.py:26`),
     `_P2_ENTRY_DTE` (`grammar/custom_predicates.py`, imported at `ranking/features.py:28`),
     `_directional_signal` (`prefilters/signal_density.py`, imported by 4 prefilters).
     Rename + keep old names as aliases for one release, or just rename and fix imports
     (all in-repo).
- b. Unify the two `_directional_signal` implementations
     (`grammar/custom_predicates.py:367` returns None; `prefilters/signal_density.py`
     raises) behind one public helper with a strict/lenient flag; grammar layer owns it.
- c. Narrow `cli/grammar_cmd.py:366` to
     `except (GrammarError, ValidationError, OSError, yaml.YAMLError)` (see
     `grammar/models.py:33,38`).
- d. `ranking/shadow.py:104`: log with `exc_info=True`; re-raise types that aren't
     IO/QueryError so coding bugs can't become permanent silent telemetry.

### 18. Small ops/docs cleanups — S each, batchable

- a. Remove dead `src/forge/king/` + `tests/unit/test_king/` pycache dirs (SRC-L5/TEST-L2);
     add a "king — retired (D190)" row to `docs/architecture.md` module map (HYG-L2).
- b. `deploy/systemd/forge.service:3,10,22`: `/home/aj/...` → `%h` (OPS-L3). NOTE: unit
     changes only take effect at the next daemon restart/daemon-reload — fold into the next
     deploy window; don't restart for this alone.
- c. `forge-eod-check`: symlink `%h/.local/bin/forge-eod-check.sh` to
     `scripts/forge_eod_check.sh` like the other units; run the headless agent with an
     enforced read-only permission mode and/or non-repo cwd (OPS-M5).
- d. D206 retirement notes in `docs/HOW-TO.md:189–193` and `docs/MANPAGE.md:452–472` (OPS-L4).
- e. Persist `SCHEMA_VERSION` (`persistence/schemas.py:13`) in a one-row metadata table on
     `db_connection()`, or document additive-only as the accepted migration policy (OPS-L1).
     If persisting: TDD via `tests/unit/test_persistence.py`; the change runs against the
     live 4.5GB DB at next daemon start — keep it a trivial CREATE-IF-NOT-EXISTS + INSERT-
     IF-EMPTY.
- f. Update `tests/README.md`: invariants row (8 non-phase files exist), rule-#10 placement
     note (TEST-M4/L1), a home for script tests (TEST-L3).
- g. Cover `src/forge/core/logging.py` (the only zero-test src module) with a smoke test.
- h. Dependency bumps (duckdb 1.5.4, polars 1.42.x, typer 0.26.x, structlog 26.x) — DEPLOY-
     GATED: full uncontended suite + restart ritual; do at a scheduled deploy window only.

---

## Not-do / explicitly rejected

- Do NOT split `grammar/custom_predicates.py` — intrinsic size, one function per
  operator-owned §3.5 rule.
- Do NOT refactor `_run_one_iteration`/`cmd_run` bodies beyond item 9's loader hoist —
  deliberately linear (inline noqa rationale at `main.py:1602`), monkeypatch seam.
- Do NOT bundle `sample_config`'s 15 params without a cold-start byte-identity test
  (SRC-L6) — low value vs determinism risk; skip unless already in there for other reasons.
- Do NOT delete `funnel/` — it is live (`cli/main.py:2127`).
- Do NOT "fix" `crucible-ingest-daily` failures or "blocked: prev batch N% gated" — benign.
- Do NOT format tree-wide outside the one-time item 3 commit.
