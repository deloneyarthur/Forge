# Task: coordinate with Crucible / contracts

Scope: cross-repo work. Forge, Crucible (`../Crucible`), and `../crucible_contracts` are sibling
repos maintained by separate agents; the operator carries messages between them. System context:
`../PIPELINE.md`.

## The boundary

- `crucible_contracts` is the ONLY import path between systems (hard rule #2). Never import
  Crucible internals; never read `~/optbt_data/runs.duckdb` directly.
- A missing model/field is a **contracts gap**: surface it, don't work around it. Propose an
  additive contracts change in the outgoing prompt.
- On a contracts release: bump `FORGE_EXPECTED_CONTRACT_VERSION` in
  `src/forge/core/contracts_check.py`, refresh `uv.lock`, update test fixtures, run `forge check`.
  §13.5 halts the CLI on MAJOR mismatch. Watch-item: Crucible has bumped contracts unannounced
  (D106) — `forge check` failing after a quiet period likely means this.
- **A contracts minor that changes parsed models is NOT live-inert** (D124 post-mortem): the
  running daemon keeps its boot-time contracts modules, so when Crucible's republished export
  carries the new fields, every registry load fail-loops on `extra_forbidden` until the service
  restarts (correct fail-loud, but emission stalls). If an adoption precedes a counterparty
  republish, the go-ahead prompt must either (a) schedule the operator-gated restart BEFORE the
  publish, or (b) state the expected stall-and-restart explicitly. Journal trap: the loop logs
  `registry_loaded_from_export` BEFORE validation — a stalled daemon looks half-healthy; grep
  for `extra_forbidden` and recent `batch_id=` lines to tell.

## Outgoing (Forge → Crucible)

Write `PROMPT_CRUCIBLE_<topic>.md` at repo root. Include:

1. Exact asks, numbered, each independently answerable.
2. Evidence (queries run, journal lines, counts) — not conclusions alone.
3. Version strings and UTC timestamps for any cohort you want them to cut on.
4. What Forge will do under each possible answer.

Tell the operator it's ready to pass. After a grammar deploy, always relay the new version string
+ deploy timestamp so Crucible can run `crucible funnel --compare`.

## Incoming (Crucible → Forge)

Responses and handoffs land in `../Crucible/docs/handoffs/FORGE_*.md`.

**Verify premises against live data before acting** — handoffs have arrived stale (D103: "dies in
the funnel" was a stale-cohort artifact) or with wrong mechanism theories (D104). Re-derive the
headline numbers via `investigate-live.md` first; record agreements/corrections in the D-entry.

## Lifecycle

Completed prompt/response pairs move to `_archive/`. Older deleted prompts are recoverable via
`git show e85f0d4^:<filename>` (see the note atop `IMPLEMENTATION_DECISIONS.md`).
