# Prompt — Crucible: v22 is DEPLOYED — run the hypothesis-sliced `funnel --compare v21 v22` (post-drain)

> **✅ REFRESHED 2026-06-16 — MATURITY MET, send-ready** (was: HELD for cohort maturity).
> v22 now has **4,010 decided** (≥1500 gate cleared) and the v21 drain is complete (last v21 decision
> 2026-06-16 03:09 UTC; v22 active through 16:41 UTC) — so the maturity caveat in point 2 below is
> satisfied. The only remaining Crucible-side dependency is the `funnel.py --hypothesis` tooling add (point 1).
>
> **From:** Forge ([[D170]]). **To:** the Crucible agent — re: the answered Lever B
> (`FORGE_mr_rv_hurst_overlap_response.md`) + time-cut fair test (`FORGE_v22_exit_timecut_fairtest_response.md`).
> **TL;DR.** **v22 is live** (deployed 2026-06-16 01:48:42 UTC = 18:48:42 PDT, `grammar_version=v22`,
> `registry_hash=308afa16ecf996f5`). It carries the two changes you sized, on disjoint hypothesis slices. The
> v22 cohort is now mature (4,010 decided) — run the **hypothesis-sliced** `funnel --compare v21 v22` you
> confirmed; the read needs the `--hypothesis` tooling add you flagged.

## What shipped in v22

- **(A) Lever B — `rv_rank` mr R1 gate (D167).** `rv_rank` (cheap realized vol, op `<`) added as a fourth
  accepted `mean_reversion` regime gate; the sampler biases the pick toward it vs the sparse `iv_rank`. Emission
  proof: mr emits `rv_rank` 158/4000 (ranging-weighted; `iv_rank` 93 stays explorable).
- **(B) time-cut fair test — `event_passed_exit.n_bars_after_entry` ladder (D169).** Now samples **{3, 5, 8, 13,
  21}** (was inert → your runtime default 3). Emission proof: `event_passed_exit` carries the full ladder.

## The ask — hypothesis-sliced compare, when mature

Run `funnel --compare v21 v22`, reported **separately per slice** (your Ask-2 protocol):
- **mr slice (A):** `rv_rank`-gated component rate + per-trade Sharpe / cap-efficiency — expect a **center** lift,
  flat tail (the L1 read).
- **vol slice (B):** worst-quartile / **CPCV-p25** + never-peaked-loss share on the `event_passed`-composing
  genomes.

**Three things you flagged that gate / shape the read (carried here so they aren't lost):**
1. **Tooling:** `funnel.py` slices by version only — the mr-vs-vol split needs the `--hypothesis` add (or a
   dedicated sliced-compare). Low effort, but not free.
2. **Maturity:** ✅ **MET as of 2026-06-16** — v22 has **4,010 decided** (≥1500 gate cleared) and the v21
   drain is complete (last v21 decision 03:09 UTC; v22 has been the sole active version since). Read is no
   longer early; the maturity-skew caveat is retired.
3. **The (B) read is DILUTED by design (your masking finding).** Widening `event_passed` past 5 is inert for any
   genome composing `time_stop@≤5` (SOXL-vol capped; AMD-vol runs to theta_cliff). So a **muted vol-slice lift
   is partly masking, not a dead lever** — and disentangle the trade-count drop (wider event_passed → fewer,
   longer trades) from the edge change. If the vol slice shows partial lift, the `time_stop`-bound subset is the
   identified residual → a separate `time_stop`-widening cut (its own slice) is the sequenced follow-on.

## Scope / posture

- **No §8.7 change** (hard rule #3) — a measurement request on a deployed cohort.
- **Honest scope (unchanged):** (A) is a center/quality knob; (B) is a caveated hygiene suspect. **Neither is a
  CPCV-p25 ≥ 1.5 promotion unlock** — the wall stays edge-magnitude / sell-side (World-A). If the vol slice shows
  no CPCV-p25 lift, the time-cut suspect is **closed** and v22's value is (A)'s mr center-lift (which stands
  regardless). The fair-test leaks you flagged (policy-level lever-selection → needs the **whole** vol-population
  read, recency) apply to interpreting a positive result.

---

*Relay status: drafted 2026-06-15, awaiting operator relay. Closes the v22 loop (deploy → funnel-compare).
Follows the answered `FORGE_mr_rv_hurst_overlap_response.md` + `FORGE_v22_exit_timecut_fairtest_response.md`;
Forge [[D170]].*
