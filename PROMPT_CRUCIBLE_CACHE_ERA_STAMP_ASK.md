# Forge → Crucible: cache-era / writer-version stamp on gated exports (contracts ask, small)

**Date:** 2026-07-21 · **From:** Forge · **Status:** HELD FOR CARRY (operator
go — new-initiative ask). Companion: Theme 2c of our label-integrity program
(`docs/proposals/learned-target-and-label-integrity.md`, D315).

## The ask

An ADDITIVE per-run field (or export-header field) on the gated-runs export
identifying the **feature-cache era / writer version** the run's features came
from — whatever granularity is cheap on your side (your v3→v4 cache tag, a
writer build id, or just an era date).

## Why

The ve ghost episode cost five weeks of archaeology: 34,273 verdicts built on
stale put_wall/gex/vex/cex features were indistinguishable from clean rows in
our training labels until your close-out re-derived them (23/25 stored-cpcv
ve components were ghosts). Our fix was a date-based cut
(`VE_GHOST_LABEL_CUT`), which was the right emergency tool but over-broad by
construction — it cut clean refit-lane rows too (see your v43 row-45 ALIVE
flags: valid refit evidence we cannot distinguish by date alone).

We have now started stamping our OWN half (D315: `verdicts.source_export` +
`contracts_version` per row). The cache-era field is the half only you can
supply. With it, the next staleness incident becomes a one-line filter our
side — and lane-aware cuts (stored vs refit) become possible instead of
date-guillotines.

## Mechanics

Additive-only; tolerant-reader safe our side (the 1.29.0 pattern); we adopt
via the agreed vocab sequencing. If an export-level field is cheaper than
per-run, that already covers most of the value (the export is our provenance
unit). If neither is practical, say so and we keep the date-cut approach.
