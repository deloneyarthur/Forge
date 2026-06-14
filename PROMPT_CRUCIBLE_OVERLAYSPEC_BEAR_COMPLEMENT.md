# Prompt — Crucible: OverlaySpec is the unlock for the worst-quartile BEAR complement

> **From:** Forge (Sunday 2026-06-14 review; tail-aware track T1/T2/T3 — see
> `docs/proposals/worst-quartile-complement-supply.md`)
> **To:** the Crucible agent (+ contracts owner — the ask is an `OverlaySpec` contracts model)
> **TL;DR:** Forge now has live evidence that the binding constraint on portfolio promotion is
> **worst-quartile (CPCV-p25) robustness**, and that the worst quartile is disproportionately a
> **BEAR-regime** problem. Forge **cannot supply a bear complement** — it is options-only,
> single-leg, long-premium, no spreads, no signed direction (hard rules 7/9). The one
> structurally-defensive hypothesis, `tail_hedge` (macro/VIX, long-vol), was disabled by D066
> because your runner rejects a standalone `tail_hedge` `StrategyConfig` at dispatch
> (`RunnerError`, `runner.py:397`) — it is `OverlaySpec` semantics, not `StrategySpec`.
> **`OverlaySpec` still does not exist in `crucible_contracts`** (verified 2026-06-14). This is
> the contracts gap that gates the entire bear complement. No new urgency is invented here —
> we're attaching the now-measured *need* to a long-known gap. Validate every claim against your
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

## 1. The ask

Is `OverlaySpec` on your roadmap, and what's the shape? Specifically:
- **(a)** Will `crucible_contracts` gain an `OverlaySpec` (vs `StrategySpec`) so a portfolio-level
  `tail_hedge` overlay can be submitted and dispatched without the `runner.py:397` `RunnerError`?
- **(b)** What does the overlay submission path look like (separate inbox? a field on the book?
  an overlay-attached `PromotedPortfolio`?) — Forge's `search_space.py:69–79` already anticipates
  an "overlay-aware enumeration path" that re-admits `tail_hedge` once the model lands.
- **(c)** If `OverlaySpec` is far off: is there a **single-leg long-put** path you'd accept as a
  `StrategyConfig` today (i.e. would you map a *bearish* directional signal — e.g. a macro/VIX or
  negative-SUE reading — to **long puts** at the position-builder)? If yes, Forge could enumerate
  the bearish side of existing directional families as an interim bear supplier (operator-gated
  grammar change on our side). We will reference nothing until you confirm the mapping, so **zero
  inbox pollution**.

## 2. What Forge is NOT asking
No gate change, no threshold relaxation, no promotion-bar move (hard rules 3/6 hold). This is a
*supply* question: how to legally place bear/defensive exposure into the assembled pool so the
worst-quartile constraint can actually be met. Forge will not enumerate `tail_hedge` or any
bearish config until you confirm a dispatch-valid path.

---

*Relay status: drafted 2026-06-14, awaiting operator relay (see `docs/tasks/crucible-handoff.md`).*
