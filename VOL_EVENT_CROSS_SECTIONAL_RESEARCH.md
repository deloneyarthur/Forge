# Vol-Event as a Cross-Sectional Strategy — Research Synthesis

**Date:** 2026-07-01
**Question (operator):** Can we make `vol_event` a cross-sectional strategy? How do top quant firms and seasoned traders trade volatility events across a universe?
**Method:** 5 parallel Sonnet deep-research lanes (event-driven edges · broad cross-sectional-vol landscape · firm/practitioner implementation · rank-signal construction · options-native expression) → Opus synthesis → verified against the live Forge/Crucible code and the `2026-07-01T19:00:03Z` registry snapshot. Scope per operator: event-driven core **inside** the broader cross-sectional-vol landscape, **tied back** to Forge's constraints.
**Source-quality convention throughout:** peer-reviewed/dataset-backed vs practitioner vs folklore vs marketing is flagged inline; effect sizes and sample periods are given where the source gave them. Discount every headline for the McLean-Pontiff ~50% post-publication haircut.

---

## 0. Bottom line

**Do not chase a cross-sectional (rank-based) `vol_event` strategy.** Three independent bodies of evidence converge against it, and they converge *toward* the path Forge is already on:

1. **The external academic + practitioner evidence says the tradeable single-name event-vol edge is not a cross-sectional *rank* — it is a per-name, pre-print, long-vol *selection* edge**, harvested by breadth across many names (a 1/N portfolio), not by ranking a universe on a vol-surface score. The signals that *are* genuinely cross-sectionally rank-coherent (IV−RV, term-structure slope) are weak, decayed, and selection-dependent.

2. **How top firms trade it corroborates this.** Systematic single-name *options* vol is run either as **dispersion** (short index vol / long single-name vol = a short-*correlation* factor bet, vega-neutral — a different animal from ranking names by an event signal) or as a **breadth book of single-name event trades**; and the biggest systematic shops (AQR, Man) explicitly **avoid single-name options altogether** because of the liquidity/cost wall. Nobody publicly ranks a universe by a single-name vol-event signal and trades the cross-section — because the option-market microstructure won't support it.

3. **Forge's own mechanics and prior results already say so.** Cross-sectional `vol_event` is *doubly locked* in code, the within-name signals theory favors are flag-excluded for a real plumbing reason, Crucible measured cross-sectional `iv_minus_rv` as directionally dead (rank-IC −0.015), and the **06-29 result already found the winning path: a mixed trend/MR + *single-name* vol_event book clears CSCV PBO 0.107 — the first promotable book reachable in v1**, no grammar bump, no v2.

The reframe: **"cross-sectional" is the wrong axis for the *edge*; it is the right axis for the *portfolio*.** Single-name event vol is valuable precisely because it is *idiosyncratic and orthogonal* (it loads only ~0.10 on the vol PC1). Its cross-sectional value is realized at **assembly** (a decorrelated portfolio of many single-name bets — Crucible's job), not at **generation** (ranking — Forge's job). This is Forge's own "decorrelation at assembly, not generation" principle, independently re-derived from the outside literature.

The one thread this research initially flagged as new — a within-family selection tilt toward cheap-implied-vs-realized-move — turns out to be **substantially already tested and refuted** (it is `iv_minus_rv`, wired at D131 and closed by the 06-28 straddle refutation; see §3.4, corrected). The producer job therefore stays what the 06-29 result established: single-name vol_event **quantity + durability**, not a new selection signal.

---

## Part 1 — What the external evidence says

### 1.1 The single-name event-vol edge is a pre-print, long-vol, *selection* edge — not a rank

The one **long-vol, cross-sectional, options-native** earnings edge with peer-reviewed support is the **pre-event straddle run-up**:

