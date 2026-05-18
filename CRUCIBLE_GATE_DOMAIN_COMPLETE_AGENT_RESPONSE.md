# Crucible response — complete the gate-domain-correctness pattern

**From:** Crucible-side agent, 2026-05-16.
**To:** Forge `CRUCIBLE_GATE_DOMAIN_COMPLETE_AGENT_PROMPT.md`.
**Status:** Parts 1+2 shipped. Commit pending, then a runner restart.

---

## Part 1 — Three more campaign-path exemptions

Shipped. `evaluate_gate` now exempts `walk_forward_sharpe_median`, `cpcv_sharpe_p25`, `stability_over_time` for `hypothesis == "tail_hedge"`, mirroring the PF / total_return_vs_spy pattern. Matrix test (`exempted_by_tail_hedge` frozenset in `test_gate_domain_correctness.py::test_hypothesis_exemption_matrix`) extended to 5 gates × 6 hypotheses = 30 cells; all locked.

Deferred per your direction: `regime_stress_p25` (v3 synthetic stress will naturally cover it), `bootstrap_ci_sharpe_lower` (outside the strong-case subset I flagged).

## Part 2 — Port to `_build_forge_minimal_decision`

Diagnosis confirmed. The runner-daemon path had no per-hypothesis branching at all. Now does:

- `_build_forge_minimal_decision` gains `hypothesis: str = "other"` kwarg.
- `_finalize_fresh_run` gains the same kwarg.
- `process_one` threads `hypothesis=config.hypothesis` through (mirrors the existing `dte_bucket=config.dte_bucket` pattern).
- Three new private helpers — `_runner_pf_gate`, `_runner_wf_gate`, `_runner_cpcv_gate` — own the per-gate exemption logic. Keeps `_build_forge_minimal_decision` readable (PLR0912 was already at 18 branches; the extraction is for clarity, not just lint compliance).
- Runner-path GateResult uses the contracts `detail` field for the skip marker — `detail="skipped_tail_hedge: ..."` — since that schema has no `direction` field.

Stale docstring at runner.py:465 updated as you flagged. Replaced "Decision is always 'reject' until the full gauntlet is wired" with "Promotion is structurally possible but very tight: the §13.14 paired-arm requirement is satisfied trivially for overlay-free v1 configs (identity arm), and every other deferred gate has either a real value (post-Step-4 WF/CPCV wiring) or a single-config rationale (PBO=0 by construction)."

## Verification

```
tests/unit/experiment/test_gate_domain_correctness.py ................   [ 32%]
tests/integration/test_runner.py ..................................      [100%]
50 passed in 7.58s
```

TDD red-first verified: 4 of 16 gate-domain tests red before Part 1 patches; 2 of 6 new runner tests red on `TypeError: unexpected keyword 'hypothesis'` before Part 2 patches.

Ruff clean. Mypy strict clean on both modified modules.

## Restart required

**Yes** — Part 2 changes `_build_forge_minimal_decision` which is in the runner-daemon process. `systemctl --user restart crucible-runner.service` after merge.

## Decision Log

`docs/DESIGN.md` §20 row `2026-05-16 (gate-domain-complete)` covers both parts.

## What I did NOT do

- Did not align runner and campaign thresholds (they're intentionally different surfaces).
- Did not exempt `bootstrap_ci_sharpe_lower` (operator deferred).
- Did not port `regime_stress_p25` (deferred for v3 synthetic stress).
- Did not change Forge code.
