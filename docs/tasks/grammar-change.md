# Task: change the grammar / enumeration policy

Scope: any change to what Forge enumerates. Classification first — it determines the ritual
(`docs/architecture.md` change taxonomy).

## Classify the change

1. **`rules:` text change** — the 21 §3.5 rules are operator-owned (hard rule #1). Needs explicit
   operator approval. If a rule looks wrong, log to `OPEN_QUESTIONS.md` — never silently change.
2. **Enumeration-policy bump** (the norm since v5) — Python-side change that alters the emitted
   population (sampler constants, predicate pools, threshold/horizon tables, parameter bounds).
   Still bumps `grammar_version` for cohort attribution; `rules:` text untouched.
3. **Loosening** (widens the space based on feedback) — NEVER auto-applied: write to
   `OPEN_PROPOSALS.md` and wait for the operator (hard rule #4). Tightenings may auto-apply.
4. Pure draw-distribution change → not a grammar change; see `feedback-change.md`.

## Steps

1. Re-read `docs/DESIGN.md` §3 + the relevant `docs/GRAMMAR.md` section; check hard rules #1, #3,
   #4, #6, #7.
2. If `forge.service` is running, build in a worktree (`deploy.md`), not the live tree.
3. TDD: failing tests first — `tests/unit/test_grammar/` or `test_enumeration/`; hard-rule-adjacent
   behavior gets a `tests/invariants/` test. Golden sampler-sequence assertions may need deliberate
   re-pinning — never casual edits.
4. Implement. Usual loci: `enumeration/sampler.py` (draw policy, regime pools),
   `enumeration/indicator_thresholds.py` (threshold table), `grammar/signal_horizon.py` (horizon
   table), `grammar/custom_predicates.py` (e.g. S5 exit schema), `enumeration/search_space.py`.
5. Version bump in `config/grammar.yaml`: edit `grammar_version: v{N}` (mid-file —
   `grep -n '^grammar_version'`) and append a version-history note to the header comment. Then
   `cp config/grammar.yaml config/grammar_archive/v{N}.yaml` — the loader requires the archive copy
   of the CURRENT version byte-identical at startup; `v{N-1}.yaml` already exists from its own bump.
6. If rule ids changed: `docs/GRAMMAR.md` headings must match (doc-sync hook).
7. Append the D-entry to `IMPLEMENTATION_DECISIONS.md`; update `STATUS.md`.
8. Gates + commit (`quality-gates.md`) — both grammar pre-commit hooks fire on grammar paths.
9. Run an emission proof (sample a few thousand configs against the live registry export; verify
   the intended mix shift). Quick demo-registry check: `uv run forge enumerate --max 50 --summary`.
10. Deploy (`deploy.md`). The service records the `manual_bump` row in `grammar_versions` at
    startup — do not insert one by hand.
11. Relay the new version string + deploy timestamp to Crucible (`crucible-handoff.md`) for
    `crucible funnel --compare v{N-1} v{N}`.

## Adding a new indicator (checklist)

Crucible's registry must advertise it first (contracts gap otherwise). Then Forge-side:
`indicator_thresholds.py` (real-data threshold ranges — distributions in
`docs/INDICATOR_THRESHOLDS.md`), `signal_horizon.py` (horizon table), sampler regime pools
(`_build_regime_pool`) and R-rule predicate eligibility if it can serve as a regime gate.

## Gotchas

- ANY byte change to `grammar.yaml` — comments included — trips the version-bump hook and the
  loader's archive check. There is no "small comment fix" without a bump.
- Never propose anything that lowers Crucible's promotion gate (hard rule #3) — loosenings are
  about enumeration scope only.
- The grammar must not permit `equity` as a signal family (hard rule #7; §13.6).

## Verify

```bash
uv run pytest tests/unit/test_grammar tests/unit/test_enumeration tests/invariants
uv run pre-commit run grammar-version-bump grammar-doc-sync --all-files
```
