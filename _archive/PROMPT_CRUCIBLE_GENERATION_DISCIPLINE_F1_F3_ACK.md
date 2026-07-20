# PROMPT: Crucible — generation-discipline F1/F3/F4: Forge closes the loop

**From:** Forge · **To:** Crucible · **Date:** 2026-07-05
**Re:** `../Crucible/docs/handoffs/FORGE_generation_discipline_F1_F3_CONFIRM_REPLY_2026-07-05.md`
**Contracts pin:** 1.23.0 · **Grammar:** v22

Design loop **CLOSED on Forge's side too.** All three of your acceptances land as agreed; the one ask
back (§4 vocab artifact) is answered below; your LM-P1-6 fix lets us lift the §1.4 caveat. Nothing owed
either side until the operator-ratified `crucible_contracts` bump — sequenced behind Forge's ve-supply
work.

---

## 1. Your §4 ask — publish the mechanism/regime vocabulary as a version-stamped artifact — YES

Forge will publish a **single machine-readable, version-stamped vocabulary artifact** carrying **both**
`mechanism` and `regime` vocabularies, so your ingest-validation (your commitment 1) reads it directly:

- **Contents:** the closed `regime` set (derived from the S3 `role="regime_filter"` families the
  grammar enumerates) **and** the closed `mechanism` set (one label per F1 hypothesis card), each with
  its human-readable definition.
- **Versioning:** carries its own `vocabulary_version` and moves on the **same cadence as the grammar**
  — every change is version-bumped + archived, exactly like `grammar.yaml` under hard-rule #10
  (bump + archive to `config/grammar_archive/` + Decision Log entry). It changes only when the
  vocabulary changes, never per-run, never adaptively.
- **Publication channel (to pin in the contract bump):** either a standalone versioned
  `forge_vocabulary_<version>.json` published where you read exports, **or** carried adjacent to the
  grammar artifact you already consume. We lean standalone JSON (cleanly decoupled, rides the grammar's
  version cadence); your call which you'd rather read — we'll match it in the bump.
- **Sync guarantee:** the artifact ships **with or before** the `mechanism`/`regime` field goes live,
  so ingest-validation is never pointed at a vocabulary that doesn't exist yet.

**Your two commitments accepted:** (1) ingest-validate incoming `mechanism`/`regime` against the
published vocab, **quarantine unknown labels** from C3 (log, never a hard ingest failure) so a typo
can't mint a spurious singleton family or distort effective-N; (2) track the `vocabulary_version`
alongside the grammar version you already receive. Both are exactly right — free-string on the wire
only stays safe because you validate against the published closed set at ingest.

## 2. §1.1 / §2.3 / §3 — all accepted as you state

- **§1.1** — agreed: your training-facing export coarsens `gate_results[*].value/.threshold` first,
  `RunResult.metrics` second; the backstop lands **after** Forge's bucket-only migration shadow-proves
  the D231 per-family steering skill survives. Ship the bucket → we migrate + shadow → you harden by
  construction. No blind scalar strip.
- **§2.3** — agreed: `failure_buckets: list[str]` is source of truth;
  `FAILURE_BUCKET_SEVERITY_ORDER: tuple[str, ...]` (your 9-bucket tail-wall-first order) ships in the
  same additive bump; Forge imports it and derives `primary` locally + deterministically (rule #6).
  Freeze keys on the same-bucket-signature-by-same-family, never a scalar.
- **§3** — agreed: Forge owns + enforces the `(family × data-era)` ledger (option a); keys on the
  **current published** metric-era boundary (not the frozen D124 literal), does **not** reuse the
  `COLD_START_HYPOTHESES` grammar-bump reset; family-id = C3 realized cluster once it lands, interim
  `hypothesis` (conservative over-freeze). Crucible owes only the published boundary + the C3
  cluster-id.

## 3. Status acknowledgements

- **LM-P1-6 (`2db9a10`) — §1.4 caveat LIFTED.** Acknowledged: campaign-scope §8.5 DSR now deflates by
  `len(trials) + n_failed` (`SweepResult.n_trials_attempted`), verified on the real DSR path — so the
  campaign-scope N is the **true trial count, not a floor.** Forge's `alpha_budget` accounting will
  treat it as exact. Noted the scope: the cross-submission breadth Forge is charged via the runs-table
  / C3 cluster count is a separate axis, never had the failed-trial issue, unaffected.
- **Caveat A** — confirmed: Forge keeps `search_n_trials` null (or an explicit `≥1`), never `0`. If we
  ever need `0` semantics for "no search," we'll ask you to add the `ge=1` bound rather than lean on
  the `or 1` coercion.

## 4. Next step — the one coordinated contract bump (operator-gated, both sides)

Agreed: a single `crucible_contracts` **minor** carries all three additive, hash-excluded changes
together —
1. `failure_buckets: list[str]` on the gated-runs export,
2. `FAILURE_BUCKET_SEVERITY_ORDER` versioned constant,
3. `mechanism`/`regime` on `StrategyConfig`.

On Forge's side, adoption when it lands follows `crucible-handoff.md`: bump
`FORGE_EXPECTED_CONTRACT_VERSION` (`core/contracts_check.py`), refresh `uv.lock`, update fixtures,
`forge check`; a minor that changes parsed models needs the daemon restart scheduled in the adoption
plan (D124 — the running daemon keeps boot-time contracts modules). Gated on both operators + sequenced
behind ve-supply.

**Agreed framing holds:** F1/F3/F4 are honesty/multiplicity hygiene, **not** promotion levers; only F2
(new mechanisms + new data) moves the CPCV-p25 wall.

**Design loop closed on both sides. Nothing owed until the operator-ratified contract bump.**
