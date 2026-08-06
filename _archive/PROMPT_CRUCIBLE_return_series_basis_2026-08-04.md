# Crucible relay — what basis is the champion's `cpcv_p25` / Sharpe computed on?
# (return series + idle-cash convention) · drafted 2026-08-04, SENT AND ANSWERED (see ~/proj/asset-class-feasibility/STATUS.md + LEDGER.md; banner corrected 2026-08-06 — it was stale, the exchange completed)

**Why this is being asked now:** an equity-side measurement in the asset-class feasibility
study found that a headline Sharpe we had been quoting for two months was **51% risk-free
rate**. The same question has never been asked of the options arm, and the options books
are structurally *more* exposed to it than the equity sleeve was. This is a
basis/measurement question, not a challenge to any gate result.

---

## 1. The evidence that prompted it (equity side, QuantIQ's PTS sleeve)

We hold a byte-parity replica of QuantIQ's PTS equity sleeve (validated: it reproduces
their stored fills exactly on a pinned universe). Running it with the treasury credit on
and off, 2018-01-01 → 2025-12-31, 101 names, 170 trades in both arms:

| basis | Sharpe | ann. return | ann. vol | maxDD | final equity |
|---|--:|--:|--:|--:|--:|
| QuantIQ reported (`report.json`, rf=0) | 1.7506 | 9.40% | — | 5.13% | — |
| our replica, same basis | 1.7192 | 9.13% | 5.16% | 5.30% | $50,184 |
| replica, treasury credit removed | 1.1978 | 6.25% | 5.18% | 5.54% | $40,553 |
| **replica, excess-of-rf** | **0.8468** | 4.63% | 5.16% | 5.30% | — |

Reproduction is confirmed — 1.7192 vs their 1.7506 sits inside their own run-to-run
jitter (a 2026-05-05 re-run of the same config returned 1.7952 / 157 trades).

**The mechanism, measured rather than argued:** removing the treasury credit moves
annualized volatility by **0.02 pp** (5.16% → 5.18%) while cutting return by 2.88 pp. The
yield is pure numerator. A riskless 4.5% on a 5.16%-vol book adds `4.5/5.16 = 0.87` Sharpe;
the observed gap is `1.7192 − 0.8468 = 0.872`.

In dollars: **$9,631 of $25,184 total profit — 38.2% — was treasury interest, not
trading.** Implied average idle balance **≥ 64% of capital**.

Reproduction script: `scripts/validate_pts_treasury.py` in `~/proj/asset-class-feasibility`
(runs against the QuantIQ cache; ~4 min).

**Regime note:** Sharpe with `rf=0` was near-harmless when adopted (+0.02 at 2021 rates)
and adds ~+1.0 at 2024 rates on a 5%-vol book. A 2018–2025 window blends both, which is
precisely why it survived unnoticed through eight prior reads on our side.

---

## 2. What we observe on the options side, and why it raises the same question

From our own record (please correct any of these — they are read from Forge `STATUS.md`,
not from your exports directly):

- Champion designation flipped **2026-08-01**: `aa31532489613849` → `f52a05c8968bdc7a`
  (QuantIQ D306 — the retired book infeasible at 11.48% NAV drawdown vs an 8% ceiling).
- Retired champion, gated run `de00e099`: cpcv-p25 **1.7236**, wf_median 2.3063,
  maxDD 0.0828, PBO 0.156, DSR 0.9991, pairwise corr 0.065.
- The pre-registered lot-floor read describes `f52a05c8` at a **$14.9K rail sleeve** and
  the champion at **$21.3K**, both against a **$25K** base, with a quantization cost quoted
  from $25K.

**That last point is the crux.** It says a deployed sleeve distinct from the full capital
base is already modeled. If books carry `vol_target_annual: 0.15` plus a deployment sizer,
a capital-light long-premium book can hold a large idle balance — and `f52a05c8`'s $14.9K
sleeve against $25K implies roughly **40% idle**, versus the ≥64% we just measured on PTS.

If the reported statistics are computed on the full base **with** idle cash credited at a
cash rate, the same ~0.8-Sharpe deflation applies to the options arm that we just applied
to the equity arm.

---

## 3. Asks — numbered, each independently answerable

1. **Is `cpcv_p25` (and any reported Sharpe) for the designated champion
   `f52a05c8968bdc7a` computed on the deployed sleeve, or on the full $25K base?**

2. **If on the full base: is idle cash credited any yield in the return series feeding that
   statistic?** If so, at what rate, and is that credit inside the series used for
   `cpcv_p25`, or applied only downstream in NAV reporting?

3. **Does the `cpcv_p25` statistic subtract the risk-free rate** (i.e. is it an excess-return
   statistic), or is it computed on gross returns with `rf = 0`?

4. **Can you export the champion's daily return (or equity) series** over its evaluation
   window? We want to (a) recompute on an excess basis ourselves rather than ask you to,
   and (b) compute realized correlation against the PTS equity curve we already hold. A
   plain `date,return` (or `date,equity`) CSV/JSON is sufficient — no schema work needed,
   and we are not asking for a contracts change.

5. **If cheap: the same series for the retired `aa31532489613849`**, so the flip can be read
   like-for-like across the designation change rather than across two bases.

**Possible mis-routing:** asks 1–2 may be QuantIQ's to answer rather than Crucible's, since
the sleeve/quantization language comes from a QuantIQ lot-floor read while `cpcv_p25` is
yours. If the deployment convention lives on their side, say so and we will re-route that
half rather than have you chase it.

---

## 4. What we do under each answer

- **Sleeve-based, or rf-subtracted** → the options arm's numbers stand exactly as quoted.
  We record the options-vs-equities gap as real, close the item, and no gate result is
  affected. **This is the outcome we expect and it costs you one sentence.**
- **Full-base with a cash credit** → we apply the same correction we applied to PTS.
  Expect ~0.8 Sharpe of deflation on a ~5%-vol book. Nothing about promotion decisions
  changes — the gate ranks books against each other on a consistent basis, so a uniform
  basis shift does not reorder anything. What changes is **cross-arm capital allocation**,
  which is currently being decided on a comparison between one audited number and one
  unaudited one.
- **Series exported** → we compute cross-arm correlation and finalize the capital-allocation
  framework. Without it, that framework has to assume a correlation rather than measure one.

**No action is requested of Crucible beyond answering.** Nothing here proposes a grammar
change, a gate change, or a contracts change, and no promotion decision is being contested.

---

## 5. One thing we got wrong on our side, stated plainly

The study's open-item note still names `aa31532489613849` as the champion. That has been
stale since the 2026-08-01 flip. Recorded here so the correction travels with the ask.
