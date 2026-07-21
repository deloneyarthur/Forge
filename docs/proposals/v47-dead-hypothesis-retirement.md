# Proposal: v47 — retire the dead single-name axes (single-name trend/MR + relative_value; single-name event_momentum pending)

**Status: STAGED + HELD (Path B) — operator "let's do Path b" 2026-07-21.** The first
prune of the freeze program (`docs/proposals/grammar-freeze-criterion.md`), now bundling
the Crucible-greenlit single-name trend/MR retirement. HELD until Crucible answers the
event_momentum relay (`PROMPT_CRUCIBLE_EVENT_MOMENTUM_SOXL_DEGENERATE.md`) so a fast yes
folds single-name `event_momentum` into the same deploy; a slow answer ships v47 without
it (em retires in a small v48). Deploys on the operator's word via `docs/tasks/deploy.md`.

Source: the D1 census (`scripts/search_multiplicity_census.py`) + Crucible
`FORGE_single_name_trend_mr_retirement_read_2026-07-21.md`. Relates to:
[[promotion-gate-tiers-and-constraint]], D215/D216/D268, hard rules #1/#4/#6/#10, D098/v5.
Class: **auto-tightening** (hard rule #4 permits without approval; the deploy is the gate).

## The change (three prunes, two mechanisms)

1. **`relative_value` → `DISABLED_HYPOTHESES`** (`search_space.py:102`; the
   `regime_arbitrage`/D098 pattern). Fully removed from enumeration — dormant + refuted
   (D215/D276: xsect rank-IC negative, corr-to-MR 0.88). Code paths stay intact for a
   one-line reopener.
2. **Single-name (per-name) `trend_continuation` + `mean_reversion` → xsect-only.** A
   scoped **sampler** change: force these two rank-coherent hypotheses to enumerate only
   the cross-sectional form (`combiner.type == cross_sectional_rank`, `underlying=None`);
   drop the named/single-underlying path. Their xsect form — the converting core — is
   untouched. (Exact lever designed at build time: the named-vs-universe branch in
   `_pick_underlying` / the combiner choice; determinism-critical → goldens re-pin.)
3. **Single-name `event_momentum` → xsect-only (PENDING Crucible ask #2).** Same
   mechanism as (2). Folded in only on a Crucible yes; otherwise deferred to v48.

## Evidence

- **relative_value:** refuted (D215/D276) + dormant (census: 0 recent flow).
- **Single-name trend/MR (Crucible read, decisive):** **0** single-name trend/MR slots
  across all 4 promoted books AND all 106 assemblies ever built; 363 xsect-trend / 142
  xsect-MR slots vs 0 single-name; ~361 admitted-but-never-selected components (their
  count 136 trend / 225 MR ≈ our ~130/~220). Dead-on-consumption. Slot-scoped DSR (D310)
  → different slot from the xsect converters, so no DSR-hurdle change: a throughput +
  minimal-surface win, not a promotion unlock.
- **Single-name event_momentum (contested — see the relay):** Crucible said "keep it"
  because `pure_sue175` uses a single-name em leg, BUT that leg is the **D268 degenerate**
  (SOXL, inert `sue`/`days_since_earnings`, naked long-SOXL calls, 0 PEAD; unreproducible
  post-D268/v32). The real-company single-name em Forge emits is dead (~3 components, 0
  conversion). Ask #2 settles whether it retires with (2). Retiring generation does NOT
  touch the frozen promoted leg.

## Prereg (register BEFORE the edit — D207, at the deploy-window open)

`forge prereg register --claim "v47 single-name-axis retirement: post-cut single-name
trend/MR (+relative_value [+event_momentum if folded]) conversion ~0; xsect converting-slot
component rate unchanged" --predicted "<= 0.001 pooled post-cut single-name conversion;
xsect rates within noise" --cohort-cut <deploy-window-open>` → commit `preregistrations.jsonl`.

## Determinism & test surface

- The sampler change (2)/(3) shifts the draw sequence → **goldens re-pin** (v43 precedent;
  onset at the first pool-tapping config). Emission proof: 0 single-name trend/MR
  (+em if folded) draws over N cold seeds; xsect trend/MR + all other hypotheses still
  reachable; 0 `relative_value` draws.
- `test_v1_grammar_loads` → v47; `NON_ENUMERABLE_HYPOTHESES` invariant picks up
  `relative_value`; new sampler invariants pin the xsect-only scoping for trend/MR (+em).

## Ritual (one operator-gated window — `docs/tasks/deploy.md`)

Build grammar-gated → `../Forge-build` worktree (this tree is production, D104). Register
prereg → edit (`DISABLED_HYPOTHESES` + the sampler xsect-only scoping) → `grammar.yaml` v47
header + bump → archive `v47.yaml` → re-pin goldens → full uncontended suite → emission
proof → stop service → commit → restart → verify journal (grammar_version=v47) →
`funnel --compare v46 v47`. STATUS block + D-entry. Reversible: revert the frozenset +
sampler scoping (a future reopener — e.g. a sector/GICS ingest decorrelating relval, or a
Crucible request — re-admits with its own bump).

## NOT in v47

- **Census accuracy fixes** (promoted-book-component protection via the `promoted_portfolios`
  export + the D268 no-earnings-underlying exclusion + degenerate-leg flagging) — tooling,
  not grammar; a census follow-up regardless.
- **xsect-PEAD add** — a net grammar *expansion* (Crucible ask #3), separate design + gate.
