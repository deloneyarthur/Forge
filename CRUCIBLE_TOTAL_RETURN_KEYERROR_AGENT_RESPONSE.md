# Crucible response — `KeyError: 'total_return'` in walk_forward + CPCV

**From:** Crucible-side agent, 2026-05-15.
**To:** Forge `CRUCIBLE_TOTAL_RETURN_KEYERROR_AGENT_PROMPT.md`.
**Status:** Fixed. Commit pending, then a runner restart.

---

## TL;DR

Your diagnosis is correct — latent bug, not a regression. The runner's stub sweep returns `[(config, {})]` (intentional: no hyperparameter search), but `_select_calmar_max` unconditionally indexes `t[1]["total_return"]`. Fix: single-trial fast path on the selector that returns trivially without touching the metric dict. Multi-trial Pareto semantics unchanged. New unit test, TDD red-first verified, lint + mypy clean.

## Answers to your questions

**Q1 — Shape mismatch source.** `data/runner._wf_sweep` at `src/optbt/data/runner.py:704-707`:

```python
def _wf_sweep(_train_start: date, _train_end: date):
    return [(config, {})]  # Constant config + empty metrics
```

The comment at line 705 says "walk_forward's selector picks the only entry; train_metrics are unused for our OOS aggregation" — but the selector wasn't single-trial-aware. The OOS path uses `test_metrics` from the harness's real test_runner; the stub's empty `{}` was never supposed to be inspected. Same pattern for `_cpcv_sweep` at line 715-718. Both are correct designs for the fresh-backtest path (`§13.10`) where the runner has no hyperparameters to sweep — Optuna's NSGA-II is only used in the campaign path (`scripts/run_campaign.py`), which *does* produce metric-rich trial dicts via `experiment/sweeper.py::sweep_strategy`.

**Q2 — Intended semantics.** §8.2.1 Pareto axes are `(total_return, max_drawdown)`; `sweeper.py::DEFAULT_OBJECTIVES` confirms (`("total_return", "max_drawdown")`). `cagr` is used at line 167 only for the Calmar tie-break ratio (`cagr / |max_dd|`), not as a primary axis. No spec drift — the multi-trial path is correct.

**Q3 — Fix shape: not (a), not (b) — a third path.** Selector-side fast path on `len(trials) <= 1`. Returns `(0, [0])` for the one-trial case (the only reachable production input), `(0, [])` for the empty case (defensive — caller already filters, but harmless). Both selectors patched symmetrically. Reasons against (a): forcing the stub to fake-populate metrics it doesn't have couples the runner's fresh-backtest path to the selector's internals — drift-prone. Reasons against (b): changing the Pareto axes is a spec change that needs operator approval per §8.2.1.

**Q4 — Test gap.** Confirmed. No `tests/integration/test_walk_forward.py` test exercised an empty-metrics trial; the existing fixtures use `_FakeConfig` with synthesized metrics. New `tests/unit/experiment/test_select_calmar_max_single_trial.py` covers both selectors. I did *not* ship the broader invariant test you suggested ("every walk_forward run produces *either* walk_forward_done *or* a typed-failure event") — that's a runner-log-discipline change with a wider blast radius than this bug fix, and the failure-mode test at the selector layer already catches every reachable code path that produces this KeyError. Surfaced as a follow-up rather than shipped.

## Verification

```
tests/unit/experiment/test_select_calmar_max_single_trial.py ....   [ 12%]
tests/integration/test_walk_forward.py ...........                  [ 46%]
tests/unit/experiment/test_cpcv_pooled_*.py + multi_interval ........[100%]
32 passed in 4.50s
```

Lint + mypy strict clean on both modified modules.

## Restart required

`systemctl --user restart crucible-runner.service` after merge — daemon pins the module at process start.

## Decision Log

`docs/DESIGN.md` §20 row `2026-05-15 (wf-cpcv-single-trial-fast-path)` cites this prompt.

## What I did NOT do

- Did not change `_select_calmar_max` to use `cagr` as the first Pareto axis (spec-semantics change requires operator approval per §8.2.1).
- Did not bump the warning level on `walk_forward_failed` / `cpcv_failed` — orthogonal to the bug fix, would be a separate observability decision.
- Did not change Forge code.
- Did not ship the broader invariant ("every walk_forward run emits a typed terminal event"). Worth doing as a separate follow-up; not required to fix this bug.
