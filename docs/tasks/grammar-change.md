# Task: change the grammar / enumeration policy

Scope: any change to what Forge enumerates. Classification first — it determines the ritual
(`docs/architecture.md` change taxonomy).

> **Pending metadata fixes to piggyback on the next bump** — these don't change enumeration, so
> do NOT bump *for* them; fold them into the next real change so the byte edit rides an
> already-needed version increment:
> - **Q49 rv_rank/iv_rank semantic relabel** (2026-07-13): both kernels compute a min-max
>   RANGE-POSITION, not a percentile rank (verified in `crucible_engine_core` rv_rank.py;
>   Crucible capitulation follow-up §3). Relabel "percentile" → "range-position" in
>   `indicator_thresholds.py` / `custom_predicates.py` comments + `docs/GRAMMAR.md`.
>   Docs-only; calibrated thresholds unaffected (kernel-unit tuning). Candidate ride:
>   the v32 manifest-wiring bump (proposal `682e1abd`).

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
9. Run an emission proof (recipe below). Quick smoke: `uv run forge enumerate --max 50 --summary`.
10. Deploy (`deploy.md`). The service records the `manual_bump` row in `grammar_versions` at
    startup — do not insert one by hand.
11. Relay the new version string + deploy timestamp to Crucible (`crucible-handoff.md`) for
    `crucible funnel --compare v{N-1} v{N}`.

## Adding a new indicator (checklist)

Crucible's registry must advertise it first (contracts gap otherwise). Then Forge-side:
`indicator_thresholds.py` (real-data threshold ranges — distributions in
`docs/INDICATOR_THRESHOLDS.md`), `signal_horizon.py` (horizon table), sampler regime pools
(`_build_regime_pool`) and R-rule predicate eligibility if it can serve as a regime gate.

**Then verify layer 3 — the writer actually COMPUTES it (mandatory for a new DIRECTIONAL):**
```bash
uv run forge check-activations --indicators <new-id>   # must print [ OK ]; exit 0
```
Registered + enumerable is NOT sufficient. `sma_slope`/`ad_slope` cleared both but Crucible's
feature-cache writer returned 0 activations for every name, so they zero-traded silently — 0/2800
submitted for ~5h post-deploy (D254). `check-activations` probes the live writer per directional; a
`[INERT]` verdict (0 activations everywhere) is a **NO-GO** — relay to Crucible, don't ship it.

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
# layer-3: any newly-adopted directional must actually fire on the live writer (D254)
uv run forge check-activations --indicators <new-directional-ids>   # exit 0 = every one produces activations
```
