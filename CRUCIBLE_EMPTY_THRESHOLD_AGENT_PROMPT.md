# Forge empty-threshold leak

**Audience:** Forge-side agent.
**Repository:** `/home/aj/proj/Forge/`.
**Sibling context (read-only):** `/home/aj/proj/Crucible/`.
**Operator authorization:** 2026-05-15 — Crucible operator confirmed the bug from runs DB.

---

## 1. The bug

A ~2% slice of Forge-emitted `SignalSpec`s have `type="threshold"` but
no `threshold` key in `params`. Crucible's prefilter predicate
(`src/optbt/persistence/feature_cache.py:200`) and the runner-side
threshold evaluator both return `lambda _v: False` when the threshold
is missing — the signal can never fire. Strategies whose `directional`
signal is in this slice produce zero trades and gate-reject on
`min_oos_trade_count: value=0.0, threshold=30.0`.

**Evidence (Crucible runs DB, 2026-05-15, n=100 sampled runs):**

| Role | Type | has_threshold | Count |
|---|---|---|---|
| directional | threshold | True | 98 |
| directional | threshold | **False** | **2** |
| regime_filter | threshold | True | 99 |
| regime_filter | threshold | **False** | **1** |
| confluence | passthrough | False | 38 (correct — passthrough doesn't need threshold) |

Confluence/passthrough is fine — `_build_predicate` returns
`lambda v: v != 0.0` for that type. The bug is specifically:
`type="threshold"` AND `threshold` absent from `params`.

## 2. Where to look in Forge

The enumerator emits `SignalSpec` instances at
`src/forge/enumeration/sampler.py` (the `sig_directional` / `sig_regime`
specs Crucible saw both originate there). Grep for the construction
sites that build `SignalSpec(type="threshold", ...)`. The leak is
almost certainly a code path where a `threshold` param is sampled
conditionally and the fallback branch forgets to set it.

The `indicator-aware threshold sampling` work (commit `846a850`)
restructured this — check whether the new sampling path covers every
indicator that role=directional or role=regime_filter can emit, or
whether a few indicators fall through to a "no threshold" default.

## 3. The fix

Two acceptable shapes:

1. **Belt-and-suspenders on emit:** at `SignalSpec` construction,
   assert `type == "threshold"` implies `"threshold" in params`. Raise
   loudly. Then track down the call site that violates it.
2. **Sampler audit:** ensure every directional/regime_filter
   indicator in the registry has a threshold-sampling rule. Confluence
   uses passthrough, so it's not affected.

Either way, add a unit test that constructs a `StrategyConfig` and
fails if any threshold-typed signal is missing its threshold param.
That test should be in Forge's enumeration tests, not Crucible.

## 4. Out of scope (Crucible is handling these)

- **`period_start = period_end` (1-day backtest):** This is a
  Crucible-side bug in `runs_repository.queue_run`. Forge does not
  send period fields, and Crucible's default short-circuited the
  runner's trailing-90-day default. Crucible operator is shipping the
  fix; you do **not** need to add period fields to the contract.
- **The 100% reject rate on existing runs:** Pre-fix, every run had
  a 1-day backtest period → 0 trades → reject on `min_oos_trade_count`.
  Once the Crucible period fix lands and the empty-threshold leak is
  closed, the reject rate should drop from 100% to whatever the gates
  honestly produce.

## 5. Acceptance

This is done when:

1. A new Forge unit test fails before your fix and passes after,
   constructing a Forge-sampled config and asserting no threshold-typed
   signal has `"threshold" not in params`.
2. Forge restarts cleanly, submits a batch, and Crucible's
   `promotion_decisions.gate_results_json` shows `min_oos_trade_count`
   passing (or at least `signal_value > 0`) for at least one run in
   the batch — confirming signals actually fire.
3. Don't push the branch; operator pushes manually.

## 6. References

- Crucible's threshold predicate: `src/optbt/persistence/feature_cache.py:196-222`
- The signal contract: `crucible_contracts/src/crucible_contracts/models.py` (`SignalSpec`)
- Sampling work that may be relevant: Forge commit `846a850`
  (indicator-aware threshold sampling)
- Crucible's period fix: tracked separately under
  `runs_repository.queue_run` (operator-authored)

Build slowly. Test ruthlessly. One unit test in the enumerator is the ground truth.
