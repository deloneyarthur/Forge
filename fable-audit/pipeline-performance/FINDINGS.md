# Findings — pipeline-performance audit 2026-07-01

Evidence lines are as of the `ceeefa4`+D216 tree; grep symbol names if drifted.
Measured numbers: see `00-BASELINE.md` (benchmark table + method).

---

## The submit phase (195–202s measured)

### F1 — `record_pre_filter_logs_for_rejected` IS the submit phase (~190s of ~197s)

- **Where:** `src/forge/submission/pre_filter_logger.py:155-163` — `db.executemany(...)`
  over ~31k rejected-config rows with NO enclosing transaction; called from
  `src/forge/cli/main.py:2115` inside the `_t_submit` timing window. (The survivor path
  `record_pre_filter_logs` at :89 writes ~7 rows per candidate inside the M-10
  per-candidate txn — that part is fine, ~2–3s total.)
- **Mechanism:** duckdb-python `executemany` executes+autocommits row-by-row: ~1.05ms/row
  binding CPU (table-size independent) + **one WAL fsync per row** (strace: 1,003 fsyncs
  / 1,000 rows). ~31k rows/batch → ~33s CPU + ~160s fsync ≈ 190s. Each insert also
  maintains the composite ART PK on a 35M-row table (F7).
- **Volume:** journal per-batch `pre_filter_logs` row counts 32.4k–33.5k (incl. ~1.6k
  survivor rows); ~94–110 batches/day → **~3.4M rows and ~3.4M fsyncs per day**.
- **Attribution check:** no sleeps/limiter waits inside the submit timer (limiter runs
  pre-enumeration, main.py:1721; the only `time.sleep` is the loop poll, main.py:2560).
  Timeline of batch f638c8f4: 13:54:26 `ranked_top_n` → 13:57:41 `funnel_export` puts
  ~195s in this write. Replay on tmpfs (fsync-free): 28.8s CPU for 27.2k rows.
- **Also relevant:** nothing in src/ or scripts/ READS `pre_filter_logs` (grep-verified;
  only the writers and the DDL in `persistence/schemas.py:75-83` mention it). The
  aggregates already live in `batch_summaries.prefilter_rejections{,_by_hypothesis}`
  (`submission/submitter.py:398-407`).

### F9 — `run_shadow_scoring` per-row autocommit (~2s/batch, ~200 fsyncs)

- `src/forge/ranking/shadow.py:75-95` — per-row `INSERT OR IGNORE` loop, autocommit.
  Journal: 2s gap `funnel_export` → `shadow_scores`. Telemetry-only path; must keep the
  never-raises posture (shadow.py:104-106).

---

## The reconcile phase (29.9–37.1s, EVERY iteration incl. 373 blocked/day)

### F2 — `record_verdicts` re-inserts the entire 10k-row export window every pass (~17–20s)

- **Where:** `src/forge/persistence/verdicts.py:79-87` — `executemany` `INSERT OR IGNORE`
  over every export row whose hash matches a Forge submission (at 254k+ submissions,
  essentially all 10k rows match, every pass). Called unconditionally from
  `src/forge/feedback/consumer.py:455` (`reconcile_all_pending`, export limit=10,000 at
  consumer.py:62). Gate-results re-serialization (`model_dump`+`json.dumps` for all ~10k
  rows) at verdicts.py:59-62 costs another ~0.3s/pass.
- **Measured:** 16.6–20.4s/pass at production scale (verdicts=140k) — the second,
  fully-idempotent pass is just as slow. Genuinely new rows per pass: **0–25 typical**
  (journal deltas), ~130 max observed.
- **Growth:** window-bounded (10k) → flat-ish; already ~60% of reconcile.

### F4 — ~7,900 no-op per-row UPDATEs per pass (~3–6s)

- **Where:** `src/forge/feedback/consumer.py:307-311` — the per-batch matched loop
  ignores the `_status` it already loaded (`_load_submissions` consumer.py:132-141,
  `status IN ('submitted','gated')`) and calls `_update_submission_to_gated`
  (consumer.py:149-162, one UPDATE per row, idempotent only via `WHERE
  status='submitted'`). Journal `newly_gated_total=7976` = matched rows re-issued every
  pass across ~150 pending batches; ~all are already `gated` → 0-row no-ops.
