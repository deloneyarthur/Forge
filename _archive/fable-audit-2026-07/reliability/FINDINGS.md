# Findings — ranked by priority (2026-07-06)

All file:line references are against HEAD `5ac7941` (clean tree, 2026-07-06).
Ranking = blast radius × likelihood, tempered by whether an incident of this class has
already happened. Each finding carries: severity, confidence that it is a real defect
(vs deliberate design missing only an alarm path), evidence, failure scenario, and a fix
sketch. Findings marked ⚠ were independently verified line-by-line by the orchestrating
session, not just by the sweep agent.

Severity: HIGH / MEDIUM / LOW. Priority tiers: P0 (fix first) → P3 (hygiene).

---

## P0 — the export-outage blind spot (silent multi-day stall class)

This class has already produced three multi-day incidents (D205 phantom in-flight depth,
D240 failed-runs never flushed, D245 asymmetric contracts bump). The two findings below are
the remaining silent paths that reproduce the same wedge, and they defeat the guards built
after those incidents.

### REL-1 ⚠ (HIGH, confidence HIGH): `_reconcile_pending_silently` swallows `QueryError` with zero logging

- `src/forge/cli/main.py:1576` — `except QueryError: return ()`. Not even warn-once. The
  docstring defers to "the rate-limit check has its own conservative path" — but that path
  is REL-2, itself fully silent.
- Trigger: Crucible's export publisher dies / disk fills / a contracts skew makes
  `gated_runs_*.json` unparseable. The direct-DuckDB fallback inside
  `consumer._fetch_crucible_runs` always fails in production (Crucible's writer holds an
  exclusive lock), so any export outage → `QueryError` on every poll.
- Failure cascade, per iteration, all silent: reconciliation no-ops → `submitted` rows never
  flip to `gated` → `_flush_failed_runs` (the D240 fix) and the aged-out flush never run →
  verdict recording stops → the §7.3 limiter blocks with `blocked: oldest in-flight batch
  … N% gated` — the exact line CLAUDE.md documents as benign backpressure. Caller cannot
  distinguish "Crucible offline" from "nothing to reconcile" (both return `()`).
- Hard-rule tension: this is the only fully-silent production catch of `QueryError`
  (CLAUDE.md: never silently caught outside test fixtures). No test pins the swallow
  (`grep _reconcile_pending_silently tests/` is empty).
- Alarm gap: the hourly healthcheck escalates to CRITICAL only after 24h of no submission,
  and its message points at the misleading block reason, not the export failure.
- Fix sketch: log a distinct per-iteration `export_read_failed` journal line (mirroring the
  D245 `inbox_rejections` pattern) + a healthcheck probe on it; optionally return a sentinel
  the caller can surface in the iteration summary. Preserve the no-crash posture.

### REL-2 ⚠ (HIGH, confidence HIGH): rate limiter swallows `QueryError` AND disables the stall/depth guards

- `src/forge/submission/rate_limiter.py:224` — `except QueryError: export_overlap = 0;
  recent = []`. No log. `RateLimitStatus` has no "export read failed" field, so
  `main.py:1860–1893` prints the ordinary `blocked: … N% gated` line.
