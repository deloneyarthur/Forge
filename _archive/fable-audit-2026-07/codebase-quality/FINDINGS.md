# Findings — full detail with evidence (2026-07-01)

All file:line references are against the dirty working tree at HEAD `ceeefa4` on 2026-07-01.
Severity scale: HIGH / MEDIUM / LOW. Each finding cross-references its WORKPLAN item number.

---

## Area 1 — `src/forge` architecture & code quality

96 modules, 22,418 lines. No high-severity findings; no hard-rule violations.

### SRC-M1 (MEDIUM, → item 9): nine near-verbatim learned-weight loaders in `cli/main.py`, each re-parsing the same export per daemon iteration

- The clones (~35 lines each, differing only in the `compute_*` function called):
  `_load_hypothesis_weights` (main.py:546), `_load_regime_weights` (:643),
  `_load_bucket_weights` (:718), `_load_underlying_class_weights` (:768),
  `_load_underlying_name_weights` (:815), `_load_directional_bucket_weights` (:863),
  `_load_orthogonal_yield_discounts` (:912), `_load_cohort_yield_weights` (:979),
  `_load_regime_gate_yield_weights` (:1033).
- Each independently calls `load_recent_gated_runs_from_export(exports_dir, limit=FEEDBACK_GATED_RUNS_LIMIT)`.
  `_run_one_iteration` (main.py:1602) invokes all nine per iteration (call sites :1761–1867),
  plus a tenth parse in `_fetch_promoted_configs` (:1148) — up to ~10 full parses of the same
  ~10k-row JSON export per daemon cycle.
- Monkeypatch-seam analysis (why the refactor is safe): tests patch only `_run_one_iteration`
  (4 sites, `tests/unit/test_cli/test_run_loop.py:583–746`) and import other private names
  listed in README rule 4 — **none of the nine loaders is patched or imported by tests**.
  A shared private helper `_load_weights_from_export(compute_fn, ...)` that keeps every
  existing name bound in `forge.cli.main`, parsing the export once per iteration and
  threading the parsed runs through, is fully compatible with D065/D105/D106.

### SRC-M2 (MEDIUM, → item 11): verdict/robustness model persistence is a copy-paste quadruplet in `ranking/model.py` (~120 lines)

- `_payload` (model.py:355) vs `_robustness_fields` (:486) — identical except a `"kind"` key.
- `save_model` (:374) vs `save_robustness_model` (:665); `load_model` (:397) vs
  `load_robustness_model` (:689); `load_latest_model` (:417) vs
  `load_latest_robustness_model` (:709) — differ only in filename prefix + field spec.
- CAUTION: the artifact bytes are content-hashed into `model_id`, so any refactor must be
  byte-identical on outputs. Add a golden-file byte-identity test BEFORE refactoring.

### SRC-M3 (MEDIUM, → item 12): type-level layering inversion — the only package cycle

- `prefilters/types.py:29` and `prefilters/expected_trades.py:32` import
  `BucketKey`/`BucketStats` from `forge.feedback.trade_rate_priors` (TYPE_CHECKING-only, so
  no runtime cycle), while `feedback/auto_tune.py:34` imports `forge.prefilters.calibration`
  at runtime. Package graph: `prefilters → feedback → prefilters`. The value types a lower
  layer consumes live in the upper layer.
- Fix: move `BucketKey`/`BucketStats` into `prefilters` (or `core`), re-export from
  `feedback.trade_rate_priors` for compatibility.

### SRC-M4 (MEDIUM, → item 10): `feedback/rejection_weights.py` (1,396 lines) carries a production-dead legacy stratum (~120 lines)

- Dead (referenced by nothing in `src/` or `scripts/`; only 2 test files):
  `compute_hypothesis_weights` (rejection_weights.py:77), `compute_hypothesis_reward_weights`
  (:222), `_run_reward` (:201), `_iter_hypothesis_outcomes` (:53). Still exported in
  `__all__` (:1389–1390).
- NOT dead — do not remove: `_sharpe_reward` (:172) is live via `_component_run_reward` (:484).
- The live remainder mixes three concerns: the shared component-rate engine
  (`_component_rate_sums` :489, `_hierarchical_posteriors` :584 — well-factored), the
  per-axis wrappers (:619–1120), and the floor policies (`apply_exploration_floor` :1290,
  `apply_orthogonal_family_floor` :1325). Optional split: floors → `feedback/floors.py`.
- COORDINATE: this file is dirty with in-flight D216 work at audit time.

### SRC-M5 (MEDIUM, → item 13): magic path `~/optbt_data/exports` hand-built 16 times across 5 packages

