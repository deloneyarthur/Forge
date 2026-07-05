# Crucible ask — walk-forward fold-distribution percentiles (WF **p95**) per honest component, via the refit lane

**From**: Forge session, 2026-06-18
**Re**: `FORGE_generation_model_plan.md` (the *quality* half); piggybacks on
`PROMPT_CRUCIBLE_REFIT_PRIORITY_AND_WORSTQ_REGIME.md` (the mr/ranging refit prioritization).
**Status**: DATA REQUEST — a label for Forge's generation-layer quality model. Nearly free: you
already compute the WF fold distribution to produce the `walk_forward_sharpe_median` gate; this
asks you to emit more of its percentiles (primarily **p95**) on the refit window.

---

## TL;DR

While the refit lane runs, additionally emit — per honest component, keyed by `config_hash` — the
**percentiles of the walk-forward test-fold Sharpe distribution you already compute**: primarily
**`wf_sharpe_p95`**, plus `p50`/`p75`/`p25` and `n_wf_folds`, on the full-history refit window.
Forge's export carries only `walk_forward_sharpe_median` today. We want the **upper tail** because
a probe shows rich config features predict honest WF-*median* at out-of-fold Spearman **+0.27**, and
we expect the *ceiling* (p95) to be a cleaner quality target.

---

## 1. Why — the quality model, and why p95

- **D186 located the `quality × decorrelation` objective:** decorrelation → **assembly** (you have
  the real pairwise corr), quality → **generation** (Forge). The generation-layer quality model
  predicts a component's quality from rich config features and steers the stream toward it.
- **Probe (this session):** the king featurizer's rich features predict **honest WF-median at IC
  +0.27** (out-of-fold Spearman; cpcv-p25 **+0.44** on the same harness as a sanity check, beating
  the D155 tail model's +0.35). So the quality model is **viable** — but WF-median is the noisy
  *central* statistic.
- **Why p95 specifically:**
  1. **Assembly tiles complementary PEAKS.** A broad component's value to the book is its strength
     *in its good periods* (which assembly stitches across regimes/time), not its typical fold. WF-p95
     captures that ceiling; the median averages in the dead folds.
  2. **Empirics point up-tail.** The sharper `cpcv_p25` predicted far better (+0.44) than WF-median
     (+0.27) on identical features — a cleaner WF statistic plausibly predicts better too.
  3. No single broad component clears the WF-median 2.0 wall (0/9398 honest singles clear cpcv 1.5);
     the promotion path is *assembled peaks*, so the peak is the right per-component target.

## 2. The ask — columns per honest component (join key `config_hash`)

| column | req? | meaning |
|---|---|---|
| `wf_sharpe_p95` | **required** | p95 of the test-fold Sharpe distribution (the new target) |
| `wf_sharpe_p50` | **required** | median on the refit window (reference vs the as-gated median we have) |
| `wf_sharpe_p75`, `wf_sharpe_p25` | strongly wanted | distribution shape |
| `n_wf_folds` | **required** | so we can drop components whose p95 rests on too few folds |
| `cohort` | strongly wanted | `xsect` \| `single` (execution-breadth definition — same as the decorrelation sample, for consistent segmentation) |
| `refit_window` | nice-to-have | the full-history honest window used |
| `grammar_version` | nice-to-have | for version-scoping |
| per-fold WF Sharpe series (or fold start/end dates) | optional | only if cheap — for the temporal-complementarity / peak-tiling follow-up (do high-p95 components peak in *different* periods?) |

## 3. Methodology — why it's nearly free

- **Same fold definition** as the existing `walk_forward_sharpe_median` gate (test-fold Sharpe across
  the single-config walk-forward folds) — just emit `p95`/`p75`/`p25` of *that same distribution*,
  not only the median.
- **On the full-history refit window** (honest / coverage-verified). As-gated WF is sparse and
  recency-fit; the refit lane gives the dense, honest, full-window values that make a WF target
  *trainable* in the first place. This is the same honesty discipline as `regime_coverage`.

## 4. Population / volume

One row per honest component the refit lane already processes — **add the columns to the refit
output**. For the first probe a representative **sample (~500–1000 honest broad components)** is
enough to test p95-vs-median predictability; for training the production quality model we'd want the
full honest pool. Lightest path: emit the columns for everything the refit touches and we'll sample.

## 5. How Forge uses it

Re-run the quality probe with target = **WF-p95**: if `IC(p95) > IC(median)=+0.27`, p95 becomes the
generation-layer quality model's target (and the meta-king's re-target objective, **M → WF-p95**, as
King folds into the standard submission path). If not, we keep the median. Either way it is the
training label for the folded-in quality model.

## 6. Scope / posture

- **No §8.7 change, no threshold moved** (hard rules 3/6). This is *additional output* on an existing
  computation (the refit WF fold distribution) — it moves no bar.
- **Join key:** `config_hash` (16-char, = Forge `submissions.config_hash`).
- **Format:** JSON/CSV/Parquet to `~/optbt_data/exports/` (name it clearly, e.g.
  `wf_percentile_refit_<ISO8601>.json`); Forge pulls by mtime. If it graduates to a production
  training label, ship as a **versioned, timestamped artifact** (the meta_king-oracle pattern) so
  Forge's determinism contract holds; the probe sample is offline-only.
