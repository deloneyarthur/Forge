# Proposal / scoping: edge-magnitude — regime-orthogonal arms (the promotion unlock)

Status: **SCOPING (research framing) — no code; defines the problem, the paths, and the first
experiments.** Date: 2026-06-14. Relates to: [[D146]] (the magnitude reframe), [[D148]] (Crucible
greenlight + the "regime-orthogonal arms" pointer), `edge-magnitude-levers.md` (the expressivity
inventory), `worst-quartile-complement-supply.md`. Backing data (Crucible-side):
`probe_results/cpcv_crater_by_regime.json`, `regime_durability.json`, `worst_quartile_regime_eraC.json`.

## Why this exists — the one lever that can actually move promotions

Everything shipped so far (T1 ranker, T2 ranging supply D150/D151, rv de-emphasis D145) is
**selection / breadth / tail hygiene** — Crucible was explicit and we verified it: it improves *what
the pool holds* but does **not** cross the binding wall. That wall is **edge MAGNITUDE**: every family
is positive in its best regime but **none means a CPCV Sharpe ≥1.5 on any regime slice (pool best
1.10)**; the worst quartile is **bear (2.39×) / ranging (1.33×)**. So the promotion unlock is a single
thing: **an arm with promotion-grade per-regime magnitude in an adverse regime, orthogonal to the
trend/vol-event factors that dominate the pool.** This scopes how Forge — a producer that computes no
metrics (§1.2), options-only, **net-debit single-leg long-premium, spreads banned** — could produce one.

## The structural frame (the hard truth, grounded)

Forge's grammar is **net-debit long-premium** (`Direction={LONG_CALL,LONG_PUT,FLAT}`, `qty≥0`, spreads
banned; D-confirmed, `FORGE_indicator_gaps_response.md` §1). Two consequences set the magnitude ceiling:

1. **The VRP headwind.** Long premium *pays* the variance risk premium on average — you are buying the
   thing that is, unconditionally, rich. Carr-Wu (RFS 2009): unconditioned single-name premium has
   little edge; **conditioning is everything.** Goyal-Saretto (JFE 2009): the documented edge is
   *conditional* long-premium (long where IV is cheap vs the name's own realized — shipped as
   `iv_minus_rv`), and the gross decile spread (~22%/mo) collapses to ~4%/mo **at quoted-spread costs
   — costs, not decay, are the binding constraint.** So within long-premium, magnitude is gated by
   (a) conditioner IC and (b) execution cost, and the headline edges barely survive costs.

2. **The high-magnitude adverse-regime edges are OUT OF v1 SCOPE.** The natural high-Sharpe play in
   **ranging/chop is premium SELLING** (theta harvest — short strangles/iron condors): structurally
   forbidden (short premium + spreads banned). The natural **bear** play is short/put-spread or a
   portfolio **tail overlay**: the overlay is Crucible-owned (`tail_leg`, D148), spreads are banned.
   Long puts *are* expressible (`LONG_PUT`), but a standalone long-put bleeds the VRP (Crucible: the
   `long_short` short leg is net-negative in bear). **So the two regimes the wall lives in are exactly
   where v1's long-premium-only constraint is weakest.**

**Bottom line:** the unlock is unlikely to come from "enumerate harder." It comes from one of three
paths — a higher-IC conditioner, lower execution cost, or a scope expansion — and two of the three are
Crucible/operator-gated. That reframes "regime-orthogonal arms" from a search problem to a
**signal-quality / cost / scope** problem.

## Three paths to magnitude

### Path A — a higher-IC conditioner/signal within long-premium [Crucible-publishes-indicator]
Lift the predictor, not the payoff. The pool's conditioners are IV-level/percentile, `iv_minus_rv`
(Goyal-Saretto), `iv_term_slope`, trend/momentum, dealer-gamma. Candidates with literature support for
*adverse-regime* option returns: **skew / risk-reversal** (crash-risk pricing), **variance-term-structure
slope** (VRP timing), **order-flow / dealer-positioning at higher fidelity** (gamma/charm/vanna),
**cross-asset / macro stress** (credit, rates, FX vol). Reach: each needs Crucible to publish the
indicator (registry) — contract-gated. **Honest:** Goyal-Saretto shows even a *good* conditioner is
cost-bound; a new conditioner must clear costs AND have adverse-regime IC, which is uncertain.

