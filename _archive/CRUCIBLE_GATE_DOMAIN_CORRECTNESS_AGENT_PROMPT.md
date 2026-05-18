# Crucible — gate-domain correctness: cross-ticker on single-asset + total_return_vs_spy on negative-carry hypotheses

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-16 — post-`9e87df8` + `a01c8fa` recovery audit by Forge-side analysis agent.
**Status:** Two correctness fixes requested. **Neither is a gate-threshold relaxation** (Forge hard rule #3 forbids that). Both are about applying gates in their correct semantic domain.

---

## TL;DR

Two gates currently reject every Forge-submitted v1 candidate for reasons unrelated to strategy quality:

1. **`cross_ticker_min_passing`** is mechanically unreachable on a single-asset universe — but only because the campaign passes `per_ticker_sharpes={"SPY": x}` (n=1) when the gate's own skip path requires `per_ticker_sharpes=None`. **Pass `None` for single-asset experiments**, or condition the skip on `len(per_ticker_sharpes) <= 1`. Either way the gate's intent is preserved (multi-ticker robustness *when applicable*).
2. **`total_return_vs_spy > 1.5×`** structurally rejects `tail_hedge` (and likely `volatility_event`) because those hypotheses are **negative-carry by design** — they buy insurance / pay event premium, not beat SPY. Other gates (PF, direction_balance) already have per-hypothesis exemptions for these. Add `tail_hedge` (and audit `volatility_event`) to the `total_return_vs_spy` exemption set.

Both changes preserve the gates' intent; they prevent the gates from rejecting candidates whose category the gate was never meant to evaluate.

## 1. The pattern (from a Forge-side analysis agent)

Forge spawned an Explore agent on 2026-05-16 to audit whether the v1 grammar can structurally clear v1 gates on SPY-only data. The agent's verdict: **structurally borderline-to-incapable, primarily because of (1) above** — the cross-ticker gate's `per_ticker_sharpes={"SPY": x}` path makes the gate mechanically impossible to satisfy regardless of strategy quality.

The agent's findings (verbatim, abridged):

> **`cross_ticker_min_passing >= 3`** (`cross_ticker_robustness.py:13-15`) — *structurally impossible* on SPY-only data when populated. If campaign passes `per_ticker_sharpes={"SPY": x}`, every SPY-only candidate fails. Only escape is for the campaign to pass `None`. Skipped only if `per_ticker_sharpes is None` (`gate.py:336`).
>
> **`total_return_vs_spy > 1.5×`** (`gate.py:137`) — categorically excludes `tail_hedge` and most `volatility_event` (negative-carry by design). PF and direction_balance bypass via `hypothesis="tail_hedge"` but the total-return gate has no such exemption (`gate.py:317-319`).

## 2. Fix 1 — `cross_ticker_min_passing` on single-asset

### Proposed fix shape (your call between two)

**(a) Campaign-side**: where `per_ticker_sharpes` is constructed, return `None` instead of `{"SPY": x}` when `n_tickers == 1`. Single-point fix at the source.

**(b) Gate-side**: in `cross_ticker_robustness.py`, treat `len(per_ticker_sharpes) <= 1` the same as `is None`. Defensive: catches any future single-asset caller path.

Both are correct. (a) is closer to the data; (b) is closer to the policy. Probably both — they're complementary. The test should construct a single-asset run and assert the gate is skipped (not failed).

### Why this is not a gate relaxation

The gate's intent is "if you have multi-ticker results, ≥3 must clear Sharpe 0.5." On single-asset data the gate has no signal to evaluate — it's not that the strategy passed or failed cross-ticker robustness, it's that the test doesn't apply. Skipping is the correct semantic. The Forge hard rule #3 reading is consistent with this: "the gate cannot be lowered" applies to thresholds and to scope, but skipping a gate in its undefined domain is neither.

If there's any doubt, treat single-asset as a temporary v1 limitation and surface to the operator — but I (Forge agent) believe (a)+(b) is the obviously-correct semantic.

## 3. Fix 2 — `total_return_vs_spy` per-hypothesis exemption

### Proposed fix shape

In `gate.py` around the `total_return_vs_spy` evaluation site (L137 / L317-319 per the analysis agent's reference), add `tail_hedge` to the exemption set the way PF and direction_balance already do. Audit whether `volatility_event` belongs in the same set.

### Why this is not a gate relaxation

The gate's intent is "the strategy must outperform buy-and-hold SPY by ≥1.5× total return." This makes sense for directional, mean-reversion, and trend strategies whose claim is alpha-over-passive. It does **not** make sense for negative-carry strategies whose claim is convex tail protection (`tail_hedge`) or event-premium capture with deliberately-low expected return (`volatility_event` — though this needs your verification). For those, the right comparison is risk-adjusted (Sharpe vs zero), not absolute return vs SPY.

Per CLAUDE.md hard rule #3, gate strictness can't change; but the gate's *domain* (which hypotheses it applies to) is a separate concept. Other gates already implement this pattern, so the precedent is established.

## 4. What you should NOT do

- **Do not lower** `walk_forward_sharpe_median`, `cpcv_sharpe_p25`, `deflated_sharpe`, `calmar_median`, or any other quality-bar thresholds. The Sharpe/Calmar/DSR triad's tightness on SPY-only is a separate operator-level scope decision (broaden universe vs. accept 0 promotions); not something Crucible should resolve unilaterally.
- **Do not add a "skip cross-ticker on single-asset" without the test** — the failure mode that lands today is "campaign passes empty/single-ticker dict, gate fires anyway." Write the invariant test first per TDD discipline.
- **Do not change Forge code.**
- **Do not silently apply the `tail_hedge` exemption without verifying** by reading §3.5 R5 + the hypothesis's exit-stack spec. If the exemption is wrong for `volatility_event`, leave it for a follow-up rather than expand the blast radius.

## 5. Background data sources

- Forge audit report: spawned 2026-05-16 by a Forge-side Explore-class agent. Key citations:
  - `/home/aj/proj/Crucible/src/optbt/experiment/gate.py:128-139` (`DEFAULT_GATE_THRESHOLDS`)
  - `gate.py:148-152` (per-DTE min_oos_trade_count map — already shipped)
  - `gate.py:336` (cross-ticker skip-on-None)
  - `gate.py:317-319` (PF / direction_balance hypothesis exemptions — pattern to follow)
  - `gate.py:137` (`total_return_vs_spy`)
  - `cross_ticker_robustness.py:13-15` (gate threshold definition)
  - `quality_bar.py:24-26` (related quality bars)
- Forge grammar / hypothesis definitions: `/home/aj/proj/Forge/docs/DESIGN.md` §3.5 (rules R1-R5)
- Hard rules: `/home/aj/proj/Forge/CLAUDE.md` (rule #3: never lower the gate)

## 6. Output expected

For each of the two fixes:

1. Confirmation that the diagnosis is right (or pushback with citation)
2. The fix's shape (which of options above, or a different one)
3. Invariant test landing alongside (TDD red→green, ship the test first)
4. Decision Log entry in the canonical Crucible-side log citing this prompt

If either fix is more complex than this prompt suggests (e.g., `volatility_event` exemption is wrong, or `cross_ticker_min_passing` has dependencies I missed), surface the trade-off and stop on that one — ship the other.

Brief is OK. Aim for under 600 words across both fixes unless something material surfaces.
