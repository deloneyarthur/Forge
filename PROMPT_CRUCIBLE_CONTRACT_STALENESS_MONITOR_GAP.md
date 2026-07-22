# Forge → Crucible: the contract-staleness monitor covers 2 of 10 consumers — and its alert names the wrong process

**Status:** held (operator carries).
**Occasion:** Forge-side incident D329, 2026-07-22 — a ~7h total producer stall caused by your fleet
holding a pre-1.35.0 contract in memory. Your monitor fired for **9 hours** and the outage still ran
its full course. This is not a "you missed an alert" note: **acting on that alert exactly as worded
would not have cleared the outage.** That is the thing worth fixing.

Everything below is already resolved operationally (fleet restarted, 74 configs recovered, pipeline
verified healthy). Nothing here is a request for help. It is one durable-fix ask against
`check_pipeline_health.py` + `optbt/core/contracts_check.py`.

---

## What happened (evidence, UTC)

| When (UTC) | Event |
|---|---|
| 2026-07-21T06:12:26Z | Crucible fleet last started — all 10 long-running units, loading contracts **1.34.0** |
| 2026-07-21T19:00:45Z | `runner_contract_stale` WARN begins firing every ~15 min |
| 2026-07-21T20:56:13Z | contracts **1.35.0** committed (`f5631d7`) — additive `SizerSpec.mode` Literal `lot_floor` |
| 2026-07-21T21:25Z | **74 Forge configs rejected** into `~/optbt_data/inbox/errors/` |
| 2026-07-22T04:00:02Z | 37th and final consecutive `runner_contract_stale` WARN |
| 2026-07-22T04:03:53–04:04:08Z | Full-fleet restart onto 1.35.0 (Forge-side operator action) |
| 2026-07-22T04:35Z | Forge submitting again |

The rejection reason, verbatim from `inbox/errors/*.reason.txt` (74 identical):

```
failed to parse <hash>.json: 1 validation error for StrategyConfig
sizer.mode
  Input should be 'fixed_risk_pct', 'vol_target' or 'fractional_kelly'
  [type=literal_error, input_value='lot_floor', input_type=str]
```

Inbox-rejected configs enter **neither** `gated_runs` **nor** `failed_runs`, so nothing retires them
(D245's "third category"). Forge batch `1a0f9dc7-dd7f-433e-b72a-1ce004583e1b` was left at
126 gated + 74 stranded = a hard **63% ceiling** under the 80% §7.3 release bar. It was the only open
batch, so Forge submitted nothing from 21:25Z to 04:35Z.

## The gap

`check_pipeline_health.py:502` →

```python
stale_contract_runners = stale_contract_owners(
    read_runner_contract_statuses(data_root), CONTRACT_VERSION,
)
```

`read_runner_contract_statuses` globs `<data_root>/runner_status/*.json`, and those files are written
only by `write_runner_contract_status(...)` — called **only from the two runner entry points**. So the
check covers `runner-1` and `runner-2`: **2 of the 10 long-running processes that import contracts.**
`crucible-db-writer`, `crucible-inbox-watcher`, `crucible-refit-watcher` and the five publishers are
invisible to it.

That matters here specifically because **the process that actually caused the outage was the
inbox-watcher**, not the runners. First-ingest is deliberately strict (`extra="forbid"`, correctly —
per your own 1.25.0 note `parse_forward_compatible` is for re-reads only), so a stale watcher rejects
100% of Forge's submissions. Your alert text says:

> `runner shard(s) runner-1, runner-2 loaded a crucible_contracts version != installed (1.35.0) … restart the shard(s) to adopt`

An operator who does exactly that — restart the two shards — **still has a stale inbox-watcher, and
Forge is still wedged.** The alert was correct, specific, and insufficient.

## Secondary finding: the WARN fires ~2h before the version exists

The alert began at 19:00:45Z but 1.35.0 was not committed until 20:56:13Z. Your monitor compares
against `CONTRACT_VERSION` read **from source** (as your QuantIQ handoff notes, deliberately, since
editable dist metadata drifts). So an in-progress edit to `_version.py` in the contracts working tree
makes every running process report stale before the version is committed, let alone released.

We are not asking you to change that — reading from source is the right call. But it means the WARN
carries a routine false-positive mode, and a check that cries stale during every contracts editing
session is a check people learn to skip. 37 consecutive fires went unheeded; that is the likely why.

## Asks

1. **Extend the status write to every long-running contracts consumer.** Call
   `write_runner_contract_status(data_root, owner_id=<unit>, pid=..., started_at=...)` at startup in
   db-writer, inbox-watcher, refit-watcher, and the five publishers. The machinery already
   generalizes — `owner_id` is a free string and `stale_contract_owners` already filters on live pids
   — so no comparison-logic change is needed and old status files keep parsing. Independently
   answerable: yes/no, and if yes, do you want the directory renamed (`runner_status` →
   `consumer_status`) or kept for backward compatibility? *(Our suggestion: keep the name, generalize
   the symbols later or never.)*

2. **Severity-split the ingest path.** A stale inbox-watcher is not WARN-class: it silently zeroes
   Forge's throughput with no other symptom on your side (queue empty, runners idle, everything
   "green"). Suggest **CRIT** for any consumer on the first-ingest path and WARN for the rest, with
   the alert text naming the *consequence* ("Forge submissions are being rejected"), not just the
   remedy. Independently answerable.

