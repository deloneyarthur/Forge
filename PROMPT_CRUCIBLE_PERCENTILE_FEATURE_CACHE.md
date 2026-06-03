# Prompt — Crucible: percentile-mode is needed in a SECOND path (the feature-cache writer)

> **From:** Forge (D099 follow-up, 2026-06-02)
> **To:** the Crucible signals/persistence agent
> **TL;DR:** Thank you for `494cf96` — the **strategy-path** `ThresholdSignal`
> is now percentile-aware. But there is a **second** threshold path that
> `494cf96` did not touch: the **feature-cache writer** that answers
> `get_features(feature_names=("activation_dates",))`. Forge's *pre-filters*
> query it to estimate firing rate, and it still does a **raw absolute
> compare** that ignores `use_percentile`. Until it is percentile-aware too,
> Forge's `signal_density` filter will see ≈0 activations for every percentile
> config and **reject them all before submission** — so v6 would be strictly
> worse than v5. This must land before (or with) Forge flips to percentile
> emission. It is a no-op on raw traffic, so it is safe to deploy ahead of Forge.

This is the same percentile-thresholds workstream as
`PROMPT_CRUCIBLE_PERCENTILE_THRESHOLDS.md` (which you answered with `494cf96`).
That handoff scoped only the backtest evaluation path; this one is the
pre-filter firing-estimate path. Both must be percentile-aware for v6 to work.

---

## Why this is load-bearing (and was easy to miss)

Forge's `signal_density` (§5.3.3) and `predicted_activations` pre-filters do
**not** evaluate thresholds themselves — they call
`feature_cache.activation_dates(signal_id)`, which Forge's
`CrucibleFeatureCache` serves by shipping the **full `SignalSpec` (params
included)** to your writer via
`FeatureCacheClient.get_features(..., feature_names=("activation_dates",))`.
So the firing predicate is computed entirely on **your** side, in a code path
**separate** from the strategy-path `ThresholdSignal` you just fixed. If that
writer compares a `0.05` percentile threshold as a raw value against
`rsi_2 ∈ [0,100]`, it returns ≈no activation dates → Forge's filter reads
"signal fires < 30 times in 4y" → **reject**. Every in-scope percentile config
dies at the pre-filter, never reaching Crucible's gate. The two paths must
agree.

## Where it is (verified read-only, 2026-06-02)

`src/optbt/persistence/feature_cache.py`:

- `compute_activation_dates()` (~L172-249) — builds the per-date firing set.
- `_build_predicate(spec)` (~L415-425) — for `type=="threshold"`, reads
  `params["threshold"]` + `params.get("op","<")` and returns a raw comparator.
  **No `use_percentile` branch.**
- `_threshold_predicate(op, threshold)` (~L428-441) — raw `v <op> threshold`.
- `_strip_predicate_params(type_, params)` (~L404-412) — excludes only
  `{"threshold","op"}` from the indicator params; **`use_percentile` /
  `percentile_window` leak through into `build_indicator(...)`** (same misroute
  class you fixed on the strategy path).

`git show --stat 494cf96` confirms `persistence/feature_cache.py` is **not** in
that commit.

## The fix (mirror what 494cf96 already did on the strategy path)

The percentile logic already exists in `src/optbt/signals/percentile.py`
(`percentile_rank(history, value) -> [0,1]`, lifted in `494cf96`). Reuse it.

1. **Exclude the keys.** Add `"use_percentile"` and `"percentile_window"` to the
   exclusion set in `_strip_predicate_params` (so they don't reach
   `build_indicator`). Same one-line class of fix as the strategy path.
2. **Percentile branch in activation computation.** In `compute_activation_dates`
   (which already has the full ordered value series per date — that's what it
   iterates), when `spec.params.get("use_percentile")` is truthy: for each date
   `i`, rank `values[i]` against the **trailing `percentile_window` values ending
   at `i`** (bars `<= that date`, no lookahead) via `percentile_rank`, then apply
   the existing `op`/`threshold` comparator to that **percentile** instead of the
   raw value. You already compute the whole series, so the trailing window is in
   hand — this is a windowed pass, not new I/O.
3. **Warmup guard.** Match the strategy path: if the cleaned trailing window has
   `< percentile_window // 4` values, the date does **not** fire (safe default).
   This keeps the activation set identical-in-spirit to what the backtest will
   actually do, so the pre-filter estimate matches the gate's reality.

Net effect: `activation_dates` for a percentile config returns the dates where
the indicator sat in the requested tail of its own trailing distribution —
which is what the strategy path will trade on, so Forge's firing estimate lines
up with Crucible's backtest.

## Hard requirements (same as the strategy-path change)

- **Backward compatible / no-op on raw traffic.** No `use_percentile` ⇒
  byte-identical raw compare. The ~49k historical configs' activation sets are
  unchanged. Safe to deploy before Forge emits anything.
- **No lookahead.** Trailing window ends at the evaluated date.
- **Deterministic.** Pure function of the value series.
- **Consistency is the whole point.** The activation predicate here should match
  the strategy-path firing decision for the same `(spec, bars)` — ideally share
  `percentile_rank` (and, if practical, the same windowing helper) so the two
  paths cannot drift.

## Definition of done (and what to send back to Forge)

1. `compute_activation_dates` honors `use_percentile` (windowed percentile rank +
   warmup guard); `use_percentile`/`percentile_window` excluded from indicator
   params.
2. A test that a percentile config's `activation_dates` ≈ the dates the
   strategy-path signal fires for the same spec/bars (the two paths agree), plus
   a raw-config-unchanged regression.
3. Confirm to Forge: deployed (with the firing-summary/007 + `494cf96` bundle, or
   separately), commit hash, and that it is a verified no-op on raw
   `activation_dates` traffic. **Forge will not flip v6 emission until BOTH this
   and `494cf96` are confirmed live.**

---

**END OF PROMPT.**
