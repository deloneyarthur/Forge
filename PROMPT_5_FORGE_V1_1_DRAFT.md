# Prompt 5 — Forge v1.1 Enhancements (DRAFT)

> **STATUS: DRAFT — NOT YET READY TO DISPATCH**
>
> This is a planning document, not a ready-to-paste prompt. It becomes a real prompt once the operator has run Forge batches and filled in the empirically-informed sections marked `[FILL IN AFTER BATCHES]`.
>
> Do NOT dispatch this prompt until:
> 1. Forge v1.0 has been running for at least 4 weeks
> 2. At least 5 batches have been processed by Crucible end-to-end
> 3. The operator has filled in the `[FILL IN AFTER BATCHES]` sections below
> 4. The operator has reviewed the data-dependent decisions
>
> See "Pre-dispatch checklist" at the end of this document.

---

## When to use this prompt

Use this prompt when Forge v1.0 is operational and you have observed enough batches to make informed decisions about which enhancements actually matter. The enhancements in this prompt are surgical additions to a running system, not greenfield work.

If Forge v1.0 is not yet running, this prompt is premature. Build and run v1.0 first. The data Forge produces is more valuable for sizing these enhancements than any pre-planning.

---

## Pre-dispatch checklist for the operator

Before dispatching this prompt, the operator should:

- [ ] Have seen at least 5 batches of Forge → Crucible results
- [ ] Have reviewed gate failure patterns: which gates reject most candidates?
- [ ] Have observed at least 5 promoted strategies (or have evidence that nothing promotes — also informative)
- [ ] Have decided whether the three new pre-filters address observed failure patterns or whether different filters are needed
- [ ] Have decided whether the two new hypotheses (`carry_harvest`, `flow_following`) map to gaps observed in the strategy library
- [ ] Have filled in all `[FILL IN AFTER BATCHES]` sections below
- [ ] Have confirmed Forge v1.0 is stable enough to modify (no active bugs in production)

If any checklist item is incomplete, the operator should pause and complete it first.

---

## To the implementing agent (when dispatched)

You are modifying Forge, the generator system in the Forge → Crucible → QuantIQ pipeline. Forge v1.0 is already built and running per `FORGE_DESIGN.md`.

This is a v1.1 enhancement — surgical additions to a running system. The constraints are:

- **Forge continues operating throughout your changes.** No interruption to batch processing.
- **Every change is independently revertible.** If one enhancement turns out to be wrong, the operator can revert just that change without touching others.
- **All existing tests continue to pass.** New tests are additive.
- **Backward compatibility for grammar archive.** Old grammar versions in `config/grammar_archive/` remain readable.

Before any code:

1. Read `PIPELINE.md` for system-of-systems context
2. Read `FORGE_DESIGN.md` for the v1 design you're extending
3. Read the operator's observations in the "Empirical context" section below
4. Confirm understanding by listing the seven enhancements and their target files

---

## Operating mode: lighter autonomy than v1 build

Since Forge is already running, you work in shorter iterations:

- Each enhancement is implemented as a separate commit with its own test additions
- After each enhancement, run the full existing test suite to verify no regressions
- Pause after each enhancement for operator confirmation that the change behaves as expected on the next batch
- No phase boundaries this time — the unit of review is the individual enhancement

Total estimated time: ~10-15 days at part-time, ~6-8 days full-time. Smaller than v1 because changes are surgical.

---

## Empirical context (operator fills in before dispatch)

The agent should understand what the operator has observed. Fill in these sections from real batch data.

### Observed gate failure distribution

Across the first N batches (N = `[FILL IN]`):

