# Prompt — Crucible: teach the strategy-path threshold signal a PERCENTILE mode

> **From:** Forge (planning for grammar v6; Decision D099, 2026-06-02)
> **To:** the Crucible signals/engine agent
> **TL;DR:** Forge wants to stop emitting *absolute* signal thresholds (an
> `rsi_2 < 8` calibrated once on SPY fires at an uncontrolled, name-dependent
> rate on every other ticker) and start emitting **percentile** thresholds
> (`rsi_2` in the bottom 5% of its own trailing 252-bar distribution). The
> params ride inside the existing `SignalSpec.params` dict — **no contracts
> change**. But Crucible's strategy-path `ThresholdSignal` does a raw compare
> today and would **misroute** the new params into indicator construction, so
> **Crucible must land percentile-mode FIRST**. It is a no-op until Forge emits
> the new keys, so it is safe to deploy ahead of Forge. Forge will not flip its
> emission (the v6 bump) until you confirm this is live.

This is the coordinated half of a two-repo change. Forge holds its side until
yours lands and you report back the param contract you actually implemented.

---

## Why (the binding constraint)

Crucible's funnel + a 2026-06-02 firing decomposition show the constraint on
strategy discovery is signal **firing**, not the gate or liquidity: ~70% of
decided runs never trade. Family split among qualified components' zero-entry
folds:

- **mean_reversion** — ~78% *directional*-never-fired (absolute `rsi_2`
  threshold too tight for most names).
- **trend_continuation** — ~58% *regime*-gated (the `adx`/`hurst` gate is too
  restrictive at an absolute level).
- **volatility_event** — fires in ~every fold. Forge will **not** touch this
  archetype's indicators (see scope below), but your change is generic so it
  doesn't matter to you.

Root cause is on the Forge side: the sampler draws absolute thresholds via
`rng.uniform` over ranges calibrated once on SPY
(`forge/src/forge/enumeration/indicator_thresholds.py:419,425`) and applies them
to every ticker. An absolute threshold fires at an uncontrolled rate per name. A
percentile of the indicator's own trailing distribution fires at a controlled
rate by construction. (Note for the record: an earlier draft of this work cited
"DESIGN.md §5.2:613" as already mandating this — that citation is wrong; the
percentile-threshold idea is a *new* design direction, logged as Forge D099, not
a pre-existing spec requirement.)

---

## The contract (what Forge will put in `SignalSpec.params`)

`SignalSpec.params` is `dict[str, Any]` in `crucible_contracts` 1.14.0
(`models.py:155`) — already open, **no contracts bump required**. When Forge
opts a signal into percentile mode it will emit:

```jsonc
{
  "threshold": 0.05,          // a PERCENTILE in [0, 1] (NOT a raw indicator value)
  "op": "<",                  // same _compare ops you already support
  "use_percentile": true,     // NEW — the mode switch
  "percentile_window": 252    // NEW — trailing window length (default 252)
}
```

**Semantics (operator-chosen: percentile in [0, 1]):** rank the latest indicator
value against its own trailing `percentile_window` bars, get a percentile
`p ∈ [0, 1]`, then `fired = _compare(p, op, threshold)`. Your existing
`_percentile_rank` in `optbt/signals/threshold.py:65` already returns exactly
this `[0,1]` convention (`below / n`), so reuse it.

Worked examples:

| intent | params | fires when |
|---|---|---|
| mean_reversion `rsi_2` directional: enter when oversold (bottom 5%) | `{threshold: 0.05, op: "<", use_percentile: true}` | `percentile_rank(rsi_2_today) < 0.05` |
| trend_continuation `adx` regime gate: allow when trend strong (top 30%) | `{threshold: 0.70, op: ">", use_percentile: true}` | `percentile_rank(adx_today) > 0.70` |

When `use_percentile` is **absent or false**, behaviour is **byte-identical to
today** — `threshold` is the raw indicator value and you compare the latest
value directly. The ~49k historical raw-threshold configs must be untouched.

---

## What to change (and why it's small)

A read-only feasibility pass over your tree (2026-06-02) says this is a modest,
low-risk addition — the series and the percentile helper already exist; only the
cache reduces them away. Concretely:

