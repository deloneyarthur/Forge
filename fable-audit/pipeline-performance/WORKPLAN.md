# Workplan — pipeline-performance audit 2026-07-01

Execute in the order recommended in `README.md`. Every item: TDD first, one module +
tests per commit, D-entry + STATUS.md block, deploy via `docs/tasks/deploy.md`.
Findings references (F#) → `FINDINGS.md`; measured numbers → `00-BASELINE.md`.
None of these items change enumeration output, §7.3 blocking semantics, grammar, or the
gate. Status boxes are for the executing agent to tick.

> Status reconciled 2026-07-05 against IMPLEMENTATION_DECISIONS.md D219–D240, the code, and
> the live journal. P0-1..P0-3 and P3-1/P3-3/P3-4 are DONE-deployed (annotations inline).
> Journal now: submit=4.7s, reconcile=2.0s, weights=17s (P1-1 open), prefetch=141s —
> prefetch is now the dominant per-batch cost (P2-1).

---

## P0-1 — Bulk-stage the rejected-rows write (F1) `[x]`

— DONE-deployed (D219, commit `18a30eb`, 2026-07-02; verified 2026-07-05). Shipped via the
workplan's sanctioned alternative below: the per-row rejected-rows write was DELETED (zero
readers; aggregates stay in `batch_summaries`), not CSV-staged. Journal now submit=4.7s
(was 195–202s). P1-2's retention decision covers the existing rows.

**Goal:** submit phase 195–202s → single-digit seconds; −~3.4M fsyncs/day.
**Module:** `src/forge/submission/pre_filter_logger.py` (`record_pre_filter_logs_for_rejected`).

Fix spec:
- Replace the bare `db.executemany` (~31k rows) with bulk staging: write the rows to a
  temp CSV (std-lib `csv`, QUOTE_ALL — `details_json` contains commas/quotes) in a
  private temp dir, then one
  `INSERT INTO pre_filter_logs SELECT ... FROM read_csv(<path>, columns={...explicit
  schema...})`, then delete the temp file. Measured: **0.14s for 27.2k rows** vs 28.8s
  CPU + ~160s fsync as-is.
- Column order/types must match `persistence/schemas.py:75-83` exactly; keep the
  uuid4-per-row id generation as-is (not §13.4-relevant).
- Keep the function signature (call site `main.py:2115`).

Do NOT (measured, rejected):
- Wrap the existing executemany in one transaction — **105.8s, WORSE** (txn-local
  version-chain cost in duckdb 1.5.2).
- Chunked multi-row `VALUES` — 15.8s (parse cost scales with placeholders).
- polars/pyarrow `register()` path — pyarrow is not installed; don't add a dep for this.

Alternative worth surfacing to the operator (merges with P1-2): stop writing per-row
rejected telemetry entirely — zero readers exist and `batch_summaries` already carries
the aggregates. If the operator picks that, P0-1 shrinks to deleting the call and P1-2's
retention decision covers the existing rows.