### Path B — execution-cost reduction (convert gross edge to net) [Crucible-gated, partly offered]
Goyal-Saretto says costs are the binding constraint, so *the same signal at lower cost* lifts realized
magnitude. Levers: **constant-maturity construction** (§20, Crucible-offered — removes the theta-bleed
confound, cleaner option_momentum/straddle returns), **liquid-universe / wider-DTE selection** (lower
bid-ask drag), **rebalance discipline**. Reach: §20 is offered (held); the rest is selector/grammar
tuning (Forge-side) + Crucible cost modeling. Lower risk than A, bounded upside.

### Path C — scope expansion beyond long-premium [hard-rule-9 / v1-scope; operator + Crucible]
The structural fix for the adverse-regime magnitude gap: **defined-risk spreads / conditional
premium-selling** (verticals, condors, calendars). This unlocks the *natural* ranging theta edge and a
bounded-risk bear structure — the high-magnitude plays v1 forbids. But it's a major decision: Crucible's
runner, gates (§8.7), and risk model must support multi-leg/defined-risk, and it re-opens hard rule 9
(single-leg long-premium). Biggest upside, biggest lift, fully operator+Crucible-gated.

## Candidate arms (regime × path)

| Arm (thesis) | Regime | Edge basis | Path | Reach |
|---|---|---|---|---|
| Skew / risk-reversal conditioner | bear | crash-risk mispricing predicts put returns | A | Crucible indicator |
| Variance-term-structure timing | high_vol/bear | VRP slope predicts long-vol payoff | A | Crucible indicator |
| Higher-fidelity dealer flow (vanna/charm) | bear/ranging | dealer hedging drives the gamma regime | A | Crucible indicator |
| Constant-maturity straddle | bull/trending | removes theta-bleed cost confound (§20) | B | Crucible (offered) |
| Defined-risk short strangle / condor | **ranging** | theta harvest in chop (the natural ranging edge) | C | scope expansion |
| Put/bear vertical | **bear** | bounded-risk downside, lower VRP bleed than naked puts | C | scope expansion |

## What to ask Crucible (the cheapest, highest-value first move)

Forge can't measure magnitude (§1.2) — Crucible can. Before any build, get the **per-family ×
per-regime magnitude + cost decomposition** (extend `cpcv_crater_by_regime.json` / `regime_durability.json`):
1. **Where is the headroom?** Which (family, regime) cells are closest to 1.5, and is the gap signal-IC
   or execution-cost? (Goyal-Saretto says cost — confirm per cell.)
2. **Would a named new conditioner** (skew, var-term-slope, dealer-vanna) plausibly lift an adverse-regime
   cell, per their data? (Directs Path A.)
3. **What would defined-risk-spread support take** on the runner/gates/contract? (Sizes Path C.)

## Recommended sequencing

1. **Relay the magnitude/cost-decomposition ask to Crucible** (above) — cheapest, and it tells us
   whether the binding gap is IC (→ Path A) or cost (→ Path B) per cell. Do this first; it directs
   everything else.
2. **Literature deep-research scan** — "single-leg long-premium option strategies / conditioners with
   documented risk-adjusted edge in bear & ranging regimes, net of costs" — to harden the Path-A
   candidate list beyond Goyal-Saretto/Carr-Wu. (Offered as the `deep-research` skill.)
3. **Decide §20 constant-maturity (Path B)** — the one cost lever already on the table.
4. **Scope-expansion feasibility (Path C)** — only if Crucible's decomposition says ranging/bear
   magnitude is structurally unreachable in long-premium (likely) AND the operator wants to re-open
   hard rule 9. The biggest, slowest, highest-upside path.

## Honest cap (hard rule 6)
This is the genuinely hard, uncertain frontier — and it may not be fully solvable inside v1's
long-premium scope. Forge cannot manufacture magnitude; it can express archetypes, lean enumeration,
and surface candidates for Crucible to measure. Expect this to be a *multi-step, Crucible-coupled
research program*, not a single increment — and be honest that the answer might be "the high-magnitude
adverse-regime edges require a scope expansion (Path C), not more search."
