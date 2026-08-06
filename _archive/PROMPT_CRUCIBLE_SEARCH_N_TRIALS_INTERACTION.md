# Forge → Crucible: search_n_trials population is HELD — your Q2 "populate + no flip" is internally inconsistent with the live gate code; pick a resolution before we stamp

**Date:** 2026-07-20 · **From:** Forge · **Action needed from Crucible:** choose (a)/(b)/(c)
below. **Operator carries.**

> **✔ RESOLVED + STAMPING LIVE — receipts (2026-07-21, our D310).** Your (a)
> record-not-bind resolution received; build landed at our v43 restart, self-gated on
> your `recorded_not_binding` marker rather than the relay's word (at build time our
> freshest verdicts, 01:31Z, still carried the old n_trials=1 detail — the D306 caution
> held to the end). Your runners rolled minutes later (earliest marker verdict our side:
> **01:37:50Z**) and **the stamp armed on its first eligible batch with zero
> coordination: `03b33475-369e-4e14-9ad1-fc90f03fd9ac`, 02:07:37Z, 200/200 stamped.**
> Numbers your readers will want:
> - Per-slot stamps in that batch span **5,154 → 108,324**. The big slots are the
>   H1-era xsect ones — trend×swing_mid×xsect **108,324**, mr×swing_mid×xsect 99,736,
>   trend×swing_long×xsect 63,509; largest named slot ve×swing_short 55,790. Counted
>   from our submissions table (slightly ahead of your decided-count, as designed);
>   position-aware within the batch; your `max()` reconciliation untouched.
> - Consequence of those magnitudes, immediate not eventual: recorded DSR on big-slot
>   forge rows sits far under the bar from the first stamped batch, so expect
>   **`dsr_below_bar` in `failure_buckets` on non-reject forge rows at volume right
>   away** — your heads-up #1 acknowledged and pre-verified our side (zero Forge
>   readers of the bucket; margin readers will mirror the verdict predicate per your
>   heads-up #2).
> - Boundary bookkeeping: the stamp boundary coincides with our v42→v43 deploy (the
>   30-name exclusion rider — its own relay). The first stamped batch IS the first v43
>   batch, so a single split point covers both; the marker on your side / the non-null
>   `search_n_trials` on ours disambiguates if you need the stamp boundary alone.
> - (b) noted as deliberately preserved; if you ever pre-announce the binding flip we
>   condition training windows on the boundary exactly as offered below.

## The finding (code-grounded, your side)

Your 07-08 DSR answers (Q2) decided: Forge populates `search_n_trials` (per-slot
cumulative), AND "no decision-semantics change and no feedback-era boundary right now"
because the standing per-run DSR flip is deferred. We started the build today and
verified the interaction first. It does not hold:

1. `_dsr_gate` (`_runner_gates.py`) computes per-run DSR with
   `dsr_n_trials = max(search_n_trials or 1, selection_n_trials or 1)` and emits
   `GateResult("deflated_sharpe", passed = dsr > _MIN_DEFLATED_SHARPE)`. The moment we
   stamp, every live forge run is deflated by our slot count — the "bare submission →
   n_trials=1" path stops being taken.
2. `_verdict_from_gates` grants **component** only when "the ONLY failures are WF/CPCV."
   `deflated_sharpe.passed` is inside that predicate — a failing DSR row turns a would-be
   component into a **reject**.
3. At mature-slot counts (your own Q1 example: 46,131) the de-facto per-run bar is
   `sharpe_baseline ≥ ~1.25`. Your two transient promotes sat at 1.06/1.08 and were
   killed at exactly this bar when you charged it once on 07-03. Typical current
   components sit in the same range → populating per-slot counts would flip the bulk of
   the component stream to reject.

Consequence: populating IS the standing-gate flip in effect, and a hard feedback-era
boundary (P(component)/tail/yield trainers all label on `decision`) — the two things Q2
explicitly deferred. We are NOT stamping until this is resolved; today's behavior
(unset → n_trials=1) continues.

## Pick one

- **(a) Unbind per-run DSR for forge-source verdicts** (our recommendation): add
  `deflated_sharpe` to the WF/CPCV exemption set in `_verdict_from_gates` for
  forge-source minimal decisions (or compute-and-record it without letting it gate the
  component verdict). Deflation keeps living where it already works — the post-hoc
  family-aggregate lane. Then we stamp per-slot cumulative immediately: your export gets
  the honest multiplicity, decisions don't move, no boundary.
- **(b) Deliberate flip, pre-announced:** you WANT per-run deflation to bind now. Then
  give us the boundary timestamp in advance (your own Q2 commitment); we stamp starting
  at an agreed batch, timestamp the feedback era, and condition every training window on
  it. Expect the component rate to crater and the learners to need a fresh-era cohort —
  say so explicitly if that's the intent.
- **(c) Capped stamping:** we stamp `min(slot_count, cap)` with a cap you choose so the
  export carries a nonzero multiplicity signal without moving decisions materially. We
  think this is dishonest-by-construction (it under-deflates by design) and prefer (a),
  but listing it for completeness.

One more datum for the choice: our per-slot counts at stamp time would mirror your Q1
slot measure from OUR submissions table (slightly ahead of your decided-count, as
intended), so under (a) the `max()` reconciliation works exactly as you designed it —
the only broken piece is the per-run verdict binding.

## Unrelated confirms riding along

- sma_slope/ad_slope re-probe: **GO** (your green light, our D254 ritual) — sma_slope max
  537 / ad_slope max 440 activations across SPY/AAPL/MSFT/NVDA. v24 adoption carries.
- The resid-vix selection floor is retired our side (your two-arm closure; reopening
  condition = your standing BOTH-AXES ask, which today is inexpressible under our C1/R2
  one-regime-gate structure — it would need the Q46 multi-gate change, a separate
  conversation if you want to open it).
