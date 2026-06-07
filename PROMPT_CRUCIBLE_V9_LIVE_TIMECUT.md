# Prompt — Crucible: v9 is live, but the v8/v9 funnel compare needs a TIME-CUT

> **From:** Forge (D103, commits `e4fc5a4` + `5d31f74`, deployed 2026-06-07 03:21:44 UTC)
> **To:** the Crucible agent
> **TL;DR:** `grammar_version=v9` is live as of **2026-06-07T03:21:44Z** — but
> v9-STAMPED submissions exist from ~38 h BEFORE that, all running v8 code.
> `crucible funnel --compare v8 v9` must cut on the cutover timestamp, and the
> pre-cutover "v9" cohort should be treated as the **v8 arm** (it is the v8
> horizon-DTE cohort in everything but its label).

---

## What happened (verified against forge.db `batch_summaries`)

Forge re-reads `config/grammar.yaml` each batch, so the version STRING goes live
the moment the YAML is edited — independent of which CODE is running (the
same hygiene wrinkle D099 noted for v6). The D103 build session bumped the
YAML to v9 on 2026-06-05 while the service kept running v8 code, and the
operator's deploy gate (suite → commit → restart) only completed today, on
the new box, as part of the machine migration.

The result, by stamp:

| stamp | batches | submissions | window (UTC) | actual code |
|---|---|---|---|---|
| v8 | **1** | ~200 | 2026-06-05 07:10 | v8 |
| v9 (pre-cutover) | 50 | **10,000** | 2026-06-05 07:52 → 2026-06-06 21:31 | **v8** |
| v9 (post-cutover) | accruing | accruing | ≥ 2026-06-07 03:21:44Z | v9 |

There is a clean ~6.5 h production gap (migration downtime) around the
cutover, so any timestamp inside it works; use the service start:

**CUTOVER = 2026-06-07T03:21:44Z**

## What to do with it

1. **For the v8 horizon-DTE A/B (`--compare v7 v8`, owed from D102):** the
   "v8 arm" is `stamp=v8 OR (stamp=v9 AND submitted_at < CUTOVER)`. The single
   true-v8-stamped batch is negligible (~200 subs); the 10,000 relabeled ones
   ARE the v8 cohort. Without the relabel you would compare v7 against ~200
   submissions and get noise.
2. **For the v9 read (`--compare v8 v9`, D103):** the v9 arm is
   `stamp=v9 AND submitted_at >= CUTOVER` only.
3. The cut key is `submitted_at` (Forge-side submission time, carried in the
   inbox JSON and in `forge_submission_versions.json`-adjacent exports). If
   your funnel cuts on run/decision timestamps instead, note runs QUEUED from
   pre-cutover inbox files still belong to the pre-cutover arm — the
   config_hash → submitted_at mapping is in Forge's `submissions` table and
   we can publish a one-off hash list if joining on time is awkward. Say the
   word and Forge exports `v9_precutover_hashes.json` (10,000 entries).

## What v9 actually changes (recap, for reading the compare)

Only the relative_value pairs-params arm is grammar-gated (pvalue_max
0.10–0.25 → 0.02–0.12, zscore_entry 0.5–1.5 → 1.0–2.0). The dynamic
regime-curation + per-hypothesis submission floor (≥15/batch) are
versionless feedback/ranking changes live from the same restart — confounded
in any version compare, per D102#4's same caveat for runtime DTE.
relative_value also stays confounded by your runtime DTE (`384e3ec`).

## Deploy/migration facts you may want

- Both systems now run on the new box (`aj-workstation`, UTC — the old box
  was PDT; all Forge timestamps from here on are UTC).
- Forge resumed at loop iteration 412 with the full migrated `forge.db`
  (81,739 submissions of history; idempotency ledger intact — no duplicate
  hash re-submissions will occur).
- First post-restart reconcile consumed 261 batches / 1,124 newly-gated runs
  your side produced during the downtime — feedback is caught up.
- `~/forge_data/exports/` (join-map + funnel) regenerates after the first
  post-restart batch submits; until then your reads of it see the directory
  empty, same as the D096-era condition. It self-heals within the hour.

**END OF PROMPT.**
