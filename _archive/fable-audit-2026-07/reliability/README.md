# Fable audit — reliability: swallowed errors, races, crash-atomicity, resource leaks (2026-07-06)

Full-repo reliability audit of Forge, performed 2026-07-06 by Claude Fable 5. Scope, as
requested by the operator: (a) race conditions, unhandled-async-failure analogues, and
resource leaks (unclosed connections, listeners, file handles); (b) every place errors are
swallowed, ignored, or logged-without-handling — ranked by blast radius. This folder is the
durable record, written so a later agent can execute fixes without re-deriving the findings.

## Contents

| File | Purpose |
|---|---|
| `README.md` | This file: verdict, method, snapshot, rules of engagement. |
| `FINDINGS.md` | Complete findings ranked by priority (P0–P3), with file:line evidence, failure scenarios, blast radius, confidence, and fix sketches; plus the verified-healthy list and coverage inventory. |

## Snapshot the audit was taken against

- Date: 2026-07-06. HEAD = `5ac7941` ("docs(audit): conditional code-complete retirement
  plan"). Working tree clean except one untracked file (`PROMPT_PROMOTION_STRATEGY_HANDOFF.md`).
  All file:line references are against this tree. NOTE: the four 2026-07-01 sibling tracks
  reference the older `ceeefa4` snapshot — line numbers are NOT interchangeable across tracks.
- No code, config, or service state was modified by this audit. Read-only throughout.

## Method

Four parallel deep-dive subagent sweeps, each finding independently spot-verified against
source by the orchestrating session before inclusion:

1. Error-swallowing, production loop (`cli/`, `submission/`, `feedback/`, `funnel/`) —
   46/46 except clauses read in full context.
2. Error-swallowing, support code (`core/`, `config/`, `enumeration/`, `grammar/`,
   `persistence/`, `prefilters/`, `ranking/`, `scripts/*.py`) — 22/22 except clauses.
3. Resource leaks (DB connections, file handles, sockets, subprocess, tmp files,
   unbounded daemon-loop state) — full call-site inventories in FINDINGS.md appendix.
4. Races / TOCTOU / crash-atomicity (file IPC with Crucible, DuckDB cross-process locking,
   hot-reload timing, SIGTERM tearing, systemd unit overlap) — including reads of the
   Crucible-side inbox watcher and `crucible_contracts` writers to trace both ends.

Note on scope translation: Forge has **no threading and no asyncio** — the
"unhandled promise rejection" class does not exist here. Its analogues (ignored subprocess
results, fire-and-forget writes, torn multi-step operations) were audited instead; all
subprocess use is `subprocess.run` with timeouts and checked return codes (clean).

## Overall verdict

**No data-corrupting defect found in the steady state; the debt is concentrated in one
systemic blind spot plus crash-path holes.**

1. **P0 — the export-outage blind spot.** Every consumer of Crucible's file exports degrades
   silently or warn-once on `QueryError`. The two that gate submission flow
   (`_reconcile_pending_silently`, the §7.3 rate limiter) are FULLY silent, and their failure
   mode renders as the `blocked: … N% gated` line that CLAUDE.md trains operators to treat as
   benign backpressure. This is structurally the same wedge as the D205/D240/D245 multi-day
   stall incidents. The rate-limiter swallow additionally disables the D137 stall guard and
   D196 depth guard — the guards built after the previous incidents.
2. **P1 — crash/kill tearing.** No SIGTERM handler anywhere + the submit write order
   (inbox rename visible to Crucible BEFORE the DB transaction commits) means every routine
   `systemctl stop` has a window that orphans a candidate at Crucible (lost verdict, possible
   duplicate run). No startup sweep reconciles the inbox against `submissions`.
3. **P2/P3 — leaks and slow burns.** The daemon's open-use-close discipline is genuinely
   good (all ~40 DB opens `with`-managed; no fd/handler accumulation). Residuals: an
   exception-path connection leak in the sanctioned `open_db`, a per-iteration Unix-socket
   client released only by GC, 5.5 GB tmpfs snapshot orphans on OOM-kill, and several
   unbounded-growth patterns.

Hard-rule tension: CLAUDE.md rule that `QueryError` is never silently caught outside test
fixtures is violated at 2 fully-silent sites and diluted at ~12 warn-once/silent-sibling
sites; `ConfigInvalid` is conflated into an anonymous failure count in the submitter.
Zero catches of `SchemaVersionMismatch` anywhere (the loop explicitly re-raises it) — clean.

## Rules of engagement for the agent that picks this up

1. **This working tree IS production** — `forge.service` runs from it via editable install;
   a reboot auto-starts onto whatever the tree contains (D104). Deploys follow
   `docs/tasks/deploy.md` (stop → full uncontended suite → commit → restart → verify journal).
   Never restart the service casually.
2. Several flagged behaviors are **deliberate, documented, and test-pinned** (each finding
   says so): fixes must preserve the documented posture (e.g., shadow scoring never raises;
   the universe fallback direction; conservative rate-limiter blocking) while adding the
   missing alarm path. Do not "fix" the degrade direction itself without an operator gate.
3. TDD per CLAUDE.md: failure-mode tests in `tests/invariants/` BEFORE production code for
   anything touching hard-rule behavior. `ruff format` only on changed files.
4. Overlap with sibling tracks: REL-12/REL-18 growth+re-parse items overlap
   `pipeline-performance` (P1-1 parse-once) and `codebase-quality` (SRC-M1 nine loaders);
   land shared items once and tick them in every plan.
