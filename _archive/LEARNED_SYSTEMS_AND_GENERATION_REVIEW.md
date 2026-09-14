# Forge — Learned-Systems & Strategy-Generation Review (deep research, 2026-06)

**Status:** research / findings · no code or config changed · operator-gated follow-ups proposed
**Scope:** an external best-practice audit of (A) Forge's learned-model systems (the ranker, the
robustness/quality lane, the train/shadow/promote MLOps) and (B) strategy generation
(grammar → enumerate → pre-filter → rank → submit), against the academic + industry literature.
**Method:** five parallel web-research sweeps (financial-ML validation; meta-labeling / calibration /
learning-to-rank; QD / alpha-mining / search; MLOps shadow-promotion / drift; backtest-overfitting),
each adversarially verified and source-tiered, cross-referenced against a direct code read
(file:line cited). Three fabricated "facts" were caught and discarded in verification; load-bearing
claims are HIGH-confidence / verbatim-sourced unless flagged. This complements `AUDIT.md` (the
2026-06-09 correctness/resilience audit) — it does **not** re-litigate determinism/throttle/resilience.

---

## 0. One-paragraph verdict

The learned-model stack and the generation pipeline are, on the big structural choices, **sound and
genuinely above-average** — deterministic and content-addressed artifacts, train/serve parity by
construction, an honest multi-metric eval, linear models that match the low-signal-finance consensus,
a downside-percentile robustness target the 2026 literature independently endorses, decorrelation
correctly deferred to assembly, and the correct diagnosis that the long-options quality ceiling is a
*representation* limit (Path C), not a search limit. The weaknesses are **narrow, concentrated, and
mostly cheap to fix**, and they cluster in three places: (1) **how the two learned scores are
combined and weighted** — the per-config promotion predictor is diluted to 0.10 of the final sort and
the `P(component) × sigmoid(ridge)` product is an unprincipled, calibration-fragile combination;
(2) **promotion discipline** — an ad-hoc streak gate, no drift monitoring, a censored-feedback loop,
and a trial-count that doesn't reflect Forge's own selection; and (3) **generation is a bandit
re-weighter, not a true illuminator** — it never keeps or mutates the strong configs it finds. None of
these can break the edge-magnitude ceiling (only the grammar can); they make the *stream* more
efficient, honest, and higher-yielding within that ceiling.

---

## 1. The system as built (map + the one number that frames everything)

**Two production learned models**, both pure-Python (no numpy in the env), both deterministic:

| Model | Algo | Target | Where | Eval |
|---|---|---|---|---|
| `VerdictModel` — P(component) | Newton-IRLS **logistic**, L2 | clears component gate ∧ honest coverage | `ranking/model.py:64,258`; ~85–90 structural features `features.py:81` | AUC vs incumbent, precision@K, **Brier + reliability table** `evaluation.py:65,136` |
| `RobustnessModel` — quality lane | **ridge**, L2 | `target_wf_p25` (WF-Sharpe 25th pct floor) | `ranking/model.py:442`; **same feature set** | Spearman rank-IC vs realized (`eval-robustness`) |

**The blend (live since D193):** `prior := P(component) × robustness_tail_norm`, where
`robustness_tail_norm = sigmoid(ridge_prediction)` (`model.py:579`, wired `cli/main.py:1911-1926`).

**Where the blend lands — the framing number.** The ranker composite (`config/ranker.yaml`,
`scorer.py:74-84`) is:

```
score = 0.30·signal_density + 0.25·novelty + 0.20·regime_diversity
      + 0.15·permutation_test + 0.10·prior_promotion_proximity
```

The entire learned per-config promotion predictor — the whole D132 → D188 → D193 investment —
occupies the **`prior_promotion_proximity` slot at weight 0.10** (`queue.py:101` swaps `P×tail_norm`
into exactly that slot). The other 0.90 are **pre-filter scores** — and every candidate being ranked
has *already passed* those same filters as hard pass/fail gates. So the final ordering is 90%
"how strongly did this clean signal pass hygiene/novelty/diversity checks" and 10% "will it promote."

**Two learned steering points, not one.** The per-config predictor above is the *ranking* lever. The
*enumeration* lever is the **yield map**: hierarchical Beta(1,50)-smoothed component-rate posteriors
per cell — `(hypothesis, directional, dte_bucket)` + cohort (D182) + regime-gate (D183) + underlying
class/name (D106) — that re-weight which cells get sampled (`feedback/rejection_weights.py`,
`enumeration/sampler.py`). Diversity is enforced separately by a greedy-Jaccard diversifier with
per-hypothesis (D103) and per-arm (D136) floors (`ranking/diversifier.py`).