- `min_trade_count`: rejected `[FILL IN]%` of candidates
- `walk_forward_sharpe < 2.0`: rejected `[FILL IN]%`
- `walk_forward_max_dd > 15%`: rejected `[FILL IN]%`
- `cpcv_sharpe_p25 < 1.5`: rejected `[FILL IN]%`
- `pbo > 0.4`: rejected `[FILL IN]%`
- `deflated_sharpe < 0.95`: rejected `[FILL IN]%`
- `profit_factor < 1.4`: rejected `[FILL IN]%`
- `mc_permutation p > 0.05`: rejected `[FILL IN]%`
- `bootstrap_ci_lower < 0.5`: rejected `[FILL IN]%`
- `cross_ticker_robustness fails`: rejected `[FILL IN]%`
- `stability_over_time fails`: rejected `[FILL IN]%`
- `mc_regime_stress p25 < 0`: rejected `[FILL IN]%`
- `total_return < 1.5x SPY`: rejected `[FILL IN]%`
- `diagnostic_gate fails`: rejected `[FILL IN]%`
- `quality_bar fails`: rejected `[FILL IN]%`
- `delta_sharpe < 0.3`: rejected `[FILL IN]%`

### Observed promoted strategies

Across the first N batches, `[FILL IN]` strategies promoted.

Hypothesis breakdown of promoted strategies:
- `trend_continuation`: `[FILL IN]` promotions
- `mean_reversion`: `[FILL IN]` promotions
- `regime_arbitrage`: `[FILL IN]` promotions
- `relative_value`: `[FILL IN]` promotions
- `volatility_event`: `[FILL IN]` promotions
- `tail_hedge`: `[FILL IN]` promotions

Observed patterns in promoted strategies (operator fills in):

`[FILL IN — what do the promoted strategies have in common structurally? Which signal families dominate? Are there regimes with no promotions?]`

### Specific patterns the enhancements should address

`[FILL IN — based on the operator's analysis, what specific patterns do they want the enhancements to catch or enable?]`

---

## Enhancement 1: Trade concentration pre-filter

### What it does

Adds an eighth filter to the pre-filter battery. Rejects any candidate where the top 3 trades by P&L would constitute > N% of total P&L over the backtest.

### Why it's needed

Strategies whose entire backtest P&L comes from 2-3 outsized trades often pass all statistical gates yet fail live. The underlying market dynamic isn't repeatable; the gates can't detect this because the in-sample sample size is technically adequate even with concentrated returns.

### Configuration

- Default threshold: 40% (top 3 trades constitute < 40% of total P&L to pass)
- Configurable via `config/prefilter.yaml`
- Auto-tune disabled for this filter initially — operator adjusts based on observed effect

`[FILL IN AFTER BATCHES — does observed data suggest the 40% threshold is right? If many promoted strategies have concentration ratios near this threshold, consider tightening to 30%. If almost no candidates fail this filter, consider loosening to 50%.]`

### Implementation

New file: `src/forge/prefilters/trade_concentration.py`

```python
class TradeConcentrationFilter(Filter):
    """
    Rejects candidates where top-3 trades constitute too much of total P&L.

    Computed cheaply by sorting trade P&Ls; only needs the trade list which
    is already loaded for other filters.
    """

    def evaluate(self, candidate: StrategyConfig, context: FilterContext) -> FilterResult:
        trades = context.simulated_trades  # cached from prior filter passes
        if len(trades) < 4:
            return FilterResult(passed=False, reason="insufficient_trades")

        sorted_pnl = sorted([abs(t.pnl) for t in trades], reverse=True)
        total = sum(sorted_pnl)
        if total == 0:
            return FilterResult(passed=False, reason="zero_total_pnl")

        top_3_ratio = sum(sorted_pnl[:3]) / total
        passed = top_3_ratio < self.threshold
        return FilterResult(
            passed=passed,
            score=1.0 - top_3_ratio,  # higher is better
            details={"top_3_ratio": top_3_ratio, "threshold": self.threshold},
        )
```

Insert at filter position 5 in `config/prefilter.yaml` (between novelty and regime_exposure — moderate cost).

### Tests

- Unit: synthetic trade list with top-3 ratio > 40% → fails; ratio < 40% → passes
- Property: filter is monotonic in concentration (higher concentration → lower score)
- Edge cases: empty trade list, single trade, all zero P&Ls

