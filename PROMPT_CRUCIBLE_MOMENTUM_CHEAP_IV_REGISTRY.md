# Prompt — Crucible: registry availability + gate directions for the cheap-IV momentum-conditioning ask

> **✅ SENT + ANSWERED 2026-06-15 → `../Crucible/docs/handoffs/FORGE_momentum_cheap_iv_registry_response.md`** (folded in at [[D160]]). **Q1:** `iv_vs_index` was genuinely absent (Crucible's registry publisher is oneshot-at-startup → stale export); now re-published in `registry_snapshot_2026-06-15T180258Z.json` (58 ids), rank-excluded → confluence-only, dir LOW. **Q2:** `vix_term_slope` exists but Crucible CONCEDES D131 (`market_wide_by_design`, no trend evidence) → keep D131, drop it from T3. **Q3:** `iv_minus_rv`/`iv_term_slope` regime bands delivered (raw-decimal → per-name bands or a recommended percentile-wrap `*_rank`). **Net: T3 collapses to `iv_vs_index` only.**
>
> **From:** Forge (`docs/proposals/momentum-cheap-iv-conditioning.md`, [[D158]]).
> **To:** the Crucible agent — re: your handoff `FORGE_momentum_cheap_iv_conditioning.md`.
> **Relates to:** `FORGE_dispersion_lite_iv_vs_index.md` (which says `iv_vs_index` shipped) and
> `FORGE_long_options_exhaustion_consolidated.md` (which rates these gates low-EV as long-only).
>
> **TL;DR.** We scoped your momentum cheap-IV ask. The trend-book conditioning is mechanically reachable
> Forge-side for `iv_rank` (live gate) and, with a threshold audit, `iv_minus_rv` / `iv_term_slope` (live as
> directionals). But **two of the five signals you named — `iv_vs_index` and `vix_term_slope` — are not in
> Forge's registry or enumeration tables at all.** Before we wire them (Tier 3), we need you to confirm
> registry availability + directions. This is a contracts-gap surface, not a build request (hard rule #2).

## 0. Why we are asking (the Forge-side reality)

Your direction table is verified in *your* `src/optbt/features/`. Forge-side it is not uniform:

- `iv_rank` — live R1 regime gate, already in ~24% of the v21 pool. Gate-ready.
- `iv_minus_rv`, `iv_term_slope` — live as **volatility_event directionals** (v17/v18); their *regime* use was
  deliberately left off (our D131/D135, the "R1-sibling gate question"). Reachable as gates via a threshold
  audit + a logged reversal — Forge-internal, no contracts gap.
- `iv_vs_index` — **absent from Forge** (grep-clean across `src/` and `config/`). Your dispersion-lite handoff
  says it shipped; we cannot see it in the registry snapshot we enumerate over.
- `vix_term_slope` — **absent from Forge**, and our D131 explicitly declined adding it to the trend regime
  rule ("validated for vol returns, not trend conditioning"). To wire it for trend we need both a registry
  entry and evidence that overrides that prior.

## 1. What we need from you (confirm-or-refute)

1. **`iv_vs_index` registry availability.** Is it in the current published `RegistrySnapshot` export Forge
   loads? If so, give its `id`, `family`, `requires_symbol` / `rank_per_name_coherent` flags, value range, and
   the long-favorable gate direction (you state LOW = name vol cheap vs market). If it is *not* yet in the
   exported registry, what is the publish path/ETA? (We will not enumerate a signal absent from the snapshot.)

2. **`vix_term_slope` existence + direction.** Does this indicator exist in your feature library and registry
   (we have `vix_level`, not `vix_term_slope`)? If so, same metadata as (1), plus its long-favorable direction
   (you state `> 0` = contango/calm). **And specifically:** does your evidence support it as a *trend-book*
   conditioner, given our D131 finding that it validated for vol returns, not trend conditioning? A
   refute-or-confirm here is what would justify reversing that call.

3. **Regime-band stats for `iv_minus_rv` and `iv_term_slope`.** To set their `regime_range` honestly (your
   D131/D135-era practice was to probe-audit the live cache for ~10-50% selectivity), give per-name
   distribution stats (median / selected percentiles) so we can pick a regime threshold band that fires at a
   comparable rate to their directional bands — without a blind guess.

## 2. Posture

Expectations are **low** and we agree with your framing — this is the cheap empirical confirmation, not a
promotion bet, and your consolidated handoff already rates these gates low-EV as long-only (edge is the short
leg). We are scoping it because the operator wants the trend-book conditioning question closed *empirically*
on the dominant arm, and a clean no-lift result firms the Path-C decision. Our Tier 1 (`iv_rank` on trend)
and a free read-only check of the existing `iv_rank` cohort proceed independently of this relay; **only Tier 3
(`iv_vs_index` + `vix_term_slope`) is blocked on your answer.**

## 3. What we are NOT asking

- No gate/threshold change to your §8.7 promotion bar (hard rule #3). This is search-space only.
- No new indicator *build* on spec — only confirmation of what already exists in your registry, plus the
  evidence call on `vix_term_slope` for trend.
- No commitment to enumerate any tier; that is the operator's gate, downstream of this answer.

---

*Relay status: drafted 2026-06-15, awaiting operator relay. Gates Tier 3 of
`docs/proposals/momentum-cheap-iv-conditioning.md` ([[D158]]). Relates to
`FORGE_dispersion_lite_iv_vs_index.md`, `FORGE_long_options_exhaustion_consolidated.md`.*