- Buy the ATM straddle ~3 trading days before earnings, **exit *at/before* the print**: **+3.34%**, highly significant; straddle-implied vol averaged 47.4% vs 43.1% realized → the market *underprices* the earnings jump in this window (Gao, Xing & Zhang, *JFQA* 2018 — peer-reviewed). This *inverts* the well-known negative baseline return to buying single-name straddles.
- The edge is **jump-risk premium, not diffusive vol**: straddle returns are positive *before* the print and turn **negative after** — holding through the print eats the ~30–50% IV crush (Gao-Xing-Zhang decomposition; vendor crush data ~38% avg, ~72% realized at the next open). The buyer's window and the seller's window are the *same trade with opposite signs*, split by the announcement.
- It is **cross-sectionally concentrated but as a *magnitude* tilt, not a clean rank**: larger for **small, illiquid, high-kurtosis, cheap-IV-vs-RV** names (Gao-Xing-Zhang; Chung-Louis 2017). The best single predictor is the gap between implied and realized/historical move — i.e. *selection on VRP*, not a vol-surface rank.
- **PEAD/SUE, the volatility smirk, and the put-call IV spread are strong cross-sectional signals — but they are *directional* (delta bets), not vega.** SUE deciles drift ~+2%/60d (Bernard-Thomas); smirk −10.9%/yr (Xing-Zhang-Zhao 2010). They rank names by *direction*, which a long-vol book cannot express as a vega position.
- **Decay/capacity are severe:** the earnings-announcement premium has partially *disappeared* post-2004 (8-Ks preempt it); the run-up edge lives specifically in illiquid, wide-spread names (that's both why it persists and its hard capacity ceiling); the post-2019 weeklies/0DTE regime post-dates most studies. An academic single-name straddle book was profitable 1996–2013 but **negative 2011–2021** (Khan & Khan, SSRN 4832160).

**Read for Forge:** the defensible edge is *long the run-up in cheap-IV names, out before the crush*, sized across many names. That is a **per-name timer plus selection**, exactly the shape Forge already produces — not a universe rank.

### 1.2 Where single-name event vol sits: the idiosyncratic, orthogonal corner

- A cross-sectional single-name vol book's **PC1 is net-long-vol *market* volatility beta**: PC1 explains 77% of single-name IV level and correlates 92% with index-option vol (Christoffersen-Fournier-Jacobs 2018; Avellaneda et al. 2020 replicate PC1 ≈ an OI/vega-weighted market vol factor; Duan-Wei 2009: single-name IV is driven by each name's *systematic* risk share).
- The big, harvestable vol premia are **short-vol and market-wide**: index VRP is strongly negative (Carr-Wu 2009), the correlation/dispersion premium is a distinct priced factor (Driessen-Maenhout-Vilkov 2009) — both the *opposite* of Forge's long-vol stance. And **single-name VRP is ~zero** (Carr-Wu: insignificant for all but 3 of 35 names; Bakshi-Kapadia: single-name premium ≈ half the index and **idiosyncratic vol is unpriced**).
- **Therefore single-name *event* vol is the least-VRP-contaminated, most idiosyncratic corner of the whole map** — orthogonal in *source* to PC1 and to dispersion, hence genuinely diversifying. This is the outside-literature derivation of Forge's measured **0.10 PC1 loading** and the 06-29 finding that a book including single-name vol_event clears PBO. Caveats it still carries: positive net-long-vol *tail* beta, the Cao-Han idio-vol delta-hedge penalty (−1.4%/mo on high-idio names), and an on-average-negative event premium that only selection overcomes.

### 1.3 What makes a vol signal cross-sectionally rank-coherent — and what does not

This is the crux, and the external methodology maps almost one-to-one onto Forge's `rank_per_name_coherent` flag.

