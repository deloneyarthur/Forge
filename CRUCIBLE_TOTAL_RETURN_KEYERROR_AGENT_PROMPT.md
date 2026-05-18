# Crucible — `KeyError: 'total_return'` in walk_forward + CPCV gates (100% failure rate)

**Audience:** Crucible-side agent.
**Repository:** `/home/aj/proj/Crucible/`.
**Sibling context (read-only):** `/home/aj/proj/Forge/`.
**Operator authorization:** 2026-05-15 — exposed by the post-`0adcfa8` + post-universe-backfill recovery; not introduced by it.

---

## TL;DR

Every Forge run that gets past `trade_count=0` and reaches the walk-forward / CPCV gate evaluator is failing with **`KeyError: 'total_return'`**, in both `walk_forward.py` and `cpcv.py`. This is **not** a regression from your `0adcfa8` work — it's a latent bug that's been masked since Phase 5 because the trade-count cascade rejected runs before they reached walk_forward. Now that universe backfill + 5yr window are restored, walk_forward actually runs — and fails 100% of the time.

## 1. The pattern

Out of 23 re-queued runs from batch `550e24a2` that completed post-universe-backfill (between 22:47 and 23:16 PT 2026-05-15):

```
23 "event": "runner_start"
22 "event": "runner_done"        ← 1 in flight at sample time
23 "event": "walk_forward_failed"  extra: {"error": "'total_return'"}
23 "event": "cpcv_failed"          extra: {"error": "'total_return'"}
 0 "event": "walk_forward_done" / "cpcv_done" / equivalent success event
```

Sample line:

```
May 15 22:49:00 crucible-runner: {"event": "walk_forward_failed",
  "extra": {"error": "'total_return'"}, "level": "warning"}
```

The bare-`'total_return'` error string is Python's KeyError repr.

## 2. Root cause site

Both `src/optbt/experiment/walk_forward.py:156` and `src/optbt/experiment/cpcv.py:219` do the same Pareto-front extraction:

```python
def _select_calmar_max(
    trials: list[tuple[Any, dict[str, float]]],
) -> tuple[int, list[int]]:
    points = [(t[1]["total_return"], t[1]["max_drawdown"]) for t in trials]
    pareto_idx = pareto_front(points)
    ...
```

The trials come from `sweep(train_start, train_end)` (`walk_forward.py:100`). The metric dicts in those trials evidently **do not contain `'total_return'`** as a key. `total_return` *is* set in `src/optbt/metrics/core.py:47`, so it's not that the metric doesn't exist anywhere — it's that the sweep's per-trial metric dict (which `_select_calmar_max` consumes) has a different shape than the run-level metrics dict.

## 3. This is latent, not a regression

`git log --oneline src/optbt/experiment/walk_forward.py src/optbt/experiment/cpcv.py src/optbt/metrics/`:

```
27f3a18 phase 5: Optuna NSGA-II sweeper (chunk 7)
add2f1b phase 5: CPCV harness — 45-path combinatorial purged CV (chunk 6)
a10ebbc phase 5: walk-forward harness (chunk 5)
81b6c4b phase 2: metrics + run report (chunk 5)
```

`0adcfa8` did **not** touch these files. The bug is from Phase 5 (the walk-forward / CPCV harness landings). It's been silently failing on every run since Phase 5 because:

- Before `0adcfa8`: every Forge submission failed the prior gate (`min_oos_trade_count`, hardcoded 30 with 90-day window — see your prior response). walk_forward was never reached.
- After `0adcfa8`: per-bucket window + floor restored. walk_forward *can* be reached, but immediately fails.
- After universe backfill + bar backfill: walk_forward actually runs the sweep, then fails on the `_select_calmar_max` key lookup.

`journalctl --user -u crucible-runner.service --since=yesterday | grep '"event": "walk_forward_'`:

```
23 walk_forward_failed
 0 walk_forward_done / walk_forward_succeeded
```

No walk_forward run has ever produced a success event in the visible journal window.

## 4. Questions to answer

1. **Shape mismatch source**: Does `sweep()` produce metric dicts with a different schema than `compute_run_metrics()` (the function that calls `core.py:47`'s `"total_return"` setter)? Cite the sweep's metric-emission site.

2. **Intended semantics**: Is `_select_calmar_max` supposed to operate on (`total_return`, `max_drawdown`) per §8.2.1, or has the spec drifted such that `cagr` is the canonical first axis? `cagr` *is* present in the trial dicts (used at `walk_forward.py:159`: `m["cagr"] / dd`).

3. **Fix shape**: Which is right?
   - (a) Add `'total_return'` to the sweep's trial-metric dict (single-point fix in sweep; spec-true).
   - (b) Change `_select_calmar_max` to compute `total_return` from `cagr` and the period length (already in scope), or to use `cagr` directly as the first Pareto axis. Requires deciding whether this changes the selection semantics from §8.2.1.
   - (c) Something else from the diagnosis.

4. **Test gap**: This bug appears not covered by any `tests/` since it's 100% reproducible and would fire on any synthetic run that reaches walk_forward. Confirm there is no test exercising the integrated walk_forward → `_select_calmar_max` path on a non-empty trials list. (A `tests/invariants/` test enforcing "every walk_forward run produces *either* walk_forward_done *or* a typed-failure event" would have caught this from day one.)

## 5. What you should NOT do

- **Do not lower or relax** the walk_forward / CPCV gate thresholds (`walk_forward_sharpe_median`, `cpcv_sharpe_p25`). They're correct; the gate has no data to score on because the harness fails before computing.
- **Do not silently swallow the KeyError** in production. The current `warning`-level logging is honest. If anything, the warning level is too low for a 100% failure rate — bump to `error` so it's surfaced in any future dashboards.
- **Do not change Forge code.** Forge has no role in walk_forward / CPCV.
- **Do not skip the test-first discipline.** Whatever the fix shape, add the invariant test that catches this class of "harness-runs-but-keys-don't-line-up" failure.

## 6. Background data sources

- Runner journal (full sample): `journalctl --user -u crucible-runner.service --since=22:47 --no-pager`
- Sample line above
- Code refs cited:
  - `src/optbt/experiment/walk_forward.py:156` — failing key access
  - `src/optbt/experiment/cpcv.py:219` — failing key access (duplicate impl)
  - `src/optbt/metrics/core.py:47` — where `total_return` is canonically set
  - `src/optbt/experiment/sweeper.py:35` — `DEFAULT_OBJECTIVES = ("total_return", "max_drawdown")` — hints at original intent

## 7. Output expected

Report back with:
1. Definitive answer to Q1-Q2 (cite file:line, list the sweep's metric-emission site)
2. Recommended fix (a/b/c from §4)
3. If the fix is your work: ship it + the invariant test (TDD red→green order) + a Decision Log entry citing this prompt
4. If the fix needs operator approval (semantics change in `_select_calmar_max` Pareto axes): surface the trade-off and stop

Brief is OK. Aim for under 500 words of report unless the investigation reveals something material.
