# Task: investigate live behavior / query state

Scope: diagnosing the running pipeline or analyzing results. Read `STATUS.md`'s top block first —
the anomaly may already be diagnosed.

## Service health

```bash
systemctl --user list-units 'forge*' 'crucible*'
journalctl --user -u forge.service -n 50 --no-pager
journalctl --user -u forge.service --since '1 hour ago' | grep -E 'blocked|error|Traceback|submitted'
```

## Forge DB (the lock trap)

The running service holds an intermittent RW lock on `~/forge_data/forge.db` that blocks even
`read_only` opens. Snapshot first; the copy is consistent (DuckDB file copy):

```bash
cp ~/forge_data/forge.db /tmp/forge_snapshot.db
python -c "import duckdb; print(duckdb.connect('/tmp/forge_snapshot.db', read_only=True).sql('SELECT status, COUNT(*) FROM submissions GROUP BY status'))"
```

Useful queries (tables: `docs/MANPAGE.md` FORGE STATE DB):

```sql
-- Recent batches
SELECT forge_batch_id, submitted_at, batch_size, promotion_rate, common_failures
FROM batch_summaries ORDER BY submitted_at DESC LIMIT 10;
-- Status of the latest batch
SELECT status, COUNT(*) FROM submissions
WHERE forge_batch_id = (SELECT forge_batch_id FROM batch_summaries ORDER BY submitted_at DESC LIMIT 1)
GROUP BY status;
-- Pending proposals / grammar audit trail
SELECT proposal_id, proposed_at, proposal_type, rationale FROM grammar_proposals WHERE status='pending';
SELECT version, change_type, decided_at, operator_initials FROM grammar_versions ORDER BY decided_at DESC LIMIT 20;
```

## Crucible exports (Forge's only read path into Crucible)

```bash
ls -t ~/optbt_data/exports/gated_runs_*.json | head -1   # fresh = < ~2 min old
```

Join export rows to `submissions` on `config_hash`. The export is a rolling **top-10k** window.

## Cohort hygiene (gets analyses wrong silently)

- Split by `grammar_version` (in the export since contracts 1.15.0). Pre-v5 re-gated rows carry
  `grammar_version=None` — exclude them or they dominate "recent" aggregates (the D103 trap).
- v9's true code cutover is **2026-06-06T06:48:49Z** (reboot-deploy), not the 06-07 migration (D104).
- Timestamps before 2026-06-07 are PDT; after, UTC. Convert before joining DB rows or journals.
- **Exception:** the gated export's `decided_at` is tz-naive LOCAL (PDT) even post-migration
  (verified 2026-06-09: run `7f5731b6` decided_at 11:37:46 vs its `runner_done` at 18:37:47Z).
  `exported_at` in the same file IS UTC. Fix requested via
  `PROMPT_CRUCIBLE_RUNNER_CAPACITY_STABILITY.md`; until it lands, add 7h before comparing
  `decided_at` to journals or `utc_now()`.
- Post-D105, the sampler is weighted — condition scans on the live weights (no more
  quasi-randomization).

## Benign signals — do not "fix" these

- `blocked: prev batch N% gated` — the §7.3 limiter doing its job (Crucible backpressure).
- `crucible-ingest-daily` unit "failed" — rfr-only oneshot failure; bars/chains fine.
- `skipped: real feature cache unavailable` — `--require-real-cache` correctly skipping an
  iteration while Crucible's db-writer is down/restarting.

## When "blocked" IS a wedge

Hours of consecutive blocks while exports stay fresh and Crucible's runner is gating → check the
aged-out flush watermark logic in `feedback/consumer.py` (history: D052 → D061 → D110) and whether
the pinned oldest batch predates a code change (skip procedure: `docs/HOW-TO.md`).