- Compounding: the same `try` covers both the export read and the direct-DB fallback, and
  the zeroed `recent` renders BOTH the D137 stall guard and the D196 depth guard inert
  (`_evaluate_stall_guard` / `_evaluate_inflight_depth` are documented "inert when no
  decisions are readable" — rate_limiter.py:227–241). An export outage therefore disables
  the very guards built after the previous stall incidents, while blocking submission
  forever in a shape indistinguishable from normal backpressure.
- The conservative *blocking direction* is deliberate (module docstring) and
  `test_no_export_is_conservative_not_a_stall` pins the no-export case — but NOT the
  QueryError case, and nothing pins the indistinguishability.
- Fix sketch: same journal-line + healthcheck pattern as REL-1; add an
  `export_read_failed: bool` to `RateLimitStatus` so the caller prints a distinct block
  reason. Keep the conservative block.

### REL-0 (systemic note spanning REL-1/2/3/6)

All 13 export-consumer catch sites (`main.py` 742, 816, 887, 936, 983, 1030, 1083, 1150,
1204, 1264, 1329, 1576; `rate_limiter.py:224`) degrade silently or warn-once on
`QueryError`. One shared helper emitting a per-iteration, distinctly-prefixed journal line +
one healthcheck check would convert the entire class from HIGH to LOW at trivial cost.

---

## P1 — wrong production output or lost data; latent but realistic triggers

### REL-3 (MEDIUM-HIGH, confidence HIGH on the monitoring hole): warn-once weight loaders + a healthcheck that can only see 48h

- `src/forge/cli/main.py:742` (`_load_hypothesis_weights`, warn-once via module flag) and
  its EIGHT fully-silent siblings returning `{}`: `_load_regime_weights` (:816),
  `_load_bucket_weights` (:887), `_load_underlying_class_weights` (:936),
  `_load_underlying_name_weights` (:983), `_load_directional_bucket_weights` (:1030),
  `_load_orthogonal_yield_discounts` (:1083), `_load_cohort_yield_weights` (:1150),
  `_load_regime_gate_yield_weights` (:1204). All catch `(QueryError, OSError)`.
- Failure scenario: persistent export read failure → the entire learned feedback loop
  (D105/D106 weights, yield maps, cohort/regime-gate steering) silently reverts to uniform
  sampling while submissions continue. The daemon looks productive; stream quality regresses
  to cold-start. `{}` is also the legitimate cold-start value — caller-indistinguishable.
- The structural bug: `check_hypothesis_weights_fallback` in
  `src/forge/cli/healthcheck_cmd.py` greps the journal for `hypothesis_weights: degraded`,
  but the daemon logs that line ONCE PER PROCESS and the healthcheck journal window is 48h.
  Daemon uptime is weeks → a degrade older than 48h reports `hypothesis_weights: OK` while
  still active. The warn-once design defeats the monitor added specifically to catch it.
- Fix sketch: re-log the degraded state once per iteration (cheap — it's one line), or have
  healthcheck probe the live state (e.g., a state file the loader touches) instead of the
  journal.

### REL-4 ⚠ (MEDIUM blast, HIGH confidence, fires on ROUTINE deploys): SIGTERM mid-submit tears inbox-file vs DB-row

- Write order in `src/forge/submission/submitter.py:185–256` (verified): (1) `INSERT
  submissions(status='pending')` uncommitted → (2) `submit_candidate` renames
  `{config_hash}.json` into Crucible's inbox — immediately visible to Crucible's watcher →
  (3) `UPDATE → 'submitted'` → (4) pre-filter log rows → (5) `COMMIT`.
- No SIGTERM handler exists anywhere in `src/` (verified: no `import signal`), and
  `deploy/systemd/forge.service` uses the default `KillSignal=SIGTERM` — the process dies
  without unwinding, so `TimeoutStopSec=120` is inert. Every `systemctl stop forge`
  (routine in the deploy ritual) that lands in the (2)→(5) window kills the txn; DuckDB WAL
  recovery discards it. A clean SIGINT hits the same tear via the deliberate
  `except BaseException: ROLLBACK; raise` at :250–256.
- End state: inbox file delivered, zero Forge record. Consequences:
  - Crucible gates it → the export row matches no submission → silently skipped by the
    consumer (`src/forge/feedback/consumer.py:283–285`) and the verdict recorder
    (`src/forge/persistence/verdicts.py:59` known-hashes filter) → verdict permanently
    lost, Crucible compute wasted, run invisible to §7.3 depth accounting.
  - The hash is not burned → a later iteration can re-enumerate and resubmit → duplicate
    Crucible run (verified: Crucible's inbox watcher has NO config_hash dedup —
    `Crucible/src/optbt/data/inbox.py:133–235`).
  - Crash on candidate #1 (zero commits) → restart replays the same iteration/seed
    (`_next_iteration_number`, main.py:1705–1725) and rewrites the same inbox file; if
    Crucible consumed the original in the gap, direct double-submit.
- The M-10 single-transaction design (pinned by `tests/unit/test_submission/
  test_submitter.py:621`) protects only DB-side consistency; nothing pins or repairs the
  inbox-side orphan. Reversing the order would recreate the pre-M-10 burned-hash bug — the
  actual holes are the missing SIGTERM handler and the missing startup sweep.
- Fix sketch (two halves, both cheap): (a) a SIGTERM handler that converts to the existing
  KeyboardInterrupt path so the current `_submit_one` completes; (b) a startup sweep
  reconciling inbox + `processed/{hash}.json` against `submissions` before the first batch.

### REL-5 ⚠ (HIGH blast, MEDIUM defect-confidence): universe fallback — a transient read failure pins a 24-ticker pool for the process lifetime

- `src/forge/enumeration/sampler.py:246` — `except QueryError` (logged loudly, Q23/M-13
  comment documents intent) → falls back to the hardcoded 24-name
  `_FALLBACK_TIER_1_2_UNDERLYINGS` instead of the live ~152-name pool. The enclosing
  `_load_underlyings()` is `@functools.lru_cache(maxsize=1)` (sampler.py:230), so ONE
  transient read race at first universe access pins the fallback until service restart; the
  warning fires exactly once and Crucible's 6-hourly republish is never re-read.
  `StaleExportError` (export >35d old) is a `QueryError` subclass → same silent shrink.
- Blast: every batch enumerates from the wrong universe — single-name breadth, currently
  the #1 producer objective (vol_event supply per D212–D235), collapses to mega-caps.
  Mitigant: `universe_fingerprint()` (sampler.py:263) folds the actual pool into batch
  identity, so rule #6 determinism is honest. Behavior is test-pinned
  (`tests/unit/test_enumeration/test_sampler.py:1028`) — deliberate design; the defect is
  the transient→permanent conversion plus zero healthcheck coverage (healthcheck watches
  the hypothesis-weights fallback but not this one).
- Fix sketch: healthcheck probe on the fallback state (the cheap one), or drop the
  lru_cache in favor of mtime-keyed reload, or raise at startup when the export is present
  but unreadable.

### REL-6 (MEDIUM, confidence MEDIUM): trade-rate priors and promoted-configs loaders — warn-once, and NO healthcheck counterpart at all

- `src/forge/cli/main.py:1264` — `_load_trade_rate_priors` → `{}`: the expected-trades
  prefilter falls back to the activations heuristic, i.e., back toward the pre-D076 ~70%
  zero-trade-waste era. `main.py:1329` — `_fetch_promoted_configs` → `[]`: the §6.2
  prior-promotion-proximity ranking factor silently disabled.
- Same trigger and same warn-once-then-silent shape as REL-3, but unlike REL-3 the
  healthcheck has no check for either (it only watches the `hypothesis_weights:` prefix).
- Fix sketch: fold into the REL-0 shared helper.

---

## P2 — degraded quality/telemetry, exception-path leaks, lost-update races

### REL-7 ⚠ (MEDIUM, confidence MEDIUM-HIGH): submitter's over-broad catch discards the failure cause — and conflates `ConfigInvalid`

- `src/forge/submission/submitter.py:221` — `except Exception as err` around
  `submit_candidate`. Marks the row `submission_failed`, commits, returns. The exception
  type/message survive only on the in-memory `SubmissionRecord.error`; the DB UPDATE
  persists only `status`, and `main.py:2329` logs only counts. A systematic cause (e.g., a
  contracts change making every config fail Forge-side validation) shows as `failed=200`
  per batch with no reason recorded anywhere — and `ConfigInvalid` (a CLAUDE.md-flagged
  contracts exception) is reduced to the same anonymous count. Also masks programming
  errors (AttributeError/TypeError) in the submit path as "submission_failed".
- Fix sketch: persist `error` (type + message) on the row or log it structured per failure;
  consider re-raising or separately counting `ConfigInvalid`.

### REL-8 (MEDIUM, confidence HIGH on mechanism): `OPEN_PROPOSALS.md` lost updates — read-modify-rewrite vs concurrent writers

- `src/forge/feedback/proposal_writer.py:361–384`: `append_proposal` = `read_text` (:375)
  → compose → `_atomic_write` (:381) with the FIXED tmp name `OPEN_PROPOSALS.md.tmp`
  (:128–136). Three interleavings:
  (a) operator hand-edit saved between read and `os.replace` → edit silently reverted
  (window is ms per proposal, every `--consume-feedback` iteration — flag ON in the unit);
  (b) `write_loosening_proposals_to_open_proposals`
  (`src/forge/feedback/threshold_proposer.py:318–319`) appends via `open("a")` — a
  different discipline on the same file; an append inside another process's read→replace
  window is discarded;
  (c) crash between file write (:381) and the dedup DB insert (:383) → duplicate proposal
  later (cosmetic).
- Blast: this is the hard-rule-#4 loosening audit queue — lost entries mean a loosening
  proposal silently vanishes. DB-lock serialization covers daemon-vs-CLI but NOT human
  editors.
- Fix sketch: O_APPEND-only discipline for all writers (or a lockfile), per-process-unique
  tmp names.

### REL-9 (MEDIUM, confidence MEDIUM): shadow scoring's `except Exception` returns an ambiguous 0 — governance clocks fed truncated telemetry

- `src/forge/ranking/shadow.py:116` — outer `except Exception` → warn
  `shadow_scoring_failed`, `return 0`, indistinguishable from the normal "no model trained
  yet" 0. A persistent bug (feature-schema drift, artifact mismatch) stops `shadow_scores`
  accumulation → the daily `forge-ranker-eval` timer evaluates thin/stale windows →
  `streak.jsonl` PASS/FAIL (the F3/§8.6 governance clock) computed on truncated telemetry
  that steers real operator flips. The never-raises posture is deliberate and correct
  (telemetry must not block submission); inner tx handler (:105) correctly
  ROLLBACK+re-raises.
- Fix sketch: distinct return/status for the failure case + a healthcheck check on
  shadow-row freshness.

### REL-10 ⚠ (MEDIUM, confidence HIGH on path / MEDIUM on impact): `open_db` leaks the connection on the schema-ensure exception path

- `src/forge/persistence/db.py:25–45` (verified): `duckdb.connect()` succeeds, then
  `SET TimeZone` and `ensure_schema(conn)` (DDL loop) run OUTSIDE any try/finally. If
  either raises (disk-full during DDL, lock race), the open WRITE connection escapes —
  `db_connection`'s `finally` (:52–55) only wraps code after `open_db` returns. In the
  daemon, each failing iteration is caught at main.py:2725 and retried per poll → one
  GC-reliant leaked write handle per poll on a DB with a known intermittent RW-lock
  problem (a live write handle blocks every other opener until finalized).
- Fix sketch: wrap post-connect setup in try/except → `conn.close(); raise`. Three lines.

### REL-11 (MEDIUM single-event, confidence HIGH on mechanism): 5.5 GB tmpfs snapshot orphans on OOM/SIGKILL; ranker-eval snapshot unvalidated

- `scripts/daily_ranker_eval.sh:38,51–52`: `SNAP=/tmp/forge_ranker_eval_$$.db`, `trap
  cleanup EXIT`. `/tmp` is tmpfs on this box (61 GB) → each daily run holds a ~5.5 GB DB
  copy IN RAM. The trap does not survive SIGKILL (OOM-killer is plausible while training
  against the snapshot); PID-suffixed names never collide so no later run cleans an
  orphan → 5.5 GB of RAM held until reboot. Same pattern on disk in
  `scripts/backup_forge_db.sh:49–51` (dot-prefixed in-progress file the retention globs
  at :129–130 never prune).
- Compounding weaknesses in the same script: the snapshot `cp` (:59–62) has no validation
  and no retry (the backup script has both), and the script runs `set -uo pipefail`
  WITHOUT `-e` — a torn copy makes train/eval fail while the script continues → a streak
  checkpoint silently skipped, next run's "fresh window" doubles (distorts the F3/§8.6
  clocks). Boot-after-downtime makes collisions likelier: `Persistent=true` on the timers
  fires backup cp + eval cp + daemon write burst concurrently.
- Fix sketch: startup sweep for `/tmp/forge_ranker_eval_*.db` not owned by a live PID;
  `set -e` (or explicit exit-on-fail); borrow the backup script's validate+retry.

### REL-12 (MEDIUM-LOW, confidence MEDIUM): corrupt model artifact → stale model or a WRONG-CAUSE message; models dir grows unbounded and is re-parsed 3×+ per iteration

- `src/forge/ranking/model.py:425` / `:784` — corrupt newest artifact → warn + silently
  serve the previous day's model (these feed the LIVE F3 prior and gate-tail ordering at
  main.py:2095/2129, not just telemetry). All corrupt → `None` → F3 reverts to the legacy
  Jaccard prior with the message `"f3_ranker: Jaccard prior (no verdict model yet)"`
  (main.py:2107–2109) — asserting a cause that is false when the cause is corruption.
