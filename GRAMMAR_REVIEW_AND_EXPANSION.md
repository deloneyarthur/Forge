# Forge — Grammar Review & Expansion Roadmap (deep research, 2026-06)

**Status:** research / findings · no code, grammar, or config changed · all expansions operator- (and
Crucible-) gated. **Companion to** `LEARNED_SYSTEMS_AND_GENERATION_REVIEW.md`, the parked
`docs/proposals/path-c-scope-expansion.md`, and `docs/proposals/long-options-exhaustion-assessment.md`.
**Method:** an exhaustive read of the live grammar (`grammar.yaml` v22, the 21 §3.5 rules, the 50+-indicator
registry) + four cited web-research pillars (option structure primitives; predictive signal families;
grammar/DSL design methodology), adversarially verified and confidence-tiered. This **validates and
enriches** the existing Path C dossier; it does not restart it.

---

## 0. Verdict

Forge's grammar *core* is best-practice and should not be touched — a valid-by-construction typed CFG with
deterministic enumeration and strong versioning is exactly what the literature prescribes, and it is *better*
than most alpha-mining systems. The "is the best grammar exposed?" question resolves into two expansion
dimensions, and — strikingly — **structure (Dimension A) and signals (Dimension B) point the same way**:
Forge is a **diversifying long-vol overlay** (WORLD_A §6.1), so its grammar should expand only toward
**net-long-vol, defined-risk structures** and **decorrelated / regime-gating signals**, and must
*structurally forbid* drift toward short-vol harvest — which an average-Sharpe-attracted enumerator is
magnetically pulled toward in *both* dimensions (credit/naked structures; seller-side surface signals). The
single highest-leverage grammar-v2 decision is a machine-checked **net-long-vol invariant** spanning both.
The edge-magnitude wall is *representational* (a single long leg pays the full variance-risk-premium "tide"),
so the ceiling-breaker is **defined-risk debit structures (Path C)**; signal adds improve component
selectivity *within* the cap. Crucially, every added primitive inflates the multiple-testing hurdle, so the
**effective-N "alpha budget" (Dimension C) is a prerequisite**, not an afterthought.

---

## 1. The unifying thesis — a *net-long-vol* grammar

Three independent findings collide on one design rule:

- **Structure (G1):** every high-Sharpe option structure (credit verticals, condors, flies, short
  strangles, ratios, risk reversals) earns its Sharpe by *selling* vol/VRP/skew — the **opposite risk
  factor** to Forge's long-vol overlay — and Sharpe *flatters* negative skew (Volmageddon: XIV −90% in one
  session). A Sharpe-maximizing enumerator will be *attracted* to exactly these and misclassify them as good.
- **Signals (G2):** the "the surface predicts the market" edges (VRP timing, VIX carry, dispersion, VVIX,
  put-skew) are overwhelmingly **seller-side premium harvests with severe negative skew** — the *wrong sign*
  for a long-premium book (consistent with the existing `INDICATOR_THRESHOLDS.md` skew note).
- **Forge's own identity + worst-quartile:** the binding constraint is the assembled pool failing
  CPCV-p25/worst-quartile OOS, and the worst quartile is **BEAR 2.39× / RANGING 1.33×** (regime_lift). Bear
  convexity is *kept* by long structures and *given away* by short ones; the ranging crater is filled by
  long-vega term-structure (calendars), not by selling premium.

**Design consequence:** make **"net-debit AND net-long-vega AND defined-risk"** a machine-checked grammar
invariant for any structure expansion, and **do not add seller-side surface signals as directional edges**.
One rule (structure) + one curation discipline (signals) keep the generator on the long-vol side of the risk
factor — and mirror Forge's existing "tighten freely, loosen only with approval" asymmetry (hard rule #4).

---

## 2. Current grammar — confirmed best-practice (do **not** change)

Grounded against the literature (citations in §5/appendix); these are *validations*, not change requests:

- **Constrained generation ≫ generate-then-reject.** Encoding the 21 rules so survivors are valid-by-
  construction is the strongest, best-quantified design finding in the field (constraints prune ~99% of the
  space / 2.5–3000× faster than rejection). Forge's whole premise is correct. *(arXiv:2508.00005.)*
- **Typed CFG = Strongly-Typed GP, the right backbone.** C2 (family↔hypothesis), the `equity`-forbidden rule
  (#7), S2/S3/C4 (role typing) are textbook STGP type restrictions expressed grammatically. *(Montana 1995;
  McKay et al. 2010.)*
