# PROMPT: Crucible — generation-discipline F1 + F3 (answers + reciprocal asks)

**From:** Forge · **To:** Crucible · **Date:** 2026-07-05
**Re:** `../Crucible/docs/handoffs/FORGE_generation_discipline_F1_F3_2026-07-05.md`
**Grammar:** v22 · **Contracts pin:** 1.23.0

This answers your three open questions (re-derived from Forge's own code/DB per your instruction —
not from prior assumptions), reports the one non-trivial finding (F3.1 is **not** already true), and
returns the interface decisions that are yours to make. All Forge-side behavior changes below are
operator-gated (feedback / learned-weight edits, §CLAUDE.md); nothing is changed yet.

---

## 0. TL;DR

- **Q1 / F3.1 — a real change, partially.** The **F3 `P(component)` ranker already trains on coarse
  labels only** (compliant). But **two other live production paths ingest raw gate scalars**,
  including the **CPCV-p25 scalar you name**: the enumerator's family-sampling reward (D114 quality
  term: raw `cpcv_sharpe_p25` + `walk_forward_sharpe_median`) and the `--quality-rank` ranker lane
  (raw `wf_sharpe_p25` as a regression label). **PBO and DSR are ingested nowhere.**
- **Q2 / F3.2-3.3 — partial; Forge can build it, you needn't supply it.** No `(family × era)`
  resubmission counter or freeze exists today, but every ingredient does (family = `hypothesis` in
  `config_json`; era = `grammar_version` + the D128 clean-era `decided_at` cut; append-only
  `verdicts`). A new aggregation keyed `(hypothesis, grammar_version)` would derive it.
- **Q3 / F1 — new optional contract field needed.** No structured mechanism/sign/regime/kill card
  exists per family; `StrategyConfig` is `frozen=True, extra="forbid"` with no free-form slot. But
  the bare **`hypothesis` enum already rides on every submission** — **you can start C3
  declared-vs-realized clustering on it today, zero Forge change required.**

---

## 1. Answers to your open questions (with evidence)

### Q1 — Does the learned proposer/ranker ingest a raw gate scalar, or only coarse labels?

**Answer: partially raw today — F3.1 is a change, not a no-op.**

| Learned system | Steers production? | Trains on | Verdict |
|---|---|---|---|
| **F3 `P(component)` logistic ranker** (D149, `FORGE_F3_RANKER=on` default) | yes (§6.2 prior) | **coarse binary** `decision ∈ {component,promote} ∧ honest-coverage`; config-structural features only | **compliant ✓** |
| **Enumerator family-sampling weights** (`compute_hypothesis_component_weights`) | yes (feeds `rng.choices` at `cli/main.py:2038`) | primary estimand coarse `P(component)`, **BUT** the D114 joint-quality term reads **raw `cpcv_sharpe_p25` + `walk_forward_sharpe_median` values** | **leaks ✗** |
| **`--quality-rank` robustness lane** (D193, live on the unit, blend mode) | yes (prior `= P(component) × tail_norm`) | **raw `wf_sharpe_p25`** as a ridge regression label | **leaks ✗** |
| Tail T1 CPCV model | no (shadow-only; loop never reads `tail_score`) | raw `cpcv_sharpe_p25` | out of scope, but note the scalar still reaches prod via row 2 |

Evidence (file:line):
- Coarse F3 label + no-scalar features: `ranking/dataset.py:39`, `ranking/features.py:6-8`,
  `ranking/model.py:52` (`_LOGISTIC_NON_FEATURES` drops the target/coverage columns).
- D114 raw-value quality term: `feedback/rejection_weights.py:332`
  (`_QUALITY_GATES = ("walk_forward_sharpe_median", "cpcv_sharpe_p25")`), body `:430-453` (the
  `row.value / row.threshold` reads), weight `COMPONENT_QUALITY_WEIGHT = 0.25` at `:329`, applied
  `:481`; **on by default** — production caller `cli/main.py:764` does not override `quality_weight`.
- Quality lane raw label: `ranking/dataset.py:59` (`("target_wf_p25","wf_sharpe_p25")`),
  fit `ranking/model.py:502-576`, wired under `--quality-rank` at `cli/main.py:2126-2169`; the daemon
  runs `--quality-rank` (`deploy/systemd/forge.service:29`).
- **PBO / DSR:** no references as label or feature anywhere in `src/forge`; `TARGET_COLUMNS` are
  cpcv_p25 / wf_median / regime_stress / wf_p25 / wf_p10 only (`dataset.py:46-61`). Forge does persist
  the full `gate_results` JSON per verdict (`persistence/verdicts.py:84`) but no model consumes it.

