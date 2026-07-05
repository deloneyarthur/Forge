# Forge §7.3 throttle — backpressure-restoration proposal

**Status:** DRAFT · operator-gated · **no code or config changed** · investigation + design only
**Date:** 2026-06-16 (live reads ~00:00Z 2026-06-17 / ~17:00 PDT 06-16)
**Author:** Forge session (diagnosis of "Crucible queue is large — is the throttle working?")
**Touches:** `forge.submission.rate_limiter`, `forge.feedback.consumer` (`STRANDED_AFTER`), `config/forge.yaml`
**Hard-rule check:** does NOT touch Crucible's gate (Rule #3); not a grammar change; not an auto-loosening (Rule #4) — this is auto-*tightening* (Forge submits less). Determinism (Rule #6/#8) preserved — gates submission, not enumeration; reads DB/wall-clock exactly as the existing stall guard already does.

---

## 1. Verdict

The §7.3 in-flight limiter is **mechanically healthy but is not delivering backpressure**, and the §7.3 *goal* — "prevents the inbox from becoming a deep queue Forge can't learn from" (DESIGN.md §7.3) — **is being missed by a wide margin.**

- It has **not blocked once** this boot: 21 batches, all `submitted=200` (`cli/main.py:1742` wires it; the `blocked` path at `:1748-1766` never fired).
- Meanwhile **54,228 configs are in flight**, oldest **7 days** old.
- **The clearest measure of the miss:** of **184,589** lifetime submissions, only **49,998 (27%)** ever received a real Crucible decision. **80,163 (43%)** were sentinel-flushed as aged-out orphans; **54,228 (29%)** are still stuck `submitted`. **73% of everything Forge has submitted never produced a learning signal.**

This is not a runaway — a *separate* mechanism (the D052/D110 aged-out flush) bounds the queue at ~8 days of accumulation. But "bounded at ~8 days of mostly-dead rows" is not the same as the §7.3 promise of a shallow, learnable queue.

## 2. Evidence (live, this session)

**Queue depth (forge.db snapshot).** `status='submitted'` = 54,228; oldest `submitted_at` = 2026-06-09 00:55 (7d). By submit-day: 06-09 = 2,019 · 06-10 = 3,663 · **06-11 = 14,843** · 06-12 = 6,095 · 06-13 = 7,340 · 06-14 = 9,688 · 06-15 = 5,495 · 06-16 = 5,085.

**The throttle clears on a zombie.** The oldest in-flight batch (`2cad5dce`, 06-09 00:55) is **82.5% gated** (165/200, 35 permanent stragglers) → `pct ≥ 0.80` → **CLEAR**. The next-oldest in-flight batches sit at **15%, 14%, 0%, 62%** — any of which would block, but the oldest-only rule (`rate_limiter.py:152`) never looks at them. The 35 stragglers are **not in Crucible's export** (0 of the 3,000 oldest *and* 0 of the 3,000 newest in-flight hashes appear in the 10k-row export window) → they will never reconcile through the normal join, so the batch stays ≥80%-but-never-100% and remains "oldest" until the 8-day flush retires it.

**Throughput imbalance is structural, not a collapse.** Crucible decides steadily at **~280/hr** (range 214–355/hr, flat all day, from export `decided_at`). Forge submits **~480/hr** (200 per ~24.5 min). **~1.7× sustained over-submission**, every day for a week.

**Real submit→decide latency** (join export `decided_at` − forge `submitted_at`, 9,405 matched): **p50 = 3.0h · p90 = 13.9h · p99 = 74.6h (3.11d) · max = 6.99d.** The flush margin `STRANDED_AFTER = 8d` therefore sits **4.9 days above the real p99**.

**Config deployed** (`forge.yaml:16-21`): `inflight_threshold: 0.80`, `stall_after_seconds: 10800` (3h), `batch_size: 200`.

## 3. Root cause — three compounding mechanisms