**1. `optbt/strategy/signals/threshold.py` — `ThresholdSignal.evaluate` / `_latest_indicator_value`.**
   - When `spec.params.get("use_percentile")` is truthy, instead of comparing
     the latest value, obtain the **trailing `percentile_window`-bar series** of
     the indicator (all bars `<= snap.asof` — no lookahead, `MarketSnapshot`
     already guarantees `<= asof`), compute the percentile of the latest value
     within it, and `_compare(percentile, op, threshold)`. The `fired` boolean
     then plugs into your **existing role branch unchanged**
     (`regime_filter → SignalVote(allow=fired, value=latest)`;
     `directional → LONG_CALL if fired else FLAT`). Percentile only changes how
     `fired` is computed.
   - **Insufficient-history guard:** mirror your base-signal impl
     (`optbt/signals/threshold.py:42-44`) — if the cleaned trailing window has
     `< percentile_window // 4` values, return the **safe default / FLAT** (do
     not fire). Keeps the early-backtest warmup honest and deterministic.

**2. The param-exclusion filter — IMPORTANT, this is the misroute bug.**
   `_latest_indicator_value` builds
   `indicator_params = {k: v for k, v in spec.params.items() if k not in ("threshold", "op")}`
   (`optbt/strategy/signals/threshold.py:83-85`, and the sibling copy in
   `evaluate`). Today that would pass `use_percentile` / `percentile_window` into
   `build_indicator(...)` and into the cache key — almost certainly an
   `Unknown param` error or a polluted cache key. **Add `"use_percentile"` and
   `"percentile_window"` to the excluded set everywhere `spec.params` is
   projected into `indicator_params`.**

**3. The indicator cache — minimal extension.**
   `optbt/strategy/signals/_indicator_cache.py` already computes the **full**
   polars series in `build_indicator_series_over_period`
   (`indicator.compute(bars.lazy())`, ~line 161) and then **discards** it down to
   `dict[date, float]`. Retain enough to answer a trailing-window percentile at
   `asof` — e.g. keep the ordered `(date, value)` series alongside the point
   dict and add a `get_percentile(indicator_id, params, underlying, asof,
   window)` that slices the `window` values `<= asof` and calls
   `_percentile_rank`. Memory cost is ~`O(window)` floats per (indicator,
   params, underlying) — negligible. (The slow path in `_latest_indicator_value`
   already has the full series in hand before `.tail(1)`, so it needs no cache at
   all — just don't throw the series away in percentile mode.)

**4. Reuse, don't duplicate.** `_percentile_rank` lives in
   `optbt/signals/threshold.py:65-71`. Lift it to a shared util or import it;
   please don't fork the logic.

You do **not** need to wire up the *other* `ThresholdSignal` in
`optbt/signals/threshold.py` (the one taking `long/short_threshold` + a
`history` series). That class is not on the `SignalSpec` path; reconciling the
two `ThresholdSignal` implementations is your architectural call and is **out of
scope** for this change — only `optbt/strategy/signals/threshold.py` consumes
Forge configs.

---

## Hard requirements

- **Backward compatible.** No `use_percentile` ⇒ exact current raw behaviour. No
  change to any of the ~49k historical configs, and **no change to Crucible's
  promotion gate** (Forge hard rule #3 — this is about *whether a signal fires*,
  never about validation strictness).
- **No-op until Forge emits.** Because the mode is detected per-signal from
  params, deploying this changes nothing until Forge starts sending the keys.
  That is the point — it lets you land and verify ahead of Forge.
- **No lookahead.** The trailing window must be bars `<= asof` only.
- **Deterministic.** Same config + same data ⇒ same fire/no-fire (percentile is a
  pure function of the trailing window).
- **No contracts change** (params is already open). If you find you *do* need a
  contracts change, stop and tell Forge — that changes the sequencing.

---

## Definition of done (and what to send back to Forge)

1. `optbt/strategy/signals/threshold.py` honors `use_percentile` for **both**
   `directional` and `regime_filter` roles, reusing `_percentile_rank`, with the
   insufficient-history guard.
2. `use_percentile` / `percentile_window` are excluded from `indicator_params`
   (the misroute is closed) — ideally with a regression test that a percentile
   config does not raise `Unknown param`.
3. A test proving: (a) a raw config is unchanged; (b) a percentile config fires
   iff the latest value's trailing-window percentile satisfies `op`/`threshold`;
   (c) warmup returns the safe default.
4. **Report back to Forge:** the **exact param keys + units you implemented** (so
   Forge emits precisely that — if you diverge from `{threshold∈[0,1], op,
   use_percentile, percentile_window}`, Forge conforms to yours), the commit
   hash, and confirmation it is deployed and is a verified no-op on current
   (raw) traffic.

Once Forge has your confirmation, Forge bumps the grammar `v5 → v6`, flips the
sampler to emit percentile params for the in-scope indicators only
(mean_reversion directional pool + the `adx`/`hurst` trend gate — **not**
`volatility_event`'s indicators, **not** the already-rank `iv_rank`/`rv_rank`),
and you can A/B it via `crucible funnel --compare v5 v6`.

---

**END OF PROMPT.**