- Growth: `load_latest_model`/`load_latest_robustness_model` glob and PARSE EVERY
  `*_model_*.json` to pick the newest; the timer publishes ~2/day and nothing prunes
  (46 files at audit time); called 3×+ per iteration (main.py:2095, :2129, shadow.py:61,67).
  (Overlaps pipeline-performance parse-once work.)
- Fix sketch: fix the message string; add retention (keep last N) to the timer script;
  pick-newest by filename without full parse.

### REL-13 (MEDIUM-LOW, confidence MEDIUM): preregistration registry — corrupt-line skip + full rewrite = permanent silent deletion

- `src/forge/feedback/preregistration.py:125` — `json.JSONDecodeError → continue` on read;
  `resolve_preregistration` (:152–160) then REWRITES the whole file from parsed entries →
  a corrupt line (hand-edit, merge artifact) in the git-tracked tamper-evidence registry is
  permanently deleted on the next resolve (recoverable only via git archaeology). Related:
  `:71` — malformed `cohort_cut` → `ValueError → None` → the claim is forever
  "insufficient" with no error; the operator waits for evidence that can never accrue. The
  rewrite itself is also non-atomic (`:160`, plain write).
- Fix sketch: refuse to rewrite when any line failed to parse; atomic write; warn on the
  `ValueError` path.

