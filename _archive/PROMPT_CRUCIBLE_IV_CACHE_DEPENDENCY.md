# Prompt — Crucible: ship a computable ATM-IV history so `iv_rank` goes live — light up the long-options VEGA / IV-cost axis (the in-scope step we skipped before declaring long-options exhausted)

> **❌ ANSWERED 2026-06-15 — PREMISE FALSIFIED; NOT SENT, do not send.**
> (`../Crucible/docs/handoffs/FORGE_iv_rank_already_live_coverage.md`, [[D154]].) Ask #1 is **moot**: there is
> **nothing to ship** — `iv_rank` has been **live since D031 (2026-05-15)** (Crucible v4 2026-06-10), non-NaN
> ~100% single-name, used in 3,998 runs / 77 components. The "NaN stub" premise came from a **stale Forge doc**
> (`docs/INDICATOR_THRESHOLDS.md`, since corrected), not Crucible state. The unblock is **Forge-side** (doc fix
> [done] + an optional low-EV mr re-enumeration; see `path-a-rich-conditioning.md` thread 1). **Ask #2 surfaced
> the one genuine gap:** `skew / risk-reversal` is **absent** (no indicator) — the only unbuilt IV-surface
> conditioner — but it is a *seller* signal (wrong-signed for long premium), so it is **Path-C-relevant, not a
> Path-A long conditioner**; do NOT request the build for Path A. Retained for history.
>
> ~~DRAFTED — ready for operator to relay~~ (`docs/tasks/crucible-handoff.md`). Thread-1 first action of the
> Path-A rich-conditioning sweep (`docs/proposals/path-a-rich-conditioning.md`).
>
> **From:** Forge. **To:** the Crucible agent (the only side that computes indicators, §1.2).
> **Trigger:** the operator reopened the long-options exhaustion ([[D152]]) on **conditioning-completeness**
> grounds: your decisive read (M1, max **gross** CPCV-p25 = 1.40 < 1.5 → IC-bound) was measured over a Forge
> population that **could not condition on the vega / IV-cost axis at all.** Our canonical "buy only when vol
> is cheap" gate, `iv_rank`, is a **NaN-only stub** on Forge's side (`docs/INDICATOR_THRESHOLDS.md:83,87`),
> which makes **§3.5 R1 structurally unsatisfiable** (`:131`) — so mean_reversion has been gating on
> `gamma_flip` / `hurst` *regime-shape* proxies (D107/D150), never on vol-cheapness. Before we accept the
> exhaustion, we owe the measurement on a book that *actually* conditions on IV cost.

## TL;DR

Please ship a **computable ATM-IV history** (per name, per date, across the backtest window) so `iv_rank`
(the 252-day percentile of ATM IV) is **non-NaN** and Forge can enumerate it as the §3.5 R1
mean_reversion gate. This is a **data dependency, not a gate/threshold/scope change** (hard rules 3/6
untouched). It unblocks the cheapest, fully **in-scope** (single-leg net-debit long-premium) step in
properly exhausting long-options — and it is **parallel to**, not a replacement for, the standing M1/M2
monitor.

## 1. The ask

1. **`iv_rank` — the priority.** Ship the ATM-IV history that makes `iv_rank` computable across the honest-era
   window (the blocker you noted: "needs ATM IV history; `chain_snapshots` may not have computable IV for all
   dates"). Confirm the coverage (which names / date ranges have non-NaN `iv_rank`) so we can scope the
   re-enumeration cohort honestly and not fail-open on missing IV.
2. **The adjacent IV-surface set (for threads 2–3, lower priority).** While you're in the IV cache, please
   confirm availability + coverage of the broader vol-state features we'd condition on jointly:
   **IV level / `iv_rank`**, **skew / risk-reversal slope**, **term-structure slope** (`iv_term_slope` — you
   already ship this; confirm single-name coverage), and **`iv_minus_rv`** (you ship this too — confirm it's
   the same vol-cheapness construct). Flag any that are index-only or sparse on single names.

## 2. Why this matters (and what it does NOT claim)

- **It does not reopen the *structural* verdict.** We accept your sign result: long premium is net-negative at
  source and the high-Sharpe edge is sell-side — conditioning on vol-cheapness changes *how much* VRP you
  pay, not the sign. We are **not** claiming `iv_rank` rescues long premium.
- **It reopens the *measurement*.** "Gross 1.40" was measured with the vol-cost gate **inert**. We have never
  observed our single-name net-debit book gating on real vol-cheapness. That measurement is cheap and
  in-scope, and the operator wants it run before declaring long-options a failure.
- **Calibrated expectations.** Your "Inventory complete" note already rates IV conditioners *low-EV for
  long-only* (their edge lives on the L/S straddle's short leg). We expect this to **close or confirm the thin
  1.40 → 1.5 pocket**, not to find a large arm. A negative result here makes the exhaustion verdict
  **stronger** (measured on a properly-conditioned book), which is itself valuable.

## 3. What Forge does with it

- **`iv_rank` live →** re-enumerate mean_reversion with the real "buy-vol-cheap" R1 gate; submit the cohort;
  you funnel-compare it against the proxy-gated (`gamma_flip` / `hurst`) cohort. The question we want answered
  on Forge-produced configs: **does conditioning on genuine vol-cheapness move the gross CPCV-p25 in the
  bear / ranging cells at all** — toward 1.5, or not? No grammar change is needed on our side (`iv_rank` is
  already the R1 canonical gate; it is merely inert), so this is a clean data-in → re-enumerate → measure loop.
- **IV-surface set confirmed →** feeds the gated thread-2 (joint-gate grammar enrichment) and thread-3
  (learned conditioner) work in `path-a-rich-conditioning.md`. No build commitment off this relay.

## 4. What Forge is NOT asking

No gate / threshold / promotion-bar change (hard rules 3/6). No scope expansion (this is **Path A**, fully
in-scope — single-leg net-debit long premium — *not* the parked Path C). No grammar change for `iv_rank`
itself. Just the data that turns an already-sanctioned gate from inert to live.

---

*Relay status: drafted 2026-06-15, awaiting operator relay. Thread-1 first action of
`docs/proposals/path-a-rich-conditioning.md`; parallel to the standing M1/M2 monitor ([[D152]]).*
