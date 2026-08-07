# MANPAGE: forge & pipeline commands

Reference for every `forge` CLI command, helper script, and pipeline service.
For operational workflow see `HOW-TO.md`.

---

## NAME

**forge** — candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

## SYNOPSIS

```
forge [GLOBAL OPTIONS] COMMAND [ARGS]
```

## GLOBAL OPTIONS

Apply to every command.

| Option | Type | Default | Description |
|---|---|---|---|
| `--log-level` | str | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `--json-logs` | flag | off | Emit structured JSON logs instead of console format. |

---

## COMMANDS

### forge version

Print Forge and `crucible_contracts` versions. No options.

```
forge version
```

### forge check

Validate that the installed `crucible_contracts` is compatible and that the DB
schema applies cleanly (tested in-memory). Run after any contracts bump.

```
forge check
```

### forge enumerate

Preview grammar-valid configs against the newest registry snapshot in
`~/optbt_data/exports/` (falls back to a built-in demo registry, with a warning,
when no export exists). Useful for eyeballing what the grammar produces. The
`(demo registry)` suffix in its output is a stale Phase-2 label either way —
trust the printed `registry_hash`.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `0` | RNG root seed (determinism). |
| `--max`, `-n` | int | `10` | Max configs to yield (min 1). |
| `--summary` | flag | off | Print per-rule rejection counts at the end. |

```
forge enumerate --seed 7 --max 50 --summary
```

### forge prefilter

Run the §5.2 pre-filter battery against enumerated candidates and report per-filter
pass/fail counts. Phase 3 diagnostic.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `0` | RNG root seed. |
| `--max`, `-n` | int | `10` | Max configs to run through the battery (min 1). |
| `--summary` | flag | off | Print per-filter rejection counts. |
| `--synthetic-cache` | flag | off | Force `SyntheticFeatureCache` instead of the Crucible-backed cache. Use for fast high-`--max` diagnostics. |

```
forge prefilter --max 500 --summary --synthetic-cache
```

### forge check-activations

Layer-3 deploy gate (D254): verify Crucible's feature-cache writer actually **computes** each
directional. For every target directional it finds one enumerated config, runs it on the probed
names against the LIVE cache, and counts activations. A directional that fires 0 on every name is
`[INERT]` (registered + enumerable but the writer produces nothing — the `sma_slope`/`ad_slope`
case) → **exit 1 (NO-GO)**. Run for any grammar bump adopting a new directional (see
`docs/tasks/grammar-change.md`).

| Option | Type | Default | Description |
|---|---|---|---|
| `--indicators` | str | all directional-enumerable | Comma-separated directional ids to check. |
| `--names` | str | `SPY,AAPL,MSFT,NVDA` | Comma-separated high-history underlyings to probe. |
| `--seed` | int | `0` | RNG root seed for the probe enumeration. |
| `--min-activations` | int | `1` | A directional must fire ≥ this on ≥ 1 probed name. |
| `--max-enumerate` | int | `8000` | Cap on configs scanned to find a probe config per id. |

```
forge check-activations --indicators sma_slope,ad_slope   # [INERT] both → exit 1
```

### forge run

The full cycle: enumerate → prefilter → rank → submit. With `--loop` it runs as a
daemon; with `--consume-feedback` it runs the feedback chain after each submit.
This is what `forge.service` runs.

Config precedence: `--config` YAML (`config/forge.yaml`) → CLI flags override →
hardcoded fallback (used only with `--no-config`). The Default column shows the
shipped YAML value, with the `--no-config` fallback in parentheses.

| Option | Type | Default | Description |
|---|---|---|---|
| `--seed` | int | `42` (`0`) | RNG root seed. |
| `--batch-size` | int | `200` (`10`) | Top-N ranked candidates to submit. |
| `--max`, `-n` | int | `5000` (`1000`) | Enumeration cap before pre-filtering (min 1). |
| `--inbox` | path | — | Crucible inbox dir. Required unless `--dry-run`. |
| `--crucible-db` | path | — | Crucible runs DB (rate limiter, §7.3). |
| `--forge-db` | path | in-memory | Forge state DB. Pass a file path for persistence. |
| `--dry-run` | flag | off | Run pipeline but skip inbox writes + DB persistence. |
| `--loop` | flag | off | Daemon mode: repeat, sleeping `--poll-interval-seconds` between cycles. |
| `--require-real-cache` | flag | off | Skip the iteration (no submit) when Crucible's real feature cache is unavailable, instead of silently degrading to the synthetic cache. Production safety; on the service. |
| `--max-iterations` | int | unbounded | Cap loop iterations (testing). |
| `--poll-interval-seconds` | int | `60` (`600`) | Sleep between loop iterations. |
| `--consume-feedback` | flag | off | Run feedback chain (consumer/analyzer/proposer/auto-tune) after submit. |
| `--cross-sectional-rank / --no-cross-sectional-rank` | flag | on | H1 (v12) breadth lever: emit `cross_sectional` combiners for the breadth-starved directional archetypes (trend/mean_reversion) at a ~1/3 exploration share, defeating the 100-trade floor. ON by default (the point of v12); `--no-cross-sectional-rank` is the kill switch (revert to confluence). |
| `--cohort-yield` | flag | off | §3 yield-map refresh (D182): make the cohort draw (cross_sectional vs confluence) yield-driven by the learned (hypothesis, directional, dte_bucket, cohort) component-rate instead of the fixed share. On the service. Off is byte-identical to the H1 draw. |
| `--regime-gate-yield` | flag | off | §2 yield-map refresh (D183): make the regime-gate draw yield-driven — compose the learned (hypothesis, directional, dte_bucket, regime_gate) rate onto the D150/uniform base, down-weighting sink gates (gamma_flip) and favouring minting ones. `relative_value` excluded (D119). On the service. Off is byte-identical. |
| `--quality-rank` | flag | off | T1 quality lane (tail-aware ranking, §8.6, D193): BLEND the wf_p25 robustness prediction into the §6.2 prior — `prior := P(component) × tail_norm`. Needs an F3 P(component) base + a `target_wf_p25` robustness model. Env kill-switch `FORGE_QUALITY_RANKER`. On the service. Off is byte-identical (F3 prior unchanged). |
| `--open-proposals` | path | `OPEN_PROPOSALS.md` | Where loosening proposals are written. |
| `--prefilter-yaml` | path | `config/prefilter.yaml` | Prefilter calibration (auto-tune target). |
| `--config` | path | `config/forge.yaml` | YAML defaults file. |
| `--no-config` | flag | off | Ignore YAML; use hardcoded defaults + CLI flags only. |

