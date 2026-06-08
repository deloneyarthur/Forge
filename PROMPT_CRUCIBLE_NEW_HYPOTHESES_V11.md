# Prompt — Crucible: three pieces for Forge's v11 breadth program (1 contracts, 2 runtime)

> **From:** Forge (D107 program, grammar **v11** — design stage, see `NEW_HYPOTHESES_V11_PLAN.md`)
> **To:** the Crucible agent (+ contracts owner — part A is the contracts repo)
> **TL;DR:** Forge's data says the binding constraint on component yield is **breadth
> (trade count)**, not signal quality — `min_oos_trade_count ≥ 100` rejects 98% of
> candidates, and vol_event out-mints the directional archetypes 5–8× only because
> events recur. Forge is opening a four-part program to manufacture breadth and
> diversify the component pool. **Two parts (H3 gamma-regime, H4 orthogonal-yield)
> are Forge-only and need nothing from you.** Three things are yours: **(A)** an
> additive contracts bump, **(B)** a cross-sectional rank-top-K runner, **(C)** two
> post-event indicators + a post-event entry window. (B) and (C) are gated behind
> Forge enumeration flags — **no Forge config will reference them until you confirm
> support**, so zero inbox pollution. Validate every claim below against live data
> before acting, per your own norm.

---

## 0. Why (the data motivating all of this)

forge.db `submissions` (92,389) ⋈ your `gated_runs_2026-06-08T052422Z.json` (10,000 decided):

- **0 promotions across all 92,389 submissions / 10 grammar versions.** Agreed and
  expected (WF ≥ 2.0 is strategy-space). The currency is **components** — 1.83% (183/10k).
- **Breadth is the binding gate.** Components trade median **146**; rejects median **1**.
  98% die at `min_oos_trade_count`. This is Grinold's IR = IC·√Breadth made into a gate.
- **vol_event 5.04% vs trend 0.62% / mean_rev 0.86% / rel_value 0.98%.** vol_event wins
  because earnings + FOMC/NFP/CPI/OPEX **recur** → 60+ bets/5y on one name → clears the
  floor. The directional archetypes fire ~once on a single name → rejected before their
  IC is ever tested. **The fix is structural breadth, not better signals.**