- **Dimensional/units consistency by construction.** S4 (lookback-class↔DTE-bucket), P2 (DTE-window↔bucket),
  P3 (delta↔DTE-band) are exactly the dimensional-grammar discipline that "vastly improves performance" in
  symbolic regression. *(PhySO 2023; AI Feynman 2020; Brence et al. 2023.)*
- **Deterministic enumeration over a typed config — keep it; do NOT add a GE-style linear genome.** That
  sidesteps Grammatical Evolution's #1 documented failure mode (low locality / wrapping / rugged
  neutral-redundancy landscape). *(Rothlauf & Oetzel 2006; Fenton et al. 2017.)*
- **Governance is best-practice:** version bump on any byte change, archive to `grammar_archive/`, D-entry,
  version-stamped cohorts. Matches SemVer + version-stamping + provenance discipline. *(Voelter 2023; PAV.)*
- **Decorrelation-at-assembly, quality+variety-at-generation (D186/D187) is triple-confirmed** — non-redundant
  *operators* (curate, e.g. C1) at generation; decorrelated *outputs* at assembly (Crucible has real
  correlation). *(AlphaGen 2023; AlphaCFG 2026; gplearn.)*
- **Closest published prior art: AlphaCFG (arXiv:2601.22119)** — a typed-CFG alpha producer with nested
  syntactic/semantic/size constraint layers + pool-level redundancy penalties; Forge's S/C/P/E/R/X map onto
  it. High-value read. (Cite its *architecture*, not its unverified 87/63/12 figures.)

---

## 3. Dimension A — structure/payoff primitives (the edge-magnitude unlock = Path C)

### 3.1 Why long-single-leg *is* the wall (verified)
A single long leg pays the **variance risk premium** continuously: VIX averaged 19.3% vs realized 15.1%
(1990–2018), a 4.2-pt gap positive every year except 2008 (Bondarenko/CBOE 2019). Long optionality has
negative expected returns absent timing: index puts ~−8–9%/wk, zero-beta straddles ~−3%/wk, and — the
decisive result — a **crash-neutral straddle still loses −3.24%/wk (t=−2.15)** (Coval-Shumway 2001). So the
"you're just paying for crash insurance" defense is dead: the bleed, not the tail, is the wall — and no
signal selectivity makes a *single long leg* clear cleanly. This is the empirical basis of the dossier's
~1.40 CPCV-p25 ceiling, externally confirmed.

### 3.2 The roadmap: debit verticals → calendars (NOT credit/naked)
- **Tier 1 — debit vertical spreads (bull-call, bear-put).** The same directional bet as today's naked long,
  made **defined-risk and cheaper**, with a closer breakeven; the short leg subsidizes the long, *recovering
  part of the VRP/theta you pay in full*. Verified: struck OTM/ATM it stays **net-long vega** (preserves the
  long-vol identity), trending neutral only as it goes ITM. Trivial signal→structure map: signal sign →
  bull/bear; expected-move/strength → width. **No new signal required.** Capital = debit only. This directly
  shrinks the bleed each *existing* signal must overcome.
- **Tier 2 — calendars (then diagonals/PMCC).** Opens a genuinely **new, decorrelated axis** (forward
  vol / term-structure): net-long vega while harvesting front-month theta. Pays in **RANGING** (pin /
  term-structure) → directly addresses the worst-quartile RANGING 1.33× crater and the 76% trend monoculture.
  *Gating:* needs a forward-IV signal Forge doesn't yet produce (low front IV expected to rise) — connects to
  the existing `iv_term_slope` + the filed `vix_term_slope` ask; management-heavy (roll the short leg);
  IV-crush failure mode. Correctly *second*.