- `persistence/registry_loader.py:33` already defines `DEFAULT_EXPORTS_DIR`, yet it is
  re-derived at: `cli/main.py:597,671,742,791,838,885,938,1005,1059,1121,1183`;
  `submission/rate_limiter.py:157`; `feedback/consumer.py:276,448`;
  `cli/healthcheck_cmd.py:459`; and a differently-spelled variant
  `Path("~/optbt_data/exports").expanduser()` at `enumeration/sampler.py:228`.
- Fix: one shared, env-overridable constant in `core` or `persistence`.

### SRC-L1 (LOW, → item 17): cross-package imports of private symbols

- `ranking/features.py:26` imports `_INDICATOR_THRESHOLD_TABLE` from
  `enumeration.indicator_thresholds`; `ranking/features.py:28` imports `_P2_ENTRY_DTE` from
  `grammar.custom_predicates`; four prefilters (`prefilters/permutation_test.py:32`,
  `prefilters/regime_exposure.py:23`, `prefilters/expected_trades.py:26`,
  `prefilters/novelty.py:27`) import `_directional_signal` from `prefilters/signal_density.py`.
- Fix: drop the underscore (make public) or add public accessors.

### SRC-L2 (LOW, → item 17): two divergent `_directional_signal` implementations

- `grammar/custom_predicates.py:367` returns `None` on non-unique;
  `prefilters/signal_density.py`'s raises `ValueError`. Same concept + same name, different
  failure contracts. Unify behind one public helper (grammar layer) with a strict/lenient flag.

### SRC-L3 (LOW, → item 17): `cli/grammar_cmd.py:366` broad `except Exception` around `load_grammar`

- Not silent (echoes + `Exit(1) from exc`) but should catch
  `(GrammarError, ValidationError, OSError, yaml.YAMLError)`;
  `GrammarLoadError`/`GrammarVersionError` exist at `grammar/models.py:33,38`.

### SRC-L4 (LOW, → item 17): `ranking/shadow.py:104` `except Exception → warn + return 0`

- A coding error in shadow scoring would log one warning line and silently produce 0 rows
  forever (documented telemetry-only, but still). Fix: log with `exc_info=True` and/or
  re-raise non-(IO/Query) exception types.

### SRC-L5 (LOW, → item 18): `src/forge/king/` contains only stale `__pycache__`

- Source correctly deleted at D190 (commit `f79394a`); untracked bytecode remains. Not a
  hazard (no importable source) but noise in a tree that auto-deploys on reboot.
- `funnel/` is NOT dead — used by `cli/main.py:2127` (`write_funnel_export`) + tests.

### SRC-L6 (LOW): `sample_config` (`enumeration/sampler.py:426`) takes 15 keyword params (10 weight maps)

