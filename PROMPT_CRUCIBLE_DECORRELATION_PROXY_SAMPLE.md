# Crucible ask — pairwise PnL-correlation SAMPLE (decorrelation-proxy validation)

**From**: Forge session, 2026-06-18
**Re**: `FORGE_generation_model_plan.md` §3 (decorrelation map) + §8.2 (joint objective)
**Status**: DATA REQUEST for a one-off validation experiment — NOT a request to build the full map yet.
This *precedes* and *de-risks* the production decorrelation map: the sample tells us whether the map is
worth building, and at what fidelity.

---

## TL;DR

Before you build the per-recipe decorrelation map, send Forge a **one-off sample of pairwise daily-PnL
correlations** (a few hundred-to-~1k strategy pairs, keyed by `config_hash`, enriched for the
broad×broad regime and spanning a range of structural distances). Forge will test whether a **cheap
structural proxy it can compute at generation time** (signal/family/regime/cohort/name-universe
distance) predicts your realized PnL correlation. The result decides *how* Forge wires the
decorrelation axis (§8.2):

- **Proxy predicts corr** → Forge needs **no map** for v1; it computes decorrelation itself and the
  axis ships inside Forge's normal increments.
- **Proxy fails (esp. broad×broad)** → the **full per-recipe map is justified** and becomes the input.

Either way you learn the answer from a sample, not by committing to build/maintain the full matrix.

---

## 1. Why this, and why a sample first

Forge has **zero return data** — it can never compute PnL correlation itself (confirmed: Crucible
exports per-strategy scalars only; no daily PnL, no pairwise corr). So decorrelation-aware generation
needs a decorrelation signal from *somewhere*. Two sources:

1. A **cheap structural proxy** Forge already computes (firing-date / content-key Jaccard, family /
   regime / cohort / name-universe distance). Free, no Crucible dependency.
2. **Your decorrelation map** (§3). Higher fidelity, but real build/maintenance cost.

We don't know if (1) works. The decisive unknown is the **broad×broad** regime the assembly thesis
lives in: broad cross-sectional legs are in-market nearly every day, so firing-date overlap is ~1 for
all of them — their decorrelation is in *which names / which rank direction*, not *which days*. The
proxy may work for sparse/single-name pairs and **fail exactly where it matters**. A sample resolves
this for a fraction of the cost of the full map.

## 2. The data — one row per sampled pair

| column | req? | meaning |
|---|---|---|
| `config_hash_a`, `config_hash_b` | **required** | 16-char hashes; must match Forge `submissions.config_hash` so we can join + recompute structure |
| `pnl_corr_full` | **required** | Pearson corr of **daily net PnL over the union calendar, flat days = 0** (the book-relevant number — see §4) |
| `n_days_union` | **required** | calendar days in the correlation window (lets us drop thin-overlap noise) |
| `n_days_a_active`, `n_days_b_active` | **strongly wanted** | position-days each leg (lets us see breadth and compute realized firing overlap) |
| `n_days_both_active` | **strongly wanted** | intersection days — lets Forge check its *predicted* firing overlap against *realized* |
| `pnl_corr_intersection` | nice-to-have | Pearson over intersection-only days (isolates directional (dis)agreement when both are on) |
| `cohort_a`, `cohort_b` | nice-to-have | `xsect` \| `single` per leg (else Forge derives it from the config) |
| `cpcv_p25_a`, `cpcv_p25_b` | nice-to-have | standalone quality, so we can weight the analysis by leg quality |

## 3. Sampling spec (this is the part that matters)

The production signal we ultimately want is **"correlation to the existing trend/MR mass"** — so bias
the sample toward that, not arbitrary pairs:

1. **Corr-to-mass core (primary):** pick a handful of representative **broad trend** and **broad MR**
   legs as "the mass." Sample many `(candidate, mass-leg)` pairs where the candidate varies in
   structure. This mirrors the eventual §3 map directly.
2. **Enrich broad×broad:** ≥ ~150 pairs where *both* legs are `cross_sectional_rank`. This is the
   regime the proxy is most likely to fail in and the one the assembly path depends on.
3. **Span structural distance — do NOT sample only extremes.** Include **near** (same
   hypothesis+directional), **mid** (same hypothesis, different directional or different regime gate),
   and **far** (different hypothesis) pairs. Forge's `signal_correlation` prefilter already truncates
   the >0.85-overlap tail from the submitted stream, so deliberately include mid-distance pairs or the
   fit is on a censored sample.
4. **Population:** pairs of Forge-submitted configs you've backtested (so hashes join). v9+ grammar
   cohort preferred; if you include older rows, stamp `grammar_version` so we can version-scope.
5. **Size:** ~300–1000 pairs total is plenty for a rank-correlation read. A sample, not the 10k×10k
   matrix.

## 4. Correlation methodology (please state what you actually did)

- **Primary = portfolio-relevant:** Pearson of **daily net PnL**, aligned on the **union** of both
  legs' trading calendar, with **non-position days set to 0 PnL** — because that's how two legs
  actually combine in a book (a leg sitting flat *is* diversification). This should reproduce the kind
  of number behind the `soft_joint` −0.04.
- **Window:** the **honest / verified** backtest window you use for the gate metrics — same data the
  cpcv/WF gates see. Please state the window and whether it's coverage-verified.
- **Report `n_days`** so we can filter pairs with too little overlap to trust.
- If cheap, also give `pnl_corr_intersection` (intersection-only) — it isolates "when both are on, do
  they agree directionally," which maps onto a structural sign feature Forge can compute.

## 5. Optional v2 — regime-conditional (only if cheap)

Worst-quartile is BEAR / RANGING (Forge's T3a read). Full-history Pearson can hide that two legs
decouple in calm and **re-couple in the bad quarter** — which is the quarter the gate scores. If you
can split corr by regime (at least BEAR vs not), include `pnl_corr_bear`. Not required for v1.

## 6. What each outcome triggers on Forge's side

| result (segmented by cohort) | meaning | Forge does |
|---|---|---|
| proxy predicts `\|corr\|` in **broad×broad** | Forge can see decorrelation from structure | ship the decorrelation axis with the **free proxy** — no map dependency |
| works only for sparse/single | useless in the regime that matters | request the **full per-recipe map** for the broad case (§3) |
| no stable relationship | structure ≠ return decorrelation | the **full map is the only path**; proxy abandoned |

We read it as Spearman(structural-distance, `|pnl_corr|`) **segmented by cohort** (pooling inverts
structure here — cf. the mr/trend cpcv-on-coverage inversion), plus the decision check "are low-distance
pairs reliably low-corr."

## 7. Logistics

- **Join key:** `config_hash` (16-char), identical to Forge `submissions.config_hash`.
- **Format:** JSON or CSV/Parquet to `~/optbt_data/exports/` is fine — name it clearly
  (e.g. `decorrelation_proxy_sample_<ISO8601>.json`); Forge will pull by mtime.
- **Determinism note:** if this graduates to the production map, it must be a **versioned, timestamped
  artifact** (the meta_king-oracle ingestion pattern) so Forge's `(grammar_version, registry_hash,
  seed)` determinism contract holds. The sample itself is offline-only, no constraint.