- Plus ~117–150 `batch_summaries` UPDATEs + sentinel COUNTs per pass (minor).

### F17 — blocked iterations pay full reconcile before the limiter check (~3.2 CPU-h/day)

- **Where:** main.py:1713-1754 — reconcile (:1718) strictly precedes `check_rate_limit`
  (:1721); blocked path returns at :1754. 373 blocked × ~31s ≈ 11,600s/day.
- **CRITICAL CONSTRAINT:** this ordering is *correct* — the depth cap counts DB
  `submitted` rows (`rate_limiter.py:344-349`) and the pct-gated check uses local gated
  counts, so **reconcile is what un-blocks the limiter. Do NOT skip or reorder it;
  make it cheap** (F2+F4 fixes take a blocked pass from ~33s to ~3–5s). Export-parse
  memoization by mtime is useless here (the file rotates ~65s → ~0 hit rate).

---

## Per-iteration fixed costs outside any timing bucket

### F3 — the 57MB gated export is parsed + Pydantic-validated ~12× per full iteration (~10–11s, invisible)

- **Where (all call `load_recent_gated_runs_from_export`, which `json.loads` the WHOLE
  file regardless of `limit` — `crucible_contracts/.../queries.py:234-283`):**
  nine weight loaders `src/forge/cli/main.py:599, 673, 744, 793, 840, 887, 1007, 1061,
  1123` (limit 10k each) + `feedback/trade_rate_priors` path; the rate limiter
  `src/forge/submission/rate_limiter.py:218` (limit 1000, every iteration incl. blocked);
  reconcile `consumer.py:232/449` (the one legitimate parse); the post-submit chain
  `main.py:1500` calls `consume_batch_results` WITHOUT the `crucible_runs=` reuse
  parameter that D046 added for exactly this purpose.
- **Measured:** 0.85–1.24s per 10k-validate load; ~12 loads/full iteration ≈ 10–11s
  (hidden in the gap between the `reconcile` and `enumeration` timers), ~2 loads/blocked
  iteration ≈ 1.7s. ~1,410 parses/day ≈ ~80GB/day of page-cache JSON decode, ~25 min
  CPU/day; the repeated ~0.5GB transient object graphs are the likely driver of the
  3.6G steady RSS.
- **Correctness-adjacent:** Crucible republishes the export ~every 65s and a full
  iteration lasts ~10 min → different loaders within ONE iteration can read DIFFERENT
  snapshots; the weight families are not computed off a consistent window.
- Each loader also opens its own write-mode DuckDB connection (each open re-runs the
  full `ensure_schema` DDL — `persistence/db.py:37-56`); ~16 write-mode opens per full
  iteration.

### F5 — novelty fingerprint full-table rescan per iteration (~5–8s + ~300MB transient, growing linearly)

- **Where:** `src/forge/cli/main.py:1226-1260` `_load_prior_structural_fingerprints` —
  `SELECT config_json FROM submissions` (NO WHERE; 254–264k rows), then per-row
  `StrategyConfig.model_validate_json` (~10µs) + `compute_structural_fingerprint`
  (~14µs; `ranking/novelty.py:79-146` json.dumps+sha256). Called at main.py:1306-1310,
  BEFORE the `t0` enumeration timer (main.py:1336) → charged to no phase.
- The docstring's "~4k rows … milliseconds" (main.py:1236-1238) is a D049-era estimate,
  stale by ~66×. Growth: +~2.4s CPU / +~120MB transient per +100k submissions.

### F6 — observability gap: the ~28s loaders/fingerprints stanza is in NO `phase_timings` bucket

- **Where:** the timings key order is fixed at main.py:365-374; buckets are set at
  main.py:1368-1370 (enumeration), :1720 (reconcile), :2042 (rank), :2151 (submit);
  nothing wraps main.py:1758-1878 (weights) or :1226-1330 (fingerprints/cache build).
  This gap is why F3/F5 stayed invisible. Fix first — it verifies everything else.

---

## Prefetch (127–215s) — how it actually works, then the findings

