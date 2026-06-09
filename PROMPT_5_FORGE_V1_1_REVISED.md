# Prompt 5 v2 — Forge v1.1 Enhancements (Revised)

> **STATUS: READY TO DISPATCH**
>
> This prompt supersedes the earlier `PROMPT_5_FORGE_V1_1_DRAFT.md`. It has been revised to integrate findings from the strategy translation corpus (`GRAMMAR_V2_PRIORITIES.md`) which surfaced silent-failure modes in Forge's grammar that should be fixed before adding new hypotheses.
>
> **Dispatch with**: `PIPELINE.md`, `FORGE_DESIGN.md`, `GRAMMAR_V2_PRIORITIES.md`, and the original `PROMPT_5_FORGE_V1_1_DRAFT.md` (for context on what changed).

---

## Why this revision

Between the draft and now, an empirical translation corpus surfaced **silent failure modes** — grammar configurations that pass validation, pass pre-filters, reach Crucible, and produce zero trades for diagnosable but invisible reasons. Three specific instances:

1. Threshold signals with `op="<"` don't infer LONG_PUT direction (silently produces zero trades)
2. Continuous directional signals (e.g., golden cross holding true for years) don't trigger entries because the template is level-triggered, not edge-triggered
3. `days_to_earnings` returns sentinel value 999 on ETFs (no earnings exist), making vol_event hypothesis effectively unusable on Tier 1

These are not theoretical concerns. They were observed in real translation attempts from production strategies.

**Key insight**: adding new hypotheses (`carry_harvest`, `flow_following`) on top of a grammar with silent-failure bugs just creates more configs that fail silently. The silent-failure fixes must ship first.

This revision reorders the enhancement set accordingly:
- **Tier 1 (silent-failure fixes)**: address the bugs that waste Forge batches before they bite again
- **Tier 2 (operational hardening)**: safety nets for the self-learning loop (mostly unchanged from draft)
- **Tier 3 (expressive expansion)**: new hypotheses (`carry_harvest`, `flow_following`), gated behind Tier 1 completion

---

## Operating mode

Forge is already running. This is a v1.1 enhancement — surgical additions to a live system. Same constraints as the draft prompt:

- Forge continues operating throughout your changes
- Every change is independently revertible
- All existing tests continue to pass
- Backward compatibility for grammar archive

Total estimated time: ~14-18 days at part-time, ~8-10 days full-time.

**Cross-system coordination**: Tier 1 enhancement P3 (ETF-aware event gates) and the predicted_activations filter require coordination with the Crucible agent. The exit-stub fix and macro-event indicators they need are in a separate prompt (`PROMPT_6_CRUCIBLE_EXIT_STUBS.md`). Coordinate timing: Crucible's Prompt 6 work should land before your work on P3.

---

## Empirical context

Per the operator's confirmation: Forge has run "decently" but not extensively. The translation corpus is the strongest empirical input we have so far. Treat its findings as authoritative for what's broken; treat per-batch promotion-rate data as preliminary.

Specifically:
- 5 strategies translated through Crucible's runner-minimal gauntlet
- 2 of 5 produced positive single-period signal (textbook long-call breakout, PraiseTheSun trend+pullback variant)
- 3 of 5 produced 0 trades for diagnosable grammar reasons (the P1/P2/P3 cases)
- 4 textbook strategies excluded because they require multi-leg vehicles (out of v1 scope)

Operator has committed to a **no-tweak period on gate thresholds**. This work does not adjust any Crucible gate; all changes are upstream of Crucible's validation.

---

## Tier 1: Silent-failure fixes (HIGHEST PRIORITY)

These are bug fixes for failure modes the corpus surfaced. Without these, Forge will continue wasting batches on configs that can't possibly produce trades.

### Enhancement T1.1: Bidirectional threshold signal inference

**Source**: GRAMMAR_V2_PRIORITIES §4.1 G1, §5.1 P1

**The problem**:
A SignalSpec like `threshold(indicators=("donchian",), params={"op": "<", "threshold": 0})` is syntactically valid and should infer LONG_PUT direction. Today, the `composable_long_options` template's direction inference is single-axis (positive vote → LONG_CALL). This means `op="<"` configs silently produce zero trades.

This blocks ~50% of directional taxonomy. Every short-side strategy (breakdown plays, put strategies on weakness, regime-flip puts) is unrepresentable in practice.

**The fix**:

Add an explicit `direction` field to SignalSpec:

