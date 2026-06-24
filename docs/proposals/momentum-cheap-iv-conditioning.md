# Condition the long trend/momentum book on CHEAP IV (Crucible ask) — scoped, operator-gated

> **STATUS (2026-06-24):** REFUTED / SHELVED — never built. Crucible's empirical read found trend cheap-IV gives no lift (mild inversion) → this D158 T1/T2 lever SHELVED [[D161]] (confirmed by the trend-enumeration-frontier-closed read [[D166]]). Historical record below.

Status: **SCOPING / HELD 2026-06-15 ([[D158]]) — change surface mapped, no build.** Operator chose
"scope the trend-side build" after the bottom-line assessment of Crucible's handoff
`../Crucible/docs/handoffs/FORGE_momentum_cheap_iv_conditioning.md`. Sits under [[D157]] (operator's D156-hold reversal — enum/grammar now un-held; this is the **trend-book**
lever, distinct from D157's mr-focused AND-gate / Q41 / mr-warm-up levers). Relates to: [[D156]] (the
now-reversed hold), [[D154]] (the in-house cheap-IV crater), [[D152]] (the exhaustion verdict), [[D131]] /
[[D135]] (the deliberate "regime use = None" deferrals this would reverse), Q34 (the R1-sibling gate
question). Sibling Crucible asks: `FORGE_long_options_exhaustion_consolidated.md`,
`FORGE_v21_mr_rank_arm_verdict.md`, `FORGE_dispersion_lite_iv_vs_index.md`.

> **✅ MOMENTUM RECOMMENDATION ANSWERED — frontier ~CLOSED ([[D166]], `../Crucible/docs/handoffs/FORGE_momentum_recommendation_and_inputs.md`).** Crucible's per-6-regime attribution of the trend sleeve (126k trades) settles the post-refutation question. **The trend enumeration frontier is ~closed.** The edge concentrates in **trending (+0.126) / high_vol (+0.103)**, is ~flat in **bear (+0.008) / ranging (+0.011)**, weak in bull. The *only* in-scope enumeration move is a **high-vol/trending regime quality tilt** — `momentum_252` (the attribution's signal; `returns_12m_skip1`/`rolling_sharpe` unlikely to differ) + a `vol_regime` HIGH or `market_state` trending regime_filter, swing_mid/long. **But every bucket is ~0.07–0.13 Sharpe → IC-bound; a tilt, not a lift, "probably not worth a grammar bump on its own."** No non-IV conditioner lifts it. **Regime-placement (the prior "residual lever") is REFUTED as a Forge move:** Crucible built+tested it (L2, [[D164]]) and uniform vol-target dominates it → **do NOT build any Forge emit-side regime plumbing** (no regime-tagged candidates / placement label / `SelectorSpec` regime hook); it's a Crucible construction question with no Forge role. **`*_rank` percentile-wraps (`iv_minus_rv_rank`/`iv_term_slope_rank`): offered-not-built, momentum use-case gone with the cheap-IV refutation → DECLINE** (leave unbuilt; flag only if another hypothesis needs a uniform-selectivity gate). **Registry is current** — the publisher is now 6-hourly (the [[crucible-registry-publisher-oneshot]] startup-only gotcha is **FIXED**), nothing shipped-but-unpublished. **Disposition:** the trend tilt is a declined low-EV option (batchable onto a v22 if ever wanted, not recommended standalone); the dominant arm's frontier is closed; the residual is **magnitude = a generation problem** (World-A), consistent with [[D165]]'s three-axis close.

> **⚑ EMPIRICAL RESULT FOLDED IN ([[D161]], `../Crucible/docs/handoffs/FORGE_momentum_cheap_iv_empirical_read.md`) — T1/T2 DE-PRIORITIZED.** Crucible ran the causal trade-attribution this scope named as the funnel-compare deliverable (era-C trend, 163 comps / **126,133 trades**): **cheap-IV conditioning does NOT lift the trend book — it mildly INVERTS** (`iv_rank` cheap−rich **−0.032**; the *rich*-IV entries are marginally best; every quintile ~0.08–0.11, IC-bound). Why: the directional net-debit book is dominated by the *move*, not the vol carry, so high-vol/trending regimes *help* it — Bakshi-Kapadia governs the pure-vol leg this book doesn't isolate. **So T1 (`iv_rank`) and T2 (`iv_minus_rv`/`iv_term_slope`) on trend are SHELVED** — the "no-lift → firms Path-C" outcome §5 anticipated has arrived. **T3 `iv_vs_index` survives separately** (a single-name SELECTION lens this attribution doesn't test). The long directional book's residual lever is **portfolio regime-placement** (momentum/vol_event for high-vol, MR for calm), not a per-name entry gate. Read §1–§6 as the now-shelved build plan, retained for the record.

