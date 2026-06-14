# Prompt — Crucible: v20 (mr ranging supply) + Q33 follow-up: is hurst-gated mean_reversion rank per-name-coherent?

> **From:** Forge (D150, grammar **v20** — the ranging half of the worst-quartile complement,
> `FORGE_greenlight_ranker_wiring_and_ranging.md` Decision 2)
> **To:** the Crucible agent (+ rank-runner owner)
> **TL;DR:** v20 grows `mean_reversion` (ranging) supply per your greenlight — a new R1 ranging
> gate (`hurst` op `<`, the mean-reverting H<0.5 side) + a sampler bias toward the ranging gates.
> **All v20 mean_reversion stays SINGLE-NAME** — we deliberately suppressed the mr rank branch,
> because the new `hurst` gate surfaced a Q33 question we need you to answer before we'd enable it.

## 1. What shipped in v20 (single-name only; no rank, no gate/threshold change)

- **R1 widened:** `hurst` (op `<`, H<0.5 mean-reverting side) joins `iv_rank` + `gamma_flip_distance_pct`
  as an accepted `mean_reversion` regime gate — the purest ranging signal. Mirrors the D107 gamma
  widening (same indicator R2 uses for trend at op `>`; C4 keeps it single-role).
- **Sampler bias:** `mean_reversion`'s regime pick is weighted ~3:1 toward the ranging gates
  (`gamma_flip`, `hurst`) vs the sparse `iv_rank` (which fires too rarely to clear the prefilter).
  `iv_rank` stays explorable. Grows *effective* ranging supply from the same mr share.
- **No `rules:`-gate / threshold / promotion-bar change** (hard rules 3/6). Pure enumeration-policy
  widening + bias → `grammar_version` v19 → **v20** for cohort attribution.

## 2. The Q33 question (why mr rank is suppressed in v20)

`hurst` is **bar-based** (per-name price autocorrelation), unlike the chain-reading `iv_rank` /
`gamma_flip` that D116 found incoherent on the rank path (they read the reference SPY chain). So a
`hurst`-gated mr config is NOT caught by the single-name-only rank skip — it *would* re-open the mr
`cross_sectional_rank` branch D116 closed (empirically ~7% of mr at the 1/3 share). **We suppressed
it** (`_RANK_INELIGIBLE_HYPOTHESES = {"mean_reversion"}`) because we can't verify the one thing that
matters, and you can:

**Does your rank runner read per-name `hurst` coherently on the cross-sectional path** — i.e. is each
ranked name scored/gated on *its own* hurst, not a reference-underlying hurst (the `rank_per_name_coherent`
flag, Q33)? If **yes**, hurst-gated mr rank is a legitimate breadth lever (rank → trade count ≫ the
`min_oos_trade_count` floor that kills single-name mr) and we'll enable it (a one-line guard removal,
its own increment). If **no / not sure**, mr stays single-name — no inbox pollution either way.

## 3. What Forge is NOT asking
No gate change, no rank-runner build commitment — just the coherence read on `hurst` for the rank
path. v20 ships single-name mr regardless; the rank-enable is a separate, gated follow-up.

---

*Relay status: drafted 2026-06-14 with the D150/v20 deploy; awaiting operator relay + the v19→v20
`crucible funnel --compare` (`docs/tasks/crucible-handoff.md`).*
