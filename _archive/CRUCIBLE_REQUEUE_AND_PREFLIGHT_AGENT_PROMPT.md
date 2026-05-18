# Crucible — re-queue plan + preflight guard sign-off

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-15 — Forge operator, post-backfill recovery.
**Status:** Two-part: (1) FYI on how Forge is handling the 125-config recovery, (2) sign-off for your proposed queue-time preflight guard.

---

## 1. The re-queue: Forge is handling it; no Crucible code needed

Your fix shipped universe data; the 125 already-submitted configs from batch `550e24a2-f37c-4870-8722-06970a91e7a3` are now `runner_failed` and won't auto-retry. We've confirmed two relevant facts:

- The original config JSONs are retained in `~/optbt_data/inbox/processed/{config_hash}.json` (3820 files there at last count).
- The inbox-watcher's queue path is unique on (`run_id` UUID PK), **not** on `config_hash` — so re-dropping the same JSON into `inbox/` produces a new run row with the same hash, which is the desired idempotent-from-Crucible's-side recovery.

**Forge plan:** a one-off script that reads the 125 `config_hash`es from Forge's `submissions` table (where `forge_batch_id = '550e24a2-…'`) and copies the JSONs from `inbox/processed/` back to `inbox/` (atomic tmp-then-rename). No `submissions` table mutation — preserves Forge's hard rule #9 (`config_hash` unique on Forge side; the table records what Forge has *emitted*, not what's currently in-flight).

You don't need to do anything for the recovery. Once the runs re-ingest, they'll hit the gate evaluator with the new 5yr universe data, produce `promotion_decision` rows, and Forge's rate-limiter will see them via `get_recent_gated_runs`. The deadlock on batch `550e24a2` resolves on its own.

**Confirm if you see a problem with this** — particularly any state-machine concern in `runs` where a new run with a config_hash that already has a terminal-failed predecessor confuses analytics or downstream gates. If you don't reply, we proceed.

## 2. Preflight guard: ship it

Re your proposed queue-time preflight in `scripts/ingest_inbox_run.py` / `runs_repository.queue_run`:

> A queue-time preflight in `scripts/ingest_inbox_run.py` / `runs_repository.queue_run` that checks `Universe(...).tickers(period_start, tier)` before persisting the run, so this class of regression fails loudly at submission rather than at the runner — pending operator sign-off…

**Approved from Forge's perspective.** Reasoning:

- Failing at queue time rather than runner time is materially better for Forge: the run never reaches `runs` as a terminal-failed row, the failure is visible in the inbox-watcher's own log (instead of buried in runner output), and (most importantly) the rate-limiter doesn't enter the deadlock we hit today.
- Universe coverage is a Crucible-data invariant, not a Forge concern — making it explicit at the boundary aligns with §13.5 contracts-version checking principles already shipped.
- Per CLAUDE.md TDD discipline: yes, write the `tests/invariants/` test first. The test should construct a `StrategyConfig` whose `period_start` predates the earliest universe snapshot, attempt `queue_run`, and assert the failure is loud + early (specific exception class, no `runs` row inserted).
- Decision Log: yes, this warrants a Crucible-side entry citing this prompt + `CRUCIBLE_UNIVERSE_BACKFILL_AGENT_RESPONSE.md`. The class of failure is "structural data gap that the gate's structural validity assumed away" — worth recording so the next agent doesn't wonder why the guard exists.

Suggested name for the exception (your call): `UniverseCoverageInsufficient` or similar — distinct from generic `IOError`-style failures so callers can branch on it specifically.

## 3. What you should NOT do

- **Do not auto-retry runner_failed runs** as part of this work. That's a separate decision (auto-retry policy is a §13 invariant change). For today, manual re-queue (the script above) is fine.
- **Do not change Forge code.**
- **Do not skip the test-first discipline** for the preflight guard — even though the change feels mechanical, it's enforcing an invariant and belongs in `tests/invariants/`.

## 4. Output expected

1. Brief acknowledgment (or pushback) on the §1 re-queue plan — under 100 words.
2. Confirmation when the preflight guard ships, with the Decision Log entry reference.

Brevity preferred. Aim for under 300 words of report.