- Parameter-object smell, but the body is a determinism-critical ordered draw pipeline
  (hard rule #6), already decomposed into `_build_selector`/`_build_sizer`/`_build_exits`/
  `_pick_underlying`. Bundling into a frozen `WeightMaps` dataclass is safe only with a
  cold-start byte-identity test. Low urgency; not in the workplan — opportunistic only.

### SRC-L7 (LOW, informational): "one file per CLI command" partially holds — by design

- `cmd_enumerate` (main.py:93), `cmd_prefilter` (:232), `cmd_run` (:2295) live inside
  `main.py` (the D065/D105/D106 deliberate structure); all seven newer commands (`feedback`,
  `healthcheck`, `status`, `alpha-budget`, `grammar`, `prereg`, `ranker-model`) follow the
  rule in their own files. Any future extraction must keep names bound in `forge.cli.main`.

### SRC-L8 (LOW, informational): `persistence/registry_loader.py:109` lazily imports `enumeration._demo_registry`

- Foundation layer reaching up for a demo fixture (deliberately `noqa: PLC0415`). Could be
  inverted via injection if ever touched.

### Size verdicts on the seven biggest files

- `cli/main.py` (2,581): **accidental but constrained** — the loader/formatter stanzas
  (SRC-M1) are the extractable ~700 lines; `_run_one_iteration` (577 lines) + `cmd_run`
  (270) are deliberately linear per the inline noqa rationale at :1602.
- `feedback/rejection_weights.py` (1,396): **mixed** — engine well-factored; dead legacy
  generation + colocated floor policies are the accidental part (SRC-M4).
- `enumeration/sampler.py` (1,335): **mostly intrinsic** — one `_sample_*_params` per signal
  family + determinism-ordered CSP; only the signature smell (SRC-L6).
- `grammar/custom_predicates.py` (1,048): **intrinsic** — one function per §3.5 rule
  (S4/S5/C1/C2/C4/P1–P3/E1–E3/R1–R3/X1/X2) + registry at :1013; operator-owned; leave alone.
- `ranking/model.py` (733): **accidental** — the persistence quadruplet (SRC-M2).
- `enumeration/indicator_thresholds.py` (643): **intrinsic** — ~340 lines are the audited
  threshold data table.
- `cli/healthcheck_cmd.py` (511): **intrinsic and well-designed** — pure journal-parse +
  per-check functions; only gather-glue touches subprocess.

### Verified HOLDING (src)

- Hard rule #8: `datetime.now` only at `core/clock.py:14`; `random.Random(` instantiated
  only at `core/seed.py:29`; zero `default_rng`/`np.random` hits.
- DB open path: `duckdb.connect` only in `persistence/db.py:32,36`.
- Hard rule #2: zero `from crucible.` imports; all access via `crucible_contracts`.
- Contracts exceptions never silently caught: `SchemaVersionMismatch` explicitly re-raised
  in the daemon guard (`cli/main.py:2544`); every `QueryError` catch is a documented, logged
  degradation (warn-once memos `main.py:350–354`; loud log `sampler.py:246`; fallback
  `rate_limiter.py:224`). `submitter.py:248` `except BaseException → ROLLBACK → raise` is
  correct transaction hygiene.
- `from __future__ import annotations` in all modules except two trivial `__init__.py`.
- Every `@dataclass` in `src/forge` is `frozen=True, slots=True` — zero exceptions.
- Pydantic confined to boundaries: `grammar/models.py` (YAML parse, D017 rationale),
  `config/forge_config.py`, isinstance-dispatch in `path_resolver.py`.
- Zero TODO/FIXME/HACK/XXX; no orphan modules (AST sweep); package import graph acyclic at
  runtime (only the type-only SRC-M3 cycle); one-file-per-prefilter holds
  (`prefilters/battery.py:16–25` imports 9 filter modules).

---

## Area 2 — test suite

149 files / 38,076 lines / 1,566 test functions (1,745 collected at run time). Verdict:
unusually healthy; no HIGH findings. Checked and cleared: no test touches `~/forge_data` or
the live DB; no network, no `time.sleep`, no `os.chdir`, no raw `os.environ` mutation.

### TEST-M1 (MEDIUM, → item 8): all four pytest markers are dead — slow tests cannot be deselected

- `pyproject.toml:112–117` defines `unit/integration/invariants/slow` with `--strict-markers`,
  but `grep pytest.mark|pytestmark` over `tests/` hits 0 files.
- Genuinely slow tests sit unmarked in the default path:
  `tests/invariants/test_phase2_invariants.py:372`
  (`test_perf_100k_configs_under_five_minutes`), `tests/integration/test_grammar_perf.py`,
  and two 1000-example Hypothesis tests in `tests/integration/test_grammar_property.py:41,62`.
- Fix: auto-apply dir-based markers via `pytest_collection_modifyitems` in `tests/conftest.py`
  and mark the 3 perf + 2 heavy property tests `slow` — or delete the unused markers.

### TEST-M2 (MEDIUM, → item 8): warnings are not errors

- `[tool.pytest.ini_options]` (`pyproject.toml:107–117`) has `--strict-markers
  --strict-config` but no `filterwarnings = ["error"]`. Pydantic/Polars/DuckDB deprecations
  pass silently until they break. Fix: add `filterwarnings = ["error", ...targeted ignores]`;
  expect a triage pass.

### TEST-M3 (MEDIUM, → item 14): `_gated_run` builder copy-pasted across ≥7 files

- Local near-identical `GatedRun` factories:
  `tests/unit/test_feedback/test_trade_concentration.py:28`,
  `tests/unit/test_feedback/test_regime_gate_yield.py:132`,
  `tests/unit/test_feedback/test_threshold_proposer.py:26`,
  `tests/unit/test_feedback/test_cohort_yield.py:151`,
  `tests/unit/test_feedback/test_rejection_weights.py:105` (+ :400 graded variant),
  `tests/unit/test_feedback/test_component_rate_weights.py:135`,
  `tests/unit/test_ranking/test_dataset.py:47`.
- `tests/README.md:10` says "Extend rather than duplicate"; a contracts model change would
  require 8 parallel edits. Fix: hoist one parameterized factory into
  `tests/fixtures/strategy_configs.py` (or new `tests/fixtures/gated_runs.py`).

### TEST-M4 (MEDIUM, → item 18): hard rule #10 test placement drifts from the suite's own rule

- `tests/README.md:9` says every hard rule gets its failure-mode test in `tests/invariants/`;
  rule #10 enforcement actually lives in `tests/integration/test_hook_scripts.py:169,231,260`
  (silent-edit rejected, archive-deleted fails, wrong-content rejected),
  `tests/unit/test_grammar/test_archive.py` (content-collision refusal),
  `tests/unit/test_grammar/test_loader.py:156` (silent-drift rejected). Coverage is COMPLETE —
  placement/doc drift only (hook scripts need real git repos, so placement is defensible).
- Fix: one README line noting the placement.

### TEST-M5 (MEDIUM, optional): parametrize nearly unused (20 uses / 1,566 tests)

- `tests/unit/test_enumeration/test_sampler.py` (2,031 lines, 84 tests) and
  `tests/unit/test_grammar/test_custom_predicates.py` (1,578 lines) carry long runs of
  structurally similar case-tests. Not incorrect (every test fn <100 lines) — opportunistic
  `@pytest.mark.parametrize` conversion when next touching these files; consider splitting
  `test_sampler.py` by concern (golden pins vs stratification vs yield-axes). Not in the
  numbered workplan; do opportunistically.

### TEST-L1 (LOW, → item 18): `tests/README.md:9` invariants row stale

- Says "one file per phase (`test_phase{0..6}_invariants.py`…)" but 8 additional non-phase
  invariant files exist (funnel, inbox_layout, inflight_depth, learned_ranker,
  option_momentum, orthogonal_family_floor [untracked/new], stall_guard).

### TEST-L2 (LOW, → item 18): dead dirs

- `tests/unit/test_king/` contains only `__pycache__` (tests deleted with the D190
  retirement); `src/forge/king/` likewise (see SRC-L5). Remove both in housekeeping.

### TEST-L3 (LOW, → item 18): loose files at `tests/unit/` root with no README-defined home

- `test_decorrelation_proxy.py` and `test_wf_quality_probe.py` test `scripts/` (not
  `src/forge/`); `test_persistence.py`, `test_registry_loader.py`, `test_phase0_smoke.py`
  sit flat rather than in mirrored dirs. Add a README row for script tests or a
  `tests/unit/test_scripts/` dir.

### TEST-L4 (LOW): one over-broad raises, already annotated

- `tests/unit/test_registry_loader.py:149` `pytest.raises(Exception)  # noqa: B017` —
  deliberate and flagged; optionally narrow. No urgency.

### TEST-L5 (LOW, no action): three assert-less "must-not-raise" smoke tests out of 1,566

- `tests/unit/test_feedback/test_analyzer.py:247`, `tests/unit/test_grammar/test_archive.py:77`,
  `tests/unit/test_persistence.py:21` — all legitimate not-raise contracts with comments.

### TEST-L6 (LOW, documented characteristic): several "unit" files depend on live `config/grammar.yaml` at module scope

- `test_sampler.py:43`, `test_horizon_matched_dte.py:30`, `test_event_momentum_grammar.py:37`,
  plus integration grammar files. Deliberate golden pinning (`tests/README.md:16`); means
  grammar edits ripple through nominally-unit tests and in-tree hot-reread can bite mid-edit.

### Coverage mapping (static)

- Test:src line ratios: feedback 8,275/4,925 (1.7), enumeration 4,283/3,097 (1.4), grammar
  3,703/2,484 (1.5), ranking 4,266/2,779 (1.5), prefilters 4,256/2,415 (1.8), submission
  2,281/1,053 (2.2), config 196/168, funnel 368/289 (+ invariants), cli 2,891/4,558 (0.63)
  + `test_cli_help.py` mechanical audit. CLI subcommand modules that look unreferenced
  (`ranker_model_cmd`, `grammar_cmd`, `prereg_cmd`) are exercised via
  `from forge.cli.main import app` + CliRunner (11–17 invocations each).
- Three worst-covered production modules:
  1. `src/forge/core/logging.py` (36 lines) — the ONLY src module with zero test references;
     configures structlog for the daemon. Cheap to cover.
  2. `src/forge/persistence/` (475 src lines) vs a 48-line direct test file — heavily
     exercised indirectly (phase4/5 invariants, tmp-DB fixtures); migration/schema-evolution
     paths have thin direct coverage.
  3. `src/forge/cli/main.py` — lowest test:src ratio among large modules; run loop tested
     through the monkeypatched `_run_one_iteration` seam rather than end-to-end (documented
     D065 trade-off).

### Verified HEALTHY (tests)

- Hard-rule invariant coverage is 10/10 present:
  - #1 rule count: `test_phase1_invariants.py:101` + `tests/integration/test_v1_grammar.py`
    (doc-sync with GRAMMAR.md).
  - #2 no Crucible internals: `test_phase0_invariants.py:134` (scans for `optbt`/`crucible.*`).
  - #3/#4 tighten-only: `test_phase5_invariants.py:40–75` (no `apply_loosening` in 5 modules;
    proposer emits tighten-only).
  - #5 no LLM: `test_phase0_invariants.py:159`.
  - #6 determinism: `test_phase2_invariants.py:39,52,587` (byte-identical, seed-diverges,
    stratification-preserving) + golden pins (`test_sampler.py:1708,1900`) + flag-OFF
    byte-identity tests for every yield axis (`:59,84,128`) + learned-ranker training
    byte-identity (`test_learned_ranker_invariants.py:193`).
  - #7 no equity: 5 tests in `test_phase1_invariants.py` + at-scale check
    `test_phase2_invariants.py:285`.
  - #8 clock/seed: `test_phase0_invariants.py:66,77` + a META-TEST at :94 proving the scan
    regexes still catch known offender patterns (standout practice).
  - #9 idempotency: `test_phase4_invariants.py:106,230` (submitter path + raw UNIQUE index)
    AND a Hypothesis property (`test_phase6_properties.py:99`).
  - #10: see TEST-M4 — fully covered.
