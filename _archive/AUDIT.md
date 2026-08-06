# Forge Audit Report

> **STALE — point-in-time audit (banner added 2026-06-09).** Snapshot at D083/v4. Many findings
> have since been addressed (see `IMPLEMENTATION_DECISIONS.md` D084–D110 — e.g. the §7.3 limiter
> and aged-out flush were reworked in D110, the feedback loop re-aimed in D094/D101/D105).
> Verify any finding against current code before acting on it.

**Audit date:** 2026-05-29
**Scope:** `src/forge/` (~75 files, ~13.5 KLOC), `tests/`, `config/`, `deploy/`, plus live system state (`~/forge_data/forge.db`, `~/optbt_data/exports/`, `forge.service` journal).
**Reference:** `docs/DESIGN.md` (source of truth), `CLAUDE.md` (10 hard rules), `OPEN_QUESTIONS.md` (Q1–Q22), `IMPLEMENTATION_DECISIONS.md` (D001–D083).
**Framing:** Forge is a *producer*, not a validator. Judgments are against the spec and hard rules, not against candidate quality. 0 promotions is not inherently a bug (DESIGN §1.2).

---

## Executive Summary

**Overall health verdict: STRUCTURALLY SOUND CORE, DEGRADED CLOSED LOOP.** Forge's grammar validator, enumeration determinism *within a process*, and the hard-rule-#4 auto-loosening guard are well-built and verified correct. However, the audit found that **the feedback/learning loop and the §7.3 flow-control mechanism are effectively non-functional in autonomous operation**, and the determinism guarantee (hard rule #6) is **violated across process restarts** because two load-bearing enumeration inputs are excluded from the determinism identity. Several operational-resilience gaps can brick or crash-loop the daemon. None of these corrupt submitted candidates or breach the gate, but they undermine the spec's central promises about reproducibility, throttling, and self-tuning.

The most consequential pattern is **silent decoupling**: multiple config knobs and learning mechanisms parse and validate but are never wired to their consumers (rate-limit threshold, feedback cadence, diversification config), and multiple "learning" steps run against the wrong data (analyzer/proposer on a 0-gated fresh batch; auto-tune adjusting a non-primary filter knob). The system *looks* like it is learning and throttling; in practice it largely is not.

### Counts by severity (post-dedup)

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 7 |
| Medium | 16 |
| Low | 18 |
| Info | 7 |
| **Total** | **48** |

### Top 5 issues to fix (most impactful first)

