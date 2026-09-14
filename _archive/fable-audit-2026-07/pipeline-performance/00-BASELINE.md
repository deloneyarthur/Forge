# Baseline measurements — 2026-07-01

Ground truth to compare against after each fix. All numbers measured on aj-workstation
2026-07-01 unless dated otherwise. Journal timestamps below are PDT (journalctl local
time); structlog lines inside messages are UTC.

## 24h cadence (journalctl, 2026-06-30 ≈14:45 → 07-01 14:45 PDT)

- **467–469 loop iterations**: 94 full batches, ~373–375 §7.3-blocked, 0 skipped.
- Blocked reason throughout: `blocked: in-flight depth 6xx exceeds cap 600 (§7.3
  backpressure)` — the D196/D200 depth cap; depth oscillates ~601–796 as Crucible drains.
- Poll interval **60s** (`config/forge.yaml` `poll_interval_seconds: 60`; the §7.3 design
  default is 600 — `src/forge/cli/main.py:2182` `_RUN_DEFAULT_POLL_INTERVAL_SECONDS`).
- Blocked iteration ≈ **33s work + 60s sleep ≈ 93s cadence** (iteration marker →
  `blocked:` line gap is 31–35s: that is reconcile).
- Full iteration ≈ **468s work + 60s sleep ≈ 8–9 min**.

## Phase timings (journal `phase_timings:` lines, 20-sample range on 07-01)

| Phase | Range | Notes |
|---|---|---|
| reconcile | 29.9–37.1s | runs EVERY iteration, incl. blocked |
| (untimed stanza) | ~28s | weight loaders + fingerprints + cache build — in NO bucket (F6) |
| enumeration | 0.6–1.5s | |
| prefetch | 127–215s | 5,000 configs / 124 underlyings |
| battery | 33.8–51.2s | ~3,750 configs reach tier 9 |
| rank | 5.4–8.1s | |
| submit | 187.8–205.3s | batch_size=200 survivors + ~31k rejected-row writes |

## Anatomy of one loop iteration (code-attributed, `_run_one_iteration` main.py:1602)

Every iteration (blocked AND full), in order:
1. `check_contracts_version()` — main.py:1683 — ~0.
2. `load_grammar` + archive byte-compare — main.py:1685; grammar/loader.py:120-145 — ~ms.
3. `load_calibration`, `load_ranker_config` — main.py:1688-1689 — ~ms.
4. `load_registry()` — registry_loader.py:56-90 — ~ms (snapshot is 13.6KB; NOT a hotspot).
5. `_ensure_grammar_version_recorded_silently` — main.py:1702 — ~0.1s (write-mode DuckDB
   open runs full `ensure_schema` DDL, db.py:37-56).
6. **`_reconcile_pending_silently`** — main.py:1718-1720 → consumer.py:413-482 — **~31s**.
7. `check_rate_limit` — main.py:1721 → rate_limiter.py:126 — ~0.6–1s (its own full 57MB
   export parse + 3 separate DuckDB opens).
8. Blocked → return (total ≈ 32–34s work).

Full iterations continue:
9. `_fetch_promoted_configs` + **9 weight loaders + trade_rate_priors** — each re-reads
   the 57MB export independently — ~20s total (F3).
10. `_load_prior_structural_fingerprints` + fresh `FeatureCacheClient` + probe —
    main.py:1252, 1310, 1315 — ~5–8s (F5).
11. enumeration ~1s → 12. prefetch 138–215s (F10/F11) → 13. battery 36–50s (F12) →
14. rank ~6s → 15. submit 195–202s (F1) → 16. post-submit feedback chain ~2s (re-parses
    the export again, F3; re-runs `load_registry` — journal shows 560 registry loads vs
    467 iterations).

## Resource accounting

- Service CPU: `CPUUsageNSec` = 127,041s over 2.79 days uptime ≈ **12.6 CPU-h/day**
  (≈53% of one core continuously; `ps` concurs).
- RSS 3.6G steady, peak 4.7G, swap ~15MB after 2.8 days → churn, not a leak.
- Box: 64 cores, 123GB RAM, load ~11.4 (Crucible backtest workers dominate).
- Journal volume: 5,263 lines / 1.20 MB per 24h; the ~9–15KB
  `feature_cache_prefetch_batch` coverage dumps are ~70% of it (F19).

