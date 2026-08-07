"""DDL for Forge's own DuckDB. See FORGE_DESIGN.md §9.1.

Idempotent — every statement is `CREATE TABLE IF NOT EXISTS` so `ensure_schema`
can be called on every CLI entry without risk. The `submissions.config_hash`
unique index implements hard rule #9 (§13.4): a given config hash can only be
submitted once.
"""

from __future__ import annotations

from typing import Final

SCHEMA_VERSION: Final[str] = "0.1.0"

DDL_STATEMENTS: Final[tuple[str, ...]] = (
    """
    CREATE TABLE IF NOT EXISTS submissions (
        forge_candidate_id  UUID PRIMARY KEY,
        forge_batch_id      UUID NOT NULL,
        config_hash         VARCHAR(16) NOT NULL,
        config_json         JSON NOT NULL,
        submitted_at        TIMESTAMP NOT NULL,
        status              VARCHAR(20) NOT NULL,
        crucible_run_id     UUID
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_config_hash ON submissions(config_hash)",
    # P3.3 (B7): how a submission was selected — 'ranked' (learned §6.2 ranking) vs
    # 'holdout' (the seeded exploration bypass). Lets evals split biased-vs-unbiased
    # labels. Idempotent ALTER; pre-P3.3 rows are NULL (treated as 'ranked').
    "ALTER TABLE submissions ADD COLUMN IF NOT EXISTS selection_mode VARCHAR(16)",
    """
    CREATE TABLE IF NOT EXISTS batch_summaries (
        forge_batch_id      UUID PRIMARY KEY,
        batch_size          INTEGER NOT NULL,
        submitted_at        TIMESTAMP NOT NULL,
        completed_at        TIMESTAMP,
        promotion_rate      DOUBLE,
        common_failures     JSON,
        grammar_version     VARCHAR(20) NOT NULL,
        registry_version    VARCHAR(20) NOT NULL
    )
    """,
    # D062: per-batch pre-filter rejection counts (first-failing filter per
    # rejected candidate). Distinct from `common_failures` which counts
    # Crucible-side gate failures populated post-feedback. Idempotent ALTER
    # so existing prod DBs pick up the column on next `db_connection` open.
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS prefilter_rejections JSON",
    # D064: per-hypothesis pre-filter rejection counts — same first-failing
    # filter semantics as `prefilter_rejections` but keyed by hypothesis so
    # we can see *which* filter kills *which* hypothesis. Surfaces the
    # "mean_reversion / trend_continuation absent from submissions"
    # diagnosis: D062's aggregate showed novelty=28% as a major bucket but
    # mean_reversion has 1 historical submission and trend_continuation has
    # 0, so neither hypothesis can be the source of novelty rejections —
    # they're killed by an earlier filter before reaching novelty.
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS prefilter_rejections_by_hypothesis JSON",
    # D085 / audit M-14 + H-3: reproducibility metadata. `seed` is the enumeration
    # seed for the batch; `enumeration_inputs_hash` fingerprints the auto-tightenings
    # YAML + universe pool that shadow the sampler but aren't in grammar_version/
    # registry_version. Together with those two, they are the full §13.1 identity
    # needed to reproduce a recorded batch (hard rule #6). Idempotent ALTER.
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS seed BIGINT",
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS enumeration_inputs_hash VARCHAR(16)",
    # D096 — pre-filter funnel upstream-stage counts
    # (FUNNEL_INSTRUMENTATION_FORGE.md Part B). `batch_size` is the
    # post-diversifier submitted count; the funnel also needs the two stages
    # above it: `enumerated_count` = total configs run through the battery
    # (len(reports)) and `survived_count` = configs that passed the whole
    # battery (sum r.passed). With `prefilter_rejections` (D062) these satisfy
    # the funnel invariant sum(rejections) == enumerated - survived.
    # `enumerated_by_hypothesis` is the per-hypothesis enumerated breakdown —
    # the "which grammar branch" annotation Crucible's funnel wants on the
    # enumerated stage. Idempotent ALTERs so prod DBs pick them up on open.
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS enumerated_count BIGINT",
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS survived_count BIGINT",
    "ALTER TABLE batch_summaries ADD COLUMN IF NOT EXISTS enumerated_by_hypothesis JSON",
    """
    CREATE TABLE IF NOT EXISTS pre_filter_logs (
        forge_candidate_id  UUID,
        filter_name         VARCHAR(64),
        passed              BOOLEAN,
        score               DOUBLE,
        details_json        JSON,
        evaluated_at        TIMESTAMP,
        PRIMARY KEY (forge_candidate_id, filter_name)
    )
    """,
    # D076 / Q16 — pre_filter_logs historically only carried rows for
    # configs that survived the battery AND submitted successfully (called
    # from `submitter.py`). Rejected configs never got a row, so the
    # table's per-filter pass-rate was a meaningless 100%. These two
    # additive columns let the battery write one row per (config, filter)
    # for rejected candidates too, keyed by `config_hash` since rejected
    # configs never land in `submissions`. Idempotent ALTERs so existing
    # prod DBs pick them up on the next `db_connection` open.
    "ALTER TABLE pre_filter_logs ADD COLUMN IF NOT EXISTS config_hash VARCHAR(16)",
    "ALTER TABLE pre_filter_logs ADD COLUMN IF NOT EXISTS forge_batch_id UUID",
    """
    CREATE TABLE IF NOT EXISTS grammar_versions (
        version             VARCHAR(20) PRIMARY KEY,
        rule_count          INTEGER NOT NULL,
        yaml_sha256         VARCHAR(64) NOT NULL,
        changed_at          TIMESTAMP NOT NULL,
        change_type         VARCHAR(20) NOT NULL,
        change_description  TEXT,
        operator_initials   VARCHAR(10)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS grammar_proposals (
        proposal_id         UUID PRIMARY KEY,
        proposed_at         TIMESTAMP NOT NULL,
        proposal_type       VARCHAR(20) NOT NULL,
        proposal_yaml       TEXT NOT NULL,
        rationale           TEXT NOT NULL,
        evidence_json       JSON NOT NULL,
        status              VARCHAR(20) NOT NULL,
        decided_at          TIMESTAMP,
        decided_by          VARCHAR(64)
    )
    """,
    # D111 — durable per-candidate Crucible verdicts. The gated-runs export is
    # a rolling top-10k window, so without this table the per-candidate
    # decision, gate values, and realized trade_count vanish once a row rolls
    # off (the 2026-06-09 review found only 13.2% of submissions had a
    # recoverable verdict). PK is `crucible_run_id`: a Crucible re-gate of the
    # same config is a NEW run_id and appends rather than overwrites, so the
    # table keeps verdict history per config. Written by
    # `forge.persistence.verdicts.record_verdicts` on every reconcile pass.
    """
    CREATE TABLE IF NOT EXISTS verdicts (
        crucible_run_id     UUID PRIMARY KEY,
        config_hash         VARCHAR(16) NOT NULL,
        decision            VARCHAR(20) NOT NULL,
        decided_at          TIMESTAMP NOT NULL,
        trade_count         INTEGER,
        grammar_version     VARCHAR(20),
        gate_results        JSON NOT NULL,
        recorded_at         TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_verdicts_config_hash ON verdicts(config_hash)",
    # D316 (Theme 2c) — label provenance. The ve ghost episode (D289/D290) cost
    # five weeks of archaeology to identify which stored verdicts were built on
    # stale features; these columns make the next era cut a filter flip.
    # `source_export` = the gated-runs export filename the row was reconciled
    # from (NULL for the DB-fallback path + pre-D316 rows); `contracts_version`
    # = the installed crucible_contracts at recording time. Idempotent ALTERs.
    "ALTER TABLE verdicts ADD COLUMN IF NOT EXISTS source_export VARCHAR",
    "ALTER TABLE verdicts ADD COLUMN IF NOT EXISTS contracts_version VARCHAR(20)",
    # D330 — LANE provenance. Crucible evaluates in two stages: `standard_window`
    # (a cheap 5yr SCREEN that structurally cannot produce an honest-coverage
    # component) and `fullhist_refit` (the floor-anchored validator, the only
    # path into the component pool). 94% of our gated feed is the screen, whose
    # honest-label rate is 0.077%, while 98%+ of all honest labels come from the
    # ~9% that is not — so the D128 label is DILUTED by a lane that cannot
    # produce it, not merely starved. Worse, a config appears in BOTH lanes with
    # OPPOSITE labels (26 of 363 paired configs measured 2026-07-22). Scoping the
    # label needs the lane recorded per row. Both fields have been on the wire
    # since contracts 1.27.0 and existed in Forge only as a comment until D330.
    # Idempotent ALTERs; NULL on legacy rows and on any producer that omits them.
    "ALTER TABLE verdicts ADD COLUMN IF NOT EXISTS measurement_basis VARCHAR",
    "ALTER TABLE verdicts ADD COLUMN IF NOT EXISTS fullhist_refit_of VARCHAR",
    # D375 — REFIT-LANE provenance (`RunResult.refit_selection`, contracts 1.44.0). Crucible's
    # stage-two scanner used to drain newest-first only; from 2026-08-06 17:10 PDT it reserves a
    # quality sub-budget ranked by margin over both promotion bars. The tag names which sub-lane
    # queued the refit, and the field exists because we asked for it (D370 §5): a quality-ordered
    # cohort is CONDITIONED ON STAGE-ONE METRICS, so pooling it with the newest-first drain would
    # silently break the like-conditioned version-delta yardstick that produced the v55 read.
    # Vocabulary is a FREE STRING by their design (the 1.24.0 vocabulary-growth lesson — a Literal
    # would have hard-failed our reader on any new member, the D261/D342 hazard): NULL = the
    # unconditioned newest-first drain and is the cohort marker, 'quality_margin' = the reserved
    # sub-lane, 'promote_stamp_recovery' = the 31-config requeue of the D370 stamp-crash cohort.
    # Idempotent ALTER; NULL on legacy rows and on any producer that omits it.
    "ALTER TABLE verdicts ADD COLUMN IF NOT EXISTS refit_selection VARCHAR",
    """
    CREATE TABLE IF NOT EXISTS promoted_patterns (
        pattern_id          UUID PRIMARY KEY,
        discovered_at       TIMESTAMP NOT NULL,
        pattern_type        VARCHAR(40),
        pattern_json        JSON NOT NULL,
        promoted_count      INTEGER NOT NULL,
        sample_size         INTEGER NOT NULL
    )
    """,
    # D132 / F2 — learned-verdict-model shadow telemetry. One row per
    # (submitted candidate, model): the model's calibrated P(component) next
    # to the incumbent §6.2 composite score, so `forge ranker-model eval` can
    # compare both against later verdicts. Written by
    # `forge.ranking.shadow.run_shadow_scoring` AFTER selection + submission —
    # never read by the production loop (F3 is a separate gate).
    """
    CREATE TABLE IF NOT EXISTS shadow_scores (
        forge_candidate_id  UUID NOT NULL,
        model_id            VARCHAR(64) NOT NULL,
        model_score         DOUBLE NOT NULL,
        composite_score     DOUBLE NOT NULL,
        scored_at           TIMESTAMP NOT NULL,
        PRIMARY KEY (forge_candidate_id, model_id)
    )
    """,
    # D140 (tail-aware T1) — the tail model's predicted worst-quartile robustness
    # (default cpcv_p25) recorded next to the P(component) shadow score, plus which
    # robustness artifact produced it. NULL until a robustness model is trained /
    # for pre-existing rows. Telemetry only — the production loop NEVER reads these
    # (tail wiring is gated; this just accrues eval data). Idempotent ALTERs so the
    # live DB picks them up at the next service restart.
    "ALTER TABLE shadow_scores ADD COLUMN IF NOT EXISTS tail_score DOUBLE",
    "ALTER TABLE shadow_scores ADD COLUMN IF NOT EXISTS tail_model_id VARCHAR(64)",
    # Comparator fix — the model-free §6.2 hygiene composite (prior slot zeroed),
    # recorded next to `composite_score` because that column stores whatever score the
    # production ranker ordered by: under gate-tail mode (P1.1) that is the lane's own
    # value, so evals reading it as "the incumbent" compare the lane against itself.
    # This column is the stable incumbent across lane-mode flips. NULL for rows recorded
    # before the fix / before the daemon restart that activates it.
    "ALTER TABLE shadow_scores ADD COLUMN IF NOT EXISTS hygiene_score DOUBLE",
)

TABLE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "submissions",
        "batch_summaries",
        "pre_filter_logs",
        "grammar_versions",
        "grammar_proposals",
        "promoted_patterns",
        "verdicts",
        "shadow_scores",
    },
)