1. **Wrong metric (per-batch, not aggregate).** §7.3 / `check_rate_limit` gates on the completion fraction of a *single* batch. It structurally cannot represent 54k configs across ~270 in-flight batches. The spec's mechanism ("previous batch ≥80%") was never a depth bound.

2. **Zombie-batch pinning.** The oldest in-flight batch is permanently ≥80% (real decisions) with a residue of never-decided stragglers that have aged out of Crucible's 10k export window. It is simultaneously **over threshold** (so it can't block) and **permanently the oldest** (always has `submitted` rows) → a permanent CLEAR signal. Because *every* batch sheds some never-decided stragglers, there is **always** a 7–8-day-old zombie holding the pin. The flush (below) retires each zombie at 8 days, but a fresh one has already taken its place.

3. **Stall guard can't see a slow gate.** `stall_after_seconds=10800` only trips if Crucible's decision clock (`max(decided_at)`) goes stale for 3h. Crucible decides every minute, so the clock always advances and the guard never fires. It catches a *dead* gate, not a chronically *underwater* one (`rate_limiter.py:244`).

**The flush interaction (already known to the authors).** `consumer.py:80` and `:350-351` state the D052/D110 flush exists *because* stranded rows "pin D046's oldest-batch rate-limit policy." The flush works — **80,163 rows retired** — but on an **8-day** lag. With real p99 latency at ~3.1d (`§2`), that margin is ~2.6× oversized; the docstring's basis ("p99 ~7.2d, biased high by window survivorship", `consumer.py:86`) had the survivorship bias backwards — direct measurement says real p99 ≈ 3d. So orphans that will never be decided occupy the queue ~8 days, and the throttle stays pinned for that whole window.

## 4. Spec grounding

> **DESIGN.md §7.3:** "Forge does not submit a new batch until the previous batch is at least 80% complete in Crucible. **This prevents the inbox from becoming a deep queue Forge can't learn from.**"

The **goal** (italic) is a shallow, learnable queue. The **mechanism** (per-batch 80%) is one way to approximate it that holds only while Crucible drains FIFO at ~Forge's rate. That precondition broke (1.7× imbalance + straggler aging), so the mechanism no longer serves the goal. Lineage: D046 (oldest-batch, not latest) → D052/D110 (aged-out flush to stop the pin) → Q38/D137 (stall guard as a *second independent block reason*). This proposal continues that line: a **third independent block reason** that enforces the §7.3 *goal* directly.

## 5. Proposed fix (two tiers)

### Tier 1 — immediate, cheap, partial: shrink the flush margin
Lower `STRANDED_AFTER` **8d → 5d** (`consumer.py:89`). 5d is still > real p99 (3.1d) with ~2d of headroom, but retires the never-decided tail ~3 days sooner. Effect: queue depth drops toward a ~5-day accumulation (~30–35k), and zombies retire fast enough that the *existing* oldest-batch throttle begins to expose genuinely-incomplete recent batches as the blocker — i.e., it starts to block intermittently again. **This does not by itself cut over-submission; it un-pins the existing throttle.** One-line constant change to an already-tested function; lowest risk; the docstring already invites tuning it down once true latency is known (`consumer.py:87`).

### Tier 2 — the real fix: aggregate in-flight-depth block reason
Add a **third independent block reason** to `check_rate_limit`, mirroring the stall guard's shape (`RateLimitStatus.stall_blocked` → add `depth_blocked`):

- Compute **genuine in-flight depth** = count of `status='submitted'` rows with `submitted_at > max(decided_at) − STRANDED_AFTER` (i.e., not-yet-flushable — excludes the dead tail so the gate measures real pressure, not orphan backlog).
- **Block** when that depth exceeds a cap, default **`max_inflight = 3 × batch_size` (600)** — keeps Forge to ~1–3 batches genuinely in flight, the §7.3 "one batch at a time" intent.
- Daemon logs `blocked: in-flight depth N > cap M` (new branch beside `:1748-1766`); knob in `forge.yaml` (`submission.max_inflight`, 0 = off), default-off in the function for byte-identical determinism, exactly as `stall_after_seconds` is handled (`rate_limiter.py:145`).

