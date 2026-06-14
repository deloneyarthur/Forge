# Proposal: throughput cut — bound the submission queue + match Crucible's drain rate

Status: **PROPOSAL — option A (queue-depth brake) build DECLINED by operator 2026-06-14; not building.**
The queue runaway (41,842, +10k/day) is accepted for now — per [[D146]] the un-drained capacity has
**no promotion cost** (the wall is edge magnitude, not volume); the residual cost is Crucible
inbox bloat + multi-day-stale feedback. Revisit if either bites. Option B (top-N cut) likewise
not building. Kept as the diagnosis-of-record (the §7.3 straggler loophole).
Date: 2026-06-14 (Sunday review lever #1). Relates to: §7.3 (`src/forge/submission/rate_limiter.py`),
[[D137]] (stall guard, the sibling block reason), [[D146]] (why cut capacity has nowhere better to go),
[[pipeline-vision-roadmap]] Phase 4 ("concentrate the stream"). Snapshot: `forge_sunday_160016.db`.

## The problem (measured 2026-06-14)

- **Queue depth: 41,842 un-reconciled (`status='submitted'`)** — **2× the 06-11 baseline (19,882)** and
  growing **~10k/day** (submit ~17,600/day vs Crucible decide ~7,400/day = **2.4× oversubscription**).
- **Oldest un-reconciled config: 2026-06-09** — a **5-day** backlog. Forge's feedback learns from
  verdicts that lag the live stream by days; the loop is *producing into a queue it can't learn from
  in time* (§1.2/§1.3 — the stream's promote-likelihood can't improve if its feedback is 5 days stale).

## Root cause — the §7.3 throttle has a straggler loophole (diagnosed)

§7.3 (`check_rate_limit`) blocks the next batch until **≥80% of the *oldest* in-flight batch** is gated.
It bounds the *front* of the queue, **not total depth**. Measured: the oldest in-flight batch (06-09) is
**82.5% gated** → the throttle *clears* and admits a new batch every poll while that batch's last 17.5%
straggle indefinitely. **60 batches** currently sit `≥80%-gated but still carrying 'submitted' stragglers`
— each a permanently-clearing "oldest," so submission is effectively unthrottled and the queue balloons.
The completion-fraction design (D036/D070) was sized for a single in-flight batch draining within a poll
cycle; under multi-day latency it no longer binds. The D137 stall guard catches a *frozen* gate, not a
*slow-but-moving* one, so it doesn't fire here.

## Why cut now (low risk, real upside)

- Per [[D146]] the reclaimed/cut capacity has **nowhere better to go** (bear/ranging supply is
  Crucible-gated; the pool's magnitude wall isn't a volume problem) — so trimming volume costs nothing
  in promotion terms and **tightens the feedback loop** (fresher verdicts → faster learning).
- It makes the operator's "**fewer but stronger**" vision concrete: submit Crucible's scarce capacity the
  ranker's *best*, not 200/batch indiscriminately.
- Hard rule 4: fewer/higher-ranked submissions is **tightening-direction** — shippable without a loosening
  approval (still via the D104 ritual restart).

## Options

### A. Queue-depth brake — a third §7.3 block reason [Forge-side, F3-INDEPENDENT] — recommended floor
Add a `max_inflight_queue` ceiling to `check_rate_limit`: block when total `status='submitted'` across all
batches exceeds the ceiling (e.g. 2–3× Crucible's daily drain ≈ 15–20k), independent of the per-batch
completion fraction. Directly closes the straggler loophole (bounds total depth regardless of front-batch
%), deterministic, needs no ranker trust. Inert default (0 = off) like the stall guard; production knob in
`forge.yaml`. **This is the safety floor — it stops the runaway.**

### B. Cut batch size / top-N — submit fewer, higher-ranked [Forge-side, F3-GATED]
Drop `batch_size` from 200 to e.g. 50 (or a top-N of the ranked survivors). The cut falls entirely on the
ranker's **weakest tail** — so it's only sound if the ranker is trusted. **F3 is now 3/3 PASS**, which is
exactly the validation the agenda gated this on. Reduces submit rate ~4× → roughly matches Crucible's
drain. Pairs naturally with A (A bounds depth; B improves per-slot quality). Independent of the §8.6
tail-margin (that gates *what* the ranker optimizes, not *how many* it submits).

### C. Slower cadence [Forge-side] — crude fallback
Longer inter-batch sleep. Reduces rate without changing per-batch quality or depth-bounding; strictly
weaker than A+B. Listed for completeness; not recommended.

## Recommendation / sequencing

1. **Ship A (queue-depth brake) first** — it's F3-independent, deterministic, stops the measured runaway,
   and fixes the straggler loophole at the source. Smallest correct increment; TDD + ritual restart.
2. **Then B (top-N cut)** as the "fewer/stronger" lever, now F3-justified (3/3 PASS). Could ride the same
   restart as A or D145.
3. **Skip C.**

Open sub-question for A: should the brake count *true* in-flight (exclude the straggler tail that may never
reconcile — i.e. age-out configs older than N days), or raw `submitted`? Aging-out stale stragglers (cf. the
D052 sentinel flush) may be the cleaner root fix and is worth pairing with the ceiling. Flag for the build.

## What this is NOT
Not a gate change, not a grammar/loosening (hard rules 3/4/6 intact). A submission-throttle (§7.3) policy
change — deterministic, ships via the D104 ritual restart. Does not touch enumeration or ranking logic
(B only changes how many ranked survivors are taken, not their order).
