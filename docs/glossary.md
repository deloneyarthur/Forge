# Glossary — domain terms an agent would misread

Scope: Forge/pipeline jargon. Code identifiers are findable by grep; this covers concepts.

## Pipeline outcomes

- **Gated** — Crucible finished backtesting a config and recorded a decision. NOT "passed";
  most gated runs are rejections. Forge `submissions.status` flips `submitted → gated` on reconcile.
- **Component** — a gated config Crucible accepts as a portfolio building block (Crucible assembles
  components into portfolios; see `../Crucible/docs/handoffs/PORTFOLIO_PROMOTION_DESIGN.md`).
  The component rate (~1–2%) is Forge's live currency — promotions are still 0.
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
- **Exploration floor** — minimum 0.05 hypothesis weight (D067); no learned tilt may starve a
  hypothesis to zero.
- **Anti-Goodhart** — feedback rewards must track what Crucible *accepts* (component rate, D105),
  never proxies like raw trade counts (the D094 reward got Goodharted; regression tests pin this).
- **Emission proof** — before deploying enumeration changes: sample thousands of configs against
  the live registry export and verify the emitted mix shows the intended change.
- **Uncontended suite** — full `pytest` with `forge.service` STOPPED. The deploy gate; a run with
  the service live is contended and doesn't count.
- **D-number / Q-number** — entries in `IMPLEMENTATION_DECISIONS.md` / `OPEN_QUESTIONS.md`.
- **Breadth vs quality lever** — Grinold framing (IR = IC·√Breadth). The binding gate failure is
  trade count (breadth); levers that only sharpen per-trade quality have a low ceiling.

## Operations terms

- **The limiter / §7.3 / "blocked"** — `forge run` refuses a new batch until ≥80% of the oldest
  in-flight batch is gated. "blocked: prev batch N% gated" in the journal is normal backpressure.
- **Aged-out flush / sentinel** — the consumer marks dead `submitted` rows as gated with a
  nil-UUID sentinel once they fall behind the export watermark (`max(decided_at) − 8d`, D110;
  history: D052 → D061 → D110 wedges).
- **Reconcile** — feedback consumer joining the gated export against `submissions` and flipping
  statuses; runs every loop iteration.
- **Inbox** — `~/optbt_data/inbox/`; Forge writes one JSON per config atomically
  (tmp-then-rename) via `crucible_contracts.submit_candidate`.
- **Registry / RegistrySnapshot** — Crucible's indicator catalog, read from
  `exports/registry_snapshot_*`; its hash is part of the determinism identity.
- **Timestamp eras** — DB/journal records before 2026-06-07 are PDT (old box), after are UTC.
  Cohort implications + the v9 cutover trap: `docs/tasks/investigate-live.md`.
- **Funnel compare** — `crucible funnel --compare vA vB` (Crucible-side) attributes a
  grammar-versioned change by cohort.
