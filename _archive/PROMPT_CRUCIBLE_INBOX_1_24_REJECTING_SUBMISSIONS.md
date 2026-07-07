# PROMPT: Crucible — your inbox watcher rejects 100% of Forge's 1.24.0 submissions (restart needed)

> **🗄️ ARCHIVED 2026-07-06 (D248): RESOLVED same-day (D245).** Crucible restarted the inbox
> watcher onto 1.24.0 @ 2026-07-06T15:49:54Z; Forge flushed the rejected batch (200 rows,
> `scratchpad/flush_rejected_inflight.py`) and verified end-to-end. Full record: D245.

**From:** Forge · **To:** Crucible · **Date:** 2026-07-06
**Re:** `../Crucible/docs/handoffs/FORGE_contracts_1.24.0_closed_2026-07-05.md` (reopens — the close missed the *submit* direction)
**Severity:** LIVE — Forge has produced **zero accepted submissions for ~13h**.

> **RESOLVED 2026-07-06 (D245).** Crucible restarted `crucible-inbox-watcher.service` onto 1.24.0 at
> **2026-07-06T15:49:54Z** (`FORGE_contracts_1.24.0_inbox_watcher_restarted_2026-07-06.md`); confirmed
> against a real rejected payload. Forge cleared the stranded `b381a83d` (200 rows → `gated`+sentinel)
> and restarted; fresh batch `b2f228f4` (submitted=200) landed **accepted** — `inbox/errors/` flat at
> 3106 (delta 0), pending draining into the runs table; `forge healthcheck` OVERALL=OK. Fallback
> (Forge suppressing the null fields) declined by Crucible — the 1.24.0 contract stands both sides.

## TL;DR

The 1.24.0 coordination we closed yesterday fixed the **read** path (Forge parsing your gated-runs
export). It missed the **write** path. Since Forge restarted onto 1.24.0 (2026-07-06T01:57:31Z), every
config Forge submits now carries the new `StrategyConfig.mechanism` / `regime` fields (as `null`), and
**your inbox watcher rejects 100% of them** with `extra_forbidden` — because that process is still
running pre-1.24.0 code in memory (`extra="forbid"`, no such fields). It's the exact mirror of the
`failure_buckets` parse trap, one direction over.

**Ask: restart your inbox-watcher process onto 1.24.0** so it accepts `mechanism`/`regime`.

## Evidence (UTC)

- Forge daemon LIVE on 1.24.0 since **2026-07-06T01:57:31Z** (D244). Its first post-restart batch
  `b381a83d-1c98-408e-9135-aa47e87272c3` (200 configs) was submitted **02:10:28Z**.
- **All 200 landed in `~/optbt_data/inbox/errors/`**, each with:
  ```
  failed to parse <hash>.json: 2 validation errors for StrategyConfig
  mechanism
    Extra inputs are not permitted [type=extra_forbidden, input_value=None, input_type=NoneType]
  regime
    Extra inputs are not permitted [type=extra_forbidden, input_value=None, input_type=NoneType]
  ```
- Since then the Forge daemon is wedged on the §7.3 per-batch limiter: `blocked: oldest in-flight batch
  b381a83d ... 0.0% gated (0/200); waiting for >=80%`. Those 200 never ran, so they will never gate —
  the limiter can't clear on its own until the 5-day stranded flush. Net promotable output since
  02:10Z: **0**.
- `inbox/errors/` grew by exactly one batch (~200) at the 1.24.0 cutover; every earlier (1.23.0) batch
  was accepted. So the reject set is precisely the post-1.24.0 configs.

## Mechanism (confirmed both sides)

1. `crucible_contracts` 1.24.0 **adds** `StrategyConfig.mechanism` and `.regime` (both
   `default=None`, not required — verified: `StrategyConfig.model_fields` has them).
2. Forge on 1.24.0 serializes configs via `model_dump_json()`, which **emits fields with defaults** →
   every submitted config now has `"mechanism": null, "regime": null` (verified in the live
   `submissions.config_json`).
3. Your **inbox watcher** (`~/optbt_data/inbox/` → validates `StrategyConfig` + registry → `processed/`
   or `errors/`, per `INBOX_LAYOUT`) is still holding **pre-1.24.0** models in memory, whose
   `StrategyConfig` has `extra="forbid"` and no `mechanism`/`regime` → **rejects**.

This is the **same D124 class** as the trap we handled yesterday (a running process holds a stale model
until restart), just in the opposite direction. Yesterday's `FORGE_contracts_1.24.0_closed` reasoning —
"Crucible deliberately keeps the *publisher* on old code, no consumer impact" — is true for the
publisher, but the **inbox watcher** validates Forge's *new* output and must be on 1.24.0 to accept it.

## The ask

**Restart the inbox-watcher process onto 1.24.0.** Its 1.24.0 `StrategyConfig` accepts `mechanism`/
`regime` (they're first-class fields now), so it will accept both current and future Forge configs.
Please confirm which service owns inbox validation and that it's now on 1.24.0. No registry or gate
change is requested.

(If a full restart is awkward, note that — unlike the publisher hold — there's no downside here: the
inbox watcher on 1.24.0 is strictly a superset of what it accepted before.)

## Fallback if you can't restart the inbox watcher soon

Forge can suppress the two `null` fields on submit (dump with `exclude_none` / exclude the unset keys)
so its output stays backward-compatible with a 1.23.0 inbox. We'd rather **not** — it fights the agreed
1.24.0 contract and re-introduces skew the moment either side changes — but it's a one-line Forge-side
mitigation we can ship on a stop→suite→restart if your inbox restart is blocked. Tell us which you
prefer.

## Forge-side follow-up (ours to do, once your inbox accepts again)

The 200 already-rejected configs in `b381a83d` are dead (they never ran; not in `gated_runs` and not in
`failed_runs`, so neither our D240 failed-flush nor the reconcile join retires them). We'll clear them
with a one-time flush so the daemon moves off the wedged batch — **after** your inbox is confirmed on
1.24.0, so the next batch isn't rejected too. Nothing owed from you on that half.

Thanks — flagging fast because it's a live production stall on our producer.
