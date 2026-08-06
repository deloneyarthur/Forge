# Scoped conditioning levers (D157 reversal): joint/AND-gate + the Q41 realized-vol cheapness gate

> **STATUS (2026-06-24):** PARTIALLY LANDED. The realized-vol cheapness gate (Lever B) was refined to `rv_rank` [[D161]], cleared the hurst-overlap gate [[D164]], and SHIPPED in grammar v22 [[D167]]/[[D170]] (a quality knob, not a promotion unlock). The AND-gate (Lever A) was DE-PRIORITIZED [[D161]] and not built. Historical record below.

Status: **SCOPING 2026-06-15 ([[D159]]) — both change surfaces mapped, no build.** The two cheapest of the
untried in-scope levers the operator un-held at [[D157]] (this session keeps the enum/grammar lane). Sibling
to the trend-book cheap-IV lever ([[D158]], `momentum-cheap-iv-conditioning.md`); supersedes Thread 2 of
`path-a-rich-conditioning.md` (un-held by D157) for the actionable build. Relates: [[D156]] (the trade-count
tension, still binding), [[D150]] (the `iv_rank` mr sparseness this targets), Q41 (`OPEN_QUESTIONS.md`).

> **Posture ([[D157]]): RUN/measure these, don't decline on a prior.** "You can't call long-options exhausted
> on levers you never ran." Expectations stay calibrated-low and the [[D156]] caveat still binds — more
> conditioning → more selective → fewer trades → fights the §5 trade-count prefilters + the §8.7 CPCV
> trade-count penalty — so each lever must be **measured** (production-grounded or shadow; offline
> `enumerate`/`prefilter` is demo-registry-ungrounded, [[D156]]), not inferred. No threshold/gate change to
> Crucible's §8.7 bar (hard rule #3). Path C stays HELD; the standalone §8.7/1.5 criterion stands.

> **✅ HURST-OVERLAP GATE CLEARED — BUILD JUSTIFIED ([[D164]], `../Crucible/docs/handoffs/FORGE_mr_rv_hurst_overlap_response.md`).** The pre-build gate the [[D161]] banner set is answered **YES, and stronger than asked.** On the era-C mr sleeve (49 comps / 9,930 trades, 94.9% joint coverage): **(i) independent** — `Spearman(hurst, rv_rank) ≈ −0.036`, hurst-pass rate identical (16.5%) across `rv_rank` quintiles (the redundancy hypothesis is refuted at the cross-tab); **(ii) the gradient survives the hurst control** — cheap−rich per-trade Sharpe **+0.142** *inside* the hurst-passing subset vs +0.114 full-sleeve (`survives_ratio 1.25`); **(iii) `rv_rank` DOMINATES `hurst`** — in the 2D double-sort `rv_rank` carries a strong Sharpe gradient inside every hurst stratum (+0.094/+0.157/+0.096) while `hurst` carries **none** inside any `rv_rank` stratum (−0.036/−0.035/−0.034, flat-to-inverted). **⇒ Build the v22 `rv_rank`-LOW MR conditioner (the R1 edit is justified).** Two build-design refinements from the answer: **(a) prefer/replace, don't stack** — hurst earns ~zero marginal MR quality once `rv_rank` is in, so carrying both buys nothing and costs grammar complexity (the minimal form is *add `rv_rank` to R1's accepted set*; biasing the sampler toward it over hurst for new mr configs is the go-forward economy call — operator's). **(b) On CONFLUENCE** — `rv_rank` is rank-coherent so it works on both, but mr's edge lives on confluence (rank caps at cpcv 0.729, "refuted on its own terms"). **Honest scope UNCHANGED — center/cap-efficiency, NOT the CPCV-p25 tail** (every `rv_rank` quintile is net-profitable; the tail is set by risk scale, [[D164]]/`design_regime_conditioned_construction.md` — selection can't move it). A quality knob, not a promotion unlock. The build is now **operator-gated only** (R1 rule edit = hard rule #1; v21→v22 bump = #10; loosening → `OPEN_PROPOSALS` = #4) — no empirical gate remains.

> **⚑ EMPIRICAL UPDATE FOLDED IN ([[D161]], `../Crucible/docs/handoffs/FORGE_mr_realized_vol_conditioner.md`).** Crucible's causal attribution of era-C mr (49 comps / 9,930 trades) resolves Lever B's open indicator choice: **use `rv_rank` (cheap REALIZED vol), not `vol_regime` or cheap-IV.** `rv_rank` shows a clean ~2.5× per-trade Sharpe gradient (cheap−rich **+0.095**, monotone step-down); `iv_rank` is weak (+0.041); `iv_minus_rv` inverts (raw-decimal artifact). Two corrections to §2: **(i)** `rv_rank` is **rank-coherent** (`rank_per_name_coherent=True`, bar-only) → works on BOTH mr's rank genomes AND confluence — **resolving the "pinned to trend R2" worry** (it's general-purpose, and a structural edge over the rank-EXCLUDED cheap-IV gates). **(ii)** Honest scope: every vol-quintile is net-profitable, so `rv_rank`-gating adds **no standalone PnL** — it concentrates mr into ~2.5× higher-Sharpe entries → a per-trade-quality / cap-efficiency lift to the book **CENTER**, **not** the CPCV-p25 **tail** (the binding wall). **A quality knob, not a promotion unlock.** **Gate before build:** Crucible offered the **hurst-overlap test** (does `rv_rank` add *beyond* v21's existing hurst mr gate, [[D150]]?) — relay it first (`PROMPT_CRUCIBLE_MR_RV_RANK_HURST_OVERLAP.md`); build only if it adds. The §2 R1-edit requirement still holds (`rv_rank` is not in R1's accepted set). **Lever A (AND-gate) DE-PRIORITIZED:** the momentum mirror (`FORGE_momentum_cheap_iv_empirical_read.md`) finds the long book's residual lever is **portfolio regime-placement**, not more per-name entry gates (momentum+vol_event align on high-vol; momentum+mr are opposite-regime *complements* at the portfolio level) — so stacking more gates is the wrong direction.

