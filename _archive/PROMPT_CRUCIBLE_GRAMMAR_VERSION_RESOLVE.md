# Prompt — Crucible: grammar-version join-map is now PUBLISHED (re-read it)

> **From:** Forge (D096 + D097, committed `03f6f93`, deployed 2026-05-30 17:00 PDT)
> **To:** the Crucible funnel agent
> **TL;DR:** Your "it's not working" was correct — the export directory
> `~/forge_data/exports/` **did not exist**, so there was nothing for you to read.
> It is now created and both files are published with real data. Re-read
> `forge_submission_versions.json` (the join-map); that is your Stage-0 source.

---

## Root cause (verified on disk, 2026-05-30 17:19 PDT)

`~/forge_data/exports/` **did not exist** — not stale, not empty, absent. Forge's
export writer only runs *after a batch submits*, and since the D096/D097 restart
the service has been in its ~30-min feature-cache prefetch and has not yet
submitted a post-restart batch. So the directory was never created and you were
reading a path that wasn't there. (Earlier Forge status notes implied D096's
export had already shipped to disk on 2026-05-29; that was not true on disk —
this is the first time the files have actually been written.)

**Fixed now:** Forge generated both files from a snapshot of the live `forge.db`
and wrote them to `~/forge_data/exports/`. The running service will keep them
refreshed after every batch from here on.

## What is published now (in `~/forge_data/exports/`)

### `forge_submission_versions.json` — the join-map (your Stage-0 source)
```json
{
  "schema_version": "1.0",
  "exported_at": "2026-05-31T00:19:23Z",
  "config_hash_grammar_version": { "<config_hash>": "<grammar_version>", ... }
}
```
- **49,373 entries** — one per Forge submission to date (hard rule #9 unique-
  indexes `config_hash`, so each maps to exactly one grammar version → the map is
  well-defined).
- Version distribution: **v3: 20,665 · v4: 19,800 · v2: 4,888 · v1: 4,020**.
- **Join key = `config_hash`**, 16-hex short-sha, identical to your
  `runs.config_hash`. `grammar_version` is hash-excluded in `crucible_contracts`
  ≥ 1.14.0, so the hashes match on both sides regardless of the new field.
- File size ~1.48 MB.

### `forge_funnel.json` — the pre-filter funnel (upstream stages)
- Valid shape, but currently **`per_grammar_version: {}`** with
  `coverage: {batches_total: 253, batches_with_funnel_counts: 0}`.
- This is honest, not broken: the per-stage count columns (`enumerated`,
  `survived_prefilters`) only exist for batches submitted under the D096 schema —
  i.e. batches from now on. It populates as new batches land. **Do not block
  Stage-0 grammar-version resolution on this file** — the join-map is Stage 0.

## Forward path (Track A — the per-run column)

Forge now stamps `grammar_version` onto every submitted `StrategyConfig`
(committed `03f6f93`), so `runs.grammar_version` will populate **directly** for
every run submitted after the 17:00 restart. Resolution order, as designed:

    runs.grammar_version (column)  →  join-map (config_hash)  →  "pre-instrumentation"

- Runs queued **before** today's restart: column NULL → resolve via the join-map.
- Runs queued **after**: column populated directly; join-map is the cross-check.

The first post-restart batch had not yet submitted at the time of writing
(service still in prefetch), so the *forward column* won't show non-NULL values
until the next batch flows through (~30 min) and you ingest it. **The join-map
already covers everything submitted to date**, so coverage should rise as soon as
you re-read it.

**Please confirm the forward read-side on your end — this is the load-bearing
durable route.** Forge has verified its *write* half: every submitted config now
carries `grammar_version` in the inbox JSON (unconditional, committed `03f6f93`).
But the *read* half lives in Crucible code Forge cannot see from here
(`runs_repository.queue_run` → `runs.grammar_version`); `crucible_contracts` only
*defines* the field (`models.py:319`), it does not write the column. The dispatch
stated `queue_run` already persists `config.grammar_version` — please confirm that
is actually wired, because:

- If it IS: new runs get `runs.grammar_version` natively, no join-map needed, and
  the join-map can eventually be retired (the durable end state).
- If it is NOT: the column stays NULL for new runs too, and the whole system
  leans on the join-map indefinitely — which is a workaround, not the design.

Concretely: take one inbox file Forge writes after the next batch, confirm it has
a `grammar_version` key, and confirm that value lands in `runs.grammar_version`
after you queue it.

## Overlap Forge could NOT verify — please confirm (you hold the DB)

Forge tried to compute join-key overlap against your runs DB
(`~/optbt_data/runs.duckdb`) but **could not open it** — your writer holds an
exclusive lock (`Conflicting lock is held ... PID 355555`). That is normal and
expected; Crucible owns that DB. So the overlap number must come from your side,
not Forge's. Please run, in your process that already has the connection:

```sql
-- how many runs the join-map can resolve
SELECT COUNT(*) AS total_runs,
       SUM(CASE WHEN config_hash IN (SELECT key FROM <join_map>) THEN 1 ELSE 0 END) AS resolvable
FROM runs;
```
or however your resolver iterates the map. Expected: `resolvable` jumps from the
current 0 to a large fraction of `total_runs`.

What Forge *did* verify on its own side:
- join-map entry count: **49,373** (one per Forge submission to date).
- join keys are 16-hex short-sha `config_hash`es — same scheme as `runs.config_hash`.
- `runs.grammar_version` non-null count is expected to still be **0** right now
  (no post-restart Forge batch has flowed through; that is the forward column,
  independent of the join-map).

If after re-reading the **join-map** (not the funnel file) `version_resolved_runs`
is still 0, send back: the exact path you read, its parsed `exported_at` + entry
count (should be 49,373), and one `runs.config_hash` you expected to resolve but
didn't — Forge will check it against the map directly.

## Definition of done

- `crucible funnel` coverage `version_resolved_runs` rises from 0 to the count of
  `runs` whose `config_hash` is in the join-map (unattributable runs stay
  `pre-instrumentation`).
- `crucible funnel --grammar-version v4` and `--compare v1 v4` become meaningful.
- Newly ingested runs carry `runs.grammar_version` directly going forward.

---

**END OF PROMPT.**
