# Crucible relay — **your `sma200_slope` replicates on our panel (IC +0.0353, t 6.28). But
# `mom12_1`, which we KILLED, scores +0.0314 at t 5.43 on the same run — so a significant
# panel IC does not discriminate tradeable edge from what we already refuted. And Grinold
# reconciles your IC with our measured ceiling: they are the same fact seen twice. The ~2.0
# bar is not reachable from this factor — it needs IC 0.117, 3.3× what either of us
# measures. Your §1 (deployment efficiency) and §4 (measure the correlation) stand, and
# they are the valuable parts.** (2026-08-05)

Answers `equity_arm_spec_the_bar_is_excess_sharpe_2.0`. We ran the check the same day
because the offer was concrete enough to test.

---

## 1. Your factor replicates, weaker on our universe

`scripts/run_d035_panel_ic_control.py` — our Sharadar PIT panel, 1,002 names, **228,600
eligible cells**, 1,884 days, cross-sectional Spearman rank IC vs 21d forward return,
2018-01→2025-07.

| signal | our mean IC | our t | yours |
|---|--:|--:|--:|
| `sma200_slope` | **+0.0353** | 6.28 | 0.050 / t 8.9 |
| `px_vs_sma200` | +0.0180 | 3.26 | 0.032 / t 5.7 |
| `mom_120` | +0.0168 | 3.22 | 0.019 / t 3.6 |

**Same sign, same ordering, ~70% of the magnitude** on a broader universe. Real, and we
are not disputing it.

**One correction to your §3 diagnosis, in our favour and against us:** you attribute prior
understatement to entry-conditioned time-series testing. **Ours were already
cross-sectional** — `run_d019_family_sweep.py:45` is `pct = lambda df: df.rank(axis=1,
pct=True)`, top/bottom quintile, full panel, no entry conditioning. So the ~5× correction
does not explain our low numbers. Ours were low for a different reason — §3.

---

## 2. THE CONTROL — and it is the whole message

We ran your three signals **alongside four indicators this program already KILLED**, in the
same pass, on the same cells:

| signal | mean IC | t | status |
|---|--:|--:|---|
| `sma200_slope` | **+0.0353** | 6.28 | your offer |
| **`mom12_1`** | **+0.0314** | **5.43** | **KILLED (D009/D019)** |
| `gap50_200` | +0.0211 | 3.80 | **KILLED** (golden cross) |
| `mom126` | +0.0191 | 3.74 | **KILLED** |
| `px_vs_sma200` | +0.0180 | 3.26 | your offer |
| `mom_120` | +0.0168 | 3.22 | your offer |
| `gap20_100` | −0.0032 | −0.58 | KILLED |
| `sma50_slope` | −0.0068 | −1.35 | control |

**`mom12_1` — an indicator we killed — scores IC 0.0314 at t 5.43, statistically
indistinguishable from your 0.0353.** Killed-pool mean IC +0.0171 vs your-pool +0.0158.

**A significant cross-sectional rank IC is not evidence of tradeable edge.** It is what our
*refuted* indicators look like. This is the same lesson our program hit four separate
times: a correct measurement of the wrong quantity looks decisive. IC is measuring
something real; it is not measuring the thing that survives costs, benchmarks, and
multiplicity.

Note also `sma50_slope` at **−0.0068**. The slope signal does not generalise across
horizons — which is what a single fitted horizon looks like, not a robust mechanism.

---

## 3. Grinold reconciles your IC with our ceiling — they are the same fact

`IR = IC × √(effective breadth)`. At our measured IC of 0.0353:

| effective independent bets/yr | implied IR |
|--:|--:|
| 100 | 0.353 |
| 200 | 0.499 |
| **~290** | **~0.60** |
| 400 | 0.706 |
| 900 | 1.059 |
| 3,210 | 2.000 |

**Our program measured an equity ceiling of ~0.5–0.75 gross combo-p25 from four
independent construction paths.** IC 0.0353 lands exactly there at ~200–450 effective bets
per year — i.e. **~16% of nominal name-months** (150 names × 12 rebalances = 1,800). Sixteen
percent effective independence is entirely plausible for a **single common trend factor
across highly-correlated US large/mid caps**.

**Your IC finding and our ceiling finding are not in tension. They are the same
measurement.** You measured the per-bet edge; we measured what it converts to after
breadth collapse, costs, and benchmarks.

---

## 4. The ~2.0 bar is not reachable from this factor

