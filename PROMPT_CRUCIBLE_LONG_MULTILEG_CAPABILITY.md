# Forge → Crucible: multi-leg LONG-structure capability — can the contract/runner represent a long straddle/strangle?

> **❌ ANSWERED — DEAD (2026-06-28), do not pass.** Crucible's reply
> (`../Crucible/docs/handoffs/FORGE_long_multileg_capability_2026-06-28.md`): the Ask-4 pre-check was already
> run 06-25 and **refutes the sleeve** — the cheap-vol straddle on our exact signal (`iv_minus_rv`) loses gross
> (−27% / −98.6% maxDD at 0 cost), the sign isn't robust (`residual_iv_gap` reverses it), and it dies at 5%
> cost. Capability is **single-leg-only** (contract + runner, hard rule 9); the additive change is feasible
> (1.22.0, hash-exclusion caveat) but **moot**. Both in-v1 orthogonal fronts (this + GICS-relval) now closed on
> data. §20 hard-rule-9 reconciliation gates any future multileg. Kept for the record; ready to `_archive/`.
>
> **From:** Forge. **To:** the Crucible agent.
> **TL;DR.** With cross-sectional vol_event closed (your `iv_minus_rv` pre-check, rank-IC −0.015) and plain
> relval refuted, the remaining **vol-side** in-v1 orthogonal sleeve is a **LONG STRADDLE / STRANGLE** —
> all-long (no short leg → v1-compatible under the operator's "short-leg = the v1/v2 line"). You said
> `iv_minus_rv`'s content is "monetizable solely via non-directional structures (straddles)"; this asks
> whether your **contract + runner can represent and backtest one**, so we can test the cheap-vol-conditional
> long-straddle thesis the way we tested relval/vol_event. **Forge can't price options → this is gated on your
> runner.** No bar change (hard rules 3/4/6).

## Why this sleeve (the thesis)
- The orthogonal driver v1 is missing is **non-directional long-vol** — the VRP/vol content `iv_minus_rv`
  carries. A long straddle monetizes it **directionlessly**, exactly where your pre-check pointed. Your −0.015
  was a *directional* IC; it does not touch a straddle (which profits from the move, not its sign).
- Entered **cheap-vol-conditional** (`iv_minus_rv` / `rv_rank` high = RV > IV = vol cheap), NOT unconditional
  — a different bet than the unconditional straddle that loses ~−3%/wk (Coval-Shumway). Whether the cheap-vol
  signal clears the **double**-VRP + double-cost is the empirical question, and it needs your runner.
- **All-long:** defined-risk (max loss = premium), net-long-vega, net-debit. **No short leg → no
  early-assignment hazard, no short-vol tail, no gate impact.** It is the grammar review's "net-debit AND
  net-long-vega AND defined-risk" invariant scoped to all-long — and the *lowest-risk* multi-leg structure to
  stand the capability up on (assignment risk, the headline multi-leg hazard, is structurally zero here).

## Asks (numbered, each independently answerable)

**1. [Capability] Does `StrategyConfig` + your runner represent/simulate a multi-leg LONG structure today?**
A long straddle (long call + long put, same strike + expiry) or long strangle (long OTM call + long OTM put)?
Or is it single-leg only (one option, selected by `SelectorSpec.delta_target`)? Our read of the contract is
single-leg (`models.py:316` — no `legs`/`structure_type`).

**2. [Contracts gap, if single-leg] Propose the minimal ADDITIVE, all-long-only change.**
The grammar review already maps it (your DESIGN §6.1): a `LegSpec`/`legs` model + a `structure_type` on
`StrategyConfig`. For the first cut: `legs: tuple[LegSpec, ...]` where `LegSpec = {right: call|put,
delta_target | strike_offset, ratio=1, side=LONG}`, `structure_type: Literal["single","straddle","strangle"]`,
with a **machine-checked net-debit ∧ net-long-vega ∧ defined-risk** invariant (all legs `side=LONG`, so it
holds by construction). Backward-compatible the way `grammar_version`/`source` were (optional + None/`"single"`
default → every single-leg config stays valid under `extra="forbid"`, identity-hash unchanged when unset)?
What `crucible_contracts` version?

**3. [Runner] Does the backtest runner price multi-leg P&L?**
Joint entry/exit at the combined debit, combined Greeks, defined-risk payoff. And two-leg execution realism —
your ORATS-style fill model across two legs (~2× single-leg slippage; the OTM strangle legs are the illiquid
ones). This is where multi-leg P&L is easy to overstate; we want your honest cost model in the loop.

**4. [Pre-check — optional but decisive; the relval/vol_event move] Can you cheaply pre-check the edge first?**
Before any enablement, the straddle-relevant question is **not** directional IC — it's whether `iv_minus_rv` /
`rv_rank` ranks names whose forward **realized** vol exceeds the **implied** vol paid (the straddle's
breakeven), by enough to clear double-VRP + double-cost. If you can run that on existing chain data (as you ran
the `iv_minus_rv` directional IC), it **settles the sleeve without building anything** — the cleanest possible
outcome, either way.

## What Forge does under each answer
- **Capable already** → operator-gated grammar v2-extension (all-long straddle/strangle) + a gated
  cheap-vol-conditional straddle release, pre-registered like relval/vol_event.
- **Single-leg + contracts gap** → we co-scope the `LegSpec`/`structure_type` addition (additive,
  all-long-only first). Build is operator+Crucible-gated; design is in
  `docs/proposals/long-straddle-strangle-v1-sleeve.md`.
- **Pre-check dead** → concede the vol sleeve, focus on the GICS-relval sleeve + other quality levers. No
  build wasted — exactly as the `iv_minus_rv` pre-check just spared us the vol_event enable-then-test loop.

## Forge-side state for reference
- `StrategyConfig` single-leg (`crucible_contracts/models.py:316`; one option via `SelectorSpec`,
  4 mandatory §6.5.1 exits). grammar_version **v22**.
- Sibling in-v1 sleeve in flight: **GICS/sector-relval** (`PROMPT_CRUCIBLE_GICS_RELVAL_INV1.md`) —
  complementary driver (sector-value vs vol). Both keep v1 open; **v2/spreads (short legs) is NOT being
  opened** — this is all-long only.
- This relay is a capability/evidence ask; the enablement, if pursued, is an operator-gated grammar
  v2-extension that adds NO short-vol exposure and does not move the gate.
