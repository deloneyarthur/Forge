# Crucible handoff — consuming Forge's funnel complement (D096)

> **From:** Forge · **To:** the Crucible funnel agent (`FUNNEL_INSTRUMENTATION.md`)
> **Status:** Forge side shipped (D096), restart-pending. Two export artifacts published per batch.
> **Reads with:** `FUNNEL_INSTRUMENTATION.md` (your spec), `FUNNEL_INSTRUMENTATION_FORGE.md` (the Forge complement).

This is the Forge-side complement your spec marks `[Forge-opt]`. It lights up your two upstream stages (`enumerated`, `survived pre-filters`) and provides the interim source for your **Stage 0** (grammar-version slicing). Your funnel still degrades gracefully without it (your hard rule #7); this just makes the data available.

---

## What Forge now publishes (two files, refreshed after every batch)

Both are written **atomically** (tmp-then-rename) to **Forge's own export dir** — `~/forge_data/exports/` — not your `~/optbt_data/exports/`. They share a filesystem today; see "Read path" below if that ever changes.

### 1. `forge_funnel.json` — your two `[Forge-opt]` stages (Part B)

```json
{
  "schema_version": "1.0",
  "exported_at": "2026-05-29T20:53:00+00:00",
  "coverage": { "batches_total": 812, "batches_with_funnel_counts": 41 },
  "per_grammar_version": {
    "v4": {
      "batches": 41,
      "enumerated": 1230000,
      "survived_prefilters": 11800,
      "submitted": 8200,
      "rejection_breakdown": { "expected_trades": 840000, "permutation_test": 150000, "...": "..." },
      "enumerated_by_hypothesis": { "regime_arbitrage": 900000, "mean_reversion": 120000, "...": "..." }
    }
  }
}
```

Maps onto your funnel table directly:
- `[Forge-opt] enumerated` ← `enumerated` (annotation: `enumerated_by_hypothesis` = "which grammar branch")
- `[Forge-opt] survived pre-filters` ← `survived_prefilters` (annotation: `rejection_breakdown` = "which pre-filter killed the rest")
- bridges to your `[Crucible] submitted` ← `submitted` (post-diversifier count; should reconcile with your submitted count for that version)

Invariant you can assert: `sum(rejection_breakdown) == enumerated - survived_prefilters`, per version.

**Coverage honesty:** only batches recorded after D096 carry these counts; `coverage` reports total-vs-included so the funnel is never silently truncated. `per_grammar_version` covers the instrumented batches; older batches are excluded (same "version-sliceable from the instrumentation date forward" posture as your Stage 0).

### 2. `forge_submission_versions.json` — your Stage 0 source (Part A, interim)

```json
{
  "schema_version": "1.0",
  "exported_at": "2026-05-29T20:53:00+00:00",
  "config_hash_grammar_version": { "3f9a1c...": "v4", "a17b22...": "v4", "...": "..." }
}
```

A `config_hash → grammar_version` join-map for **every** config Forge has submitted. Well-defined as a function: Forge unique-indexes `config_hash` (hard rule #9), so each hash was submitted exactly once, under exactly one grammar version.

---

## The Stage-0 divergence — please read

Your spec's Stage 0 assumes the version arrives **in the submission metadata** and your inbox watcher reads it into a `runs.grammar_version` column. **It cannot today:** Forge submits a bare `StrategyConfig` via `crucible_contracts.submit_candidate`, and that model is `extra="forbid"` with no `grammar_version` field — there is nowhere in the current contract for the version to ride. (Confirmed in `crucible_contracts/{models,queries}.py`.)

So, per the operator's decision, there are **two tracks**:

- **Now (interim):** populate `runs.grammar_version` by **joining `runs.config_hash` against `forge_submission_versions.json`**. For runs whose `config_hash` isn't in the map (pre-instrumentation, or never-from-Forge), mark `grammar_version = 'pre-instrumentation'` exactly as your Stage 0 spec already prescribes. This needs no contracts change and unblocks your version-slicing immediately.

- **Durable:** a contracts change is proposed (`CONTRACTS_GRAMMAR_VERSION_PROPOSAL.md`) to add `grammar_version` to the submission payload **without changing `config_hash`** (the field is excluded from the hash, so all historical hashes/joins stay valid). Once it lands and Forge stamps it, your inbox watcher can read `config.grammar_version` directly — your Stage 0 as originally written. The join-map can stay as a backfill/cross-check during the transition, then retire.

Both converge on the same `runs.grammar_version` column; the interim join-map is just the bridge.

---

## Read path (one thing to confirm)

Forge writes to `~/forge_data/exports/`. If your funnel process runs somewhere that can read that directory (same host/filesystem today), point it there. If not, tell us and we'll agree a published location under `~/optbt_data/exports/` or a copy step. We deliberately kept Forge writing into its **own** export space rather than into your `~/optbt_data/exports/` to keep the ownership boundary clean — but the path is negotiable.

## Coordinate back

1. Confirm the read path above.
2. Confirm you'll consume the **join-map** for Stage 0 now (interim), and weigh in on the **contracts proposal** for the durable field.
3. Optional: confirm whether `forge_funnel.json`'s `submitted` per version should reconcile against your own `submitted` stage as a cross-check (it should match closely; divergence would flag a submission/ingest gap).

No rush on the contracts side — the interim join-map makes your funnel fully version-sliceable today.


---

## UPDATE 2026-05-30 — Track A forward-stamping LIVE; contracts 1.14.0 adopted (Forge D097)

The Stage-0 grammar-version axis is now complete on the Forge side, both directions:

- **Forward:** every submission's `StrategyConfig` now carries `grammar_version`
  (the live grammar version, hash-excluded), so `runs.grammar_version` populates
  directly for new runs. Forge pin bumped to `crucible_contracts==1.14.0` (the
  durable field from `CONTRACTS_GRAMMAR_VERSION_PROPOSAL.md`, now landed).
- **Historical:** the `config_hash -> grammar_version` join-map
  (`~/forge_data/exports/forge_submission_versions.json`) is published each batch
  for back-resolving the ~51k pre-instrumentation runs.

Crucible side: resolver order `runs.grammar_version` column -> join-map ->
`pre-instrumentation` (as designed). `crucible funnel` coverage
(`version_resolved_runs`) should climb from 0 as new stamped runs land and the
backlog back-resolves. No Crucible change required.