This bounds the learnable queue directly, is immune to zombie-pinning (aggregate, not one batch), and composes with — does not replace — the existing completion-fraction and stall checks. **Auto-tightening** → per Rule #4 it *could* ship without approval, but it is §7.3-structural and you asked for a proposal, so it stays operator-gated.

## 6. Test plan (TDD — invariants first, per CLAUDE.md)

1. `tests/invariants/` — new failing test: with N>cap synthetic `submitted` rows (all fresh, none flushable) and an oldest batch ≥80%, `check_rate_limit(..., max_inflight=cap)` returns `clear=False, depth_blocked=True`. Asserts the zombie-pin scenario from §2 is now caught.
2. Determinism guard: `max_inflight=0` ⇒ `RateLimitStatus` byte-identical to today (completion-fraction + stall only).
3. Stranded-tail exclusion: rows older than `max(decided_at) − STRANDED_AFTER` do **not** count toward depth (else the dead tail would block forever — the failure mode we're removing).
4. Tier-1: re-pin `STRANDED_AFTER` test expectations (the flush has direct tests around the watermark) and add a regression asserting margin > a configurable latency p99 fixture.
5. Full suite + `mypy --strict` + `ruff` on changed scope; then the deploy ritual (`docs/tasks/deploy.md`) — stop service, uncontended suite, commit, restart, verify journal shows the new block line under load.

## 7. Risks & open dependencies

- **Latency measurement is survivorship-biased** (only configs still in the 10k window were matched). It biases p99 *low*, so keep Tier-1 margin ≥ 5d and revisit if Crucible publishes a true latency distribution. A Crucible relay (you deprioritized this) would settle both the real latency and the 1.7× throughput imbalance — note that **the imbalance is upstream of Forge**: even a perfect throttle just means Forge *waits more*, it does not make Crucible faster. Tightening the throttle trades queue depth (and wasted Forge prefetch/battery/rank compute on configs that never get graded) for a slower but *learnable* stream — which is the §7.3 bargain.
- **Don't over-tighten into starvation.** If `max_inflight` is set below Crucible's true in-flight capacity, Forge idles. Default 600 (3 batches) is conservative given ~280/hr decode and p90 14h latency (~3,900 genuinely-in-flight at steady state would be "Crucible-limited"); 600 deliberately throttles Forge *below* that to drain the backlog, then can be raised. Make it a config knob and tune live.
- **Spec status.** §7.3's literal text is per-batch; the depth gate is an *addition*. Precedent (stall guard, Q38/D137) added a block reason without a spec rewrite, but flag for operator/spec sign-off whether DESIGN.md §7.3 should be amended to state the depth bound explicitly.

## 8. Explicitly NOT proposed
No change to Crucible's gate or any promotion criterion (Rule #3). No grammar change. No loosening. No change to enumeration/ranking. The 73%-orphan finding is **not** an argument to submit *more* or differently — it is the cost of the current over-submission, which this proposal reduces.

## 9. Recommendation
Ship **Tier 1 now** (one-line, data-backed, un-pins the existing throttle) and **build Tier 2** as the durable fix (third block reason, stall-guard pattern, TDD). Both behind the deploy ritual. Optionally pair with a Crucible relay on the 1.7× throughput imbalance + true latency, to right-size `max_inflight` and `STRANDED_AFTER` from Crucible-side ground truth rather than survivorship-biased Forge estimates.

---
*Appendix — key references:* `rate_limiter.py:105` (`check_rate_limit`), `:152` (oldest-batch select), `:230` (clear logic), `:244` (stall guard) · `cli/main.py:1742` (call site), `:1748` (blocked log) · `consumer.py:89` (`STRANDED_AFTER`), `:340` (`_flush_aged_out_submissions`), `:454` (flush call site) · `forge.yaml:16` (submission block) · DESIGN.md §7.3.
