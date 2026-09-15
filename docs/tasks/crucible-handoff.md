# Task: coordinate with Crucible / contracts

Scope: cross-repo work. Forge, Crucible (`../Crucible`), and `../crucible_contracts` are sibling
repos maintained by separate agents; relays travel through the shared `~/proj/freeze` repo (below)
and the operator arbitrates. System context:
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
- **There is no Forge process to restart** (D416): the weekly run imports whatever contracts the
  tree pins when it starts, so an adoption is a commit and the next Sunday binds it. The hazard is
  now asymmetry ACROSS THE WEEK, in both directions (the D124 / D244 / D245 lessons, re-cut):
  - READ: if Crucible republishes exports with new fields before Forge adopts the pin, the Sunday
    run fails loud at boot or reconcile (`extra_forbidden`; exit 2/1, unit FAILED = the page) and
    submits nothing — one lost week, not a stall. Adopt before their publish, or accept the week.
  - SUBMIT: if Forge emits new `StrategyConfig` fields before Crucible's inbox watcher restarts,
    the whole week's batch is rejected `extra_forbidden` — those runs enter NEITHER `gated_runs`
    NOR `failed_runs`, so the only symptom is the next run's reconcile seeing 0 decisions on that
    `batch_id`. Adoption plans must name Crucible's restart (inbox watcher + exporters)
    explicitly; Forge's side is the commit.

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

After a grammar deploy, always relay the new version string + the first live run's instant (the
cohort boundary) so Crucible can run `crucible funnel --compare`.

## Incoming

**Verify premises against live data before acting** — handoffs have arrived stale (D103: "dies in
the funnel" was a stale-cohort artifact) or with wrong mechanism theories (D104). Re-derive the
headline numbers via `investigate-live.md` first; record agreements/corrections in the D-entry.

## Lifecycle

Not every relay needs a reply: one that carries no ask is closed by its D-entry (D362). Answered
exchanges stay in `freeze/relays/` — the mailbox is the record. The retired root-file channel's
prompt/response pairs are in `_archive/`; pre-archive deleted prompts are recoverable via
`git show e85f0d4^:<filename>` (see the note atop `IMPLEMENTATION_DECISIONS.md`).
