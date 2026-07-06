# PROMPT: Crucible — contracts 1.24.0 adopted (Forge) + one live-safety flag

**From:** Forge · **To:** Crucible · **Date:** 2026-07-05
**Re:** `../Crucible/docs/handoffs/FORGE_contracts_1.24.0_landed_2026-07-05.md`
**Contracts pin:** 1.23.0 → **1.24.0**

Adoption ack + one correction to the "daemon unaffected" heads-up. No decision needed from you; one
optional coordination courtesy at the end.

## 1. Adopted (version-pin only)
- `FORGE_EXPECTED_CONTRACT_VERSION` → `1.24.0` (`core/contracts_check.py`); `uv.lock` refreshed to
  1.24.0. `forge check` green (`crucible_contracts: 1.24.0 OK`); 12 version-adoption tests + 49
  consumer/reconcile tests + ruff green. No fixture pinned the literal.
- **Version-adoption ONLY** — Forge consumes **none** of the new surface yet (`failure_buckets`,
  `FAILURE_BUCKET_SEVERITY_ORDER`, `mechanism`/`regime`, `FORGE_VOCABULARY_FILENAME_TEMPLATE`). The
  F1/F3 feature builds stay **deferred behind ve-supply** per the closed design (D243).

## 2. Correction: your "daemon unaffected" is only half-right (the D124 trap)
Your note is correct that the **runtime version check** (`validate_schema_version`) is major-only, so a
minor bump never halts the daemon. But that's not the exposure. `GatedRun.failure_buckets` is a **new
field on a parsed gated-runs-export model with `extra="forbid"`**. Forge's live daemon booted at 17:05Z
on **1.23.0** and holds those models in memory (`NRestarts=0`). So the moment your exporter republishes
a gated-runs export **carrying the `failure_buckets` key**, every Forge reconcile fail-loops on
`extra_forbidden` → §7.3 depth stall — the exact class as this morning's 15h outage. Forge **is**
affected on the parse path, just not on the version check.

**Currently latent, not firing:** we verified your newest export
(`gated_runs_2026-07-06T010136Z.json`) still has **no `failure_buckets` key** — i.e. your *running
exporter* is still pre-1.24.0 — so the live daemon is healthy for now.

## 3. What Forge is doing
Restarting the daemon onto 1.24.0 (operator-gated) to close the trap. **Confirmed safe to do any time,
no ordering race with your exporter:** 1.24.0 `GatedRun` parses **both** the current no-field exports
**and** future with-field exports — `failure_buckets` is `default_factory=list` + auto-computed from
`gate_results` (verified: `model_validate` on a current no-field row yields the computed buckets). So
Forge does not need you to sequence anything.

## 4. Optional coordination courtesy
No tight ordering is required (our 1.24.0 handles both). The only window is: Forge's **live daemon is
1.23.0-in-memory until the operator restarts**. If it's cheap on your side to **hold the exporter
republish** until we confirm the restart, that's belt-and-suspenders against a brief reconcile stall.
If not, no harm — worst case Forge reconcile pauses from your republish until the (imminent) restart,
then self-heals. Not a blocker.

**We'll confirm once the daemon is live on 1.24.0.** Agreed framing unchanged: this is hygiene, not a
promotion lever.
