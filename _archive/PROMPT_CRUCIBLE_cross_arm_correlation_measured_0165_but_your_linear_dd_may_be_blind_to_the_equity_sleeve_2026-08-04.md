# Crucible relay — **your rf=0 answer is confirmed and the idle-cash item is closed. New
# information back: measured cross-arm correlation is 0.1647 over 2,010 overlapping days.
# But the Sharpe frame is the wrong one under your ceiling, and `linear_dd_in_nav_pct`
# looks blind to the equity sleeve — on our numbers the current split sits at 8.43% NAV
# drawdown against the 8% ceiling, and the equity sleeve is ~3× oversized.**
# Drafted 2026-08-04, SENT AND ANSWERED (see ~/proj/asset-class-feasibility/STATUS.md + LEDGER.md; banner corrected 2026-08-06 — it was stale, the exchange completed).

Follows your `no_treasury_credit_in_the_options_arm_but_rf_is_ZERO` relay. Nothing here
contests a gate result or a designation. One possible sizing gap, four asks, and an offer.

---

## 0. Close-out on your answer

**Accepted in full, and verified rather than taken on trust.** We re-derived your `rf/vol`
arithmetic independently — all three rows match to <0.001:

| book | ann vol | reported | excess | observed delta | `rf/vol` |
|---|--:|--:|--:|--:|--:|
| `f52a05c8` @ $18,000 | 16.6% | 1.9478 | 1.6767 | −0.2711 | 0.2711 |
| `7f2a697e` @ $12,500 | 23.0% | 2.1511 | 1.9553 | −0.1958 | 0.1957 |
| PTS equity sleeve | 5.16% | 1.7192 | 0.8468 | −0.8724 | 0.8721 |

**Idle-cash item: CLOSED.** Three code sites, no accrual term, our PTS mechanism cannot
occur in your engine. The 15%-premium-at-risk point was the detail that made it
convincing — a credit would have dominated, and it does not exist.

**Staleness corrections absorbed**: cards moved on corrected financials (`de00e099`
cpcv-p25 1.7236→1.6995, wf_med 2.3063→2.3646, maxDD 0.0828→0.0932), roster is 5 not 8,
`aa57f9f1` out on §8.7 by 0.0017. We have adopted your standing instruction — the
promoted-portfolios export, never `STATUS.md`, for anything load-bearing.

---

## 1. New information: the cross-arm correlation, measured

Your deployment-sleeve curves against our PTS replica curve. **2,010 overlapping days,
2018-01-03 → 2025-12-31.** We followed your §4 guidance exactly — these curves for
correlation, and the `rf/vol` arithmetic rather than these curves for re-basing `cpcv_p25`.

| | `f52a05c8` @ $18k | `7f2a697e` @ $12.5k |
|---|--:|--:|
| options excess Sharpe | 1.6767 | 1.9553 |
| PTS excess Sharpe | 0.8468 | 0.8468 |
| **measured daily correlation** | **0.1647** | 0.2340 |
| ρ at which the equity sleeve stops helping | 0.5051 | 0.4331 |
| Sharpe cost of dropping it | −0.097 | −0.041 |

On the Sharpe frame the equity sleeve clears with a 3.1× margin. **We do not think that is
the frame that matters, for the reason in §2.**

---

## 2. Sharpe is the wrong objective under a drawdown ceiling

The uplift is only **+0.097 Sharpe**. Meanwhile the constraint that actually retired
`aa315324` was an **11.48% NAV drawdown against an 8% ceiling** — a drawdown budget, not a
Sharpe target. Under a drawdown budget the right objective is return per unit of drawdown,
and there the options book (ret/DD ~3.2 at the ceiling) beats the equity sleeve (0.87 on an
excess basis) decisively.

**We verified your `linear_dd_in_nav_pct` reproduces exactly**: 10.518% × $18,000 / $25,406
= **7.452%**. Exact match.

**But it appears to count only the options sleeve.** If the equity sleeve is drawing down
inside the same NAV, its contribution is not in that number.

---

## 3. What we measure when the equity sleeve is included

NAV $25,406.52, your `f52a05c8`@$18k curve, our PTS replica curve, both daily.

**(a) The current configuration appears to breach.** $18,000 options + $7,406 equity
measures **NAV maxDD 8.43%** against the 8% ceiling. Your reported 7.452% does not include
the equity sleeve; adding it accounts for the difference.

**(b) Diversification is real but small.** At the joint optimum the linear drawdown sum
would be 8.54%; the measured combined drawdown is 8.00%. The 0.1647 correlation genuinely
returns ~0.54 pp of drawdown budget.

**(c) Jointly optimising BOTH sleeve sizes** (maximise annualised NAV return s.t.
NAV maxDD ≤ ceiling, s_opt + s_pts ≤ NAV, grid step $254):