- **Defer / research-only — long straddle/strangle, backspreads.** Pure convexity, but they pay the *full*
  VRP tide (the current book's exact failure) — only worth it with a strong vol-expansion timing signal;
  expose narrowly, event-gated.
- **Do NOT expose — credit verticals, iron condors/flies, short strangles/straddles, ratios, risk
  reversals.** All earn Sharpe by *selling* vol/VRP/skew (wrong risk factor), several are undefined-risk, and
  they *give away* the bear convexity the worst-quartile gate demands. **This sharpens the parked dossier:
  its rungs 2–3 (credit defined-risk → naked premium) are the wrong direction for Forge — drop or quarantine
  them.**

### 3.3 The machine-checked net-long-vol invariant
Make **"net-debit AND net-long-vega AND defined-risk"** a structural grammar-v2 invariant. In one rule it
(a) admits exactly the Tier-1/Tier-2 primitives that reduce the bleed, (b) structurally bars the short-vol
drift the enumerator is biased toward, (c) eliminates undefined-risk + early-assignment-blowup hazards, and
(d) mirrors hard rule #4's asymmetry. This is the single highest-leverage grammar-v2 design decision.

### 3.4 Relationship to the parked Path C dossier
G1 **validates** the dossier's "debit defined-risk first" rung and its "long-options is IC-bound not
cost-bound" thesis, and **sharpens** it on two points: (1) reframe rungs 2–3 as out-of-identity (net-long-vol
invariant replaces the rung ladder); (2) the resume trigger should be read together with §3.1 — the bleed is
the wall, so the debit vertical (bleed reduction) is the *first* thing to try when the drought-resume gate
fires, not a last resort. New surface to touch is as the dossier documents: a `LegSpec`/`legs` model + a
`structure_type` in `crucible_contracts`; new S6/C5/P5-6/E4/R4 grammar rules; a `composable_spreads`
enumeration + runner path (Crucible-side). Operator- and Crucible-gated.

**Pitfalls to budget for (verified):** execution realism (ORATS: ~75% of bid-ask width single-leg → ~53%
four-leg; mid-price fills overstate multi-leg P&L — and the far-OTM/dated legs you'd add are the illiquid
ones); early assignment breaks "defined risk" on paper (short leg assigned + long expires → naked stock over a
gap); and the combinatorial/multiple-testing cost (§5).

---

## 4. Dimension B — signal/feature families (selectivity *within* the cap)

**The base is strong and literature-aligned** — the genuine gaps are narrower than the 10-family list
suggests. Apply a ~50% out-of-sample haircut to every cross-sectional equity signal (McLean-Pontiff 2016),
larger in the small/illiquid names where listed options are thin — which is *why* the best adds are
**options-native** (live where options are liquid) or **macro regime gates** (not single-name anomalies).

### 4.1 Prioritized adds (highest robust-edge-per-complexity)
1. **Credit spread / Excess Bond Premium (HY-IG OAS)** — options-legal regime gate, robustness HIGH, data =
   *one daily series*. Best edge-per-complexity: robustly gates equity-vol/drawdown regimes and answers
   whether MR/pairs should be turbulence-gated. *(Gilchrist-Zakrajšek 2012 AER.)*
2. **Yield-curve slope (10y-2y / 10y-3m)** — options-legal regime gate, HIGH for vol/recession regime, data =
   one daily series. Slow risk-regime conditioner; pair with #1. *(Estrella-Mishkin; NY Fed.)*
3. **Options-native earnings-vol gate: implied-move-vs-realized-move + call/put IV-spread** — options-legal,
   MED-HIGH where options liquid, data = *option chain + earnings calendar you already hold*. Orthogonal to
   the existing `sue` family; no new feed. *(An-Ang-Bali-Cakici 2014 JF; Cremers-Weinbaum 2010.)*
4. **Options-derived short-constraint proxy: put-call-parity violation / call-minus-put IV-spread** —
   options-legal, MED-HIGH, *option data only*. Recovers most of the HIGH-tier borrow-fee signal without the
   proprietary securities-lending feed. *(Ofek-Richardson-Whitelaw 2004 JFE.)*
5. **Momentum-crash regime gate (Daniel-Moskowitz 2016)** — options-legal risk gate, HIGH-value, data =
   price+vol. Disables short-vol/short-gamma behavior in panic-rebound states; complements the bear/ranging
   complement work. Also reconcile `market_state`'s 12-mo trailing vs the canonical 36-mo (Cooper-Gutierrez-
   Hameed) definition.
6. **VIX term-structure SLOPE (VIX vs VIX3M)** — already filed as `vix_term_slope`; the single best-replicated
   long/short-vol carry gate; prioritize the ingest. Caveat: it is carry / price-of-variance-risk, not market
   timing. *(Johnson 2017 JFQA; Simon-Campasano 2014.)*

*Lower priority / data-gated:* profitability-quality and analyst-revisions (robust but need a fundamentals /
analyst feed); VVIX and option-implied dispersion (real but heavier data and seller-side/crash-prone).