```python
class SignalSpec(BaseModel):
    role: Literal["directional", "regime_filter", "confluence"]
    type: Literal["threshold", "rank", "event"]
    indicators: tuple[str, ...]
    params: dict[str, Any]
    direction: Literal["long_call", "long_put", "inferred"] = "inferred"
```

When `direction="inferred"`, the template uses existing inference logic.
When `direction="long_call"` or `direction="long_put"`, the template uses that direction explicitly, ignoring inference.

Grammar rule update: add to S2 (directional signal compatibility):
> If `direction="inferred"` and `op="<"` (or analogous "low" semantic), the inference must map to LONG_PUT. Implementation in `composable_long_options.signals.threshold.infer_direction()`.

**Tests**:

- Unit: `SignalSpec(direction="long_put", ...)` produces only LONG_PUT entries regardless of threshold direction
- Unit: `SignalSpec(direction="inferred", op=">", ...)` produces LONG_CALL entries
- Unit: `SignalSpec(direction="inferred", op="<", ...)` produces LONG_PUT entries (THIS IS THE NEW BEHAVIOR)
- Integration: re-run `textbook_long_put_breakdown` from the corpus; assert n_trades > 0
- Invariant: `tests/invariants/test_direction_inference.py` — for any indicator with both `op=">"` and `op="<"` thresholdable on it, both should produce non-zero trades on appropriate underlying

**Backward compatibility**: existing configs without `direction` field default to `"inferred"` — same behavior as today for LONG_CALL configs, fixed behavior for LONG_PUT configs.

**Revert**: feature-flag in `config/template.yaml`: `composable_long_options.bidirectional_inference: false` falls back to single-axis behavior.

---

### Enhancement T1.2: Edge-triggered vs level-triggered entry cadence

**Source**: GRAMMAR_V2_PRIORITIES §4.1 G2, §5.1 P2

**The problem**:
Continuous true signals (e.g., golden cross holding true for years) silently produce 0 trades because the template doesn't re-enter while a position is open AND doesn't re-trigger on continuously-true signals. A Forge batch enumerating golden-cross-like configurations would produce zero useful results with no actionable diagnostic.

**The fix**:

Add an `entry_cadence` field on directional SignalSpec:

```python
class SignalSpec(BaseModel):
    # ... existing fields ...
    entry_cadence: Literal["on_edge", "on_each_bar", "periodic_N_bars"] = "on_edge"
    cadence_period_bars: Optional[int] = None  # required if entry_cadence == "periodic_N_bars"
```

Semantics:
- `on_edge` (default): fires only when the signal transitions from false to true. Suitable for crossover signals, threshold breaks, regime changes.
- `on_each_bar`: fires whenever the signal is true (and no open position exists for the strategy). Suitable for always-on / insurance-style strategies, persistent-condition strategies.
- `periodic_N_bars`: fires every N bars while the signal is true. Suitable for systematic re-entry strategies (e.g., DCA-style).

Update `composable_long_options.evaluate_entry()` to respect this field.

**Tests**:

- Unit: continuously-true signal with `entry_cadence="on_edge"` produces 1 trade (initial entry only)
- Unit: same signal with `entry_cadence="on_each_bar"` produces N trades (one per bar while true, gated by open-position-state)
- Integration: re-run `praisethesun_golden_cross` from the corpus with `entry_cadence="on_each_bar"`; assert n_trades > 0
- Property: `on_edge` semantics match the existing template behavior exactly for legacy configs (backward compatibility)

**Backward compatibility**: default value `"on_edge"` matches existing behavior. Existing configs unaffected.

**Revert**: feature-flag: `composable_long_options.entry_cadence_support: false` falls back to existing always-edge-triggered logic.

---

### Enhancement T1.3: Predicted-activations pre-filter

**Source**: GRAMMAR_V2_PRIORITIES open question §7.2, generalized

**The problem**:
The corpus surfaced three specific cases of "syntactically valid, semantically inert" configs. There are likely more we haven't catalogued. The general failure mode: a config passes the existing 7 pre-filters but produces 0 trades during the full backtest because the signal never fires on the chosen underlying.

This wastes compute. A full backtest costs ~1-2 hours of compute; a config that produces 0 trades has wasted that compute, contributes no learning, and slips through pre-filtering.

**The fix**:

Add an eighth pre-filter: **predicted_activations**. Estimates how many trade entries a config would fire across the backtest period, *before* running the full backtest.

Implementation:

```python
class PredictedActivationsFilter(Filter):
    """
    Estimates n_entries by counting signal firings on cached historical data.

    For each directional signal in the config:
      1. Load its historical values from the feature cache
      2. Apply the threshold (respecting op, direction, entry_cadence)
      3. Count firings (edge-triggered) or true-bars (level-triggered)
      4. Intersect with regime gates (logical AND)
      5. Reject if expected n_entries < threshold (default: 10)
    """
    def evaluate(self, candidate: StrategyConfig, context: FilterContext) -> FilterResult:
        directional_signals = [s for s in candidate.signals if s.role == "directional"]
        regime_gates = [s for s in candidate.signals if s.role == "regime_filter"]

        # Load cached signal firings
        directional_firings = self._load_firings(directional_signals[0], context)
        regime_active = self._load_regime_mask(regime_gates, context)

        # Intersect
        combined_firings = directional_firings & regime_active

        # Apply entry_cadence semantics
        if directional_signals[0].entry_cadence == "on_edge":
            n_entries = self._count_edges(combined_firings)
        elif directional_signals[0].entry_cadence == "on_each_bar":
            n_entries = combined_firings.sum()
        else:
            n_entries = self._count_periodic(combined_firings, directional_signals[0].cadence_period_bars)

        passed = n_entries >= self.threshold
        return FilterResult(
            passed=passed,
            score=min(1.0, n_entries / (self.threshold * 5)),
            details={"predicted_n_entries": int(n_entries), "threshold": self.threshold},
        )
```

Insert at filter position 4 in `config/prefilter.yaml` (after signal density, before novelty). Default threshold: 10 expected entries.

**Tests**:

- Unit: config with high-frequency firing signal → passes (high predicted entries)
- Unit: config with rare-firing signal (e.g., 3 firings in 7 years) → fails
- Unit: ETF + `days_to_earnings` regime gate → predicted entries = 0, fails
- Unit: `op="<"` config with `direction="long_put"` correctly counts entries (no LONG_CALL/LONG_PUT confusion)
- Integration: re-run all three corpus failure cases; all three should be rejected by this filter rather than reaching Crucible

**Critical**: this filter must respect the changes in T1.1 (direction field) and T1.2 (entry_cadence field). Implement T1.1 and T1.2 first, then T1.3.

**Backward compatibility**: new filter, additive. Existing configs that would have passed Crucible may now be rejected at pre-filter — this is the intended behavior (they would have produced 0 trades anyway).

**Revert**: set `prefilter.predicted_activations.enabled: false`.

---

### Enhancement T1.4: ETF-aware event regime gates

**Source**: GRAMMAR_V2_PRIORITIES §4.1 G3, §5.1 P3

**The problem**:
`days_to_earnings` returns sentinel value 999 for ETFs (no earnings exist). A vol_event config with `days_to_earnings <= 3` regime gate produces 0 trades on Tier 1 (SPY, QQQ, IWM, DIA) silently.

The agent's recommendation offers two fixes; we adopt the broader one:

**The fix**:

Adopt option (b): add ETF-applicable event indicators and require vol_event configs to use an event indicator valid for the chosen underlying.

Required changes:

1. **Coordinate with Crucible agent** (`PROMPT_6_CRUCIBLE_EXIT_STUBS.md`) to add three new event indicators to the registry:
   - `days_to_cpi` — distance to next CPI release
   - `days_to_nfp` — distance to next Nonfarm Payrolls release
   - `days_to_opex` — distance to next monthly options expiration (3rd Friday)

2. Update grammar rule R3 (regime coherence) in `config/grammar.yaml`:

```yaml
- id: R3
  category: regime_coherence
  predicate:
    type: requires_with_compatibility
    if:
      field: hypothesis
      value: volatility_event
    then:
      field: signals.regime_filter.indicator
      one_of: [days_to_earnings, days_to_fomc, days_to_cpi, days_to_nfp, days_to_opex]
      compatibility:
        - underlying_type: single_name
          allowed: [days_to_earnings, days_to_fomc, days_to_cpi, days_to_nfp, days_to_opex]
        - underlying_type: etf
          allowed: [days_to_fomc, days_to_cpi, days_to_nfp, days_to_opex]
        - underlying_type: index
          allowed: [days_to_fomc, days_to_cpi, days_to_nfp, days_to_opex]
```

3. Update the universe queue-time preflight (per `runs_repository.queue_run`) to reject vol_event configs whose event indicator is incompatible with the chosen underlying type. Coordinate with Crucible agent — this preflight lives in Crucible.