### Backward compatibility

This is a strict additional filter — strategies that pass v1.0 may fail v1.1. The operator should expect promotion rate to drop by 5-15% after this filter is enabled. If the drop is larger than 30%, the threshold is too tight; loosen.

### Revert

Set `prefilter.trade_concentration.enabled: false` in config. Filter is skipped entirely.

---

## Enhancement 2: Signal correlation pre-filter

### What it does

For any candidate with 2+ signals, computes pairwise correlation of signal firing dates. Rejects if max pairwise correlation > 0.85.

### Why it's needed

The grammar's C1 rule blocks two indicators from the same family. But indicators from different families can still be empirically redundant (e.g., RSI and stochastic K compute similar things despite different families). This filter catches what C1 misses.

### Configuration

- Default threshold: 0.85
- Configurable via `config/prefilter.yaml`

### Implementation

New file: `src/forge/prefilters/signal_correlation.py`

```python
class SignalCorrelationFilter(Filter):
    """
    Rejects candidates with empirically redundant signals.

    Computed by loading each signal's historical firing dates (from
    Crucible's feature cache), then computing pairwise correlation.
    """

    def evaluate(self, candidate: StrategyConfig, context: FilterContext) -> FilterResult:
        if len(candidate.signals) < 2:
            return FilterResult(passed=True, score=1.0, details={"n_signals": 1})

        firing_series = [
            self._load_firing_series(signal, context.feature_cache_path)
            for signal in candidate.signals
        ]

        max_corr = 0.0
        for i in range(len(firing_series)):
            for j in range(i + 1, len(firing_series)):
                corr = self._pearson_on_binary(firing_series[i], firing_series[j])
                max_corr = max(max_corr, abs(corr))

        passed = max_corr < self.threshold
        return FilterResult(
            passed=passed,
            score=1.0 - max_corr,
            details={"max_correlation": max_corr, "threshold": self.threshold},
        )
```

Insert at filter position 4 in `config/prefilter.yaml` (after signal density, before novelty — needs signal firing dates, which are computed for density check anyway).

### Tests