- Hermeticity exemplary: autouse `_isolated_home` (`tests/conftest.py:18–31`) redirects
  `Path.home()` per test; backup-script integration test documents "never touches the live
  ~/forge_data"; zero skips/xfails.
- Hypothesis usage substantive: 1000-example valid-config and mutated-invalid properties
  where the mutant must fail AND the validator must name the broken rule
  (`test_grammar_property.py:62–83` — error-attribution testing).
- Internal-patching within budget: only `test_run_loop.py` setattrs `forge.cli.main`
  internals (4 sites, the documented seam); ~5–6 files import private `main` helpers —
  within the documented "~10 files"; MagicMock concentrated in
  `test_crucible_feature_cache.py` at a genuine client boundary; everything else uses real
  DuckDB in tmp dirs.
- Single 31-line conftest; `tests/fixtures/` helpers imported by 70 files.
- Doc-drift guards as tests: `test_cli_help.py` enforces docstring/help/README sync for
  every Typer command; `test_phase6_invariants.py` pins MANPAGE/HOW-TO/architecture content.

---

## Area 3 — tooling, scripts, packaging, ops

Note: `scripts/` holds 14 files (10 Python = 2,546 lines, 4 bash ≈ 1,100 lines).

### OPS-H1 (HIGH, → items 3 & 5): quality gate is local-only and demonstrably bypassed — no CI; the tree fails its own ruff-format hook

