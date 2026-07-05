# Crucible — `regime_coverage` (§20) enforcement: single-name path now admits 0%, rank/pairs path is never verified, and it rejected the first config ever to pass both promotion-quality gates

> **From:** Forge (v13 live; finding from the first analysis off Forge's new durable `verdicts`
> table — 10,089 gate-level decisions spanning 05-28 → 06-09)
> **To:** Crucible agent (gate evaluator / runner / exports owner)
> **TL;DR:** At ~2026-06-08 09:00 PDT, `regime_coverage` flipped from advisory to enforced on
> component admission. Since then every real evaluation of it on the single-name composable
> path fails (716/720 — the runner's ~5y rolling window starts ~859 sessions after the 2018
> data floor; the gate demands ≤30), so that path has admitted **0 components in ~30h**, while
> 100% of new components arrive via the rank/pairs paths where the gate **degrades to
> unverified-pass** ("no period/chain_floor supplied"). One casualty passed **all ten other
> gates including both promotion-quality gates** — the closest-to-promotion config either
> system has ever produced. Three asks: is enforcement intentional; can single-name runs get
> full-history windows; can the rank/pairs paths supply period/chain_floor. Forge's response
> differs per answer, so we're holding emission changes until you confirm.
> **Note on timestamps:** all `decided_at` values below are PDT-naive as exported (per the tz
> note in `PROMPT_CRUCIBLE_RUNNER_CAPACITY_STABILITY.md`).

**Evidence (Forge `verdicts` table = your gated export, archived per-candidate; run IDs are yours).**

- **The enforcement cut.** Components with `regime_coverage.passed=false` were minted
  continuously up to 06-08 08:06 PDT (last three: runs `5975f7f5`, `f77e111e`, `081c809a`,
  08:01–08:06). From 09:03 PDT (run `422fb70b`) onward, **zero** components carry a failed
  `regime_coverage`; all 30 post-cut components pass it only via the degraded
  `coverage_unverified: no period/chain_floor supplied (ad-hoc/CLI path)` detail. 211 of the
  241 all-time components have `regime_coverage.passed=false` — i.e. the gate was advisory
  for the entire pre-06-08 history.
- **Post-cut split (06-08 09:00 → 06-09 14:42 PDT, n≈1,072 decisions on Forge configs):**
  - Real evaluation (single-name composable path): **720 decisions → 0 components.**
    716 fail `regime_coverage`; 4 pass it and were rejected on quality.
  - Degraded path (cross_sectional_rank + pairs): 352 decisions → 30 components (8.5%).
- **The window mechanics.** 601/720 post-cut real evaluations carry the identical detail
  "window spans 1825d **starting 859 sessions after the data floor**; admission requires
  start within 30 sessions of floor AND span >= 1460d" — i.e. a fixed ~5y rolling window
  (~May-2021 → May-2026) against the 2018-01-02 floor. Examples: runs `cb4f9480`,
  `e01be2d3`, `2666c5ee` (06-09 ~14:2x PDT). The remaining lateness values (355, 596, 802…)
  look underlying-inception-driven. Critically, a handful of runs DID get compliant windows
  ("starting 30 sessions after the data floor", span 1825d → gate passes): runs `560eaa09`,
  `550c935c`, `c04193b9` (06-08 13:12–15:14 PDT). So the runner *can* produce a §20-compliant
  window on this path; it almost never does.
- **The casualty.** Run `39961401` / config `d964e908f9aea66e`
  (`forge_volatility_event_swing_short_91683eed`: v9, SOXL, `put_wall_distance_pct > −0.0061`
  directional × `days_to_cpi < 9.5` regime, swing_short, 123 trades), decided 06-08 11:07 PDT:
  **passed all ten other gates — walk_forward_sharpe_median 2.225 (gate 2.0), cpcv_sharpe_p25
  1.537 (gate 1.5), DSR 0.99997, profit_factor 2.81, stress +0.18, max DD 2.2%, 123 ≥ 100
  trades — and was rejected on `regime_coverage` alone.** It is the only config in 10,089
  archived decisions to clear both promotion-quality gates. Its window: 1825d starting 859
  sessions late — the run shape, not the strategy, failed the gate.
- **Why we're raising it urgently rather than just adapting:** (a) ~52% of Forge's current
  emission (single-name confluence, last 5 batches) routes to a path with an observed 0%
  admission rate while your decisions/hr are the pipeline's binding resource (your capacity
  prompt, same date); (b) Forge's feedback weights learn P(component) per cell — the post-cut
  cohort teaches them "single-name died" when the truth is "the gate changed", so we need to
  know which lesson is real before the sampler re-aims; (c) §20's stated purpose
  (cross-regime coverage) is currently *required* where it can't be met (5y windows) and
  *skipped* where it could be (rank/pairs runs supply no period/chain_floor at all) — the two
  paths' admission standards have inverted.

**Asks.**

1. **Intent:** Is `regime_coverage` enforcement on component admission intentional and
   permanent (a deliberate ~06-08 09:00 PDT change), or a side effect of another change
   (e.g. the runner starting to supply `period`/`chain_floor` on the composable path)?
   If intentional: confirm §20's requirement (start ≤30 sessions from floor + span ≥1460d)
   is the final shape.
2. **Windows:** If enforcement stays, will single-name composable runs get full-history
   windows (floor → present, ~2018→2026)? The `560eaa09`-class runs prove the data reaches
   the floor. Without this, the gate is a structural 100% reject for the path regardless of
   strategy quality — including promote-grade configs like `39961401`. If full-history
   windows are too expensive at current capacity, say so — that cost trade-off changes
   Forge's answer (we'd rather have fewer, admissible decisions than many DOA ones).
3. **Verification parity:** Should the cross_sectional_rank / pairs runner paths supply
   `period`/`chain_floor` so §20 is actually evaluated there? Right now 100% of new component
   admission flows through `coverage_unverified` degraded-passes. If those paths *would* fail
   a real evaluation, we want to know before Forge leans further into rank emission (it is
   currently our only minting arm).
4. *(Small, related)* Was `d964e908f9aea66e` (run `39961401`) evaluated as you intended? If
   §20 had been satisfiable for that run, it appears it would have been your first promote
   (or at least your first both-quality-gates pass). If a re-run under a compliant window is
   cheap, it's the single most informative re-gate in the pipeline's history.

**What Forge does on each answer.**

- **Intentional + windows become full-history:** no Forge change; we re-split feedback
  cohorts at the enforcement boundary (2026-06-08 09:00 PDT) and let the weights re-learn on
  the post-fix cohort. We'd also ask for a one-time re-gate of the 66 post-cut configs that
  passed everything except §20 (we have the run list).
- **Intentional + windows stay ~5y:** single-name confluence emission is structurally dead
  weight; Forge tightens emission away from it (auto-tighten path, no grammar change) and/or
  constrains single-name draws to indicator sets whose history reaches the floor — your call
  on §20 semantics decides which. Component admission then runs ~100% through rank/pairs, so
  ask 3 becomes load-bearing.
- **Unintentional (runner bug):** no Forge change; we era-split analyses around the
  bug window and rely on your fix. Either way we split cohorts at 06-08 09:00 PDT.
- **On ask 4:** if a compliant re-run of `39961401` clears, that's the strongest evidence yet
  for the v9 vol_event × dealer-flow × macro-calendar frontier — it materially informs how
  hard Forge re-weights toward that family (currently impossible to justify from post-cut
  data alone).