### 4.2 What NOT to add (evidence-negative)
- **Seller-side surface signals as directional edges** — put-skew/risk-reversal (most-decayed, borrow-fee
  proxy per Muravyev-Pearson-Pollet 2025), VRP timing, VVIX, dispersion. Wrong sign for the long-vol book.
- **Folklore** — vanna/charm OPEX flows (no peer-reviewed per-name signal), max-pain *direction*
  (sign-ambiguous), general "unusual options activity" scanners.
- **Decayed / data-mined** — accruals (dead post-2002), pre-FOMC drift (vanished after ~2011 once publicized,
  Kurov 2021), calendar seasonality. Forge's existing event-proximity gates are the defensible part; don't
  add these as edges.
- **Directional signed-option-flow harvest** — HIGH-tier (Pan-Poteshman) but structurally untradeable by an
  options-only producer *and* needs proprietary CBOE-coded flow. `put_call_flow` is the usable gating residue.

**Implementation locus:** new indicators wire into `src/forge/enumeration/indicator_thresholds.py`
(`directional_range`/`regime_range` + coherence class), mirroring the recent `iv_term_slope`/`iv_minus_rv`
adds, plus the registry on Crucible's side.

---

## 5. Dimension C — methodology & governance (how to expand *safely*; prerequisites)

- **[PREREQUISITE] Charge the gate against a CUMULATIVE, EFFECTIVE-N "alpha budget."** Every grammar add
  (structure or signal) enlarges the space; the False Strategy Theorem says expected *max* Sharpe rises with
  N — ~1,000 *independent* noise trials → best Sharpe **~1.5–2.0 with zero edge** (illustrative, scales with
  cross-trial dispersion). **Forge's ~1.40 wall is, to first order, near the null expectation of a large
  search.** Count *effective* (clustered, ONC) trials, deflate cumulatively over the generator's lifetime
  (alpha-investing/LORD: expansions *spend* budget, promotions *replenish*, droughts *tighten*), and lengthen
  MinBTL as N grows. **Expanding either dimension without this inflates the false-discovery bill.** Crucible-
  coordination item (the gate is theirs). *(Bailey-LdP DSR; López de Prado 2019; Harvey-Liu t≈3.18.)*
- **Pre-register every prune/retarget and confirm payoff on a *later* time-cut cohort** (never the cohort that
  motivated it) — Forge already has the hold-out splits (`grammar_version`/reboot-deploy cuts). Avoids the
  post-selection-inference trap behind "family X is dead → re-aim." *(Shalizi; Biometrika 2024.)*
- **Make rank-coherence a first-class grammar TYPE.** Encode the contracts `rank_per_name_coherent` flag as a
  structural gate on the `cross_sectional_rank` branch, so the v13–v16 chain-reading-on-rank incoherence
  becomes *unrepresentable* rather than runtime-inert (it was fixed reactively via `rank_excluded_ids`).
  *(Kakushadze CS/TS split; AlphaCFG semantic layer.)*
- **Add a few hard SHAPE constraints (sign/monotonicity)** — e.g. long-vol attractiveness monotone
  non-increasing in IV-rank; momentum sign agrees with trend direction. Injects economic priors the
  *threshold* gates (R1-R3) don't capture; damps overfitting. *(Kronberger et al. 2022.)*
- **Decide "expand grammar" only when illumination shows a region is BARREN, not UNDER-SAMPLED** — frame
  more-search-vs-expand as a bandit *with change detection* over the yield map (`--cohort-yield` /
  `--regime-gate-yield`), and *validate the illumination axes themselves* (Forge already found regime-as-proxy
  is a bad axis, D186). *(Mouret & Clune 2015; Da Costa et al. 2008.)*
- **Prune on measured *contribution* (marginal gate-clear/promotion lift), not raw zero-count, and monitor for
  regrowth.** *(fANOVA, Hutter et al. 2014; intron caveat, Luke.)*
- **Migration-chain governance:** when a *breaking* grammar change lands, decide whether old `config_hash`es
  stay re-derivable/re-runnable (PAV `pav:previousVersion`/`pav:derivedFrom`), not just archived. *(Voelter
  2023.)*
- **Treat any learned generator-side reweighting (the quality lane) as a versioned grammar-class change,
  cold-start byte-identical-tested** — constrained reweighting distorts the output distribution, not just the
  support. Forge already does this (D193 revert = byte-identical). *(CARS 2025; Whigham learnt-bias.)*

---

## 6. Prioritized roadmap (sequenced by effort × leverage)