Per batch: `_run_battery_for_seed` (main.py:1888) constructs a **brand-new**
`CrucibleFeatureCache` + `FeatureCacheClient` (main.py:1313-1317 via
`_build_feature_cache` main.py:186-207). `prefetch_for_batch`
(`src/forge/prefilters/crucible_feature_cache.py:254-327`) partitions 5,000 configs by
underlying (124 partitions, ~80 unique specs each) and per underlying makes (1) one
chunked `activation_dates` request (chunk=500) and (2) one `returns`+`regime_label`
request for the full permutation window (3,111 calendar dates → ~2,134 trading rows as
`{iso_date: value}` JSON) — **~249 strictly sequential blocking round-trips** over one
`multiprocessing.connection` Unix socket to Crucible's db_writer
(`~/optbt_data/db_writer.sock`; envelope pickled, payload JSON —
`crucible_contracts/.../feature_cache.py:147-171`). After prefetch, the battery's
per-config `prefetch_for_config` is I/O-free. All client-side state dies with the
iteration.

### F10 — Crucible-side: unconditional chain load × 124 underlyings thrashes a 3-slot LRU (~90–160s/batch; NOT Forge-fixable)

- **Where (Crucible, read-only evidence):**
  `../Crucible/src/optbt/persistence/feature_cache.py:795-826` — every
  `compute_feature_batch` loads bars, trades, and the full 2,134-day chain range via
  `chain_cache.get_or_load(...)` BEFORE checking whether any requested feature will miss
  its persistent SQLite feature store; `chain_cache.py:63` — `max_underlyings: int = 3`
  (docstring: ~5.3M rows ≈ 800MB for SPY); `db_writer.py:107` — "a pure cache-hit
  feature_batch returns in ~150-250 ms".
- **Mechanism:** Forge cycles all 124 underlyings once per batch; capacity 3 « 124 →
  every underlying's first request per batch is a chain-scan miss → **~124 chain parquet
  scans per batch, every ~13 min, forever** — even when all requested values are served
  from the SQLite cache and chains are never needed. Even the pure-hit floor is
  249 × 0.15–0.25s ≈ 37–62s of serialized round-trips.
- **Ownership:** Crucible-internal → hard rule #2 says relay, never work around (P2-1).

### F11 — Forge-side: the feature cache dies each iteration; immutable history re-fetched every batch (~25–40s + ~200–350MB churn)

- **Where:** cache construction per-iteration (main.py:1313-1317); the reuse machinery
  exists but never fires — `_window_loaded_for` (crucible_feature_cache.py:127-150)
  gates the full-window fetch to first touch and later prefetches fetch only
  `missing_dates` (:297-310), but the object is discarded per iteration.
- **Evidence it's redundant:** identical `returns_coverage`/`regime_coverage` (2,134/full
  ticker) in every consecutive `feature_cache_prefetch_batch` journal line. ~124 × 2,134
  × 2 maps ≈ ~529k `{iso_date: value}` entries re-transferred and re-parsed
  (`date.fromisoformat` per entry) per batch ≈ ~95M redundant points/day.
- **OOM trap for the fix:** `_activations` gains ~10k unique keys/batch — spec thresholds
  are minted fresh at 4 decimal places (`enumeration/indicator_thresholds.py:577`
  `round(rng.uniform(...), 4)`) so cross-batch key reuse is ~nil → ~100–200MB/batch
  unbounded if persisted. `_returns`/`_regimes` are ~100MB steady and safe to keep.

### F13 — no pipelining: 249 sequential RTTs on one connection (deferred)

- The writer supports concurrent per-connection threads (`db_writer.py:314-315`) and its
  heavy compute pool runs unlocked (feature_cache.py:765-770, 1057-1107). BUT concurrent
  distinct-underlying misses each transiently hold an ~800MB chains DataFrame — the
  D179 OOM class (the writer has been OOM-killed before). Only worth doing AFTER F10's
  lazy chain load lands, with Crucible coordination, concurrency ≤4.

### F18 — cache-effectiveness telemetry is discarded

- Every `FeatureBatchResponse` carries `cache_hits`/`cache_misses`/`window_hash`
  (`crucible_contracts/.../feature_cache.py:74-77`); Forge reads them only inside the
  M-5 empty-window warning (crucible_feature_cache.py:236-238). The
  `feature_cache_prefetch_batch` log (:317-327) logs coverage but not hit/miss.
  Quantifies F10/F11 for the relay; trivial to add.

