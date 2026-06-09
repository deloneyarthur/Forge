# Task: versionless feedback / learned-weight change

Scope: re-aiming how the sampler weighs its draws from Crucible's results — no population change,
no grammar bump. The D094 → D101 → D103 → D105 → D106 → D108 lineage; read the latest of those
D-entries before adding a new mechanism.

## Loci

- `feedback/rejection_weights.py` — the reward engines (component-rate estimand, hierarchical
  cells, discounts). New mechanisms usually extend this module.
- `enumeration/sampler.py` — where weights are consumed (`sample_config`, `_pick_underlying`,
  `_pick_regime`, …). Attach a new weight at the single draw point where its cell is fully
  determined.
- `feedback/trade_rate_priors.py` — expected-trades prior + `COLD_START_HYPOTHESES`.
- `feedback/auto_tune.py` — prefilter calibration only (tighten-only).

## Structural requirements (each has precedent tests — copy the pattern)

1. **Cold-start byte-identical** (hard rule #6): with the new input empty (`{}` / flag off), the
   emitted sequence must be byte-identical. Pinned by golden sampler-sequence tests — add yours.
2. **Exploration floor preserved** (D067): the 0.05 hypothesis floor (and the underlying floor)
   apply AFTER your mechanism; nothing may starve a cell to zero.
3. **Anti-Goodhart**: reward what Crucible accepts (component/promote rate), never raw trade
   counts; key on components, not trades (D105). Write the regression test that asserts the new
   ranking beats the old proxy on identical data.
4. **Version-scoped reads**: join the gated export to `submissions` by `config_hash` and scope by
   grammar version — the export is a rolling top-10k window polluted by pre-v5 re-gates
   (`investigate-live.md`).
5. **Risky arm → A/B flag**, default OFF = byte-identical (D108 pattern): flag on `forge run`,
   flipped later by editing the service unit.

## Steps

TDD against the requirements above → implement → emission proof (real registry + live export;
verify the weight tilt and that mass is preserved) → D-entry + `STATUS.md` → full gates →
deploy per `deploy.md`.

## Verify

```bash
uv run pytest tests/unit/test_feedback tests/unit/test_enumeration tests/invariants
```

Post-deploy: watch the journal weight lines (`hypothesis_weights:`, `bucket_weights:`,
`underlying_class_weights:`, `underlying_name_weights:`, `orthogonal_yield_discounts:`) on the
first unblocked iteration.

## Attribution

Versionless = invisible to `crucible funnel --compare`. Read the effect in the submission mix and
the realized component rate of the affected cells. Say so in the D-entry.