### REL-14 (LOW-MEDIUM, confidence HIGH): grammar.yaml — non-atomic revert write + loader double-read TOCTOU, under hot-reread

- `src/forge/cli/grammar_cmd.py:400` — `forge grammar revert` writes grammar.yaml with
  plain `write_text` (truncate-then-write) in the live tree the daemon re-reads every
  iteration (main.py:1824). Mid-write daemon read → one lost iteration (self-heals); crash
  mid-write → corrupted grammar.yaml → EVERY subsequent iteration fails until manual
  repair (daemon up, repeating journal error). Loader double-read:
  `src/forge/grammar/loader.py:78` (`read_text` → parse) vs `:134` (`read_bytes` → archive
  byte-comparison) — an edit between the two reads makes the version check judge different
  bytes than were parsed (loud, transient).
- Important negative result (verified): the rule-#6 determinism invariant is NOT breakable
  by hot-reload mid-batch — grammar/registry/calibration load once per iteration
  (main.py:1824–1829) and feed enumeration, `mint_batch_id`, and summaries consistently;
  the two lru_caches pin the shadow inputs so `enumeration_inputs_hash()` provably matches
  what the sampler consumed.
- Fix sketch: tmp+rename in `grammar_cmd` revert; single `read_bytes` in the loader, parse
  and compare the same bytes.

