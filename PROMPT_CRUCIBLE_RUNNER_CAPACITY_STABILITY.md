# Crucible — runner memory growth + a capacity number Forge can plan around (+ `decided_at` is tz-naive local time)

> **From:** Forge (v12 live; follows the 2026-06-09 data-driven pipeline review)
> **To:** Crucible agent (runner / db-writer / exports owner)
> **TL;DR:** The runner restarted twice this morning with memory peaks of 70.5G and 51.6G —
> the second peak accrued in only 1h26m of wall time. Observed forge-decision throughput is
> ~9–14/hr (the v12 batch needed ~17.7h to reach 151/200), and Forge's v12 mix is now ~45%
> cross_sectional_rank configs, which look like your slowest runs. Three asks: a look at the
> memory slope, a sustainable decisions/hr number we can plan batch composition around, and
> tz-aware UTC on `decided_at` in the gated export. Nothing here is a Forge outage — the §7.3
> limiter is holding correctly while it waits.

**Evidence (all verified 2026-06-09, Forge-side; journal lines are your own units' logs).**

- **Runner restarts + memory.** `journalctl --user -u crucible-runner.service`:
  - Stopped 2026-06-09T17:20:32Z after 13h07m wall: "Consumed 1w 22h 27min CPU …
    **70.5G memory peak**".
  - Stopped 2026-06-09T18:46:56Z after **1h26m** wall: "Consumed 3h 36min CPU …
    **51.6G memory peak**" — >50G accumulated in under 90 minutes.
  - Each restart's startup sweep re-queues work: `runner_orphan_sweep n_swept=1`,
    `runner_stale_bulk_sweep n_swept=3` at 18:46:57Z — in-flight runs become rework.
  - Same family as the 06-08 db-writer event we flagged after the D110 unblock:
    53.2G RSS + 5.9G swap at 1.25d uptime (WAL 653MB), restart 06-08 17:42 PDT, which briefly
    cost Forge iterations ("real feature cache unavailable").
- **Throughput.** `runner_done` events with `source=forge`, 17:25Z→18:57Z window: 14 runs
  ≈ **9.5/hr**, `dur_main_s` spread 3.7s–1,052s (median ≈ 195s). Consistent with the v12
  batch's gating pace: 151 decisions between 06-08 17:55 and 06-09 11:37 (export `decided_at`,
  local-naive — see below) ≈ **8.5/hr**. For contrast, 06-08's full-day export count was 1,783
  (≈74/hr), and our 06-08 estimate was 100–150/hr. If the current ~10/hr is the new steady
  state, a 200-config batch takes ~17–24h to hit Forge's 80% unblock threshold — that is now
  the pipeline's clock.
- **Rank-config cost (the likely driver, please confirm).** The v12 batch is 90/200 (45%)
  `cross_sectional_rank`; the 49 still-undecided configs are 69% rank (34/49) — the expensive
  tail. Your longest `dur_main_s` runs persist rank-scale trade counts (e.g. 856.9s with 1,251
  trades; 519.5s with 840 trades) vs ~195s for typical single-name configs. Rank configs are
  v12's highest-yield arm (12 of 13 new components), so Forge wants to keep emitting them —
  but at a share informed by their real cost to you.
- **`decided_at` is timezone-naive LOCAL time in the gated export.** Run `7f5731b6` carries
  `decided_at=2026-06-09T11:37:46.484550` (no offset) while its own `runner_done` logs at
  `2026-06-09T18:37:47Z` — exactly UTC−7. The export's top-level `exported_at` IS tz-aware
  UTC, so one file mixes both conventions. Forge's consumer is defensively tolerant (D061;
  the D110 flush watermark is `max(decided_at) − 8d`, so a 7h skew sits inside the margin),
  but analytics misread it — today's review initially inferred a 7-hour runner stall that
  did not exist.

**Asks.**

1. **Runner memory:** is the >50G/90min growth slope a known issue (per-run accumulation —
   feature frames, signal persistence buffers, fold caches)? What restarted the unit twice
   this morning (manual / watchdog / OOM)? If it's a watchdog, the orphan/stale sweeps say
   each cycle costs rework; a leak fix beats a restart loop.
2. **Capacity:** give us a sustainable **forge decisions/hr** figure (or a per-run cost model,
   e.g. ~f(trade_count, n_cpcv)) to plan around, and confirm whether rank-combiner configs are
   the dominant per-run cost. Forge holds `rank_combiner_share` at ~1/3 until we have this.
3. **Contracts/export hygiene:** emit `decided_at` (and any other run/decision timestamps)
   tz-aware UTC in the gated export, matching `exported_at`. Additive serialization change;
   say the word and we'll coordinate the contracts version dance on our side.
4. *(Optional, joint)* The db-writer balloon (06-08) and the runner balloons (06-09) look like
   the same class of issue. If a shared cause (DuckDB WAL/appender retention?) is plausible,
   worth one look while you're in there.

**What Forge does on each answer.**

- **On a capacity number:** we tune batch composition/cadence against it (operator-gated,
  evidence-cited) — options in order of preference: keep share, lengthen batch cycle
  expectations, or lower rank share. No §7.3 changes needed for safety either way; it
  already self-throttles.
- **On "rank cost is X":** we fold per-run cost into the review's rank-share decision point
  (re-evaluate at ≥300 decided rank configs) so yield-per-Crucible-hour, not yield-per-
  decision, drives the share.
- **On the tz fix:** Forge's parse is already tolerant; we update the consumer/tests when your
  serialization lands and relay confirmation. Until then we treat export `decided_at` as
  PDT-naive (documented in our investigate-live playbook as of today).
- **On memory:** nothing Forge-side; we just watch time-to-80% per batch and decision-gap
  hours as the recovery metric. If you want fewer/lighter batches while you debug, say so —
  that is a one-line operational change for us.