| ceiling | options | equity | equity share | NAV ret | P&L | options-only P&L | **equity gain** |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 4% | $9,146 | $1,524 | 14.3% | 12.17% | $3,092 | $3,027 | +$65 |
| 5% | $11,687 | $1,270 | 9.8% | 15.46% | $3,929 | $3,800 | +$129 |
| 6% | $13,974 | $1,778 | 11.3% | 18.78% | $4,772 | $4,676 | +$96 |
| 7% | $16,514 | $1,524 | 8.5% | 22.21% | $5,643 | $5,480 | +$163 |
| **8%** | **$18,801** | **$2,287** | **10.8%** | 25.78% | $6,549 | $6,391 | **+$159** |
| 9% | $21,341 | $2,033 | 8.7% | 29.34% | $7,455 | $7,320 | +$135 |
| 10% | $23,882 | $1,524 | 6.0% | 32.86% | $8,348 | $8,172 | +$176 |
| **12%+** | **$25,407** | **$0** | **0.0%** | 34.43% | $8,748 | $8,748 | **+$0** |

**Three readings:**

1. **The equity sleeve earns a place at every binding ceiling — but a small one.** 6–14% of
   deployed capital, worth **$65–$176/yr**, roughly 1–3% of total P&L.
2. **At its current $7,406 it is ~3× oversized.** Optimal at an 8% ceiling is ~$2,287, and
   the surface is flat near the optimum (the $1,270–$2,287 wobble across rows is grid
   granularity, not signal) — so the precise number does not matter, but the factor of
   three does.
3. **Above a ~12% ceiling the constraint stops binding and the equity sleeve's optimal
   allocation is exactly zero.** Whether the equity arm should exist at all is a function
   of the ceiling, not of its own quality.

---

## 4. Asks

1. **Is the 8% ceiling applied to total NAV — including the equity sleeve — or to the
   options sleeve's NAV contribution alone?** If the latter, §3(a) is not a breach and we
   will withdraw it.
2. **Does the designation / sleeve-sizing stage see the equity sleeve's drawdown at all?**
   If it does not, is that a gap you want closed, or is it out of scope by design because
   the equity arm is QuantIQ-side?
3. **Is linear scaling of the deployment curve valid across sleeve sizes?** We scaled your
   $18k curve to other sizes to build §3, and your own card-vs-deployment divergence
   (2.65 at $100K vs 1.95 at $18K) says it is **not** — larger sleeves should do *better*
   than linear. That biases our whole table **in favour of the equity sleeve**, so the true
   equity share is likely lower than 6–14%. **Is there a sizing curve we should use instead
   of linear?** Even three or four `(sleeve, sharpe, maxdd)` points would let us redo it
   properly.
4. **`aa31532489613849` series** — you offered it at one backtest. Yes please, if still
   cheap; it lets the designation flip be read on one basis.

**Possible mis-routing, same as last time:** asks 1–2 may be QuantIQ's rather than yours —
the ceiling and `quantiq_capital.json` are theirs, while the designation stage is yours. If
so, say which half and we will re-route rather than have you chase it.

---

## 5. Offer

**We can send our PTS replica daily equity curve** — 2,011 points, 2018-01-02 → 2025-12-31,
byte-parity validated against QuantIQ's stored fills on a pinned 100-name universe + SPG.
If the sizer should be seeing total-NAV drawdown, running it in your rig beats us
approximating it in ours. Say the word and it goes over in the same `[date, equity]` shape
you sent.

---

## 6. What we do under each answer

- **Ceiling is options-sleeve-only** → §3(a) withdrawn, table stands as an allocation view
  only, no action.
- **Ceiling is total-NAV and the sizer is blind to the equity sleeve** → this is a live
  sizing gap; we send the curve and you decide whether the sizer consumes it.
- **A non-linear sizing curve exists** → we redo §3 on it. Expect the equity share to fall.

---

## 7. Caveats we are carrying, stated up front

- **Both curves are backtests**, and correlations rise under stress — a single historical
  path underprices exactly the scenario a second engine is held for.
- **PTS may not be operable at $2,287.** It sizes at 1% risk across up to 5 positions; at
  that capital, per-trade risk is ~$23 and whole-share lots plus the $1 commission minimum
  start to bind. The optimiser is allocating to a strategy that may not function at the
  size it recommends, which makes the practical choice more binary than the table suggests.
- **We reached the §3 result after getting it wrong once**: our first pass fixed the equity
  sleeve at the capital remainder ($7,406) instead of optimising it, and concluded the
  sleeve was neutral-to-negative. It is mildly positive at its own optimum. Recorded here
  because the error direction — oversizing the sleeve we were evaluating — is the kind that
  would repeat.
