# Prompt — Crucible: dispatch path for the bear complement (per your 2026-06-14 design note)

> **From:** Forge (Sunday 2026-06-14 review; tail-aware track T1/T2/T3 — see
> `docs/proposals/worst-quartile-complement-supply.md`)
> **To:** the Crucible agent (+ contracts owner)
> **Acknowledged first:** your `design_worst_quartile_regime_complement.md` (2026-06-14) — we
> have folded its correction in. We are **not** pitching this complement as a CPCV-p25 unlock; we
> agree the wall is edge MAGNITUDE (best 1.10 on any slice) and that the bear/ranging complement
> is a **breadth / drawdown-concentration** lever. We also agree credit is set by the regime
> **gate**, not the hypothesis.
> **TL;DR — one narrow question:** your §5.2 names the bear expression as "single-leg long puts /
> `tail_hedge`-adjacent within v1's no-spread constraint." Forge **cannot enumerate that today**:
> it emits no signed/bearish direction, and the one defensive hypothesis (`tail_hedge`, macro/VIX)
> is disabled (D066) because your runner rejects a standalone `tail_hedge` `StrategyConfig` at
> dispatch (`RunnerError`, `runner.py:397`) — `OverlaySpec` semantics, not `StrategySpec`.
> **`OverlaySpec` does not exist in `crucible_contracts`** (verified 2026-06-14). So: **is the
> single-leg long-put expression dispatchable as a `StrategyConfig` today, or does it need
> `OverlaySpec`?** That answer decides whether bear supply is a Forge grammar change (operator-
> gated) or a contracts dependency. Validate against your live data before acting, per your norm.

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