**MLOps.** A daily 05:00 timer (`forge-ranker-eval.timer`, `scripts/daily_ranker_eval.sh`) retrains
both heads, scores them in **shadow** (post-submission, telemetry-only, fails safe to 0 rows —
`shadow.py`), and appends a **consecutive-PASS streak** to `~/forge_data/ranker_eval/*.jsonl`. The
loader serves the **newest** artifact matching a target (`load_latest_robustness_model(..., target=)`).

---

## 2. Top findings & recommendations — prioritized

Each: **what · evidence · why it matters · fix · effort**. Tiers are effort×leverage, not importance.

### Tier 1 — cheap, high-leverage, low-risk (start here; several directly validate the just-shipped D193)

**B1. Diagnose whether the D193 quality lane actually earns its keep (the product may be redundant).**
- *What:* `P(component)` and the wf_p25 ridge are trained on the **identical ~85-feature vector** and
  on overlapping populations, predicting correlated targets (clearing the gate ↔ downside robustness).
  Two models on the same inputs can be near-redundant — "you can't squeeze the same orange twice."
- *Why:* You flipped the lane ON yesterday. Before building on it, confirm `P×tail_norm` ranks
  *better than `P` alone* — otherwise the lane adds complexity and a second overfitting surface for
  little lift.
- *Fix (one afternoon):* (a) Spearman corr between the two heads on shadow rows; (b) ablation —
  realized component/promotion lift of ranking by `product` vs `P-alone` vs `tail_norm-alone`. If
  product ≈ P-alone, the lane is buying little; if product ≈ tail_norm-alone, P is being dominated.
- *Sources:* Sculley et al. 2015 (correction cascades); QuantConnect meta-stacking critique. *Effort: S.*

**B2. Revisit the 0.10 prior weight — the promotion predictor is plausibly under-leveraged.**
- *What:* The only term trained on *realized promotion outcomes* carries 0.10 of the sort; 0.90 is
  pre-filter hygiene that has already been enforced as pass/fail gates upstream.
- *Why:* If the job of ranking is to surface the most promotable configs first, the predictor that
  models promotability should plausibly dominate the *ordering*, with hygiene/novelty driving the
  *diversifier* (which already exists separately). Even a perfect `P(component)` can only move the
  composite by 0.10 today.
- *Fix:* Shadow-A/B the prior weight (e.g. 0.10 → 0.3/0.5/0.7) and measure realized promotion-yield
  of the resulting top-N. This is a learning-to-rank question; don't assume — measure. Keep the
  diversifier as the diversity mechanism so a higher prior weight doesn't collapse variety.
- *Sources:* Liu 2009 (LTR families); Burges 2010 (proxy-loss ≠ ranking metric). *Effort: S–M.*

**B3. Calibrate `P(component)` and make calibration a tracked, gating metric.**
- *What:* You already *measure* calibration (Brier + reliability table, `evaluation.py:65`) — better
  than most — but never *act* on it: no recalibration step, no calibration-based promotion gate, no
  ECE-trend over time, and the streak metric (rank-IC / AUC) is **blind to calibration**.