**Tests**:

- Unit: vol_event config with `days_to_earnings` on SPY → rejected at grammar validation
- Unit: vol_event config with `days_to_fomc` on SPY → passes grammar validation
- Integration: re-run `textbook_iv_crush_earnings` from the corpus with `days_to_fomc` instead of `days_to_earnings`; assert n_trades > 0
- Invariant: `tests/invariants/test_vol_event_universe_compatibility.py` — for every supported underlying type, asserts that at least one vol_event config can be constructed that passes grammar validation

**Backward compatibility**: existing vol_event configs with `days_to_earnings` on single-names continue to work. Existing configs with `days_to_earnings` on ETFs (if any) would now be rejected — this is correct, they would have produced 0 trades.

**Revert**: feature-flag in `config/grammar.yaml`: `rules.R3.strict_compatibility: false` allows incompatible combinations (legacy behavior).

---

## Tier 2: Operational hardening (UNCHANGED FROM DRAFT)

These are the safety-net enhancements from the original draft. They make the self-learning loop safer to operate autonomously. Implement after Tier 1.

### Enhancement T2.1: Confidence-weighted grammar proposals

**Unchanged from draft Enhancement 6.** See draft for full spec.

**Why still needed**: as silent-failure cases get fixed in Tier 1, the grammar refiner will start seeing different patterns in batch results. Confidence weighting prevents low-sample-size early proposals from being acted on.

---

### Enhancement T2.2: Reversibility for auto-tightening

**Unchanged from draft Enhancement 7.** See draft for full spec.

**Why still needed**: even after Tier 1, auto-tightening can be wrong. Reversibility is the safety net.

---

### Enhancement T2.3: Counterfactual evaluation for proposals

**Unchanged from draft Enhancement 8.** See draft for full spec.

**Why still needed**: with the Tier 1 fixes, more candidates will produce signal, which means more candidates will promote, which means counterfactual evaluation has more data to work with. This makes counterfactual checks more reliable.

---

### Enhancement T2.4: Persistent proposal detection

**Unchanged from draft Enhancement 9.** See draft for full spec.

---

### Enhancement T2.5: Trade concentration pre-filter

**Unchanged from draft Enhancement 1.** See draft for full spec.

**Position in pre-filter battery**: insert at position 6 (after predicted_activations, before signal_correlation).

---

### Enhancement T2.6: Signal correlation pre-filter

**Unchanged from draft Enhancement 2.** See draft for full spec.

**Position in pre-filter battery**: insert at position 7.

---

### Enhancement T2.7: Structural fingerprint novelty

**Unchanged from draft Enhancement 3.** See draft for full spec.

**Position in pre-filter battery**: modify existing novelty filter at position 5 to use structural fingerprint as additional check.

---

## Tier 3: Expressive expansion (DEFERRED BEHIND TIER 1)

These add new hypothesis types. **Do not start Tier 3 until Tier 1 is complete and verified.** New hypotheses on top of silent-failure bugs amplify the bugs.

### Enhancement T3.1: `carry_harvest` hypothesis

**Largely unchanged from draft Enhancement 4** with one important update:

The `iv_normalization_exit` referenced in the draft is being implemented by the Crucible agent in `PROMPT_6_CRUCIBLE_EXIT_STUBS.md`. Coordinate timing: do not implement T3.1 until Crucible confirms `iv_normalization_exit` is functional (not a stub).

Additionally: `carry_harvest` should support both LONG_CALL and LONG_PUT direction (relevant when buying calls during periods of cheap call IV vs buying puts during periods of cheap put IV). The S2 compatibility rule must allow either direction. This requires T1.1 (bidirectional inference) to be in place first.

---

### Enhancement T3.2: `flow_following` hypothesis

**Largely unchanged from draft Enhancement 5** with same coordination requirements:

- `flow_reversal_exit` is being implemented in `PROMPT_6_CRUCIBLE_EXIT_STUBS.md`. Wait for confirmation before implementing T3.2.
- `flow_following` strategies frequently use continuous signals (dealer positioning rarely transitions cleanly). Default `entry_cadence` should be `on_each_bar`, not `on_edge`. Requires T1.2 to be in place.

---

## Implementation order

Recommended sequence, with explicit dependencies:

**Wave 1 (silent-failure fixes, can run in parallel):**
- T1.1 (bidirectional threshold inference) — no dependencies
- T1.2 (entry cadence) — no dependencies

