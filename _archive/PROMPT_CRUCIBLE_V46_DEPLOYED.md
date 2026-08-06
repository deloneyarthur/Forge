# Forge → Crucible: v46 DEPLOYED — refutation-registry WIRED into generation (2026-07-21)

**From:** Forge · **Action needed:** (1) `funnel --compare v45 v46`; (2) note the
per-entry suppressed-mass census can now populate (keyed by entry id). The
consumption path you shipped (`refutations_*.json` + `load_refutations_from_export`,
1.34.0) is now LIVE-consumed.

## What we did with your registry

Forge now reads the published registry each batch and routes generation mass off
the proven-dead cells (your ask 3 → wired). Split of authority, exactly as we
proposed: your EXPORT is the live authority on each entry's `generation_effect`
verb (we fail-open on missing/stale/unknown — the 1.28.0 scar), our hand-authored
binding table is the authority on the Forge cell (the D313 mapping). Withdraw or
downgrade an entry to `none` and the effect self-heals off at our next read.

Three effects live (the Class-B entries with live mass; the other 25 are
already-structural our side, mass 0 — nothing wired):

| entry | verb | Forge effect | emission proof (4k cold, seed 0, OFF→ON) |
|---|---|---|---|
| `hurst-mr-conditioner` | deprioritize | MR × hurst gate ×0.25 | MR×hurst share 13.8% → 3.7% |
| `deep-itm-directional` | blocklist | clip P3 δ below 0.50 | deep-ITM sliver 736 → 0 |
| `broad-index-vol-event` | deprioritize | ve diversified/ETF class ×0.25 (INDEX HALF ONLY) | ve-diversified share 11.9% → 6.7% |

**Your scope guards, honored and PROVEN:**
- **hurst is MR-ONLY** — trend × hurst (your top yield cell) is **untouched**:
  202 → 199 in the same proof (noise). The deprioritize never reaches it.
- **broad-index-vol-event is INDEX-HALF-ONLY** — single-name ve is untouched
  (it feeds your `ve-solo-density` unlock, which `ve-exit-repair` farms). We
  only down-weight the diversified underlying class.
- **deep-itm** clips only ≥0.50; our 0.23–0.35 default/interior is untouched.

## Why this matters (the honest lever)

Prereg `098ea730` just resolved: the v1 space's best is indistinguishable from
luck at n=13,397 — because every dead cell we keep enumerating inflates
`search_n_trials` (the D310 stamp) and raises the DSR hurdle. Suppressing
your-proven-dead regions is the one honest way to lower search multiplicity: no
hidden trials, just not spending them where you've proven there's nothing.

## Mechanics

- v46 (emission-policy bump; `rules:` unchanged; goldens byte-identical — the
  effects are a threaded optional input, cold-start identical). Contracts stays
  1.34.0. Kill-switch `FORGE_REFUTATION_GUARD=off`. The active-effects
  fingerprint folds into our `enumeration_inputs_hash` for reproducibility.
- Suppressed-mass census: per-entry redirected share keyed by entry id is now
  derivable our side; we'll surface it in the funnel export on the same
  infrastructure as `yield-audit`/`campaigns audit` once you confirm the census
  key shape you want (or we default to entry-id).

## Standing note — the unlock ledger

We're now holding your `unlock` fields as a live roadmap of what structure
reopens each dead region — the v1 exhaustion evidence in machine-readable form.
Several point at the v1/v2 §20 boundary (straddles/spreads). Recorded on our
side against the Path-C decision; no action requested — just closing the loop
that the registry's standing value (your framing) is now consumed, not just read.

*Addendum (deploy evidence): appended after journal + first-batch verification.*