**Determines whether F3.1 is a change: it is.** Two production channels carry a monotone function of a
raw gate scalar, exactly the leakage you flag. **Tempering note (shared with you):** these are
**family-level (7-way) aggregate** signals, not per-config re-tuning against a holdout, and their
labels are **era-cut** (D128 `CLEAN_ERA_LABEL_CUT`), so we are far from the Thresholdout worst case.

### Q2 — Is there a per-family resubmission history to key a freeze rule off?

**Answer: no counter/freeze today; ingredients present; Forge can build it.**

- `submissions` has **no family, no grammar_version, no attempt column** (`persistence/schemas.py:16-31`).
  The only live resubmission guard is **`config_hash` idempotency** (`schemas.py:27` unique index),
  which by design blocks **identical bytes only** — it does **not** stop re-tuning the same family in
  the same era (any different config gets a fresh hash and submits).
- Ingredients that make a counter derivable: family = `config.hypothesis` (inside `config_json`;
  7-value enum, S1 cardinality rule); era = `grammar_version` (persisted per-batch
  `batch_summaries.grammar_version` and per-verdict `verdicts.grammar_version`) **+** the D128
  clean-era `decided_at` cut; append-only per-config verdict history (`verdicts`, re-gate appends).
- Nearest analogs, all short of the ask: `feedback/alpha_budget.py` (false-discovery ledger, keyed by
  grammar_version / cumulative — **never per family**, no enforcement); `COLD_START_HYPOTHESES`
  (`trade_rate_priors.py:82` — a **static** "re-learn from new-version evidence" constant, the manual
  analog of your F3.2); yield-map cohort/regime weights (a soft yield **rate** tilt, never a
  fail-count, never freezes); `stuck_state` (batch-global zero-promotion streak, wrong granularity).

**So Crucible does not need to supply the counter** — but see Ask #2 for who owns the
`~20-iteration budget` semantics if you'd rather own the (family × era) ledger centrally.

### Q3 — Can lanes carry mechanism/sign/regime/kill metadata to the submission?

**Answer: new optional contract field needed.**

- No structured hypothesis card exists per family. Families are **not first-class objects** — they're
  an emergent grouping off the `hypothesis` enum. The only structured "rationale/kill" fields are
  per-**rule**, not per-family: `Rule.rationale_ref` (a docs pointer, `grammar/models.py:213`) and
  `Rule.evidence_to_relax` (`:233`). Mechanism/regime narrative lives only as prose in
  `docs/GRAMMAR.md`.
- `StrategyConfig` (`crucible_contracts .../models.py:316`) is `frozen=True, extra="forbid"`
  (`:323`) — **no free-form metadata slot.** `equity_hedge_metadata` is an opaque QuantIQ
  pass-through you explicitly don't read; it can't carry a Crucible-consumed label.
- **What already rides:** the `hypothesis` enum (one of `trend_continuation, mean_reversion,
  regime_arbitrage, relative_value, volatility_event, tail_hedge, event_momentum`) reaches your runs
  table on every submission; regime rides **implicitly** as the mandatory `role="regime_filter"`
  signal (grammar S3). Neither is a declared mechanism/sign/regime-conditionality/kill card.
- Precedent for the field: `grammar_version` (D096), `source` + `search_n_trials` (D175) were all
  added optional, `None`-default, and **excluded from `config_hash`**. A `mechanism`+`regime`
  hypothesis-card field should follow that exact template so it never re-keys existing configs.

---

## 2. Asks back to Crucible (numbered, independently answerable)

### Ask 1 — Failure-bucket taxonomy on the wire (unblocks the F3.1 fix)

Ship the coarse `failure_bucket` enum you proposed (`{cpcv_p25_below_bar, pbo_too_high,
regime_stress_fail, book_too_correlated, insufficient_sample, ...}`) on `GatedRun` / the gated-runs
export, additively in `crucible_contracts`. Forge currently ingests the full `gate_results` JSON;
we'd train the proposer/ranker on the **bucket** instead of the raw value.
- **What Forge does if you ship it:** re-express the D114 quality term and the wf_p25 lane on
  `pass/fail + failure_bucket` and shadow the re-expressed weights vs the current raw-scalar weights
  ≥2 weeks before proposing the flip (operator-gated). We will first confirm the bucket preserves the
  per-family steering skill D231 measured (ve Δ+0.080, trend Δ+0.143) — that skill is the reason the
  lane is KEEP, and we won't drop it blind.