1. **§7.3 rate limiter is structurally inert in production** (H). D046 (oldest-batch) + D052 (sentinel-flush) jointly defeat the ≥80%-gated throttle. Live: 91.6% of "gated" rows are nil-UUID sentinels; 0 rate-limit pauses since restart while submitting ~26× faster than Crucible decides. The "deep queue Forge can't learn from" that §7.3 forbids is the live state.
2. **Feedback loop is dead in the `--loop` body** (H). The analyzer/proposer/auto-tune chain only ever runs against the just-submitted (0-gated) batch; the newly-gated batches that reconcile flips are discarded. §2.1 steps 10–11 produce nothing in autonomous operation.
3. **Determinism (hard rule #6) is violated across restarts** (H ×2 + M ×2, merged). The `auto_tightened_thresholds.yaml` content and the `universe_tickers.json` export both change the enumerated config sequence but are excluded from `registry_hash`/`grammar_version`/`mint_batch_id`/`batch_summaries`. Same `(grammar_version, registry_hash, seed)` → different configs and a colliding `batch_id`.
4. **`inflight_threshold` config knob is dead** (H). The §7.3 operator threshold parses into `ForgeConfig` but is never passed to `check_rate_limit`; editing `forge.yaml` has no effect. Compounds #1.
5. **auto-tune writes live `prefilter.yaml` non-atomically** (H). A crash mid-write corrupts the file the daemon re-reads every iteration with no exception guard → permanent 30s systemd crash-loop until manual repair. The self-tuning step can brick the daemon on the file it tunes.

---

## CRITICAL

*No critical findings.* The audit confirmed no path where bad candidates bypass Crucible's gate, no path where auto-loosening reaches `grammar.yaml`/`prefilter.yaml` automatically, and no data corruption of submitted candidates.

---

## HIGH

### H-1. §7.3 rate limiter is structurally inert in production — D046 + D052 jointly defeat the ≥80%-gated throttle
**Subsystem:** production-reality / ranking-submission
**Locations:** `src/forge/submission/rate_limiter.py:119-190` (oldest-batch query); `src/forge/feedback/consumer.py:302-360` (`_flush_aged_out_submissions`)
**Spec/rule:** DESIGN §7.3; CLAUDE.md per-batch step 8; contradicts D070's stated intent (IMPLEMENTATION_DECISIONS.md:2089-2093)

**What's wrong:** §7.3 mandates Forge not submit a new batch until the previous is ≥80% complete in Crucible, "to prevent the inbox from becoming a deep queue Forge can't learn from." Two prior decisions jointly void this:
- **D046** makes the rate limiter inspect only the single *oldest* batch with `status='submitted'` rows (`rate_limiter.py:119-128`). The blocker is the queue *front*, not the most-recent batch.
- **D052** ages stuck rows out to `status='gated'` with a nil-UUID sentinel (`consumer.py:356`), and the rate limiter's gated count (`rate_limiter.py:151`) does not exclude sentinels (the query at `:140-147` never fetches `crucible_run_id`).

Result: an old, legitimately-decided batch (live: `c9c817ca`, 178/200=89% real gates) satisfies the threshold and clears, while 17 newer batches at ~0% real-gated are never the blocker.

**Why it matters:** The flow-control mechanism the spec calls "core" is silently open. Live evidence: 0 journal lines matching `waiting|blocked|rate-limit` since the 2026-05-28 restart; batches submit every ~20–33 min; of 29,629 rows marked `gated`, only 2,488 (8.4%) are real Crucible decisions and 27,141 (91.6%) are sentinel flushes. Forge submits ~26× faster than Crucible decides. The exact "deep queue" §7.3 forbids is the live state, and the feedback loop is starved of real outcomes.

**Recommended fix:** Surface to operator as a Decision Log entry — this voids a spec mechanism and must not be silently re-fixed. Options: (a) count only real gates (exclude nil-UUID `crucible_run_id`) in `pct_gated`; (b) base the throttle on a rolling submission-vs-real-gate-rate ratio rather than a single oldest-batch snapshot; (c) cap the in-flight non-sentinel-gated backlog. Keep the D052 flush for genuinely rolled-off rows, but it must not be the dominant disposal path — its "enough time has passed for a decision" watermark is invalid whenever Crucible throughput < submission rate.

---

### H-2. Analyzer/proposer (§2.1 steps 10–11) never run on completed batches; reconciled `BatchFeedback`s are discarded
**Subsystem:** pipeline-order
**Locations:** `src/forge/cli/main.py:855-884` (`_reconcile_pending_silently`), `:1221-1228`, `:887-948` (`_consume_feedback_after_submit`); `src/forge/feedback/consumer.py:236-293`
**Spec/rule:** DESIGN §2.1 steps 10–11, §8.2/§8.3

**What's wrong:** In the `--loop` body, the only step that flips old completed batches to `gated` is `_reconcile_pending_silently → reconcile_all_pending`, which returns one `BatchFeedback` per in-flight batch — but the caller *discards* them after summing `fb.gated_count` for a log line (`main.py:872-884`). The analyzer/proposer/promoted-patterns/auto-tune chain is invoked *only* from `_consume_feedback_after_submit`, called with `batch_id=result.batch_id` — the batch just written to the inbox *this* iteration. Those config hashes were submitted seconds ago, so the join in `consume_batch_results` against Crucible's gated runs produces 0 matches → `analyze_batch`/`propose`/`record_promoted_patterns`/`auto_tune` all operate on a 0-gated, 0-promoted batch and produce nothing.

**Why it matters:** §2.1 steps 10–11 (the entire learning/feedback layer) are effectively dead in autonomous operation. `batch_summaries` DB state is still correct (written inside `reconcile_all_pending`), so this is not corruption — but no proposals, no promoted-pattern recording, and no auto-tune ever fire on real gated data. The `forge feedback` standalone command is a manual workaround outside the loop. Not flagged as known in D046 (which documents the reconcile path's rate-limit purpose only).

**Recommended fix:** In the loop, feed the `BatchFeedback` objects returned by `reconcile_all_pending` into `analyze_batch`/`record_promoted_patterns`/`propose`/`auto_tune`, instead of (or in addition to) re-consuming the freshly-submitted batch. The analysis target must be the most-recently-*completed* (newly-gated) batches, never the just-submitted one.

---

### H-3. Determinism triple omits `auto_tightened_thresholds.yaml` and the universe export — same `(grammar_version, registry_hash, seed)` yields different config sequences across restarts
**Subsystem:** enumeration
**Locations:**
- `src/forge/enumeration/indicator_thresholds.py:280-329` (`_auto_tightenings`/`_effective_range`), `:280-281` (`@lru_cache`)
- `src/forge/enumeration/sampler.py:100-151` (`_UNIVERSE_EXPORT_PATH`, `_load_underlyings`, `_pick_underlying`), `:103-104` (`@lru_cache`)
- `src/forge/enumeration/registry_fingerprint.py:26-38` (`registry_hash`)
**Spec/rule:** DESIGN §13.1; **hard rule #6** (deterministic enumeration)

> *Merged finding:* combines the two HIGH determinism findings (auto-tightenings YAML; universe export) and the related MEDIUM `lru_cache` process-start finding, which share one root cause and fix.

**What's wrong:** Hard rule #6 / §13.1 require `(grammar_version, registry_snapshot, seed)` to produce the same sequence every time. Two external inputs shadow the sampler's draws but are excluded from the determinism identity:
1. **`config/auto_tightened_thresholds.yaml`** — loaded via `lru_cache` in `_auto_tightenings`, fed into `rng.uniform(low, high)` at `:380/:385`. Its content is in neither `registry_hash` (hashes only `RegistrySnapshot.model_dump()`, `registry_fingerprint.py:33-37`) nor `grammar_version`. **Empirically proven:** with the YAML present (16 tightenings) vs absent, an 80-config enumeration at seed=137 on the demo registry diverges in **49/80** config hashes (first diff at index 2). D073 itself (IMPLEMENTATION_DECISIONS.md:2196) states the contract should be `(grammar_version, registry_hash, seed, auto_tightenings_yaml_hash)` — but no code computes that fourth element.
2. **`~/optbt_data/exports/universe_tickers.json`** (D078) — `_load_underlyings` reads it (lru_cache'd) and `_pick_underlying` calls `rng.choice` over the pool, changing both the chosen value and the rng stream for every subsequent draw. **Empirically proven:** a 60-config enumeration at seed=42 diverges in **60/60** hashes (24-ticker fallback vs a 5-ticker export). The file is currently *absent* on this machine, so production uses the fallback today; the day Crucible publishes it, every same-seed reproduction breaks.

The `lru_cache(maxsize=1)` on both loaders compounds this: enumeration depends on process-start filesystem state. A proposer-written YAML between batches is silently ignored until restart, so the effective inputs are a function of *when the process started*, not just the recorded triple. The invariant tests (`test_phase2_invariants.py:39-49`, `test_batch_reproducibility.py`) cannot catch any of this because both enumerations run in the same process against one warm cache.

**Why it matters:** This is a genuine hard-rule-#6 violation once either file exists or changes. Reproduction/audit of a recorded batch is impossible from the persisted identifiers. It does not affect mid-run consistency (lru_cache holds within a process) and does not let bad configs through the gate, hence High not Critical.

**Recommended fix:** Fold a content hash of `auto_tightened_thresholds.yaml` and a hash/version of the resolved universe pool into the recorded determinism identifier *and* `mint_batch_id`'s payload. Prefer sourcing the universe set from `RegistrySnapshot` so it rides `registry_hash` (also resolves the hard-rule-#2 issue H-5). Either invalidate the caches at batch boundaries and record the loaded hash per batch, or thread the loaded files as explicit batch inputs. Add an invariant test that toggles each file (with `cache_clear`) and asserts the sequence changes only when the recorded identifier also changes.

---

### H-4. `inflight_threshold` config knob is dead — rate limiter always uses the hardcoded module default
**Subsystem:** ranking-submission
**Locations:** `src/forge/cli/main.py:1096`; `:1256-1315` (`_resolve_run_defaults`); `src/forge/submission/rate_limiter.py:59,91`
**Spec/rule:** DESIGN §7.3; §10.1 (`forge.yaml`)

**What's wrong:** `forge.yaml`'s `submission.inflight_threshold` (the §7.3 ≥80% threshold) is parsed and validated into `ForgeConfig` (`forge_config.py:45`) but never plumbed to its only consumer. `check_rate_limit(forge_db_path, crucible_db)` is called at `main.py:1096` with no `threshold=` argument, so it silently falls back to `_DEFAULT_THRESHOLD = 0.80`. `_resolve_run_defaults` reads `batch_size`/`poll_interval_seconds`/`seed` but never `inflight_threshold`; the `_ResolvedRunDefaults` TypedDict has no such field. The whole D036/D070 history of editing `_DEFAULT_THRESHOLD` in source *is the symptom* — editing source was the only way to change the threshold.

**Why it matters:** The operator cannot control the §7.3 throttle via config. It happens to equal 0.80 today, masking the bug; editing `forge.yaml` to 0.50 would have no effect. Compounds H-1.

**Recommended fix:** In `_resolve_run_defaults`, read `cfg.submission.inflight_threshold`, add it to `_ResolvedRunDefaults`, and pass `threshold=resolved.inflight_threshold` into `check_rate_limit`. Add an end-to-end test asserting a non-default `forge.yaml` threshold changes the clear/block decision.

---

### H-5. Enumerator reads Crucible's `universe_tickers.json` directly — a file not in `crucible_contracts.EXPORT_LAYOUT` (hard rule #2)
**Subsystem:** contracts-boundary
**Locations:** `src/forge/enumeration/sampler.py:100-118` (`_UNIVERSE_EXPORT_PATH`, `_load_underlyings`)
**Spec/rule:** **hard rule #2** (all inter-system access via `crucible_contracts`)

**What's wrong:** D078 replaced the hardcoded ticker mirror with a raw read of `~/optbt_data/exports/universe_tickers.json` via `json.loads(_UNIVERSE_EXPORT_PATH.read_text())`. That file is not on the contracts surface — verified against contracts v1.12.0: `EXPORT_LAYOUT.files == ('registry_snapshot_*.json', 'gated_runs_*.json', 'promoted_strategies_*.json', 'promoted/')`, and there is no model or loader for a universe file (`dir(crucible_contracts)` exposes only `DEFAULT_UNDERLYING`). This is an inter-system data dependency bypassing `crucible_contracts`. The contrast is explicit: `registry_loader.py:31,72` reads the contract-listed `registry_snapshot_*.json` through `RegistrySnapshot.model_validate_json` — the blessed pattern.

**Why it matters:** `_load_underlyings` is in the hot path of every config sample (`_pick_underlying`), so every produced candidate's underlying is chosen via an uncontracted cross-system read. D078's "Alternatives considered" (IMPLEMENTATION_DECISIONS.md:2624) never mentions hard rule #2. Prior decisions flagged this exact shape (D033:584,593; OPEN_QUESTIONS.md:401), so the regression is into a known-bad pattern. **Not** tracked in any current Q (Q19 is `universe_min_asof` date coverage, unrelated).

**Recommended fix:** Surface as a contracts gap. Add the Tier-1/2 universe to `crucible_contracts` — either a `universe_tickers_*.json` entry in `EXPORT_LAYOUT.files` + a `load_universe_tickers_from_export` helper, or a `tier_tickers` field on `RegistrySnapshot` (matching the Q19 precedent; this also fixes the determinism half of H-3). Until that lands, revert to the D033 hardcoded list with an explicit OPEN_QUESTIONS.md #2-deviation entry.

---

### H-6. auto-tune writes the live `prefilter.yaml` non-atomically — a crash mid-write bricks the daemon into a 30s crash-loop
**Subsystem:** ops-resilience
**Locations:** `src/forge/feedback/auto_tune.py:49-64` (`write_calibration_yaml`), called from `_apply_tighten_and_persist:200`; consumed at `src/forge/cli/main.py:1067`; `deploy/systemd/forge.service` (`Restart=on-failure RestartSec=30`)
**Spec/rule:** DESIGN §5.5, §13.2

**What's wrong:** `write_calibration_yaml` writes the production `config/prefilter.yaml` with a plain `path.write_text(yaml.safe_dump(...))` (`auto_tune.py:64`) — *not* atomic. **Verified:** the sibling `proposal_writer._atomic_write` (`:136-137`) deliberately uses `tmp.write_text(...) + os.replace(tmp, path)`, so the non-atomicity here is an inconsistency, not a choice. Auto-tighten runs inside `--consume-feedback` on every loop iteration, and `_run_one_iteration` re-loads this exact file at the top of *every* iteration via `load_calibration(prefilter_yaml)` (`main.py:1067`), which raises `ValueError`/`FileNotFoundError` on any missing-key/truncated content (`calibration.py:183-211`). A kill mid-`write_text` (OOM, SIGTERM with short `TimeoutStopSec`, power loss) leaves the file truncated → next iteration's `load_calibration` raises → uncaught (see M-1) → systemd restart → raise again → permanent crash-loop until manual repair.

**Why it matters:** The self-tuning step has created a path where the daemon bricks itself on the file it tunes. The only operator signal is a flapping service and journal noise.

**Recommended fix:** Make `write_calibration_yaml` atomic — reuse the tmp + `os.replace` pattern from `proposal_writer._atomic_write` (write `prefilter.yaml.tmp`, fsync, rename). Small mechanical fix that removes the path entirely.

---

### H-7. Deterministic `batch_id` collides across proposer runs — `mint_batch_id` uses only `(seed, grammar_version, registry_hash)`
**Subsystem:** enumeration
**Locations:** `src/forge/submission/batch.py:24-42` (`mint_batch_id`); `src/forge/persistence/schemas.py:29-38` (`batch_summaries` PK = `forge_batch_id`); insert guard at `src/forge/submission/submitter.py:85-108`
**Spec/rule:** DESIGN §13.1, §13.4; hard rule #6

> *Promoted to High* (the source finding rated it Medium); it is the direct data-integrity consequence of H-3 and shares its fix, so it is grouped here.

**What's wrong:** `mint_batch_id` derives a deterministic UUID from exactly `f"forge|{grammar_version}|{registry_hash}|{seed}"` (`batch.py:40`) and documents "a re-run with identical inputs is a structural no-op." But because `auto_tightened_thresholds.yaml` is excluded (H-3), the proposer rewriting that YAML — *the whole point* of D073 — yields the *same* UUID with a *different* set of config hashes. Note the corrected mechanism: the proposer writes `config/auto_tightened_thresholds.yaml` (a calibration shadow), **not** `grammar.yaml`, so `grammar_version` does **not** change. `_insert_batch_summary` (`submitter.py:96-108`) does SELECT-then-INSERT and silently no-ops on the existing row, so the second genuinely-distinct batch keeps the *first* run's `batch_size`/`submitted_at`, while its new `submissions` rows all carry the stale `forge_batch_id`. The feedback consumer then updates `promotion_rate` for that UUID, mixing two distinct enumeration populations.

**Why it matters:** Analytics/observability corruption: wrong `batch_size`, stale `submitted_at`, and `promotion_rate` feedback blending two populations — which in turn degrades the auto-tune signal. No PK error (the SELECT-guard masks it), so it is silent.

**Recommended fix:** Add the auto-tightenings-YAML hash (and universe identifier) to `mint_batch_id`'s payload so distinct enumeration inputs always mint distinct UUIDs, restoring the documented "identical inputs ⇒ no-op" invariant. Same fix as H-3.

---

## MEDIUM

### M-1. Daemon loop has no per-iteration exception guard — any non-KeyboardInterrupt error crashes into a systemd restart loop
**Subsystem:** ops-resilience
**Locations:** `src/forge/cli/main.py:1460-1484` (loop body); `deploy/systemd/forge.service` (`Restart=on-failure`, `RestartSec=30`)
**Spec/rule:** DESIGN §13 (production quality)

**What's wrong:** The `--loop` daemon wraps `_run_one_iteration` in `try/except KeyboardInterrupt` *only* (`:1460,1482`). Every other exception (corrupt grammar/registry/`prefilter.yaml` parse, an unexpected filter exception, `SchemaVersionMismatch` from the per-iteration `check_contracts_version()` at `:1062`, a DuckDB error, an `OSError`) propagates out of `cmd_run`, exits non-zero, and systemd restarts every 30s. Only `FeatureCacheUnavailableError` is handled gracefully (`:1146`, the D080 fix) — D080 hardened exactly one failure mode and left every other one as a process-killer.

**Why it matters:** A deterministic on-disk fault (malformed grammar/`prefilter.yaml`, a bad `ranker.yaml` edit) → permanent flapping service until manual intervention, with no graceful skip-and-retry. This is also the propagation path that turns H-6's corrupt-write into a brick.

**Recommended fix:** Wrap the per-iteration call in a targeted `try/except` that logs the traceback loudly and `continue`s to the next poll, with a consecutive-failure backoff. **Important nuance:** do *not* blindly swallow `SchemaVersionMismatch` (a contracts major bump arguably *should* halt) — distinguish known-transient parse errors from intentional halts. Always re-raise `KeyboardInterrupt`/`SystemExit`.

---

### M-2. Permutation-test null pool is restricted to prefetched activation-date returns, not the full market series
**Subsystem:** prefilters
**Locations:** `src/forge/prefilters/permutation_test.py:93-105`; `src/forge/prefilters/crucible_feature_cache.py:237-249,290-301,326-337`
**Spec/rule:** DESIGN §5.3.7; hard rule #6 (per-config isolation)

**What's wrong:** §5.3.7 requires the null distribution be built by shuffling signal→return over the strategy's full return history. But `CrucibleFeatureCache` fetches `returns` only for the *union of activation dates* of the batch's configs (`prefetch_for_batch:237-249`), and `returns()` silently drops every non-prefetched date (`:337`). So `permutation_test`'s full-window `returns(window)` call yields only the activation-date pool. That pool is biased toward whatever regime the batch's signals select for, and — because the prefetched union differs per batch — **one config's p-value depends on the other configs in the batch**, breaking per-config isolation and cross-batch reproducibility. Simulation: a regime-clustered batch gave p=0.908 (intended full-window) vs p=1.000 (activation-only). D082 did not change this; D033 chose activation-only fetching to avoid KeyErrors without resolving the downstream permutation implication.

**Why it matters:** Biased p-values affect filter selectivity (which candidates reach Crucible), and the batch-dependence is a hard-rule-#6 corner. Severity is Medium not High because a 5000-config batch with diverse signals likely covers most of the market, making the bias partial.

**Recommended fix:** Prefetch returns for the full permutation window once per underlying (or lazily fetch missing in-window dates on miss). Add an integration test driving `PermutationTestFilter` through `CrucibleFeatureCache` (stub client) asserting the null-pool size equals the full window, not the activation count. This finding is the root cause of M-3 and M-4.

---

### M-3. D082 calendar-span window fix is a no-op in production
**Subsystem:** prefilters
**Locations:** `src/forge/prefilters/permutation_test.py:47-53,94-95`; IMPLEMENTATION_DECISIONS.md D082
**Spec/rule:** DESIGN §5.3.7

**What's wrong:** D082 (Q21) widened `_full_window` to span `ceil(n_trading_days * 366/252)` calendar days so the null pool reaches ~today. But because production `returns()` only serves prefetched activation dates (M-2), the newly-added calendar dates are dropped and never enter `all_returns`. The D082 text — "returns() drops the surplus dateless days, so over-coverage is free" — conflates genuinely-dateless calendar days (weekends/holidays) with *trading days that were simply never prefetched*. The widened window is visible only to the unit tests (whose `_ReturnsCache` stub provides a full-window dict); the production null pool is unchanged and the p-value bias D082 intended to fix persists.

**Why it matters:** A shipped fix that does not change production behavior, with a regression test (`test_q21_full_window_spans_calendar_extent_of_trading_days`) that guards only the helper, not the cache.

**Recommended fix:** Fix M-2 first; then D082's wider window matters. Add a test asserting the production cache's `returns(window)` covers the full trading-day range.

---

### M-4. D075 forward-horizon return comparison is largely defeated in production
**Subsystem:** prefilters
**Locations:** `src/forge/prefilters/permutation_test.py:75-87`; `src/forge/prefilters/crucible_feature_cache.py:290-301`
**Spec/rule:** DESIGN §5.3.7 / D075

**What's wrong:** D075 shifts activation dates by `forward_horizon_days` and reads returns at T+k so trend/leading signals get credit for forward drift (`target_dates = [d + timedelta(days=horizon) for d in activations]`, `:78`). But the prefetch never loads T+k dates — only activation dates. `returns(target_dates)` (`:81`) drops every target date not coincidentally also an activation date, collapsing `effective_n` toward the small `{act+k}∩{act}` overlap. The headline D075 mechanism (the reason `trend_continuation` was supposed to stop being wiped out) operates only against the unit-test stub's full-window dict.

**Why it matters:** D075's stated benefit is only partially realized in production. Medium not High because `prefetch_for_batch` loads the union of *all* batch specs' activations (thousands of dates), so incidental {act+k} overlap is non-negligible — `effective_n` is suppressed, not zeroed.

**Recommended fix:** In `prefetch_for_config`/`prefetch_for_batch`, expand the requested date set by `forward_horizon_days` before `_fetch_window_for_dates`. Add an integration test that sets `forward_horizon_days=5` through `CrucibleFeatureCache` and asserts `effective_n` is not silently collapsed.

---

### M-5. Empty/partial Crucible feature-cache response silently miscalibrates `regime_exposure` + `permutation_test` (D080 class, per-underlying)
**Subsystem:** ops-resilience / prefilters
**Locations:** `src/forge/prefilters/crucible_feature_cache.py:171-198,326-348`; `src/forge/prefilters/regime_exposure.py:62`; `src/forge/prefilters/permutation_test.py:81-95`
**Spec/rule:** DESIGN §5.3.6/§5.3.7; D080

**What's wrong:** A valid `FeatureBatchResponse` may have an empty/partial `features` dict (`default_factory=dict`; thin-data Tier-2 underlying or transient writer state). When the window-fetch returns no `returns`/`regime_label` for an underlying, the cache does not raise: `returns()` returns `{}` and `regime_label()` defaults *every* date to `"low_vol"`. Downstream, `regime_exposure` sees `Counter(low_vol=N)` → `max_share=1.0 > 0.80` → REJECT; `permutation_test` sees `effective_n=0` → `p_value=1.0` → REJECT. The config is killed for a data-availability reason but the verdict is indistinguishable from a genuine signal-quality rejection. D080 guards only *total* cache unavailability via `probe()`, which fetches one date on the *default* underlying (SPY) — it cannot catch a Tier-2 ticker with no ingested data, which the D033 multi-underlying expansion makes a live case.

**Why it matters:** Same silent-degradation class as the D080 incident, at per-underlying granularity. The harm is *false rejections* (not unsafe submissions), which pollute `pre_filter_logs` and contaminate the D076 empirical-prior buckets with mislabeled zero-activation rejections. Medium (not High) because, for a producer, false rejections degrade the feedback signal rather than let bad configs through.

**Recommended fix:** In `_fetch_window_for_dates`, detect the degenerate case (non-empty `missing_dates` but zero returns *and* zero regimes populated): log loudly (D080 stance) and have `returns()`/`regime_label()` raise or short-circuit to an explicit `data_unavailable` verdict distinct from a signal-quality FAIL. Surface the discarded `cache_misses`/`window_hash` so the operator has a first-class signal (see M-6).

---

### M-6. `CrucibleFeatureCache` has zero observability into degraded/partial responses
**Subsystem:** ops-resilience
**Locations:** `src/forge/prefilters/crucible_feature_cache.py` (entire module — no logging); discarded `FeatureBatchResponse.cache_hits/cache_misses/window_hash`
**Spec/rule:** DESIGN §13 (observability); D080 RCA

**What's wrong:** The production feature cache contains no logging whatsoever (grep for `log|warn|echo|stderr` returns nothing). The contract response carries `cache_hits`, `cache_misses`, `window_hash` precisely so a consumer can detect degraded responses — all three are discarded; only `response.features` is read. `_window_loaded_for` is tracked (`:198`) but never inspected for the "loaded but empty" condition. The only operator-visible signal that a batch ran against thin/partial data is the downstream `prefilter_rejections` histogram, which looks identical to genuine signal-quality rejections (M-5). This is the same blindness that let the D080 incident persist for 7 iterations before diagnosis.

**Recommended fix:** Emit a per-batch telemetry line from `prefetch_for_batch` (specs requested, activation-date coverage, per-underlying non-empty returns/regime window), and a WARNING when an underlying yields activations but an empty window. Plumb `cache_misses`/`window_hash` into it.

---

### M-7. Aged-out (sentinel-flushed) submissions dilute `promotion_rate`, biasing auto-tune toward the LOOSEN branch
**Subsystem:** feedback-autotune
**Locations:** `src/forge/feedback/consumer.py:105-119,150-180,302-360`; `src/forge/feedback/auto_tune.py:67-86,272-279`
**Spec/rule:** DESIGN §5.5, §8.2

**What's wrong:** Auto-tune reads `batch_summaries.promotion_rate` (promoted/`submitted_count`), where `submitted_count` counts `status IN ('submitted','gated')` (`consumer.py:113-114`). D052's `_flush_aged_out_submissions` transitions aged-out rows to `gated` with a nil-UUID sentinel even though Crucible never returned a decision. For a partially-aged-out batch, those sentinel rows are in the denominator but never in `outcomes` (absent from the export), so they only depress `promotion_rate`. A run of low-promotion batches caused by *export-window loss* — not candidate quality — pushes the rolling rate below `min_promotion_rate` (0.5%) and makes auto_tune emit spurious LOOSEN proposals.

**Why it matters:** The §5.5 calibration signal becomes a function of export latency. Not a hard-rule-#4 breach (loosen only proposes to `OPEN_PROPOSALS.md`, never applies), but it corrupts the rate the spec defines. Trigger requires a batch straddling the watermark, so Medium not High. (Related to H-1's sentinel mechanism.)

**Recommended fix:** Exclude sentinel-flushed rows (`crucible_run_id != sentinel`) from the `promotion_rate` denominator, or skip auto_tune when a batch contains sentinel rows.

---

### M-8. Auto-tightening does not tighten the D076 empirical-prior knobs that are now the PRIMARY expected-trades gate
**Subsystem:** feedback-autotune / prefilters
**Locations:** `src/forge/prefilters/calibration.py:351-406` (`apply_tightening`); `src/forge/prefilters/expected_trades.py:138-149`
**Spec/rule:** DESIGN §5.5

> *Merged:* the two findings on this topic (one framed as "auto-tune can't adjust the discrimination knobs," one as "auto-tightening is a no-op for the dominant filter") are the same defect.

**What's wrong:** Per §5.5, an above-5% promotion rate should tighten pre-filters by 10%. `apply_tightening` shifts `min_activations`, `min_trades`, the three Jaccard ceilings, regime concentration, and permutation p-value — but leaves `expected_trade_count.min_pass_probability` and `min_bucket_samples` unchanged (`calibration.py:370-373` rebuilds with only `min_trades` scaled). Since D076/Q16, the expected-trades filter decides on `posterior_p_pass >= min_pass_probability` for every warmed bucket (`expected_trades.py:149`); `min_trades` only governs the cold-start activations fallback. **Verified empirically:** after 10 tightening passes, `min_trades` 50→131, novelty 0.8→0.279, perm-p 0.10→0.0349, but `min_pass_probability` stayed 0.10 and `min_bucket_samples` stayed 20.

**Why it matters:** The single most-discriminating trade-count filter (rejecting ~3,250/5,000 per batch live) is invisible to auto-tune's tightening. A tighten step is largely a no-op for the filter §5.5 most needs to reach.

**Recommended fix:** Have `apply_tightening` also raise `min_pass_probability` toward 1.0 on tighten (bounded) and/or lower `min_bucket_samples`. Add an invariant test that a tighten makes the expected-trades filter strictly stricter for a learned bucket — or, if exemption is intended, document it.

---

### M-9. R3 macro-event indicators (`days_to_cpi/nfp/opex`) are unsamplable as regime gates
**Subsystem:** enumeration / grammar
**Locations:** `src/forge/grammar/custom_predicates.py:187-193` (`_R3_EVENT_PROXIMITY_INDICATORS`); `src/forge/enumeration/indicator_thresholds.py:70-259` (`_INDICATOR_THRESHOLD_TABLE`), `:332-358` (`is_threshold_skippable`); sampler filters at `sampler.py:354-355,405-406`
**Spec/rule:** DESIGN §3.5 R3

**What's wrong:** T1.4/D039 expanded R3's event-proximity pool to `days_to_cpi/nfp/opex` specifically to make `volatility_event` usable on ETFs. But none of the three are in `_INDICATOR_THRESHOLD_TABLE`, so `is_threshold_skippable(ind, 'regime_filter')` returns True (`:352-353`), and both `_viable_buckets` and `_pick_directional_regime_pair` filter them out. **Verified:** `is_threshold_skippable('days_to_cpi','regime_filter')=True` (and nfp/opex); `days_to_fomc`/`days_to_earnings` return False. On ETFs, `days_to_earnings` is also R3-incompatible, leaving only `days_to_fomc` samplable — so the enumeration-scope widening is largely inert.

**Recommended fix:** Add `regime_range` + `op_regime` entries (mirroring `days_to_fomc`) for `days_to_cpi/nfp/opex` to `_INDICATOR_THRESHOLD_TABLE`. Add a coverage test asserting every indicator in `_R3_EVENT_PROXIMITY_INDICATORS` has a regime threshold entry or is intentionally skipped.

---

### M-10. No transaction around INSERT(pending) → submit_candidate → UPDATE; a crash strands rows in `pending` and burns the config_hash slot
**Subsystem:** ranking-submission
**Locations:** `src/forge/submission/submitter.py:149-211`; `src/forge/persistence/db.py:48-55`
**Spec/rule:** DESIGN §7.2/§13.4; **hard rule #9** (idempotency)

**What's wrong:** `_submit_one` runs three autocommit statements with no enclosing transaction (**verified:** zero `BEGIN/COMMIT` in `submitter.py` or `db.py`; DuckDB autocommits per `execute`): (1) INSERT row as `pending` (claiming the unique `config_hash`), (2) `submit_candidate` (filesystem write), (3) UPDATE to `submitted`. A kill between (1) and (3) commits the `pending` INSERT but never the status update. **`pending` is write-only** — never queried/reconciled (`reconcile_all_pending` selects `status='submitted'`; `_load_submissions` filters `IN ('submitted','gated')`); no cleanup path exists. The stranded row permanently holds its config_hash, so a re-run hits the UNIQUE index → `skipped_duplicate` → that candidate is never submitted and never retried. (Note D046's IMPLEMENTATION_DECISIONS.md:1012 claim "production never writes pending" is factually wrong — `submitter.py:163` writes it.)

**Why it matters:** Breaks the module's documented idempotency ("idempotent re-run = no-op") and hard rule #9 in the crash case. Stranded rows also inflate the rate-limiter denominator (the `:140-147` query has no status filter — see H-1). Medium not High: Forge is a producer, losing individual candidates is acceptable (§1.2/1.3); the more meaningful cost is permanent config_hash burn reducing long-run enumeration coverage.

**Recommended fix:** Wrap INSERT+submit+UPDATE in `conn.begin()/commit()`, OR insert the row only *after* `submit_candidate` succeeds (write-to-inbox-first), OR add a startup sweep that re-drives/flushes `status='pending'` rows. Add a test simulating an exception between INSERT and UPDATE asserting no orphan blocks resubmission.

---

### M-11. auto-tune cumulative-tightening cap can be silently exceeded if the process dies between the YAML write and the audit-row write
**Subsystem:** ops-resilience / feedback-autotune
**Locations:** `src/forge/feedback/auto_tune.py:186-207` (`_apply_tighten_and_persist`), `:89-109` (`_cumulative_tightenings`), `:260-263` (cap check)
**Spec/rule:** DESIGN §5.5 (cumulative cap); hard rule #4 (auto-tightening discipline)

**What's wrong:** The 30% cumulative cap sums `step_pct` from prior `grammar_versions` rows. `_apply_tighten_and_persist` does two non-atomic cross-resource writes: (1) `write_calibration_yaml` mutates `prefilter.yaml` (`:200`), then (2) `_write_grammar_versions_row` inserts the audit row (`:201`, autocommit). A kill between them leaves the calibration tightened on disk but the step unrecorded, so the next run's `_cumulative_tightenings` under-counts and the cap gate (`:262`) permits tightening beyond 30%. The `grammar_versions.yaml_sha256` is a 64-zero placeholder for calibration rows (`:129`), so there's no cross-validation of on-disk YAML vs DB accounting, and no startup reconciliation.

**Why it matters:** Repeated unlucky crashes can tighten the battery past its design cap with no audit trail — silent drift in the only structural lever §5.5 owns. The invariant test (`test_phase5_invariants.py:186`) covers only the happy-path cap.

**Recommended fix:** Write the `grammar_versions` row *before* the YAML mutation (so a crash can only *under*-apply — the safe direction), and make the YAML write atomic (H-6). Ideally compute the cap from the YAML's actual current value vs the original baseline rather than a summable step-log that can desync.

---

### M-12. `forge feedback` performs Crucible I/O without the startup contracts-version check
**Subsystem:** contracts-boundary
**Locations:** `src/forge/cli/feedback_cmd.py:55-119` (`cmd_feedback`); registered at `main.py:1487`
**Spec/rule:** DESIGN §13.5; hard rule #5 (startup contracts version check)

**What's wrong:** Every Crucible-touching command calls `check_contracts_version()` first (`version`:68, `check`:78, `enumerate`:107, `prefilter`:265, `run` via `_run_one_iteration`:1062) — except `forge feedback`. `cmd_feedback` goes straight from `_resolve_paths` into `consume_batch_results`, which calls `load_recent_gated_runs_from_export`/`get_recent_gated_runs`. The root callback only configures logging (`main.py:55-60`). A major-version contracts mismatch on the feedback path would not produce the clean §13.5 `SchemaVersionMismatch` halt — it would fail later or mis-parse.

**Recommended fix:** Add `check_contracts_version()` at the top of `cmd_feedback`, or — more robustly — move the check into the `_root` callback so every command inherits it.

---

### M-13. Universe-export read silently swallows all parse/IO errors and degrades to a stale hardcoded list
**Subsystem:** contracts-boundary / ops-resilience
**Locations:** `src/forge/enumeration/sampler.py:110-118` (`_load_underlyings`)
**Spec/rule:** hard rule #2 (spirit); DESIGN §13; D080 (loud-fallback principle)

> *Merged:* the contracts-boundary and ops-resilience framings of the same silent-fallback defect.

**What's wrong:** `_load_underlyings` wraps the universe read in `except (OSError, json.JSONDecodeError, TypeError): pass` and falls back to the D033 24-ticker list with *no log* (also silently when the file parses but yields an empty set, via the `if tickers:` guard). There is no logger in `sampler.py` at all. Because the function is `lru_cache(maxsize=1)`, a transient unreadability at first call freezes the stale pool for the entire process lifetime. This contrasts with `registry_loader.py:81` (`_LOG.warning("registry_demo_fallback", ...)`) and D080's explicit "log LOUDLY in every mode" stance — D080's scope was the feature cache; this path was left silent. Functionally narrows the pool from ~152 (D078 rationale) to 24 with zero observability; the chosen pool is also not in `registry_hash`, so telemetry won't reflect the degradation either.

**Recommended fix:** Log a one-shot WARNING when the export is missing/malformed/empty and the fallback is used (mirror `registry_demo_fallback`/D080). Distinguish "file absent" (expected offline) from "present but unparseable" (drift signal). Surface the active ticker-pool size in per-iteration telemetry.

---

### M-14. Reproducibility metadata not persisted — `batch_summaries` records no seed and no extra-input hashes
**Subsystem:** enumeration
**Locations:** `src/forge/persistence/schemas.py:29-53`; `src/forge/cli/main.py:1072-1075`
**Spec/rule:** DESIGN §13.1 ("logs the (grammar_version, registry_version, seed)"), §12 reproducibility

**What's wrong:** `batch_summaries` stores `grammar_version` and `registry_version` but has **no seed column** and no auto-tightenings/universe hash column. `batch.seed` rides on `BatchContext` but is never written; the CLI echoes it only to stdout (`main.py:1072-1075`). Given H-3, a recorded batch cannot be reproduced from the persisted row: the seed is absent and two load-bearing inputs are invisible.

**Why it matters:** Medium (not High) because `mint_batch_id` non-reversibly encodes the triple, so the info exists in the UUID — but an operator cannot replay a batch from the DB without externally recovering the root_seed and iteration. An observability/auditability shortfall against the §13.1 requirement.

**Recommended fix:** Add `seed`, `auto_tightenings_yaml_hash`, and `universe_id` columns (idempotent ALTER) and write them at submit time. Pairs with H-3.

---

### M-15. GRAMMAR.md S5 narrative is stale — never updated for the v3/v4 `required_from_set` multi-exit schema (hard rule #10 / §3.1 sync)
**Subsystem:** grammar (docs)
**Locations:** `docs/GRAMMAR.md:60-74`; impl `src/forge/grammar/custom_predicates.py:82-139` (`_S5_HYPOTHESIS_EXITS`)
**Spec/rule:** §3.1 (files must stay synchronized); hard rule #10; §3.5 S5

**What's wrong:** GRAMMAR.md §S5 still describes the v2 single-required-exit model ("trend_continuation: must include trailing_atr", "mean_reversion: must include time_stop", "relative_value: must include convergence_exit"). The live v3/v4 impl uses `required_from_set` 3-way choices, so a `trend_continuation` config with `chandelier_exit` (no `trailing_atr`), or `mean_reversion` with `target_exit` (no `time_stop`), all PASS validation while contradicting the narrative. **Verified:** the S5 section is byte-identical between the Phase-1 commit (666159d) and HEAD; D071-final's action list (IMPLEMENTATION_DECISIONS.md:2374-2381) omits any GRAMMAR.md update. The pre-commit doc-sync hook checks only heading-id existence, not content, so the drift passes silently.

**Why it matters:** The runtime validator is correct; this is documentation integrity per §3.1. An operator reading GRAMMAR.md would be misled about what exits are required/allowed per hypothesis.

**Recommended fix:** Rewrite §S5 to document the v3 `required_always`/`required_from_set`/`optional_additions`/`forbidden` schema per hypothesis. Add a content-aware check to `scripts/check_grammar_doc_sync.py`.

---

### M-16. Grammar S5 `K_MAX_OPTIONAL` cap has no working failure-mode test — the only test always skips and asserts nothing
**Subsystem:** test-coverage / grammar
**Locations:** `tests/unit/test_grammar/test_custom_predicates.py:246-271`; impl `src/forge/grammar/custom_predicates.py:388-393`
**Spec/rule:** DESIGN §3.5 S5 (D071); **hard rule #1** + CLAUDE.md TDD ("every hard rule has a failure-mode test")

**What's wrong:** S5 branch (4) rejects configs whose optional-exit count exceeds `K_MAX_OPTIONAL=2`. The only test, `test_d071_too_many_optional_additions_fails`, (a) unconditionally `pytest.skip`s because no shipped hypothesis has >2 `optional_additions` entries (so it *always* skips), and (b) even past the skip, the body has **no assertion** (comment: "not asserted here"). **Verified:** full suite shows exactly 1 skip and it is this test. The rejection branch is reachable plain set-arithmetic and could be tested directly with a 3-optional-exit config. D071-final acknowledges "1 skipped" but does not note the missing assertion or a fix plan.

**Why it matters:** A hard-rule-#1 (§3.5) rejection branch has zero effective coverage. The production code is correct under the current grammar, so no live defect — but a future grammar expansion with >2 optional additions would be silently unguarded, violating CLAUDE.md TDD discipline.

**Recommended fix:** Build the violating config directly (attach 3 IDs from the optional pool, extending a synthetic `_S5_HYPOTHESIS_EXITS` entry in the test if needed), call `_s5_exits_match_hypothesis`, assert `passed is False` with "too many optional_additions". Remove the unconditional skip.

---

## LOW

### Grammar / validator

**L-1. GRAMMAR.md R3 narrative is stale (v2/D039 5-indicator + ETF-rejection expansion).** `docs/GRAMMAR.md:236-244`; impl `custom_predicates.py:187-199,769-820`. §3.1 / hard rule #10. The narrative still says "must reference `days_to_earnings` or `days_to_fomc`" (2 indicators) and has no version marker, while the live grammar (v2/D039) accepts 5 event-proximity indicators *and* rejects ETF underlyings paired with `days_to_earnings`. D039's file list omits GRAMMAR.md. R2 got a `(v2, D077)` marker; R3 did not. *Fix:* list all 5 indicators + the ETF rejection rule and add a `(v2, D039)` marker.

**L-2. DESIGN §3.5 C1 / GRAMMAR.md §C1 list 11 indicator families; contracts now defines 12 (adds `trend_strength`).** `docs/DESIGN.md:290`; `docs/GRAMMAR.md:82`; contracts `models.py:30-43,371-384`. §3.5 C1. Purely documentation lag — C1's code reads `im.family` dynamically with no hardcoded list, so it functions correctly on all 12. D019 added `trend_strength` to contracts but neither doc was updated. *Fix:* update both docs to 12 families, or defer to `crucible_contracts._INDICATOR_FAMILIES` as canonical.

**L-3. S5 implementation deviates from literal DESIGN §3.5 wording (required exits made substitutable) — operator-approved (D071-final) but §3.5 text never amended.** `custom_predicates.py:94-121`; `docs/DESIGN.md:279-285`. §3.5 S5 / hard rule #1. §3.5 still says "time stops required" / "convergence exit required"; the impl makes them substitutable via `required_from_set`. The change was operator-approved and logged (not silent), but DESIGN.md, GRAMMAR.md, and the code are in three-way disagreement. *Fix:* add a §3.5 S5 amendment note pointing to D071-final; confirm `time_stop` was intended to become fully optional for MR (vs always-required-plus-optional-zscore).

**L-4. C2 directional-family check is order-dependent and only inspects `indicators[0]`.** `custom_predicates.py:458-481`. §3.5 C2 / §4.5 (validator must accept any StrategyConfig). C2 derives family from `indicator_ids[0]` only; the justifying comment that "C1 restricts to one indicator-per-family" is wrong (C1 is strategy-level, not signal-level). A directional signal mixing `(sma_cross[trend], atr_pct[volatility])` passes/fails C2 depending on order. **Latent only:** the production sampler always builds directional signals with a single indicator (`sampler.py:247`), so no production path reaches it — but the validator must be authoritative for hand-authored/requeued configs. *Fix:* check all indicator families (order-independent); fix the comment.

**L-5. R1 IV-rank gate check ignores the comparison operator (`op`), only validating the threshold value.** `custom_predicates.py:708-734`. §3.5 R1 ("only fire when IV is cheap"). R1 checks `threshold <= 50.0` but never reads `op`, so `iv_rank {threshold:30, op:'>'}` (fires when IV is *expensive*) passes. **Latent only:** the sampler pins `op='<'` for iv_rank (`indicator_thresholds.py:178-181` default + `sampler.py:387`); exploitable only by externally-authored configs. *Fix:* require `op in ('<','<=')`; add a test for the inverted-op case.

### Enumeration

**L-6. `pairs_zscore` template params pass P1 only via the empty-schema escape hatch.** `sampler.py:581-628`; `custom_predicates.py:540-564`. §3.5 P1 / §4.2(a). The sampler injects 5 keys into `relative_value` signals; P1 tolerates unknown keys only when `allowed_keys` is empty (`:555`). Both the demo registry and the live production registry snapshot currently ship `pairs_zscore.params_schema={}`, so nothing fails today — but a future non-empty schema omitting those keys would mass-fail every `relative_value` config (risking EnumerationCapped). Forward-compatibility fragility, not a current defect. *Fix:* declare the 5 keys in the registry schema, or gate injection on the schema's declared keys; add a non-empty-schema test.

**L-7. Hypothesis-weight prior-mean constant `1.0/11.0` is a hand-mirrored duplicate of `rejection_weights.prior_mean()`.** `sampler.py:62-66`. No spec ref (correctness-of-weighting). Duplication is intentional (circular-import avoidance) and equals `prior_mean()` today; the CLI always passes `prior_mean()` into `apply_exploration_floor`, so the literal rarely fires. Risk is silent desync if `DEFAULT_BETA` changes. *Fix:* one-line invariant test asserting `_HYPOTHESIS_WEIGHT_PRIOR_MEAN == prior_mean()`.

**L-8. `lru_cache` makes enumeration depend on process-start filesystem state; proposer-written YAML is silently ignored mid-process.** `indicator_thresholds.py:280-281`; `sampler.py:103-104`. §13.1 / hard rules #4,#6. Both loaders cache for the process lifetime (docstrings say "restart to pick up changes"). The threshold proposer is a manual standalone script (not in-loop) and the universe file is Crucible-written, so the practical risk is operational: running `propose_threshold_tightenings.py` without restarting `forge.service` silently uses stale thresholds. *(Subsumed by the H-3 fix; tracked separately as the operational facet.)*

### Ranking / submission

**L-9. Rate limiter (§7.3) is silently skipped when `--crucible-db` is absent in `--loop`.** `main.py:1088` (guard `if crucible_db is not None and not dry_run:`) + `:1428-1430` (only `--inbox` required). DESIGN §7.3 / step 8. `forge run --loop --inbox X --no-config` (or `forge.yaml` lacking `crucible.db_path`) submits a full batch every `poll_interval_seconds` with no rate limiting. **Production default is safe** (`forge.yaml:9` supplies `db_path`); the vulnerable path is a dev/test invocation. *Fix:* add `if loop and not dry_run and crucible_db is None: raise typer.Exit(code=2)` after `:1430`, mirroring the inbox guard.

**L-10. `submission_failed` permanently burns the config_hash slot — transient inbox-write failures never retried.** `submitter.py:179-192`. §7.4 / hard rule #9. On `submit_candidate` exception the `pending` row is updated to `submission_failed` (terminal — `consumer.py:110` excludes it); no retry/cleanup. A re-derived config hits the UNIQUE index → `skipped_duplicate`, never reaching Crucible. §13.4 imposes the unique constraint but the spec is silent on retry, and the failure is observable (`failed_count` non-zero, error logged), so impact is marginal. *Fix:* DELETE/reset `submission_failed` rows before retry, or claim the slot only after the write succeeds. (Shares root with M-10.)

**L-11. Diversification config (`method`/`similarity_metric`) loaded from `ranker.yaml` is silently discarded by `rank_batch`.** `main.py:1068`; `ranking/queue.py:30-64`. §6.3. The CLI keeps only `.weights`; `rank_batch` hardcodes `jaccard_signal_ids` + greedy. The loader validates only `method='greedy'`/`similarity_metric='jaccard'` (so an invalid edit raises, not silent misbehavior), and §6.3 confirms "greedy in v1" — no runtime impact today. The footgun is the misleading `ranker.yaml` comment `# 'greedy' or 'dpp'` and a future-wiring gap. *Fix:* thread `RankerConfig.diversification` through `rank_batch`, or document the block as reserved in v1.

### Prefilters

**L-12. Per-config-only prefetch path (`forge prefilter`) makes the permutation null pool degenerate → forced reject.** `battery.py:77-79`; `main.py:305`; `crucible_feature_cache.py:290-301`. §5.3.7. When only `prefetch_for_config` runs, the null pool is exactly that config's own activation-date returns: with `horizon=0`, `p_value` is forced to 1.0; with the production-default `horizon=5`, `effective_n=0` → `p_value=1.0`. Always reject. **Not production:** `forge run` uses `_run_battery_for_seed` → `prefetch_for_batch` (rich pool); the broken path is the `forge prefilter` diagnostic command with the writer socket up. Note `_window_loaded_for` (`:88,126,198`) is set but never read. *Fix:* make `prefetch_for_config` load full-window returns, or document the demo path's permutation verdicts as not data-grounded.

**L-13. `SyntheticFeatureCache.returns()/regime_label()` ignore the underlying (latent D033-class miscalibration in tests).** `feature_cache.py:93-102`. No spec ref. Seeds purely on date (`return:{d}`, `regime:{d}`) — no underlying, unlike `CrucibleFeatureCache` (D033). A multi-underlying batch on the synthetic cache gives every ticker identical returns/regimes per date. D080 refuses synthetic in production, so contained to dev/test. *Fix:* incorporate the active underlying into the synthetic seed for parity, or assert single-underlying in tests.

**L-14. `prefetch_for_batch` uses a single per-group sentinel spec — but the per-config fallback recovers (lower impact than claimed).** `crucible_feature_cache.py:200-249`. §5.3.6/§5.3.7. The window fetch uses `group[0].signals[0]` as a sentinel; if its feature_map is empty, the batch-level optimization produces nothing. **Corrected mechanism:** `_window_loaded_for.add` (`:198`) is a dead write (read nowhere); the actual re-fetch guard is `missing_dates = all_activations - _returns[underlying].keys()`, so `prefetch_for_config` re-issues per-config window fetches that *do* recover. The real cost is one wasted batch round-trip per partition + silent loss of the amortization goal — not a silenced partition. *Fix:* assert the batch window fetch populated something (coverage > 0 when `missing_dates` non-empty); log/retry with an alternate sentinel.

### Hard-rule invariants & coverage

**L-15. Hard rule #8 RNG invariant misses every determinism-breaking pattern except the two literal forms.** `tests/invariants/test_phase0_invariants.py:20-21,54-62`. Hard rules #8/#6. Only matches `random.seed(` and `np.random.default_rng(`. `random.Random()`, `random.Random(42)`, `rng.seed(x)`, `np.random.RandomState`, `Generator(PCG64(...))`, `secrets.*` all pass green. **No current violation** (exhaustive grep of `src/forge/` finds zero out-of-hierarchy RNG; the blessed `seed.py:29` uses the constructor form, so the scan needs a path-aware allow-list like the datetime test). *Fix:* broaden to a path-aware allow-list (only `seed.py` may construct RNGs) matching `random\.Random\s*\(`, `\.seed\s*\(`, `np\.random\.(default_rng|RandomState|Generator|PCG64|SeedSequence)`, and add `secrets`.

**L-16. No positive-control (canary) test proving the hard-rule-#8 clock/RNG invariants actually fire.** `tests/invariants/test_phase0_invariants.py:43-62`. Hard rule #8 / CLAUDE.md TDD ("prove the invariant fires"). Both tests are pure negative scans (`assert not offenders`); no test feeds a known-bad string through the regexes to confirm they match. A silent regex regression would leave both green. *Fix:* add a meta-test running `_DATETIME_NOW`/`_RANDOM_SEED`/etc. against representative offender strings (asserting match) plus a negative control.

**L-17. Hard rule #10 pre-commit version-bump hook is configured but not installed in `.git/hooks`.** `.pre-commit-config.yaml`; `.git/hooks/pre-commit` (absent). Hard rule #10 / §13.2. The `grammar-version-bump` hook is declared and its script well-tested, but `pre-commit install` has not been run on this checkout — enforcement depends on the operator. **Two compensating runtime controls exist:** `forge.grammar.archive` raises `GrammarVersionError` on hash drift at load (D015), and the `grammar_versions` audit table (D049). The hook is defense-in-depth. *Fix:* add `pre-commit install` to setup/CI; add an invariant parsing `.pre-commit-config.yaml` to assert the hooks remain present.

**L-18. Hard-rule invariant scans exclude `scripts/`, and an operator script writes Crucible's inbox bypassing `submit_candidate`.** `tests/invariants/test_phase0_invariants.py:16` (`SRC_ROOT = src/forge`); `scripts/requeue_high_value_configs.py:229-231` (raw `shutil.copyfile + rename`). Hard rule #2 / blessed-APIs. The #2/#5/#8 scans never cover `scripts/`. The requeue tool is a documented operator recovery escape-hatch (D048), not imported by the production loop, and currently contains no `datetime.now`/RNG/crucible-internal violations. *Fix:* extend the scans to `scripts/` (or document it out-of-scope), and prefer routing requeues through `submit_candidate` (or annotate the raw-copy as recovery-only).

### Other coverage / dead code

**L-19. `threshold_proposer` `config_json` robustness branches untested despite parsing mixed-shape Crucible exports.** `threshold_proposer.py:104-127`. §5.5 / D073. `_extract_thresholds_per_role` advertises robustness ("string vs dict, missing keys") but the JSON-decode-fail / non-dict / bad-role / non-numeric branches (`107-112,117,120,124`) are 0%-covered; no test feeds malformed input. Branches are graceful-degradation (return `[]`), so a real export schema change would silently extract nothing rather than crash. (Note: the referenced "D083" does not exist; last entry is D082.) *Fix:* table-driven tests for each malformed shape.

**L-20. `core/config.py` is dead code with 0% coverage.** `src/forge/core/config.py:1-23`. CLAUDE.md Style ("don't over-build"). `load_yaml` has no production caller (every YAML consumer does inline `yaml.safe_load`); its `isinstance(result, dict)` guard is never reached. *Fix:* delete it, or route consumers through it and test the `ValueError` path.

---

## INFO

**I-1. Structural hard-rule-#4 check: PASS — no automatic path can loosen `grammar.yaml`/`prefilter.yaml`.** All cited evidence independently confirmed: no `apply_loosening` symbol exists anywhere in `src/forge/`; `calibration.py:361-363` raises on non-tighten; `auto_tune.py:272-279` routes below-min exclusively to `OPEN_PROPOSALS.md`; `grammar_cmd.py:242-251` hard-exits on non-`tighten`; `indicator_thresholds.py:319-320` skips any baseline-widening entry; `grammar revert` requires operator `--initials`. Hard rule #4 is structurally enforced across every relevant path. *(Optional: add an invariant asserting `forge grammar apply-proposal` exits non-zero for a loosen proposal_type.)*

**I-2. Hard rule #5 LLM-import invariant covers only 4 named SDKs; common alternatives (litellm, langchain, transformers, vertexai, ollama, mistralai, boto3) bypass it.** `test_phase0_invariants.py:32-36`. **No current violation** — none of these appear in `src/forge/` or any dependency file. The rule's intent (no LLM present) is met for today's threat surface; this is incompleteness, not exposure. *Fix (optional):* invert to a dependency-allowlist check, more durable than chasing SDK names.

**I-3. R3 ETF-incompatibility fall-through is effectively dead code under a grammar-valid config.** `custom_predicates.py:790-801`. §3.5 R3/C1. After matching an ETF-incompatible event indicator, R3 `continue`s to scan for an alternative — but all 5 event-proximity indicators are `calendar` family and C1 forbids two same-family indicators, so a grammar-valid `volatility_event` config has at most one calendar gate. Behavior in isolation is correct (ETF+`days_to_earnings`→False; single-name→True). *Fix (optional):* simplify the loop to a single-gate check with a comment noting C1's guarantee.

**I-4. Validator-side R3 ETF enforcement confirmed correct — narrows open Q18 to the sampler/requeue path.** `custom_predicates.py:769-820`; OPEN_QUESTIONS.md:362-383. Q18 explicitly noted the validator path was unverified; this audit confirms `_r3` rejects `SPY+days_to_earnings`. The ~10 shipped ETF configs were the pre-D055 requeue gap (v1-era configs shipped without grammar-version checks), not a validator bug. *Action:* when resolving Q18, focus on `scripts/requeue_high_value_configs.py` and any path not re-running `validate()`.

**I-5. expected_trades cold-start hold-days use entry-DTE midpoints, not holding period.** `expected_trades.py:38-42,89-91`. §5.3.4/§3.5 P2. `_HOLD_DAYS_BY_BUCKET = {15,35,75}` uses entry-DTE midpoints; §5.3.4 wants hold time (entry_DTE_mid − exit_DTE_mid ≈ 11.5/29/49.5). **Direction note:** using the larger entry-DTE values makes capacity *smaller* → the filter is marginally *stricter*, not weaker (contra the original claim). Per Q16 the capacity cap is rarely binding (n_activations dominates), and the heuristic is cold-start-only (D076). Negligible practical impact. *Fix (optional):* use the holding-period values or rename the constant to reflect it is time-to-expiry.

**I-6. STATUS.md v4 zero-trade claim (36% vs 61.6%) is directionally validated but imprecise.** STATUS.md:5. §1.2. Live join (gated_runs ↔ `batch_summaries.grammar_version`): v4=29.8% (n=258), v1=80.5%, full-export mixed=61.7%. The improvement is genuine but: (a) "36%" is now ~30%; (b) "61.6% legacy" is the mixed-window figure (dominated by old v1), not a pure v1 baseline (v1 alone ≈83%); (c) the v4 cohort is skewed (volatility_event/regime_arbitrage only; relative_value/mean_reversion/tail_hedge ≈0 v4 gated — caveat already partly noted in STATUS). Reporting fidelity, no code defect. *Fix:* report v4 as ~30% (n=258), label 61.6% explicitly as the mixed/legacy baseline.

**I-7. Open-question triage against live behavior — Q16 fixed-verified; Q13 superseded; Q21 resolved-verified; Q17 Forge-side-mitigated; Q9/Q10/Q19/Q20 correctly open. One correction: Q22 is NOT resolved.** OPEN_QUESTIONS.md. Live `prefilter_rejections` confirm expected_trades now rejects ~3,250/5,000 (Q16/D076 working; was a structural no-op); permutation_test no longer the sole killer (Q13 superseded); Q21 closed by D082 with prefetch plateaued ~1,500–1,680s. **Correction to the source triage:** Q22 (prefetch 17–38 min/batch, ~10k unique-spec cache misses) has *no* Resolution block and is *not* closed by D082 — do not conflate. Also: contracts 1.12.0 ships `universe_min_asof`, but Forge has zero code consuming it (grep finds no reference), so **Q19 remains open from Forge's side**. *Action:* annotate Q13 (superseded by D076), confirm Q16 fixed, note Q17 Forge-side-mitigated; keep Q22/Q9/Q10/Q19/Q20 open; re-prioritize H-1 above all open Qs.

---

## Verified Correct / Strengths

The audit independently confirmed the following are sound:

- **Hard rule #4 (auto-loosening) is structurally airtight** (I-1). Every automatic path that could touch `grammar.yaml`/`prefilter.yaml` is tighten-only or routes loosenings to `OPEN_PROPOSALS.md`; no `apply_loosening` symbol exists; the threshold-proposer reader defensively skips any baseline-widening entry; `grammar revert` requires operator initials. This is the dimension's central guarantee and it holds.
- **The R3 ETF-incompatibility validator is correct** (I-4) — `volatility_event` + ETF underlying + `days_to_earnings` is rejected. The shipped ETF configs were an upstream requeue-path artifact, not a validator bug.
- **Within-process enumeration determinism holds.** The lru_cache ensures consistency within a single run; the violation (H-3) is strictly cross-process/cross-day on file-state transitions.
- **The grammar validator is authoritative and mostly precise.** C1 reads families dynamically (correct on 12 families despite stale docs); R3's ETF fall-through, while dead code, is correct in isolation; the S5 `required_from_set` logic matches the operator-approved D071-final design.
- **Q16/Q13 are genuinely resolved in production** (I-7) — the expected_trades filter is no longer a structural no-op (rejects ~3,250/5,000), and permutation_test is no longer the sole killing filter.
- **The atomic-write pattern exists and is correctly used** in `proposal_writer._atomic_write` (the H-6 fix is to extend it, not invent it).
- **Hard-rule invariants for clock/RNG/LLM/crucible-internal have no current violations** — the gaps (L-15, L-16, I-2, L-18) are all about preventing *future* regressions, not active breaches.
- **The D077–D079 grammar work measurably improved zero-trade rates** (I-6): v4 ≈30% vs v1 ≈83%, a real and verifiable gain (on a narrow cohort).

---

## Recommended Next Actions (ordered, most impactful first)

1. **Restore §7.3 flow control (H-1, H-4, M-7, M-10 rate-limiter facet).** File a Decision Log entry acknowledging D046+D052 void §7.3. Make `pct_gated` count only real (non-sentinel) gates and add a status filter to the rate-limiter query; wire `inflight_threshold` from `forge.yaml` into `check_rate_limit`. This is the single highest-leverage fix — it re-couples submission rate to Crucible throughput and stops the unbounded-queue state.
2. **Revive the feedback loop in `--loop` (H-2).** Feed `reconcile_all_pending`'s `BatchFeedback`s into `analyze_batch`/`record_promoted_patterns`/`propose`/`auto_tune`; stop analyzing the just-submitted 0-gated batch. Restores §2.1 steps 10–11.
3. **Close the determinism gaps (H-3, H-7, M-14).** Add `auto_tightenings_yaml_hash` + universe identifier to `mint_batch_id`, `registry_hash`'s effective key, and `batch_summaries` (+ a `seed` column). Add the cross-process toggle invariant test. Prefer sourcing the universe from `RegistrySnapshot` (also resolves H-5).
4. **Make config writes crash-safe (H-6, M-1, M-11).** Convert `write_calibration_yaml` to atomic tmp+rename; write the `grammar_versions` audit row *before* the YAML mutation; add a targeted per-iteration exception guard in the loop (log-and-continue with backoff, but do not swallow `SchemaVersionMismatch`). Removes the daemon-brick and crash-loop paths.
5. **Resolve the hard-rule-#2 universe read (H-5, M-13).** Surface `universe_tickers.json` as a contracts gap; until contracts lands it, revert to the hardcoded list or add loud-fallback logging. Pairs with action 3.
6. **Fix the permutation/feature-cache data-coverage chain (M-2 → M-3, M-4, L-12).** Prefetch the full permutation window (and horizon-shifted dates) per underlying so the null pool is the real return series; this is the root cause that makes D082/D075 no-ops and the demo path degenerate.
7. **Add per-underlying degraded-response detection + observability (M-5, M-6, L-14).** Detect empty/partial windows, raise/short-circuit to a `data_unavailable` verdict, and emit cache telemetry (`cache_misses`/`window_hash`). Stops thin-data false-rejections from polluting the D076 priors.
8. **Tighten the auto-tune knobs that actually gate (M-8).** Have `apply_tightening` adjust `min_pass_probability` (the D076 primary expected-trades knob), or document the exemption — and reconcile the analyzer (≥2) vs proposer (≥4) promoted-pattern thresholds.
9. **Restore documentation/spec sync (M-15, M-16, L-1, L-2, L-3).** Rewrite GRAMMAR.md §S5/§R3, add the §3.5 S5 amendment note, update the family count, and write the missing `K_MAX_OPTIONAL` failure-mode test (with assertions, no skip). Add a content-aware doc-sync hook.
10. **Harden the invariant test suite and close the small gaps (L-9, L-10, L-15 through L-20, M-9, M-12).** Broaden the RNG/LLM scans (path-aware allow-list / dependency allowlist), add positive-control canaries, install the pre-commit hook, add `check_contracts_version()` to `forge feedback`, add `days_to_cpi/nfp/opex` threshold entries, guard the `--crucible-db`-absent loop path, and delete `core/config.py`.

---

*End of report. 48 findings post-dedup: 0 Critical, 7 High, 16 Medium, 18 Low, 7 Info. The producer-side core (grammar validation, hard-rule-#4 enforcement) is sound; the closed-loop machinery (flow control, feedback, cross-process determinism, crash-resilience) is where the work is.*