## 0. The two levers, and the asymmetry that orders them

| | Lever A — joint / AND-gate | Lever B — Q41 vol-cheapness gate (mr) |
|---|---|---|
| **What** | sampler emits 2 of the ≤4 signals C3 allows; let it AND-compose a 2nd/3rd regime gate per entry | give `mean_reversion` a denser cheap-vol gate — **`rv_rank`** (Crucible-validated, [[D161]]; `vol_regime` alt) — vs the sparse `iv_rank` ([[D150]]) |
| **Grammar bump?** | **No** — sampler-only (C3 already allows 4; pools are registry-derived). But re-pins the golden sampler sequence (hard rule #6 deliberate change) | **Yes** — requires an **R1 rule edit** (operator-owned, hard rule #1) + bump v21→v22 + loosening (hard rule #4 → `OPEN_PROPOSALS`) |
| **Trade-count effect** | **NEGATIVE** — more gates → fewer trades → *fights* the binding constraint ([[D156]] headwind) | **POSITIVE** — a denser gate → more entries → *fixes* the [[D150]] sparseness that sank mr's `iv_rank` gate |

**The decisive asymmetry:** the two levers pull opposite ways on the constraint [[D156]] identified as binding.
Lever A is a probe *of* that constraint (does a joint pocket have enough IC to survive the trade-count/DSR
hit?); Lever B *relieves* it (a denser gate is the breadth fix the thin 19-component mr arm needs). **⇒
sequence Lever B first** — it is lower-risk, trade-count-positive, and repairs a known defect; Lever A is the
higher-variance probe.

## 1. Lever A — joint / AND-gate conditioning

**The gap (grounded):** a config attaches **one** regime gate, so it cannot say *"enter long when momentum>0
AND IV-cheap AND not-pre-earnings."* Joint conditioning is the genuinely un-swept dimension `path-a` Thread 2
flagged (`sampler.py` confirmed: one regime gate per entry).

**Change surface (verified, line-cited):**
- **C3 already permits ≤4 signals** (1 directional + ≤3 supporting): rule `grammar.yaml:469-481`, validator
  `predicates.py:65-105`, narrative `GRAMMAR.md:149-157`. So the cap is not the blocker.
- **The sampler emits only 2(-3) today:** 1 directional + 1 regime_filter (`sampler.py:519-534`), plus an
  optional X1/X2 chain confluence signal (`:550-558`). The single regime is picked once from
  `_compatible_regimes()` (`sampler.py:651-676`, selection ~`:824`).
- **Combiner:** `CombinerSpec(type="confluence", direction_strategy="k_of_n", k=1)` (`sampler.py:609`). To
  require ALL gates fire (true AND / joint conditioning), the sampler emits N regime gates and sets `k`
  accordingly. **This is the implementation question to settle in the build:** stacked `regime_filter` signals
  (each an independent necessary gate) vs. raising the confluence `k` — pick the one whose runtime semantics
  Crucible's backtester interprets as conjunction. (Verify against the contract before coding.)
- **No `grammar.yaml` byte change.** Regime pools are registry-derived (`search_space.py:200-210`), not
  grammar-authored; emitting more of them is enumeration policy (D150/D151 class). **But** it is a deliberate
  enumeration-sequence change → **hard rule #6 re-pin**: `tests/invariants/test_phase2_invariants.py:39-50`
  plus ~7 sampler golden/cold-start tests (`tests/unit/test_enumeration/test_sampler.py`) and
  `tests/integration/test_batch_reproducibility.py` must be re-baselined deliberately. Rule #6 is preserved
  (same `(grammar_version, registry_hash, seed)` → same sequence *after* re-pin); the sequence simply changes.
- **Dead-intersection pruning already exists:** `SignalCorrelation` (tier 7, Jaccard activation-overlap,
  `prefilters/signal_correlation.py`) drops empirically-redundant gate pairs; `ExpectedTrades`
  (`prefilters/expected_trades.py`) drops the too-sparse conjunctions. The latter is the **binding** filter.

**EV / risk:** the [[D156]] headwind is the whole story — every added gate narrows entries, so the cohort
either gets prefilter-rejected (too few trades) or clears with a larger effective-N that makes §8.7 DSR deflate
harder (correct behavior, M4). Lever A pays off only if a joint pocket carries enough true IC to survive both.
**Measure:** AND-gated cohort's prefilter pass-rate AND the CPCV-p25 distribution of survivors vs the
single-gate baseline, on a deployed v-cohort (funnel-compare).

## 2. Lever B — Q41 realized-vol cheapness gate for mean_reversion

**The gap (Q41, `OPEN_QUESTIONS.md`; severity LOW):** Forge's generator leaves the orphaned `volatility`
family largely unreachable — `vol_regime`, `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol`, `atr_pct`,
`amihud` are live (threshold specs in `indicator_thresholds.py`) but in **no** hypothesis enumeration pool.
And mr's designated "buy-cheap-vol" gate `iv_rank` fires too sparsely to survive the prefilter ([[D150]]
de-weights it 3:1), so the thin mr arm (19/309 components) is starved of a working cheap-vol conditioner.