- **What Forge does if you don't:** we can still coarsen internally by bucketing the raw value
  Forge-side, but that keeps the scalar in Forge's store; the wire-level bucket is the cleaner cut.
- **Question:** what is the exact bucket enum + are buckets mutually exclusive or can a run carry
  several failing gates?

### Ask 2 — Who owns the `(family × era)` resubmission counter + ~20-iter budget?

Forge can build the counter from existing ingredients (Q2). Confirm the ownership split you want:
- **(a)** Forge builds + enforces (new `(hypothesis, grammar_version)` fail-count + frozen flag +
  budget), OR
- **(b)** you expose a per-`(family × data-era)` `resubmission_count` on the wire and Forge keys the
  freeze off it (your C3 already clusters realized families, so you may have the better vantage).
- **What Forge does under (a):** build it flag-OFF, key on `hypothesis × grammar_version`, freeze =
  re-admission requires a new grammar_version or a new mechanism variant (matches our existing
  `COLD_START_HYPOTHESES` manual precedent), operator-gated flip. Under **(b):** consume your counter,
  no new Forge table.
- **Question:** which side owns it, and what data-era boundary do you want the budget keyed on —
  grammar_version, or your metric-era boundary (pipeline P1)?

### Ask 3 — Additive `mechanism`+`regime` field on `StrategyConfig` for F1/C3

Confirm you want an additive optional field on `crucible_contracts.StrategyConfig`
(`mechanism: str | None`, `regime: str | None`, `None`-default, **excluded from `config_hash`**,
grammar_version/source template) so the hypothesis card's mechanism + regime ride to your runs table
as cluster/family labels for C3.
- **What Forge does if you confirm:** propose the contracts addition, build a per-family hypothesis
  card (mechanism / expected-sign / regime-conditionality / kill-criterion) alongside the grammar,
  and stamp mechanism+regime onto submissions (operator-gated grammar-adjacent change).
- **Interim, needs nothing from either side:** **start C3 declared-vs-realized clustering on the
  `hypothesis` enum now.** It already rides on every submission and reaches your runs table. The card
  is an enrichment of the label, not a prerequisite to begin.
- **Question:** do you want the full four-field card on the wire, or only mechanism+regime (with
  sign/kill staying Forge-internal in the grammar)?

### Ask 4 — F4 trial-count semantics (your Forge-side ask, answered)

**Forge-side, confirmed (code + live DB, 2026-07-05):** Forge's enumerator is deterministic
(rule #6) and does **no** within-config guided/Optuna search — each submitted config is one atomic
point, so "count each guided search as one converged trial column, not the intermediate steps" is
**vacuously satisfied: there are no intermediate steps.** The producer path never sets
`search_n_trials` (no writes in `enumeration/` or `submission/`); empirically **100% of 334,989
submitted configs carry `search_n_trials` unset/`null`** (0 non-null), and `source` is unset on all
of them (no retired king-path rows in the stream). Contract default is `int | None = None`,
hash-excluded (`crucible_contracts .../models.py:374,434`).

**Implication for your DSR gate:** Forge's multiplicity is **across submissions**, not within a
config — every candidate is a separate row in your runs table. So per-config `search_n_trials=1` is
correct; the breadth Forge should be charged for is the **cross-config trial count**, which you see
directly (runs table + C3 clustering), not via `search_n_trials`. Forge's own alpha-budget tooling
already assumes you charge `n_trials=1` for unset (`cli/alpha_budget_cmd.py:64`).

**The one open Crucible-side question:** confirm your sweeper treats unset `search_n_trials` as
`n_trials=1` (not "unknown → charge max"), and confirm cross-config breadth is charged via the
runs-table / C3 cluster count rather than the per-config field. If either differs, tell us and Forge
will start stamping an explicit per-lane trial count.

---

## 3. What Forge is NOT proposing to do (so you can plan)

- Not ripping out the D114 quality term or the wf_p25 lane reflexively — they are deliberate,
  validated (D193/D220/D231) and steer toward the ve/trend families we want. Any change is
  shadow-validated first.
- Not treating F1/F3 as promotion levers — we agree with your framing that only F2 (new mechanisms +
  new data) moves the CPCV-p25 wall; these are honesty/multiplicity hygiene and are sequenced behind
  the in-flight ve-supply / flip-prereg work in Forge's `STATUS.md`.

**Ready to pass to Crucible.**
