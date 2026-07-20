# Proposal: ops-debt roundup, post-promotion (Theme 5)

Status: **BRAINSTORM DRAFT — operator-gated; nothing ships off this doc.**
Date: 2026-07-20. Source: post-promotion process-improvement review.
Relates to: memory `pipeline-performance-audit-2026-07` +
`fable-audit/pipeline-performance/` (the committed plan), [[D295]] (cleanup
sweep #3 — relay archiving already done), `fable-audit/reliability/`
(REL-1..21, committed eab8204), [[D259]] (tmp-headroom incident class).

## Items, cheapest-first

### 5a. DuckDB write-path batching (the July perf audit, still unimplemented)
Per-row executemany + fsync: submit ~190s, reconcile ~20s per cycle.
Reconcile time sits INSIDE every deploy down-window (the stop→test→commit→
start ritual), so this buys deploy-window margin, not just throughput.
The plan already exists in `fable-audit/pipeline-performance/` — this is a
scheduling ask, not a design ask. Versionless persistence change; needs the
usual uncontended-suite + restart window to activate.

### 5b. Relay ledger (small, docs-only)
D295 archived 33 answered relays; the live/held pile is ~10 + research
notes. Remaining gap: no single index of relay state (sent / held-for-carry /
answered / superseded). One `RELAYS.md` table (filename, direction, state,
awaiting-what) maintained at triage time would replace re-deriving it from
STATUS blocks each session. No automation needed.

### 5c. Campaign-audit timer wiring (follows D297)
`forge campaigns audit` exists as an on-demand command. Once trusted, add it
to the daily 05:00 eval script (it already snapshots forge.db — reuse that
snapshot, D259 headroom rules apply) and surface a WARN line in
`forge healthcheck` when the last audit found a STARVED campaign. Keeps the
D287 failure class permanently lit without a new service.

### 5d. Standing calendar watches (no build; listed so they don't rot)
- Alpha-budget prereg `098ea730d5f2` resolves <= 2026-07-21 (tomorrow) —
  then archive ALPHA_BUDGET_DSR + STALE_VOLUME relays per D295.
- ve v38-vs-v39 funnel read: ~2026-07-21 (their side).
- v39-vs-v40 MR read: ~2026-07-22/23 — retires or re-scopes the
  mr-timer-duration campaign (registry edit + D-entry on the read).
- Their per-name spread-charging word → tier=0 xsect stamping rides a bump
  (D296 standing directive).
- Q52 (integer-contract floor): waits on the operator's reference-NAV
  declaration (their annotation build is gated on it).

## Not in scope
- Off-box DR target: still operator-gated (ops-hardening sprint leftover).
- auto_tune re-arm-or-delete: separate decision, already staged (D295); the
  proposer's two PENDING tighten proposals await operator review in
  OPEN_PROPOSALS.md.