### REL-15 (MEDIUM-latent, confidence MEDIUM): the D216 lever's env knob silently drops malformed tokens

- `src/forge/cli/main.py:588` — `_orthogonal_family_floors` parsing
  `FORGE_ORTHOGONAL_FAMILY_FLOOR`: `ValueError → continue` and no-`=` tokens skipped, NO
  warning — unlike siblings `_rewire_p_floor` (:615) and
  `_resolve_exploration_holdout_frac` (:647) which warn-once. A typo
  (`volatility_event=0.2O`) makes the flag-ON deploy silently behave flag-OFF; the A/B
  window elapses measuring nothing. This is the one env knob tied to the current
  promotion-critical lever (single-name vol_event supply, D216).
- Fix sketch: warn-once like its siblings. Two lines.

---

## P3 — hygiene, slow burns, theoretical races

### REL-16 (LOW today / latent, confidence HIGH): `FeatureCacheClient` Unix socket opened every iteration, never closed

- `src/forge/cli/main.py:195–208` constructs the contracts `FeatureCacheClient` (docstring:
  "Caller owns construction + close()"); it is buried in `CrucibleFeatureCache` (no close
  method), built per iteration at main.py:1455, dropped on return. CPython refcounting
  rescues it today; the release is nondeterministic, the writer-rejected error path leaves
  the socket open on the dropped object, and any future refactor that caches the client
  becomes a real fd leak. Contrast: `scripts/probe_option_momentum_min_months.py:287–302`
  closes the same client in `finally`.
- Fix sketch: add `close()`/context-manager to `CrucibleFeatureCache`, close per iteration.

### REL-17 (LOW, confidence HIGH): orphaned `{hash}.json.tmp` in Crucible's inbox are never cleaned by either side