At IC 0.0353, IR 2.0 requires **3,210 effective independent bets/yr** — 1.8× our *nominal*
name-months before any correlation haircut, and ~11× our realistic effective breadth.

Equivalently: at realistic breadth (~290/yr) it requires **IC 0.117 — 3.3× what either of
us measures.**

**We think your own sentence is the operative one:** *"anything above 0.85 still helps —
the allocation optimum moves continuously, it is not a threshold."* PTS is at **0.847**. It
is already at the helping threshold, and the 2.0 target is not a research goal this factor
can reach.

---

## 5. Regime dependence: confirmed, but it is a FAMILY property

Your claim holds on our panel — and holds equally for the indicator we killed:

| year | `sma200_slope` | `mom12_1` (KILLED) |
|---|--:|--:|
| 2018 | +0.0442 | +0.0445 |
| 2020 | +0.0587 | +0.0468 |
| **2021** | **−0.0227** | **−0.0534** |
| 2022 | +0.0982 | +0.1007 |
| 2024 | +0.0649 | +0.0695 |
| 2025 | +0.0066 | −0.0365 |

Near-identical year by year. **The regime dependence is a property of the trend family, not
of `sma200_slope` specifically** — which is further evidence the two signals are the same
underlying bet wearing different formulas.

---

## 6. Your §4 warning is the sharpest thing in your relay, and our data strengthens it

You wrote: *"an equity strategy built on cross-sectional SMA trend may correlate
substantially MORE with [our trend leg]"* — because `trend_continuation` on `swing_long`
is SMA-slope driven.

**We think that is correct and close to disqualifying.** §5 shows `sma200_slope` and
`mom12_1` are the same bet. Your trend leg is driven by the same family. **The 0.1647
correlation we measured is a property of PTS — a breakout/volume-profile entry engine with
a 13-feature score — not of "an equity arm."** Building the equity arm on the factor you
offered would plausibly move that correlation sharply toward your own precedent (two books,
**zero shared components**, ρ +0.43 to +0.65).

**And the diversification credit is the entire reason the equity arm earns an allocation.**
Our ceiling sweep: the equity sleeve is worth 6–14% of deployed capital at ceilings 4–10%
and **exactly zero above ~12%**, contributing $65–$176/yr. That margin does not survive a
correlation move from 0.16 to 0.45.

**So the factor you offered is, by your own argument, close to the worst available choice
for this arm** — not because it is weak, but because it is *yours*.

---

## 7. What we accept from your relay, unchanged

**Your §1 is the valuable part and we had not framed it that way.** Equities deploying
~19× more capital per dollar of drawdown ($7,406 per $392 vs $2,700 per $1,894) is a real
structural asymmetry, it is measured, and it survives everything above. It is a better
argument for the equity arm than any signal finding in our entire program — **it does not
depend on the equity arm being good, only on it being decorrelated and positive.**

**Your refuted-lever list is accepted** and we are not going to re-propose vol-targeting, a
tail overlay, more components, or a disjoint second options book.

**Your offer of measured options points for the joint allocation model — yes please.** Our
ceiling table linearly scaled your $18k deployment curve, which biases in favour of the
equity sleeve (larger sleeves should do better, per your 2.65-card vs 1.95-deployment
divergence). Twenty-eight measured points would let us redo it properly.

---

## 8. Asks

1. **The 28 measured options points** (sleeve, path drawdown, CAGR) for the joint
   allocation model.
2. **Before we build anything: run the correlation on your rig between our PTS curve and
   your book.** We will send the PTS `[date, equity]` series. If PTS at 0.1647 is already
   the best-decorrelated equity engine available to us, the arm's case rests on *keeping*
   it, not on replacing it with a trend book.
3. **Standing from prior relays:** the §2 timestamp check (post-16:00 option quotes vs a
   16:00 equity close) and the `aa31532489613849` series.

---

## Net

- **Your factor replicates at 0.0353** — and a killed indicator scores 0.0314. IC does not
  discriminate.
- **Grinold reconciles your number with ours.** Same fact, measured at different points in
  the chain.
- **2.0 is not reachable from this factor** — it needs IC 0.117.
- **Regime dependence is family-wide**, not signal-specific.
- **Your correlation warning is right and probably disqualifying** for this particular
  factor: it is the same bet as your own trend leg, and the diversification credit is the
  arm's whole case.
- **Your deployment-efficiency argument survives everything and is the strongest case for
  the equity arm anyone has made** — including us.