> **EV is LOW by every assessment on file — read this as a defensible empirical *confirmation*, not a
> promotion path.** Crucible's own consolidated handoff rates `iv_term_slope` / `vix_term_slope` /
> `iv_minus_rv` "low-EV as long-only gates (edge is the short leg)." Our strongest in-house cheap-IV-
> conditioned long config — `iv_rank × days_to_opex` — already sits at WF 1.43 / **CPCV-p25 0.70**
> ([[D154]]). And [[D156]] reasoned the structural headwind: more conditioning → fewer trades → fights the
> trade-count prefilters + CPCV's low-trade-count penalty. The honest-era gross max CPCV-p25 is **1.40 < 1.5**
> and **IC-bound**, not cost-bound ([[D152]]). The prize is the thin 1.40→1.5 pocket on the trend book, on a
> *non-rank* genome — nothing more. This scope exists so the operator can decide that wager with the full
> change surface in hand.

## 0. What this is, and is NOT

- **IS:** a scoped, gated plan to widen `trend_continuation`'s R2 regime-gate pool so single-name
  *confluence* trend genomes can gate entry on cheap optionality (the handoff's ask), risk/cost-ordered into
  three tiers. Search-space exploration, hard-rule-6 framed — **no threshold/gate changes to Crucible's bar.**
- **IS NOT:** a build. No `grammar.yaml`, `custom_predicates.py`, `indicator_thresholds.py`, or `sampler.py`
  edit has been made. No version bump, no `OPEN_PROPOSALS.md` record, no deploy. (The T3 relay is now sent + answered, [[D160]].)
- **IS NOT:** a promotion path or a reopening of the exhaustion verdict. A clean no-lift result *firms*
  [[D152]] and points the operator at Path-C; it does not un-park anything.

## 1. The ask vs. the Forge-side reality

The handoff asks Forge to enumerate single-name `trend_continuation` (and `volatility_event`) **confluence**
genomes = a momentum directional + one or more cheap-IV regime gates, and to "activate the three dormant
conditioners." Its direction table is verified — **in Crucible's `src/optbt/features/`.** Forge-side, the
five named signals are not the uniform "built, published, unsampled" set the handoff assumes:

| signal | Forge-side status (verified) | gate-usable today? | in v21 pool |
|---|---|---|---|
| `iv_rank` | live R1 regime gate, `regime_range=(10,50)` op `<` (`indicator_thresholds.py:236-239`) | **yes** | **73/309 (~24%)** |
| `iv_minus_rv` | live ve **directional**; `regime_range=None` — regime use deferred [[D131]] (`:288-292`) | no | 0 |
| `iv_term_slope` | live ve **directional**; `regime_range=None` — regime use deferred [[D135]] (`:307-311`) | no | 1 |
| `vix_term_slope` | exists Crucible-side but `market_wide_by_design` (a *when*-gate, can't select names); [[D131]] upheld — **Crucible CONCEDED ([[D160]])** → dropped from T3 | no (out) | 0 |
| `iv_vs_index` | was a **stale export** (correctly grep-clean); now **published** in `registry_snapshot_2026-06-15T180258Z.json` ([[D160]]); `iv_structure`, rank-excluded → confluence-only, dir **LOW** | not yet (needs snapshot adopt + threshold spec) | 0 |

So only `iv_rank` is gate-usable now — and it is already well-sampled (and its best long config already
craters, [[D154]]). Two of the five are not wired Forge-side at all; the other two are *active as
directionals* but their **regime** use was deliberately turned off (§3). "Dormant conditioners" is inaccurate
Forge-side.

The empirical context is otherwise as the handoff states: `trend_continuation` is the dominant arm
(**202/309 = 65%** of v21 components; ve 88, mr 19), and the single highest CPCV-p25 component is exactly the
target shape — `trend_continuation / swing_long / confluence`, **cpcv-p25 1.219, non-rank.**

## 2. The change surface (verified, line-cited)

`trend_continuation`'s regime gate is governed by **R2** (`grammar.yaml:604-614`, validator
`custom_predicates.py:865-884`). Its pool is the python-side constant
`_R2_TREND_CONTINUATION_REGIME_INDICATORS = {adx, hurst, rv_rank, gamma_flip_distance_pct, market_state}`
(`custom_predicates.py:246-257`), assembled in `search_space.py:337`.

To add a cheap-IV gate the minimal edits are:

| edit | file:line | bump? |
|---|---|---|
| add id(s) to `_R2_TREND_CONTINUATION_REGIME_INDICATORS` | `custom_predicates.py:246-257` | **yes** (grammar-coupled pool, [[D131]]/[[D150]] precedent) |
| `grammar.yaml` version bump v21→v22 + archive + R2 `evidence_to_relax`/header note | `grammar.yaml` | **yes** (hard rule #10, ANY byte) |
| `GRAMMAR.md#R2` narrative sync | `docs/GRAMMAR.md` | (doc-sync hook) |
| set `regime_range` for `iv_minus_rv` (`None`→audited range) and `iv_term_slope` (`None`→audited range) | `indicator_thresholds.py:288-292, 307-311` | no (enumeration policy) — **T2 only** |
| `sampler.py` regime selection | `sampler.py:1113-1143` | **NO CHANGE** — it samples whatever is in the pool |

`iv_rank` already carries the correct regime spec (`regime_range=(10,50)`, op `<` = fire when IV-rank LOW =
cheap), so the T1 thresholds need no calibration. `iv_minus_rv` / `iv_term_slope` regime ranges must be
**probe-audited against the live feature cache** for ~10-50% selectivity ([[D131]]/[[D135]] precedent), not
hardcoded blind.

**Self-limiting safety property (decisive):** all three IV signals are `requires_symbol` →
`rank_per_name_coherent=False` → rank-excluded (`search_space.py:141-149`). Adding them to R2's pool can
therefore **only** produce *confluence* (single-name) genomes — on the rank arm the sampler will never pick
them, exactly as it never picks `gamma_flip_distance_pct` (already in R2's pool, also rank-excluded,
confluence-only). The rank arm is structurally untouched, and R2 still has `adx`/`hurst`/`market_state` to
satisfy the rank path. This is precisely the confluence-only attachment the handoff argues for, enforced by
machinery already in place. **C1** (no two same-family indicators) makes the three `iv_structure` gates
**mutually exclusive** — at most one cheap-IV gate per config (`custom_predicates.py:521-543`).

## 3. The deliberate decisions this reverses (must be revisited, not silently overridden)

The regime-gate-off state is not an oversight — it is recorded operator-owned intent:

- **[[D131]] (v17):** `iv_minus_rv` activated as a ve directional; *"Regime use deliberately NOT enabled — the
  R1-sibling gate question stays open (Q34 coda)."* Same entry: *"vix_term_slope deliberately NOT added to R2
  (validated for vol returns, not trend conditioning)"* — i.e. the exact use this handoff proposes for
  `vix_term_slope` was already considered and declined.
- **[[D135]] (v18):** `iv_term_slope` activated as a ve directional; *"Regime use deliberately None (the
  R1-sibling question stays open, the iv_minus_rv precedent)."*
- **Q34 (resolved 2026-06-10):** the R1-sibling question — whether the cheap-IV gate direction is right — was
  resolved **in favor of the cheap-IV side**: every MR template is net-debit at entry → net-long premium
  wants IV cheap → `iv_rank < threshold` is the evidence-supported direction. So the handoff's *direction* is
  consistent with resolved policy; what stayed deferred was the regime **wiring**, on orthogonality grounds,
  to *"re-open only on post-fix evidence."* This handoff (Crucible-initiated, post-fix) is plausibly that
  trigger — but enabling regime use is a deliberate reversal of D131/D135 and must be logged as one.

## 4. Staged tiers (risk/cost-ordered)

Each tier is an independent operator-gated increment; the operator can approve T1 alone, T1+T2, or all three.

- **T1 — `iv_rank` on the trend book (Forge-only, smallest reversal).** Add `iv_rank` to R2's pool. No
  threshold work (spec already correct). Cheapest real test of "does cheap-IV conditioning lift the *trend*
  confluence book?" Caveat: `iv_rank` is the signal whose best long config already craters ([[D154]]) — though
  that was a ve/`days_to_opex` config, not trend; T1 tests the trend cell specifically.
- **T2 — `iv_minus_rv` + `iv_term_slope` as regime gates (Forge-only, reverses [[D131]]/[[D135]]).** Set their
  `regime_range` and add to R2's pool. Adds the Goyal-Saretto (cheap-vs-realized) and Vasquez (term-slope)
  gates. Mutually exclusive with `iv_rank` per C1. **Crucible supplied the band audit ([[D160]], Q3):** pooled
  + per-name p10/25/50/75/90 + a selectivity→threshold map over 20 Tier-2 names. **Decision the build needs:**
  they are raw-decimal → one global band fires at name-dependent rates (2–4× spread), so either use per-name
  bands (from the JSON, immediate) OR ask Crucible to ship the **percentile-wrap** `iv_minus_rv_rank` /
  `iv_term_slope_rank` (cheap; reuses `iv_rank`'s engine — the right shape for *gate* use). This converges with
  the [[D159]]/Q41 finding that percentile gates fire uniformly where raw/sparse ones don't. (`iv_term_slope`
  foot-gun: pair with `days_to_earnings`.)
- **T3 — `iv_vs_index` only (cross-system, now UNBLOCKED — [[D160]]).** The relay is answered: `vix_term_slope`
  is **dropped** (Crucible conceded [[D131]] — `market_wide_by_design`, a *when*-gate that can't select names,
  no trend evidence), so T3 collapses to one signal. `iv_vs_index` was a stale export, now **published**
  (`registry_snapshot_2026-06-15T180258Z.json`); `requires_symbol`/rank-excluded → confluence-only (same
  self-limiting property), dir **LOW** = cheap vs market, single-names-only (inert on the index). **Remaining
  Forge-side:** adopt the new snapshot (registry change → likely a ritual restart, [[D104]]) + wire an
  `iv_vs_index` threshold spec in `indicator_thresholds.py` + add it to R2's pool → then a T1-class build.

## 5. Expected value and the two clean outcomes

The EV is low and the structural headwind ([[D156]]: conditioning → fewer trades → fights CPCV) applies to
every tier. The value is in the *decision the result enables*, not the arm:

- **No lift (the expected outcome):** the single-name net-debit book agrees with the index-level literature
  and our own `iv_rank` crater — cheap-IV conditioning does not lift the long leg toward 1.5. This **closes
  the long-options conditioning question empirically** on the dominant arm and *firms* Path-C's provability
  gate ([[D152]]), a stronger verdict than reasoning alone.
- **Surprise lift (low probability):** the first evidence that our single-name net-debit book beats the
  index-level long-side pessimism — i.e. that cheap-IV (not high-vol) conditioning is where a residual long
  edge lives. That would be a cheap in-scope arm and a genuine update.

Either way the result is informative and the cost is bounded. A cheaper *read-only* proxy exists and should
run first regardless (see §6, step 0): characterize the 73 existing `iv_rank`-conditioned components — if
that slice already shows no CPCV-p25 lift, much of T1's answer is in hand before any bump.

## 6. Gated sequencing

0. **(Free, do first) Read-only confirmation.** Characterize the existing 73 `iv_rank` components' CPCV-p25
   vs the unconditioned book (snapshot `/tmp` per `investigate-live.md`). Extends [[D154]]. May moot T1.
1. **Operator approval of this scope** + choice of tiers.
2. **Loosening proposal → `OPEN_PROPOSALS.md` via the approval flow** (hard rule #4 — widening a regime pool
   is a *loosening*; it is structurally forbidden to write `grammar.yaml` directly). Awaits operator
   approval-marker. *(Not authored here — the file is a machine-managed queue; do not hand-write the record.)*
3. **T3:** relay SENT + ANSWERED ([[D160]]) — `iv_vs_index` unblocked, `vix_term_slope` dropped. T3's remaining
   gate is now Forge-side: adopt `registry_snapshot_2026-06-15T180258Z.json` (ritual restart) + wire its threshold spec.
4. **Build per the grammar-change ritual** (`docs/tasks/grammar-change.md`): TDD red-first (new
   `test_grammar`/`test_enumeration` cases; re-pin the golden sampler sequence deliberately) → pool +
   threshold edits → version bump v21→v22 + archive + GRAMMAR.md#R2 sync → emission proof
   (`enumerate_candidates` mix + `forge enumerate --summary`) → D-entry + STATUS.
5. **Deploy per `deploy.md`** (worktree build → full uncontended suite → commit → ritual restart → journal
   verify): expect a new cheap-IV-gated confluence trend cohort under v22.
6. **Relay v21→v22 to Crucible** for `crucible funnel --compare v21 v22` — the empirical read that resolves §5.

## 7. Artifacts / cross-references

- This scope: `docs/proposals/momentum-cheap-iv-conditioning.md` ([[D158]]).
- Contracts-gap relay: `PROMPT_CRUCIBLE_MOMENTUM_CHEAP_IV_REGISTRY.md` (T3 gate) — **SENT + ANSWERED** ([[D160]], `FORGE_momentum_cheap_iv_registry_response.md`).
- Parent exhaustion record: `docs/proposals/long-options-exhaustion-assessment.md`, `path-a-rich-conditioning.md` ([[D156]]).
- Source ask: `../Crucible/docs/handoffs/FORGE_momentum_cheap_iv_conditioning.md`.