- Writer: `crucible_contracts/queries.py:211–213` (tmp write → rename, no fsync). Crash
  between write and rename leaves a per-hash `.tmp` that is never overwritten (the unique
  index means the hash is rarely re-picked), Crucible's watcher skips `.tmp` forever
  (`Crucible/src/optbt/data/inbox.py:85–87`), nothing in Forge sweeps them, and inbox-depth
  metrics glob `*.json` so they are invisible. Zero on disk at audit time (verified).
  The no-fsync also means power-loss can publish an EMPTY `{hash}.json` → Crucible
  parse-fails it into `errors/` while Forge's row says `submitted` → retired only by the
  5-day age-out flush.
- Fix sketch: fold into the REL-4 startup sweep.

### REL-18 (LOW-MEDIUM over months, confidence HIGH): unbounded-growth patterns in the daemon's per-iteration working set

- `main.py:1387–1400` `_load_prior_structural_fingerprints`: full-table
  `SELECT config_json FROM submissions` + Pydantic-parse of every historical config, EVERY
  iteration — peak memory and iteration time ratchet with total lifetime submissions.
  Similar shape: `persistence/verdicts.py:48–50` full DISTINCT scan per poll; the 10k-row
  gated export parsed 3×+ per iteration. Append-only growth elsewhere: `OPEN_PROPOSALS.md`
  fully rewritten per appended proposal; streak `.jsonl`s re-read whole (bounded-slow).
  (Overlaps pipeline-performance P1-1/P4-8 and codebase-quality SRC-M1 — land once.)

### REL-19 (LOW today, confidence HIGH it's a gap): `_auto_tightenings` corrupt-YAML swallow — silent AND pinned by lru_cache

