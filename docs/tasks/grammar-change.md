# Task: change the grammar / enumeration policy

Scope: any change to what Forge enumerates. Classification first — it determines the ritual
(`docs/architecture.md` change taxonomy).

> **The grammar is FROZEN at v55 (D390). Step 0: `forge prereg register` with a required n; the
> `freeze-governance` pre-commit hook refuses a `grammar.yaml` content change without an open
> prereg (`FORGE_FREEZE_REOPENER=D###` for a §5 reopener, with that D-entry staged).**

## Classify the change

1. **`rules:` text change** — the 21 §3.5 rules are operator-owned (hard rule #1). Needs explicit
   operator approval. If a rule looks wrong, log to `OPEN_QUESTIONS.md` — never silently change.
2. **Enumeration-policy bump** (the norm since v5) — Python-side change that alters the emitted
   population (sampler constants, predicate pools, threshold/horizon tables, parameter bounds).
   Still bumps `grammar_version` for cohort attribution; `rules:` text untouched.
3. **Loosening** (widens the space) — an operator commit behind a preregistration like any other
   grammar change (hard rule #4); nothing auto-applies in either direction, and `OPEN_PROPOSALS.md`
   is a static record with no writer (D420).
4. Selection-policy change (which cells a run targets, budgets, the challenger gate) → not a
   grammar change: ordinary code in `src/forge/campaign/`, TDD + full suite + `deploy.md`. The
   population must stay byte-identical (the sampler goldens + `test_campaign_invariants`).

## Steps

1. Re-read `docs/DESIGN.md` §3 + the relevant `docs/GRAMMAR.md` section; check hard rules #1, #3,
   #4, #6, #7.
2. Build in a worktree (`deploy.md`), not the live tree — the timer fires onto whatever this tree
   contains.
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
9. Run an emission proof (recipe below). Quick smoke: `uv run forge enumerate --max 50 --summary`.
10. Deploy (`deploy.md`). The next run records the `manual_bump` row in `grammar_versions` when it
    first loads the new version (`grammar/version_audit.py`) — do not insert one by hand.
11. Relay the new version string + the first live run's instant to Crucible (`crucible-handoff.md`)
    for `crucible funnel --compare v{N-1} v{N}`.

## Adding a new indicator (checklist)

Crucible's registry must advertise it first (contracts gap otherwise). Then Forge-side:
`indicator_thresholds.py` (real-data threshold ranges — distributions in
`src/forge/enumeration/indicator_thresholds.py` — the code is the truth), `signal_horizon.py` (horizon table), sampler regime pools
(`_build_regime_pool`) and R-rule predicate eligibility if it can serve as a regime gate.

**Then verify layer 3 — the writer actually COMPUTES it (mandatory for a new DIRECTIONAL):**
registered + enumerable is NOT sufficient. `sma_slope`/`ad_slope` cleared both but Crucible's
feature-cache writer returned 0 activations for every name, so they zero-traded silently — 0/2800
submitted for ~5h post-deploy (D254). The `forge check-activations` probe left with the daemon
(Batch 5 G1): ask Crucible to probe the writer for the new id in the relay that announces the bump
(`crucible-handoff.md`) BEFORE the first live run, and read that run's `gated_out` / funnel
`rejection_breakdown` afterwards — the `predicted_activations` prefilter rejecting every carrier is
the same INERT verdict, one week late. An inert directional is a **NO-GO**; don't ship it.

## Emission proof (recipe)

`load_registry()` reads the newest live export when one exists (demo fallback otherwise; the
CLI's `(demo registry)` output suffix is a stale label — trust `registry_hash`). Sample the cold
mix; swap the `Counter` key for the field your change targets:

```bash
uv run python - <<'EOF'
from forge.core.logging import configure_logging
configure_logging(level="WARNING")   # sampler rejections flood at debug otherwise
from collections import Counter
from pathlib import Path
from forge.enumeration import enumerate_candidates
from forge.grammar import load_grammar
from forge.persistence.registry_loader import load_registry

grammar = load_grammar(Path("config/grammar.yaml"), archive_dir=Path("config/grammar_archive"))
registry = load_registry()
mix = Counter(c.hypothesis for c in enumerate_candidates(grammar, registry, seed=0, max_candidates=3000))
print(mix.most_common())
EOF
```

A hypothesis at zero that shouldn't be usually means the live registry disagrees with what the
change assumed — e.g. an indicator family Crucible hasn't republished yet (Q30): the §3.5 C1
different-family pairing check then rejects every draw structurally.

## Gotchas

- ANY byte change to `grammar.yaml` — comments included — trips the version-bump hook and the
  loader's archive check. There is no "small comment fix" without a bump.
- Never propose anything that lowers Crucible's promotion gate (hard rule #3) — loosenings are
  about enumeration scope only.
- The grammar must not permit `equity` as a signal family (hard rule #7; §13.6).

## Verify

```bash
uv run pytest tests/unit/test_grammar tests/unit/test_enumeration tests/invariants
# pre-commit takes ONE hook id per run (two ids in one call is a usage error):
uv run pre-commit run grammar-version-bump --all-files
uv run pre-commit run grammar-doc-sync --all-files
# layer-3 (D254): a newly-adopted directional must fire on the live writer — Crucible probes it (relay); see above
```
