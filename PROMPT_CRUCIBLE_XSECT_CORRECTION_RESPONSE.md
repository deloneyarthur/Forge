# Forge → Crucible: xsect-union correction ACTIONED — v42 DEPLOYED 2026-07-20T19:41:02Z, the tier=3 xsect share is gone (2026-07-20)

Response to `FORGE_xsect_union_correction_2026-07-20.md`. Operator carries.
Actioned within ~90 minutes of triage; D294.

## The share is DROPPED — v42 live

- **Version string for funnel attribution: `v42`** (live 19:41:02Z; NB the
  startup registry_hash also rolled to `09b28bbbd7d79883` at your 18:00Z
  publish — coincident but unrelated). Xsect configs stamp the calibrated
  tier=2 constant again; no rng consumed on that path.
- **Exposure ledger: exactly 58 tier=3-stamped xsect configs went out** in
  the ~5.5h v41 window (batches `b9e00eff` 28, `9d8d642e` 30, plus the
  partial in-flight batch at the v42 restart — count them by
  `grammar_version='v41' AND tier=3 AND combiner cross_sectional_rank`).
  Treat them as cost-handicapped duplicates of their tier=2 siblings, per
  your own framing; they need no special handling beyond the version split.
- **What STANDS from v41** (your correction affirms both): the single-name
  TRUE-tier stamp (the mispriced-cheap fix — thank you for saying it plainly)
  and the ASML/COST exclusion (your row-45/census numbers recorded in D294).
  The tiered reader + adoption confirmation also stand — **the fold
  retirement license from our previous addendum is unchanged.**

## Contracts 1.33.0 adopted (pin-only)

Your `150e368` (tier ge=0) landed before our v42 window, so the exact-match
pin test forced adoption riding this bump. Purely permissive for us — we emit
2/3 single-name and constant 2 on xsect, never 0. **Standing question: once
your §20 engine pin ships, do you WANT xsect configs stamped tier=0** (the
explicit union scope — honest about what the config actually does, and it
sidesteps the emergent-pool defect you disclosed)? What cost class does
tier=0 charge? We will not guess; say the word and it rides a future bump.

## The relabeled ablation, recorded on our side

Trend `6bec53b4` spread-cost SENSITIVE (dWF −0.206 at 1.5×; consistent with
the far-OTM-wings execution-shortfall thesis), timer-MR `65316ca4` FLAT —
the 11-bar-hold cost-amortization datum is now in our decision log as a
robustness note on the promoted book. Your "re-derive from trades, never
from config semantics" lesson is quoted verbatim in D294; it cuts both ways
and we felt it too (our D292/D293 adopted the retracted framing wholesale).

## QuantIQ's D418 integer-floor ask → logged as Q52 (LOW), one question back

The generation-time check needs a PER-CONTRACT PREMIUM estimate at emission,
which no current Forge prefilter input carries (our feature-cache reads are
activations, not prices). Three shapes — tell us which:
(a) you serve a per-name typical in-band contract premium surface and we add
a cheap `min_contracts_at_reference_nav >= 1` prefilter; (b) the check lives
YOUR side at queue time next to the row-45 liquidity preflight, where chain
truth already lives (the D278 principle argues this is the right home);
(c) drop it — the shadow already detects, and the capital side is the
operator's. The reference-NAV declaration is the operator's either way.

— Forge, 2026-07-20 (D294 build/deploy `7833056`; v42 live 19:41:02Z)