**A vol signal is rank-coherent iff** it is (i) a **within-name ratio/difference of two vols** (the name's scale cancels), or (ii) a raw quantity **cross-sectionally standardized + sector/size/liquidity-neutralized each period**. It is rank-**in**coherent if it is (iii) a raw level, (iv) a **name-vs-own-history normalization** (IV rank/percentile/z-score — these are *per-name timers wearing cross-sectional clothes*), or (v) market-wide (VIX, implied correlation — no cross-section at all).

| Rank-COHERENT (durable cross-sectional vol ranks) | Rank-INCOHERENT (timer / no cross-section) |
|---|---|
| **IV − RV / IV÷RV** (VRP) — Goyal-Saretto 2009, the flagship | Raw IV or RV **level** |
| **Term-structure slope** IV(long)−IV(short) — Vasquez 2017 | **IV rank / IV percentile / vol z-score** (per-name timer) |
| **Put-call IV spread** — Cremers-Weinbaum 2010 | **VIX / market term-slope / implied correlation** (market-wide) |
| **Skew / smirk slope** — Xing-Zhang-Zhao 2010 | Raw earnings surprise in $ (before standardization) |
| Ranked, neutralized **idiosyncratic vol** — Ang et al.; Cao-Han | "Is IV elevated vs its own past" (the textbook timer) |

- **The SUE analogy gives a concrete vol-native recipe:** raw surprise is made comparable by dividing by the name's own estimate dispersion; the vol analog is **standardized vol-surprise = realized move ÷ implied (expected) move** — rank-coherent by construction. But its *alpha* is mostly the residual VRP (Goyal-Saretto) — the denominator already prices the rest.
- **Evaluation bar:** cross-sectional rank-IC of **0.02–0.05 is typical/meaningful, 0.05–0.10 is strong**; judge the *mean-IC t-stat over time* plus decile monotonicity, and **neutralize sector/size/liquidity before computing IC** or it's an artifact (the Ang et al. IVOL anomaly is partly a liquidity-microstructure artifact — Cao-Han attribute ~40% to limits-to-arbitrage).

**Read for Forge:** the signals theory says *are* rank-coherent — IV−RV and term-slope — are exactly the ones Forge has (`iv_minus_rv`, `iv_term_slope`) but flags rank-*incoherent* (§2.2). The signals Forge would naively reach for (IV rank) are the *timers* the literature also rejects for ranking. The framework agrees with Forge's flag *in intent*; the disagreement is narrow and mechanical, and it resolves against enumeration on the data (§2.2).

### 1.4 How top firms and seasoned traders actually trade it

- **Nobody publicly ranks a universe by a single-name vol-*event* signal and trades the cross-section in options.** The systematic single-name options-vol activity that exists is **dispersion**: short index vol / long a basket of single-name vol = **long dispersion = short correlation**, delta-hedged and **vega- (or theta-) weighted**, so the book's residual is a *correlation* bet, not a level or event bet (Bennett 2014; Jacquier-Slaoui 2010; Driessen-Maenhout-Vilkov 2009). It is run by dedicated shops (**Capstone ~$11bn, QVR, Parallax, Argentière, 36 South, Universa**) and as embedded pods at the multi-strats (**Millennium's "VAD," Citadel, Balyasny, Verition, Schonfeld, LMR, QRT**). It is *crowded* as of 2024–25 (Eifert/QVR publicly put on the *reverse* dispersion trade), carries **short-correlation convexity** ("nets lie under stress"; blows out when correlation spikes — Feb-18, Mar-20), and DMV find the premium "cannot be captured under realistic frictions." Dedicated single-name long-vol funds are rare and **struggle to scale** (Brevan Howard's Global Volatility Fund wound down 2025 for lack of scale).
- **The biggest systematic factor shops avoid single-name options on purpose.** AQR states plainly that vol selling is confined to the index because of "the thin market for single-stock options" (0.00% options in its 13F; permitted-instruments list is index options only). Man Group's public options work is likewise index/futures-level. The reason is the cost wall (§1.5), and it applies with *more* force to a long-vol buyer.
- **Seasoned-trader consensus leans hard to *selling* vol** (Sinclair: "you get paid for selling options… not for buying"; the VRP is "the tide that long option positions need to overcome"; Abdelmessih: the structural edge "comes from selling them to harvest the VRP," ~40–100%, "fattest when realized vol is very low"; Eifert: "long volatility costs money over time"; Taleb's own Empirica "did nothing but lose money" bleeding on long tails). Long-vol earns its keep in only two narrow places, **both of which are Forge's exact situation**:
  1. **Taleb's cheap, deep-OTM, dormant convexity spread 1/N across many names** — justified *only* by minimizing cost-per-trial, and explicitly **not** continuous ATM vol. "A large exposure to a single trial has lower expected return than a portfolio of small trials." Breadth across many independent small bets (risk scales √N) is the harvest mechanism.
  2. **Event/earnings vol where the implied move overshoots realized and you screen cross-sectionally for names whose *base* vol is cheap** — Abdelmessih's "renting the straddle" (buy pre-print, gamma-hedge, sell *before* the announcement), Sinclair's implied-vs-realized-move gap. Note Abdelmessih **measures VRP as a *ratio* "because it makes cross-sectional comparison easier"** — the practitioner statement of §1.3's rank-coherence rule.

**Read for Forge:** the professional templates are (a) dispersion — a short-correlation factor bet Forge structurally cannot and should not build (it's short-vol-ish and lives at the index/assembly layer), and (b) a **breadth 1/N book of single-name event trades** — which is precisely what Forge's single-name vol_event stream *is*. The pros who do (b) select on *cheap base vol / implied-vs-realized-move*, not on a vol-surface rank.

### 1.5 Options expression, DTE, and the cost wall

- **Two design cautions that dominate structure choice** (Bennett; Natenberg; Fidelity Greeks):
  - **"Long vega" ≠ "long the event jump."** They are different exposures, and most multi-leg structures deliver one at the cost of the other: a long *calendar* is long vega but **short the event move** (short gamma — it loses on a big surprise); a *reverse* calendar is long the move but **short vega** (violates the mandate). Only **outright longs (call/put/straddle/strangle) and net-debit ratio backspreads** are simultaneously long vega *and* long the jump.
  - **"Net-debit AND defined-risk" does NOT imply "net-long-vega."** A long butterfly is a debit, defined-risk structure that is net **short** vega; a narrow deep-ITM debit vertical is ~vega-neutral. **A Path-C filter must compute the net-vega sign directly — never infer long-vol from "debit + defined-risk."** (Directly relevant to the v2 invariant "net-debit AND net-long-vega AND defined-risk.")

- **Structures for a long event-vol view** (mandate = net-debit AND net-long-vega AND defined-risk; vega sign is to a parallel IV shift):

| Structure | Net vega | Jump (gamma) | Carry/theta | Cost per net-vega | Mandate? |
|---|---|---|---|---|---|
| Long straddle / strangle | **Long** | **Long** | Heavy −θ; full crush if held through | Low–moderate | **Yes** — buy pre-print, **exit before crush** |
| Long single call / put | **Long** | Long + directional δ | ~½ straddle θ | **Lowest** | **Yes** — long-jump *with* a direction view |
| **Net-debit ratio backspread** | **Long** | **Long** | **~zero / positive** (shorts finance longs) | Moderate | **Yes (best structural fit)** — long-vega + long-jump + minimal carry; risk = a *small* move; vega flips short near expiry |
| Long calendar / diagonal | **Long (term)** | **SHORT the move** | Positive-ish θ; isolates event vs term vol | High (legs net) | **Qualified** — a *term-structure* bet; can **lose in a rising/inverted-IV regime**; profits only if realized < implied |
| Debit vertical | **~0 / weakly long** | Long but capped | Reduced θ (short leg also crushes) | Worse (nets vega) | **Weak** — a capped *directional* bet, not a vol structure |
| Credit spread / short straddle-strangle / iron condor | **SHORT** | Short | Collects θ | — | **No** — the seller's side (violates net-long-vega) |
| Long butterfly / broken-wing | **SHORT** | Short (pin bet) | Positive θ | — | **No** — debit but short vega (the "debit⇒long-vol" trap) |

- **DTE rule:** trade the shortest expiry that still contains the print — "the expiry just after the key date, so the greatest % of time value is the jump" (Bennett §6.4); decompose **total variance = diffusive + jump variance** (additive; Leung-Santoli 2014 closed form) and price/trade the jump separately.
- **The cost wall is the binding real-world constraint** and the reason cross-sectional single-name options don't scale: single-name option **effective** spread ~**5–6% of premium ATM, 10–13% OTM** (quoted up to ~17%, and **13%+ quoted for small/mid caps**) vs **sub-1% for index** (Muravyev-Pearson 2020; Christoffersen-Goyenko-Jacobs-Karoui 2018; Cao-Wei 2010). Per-name depth is thin (~1,600 contracts/day for an S&P 500 name), so a systematic book **scales via breadth, not depth**, and liquidity *commonality* means it dries up market-wide exactly in stress. The earnings gap itself is **un-hedgeable** — for a long-vol book the correct handling is to be **delta-neutral into the print to capture the gap** (the gap is the payoff), not to hedge it.

**Read for Forge:** confirms the memory'd cost-wall closure (straddle redirect −96/−100% @5%). It also says the *cheapest* compliant long-vega expression is the **debit vertical**, and calendars isolate event-vs-term vol — relevant only if/when Path C (spreads, grammar v2) is ever revisited; not a v1 lever.

---

## Part 2 — The Forge tie-back (verified against current code + registry)

### 2.1 Cross-sectional `vol_event` is *doubly locked* — and both locks are deliberate

Cross-sectional enumerability in Forge is a **two-gate AND** (verified `2026-07-01`):

- **Gate 1 — hypothesis membership.** `RANK_COMBINER_HYPOTHESES = {trend_continuation, mean_reversion, event_momentum}` (`src/forge/enumeration/search_space.py:111`). `_cohort_xsect_probability` returns `0.0` for any other hypothesis (`sampler.py:413`), which short-circuits the rank draw. **`volatility_event` is not in the set — it can *never* be enumerated cross-sectionally**, by policy (D109). The exclusion comment reasons vol_event "already clears breadth via recurring events" — a rationale D214 itself flags as *stale under PBO* (single-name is book-excluded regardless of breadth), but the frozenset is unchanged and the build was held.
- **Gate 2 — per-indicator flag.** A config can be emitted as `cross_sectional_rank` only if no drawn indicator is rank-excluded, where excluded = dealer-family OR (`not rank_per_name_coherent and not market_wide_by_design`) (`search_space.py:149`; enforced at `sampler.py:694`). **All 14 `volatility_event` directionals** (`iv_structure` ×7, `flow` ×1, `dealer_positioning` ×6) **plus `sue` are `rank_per_name_coherent=False`** — confirmed against the live registry snapshot and Crucible's `rank_gate_class_map.json`. The flag is defined on `IndicatorMetadata` in **crucible_contracts** (`models.py:501`), **fail-closed by default** ("a new indicator ships off the rank branch until Crucible proves coherence").

So vol_event fails *both* gates. This is not an accident to be patched around in Forge — Gate 2 is owned by contracts/Crucible (rule #2), and Gate 1 is an operator-gated enumeration policy.

### 2.2 The signals theory favors exist in Forge — but are flag-excluded for a real reason

The durable cross-sectional vol ranks from §1.3 map to **existing Forge indicators**, all currently rank-excluded:

| Literature signal | Forge id | Present? | `rank_per_name_coherent` | Cross-sectionally enumerable today |
|---|---|---|---|---|
| VRP (IV−RV) | `iv_minus_rv` | yes | **False** | No |
| Term-structure slope | `iv_term_slope` | yes | **False** | No |
| Skew / butterfly | `skew_25d`, `butterfly_25d` | yes | **False** | No |
| Put-call flow | `put_call_flow` | yes | **False** | No |
| SUE | `sue` | yes | **False** | No (even though `event_momentum` ∈ Gate 1) |
| Realized-vol rank | `rv_rank` | yes | **True** | Yes — but a *regime gate*, not a vol-surface directional |

The reason they're `False` is **mechanical, not theoretical**: per Crucible's `rank_gate_class_map.json`, these ids read `params['symbol']` and are **unthreaded on the rank path** (`per_name_chain_unthreaded` / `chain_*_broken`) → they return NaN/garbage when computed across a universe. In principle Crucible could *thread* them and flip the flag — which is why this looked like an unlock. **But the data already closed it:** Crucible measured cross-sectional `iv_minus_rv` and found it **directionally dead (rank-IC −0.015, t −0.86)** (memory D-thread, 06-28), and the xsect vol-surface "second factor" batch is un-enumerable *and* foreshadowed as PC1 = net-long-vol beta (signal novelty ≠ factor novelty). So even the *theoretically* rank-coherent vol signals do not carry a cross-sectional edge in this data — matching §1.1's decay findings and §1.2's "single-name VRP ≈ zero."

Net today: **0 enumerable cross-sectional vol-surface-led configs** from Forge (STATUS.md), and the evidence says that's the correct number.

### 2.3 Reconciliation: Forge already found the right answer

The 06-29 result — **mixed trend/MR + *single-name* vol_event book clears real-sortino CSCV PBO 0.107 « 0.40, the first promotable book reachable in v1** — is not a consolation prize for a failed cross-sectional attempt. The external evidence says it is *the* answer:

- single-name event vol is the idiosyncratic/orthogonal corner (§1.2) → it loads 0.10 on PC1 → it *lowers* book PBO, which is the actual binding gate;
- the professional long-vol templates are breadth (1/N) and event selection, both single-name (§1.4);
- cross-sectional ranking of vol-surface signals is neither how pros do it, nor rank-coherent, nor empirically alive (§1.1, §1.3, §2.2).

**"Cross-sectional" belongs at assembly, not generation.** The value of many single-name event bets is a *decorrelated portfolio* — Crucible composes it with real correlations; Forge's job is to *supply* quality, durable, diverse single-name event vol. This is Forge's own decorrelation-at-assembly principle, and the outside literature (Taleb's 1/N; PC1-residual sizing; dispersion-lives-at-the-index-layer) lands in the same place from a completely different direction.

---

## Part 3 — Verdict and options

### 3.1 Verdict

**Making `vol_event` a cross-sectional (rank) strategy is not the lever.** It is blocked by two deliberate gates, unsupported by the cross-sectional-vol literature (the edge is per-name selection, not a rank), not how any top firm trades single-name event vol (they do dispersion, breadth, or nothing), and already measured dead on Forge's own data. Reopening it would mean a Crucible plumbing change (thread the chain-reading ids) to enumerate a signal Crucible already found rank-IC ≈ 0 — negative EV.

### 3.2 The lever the research *does* support (already in flight, operator-gated)

Keep and strengthen **single-name vol_event supply as a breadth book** — which is the current producer job. The research adds two refinements to *what* to supply, both consistent with existing held/flag-off work:

- **Quantity + durability of single-name vol_event**, not cross-sectional reach. The flag-off `FORGE_ORTHOGONAL_FAMILY_FLOOR` (D216, lifts vol_event's share off the 5% floor) is the right shape; the external evidence (idiosyncratic/orthogonal → lowers PBO) is the theoretical warrant for activating it. Activation stays operator-gated (prereg / alpha-budget / later cohort).
- **Durability is the open question the literature underscores**: the earnings-announcement premium has decayed post-2004 and post-weeklies; the academic single-name straddle book went negative 2011–2021. This is the same "transfer-fragility / QuantIQ-incubation" question already flagged — treat measured single-name vol_event edge as *decaying* and lean on breadth + freshness, not on any one recurring setup.

### 3.3 Where "cross-sectional" genuinely lives (not a Forge action)

The one real cross-sectional structure in single-name vol is **dispersion / the correlation premium** — a short-correlation factor bet that belongs at the **index/assembly layer**, is short-vol-convexity, is crowded, and is uncapturable under realistic frictions. It is *not* a Forge generation target and *not* long-vol. Flag it as understood-and-declined, not unexplored.

### 3.4 The within-family selection lever — SUBSTANTIALLY ALREADY TESTED AND REFUTED

**Correction (2026-07-01, post-synthesis record check — supersedes this section's original "one new falsifiable experiment" framing, which under-credited prior work.)** The "select on cheap-implied-vs-realized-move" idea is *not* new to Forge — it is `iv_minus_rv` (Goyal-Saretto), and the record shows it has been tested from three sides, all weak-to-dead:

1. **As the single-name vol_event *directional* — LIVE since grammar v17 (D131, 2026-06-10)**, wired explicitly as "Goyal-Saretto, net-debit book" (`iv_minus_rv < −0.05`, 21d horizon). It became the **top vol_event directional (123/587)** and landed a first component — but Crucible's 23/25-claim causal sweep found it **low-EV as a long-only gate**: conditioning on cheap/high vol is where the *seller's* edge is largest, not a long rescue (the edge is on the short leg Forge cannot sell) (STATUS:751-752).
2. **As a cross-sectional rank — refuted** (rank-IC −0.015, t −0.86; §2.2).
3. **As a straddle / long-vol monetization — refuted head-on** (06-28 faithful backtests: cheapest-`iv_minus_rv` quintile −27% / −98.6% maxDD at zero cost, **direction backwards**, −99/−100% @ 5% cost; both `iv_minus_rv` and `rv_rank` straddle entries dead — STATUS:42-48). The "cheap-vol-conditional" straddle variant is covered by this and also died.

**So the axis is substantially closed, not open.** And the strongest documented long-vol event edge the literature points at — the Gao-Xing-Zhang pre-print straddle (+3.34% at ~T-3) — is **already emitted** as `ve×days_to_earnings` and produced Forge's only-ever double-quality-gate config (`d964e908`, STATUS:1231): it is captured, not untested.

**The only genuinely-untested residual** is narrow and now *lower-prior*: a dedicated **event-move-overshoot** indicator — the implied straddle *move* vs the name's typical realized *earnings move* (a SUE-style standardized vol-surprise, distinct from `iv_minus_rv` = IV level − RV level), which does not exist as an indicator. Its prior dropped because the cheap-vol-conditional straddle it would feed was tested and died, and the causal frame says the VRP edge lives on the un-sellable short leg. **Do not build it ahead of the D216 / marginal-contribution threads; treat the selection axis as closed on data unless Crucible surfaces new evidence.** If it is ever revisited, the guardrails still stand: prereg (D208), alpha-budget charge (D207), CPCV purge ≥ max DTE, Harvey t ≥ 3, net of the §1.5 cost wall.

### 3.5 What NOT to do

- Do **not** add `volatility_event` to `RANK_COMBINER_HYPOTHESES`, or ask Crucible to thread the chain-reading vol ids for ranking — reverse-D109 grammar/enumeration change to enumerate a rank-IC-≈-0 signal.
- Do **not** build dispersion / short-correlation — off-mandate (short-vol, index-layer) and uncapturable net of frictions.
- Do **not** buy-and-hold straddles through the print (that's the seller's harvest), and do **not** treat IV rank/percentile as a cross-sectional score (it's a per-name timer).
- Do **not** re-propose "select vol_event on cheap-implied-vs-realized-move" as a novel lever — it is `iv_minus_rv` (D131), tested as a directional gate, a cross-sectional rank, and a straddle, and refuted from all three (§3.4).
- Do **not** propose grammar/registry changes here — this is a research note; any lever above is operator-gated with its own D-entry.

---

## Sources (consolidated; discount all for ~50% McLean-Pontiff post-publication haircut)

**Event-driven cross-sectional vol**
- Gao, Xing & Zhang, "Anticipating Uncertainty: Straddles Around Earnings Announcements," *JFQA* 53(6), 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2204549
- Chung & Louis, "Earnings Announcements and Option Returns," *J. Empirical Finance* 40, 2017 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2886040
- Barth & So, "Non-Diversifiable Volatility Risk and Risk Premiums at Earnings Announcements," *The Accounting Review* 89(5), 2014 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1635584
- Alexiou, Goyal, Kostakis & Rompolis, "Pricing Event Risk: Evidence from Concave Implied Volatility Curves," *Review of Finance* 29(4), 2025 — https://academic.oup.com/rof/article/29/4/963/8079062
- Bernard & Thomas (PEAD, 1989); Xing, Zhang & Zhao, "…Option Volatility Smirk…," *JFQA* 45, 2010 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1107464
- Leung & Santoli, "Accounting for Earnings Announcements in the Pricing of Equity Options," 2014 — https://arxiv.org/pdf/1412.8414
- Khan & Khan, single-name straddle book profitability (negative 2011–2021) — SSRN 4832160
- "The Disappearing Earnings Announcement Premium" (Rotman WP); de Silva et al., "Losing is Optional: Retail Option Trading…," 2025

**Broad cross-sectional-vol landscape & factor structure**
- Carr & Wu, "Variance Risk Premiums," *RFS* 22(3), 2009 — https://engineering.nyu.edu/sites/default/files/2019-01/CarrReviewofFinStudiesMarch2009-a.pdf
- Bakshi & Kapadia (individual equity), *J. Derivatives* Fall 2003 — https://people.umass.edu/~nkapadia/docs/Bakshi_Kapadia_JoD_Fall_2003.pdf
- Goyal & Saretto, "Cross-Section of Option Returns and Volatility," *JFE* 94, 2009 — https://www.cis.upenn.edu/~mkearns/finread/CrossOptions.pdf
- Cao & Han, "Cross Section of Option Returns and Idiosyncratic Stock Volatility," *JFE* 108, 2013 — https://www-2.rotman.utoronto.ca/facbios/file/Han_JFE_published.pdf
- Vasquez, "Equity Volatility Term Structures and the Cross-Section of Option Returns," *JFQA* 2017 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1944298
- Ang, Hodrick, Xing & Zhang, "The Cross-Section of Volatility and Expected Returns," *JF* 61(1), 2006
- Driessen, Maenhout & Vilkov, "The Price of Correlation Risk," *JF* 64(3), 2009 — https://www.ssrn.com/abstract=673425
- Christoffersen, Fournier & Jacobs, "The Factor Structure in Equity Options," *RFS* 31(2), 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2224270
- Avellaneda, Healy, Papanicolaou & Papanicolaou, "PCA for Implied Volatility Surfaces," 2020 — https://arxiv.org/abs/2002.00085
- Duan & Wei, "Systematic Risk and the Price Structure of Individual Equity Options," *RFS* 22(5), 2009

**Rank-coherence / signal construction / evaluation**
- Cremers & Weinbaum, "Deviations from Put-Call Parity…," *JFQA* 2010 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968237
- Cao, Han, Tong & Zhan, "Option Return Predictability," *RFS* 35(3), 2022 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2698267
- Bali & Hovakimian, "Volatility Spreads and Expected Stock Returns," *Mgmt Sci* 55, 2009
- Grinold & Kahn (IC / Fundamental Law); "Liquidity Biases and the Pricing of Cross-Sectional Idiosyncratic Volatility"
- SUE construction / standardized surprise references

**Firm & practitioner implementation, structures, costs**
- Bennett, *Trading Volatility: Correlation, Term Structure and Skew*, 2014 — https://www.trading-volatility.com/Trading-Volatility.pdf
- Sinclair, *Volatility Trading* (2013), *Positional Option Trading* (2020); "Confidence Intervals for the Kelly Criterion," SSRN 2457368
- Abdelmessih (Moontower): "Dispersion Trading For The Uninitiated"; "HOOD: A Case Study in 'Renting the Straddle'"; "Weighting an Options Pair Trade"; VRP-as-ratio notes
- Eifert / QVR: reverse-dispersion (Hedgeweek 2025-09-22); Odd Lots 2025-02-17
- Taleb, "Understanding is a Poor Substitute for Convexity," 2012 — http://fooledbyrandomness.com/ConvexityScience.pdf; Gladwell, "Blowing Up," *New Yorker* 2002
- AQR: Ang/Jiang/Maloney, "Understanding Alternative Risk Premia," 2018 (single-stock-options avoidance) — https://www.aqr.com/-/media/AQR/Documents/Whitepapers/Understand-Alternative-Risk-Premia.pdf; Israelov & Nielsen, "Covered Calls Uncovered," *FAJ* 2015
- Muravyev & Pearson, "Options Trading Costs Are Lower than You Think," *RFS* 33(11), 2020; Christoffersen, Goyenko, Jacobs & Karoui, "Illiquidity Premia in the Equity Options Market," *RFS* 31(3), 2018; Cao & Wei, *J. Financial Markets* 13(1), 2010
- Muravyev et al., "Options Market Makers," 2025; Boyle & Emanuel (1980); Leland (1985); Whalley & Wilmott (1997)
- BIS Bulletin 95 (Todorov & Vilkov), Aug-2024 vol spike — https://www.bis.org/publ/bisbull95.pdf; Gerchik, Ruffo, Schönleber & Vilkov, "Factor Dispersions," 2024 (SSRN 4853747)
- Firm reference class (dispersion / vol RV): Capstone, QVR, Parallax, Argentière, 36 South, Universa; embedded pods Millennium/Citadel/Balyasny/Verition/Schonfeld/LMR/QRT; Malachite (defunct 2020) and Brevan Howard Global Volatility Fund (wound down 2025) as cautionary cases

**Forge / Crucible as-built (verified 2026-07-01)**
- `crucible_contracts/src/crucible_contracts/models.py:501` (`rank_per_name_coherent`), `:459` (`IndicatorMetadata`)
- `src/forge/enumeration/search_space.py:111` (`RANK_COMBINER_HYPOTHESES`), `:142,:149` (`rank_excluded_indicator_ids`)
- `src/forge/enumeration/sampler.py:388-423,653-705` (two-gate decision), `:368-385` (`_uses_single_name_only_indicator`)
- `src/forge/grammar/custom_predicates.py:179` (`volatility_event` family map)
- Live registry `registry_snapshot_2026-07-01T190003Z.json`; Crucible `rank_gate_class_map.json`
- Decisions: D109 (`RANK_COMBINER_HYPOTHESES`), D214 (vol_event exclusion stale-under-PBO, held), D216 (`FORGE_ORTHOGONAL_FAMILY_FLOOR`), D150/D151 (hurst/rv_rank rank-coherent)
- Related notes: `GRAMMAR_REVIEW_AND_EXPANSION.md` (rank-coherence-as-type proposal), `STRIKE_FORECASTING_RESEARCH.md` (earnings event-phase)