**Change surface (verified, line-cited) — and a correction to D157's framing:**
- **`vol_regime` is live but unreachable:** spec `indicator_thresholds.py:180-183` (regime classifier
  0=high / 1=low / 2=extreme vol; `regime_range=(0,2)`, op `<` = fire in low-vol; horizon 20,
  `signal_horizon.py:180`); no enumeration path today.
- **CRITICAL — R1 is not `iv_rank`-exclusive, so this needs a rule edit.** R1
  (`mean_reversion_requires_iv_rank_gate`, validator `custom_predicates.py:816-857`) already accepts **any one
  of three** gates: `iv_rank` (≤50), `gamma_flip_distance_pct` ([[D107]]), `hurst` ([[D150]]). A config gated
  on `vol_regime` *alone* would therefore **fail R1** and never enumerate. Making `vol_regime` a standalone mr
  cheap-vol gate (the "denser than `iv_rank`" intent) means **adding it to R1** — an **operator-owned grammar
  rule edit** (hard rule #1) + version bump v21→v22 (#10) + a loosening → `OPEN_PROPOSALS` (#4). This corrects
  [[D157]]'s "sampler/pool edit, no bump" note: only the *supplementary* form (vol_regime stacked on top of a
  required R1 gate — which is just Lever A in disguise, and adds selectivity rather than relieving it) is
  no-bump. The denser-gate intent requires the bump.
