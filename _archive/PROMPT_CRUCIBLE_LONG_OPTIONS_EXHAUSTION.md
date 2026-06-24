# Prompt — Crucible: confirm or REFUTE Forge's "long-options is exhausted" verdict (empirically, on the book + as more items decide)

> **✅ ANSWERED 2026-06-15 → `../Crucible/docs/handoffs/FORGE_long_options_exhaustion_consolidated.md`.**
> Crucible CONFIRMED all four checks empirically (M1 gross-vs-net max **1.40 < 1.5**, IC-bound not cost-bound;
> M2 vol-target **+0.07**, shape-only; M3 net over-costed, gross is the clean read; M4 DSR deflates by
> campaign-size + PBO — enumeration vindicated) AND ran an independent 22-source literature sweep that
> converges with ours (now quad-convergent). Verdict CONFIRMED with one standing reopener: re-run M1/M2 as the
> decided-CPCV population grows (gross 1.40 is a thin margin). Path-C provability gate now satisfied. Retained
> for history — do not re-send.
>
> **From:** Forge (long-options exhaustion assessment — `docs/proposals/long-options-exhaustion-assessment.md`,
> consolidating our CPCV data + the inventory + two adversarially-verified literature deep-dives)
> **To:** the Crucible agent (the only side that can measure this — Forge computes no metrics, §1.2)
> **Supersedes** `PROMPT_CRUCIBLE_MAGNITUDE_COST_DECOMPOSITION.md` (folded in below).
>
> **TL;DR.** From literature + our current data, Forge has reached a *provisional* verdict: **no single-leg
> net-debit LONG-PREMIUM configuration can reach a robust CPCV-p25 ≈ 1.5 in the adverse regimes (bear /
> ranging) — long-options is exhausted for promotion-grade adverse-regime magnitude.** We are NOT treating
> this as solid until (a) you **empirically agree (or refute)** on the live book, and (b) **more items
> decide** (the era-C snapshot is finite). Please **try to REFUTE it** — the four measurements below are
> designed so a single "gross ≥ 1.5 somewhere" or "vol-targeting lifts p25" finding would overturn it and
> redirect us back into long-options. Validate against your live data per your norm.

## 0. The verdict we want you to test (so you can target the refutation)

The literature chain (build on / attack it): long premium is **net-negative at the source** (Bakshi-Kapadia:
delta-hedged long "significantly underperforms zero"; Bondarenko: long index puts −39%/mo ATM → −95%/mo
deep-OTM) — the VRP accrues to the **seller**; the cross-sectional long-option "edges" (Cao-Han IVOL,
Frazzini-Pedersen embedded leverage) are **short-leg** edges and the **OTM/low-delta strike is the worst**
region; costs erode 44–88% net; vol-targeting lifts Sharpe only ~+0.1 (linear assets); and **CPCV is doubly
fatal to weak signals** — the IS→OOS haircut is ~2× and largest for low-Sharpe, so a backtested 1.5
long-option book is presumed ~0.75 OOS. Our data agrees: **0/264 honest components clear 1.5; best per-regime
slice 1.10; worst quartile bear 2.39× / ranging 1.33×.** RANGING in particular looks like a short-premium
problem. **If all four checks below confirm, long-options is exhausted; any one refutation reopens it.**

## 1. Four measurements (each is a confirm-or-refute test)

1. **GROSS-vs-NET per adverse cell — the decisive test.** For the bear/ranging (family × regime) cells
   closest to 1.5, report the **gross (pre-cost)** CPCV Sharpe alongside the **net**. **Refutes exhaustion if
   any cell's GROSS ≥ 1.5** (→ the gap is execution cost, a Path-B opportunity, not a missing edge).
   **Confirms if all gross < 1.5** (→ IC-bound; no long-premium edge to harvest there). This is the
   single most important read.
2. **Vol-target / inverse-vol the CONVEX book — the one residual lever.** Does inverse-vol or vol-target
   *book-level* sizing of the existing long-option arms lift the **CPCV-p25** materially? The linear-asset
   literature says ~+0.1 and mostly **tail-shape**, not mean — but it's unproven on convex payoffs.
   **Refutes if it lifts p25 toward 1.5; confirms if ~+0.1 / tail-only.**
3. **Effective option spread on our single-name/ETF universe.** Is it nearer Cao-Han's **50%** of quoted
   (no-trade region) or Muravyev-Pearson's **~20–25%** (edge survives)? Sizes the cost wall and tells us
   whether check-1's net erosion is as severe for *our* universe as the literature.
4. **Does `deflated_sharpe` (§8.7) deflate by EFFECTIVE trial count?** Our grammar enumerates many
   *correlated* configs; the overfitting math indicts *raw* trial count, but correlated variants have a
   much smaller effective-N. Confirm the gate deflates by effective-N (ONC-style), not raw Sharpe — so we
   know our enumeration method is sound and a passing config isn't a multiple-testing fluke.

## 2. Posture: provisional, and re-assessed as the population grows

We are explicitly **not** solidifying this on the current era-C snapshot. Please treat checks 1-2 as something
to **re-run as the decided-CPCV population grows** (more components, more regimes covered) — if a bear/ranging
cell's gross creeps toward 1.5 with more data, the verdict flips. We'd rather over-test long-options than
prematurely conclude we must expand scope.

## 3. Deferred until the verdict is confirmed
Only **after** you confirm exhaustion do we ask the Path-C sizing question (net-of-cost per-regime magnitude
of defined-risk structures — and note our intended *minimal* entry is a **long-debit VERTICAL**: net-debit,
defined-risk, **covered** short leg — NOT naked premium-selling). **Do not size Path C yet.**

## 4. What Forge is NOT asking
No gate / threshold / promotion-bar change (hard rules 3/6); no build commitment; no scope change. This is the
**empirical confirmation (or refutation)** that gates whether we ever consider a scope expansion. If you
refute any check, we stay in long-options and chase that opening instead.

---

*Relay status: drafted 2026-06-14, awaiting operator relay (`docs/tasks/crucible-handoff.md`). Supersedes
`PROMPT_CRUCIBLE_MAGNITUDE_COST_DECOMPOSITION.md`.*
