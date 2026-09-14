# Pipeline-performance audit — 2026-07-01

Runtime-performance audit of the Forge daemon's production loop (enumerate → prefilter →
rank → submit → feedback), written as a durable record so a later agent (e.g. Opus) can
execute the workplan without re-deriving the findings. Snapshot: HEAD `ceeefa4` plus the
uncommitted D216 working-tree changes — same snapshot as the sibling audits.

Method: five parallel subsystem audits (prefetch/battery, submit/persistence,
feedback/reconcile, run-loop orchestration, enumeration/ranking/trainer), grounded in
live journal `phase_timings`, systemd accounting, `strace`, and write-pattern replays
against a scratchpad **copy** of forge.db at production scale. Read-only — nothing was
changed, no service action taken.

## Files

| File | What |
|---|---|
| `00-BASELINE.md` | Measured ground truth (timings, anatomy of an iteration, DB/table stats, benchmarks) + how to re-measure. Compare against this after every fix. |
| `FINDINGS.md` | All findings F1–F23 with evidence (file:line), mechanism, measured impact. |
| `WORKPLAN.md` | Executable items P0-1 … P4, each self-contained: fix spec, rejected alternatives, required tests, verification. |

## The headline

The daemon burns **~12.6 CPU-h/day; ~11 h/day is avoidable overhead**, on a 64-core box
**shared with Crucible's gating compute** — the pipeline's actual bottleneck, so Forge
waste taxes it directly. One root cause dominates: **duckdb-python `executemany`
autocommits and WAL-fsyncs every row** (strace: 1,003 fsyncs per 1,000-row insert).
It is ~190s of the 197s submit phase (F1) and ~20s of the 31s reconcile phase (F2).
Verified fixes take submit → ~6s and reconcile → ~3s, a full cycle from ~8 min to
~4.5 min, and remove ~3.4M fsyncs/day of NVMe wear.

**Framing — do not oversell:** submission throughput is intentionally §7.3-bounded
(Crucible's gating is the binding constraint; the daemon spends most iterations blocked
on the depth cap). These fixes do NOT buy more submissions. They buy: CPU/IO returned to
Crucible, ~2× feedback cadence, disk-wear elimination, bounded DB/backup growth, and
headroom to raise poll/batch if the operator ever wants to.

## Recommended sequence

1. **P3-1** (add `weights=` phase-timings bucket) — ~30 min; makes every later fix
   journal-verifiable and surfaces the currently-invisible ~28s stanza (F6).
2. **P0-2 then P0-3** (separate commits, same reconcile path) — the per-iteration tax,
   paid by all 373 blocked iterations/day too.
3. **P0-1** — the submit phase.
4. **P1-1** — parse-once (feedback-change ritual).
5. **P2-2 → P2-3 → P2-4**; draft the **P2-1** Crucible relay early (cross-repo latency).
6. **P1-2** when the operator is available for the retention decision.

## Rules of engagement (binding on every item)

- **This working tree IS production** (`forge.service`, editable install). Changes land
  only via `docs/tasks/deploy.md`: stop service → full uncontended suite → commit →
  restart → journal-verify. One small commit per item (one module + tests). Each
  increment gets a D-entry in `IMPLEMENTATION_DECISIONS.md` + a `STATUS.md` block.
- **TDD first** (CLAUDE.md): failing test before production code; invariant-class
  behavior gets its test in `tests/invariants/`. Then `uv run ruff check src tests
  scripts`, `ruff format` on changed files ONLY (tree is not format-clean),
  `uv run mypy --strict src`, scoped pytest.
- **Hard rule #6 (determinism):** same `(grammar_version, registry_hash, seed)` →
  byte-identical enumeration. P0 items are persistence-only (trivially safe); P2-3 and
  P2-4 must ship with the equivalence tests specified in their workplan entries.
- **Hard rule #2:** cross-system access only via `crucible_contracts`. P2-1 is a relay
  ask to Crucible, never a workaround. Never import Crucible internals.
- **Hard rule #8:** only `forge.core.clock.utc_now()` and `forge.core.seed.SeedHierarchy`.
- **Hard rule #9 / §13.4:** submission idempotency (unique `config_hash` index) must
  survive every submit-path edit untouched.
- **`forge.cli.main` seams:** ~10 test files monkeypatch its internals (D065/D105/D106);
  the structure is deliberate. Extend with optional kwargs/helpers; never rename or
  restructure the `_load_*`, `_build_feature_cache`, `_reconcile_pending_silently`,
  `submit_batch` seams.
- **§7.3 semantics are spec'd** (three block reasons — DESIGN §7.3, D137, D196). Making
  the check cheaper is fine; changing when it blocks is not. **Never skip reconcile while
  blocked**: the depth cap counts DB `submitted` rows and reconcile is what flips them to
  `gated` — skipping would wedge the limiter permanently. Make reconcile cheap instead
  (P0-2/P0-3).
- Live `~/forge_data/forge.db` holds an RW lock — never open directly; `cp` to /tmp and
  query the copy (`docs/tasks/investigate-live.md`).
- Line numbers are as of 2026-07-01 on the `ceeefa4`+D216 tree; if drifted, grep the
  quoted symbol names.

## Already good — do NOT "fix" (verified, with the reason)

- **Batched prefetch (D033)** and the **2-request-per-underlying split** — the split is
  load-bearing: merging returns+regime into per-feature requests would echo the full
  ~2,134-entry maps once per signal (~80× serialization balloon; Forge's client reads
  only the first entry).
- **Crucible's SQLite feature store** — append-immune window tokens; value-series and
  activations persist across days and tail-extend. The expensive surface computes are
  NOT being redone per batch; the waste is elsewhere (F11).
- **Battery ordering** — empirically near-optimal: the costliest filter
  (`permutation_test`, tier 9) is last AND the top rejector (~2.6k/batch); the
  zero-rejection filters cost ≈0 (hash/lookup only).
- **Enumeration** — genuinely lazy, seeded, retry-capped (`EnumerationCapped` at 100×,
  dead-end blacklisting); weight concentration cannot spin it. Grammar load + archive
  byte-compare ≈ ms; registry snapshot is 13.6KB — re-parse is a non-issue.
- **Reconcile's internal D046 snapshot reuse** — parses the export once and threads
  `crucible_runs=` through all per-batch consumes (the exact pattern P1-1 extends).
- **Aged-out flush** — filtered SELECT on a watermark, not a scan (D110 design sound).
- **Learned-weight computes** — set-based and window-bounded (`WHERE … IN (SELECT
  UNNEST(?))`); they do NOT grow with history. Reconcile will not creep after P0.
- **Survivor per-candidate transactions** (M-10) — deliberate crash-atomicity, ~2–3s
  total for 200 candidates. The submit cost is the *rejected-rows* write (F1), not this.
- **Inbox writes** — flat-dir tmp-then-rename, page-cache speed. (Side note: no fsync
  before rename = a durability question owned by contracts/D006, not a perf item.)
- **Backup script design** — validate → atomic publish → prune-only-after-success;
  KEEP=14 rotation works. The problem is the source size (P1-2), not the script.
- **No memory leak** — 3.6G RSS steady over 2.8 days (peak 4.7G, swap ~15MB) is
  allocation churn from F3/F11, not growth.
- **Cold start** ≈ one normal iteration (~8 min); deploy downtime is dominated by the
  test-suite ritual, not process startup.