Tests: unit — same rows land byte-equal vs the old path on a temp DB (round-trip
equality incl. `details_json` edge cases: quotes, newlines, unicode, NULLs); keep the
existing pre_filter_logger tests green.
Verify after deploy: journal `phase_timings` submit < 15s; row counts per batch
unchanged (compare a batch's `pre_filter_logs` count on a DB snapshot).
Effort S–M. Risk: CSV quoting subtleties — the round-trip test is the guard.

---

## P0-2 — Delta-first verdict insert (F2) `[x]`

— DONE-deployed (commit `2d601a0`, 2026-07-02; verified 2026-07-05). `persistence/verdicts.py`
delta-first insert as specced; journal now reconcile=2.0s (was 30–37s).

**Goal:** reconcile −17–20s/pass (paid by ALL ~467 iterations/day).
**Module:** `src/forge/persistence/verdicts.py` (`record_verdicts`).

Fix spec:
- Before building rows: fetch existing ids window-bounded —
  `SELECT crucible_run_id FROM verdicts WHERE decided_at >= <min(decided_at) over the
  export batch>` (~10k ids, ~50ms) — into a Python set; skip rows whose id is present.
  Build gate-results JSON (`model_dump`/`json.dumps`, verdicts.py:59-62) ONLY for the
  survivors (~0–130 rows). Keep the final `INSERT OR IGNORE` as the race-safe backstop.
- Preserve append-only semantics (PK on run_id; D111 verdict history) — this only
  avoids re-staging rows that already exist.

Tests: unit — (a) fresh rows insert identically to the old path; (b) fully-idempotent
second call inserts nothing and is fast; (c) mixed new/old; (d) end-state equality
old-vs-new implementation on the same input.
Verify after deploy: `phase_timings` reconcile drops by ~15–20s; `reconciled:` journal
lines unchanged in shape.
Effort S.

---

## P0-3 — Skip the no-op UPDATE sweep in reconcile (F4) `[x]`

— DONE-deployed (commit `bf822c3`, 2026-07-02; verified 2026-07-05). `consumer.py` now skips
non-submitted rows in the matched loop.

**Goal:** reconcile −3–6s/pass.
**Module:** `src/forge/feedback/consumer.py` (`consume_batch_results` matched loop).

Fix spec:
- consumer.py:307-311: the loop already has `_status` from `_load_submissions` (same
  connection, same pass) — add `if _status != "submitted": continue` before
  `_update_submission_to_gated`. Exactly the rows the `WHERE status='submitted'` clause
  would no-op are skipped; DB end-state identical. Optionally batch the remaining few
  UPDATEs set-wise (`WHERE config_hash IN (...) AND status='submitted'`) — not required.
- Preserve the D046/H-2 return contract of `reconcile_all_pending` (a patched seam).

Tests: existing consumer idempotency tests must pass unchanged; add one asserting a
row already `gated` is not re-updated (e.g. via an UPDATE-counting connection wrapper)
and end-state equality.
Verify: reconcile ≈3–10s total once P0-2+P0-3 are in; blocked-iteration gap (iteration
marker → `blocked:` line) shrinks from ~31–35s to ~3–5s.
Effort S.

---

## P1-1 — Parse the gated export once per iteration (F3, F14, F15) `[ ]`

— Still OPEN (verified 2026-07-05: no code trace). The D234 `weights=` bucket now makes the
cost visible — journal weights=17s — so this is the next-biggest in-process win after P0.

**Goal:** −~10s/full iteration + snapshot-consistent weights; −~1.7s/blocked iteration.
**Modules:** `src/forge/cli/main.py` (loaders + iteration wiring),
`src/forge/submission/rate_limiter.py`, call into `feedback/consumer.py` (no logic change).

Fix spec:
- Parse once near the top of the iteration (reconcile already holds the parsed list —
  `consumer.py:449`; hoist or return it) and thread it through:
  - each `_load_*` weight loader (main.py:599, 673, 744, 793, 840, 887, 1007, 1061,
    1123) gains an optional `gated_runs: Sequence[GatedRun] | None = None` kwarg;
    `None` → current self-loading behavior (preserves the ~10 monkeypatching test
    files, D065/D105/D106). The underlying `compute_*` functions in
    `feedback/rejection_weights.py` / `trade_rate_priors.py` ALREADY accept
    `gated_runs` — this is wrapper plumbing only.
  - `check_rate_limit` (rate_limiter.py:218) — same optional-kwarg pattern.
  - the post-submit `consume_batch_results` call (main.py:1500) — pass `crucible_runs=`
    (the parameter already exists, D046); better: pass the already-built `BatchFeedback`
    selected at main.py:2162-2166 instead of re-consuming (F15).
- Opportunistic (same commit or follow-up): let the loaders share one DB connection
  instead of one write-mode open (+DDL) each; and reduce `check_rate_limit`'s three
  opens (rate_limiter.py:158/294/344) to one passed-in connection.

Ritual: this is a **feedback change** (`docs/tasks/feedback-change.md`) — warm-path
weight values can shift because all loaders now see the reconcile-time snapshot instead
of a possibly ~65s-newer file. Cold-start byte-identity (hard rule #6) holds trivially
(no exports → `{}` either way) — state that in the D-entry, and run the cold-start
determinism goldens.
Tests: each loader old-path vs passed-list equality on a fixture export; monkeypatch
seams untouched (existing CLI tests green without edits).
Verify: with P3-1's `weights=` bucket in place, the bucket drops from ~20s to ~2s.
Effort S–M.

---

## P1-2 — `pre_filter_logs` growth policy (F7, F8) — OPERATOR DECISION `[ ]`

— PARTIAL (verified 2026-07-05): the retention DECISION is made — option (a), stop per-row
rejected writes, chosen and shipped with D219 (`18a30eb`, 2026-07-02), so daily growth is
stopped. Still OPEN: one-time compaction of the existing GBs, confirm+delete the stray 4.5GB
`~/forge_data/forge.db.bak-pre-flush-20260624`, and optional zstd backup compression.

**Goal:** stop ~200MB/day DB growth; shrink backups (46GB → bounded).

Present these options to the operator (do not pick unilaterally — data-lifecycle):
- (a) **Stop per-row rejected writes** (cleanest; merges with P0-1's alternative).
  Evidence for safety: zero readers in src/ and scripts/; aggregates already in
  `batch_summaries.prefilter_rejections{,_by_hypothesis}` (submitter.py:398-407).
  Confirm the D076 empirical trade-rate priors never need row-level rejected data
  (they read gated runs + submissions, not this table — verify at decision time).
- (b) Retention: nightly `DELETE FROM pre_filter_logs WHERE evaluated_at < utc_now() -
  INTERVAL N days` + `CHECKPOINT` (e.g. in `scripts/backup_forge_db.sh`'s timer or a
  new one). NOTE: DuckDB does not shrink the file on DELETE — schedule a ONE-TIME
  offline compaction (copy-table-rebuild or EXPORT/IMPORT) during a deploy window to
  reclaim the ~2GB+.
- (c) Archive-to-parquet then delete (keeps history off-DB).
- Housekeeping regardless: confirm + delete the stray
  `~/forge_data/forge.db.bak-pre-flush-20260624` (4.5GB, outside KEEP=14 rotation);
  optionally zstd-compress backups (3–5×).

Effort M (mostly coordination). Gate: operator + D-entry.

---

## P2-1 — Crucible relay: lazy chain-load in the feature writer (F10, F18) `[ ]`

— Still OPEN (verified 2026-07-05: no code trace — neither the Forge-side hit/miss telemetry
nor the relay prompt exists). With P0 done, prefetch=141s is now the DOMINANT per-batch cost;
this item's priority has risen accordingly.

**Goal:** prefetch −90–160s/batch. **This is Crucible's code — Forge relays (rule #2).**

Steps:
1. Forge-side FIRST (S, ships with any deploy): accumulate Σ`cache_hits`/Σ`cache_misses`
   (+ per-underlying misses) in `prefetch_for_batch` and add them to the existing
   `feature_cache_prefetch_batch` log line (crucible_feature_cache.py:317-327). The
   response fields already exist (`crucible_contracts/.../feature_cache.py:74-77`) and
   are currently discarded. This quantifies the ask with production numbers.
2. Draft `PROMPT_CRUCIBLE_FEATURE_CACHE_PERF.md` at repo root per
   `docs/tasks/crucible-handoff.md`, containing: the F10 evidence (their
   `feature_cache.py:795-826` unconditional bars/trades/chain load before consulting the
   SQLite feature store; `chain_cache.py:63` max_underlyings=3 vs Forge's 124-underlying
   sweep every ~13 min), the measured 138–215s prefetch vs their own ~150–250ms
   pure-hit claim (db_writer.py:107), and the ask: **defer chain loading to the first
   value-series compute that actually needs chains** (their value-series/activation
   caches at feature_cache.py:899-1150 mostly hit). Byte-identical outputs — only load
   ordering changes. Include the step-1 hit/miss numbers.
3. Do NOT implement pipelining yet (F13): concurrent distinct-underlying misses each
   hold ~800MB chain frames transiently — the D179 writer-OOM class. Revisit at ≤4
   connections only AFTER lazy loading lands, with Crucible coordination.

Effort: S (Forge telemetry) + relay latency. Operator carries the prompt to Crucible.

---

## P2-2 — Persistent feature cache across iterations (F11, F20) `[ ]`

**Goal:** prefetch −25–40s/batch; −~124 writer requests/batch (relieves Crucible's
writer); −200–350MB/batch allocation churn.
**Modules:** `src/forge/cli/main.py` (`_build_feature_cache` / `cmd_run` wiring),
`src/forge/prefilters/crucible_feature_cache.py`.

Fix spec:
- Construct the `CrucibleFeatureCache` + `FeatureCacheClient` once at `cmd_run` scope
  and pass down; keep `_build_feature_cache`'s signature (monkeypatched seam) — let it
  return the cached instance when the flag is on.
- Flag-gated: `FORGE_PERSISTENT_FEATURE_CACHE` env (default OFF = byte-identical current
  behavior), matching house style for behavior-adjacent flips (cf. D193's kill-switch
  pattern).
- Invalidation: rebuild when `(registry.data_history_days, registry.data_start_date)`
  changes (window definition — crucible_feature_cache.py:111-117, 245-252; the daemon
  hot-reloads the registry by mtime) AND on a daily boundary (historical restatements
  happen — `~/optbt_data/_repull_logs`).
- **MANDATORY: clear `_activations` at the start of each iteration** while keeping
  `_returns`/`_regimes`/`_window_loaded_for`. Rationale in F11 (fresh 4-dp thresholds →
  ~10k new keys/batch → ~100–200MB/batch unbounded growth = OOM within ~a day).
- Keep the `--require-real-cache` fail-loud posture (2026-05-28 RCA) — a persistent
  cache must not mask a dead writer: the per-batch `missing_dates` fetch and probe
  behavior stay as-is.
- Do NOT merge the 2-request-per-underlying split (see README "already good").
- Bundled micro-fixes (same module, optional): intern table `dict[str, date]` for
  `date.fromisoformat`; memoize `signal_content_key` per spec object (F20).

Tests: invariant — warm-cache vs cold-cache battery results byte-equal on a fixture
writer (same values → same filter verdicts); `_activations` cleared per iteration
(assert size); flag OFF → current code path (existing tests green).
Verify after deploy (flag ON via the unit file, operator-gated): prefetch < ~80s
(remaining = activations + writer floor until P2-1 lands); RSS stable over 24h
(`systemctl --user show forge.service -p MemoryCurrent` — compare 3.9G baseline).
Effort M.

---

## P2-3 — Memoize `permutation_test` per batch (F12) `[ ]`

— Still OPEN, but its stated blocker is CLEARED (noted 2026-07-05): the permutation-semantics
fix this memo had to wait for (strategy-audit P1-1) is built (D224) and FLIPPED live
2026-07-04 (D238) — the memo can now pin the correct computation and is buildable.

**Goal:** battery 36–50s → ~5–10s.
**Module:** `src/forge/prefilters/permutation_test.py` (+ `FilterContext` if chosen).

Fix spec:
- Per-batch memo (attach to `FilterContext` — one is built per battery run — or a
  module-level dict keyed by `id(ctx)`, cleared per batch):
  (a) `all_returns: list[float]` per underlying (hoists `_full_window` + returns-dict +
  `list(...)` ≈ 1.1ms × 3,750);
  (b) permuted-sums tuple keyed `(underlying, effective_n)` — 100 sums computed once per
  distinct key; `p_value` = fraction of memoized sums ≥ `real_notional`.
- **Byte-identical by construction** — the per-config RNG is re-seeded identically
  (seed.py:27-29) so draws depend only on `(len(all_returns), effective_n)`, and the
  returns population order is chronologically stable (crucible_feature_cache.py:440).
  Rule #8 intact (still SeedHierarchy-derived; no new RNG).

Tests (BEFORE the change, per TDD): invariant test in `tests/invariants/` — memoized vs
unmemoized `p_value` equality over a Hypothesis-generated spread of configs sharing and
not sharing `(underlying, effective_n)`; plus a fixture asserting identical
accept/reject verdicts on a recorded batch.
Verify: `phase_timings` battery < ~15s; per-filter rejection counts unchanged in the
journal (permutation_test ≈ 2.5–2.6k/batch).
Effort S–M. Risk: low, but this is a §5 prefilter — verdict changes would alter
submissions, hence the equality tests are non-negotiable.

---

## P2-4 — Incremental novelty-fingerprint cache (F5) `[ ]`

**Goal:** −~6s CPU and −~300MB transient per full iteration; kills the linear growth.
**Module:** `src/forge/cli/main.py` (`_load_prior_structural_fingerprints` + a small
process-scope holder; do NOT restructure the function — add a helper).

Fix spec:
- Process-lifetime state: `(watermark, fingerprint_set)` where watermark =
  `max(submitted_at)` (or max rowid) seen. Per iteration: `SELECT config_json FROM
  submissions WHERE submitted_at > ?`, fingerprint only the new rows, update the set;
  also add the just-submitted batch's own fingerprints in-process after submit (saves
  next iteration's query finding them). Cold start = full scan once (unchanged
  behavior) → resulting set content-identical at every iteration → novelty verdicts
  identical (rule #6 safe).
- Fix the stale docstring ("~4k rows … milliseconds") while there.
- Heavier alternative (only if the operator prefers durability over process state):
  persist the fingerprint as a submissions column at submit time — schema change,
  operator-gated; not needed for the win.

Tests: invariant — cached-set vs fresh-full-scan set equality after simulated
multi-iteration inserts (including same-timestamp edge rows — use `>=` + id dedup or
rowid watermark to avoid boundary loss; test that edge explicitly).
Verify: with P3-1's bucket, the fingerprint stanza drops to ~0; full-iteration wall
−5–8s.
Effort S–M.

---

## P3 — hygiene bundle (each its own small commit)

- **P3-1 `[x]` `weights=` timings bucket (F6) — DO FIRST.** — DONE-deployed (D234, commit
  `3acc66b`, 2026-07-02; `weights=` bucket live in the journal, verified 2026-07-05). Wrap main.py:1758-1878 (and
  ideally the :1226-1330 fingerprints/cache-build stanza as e.g. `prep=`) with timer
  entries; extend the fixed key order at main.py:365-374. Journal-format change → update
  `docs/MANPAGE.md`'s phase_timings description in the same commit (docs routing rule).
  Effort: trivial; unlocks verification of P1-1/P2-4.
- **P3-2 `[ ]` Adaptive blocked sleep (F16).** In `cmd_run`'s loop (main.py:2517-2560):
  when `_run_one_iteration` returns "blocked", escalate sleep 60→120→240→cap 600; reset
  on any other status. §7.3 semantics untouched (only poll frequency); worst case adds
  ≤10 min latency to noticing "unblocked" — negligible vs the 8-min batch. Do NOT
  instead raise `poll_interval_seconds` globally (would slow unblocked cadence 30–40%).
- **P3-3 `[x]` Shrink the prefetch coverage log (F19).** — DONE-deployed (D234, commit
  `0068f44`, 2026-07-02; verified 2026-07-05). crucible_feature_cache.py:
  317-330 — replace the two full 124-ticker dicts + ticker list with aggregates:
  `n_underlyings`, `n_full_coverage`, `below_full=[TICKER:rows,...]` (only tickers below
  max), keep `data_unavailable` verbatim (M-5 intent) and the event name (grepped by
  operators/tools). ~70% of journal volume.
- **P3-4 `[x]` Single-txn shadow scores (F9).** — DONE-deployed (commit `af4b1a7`,
  2026-07-02; verified 2026-07-05). shadow.py:75-95 — wrap the loop in one
  transaction (or executemany + txn); MUST keep the never-raises posture (:104-106).
- **P3-5 `[ ]` Rate-limiter connection reuse (F14).** — Deliberately DEFERRED by D234
  (2026-07-02): "do it with P1-1" so §7.3 block decisions stay byte-identical. Collapse the three
  `db_connection` opens to one (pass a connection in, optional param); combine with
  P1-1's `gated_runs=` kwarg. Keep the three block-reason evaluations and their journal
  lines byte-identical.

---

## P4 — scaling ledger (schedule; none urgent — details in FINDINGS F21–F23)

- **P4-1 `[ ]`** Trainer window cap (operator-gated — changes the trained model) +
  stop building the frame twice nightly (`daily_ranker_eval.sh:66,84` — build once,
  train both targets from it). Interim pure-perf: columnar (polars) frame build.
- **P4-2 `[ ]`** Sparsity-preserving standardization in `_fit_irls`/`_solve_ridge`
  (fold mean/std into the algebra; numeric-equivalence tests; ~5–8× train speed).
- **P4-3 `[ ]`** Cap the *cumulative* eval prints at trailing 30–60d (telemetry-only).
- **P4-4 `[ ]`** `compute_mature_arms`: GROUP BY `config_hash` + monotone mature-set
  cache (content-identical result).
- **P4-5 `[ ]`** Model-artifact loader: newest-first short-circuit preserving the exact
  `(trained_through, model_id)` tiebreak; prune >N-day artifacts; one load/iteration
  shared by F3/quality/shadow closures.
- **P4-6 `[ ]`** Diversifier O(K·P) rewrite ONLY if batch_size is ever raised —
  golden-compare property test mandatory (selection order = submission order).
- **P4-7 `[ ]`** Funnel version map windowing — needs Crucible sign-off (D096 consumer).
- **P4-8 `[ ]`** `_iter_hypothesis_outcomes`: restrict like `_component_rate_sums` or
  deprecate (overlaps codebase-quality audit's dead-code item — land once).

---

## Expected end-state after P0–P2 (verify against 00-BASELINE.md)

| Metric | Before | After |
|---|---|---|
| Full iteration work | ~468s | ~200–230s (prefetch-dominated until P2-1 lands Crucible-side) |
| Blocked iteration work | ~33s | ~3–5s |
| `phase_timings` submit | 195–202s | < 10s |
| `phase_timings` reconcile | 30–37s | ~3–10s |
| `phase_timings` battery | 36–50s | ~5–15s |
| Daemon CPU | ~12.6 h/day | ~2–3 h/day |
| fsyncs | ~3.4M/day | ~thousands/day |
| forge.db growth | ~200MB/day | ~10–20MB/day (with P1-2) |
