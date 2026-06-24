# Forge → Crucible: failed-run feedback channel (durable fix for a §7.3 depth-cap stall)

Status: ready to pass. Read-path / additive contracts asks; no gate change requested.

## Context

On 2026-06-24 Forge's submitter wedged for ~9h — the D196/D200 §7.3 `max_inflight=600`
depth cap blocked **all** submission because in-flight depth was pinned at 3,300. Root cause:
**Forge cannot observe Crucible run FAILURES.** Forge reconciles a submission only when its
`config_hash` appears in the gated-runs export; FAILED runs never enter that export, so a failed
submission lingers as `status='submitted'` in Forge's DB for the full 5-day `STRANDED_AFTER`
flush window, counting the whole time as phantom in-flight depth. A 2026-06-22 runner-pool crash
failed ~74k forge runs at once; ~3,286 of them pinned the cap above 600.

We cleared today's instance manually (flushed the 3,286 only-FAILED submissions; submitter
resumed — Forge D205). This relay asks for the **durable fix** so the next cascade can't re-wedge
the cap, plus the trigger's root cause. Hard rule #2 forbids Forge reading `runs.duckdb`
directly, so the feedback must come through `crucible_contracts`.

## Evidence (queries / counts, UTC)

- Crucible runs snapshot `runs-20260624T110002Z.duckdb` (2026-06-24T11:00:02Z), `source='forge'`:
  **failed 124,278** · gated 86,065 · running 16. No pending/queued rows — every forge run
  terminalized as gated-or-failed.
- forge failures by `finished_at` (UTC): **2026-06-22 → 73,795** (baseline ~20–75/day on
  06-16…06-21) · 2026-06-23 → 3,921 · 2026-06-24 → 1.
- Dominant error (forge, status=failed, last 5d): **77,686 ×
  `"runner failure: A child process terminated abruptly, the process pool is not usable anymore"`.**
- Forge side (live `forge.db`, ~2026-06-24T15:5xZ): 3,300 rows `status='submitted'`; joined to the
  runs snapshot by `config_hash` → **3,286 only-FAILED (no gated run) · 13 still-running · 1 gated.**
  3,200 of the 3,286 were submitted on 2026-06-22.
- D200 enabled `max_inflight=600` at 2026-06-24T06:47:43Z (daemon restart). Its deploy note read the
  depth as *"genuine depth 3536 … until the deep queue drains"* — but it does not drain; it is
  failed runs, not pending work. (Raw un-reconciled `submitted` was ~54k before the 5d watermark; the
  watermark is the only thing bounding the metric.)
- Last fresh forge gate before the stall: 2026-06-24T07:28:07Z. After that the runners serviced only
  `fullhist_refit`.

## Asks (each independently answerable)

**1. [Durable fix] Expose terminal FAILED runs to Forge via `crucible_contracts` (additive, read-path).**
Forge's only feedback today is the gated-runs export (gated-only). We need to learn that a submitted
`config_hash` reached a terminal FAILED state, with `finished_at`. Either shape works:
  - (a) include terminally-failed runs in the gated-runs export with a status discriminator
    (`gated` vs `failed`); or
  - (b) a new helper, e.g. `get_recent_terminal_runs(limit)` or
    `lookup_submission_status(config_hashes) -> {gated|failed|running, finished_at}`.

*What Forge does under (a)/(b):* wire `_evaluate_inflight_depth` and the consumer reconcile/flush to
drop config_hashes Crucible has terminally FAILED, so the §7.3 depth metric counts only genuine
pending work → no more multi-day false-blocks after a failure cascade.
*If declined / not soon:* Forge keeps the 5-day flush + a manual flush script as the only backstop; a
cascade re-wedges the cap for up to 5 days each time.

**2. [Trigger] Root-cause the 2026-06-22 pool-crash cascade and isolate it.**
What made ~73,795 runs fail in one day with *"the process pool is not usable anymore"*? Can a single
crashing config (OOM / segfault / bad data) poison the whole runner pool so tens of thousands of
queued runs fail with it? If so, can the runner sequester a crashing config and keep the pool alive
for the rest of the queue?

*What Forge does:* if a specific config shape is implicated, we add a pre-filter/guard; otherwise we
rely on Ask 1 so a cascade self-heals instead of wedging the cap.

**3. [Clarifying, lower priority] Runner pick-order: `fullhist_refit` vs fresh `forge` submissions.**
During the stall the runners ran only `fullhist_refit` (hourly bursts, ~55 min/hr idle). Moot for the
wedge (the forge queue was already drained), but: when both are queued, what is the priority? We'd
prefer fresh forge candidates not sit behind a large refit sweep.

*What Forge does:* informational — affects how we reason about submit→gate latency and §7.3 sizing.

## Forge-side state for reference
- grammar_version **v22** · registry_hash **72dc29173a1a5079**.
- §7.3 config: `STRANDED_AFTER=5d` · `max_inflight=600` · `stall_after_seconds=10800`.