**Env-only knob — `FORGE_ORTHOGONAL_FAMILY_FLOOR`** (D216; **RETIRED from the unit at D367** —
the ve floor's founding evidence was retracted; the knob stays functional as a one-line revert):
comma-separated `family=floor` pairs lifting named hypothesis families to a minimum
**max-normalized** sampling weight (NOT a delivered share — judge on the journal's `floor
ACTIVE` line). Only ever raises (`max` semantics); unset → byte-identical (hard rule 6).
Consumed by `forge.cli.main._orthogonal_family_floors` →
`rejection_weights.apply_orthogonal_family_floor`. History: D216/D367.

**`search_n_trials` stamping (D310, automatic, self-gated)**: every submitted config is stamped with its
per-slot cumulative search multiplicity (slot = hypothesis × dte_bucket × xsect-vs-named, counted from
`submissions`) — the half of Crucible's DSR `n_trials = max(search, selection)` that Forge owes (their
07-08 Q1/Q2 answers + their (a) record-not-bind resolution). Stamping SELF-ARMS: it begins only once
Crucible's `recorded_not_binding` marker is observed in a fresh verdict's `deflated_sharpe` detail (their
deployment signal); until then configs ship unset (their `n_trials=1` path). Journal line per batch:
`search_n_trials: stamped N configs (max slot n_trials=M)` or `search_n_trials: dormant (…)`. The field is
hash-excluded (contracts 1.19.0) — idempotency and batch identity untouched. No flag; module
`forge/submission/search_multiplicity.py`.

**Env kill-switch — `FORGE_F3_RANKER`** (D149): default `on` — the F3 `P(component)` ranker prior (latest
trained model under `<forge-db-dir>/models`) feeds the §6.2 slot. Set `off`/`0`/`false`/`no` to skip the
model load entirely and revert scoring to the pre-F3 Jaccard-novelty baseline. Emergency revert lever, the
F3 sibling of `FORGE_QUALITY_RANKER` (which kills the D193 quality lane on top of F3). Never set in
production; consumed by `forge.cli.main` at model-load time.

**Env-only knob — `FORGE_QUALITY_RANK_MODE`** (the `--quality-rank` lane form, D217/P1.1): `blend` (default,
unset → byte-identical) computes `prior := P(component) × tail_norm` into the §6.2 slot; `gate-tail`
switches to the validated hard-gate form — `P(component)` GATES eligibility at `FORGE_REWIRE_P_FLOOR`
(default 0.02) and the wf_p25 tail prediction ORDERS the survivors. **P1.1:** under `gate-tail` the composite
IS the gate-tail value (the §6.2 hygiene blend is BYPASSED), so the gate is HARD — below-floor configs pin
to 0.0 and can never outrank an eligible config (matching the `rewire_streak_wfp25` shadow the flip decision
reads, which gates on the SAME `FORGE_REWIRE_P_FLOOR`). Consumed by `forge.cli.main._quality_rank_mode` →
`rank_batch(gate_tail_ordering=…)`. Flipping to `gate-tail` is an operator-gated deploy (prereg + the §8.6
rewire streak); keep the floor env identical on `forge.service` and `forge-ranker-eval` so shadow==production.

**Env-only knob — `FORGE_EXPLORATION_HOLDOUT_FRAC`** (P3.3/B7, D232): the fraction of each batch that
BYPASSES the learned ranking as a seeded random draw from the prefiltered survivors — unbiased labels for
F3 / the wf_p25 lane / the D076 estimand (which otherwise all train on Forge-*selected* submissions). Unset
/ empty / `0` → **byte-identical** (no holdout, plain `rank_batch`). A value >0 reserves `round(frac·batch_size)`
slots (the holdout REPLACES rank slots — total submitted stays ≤ batch_size, no oversubscription); clamped to
`[0, 0.10]`; malformed → 0 (degrade-never-crash, warn-once). Draws via `SeedHierarchy(seed).rng(
"exploration_holdout")` (deterministic, rule #8) and tags `submissions.selection_mode='holdout'` (vs `'ranked'`)
so evals can split biased-vs-unbiased. Consumed by `forge.cli.main._resolve_exploration_holdout_frac` →
`rank_batch_with_holdout`. Activation is an operator-gated submission-mix change (deploy ritual + the D220 hold).

**Experiment-cell selection floor (D287/D299)** — `forge.ranking.experiment_cells.EXPERIMENT_CELLS`
DERIVES from farming campaigns in the registry (`forge.ranking.campaigns`) and reserves
`EXPERIMENT_CELL_SLOTS` (4) ranked slots per pinned (directional, regime) cell via a diversifier
reservation phase, so a learned ranker cannot starve a live experiment at selection (the
D119/D136 principle). **The pin set is currently EMPTY** — the resid×vix campaign retired on
Crucible's relay (D305) — so the reservation phase is a no-op until a future campaign pins a
cell. Journal line when active: `experiment_cell_floor: {...}`. History: D287/D299/D305.

**Env kill-switch — `FORGE_YOUNG_CELL_FLOOR`** (D307, Theme 2b): default `off` — must be exactly
`on` to activate the YOUNG-cell exploration floor (diversifier phase 0c): any (directional,
regime) cell with < 25 honest-era verdicts (`forge.ranking.cell_floor`, ghost-cut applied) gets
≤ 2 reserved slots per batch, capped at 10% of the batch, hand-pinned campaign cells exempt —
the D287 protection made automatic so a novel pair cannot be starved at selection even when both
its arms are individually mature (the arm-floor keying gap that forced the D287 hand pin).
`off`/unset → `mature_cells=None` → **byte-identical** (reboot-safe before the activation
window). Activation is an operator-gated deploy (flip the env on `forge.service` + restart);
journal line when active: `cell_floor: mature_cells=N …`.

**Env-only knob — `FORGE_TAIL_LANE_SLOTS`** (prereg `8cfe95f4a6e9`): ranked slots per batch
reserved for the **tail arm**, ordered by `P(top-N by sharpe_baseline)` from the `train-tail`
artifact; tagged `selection_mode='tail_lane'` (a concurrent arm — arm splits inside the same
batches cancel Crucible's measured drift floor, which a before/after read cannot; the arm draws
FIRST so merit and holdout never see its picks). Unset/0 → byte-identical; no artifact → lane
logs `inert`; clamp **[0, 150]** so a control arm always survives. Journal:
`tail_lane: ACTIVE N slots (…)`. Activation is an operator-gated deploy.

**Env-only knob — `FORGE_TREND_LANE_SLOTS`** (prereg `8cfe95f4a6e9`, trend leg): the second
objective lane, ordered by `P(top-200 by wf_sharpe_p10)`, tagged `selection_mode='trend_lane'`
— the target is REGIONAL (the metric rejected for MR is the trend winner; the wf_p10 label
carries a count cliff, so it is pinned at top-200). Clamp **[0, 60]** so the merit arm survives
both lanes. Needs a `train-tail --base-target target_wf_p10 --n-pos 200` artifact; without one
the lane logs `inert`. Measurement narrative: the prereg + its D-entries.

**Env-only knob — `FORGE_GENERATION_ARM_B_SHARE`** (D341; **A/B CLOSED REFUTED at D351** — the
unit carries `0`): the generation-side concurrent A/B — a fraction of enumerated configs drawn
under arm B's book-usable-rate regime-gate weights instead of the incumbent component-rate map,
tagged via the contracts 1.39.0 `generation_arm` field. Unset/0/malformed → no arm coin, no rng
consumed, no stamp — byte-identical (hard rule #6). Clamp [0.0, 0.5] (an experiment keeps a
control). The `generation_arm` field is free for the next generation experiment
(`contracts_check.py` note). History: D341/D351.

**Env-only knob — `FORGE_YOUNG_CELL_EXPLORE_SLOTS`** (D316, Theme 2d): extra seeded-random
submission slots per batch reserved for YOUNG-cell members, tagged
`selection_mode='young_explore'` — a THIRD lane, deliberately distinct from the uniform
holdout (which is the ranker-vs-random estimand and the campaign-audit denominator, and must
stay an unweighted draw). The floor guarantees young cells get submitted; this quota makes
them accrue UNBIASED labels faster. Requires the young-cell floor ON (needs `mature_cells`);
inert without it. Unset/0 → **byte-identical**; clamp [0, 8]; recommended 4. Slots REPLACE
rank slots (total ≤ batch_size), feasibility-checked so a short young pool never under-fills
the merit lane. Draw via `SeedHierarchy(seed).rng("young_cell_explore")`. Activation is an
operator-gated deploy (env + daemon-reload + restart). Journal line: `young_explore: K of N …`.

```
# One real batch, persisted:
forge run --inbox ~/optbt_data/inbox --forge-db ~/forge_data/forge.db --batch-size 200

# Daemon (what the service runs — see deploy/systemd/forge.service):
forge run --loop --consume-feedback --require-real-cache \
  --cohort-yield --regime-gate-yield --quality-rank

# Dry run, no side effects:
forge run --dry-run --max 100
```

**§7.3 backpressure (yaml-only knobs under `submission:`).** Before each batch the loop
asks `check_rate_limit` whether to submit; it can block for two independent reasons:

- **Completion fraction** (`inflight_threshold`, default `0.80`): wait until ≥80% of the
  oldest in-flight batch is gated. Journal: `blocked: oldest in-flight batch … N% gated`.
- **Stall guard** (`stall_after_seconds`, default `10800` = 3 h; `0` disables — D137): block
  when Crucible has had new work in its queue for ≥ that long and decided nothing (the
  decision clock `max(decided_at)` is stale while configs submitted after it sit pending).
  Catches the wedge the completion fraction misses — a 99%-gated front batch while newer
  configs pile into a dead gate. Stateless and deadlock-immune (a clock left stale by
  Forge's *own* quiet has no submission postdating it, so the guard stays silent). Journal:
  `blocked: crucible stalled — no decisions since <ts> (<X.X>h); <N> configs pending ≥3h`.

### forge feedback

Manual single-batch feedback: read Crucible's gated runs, analyze, propose grammar
refinements. Auto-tune always runs. (Daemon equivalent: `forge run --consume-feedback`.)

| Option | Type | Default | Description |
|---|---|---|---|
| `--batch-id` | str | latest | Explicit batch UUID to analyze. |
| `--since` | str | batch time | ISO datetime cutoff for Crucible runs. |
| `--config` | path | `config/forge.yaml` | YAML defaults. |
| `--no-config` | flag | off | Skip YAML; require explicit paths. |
| `--forge-db` | path | yaml | Override Forge DB path. |
| `--crucible-db` | path | yaml | Override Crucible DB path. |
| `--open-proposals` | path | `OPEN_PROPOSALS.md` | Proposal audit file. |
| `--prefilter-yaml` | path | `config/prefilter.yaml` | Prefilter calibration. |

```
forge feedback --batch-id 1a41005f-... --forge-db ~/forge_data/forge.db
```

### forge ranker-model dataset

Build the learned verdict model's honest-era training frame (D132 / F1):
`verdicts ⋈ submissions` on config_hash, rows hard-cut at the clean-era label
boundary, label = component/promote AND D128-honest coverage, one feature
column per emitted feature name (wide, missing → 0.0). The live forge.db holds
an intermittent RW lock — point `--forge-db` at a `/tmp` snapshot.

| Option | Type | Default | Description |
|---|---|---|---|
| `--out` | path | required | Output parquet path. |
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override (naive = UTC). |

```
SNAP=$(scripts/live_db_snapshot.sh)   # real disk, reused; NEVER /tmp (tmpfs, see investigate-live.md)
forge ranker-model dataset --forge-db "$SNAP" --out /tmp/verdict_dataset.parquet
```

### forge ranker-model train

Train the verdict model on the honest era and save the artifact (D132 / F2 —
manual, run at the daily checkpoints). Refuses datasets under 50 rows / 5
positives. Artifacts are append-only canonical JSON with coefficients by
feature name; the daemon shadow-scores against the newest artifact in
`<forge_data>/models/` from its next batch (telemetry only until F3).

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML defaults (db_path, models dir). |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override. |
| `--lambda` | float | 1.0 | L2 regularization strength. |
| `--models-dir` | path | `<config db_path parent>/models` | Artifact dir (NOT derived from `--forge-db` — that's a snapshot). |

### forge ranker-model train-tail

Train the **tail-lane** model (prereg `8cfe95f4a6e9`) — an L2 logistic predicting
`P(config lands in the top N by a continuous base metric)`, default
`target_sharpe_baseline` top-800. Distinct from `train-robustness`, which fits a *ridge on a
continuous value*: promotion is a tail event and an average-shaped objective does not order
tails (on stage-one cells spearman(cell mean, cell std) = −0.148 while spearman(cell
P(≥1.0), cell std) = +0.500). Refuses when the base-metric column is absent, when under 50
rows carry it, or when `--n-pos` ≥ the trainable rows (the label would be every row). Saves
an append-only `tail_model_<base_target>_n<N>_*.json` artifact — base metric and label size
are both in the FILENAME, so two lanes at different sizes never shadow each other. Published
daily by `scripts/daily_ranker_eval.sh` (staging + atomic mv); the artifact must exist
BEFORE `FORGE_TAIL_LANE_SLOTS` is set or the lane logs `inert` and changes nothing.

`--n-pos` is a **count, never a quantile**: five independently-tuned parameters have failed
to transfer forward on this data, and `wf_p10` carries a mass point at zero where a quantile
threshold lands inside a tie block and reduces the label to an arbitrary tie-break. The
default 800 is the measured operating point, not a value to search.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML defaults (db_path, models dir). |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override. |
| `--lambda` | float | 10.0 | L2 regularization strength. |
| `--base-target` | str | `target_sharpe_baseline` | Continuous metric the top-N label ranks. |
| `--n-pos` | int | 800 | Label size: the top N by `--base-target`. Pinned, not searched. |
| `--models-dir` | path | `<db parent>/models` | Artifact directory. |

### forge ranker-model train-robustness

Train the tail-aware T1 model (D140) — a deterministic ridge fit predicting a
continuous worst-quartile gate value (default `cpcv_sharpe_p25`) instead of
P(component). Same honest-era dataset, manual at the daily checkpoints; refuses
when under 50 rows carry the target. Saves an append-only `robustness_model_*.json`
artifact; the summary line reports `oos_r2=` (out-of-sample R², D233) and `rmse=`
alongside the artifact path. The daily timer trains the **`target_wf_p25`** model (D191/D192) — the
quality lane's; that artifact is shadow-scored in the daemon and (when `--quality-rank`
is on) blended into the §6.2 prior. Design: §8.3 / §1.2 (Forge consumes Crucible's
`gate_results` values, computes none).

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML defaults (db_path, models dir). |
| `--exports-dir` | path | exports default | Crucible exports dir (registry snapshot). |
| `--era-cut` | str | `2026-06-10T17:17:13Z` | ISO label-era cutoff override. |
| `--lambda` | float | 1.0 | L2 regularization strength. |
| `--target` | str | `target_cpcv_p25` | Continuous gate value to predict (`target_wf_p25` — the lane's, `target_wf_p10`, `target_wf_median`, `target_regime_stress`). |
| `--label` | path | none | Per-component label JSON sourcing the target column. |
| `--label-col` | str | `wf_sharpe_p25` | Label column to use as the target (requires `--label`). |
| `--models-dir` | path | `<config db_path parent>/models` | Artifact dir (NOT derived from `--forge-db`). |

### forge ranker-model eval

Shadow vs incumbent readout on decided verdicts (the F3 criterion: model AUC ≥
incumbent + 0.05 AND precision@K ≥ incumbent's, on ≥3 consecutive daily
checkpoints of ≥150 fresh verdicts each). Prints AUC/precision@K/Brier and a
reliability table per model_id.

**Calibration line (P1.3)** — `ece` (overall, frequency-weighted, ~small because the
mass sits in well-calibrated low-P bins), `max_ce` (**the floor-relevant measure**: max
calibration gap over bins with ≥20 rows — the gate-then-tail floor selects the high-P
sliver where P over-predicts ~3-5x), `ece_platt` (the ECE a held-out Platt recal reaches —
the *recoverable* calibration floor), and a **co-primary calibration criterion**
(`max_ce ≤ 0.20`). This blesses `P` for the ABSOLUTE floor, distinct from the AUC verdict
that blesses the model for the blend's RANKING — a well-ranking-but-miscalibrated model
passes AUC and fails calibration. Telemetry only (gates no live behavior); the daily timer
tracks `model_ece`/`model_max_ce`/`model_ece_platt`/`calibration_verdict` in `streak.jsonl`.
The recalibrator's *application* to the live `P` is deferred to the gate-tail floor
re-derivation (P1.1) — recalibrating the `P` that fills the §6.2 prior slot would change
the composite sort.

**Hygiene-incumbent block** — a second per-model readout judged against
`shadow_scores.hygiene_score`, the **model-free §6.2 hygiene composite** (prior slot zeroed),
restricted to rows that carry it (paired). Why: `composite_score` stores whatever score
production ordered by, so under gate-tail mode (P1.1) the legacy "incumbent" is the lane's
own value — self-referential. The hygiene column is the incumbent that stays stable across
lane-mode flips; it is NULL for rows recorded before the fix (populates after the next
service restart), and the block prints a placeholder line until then.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--since` | str | clean-era boundary | ISO window start (naive = UTC). |

```
SNAP=$(scripts/live_db_snapshot.sh)   # real disk, reused; NEVER /tmp (tmpfs, see investigate-live.md)
forge ranker-model train --forge-db "$SNAP"
forge ranker-model eval --forge-db "$SNAP" --since 2026-06-11T00:00:00Z
```

### forge ranker-model eval-robustness

Tail-aware (T1, D143) readout: does ranking by the predicted tail value (the D141 `tail_score`)
surface configs with higher REALIZED worst-quartile robustness? Per `tail_model_id`, over
verified-coverage decided verdicts, prints **Spearman(tail_score, realized `--gate` value)** and
**top-K mean realized value** (tail model vs the incumbent composite). No PASS/FAIL — the §8.6
criterion margin is set once the shadow distribution is visible.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--since` | str | clean-era boundary | ISO window start (naive = UTC). |
| `--gate` | str | `cpcv_sharpe_p25` | Realized worst-quartile gate to correlate against (timer uses `wf_sharpe_p25`). |

**Automated daily** by the `forge-ranker-eval` systemd timer (05:00; `scripts/daily_ranker_eval.sh`)
— it snapshots the DB, trains BOTH shadow models (`train` for P(component) + `train-robustness
--target target_wf_p25` for the quality lane's tail-aware model, D191/D192; each atomic-published to
`~/forge_data/models/`), evaluates (`eval` for the streak + `eval-robustness --gate wf_sharpe_p25`
for the observational tail readout), and appends **TWO consecutive-PASS clocks**: the F3
verdict-model streak to `~/forge_data/ranker_eval/streak.jsonl` (judged on the hygiene incumbent
once populated, D284 — `margin_source` per row) and the gate-then-tail re-wire streak to
`~/forge_data/ranker_eval/rewire_streak_wfp25.jsonl`. Both judge a **fresh per-checkpoint window**
(verdicts decided since the prior run), NOT the cumulative `--since` default — read the clocks
there instead of re-deriving them. The **§8.6 wf_p25 tail streak**
(`robustness_streak_wfp25.jsonl`) was **RETIRED 2026-07-16 (D285)**: after the gate-tail flip its
recorded incumbent was the lane's own ranking score, pinning its paired delta to ≈0 by
construction; the history file stays on disk.

### forge ranker-model eval-rewire

Gate-then-tail re-wire shadow (§8.6): does gating on `P(component)` (eligibility floor `--p-floor`)
and then ordering the survivors by the predicted WF floor surface configs with a higher REALIZED
`--gate` than ranking by `P(component)` alone (the deployed lane ≈ the P-baseline)? Prints the
gate-then-tail vs P-baseline top-K mean realized value over verified-coverage decided verdicts.
Also prints **`eligible_fraction`** (P1.3) — the fraction clearing `--p-floor`, i.e. the floor's
KEEP-RATE; watch it for silent drift (P miscalibration moves the eligible set under a fixed floor).
Telemetry only — no PASS/FAIL until the §8.6-style margin is set. Design:
`docs/proposals/quality-lane-rewire.md`.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--since` | str | clean-era boundary | ISO window start (naive = UTC). |
| `--gate` | str | `wf_sharpe_p25` | Realized worst-quartile gate to score against. |
| `--p-floor` | float | `0.02` | Absolute `P(component)` eligibility floor (production-calibrated). |

### forge ranker-model eval-prior-weight

Prior-weight A/B (B2): the §6.2 composite scores candidates as a weighted sum whose learned
`P(component)` term (`prior_promotion_proximity`) sits at weight **0.10** — the other four
(hygiene) terms carry 0.90 and measure ~coin-flip AUC vs realized promotion. Re-scores the
submitted shadow rows under each `--weights` value (holding the hygiene terms' relative
proportions) and prints the top-K realized component yield (precision@K, AUC) per weight.
Higher at higher weight ⇒ the 0.10 slot under-weights the (good) prior. Offline + censored
(only submitted configs carry verdicts) — a first-pass signal; confirm the winner on a live
shadow lane before any `ranker.yaml` change. fable-audit learned-systems P1.4/B2.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | yaml | Forge DB path (use a `/tmp` snapshot of live). |
| `--config` | path | `config/forge.yaml` | YAML default for the DB path. |
| `--since` | str | clean-era boundary | ISO window start (naive = UTC). |
| `--weights` | str | `0.10,0.30,0.50,0.70,1.0` | Comma-separated prior weights to A/B (0.10 = the live slot). |

### forge healthcheck

Reports whether the daemon is alive AND productive, then exits 0 (OK) / 1 (WARN) / 2
(CRITICAL). The checks: **service** (`systemctl is-active forge.service`), **loop** (newest
`--- loop iteration` journal line — catches a wedged-but-active process), **submission**
(newest `submitted=N` line + the latest `blocked:` reason — catches a chronically-stalled
pipeline, e.g. a Crucible stall, and points upstream), **backup**/**model** freshness (a
silently-broken daily timer), **contracts** (installed vs `FORGE_EXPECTED_CONTRACT_VERSION`:
minor drift WARN, major CRITICAL), **component_contributions** (D216: soft presence check on
Crucible's `component_contributions_*.json` export — the export is per-promoted-portfolio, so
absent-until-the-first-promotion is OK, never a WARN), two **learning drift** checks (the F3 +
wf_p25 `forge status` clocks — CRITICAL if a learned lane has gone anti-predictive, WARN if it
has lost its edge over the §6.2 composite or dropped sharply from its trailing median; catches
a bad daily model rotation that newest-wins adoption would otherwise put live silently, D209),
and **hypothesis_weights** (P3.2/B6: WARN when the journal shows the sampler degraded to
UNIFORM hypothesis sampling because the learned yield/cohort weights failed to load — the
feedback loop silently muted), and **inbox_rejections** (D245: count of recently-mtimed
`~/optbt_data/inbox/errors/*.json` — rejected submissions — WARN on a chunk, CRITICAL on a
batch-sized burst; catches the 'submitting-but-rejected' wedge an asymmetric contracts
upgrade causes, which otherwise reads identically to ordinary §7.3 backpressure; window/
thresholds tunable via `--inbox-reject-window-hours`/`--inbox-reject-warn`/`--inbox-reject-critical`),
and **tmp_headroom** (D259: `/tmp` free space as a multiple of the forge.db size — WARN below
`--tmp-warn-ratio` (5×), CRITICAL below `--tmp-critical-ratio` (3.5×); catches the CAUSE of the
2026-07-09 stall — the daily ranker-eval's `cp forge.db /tmp/…` fails on a full /tmp and the
F3/wf_p25 models silently stale until the `model` check CRITs ~2 days later), and
**campaign carriage** (D302: the daily campaign-audit JSONL row — WARN when a farming
campaign is STARVED at selection (the D287 class) or the audit row has gone stale;
OK-with-note before the first 05:00 fire). Plus **activation probe** (D316: the daily
writer-activation probe row — WARN on INERT directionals, the ref_trailing_return/D254
drawn-then-killed class, or a stale probe file). Plus **freeze census** (D328: the daily
grammar-freeze metric-B row — WARN when the dead-unprotected share of submission flow
rises past the operator bar (a dead axis started flowing or a farming protection retired)
or the census file is stale).
Authoritative list: the `check_*` calls in
`src/forge/cli/healthcheck_cmd.py`. Reads the journal + filesystem +
version + the ranker-eval clocks — no DB snapshot.
Run by hand or via the `forge-healthcheck` timer (hourly); the timer's unit sets
`SuccessExitStatus=1` so only CRITICAL marks it failed (visible in `systemctl --user
--state=failed`). Thresholds are tunable (`--submission-warn-hours`, `--loop-critical-minutes`, …).

```
forge healthcheck        # or: systemctl --user start forge-healthcheck.service
```

### forge status

Pretty-prints the two curated learning clocks the daily ranker-eval timer writes under
`~/forge_data/ranker_eval/` — answering "is the stream improving?" at a glance, with no
`tail|json` spelunking and **no DB access**: the **F3 verdict ranker** (`streak.jsonl`, AUC
margin over the incumbent — hygiene-judged once populated, D284) and the **re-wire gate-tail**
clock (`rewire_streak_wfp25.jsonl`, Δ of the live lane's top-K realized WF floor vs P-alone).
The §8.6 wf_p25 tail clock was retired 2026-07-16 (D285, self-referential post gate-tail flip)
— a tombstone line points at its history file. Each line shows the latest verdict, the
trailing consecutive-PASS streak (N/3), the latest metric, and an N-checkpoint trend. A
**`P calibration/floor`** line (P1.3) adds the drift guard: the latest floor-relevant
calibration verdict + `max_ce` (from the F3 streak) and the gate-tail floor keep-rate
(`eligible_fraction`, from the rewire clock) — tolerant of pre-P1.3 records (`n/a`). A
**`gate-tail flip gate`** line (P1.2, criterion re-based P3.1/B5) shows whether gate-tail is
safe to flip: `MET` only when a **Wald SPRT over the fresh-window paired deltas** decides
"promote" (log-likelihood-ratio crosses the upper Wald boundary — controls the false-promote
rate at ~alpha under daily peeking; full-pool "look" records excluded). The fresh PASS streak
shown alongside is a display-only diagnostic — the SPRT weighs delta magnitudes, not the
binary PASS (`src/forge/cli/status_cmd.py`). Distinct from `forge healthcheck` (is the daemon
*alive/producing?*); this is *is the learning improving?*. For the authoritative recompute
use `forge ranker-model eval` / `eval-robustness`.

```
forge status
```

### forge campaigns list / audit

The campaign registry — the discover→concentrate→farm loop as a first-class object (D299).
`list` prints every registry record (`forge.ranking.campaigns.CAMPAIGNS`): lifecycle status,
origin evidence, D-refs, the selection floor if any, the funnel read the campaign waits on, and
its retire condition. The registry is code, edited only with a D-entry (the sampler-pin
convention); the D287 experiment-cell floor DERIVES from it, pinned byte-identical by test.

`audit` runs the region-carriage check per farming campaign over a `--days` window (default 7):
ranked-lane member share vs holdout-lane member share. The holdout bypasses ranking, so its share
is an unbiased estimate of the campaign's share of the passed pool; ranked share below
0.25× holdout share (with ≥3 holdout members) flags **STARVED** — the D287 failure class
(generation feeds a region, the learned lane's P-gate eats it at selection). Also prints
verdict-decision counts for window members. Exit 1 when any campaign is starved (scriptable
tripwire). Read-only; snapshot the live DB first (RW-lock pitfall).

```
forge campaigns list
SNAP=$(scripts/live_db_snapshot.sh) && forge campaigns audit --forge-db "$SNAP" --days 7
```

### forge yield-audit

The standing dead-cell detector (D302, Theme 4 of the post-promotion process review). Runs the
census-class yield reads locally over decided verdicts: **dead names** (≥ `--min-name-n`, default
500, decided with ZERO conversions — the ASML/COST class) and **cold cells**
((hypothesis × dte_bucket) at ≥ `--min-cell-n`, default 1000, converting below 0.25× the
hypothesis baseline). Honesty guards built in: the ve ghost-label cut (pre-07-18 ve rows are
never evidence), the clean-era `--since` default, farming-campaign hypotheses exempt from cell
flags (a young concentrated sweep looks exactly like a dead cell), already-excluded names
reported for retire-review but never re-flagged, and zero-baseline hypotheses skipped.
**Detection only — writes nothing.** Dead names render a STAGED RIDER DRAFT (v34/v37 frozen-list
terms) for the operator to lift into a grammar-bump proposal after a prereg (D207) and Crucible
row-45 cross-check. Caveat before acting: cross-check flags against the CURRENT universe —
names no longer drawn save nothing. Always exit 0. Snapshot the live DB first.

```
SNAP=$(scripts/live_db_snapshot.sh) && forge yield-audit --forge-db "$SNAP"
```

### forge prereg

Pre-register a prune/retarget, then confirm it on a *later* cohort (Tier-1a honesty discipline,
D208). The §8.4 auto-tightening triggers — and most manual prunes — observe a pattern in a cohort
and act on the same cohort that revealed it (post-selection bias). `forge prereg register` records
the claim with a `--cohort-cut`; only data after the cut may confirm it, and `forge prereg resolve`
takes operator-supplied post-cut evidence. The registry is a git-tracked JSONL
(`config/preregistrations.jsonl`) so the prediction is committed before its test; the
`confirm_promotion_claim` guard (in `forge.feedback.preregistration`) structurally drops pre-cut
rows for programmatic callers. Read/write only — no production-loop or grammar change.

```
forge prereg register --claim "adx<10 never promotes" --predicted "<= 0.005" \
    --action "tighten adx lower bound" --cohort-cut 2026-06-25T00:00:00
forge prereg list --open-only
forge prereg resolve <id> --outcome confirmed --evidence "post-cut rate 0.002 (n=120)"
```

### forge grammar list-proposals

List pending refinement proposals. Recurring themes (3+ pending) tagged `[PERSISTENT]`.

| Option | Type | Default | Description |
|---|---|---|---|
| `--forge-db` | path | `:memory:` | Forge state DB. |

```
forge grammar list-proposals --forge-db ~/forge_data/forge.db
```

### forge grammar approve-proposal / reject-proposal

Record an operator decision (audit row). **Approve does NOT mutate `grammar.yaml`** —
you still edit it by hand and let the pre-commit hook enforce version + archive.

| Option | Type | Default | Description |
|---|---|---|---|
| `--id` | str | *required* | Proposal UUID. |
| `--initials` | str | *required* | Operator initials (audit). |
| `--forge-db` | path | `:memory:` | Forge state DB. |

```
forge grammar approve-proposal --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
forge grammar reject-proposal  --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
```

### forge grammar apply-proposal

Atomically apply a pending proposal (YAML edit + audit row + `grammar_versions`
entry). **Only `target=prefilter_calibration` (tighten-only) proposals** are
supported; grammar proposals stay manual.

| Option | Type | Default | Description |
|---|---|---|---|
| `--id` | str | *required* | Proposal UUID. |
| `--initials` | str | *required* | Operator initials. |
| `--forge-db` | path | `:memory:` | Forge state DB. |
| `--prefilter-yaml` | path | `config/prefilter.yaml` | Target YAML for calibration proposals. |

```
forge grammar apply-proposal --id <UUID> --initials AJ --forge-db ~/forge_data/forge.db
```

### forge grammar revert

Revert `grammar.yaml` to a prior archived version by promoting it forward as a new
bumped version (preserves the audit trail — no history rewrite).

| Option | Type | Default | Description |
|---|---|---|---|
| `--to-version` | str | *required* | Archived version to revert to (e.g. `v3`). |
| `--initials` | str | *required* | Operator initials. |
| `--forge-db` | path | `:memory:` | Forge state DB. |
| `--grammar-yaml` | path | `config/grammar.yaml` | Current grammar file. |
| `--archive-dir` | path | `config/grammar_archive` | Archived versions dir. |

```
forge grammar revert --to-version v3 --initials AJ --forge-db ~/forge_data/forge.db
```

---

## SCRIPTS

Run via `.venv/bin/python scripts/NAME.py` from the Forge repo root.

### daily_ranker_eval.sh

**Bash, not Python** — the `ExecStart` of the `forge-ranker-eval` timer (05:00 daily), runnable by
hand too. Snapshots the live DB to `/tmp`, trains the verdict model AND the tail-aware
`wf_p25` robustness model (D191/D192, the quality lane's) into a staging dir and **atomically**
publishes each to `~/forge_data/models/` (the daemon's `load_latest_model` never reads a half-written
file), evaluates the live shadow models, and appends one JSON row to EACH of two clocks — the F3
verdict streak `~/forge_data/ranker_eval/streak.jsonl` (hygiene-incumbent-judged once populated,
D284) and the gate-then-tail re-wire streak `~/forge_data/ranker_eval/rewire_streak_wfp25.jsonl`
(the §8.6 tail streak was retired 2026-07-16, D285) — both judged
on a fresh per-checkpoint window. D302 adds a final non-fatal block: the campaign
region-carriage audit (`forge.ranking.campaign_audit`) appends one row to
`~/forge_data/ranker_eval/campaign_audit.jsonl`; the healthcheck's `campaign carriage` check
WARNs on a starved campaign or a stale file. D316 adds the writer-activation probe:
`forge check-activations` daily → `~/forge_data/ranker_eval/activation_probe.jsonl` (the
`activation probe` healthcheck WARNs on INERT ids). D328 adds the grammar-freeze census:
`scripts/search_multiplicity_census.py --db $SNAP --jsonl-out …` reuses the same snapshot →
`~/forge_data/ranker_eval/search_multiplicity_census.jsonl` (one metric-B row/day; the
`freeze census` healthcheck WARNs on a rise past the bar or a stale file). D339 adds the
vix-conditioner ranked share → `~/forge_data/ranker_eval/vix_conditioner_share.jsonl`: the
cell's share of its eligible pool per selection arm, over 7d. **Deliberately no healthcheck
check** — the cell is worth ~0.01% of strong production, so it is a row to read when asked,
not an alert. It exists to keep the D339 commitment to Crucible auditable: their
`vix-trend-conditioner` entry is left UNBOUND because our ranker already de-selects the cell
~24x, and we bind it if `ranked_share_max` climbs toward `unbiased_share_mean`. Deterministic
(no LLM, hard rule #5); telemetry-only — never touches grammar/weights/config/ranking.
Trap-cleans the snapshot + staging on every exit. No args.

```
scripts/daily_ranker_eval.sh        # or: systemctl --user start forge-ranker-eval.service
```

### backup_forge_db.sh

**Bash, not Python** — the `ExecStart` of the `forge-backup` timer (04:00 daily), runnable by
hand too. Nightly disaster-recovery backup of the non-git state. `cp`s the live `forge.db`
between write bursts, **validates** the copy (opens it read-only and queries `submissions`; a torn
mid-write copy fails and retries ≤3×), then publishes it via atomic same-fs rename as
`forge_db_<UTC>.duckdb`; `~/forge_data/models/` is tar.gz'd alongside. Retention keeps the newest
`FORGE_BACKUP_KEEP` (default 14) of each and prunes **only after** a validated new backup exists, so
a failed run never deletes the last good one. Validation uses the venv python directly (no `forge`
import) so a broken deploy can't break the backup. Env knobs: `FORGE_BACKUP_DEST` (default
`~/forge_data/backups` — **same-disk**; point at a mounted external/remote target for true off-box
DR), `FORGE_BACKUP_KEEP`, `FORGE_BACKUP_MIN_FREE_MB`. Deterministic-loop rules don't apply (ops glue,
not `src/`); reverting = disable the timer. No args.

```
scripts/backup_forge_db.sh          # or: systemctl --user start forge-backup.service
```

### deploy_preflight.sh

**Bash** — a read-only GO/NO-GO gate for the D104 deploy ritual (`docs/tasks/deploy.md`),
run before committing + restarting. Checks (1) the git tree is clean (uncommitted tracked
changes deploy on reboot) and (2) the FULL suite passes — which covers the contracts-pin
equality test (D176) and the loop/single-iteration forward tests (D185), so a green suite
proves pin-adoption + anti-inertness in one shot. Exit 0 = GO (prints the stop→restart
steps); non-zero = NO-GO (prints the blocking reason). Never stops/starts the service or
mutates the tree. No args.

```
scripts/deploy_preflight.sh
```

### check_grammar_version_bump.py / check_grammar_doc_sync.py

Pre-commit hooks (no CLI args). The first enforces that a changed `grammar.yaml`
bumps `grammar_version` and archives the prior version. The second keeps
`grammar.yaml` rule IDs and `docs/GRAMMAR.md` headings in sync.

### Full scripts inventory (every file in `scripts/`, classed)

**Standing rule (2026-08-06): a one-off analysis script is DELETED with a retirement-ledger
row below once its D-entry lands** — the conclusion lives in the ledger, the code in git
history. `scripts/` holds only wired, ritual, and in-flight instruments.

| Class | Scripts |
|---|---|
| WIRED — machinery executes them | `daily_ranker_eval.sh` (05:00 timer), `backup_forge_db.sh` (04:00 timer), `search_multiplicity_census.py` (invoked by the daily eval), `check_grammar_version_bump.py` + `check_grammar_doc_sync.py` (pre-commit), `deploy_preflight.sh` (deploy step 0), `live_db_snapshot.sh` (the blessed DB-snapshot idiom) |
| RITUAL / standing monitor | `tail_verified_alignment.py` (D155 verified-coverage alignment monitor; run against a `live_db_snapshot.sh` snapshot), `production_by_group.py` (per-arm/per-category production reads) |
| IN-FLIGHT freeze/ceiling instruments | `freeze_tail_reading.py` (+ its importer `freeze_registered_read.py` — spent once its prereg-pinned tests retire with the declaration), `ceiling_record_test.py`, `joint_frontier.py` (D368), `second_gate_contrast.py` (carries the D360 measurement_basis pooling defect — repair queued in the freeze declaration), `threshold_resolution_value.py` (D353), `promoted_leg_recall.py` |

Retired 2026-07-05 (D241 follow-through; recoverable from git history): `signal_correlation_regime_pair_audit.py` (D227 evidence), `decorrelation_proxy_alignment.py` (D186), `wf_quality_probe.py` (D186→D189).
Retired 2026-07-20 (D295 post-promotion sweep; recoverable from git history, tests removed with them): `backfill_verdicts.py` (D111 one-time catch-up, completed), `migrate_verdicts_decided_at.py` (D117 one-time era repair, completed), `requeue_high_value_configs.py` (one-off recovery, completed), `probe_option_momentum_min_months.py` (Q39 one-shot probe + its `probe_results/` output; Q39 resolved at v19/D138).
Retired 2026-07-20 (D298 — D206 made permanent): `propose_threshold_tightenings.py` + `forge.feedback.threshold_proposer` (D073 threshold-range proposer; the axis measured flat on CPCV-p25, monoculture risk; `auto_tightened_thresholds.yaml` stays empty and the reader/fingerprint stay — determinism-load-bearing).
Retired 2026-08-06 (repo-simplification Step C; conclusions all shipped and D-cited): the tail-target sweep chain `exceedance_target_sweep.py`, `exceedance_extreme_sweep.py`, `exceedance_merge_sweep.py`, `wf_blend_sweep.py`, `wf_p10_validation.py`, `sharpe_baseline_nested_test.py`, `tail_target_headtohead.py`, `tail_lane_tradeoff.py`, `trend_tail_target_sweep.py`, `target_sweep.py` (→ the live `FORGE_TAIL_LANE_SLOTS`/`FORGE_TREND_LANE_SLOTS` values + the cpcv retarget, D336/D345-era); the winner-prior trio `winner_prior_signal_probe.py`, `winner_prior_shadow.py`, `winner_prior_stage_one.py` (programme parked, prereg `916d79109b4d` refuted); `collider_fix_sweep.py` (Q59 → `FORGE_HONEST_LABEL_SCOPE=off`); `vix_conditioner_stage_decomposition.py`, `resid_vix_construct_split.py` (D339; superseded by the inline share computation in `daily_ranker_eval.sh`); the freeze-prep set `tail_lane_model_era_split.py`, `trend_lane_arm_read.py`, `exhaustion_power_assessment.py`, `honest_cell_scorecard.py`, `export_generation_by_version.py`, `tail_target_rank_ic.py` (preregs resolved / Tier-1 A/B closed D351).
Retired 2026-08-06 (Step E2, D373 — the alpha-budget question is ANSWERED): `forge alpha-budget` (`feedback/alpha_budget.py` + `cli/alpha_budget_cmd.py` + tests) and `scripts/alpha_budget.py`. Its prereg `098ea730d5f2` resolved confirmed 2026-07-21; the exhaustion monitor it closed cannot reopen (dossier §0); the *standing* multiplicity accounting lives in `submission/search_multiplicity.py` (D310), which is unrelated code and stays. Spec/results record: `_archive/ALPHA_BUDGET_SCOPE.md`.

---

## CONFIG FILES

Under `config/`. CLI flags override YAML; YAML overrides hardcoded defaults.

| File | Controls |
|---|---|
| `forge.yaml` | Forge DB path, Crucible wiring, enumeration cap, batch size, rate-limit threshold, stall-guard window (`submission.stall_after_seconds`, D137), in-flight-depth cap (`submission.max_inflight`, D196; 0=off). (`data_root`/`log_root`/`feedback.*` cadence keys retired D247 — never read; feedback runs every iteration via `--consume-feedback`.) |
| `grammar.yaml` | The 21 grammar rules (S/C/R/X families). Operator-owned; version-bumped + archived on change. |
| `prefilter.yaml` | Per-filter thresholds (signal density, expected trades, novelty, regime exposure, permutation, auto-tune bounds). |
| `ranker.yaml` | Composite-score weights + diversification method. |
| `auto_tightened_thresholds.yaml` | RETIRED-EMPTY (`tightenings: []`, D206, permanent per D298). Retained because its fingerprint feeds `enumeration_inputs_hash` — deleting it changes the determinism identity. |
| `grammar_archive/v{N}.yaml` | Frozen copies of each prior grammar version. |

---

## FORGE STATE DB

`~/forge_data/forge.db` (DuckDB). Tables:

| Table | Holds |
|---|---|
| `submissions` | One row per submitted config. `config_hash` is unique-indexed (idempotency, hard rule #9). `status` lifecycle: `pending` (insert) → `submitted` \| `skipped_duplicate` \| `submission_failed`, then `gated` once Crucible decides — set on reconcile, on age-out, or on the D240 failed-run retirement (runner-FAILED runs from `failed_runs_*.json` are retired each poll with the aged-out sentinel `crucible_run_id`; `feedback/consumer.py`). `selection_mode` (P3.3/B7) tags each row `ranked` vs `holdout` so evals can split biased-vs-unbiased labels. |
| `batch_summaries` | Per-batch stats: size, grammar/registry version, promotion rate, prefilter rejections. |
| `pre_filter_logs` | Per-(candidate, filter) pass/score/details. |
| `verdicts` | Durable per-candidate Crucible decisions (D111): decision, decided_at, trade_count, grammar_version, full gate_results JSON. PK `crucible_run_id`, so re-gates append. Populated on every reconcile pass; survives the rolling export window. |
| `grammar_versions` | Grammar change history (version, sha256, operator initials). |
| `grammar_proposals` | Refinement proposals (pending/approved/rejected/applied). |
| `promoted_patterns` | Discovered patterns across promoted strategies. |
| `shadow_scores` | D132/F2 telemetry: per (submitted candidate, model_id) the verdict model's P(component) next to the incumbent §6.2 composite. D140/D141 add `tail_score` + `tail_model_id` (the tail-aware model's predicted worst-quartile value — `wf_p25` per D191/D192, NULL until one is trained). Written post-submission; never read by the loop. |

---

## PIPELINE SERVICES

systemd **user** services (`systemctl --user ...`). Start the writer first; stop it last.
The Crucible rows below are the **Forge-relevant subset**, not Crucible's full unit inventory —
`systemctl --user list-unit-files 'crucible-*'` for the whole set.

| Service | Runs | Role |
|---|---|---|
| `crucible-db-writer` | `start_db_writer.py` | Single-writer DuckDB process; holds the exclusive lock. All others depend on it. |
| `crucible-inbox-watcher` | `start_inbox_watcher.py` | Polls `inbox/`, validates configs, queues runs. |
| `crucible-runner@1` / `crucible-runner@2` | `start_runner.py` (templated instances) | Backtest queued runs through the full gate; write promotion decisions. Production runs the templated instances; the plain `crucible-runner.service` is inactive. |
| `crucible-gated-runs-publisher` | `export_gated_runs.py --poll-interval 60` | Exports gated-run snapshots every 60s (Forge's read path). |
| `crucible-failed-runs-publisher` | `export_failed_runs.py --poll-interval 300` | Exports `failed_runs_*.json` — runner-FAILED runs that never reach the gated export. Forge's D240 read path: the feedback consumer retires matching `submitted` rows each poll (`feedback/consumer.py` `_flush_failed_runs`) so failures stop pinning §7.3 in-flight depth. |
| `crucible-promoted-strategies-publisher` | `export_promoted_strategies.py --poll-interval 60` | Exports promoted strategies every 60s (QuantIQ's read path). |
| `crucible-component-contributions-publisher` | `export_component_contributions.py --poll-interval 60` | Exports per-promoted-portfolio contribution scores (D216); consumed by `forge healthcheck`'s soft presence check — empty until the first promotion. |
| `crucible-registry-publisher` | `export_registry.py` | Publishes the indicator registry snapshot every ~6h (timer-driven oneshot, D166; was oneshot-at-startup pre-2026-06-15). Forge re-reads the newest snapshot by mtime. |
| `crucible-universe-publisher` | `export_universe.py` | Timer-driven oneshot publishing `universe_tickers` (the underlying set enumeration draws from). |
| `crucible-refit-watcher` | `start_refit_watcher.py` | Polls `refit_inbox/` for QuantIQ re-validation requests. |
| `forge` | `forge run --loop --consume-feedback --require-real-cache --cohort-yield --regime-gate-yield --quality-rank` | The Forge daemon: generate → submit → learn. Yield-driven draws (D182/D183) + the wf_p25 quality lane (D193) are on. |

Timers (independent): `crucible-ingest-daily` (19:00, market data), `crucible-morning-digest` (06:00). **Forge timers:** `forge-ranker-eval` (05:00, daily train of both shadow models — verdict + tail-aware wf_p25 robustness, D191/D192 — + eval & eval-robustness → two clocks: `streak.jsonl` (F3 verdict, hygiene-judged once populated D284) + `rewire_streak_wfp25.jsonl` (gate-tail lane; the §8.6 tail clock retired D285), both under `~/forge_data/ranker_eval/`; `scripts/daily_ranker_eval.sh`), `forge-backup` (04:00, nightly DR backup of `forge.db` + `models/` → `~/forge_data/backups`; retention = `FORGE_BACKUP_KEEP` set on the unit, `deploy/systemd/forge-backup.service` — script default 14; `scripts/backup_forge_db.sh`), `forge-healthcheck` (hourly, daemon health → exit 0/1/2; CRITICAL marks the unit failed; `cli/healthcheck_cmd.py`, D197). Forge timer units live in `deploy/systemd/`, symlinked into `~/.config/systemd/user/`.

```
# Inspect any service:
systemctl --user status SERVICE
journalctl --user -u SERVICE -n 50 --no-pager
```
