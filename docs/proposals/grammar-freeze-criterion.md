# Grammar Freeze Criterion

> **⚠️ RE-BASED 2026-07-22 (D330) — read this box before using anything below.**
>
> Conditions (A) and (B) below, and the baseline table, are computed from Forge's
> `verdicts` ledger — which is **94% Crucible stage-one screen rows**
> (`measurement_basis = 'standard_window'`). That lane yields coverage-honest labels at
> **0.064%** and *structurally cannot* produce a component; the honest population is the
> **stage-two `fullhist_refit`** lane (80.8% honest, 5.9% of the feed). So metric B
> (2.11%) and the whole dead-mass ledger are **stage-one artifacts**, and the
> `converting` / `dead_unprotected` classification is measured on the wrong basis.
>
> **Three corrections, all landed in the joint program (`~/proj/freeze`):**
> 1. **Basis.** Grammar quality is measured on `measurement_basis = 'fullhist_refit'`,
>    never stage-one (joint charter §2, signed).
> 2. **Metric.** Component **admission is not a quality metric** — 593/593 stage-two rows
>    fail `cpcv_sharpe_p25` while 80.8% are admitted. Admission is a pool bar. The quality
>    axis is the **CPCV distribution**, and `GateResult.value` puts it within Forge's
>    reach today (100% `config_hash` join to stage-two rows, no contract change).
> 3. **Vocabulary.** `unverified` (could not evaluate) / `failed` (evaluated, failed) /
>    `honest` (evaluated, passed) — never a two-way split. Conflating the first two
>    inverted a conclusion on 2026-07-22 and set a bar ~250× too loose.
>
> **A new condition (C) is added below and is now the binding one.** Conditions A and B
> survive as *surface/throughput* conditions and must be re-derived on the stage-two
> basis before they mean anything.

**Status: SUPERSEDED IN PART — the measurable definition of "the grammar is done."**
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

**(B) Multiplicity efficiency — RE-BASED 2026-07-22 (D331 item 2); the pre-re-base series is
NOT comparable.** The census now requires an **honest** component before calling a cell
`converting`, and adds an `unevaluated` class for cells with flow but zero honest
evaluations (never a prune target — a new cell is in that state by construction, and
pruning it is the v17 cold-start mistake). **Metric B moved 2.11% → 0.85% on the same
snapshot. That is a definitional change, not progress:** the drop is `unevaluated` mass
no longer being counted as dead. The operator threshold must be re-set against the new
baseline, and the 2.80% / 2.11% readings belong to the old basis. **A third number is now
visible and is arguably the more actionable one: 11.0% of all-time multiplicity sits in
cells that have never had a fair hearing.**

The dead-unprotected share of current flow (metric B) is below
an **operator-set threshold** and **stable over N census runs**. The threshold is set from the
baseline, not invented here — mirror the robustness-streak pattern (record the raw series first,
operator finalizes the bar). Baseline is 2.80%; a natural target is to drive it to the residual
that remains after the deferred single-name-axis read resolves, then hold.

**(C) Quality ceiling, on the stage-two basis — ADDED 2026-07-22 (D330), and binding.**
The grammar is exhausted when, on `measurement_basis = 'fullhist_refit'` at n ≥ 300 per
version: (1) admitted **median** CPCV shows no improvement over N trailing versions,
**and** (2) **p90** CPCV does not move — the ceiling, not the centre, since the centre
drifts on cell mix alone — **and** (3) no newly-added component clears a pre-set
within-cell lift bar on *both* admission and CPCV.

**Where (C) already stands, measured (2026-07-22):**

| reading | value | source |
|---|---|---|
| admitted median CPCV, v18 → v42 | 0.5881 → **0.4340** (declined; best figures are the oldest) | `freeze/analysis/forge_convergence_read_2026-07-22.txt` |
| admitted p90 across 20 versions | **0.6695–0.8646, no trend** | same |
| stage-two rows ever clearing CPCV 1.5 | **8 of 16,873** (0.047%) | `freeze/data/crucible/stage2_quality_by_version_2026-07-22.json` |
| best / worst measurable cell (medCPCV) | `bb_pct` 0.5619 / `residual_momentum` 0.2406 | `freeze/data/forge/forge_cell_cpcv_scorecard_2026-07-22.json` |
| stage-two coverage of v43–v48 | **zero** | Crucible per-version artifact |

Read strictly, **(C)(1) and (C)(2) are already satisfied on the historical series** — the
ceiling has not moved in 20 grammar versions and ~481k stage-one runs, and the entire
cell range sits below *half* the promotion gate. Forge deliberately does **not** claim
this, because the five versions carrying our largest structural changes (v43–v48) have
zero stage-two rows. Declaring exhaustion on a series ending at v42 is the basis trap.

**The blocking constraint is the stage-two FEED, not throughput and not optimization.**
(Corrected 2026-07-22 — an earlier version of this paragraph proposed a stage-one intake
cut on a "divergence, not a backlog" argument. That was **wrong**: Crucible's scanner is
`ORDER BY pd.decided_at DESC`, re-derived every pass, so new work never queues behind old
work and cutting intake would not have improved v47/v48 coverage. Operator refused it on
exactly that ground.)

The real mechanism: `_triggers_rederive` admits a stage-one row into stage two via
`reject → coverage_blocked_component` or `component → not-honest-coverage`. **The reject
path has contributed ZERO all along** — `deflated_sharpe` fails ~100% of forge rows and is
absent from `_COMPONENT_ELIGIBLE_GATE_FAILURES`, failing the subset test. So *every*
version's stage-two feed came from the component path: the `rank_k=20` unverified bypass.
**v48 closed that bypass, so v48 feeds ZERO rows into stage two** (v46 508, v47 509,
**v48 0**). Crucible's DESIGN.md §20 `dsr-record-not-binding-forge-minimal` already ruled
DSR must not bind here; the exemption landed in `_verdict_from_gates` but never reached
`fullhist_refit.coverage_blocked_component`. Honoring it (source-scoped, `wf>0`/`cpcv>0`
untouched, so **not** a gate relaxation) would take v48 from 0 to 368 eligible rows in our
window sample. **Until that lands, condition (C) cannot be evaluated on v48 at any n.**

Freeze is declared when **(A), (B) and (C) hold**, A and B re-derived on the stage-two
basis, and (C) evaluated on a set that includes **v47 and v48**.

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