### F20 — micro: `signal_content_key` recomputed ~5×/spec (~50k calls ≈ 1s/batch); no date interning

- Keys: crucible_feature_cache.py:283, 294 (prefetch_for_batch) + :351-353, 356-357, 367
  (prefetch_for_config); each is json.dumps+sha256
  (`crucible_contracts/signal_content_key.py:23-38`). Dates: `date.fromisoformat` per
  entry with no intern table (:187-189, 212, 216) — the same ~2,134 trading dates are
  materialized thousands of times per batch.

---

## Battery (33.8–51.2s)

### F12 — `permutation_test` re-derives per-underlying constants and re-runs an identically-seeded loop per config (≈ the whole phase)

- **Where:** `src/forge/prefilters/permutation_test.py:112-124` — per config:
  `_full_window(...)` builds 3,111 `date` objects; `ctx.feature_cache.returns(window)`
  builds a fresh ~2,134-entry dict; `list(...)`; then 100 × `rng.sample(all_returns,
  effective_n)` + `sum`.
- **Volume:** ~3,750 of 5,000 configs reach tier 9 per batch (it's the top rejector,
  2,549–2,640 rejections/batch). Measured 2.6–12.2 ms/config → ≈ the observed 36–45s.
- **The key fact enabling a byte-identical memo:** `ctx.rng_factory("permutation_test")`
  returns a freshly re-seeded `random.Random` with the SAME derived seed for every
  config in the batch (`src/forge/core/seed.py:27-29`; factory wired at main.py:1297,
  1321) → the sampled index sequences depend only on `(len(all_returns), effective_n)`
  → **the permuted sums are a pure function of `(underlying, effective_n)`**. The
  returns dict is built in chronological window order regardless of fetch order
  (crucible_feature_cache.py:440), so the population order is stable too.

---

## Rate limiter / post-submit / loop policy

### F14 — `check_rate_limit`: 3 separate DB opens (each re-running the DDL) + its own 57MB export parse, every iteration

- `src/forge/submission/rate_limiter.py:158/171, 294/315, 344/366` (three
  `db_connection` opens) and :218/229-238 (own `load_recent_gated_runs_from_export`,
  limit=1000 — the file reconcile parsed seconds earlier). ~1–2s/iteration.

### F15 — post-submit chain re-consumes a batch reconciled ~30s earlier in the same iteration

- `main.py:1500` (`_consume_feedback_after_submit`) runs a fresh `consume_batch_results`
  (12th export parse + redundant no-op UPDATE sweep) although `reconcile_all_pending`
  already produced the identical `BatchFeedback` (H-2 selection at main.py:2162-2166).
  ~1–2s/full iteration.

### F16 — fixed 60s sleep, no backoff while blocked

- `main.py:2560` unconditional `time.sleep(poll_interval_seconds)`; production poll=60
  vs the §7.3 design default 600 (main.py:2182). Blocked duty cycle today ≈ 35% work.
  After P0 this matters much less (~3–5s work/93s), but multi-hour Crucible backlogs
  still spin ~40 polls/hour for nothing.

---

## Growth / storage

### F7 — `pre_filter_logs`: unbounded, write-only, 34.9–36.4M rows (~2GB + ART PK), +3.4M rows/day

- DDL `persistence/schemas.py:75-83`. Zero readers (grep src/ scripts/). Drives the
  ~180–250MB/day forge.db growth, inflates every backup ~40%, and every F1 insert pays
  index maintenance against it. DuckDB does not reclaim file space on DELETE — a
  one-time offline compaction (operator-gated) is needed to shrink the file.

### F8 — backups: ~46GB now → ~80–90GB steady state (KEEP=14), same NVMe; one stray 4.5GB file outside retention

- `scripts/backup_forge_db.sh` (KEEP at :35). The design is sound; the source size is
  the problem (F7). Stray: `~/forge_data/forge.db.bak-pre-flush-20260624` (4.5GB) —
  operator confirm + delete. Optional: zstd -3 compresses DuckDB files ~3–5×.

---

## Scaling ledger (time-bombs; months out — see WORKPLAN P4)

