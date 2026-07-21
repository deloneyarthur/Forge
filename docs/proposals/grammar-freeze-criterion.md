# Grammar Freeze Criterion

**Status: SCOPING (docs-only) — the measurable definition of "the grammar is done."**
Operator directive 2026-07-21: "optimize and maximize the grammar as much as possible … the
search_n_trials and freeze criterion (without opening Path C)." Establishes when Forge stops
bumping `grammar_version` and commits the search budget to the converting core. No code path,
grammar, or determinism touched by this document.

Relates to: [[promotion-gate-tiers-and-constraint]], [[grammar-review-expansion]],
[[exhaust-long-options-before-v2-spreads]]; hard rules #1/#4/#6/#10; §12 phases. Instrument:
`scripts/search_multiplicity_census.py` (D1). Precedent for the enumeration-policy bump class:
D098/v5 (rules text unchanged, version bump for funnel attribution).

## Why a freeze, and why now

Prior analysis (STATUS 2026-07-21; the memory ledgers) established that grammar **expansion**
cannot raise the promotion cap — that is structural (Path C, parked) — and the signal surface is
exhausted (23/72 registered indicators dark, none correctly-signed for a net-long-vol book). The
remaining lever is **convergence**: retire dead/refuted enumeration cells so the frozen grammar
is minimal and defensible, and the stream spends its budget on cells that convert.

**Honest scope (state it plainly):** the DSR hurdle is *slot-scoped*
(`search_multiplicity.slot_key` = hypothesis × dte_bucket × xsect/named), and the converting
slots carry ~0 within-slot dead mass. So pruning **cannot lower the converters' DSR hurdle** —
that hurdle is honest search breadth. Freezing buys a **minimal, auditable surface + reclaimed
throughput + a clear line under the v1 producer program**, not a promotion. Promotion stays the
structural question this document deliberately does not open.

## Baseline (census, forge.db snapshot 2026-07-21T21:24Z; 526,789 distinct configs)

| Class | Share of all-time multiplicity | Meaning |
|---|---|---|
| converting | 51.5% | produced a component/promote in the recent window |
| protected | 11.2% | matches a `farming` campaign (`mr-timer-duration`, `ve-exit-repair`) |
| already_pruned | 7.9% | emission-excluded (v31/v33/v34); recent rows are the aging tail |
| disabled_legacy | 2.9% | `regime_arbitrage` (D098) + `tail_hedge` (D066) — not enumerated |
| legacy_inactive | 12.5% | 0 recent submissions — old versions, already gone |
| **dead_unprotected** | **4.1%** | **still emitted, still ~0 conversion — the prune backlog** |
| thin | 10.0% | too few recent submissions to judge |

**Freeze metric (B), current flow:** of the last 14 days of submissions, **2.80%** land in
dead-unprotected cells. The backlog is 13 cells, dominated by the single-name (`named`) trend/MR
gated axis (deferred — see below) plus `event_momentum` `named` (same class: its productive
cross-sectional form is not generated). `relative_value` is already dormant (0 recent flow).

## Definition of "frozen"

The grammar is **frozen** when `grammar_version` stops bumping, `enumeration_inputs_hash`
stabilizes, and the search/throughput budget is committed to the converting core. Post-freeze,
new alpha work is Crucible-selection-side (assembly, gating), not Forge-generation-side. Freeze
is a **checkpoint, not a terminus** — the reopeners below are first-class.

## The two freeze conditions (both read off the census)

**(A) Coverage.** Every cell carrying material current flow is classified
`{converting | refuted-and-pruned | protected-with-an-open-read}`. No cell carries material flow
with *unmeasured* promotion potential. Operationally: the census `dead_unprotected` ledger is
empty of any cell that has not been either (i) pruned via a version bump, or (ii) explicitly
deferred with a named open decision (a Crucible relay or a farming campaign).

**(B) Multiplicity efficiency.** The dead-unprotected share of current flow (metric B) is below
an **operator-set threshold** and **stable over N census runs**. The threshold is set from the
baseline, not invented here — mirror the robustness-streak pattern (record the raw series first,
operator finalizes the bar). Baseline is 2.80%; a natural target is to drive it to the residual
that remains after the deferred single-name-axis read resolves, then hold.

Freeze is declared when **(A) and (B) both hold and B has been stable** across the census series.

## The freeze ledger (how progress is tracked)

Two standing records, both already in the tree:
- **The refutation registry** — `enumeration/refutations.py` consumer + Crucible's
  `refutations.yaml` (D313/D320): what has been ruled dead and is being routed off.
- **The census JSONL** — `scripts/search_multiplicity_census.py`, productionized into the daily
  timer (`search_multiplicity_census.jsonl`) + a `forge healthcheck` reader (D1 Step 1b): the
  running metric-B series and the live dead-mass ledger.

## Reopeners (freeze is reversible)

Any of these reopens a `grammar_version` bump after a freeze, each operator-gated:
1. **A Crucible refutation retraction** — a cell ruled dead is re-validated (the ghost-era class).
2. **A new registry family with a net-long-vega mechanism argument** — a genuinely orthogonal,
   correctly-signed signal (not the currently-dark seller-side surface set).
3. **A Path-C structural decision** — the operator un-parks defined-risk structure. This raises
   the cap and necessarily reopens the grammar (`exhaust-long-options-before-v2-spreads`).

## Governance (every prune, before and after freeze)

Each retirement is its own operator-gated increment:
- **Class:** enumeration-policy bump (rules text unchanged — D098/v5), or an emission-exclusion
  edit in `search_space.py` (the `_DIRECTIONAL_POOL_EXCLUDED_IDS` / `DISABLED_HYPOTHESES` /
  `_REGIME_GATE_GLOBALLY_EXCLUDED_IDS` pattern). Auto-*tightening* needs no approval (hard rule
  #4); the deploy/restart is operator-gated (CLAUDE.md).
- **Version + archive + Decision Log** (hard rule #10), goldens re-pinned (removing draws shifts
  the sequence — v43 precedent), emission proof (0 draws of the retired cell).
- **Prereg first** (D207): register the predicted post-cut conversion ≈ 0 on the pruned cells with
  a cohort cut *before* the edit (mirror the v43 rider prereg `44a4e08aef4f`); resolve on post-cut
  evidence via `forge prereg resolve`.
- **Funnel attribution** (`funnel --compare vN vN+1`), STATUS block + D-entry.

## Backlog (census-derived, 2026-07-21)

| Item | Flow share | Disposition |
|---|---|---|
| `relative_value` (dormant) | ~0% (surface only) | **Clean prune** — refuted (D215/D276), retire to shrink the surface + prove the machinery (v47, `docs/proposals/v47-dead-hypothesis-retirement.md`). |
| Single-name (`named`) trend/MR gated axis | bulk of the 2.8% | **Deferred** — single-name components are Crucible's assembly-diversity source (~15.9% of the honest pool, D215/D186); needs a Crucible "do books consume these?" read before retiring. Draft the relay. |
| `event_momentum` `named` | ~0.4% | **Deferred** — dead in its `named` form, productive cross-sectional form not generated; joins the single-name-axis read (not a standalone clean prune). |
| Single-name `volatility_event` | (protected today) | **On probation** — `ve-exit-repair` farming campaign; re-anchors on the v38-vs-v39 ve funnel, not a prune target until then. |
