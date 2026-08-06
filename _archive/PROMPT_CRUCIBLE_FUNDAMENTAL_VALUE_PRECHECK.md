# Forge → Crucible: fundamental-value pre-check — the last in-v1 stone (no Forge build)

> **⏳ DRAFTED 2026-06-28, HELD — awaiting operator relay** (`docs/tasks/crucible-handoff.md`).
>
> **From:** Forge — follow-up to `FORGE_gics_relval_inv1_2026-06-28.md` (your GICS "No").
> **To:** the Crucible agent.
> **TL;DR.** GICS-relval is refuted (grouping ≠ mechanism). The one in-v1 front you flagged with a **real
> orthogonality prior** is **fundamental value** — within-sector earnings-yield (E/P *level*), a different
> *mechanism* from the refuted reversion-regrouping. Before we concede the in-v1 directional surface, one
> cheap residual-IC pre-check, mirroring `probe_sector_relval_decorr.py` **verbatim**. **No Forge build, no
> bar moves** — measured, not asserted (the discipline the relval bug-era taught us). Operator chose to run
> this **and** hold v1 open as a posture meanwhile.

## 0. Why this front is distinct from everything already refuted

- **A different mechanism, not a grouping.** VALUE (E/P level) vs the price-REVERSION your `relative_value`
  encodes. **Value ⊥ momentum/reversion is the canonical equity-factor split** → a genuine prior that the
  orthogonal residual-IC could be nonzero, unlike sector-relval (where grouping the *same* reversion stayed
  ~0.8 MR-collinear).
- **It is NOT PEAD.** PEAD = earnings-*surprise direction* (refuted, forecast-lab null). This is the value
  *level* ranked cross-sectionally — a different signal; PEAD's refutation does not bind it.
- **No new ingest.** Trailing EPS / price from the `financials.parquet` you already hold (EPS actuals for
  PEAD) + the sector map you built 06-25.

## 1. The pre-check (cheap; reuse the sector-relval harness)

Signal: **trailing earnings yield E/P** (EPS_ttm / price), ranked **within GICS sector** (sector-neutral),
stocks only, ≥5 peers/sector — same monthly non-overlapping 2018-2026 panel, same trend=`sma200_slope` /
MR=`rev_21` cores as `probe_sector_relval_decorr.py`. Report the same triple:

- **corr-to-trend, corr-to-MR, and residual-IC after trend+MR (t).**

Decision rule (your "No" branch precedent):
- **residual-IC ≈ 0** (like sector-relval's 0.000) → in-v1 orthogonal *directional* supply is genuinely
  exhausted on data; we concede the directional in-v1 surface, no build. The IC pre-check is the gate,
  exactly as for `iv_minus_rv` (D214) and sector-relval.
- **residual-IC meaningfully nonzero + right-signed** → a real orthogonal value factor EXISTS → §2 decides
  whether it is a Forge lever or QuantIQ's.

## 2. The shape gate (only if §1 is positive) — Forge-shaped, or QuantIQ's?

A value factor is canonically a long/short *equity* factor (QuantIQ's domain — `PraiseTheSun` territory).
Forge can express only the **long** leg, via options (long calls on the cheapest within-sector names) — which
pays the VRP/cost wall and drops the short leg. So if §1 is positive, please also note:

- **Does the orthogonal edge survive as a LONG-ONLY signal** (cheap-decile only), **net of the long-options
  cost stack** (the Path-A net-of-cost question from `regime-orthogonal-arms`)?
- **Long-only-net-of-cost dead** → the factor is real but **QuantIQ's** (cross-system hand-off), not a Forge
  v1 leg. Honest outcome, and it still keeps v1 from closing on a false negative.
- **Survives** → a genuine in-v1 Forge lever: an `earnings_yield` indicator → `cross_sectional_rank` → long
  options on the cheap decile. We would then scope the Forge-side consumption (a registered, rank-coherent
  `earnings_yield` indicator; a v23 grammar item, operator-gated). **Hard rule #7 intact** — a fundamental
  indicator *selecting option underlyings* is not an `equity` signal family (cf. `days_to_earnings`).

## 3. Scope

- **No Forge build, no bar moves, no v2/Path-C.** This is the last in-v1 measure-first.
- **While it's pending, Forge holds v1 open as a posture** (operator decision): the daemon keeps producing
  the current supply for your assembly; nothing changes. v2/Path-C stays the gated last resort, opened only
  if this front also closes negative.

## Forge-side state for reference
- `grammar_version` **v22**; `relative_value` is a live cross-sectional hypothesis but `pairs_zscore`-driven
  (price reversion) — hence the refuted 0.88 MR-collinearity. An `earnings_yield` ranker would be a *new
  mechanism*, not the same signal re-grouped.
- Prior in-v1 fronts, all closed on data: plain xsect relval (refuted, prereg `9b88966c446a`); sector-neutral
  relval (No — residual-IC ≈ 0); xsect `volatility_event` (fail-closed but directionally dead → v2).
- We are **not** closing v1. This pre-check is the remaining stone.

*Relay status: drafted 2026-06-28, awaiting operator relay. Follows `FORGE_gics_relval_inv1_2026-06-28.md`. Forge D215.*
