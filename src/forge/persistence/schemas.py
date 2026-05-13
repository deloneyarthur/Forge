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
