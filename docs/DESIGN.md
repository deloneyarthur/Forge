# Forge — Design Specification

**Version:** 1.0
**Audience:** Implementing engineer or AI coding agent
**Status:** Authoritative design for v1
**Last updated:** 2026-05-13

---

## 0. How to read this document

Forge is the **generator** in the Forge → Crucible → QuantIQ pipeline. Before reading this document:

1. Read `PIPELINE.md` for the system-of-systems context
2. Have access to `crucible/DESIGN.md` for Crucible's interfaces (especially §11, §13, §25)
3. Have access to `crucible_contracts/` source for the data models you'll consume

Forge's job is **narrow**: produce candidate strategy configurations that respect a hypothesis grammar, cheaply pre-filter them, submit survivors to Crucible. It does not backtest. It does not validate. It learns from Crucible's promotion decisions and refines its grammar over time.

When in doubt, defer to Crucible. Forge is the producer; Crucible is the authority on quality.

---

## 1. Project overview

### 1.1 What Forge does

Generates YAML strategy configurations that Crucible can backtest. Each config describes a long-options trading strategy: signals, parameters, exit stacks, regime gates, sizer settings. Forge's output is the *input* to Crucible.

### 1.2 What Forge does NOT do

- Backtest strategies (Crucible's job)
- Compute Sharpe, drawdown, or any strategy metric (Crucible's job)
- Generate new indicator implementations or signal logic (out of v1 scope; see §11.5)
- Use LLMs as autonomous agents in the production generation loop
- Operate on equity strategies (Crucible is long-options only; equity stays in QuantIQ)
- Make operational decisions (lifecycle, capital allocation, kill switches — QuantIQ's job)

### 1.3 Honest expectations

The early weeks of Forge will feel useless. Promotion rates will start near zero. The grammar will be wrong in subtle ways. Most candidates will be junk.

By month 3-6, Forge should reach 1-3% promotion rate (1-3 of every 100 submitted candidates pass Crucible's gate). By month 6-12, the rate may climb to 3-5%. This is success. Anything significantly above 5% promotion rate is **suspicious** — likely indicates the grammar has been over-tuned to match Crucible's gate, which is its own form of overfitting.

### 1.4 Hardware

Forge runs on the same workstation as Crucible. 12-core / 12 GB RAM. Forge's compute is light (combinatorial enumeration is cheap; pre-filters are cheap). Most of the pipeline's compute is Crucible.

Forge does not run in parallel with itself — single-process is sufficient. It does run in parallel with Crucible: while Crucible is processing a batch, Forge is enumerating the next batch.

---

## 2. Architecture

### 2.1 Five-component architecture

```
┌────────────────────────────────────────────────────┐
│ Hypothesis Grammar (GRAMMAR.md + grammar.yaml)     │
│ - Human-readable rules                             │
│ - Machine-checkable predicates                     │
│ - Versioned, refined via supervised loosening      │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ Component 1: Enumerator                            │
│ - Walks grammar-valid combinations                 │
│ - Produces 10K-100K candidate configs per batch    │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ Component 2: Pre-filter Battery                    │
│ - Signal density check                             │
│ - Novelty check (vs prior tested configs)          │
│ - Expected trade count                             │
│ - Permutation test for signal information          │
│ - Regime exposure check                            │
│ - Structural redundancy check                      │
│ - Resource feasibility check                       │
└────────────────────┬───────────────────────────────┘
                     │ (rejects ~90% of candidates)
                     ▼
┌────────────────────────────────────────────────────┐
│ Component 3: Ranker & Queue                        │
│ - Composite pre-filter score                       │
│ - Diversification penalty (avoid clustering)       │
│ - Top-N selection for submission                   │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ Component 4: Submitter                             │
│ - Writes YAML to Crucible's inbox                  │
│ - Rate-limits submission to match Crucible's       │
│   throughput                                       │
│ - Tracks submission state                          │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
        (Crucible processes; results in DB)
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ Component 5: Feedback & Grammar Refiner            │
│ - Reads Crucible's gated runs (read-only)          │
│ - Updates pre-filter weights and ranker priors     │
│ - Proposes grammar refinements                     │
│ - Auto-applies tightening; surfaces loosening      │
└────────────────────────────────────────────────────┘
```

### 2.2 Design principles

1. **Forge is stateless except for the grammar and learnings DB.** Restarts are safe; no in-memory state needs to be persisted across sessions.
2. **The grammar is the conceptual heart of Forge.** Every decision flows from it. Treat grammar changes with surgical care.
3. **Cheap filters before expensive ones.** Pre-filters are ordered by cost. The cheapest one runs first; candidates are rejected as early as possible.
4. **Forge never touches Crucible's internals.** All access via `crucible_contracts`.
5. **Auto-tightening is safe; auto-loosening is not.** The grammar refiner can automatically add rules (which reduce candidates) but never remove rules (which expand candidates) without supervised approval.
6. **Diversity over depth.** A batch of 200 candidates spread across 20 hypothesis families beats 200 variations of one family.
7. **Forge optimizes for promotion rate AND coverage.** If promotion rate is high but all promoted strategies are in one regime, Forge is under-exploring. Both metrics matter.

### 2.3 Technology stack

Same as Crucible where applicable:
- Python 3.12, `from __future__ import annotations`
- Polars ≥ 1.0, Pydantic ≥ 2.7, DuckDB ≥ 1.0
- `crucible_contracts` package
- Ruff strict + mypy strict
- Hypothesis for property tests
- pytest for unit and integration tests
- `uv` for environment management

Forge-specific:
- `pyyaml` for grammar file parsing
- `networkx` for grammar dependency analysis (rule → rule constraints)

No LLM dependencies. No GPU. No additional data sources beyond what Crucible already provides.

---

## 3. The hypothesis grammar

The grammar is the single most important artifact in Forge. This section defines its structure, semantics, and the v1 ruleset.

### 3.1 Structure

The grammar lives in two files:

**`config/grammar.yaml`** — machine-readable rules with Pydantic schema. This is what the enumerator and pre-filters use.

**`docs/GRAMMAR.md`** — human-readable narrative explaining each rule, its rationale, what it costs, and how to know if it should be relaxed. This is what the operator + Claude maintain together.

The two files must stay synchronized. A pre-commit hook validates that every rule in `grammar.yaml` has a corresponding section in `GRAMMAR.md`.

### 3.2 Rule categories

Rules are organized by scope:

**Structural rules** (S-prefix): what shape a strategy must have. Examples: "exactly one hypothesis", "exactly one directional signal source", "at least one regime gate".

**Signal composition rules** (C-prefix): which signal combinations are allowed. Examples: "no two indicators from the same family", "directional signal family must match hypothesis".

**Parameter coherence rules** (P-prefix): which parameter ranges make sense given the signals. Examples: "RSI period must be 2-30", "DTE must match signal lookback".

**Exit logic rules** (E-prefix): what exit stacks are well-formed. Examples: "trend strategies use trailing stops, not hard targets".

**Regime coherence rules** (R-prefix): when regime gates make sense. Examples: "low-IV strategies require IV rank gate".

**Risk coherence rules** (X-prefix): sizer settings must match strategy character. Examples: "vol-target sizing requires recent_vol input feature".

### 3.3 Rule format

Each rule in `grammar.yaml` has this shape:

```yaml
- id: S1
  category: structural
  version: 1
  active: true
  rationale_ref: "GRAMMAR.md#S1"
  predicate:
    type: cardinality
    field: hypothesis
    count: 1
  cost_estimate: low      # how much of the search space this rule eliminates
  evidence_to_relax:
    - "If 3+ promoted strategies have explicit multi-hypothesis structure"
    - "If domain expert provides theoretical basis for relaxation"
```

The `predicate` is interpreted by Forge's rule engine; the supported predicate types are listed in §3.4.

### 3.4 Supported predicate types

The rule engine supports these predicate types in v1:

**`cardinality`**: a field must appear exactly N times (or in range [min, max]).
```yaml
predicate:
  type: cardinality
  field: signals.role.directional
  count: 1
```

**`requires`**: presence of A implies presence of B.
```yaml
predicate:
  type: requires
  if:
    field: hypothesis
    value: mean_reversion
  then:
    field: exits
    includes: time_stop
```

**`forbids`**: presence of A forbids presence of B.
```yaml
predicate:
  type: forbids
  if:
    field: signals.family
    value: trend
  then:
    field: exits
    includes: hard_profit_target
```

**`compatibility`**: structural compatibility between two fields.
```yaml
predicate:
  type: compatibility
  field1: signals.directional.lookback
  field2: dte_bucket
  table:
    short_lookback: [swing_short]
    medium_lookback: [swing_short, swing_mid]
    long_lookback: [swing_mid, swing_long]
```

**`numerical_range`**: parameter value must be in range.
```yaml
predicate:
  type: numerical_range
  field: params.rsi_period
  min: 2
  max: 30
```

**`custom_python`**: escape hatch for rules that need code. Function name is referenced; function lives in `forge/grammar/custom_predicates.py`.
```yaml
predicate:
  type: custom_python
  function: predicate_universe_coverage
```

### 3.5 The v1 ruleset

Below is the v1 grammar. These are the rules we (operator + Claude) have worked through together, with rationales. The implementing agent should review them but **does not modify them** without operator approval.

#### Structural rules

**S1: One hypothesis per strategy.**
Each strategy declares exactly one of: `trend_continuation`, `mean_reversion`, `regime_arbitrage`, `relative_value`, `volatility_event`, `tail_hedge`. Combining hypotheses happens at portfolio level (QuantIQ), not within a single strategy.

**S2: One directional signal source per strategy.**
Exactly one signal has `role: directional`. Other signals can be filters, gates, or confluence requirements.

**S3: At least one regime gate per strategy.**
At least one signal has `role: regime_filter`. Strategies must explicitly declare when they are inactive.

**S4: DTE bucket matches the signal's natural holding period.**
Short-lookback signals (RSI<5, 0-5 day momentum) → `swing_short` only.
Medium-lookback signals (RSI 7-21, MACD, weekly breakouts) → `swing_short` or `swing_mid`.
Long-lookback signals (12-month momentum, quality factors, cointegration) → `swing_mid` or `swing_long`.

**S5: Exit framework consistent with hypothesis.**
- `trend_continuation`: trailing stops required; hard profit targets forbidden.
- `mean_reversion`: time stops required; z-score-based exits encouraged.
- `regime_arbitrage`: regime-flip exit required.
- `relative_value`: convergence exit required.
- `volatility_event`: IV-crush exit required; event-passed exit required.
- `tail_hedge`: roll-on-schedule exit required; profit-taking forbidden.

> **Amendment (D071-final, v3 grammar; L-3 audit 2026-05-29).** The single-required
> exits above were made *substitutable* — each "X required" became a
> `required_from_set` "pick one of {X, …}" choice (operator-approved). e.g.
> `trend_continuation` accepts `trailing_atr` **or** `chandelier_exit` **or**
> `parabolic_sar_exit`; `mean_reversion` accepts `time_stop` **or** `target_exit`
> **or** `zscore_reversion_exit` (so `time_stop` is no longer always-required for MR).
> The live schema is the table in `docs/GRAMMAR.md` §S5 and the source of truth
> `_S5_HYPOTHESIS_EXITS` in `src/forge/grammar/custom_predicates.py`. This DESIGN
> text is kept verbatim as the original intent; the impl follows D071-final.

#### Signal composition rules

**C1: No two indicators from the same family.**
Families are: trend, mean_reversion, volatility, iv_structure, dealer_positioning, flow, macro, calendar, fundamental, smart_money, pairs. Within a strategy, no two indicators may share a family.
*Cost*: blocks combinations like RSI + RSI(2) which might both have signal. Accept the cost; redundancy is a real failure mode.

**C2: Directional signal family must match hypothesis.**
- `trend_continuation`: directional signal from `trend` family
- `mean_reversion`: directional signal from `mean_reversion` family
- `regime_arbitrage`: directional signal from any family + explicit regime-switching exit
- `relative_value`: directional signal from `pairs` family
- `volatility_event`: directional signal from `iv_structure` or `flow` family
- `tail_hedge`: directional signal from `macro` family (typically VIX-based)

**C3: Maximum 4 signals per strategy.**
1 directional + at most 3 supporting (regime, filter, confluence). More than 4 signals is almost always overfit.

**C4: Regime gate cannot use the same indicator as the directional signal.**
A signal cannot be both directional and its own filter. Prevents circular logic.

#### Parameter coherence rules

**P1: Indicator parameters within published ranges.**
Each indicator has a `param_ranges` field in the registry; Forge can only enumerate within those ranges. E.g., RSI period ∈ [2, 50]; ATR period ∈ [5, 30].

**P2: DTE bucket parameter ranges fixed per §6.2 of crucible/DESIGN.md.**
`swing_short`: entry 14-21 DTE, exit 5-7 DTE
`swing_mid`: entry 30-45 DTE, exit 7-10 DTE
`swing_long`: entry 60-90 DTE, exit 21-30 DTE

**P3: Delta target within DTE-appropriate band.**
`swing_short`: delta 0.40-0.55 (ATM-ish)
`swing_mid`: delta 0.30-0.45
`swing_long`: delta 0.20-0.35

**P4: Sizer per-trade risk pct in [0.005, 0.02].**
Hard upper cap from Crucible's invariants. Lower bound prevents accidental zero-sized positions.

#### Exit logic rules

**E1: Mandatory exits always present.**
Every strategy includes `expiry_exit`, `theta_cliff_exit`, `earnings_exit`. These are Crucible's mandatory exits and cannot be removed.

**E2: At most 2 stop-loss exits.**
A strategy with 3+ stop-loss types is over-specified. One premium stop + one underlying-ATR stop is the max.

**E3: Trailing stop requires activation threshold.**
`trailing_atr` exit must specify `activate_after_gain_pct` ≥ 0.30. Trailing from zero gain locks in losses.

#### Regime coherence rules

**R1: Low-IV strategies require IV rank gate.**
If `hypothesis == mean_reversion` AND directional signal is mean-reversion family: must include `iv_rank` regime gate with threshold ≤ 50 (only fire when IV is cheap).

**R2: Trend strategies require trend strength gate.**
If `hypothesis == trend_continuation`: must include `adx` or `hurst` regime gate.

**R3: Volatility-event strategies require event proximity gate.**
If `hypothesis == volatility_event`: must include `days_to_earnings` or `days_to_fomc` regime gate.

#### Risk coherence rules

**X1: Vol-target sizing requires recent_vol feature.**
If `sizer.mode == vol_target`: the strategy must include `realized_vol` as a feature input.

**X2: Fractional Kelly sizing requires expected_value estimate.**
If `sizer.mode == fractional_kelly`: the strategy must include `expected_value_estimator` (which is itself a Crucible-provided helper that computes EV from win rate and avg win/loss).

### 3.6 Total rule count and search-space impact

v1 grammar has 25 rules across 6 categories. Combined, they reduce the raw combinatorial space from ~10^15 (every possible config) to ~10^5-10^6 (grammar-valid configs). Pre-filters then reduce this further to ~10^3-10^4 candidates worth submitting to Crucible.

This is the right order of magnitude. Lower would mean the grammar is too strict (you'd miss things). Higher would mean the grammar is too loose (Crucible drowns in junk).

---

## 4. Component 1: Enumerator

### 4.1 Responsibility

Given the current grammar and Crucible's registry, enumerate grammar-valid strategy configs.

### 4.2 Algorithm

The enumerator is a constraint-satisfaction problem solver, not a brute-force enumerator.

```python
def enumerate(grammar: Grammar, registry: RegistrySnapshot,
              max_candidates: int = 100_000) -> Iterator[StrategyConfig]:
    """
    Yields grammar-valid configs lazily. Uses CSP-style search:
    1. Pick a hypothesis (6 options)
    2. Constrain compatible directional signals (~10-30 per hypothesis)
    3. Constrain compatible DTE buckets (1-2 per signal)
    4. Constrain compatible regime gates (3-10 per hypothesis)
    5. Sample parameter values from valid ranges
    6. Compose exits per E-rules
    7. Compose sizer per X-rules
    8. Yield the config
    """
```

Implementation uses `networkx` to model rule dependencies and `python-constraint` (or a custom CSP solver if dependencies bloat) to satisfy them.

### 4.3 Output

Each yielded config is a `crucible_contracts.StrategyConfig` instance, hashable, JSON-serializable. The enumerator does NOT write to disk — it yields in-memory configs for the pre-filter battery to consume.

### 4.4 Determinism

Enumeration is deterministic given a fixed grammar + registry + seed. Forge logs the (grammar_version, registry_version, seed) for each enumeration batch.

### 4.5 Test requirements

- Unit: enumerator produces only grammar-valid configs (property-based test with 1000 random samples)
- Unit: enumeration is deterministic (same inputs → same output sequence)
- Integration: full enumeration on a small registry produces expected count
- Performance: enumerating 100K configs completes in under 5 minutes

---

## 5. Component 2: Pre-filter battery

### 5.1 Responsibility

For each enumerated config, run cheap statistical and structural checks. Reject configs that fail any filter.

### 5.2 Filter ordering

Filters run in ascending order of cost. Cheap first; expensive last. A failed filter short-circuits the rest.

| Order | Filter | Cost | Rejects |
|---|---|---|---|
| 1 | Structural redundancy | O(1) | Configs equivalent to already-tested ones |
| 2 | Resource feasibility | O(1) | Configs whose lookback > available data |
| 3 | Signal density | O(N) feature rows | Configs whose directional signal has < 30 historical activations |
| 4 | Expected trade count | O(N) | Configs whose expected trade count < 50 over 4yr backtest |
| 5 | Novelty | O(M) prior configs | Configs with > 80% temporal overlap with already-tested configs |
| 6 | Regime exposure | O(N) | Configs that only activate in 1 regime (insufficient diversification) |
| 7 | Permutation test | O(K) permutations | Configs whose signal lacks statistical information |

Total per-config cost: 50ms-2s depending on which filters trigger.

### 5.3 Filter details

#### 5.3.1 Structural redundancy filter

Configs that hash-equivalent to already-tested configs are rejected immediately. Hash includes: signals (sorted), parameters (canonicalized), exits (sorted), sizer.

#### 5.3.2 Resource feasibility filter

If the config's max indicator lookback > available historical data for the universe, reject. (Avoids configs that would have NaN for most of the backtest.)

#### 5.3.3 Signal density filter

Loads the directional signal's historical values (from Crucible's feature cache, read-only). Counts how often the signal would have fired (passed threshold) in the past 4 years. If < 30 activations, reject — insufficient sample size.

#### 5.3.4 Expected trade count filter

Estimates how many trades the strategy would have produced in 4 years. Combines signal density (frequency of firing) with hold time (DTE bucket exit). If < 50, reject — Crucible requires 100 OOS trades for promotion, so we want headroom.

#### 5.3.5 Novelty filter

For each prior tested config (from Forge's own DB), compute the Jaccard overlap of historical signal-firing dates. If max overlap > 0.80, reject — this config is too similar to existing tests.

This is the filter that prevents Forge from flooding Crucible with minor variations.

#### 5.3.6 Regime exposure filter

For each macro regime (bull, bear, low-vol, high-vol, trending, ranging), count activations. If 80%+ of activations are in one regime, reject — strategy is too narrowly specialized.

#### 5.3.7 Permutation test filter

For K=100 permutations, shuffle the signal-to-return mapping and compute the equivalent of "did the strategy make money?" on permuted data. If the real strategy's notional return is within the 90th percentile of permuted returns, reject — signal has no detectable information.

K=100 is a compromise; K=1000 is more rigorous but 10× slower.

### 5.4 Output

Each surviving config gets a `PreFilterReport`:

```python
@dataclass(frozen=True)
class PreFilterReport:
    config: StrategyConfig
    passed: bool
    composite_score: float  # 0.0-1.0, used by ranker
    filter_results: dict[str, FilterResult]
    diagnostic_notes: list[str]
```

Failed reports are logged to Forge's DB but not forwarded to the ranker.

### 5.5 Calibration

Pre-filter thresholds (e.g., the 30-activation minimum, 80% overlap threshold) are configurable in `config/prefilter.yaml`. Initial values are conservative; they tune based on Crucible's hit rate.

**Auto-tune rule**: if Crucible's promotion rate from Forge-submitted candidates drops below 0.5% for 2 consecutive batches, pre-filters loosen by 10%. If promotion rate climbs above 5%, pre-filters tighten by 10%. Maximum auto-adjustment is 30% in either direction; further changes require operator approval.

---

## 6. Component 3: Ranker and queue

### 6.1 Responsibility

From the pool of pre-filtered candidates, select the top-N for submission to Crucible.

### 6.2 Composite score

Each candidate has a composite score:

```
score = (
    0.30 × signal_density_score +
    0.25 × novelty_score +
    0.20 × regime_exposure_score +
    0.15 × permutation_test_score +
    0.10 × prior_promotion_proximity_score
)
```

`regime_exposure_score`: output of the §5.3.6 `regime_exposure` filter (named after the property being measured — concentration of trade dates in any one regime label). Earlier drafts called this `regime_diversity_score`; the rename keeps §6.2's score names in lockstep with §5.3 filter names. The corresponding weight key in `config/ranker.yaml` is `regime_diversity` (back-compat — yaml key intentionally preserved across this rename).

`prior_promotion_proximity_score`: high if the candidate is structurally similar to a previously-promoted strategy (in terms of signals used, hypothesis, etc.). This is a learning signal — once we know a region is promising, sample more from it.

### 6.3 Diversification penalty

Top-N selection is not "highest score wins." It uses a determinantal point process (DPP) or simple greedy diversification:

```python
def select_top_n(candidates: list[PreFilterReport], n: int) -> list[StrategyConfig]:
    selected = []
    remaining = sorted(candidates, key=lambda c: -c.composite_score)
    while len(selected) < n and remaining:
        # Pick highest-scoring candidate that adds diversity
        best = None
        for candidate in remaining:
            similarity_penalty = max(
                jaccard_similarity(candidate, s) for s in selected
            ) if selected else 0.0
            adjusted_score = candidate.composite_score * (1 - similarity_penalty)
            if best is None or adjusted_score > best[1]:
                best = (candidate, adjusted_score)
        selected.append(best[0])
        remaining.remove(best[0])
    return selected
```

This prevents the queue from being 200 minor variations of one promising idea.

### 6.4 Batch size

Default batch: 200 candidates. Configurable in `config/submitter.yaml`. Larger batches require longer Crucible processing time before feedback; smaller batches mean more grammar refinement cycles per unit of compute.

Recommended ranges:
- Initial weeks (high uncertainty): 100 candidates per batch
- Stable operation: 200 candidates per batch
- Late-stage refinement: 50 candidates per batch (focused sweep)

---

## 7. Component 4: Submitter

### 7.1 Responsibility

Write top-N selected configs to Crucible's inbox as YAML files. Track which candidates have been submitted, which are in flight, which have results.

### 7.2 Submission protocol

For each selected config:

1. Generate a unique `forge_candidate_id` (UUID4)
2. Write the config to `{crucible_data_root}/inbox/{forge_batch_id}/{candidate_id}.yaml`
3. Record submission in Forge's own DB: `submissions(forge_candidate_id, forge_batch_id, config_hash, submitted_at, status)`
4. Move on to the next config

Submission is atomic per-file (write to temp + rename). Crucible's inbox watcher picks up files independently; Forge doesn't wait for confirmation.

### 7.3 Rate limiting

Forge does not submit a new batch until the previous batch is at least 80% complete in Crucible. This prevents the inbox from becoming a deep queue Forge can't learn from.

Check rate: every 10 minutes, Forge queries Crucible's runs DB for the status of the previous batch's candidates. When 80%+ are `gated`, Forge submits the next batch.

### 7.4 Failure handling

If Crucible rejects a config (validation error), the file moves to Crucible's `errors/` directory with a `.reason.txt` companion. Forge's submitter watches the errors directory and logs failed submissions to its DB with `status='rejected_by_crucible'` and the reason.

A config that's rejected for grammar drift (e.g., references a deprecated indicator version) is logged as a hint to the grammar refiner to update.

---

## 8. Component 5: Feedback and grammar refiner

### 8.1 Responsibility

Read Crucible's gated results. Learn from them. Propose grammar refinements. Apply tightening automatically; surface loosening for operator approval.

### 8.2 What is read

After each batch completes:

```python
def consume_batch_results(batch_id: str) -> BatchSummary:
    """
    Reads from crucible_contracts.get_gated_runs(filter=batch_id).
    Returns aggregated results: promotion rate, common gate failures,
    metric distributions per outcome.
    """
```

Read is via `crucible_contracts`, never direct DB access.

### 8.3 What is learned

Per batch:

- **Promotion rate**: pass count / total. Tracked over time.
- **Gate failure breakdown**: which gates rejected the most candidates. Used to refine pre-filters.
- **Metric distributions per hypothesis**: which hypotheses produced highest Sharpe, lowest DD, etc. Used to weight the ranker.
- **Promoted strategy structural patterns**: signals used, regimes targeted, parameter ranges. Used to update `prior_promotion_proximity_score`.

Saved to `forge.db` in tables `batch_summaries`, `gate_failures`, `promoted_patterns`.

### 8.4 Grammar refinement: auto-tightening

When evidence is strong enough, Forge automatically tightens the grammar. Examples:

**Trigger**: 95%+ of rejected candidates failed gate X.
**Action**: add a pre-filter that catches likely-gate-X failures earlier.

**Trigger**: 100% of promoted strategies have signal_family Y as their directional signal.
**Action**: weight family Y higher in enumeration; do NOT remove other families.

**Trigger**: 0 promoted strategies in 200+ submissions have parameter Z above threshold T.
**Action**: tighten parameter Z's upper range in `grammar.yaml`.

Auto-tightening is logged to `IMPLEMENTATION_DECISIONS.md` and `grammar.yaml` is updated with a version bump.

### 8.5 Grammar refinement: supervised loosening

Forge can propose loosening but cannot apply it. Examples of proposals:

**Proposal**: "Rule C1 (no two indicators from same family) is rejecting 35% of high-pre-filter-score candidates. Consider relaxing to allow specific cross-family pairs."

**Proposal**: "Rule S4 (DTE matches signal lookback) is rejecting all candidates with RSI(2) + swing_mid. Consider allowing if regime gate is present."

Proposals appear in:
- `OPEN_PROPOSALS.md` (timestamped, awaiting operator review)
- Forge's dashboard surface area
- Slack notification if configured

The operator approves, rejects, or modifies. Approved changes get applied to `grammar.yaml` with operator initials in the decision log.

### 8.6 Feedback loop cadence

- After every batch: light consumption (record results, update tracking tables)
- After every 10 batches OR weekly: full analysis pass (look for refinement opportunities)
- After every 50 batches OR monthly: deep review (operator-facing report on grammar evolution)

### 8.7 Test requirements

- Unit: tightening proposals are correctly identified from synthetic batch data
- Integration: loosening proposals require explicit approval before being applied
- Property: the grammar version monotonically increases; previous versions are preserved in `config/grammar_archive/`

---

## 9. Persistence and database schema

### 9.1 Forge's own DB

DuckDB file at `~/forge_data/forge.db`. Tables:

```sql
CREATE TABLE submissions (
    forge_candidate_id  UUID PRIMARY KEY,
    forge_batch_id      UUID NOT NULL,
    config_hash         VARCHAR(16) NOT NULL,
    config_json         JSON NOT NULL,
    submitted_at        TIMESTAMP NOT NULL,
    status              VARCHAR(20) NOT NULL,  -- 'pending', 'gated', 'rejected_by_crucible'
    crucible_run_id     UUID                   -- links to Crucible's runs table
);

CREATE TABLE batch_summaries (
    forge_batch_id      UUID PRIMARY KEY,
    batch_size          INTEGER NOT NULL,
    submitted_at        TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    promotion_rate      DOUBLE,
    common_failures     JSON,
    grammar_version     VARCHAR(20) NOT NULL,
    registry_version    VARCHAR(20) NOT NULL
);

CREATE TABLE pre_filter_logs (
    forge_candidate_id  UUID,
    filter_name         VARCHAR(64),
    passed              BOOLEAN,
    score               DOUBLE,
    details_json        JSON,
    evaluated_at        TIMESTAMP,
    PRIMARY KEY (forge_candidate_id, filter_name)
);

CREATE TABLE grammar_versions (
    version             VARCHAR(20) PRIMARY KEY,
    rule_count          INTEGER NOT NULL,
    yaml_sha256         VARCHAR(64) NOT NULL,
    changed_at          TIMESTAMP NOT NULL,
    change_type         VARCHAR(20) NOT NULL,  -- 'auto_tighten', 'supervised_loosen', 'manual'
    change_description  TEXT,
    operator_initials   VARCHAR(10)  -- null for auto changes
);

CREATE TABLE grammar_proposals (
    proposal_id         UUID PRIMARY KEY,
    proposed_at         TIMESTAMP NOT NULL,
    proposal_type       VARCHAR(20) NOT NULL,  -- 'tighten', 'loosen', 'add_rule', 'remove_rule'
    proposal_yaml       TEXT NOT NULL,
    rationale           TEXT NOT NULL,
    evidence_json       JSON NOT NULL,
    status              VARCHAR(20) NOT NULL,  -- 'pending', 'approved', 'rejected', 'auto_applied'
    decided_at          TIMESTAMP,
    decided_by          VARCHAR(64)
);

CREATE TABLE promoted_patterns (
    pattern_id          UUID PRIMARY KEY,
    discovered_at       TIMESTAMP NOT NULL,
    pattern_type        VARCHAR(40),  -- 'hypothesis_dominance', 'parameter_cluster', etc.
    pattern_json        JSON NOT NULL,
    promoted_count      INTEGER NOT NULL,
    sample_size         INTEGER NOT NULL
);
```

### 9.2 What Forge reads from Crucible

Read-only access to Crucible's DuckDB:

```sql
-- Forge queries
SELECT r.run_id, r.config_hash, r.status, pd.decision, pd.gate_results_json,
       m.value AS sharpe_value
FROM runs r
LEFT JOIN promotion_decisions pd ON r.run_id = pd.run_id
LEFT JOIN metrics m ON r.run_id = m.run_id AND m.metric_name = 'walk_forward_sharpe_median'
WHERE r.source = 'forge'
  AND r.status = 'gated'
  AND r.finished_at > '<last_seen>'
ORDER BY r.finished_at;
```

Forge never writes to Crucible's DB.

### 9.3 What Forge writes to Crucible

Only YAML files in `{crucible_data_root}/inbox/`. Never direct DB writes.

---

## 10. Configuration

### 10.1 `config/forge.yaml`

```yaml
forge:
  data_root: ~/forge_data
  db_path: ~/forge_data/forge.db
  log_root: ~/forge_data/logs

  crucible:
    inbox_path: ~/optbt_data/inbox     # where Forge writes
    db_path: ~/optbt_data/results.duckdb  # where Forge reads (read-only)
    contracts_version: "1.0"

  enumeration:
    max_candidates_per_batch: 100000
    seed: 42

  submission:
    batch_size: 200
    inflight_threshold: 0.80         # wait until 80% of prev batch is gated
    poll_interval_seconds: 600       # check Crucible status every 10 min

  feedback:
    light_consumption_after_every: 1     # every batch
    full_analysis_after_every: 10        # every 10 batches
    deep_review_after_every: 50          # every 50 batches
```

### 10.2 `config/prefilter.yaml`

```yaml
prefilter:
  signal_density:
    min_activations: 30
  expected_trade_count:
    min_trades: 50
  novelty:
    max_jaccard_overlap: 0.80
  regime_exposure:
    max_single_regime_concentration: 0.80
  permutation_test:
    n_permutations: 100
    p_value_threshold: 0.10
  auto_tune:
    enabled: true
    min_promotion_rate: 0.005          # 0.5%
    max_promotion_rate: 0.05           # 5%
    adjustment_pct_per_step: 0.10
    max_cumulative_adjustment: 0.30
```

### 10.3 `config/ranker.yaml`

```yaml
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: greedy   # 'greedy' or 'dpp'
    similarity_metric: jaccard
```

---

## 11. File structure

```
forge/
├── pyproject.toml
├── uv.lock
├── README.md
├── docs/
│   ├── DESIGN.md            # this file
│   ├── GRAMMAR.md           # narrative grammar documentation
│   └── DECISIONS.md         # implementation decisions log
├── config/
│   ├── forge.yaml
│   ├── prefilter.yaml
│   ├── ranker.yaml
│   ├── grammar.yaml         # machine-readable grammar (current version)
│   └── grammar_archive/     # previous versions
│       ├── v1.yaml
│       ├── v2.yaml
│       └── ...
├── src/forge/
│   ├── __init__.py
│   ├── version.py
│   ├── grammar/
│   │   ├── loader.py        # parses grammar.yaml into rule objects
│   │   ├── predicates.py    # built-in predicate types
│   │   ├── custom_predicates.py  # escape-hatch for code rules
│   │   ├── validator.py     # checks a config against the grammar
│   │   └── archive.py       # version management for grammar changes
│   ├── enumeration/
│   │   ├── enumerator.py    # main enumerator
│   │   ├── csp.py           # constraint-satisfaction primitives
│   │   └── candidate.py     # candidate config representation
│   ├── prefilters/
│   │   ├── base.py          # Filter protocol
│   │   ├── registry.py      # filter registry
│   │   ├── structural_redundancy.py
│   │   ├── resource_feasibility.py
│   │   ├── signal_density.py
│   │   ├── expected_trades.py
│   │   ├── novelty.py
│   │   ├── regime_exposure.py
│   │   └── permutation_test.py
│   ├── ranking/
│   │   ├── scorer.py        # composite score computation
│   │   ├── diversifier.py   # greedy / DPP selection
│   │   └── queue.py         # batch queue management
│   ├── submission/
│   │   ├── submitter.py     # main submission logic
│   │   └── rate_limiter.py  # in-flight tracking
│   ├── feedback/
│   │   ├── consumer.py      # reads Crucible's gated runs
│   │   ├── analyzer.py      # extracts patterns from results
│   │   └── proposer.py      # generates grammar proposals
│   ├── persistence/
│   │   ├── db.py            # DuckDB wrapper for Forge's DB
│   │   └── schemas.py       # DDL
│   └── cli/
│       ├── main.py
│       ├── run.py           # `forge run` — full cycle
│       ├── enumerate.py     # `forge enumerate` — just enumerate
│       ├── analyze.py       # `forge analyze` — feedback analysis
│       └── grammar.py       # `forge grammar` — proposal management
├── scripts/
│   ├── init_db.py
│   ├── seed_grammar.py
│   └── audit_proposals.py
└── tests/
    ├── unit/
    │   ├── test_grammar/
    │   ├── test_enumeration/
    │   ├── test_prefilters/
    │   └── test_ranking/
    ├── integration/
    │   ├── test_end_to_end.py
    │   ├── test_crucible_integration.py
    │   └── test_grammar_refinement.py
    ├── invariants/
    │   ├── test_enumeration_determinism.py
    │   ├── test_no_circular_grammar.py
    │   └── test_submission_idempotency.py
    └── fixtures/
        ├── synthetic_registry.py
        ├── known_promoted_strategies.py
        └── adversarial_grammars.py
```

---

## 12. Implementation phases

Five phases. Estimated 6-10 weeks at part-time (~4 hrs/day), 4-6 weeks full-time.

### Phase 0 — Bootstrap (3-5 days)

- Project skeleton, configs, DuckDB schema
- `crucible_contracts` integration (import, version check)
- First successful read of Crucible's runs DB (synthetic data; Crucible may not be built yet)
- Logging, error handling, basic CLI
- Pre-commit hooks (ruff strict, mypy strict, version-bump check)

**Deliverable**: `forge --help` runs; tests pass on empty skeleton.

### Phase 1 — Grammar engine (7-10 days)

- `grammar.yaml` parser and validator
- All 6 predicate types (cardinality, requires, forbids, compatibility, numerical_range, custom_python)
- Rule loader with version archive
- Validator: given a StrategyConfig and a grammar, returns valid/invalid + reasons
- v1 grammar (25 rules) written to `config/grammar.yaml`
- `GRAMMAR.md` narrative documentation

**Deliverable**: any StrategyConfig can be validated against the v1 grammar in < 10ms. Property test: 1000 random valid configs all pass validation; 1000 random invalid configs all fail.

### Phase 2 — Enumerator (7-10 days)

- CSP-style search over grammar
- Deterministic enumeration (seed-controlled)
- Integration with `crucible_contracts.IndicatorMetadata` to know what's in the registry
- Performance optimization: enumerate 100K configs in < 5 min

**Deliverable**: `forge enumerate --max-candidates=10000` produces 10K valid configs.

### Phase 3 — Pre-filter battery (10-14 days)

- Filter protocol and registry
- All 7 filters implemented
- Each filter has unit tests with known-pass and known-fail cases
- Auto-tune mechanism (with manual override)
- Performance: full battery on 10K candidates completes in < 30 min

**Deliverable**: `forge prefilter --batch-id=test` runs the full battery on enumerated candidates.

### Phase 4 — Ranking and submission (5-7 days)

- Composite scorer
- Diversification (greedy in v1; DPP optional)
- Batch queue management
- Submitter writes YAML to Crucible's inbox
- Rate limiter watches Crucible's status

**Deliverable**: `forge run` performs full cycle (enumerate → pre-filter → rank → submit). Stops when previous batch is 80% complete in Crucible.

### Phase 5 — Feedback and refinement (10-14 days)

- Consumer reads Crucible's gated runs
- Analyzer extracts patterns
- Proposer generates grammar refinement proposals
- Auto-tightening pipeline
- Supervised loosening workflow (proposals to `OPEN_PROPOSALS.md`)

**Deliverable**: full feedback loop operational. Forge can run autonomously for multiple batches with grammar refinement.

### Phase 6 — Polish and operational discipline (5-7 days)

- Property-based invariant tests
- Reproducibility tests (same seed + same grammar → byte-identical batch)
- Resilience tests (Crucible offline; corrupt feedback; partial batches)
- CLI completion and help text
- Operational runbook in README

**Deliverable**: full test suite green; runbook documents normal operation and recovery.

---

## 13. Production-quality requirements

These are non-negotiable. See Crucible's §13 for the full philosophy; Forge follows the same discipline.

### 13.1 Deterministic enumeration

Given (grammar_version, registry_snapshot, seed), enumeration produces the same sequence of configs every time. Test enforces byte-equality.

### 13.2 Grammar version safety

A `grammar.yaml` change requires:
- Bump of grammar_version in the file
- Archive of the old version to `config/grammar_archive/`
- Decision log entry
- Pre-commit hook verifies all three

### 13.3 No silent grammar changes

The grammar refiner cannot modify `grammar.yaml` without writing an entry to `grammar_versions` table. Auto-tighten changes carry `operator_initials = NULL`; manual changes carry initials.

### 13.4 Submission idempotency

A config with the same hash cannot be submitted twice. The `config_hash` column in `submissions` is unique-indexed.

### 13.5 Crucible-version compatibility

At startup, Forge validates that its `crucible_contracts` version is compatible with Crucible's. Mismatch halts execution with a clear error.

### 13.6 No equity exposure

Forge's grammar must not permit `equity` as a signal family. Validator rejects configs that try. This prevents accidental Crucible-equity-strategy generation.

### 13.7 Resource limits

Forge respects `worker_mem_limit_mb` from Crucible's `runtime.yaml` shared config. If pre-filtering OOMs, gracefully degrade and resume.

---

## 14. Decision log

Append-only. Major design decisions documented here for the implementing agent.

| Date | Decision | Rationale | Alternatives |
|---|---|---|---|
| 2026-05-13 | Five-component architecture (Enumerator / Pre-filter / Ranker / Submitter / Feedback) | Each component has one job; failures are localized | One monolithic generator (poor testability) |
| 2026-05-13 | Grammar in YAML + Python predicates | YAML for declarative rules, Python for escape-hatch rules | Pure Python (less human-readable); pure YAML (insufficient expressivity) |
| 2026-05-13 | 25 rules in v1 grammar | Enough to constrain meaningfully without over-restricting | More rules (over-restriction); fewer rules (too much junk in submissions) |
| 2026-05-13 | Auto-tighten / supervised-loosen | Tightening reduces search space (safe); loosening expands (risky) | All-auto (drift); all-manual (slow) |
| 2026-05-13 | DuckDB for Forge's own state | Consistent with Crucible; embeddable; column-store | SQLite (slower for analytics); separate process |
| 2026-05-13 | Greedy diversification (not DPP in v1) | Simpler implementation; DPP can be added later if needed | DPP from day 1 (more complex, more correct) |
| 2026-05-13 | No LLM in production loop | LLMs trained on financial writing regenerate overfit ideas | LLM-as-collaborator (acceptable for grammar refinement sessions) |

---

**End of specification.**
