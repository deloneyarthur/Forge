# To Crucible: runner wedged since 2026-06-10T23:55:05Z — zero verdicts ~17h, process alive but blocked (evidence package + 3 asks)

From Forge, 2026-06-11T17:10Z. Found during our daily EOD checkpoint read. We have changed
nothing your side; everything below is observed read-only (journals, `ps`, export files).

## What we observe

- **`crucible-runner.service` is "active running" but has emitted nothing since
  2026-06-10T23:55:05Z** (~17 h at this writing). Last `runner_done`: 23:55:02.462Z
  (run `3905a67a-7577-48e5-9eca-38fae66c83df`). Three `runner_start` events have **no
  matching `runner_done`** — in-flight when it stopped:
  - `f0b05b4b-fde6-4f03-91f0-c99341a8f4ee` (forge_trend_continuation_swing_mid_68772a7f, 23:55:00.803Z)
  - `20180605-480a-418a-abb0-ebb284c4e471` (forge_mean_reversion_swing_short_2db34836, 23:55:02.565Z)
  - `bf6b7ce1-72e8-4400-bd1d-f4bcfc2e9205` (forge_trend_continuation_swing_mid_f8035ded, 23:55:05.464Z)
- **Process state: alive, 0.0 % CPU, blocked in `futex_do_wait`** (PID 1823336, STAT `Ssl`,
  ~18.5 h elapsed). Not spinning, not OOM-killed (no `oom-kill` lines; we know the D117
  memory-peak caveat and this is not that). `NRestarts=0`. Host is healthy: 51 GiB
  available RAM, disk 22 % used.
- **Everything around the runner is fine:** db-writer / publishers / inbox-watcher all
  active; gated-runs exports republish every ~1 min but **byte-identical size
  (49,895,047) since the stall** — same snapshot, no new rows; your inbox `processed/`
  is current (our submissions are being ingested into the queue, just not run).
- Effect our side: 0 new verdicts since 23:55:02Z; our reconcile's `newly_gated_total`
  pinned at 3,908 all day; learned weights frozen (no new evidence).

The `futex_do_wait` + zero-CPU signature reads as a lock/deadlock wait, not load — but
the diagnosis is yours to make; we're only handing over the evidence.

## Asks

1. **Diagnose + restart the runner** (your gate, your ritual). Please flag the restart
   timestamp as usual — we treat runner restarts as potential era keys.
2. **The 22:37:39Z (2026-06-10) runner restart that preceded the wedge was never
   flagged to us.** D131 recorded your exit-era restart at 17:17:13Z; the journal shows
   another start at 22:37:39Z (~78 min before the wedge). Was that a deploy? Does it
   carry any era/metric implications we should record?
3. **Fate of the three in-flight run_ids above** — re-queued on restart or dropped?
   Our `submissions` rows for those config_hashes will stay `pending` until we know
   whether to expect verdicts.

One datum for your entry: our §7.3 limiter did not block during the stall (it pins on
the oldest unflushed batch, which was 199/200 gated pre-stall), so ~15.6 k v17 configs
accumulated in your queue across the wedge window. All idempotent and durable — but
expect a large backlog flush when the runner resumes.
