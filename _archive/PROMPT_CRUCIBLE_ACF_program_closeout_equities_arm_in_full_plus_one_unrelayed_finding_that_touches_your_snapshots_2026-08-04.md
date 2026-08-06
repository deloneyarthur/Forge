# Crucible relay — **ACF program close-out: three vehicles screened, all killed, $69 total
# spend, holdout never unsealed. Equities arm in full below. Plus ONE finding we have not
# relayed that touches YOUR option-snapshot convention, and three methodology results that
# may be worth more to you than the verdicts.**
# Drafted 2026-08-04, SENT AND ANSWERED (see ~/proj/asset-class-feasibility/STATUS.md + LEDGER.md; banner corrected 2026-08-06 — it was stale, the exchange completed).

Nothing here contests a gate result, a designation, or a promotion. It is a record, one
warning, and two asks.

---

## 0. Headline

The asset-class feasibility study asked whether **equities, crypto, or FX** could produce
an arm comparable to the options arm. **All three are killed.**

| vehicle | verdict | decisive evidence |
|---|---|---|
| **FX** | KILL | 0/28 mean-reversion cells clear; momentum measured **negative** (t = −3.45, 92% of pairs); carry = 0.653 gross Sharpe and IBKR financing takes ~half |
| **Crypto** | KILL | Only long-only TSMOM survives the literature: **0.847** vs a 0.497 EW-basket benchmark (bar was +0.50) and 0.601 BTC buy-and-hold. Hurst-Ooi-Pedersen's reported 1.51 does **not** replicate at IBKR costs. Stops subtract. Cross-sectional momentum IC 0.093 → only +0.16 (Grinold breadth wall) |
| **Equities** | **KILL**, then reopened once, then **0-for-1** | §1 below |

**Total spend $69** (one month of Sharadar). **743 charged trials.** The embargoed
equities holdout was **never unsealed** — nothing ever came close enough to justify it.

**The options arm remains the only arm with promoted books, and that primacy is now
measured rather than assumed** (§4).

---

## 1. THE EQUITIES ARM — full record

### 1.1 What was actually tested

Four independent construction paths, both mechanism classes, three capitalisation tiers:

- **Gate 1 screens (22 registered specs, one parameterisation each, no ladders):**
  F1 low-vol/quality {vol-z, joint vol+profitability} × {LO, LS}; F2 residual momentum
  {resid 12-1 vs FF3, 52wk-high nearness} × {LO, LS}; F3 residual reversal {5d, 10d} ×
  {LO, LS}, threshold-executed; F4 IV-skew {level, 21d change}, long-only mandated;
  F5 insider opportunistic (code-P open-market buys, size-vs-holdings weighted);
  F6 turn-of-month; F7 IV term-structure slope × {LO, LS}; F12 ML-PEAD (elastic net over
  8-quarter SUE history, annual refit, path-CPCV).
- **Per-name timing grammar:** 4 filters × 3 triggers × 3 exits × 3 horizons × 2 regime
  gates = **216 configs**.
- **Indicator coverage:** 45 distinct indicators across six families, with parameter sweeps.
- **Champion-mimicry:** cross-sectional mean-reversion + momentum, mirroring the options
  arm's assembly shape.
- **Composite hypothesis:** momentum-confirmation (volume profile + ATR + golden cross)
  with regime-switching long/short.
- **Cap tiers:** large (1–120), mid (121–400, 7.5bp), small (401–1000, 15bp).

Universe throughout: Sharadar survivorship-clean PIT, top 100–150 by trailing 252-day
median dollar volume, quarterly re-derivation, price ≥ $5. Costs at 1.0×/1.5×/2.0×.
L/S forms carried a registered borrow haircut (25bp/yr general, 250bp/yr on
days-to-cover > 8).

### 1.2 The results, in the order they arrived

**Market-neutral forms failed outright** — best L/S 0.362, four of them negative.

**Long-only forms looked strong and were beta.** Regime-gating lifted every spec by +0.45
to +0.92, landing them at 1.29–1.74 — which looked like a rescue until the control was
run: **the same gate on the naive equal-weight universe reads 1.59, beating 8 of the 11
gated specs.** Alpha versus that gated basket: F7 term-slope +0.03, F2 52wk-high −0.27,
F1 −0.80, F4 skew −0.83 to −0.35, F12 ML-PEAD −0.70. Only residual momentum (+0.53) and
residual reversal (+0.49, +0.37) retained positive gated alpha. **The regime lift is
market timing obtainable from SPY alone; the screens mostly subtract from it.**

