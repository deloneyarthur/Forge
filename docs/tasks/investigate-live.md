# Task: investigate live behavior / query state

Scope: diagnosing the weekly run or analyzing results. Read `STATUS.md`'s top block first — the
anomaly may already be diagnosed. Era boundaries that silently wreck joins: `docs/HOW-TO.md` §Eras.

## Run health

```bash
systemctl --user list-units 'forge*' 'crucible*' --state=failed   # a FAILED forge-campaign unit is the page
systemctl --user list-timers 'forge-*'                             # next Sunday 03:00 / 04:30 UTC
journalctl --user -u forge-campaign.service -n 60 --no-pager       # boot rows, triggers, selection line, closing line
SNAP=$(scripts/live_db_snapshot.sh)
uv run forge campaign status --last 4 --forge-db "$SNAP"           # records + what each run's submissions earned
```

How to read the block: `docs/HOW-TO.md` §Weekly check. The record itself is
`~/forge_data/campaigns/<run_id>.json` (`campaign_run/v1`; fields in `docs/MANPAGE.md`) — a second
`--dry-run` on the same exports must reproduce the plan; if not, compare the two records'
`watermarks`.

## Forge DB (the lock trap)

A run in progress holds an RW lock on `~/forge_data/forge.db` that blocks even `read_only` opens;
between runs the file is quiet, but the habit stays: snapshot first (a DuckDB file copy is
consistent), because a Sunday run can start under you.

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

> **WHY (2026-08-02, learned the expensive way).** `/tmp` on this box is a 62 GB tmpfs — RAM — and
> the live DB is ~7 GB. Nine hand-rolled snapshots in one session filled it and took the shell down
> twice: every command, `true` included, returned exit 1 with no output, because the harness could
> not write its own output capture. It presents as broken tooling, not as "disk full". The helper
> enforces real disk, reuses one copy instead of a new 7 GB per question, and gives you `--clean`.
> `python` is also not on PATH here — use `uv run python`. `--force` re-copies when you need the
> current state rather than a fresh-enough one.

Useful queries (tables: `docs/MANPAGE.md` FORGE STATE DB):

```sql
-- Campaign submissions by trigger and status
SELECT selection_mode, status, COUNT(*) FROM submissions
WHERE selection_mode LIKE 'campaign:%' GROUP BY 1, 2 ORDER BY 1, 2;
-- Recent batches (one per weekly run that submitted)
SELECT forge_batch_id, submitted_at, batch_size, promotion_rate, common_failures
FROM batch_summaries ORDER BY submitted_at DESC LIMIT 10;
-- What the campaign cohort earned (the durable ledger; re-gates append per run_id)
SELECT v.decision, COUNT(*) FROM verdicts v JOIN submissions s USING (config_hash)
WHERE s.selection_mode LIKE 'campaign:%' GROUP BY 1;
-- Grammar version history (the loader's audit writes it on an operator bump)
SELECT version, change_type, decided_at, operator_initials FROM grammar_versions ORDER BY decided_at DESC LIMIT 20;
```

## Crucible exports (Forge's only read path into Crucible)

```bash
ls -t ~/optbt_data/exports/forge_gated_runs_*.json | head -1   # the 14-day forge-scoped verdict stream; fresh = minutes old
ls -t ~/optbt_data/exports/gated_runs_*.json | head -1         # the all-source rolling top-10k window — the FALLBACK only
```

Join export rows to `submissions` on `config_hash`. The forge stream's `truncated` flag means its
OLDEST verdicts are missing; the run then skips the aged-out flush (D415). Read the stream through
`crucible_contracts.load_forge_gated_runs_from_export`, never by glob — the all-source glob collides.

## Refit-lane cohorts (`verdicts.refit_selection`) — the skim trap

From **2026-08-06 17:10 PDT** Crucible's stage-two scanner runs two lanes: a reserved quality
sub-budget ranked by margin over both promotion bars, and the newest-first drain. The tag names
which one queued the refit, so **the untagged cohort is TOP-DEPLETED from that moment onward,
permanently** — the quality lane skims exactly the rows that used to sit at the top of it.

Measured on our own rows (stage two, post-boundary):

| cohort | n | medCPCV | promotes |
|---|--:|--:|--:|
| untagged (drain) | 1,887 | +0.5101 | 23 |
| `quality_margin` | 24 | **+1.3374** | 4 |

**The rule (Crucible's, adopted):**

- **Within-era** (both cohorts post-boundary): filter to untagged. Like-conditioned, clean.
- **Cross-boundary** (any pre-2026-08-06 cohort — which includes *every* v55-vs-vNext read):
  use the **UNION of untagged + `quality_margin`** per version. The two lanes partition one
  eligible population; the union is what stage two actually measured and the only thing
  commensurable with pre-boundary rows. Untagged-only costs the newer version ~0.10 medCPCV
  **by construction** — the size of a real version delta, in the direction that flatters a freeze.
- **`promote_stamp_recovery` is excluded from BOTH**, always. It is a one-shot selected batch,
  not a lane.

**And one that is ours alone — the recovery batch is invisible to the tag in our mirror.** Our 23
recovery rows were ingested minutes *before* the `refit_selection` column shipped (D375) and the
writer is `INSERT OR IGNORE`, so they carry **NULL, not `'promote_stamp_recovery'`**. A naive
`refit_selection IS NULL` filter therefore *includes* them: 0.7% of the untagged rows, **35% of its
promotes** (14 rows, medCPCV +1.5777, 8 promotes) — median reads barely notice, promote-rate reads
inflate by 53%. Exclude them by time, not tag:

```sql
AND decided_at NOT BETWEEN '2026-08-07 00:32:40' AND '2026-08-07 00:33:15'
```

Rows reconciled after the column shipped are correctly tagged; this applies only to that one batch.

## Benign signals — do not "fix" these

- `crucible-ingest-daily` unit "failed" — rfr-only oneshot failure; bars/chains fine.
- Crucible runner/db-writer "Consumed … N G memory peak" on a CLEAN stop — a deploy restart,
  not an OOM or leak; the systemd peak counts reclaimable page cache (D117). The
  flag-worthy signal is an `oom-kill` line, nothing else.
- `forge_gated_runs` `truncated: true` while the daemon era's last batches are inside the 14-day
  window (STATUS has the date it should clear). After that date it is a relay, not a shrug (D412).

## Retired daemon-era signals (Batch 5, D416–D421)

`blocked: …` journal lines (`prev batch N% gated`, `crucible stalled`, `in-flight depth N exceeds
cap M`) came from the §7.3 rate limiter; `skipped: real feature cache unavailable` from the daemon's
`--require-real-cache` iteration skip. Neither exists: the weekly run has no in-flight backpressure
(`campaign.weekly_cap` + the inbox-backlog boot check) and a missing writer socket ends the run as an
`error` record (the page). History: D046 / D137 / D196 / D200 and the D205 / D240 / D245 wedges.