- *Why:* The moment you **multiply** `P` by anything, calibration becomes load-bearing: a sort is
  invariant to any monotone warp, but a **product is invariant only to affine** transforms — so
  miscalibration of `P` leaks directly into the final ordering (Zadrozny–Elkan's exact result).
  Heavily-regularized logistic systematically shrinks probabilities toward the base rate.
- *Fix:* Add a held-out **Platt** scaling step (safe for pure-Python + modest calibration sets;
  isotonic only if >~1000 held-out positives); track Brier (decomposed) + reliability + **ECE** over
  time; make `P(component)` eval co-primary on calibration, not just AUC/IC.
- *Sources:* Zadrozny & Elkan 2001 (ICML); Guo et al. 2017; Kull et al. 2017 (beta calibration);
  Niculescu-Mizil & Caruana 2005. *Effort: S–M.*

**B4. Replace `sigmoid(ridge)` with a principled magnitude (two-part / hurdle form).**
- *What:* `sigmoid(ridge_prediction)` is a Bernoulli-posterior squashing with an arbitrary
  location/scale (set by the intercept + sigmoid gain) bounded to (0,1) regardless of the true Sharpe
  scale — it is **not** a conditional magnitude, and its nonlinear warp is exactly what breaks the
  expected-value ordering inside the product.
- *Fix:* The decision-theoretic combination is `E[Y|x] = P(Y>0|x) · E[Y | Y>0, x]` — a probability
  times a **conditional magnitude**. Use the ridge's native-scale prediction inside an explicit value
  formula: `prior = P(component) · g(wf_sharpe_p25)` with `g` a scale-meaningful monotone transform
  (ideally `E[wf_p25 | clears]`), not a free-gain sigmoid. Pairs with B1/B3.
- *Sources:* Belotti et al. 2015 (`twopm`); Mullahy 1986; Elkan 2001 (cost-sensitive). *Effort: M.*

### Tier 2 — promotion & validation discipline (medium effort, real risk-reduction)

**B5. Replace the ad-hoc "3 consecutive PASS" streak with a paired, significance-based gate.**
- *Evidence:* 0.5³ = **12.5%** false-promotion under the null (looser than α=0.05; you'd need k≥5 for
  ~0.05). The §8.6 lane PASS is an **absolute** `Spearman ≥ 0.30` (PROVISIONAL in
  `ranker_model_cmd.py`) — *not* incumbent-relative and *not* significance-tested — and it is **pooled
  across daily models**, so "3 checkpoints" aren't 3 clean looks at one challenger. STATUS records the
  D193 flip as *"operator overrode the 3/3 gate"* — so even the heuristic didn't bind.
- *Fix:* Gate on a **paired (challenger − incumbent)** per-checkpoint statistic with a
  **confidence-sequence / SPRT / e-value** (explicit α + a minimum effect size); stop pooling across
  artifacts; until then, treat the streak honestly as telemetry, and log overrides as reviewed
  exceptions.
- *Sources:* Wald (SPRT); Johari et al. (always-valid inference); Howard et al. 2021 (confidence
  sequences). *Effort: M.*

**B6. Add drift / performance-decay monitoring; move retrain from blind-calendar to trigger-based.**
- *Evidence:* Daily refit on a **low-SNR, non-stationary** label is the canonical noise-chasing case,
  and there is currently **no** feature-drift (PSI/JS), label/prior-shift, or IC-decay monitor. On the
  ML Test Score the *Monitoring* category (which **caps** the total via min-aggregation) is ≈0.
- *Fix:* PSI (Lewis 0.1/0.25) or Jensen-Shannon on the feature vector per checkpoint; a label/prior
  shift check; Page-Hinkley/ADWIN (or CUSUM) on the *paired* IC. Keep daily *training*, but gate on
  forward improvement + retrain-on-drift rather than unconditionally adopting the newest artifact.
- *Sources:* Gama et al. 2014 (concept-drift survey); Huyen 2022; Breck et al. 2019 (ML Test Score).
  *Effort: M.*

**B7. Address the censored-feedback / selection-bias loop.**
- *Evidence:* Both models train on verdicts of configs **Forge itself selected**, and the tail eval is
  further restricted to verified-coverage rows — a doubly-selected, missing-not-at-random sample the
  model itself shapes (a textbook direct feedback loop). The exploration floors mitigate but don't
  correct it; "pooling inverts mr vs trend" and "verified-coverage-only" are *symptoms* of this.
- *Fix:* Off-policy correction (IPS-style propensity weighting on submission probability, clipped away
  from zero) **or**, simpler, periodically submit a small **randomized exploration holdout** to obtain
  unbiased labels. Keep splitting all IC analysis on `honest_regime_coverage_row` (already done).
- *Sources:* Sculley et al. 2015; Joachims et al. 2017 (unbiased LTR); Bottou et al. 2013. *Effort: M.*

**B8. Settle effective-vs-nominal trial counting with Crucible; standard configs report no breadth.**
- *Evidence (verified):* `crucible_contracts/models.py:357` — `search_n_trials: int | None = None`;
  the **standard submitter never sets it** (only the retired meta-king did). The field's own doc says
  Crucible "folds it into the single-config DSR `n_trials`." So Forge's enumerate→filter→rank
  selection intensity is **not reported** to the Deflated-Sharpe gate for the production stream.
  Separately, even if reported, grammar-correlated configs mean **effective N ≪ nominal**, so a raw
  count would **over-deflate**.
- *Why it's nuanced (not a clean bug):* Crucible owns the gate; CPCV/WF are OOS and partially
  compensate; and the multiple-testing *magnitude* is genuinely contested (over-deflation kills real
  edges — Hou-Xue-Zhang 2020 vs Jensen-Kelly-Pedersen 2023 vs Chen 2024). So the move is **measure +
  coordinate**, not "crank up N."
- *Fix:* A Crucible handoff to (a) decide whether/how the generation funnel's breadth should be
  charged, (b) if so, estimate **effective N via strategy clustering (ONC / correlation eigenstructure)**
  per López de Prado 2019, and (c) pin the accounting boundary (per-batch vs cumulative campaign —
  Forge is uniquely positioned to track the cumulative honest count).
- *Sources:* Bailey & López de Prado 2014 (DSR); López de Prado & Bailey 2021 (False Strategy
  Theorem); López de Prado 2019 (multiple-testing crisis). *Effort: M (mostly coordination).*

### Tier 3 — generation quality (bigger lifts; one gated on B8)

**B9. Make the cell allocator uncertainty-aware (Thompson/UCB) instead of base-rate + flat floors.**
- *What:* You already maintain a per-cell **Beta posterior** (D105). Use it: Thompson = draw a sample
  from each cell's Beta and allocate proportionally; UCB = mean + c·posterior-sd. This explores
  high-variance, under-sampled cells *automatically* and implements the optimizer's-curse shrinkage
  remedy more principledly than a hard 0.05 floor. Near-zero new infrastructure; deterministic with a
  seeded draw.
- *Sources:* Auer et al. 2002 (UCB1); Chapelle & Li 2011 (Thompson); Smith & Winkler 2006
  (optimizer's curse). *Effort: S–M.*

**B10. Promote structural diversity from a *floor* to an *objective* (attack the 76% trend monoculture
at the source).** The successful generation-time-diversity systems make structural novelty a *search
objective* (PCA-QD, GFlowNet reward-proportional sampling), which beats post-hoc filtering by not
wasting budget on near-duplicates. This stays **structural** (indicator/hypothesis distance) and is
fully consistent with D186 (return-decorrelation stays at assembly). *Sources:* AutoAlpha 2020;
AlphaSAGE 2025; contrast AlphaGen 2023. *Effort: M.*

**B11. Turn the yield map into a true illuminator: keep & mutate a bounded per-cell elite archive.**
- *What:* Today a config that clears the gate is **submitted and forgotten** — Forge re-derives only an
  aggregate cell weight, discarding the actual high-performing genome it could perturb. Canonical
  MAP-Elites keeps the best solution per cell and **mutates it** to find neighbors; that is the engine
  of quality improvement Forge's bandit-reweighter lacks. This is the biggest generation-side *quality*
  upside and directly fills thin cells (mr, ranging complements) instead of waiting for a floor to hit
  them.
- *Gate:* **Ship after B8.** Mutating elites *increases* effective N and would worsen
  overfitting-by-search if the trial count is still understated. Keep it a *bounded, descriptor-honest*
  archive, not unbounded illumination. Seeded mutation keeps rule #6.
- *Sources:* Mouret & Clune 2015 (MAP-Elites); Fontaine et al. 2020 (CMA-ME); de Witt & Pakkanen 2026
  (first MAP-Elites for execution — and its sparse-cell overfitting caveat). *Effort: L.*

**B12. Institutionalize a per-cell "ceiling-vs-coverage" telemetry flag.** You made the *correct*
representation-vs-search call for long-options *manually* (flat CPCV ceiling across v9→v22 ⇒ grammar,
not more search). Generalize it: per cell, flag empty/weak-due-to-low-sampling (→ explore) vs
flat-ceiling-under-adequate-sampling (→ representation limit / grammar candidate). Turns the most
expensive decision Forge makes into a data-driven trigger. *Sources:* Mouret & Clune 2015 (coverage);
Lehman & Stanley 2011 (deception). *Effort: M.*

### Tier 4 — the strategic throughline (no code; decision-framing)

**B13. The learned systems optimize *efficiency within a capped space*; the quality *ceiling* is the
grammar.** The recurring empirical fact — 0 of ~7,566 honest single-config CPCV values reach 1.5,
flat across 15 grammar iterations — is the textbook signature of a **representation** wall, not a
search/ranking wall (and your Path-C-as-last-resort call is correct on exactly this evidence). No
amount of better ranking, calibration, QD, or trial-counting manufactures edge the long-options
grammar can't express. **Implication:** the Tier 1–3 work is worth doing (it raises realized yield,
honesty, and compute-efficiency, and de-risks D193) — but the largest "build higher-quality
strategies" lever remains *representational* (spreads / defined-risk structures / Path C), which you
have deliberately held. Worth periodically re-pricing that hold against the now near-exhausted
in-scope levers. *Sources:* Allen & Karjalainen 1999; Sullivan-Timmermann-White 1999 (the honest
generate-and-test ceiling reproduced).

---

## 3. What you're already doing right (do **not** "fix")

- **Determinism + reproducibility:** content-addressed (sha256) artifacts; **train/serve parity by
  construction** (one `extract_features().as_dict()` path, pinned by a round-trip test = Zinkevich
  Rule #32); the whole loop deterministic. The H-3 cross-restart determinism gap from `AUDIT.md` was
  **largely closed by D085** (`mint_batch_id` now folds `enumeration_inputs_hash`); that audit line
  reads stale now.
- **Honest, multi-metric eval:** AUC vs incumbent, precision@K, **Brier + a calibration table**, and a
  Spearman that returns `None` (not a fabricated 0) on degenerate windows. Above-average.
- **Linear/ridge under low-SNR is the peer-reviewed consensus** (Gu-Kelly-Xiu 2020; Kozak-Nagel-Santosh
  2020). The determinism constraint costs little here — the dominant *signals* are linearly
  identifiable; only *interactions* are left on the table (capturable with hand-engineered interaction
  features, deterministic, no numpy).
- **A genuine no-op shadow + above-average champion/challenger** process (held-out forward window,
  revert-to-byte-identical kill switch).
- **The robustness target is well-chosen:** `wf_sharpe_p25` (a downside/floor percentile) is endorsed
  by the 2026 robust-objective literature (Pardo plateau; CVaR/coherent-risk; GT-Score 2026's +98%
  generalization). *Caveat:* `wf_sharpe_p10` is statistically fragile at ~10–20 folds (≈ the minimum) —
  keep it a diagnostic guardrail, never a learned target or hard cutoff.
- **Decorrelation deferred to assembly (D186)** matches the alpha-mining mainstream (AlphaGen,
  AlphaForge, gplearn) and your own per-pair experiment — correct, not a shortcut.
- **Beta-smoothing of cell yields** is, structurally, the optimizer's-curse shrinkage remedy.
- **Delegating CPCV/WF/DSR to an independent authority and running *both* CPCV and WF** is the right
  hedge against each method's blind spot.

---

## 4. Cross-cutting audit item (measurement integrity, largely Crucible-side)

**Options point-in-time / leakage.** No cross-validation Crucible runs can catch *feature-level*
look-ahead — purge/embargo only neutralize label/serial overlap. The trap-prone constructs are exactly
the ones in play: **`iv_rank` (percentile-over-window), `rv_rank`, regime labels, any IV/RV/VIX-derived
signal, `days_to_opex`**. The documented impact of a full-sample vs trailing percentile is **15–30%
Sharpe inflation**; for thin long-vol (VRP) edges, a mid-price fill or full-sample percentile can
manufacture the *entire* apparent edge. If those features leak, the `wf_p25`/component labels Forge
trains on are inflated → garbage-in for every model above. *This is mostly Crucible/feature-cache
territory* (Forge consumes gate outputs), but it's high-value to confirm each such feature is strictly
trailing/as-of and that Crucible's embargo ≥ the longest option-feature lookback. Worth a named,
tested invariant. *Sources:* Kapoor & Narayanan 2023 (leakage taxonomy); Dobrowolski 2024 (VRP
percentile leak). `iv_rank` is load-bearing (live since D031, ~3998 runs); `INDICATOR_THRESHOLDS.md`
is stale (pre-D031) — so it warrants a fresh look.

---

## 5. Minor precision corrections (not flaws)

- **It's stacked generalization (Wolpert 1992), not meta-labeling (López de Prado ch.3).** Both heads
  predict the outcome directly, not the *correctness of a primary directional call*. Cite Wolpert as
  the pedigree; this redirects you to stacking best-practice (out-of-fold training between stages —
  worth confirming the two heads are trained on held-out-from-each-other data).
- **Stop treating low train R² (~0.23) as a virtue.** It's a fine *symptom* of regularization, but
  "low fit is good" is contested (the Virtue-of-Complexity debate: Kelly-Malamud-Zhou 2024 vs
  Nagel 2025). Report **OOS** R²/IC + calibration, not train R².
- **Feature importance:** with ~85 correlated features, prefer **conditional-permutation MDA** over
  MDI; a model-fingerprint check quantifies whether a (deterministic, monotonic) GBM would buy
  anything over linear.
- **Add top-of-list metrics** (precision@N / NDCG@N at the submission cutoff) — you act on the top of
  the ranking, but rank-IC weights the whole distribution equally.

---

## 6. Suggested sequencing

1. **B1 + B3** (diagnose the D193 product + start measuring/curing calibration) — validates yesterday's
   flip and is prerequisite to trusting the blend.
2. **B2** (shadow-A/B the 0.10 weight) — possibly the single highest realized-yield lever, cheap to test.
3. **B4** (principled combination) — once B1/B3 say the lane is worth keeping.
4. **B5–B7** (gate, drift, feedback-bias) — promotion discipline; can proceed in parallel.
5. **B8** (effective-N with Crucible) — coordination; unblocks B11.
6. **B9 → B10 → B11 → B12** (generation: bandit→uncertainty→diversity-objective→elite-archive→coverage).
7. **B13** (re-price the Path-C hold) — periodic operator decision.

All Tier-1/2 items are auto-tightening or telemetry (Rule #4 clean), deterministic (Rules #6/#8), no
LLM (Rule #5), and the existing `--quality-rank` / flag pattern makes them revertible to byte-identical.

---

## Appendix — load-bearing citations (HIGH-confidence unless noted)

- **Calibration & combination:** Zadrozny & Elkan, ICML 2001; Elkan, IJCAI 2001; Guo et al., ICML 2017;
  Kull et al., AISTATS 2017; Niculescu-Mizil & Caruana, ICML 2005; Belotti et al., *Stata J.* 2015 (two-part).
- **Learning-to-rank:** Liu, *FnT IR* 2009; Burges, MSR-TR-2010-82; Poh et al., *JFDS* 2021 ("3×" is one
  un-deflated backtest — directional only).
- **Low-SNR modeling:** Gu, Kelly & Xiu, *RFS* 2020; Kozak, Nagel & Santosh, *JFE* 2020; Kelly, Malamud
  & Zhou, *JoF* 2024 vs Nagel 2025 / FEDS 2025-089 (contested).
- **Validation / overfitting:** López de Prado, *AFML* 2018 (CPCV, purge/embargo, MDA); Bailey & López
  de Prado, *JPM* 2014 (DSR); López de Prado & Bailey, *Amer. Math. Monthly* 2021 (False Strategy
  Theorem); Bailey et al., *J. Comp. Finance* 2017 (PBO/CSCV); Harvey, Liu & Zhu, *RFS* 2016 (t>3.0);
  López de Prado, *JFDS* 2019 (effective-N / ONC); Arian, Norouzi & Seco, *KBS* 2024 (CPCV beats WF on
  PBO); Bergmeir, Hyndman & Koo, *CSDA* 2018.
- **Robust targets:** Rockafellar & Uryasev 2000 (CVaR); Artzner et al. 1999 (coherent risk); Pardo
  2008 (WF efficiency / plateau); Sheppert, *JRFM* 2026 (GT-Score).
- **Leakage:** Kapoor & Narayanan, *Patterns* 2023; Dobrowolski 2024 (VRP percentile leak).
- **MLOps:** Sculley et al., NeurIPS 2015 (hidden tech debt / CACE / correction cascades); Zinkevich,
  "Rules of ML"; Huyen, *Designing ML Systems* 2022; Breck et al., MLSys 2019 (ML Test Score);
  Wald (SPRT); Howard et al. 2021 (confidence sequences); Joachims et al., WSDM 2017 (unbiased LTR).
- **Quality-diversity / search:** Mouret & Clune 2015 (MAP-Elites); Fontaine et al. 2020 (CMA-ME);
  Lehman & Stanley 2011 (novelty/deception); de Witt & Pakkanen 2026; Auer et al. 2002 (UCB);
  Chapelle & Li 2011 (Thompson); Smith & Winkler 2006 (optimizer's curse).
- **Alpha mining:** Kakushadze 2016 (101 Alphas); AlphaGen (KDD 2023); AlphaForge (AAAI 2025); AutoAlpha
  2020; Allen & Karjalainen, *JFE* 1999; Sullivan, Timmermann & White, *J. Finance* 1999.