3. **Distinguish committed-version staleness from working-tree churn** (optional, lower value). If
   the comparison also carried the contracts git HEAD short-sha, an editing-session false positive
   would be distinguishable from a genuine post-release drift. Your call entirely — we raise it only
   because alert fatigue is the mechanism that turned a detected condition into a 7h outage.

4. **QuantIQ is a third direction, flagged not asked.** `quantiq-backend` and `quantiq-scheduler`
   import contracts via an editable install resolving to `~/proj/crucible_contracts/src`
   (`crucible_contracts>=1.20,<2`); `quantiq-frontend` is Node and never affected. They sit outside
   your process tree, so we are not asking you to own them — only noting that "restart both
   directions" is really **three** directions, in case your monitor is the natural home for a
   fleet-wide view.

## What Forge does under each answer

- **Ask 1 yes** → nothing to build on our side; we drop the manual `ActiveEnterTimestamp`-vs-commit-time
  audit from our contracts-adoption ritual and rely on your check. We will confirm coverage after your
  next deploy by killing a publisher and checking it alarms.
- **Ask 1 no / deferred** → we keep the manual audit and add it to `docs/tasks/crucible-handoff.md` as a
  required step on every contracts bump. No contracts change either way.
- **Ask 2 yes** → no Forge change; the CRIT is for your operators, and it shortens our stall exposure.
- **Ask 2 no** → we lean harder on our own side: Forge's `inbox_rejections` healthcheck (D246) already
  CRITs on `inbox/errors/` growth and is our real backstop. Worth stating plainly — **our check caught
  the consequence, yours caught the cause, and neither was watched.**
- **Ask 3/4 any answer** → informational; no Forge work either way.

## Recovery note (may be useful to you)

We did **not** use D245's remedy (retire the stranded rows to `gated` + sentinel, discarding the work).
`inbox/errors/` preserves the full `{config_hash}.json` payload alongside the `.reason.txt`, so once the
watcher spoke 1.35.0 all 74 re-validated as `StrategyConfig` and were re-submitted through
`crucible_contracts.submit_candidate` (atomic tmp-then-rename), originals left in place as backup.
That recovered 73 of 74 (the 74th was an ordinary `chain[RIVN]: 82 consecutive sessions with no
snapshot` coverage failure), mutated no DB row, and needed no Forge restart. Inbox drained 74→0 in
~40s with `errors/` flat — zero re-rejection. **Replay before flush** whenever the payloads survive.

---

**Forge-side ref:** D329 (`IMPLEMENTATION_DECISIONS.md`), `STATUS.md` 2026-07-22 block.
**Contracts:** pin == installed == 1.35.0 both sides; your `CRUCIBLE_EXPECTED_CONTRACT_VERSION` is
still 1.34.0, which is harmless (`validate_schema_version` gates on MAJOR only) but worth a bump on
your next pass so `deploy_preflight` stays honest.
