# Proposal: v43 — 30-name structural exclusion rider (yield-audit round 1)

Status: **APPROVED-STAGED (operator "Ship all 30", 2026-07-20) — awaiting the
deploy window.** Ships as its own bump or rides the next Crucible-driven bump,
whichever comes first (candidate: the v39→v40 MR read ~07-22/23). Prereg
`44a4e08aef4f` is on record (cohort cut 2026-07-21T00:00:00) BEFORE any code.
Date: 2026-07-20. Source: `forge yield-audit` first live run (D302).
Relates to: [[D302]] (the detector + guards), [[D286]]/[[D293]] (frozen-list
precedents), [[D207]] (prereg), hard rule #4 (tightening), D273 (label guards).

## Evidence (live snapshot, 2026-07-20; all guards applied)

- 346,904 decided rows since the clean era (2026-06-10T17:17:13), 33,467
  pre-07-18 ve ghost rows cut.
- **30 names, each ≥500 decided verdicts with ZERO conversions** (component or
  promote): AAL, ADBE, AMZN, ARKK, BSX, DIA, DVN, EEM, EFA, GE, INTC, KO,
  LRCX, LUV, MS, MSFT, NEM, NKE, PEP, TXN, UNG, UPS, VZ, WFC, XBI, XLF, XLI,
  XLP, XLV, XOM (513–1,139 decided each; full counts in the D302 entry).
- **Universe cross-check PASSED** (2026-07-20T184245Z export, tiered reader):
  all 30 still in the 118-name union (DIA tier-1; AMZN/GE/MS/MSFT/XOM tier-2;
  the other 24 tier-3) — the waste is ongoing, not historical.
- **Ongoing cost: 3,092 single-name submissions in the last 7 days = 4.7% of
  the stream** (cf. the EV retirement freeing 6.2%).

## The change (one bump)

`_STRUCTURALLY_UNTRADEABLE_UNDERLYINGS` +30 (8 → 38 names; NB 38/118 = 32% of
the union — flagged to the operator and approved). Same frozen-list terms as
v34/v37/v41: Crucible-measured-or-our-verdict-measured per name, re-admission
on their relay, the WHOLE list retires when their queue-time liquidity
preflight ships. Known limitation stands: cannot keep these names out of
cross_sectional baskets (underlying None; their preflight is the complete fix).

Mechanics at build time: grammar_version bump + archive + Decision Log (hard
rule #10 — any emission-population change is versioned; rule #6 forbids it as
a versionless change); goldens re-pin environment-matched (the pool shift
moves every underlying draw — the v37/v41 signature); emission proof = zero
draws on all 38 names over a 3k cold enumeration; first-batch audit = zero
excluded-name draws; deploy relay carries the name list + the **row-45
cross-check request** (the v41 ASML/COST pattern) + funnel signatures.

## Post-ship reads

- Prereg `44a4e08aef4f` resolves on post-cut data (the names can no longer be
  drawn single-name, so the resolution read is on any REMAINING decided
  verdicts in flight + their row-45 telemetry; a paradoxical conversion would
  be visible in verdicts on pre-cut submissions).
- `forge yield-audit` keeps running (weekly, per the D302 proposal); its
  excluded-names retire-review section now tracks all 38.