— Status 2026-07-05: format half RESOLVED (item 3 DONE, `038cb46` 2026-07-02 — hook set now
satisfiable). CI half (item 5) still OPEN.

- No `.github/`, `.gitlab-ci.yml`, `.circleci/` or any CI file (`git ls-files` shows none);
  `.pre-commit-config.yaml:17` even says "CI must run mypy via `uv run` for the same
  reason" — a CI that does not exist.
- `uv run ruff format --check src tests scripts` fails on 28 files (e.g.
  `tests/unit/test_prefilters/test_novelty.py`) despite `ruff-format` being a configured
  hook (`.pre-commit-config.yaml:11`) — proving commits routinely land with `--no-verify`.
- Habitual `--no-verify` also skips the grammar-version-bump hook
  (`.pre-commit-config.yaml:41–52`), the pre-commit half of hard rule #10, in a repo where
  a reboot deploys the working tree (D104). Only the loader-side archive check remains.
- Fix order matters: (b) format the 28 files in ONE commit so the hook set becomes
  satisfiable (root cause), then (a) add minimal CI.

### OPS-M1 (MEDIUM, → item 6): `scripts/` not type-checked; currently fails `mypy --strict` with 22 errors

- Documented command (`CLAUDE.md`, `docs/tasks/quality-gates.md`) is `mypy --strict src`;
  the pre-commit mypy hook is scoped `files: ^src/` (`.pre-commit-config.yaml:26`).
- `uv run mypy --strict scripts` → 22 errors in 3 files:
  `scripts/decorrelation_proxy_alignment.py:167,341–357`, `scripts/backfill_verdicts.py:48`,
  +1 more. Mechanical fixes (`list` type-args, `object`-typed dict access).

### OPS-M2 (MEDIUM, → item 7): live-DB-writing scripts have docstring-level safety only

- `scripts/backfill_verdicts.py:12–24` (INSERTs into `verdicts`) and
  `scripts/migrate_verdicts_decided_at.py:24–30,132` (UPDATEs `decided_at`) both default to
  the LIVE `~/forge_data/forge.db` (`backfill_verdicts.py:70`,
  `migrate_verdicts_decided_at.py:87`) with dry-run OFF by default; the "MUST run while
  forge.service is stopped" contract is prose only.
- Both are executed one-offs (D111/D117, run 2026-06-09). Fix: 3-line
  `systemctl --user is-active forge.service` refusal guard or dry-run default-on; mark RETIRED.

### OPS-M3 (MEDIUM, → item 7): `scripts/requeue_high_value_configs.py` writes raw JSON into Crucible's inbox, bypassing `submit_candidate` and the §7.3 limiter

