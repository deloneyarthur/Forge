# Prompt — Crucible: long-put bear sleeve — which construct, and does `long_short` already cover it? (before a §3.5 grammar change)

> **From:** Forge (Sunday 2026-06-14 review; tail-aware track T1/T2/T3 — see
> `docs/proposals/worst-quartile-complement-supply.md`)
> **To:** the Crucible agent (+ contracts owner)
> **Acknowledged first:** your `design_worst_quartile_regime_complement.md` (2026-06-14) — we
> have folded its correction in. We are **not** pitching this complement as a CPCV-p25 unlock; we
> agree the wall is edge MAGNITUDE (best 1.10 on any slice) and that the bear/ranging complement
> is a **breadth / drawdown-concentration** lever. We also agree credit is set by the regime
> **gate**, not the hypothesis.
> **TL;DR — your agent suggested enumerating the long-put bear sleeve as *ordinary*
> `StrategyConfig`s (i.e. dispatchable today, no `OverlaySpec` needed). That answers the original
> dispatch question — good. Before we commit the §3.5 grammar change to express bearish direction
> (Forge emits none today; delta_target is unsigned, so Crucible always buys calls), two questions,
> because the economics split sharply:**
>
> **Q1 — which construct, and how does it clear the component gate standalone?** A *constant*
> long-put / long-vol hedge has **negative carry** → it fails `deflated_sharpe` / `profit_factor`
> standalone (it's *why* `tail_hedge` is overlay semantics, D066; its home is the PortfolioConfig
> **`tail_leg` @1.5%**, not the ordinary gate). A *timed downside-directional* bet (buy puts when a
> bearish signal fires) can be net-positive standalone. **If you mean ordinary `StrategyConfig`s
> through the standard component gate, how do you expect a long-put strategy to clear
> `deflated_sharpe` / `profit_factor`?** — that answer tells us which construct you mean (and
> whether the intake is the gate or the tail_leg overlay slot).
>
> **Q2 — what does `long_short` cross-sectional rank's short leg already supply in bear?** It's
> already enumerated (your balanced-frontier `7a5a782` is `long_short`), so we likely have *partial*
> bear exposure today. A per-regime edge read on the `long_short` short leg vs a dedicated long-put
> bet tells us whether a new put sleeve adds anything — and whether it carries the promotion-grade
> magnitude your own note says the complement lacks (or is drawdown hygiene). Validate against your
> live data before acting, per your norm.

---

## 0. The evidence (Forge-side, this week, honest-era only)

honest era = verdicts `decided_at ≥ 2026-06-10T17:17:13Z`; clean cohort = grammar v17+v18+v19.

- **0 promotions all-time.** Component (gate-pass) rate is in/above band (~5%); the gap is
  end-to-end PORTFOLIO promotion, which your `FORGE_portfolio_promotion_wiring_status.md` (06-10)
  said is bound by the assembled pool **failing CPCV-p25 / worst-quartile OOS**.
- **T3a (your era-C 342-comp book, `probe_results/worst_quartile_regime_eraC.json`):** the worst
  CPCV quartile is **BEAR 2.39× / RANGING 1.33×** regime_lift; every vol/trend/bull regime is
  at-or-below base rate. The tail is a directional-drawdown (bear) problem, consistent with the
  −63% maxDD vol-targeting finding.
- **T1 tail shadow (Forge ranker retargeted to predict cpcv_p25, telemetry-only):** decided=85,
  spearman(pred, realized cpcv_p25) **+0.451**, top-8 realized cpcv_p25 **0.727 vs 0.467
  incumbent**. The ranker *can* pick worst-quartile-robust components — when they exist.
- **D144 `regime_supply:` (per-batch journal):** **`bear selected 0 / pool 0`** every iteration;
  ranging pool ~2% (ranker already over-selects it). The complement is simply not enumerable.

## 1. The ask — two questions before Forge commits the grammar change

**Q1 — construct + standalone gate-passability.** Is the bear sleeve you have in mind a *constant*
long-put / long-vol hedge or a *timed downside-directional* bet (puts on a bearish signal)?
Concretely: **how do you expect a long-put `StrategyConfig` to clear `deflated_sharpe` /
`profit_factor` standalone** at the component gate? A constant hedge is negative-carry and won't —
which would mean its intake should be the PortfolioConfig **`tail_leg` overlay slot**, not the
ordinary gate (the D066 reason `tail_hedge` is overlay semantics). If you intend a *timed*
directional-down bet that *can* gate-pass, say so and (ideally) name the directional signal you'd
map to **long puts** at the position-builder (a macro/VIX-stress or negative-momentum reading) —
Forge will then add a signed-direction §3.5 rule (operator-gated) to enumerate exactly that.

**Q2 — what does `long_short` rank's short leg already supply in bear?** `cross_sectional_rank`
with `direction_mode="long_short"` is already enumerated (your balanced-frontier `7a5a782`), so its
short leg is *already* bear-adjacent downside exposure. A per-regime edge read (the `long_short`
short leg vs `long_only`, on your CPCV-by-regime calendar) tells us **(a)** whether we already have
the bear leg — making a dedicated put sleeve redundant — and **(b)** whether a downside-directional
put bet would carry **promotion-grade magnitude in bear**, or is purely drawdown hygiene (per your
own note's caveat). This decides whether the §3.5 grammar work is worth it at all.

**Fallback (only if Q1 says "neither — it must be an overlay"):** is `OverlaySpec` on your roadmap
(the contracts model + submission path), so a portfolio-level `tail_hedge`/tail_leg overlay can be
dispatched without the `runner.py:397` `RunnerError`? Forge's `search_space.py:69–79` already
anticipates re-admitting `tail_hedge` via an "overlay-aware enumeration path" once that lands.

## 2. What Forge is NOT asking
No gate change, no threshold relaxation, no promotion-bar move (hard rules 3/6 hold). This is a
*supply* question. Forge will not enumerate any bearish config until you answer Q1/Q2 — **zero inbox
pollution** until the dispatch-valid path and the construct are confirmed.

---

*Relay status: drafted 2026-06-14; revised same day after Crucible's agent suggested ordinary
`StrategyConfig` enumeration — re-pivoted to Q1 (construct + standalone gate-passability) + Q2
(`long_short` short-leg bear edge), OverlaySpec demoted to fallback. Awaiting operator relay (see
`docs/tasks/crucible-handoff.md`).*
