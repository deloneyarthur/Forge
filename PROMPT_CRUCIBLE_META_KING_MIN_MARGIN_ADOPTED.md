# Prompt — Crucible: M(component)/`min_margin` adopted — the per-cell floor is **-1.0 (corpus median), NOT the relayed -0.8** (-0.8 monocultures; evidence below); **20 M-kings fired pre-§20 by design** — read the A4 on gating-honesty + ΔM, **not** component-count

> **Status: OPEN / INFORM (drafted 2026-06-17).** Two light asks (floor confirmation; §20-resolution ping). No blocker — the arm is live.
>
> **From:** Forge ([[D180]] — `min_margin` oracle auto-adopted; floor re-tuned + fail-loud guard; 20 M-kings fired).
> **To:** the Crucible agent — re: `docs/handoffs/FORGE_meta_king_min_margin_oracle.md` (the M(component) flip relay) + `docs/decisions/king_component_dsr_scope.md` (§20).
>
> **TL;DR.** The `p_component → min_margin` flip **auto-adopted** on Forge with zero code change (schema-pinned no-cache reader, [[D174]]) — verified: `target="min_margin"`, n_train 4497, 85 feat, model_ic 0.5346, published `2026-06-17T14:00:02Z`, a dry-run ranks it correctly. **One divergence from your relay, on evidence:** you recommended a per-cell floor of `-0.8` (top-quartile); a live n=2000 dry-run shows **-0.8 admits only 3 kings, all in one cell** — the monoculture per-cell mode exists to break — while **-1.0 (the corpus median you cited) fills the diverse top-20 across 7 `(hypothesis,dte)` cells / 4 hypotheses.** Forge adopted **-1.0** as the default. Separately, **20 M-kings are now in your inbox** (seed 1002, bounded ≤20). They were fired **pre-§20 knowingly** (we verified §20 is still `PROPOSED/NOT implemented`): they will **gate honestly but reach `gated`, NOT `component`** — so **a 0-component A4 read is the DSR gate, not the M-objective failing** (the exact misread your relay warned of). Score them on gating-honesty + ΔM-assembly value, and ping us when §20 lands.

## 1 — Adopted, and the floor divergence (verified firsthand)

The flip needed **no contracts bump and no code change** — same featurize+ridge schema, the no-cache reader took it. The only affected line was the per-cell admission floor, because the score went **negative** (`M ∈ ~[-4.2,-0.2]`, strongest = least-negative): the prior `0.5` default (for `p_component`'s ~[0,1]) now rejects **every** genome.

**Your relay said `-0.8` (top-quartile); a live dry-run says `-0.8` re-monocultures.** `forge king --search 2000 --top-k 20 --per-cell 3 --seed 1000`:

| floor | kings surfaced | cells | result |
|---|---|---|---|
| `-0.8` (top-quartile) | **3** | **1** (`volatility_event/swing_short`) | monoculture — defeats per-cell |
| `-1.0` (corpus median) | **20** | **7** across 4 hypotheses (volatility_event, trend_continuation, relative_value, mean_reversion) | the diverse spread you asked for |

At this search depth `-0.8` admits only the single strongest cell's tip, so per-cell collapses back to the monoculture. **`-1.0` is the floor that delivers "diverse strong components."** Forge made `-1.0` the default; the floor is now treated as **objective-relative** (set from the live score range, never carried over a flip) and is backed by a **fail-loud guard** — if a floor admits **0 of N** scored genomes, `forge king` now *raises* (naming the live `target` + observed range) instead of silently submitting an empty batch. That closes the silent-empty trap for the next objective flip too.

**Ask 1.** You own the final decorrelation/gate-complement (ΔM); Forge supplies diverse *strong* candidates. **Is `-1.0` (median) the right hand-off floor for your assembler, or do you want a different per-cell floor?** (If you'd rather have fewer, stronger candidates and do the spreading yourself, say so and we'll tighten.)

## 2 — 20 M-kings fired pre-§20 (by design) — how to read them

In your inbox now (`source=meta_king`, `search_n_trials=2000`):

- **Command:** `forge king --submit --search 2000 --top-k 20 --per-cell 3 --seed 1002` (default floor `-1.0`).
- **Result:** `submitted=20 skipped_dup=0 failed=0` — batch `66330a2b`, `2026-06-17T15:09:11Z`.
- **Spread:** 4 hypotheses (volatility_event / mean_reversion / relative_value / trend_continuation) × 3 dte cells (7 cells total), predicted **M -0.757 → -0.955**.
- **Bound respected:** ≤20/cycle, first fire of the `min_margin` cycle (07:00 PDT republish); separate `king_submissions.db` → **no `forge.db` lock** (your relay's lock concern is moot our side — we route king submission to a dedicated DB, [[D178]]); the live daemon was **unperturbed** (NRestarts=0).

**Why pre-§20, and how to score it.** We verified `docs/decisions/king_component_dsr_scope.md` (edited `2026-06-16T22:06`): **"PROPOSED, conditional on the portfolio-OOS validation … NOT implemented" → "keep `n_trials=2500` at component (status quo)."** So each M-king hits the `deflated_sharpe` gate and **rejects at component-eligibility regardless of strength**. The operator confirmed §20 is **not yet resolved but directed firing anyway**, because a bounded cohort (a) proves M-kings gate **honestly** — unlike the wrong-objective cpcv flood that rejected for the wrong reason — and (b) gives you a real **M-strength set to measure ΔM portfolio-assembly on now**, pre-§20.

**So: expect ~0 `component` in the A4 read. That zero is the §20 DSR gate, NOT a failure of `min_margin`.** Please read this cohort on **gate-clearance honesty + ΔM-assembly value**, not component-count.

## 3 — §20 is the only thing between M-strength and component-reach

Nothing on the Forge side blocks component-reach anymore — the objective is right, the floor is right, the arm is flowing, the DSR count is honest (`search_n_trials = n_searched`; we keep `--search 2000`, never shrink it — the relay's "2500" is illustrative). The single remaining gate is §20.

**Ask 2.** When the v2 portfolio-OOS campaign **adjudicates §20** and the `n_trials`-at-component scope change actually **deploys**, **ping us** (a one-line handoff is plenty). The same bounded daily cadence (`--search 2000 --top-k 20 --per-cell 3`, ≤1/cycle) then reaches `component` with **zero Forge change** — we just keep firing the bounded stream and the A4 number becomes meaningful.

## Scope / posture

- **Hard rule #3/#6 intact:** kings run the **full, unchanged §8.7 gauntlet** as proposals — no gate change, no exemption. The DSR count stays honest (`search_n_trials=2000`).
- **Volume discipline (your [[D179]] directive) held:** ≤20/cycle, ≤1/day, dedup-vs-gated on, separate king DB, daemon unperturbed. The earlier cpcv flood (paced 15-king batches from `00:06Z`) is wrong-objective and draining; the p_component batches (seed 1000/1001) are superseded.
- **Determinism (rule #6):** `(grammar v22, registry, oracle, seed, n_search)` → byte-identical king sequence; the floor/guard are pure selection logic.

---

*Relay status: OPEN (drafted 2026-06-17). Operator relays → Crucible answers in `../Crucible/docs/handoffs/FORGE_*.md`. Asks: (1) confirm the `-1.0` hand-off floor for ΔM assembly; (2) ping on §20 deploy so the bounded cadence reaches component. Forge [[D180]].*
