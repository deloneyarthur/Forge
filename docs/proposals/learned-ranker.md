# Learned Verdict Model for Ranking — Design Proposal (F-track)

**Status: PROPOSED — operator-gated at three points (F1 / F2 / F3 below). No code exists yet.**
**Date:** 2026-06-10. Origin: operator brainstorm session ("should we incorporate learning
prediction models for strategy generation?").
**Spec anchors:** §6.2 (composite score; the `prior_promotion_proximity` learning slot),
§8.3 ("metric distributions … used to weight the ranker"), §10.3 (`config/ranker.yaml`),
§1.2/§1.3 (success = stream becomes more promotable; 1–3% target, >5% Goodhart warning).
**Decision-log home:** on F3 approval this becomes the first entry in `docs/DECISIONS.md`
(design-level: §6.2's learning term generalized). Each shipped phase gets its own D-entry.

---

## 1. Problem

Two facts, both verified against the as-built code on 2026-06-10:

1. **The ranker has no outcome gradient.** The §6.2 composite
   (`src/forge/ranking/scorer.py:51-84`) is four structure scores from the pre-filter
   battery plus `prior_promotion_proximity` (weight 0.10) — the spec's designated
   "learning signal." That term is Jaccard similarity to previously **promoted** configs,
   and `promoted_patterns` is empty (0 promotions all-time). The only term designed to
   learn currently discriminates nothing. Within a batch, ranking cannot prefer configs
   that *resemble what Crucible accepts*.

2. **Learned steering is per-cell counting with no pooling across features.** The
   feedback weights (hypothesis / bucket / underlying-class, D105/D106) are
   Beta-smoothed empirical rates per stratum. A brand-new arm has no cells — it starts
   from the prior and gets starved before evidence can accrue. Live symptom at the
   2026-06-10T18:53Z baseline: `iv_minus_rv` at 2/600 submitted vs ~4% raw emission
   share, ~16 hours after we paid the full operator-gated cost of activating it (v17).

A calibrated model P(component | config features) addresses both: it gives the ranker an
outcome gradient, and — because it scores configs by their *features* rather than their
arm identity — it generalizes to arms it has never seen (a new indicator still has a
hypothesis, family, bucket, delta position, exit shape…).

## 2. What this is NOT

- **Not a market predictor.** Features are config-structural only; no price/return data
  enters the model. Forge predicts *Crucible's verdict*, not the market. Alpha stays
  Crucible's jurisdiction (§1.2).
- **Not a grammar change.** `grammar.yaml` untouched; enumeration untouched; sampling
  untouched in F1/F2. Hard rules #1/#3/#10 not in play.
- **Not an LLM and not stochastic** (hard rule #5). A regularized logistic regression is
  deterministic Python: convex objective, zero-init Newton iterations, no RNG anywhere.
- **Not a gate.** The model ranks; it never rejects. Pre-filters and Crucible's gate are
  unchanged.

## 3. Spec fit and the one deviation

§6.2 describes `prior_promotion_proximity_score` as "high if the candidate is
structurally similar to a previously-promoted strategy … This is a learning signal —
once we know a region is promising, sample more from it." With zero promotions the
literal reading is inert. This design generalizes the term's *computation* — from
"Jaccard similarity to promoted configs" to "calibrated promotion-proximity learned from
all honest verdicts" — while keeping the term's *intent*, name, slot, and weight. §8.3
already sanctions outcome-driven ranker inputs. The generalization is the deviation;
it is proposed here, never silently applied, and lands in `docs/DECISIONS.md` on
approval. Until F3 is approved the production formula does not change at all.

## 4. Architecture — three phases, three operator gates

```
F1: dataset + features        (zero behavior change; retroactive over honest era)
F2: shadow model + daily eval (zero behavior change; logs scores next to the incumbent)
F3: live wiring + per-arm exploration floor   (ships ONLY as a pair; evidence-gated)
```

### F1 — Feature extraction and dataset builder

**New module `forge.ranking.features`** — one pure function:

```
extract_features(config: StrategyConfig, registry: RegistrySnapshot) -> FeatureVector
```

frozen dataclass output, `FEATURE_SCHEMA_VERSION = 1`. **Single codepath** used at
training time (configs rehydrated from `submissions.config_json`) and at scoring time
(in-memory configs) — train/serve skew is impossible by construction, pinned by a
round-trip test. No new logging is needed: `submissions` already stores full
`config_json`, and `verdicts` (D111) joins by `config_hash`. The entire honest era is
training data retroactively.

**v1 feature list** (~35 dims after one-hot; every input available at submission time):

| Group | Features |
|---|---|
| Identity | hypothesis (7), dte_bucket (3), underlying class (D106 classes), ETF flag, rank-arm flag (+ rank_k when rank) |
| Signals | directional family (13); directional indicator id (one-hot over ids with ≥10 train rows, else an "other" bucket — new arms at score time hit family + "other", which is the generalization property); regime-gate indicator ids (multi-hot, same treatment); n_signals; has_filter; has_confluence; combiner type |
| Selector | delta_target normalized within its P3 band → [0,1]; dte_min/dte_max normalized within the P2 window; directional threshold quantile within its sampler range (where a threshold-table entry exists) |
| Sizer | mode (3), per_trade_risk_pct normalized within [0.005, 0.02] |
| Exits | non-mandatory exit ids (multi-hot), n_optional_exits |

Deliberately excluded from v1: grammar_version (confound — the era filter handles it),
anything verdict-derived (leakage), anything market-derived (jurisdiction).

**Label.** `y = 1` iff `decision ∈ {component, promote}` **and** the run passes the D128
honesty predicate — imported from the feedback module (`_honest_regime_coverage`,
`src/forge/feedback/rejection_weights.py`), never re-implemented. `y = 0` for rejects.

**Row filter (the era cut).** `decided_at ≥ 2026-06-10T17:17:13Z` — the composite
clean-era boundary (earnings-exit live + chain-fix registry + v17; D130/D131). This is
deliberately stricter than D128's 22:52:57Z value-cut: labels must come from the engine
that actually enforces earnings exits and reads correct single-name chains. The constant
lives beside the existing era keys with a name like `CLEAN_ERA_LABEL_CUT`; **any future
declared era boundary obsoletes models trained before it** (see F3 guards). Refit
children (same `config_hash`, new `crucible_run_id`) are kept as separate rows — they
are independent gate evaluations (D124 continuity decision).

**CLI.** `forge ranker-model dataset [--db <snapshot>] --out <parquet>` — polars over a
forge.db snapshot (the `/tmp` copy ritual when reading live). Deterministic given the
snapshot: rows ordered by `(decided_at, crucible_run_id)`.

**Scale check.** ~339 decided post-boundary verdicts at the 18:53Z baseline (18
component / 321 reject), accruing at Crucible's ~60 decisions/hr → roughly 1.4k/day.
The model trains at any n but stays shadow until the F3 criterion is met.

### F2 — Shadow model, trainer, daily-checkpoint eval

**Model: L2-regularized logistic regression, pure-Python Newton–IRLS.** At d≈35 and
n≤10k this is a 35×35 solve per iteration — trivial without numpy. **numpy and sklearn
are not currently dependencies** (verified: polars/duckdb/typer/pydantic/structlog);
recommendation is zero new dependencies. Alternative (operator call): add scikit-learn
for a battle-tested solver at the cost of a heavy dep and more determinism surface.

**Determinism (hard-rule #5/#6 posture):** convex objective, coefficients zero-init,
fixed λ (default 1.0 on standardized features), fixed iteration cap + tolerance,
features in schema order, rows in dataset order — **no RNG exists in train or score
paths** (nothing for `SeedHierarchy` to even seed). Same DB snapshot → byte-identical
artifact; this is an invariant test, not a hope.

**Artifact:** JSON at `~/forge_data/models/verdict_model_v<schema>_<trained_through>Z_<sha8>.json`
carrying: schema version, era cut used, n rows / class counts, λ, coefficients **by
feature name** (auditability: the operator can read which axes the model believes in),
train metrics, content sha256. Directory is append-only — the `grammar_archive/` analog.

**Trainer CLI:** `forge ranker-model train [--db <snapshot>] [--lambda <f>]` — run
manually at the daily checkpoints first; automation is a later, separate decision.

**Shadow scoring:** in `_run_one_iteration`, after ranking and selection are complete,
score every ranked candidate and write to a new additive table:

```sql
CREATE TABLE shadow_scores (
    forge_candidate_id UUID,
    model_id VARCHAR(64),
    model_score DOUBLE,        -- calibrated P(component)
    composite_score DOUBLE,    -- the incumbent §6.2 score, persisted for comparison
    scored_at TIMESTAMP,
    PRIMARY KEY (forge_candidate_id, model_id)
)
```

plus one structlog summary line per batch. **Selection is untouched** — an invariant
test pins that the submitted set is byte-identical with and without a model file
present. Persisting `composite_score` here also closes a telemetry gap: the incumbent's
score is currently not stored anywhere, so today we couldn't even measure whether the
existing ranker ranks well.

**Eval CLI:** `forge ranker-model eval --since <ts>` — joins `shadow_scores ⋈ verdicts`,
reports for model vs incumbent: AUC, precision@K (K = realized component count in the
window), Brier score, and a calibration-decile table. Run at each daily checkpoint
alongside the existing EOD reads.

**F3 promotion criterion (defaults, operator-tunable):** the model may be wired live
only when, on **≥3 consecutive daily checkpoints**, each with **≥150 newly-decided
honest-era verdicts spanning ≥5 batches**: model AUC ≥ incumbent AUC + 0.05 **and**
model precision@K ≥ incumbent precision@K. Until then it shadows indefinitely at zero
risk.

### F3 — Live wiring + per-arm exploration floor (one unit, never split)

**Wiring:** `prior_promotion_proximity_score := model P(component)` (already [0,1]).
Weight stays at 0.10 initially — raising it is a separate, later, evidence-gated
`ranker.yaml` change. Fallback chain (the D076 two-mode precedent): model file missing /
schema mismatch / stale → current Jaccard path, with a structlog warning. Guards:

- **Staleness:** refuse a model whose `trained_through` is older than 7 days.
- **Era:** refuse a model whose era cut predates the newest declared era boundary
  (the boundary list is imported from the feedback module's era keys — one source).
- **Cohort keying:** `batch_summaries` gains an additive `model_id` column (D085
  `enumeration_inputs_hash` precedent) so funnel reads split pre/post-model cohorts.

**Per-arm exploration floor — why it is coupled.** The moment the model shapes
submissions, its future training data is conditioned on its own choices: an early-noise
verdict against an arm could suppress that arm forever, and the model would never
collect the evidence to correct itself. The floor guarantees model-independent coverage.
Shipping F3's wiring without the floor is the one configuration this design forbids.

Mechanism (the D103 per-hypothesis-floor precedent, same insertion point):

- **Arm** = `(role, indicator_id)` for role ∈ {directional, regime_gate}.
- An arm is **young** while its honest-era verdict count < **K = 25**.
- The diversifier (`src/forge/ranking/diversifier.py`) gains a reservation phase:
  up to **2 slots per young arm**, capped at **10% of batch** total, filled with the
  highest-composite candidates carrying that arm, then greedy-fills the remainder
  as today. Deterministic (arms in sorted order); floored candidates still passed
  every pre-filter.
- The floor never invents candidates: if no survivor carries a young arm, nothing is
  reserved — generation-side starvation stays visible in the funnel rather than being
  papered over. (If tonight's EOD read shows the *sampler or pre-filters* starving new
  arms before ranking, a sampler-side quota is a separate follow-up; this floor fixes
  the ranking stage.)

## 5. Hard-rule and invariant compliance

| Rule | Posture |
|---|---|
| #2 contracts-only | Trains/scores from forge.db only (`submissions`, `verdicts` — both populated via existing contracts read paths). No Crucible internals. |
| #3 gate untouched | Model ranks; nothing about Crucible's promotion gate moves. |
| #4 no auto-loosening | Model affects ranking, not grammar. The floor adds coverage; it relaxes nothing. |
| #5 no LLM, deterministic loop | Convex fit, zero-init, no RNG. Deterministic Python end to end. |
| #6 deterministic enumeration | Enumeration untouched. Ranking already depends on mutable learned state (hypothesis/bucket/class weights) — the model is one more such input, cohort-keyed via `model_id`. |
| #8 clock/seed | `forge.core.clock.utc_now()` for all timestamps; no RNG to seed. |
| #9 idempotency | Submission path untouched. |

**Invariant tests (`tests/invariants/`, RED-first per TDD discipline):**

1. Determinism: same dataset fixture → byte-identical model artifact.
2. Era cut: a pre-boundary verdict row in the fixture is excluded from training.
3. Honesty reuse: a dishonest-coverage "component" labels as 0 (predicate imported, not copied).
4. Shadow no-op: submitted set identical with model present vs absent (F2).
5. Fallback: stale or schema-mismatched model → Jaccard path + warning (F3).
6. Floor guarantee: a young-arm survivor in the pool → at least one selected (F3).
7. Skew-proof: features from `config_json` round-trip == features from the in-memory config.

## 6. Risks

- **Goodhart on the proxy label.** P(component) is not P(promote); optimizing it can
  drift from the real target. Mitigations: weight stays 0.10; §1.3's >5% warning stands;
  checkpoint eval watches component-rate vs promotion-rate divergence once promotions exist.
- **Tiny-n overfit.** ~18 positives today. Mitigations: strong λ, capped feature set,
  id-level features bucketed under a row-count floor, shadow-until-criterion, and
  coefficients printed by name at every eval so drift toward nonsense is visible.
- **Closed-loop selection bias.** The central risk; the floor is the mitigation, and
  the F2 shadow period provides a model-independent baseline window.
- **Era boundary after training.** The era guard refuses the model; retraining after any
  declared boundary is mandatory and cheap.
- **Incumbent comparison unfair at first** (composite was never persisted historically).
  Accepted: comparison starts when shadow logging starts; no retroactive incumbent claims.

## 7. Build plan (each phase: TDD, own D-entry, `STATUS.md` block)

- **F1** (~1 session): `forge.ranking.features` + dataset CLI + invariants 1–3, 7.
- **F2** (~1–2 sessions): IRLS solver + trainer + `shadow_scores` + shadow hook +
  eval CLI + invariant 4. Then it runs at the daily checkpoints and accrues evidence.
- **F3** (~1 session, **only after the F2 criterion is met and operator re-approves**):
  scorer wiring + guards + `model_id` cohort key + per-arm floor + invariants 5–6 +
  `docs/DECISIONS.md` entry + MANPAGE/architecture doc updates in the same commit.

## 8. Operator decisions needed before F1 starts

1. **Approve the F-track shape** (shadow-first, three gates, floor coupled to F3)?
2. **Solver dependency:** pure-Python IRLS, zero new deps (recommended) — or scikit-learn?
3. **Slot:** upgrade `prior_promotion_proximity` (recommended; spec's designated slot) —
   or add a sixth composite term with its own weight?
4. **F3 criterion defaults:** 3 consecutive checkpoints / ≥150 verdicts / AUC margin
   +0.05 / precision@K parity — acceptable?
5. **Floor constants:** K=25 honest verdicts to graduate an arm; 2 slots per young arm,
   ≤10% of batch — acceptable?
6. **Refit children:** keep all rows per config_hash (recommended, D124-consistent) —
   or first-decision-only?