**Wave 2 (depends on Wave 1):**
- T1.3 (predicted_activations filter) — requires T1.1 and T1.2 to compute correctly
- T1.4 (ETF-aware event gates) — requires Crucible Prompt 6 to land first (new indicators)

**Wave 3 (operational hardening, can run after Wave 2 or in parallel with Wave 4):**
- T2.1 - T2.7 — independent of Wave 4

**Wave 4 (expressive expansion, must wait for Wave 1-2):**
- T3.1 (carry_harvest) — requires T1.1, Crucible Prompt 6 (iv_normalization_exit)
- T3.2 (flow_following) — requires T1.2, Crucible Prompt 6 (flow_reversal_exit)

Total wall time: ~14-18 days at part-time. Wave 1 is fastest (no dependencies); Wave 4 must wait for Crucible coordination.

---

## Hard rules — do NOT relax

1. Tier 1 ships before Tier 3. Silent-failure fixes are blockers.
2. Every enhancement independently revertible via config flag or CLI.
3. No enhancement breaks any existing v1.0 test.
4. No enhancement weakens Crucible's promotion gate or bypasses pre-filters.
5. No new dependencies without strong justification.
6. The 25 v1 grammar rules continue to apply; modifications only as specified above.
7. Cross-system changes (T1.4, T3.1, T3.2 indicators/exits) require Crucible Prompt 6 to ship first.

---

## Decision log entries to add

To `forge/DECISIONS.md`:

- D-FORGE-001: Bidirectional threshold inference added; fixes silent zero-trade outcome for short-side strategies
- D-FORGE-002: Entry cadence (on_edge / on_each_bar / periodic_N_bars) added; fixes silent zero-trade outcome for continuous signals
- D-FORGE-003: Predicted activations pre-filter added; catches silently-inert configs before expensive backtest
- D-FORGE-004: ETF-aware event regime gates; vol_event hypothesis now usable on Tier 1 (with macro-event indicators)
- D-FORGE-005: Confidence-weighted proposals added
- D-FORGE-006: Reversibility CLI added (`forge grammar revert`)
- D-FORGE-007: Counterfactual evaluation for auto-tightening
- D-FORGE-008: Persistent proposal detection
- D-FORGE-009: Trade concentration pre-filter
- D-FORGE-010: Signal correlation pre-filter
- D-FORGE-011: Structural fingerprint novelty
- D-FORGE-012: `carry_harvest` hypothesis added (requires Crucible Prompt 6)
- D-FORGE-013: `flow_following` hypothesis added (requires Crucible Prompt 6)

---

## Coordination notes for the agent

### What's in your scope

- All grammar changes (`config/grammar.yaml`, `docs/GRAMMAR.md`)
- All pre-filter additions and ordering
- Template updates (`composable_long_options` direction inference and cadence handling)
- Self-learning improvements (proposer, refiner, reversibility CLI)
- Tests (unit, integration, invariant, property)

### What's NOT in your scope (Crucible agent's work via Prompt 6)

- New event indicators (`days_to_cpi`, `days_to_nfp`, `days_to_opex`) — Crucible side
- Functional implementations of `iv_crush_exit`, `event_passed_exit`, `iv_normalization_exit`, `flow_reversal_exit` — Crucible side
- Queue-time preflight in `runs_repository.queue_run` — Crucible side

### Coordination points

- Before starting T1.4: confirm Crucible Prompt 6 has shipped the new event indicators
- Before starting T3.1: confirm `iv_normalization_exit` is functional
- Before starting T3.2: confirm `flow_reversal_exit` is functional
- If any Crucible indicator is named differently than expected: update grammar references in T1.4

If Crucible Prompt 6 is delayed, you can ship Tier 1.1, 1.2, 1.3, and all of Tier 2 without waiting. T1.4, T3.1, T3.2 wait.

---

## Pre-dispatch checklist for the operator

- [ ] Confirmed Forge v1.0 is stable (no active bugs)
- [ ] Backup of current `forge.db` and `config/grammar.yaml` taken
- [ ] Crucible Prompt 6 dispatched (or its work confirmed scheduled) — for T1.4, T3.1, T3.2
- [ ] No-tweak-gate-thresholds commitment is recorded and the agent knows not to suggest gate changes
- [ ] Agent has been provided this prompt, `PIPELINE.md`, `FORGE_DESIGN.md`, `GRAMMAR_V2_PRIORITIES.md`

---

**END OF PROMPT 5 v2.**