- `requeue_high_value_configs.py:214–230` copies `processed/{hash}.json → inbox/` directly
  (dry-run opt-in, :91). An unpaced inbox flood previously OOM'd Crucible's writer (D179).
  `docs/MANPAGE.md:475–493` presents it without a retired marker despite one-off purpose
  (D048, executed 2026-05-18). Fix: RETIRED banner in header + MANPAGE (or a batch cap).

### OPS-M4 (MEDIUM, → item 4): `scratchpad/` untracked, unignored, holds referenced evidence

— Status 2026-07-05: PARTIAL — gitignored (`0b2018c`) but the cited probes were never
committed; the provenance half remains OPEN (see item 4's deviation note).

- 7 .py + 1 .txt. `release_relval_sample.py` / `release_volevent_sample.py` submit to
  Crucible's gate (dry-run default — good); `relval_experiment_submitted.txt` is the
  submitted-hash record for prereg `9b88966c446a`, cited from `STATUS.md` (multiple blocks)
  but preserved nowhere durable. Fix: commit the cited probes/records, gitignore the rest.

### OPS-M5 (MEDIUM, → item 18): nightly `forge-eod-check` runs a headless LLM agent inside the production tree with prompt-only write restrictions

- `deploy/systemd/forge-eod-check.service:8` executes `%h/.local/bin/forge-eod-check.sh` —
  a COPY (not symlink) of `scripts/forge_eod_check.sh` (byte-identical today, but every
  other unit path is a symlink per `docs/MANPAGE.md:599` → drift is one edit away). The
  script's "do not modify anything inside ~/proj/Forge" constraint
  (`scripts/forge_eod_check.sh:19–22`) is prompt text, not permissions, with cwd = the live
  tree. Not a rule-#5 violation (report-only, outside the loop). Fix: symlink + enforced
  read-only permission mode / non-repo cwd.

### OPS-L1 (LOW, → item 18): schema migrations ad-hoc additive-only; `SCHEMA_VERSION` declared but never persisted or checked

- `src/forge/persistence/schemas.py:13` (`SCHEMA_VERSION = "0.1.0"`, exported in
  `persistence/__init__.py`, unused elsewhere); `db.py:19–22` replays
  `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS` on every open.
  Fine for additive history; renames/type-changes have no path and the DB carries no record
  of what's applied. Fix: one-row metadata table, or document additive-only as accepted.

### OPS-L2 (LOW, → item 8): pytest does not escalate warnings (same as TEST-M2).

### OPS-L3 (LOW, → item 18): `forge.service` hardcodes `/home/aj/...` while every other unit uses `%h`

- `deploy/systemd/forge.service:3,10,22`; `deploy/NEW_BOX_TRANSFER.md:5` papers over it.

### OPS-L4 (LOW, → item 18): docs drift on the D206-retired tightening path

- `docs/HOW-TO.md:189–193` still presents `propose_threshold_tightenings.py` as the routine
  "tune the generator" ritual; `docs/MANPAGE.md:452–472` carries no retirement note (though
  `config/auto_tightened_thresholds.yaml:1` documents the D206 retirement).

### OPS-L5 (LOW, → item 7): half of `scripts/` is executed one-off history in the active namespace

- `backfill_verdicts.py` (D111), `migrate_verdicts_decided_at.py` (D117),
  `requeue_high_value_configs.py` (D048), `probe_option_momentum_min_months.py` (Q39-closed),
  `propose_threshold_tightenings.py` (D206-retired) — 5 of 10 Python scripts. Retention
  defensible (tested, excellent headers) but nothing distinguishes them from live tools.
  Fix: `scripts/archive/` or a standard `STATUS: RETIRED/one-off` header line.

### OPS-L6 (LOW, no urgent action): `crucible_contracts` version-unconstrained in packaging

- `pyproject.toml:10` bare; `:41` editable sibling path, so `uv.lock` can't pin it.
  Mitigated by the runtime pin `FORGE_EXPECTED_CONTRACT_VERSION = "1.21.0"`
  (`src/forge/core/contracts_check.py:62`) checked at CLI startup + a suite test.
  Optional: `>=` floor in pyproject.

### OPS-L7 (LOW, → item 18): minor dependency lag

- duckdb 1.5.2→1.5.4, polars 1.40.1→1.42.1, typer 0.25.1→0.26.8, structlog 25.5.0→26.1.0
  (the only major-behind). pydantic 2.13.4 current. `uv.lock` committed. Upgrades are
  deploy-gated (full suite + restart ritual).

### Verified HEALTHY (tooling/ops)

- All 10 Python scripts: `from __future__ import annotations` (zero misses), zero clock/RNG
  violations, WHY-rich docstrings with usage/safety/D-numbers; pure-analysis scripts open
  DuckDB `read_only=True` (`decorrelation_proxy_alignment.py:198`,
  `tail_verified_alignment.py:139`, `wf_quality_probe.py:387`). Ruff-clean incl. scripts.
- Even one-offs are tested: `tests/integration/test_{backfill_verdicts,backup_script,hook_scripts,migrate_verdicts_decided_at,requeue_high_value_configs}.py`.
- Backup/DR (D195) genuinely well-engineered: `scripts/backup_forge_db.sh` does torn-copy
  validation with retry, atomic same-fs rename publish, prune-only-after-verified-new,
  disk-space guard, env-overridable paths, trap cleanup; 3 failure-mode integration tests;
  timer live (04:00 daily).
- Pre-commit: hard-rule-#10 grammar-version-bump hook + grammar↔doc sync hook present,
  stdlib-only, correctly file-scoped (`.pre-commit-config.yaml:38–63`).
- systemd: deployed copies byte-identical to `deploy/systemd/`; timers deliberately
  staggered (comments explain DB-copy collision avoidance); `Persistent=true` everywhere;
  `forge-healthcheck.service` uses `SuccessExitStatus=1` for WARN; `forge.service` has sane
  `Restart=on-failure`/`RestartSec=30`/`TimeoutStopSec=120`, `NoNewPrivileges`+`PrivateTmp`;
  every non-default ExecStart flag comment-documented with kill switch.
  `deploy/setup_new_box.sh` + `NEW_BOX_TRANSFER.md` match the actual unit set.
- Persistence: single blessed open path; UTC session-TZ pin (D061, `db.py:37–43`); rule-#9
  unique index on `config_hash` (`schemas.py:27`); DDL annotated with decision provenance.
- pyproject: mypy strict truly strict (no overrides/ignores/exclusions); pytest
  `--strict-markers --strict-config` with defined markers; ruff per-file-ignores few and
  justified; deps sane `>=x,<next-major`; `requires-python >= 3.12`.
- No unused declared dependencies (all six runtime deps imported in `src/forge`).

---

## Area 4 — repo & docs hygiene

### HYG-H1 (HIGH, → item 1): dirty production tree, dirt aged up to 15 days (D104 violation)

— Status 2026-07-05: RESOLVED (item 1 DONE — `63d7bfe`/`0ee6b5c`/`ce83584`, 2026-07-01).

- 12 modified tracked + 18 untracked paths; a reboot auto-starts the daemon on uncommitted code.
- Code dirt (D216 work, mtimes 2026-07-01): `src/forge/cli/main.py` (+51),
  `src/forge/feedback/rejection_weights.py` (+39), `src/forge/cli/healthcheck_cmd.py` (+32),
  3 test files, plus untracked `tests/invariants/test_orthogonal_family_floor_invariants.py`.
  Mitigated (flag-OFF, byte-identical claimed) but reboot-exposed.
- Ledger dirt: `IMPLEMENTATION_DECISIONS.md` (+108 lines) and `STATUS.md` (+117 lines) last
  committed 2026-06-25 (`62d8ffa`) — ~6 days of decision/status records (D216, the
  06-28/06-29 blocks) exist only in the working tree.
- Aged dirt: `PROMPT_CRUCIBLE_V22_FUNNEL_COMPARE.md` modified 06-25; untracked
  `FORGE_THROTTLE_BACKPRESSURE_PROPOSAL.md` and
  `PROMPT_CRUCIBLE_REFIT_PRIORITY_AND_WORSTQ_REGIME.md` date to Jun 16 (~15 days untracked).

### HYG-M1 (MEDIUM, → item 15): root sprawl outgrew the sweep cadence (68 root .md; the taxonomy itself is good)

— Status 2026-07-05: RESOLVED for this cycle (second sweep today: 56 records → `_archive/`,
root .md 72→16). Cadence convention still to be agreed with the operator.

- 68 root .md: 44 `PROMPT_CRUCIBLE_*`, 8 other cross-repo/agent prompts, 9
  plans/specs/drafts/research, 1 stale audit (`AUDIT.md`, 68KB, stale-BANNERED and
  taxonomy-sanctioned), 6 living ledgers. 12 files >30 days stale (mtime pre-Jun-1, e.g.
  `PROMPT_5_FORGE_V1_1_DRAFT.md`/`_REVISED.md` May 17, `FORGE_REAUDIT_FOLLOWUP_AGENT_PROMPT.md`
  May 18, `CONTRACTS_V1_2_AGENT_PROMPT.md` May 13).
- `docs/architecture.md` §"Root-file taxonomy" (lines 99–115) DOES prescribe all of this;
  archive convention exists: root `_archive/` (43 files, "periodically swept once their
  D-entry lands", D202). Sprawl conforms in KIND but not CADENCE: last sweep 2026-06-24
  (`b1d3b79`, 28 files); since then ≥10 answered relays accumulated (relval RESOLVED,
  GICS-relval REFUTED, volsurface RESULT, xsect-volevent answered, gen-levers validated
  per D215 — all still at root) plus the 12 pre-Jun-1 stragglers the D202 sweep missed.
- `FORGE_THROTTLE_BACKPRESSURE_PROPOSAL.md` is at root while its two younger siblings
  correctly live in `docs/proposals/` (19 files).

### HYG-M2 (MEDIUM, → item 16): giant living documents approaching rotation thresholds

— Status 2026-07-05: still OPEN and now PAST threshold — `IMPLEMENTATION_DECISIONS.md` is
1,006,649 bytes, over the ~1MB rotation trigger this finding set.

- `IMPLEMENTATION_DECISIONS.md` 920KB / 216 D-entries (~4.3KB avg); `STATUS.md` 438KB /
  156 blocks; `OPEN_QUESTIONS.md` 129KB / 37 Q-entries; `OPEN_PROPOSALS.md` 30KB.
- Discipline itself is strong: STATUS newest-on-top verified programmatically across all
  156 date headers (monotonically non-increasing, top block 2026-07-01); D-entry headings
  format-consistent (`## D### — date — title`) and grep-able; the two numbering anomalies
  are documented, not rot (duplicate `D071`/`D071-final` at lines 2243/2323; `D173`
  "reserved" per D174).
- Problem: >any single read window; growing per-session seek cost; only convention prevents
  mid-file edits.

### HYG-M3 (MEDIUM, → item 2): two committed features missing from MANPAGE

— Status 2026-07-05: RESOLVED (item 2 DONE — MANPAGE-sync test green; suite 1846 at D240).

- `ranker-model eval-rewire` (`@ranker_model_app.command("eval-rewire")` in
  `src/forge/cli/ranker_model_cmd.py`, commits `edb03e6`/`fdeed29`) — 0 occurrences in
  MANPAGE (HEAD or working tree). THIS is the failing test.
- `FORGE_QUALITY_RANK_MODE` (commit `92e9061`, lives in `src/forge/cli/main.py`) —
  documented only in `docs/proposals/quality-lane-rewire.md`, not MANPAGE.
- Note the uncommitted D216 diff DOES add its own knob to MANPAGE
  (`FORGE_ORTHOGONAL_FAMILY_FLOOR`, MANPAGE line 116) — discipline held for the newest
  change, missed the prior two.

### HYG-L1 (LOW, → item 4): `scratchpad/` — same as OPS-M4.

### HYG-L2 (LOW, → item 18): `docs/architecture.md` module map omits `king/`

- Module-map table (lines 34–48) lists 11 of 12 packages; add a row marked
  "retired (D190), code removed / pycache only".

### Verified HEALTHY (hygiene)

- Git history: last 30 commits cleanly conventional (`feat(scope):`/`fix:`/`docs:`/`chore:`/
  `ops:` + D-refs). No large binaries; biggest tracked files are the .md ledgers + `uv.lock`;
  `.git` 72MB, unremarkable.
- `.gitignore` covers `.hypothesis/`, all caches, `*.duckdb(.wal)`, venvs, coverage,
  `forge_data/` (verified via `git check-ignore`). Only gap: `scratchpad/`.
- Config: `config/grammar_archive/` holds v1–v22 COMPLETE, no gaps; live `grammar.yaml` is
  v22 and byte-identical to `grammar_archive/v22.yaml`; `preregistrations.jsonl` every line
  valid JSON with one consistent key-set; `auto_tightened_thresholds.yaml` in documented
  D206-retired state.
- GRAMMAR.md sync-enforcement is real: pre-commit runs `scripts/check_grammar_version_bump.py`
  + `scripts/check_grammar_doc_sync.py`; hook installed at `.git/hooks/pre-commit`; scripts
  themselves tested in `tests/integration/test_hook_scripts.py`.
- MANPAGE↔CLI spot checks 5/5 pass (`healthcheck`, `status`, `alpha-budget`,
  `run --quality-rank/--cohort-yield/--regime-gate-yield`, `grammar`/`prereg`/`ranker-model`
  sub-apps; registrations at `main.py:2566–2572`); services/timers section matches deployed units.
- Stale-doc traps systematically bannered: `docs/INDICATOR_THRESHOLDS.md` double-noted;
  `AUDIT.md`, `docs/STRATEGY_GENERATION_STATE.md`, `docs/handoffs/PROMPT_FORGE_NEXT_ACTIONS.md`,
  `docs/DECISIONS.md` all dated STALE/HISTORICAL with redirects. As-built docs bulk-refreshed
  to D200 on 06-24 (`76e7861`). No un-bannered >30-day doc asserting volatile facts found.