## DB / disk (snapshot-dependent; two snapshots used)

| Table | Rows | Source |
|---|---|---|
| pre_filter_logs | **34.9M** (Jul-1 04:00 backup) / **36.4M** (Jul-1 daytime copy) | ~2GB data + ART PK index; ZERO readers in src/ or scripts/ (grep-verified) |
| submissions | 254,189 (backup) / 264,189 (live export `forge_submission_versions.json`) | |
| verdicts | 130,322–140,451 | |
| shadow_scores | 145,200–155,200 | |

- forge.db: 4.51GB (Jun 24) → **5.75GB** (Jul 1) ≈ **+180–250MB/day**, dominated by
  `pre_filter_logs` (~31k rows/batch × ~94–110 batches/day ≈ 3.4M rows/day).
- `~/forge_data` = 56GB, of which `backups/` = **46GB** (KEEP=14 rotation, 10 dailies so
  far → ~80–90GB steady state, same single NVMe). Stray file outside retention:
  `~/forge_data/forge.db.bak-pre-flush-20260624` (4.5GB).
- Gated export `~/optbt_data/exports/gated_runs_*.json`: ~57MB, rolling 10k window,
  republished ~every 65s.
- Disk headroom: 326GB free of 815GB (58% used) — watch item, not an emergency.

## Micro-benchmarks (read-only, production-scale scratchpad copy of forge.db; duckdb 1.5.2 / pydantic 2.13.4)

| Operation | Measured |
|---|---|
| `executemany` fsync behavior | **1,003 fsyncs per 1,000-row executemany** (strace -c) |
| duckdb-python executemany binding CPU | ~1.05 ms/row (table-size independent — client overhead) |
| Rejected-rows write, 27.2k rows, as-is (tmpfs = CPU only) | 28.8s CPU (+ ~155–160s fsync on NVMe est.) |
| Same rows via temp CSV + `INSERT … SELECT FROM read_csv(...)` | **0.14s** (~200×, one fsync) |
| Same rows, executemany wrapped in one txn | 105.8s — WORSE (txn-local version-chain cost) |
| Same rows, chunked multi-row VALUES | 15.8s (parse scales with placeholders) |
| `record_verdicts` full pass @ verdicts=140k | 16.6–20.4s, **even when 0 rows are new** |
| Set-based ANTI-JOIN verdict insert | ~0.01s |
| 57MB export load: json.loads + 10k `GatedRun.model_validate` | 0.85–1.24s per call |
| Same, limit=1000 (rate limiter) | 0.53s (json.loads is the whole file regardless of limit) |
| `StrategyConfig.model_validate_json` | ~9–10µs/row |
| `compute_structural_fingerprint` | ~14µs/row |
| `extract_features` (ranker) | ~6µs/config |
| IRLS train (pure Python, d≈85) | ~1.7ms/row, linear (1k→2.0s, 4k→6.7s) |
| permutation_test per config (production sizes) | 2.6–12.2ms (window+dict rebuild ≈1.1ms) |
| DuckDB connect + ensure_schema | 0.07–0.09s per open |
| Funnel export write (incl. 8MB version map) | 0.23s |

## How to re-measure

```bash
# Phase timings + cadence (compare these after every deploy)
journalctl --user -u forge.service --since "24 hours ago" --no-pager | grep -c "loop iteration"
journalctl --user -u forge.service --since "24 hours ago" --no-pager | grep -c "phase_timings"
journalctl --user -u forge.service --since "24 hours ago" --no-pager | grep "phase_timings" | tail -20
# CPU / RSS
systemctl --user show forge.service -p MemoryCurrent -p CPUUsageNSec -p ActiveEnterTimestamp
# DB stats — NEVER open the live DB; snapshot first
cp ~/forge_data/forge.db /tmp/forge_snap.db   # or use the newest ~/forge_data/backups/ file
# then: SELECT count(*) FROM pre_filter_logs; etc. on the copy
du -sh ~/forge_data/backups; ls -la ~/optbt_data/exports/gated_runs_*.json | tail -1
```