### F21 — the daily trainer

- **Window cap never implemented:** `ranking/model.py:6-7` docstring claims "At the
  window cap (10k rows…)" but `ranking/dataset.py:112-122` selects EVERYTHING since the
  fixed `CLEAN_ERA_LABEL_CUT` (`feedback/rejection_weights.py:396`, 2026-06-10
  constant); `cli/ranker_model_cmd.py:167-168, 448` rebuild the full frame;
  `scripts/daily_ranker_eval.sh:66,84` builds the growing frame TWICE nightly.
  At +600 rows/day: 12 mo → n≈230k → IRLS 6–7 min ×2 + multi-GB RSS around n≈300–500k
  (dataset.py:124-154 list-of-dicts + model.py:254 dense matrix). Capping **changes the
  trained model** → operator-gated modeling decision.
- **Standardization defeats the sparsity guards:** model.py:252 `(v-mean)/std` maps the
  ~88%-zero one-hot entries nonzero, so the `if xj == 0.0: continue` fast-paths at
  model.py:183-184 (`_fit_irls`) and :474-476 (`_solve_ridge`) can never fire → O(n·d²)
  fully dense. Folding mean/std into the algebra ≈ 5–8× training speed. Numeric-
  equivalence tests required; artifact bytes change (content-hashed shadow artifacts —
  acceptable; not rule-#6 territory).
- **Cumulative eval windows** anchored at the fixed era cut: `daily_ranker_eval.sh:143,
  263, 375` + `eval-robustness` default since (ranker_model_cmd.py:66-72); each re-joins
  and re-hydrates gate_results per row (`ranking/evaluation.py:96-107, 231-241,
  378-388`). They are continuity prints, not streak inputs (daily_ranker_eval.sh:19-21)
  → cap at trailing 30–60d.

### F22 — assorted linear/quadratic creep

- `compute_mature_arms` (`ranking/arm_floor.py:87-101`): full honest-era scan per
  iteration, GROUP BY the full `config_json` STRING; inside the rank timer
  (main.py:1931; `_t_rank` at :1921) so rank≈6s will silently absorb its growth.
  Fix: GROUP BY `config_hash` + exploit maturity monotonicity (a mature arm stays
  mature — cache the mature set in-process).
- **Model-artifact loads:** `ranking/model.py:417-429` and :709-733 glob + parse ALL
  files in `~/forge_data/models` (36 now, +2/day, unbounded), 4 loads per full iteration
  (main.py:1951, 1981; shadow.py:61, 67). Fix: newest-first short-circuit preserving the
  exact `(trained_through, model_id)` max-tiebreak (parse all files sharing the newest
  stamp), prune old artifacts (reproducible from the DB), load once per iteration.
- **Diversifier O(K²·P) cliff:** `ranking/diversifier.py:137-170` (fast path) and
  :279-326 (production floored path `_select_top_n_floored`): each of K picks rescans
  the pool recomputing max-similarity vs all selected. Fine at K=200 (~6s; a prior
  10-min incident is documented at :129-131); K=600 ≈ 9×. Only if K is ever raised:
  running per-candidate `max_sim` updated only vs the newly-selected config — O(K·P),
  provably identical selection sequence; golden-compare property test REQUIRED
  (selection order feeds submission order → determinism-critical).
- **Funnel version map:** `funnel/aggregate.py:106-113` re-joins/serializes all ~264k
  submissions into the 8MB `forge_submission_versions.json` every batch (inside the
  submit timer, main.py:2127). Windowing needs Crucible sign-off (their instrumentation
  consumes it, D096).

### F23 — latent full-scan kept in the API

- `feedback/rejection_weights.py:65` `_iter_hypothesis_outcomes`: `SELECT config_hash,
  config_json FROM submissions` (no WHERE — a 264k-row/~320MB fetchall). No production
  caller today (`compute_hypothesis_weights`/`compute_hypothesis_reward_weights` are
  exported but unused in src/), but any new caller inherits it. The sibling
  `_component_rate_sums` (:508-520) documents and avoids exactly this. Restrict to gated
  hashes the same way, or deprecate. (Overlaps the codebase-quality audit's
  `rejection_weights.py` dead-code item — land once.)