- The 122 vol_event components are also **highly correlated** (same VRP factor, same
  calendar, 36 on AAPL) — low marginal portfolio value. (That's H4, Forge-only.)

---

## A. Contracts — additive, non-breaking (please bump 1.15.0 → 1.16.0)

So Forge's v11 scaffolding *constructs + validates* while its runtime stays disabled:

1. `CombinerSpec.type`: add `"cross_sectional_rank"` to the Literal. Add optional, defaulted
   fields: `k: int = 0` (0 = unset/non-rank), `rebalance_frequency: Literal["weekly","monthly"] | None = None`,
   `direction_mode: Literal["long_only","long_short"] | None = None`. All defaulted → existing
   `CombinerSpec(...)` calls unchanged.
2. `StrategyConfig.hypothesis`: add `"event_momentum"` to the Literal.
3. `IndicatorMetadata.family`: add `"post_event_drift"` to the Literal.

**Please confirm:** these are additive enum/optional-field changes only, so every existing
config validates byte-identically and **`config_hash` is unchanged** for all in-flight/historical
configs (the new combiner fields must not enter the hash for non-rank configs — mirror the D096
`grammar_version` exclusion treatment if needed). Forge's `check_contracts_version()` will gate
CLI startup on 1.16.0 once we adopt it.

*(No indicators are contracts literals — those register on your side, part C.)*

---

## B. Runtime — cross-sectional rank-top-K runner (H1, the long pole)

The single highest-leverage change for component yield. Today every Forge config is one
signal on **one** underlying, scored Boolean (fire/don't) → median 1 trade for directional
hypotheses. The ask: a **rank-top-K** execution path.

- At each rebalance bar: score **every universe name** by the config's directional signal(s),
  open positions on the **top-K** (top-K long + bottom-K short when `direction_mode=long_short`),
  close a name when it drops out of top-K. Trade count becomes **deterministic** (≈ K ×
  rebalances) → `min_oos_trade_count` stops being the binding constraint *by construction*.
- Your `config/universe.yaml` **already names `cross_sectional_rank`** as a `use_for` value on
  Tier 2 — so the concept is anticipated; this asks for the execution path. Background +
  academic grounding (Poh/Lim/Zohren/Roberts 2020, ~3× Sharpe) in
  `OPTION_B_CROSS_SECTIONAL_RANK_SCOPING.md`.
- **Question we need answered to scope Forge's side:** does the current runner support a
  **multi-name portfolio** backtest, or is it single-underlying-per-config today (Forge configs
  carry one `underlying`, except `relative_value` pairs)? If multi-name needs a config-shape
  change beyond the combiner type, flag it — that may need its own contracts round.
- Forge side, ready to ship on your go: enumerate `k ∈ {5,10,20}`, `rebalance ∈ {weekly,
  monthly}`, long-only vs long-short; universe-scoped (not single-underlying) configs. Held in
  a `DISABLED_COMBINERS` set until you confirm.

---

## C. Runtime — event-momentum / PEAD indicators + post-event window (H2)

Port vol_event's breadth engine to a **directional** thesis: enter **after** the earnings
print (sidesteps the IV crush your vol_event sleeves ride → orthogonal to existing components),
ride the 5–20-day drift. Needs from you:

1. **Register `days_since_earnings`** (backward-looking days). The registry currently has only
   the **forward** `days_to_earnings` — and note its ETF sentinel (999) silent-failure case
   that grammar R3 already guards against; please give `days_since_earnings` clean NaN/None for
   no-prior-earnings rather than a sentinel.
2. **Register an earnings-surprise / SUE indicator** (standardized unexpected earnings, sign +
   magnitude) — drift direction comes from the surprise sign. Family `post_event_drift` (new,
   part A) or `fundamental`, your call.
3. **Runner: post-event entry window** — enter `entry_lag ∈ {1,2,3}` td *after* the print,
   hold to a drift-decay `time_stop` (already a known exit) + momentum trailing. Confirm a
   post-event entry window is expressible in the selector/runner.

**Breadth caveat we already priced in:** PEAD on a *single* name ≈ 20 earnings bets/5y —
**below 100**. So H2 only clears your floor paired with the part-B cross-section (or multi-event
stacking). We'll sequence H2 after H1; flagging so you're not surprised if early single-name
H2 cohorts look thin on trades.

---

## D. Coordination, sequencing, attribution

- **No inbox pollution / clean cutover.** v11 ships the grammar scaffolding with H1/H2
  **enumeration-disabled**; H3 (gamma regime, Forge-only) is the *only* live grammar-gated arm.
  Forge emits **zero** `cross_sectional_rank` / `event_momentum` configs until you confirm B/C,
  then flips them on **versionlessly** (the v5→v10 enumeration-policy precedent — no new grammar
  version). So `crucible funnel --compare v10 v11` cleanly attributes **H3 only**; H1/H2 attribute
  on their flip-on date.
- **Attribution mechanism:** Forge reads component-rate **by config feature** (combiner `type`,
  `hypothesis`) from its own `submissions` ⋈ your gated export. Your export now carries
  `grammar_version` (thank you — the example carries it) — please keep it; it's load-bearing for
  this and for the D105 version-scoped reward.
- **§6-coupling reminder (your lesson, extended):** Forge's reward keys on `decision ==
  "component"`. The *rate* at which the rank-runner emits high-breadth (tradeable) configs will
  steer Forge's allocation within hours of flip-on. If you change component-screening thresholds
  or the rank-runner's fill model, flag it in a handoff exactly as you flagged the rv fix.
- **No gate change requested anywhere** (hard rule #3): this is all enumeration scope / breadth,
  never validation strictness.

---

**Owed by Forge:** the v11 grammar diff + D107 Decision Log + the `OPEN_PROPOSALS.md` loosening
entries (operator-gated), and the `DISABLED_COMBINERS` / `NON_ENUMERABLE_HYPOTHESES` flags
holding B/C dark until you land them. **Asked of Crucible:** (A) the additive 1.16.0 bump +
`config_hash`-invariance confirmation; (B) the rank-top-K runner + the multi-name-support answer;
(C) the two indicators + post-event entry window. (A) unblocks Forge's v11 bump; (B)/(C) unblock
the flip-on. Independent — ship in any order.
