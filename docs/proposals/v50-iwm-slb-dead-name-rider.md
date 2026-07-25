# Proposal: v50 — IWM + SLB structural-exclusion rider (yield-audit round 2)

Status: **STAGED (operator "yes", 2026-07-24) — awaiting the deploy window.** Ships
as its own bump (v50) or rides the next Crucible-driven bump, whichever comes first.
Prereg `8eaa7e4aca93` is on record (cohort cut 2026-07-24T18:28:23Z) BEFORE any code.
Date: 2026-07-24. Source: `forge yield-audit` round 2 (D302 detector).
Relates to: [[D302]] (the detector + guards), [[D309]] (v43 round-1 rider, 30 names),
[[D286]]/[[D293]] (frozen-list precedents), [[D207]] (prereg), hard rule #4
(tightening). Freeze governance: `grammar-freeze-criterion.md` §Governance/§Backlog.

## Evidence (live snapshot, 2026-07-24; all yield-audit guards applied)

- 377,619 decided rows since the clean era (2026-06-10T17:17:13); 33,467 pre-07-18
  ve ghost rows cut.
- **2 names, each ≥500 decided verdicts with ZERO conversions** (component or
  promote) since the clean-era cut:
  - **IWM** — 502 decided / **0** converted
  - **SLB** — 540 decided / **0** converted
- Both are NEW since the v43 round-1 cohort (neither is in the existing 38-name
  `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS`). IWM is in `_NO_EARNINGS_UNDERLYINGS`, so
  it is already barred from *earnings-gated* configs — but it still draws single-name
  on non-earnings templates, which is where the 502/0 accrued.
- No cold-cell flag is actionable this round: the only one printed
  (`event_momentum × swing_mid`, 0/1359) is a hypothesis already in
  `DISABLED_HYPOTHESES` — no live enumeration, nothing to prune.

## The change (one bump)

`_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` +2 (38 → 40 names): add `"IWM"`, `"SLB"`.
Same frozen-list terms as v34/v37/v41/v43: our-verdict-measured per name,
re-admission on Crucible's relay, the WHOLE list retires when their queue-time
liquidity preflight ships. Known limitation stands (v43): the exclusion cannot keep
these names out of `cross_sectional_rank` baskets (underlying `None`; the universe is
Crucible's) — their preflight is the complete fix.

Mechanics AT BUILD TIME (the deploy window, not now):

1. Edit `sampler.py` — add `"IWM"`, `"SLB"` to `_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS`
   with a v50/D### comment citing this rider + the yield-audit evidence.
2. `config/grammar.yaml` `grammar_version: v49 → v50` + archive
   `config/grammar_archive/v50.yaml` + Decision Log entry (hard rule #10 — any
   emission-population change is versioned; rule #6 forbids it as a versionless
   change). The pre-commit version-bump scanner + grammar↔GRAMMAR.md sync enforce.
3. **Goldens re-pin, environment-matched** — the pool shift moves every underlying
   draw (the v37/v41/v43 signature). Re-pin the `test_sampler` goldens.
4. **Emission proof** — zero draws on all 40 names over a ~3k cold enumeration;
   first-batch audit = zero excluded-name draws in the journal.
5. Deploy ritual (`docs/tasks/deploy.md`): stop → full uncontended suite → READ the
   result → commit → restart → verify journal (grammar_version v50, no traceback).
6. **Deploy relay** carries the 2-name list + the **row-45 cross-check request** (the
   v41/v43 pattern — ask Crucible to confirm IWM/SLB against their per-name liquidity
   telemetry) + the funnel signatures.

## Attribution note (why this is a clean v50)

Dead-name retirement is orthogonal to the CPCV-quality read the freeze program cares
about: IWM/SLB are 0-converting, so removing them cannot move the honest-arm CPCV
distribution (they produce no honest components to begin with). So this bump is a
**clean "prune loses nothing" demonstration** — the exact shape a freeze wants — and
it does NOT contaminate the honest-arm baseline the tail-model target decision reads.
It can therefore ship as its own v50 or ride a later bump without either interfering
with the other.

**DECIDED 2026-07-24 (operator: "definitely bundle"): this rides ONE bundled v50 bump**
with `v50-rank-k-trend-bias.md`. Disjoint populations make it safe — since v47 made
trend/MR xsect-only, this name exclusion can only affect SINGLE-NAME draws (i.e.
`volatility_event`), while the rank_k bias only affects TREND XSECT, so neither can
confound the other in `funnel --compare`.

## Post-ship reads

- Prereg `8eaa7e4aca93` resolves on post-cut data: once excluded the names can no
  longer be drawn single-name, so the resolution read is on any REMAINING in-flight
  pre-cut verdicts + Crucible row-45 telemetry; a paradoxical conversion would be
  visible on pre-cut submissions. `forge prereg resolve` on the post-cut cohort.
- `funnel --compare v49 v50` for the attribution signature.
- `forge yield-audit` keeps running; its excluded-names retire-review section now
  tracks all 40.