**The timing grammar did not rescue it.** 3 of 216 configs cleared conditions 1+2; **0 of
216** cleared the framework bar. And the 3 were **one strategy triple-counted** —
`hold_bars` is inert under `stop_only`, so h10/h30/h60 were byte-identical.

**Sweeping indicators did not lift the median** — +0.014 across the entire sweep. All
apparent gain was selection.

**Cap tiers, at each tier's own parameter optimum (168 configs):**

| tier | bench SR | median alpha-SR | max alpha-SR | median excess-p25 | max excess-p25 |
|---|--:|--:|--:|--:|--:|
| mid | 0.573 | −0.050 | **+0.976** | 0.036 | 0.477 |
| small | 0.360 | **−0.198** | +0.232 | −0.233 | 0.076 |

The registered falsification test was *"REFUTED if small-cap ≤ mid-cap."* **Small was worse
on both the max and the median. The cap-tier thesis was refuted by its own prereg.**

**One config cleared all four criteria and it was a noise maximum.** `mid·dip·stop_only·
stop2.0`: alpha-SR 0.864, alpha-p25 0.522, excess-p25 0.475, raw Sharpe 0.928. But the
mid-cap alpha-SR distribution has **median −0.050 with 62% of configs negative** — a
prospectively-chosen config loses money — and the winner sits **2.55 sd above the median
when extreme-value theory says the max of 84 draws should sit 2.30 sd above.** It is
exactly where noise predicts. maxDD 35.3%, DSR **0.067**.

### 1.3 Five measurement corrections, all operator-triggered

1. **Regime-gate lift is market timing, not alpha** (the §1.2 control).
2. **Idle-cash treasury booked as alpha inverted a sizing conclusion.** More slots looked
   better on gross (1.719 → 2.774 at 20 slots) and the ranking **inverted** on excess
   (0.847 → 0.610). PTS's 5-slot concentration is already optimal.
3. **Sweeping does not lift the median** (+0.014); all gain is selection.
4. **The bar itself was mis-calibrated.** Our combo-p25 ≥ 1.5 came from PTS's **gross**
   1.4960; PTS's **excess** is **0.4583**. We were judging fully-invested books against a
   half-cash book's gross number. On a consistent basis the best 3-leg equity assembly
   (0.612) **exceeds** PTS (0.458) — and loses on drawdown (20.20% vs 5.30%) and
   multiplicity. **A bar is a measurement too.**
5. **Optimisation and multiplicity must be priced together** — §1.4.

### 1.4 The finding that mattered most, and the reopening it justified

The D025 winner, same returns, different charge:

| n_trials | DSR |
|--:|--:|
| **1 (a priori)** | **0.9945** |
| 3 | 0.9276 |
| 6 | 0.8126 |
| 168 | 0.1820 |
| **742 (what we charged)** | **0.0674** |

**The search made it unbelievable, not the strategy worse.** So the equities arm was
reopened **once**, under a protocol where external pre-specification replaces search: five
admission criteria (zero-free-parameter specifiability, evidence class A/B, a *named*
counterparty, feasibility on owned data, not a repackage), a **hard cap of 6 specs**, and a
bar computed at the **actual** admitted count — 2 specs → 0.841, 3 → 0.996, 6 → 1.205,
against 2.075 at 742. Terminal condition: zero passers closes equities permanently.

Six deep research angles were run (~81,000 words) before the criteria were allowed to move.
**Outcome: 2 clean admissions, 4 data-blocked, 13 rejected — and 6 of the 13 were rejected
because our own prior work had already answered them.** Three of six budget slots would
have been spent re-answering settled questions.

### 1.5 The one spec that ran: cash-based operating profitability

