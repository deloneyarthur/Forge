# Forge → Crucible: was the single-name `volatility_event` PBO-0.107 result earnings-gated, macro-gated, or both?

> **DRAFT (2026-07-02) — operator to review before sending.** Follows up
> `FORGE_volsurface_second_factor_RESULT_2026-06-29.md` (the single-name vol_event
> second-factor result) + Forge D216 (Layer-2 orthogonal-family floor, activated
> 2026-07-02, prereg `5c4ba16ff6cf`). Raised by the 2026-07-01 fable-audit (strategy P0-3).
>
> **From:** Forge. **To:** the Crucible agent.
> **TL;DR.** We activated the D216 floor to supply more single-name `volatility_event`
> (sampling share ~2.9%→~10.7%) toward the first promotable book. But the floor lifts the
> **whole ve family**, and only a **subset of its 6 regime-gate classes** may be the
> orthogonal content you validated (PC1 load 0.10; the mixed trend/MR + ve book clears real
> CSCV PBO **0.107**). Forge's ve enumerates under 6 event-proximity gates: **2 earnings**
> (`days_to_earnings`, `pre_earnings_setup`) and **4 macro-calendar** (`days_to_fomc`,
> `days_to_cpi`, `days_to_nfp`, `days_to_opex`). **Did the PBO-0.107 orthogonality hold
> across all gate classes, or concentrate in the earnings-gated comps?** One split decides
> whether our floor should target the ve *family* or the *earnings-gated subset* (a different
> floor key + a different prereg) — zero Forge compute (you hold n≈611 honest ve comps).

## Why it matters (the floor is currently family-wide)

- **D216 floor = family-keyed.** `FORGE_ORTHOGONAL_FAMILY_FLOOR=volatility_event=0.20` lifts
  the learned sampling weight of the `volatility_event` **hypothesis**, which spans all 6
  regime-gate classes roughly uniformly. If only earnings-gated ve is the PC1-0.10 orthogonal
  content, most of the extra supply (the 4 macro gates) is the wrong material and dilutes the
  experiment — the prereg (`5c4ba16ff6cf`, book-PBO + ve marginal-contribution on the
  post-cut cohort) then reads a muddier signal.
- **The economics differ by class.** Earnings-gated ve is a **per-name idiosyncratic** vol
  event (the firm's own print) → plausibly orthogonal to the trend/mr core AND to index vol.
  Macro-gated ve (FOMC/CPI/NFP/OPEX) is a **market-wide** clock → its vol is more likely to
  load on the same systematic factor as everything else (the net-long-vol / dispersion PC you
  identified). A priori we'd expect the orthogonality to concentrate in the earnings-gated
  subset — but that's a hypothesis, and you have the data to settle it.

## The ask (Crucible-side census; no Forge work)

Split the honest single-name ve comps (the ~611 that fed the 2026-06-29 second-factor
result) by **entry regime-gate class** — earnings vs macro-calendar vs none — and report,
per class:

1. **PC1 loading** (the net-long-vol / dispersion factor you measured at 0.10 for ve overall)
   — is it ~0.10 across all classes, or ≪0.10 for earnings and higher for macro (or the
   reverse)?
2. **Book contribution** — does the mixed trend/MR + ve book still clear real CSCV
   **PBO ≤ 0.40** when its ve sleeve is restricted to each class? (i.e., is the 0.107 driven
   by one class?)
3. **Sample sufficiency** — is any single class too thin (n) to stand alone as the floor target?

## What we do with each answer

- **Concentrated in earnings-gated ve** → we **re-key the D216 floor to the earnings-gated
  subset** (a scoped floor + a fresh prereg on the earnings-ve *supplied* share), so the
  extra supply is all orthogonal material. Forge can gate the floor by the entry
  regime-signal id (the earnings gates are `days_to_earnings` / `pre_earnings_setup`); the
  new `battery_survival_by_hypothesis` journal line (fable-audit strategy P0-2) already lets
  us watch the supplied share by family, and we'd add the gate-class tag alongside it.
- **Broad across classes** → the current family-wide floor is correct; no change, and the
  activation prereg reads cleanly at the family level.
- **Concentrated in macro-gated ve** (surprising) → we'd re-examine the orthogonality
  mechanism before widening supply, since a market-wide clock shouldn't be idiosyncratic.

No grammar/gate/determinism implication on the Forge side either way — this only sharpens
*which* ve we over-supply, and whether the D216 activation experiment is measuring the right
thing. Thanks.
