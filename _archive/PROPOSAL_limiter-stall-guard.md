# §7.3 Stall Guard — Design Proposal (Q38)

> **STATUS (2026-06-24):** LANDED + extended + live. Stall guard BUILT [[D137]] (the design below, all four §8 decisions); the §7.3 backpressure family was later completed by [[D196]] (added an aggregate in-flight `max_inflight` depth block beside this guard) and DEPLOYED [[D200]]. Service runs with the guard active. Historical record below.

**Status: BUILT 2026-06-13 (D137) — all four §8 decisions implemented as approved
(decision-clock predicate, T = 3 h `stall_after_seconds: 10800`, direct enforce, extend
`check_rate_limit`). TDD: 12 unit + 3 invariants + wiring/model tests; full suite 1,563/0,
mypy 0/89, ruff clean. Production enabled via `config/forge.yaml`; SERVICE-INERT until the
next D104 ritual restart (the running daemon won't reload until then). One implementation
note vs the design: `RateLimitStatus` also carries `stall_pending_count` (the journal line's
`<N> configs pending` needs the count, so the predicate is a COUNT not a bare EXISTS — same
single query). Code-layer default is OFF (0); production opts in — see D137 rollout posture.**

**Status (prior): APPROVED 2026-06-11 — all four §8 decisions resolved (in-session
AskUserQuestion, every recommended option chosen): decision-clock predicate, T = 3 h
(`stall_after_seconds: 10800`), direct enforce riding the next D104 ritual restart,
extend `check_rate_limit`.**
**Date:** 2026-06-11. Origin: [[Q38]] — the 2026-06-10T23:55:05Z Crucible runner wedge
(18.08 h, zero decisions, ~13,000 Forge submissions into a dead gate; evidence in
`PROMPT_CRUCIBLE_RUNNER_WEDGE.md`; runner recovered 2026-06-11T17:59:34Z).
**Spec anchors:** §7.3 (rate limiting — "prevents the inbox from becoming a deep queue
Forge can't learn from"), §8.2 (consumer read path).
**Decision lineage:** D046 (oldest-batch policy), D052/D110 (aged-out flush + watermark),
D061 (naive/aware conventions), D070 (67× produce-vs-gate mismatch — why §7.3 matters),
D083 (H-1 sentinel exclusion, H-4 knob wiring).

---

## 1. Problem

§7.3's designed signal is the completion fraction of the in-flight queue front: "wait
until ≥80 % of the oldest in-flight batch is gated." That signal is blind to one stall
mode, now observed live: **Crucible's gate stops deciding while its export stays
fresh-by-mtime** (publisher republishing byte-identical content every minute).

Measured during the 2026-06-10 wedge (live-DB snapshot, 2026-06-11):

- Crucible's decision clock stopped 23:55:02Z → 17:59:34Z next day (**18.08 h**).
- The limiter stayed clear the whole time: the oldest in-flight batch (`00dbf3b8`,
  pre-stall) read 199/200 = 99.5 % gated every check, while every batch behind it sat
  at 0 %. Forge submitted **13,000** configs into the dead gate.
- The natural backstop is `STRANDED_AFTER = 8 days` (consumer.py): only when the
  pre-stall stragglers age out does a 0 %-gated post-stall batch reach the queue front
  and trip the limiter. **The blind window is up to ~8 days per stall.**
- Not a one-off: the verdicts table holds a second instance — 2026-05-30, **17.12 h**
  with no decisions while Forge submitted 10,000 configs (the era whose limiter
  pathology the 05-29 audit later diagnosed by hand as H-1).

**Premise correction to Q38 as filed.** The suggested signal — "`newly_gated_total`
stagnation across N reconciles" — does not survive contact with the code.
`consume_batch_results` re-derives `outcomes` from the export window for **all** batch
rows by `config_hash` on every pass (consumer.py:274-300), regardless of current row
status. The `newly_gated_total` journal line is therefore *cumulative window overlap
of still-pending batches*, not newly flipped rows: during the wedge it read ~199 every
iteration, never 0. A stagnation detector on it would need both a semantics fix and new
cross-iteration state. (The log label is misleading; renaming is out of scope here.)

Cost of the gap (per Q38): no correctness issue — submissions are idempotent (hard
rule #9) and the inbox durable. The cost is unbounded queue growth Crucible-side plus
the full enumerate→prefetch→battery→rank compute of every dead iteration.

## 2. What this is NOT

- **Not a gate or grammar change.** Affects only *when* the next batch may submit;
  never *what* is submitted. Hard rules #1/#3/#10 not in play.
- **Not a change to the 0.80 completion threshold** or the D046 oldest-batch policy.
  The stall guard is a second, independent reason to block — additive.
- **Not Crucible monitoring.** No alerting, no health checks their side; Forge only
  protects its own loop. (Stall *diagnosis* remains the relay-prompt path.)
- **Not a determinism risk.** Blocked iterations consume no seeds — the iteration
  number derives from persisted batch count (`_next_iteration_number`,
  main.py:1395-1415) and blocked returns precede enumeration. Identical to today's
  threshold-blocked path. Hard rule #6 untouched.

## 3. Signals considered

**A. Newly-gated-delta stagnation across N reconciles (Q38's sketch).** Rejected:
premise broken as measured (§1); requires persisting a cross-iteration counter that
resets on daemon restart; N couples detection latency to poll cadence.

**B. Export freshness (mtime or content hash).** Rejected: mtime is this wedge's exact
blind spot (byte-identical republish kept it fresh); a content hash detects
publisher-dead but not the observed runner-dead-publisher-alive mode.

**C. Decision-clock staleness with a work-pending guard (recommended).** The export's
`max(decided_at)` *is* Crucible's decision clock — the same quantity D110 already
trusts as the flush watermark's anchor. Stateless: computed fresh from data the
limiter already loads, every check. Detects both observed stall modes (runner dead,
publisher dead → no export → existing conservative path already blocks).

## 4. The predicate (option C)

```
stall_blocked ⇔ export readable
              ∧ ∃ submissions row: status = 'submitted'
                                 ∧ submitted_at > max(decided_at)
                                 ∧ submitted_at ≤ utc_now() − T
```

Plain English: **Crucible has had new work in hand for at least T and has decided
nothing in that time.** (The witness row implies `now − max(decided_at) > T`, so a
separate staleness clause is redundant — stated here for clarity, collapsed in code.)

Properties, each load-bearing:

- **Stateless recovery.** Recomputed from the export every check; a single new
  decision anywhere advances `max(decided_at)` past every witness row and clears the
  block on the next poll. No counter, no hysteresis (T ≫ all healthy gaps, §5), no
  state to reset on restart. This is the structural answer to the D110 lesson — the
  documented failure mode of limiter logic is an *unrecoverable* block; a predicate
  with no memory cannot latch.
- **Deadlock immunity (the inverse-wedge guard).** If Crucible's clock is stale
  because *Forge* was quiet (our outage, our block, migration), no submission
  postdates their last decision → guard never fires → the next batch flows and
  restarts their clock. Without this clause, staleness-only would self-deadlock: we
  block because they're idle; they're idle because we stopped feeding them.
  Historical instance verified: the 06-06→07 migration gap (3.38 h, 0 submissions
  during) — correctly silent.
- **Stall-duration coverage.** During a stall, D110's flush watermark
  (`max(decided_at) − 8 d`) freezes with the clock, so pending rows cannot age out
  mid-stall — the witness row persists for the stall's whole duration. The guard and
  the flush are anchored to the same clock and cannot disagree.
- **Clock-skew safe.** A Crucible `decided_at` ahead of our clock only *under*-states
  staleness (fail-open toward submitting, the status quo). `utc_now()` per rule #8;
  naive/aware normalization per the D061 conventions already used at
  consumer.py:374-384.

## 5. Threshold calibration (measured 2026-06-11, /tmp snapshot)

Inter-decision gaps over distinct `decided_at` in `verdicts` (D111 table, history from
2026-05-28; 15,344 rows). Healthy era 06-07 → stall start: **14,099 gaps, p50 = 7 s,
p90 = 36 s, p99 = 4.7 min, max = 65.0 min** (worst gaps all in the 06-09 capacity
crunch, ~50–65 min).

All four >2 h gaps in the table's full history, detector verdict at T = 3 h:

| Gap end | Length | Forge subs during | Detector | Verdict |
|---|---|---|---|---|
| 05-30 17:39 | 17.12 h | 10,000 | **fires** | true stall (H-1 era) |
| 06-04 01:34 | 2.02 h | 400 | silent | healthy-slow (long CPCV runs) |
| 06-07 01:21 | 3.38 h | 0 | silent (guard) | Forge-quiet migration window |
| 06-11 17:59 | 18.08 h | 13,000 | **fires** | the Q38 wedge |

**Backtest: 2/2 true positives, 0 false positives, both non-stalls correctly silent.**

- **T = 3 h (recommended):** 2.77× the worst healthy gap; would have detected the
  wedge at 02:55Z, avoiding 10,800 of 13,000 dead submissions (83 %) and ~15 h of
  dead full-pipeline iterations.
- T = 2 h: marginally trips the 06-04 gap near its end (~2 min before recovery; one or
  two skipped iterations, self-clearing — harmless but not clean).
- T = 6 h: doubles undetected waste (~2,700 more dead submissions at the observed
  ~900/h cadence) for no added safety.

False-trip cost in general: skipped submit iterations during a window that was
producing zero feedback anyway, self-clearing on the next decision. The asymmetry
(cheap false block, expensive false clear) is the same one the module already encodes
for a missing Crucible DB (rate_limiter.py:24-27).

## 6. Placement and shape

**Extend `check_rate_limit` / `RateLimitStatus` (recommended).** The function already
fetches the newest export slice (`load_recent_gated_runs_from_export`, newest-first —
`max(decided_at)` is free over fetched runs) and already owns the "may the next batch
submit?" question. Adding the predicate costs one EXISTS query on `submissions`. A
separate `stall_guard.py` module was considered and rejected: it would re-parse the
~50 MB export a third time per iteration (reconcile and the limiter each already parse
it) and add a second seam to `_run_one_iteration` (main.py is monkeypatch-load-bearing
for ~10 test files — D065/D105/D106; touch it minimally).

- `RateLimitStatus` gains `stall_blocked: bool` and `last_decided_at: datetime | None`;
  `clear` becomes `pct ≥ threshold AND NOT stall_blocked`. Existing fields and the
  threshold path are byte-for-byte unchanged when the guard is off or silent.
- **Knob:** `submission.stall_after_seconds` in `forge.yaml` (default `10800`),
  `0` = guard disabled. Parsed into `ForgeConfig` AND wired through
  `_resolve_run_defaults` to `check_rate_limit` — the H-4 lesson: the wiring gets its
  own test, not just the parse.
- **Journal line** distinct from the §7.3 message (operators are trained that
  "blocked: prev batch N % gated" is benign):
  `blocked: crucible stalled — no decisions since <ts> (<X.X>h); <N> configs pending ≥<T>h`.
- Both entry points inherit automatically: the daemon loop and one-shot `forge run`
  call the same check.
- **Docs in the same commit** (CLAUDE.md routing): `docs/MANPAGE.md` (knob),
  `docs/HOW-TO.md` §7.3 blurb, `docs/tasks/investigate-live.md` (new journal signal:
  what it means, that it self-clears, when to relay a wedge prompt instead).

## 7. Hard rules, invariants, tests

| Rule | Status |
|---|---|
| #2 contracts-only | Uses `GatedRun.decision.decided_at` from the existing fetch; no new access path |
| #4 tighten/loosen | Submission flow-control tightening — but limiter changes are pitfall-listed and the deploy is a daemon restart, so **operator-gated regardless** |
| #5 no LLM / #6 determinism | Pure predicate over DB + export; blocked iterations consume no seeds (§2) |
| #8 clock | `forge.core.clock.utc_now()` — first clock use in `rate_limiter.py`, blessed path only |
| #9 idempotency | Untouched |

TDD plan (RED-first, `tests/invariants/` before production code per house rule):

1. **Predicate truth table** (unit): stale + pending-after-clock → blocked;
   stale + nothing-after-clock → clear (deadlock guard); fresh decisions → clear;
   pending younger than T → clear; export missing/empty → today's conservative path,
   byte-identical status.
2. **Invariants:** (a) *deadlock immunity* — `stall_blocked ⇒` a witness row exists
   (Hypothesis property over synthetic submission/decision timelines: the guard never
   blocks a state where Crucible has no undecided work older than T); (b) *stateless
   recovery* — appending one fresh decision to any blocked state unblocks it;
   (c) *guard-off equivalence* — `stall_after_seconds=0` reproduces current behavior
   exactly.
3. **Wiring** (H-4): `forge.yaml` value reaches `check_rate_limit`; default applies
   when absent; `0` disables.
4. **Replay:** the four §5 historical episodes as fixture timelines, asserting the
   table's verdicts.

## 8. Operator decisions

**Decision 1 — Signal.**
- **(A, recommended) Option C predicate** (decision-clock staleness + work-pending
  guard, §4) — stateless, deadlock-immune, 2/2-0/2 backtest.
- (B) Q38's original newly-gated-delta counter — requires semantics fix + persistent
  state; weaker on restart.
- (C) Do nothing — accept the 8-day blind window; rely on relay prompts.

**Decision 2 — Threshold default.**
- **(A, recommended) T = 3 h** (`stall_after_seconds: 10800`) — 2.77× worst healthy
  gap, clean backtest.
- (B) T = 2 h — earlier detection, one marginal historical trip.
- (C) T = 6 h — maximum caution, ~2× the dead-submission waste per stall.

**Decision 3 — Rollout.**
- **(A, recommended) Enforce directly**, riding the next D104 ritual restart. The §5
  backtest over the table's full history *is* the shadow evidence — a log-only stage
  would cost a second operator-gated restart to flip the knob, to observe a detector
  we can already replay against every stall and non-stall on record.
- (B) Log-only first (`stall_after_seconds` honored for the journal line only), flip
  to enforce at a later restart after N clean days.

**Decision 4 — Placement.**
- **(A, recommended) Extend `check_rate_limit`/`RateLimitStatus`** (§6).
- (B) Separate `submission/stall_guard.py` + own loop wiring — cleaner separation,
  third export parse per iteration, second main.py seam.

Build plan on approval: one increment (rate_limiter + config + tests + docs), own
D-entry, `STATUS.md` block; service-inert until the next ritual restart (no urgency —
the runner just recovered; the next stall is what this buys down).