**Track 0 — prerequisite (do before expanding either dimension):**
- Stand up the **effective-N cumulative alpha budget** with Crucible (Dimension C). Without it, expansion
  raises the null hurdle faster than it adds real edge.

**Track 1 — cheap, in-paradigm, no grammar-v2 (ship within current rules):**
- Signal adds needing *no new data feed*: **options-native earnings-vol gate** (#3), **PCP-violation borrow
  proxy** (#4), **momentum-crash regime gate** (#5). Plus the **`vix_term_slope`** ingest (#6, already filed).
- Cheap macro **regime gates**: **credit-spread/EBP** (#1) + **yield-curve slope** (#2) — one daily series each.
- Methodology: **rank-coherence-as-type** + a couple of **shape constraints**.
- *Honest scope:* these improve **component selectivity/quality within the cap** (Forge's currency is
  components, not single-config promotions) — they do not break the ceiling.

**Track 2 — the ceiling-breaker (grammar v2 + Crucible multi-leg contracts; operator+Crucible-gated):**
- **Path C Tier 1: debit vertical spreads** behind the **net-long-vol invariant**. This is the
  representational unlock — it reduces the VRP bleed that caps the single-leg book.
- **Path C Tier 2: calendars** (after a forward-IV signal exists) — fills the RANGING worst-quartile crater
  and decorrelates the trend monoculture.

**Avoid in all tracks:** credit/naked structures; seller-side surface signals as edges; folklore/decayed
signals (§4.2).

---

## 7. The honest ceiling (ties to the first review's B13)

Signals (Track 1) improve *how well you select within* the long-single-leg space; structure (Track 2) *raises
the space's ceiling*. Only Track 2 changes the single-config promotion math — the wall is representational (a
long leg pays the full VRP tide), exactly as the dossier and Coval-Shumway both say. And Track 0 is the
governor: more primitives inflate the null Sharpe hurdle, so disciplined effective-N accounting must precede
expansion or you make the wall *higher*. Net: the cheap signal/methodology work is worth doing now (better
components, safer growth), but the largest "build higher-quality strategies" lever remains the **defined-risk
debit-structure expansion** — to be sequenced when the dossier's resume triggers fire, behind the
net-long-vol invariant and the alpha budget.

---

## Appendix — load-bearing citations (HIGH unless noted)

- **Structure / VRP:** Bondarenko, *Historical Performance of Put-Writing* (CBOE 2019); Coval & Shumway,
  *Expected Option Returns* (J. Finance 2001); AQR, *Understanding the Volatility Risk Premium* (2018);
  Carr & Wu, *Variance Risk Premiums* (RFS 2009); Augustin-Cheng-Van den Bergen, *Volmageddon* (FAJ 2021);
  Sinclair, *Volatility Trading* 2e; OCC/Fidelity strategy guides; ORATS backtest methodology.
- **Signals:** McLean & Pontiff (J. Finance 2016, the ~50% haircut); Gilchrist & Zakrajšek (AER 2012, EBP);
  Estrella & Mishkin (yield curve); An-Ang-Bali-Cakici (J. Finance 2014, option-implied vol & returns);
  Ofek-Richardson-Whitelaw (JFE 2004, PCP violations); Daniel & Moskowitz (JFE 2016, Momentum Crashes);
  Johnson (JFQA 2017, VIX term structure); Xing-Zhang-Zhao (JFQA 2010, skew); Muravyev-Pearson-Pollet (2025,
  borrow-fee critique); Kurov et al. (2021, pre-FOMC drift disappeared); Baltussen-Da-Lammers-Martens
  (JFE 2021, dealer gamma); Golez & Jackwerth (JFE 2012, index anti-pinning).
- **Methodology / overfitting:** Bailey & López de Prado (DSR 2014); López de Prado, *Practical Solution to
  the Multiple-Testing Crisis* (2019) & *AFML* (2018); Harvey, Liu & Zhu (RFS 2016, t≈3); Montana (STGP 1995);
  Rothlauf & Oetzel (2006, GE locality); Fenton et al. (PonyGE2 2017); Mouret & Clune (MAP-Elites 2015);
  Kronberger et al. (shape-constrained SR 2022); arXiv:2508.00005 (constrained generation); AlphaGen (KDD
  2023); AlphaCFG (arXiv:2601.22119 — architecture only); Kakushadze (101 Alphas 2016); Voelter (language
  evolution 2023); Shalizi / Biometrika 2024 (post-selection inference).
