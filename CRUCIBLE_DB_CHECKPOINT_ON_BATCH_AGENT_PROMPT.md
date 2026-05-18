# Crucible — DuckDB checkpoint-on-batch in `db_writer.service`

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-17 — operator approval after Forge-side diagnostic audit (`OPTION_B_CROSS_SECTIONAL_RANK_SCOPING.md` adjacent, this is a separate operational fix).
**Status:** Single contained fix. Operational throughput, no schema or contract changes.

---

## 1. The pattern

Forge-side Explore agent ran a slowdown diagnostic on 2026-05-17 at ~10:25 PT. Findings:

```
db_writer.wal:        ~52 MB         (and growing)
runs.duckdb.wal:      ~14 MB         (and growing — was 8.4MB at 10:25, 13.9MB at 10:38)
db_writer process:    1.2 GB resident, 11-14% CPU sustained
backtest run pace:    pre-2026-05-16: 17-27 min/run
                       post-D032 + D033: 80 min/run (~3-4x slowdown)
```

The agent's root-cause hypothesis: WAL accumulation without checkpoints + feature-cache cold misses post-Tier-2 backfill. The two compound — heavy write churn + cold-compute on backfilled tickers + no checkpoint means each subsequent run pays elevated I/O latency.

## 2. The fix request

Add an explicit `CHECKPOINT` (or `PRAGMA wal_autocheckpoint(N)` config) to `db_writer.service`'s commit cycle. Targets:

- After every Nth `process_batch()` call (e.g., N=10 batches, or every 60 seconds) issue `conn.execute("CHECKPOINT")` to flush the WAL into the main DB file.
- OR: set a `wal_autocheckpoint` threshold so DuckDB auto-checkpoints at a known WAL size (e.g., 32MB).
- Whichever is cleaner per DuckDB's idiomatic pattern.

Goal: bound the WAL size, keep fsync latency predictable, reduce per-run baseline by ~20-30 sec.

## 3. What you should NOT do

- **Do not switch to a different DB.** DuckDB is the canonical store; this is a tuning fix, not a migration.
- **Do not change Forge code.**
- **Do not skip the test.** Add an invariant in `tests/integration/test_db_writer.py` (or equivalent) that asserts:
  - After N batches, WAL size is bounded
  - No data is lost (read a row written pre-checkpoint and verify it persists)
- **Do not drop write-ahead-log entirely.** WAL is correct; checkpoint cadence is the question.
- **Do not block on every checkpoint** if it adds tail latency to individual writes — checkpoint cadence should be background or batched.

## 4. Questions to answer (briefly)

1. **Idiomatic DuckDB pattern**: is `PRAGMA wal_autocheckpoint(N)` the right knob, or should the writer issue explicit `CHECKPOINT` calls? Cite DuckDB docs or your reading of `optbt/persistence/db_writer.py`.
2. **Cadence**: what's the right N (batches per checkpoint) or time interval? Reasoning?
3. **Failure mode**: what happens if a checkpoint hits a long-running transaction? Need a fallback?
4. **Concurrency**: does checkpoint block the writer? If yes, schedule it during a known-idle window (e.g., when the inbox is empty).

## 5. Background data sources

- `db_writer` impl: `/home/aj/proj/Crucible/src/optbt/persistence/db_writer.py`
- `runs.duckdb.wal` live state: `~/optbt_data/runs.duckdb.wal`
- Forge-side diagnostic agent's full report is in the Forge session transcript; key citations:
  - WAL bloat with no checkpoint
  - db_writer holds 1.2GB resident
  - Compounded slowdown post-Tier-2 backfill

## 6. Output expected

1. Confirmation diagnosis is right (or pushback)
2. Fix shipped — small in scope (~10-20 lines + a test)
3. Verification: WAL size bounded under load; run pace recovers measurably
4. Decision Log entry in the canonical Crucible-side log citing this prompt

## 7. Note: not on the critical path for tonight

This fix improves baseline throughput but doesn't help Forge ship its first D033 (Tier 2) batch faster — that batch's bottleneck is **feature-cache cold misses** for the 23 newly-introduced underlyings (AAPL/NVDA/etc.), which is a CPU-bound compute problem, not a WAL/I/O problem.

If you have spare cycles after the checkpoint fix, the **bigger win** is **pre-warming the Tier 2 feature cache** — when the universe-publisher service (or whatever runs `ingest_universe.py`) completes a tier expansion, automatically schedule a feature-cache pre-compute for the new tickers' bars. Otherwise Forge's first Tier 2 batch pays N×M tickers×features of cold-compute serially. Surface as a follow-up if it's bigger scope than this prompt.

Brief is OK. Aim for under 400 words.