- `src/forge/enumeration/indicator_thresholds.py:440` — `except (OSError, yaml.YAMLError):
  return {}`, zero logging (verified), then `@lru_cache` pins the empty result for the
  process lifetime. Fallback direction is safe (D031 baselines; can't loosen — rule #4) and
  `auto_tightenings_fingerprint()` records the actual state (rule #6 honest). LOW today only
  because D206 emptied the file; returns to MEDIUM if the proposer lane revives. The
  transient→permanent lru_cache pattern is shared with REL-5.
- Fix sketch: one structlog warning distinguishing corrupt from absent.

### REL-20 (LOW, confidence MEDIUM): backup/restore edge cases

- `scripts/backup_forge_db.sh:79–96`: validation scans ONE table (`count(*) from
  submissions`) — a copy torn elsewhere can publish as a "good" backup; `cp` takes
  `forge.db` without the WAL → backups silently lack un-checkpointed txns
  (consistent-but-stale; undocumented). Newest-by-mtime export selection
  (`src/forge/persistence/registry_loader.py:53–57`, contracts queries.py:262–265) fails
  under mtime-preserving restore (`cp -p`/`rsync -a` skips NEWER content) or a backwards
  clock step; no name-timestamp cross-check.

### REL-21 (LOW, grouped): small swallows and cosmetic races — for completeness

- `src/forge/feedback/auto_tune.py:120` — `ValueError → continue` parsing `step_pct=` out
  of audit rows silently UNDERCOUNTS the §8.4 cumulative-tightening budget (fail-open is
  the wrong default for a budget guard; corruption source unlikely).
- Per-row parse skips with no counter (all deliberate defensive reads of Forge's own JSON):
  `feedback/trade_rate_priors.py:115`, `feedback/threshold_proposer.py:99`,
  `cli/main.py:1396` (novelty dedup — a malformed legacy row lets a structural
  near-duplicate re-enumerate; exact dupes still blocked by the unique index),
  `feedback/proposal_writer.py:242`, `cli/status_cmd.py:246`,
  `cli/healthcheck_cmd.py:407`, `cli/grammar_cmd.py:73`.
- `cli/main.py:1544` / `:2306` — over-broad but logged-per-occurrence catches around the
  audit-row self-heal and the funnel export (deliberate degrade; funnel is non-fatal by
  design). `main.py:2725` — the loop's `except Exception` logs every failure and re-raises
  `KeyboardInterrupt`/`SchemaVersionMismatch` (:2721), but N consecutive failed iterations
  never escalate beyond log lines — no failure counter.
- Ghost `batch_summaries` row after a crash-then-input-roll (permanent zero-candidate row,
  excluded from rolling rates). `grammar/path_resolver.py:89` sugar-filter item skip
  (unreachable with homogeneous Pydantic lists).
  `scripts/probe_option_momentum_min_months.py:261` best-effort provenance stamp (`""` on
  failure, visible in artifact).
- Theoretical-only (DB file lock precludes): `_insert_batch_summary` SELECT-then-INSERT
  TOCTOU (`submitter.py:98–128`); concurrent identical-config `submit_candidate` fixed tmp
  name collision. Daemon-vs-operator duplicate iteration numbers self-heal via the unique
  index and are invariant-pinned (`tests/invariants/test_phase4_invariants.py:106,131,230`).

---

## Verified healthy (explicit negative results)

- **No threading, no asyncio, no `Popen`** — the unhandled-promise-rejection class has no
  analogue beyond what is reported above. All 7 subprocess sites are `subprocess.run` with
  timeouts, `capture_output`, and checked return codes.
- **No bare `except:`, no `contextlib.suppress` anywhere in `src/` or `scripts/`.**
- **Zero catches of `SchemaVersionMismatch`** (the loop explicitly re-raises it); zero
  catches of `ConfigInvalid` by name (but see REL-7's `except Exception` conflation).
- **`core/`, `config/`, `persistence/` contain ZERO exception handlers** — all errors
  propagate to callers.
- **All ~40 `db_connection` call sites are `with`-managed**; `db_connection` closes in
  `finally`; the only gap is inside `open_db` itself (REL-10). Scripts with direct
  `duckdb.connect` close in `finally`.
- **All 5 `open(` sites in `src/` use `with`**; scripts use `read_text`/`write_text`; no
  `json.load(open(...))`.
- **No logging-handler accumulation** (one configure site, called once per process); both
  `lru_cache`s bounded at maxsize=1 (their staleness is REL-5/REL-19, not a memory issue).
- **No state survives daemon iterations** except 6 warn-once bools and the 2 caches — the
  rebuild-everything/open-use-close pattern is sound.
- **Atomic writers on both sides of the export IPC** (Crucible `_atomic_write_json`
  tmp+`Path.replace` same-dir; contracts inbox tmp+rename same-dir) — half-written reads
  cannot occur in normal operation; `*.json` globs never match `.tmp`.
- **Determinism (rule #6) not breakable by hot-reload mid-batch** — single load per
  iteration; fingerprints fold actual degraded states into batch identity (REL-5/REL-19).
- **Submission idempotency is INSERT-first** (constraint-catch, not check-then-insert) —
  the correct pattern, no TOCTOU window.
- **Submitter and shadow transaction discipline is exemplary** (BEGIN/COMMIT with
  `BaseException → ROLLBACK+reraise`); the reconciler's two-step flushes are idempotent
  (`WHERE status='submitted'`, `INSERT OR IGNORE`) and serialized by the DB file lock.
- **Timers cannot collide with the daemon on the DB**: healthcheck/status never open it
  (journal + filesystem only); backup and ranker-eval `cp` the file without the duckdb
  lock. Inbox writes happen only while the daemon holds the DB lock, so lock contention
  can never tear inbox-vs-DB — only process death can (REL-4).
- **Model artifact publish/consume is well defended**: staging dir + same-fs `mv`;
  selection by embedded `(trained_through, model_id)`, not mtime; corrupt files skipped
  with a warning (message bug aside — REL-12).
- `deploy_preflight.sh` is genuinely read-only (no locks, temps, or background jobs).
- Zero orphaned `.tmp` files in the inbox and zero orphaned snapshots in `/tmp` at audit
  time (REL-11/REL-17 are about the unswept failure path, not a current mess).

## Coverage appendix

- Except clauses read in full context: 46/46 production loop (`cli/` 35, `submission/` 4,
  `feedback/` 7, `funnel/` 0) + 22/22 support (`grammar/` 11, `enumeration/` 3,
  `prefilters/` 1, `ranking/` 5, `scripts/*.py` 2, `core|config|persistence` 0) = **68/68**.
- Resource inventory: 5 direct `duckdb.connect` sites + ~40 `db_connection` call sites;
  5 `open(` sites in src, 0 in scripts; 7 subprocess sites; 1 logging-configure site;
  2 lru_caches; 1 Unix-socket client. Shell: 5 scripts read (backup, ranker-eval,
  preflight, setup, stage).
- Cross-system reads: `crucible_contracts` `submit_candidate`/queries writers and
  Crucible's `inbox.py` watcher + `exports.py` writers were read to trace both ends of
  every IPC edge.
- Method: four parallel sweep agents; every P0/P1 finding and REL-7/REL-10 re-verified
  line-by-line by the orchestrating session (marked ⚠).
