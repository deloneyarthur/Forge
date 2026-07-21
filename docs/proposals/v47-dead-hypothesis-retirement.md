# Proposal: v47 — retire `relative_value` from enumeration (first freeze prune)

**Status: STAGED (operator-gated deploy) — built nowhere yet; this doc + the prereg are the
gate.** The first prune of the freeze program (`docs/proposals/grammar-freeze-criterion.md`).
Deploys on the operator's word via `docs/tasks/deploy.md`; rides its own window or the next
grammar bump.

Source: the D1 search-multiplicity census (`scripts/search_multiplicity_census.py`, baseline
2026-07-21). Relates to: [[promotion-gate-tiers-and-constraint]] (relval refutation D215/D216),
[[grammar-review-expansion]]; hard rules #1/#4/#6/#10; D098/v5 (the enumeration-policy bump
precedent). Class: **auto-tightening** (removes a hypothesis; hard rule #4 permits it without
approval — the deploy/restart is the operator gate).

## The change

Add `relative_value` to `DISABLED_HYPOTHESES` in `src/forge/enumeration/search_space.py:102`
(today `frozenset({"regime_arbitrage"})` → `frozenset({"regime_arbitrage", "relative_value"})`).
This stops enumeration while leaving every relval code path intact (the pairs combiner, the
universe-template underlying=None path) — exactly the `regime_arbitrage`/D098 pattern, so a
reopener is a one-line revert, not a rebuild. `rules:` text is unchanged; the `grammar_version`
bump v46 → v47 exists solely for Crucible funnel attribution.

## Evidence (census + prior refutation)

- **Refuted with data, not by construction:** cross-sectional relval rank-IC −0.038 (t −2.2),
  corr-to-MR 0.88, residual IC −0.044 — no orthogonal directional edge (D215, prereg
  `9b88966c446a` RESOLVED REFUTED; reaffirmed D276). It is ranker-zeroed today (D145 floor
  exemption).
- **Already dormant:** the census shows `relative_value swing_short/swing_mid named` at **0
  decided in the last 14d** and **not in the dead-mass flow ledger** (below the liveness floor) —
  it is enumerated but not reaching submission. Retiring it therefore reclaims ~no current
  throughput; its value is **surface minimality** (removes ~4% of all-time multiplicity from the
  frozen picture) and **proving the freeze machinery on a zero-risk case**.

## NOT in this proposal — `event_momentum` (census correction of record)

The freeze plan floated `event_momentum` as a co-prune. The census refutes "clean": it exists
**only** as single-name (`named`) `sue × days_since_earnings` (~606 submitted/14d, **0 recent
components**), and **no cross-sectional `event_momentum` slot is generated at all**. That is the
same "productive form not enumerated" pattern as the single-name trend/MR axis — retiring the
`named` form could discard a form whose xsect variant was never tried. So `event_momentum` is
**deferred into the single-name-axis Crucible read**, not retired here. Honest scope: v47 is
`relative_value` alone.

## Prereg (register BEFORE the edit — D207)

`forge prereg register --claim "v47 relative_value retirement: post-cut relval conversion ≈ 0
and no conversion displaced to other hypotheses" --predicted "<= 0.001 pooled post-cut relval
conversion; converting-slot component rate unchanged within noise" --action "confirm the
retirement lost nothing" --cohort-cut <deploy-window-open>` → commit `config/preregistrations.jsonl`
so the prediction is recorded before its test. Resolve on post-cut evidence via `forge prereg
resolve`.

## Determinism & test surface

- Removing a hypothesis from enumeration **shifts the draw sequence** → the sampler/enumeration
  **goldens re-pin** (v43 precedent: onset at the first pool-tapping config; regime goldens shift
  first). Environment-matched re-pin in the build window.
- **Emission proof:** enumerate N cold seeds against the live registry → **0 `relative_value`
  configs** post-change; all other hypotheses still reachable.
- `test_v1_grammar_loads` → v47; `NON_ENUMERABLE_HYPOTHESES` invariant coverage picks up the new
  member (mirror the `regime_arbitrage` assertions).

## Ritual (one operator-gated window — `docs/tasks/deploy.md`)

Build grammar-gated → `../Forge-build` worktree (this tree is production, D104). Register prereg →
edit `DISABLED_HYPOTHESES` → `grammar.yaml` v47 header note + `grammar_version` bump → archive
`config/grammar_archive/v47.yaml` → re-pin goldens → full uncontended suite green → emission proof
→ stop service → commit → restart → verify journal (grammar_version=v47, no traceback) →
`funnel --compare v46 v47`. STATUS block + D-entry. Reversible: drop `relative_value` from the
frozenset (a future relval reopener — e.g. a sector/GICS ingest that decorrelates it — would
re-admit it with its own bump).
