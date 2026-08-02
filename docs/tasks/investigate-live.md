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
`read_only` opens. Snapshot first; the copy is consistent (DuckDB file copy).

**Use the helper — do NOT hand-roll a `cp`, and NEVER snapshot into `/tmp`:**

```bash
SNAP=$(scripts/live_db_snapshot.sh)          # real disk, reused if <15 min old, path on stdout
uv run python -c "
from pathlib import Path
from forge.persistence.db import db_connection
with db_connection(Path('$SNAP')) as c:
    print(c.execute('SELECT status, COUNT(*) FROM submissions GROUP BY status').fetchall())
"
scripts/live_db_snapshot.sh --clean          # when you are done
```

> **⚠️ WHY (2026-08-02, learned the expensive way).** This section used to say
> `cp ~/forge_data/forge.db /tmp/forge_snapshot.db`. **`/tmp` on this box is a 62 GB tmpfs —
> RAM — and the live DB is 6.7 GB.** Nine investigation snapshots in one session filled it and
> **took the shell down twice**: every command, including `true` and `/bin/echo`, returned exit
> 1 with *no output*, because the harness could not write its own output capture. It does not
> present as "disk full", it presents as the tooling being broken, and it cost a mid-task
> investigation both times. The helper enforces real disk, reuses one snapshot instead of
> making a new 6.7 GB copy per question, and gives you `--clean`. `python` is also not on PATH
> here — use `uv run python`, per the same class of stale instruction.

Note the daemon writes to the tree it runs from, so a snapshot ages the moment you take it;
`--force` re-copies when you need the current state rather than a fresh-enough one.

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
- `decided_at` eras: exports published AFTER 2026-06-09T22:55Z emit tz-aware UTC (Crucible
  fixed storage + export end-to-end, D117); on-disk export files from before then carry
  naive LOCAL values (mixed eras — do not trust them without the +7h correction). The
  `verdicts` table was repaired once via `scripts/migrate_verdicts_decided_at.py` (script
  retired 2026-07-20, D295 — recoverable from git history); rows
  written after the fix are correct at ingest.
- **Cost-floor value era: hard-cut at `2026-06-09T22:52:57Z`** (Crucible-confirmed exact
  restart; their "~23:09" STATUS note is the deploy-sequence tail). WF/CPCV/Sharpe **values**
  decided before the cut were priced with zero slippage — never learn from or compare gate
  values across the cut (D124).
- **Coverage honesty is a row marker, not a time-cut:** trust
  `gate_results["regime_coverage"].passed == true` AND `detail` NOT containing
  `'coverage_unverified'` — byte-for-byte Crucible's `honest_regime_coverage` predicate.
  Real coverage floors went live 2026-06-10T01:00:02Z (pairs) / 01:28:03Z (rank); earlier
  rank/pairs coverage passes are unverified (D124).
- **Fullhist-refit children re-gate under the same `config_hash` with a new `run_id`** —
  `verdicts` holds both parent and child rows; lineage pointer at
  `universe_json.submission_metadata.fullhist_refit_of` (D124).
- **Earnings-calendar eras (D130, two-stage):** the forward calendar NEVER existed before
  **2026-06-10T17:05:01Z** (`days_to_earnings` = 999 every bar before it → `<`-gates never
  admitted; exposure contained at 86 prefilter-era submissions, zero verdicts). Indicator-side
  reads are real from 17:05:01Z; **the mandatory `earnings_exit` only fires from Crucible's
  NEXT runner restart after that** (wiring `1ca0361` — boundary flagged by them when it lands;
  check D130/STATUS for the timestamp). Every backtest decided before the exit-side boundary
  HELD THROUGH EARNINGS, every single-name config. Post-boundary protection is PARTIAL, not
  binary: filing-date anchors are late for ~32.5% of events (their §20 probe) — do not read
  the era flip as full earnings-risk exclusion.
- Post-D105, the sampler is weighted — condition scans on the live weights (no more
  quasi-randomization).

## Benign signals — do not "fix" these

- `blocked: prev batch N% gated` — the §7.3 limiter doing its job (Crucible backpressure).
- `crucible-ingest-daily` unit "failed" — rfr-only oneshot failure; bars/chains fine.
- `skipped: real feature cache unavailable` — `--require-real-cache` correctly skipping an
  iteration while Crucible's db-writer is down/restarting.
- Crucible runner/db-writer "Consumed … N G memory peak" on a CLEAN stop — a deploy restart,
  not an OOM or leak; the systemd peak counts reclaimable page cache (D117). The
  flag-worthy signal is an `oom-kill` line, nothing else.

## `blocked: crucible stalled` — the D137 stall guard fired (NOT benign, but self-clearing)

Distinct journal line from the benign `prev batch N% gated`:
`blocked: crucible stalled — no decisions since <ts> (<X.X>h); <N> configs pending ≥3h`.
The §7.3 stall guard (`submission.stall_after_seconds`, default 3 h) tripped — Crucible's
decision clock `max(decided_at)` has been stale ≥3 h while Forge has work submitted after it.
This is the guard working as designed (it would have caught the 2026-06-10 wedge at +3 h
instead of +18 h). It is **stateless and self-clearing**: one fresh Crucible decision advances
the clock past every pending witness and the next poll submits again — no Forge intervention.

The signal points UPSTREAM. Diagnose the runner (`futex_do_wait` at 0% CPU + byte-identical
exports = the wedge signature), restart it if wedged, and relay a wedge prompt
(`PROMPT_CRUCIBLE_RUNNER_WEDGE.md`). Never lower the knob to "unblock" — that just resumes
feeding the dead gate (the exact waste the guard exists to prevent). Deadlock-immune by
construction: if the clock is stale because *Forge* was quiet (our outage/migration), no
submission postdates it, so the guard stays silent and the next batch flows.

## `blocked: in-flight depth N exceeds cap M` — the §7.3 backpressure block (D196/D200)

The third §7.3 block reason (beside the per-batch completion fraction and the D137 stall
guard): the *aggregate* genuine in-flight `submitted` depth — rows newer than the flush
watermark, summed across batches — exceeds `submission.max_inflight`. Normally this is the
throttle working: Crucible is draining slower than Forge submits, and it self-clears as the
queue drains below the cap.

Since D240 the feedback consumer also retires runner-FAILED runs **every poll** from
Crucible's `failed_runs_*.json` export (`feedback/consumer.py` `_flush_failed_runs`), so
failures can no longer sit `submitted` and pin the depth metric until the 5-day age-out
(the 2026-06-24 / 2026-07-05 incidents). A *persistent* depth block therefore means either
the `crucible-failed-runs-publisher` is down (failed runs invisible again) or a genuine
Crucible backlog. Diagnose with the D205/D240 join: forge.db `submitted` rows vs Crucible's
`run.status` / the failed_runs export, on `config_hash` — a large `submitted`-but-FAILED
overlap means the failed-runs read path is broken, not the gate slow.

tz trap while correlating: `journalctl --since` parses timestamps as LOCAL (PDT box config)
while the exports/DB are UTC — prefer relative forms (`--since -15min`) over absolute ones.

## When "blocked" IS a wedge (the completion-fraction path)

Hours of consecutive `prev batch N% gated` blocks while exports stay fresh and Crucible's runner is
gating → check the aged-out flush watermark logic in `feedback/consumer.py` (history: D052 → D061 →
D110) and whether the pinned oldest batch predates a code change (skip procedure: `docs/HOW-TO.md`).
(Post-D137 this specific 18-h-blind-window wedge is caught by the stall guard above within 3 h.)
