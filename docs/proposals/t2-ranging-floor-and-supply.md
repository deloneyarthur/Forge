# Proposal: T2 ranging-complement floor + mean_reversion (ranging) supply growth

> **STATUS (2026-06-24):** PARTIALLY LANDED. The ranging SUPPLY-growth half shipped: grammar v20 added the `hurst` mr R1 gate + biased the regime draw toward ranging [[D150]], and v21 enabled mr RANK [[D151]]; v22 added `rv_rank` [[D167]]. The T2 enforcement FLOOR itself remains un-shipped (gated on complement supply + the §8.6 criterion + F3). Historical record below.

Status: **SCOPING — awaiting operator sign-off on the supply lever (the grammar/enumeration change).**
Date: 2026-06-14. Greenlit by [[D148]] (`FORGE_greenlight_ranker_wiring_and_ranging.md`, operator-approved).
Ships *together* (Crucible: the floor alone only caps trend). Relates to [[D103]] (the existing
per-hypothesis submission floor), [[D107]] (the gamma_flip ranging gate), [[D144]] (`regime_supply`),
[[D116]] (mean_reversion can't rank — Crucible-gated), [[D149]] (F3 wiring, batches with this).

## Part A — the T2 ranging floor (ranking-side, no grammar)

**Honest finding: it is largely redundant with D103 today.** `D103 min_per_hypothesis=15` already
reserves `mean_reversion` 15/200 of the submitted batch, and the live `regime_supply:` line shows the
ranker already pulls ~all available ranging (≈15 selected vs a ~20–30 pool). So a *new* ranging floor
has **~5 configs of headroom** until supply grows — which is exactly why Crucible says ship it *with*
the supply growth.

**What's still worth building:** make the reservation **regime-bet-targeted**, not just
hypothesis-targeted — reserve for `mean_reversion` configs whose regime gate is a *ranging* gate
(`gamma_flip_distance_pct` op `<`, or `hurst` op `<` if Part B option 2 lands), not the sparse
`iv_rank` variant. This is a small diversifier change (a `ranging_floor` analogous to the D145/D103
machinery, keyed on the `regime_supply` ranging classification). It is **ranking-side, deterministic,
no grammar** — I'll TDD it freely. Its value scales with Part B; alone it's marginal.

## Part B — grow ranging supply (the dominant lever; needs operator sign-off)

**Mechanics (why ranging supply is thin):**
- `mean_reversion` is **single-name only** — it can't use the `cross_sectional_rank` breadth lever
  (D116/v14: its regime pool is single-name-only; re-admission is Crucible-gated, deferred).
- Its enumeration **share** is feedback-learned (~0.053) plus a uniform ~2% D037 floor (~100/5000).
  The weight is the feedback loop's to set (don't override); the floor is not mean_reversion-specific.
- Its R1 regime gate is picked **uniformly 50/50** between `iv_rank` (≤50) and `gamma_flip_distance_pct`
  (the ranging/long-gamma gate, D107) — `_pick_regime`, `sampler.py:824-830` (the D103 `regime_weights`
  tilt is scoped to `relative_value` only). **`iv_rank`-gated mean_reversion fires sparsely and dies at
  the prefilter** (the v6 expected_trades history); `gamma_flip`-gated is the ranging-paying, surviving
  variant. So **half of mean_reversion enumeration is routed to the gate that mostly dies.**