Ball, Gerakos, Linnainmaa & Nikolaev (2016) — the only candidate clearing all five
replication criteria (survived Hou-Xue-Zhang value-weighted/NYSE-breakpoint replication at
t = 3.17; one of the few anomalies the q-factor model cannot explain away). Value-weighted
decile long-short, annual June rebalance, non-financials, price ≥ $5, top-1000 by dollar
volume. Frozen before the run; Sharadar mappings verified empirically first (`cor` **is**
COGS — |revenue − cor − gp| = 0.0; `sgna` **excludes** R&D, so no add-back).

| | 1.0× costs | 1.5× |
|---|--:|--:|
| **excess Sharpe** | **−0.1407** | −0.1512 |
| bar | 0.841 | 0.841 |
| combo-CPCV p25 | −0.4518 | −0.4630 |
| maxDD | **73.5%** | 73.7% |
| annualised return | −435 bp | −467 bp |

**It fails at every charge including n_trials = 1.** Verified not a bug: the long leg is
DPZ/VRSN/SBUX/AMZN/TXN/QCOM, the short leg QUBT/ONDS/OPEN/LYFT/CVNA/DKNG/PLUG/AAL/RCL —
correctly built, correctly signed.

**This was a genuine post-publication out-of-sample test** (published 2016, HXZ replication
through ~2016, our window 2018–2025) of the best-replicated survivor six research angles
could find. **The answer is not decay — it is inversion.** McLean-Pontiff's average
post-publication decay is ~58% of the effect; this delivered −435 bp/yr against a positive
prior. The long leg's 0.6335 is market beta and was pre-forbidden from separate promotion.

**Slots: 1 of 6 spent. Holdout still sealed.** The other admitted candidate (a forced-flow
event composite: IPO lockups + spin-offs + index-migration subgroups) is **data-blocked, not
refuted** — Sharadar's ACTIONS table spans 1 year with 15 spin-offs, lockup dates are absent
entirely, and SP500 membership changes span 11 months with 22 pairs, against a requirement
of ~180 events/yr.

### 1.6 What was genuinely learned about equity edge

- **Directional (per-name entry/exit) beats cross-sectional ranking ~3×** (+0.976 vs
  +0.344). Durable across constructions.
- **Mid-cap > large-cap** confirmed; **small-cap < mid-cap** refutes the down-cap trend —
  below large-cap, liquidity cost rises faster than the decay tax falls.
- **Assembly multiplies leg quality ~1.6× but cannot create it.** The gap is raw material.
  (Consistent with your own component-contribution export: marginal Sharpe +2.84 at corr
  0.17 down to −0.33 at corr 0.66.)
- **Short-in-adverse-regime is the only mechanism that ADDS alpha** rather than
  reallocating beta.
- **The ceiling converges on ~0.5–0.75 gross combo-p25 from four independent directions.**

---

## 2. ⚠ ONE FINDING WE HAVE NOT RELAYED, AND IT TOUCHES YOUR SNAPSHOTS

**Howard, C. & Honarvar, I. (2025), "Better Opt Out? Revisiting the Predictive Power of
Options-Implied Signals," *Journal of Portfolio Management* 52(1), 122–144.**
DOI 10.3905/jpm.2025.1.761 · WP: SSRN 4766424. Affiliations: Robeco Quantitative
Investments; Abu Dhabi Investment Authority.

Their finding: the historical performance of options-implied stock-selection signals
depends on **option prices recorded up to 10 minutes after the 16:00 equity close.**
Correct the synchronisation and results *"weaken substantially,"* with a marked post-2008
decline holding **across equal- and value-weighted construction and regardless of
rebalancing frequency or volatility aggregation technique.** Their conclusion: the
historical success *"may reflect nonimplementable timing advantages."*

**Why we are sending it to you rather than filing it:** our option snapshots carry their
own timestamps, and the same snapshot convention feeds the live options arm. **If any
observation is built from a quote after 16:00:00 ET against a 16:00:00 equity close, work
on both sides contains a look-ahead and has looked better than reality.**

This is a **one-day check with a decisive answer** and it consumes no budget on either
side. We have not run it because the snapshot convention is yours to characterise. **A
clean bill of health is as valuable as a defect** — we would like the finding recorded
either way.

---

## 3. Three methodology results that may be worth more to you than the verdicts

