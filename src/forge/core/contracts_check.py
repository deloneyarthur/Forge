"""Startup compatibility check against `crucible_contracts`.

Hard rule #2: no imports from Crucible internals. All inter-system access goes
through `crucible_contracts`. This module enforces SemVer compatibility at CLI
entry (§13.5); a mismatch halts execution before any further work.

`FORGE_EXPECTED_CONTRACT_VERSION` is the version this build of Forge was
written against. Bump when adopting a new contracts release; major-version
bumps are deliberate events that may require code changes elsewhere.
"""

from __future__ import annotations

from crucible_contracts import (
    CONTRACT_VERSION,
    SchemaVersionMismatch,
    validate_schema_version,
)

# 1.18.0 (D123): IndicatorMetadata rank-path flags (`rank_per_name_coherent`,
# `market_wide_by_design`), fail-closed defaults — together they reconstruct
# the D118 rank-exclusion key (excluded == NOT coherent AND NOT market_wide)
# so the v16 enumeration policy can key on the registry instead of explicit
# id sets. Additive/minor: pre-1.18 snapshot files still validate (fields
# absent → False/False == excluded); the first republished snapshot rotates
# `registry_hash` — a contracts boundary, not drift (the D118 45≡45 manual
# id-set check retires here).
# 1.17.0 (D121): universe-export freshness bound — the enumerator's
# `load_universe_tickers_from_export` call now raises `StaleExportError`
# (a `QueryError` subclass) when the newest export exceeds max_age_days=35,
# instead of silently enumerating a stale pool after a dead monthly publisher.
# 1.16.0 (D109): the additive CombinerSpec rank fields (rank_k /
# rebalance_frequency / direction_mode) + the event_momentum hypothesis literal +
# the post_event_drift family literal — the H1 cross_sectional_rank combiner and
# the H2 event_momentum hypothesis (v12) construct and validate against these.
# Additive/minor: §13.5 SemVer compatibility is MAJOR-only, so this pin is
# hygiene + suite-correctness (the editable install already serves 1.16.0).
# 1.15.0 (D106): RunResult.grammar_version rides the gated export (Crucible
# 9995f81, shipped 2026-06-08 00:10Z in response to the D105 yield-map reply's
# "export carries no version field" note). extra="forbid" makes this a
# REQUIRED adoption: pre-1.15.0 readers reject the new export rows outright.
# 1.19.0 (D176): hash-excluded StrategyConfig.source + search_n_trials for the
# meta-king A3 submission arm (Crucible 30b8fa9; D096 provenance pattern, no
# config_hash churn). Required adoption — installed contracts is 1.19.0, so the
# pin must match or check_contracts_version fails every CLI startup.
# 1.20.0 (D200): portfolio resolved-provenance fields (PromotedPortfolio.vol_target_annual,
# PortfolioComponent.asof_universe_rule) + drop BOOK-level rebalance_freq from the
# portfolio identity (Crucible f8ef52d, Path A engine-core). NO-OP for Forge — verified:
# additive minor (existing models unchanged); the dropped field is the PORTFOLIO
# config_hash (assembly-side, Forge neither computes nor reads it); and the per-component
# CombinerSpec.rebalance_frequency Forge generates (sampler.py) stays identity-bearing
# inside each StrategyConfig.config_hash, so Forge config_hashes are UNCHANGED. Pin-only.
# 1.21.0 (D211): premium-R exit family — KNOWN_EXIT_IDS += delta_floor_stop / premium_r_target /
# premium_r_time_stop (18->21); STOP_LOSS_EXIT_IDS += delta_floor_stop; SelectorSpec.stop_atr_mult
# (None-sentinel, DROPPED from StrategyConfig.config_hash when unset — contracts' golden-hash suite
# confirms byte-identity). NO-OP for Forge — verified: config_hash UNCHANGED (Forge never sets
# stop_atr_mult so it drops); MANDATORY_EXIT_IDS unchanged (every determinism golden + e1_mandatory
# safe); STOP_LOSS_EXIT_IDS grew but no Forge config composes delta_floor_stop (the E2
# at_most_two_stop_loss count is unchanged); KNOWN_EXIT_IDS is not imported by Forge; the 3 new exit
# ids are grammar-gated (Forge S3.5 E2, unbuilt) so they are NOT auto-enumerated — they go live only
# when Forge bumps grammar to enumerate them. Pin-only; full suite green confirms.
# 1.22.0 (D216): component_contributions export reader for the Layer-1
# decorrelated-supply signal — ComponentContribution (frozen: portfolio_id,
# correlation_to_incumbent, marginal_sharpe; marginal_sharpe may be NEGATIVE — do
# not clamp) + load_component_contributions_from_export + COMPONENT_CONTRIBUTIONS_SCHEMA
# (Crucible afbe737, reply to PROMPT_CRUCIBLE_CONTRIB_LOADER_IN_CONTRACTS). NO-OP for
# Forge — verified: purely ADDITIVE (no existing model/hash changed → no major-guard
# trips); nothing in Forge imports the loader yet (the estimand re-aim that consumes it
# is HELD until the export carries real promoted-book data, currently empty). Cold-start
# {} on absent/empty/unknown-schema. Pin-only.
# 1.23.0 (2026-07-05 incident): failed-run feedback reader — FailedRun (frozen:
# config_hash, finished_at, error_category; error_category an OPEN string so new
# Crucible failure taxonomies don't break the contract) + load_recent_failed_runs_from_export,
# mirroring the gated-run loader. Consumed by feedback.consumer._flush_failed_runs so
# runner_failure / pool_break runs (which never enter gated_runs) are retired from the
# `submitted` set instead of pinning §7.3 in-flight backpressure until the 5-day age-out.
# Purely ADDITIVE (no existing model/hash changed → no major-guard trips). Forge DOES import
# the loader (unlike the D216 pin-only add): the reconcile wiring lands in the same commit.
# 1.24.0 (D243 coordinated F1/F3/F4 bump): GatedRun.failure_buckets (auto-computed coarse
# failure labels) + FAILURE_BUCKET_SEVERITY_ORDER + failure_bucket_for_gate/…_from_gate_results
# helpers + StrategyConfig.mechanism/regime (free-str, None-default, hash-excluded) +
# FORGE_VOCABULARY_FILENAME_TEMPLATE. All ADDITIVE (no existing model/hash changed → no major
# trip). Forge does NOT yet consume any of it — feature adoption (bucket-only training, mechanism/
# regime stamping, vocab artifact, freeze ledger) stays DEFERRED behind ve-supply per D243; this
# pin is version-adoption ONLY. NOT deferrable like prior additive pins (D124 trap): failure_buckets
# lands on GatedRun, a PARSED gated-runs-export model with extra="forbid" — the running daemon holds
# its boot-time model in memory, so it MUST be restarted onto 1.24.0 BEFORE Crucible's exporter
# republishes with the field, else every reconcile fail-loops on extra_forbidden → §7.3 stall.
# 1.25.0 (2026-07-06, forward-compat hardening after the D244/D245 asymmetric-upgrade traps):
# adds `parse_forward_compatible(model_cls, data)` — a tolerant RE-READ that, when strict
# validation fails with ONLY extra_forbidden errors, prunes the purely-additive unknown keys,
# warns once, and retries (so a long-running process holding a pre-bump model tolerates a new
# minor field instead of failing the run — the exact runner-side `other`-failure cause on 07-06).
# Changes NO parsed model (validators.py only) → unlike 1.24.0 this pin is DEFERRABLE for Forge's
# restart: no extra_forbidden trap on the running 1.24.0-in-memory daemon. Version-adoption ONLY
# (Forge does not yet call parse_forward_compatible; wiring it into reconcile is a separate build).
FORGE_EXPECTED_CONTRACT_VERSION: str = "1.25.0"


def check_contracts_version() -> str:
    """Validate the installed `crucible_contracts` version is compatible.

    Returns the installed version string on success. Raises
    `SchemaVersionMismatch` on major-version mismatch.
    """
    validate_schema_version(FORGE_EXPECTED_CONTRACT_VERSION, CONTRACT_VERSION)
    return CONTRACT_VERSION


__all__ = [
    "FORGE_EXPECTED_CONTRACT_VERSION",
    "SchemaVersionMismatch",
    "check_contracts_version",
]
