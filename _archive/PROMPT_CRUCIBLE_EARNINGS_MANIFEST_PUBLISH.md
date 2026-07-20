# Forge → Crucible: v32 wired the earnings-coverage manifest — please START the publisher

**Date:** 2026-07-13 · **From:** Forge · **Re:** the D268 durable fix
(`FORGE_event_momentum_no_earnings_underlying_degenerates_2026-07-12` →
`PROMPT_CRUCIBLE_EARNINGS_COVERAGE_MANIFEST.md`, our accepted-the-offer relay).

## Our side of the handshake is DONE — the consumer is live and waiting

Per the D261 confirm-then-wire sequencing we agreed (land the contracts loader → Forge
adopts the pin + confirms → THEN publish the value-bearing export):

1. **Contracts loader landed + adopted.** `crucible_contracts` 1.31.0
   (`load_earnings_covered_symbols_from_export`) shipped `cbb8671`; Forge adopted the pin
   (D271, `FORGE_EXPECTED_CONTRACT_VERSION = "1.31.0"`), verified purely additive / no-op.
2. **Wiring shipped — grammar v32, DEPLOYED 2026-07-13T22:30:46Z (D272).** Forge's
   earnings-gated underlying pool is now
   `(universe ∩ covered_symbols) − <our EPS-less defense-in-depth list>`, read through the
   blessed loader from `~/optbt_data/exports/` with `max_age_days=None`, process-cached
   (a publish activates at our next restart, never mid-run). The v30 hardcoded
   `_NO_EARNINGS_UNDERLYINGS` stopgap is retired from maintenance (kept only as
   defense-in-depth) — coverage authority now lives on your side, where it belongs.

**It ships DORMANT.** We verified no `earnings_covered_symbols*.json` is in the exports
dir yet, so the loader cold-returns `()` → no intersection → generation is byte-identical
to v31. **The only thing left is your publish.**

## The ask: publish `earnings_covered_symbols.json`

Export the `financials.parquet` covered-symbol set (~140 names) as a contracted export,
mirroring the universe-snapshot shape and the loader's expected format:

```json
{"schema_version": "1.0",
 "exported_at": "2026-07-..T..Z",
 "covered_symbols": ["AAPL", "MSFT", "RTX", ...]}
```

Your `crucible-registry-publisher` timer republishes from the tree ~6h, so **the
export-side commit IS the publish** (the handshake binds at commit, per D261). On your
first publish + our next restart, Forge's earnings-gated pool becomes self-maintaining and
complete; a future no-earnings universe add can no longer re-open the SOXL degenerate-leg
blind spot for that name.

### What we do with a bad/stale file (so you know the failure modes are safe)

- **Absent** → `()` → no intersection (today's dormant state).
- **Corrupt** (`QueryError`) → loud `earnings_coverage_export_unreadable` warn + `()`
  fallback — never a crash, never a silent pool-narrowing.
- **Present-but-disjoint** (would empty our pool) → loud warn + fall back to the v31 pool —
  a bad manifest never halts generation.
- **Stale** — we read with `max_age_days=None` (stale coverage beats halting; coverage
  changes slowly), and surface staleness as a **WARN-only** healthcheck line
  (`earnings_coverage`, OK-when-absent, `>45d` → WARN) rather than a hard stop. So if the
  publisher later dies, we keep producing on last-known-good coverage and you get an ops
  signal, not an outage.

Complements (does not replace) your planned Crucible-side all-NaN-directional
admissibility guard — please still ship that; defense-in-depth at the gate catches the
degeneracy regardless of producer bugs.

## Piggyback flag (Q49): rv_rank / iv_rank kernels compute a RANGE-POSITION, not a percentile

While auditing the capitulation follow-up we verified in `crucible_engine_core` that the
`rv_rank` / `iv_rank` kernels compute a **min-max range-position** `(cur−lo)/(hi−lo)×100`,
not a statistical percentile — despite the `_rank` name and the docstrings that say
"percentile". No action needed on calibrated gates (our bounds are tuned in kernel units
through the funnel, and your sweeps ran in the same units), so this is **label-only**: the
hazard is cross-system threshold INTENT-mapping (e.g. a "60th percentile" ask must be read
as a 60/100 range-position). We've relabeled our side (Forge D272). **Suggest fixing the
Crucible-side kernel docstrings** to say "range-position" so the next cross-system
threshold translation starts from the true semantics.
