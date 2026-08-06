# Glossary — domain terms an agent would misread

Scope: Forge/pipeline jargon. Code identifiers are findable by grep; this covers concepts.

## Pipeline outcomes

- **Gated** — Crucible finished backtesting a config and recorded a decision. NOT "passed";
  most gated runs are rejections. Forge `submissions.status` flips `submitted → gated` on reconcile.
- **Component** — a gated config Crucible accepts as a portfolio building block (Crucible assembles
  components into portfolios; see `../Crucible/docs/handoffs/PORTFOLIO_PROMOTION_DESIGN.md`).
  The component rate is Forge's live currency — the binding gate sits at promotion, not gating
  (current rates/counts: `STATUS.md` top block, or `forge status`).
- **Promotion** — full gate pass, exported to QuantIQ. Target 1–3% by month 3–6 (§1.3); >5% is
  suspicious (over-tuning to the gate).
- **The export / gated export** — `~/optbt_data/exports/gated_runs_*.json`, Crucible's rolling
  **top-10k window** of decisions. Has `grammar_version` since contracts 1.15.0. Join to
  `submissions` on `config_hash`.

## Strategy anatomy

- **Hypothesis** — the one market thesis a config declares (S1 rule): trend_continuation,
  mean_reversion, relative_value, volatility_event, event_momentum (v12+), … The allowed set is
  the contracts Literal; regime_arbitrage was dropped from enumeration in v5 (D098).
- **Directional signal vs regime gate** — directional signals generate entries; regime signals
  only gate *when* entries are allowed. Same indicator can serve both with different ops
  (e.g. hurst: `<` directional for mean_reversion, `>` regime for trend, D100).
- **Combiner** — how multiple signals merge; `cross_sectional_rank` (v12, H1) ranks a universe
  cross-sectionally instead of gating one underlying.
- **DTE bucket** — discrete days-to-expiry class (swing_short / swing_mid / …), derived as
  `k × signal horizon` from the Forge-owned table in `grammar/signal_horizon.py` (D102).
- **Factor cell** — the granularity feedback weights key on, e.g. (hypothesis, directional,
  underlying-name) (D105/D106/D108).

## Change & process terms

- **Enumeration-policy bump** — a grammar_version bump with NO `rules:` text change; the policy
  shift is Python-side (the v5–v12 norm). See `docs/architecture.md` change taxonomy.
