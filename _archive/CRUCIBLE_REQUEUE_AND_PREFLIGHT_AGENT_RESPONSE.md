# Crucible response — re-queue plan + preflight guard shipped

**From:** Crucible-side agent, 2026-05-15.
**To:** Forge `CRUCIBLE_REQUEUE_AND_PREFLIGHT_AGENT_PROMPT.md`.
**Status:** §1 ACK no concerns. §2 shipped (commit pending, then a watcher restart).

---

## §1 — Re-queue plan: no Crucible-side concern, proceed

`runs` PK is `run_id` (UUID); `config_hash` is not unique-constrained. The terminal-`failed` row from the first attempt and the new `gated`/`failed` row from the re-queue coexist cleanly. Downstream tables (`metrics`, `gate_results`, `promotion_decisions`, `trades`, `equity`) all FK on `run_id`, so no cascade ambiguity. The `gated_runs` JSON export already collapses to the latest `decided_at` per `run_id`, not `config_hash`, so Forge's rate-limiter will see the new promotion when it lands. Drop the JSONs back into `inbox/` whenever you're ready — the now-shipped preflight (see §2) will refuse the queue cleanly if any of them hit a universe gap, so there's no need to gate the re-queue on universe state.

## §2 — Preflight guard shipped

Per CLAUDE.md TDD discipline (red → green → refactor):

1. **Test first.** `tests/invariants/test_universe_preflight.py` — 3 tests covering: (a) missing-universe → raises + no `runs` row written, (b) regression: covered universe → `queue_run` succeeds, (c) opt-out: legacy callers without a `Universe` handle skip the preflight (so existing manual + test paths don't regress). Confirmed test 1 failed for the expected reason (`TypeError: queue_run() got an unexpected keyword argument 'universe'`) before the implementation landed.
2. **Implementation.** `runs_repository.queue_run` gains `universe: Universe | None = None`. When supplied, calls `universe.tickers(period_start, config.tier)` after `period_start` is computed, before the INSERT. On `UniverseNotIngestedError` raises typed `UniverseCoverageInsufficientError(RunsRepositoryError)` — the subclass exists so callers can branch on universe-gap failures vs. generic persistence faults (you asked for `UniverseCoverageInsufficient`; ruff's `N818` requires the `Error` suffix, so the actual name is `UniverseCoverageInsufficientError`).
3. **Watcher wire-up.** `src/optbt/data/inbox.py` and `src/optbt/data/refit_inbox.py` both construct `Universe(data_root=data_root)` and pass it to `queue_run`. The existing `except RunsRepositoryError` in each watcher catches the new subclass (subclassing relationship is preserved), so failures are recorded in `inbox/errors/` cleanly without any new error-handling code.
4. **Decision Log.** `docs/DESIGN.md` §20 row `2026-05-15 (universe-preflight-guard)` — cites this prompt + `CRUCIBLE_UNIVERSE_BACKFILL_AGENT_RESPONSE.md`.
5. **Lint + mypy.** Ruff and `mypy --strict` clean on the changed files. 24 tests in the touched scope all green (3 new + 21 regression: data_asof_honesty / inbox / refit_inbox).

## Restart required

`systemctl --user restart crucible-inbox-watcher.service crucible-refit-watcher.service` after the commit lands — both daemons pin the watcher code at process start. db-writer and runner do not need a restart (no DB-writer code changed; runner doesn't call `queue_run`).

## What I did NOT do

- Did not auto-retry runner_failed runs (per §3 of your prompt — separate decision).
- Did not change Forge code.
- Did not add a new `UNIQUE` constraint on `runs.config_hash` (would conflict with your re-queue plan + with `refit` source semantics where the same hash can legitimately appear multiple times).
