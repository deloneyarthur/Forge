# Ceiling saturation experiment — DESIGN, HELD

**Status:** DESIGN ONLY. **Not registered, and deliberately so** — its precondition is unmet
(§5). Registering it now would produce a measurement of Crucible's refit queue rather than of our
grammar.
**Relates to:** `grammar-freeze-declaration.md` §4/§8, D368, `scripts/joint_frontier.py`,
`scripts/ceiling_record_test.py`. Relay 2026-08-06 (refit ordering) is the blocking dependency.

---

## 1. The question this exists to answer

"Have we exhausted the grammar's ceiling?" has never been answered, only inferred from quiet
periods. Freeze condition (C) tests whether a bulk-tail statistic **stopped rising over a window**
— which a bounded distribution and an unbounded quiet one both produce. Exhaustion is a different
claim and needs a different instrument.

**Exhaustion must be demonstrated by a saturation curve, not by waiting.**

## 2. The metric: frontier advances per DOUBLING of cumulative search

A config is a *frontier advance* if nothing earlier beat it on **both** binding axes
(`cpcv_sharpe_p25`, `walk_forward_sharpe_median`). The count of advances grows like log(n) for a
fixed distribution, so:

> Under a fixed, not-yet-exhausted distribution, **advances per doubling of cumulative search is
> constant.** Saturation appears as a monotone **decline** across successive doublings. An
> improving distribution appears as a **rise**.

This is the right unit precisely because it is invariant to how much we search — it cannot be
gamed by throughput, and it separates "we stopped looking" from "there is nothing left to find."

## 3. Observed baseline (2026-08-06) — and it already falsifies the exhaustion hypothesis

```
advances per doubling, ranked lane, stage one

swing_mid    2  3  2  2  2  2  3  3  6  4  4  3  5  6  5  7  10     n=139,730, 68 advances
swing_long   1  2  2  3  1  3  2  0  2  3  3  3  4  1   5           n= 18,611, 34 advances
```

**Neither lane shows the declining signature.** `swing_mid` is *rising* — 10 advances in its last
full doubling, the most of any — consistent with its permutation test (z=+3.71, p=0.003).
`swing_long` is flat at 2–3 per doubling: **stationary but not saturating.**

**A correction that this table forced, recorded because it was a real error.** On first reading the
per-lane permutation z-scores (swing_long −0.19, swing_short −0.05) we described those lanes as
"already exhausted." That is wrong and it is the exact confusion `joint_frontier.py`'s own docstring
warns about — *stationary is not ceiling-reached*. A stationary distribution still yields new maxima
at the baseline rate, and swing_long's do not stop. What is true of swing_long is different and
still useful: **its frontier sits far below the promotion gate** (max cpcv 1.084 among rows with
WF ≥ 2.0; it has never produced a config at cpcv ≥ 1.5). A low ceiling, not a reached one.

## 4. The experiment

**Cell under test:** `mean_reversion / swing_mid` — the only lane that has ever put a config above
both binding gates, holder of every record, and the only one with a rising advance rate.

**Intervention:** concentrate ranked-lane search in the cell to reach **one further doubling** of
its cumulative stage-one count.

**Prediction (to be registered when unblocked):** advances in the next doubling are **not fewer
than** the mean of the last three completed doublings (5, 7, 10 → mean 7.3), against a
one-sided test.

**Falsifier — and this is the outcome worth having:** advances in the next doubling fall
materially below that baseline, *and* the decline continues into a second doubling. Two
consecutive declining doublings is the saturation signature. **A single low doubling is not**, and
the prereg must say so, because advance counts are small integers with real Poisson noise —
sd on a count of ~7 is ~2.6.

**Required n, stated in advance (the D363/D364 rule):** one doubling of swing_mid means **+139,730
ranked stage-one rows in that cell**. At the observed accrual (~4,200/day) that is **≈33 days**,
and mix concentration cannot shorten it much — swing_mid is already 80.7% of supply, so the
reachable speed-up is ~1.24×, not 2×. **The honest cost of this experiment is about a month**, and
a design that pretends otherwise would repeat the D364 failure of discovering the denominator at
resolution.

**Two consecutive doublings** — the full falsifier — is therefore a ~3-month commitment. That cost
is itself an argument for fixing §5 first.

## 5. THE PRECONDITION — why this is held

**61% of swing_mid configs clearing both binding gates never reach stage two** (D368: 14 of 23,
identical stage-one verdicts, refit latency p99 = 2h so they were passed over rather than queued).
Frontier advances are computed on stage-one values and so are not *directly* corrupted by that —
but the experiment's purpose is to characterise the reachable ceiling, and a ceiling measured while
a recency-ordered queue discards most of the qualifying output is a property of the queue.

More practically: if refit ordering becomes quality-aware, the *value* of a frontier advance
changes discontinuously — advances would start converting instead of being discarded — and the
experiment would be measuring a different world halfway through. Running it across that boundary
would produce an uninterpretable series, exactly like the composition drift that voided the first
version of freeze condition (C).

**Unblocks when:** Crucible answers the 2026-08-06 refit-ordering relay, either way. A "no, recency
is deliberate" answer unblocks it just as cleanly as a change would — what cannot be tolerated is
running the experiment *across* an unannounced change.

## 6. What this experiment cannot decide

- **It is a per-cell result.** Saturating `swing_mid` would not license "the grammar is exhausted";
  it would license "this cell is exhausted at this search depth."
- **It says nothing about assembly.** Frontier advances are solo statistics, and D361 stands:
  promotion is an assembly property and no solo metric ranks on that axis. A cell can saturate on
  (cpcv, WF) and still matter — `swing_long` is bad on every solo metric and sits in 7 of 7
  promoted books.
- **It cannot see representable-but-unsampled territory.** 19 of 72 registered indicators are dark
  and the largest trend cell has never carried a second regime gate. Saturating the sampled surface
  is evidence about the search, not about the grammar.