- **Edits (R1-edit form):** constant + branch in `custom_predicates.py` (~288-307 constants, 816-857 validator);
  mr regime pool in `search_space.py` (~338-351); regime weighting `_MR_RANGING_GATES` in `sampler.py`
  (~107-114); `grammar.yaml` v21→v22 + archive; `GRAMMAR.md#R1` sync. R1's pass/fail *logic* is unchanged —
  only its accepted-gate set widens (no §8.7-bar touch, hard rule #3 intact).
- **Indicator choice (operator to confirm):** `vol_regime` (D157-named; a coarse 0/1/2 regime classifier —
  densest, but "low-vol regime" is a looser cheap-vol proxy than a percentile) vs **`rv_rank`** (realized-vol
  *percentile*, the tightest parallel to `iv_rank`'s IV-percentile — but it is already pinned to the trend R2
  pool, so reuse needs dual-hypothesis handling). I lean `vol_regime` per D157; flagging `rv_rank` as the
  semantically-closer "cheapness" gate.

**EV / risk:** this is the trade-count-**positive** lever — a denser gate gives the starved mr arm breadth
(parallels the T2 ranging-supply work), directly fixing the [[D150]] sparseness. The tradeoff: denser = less
selective, so it may dilute per-trade edge. **Measure:** does `vol_regime`-gated mr produce a viable cohort
(survives the prefilter where sparse `iv_rank` did not) with competitive CPCV-p25 vs the gamma/hurst-gated mr
baseline. The cleaner EV story of the two.

## 3. Gated sequencing

1. **Lever B first** (lower-risk, trade-count-positive). TDD red-first (`test_custom_predicates` R1-accepts-
   `vol_regime`; `test_search_space` mr-pool; `test_sampler` emission) → R1 edit + pool + weighting → bump
   v21→v22 + archive + `GRAMMAR.md#R1` sync → **loosening to `OPEN_PROPOSALS` via the approval flow** (hard
   rule #4; the machine-managed queue — not hand-authored) → emission proof (`enumerate_candidates` mix +
   `forge enumerate --summary`) → deploy ritual (`deploy.md`) → Crucible `funnel --compare v21 v22`.
2. **Lever A second** (the probe). TDD red-first → multi-gate sampler change + combiner-k decision → **re-pin
   the golden/determinism tests deliberately** (§1 list) → emission proof → deploy ritual → funnel-compare.
   No version bump, but enumeration-affecting → full ritual + kill-switch discipline.
3. **Batching note:** the two grammar-bumping levers in flight — Lever B's R1 edit and the trend lever's R2
   widening ([[D158]]) — can fold into a **single v22 bump** if the operator approves both, or ship v22/v23
   sequentially to keep funnel cohorts clean (the v20/v21 split precedent, [[D151]]).
4. **Measurement is the deliverable** (not the deploy): for each, the funnel-compare must report prefilter
   pass-rate AND survivor CPCV-p25 vs baseline — the explicit test of whether the added/denser conditioning
   beats the trade-count effect.

## 4. Relationship to the rest of the program

- **Lever A = `path-a-rich-conditioning.md` Thread 2**, un-held by [[D157]]; that doc's "is the probe worth the
  build" framing is answered (run it) — its banner now points here for the build.
- **mr warm-up** (the 3rd D157 lever — lift the [[D150]] `iv_rank` de-weight) is **subsumed by Lever B**:
  Lever B gives mr a *denser* gate, the better form of "make mr's cheap-vol gate fire enough to survive."
- **No new Crucible relay** — these are Forge-internal enumeration changes measured by funnel-compare; the
  operator's standalone-primary relay Q1 (`PROMPT_CRUCIBLE_OPTIONS_PRIMARY_STANDALONE.md`) already asks
  Crucible to prioritize these levers.
- **Thread 3** (learned conditioner) stays the operator's parallel models workstream ([[D155]],
  `generation-model-levers.md`), sequenced after these cheap sampler/grammar levers.

## 5. Artifacts / cross-references

- This scope: `docs/proposals/conditioning-levers.md` ([[D159]]).
- Un-held home of Lever A: `docs/proposals/path-a-rich-conditioning.md` (Thread 2).
- Sibling lever: `docs/proposals/momentum-cheap-iv-conditioning.md` ([[D158]], trend-book cheap-IV).
- Source: [[D157]] reversal; Q41 in `OPEN_QUESTIONS.md`.
