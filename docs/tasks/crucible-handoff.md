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
- **A contracts bump must restart BOTH directions' processes** (D244/D245): each process holds its
  boot-time contracts modules, so upgrade asymmetry wedges either path. READ direction (D244):
  Forge's daemon fail-loops on new export fields until `forge.service` restarts. SUBMIT direction
  (D245): Crucible's `crucible-inbox-watcher` rejects 100% of Forge's submissions as
  `extra_forbidden` when Forge emits new `StrategyConfig` fields first — surfaces only as a quiet
  `0/N gated` per-batch stall (inbox-rejected runs enter NEITHER `gated_runs` NOR `failed_runs`;
  healthcheck's `inbox_rejections` check, D246, CRITs on it within hours). Adoption plans must
  name both restarts explicitly: Forge `forge.service` AND Crucible's inbox watcher + exporter.

## The channel (D362 — the shared repo IS the transport)

All relays live in **`~/proj/freeze/relays/`**, both directions. **Committing there is
delivering** — there is no separate "send" step and no unsent queue to track (the pre-D362
"N unsent" bookkeeping was a fiction; every tracked relay had already been answered).

- Outgoing: `FORGE_<topic>_<YYYY-MM-DD>.md`, commit message `relay(crucible): …` /
  `relay(quantiq): …`.
- Incoming: `CRUCIBLE_*` / `QUANTIQ_*` files appear the same way; watch the repo, not root.
- Standing obligations and what each side has already handled: **`freeze/INDEX_forge_answered.md`**
  (ours) and **`freeze/relays/INDEX_crucible_answered.md`** (theirs). Update ours in the same
  commit when an exchange creates or discharges a standing obligation.
- Never write `PROMPT_CRUCIBLE_*.md` at Forge root — that channel is retired; the historical
  pile is in `_archive/`.

## Outgoing content (unchanged by the channel move)

1. Exact asks, numbered, each independently answerable.
2. Evidence (queries run, journal lines, counts) — not conclusions alone.
3. Version strings and UTC timestamps for any cohort you want them to cut on.
4. What Forge will do under each possible answer.

After a grammar deploy, always relay the new version string + deploy timestamp so Crucible can
run `crucible funnel --compare`.

## Incoming

**Verify premises against live data before acting** — handoffs have arrived stale (D103: "dies in
the funnel" was a stale-cohort artifact) or with wrong mechanism theories (D104). Re-derive the
headline numbers via `investigate-live.md` first; record agreements/corrections in the D-entry.

## Lifecycle

Not every relay needs a reply: one that carries no ask is closed by its D-entry (D362). Answered
exchanges stay in `freeze/relays/` — the mailbox is the record. The retired root-file channel's
prompt/response pairs are in `_archive/`; pre-archive deleted prompts are recoverable via
`git show e85f0d4^:<filename>` (see the note atop `IMPLEMENTATION_DECISIONS.md`).
