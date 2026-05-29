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
)

TABLE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "submissions",
        "batch_summaries",
        "pre_filter_logs",
        "grammar_versions",
        "grammar_proposals",
        "promoted_patterns",
    },
)