- Unit: two identical signals → correlation 1.0 → fails
- Unit: two uncorrelated signals → correlation ~0 → passes
- Property: filter is symmetric (order of signals doesn't matter)
- Edge cases: signal with zero activations, signal with all-1 activations

### Backward compatibility

Strategies that pass v1.0 with redundant signals will start failing. Operator should expect some legitimate-seeming strategies to fail this filter. That's the intended behavior.

### Revert

Set `prefilter.signal_correlation.enabled: false` in config.

---

## Enhancement 3: Structural fingerprint novelty filter

### What it does

For each candidate, computes a hash of its `(hypothesis, signal_family_set, regime_gate_set, exit_set)` tuple. Rejects if fingerprint exactly matches a prior tested candidate's fingerprint (regardless of parameter differences).

### Why it's needed

The existing novelty filter uses Jaccard overlap on signal firing dates — temporal similarity. This misses structural similarity: two strategies that fire on different dates but encode the same idea. Optuna already explores parameter variations within a structure; we don't need Forge to redundantly enumerate them.

### Configuration

- Match mode: strict (exact fingerprint match) or fuzzy (overlap > 80%)
- Default: strict

`[FILL IN AFTER BATCHES — if Forge is producing many minor variations and the operator observes that promoted strategies' "neighbors" rarely also promote, fuzzy match is appropriate. If strategies in the same structural family but different parameters consistently produce diverse promotion outcomes, strict is correct.]`

### Implementation

Replace the existing novelty filter's logic OR add as a second-stage novelty check (operator decides):

```python
def _structural_fingerprint(config: StrategyConfig) -> str:
    components = {
        "hypothesis": config.hypothesis,
        "signal_families": sorted(set(s.family for s in config.signals)),
        "regime_gates": sorted(g.id for g in config.regime_gates),
        "exits": sorted(e.id for e in config.exits),
    }
    canonical = json.dumps(components, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

### Tests

- Unit: two configs with same fingerprint but different parameters → second is rejected
- Unit: two configs with different signal families → both pass novelty
- Property: fingerprint is stable across parameter changes
- Edge case: hypothesis-only difference (same signals, different hypothesis) — should be treated as distinct

### Backward compatibility

This filter is more aggressive than the existing novelty filter. Promotion rate will likely drop initially. Over time, Forge's enumeration should compensate by exploring more structural variety.

### Revert

Set `prefilter.novelty.use_structural_fingerprint: false` in config.

---

## Enhancement 4: `carry_harvest` hypothesis

### What it adds to the grammar

A new hypothesis option in §3.5: `carry_harvest`. Strategies that systematically collect risk premium from market structure rather than directional movement.

### Why it's needed

The v1 grammar covers directional strategies and event-driven strategies. It doesn't have a category for strategies whose thesis is "the market consistently overprices certain options; collect that premium." This is a real class of strategies (especially in long-options form: buying when implied < realized).

`[FILL IN AFTER BATCHES — has the operator observed strategies that look like carry harvest behavior in their existing trades? Is there a regime where current strategies systematically underperform that carry-harvest could fill?]`

### Grammar rule changes

Add to S1 hypothesis enum: `carry_harvest`

Add new S2 compatibility rule: if `hypothesis == carry_harvest`, directional signal must be from `iv_structure` or `volatility` family.

Add new S5 exit rule:
```yaml
- id: S5e
  if:
    field: hypothesis
    value: carry_harvest
  then:
    exits_require: [theta_cliff_exit, iv_normalization_exit]
    exits_forbid: [trailing_atr_exit]
```

The reasoning: carry harvest captures premium decay (theta) — trailing stops fight this; you exit when the premium has normalized or theta has reached the cliff.

### New exit rule needed

`iv_normalization_exit`: closes the position when IV has reverted to its mean (specifically: when IV rank crosses 50 from below). Implementation in `crucible/strategy/exits/iv_normalization.py` (note: this is a Crucible change, not Forge).

This requires coordination with the Crucible agent. If Crucible already has this exit, use it. If not, surface as an open question.

### Tests

- Grammar test: configs with `carry_harvest` hypothesis and trailing stop fail validation
- Grammar test: configs with `carry_harvest` hypothesis and required exits pass
- Enumeration test: enumerator produces `carry_harvest` configs at expected frequency

### Backward compatibility

Adding a new hypothesis to the enum is additive. Old configs without `carry_harvest` continue to validate. Grammar version bumps from N to N+1.

### Revert

Remove `carry_harvest` from S1 enum; remove the S2 and S5e rules; archive grammar version. All in one config commit.

---

## Enhancement 5: `flow_following` hypothesis

### What it adds to the grammar

A new hypothesis option in §3.5: `flow_following`. Strategies whose directional thesis is dealer positioning and order flow (long when dealers are short gamma; short when dealers are long gamma, etc.).

### Why it's needed

Crucible's design includes dealer positioning features (GEX, VEX, CEX). The v1 grammar can use them as confluence signals but doesn't have a hypothesis that centers on them. This adds explicit support.

`[FILL IN AFTER BATCHES — operator should verify that dealer positioning features in Crucible's registry are producing meaningful values. If GEX/VEX/CEX are computing correctly but rarely appearing in promoted strategies, this hypothesis is the right framing.]`

### Grammar rule changes

Add to S1 hypothesis enum: `flow_following`

Add new S2 compatibility rule: if `hypothesis == flow_following`, directional signal must be from `dealer_positioning` family.

Add new S5 exit rule:
```yaml
- id: S5f
  if:
    field: hypothesis
    value: flow_following
  then:
    exits_require: [flow_reversal_exit, theta_cliff_exit]
```

The reasoning: flow-following strategies exit when the flow regime flips, not on trailing price action.

### New exit rule needed

`flow_reversal_exit`: closes position when the dealer-positioning signal that drove the entry has reversed (specifically: GEX crosses zero in the opposite direction, or VEX changes sign). Coordinate with Crucible agent.

### Tests

- Grammar test: configs with `flow_following` and wrong directional family fail
- Grammar test: configs with `flow_following` and required exits pass
- Enumeration test: enumerator produces `flow_following` configs

### Backward compatibility

Same as Enhancement 4 — purely additive.

### Revert

Same as Enhancement 4.

---

## Enhancement 6: Confidence-weighted grammar proposals

### What it does

Adds a confidence score to every grammar refinement proposal based on the sample size that generated the proposal.

### Why it's needed

The current refiner (§8 of FORGE_DESIGN.md) proposes refinements based on aggregate statistics. A proposal backed by 5 rejected candidates is much weaker than one backed by 500. The operator should see this and prioritize accordingly.

### Implementation

In `src/forge/feedback/proposer.py`, the `GrammarProposal` dataclass gains a `confidence` field:

```python
@dataclass(frozen=True)
class GrammarProposal:
    proposal_id: UUID
    proposed_at: datetime
    proposal_type: Literal["tighten", "loosen", "add_rule", "remove_rule"]
    proposal_yaml: str
    rationale: str
    evidence: dict[str, Any]
    sample_size: int                    # NEW: how many candidates support this
    confidence: float                   # NEW: derived from sample_size (Wilson interval or similar)
    status: ProposalStatus
```

Confidence computation:

```python
def compute_confidence(sample_size: int, observed_rate: float) -> float:
    """
    Returns a confidence score in [0, 1] based on sample size and effect size.
    Uses Wilson interval lower bound to penalize small-sample proposals.
    """
    if sample_size < 20:
        return 0.1  # very low confidence
    elif sample_size < 100:
        return 0.3 + 0.4 * (sample_size - 20) / 80
    else:
        return min(1.0, 0.7 + 0.3 * (sample_size - 100) / 400)
```

Proposals with confidence < 0.5 are flagged as `low_confidence` in the operator's review interface; the operator can choose to wait for more data before accepting.

### Tests

- Unit: confidence is monotonic in sample size
- Unit: small samples produce low confidence regardless of effect size
- Integration: low-confidence proposals are not auto-applied even if they'd otherwise be auto-tightening

### Backward compatibility

Existing proposals in `grammar_proposals` table without a confidence value get treated as confidence = 0.5 (medium). Migration adds the column with this default.

### Revert

Set `feedback.proposals.use_confidence_weighting: false` in config. Confidence is computed but not displayed or used to gate auto-application.

---

## Enhancement 7: Reversibility for auto-tightening

### What it does

Every auto-tightening change includes a one-command revert path. Prior grammar version is always preserved; reversal is atomic.

### Why it's needed

Currently auto-tightening writes a new grammar version and archives the old. But there's no operator-facing tooling to revert if the tightening turns out to be wrong (e.g., promotion rate drops sharply). This adds explicit reversibility.

### Implementation

New CLI command:

```bash
forge grammar revert --to-version <prior_version>
```

The command:
1. Reads the prior version from `config/grammar_archive/`
2. Validates the prior version is well-formed
3. Writes it as the new current grammar (incrementing version, not deleting current)
4. Logs the revert action in `IMPLEMENTATION_DECISIONS.md`
5. Notifies via Slack if configured

Additionally, auto-tightening proposals now include an explicit "expected effect" — the proposer estimates how many candidates the tightening will reject. If actual rejections after applying are significantly higher than estimated (e.g., 2× more than expected), Forge surfaces a "consider revert" notification.

### Tests

- Unit: revert produces the prior grammar exactly
- Integration: auto-tightening that exceeds estimated effect triggers notification
- Integration: revert action is logged and survives restart

### Backward compatibility

Existing auto-tightenings without "expected effect" metadata get retroactive estimates (run the tightening against the prior batch to compute what would have been rejected).

### Revert

This is the revert mechanism; it doesn't itself have a revert. But the CLI command is safe — it's just writing a known-good prior grammar.

---

## Enhancement 8: Counterfactual evaluation for proposals

### What it does

Before applying an auto-tightening, evaluate: "what would have happened if this tightening had been applied to the previous batch?" If the tightening would have rejected strategies that actually promoted, the auto-tightening is NOT applied — it's surfaced as a high-priority operator review.

### Why it's needed

Auto-tightening is the most dangerous code in Forge. A bug or misjudgment here can corrupt the grammar over time. Counterfactual evaluation is a structural safeguard: tightenings that would harm what we want to find are rejected automatically.

### Implementation

In `src/forge/feedback/proposer.py`:

```python
def evaluate_counterfactual(proposal: GrammarProposal, prior_batches: list[BatchSummary]) -> CounterfactualResult:
    """
    Apply the proposed tightening to the configs in the prior batches.
    Compute how many promoted strategies would have been rejected.
    """
    promoted_strategies = [
        s for batch in prior_batches
        for s in batch.promoted_strategies
    ]

    would_be_rejected = [
        s for s in promoted_strategies
        if not validates_against_grammar(s, proposal.proposed_grammar)
    ]

    return CounterfactualResult(
        promoted_count=len(promoted_strategies),
        would_be_rejected_count=len(would_be_rejected),
        rejection_rate=len(would_be_rejected) / max(len(promoted_strategies), 1),
        would_be_rejected_ids=[s.run_id for s in would_be_rejected],
    )
```

Decision logic:

```python
def should_auto_apply_tightening(proposal: GrammarProposal) -> bool:
    counterfactual = evaluate_counterfactual(proposal, recent_batches(n=5))

    if counterfactual.rejection_rate > 0.0:
        # Tightening would reject at least one promoted strategy
        proposal.status = "operator_review_required"
        proposal.reason_for_review = f"Would reject {counterfactual.would_be_rejected_count} promoted strategies"
        return False

    if proposal.confidence < 0.7:
        # Low confidence; require operator approval
        proposal.status = "operator_review_required"
        return False

    return True  # Safe to auto-apply
```

### Tests

- Unit: tightening that would reject a promoted strategy is not auto-applied
- Unit: tightening with insufficient confidence is not auto-applied
- Integration: full flow from proposal generation to counterfactual to decision

### Backward compatibility

This is a new gate on auto-tightening. Existing tightening logic continues; new gate is applied on top. No migration needed.

### Revert

Set `feedback.auto_tighten.use_counterfactual_check: false` in config. Auto-tightening proceeds with v1.0 logic.

---

## Enhancement 9: Trend detection in repeated proposals

### What it does

If the same proposal type is generated and rejected (by operator or by counterfactual) across 3+ consecutive batches, escalate the proposal as "persistent signal" — present it to the operator with stronger urgency and a summary of why it keeps appearing.

### Why it's needed

Currently each proposal is treated independently. If the data keeps pointing to "rule X should be tightened" and we keep rejecting it, either:
- The operator should reconsider their rejection (the signal is consistent)
- There's a bug in proposal generation (it shouldn't keep proposing this)

Either way, the operator should know.

### Implementation

In `src/forge/feedback/proposer.py`, track proposal patterns across batches:

```python
def detect_persistent_proposals(recent_proposals: list[GrammarProposal]) -> list[PersistentProposal]:
    """
    Find proposal "themes" that have appeared in 3+ recent batches without being applied.
    """
    by_theme = defaultdict(list)
    for proposal in recent_proposals:
        theme = (proposal.proposal_type, proposal.target_rule_id)
        by_theme[theme].append(proposal)

    return [
        PersistentProposal(
            theme=theme,
            occurrences=props,
            consistency_score=compute_consistency(props),
            recommended_action="escalate_to_operator",
        )
        for theme, props in by_theme.items()
        if len(props) >= 3
    ]
```

Persistent proposals appear in `OPEN_PROPOSALS.md` with a `[PERSISTENT]` tag and a summary of how many times they've recurred.

### Tests

- Unit: 3 identical proposals across batches → persistent detection
- Unit: 2 proposals or non-identical proposals → no escalation
- Integration: persistent proposal is surfaced with all occurrences

### Backward compatibility

Additive. Doesn't change v1.0 behavior; only adds a new escalation path.

### Revert

Set `feedback.proposals.detect_persistent: false`.

---

## Implementation order

Recommended sequence (each commit independent):

1. **Enhancement 1** (trade concentration) — simplest, immediately useful
2. **Enhancement 7** (reversibility) — safety net for everything that follows
3. **Enhancement 6** (confidence-weighted) — affects how proposals look to operator
4. **Enhancement 8** (counterfactual) — depends on confidence and reversibility
5. **Enhancement 9** (persistent proposals) — builds on proposal infrastructure
6. **Enhancement 2** (signal correlation) — needs careful threshold tuning
7. **Enhancement 3** (structural fingerprint) — interacts with novelty filter
8. **Enhancement 4** (carry_harvest hypothesis) — requires Crucible coordination
9. **Enhancement 5** (flow_following hypothesis) — requires Crucible coordination

After each enhancement, run a full batch with the new feature enabled and verify behavior before proceeding to the next.

## Coordination notes

Enhancements 4 and 5 require the Crucible agent to add new exit rules (`iv_normalization_exit`, `flow_reversal_exit`). This is a separate work stream:

- Forge agent creates an issue requesting the new exits
- Crucible agent implements the exits in `crucible/strategy/exits/`
- Crucible agent updates the registry export so Forge sees the new exits
- Forge agent then completes Enhancements 4 and 5

If Crucible is unavailable for this work, Forge can implement Enhancements 1-3 and 6-9 immediately; 4-5 wait.

---

## Hard rules — do NOT relax

1. Every enhancement must be independently revertible via config or CLI
2. No enhancement breaks any existing v1.0 test
3. No enhancement changes the structure of Forge's DB tables without a working downgrade migration
4. The 25 v1 grammar rules continue to apply; additions only
5. No enhancement weakens Crucible's promotion gate or bypasses it
6. No LLM in production loop (same as v1)
7. All randomness through the existing seed module (same as v1)

---

## Decision log entries to add

To `forge/DECISIONS.md`:

- D-FORGE-001: Trade concentration filter added based on observed gate-pass-but-live-fail pattern in `[batch range]`
- D-FORGE-002: Signal correlation filter added to catch structural redundancy missed by family-based C1 rule
- D-FORGE-003: Structural fingerprint novelty added to reduce parameter-only variations in submissions
- D-FORGE-004: carry_harvest hypothesis added; rationale `[FILL IN based on observed gaps]`
- D-FORGE-005: flow_following hypothesis added; rationale `[FILL IN based on observed gaps]`
- D-FORGE-006: Confidence-weighted proposals added; auto-tightening now requires confidence > 0.7
- D-FORGE-007: Reversibility CLI added (`forge grammar revert`)
- D-FORGE-008: Counterfactual evaluation now gates all auto-tightenings
- D-FORGE-009: Persistent proposal detection escalates repeated rejected proposals

---

## Final operator checklist (before dispatch)

- [ ] All `[FILL IN AFTER BATCHES]` sections completed
- [ ] Empirical context section accurately reflects observed data
- [ ] Decision log placeholders updated with batch range and rationale
- [ ] Confirmed Crucible agent is available for Enhancements 4/5 coordination (or willing to defer those)
- [ ] Forge v1.0 is stable (no active bugs)
- [ ] Backup of current `forge.db` and `config/grammar.yaml` taken

When all checkboxes are filled, this draft becomes a deployable prompt. Paste with `PIPELINE.md` and `FORGE_DESIGN.md` attached.

---

**END OF DRAFT.**