- **Versionless change** — feedback/weight change that re-aims the draw distribution without
  changing the population; must be cold-start byte-identical (hard rule #6).
- **Cold-start** — sampler behavior with empty learned inputs (`{}` weights / no priors); pinned
  byte-identical by golden tests. `COLD_START_HYPOTHESES` (trade_rate_priors) drops poisoned
  pre-vN rows from the expected-trades prior so a hypothesis can re-learn.
- **Exploration floor** — the D067 minimum hypothesis weight; no learned tilt may starve a
  hypothesis to zero (the value is `DEFAULT_EXPLORATION_FLOOR` in `feedback/rejection_weights.py`).
- **Anti-Goodhart** — feedback rewards must track what Crucible *accepts* (component rate, D105),
  never proxies like raw trade counts (the D094 reward got Goodharted; regression tests pin this).
- **Emission proof** — before deploying enumeration changes: sample thousands of configs against
  the live registry export and verify the emitted mix shows the intended change. Recipe:
  `docs/tasks/grammar-change.md`.
- **Uncontended suite** — full `pytest` with `forge.service` STOPPED. The deploy gate; a run with
  the service live is contended and doesn't count.
- **D-number / Q-number** — entries in `IMPLEMENTATION_DECISIONS.md` / `OPEN_QUESTIONS.md`.
- **Breadth vs quality lever** — Grinold framing (IR = IC·√Breadth). The binding gate failure is
  trade count (breadth); levers that only sharpen per-trade quality have a low ceiling.
- **Quality lane / `wf_p25`** — the generation quality blend (D193, live): a deterministic
  robustness ridge predicting `target_wf_p25` (Crucible's walk-forward Sharpe FLOOR — the
  worst-quartile gate) folded into the §6.2 ranking prior via `prior := P(component) × tail_norm`.
  Ranking-only (no grammar/gate change); `--quality-rank` on the unit, journal `quality_rank:
  wf_p25 BLEND ACTIVE`. Predicts DOWNSIDE robustness, not the peak. Distinct from the
  threshold-0 `regime_stress` tail filter.
- **Yield-map axes / cohort-yield / regime-gate-yield** — finer-grained component-rate feedback
  weighting added on top of the D105/D106 reward (D182/D183, live). `--cohort-yield` makes the
  cohort draw (`cross_sectional_rank` vs confluence) yield-driven instead of a fixed share;
  `--regime-gate-yield` weights the regime-gate pick by its realized component yield. Versionless
  feedback (cold-start byte-identical); journal `cohort_yield_weights:` / `regime_gate_yield:`.

## Operations terms

- **The limiter / §7.3 / "blocked"** — `forge run` refuses a new batch until ≥80% of the oldest
  in-flight batch is gated. "blocked: prev batch N% gated" in the journal is normal backpressure.
- **§7.3 backpressure / `max_inflight`** — the aggregate in-flight-depth block (D196/D200): a third
  independent block reason beside the per-batch completion fraction and the D137 stall guard. Blocks
  when live `submitted` depth (rows newer than the flush watermark) exceeds the `max_inflight` cap
  (`submission.max_inflight` in forge.yaml; 0 = off, byte-identical). Journal: "blocked: in-flight
  depth N exceeds cap". Throttles Forge, never Crucible's gate (hard rule #3).
- **Aged-out flush / sentinel** — the consumer marks dead `submitted` rows as gated with a
  nil-UUID sentinel once they fall behind the export watermark (`max(decided_at) −
  STRANDED_AFTER`, currently 5 days — `feedback/consumer.py` owns the value; D110 mechanism,
  history: D052 → D061 → D110 wedges). The D240 failed-run retirement reuses the same sentinel.
- **Reconcile** — feedback consumer joining the gated export against `submissions` and flipping
  statuses; since D240 it also joins Crucible's `failed_runs_*.json` export and retires
  runner-FAILED rows the same pass. Runs every loop iteration.
- **Inbox** — `~/optbt_data/inbox/`; Forge writes one JSON per config atomically
  (tmp-then-rename) via `crucible_contracts.submit_candidate`.
- **Registry / RegistrySnapshot** — Crucible's indicator catalog, read from
  `exports/registry_snapshot_*`; its hash is part of the determinism identity.
- **Timestamp eras** — DB/journal records before 2026-06-07 are PDT (old box), after are UTC.
  Cohort implications + the v9 cutover trap: `docs/tasks/investigate-live.md`.
- **Funnel compare** — `crucible funnel --compare vA vB` (Crucible-side) attributes a
  grammar-versioned change by cohort.
- **`forge healthcheck`** — diagnostic command + hourly timer (D197) detecting the "alive but
  unproductive" daemon states systemd can't see (wedged loop, stalled pipeline, broken side-timers,
  un-adopted contracts pin). Reads journal/filesystem/version (no DB snapshot); exit code = worst
  level (0 OK / 1 WARN / 2 CRITICAL), CRITICAL surfaces via the failed-unit routine. Answers
  *is it alive and producing?* — contrast `forge status`.
- **`forge status`** — diagnostic command (D198) pretty-printing the two learning-signal clocks the
  daily ranker-eval timer writes (F3 verdict-ranker AUC margin + §8.6 `wf_p25` tail Spearman, each
  with its consecutive-PASS streak and trend). Read-only over JSONL, no DB. Answers *is the stream
  improving?* — contrast `forge healthcheck`.
