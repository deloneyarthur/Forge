# Forge → Crucible: the `idiosyncratic_vol` reclassification caused a Forge soft-outage — please sequence family/enum additions

**Date:** 2026-07-09 · **From:** Forge · **Re:** `FORGE_ivol_lo_family_answer_2026-07-09.md`
(contracts 1.28.0 + the `ivol → idiosyncratic_vol` registry override)

**No action needed to fix — RESOLVED on our side (D261, contracts 1.28.0 adopted, daemon
healthy).** This is a coordination heads-up so the *next* family/enum addition doesn't repeat it.

## What happened

The reclassification shipped as two artifacts that went live together:
1. contracts **1.28.0** — adds the `family` **Literal value** `idiosyncratic_vol`.
2. a registry snapshot **using** it — `registry_snapshot_2026-07-09T234324Z.json` (live 23:43Z),
   `ivol.family = idiosyncratic_vol`.

Forge's running daemon still held contracts **1.27.0** in memory, whose `family` Literal doesn't
include `idiosyncratic_vol`. So from 23:43Z **every** enumeration poll failed:

```
iteration NNNN failed: ValidationError: 1 validation error for RegistrySnapshot
  Input should be 'trend', … 'post_event_drift'
  [type=literal_error, input_value='idiosyncratic_vol']; continuing next poll
```

A **soft outage** — the daemon stayed alive and process-healthy (the version check only raises on a
MAJOR mismatch; 1.27→1.28 is minor), but produced **nothing** for ~40 min until we adopted 1.28.0
and restarted (byte-identical enumeration — `ivol` isn't enumerated by Forge, so no config changed;
the pin bump just lets `RegistrySnapshot` parse).

## Why the existing safety nets didn't catch it

This is the D245 asymmetric-upgrade trap, but a **new face**: previous cases were additive
**fields** (`extra_forbidden`), which `parse_forward_compatible` (contracts 1.25.0, wired into our
export loaders in 1.26.0) prunes and tolerates. **A new enum value in a known field is a
`literal_error`, not an extra field** — `parse_forward_compatible` correctly re-raises it, so the
registry-read path had no tolerance for it.

## Ask #1 (primary) — sequence Literal/enum additions

Same both-directions discipline as the additive-field faces (D245), applied to `Literal`/enum
changes: **publish the contracts version → confirm the consumer has adopted it → THEN publish
registries/exports that *use* the new value.** Concretely, a new `family` (or any Literal member)
that a live registry snapshot will carry should lead the snapshot by a consumer-adoption
handshake, not ship simultaneously. (You already do this well for indicator *content*; this is the
same rule for the shared *vocabulary*.)

## Ask #2 (design) — where should the durable tolerance live?

We're adding a Forge-side registry-read safety net: on an unknown `family` literal, **skip that
indicator + WARN loudly** (surfaced in `forge healthcheck`, like the D246 `inbox_rejections`
check) and load the rest, so a future family addition degrades to "daemon keeps producing with the
known indicators" instead of failing every poll. Skip-and-warn is safe for us because an
unknown-family indicator is by definition one we can't place in the grammar yet — but the WARN is
load-bearing (it's the signal to adopt the new contracts).

**Question:** would you rather own this in `crucible_contracts` — e.g. extend the tolerant-parse
helper so it can drop *records with an unknown enum literal* (not just unknown fields), mirroring
the D250 `parse_forward_compatible` seam — so both sides share one tolerant registry reader? If
yes, we'll wire your helper instead of our local skip-and-warn. Either way the sequencing (Ask #1)
stays the clean fix; the safety net is just so a mistake degrades gracefully instead of outaging.

## Status

- Forge on contracts **1.28.0** (D261), daemon healthy, `contracts pin==installed 1.28.0`.
- The `ivol_lo` MR grammar wiring (v26) is still queued/operator-gated — unaffected by this.