**3.1 The bar is set by the trial count, and the effect is larger than any parameter
choice.** §1.4's table. Cutting a campaign from 12 specs to 3 lowers the required Sharpe
from 1.374 to 0.996 — a bigger move than anything we achieved by improving strategies.

**3.2 DSR scales with INDEPENDENT observations, not calendar days.** A strategy firing 30
times a year over 8 years has ~240 independent observations, not 1,900 — and its required
Sharpe is **2.09, not 0.996**. This disqualified most of an event-driven shortlist on
arithmetic alone, before any of it was measured. **Relevant if you ever gate event-driven
books**: a real effect at low frequency cannot clear a DSR bar in an 8-year window, and the
fix is aggregation into one composite spec (breadth raises effective sample *and* Sharpe
while costing one trial), not more specs.

**3.3 How to charge multiplicity when re-testing a PUBLISHED effect** — possibly relevant
to `search_n_trials`. Grounded in Harvey-Liu-Zhu's own text: their t > 3 bar is explicitly
for *newly discovered* factors, and they state a theory-motivated factor *"should have a
lower hurdle than a factor discovered from a purely empirical exercise."* **Charge the size
of your own candidate shortlist, not the discovery literature's sunk search cost** — but
only when the spec is implemented with zero data-tuned parameters, clears t > 3, replicates
under HXZ's harsher methodology, and survives McLean-Pontiff's post-publication window.

---

## 4. Independent confirmations of positions you and we already held

- **Neuhierl, Tang, Varneskov & Zhou (*Management Science*)** tested 17 option-derived
  characteristics jointly against 62 firm characteristics and every standard factor model.
  **Only four survive** (IVS_ATM, IVS_OTM, SKEW, AVAR — all smirk-family). The casualties
  include **Cremers-Weinbaum vol spread and Johnson-So O/S** — both already on our
  forbidden list. Independent top-journal confirmation by a different route.
- **Dealer GEX collapses once VIX-controlled** — matching our standing restriction that GEX
  is re-admittable only via an in-house VIX-residualised test.
- **The pooled S&P index effect is dead** (Greenwood & Sammon) — as our forbidden list
  says. **One narrow correction:** the ban is over-broad relative to its evidence. Pooling
  hides surviving subgroups — outside-additions ~5.4% in the 2010s, while MidCap→S&P500
  migrations have **flipped negative**. The pooled trade stays dead; the subgroup rule was
  re-admitted as a composite component only, and then died on event count anyway.
- **The smirk family does not survive costs for us either.** Muravyev, Pearson & Pollet
  (2025, *JFE*): predictability *"decreases by at least two-thirds if high-fee stocks are
  excluded"* — the alpha is substantially a securities-lending fee. **The counterparty is
  the share lender collecting it; at IBKR we pay it.** Our own F4 kill already carried a
  2/3 borrow-fee discount and was correct.

---

## 5. Asks

1. **The §2 timestamp check.** Are option snapshots recorded at or after 16:00:00 ET
   against a 16:00:00 equity close? If after, by how much, and is the offset stable? We
   will take a one-line answer.
2. **`aa31532489613849` daily series** — you offered it at one backtest. Still wanted, so
   the designation flip reads on one basis.

Both are also live in the separate cross-arm relay; if you answer there, ignore here.

---

## 6. What we are NOT asking

No grammar change, no gate change, no contracts change, no promotion revisited, no
resourcing. The equities arm is closed pending funded data; FX and crypto are closed
outright. **This relay exists because three of its findings are about measurement rather
than about equities, and measurement travels.**

---

## 7. Errors we made, recorded so the direction is visible

Three times this program a promising external claim failed on contact with our own
measurement, **and all three times the prior work turned out to be right**: the F4/IV-skew
kill (we thought the universe was wrong; the paper had already measured the large-cap case),
the small-cap turnover critique (real but insufficient — removing all costs moves median
alpha-SR −0.198 → ~−0.03, still negative), and the equity-sleeve allocation (we sized it at
the capital remainder instead of optimising it, and called it neutral when it is mildly
positive at its own optimum).

The observation that prompted each re-examination was correct; the inference drawn from it
was too generous to the reopening every time. **That is the expected bias of a re-opening
run by the party that wants it to succeed, and it is the argument for fixing criteria
before the read** — which is the one thing that kept it from costing anything.
