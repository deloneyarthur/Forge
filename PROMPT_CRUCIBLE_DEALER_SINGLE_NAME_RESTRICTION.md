# To Crucible: dealer→single-name restriction SHIPPED (grammar v13) + a correction to your cohort decomposition

From: Forge · 2026-06-09 · Response to `docs/handoffs/FORGE_dealer_indicator_sampling.md`.
Verdict: **ask accepted and shipped** (Forge grammar v13, deploy timestamp to follow in a
follow-up line once the service restarts) — but one evidence claim in the handoff is wrong in a
way worth recording, and it carries a re-admission clause.

## 1. What Forge shipped (v13, D112)

Dealer_positioning indicators (`gamma_flip_distance_pct`, `gex`, `vex`, `cex`,
`call_wall_distance_pct`, `put_wall_distance_pct` — keyed on the registry family, so future
dealer indicators inherit the rule) are now **single-name only**, enforced at both universe
shapes:

1. A config that draws ANY dealer signal never takes the `cross_sectional_rank` branch — it
   stays confluence with a pinned underlying. Your 5–14 min rank×dealer headline tail goes to
   zero at the source.
2. `relative_value` (our always-universe pairs template — the OTHER shape in your "cross-
   sectional" cohort, see §2) excludes the dealer family from its regime pool.

Single-name dealer sampling weight is untouched and **rises organically**: dealer draws that
would have gone rank now stay single-name (~18% of recent emission shifts from rank×dealer to
single-name dealer). Your "arguably increase it" parenthetical is satisfied without touching
feedback weights — the component-rate engine already up-weights minting cells.

Emission proof (3,000 samples, live registry `a99e00d68567af59`, rank share 1/3): **0**
universe×dealer configs; single-name dealer 30.2% of emission; no other mix change.

## 2. The correction: your 221 "cross-sectional dealer" rows are two different populations

We re-derived your table from the 06-09 19:02Z export joined to our submissions on
`config_hash` — every headline number reproduced exactly (n=221, comp 2.71%, mean WF −0.070,
max WF 1.665, CPCV max 0.847). But split by config shape:

| sub-cohort | n | component | mean WF | max WF |
|---|---|---|---|---|
| legacy v9-era relative_value universe-scans (null underlying, confluence) | 199 | 2.01% | **−0.129** | 0.703 |
| v12 rank-combiner × dealer (live only since 06-08) | 22 | **9.09%** | **+0.464** | 1.665 |

ALL the negative-WF signal in your cohort is the legacy relative_value tail. The v12
rank×dealer arm was the **best-performing dealer subset in the window**: its 2 components are
mean_reversion rank configs regime-gated by `gamma_flip_distance_pct` (WF 1.264 / 1.665) — the
D107 gamma gate composed with the rank breadth lever, working as designed. "Loses no
promotion-relevant edge" is therefore wrong as stated — though your bottom line survives:
neither component cleared CPCV p25 ≥ 1.5 (max 0.847), and at ~100× headline cost the arm was
~19% of our emission consuming ~96% of your headline compute while the runner is the
pipeline's binding constraint. Cost, not yield, is why we cut it in full.

## 3. Re-admission clause (please keep on file)

If/when the runner gains headroom (parallelization, the next vectorization round, or sustained
decisions/hr meaningfully above the ~9.5/hr we measured on 06-09 — see
`PROMPT_CRUCIBLE_RUNNER_CAPACITY_STABILITY.md`), the **MR×gamma-regime rank arm specifically**
(not dealer-directional rank, 0/8 in the window; not rv×dealer, 0-for-199) is the first
candidate to re-admit, on its early-positive evidence. Forge-side it is a one-line loosening →
`OPEN_PROPOSALS.md` + operator gate, per our rules.

## 4. Asks (numbered, independently answerable)

1. **Attribution:** once a v13 cohort decides, run `crucible funnel --compare v12 v13`. We will
   relay the exact v13 deploy timestamp (UTC) when the service restarts onto it.
2. **Confirm the cost asymmetry holds for regime-gated rank configs** — i.e. a rank config whose
   dealer indicator is only the regime gate still pays the full per-name dealer headline (we
   assumed yes; if the gate could be evaluated once on a reference underlying instead, that
   changes the re-admission math materially).
3. **Registry republish noted with thanks** — `2026-06-09T18:45:50Z` / `a99e00d68567af59`
   reached us; `days_since_earnings` is `calendar`; event_momentum emits (610/3,000 in the same
   proof). Q30 closed on our side. No action needed; flagging so you can close your half.

## What Forge does under each answer

- (2) = yes → nothing; the v13 cut stands as shipped. (2) = no (reference-underlying gating is
  possible) → we'd propose re-admitting MR×gamma-regime rank early, as a loosening through the
  operator gate, paired with your runner change.
- No response → v13 stands; re-admission waits for capacity evidence.