### Option 1 (RECOMMENDED) — bias mean_reversion's regime pick toward the ranging gate [sampler; versionless]
Route `mean_reversion`'s regime-gate pick toward `gamma_flip_distance_pct` (the ranging gate) instead
of 50/50 with the sparse `iv_rank`. Highest-leverage single change: it lifts the *effective* ranging
supply (more ranging-paying, prefilter-surviving mr reaching Crucible's gate) from the SAME enumeration
share — no new indicator, no grammar rule. **Not a `grammar.yaml` diff** — it's enumeration *policy*
(like the D103 `relative_value` tilt), so **no grammar_version bump**; but it changes the deterministic
enumeration sequence → operator-gated + a property-test baseline regen.

Exact diff (`src/forge/enumeration/sampler.py`):
```python
# new constants (near the relative_value regime constants ~_REGIME_CURATED_HYPOTHESIS):
_MR_HYPOTHESIS = "mean_reversion"
_MR_RANGING_GATE = "gamma_flip_distance_pct"   # D107 long-gamma/ranging R1 gate
_MR_RANGING_GATE_WEIGHT = 3.0                  # ~3:1 toward the ranging gate vs sparse iv_rank

# in _pick_regime(), before the final `return rng.choice(regimes)`:
    if hypothesis == _MR_HYPOTHESIS and len(regimes) > 1:
        weights = [_MR_RANGING_GATE_WEIGHT if r == _MR_RANGING_GATE else 1.0 for r in regimes]
        return rng.choices(regimes, weights=weights, k=1)[0]
```
`iv_rank` stays explorable (weight 1.0, not zeroed). Tunable knob (`_MR_RANGING_GATE_WEIGHT`).

### Option 2 — widen R1 with a third ranging gate: `hurst` op `<` [TRUE grammar.yaml diff; version bump]
Add `hurst` (op `<`, the mean-reverting side <0.5) to `mean_reversion`'s R1 regime pool. Thematically
ideal — **`hurst < 0.5` is the definition of a mean-reverting/ranging regime** — single-name-safe, and
it mirrors the gamma_flip/D107 precedent exactly (R2 already uses `hurst` op `>` for trend; this adds
the opposite side for mr). Additive (doesn't remove iv_rank); gives mr more ranging-admitting variety.
This **is** a §3.5 R1 rule change → the grammar-change ritual (`docs/tasks/grammar-change.md`):
`grammar_version` bump + `grammar.yaml` comment + `GRAMMAR.md` sync + archive + decision log.

Exact change set:
```python
# src/forge/grammar/custom_predicates.py — new constant + R1 acceptance (op "<", threshold < 0.5)
_R1_HURST_INDICATOR = "hurst"
_R1_HURST_MAX_THRESHOLD = 0.50
# (R1 predicate _r1_mean_reversion_requires_iv_rank_gate accepts a hurst gate with op "<" & thr < 0.5)

# src/forge/enumeration/search_space.py:341 — add hurst to the MR regime pool
pool[hyp] = tuple(sorted(
    {_R1_IV_RANK_INDICATOR, _R1_GAMMA_REGIME_INDICATOR, _R1_HURST_INDICATOR} & registry_ids))

# src/forge/enumeration/sampler.py:1111 — extend the MR op "<" switch to hurst (mean-reverting side)
if hypothesis == "mean_reversion" and regime_id in {"gamma_flip_distance_pct", "hurst"}:
    params["op"] = "<"

# src/forge/enumeration/indicator_thresholds.py — confirm hurst regime_range covers <0.5 (R2 entry exists, op ">")
# config/grammar.yaml — grammar_version v19 -> v20 + R1-hurst comment (the operator-owned byte change)
# docs/GRAMMAR.md — R1 narrative sync; config/grammar_archive/ — archive v19
```

## Recommendation / sequencing

1. **Build Part A (ranging floor, ranking-side) + Option 1 (sampler regime bias)** — together they
   grow *effective* ranging supply and give the floor more to reserve, with **no grammar_version bump**
   (versionless enumeration-policy + ranking change). Lightest path that satisfies Crucible's
   "ship the floor with supply."
2. **Option 2 (R1 `hurst` widening)** is the *true grammar.yaml diff* — take it if you want a
   version-bumped grammar change with more ranging-gate variety; it's additive and can land in the same
   restart, but it carries the full grammar ritual (version bump + GRAMMAR.md + archive + relay to
   Crucible, since grammar_version changes).

**Honest cap (hard rule 6, Crucible's framing):** none of this unlocks promotion — ranging
`mean_reversion`'s best-regime Sharpe (~0.62–0.65) is sub-grade. This is breadth/DD hygiene + giving
the (greenlit) ranking machinery a real ranging complement to work with.

## Decision needed
- **Option 1 only** (sampler bias, versionless) — recommended; or
- **Option 1 + Option 2** (also widen R1 with `hurst` — the version-bumped grammar change); or
- **Option 2 only** (grammar widening without the bias).

Part A (the ranking-side floor) builds regardless. Batches with D149 in one restart.
