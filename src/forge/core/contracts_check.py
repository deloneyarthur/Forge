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
# Changes NO parsed model (validators.py only) → the 1.25.0 pin was deferrable; 1.26.0 (below)
# is what Forge actually consumes.
# 1.26.0 (2026-07-06): the gated/failed export LOADERS (load_recent_{gated,failed}_runs_from_export)
# now parse each row via parse_forward_compatible instead of strict model_validate. Forge's
# reconcile read path (feedback.consumer) thus SELF-HEALS on a future additive Crucible export
# field instead of fail-looping on extra_forbidden (the D244 read-side trap) — so this closes the
# read-side hole the way the runner restart (D249) closed Crucible's re-read side. Byte-identical
# today (tolerance only fires on extra_forbidden; determinism paths unaffected — no model change).
# The RUNNING daemon must restart onto 1.26.0 to get the tolerant loaders (this pin's deploy DOES
# restart, unlike D249's deferral) — safe + byte-identical (models unchanged since 1.24.0).
# 1.27.0 (2026-07-08, Crucible DSR Q4): adds two OPTIONAL RunResult fields — `measurement_basis`
# (standard-window vs fullhist-refit, killing the alpha-budget basis-trap class) and
# `fullhist_refit_of`. Purely additive; Forge parses no model that breaks, and the 1.25/1.26
# forward-compat tolerance covers the new keys. Adopted (not just tolerated) so Forge↔Crucible
# run on the same contracts version; folded into the v25 deploy (D257/D258) per operator.
# 1.28.0 (2026-07-09, Crucible ivol reclassification): adds ONE family-literal value —
# `idiosyncratic_vol` (ivol split off `volatility` so §3.5 C1 will permit `ivol_lo` stacked on a
# volatility gate — the validated MR lever, wired later in v26). INCIDENT-DRIVEN adopt: Crucible
# published a registry snapshot USING the new family before Forge spoke 1.28.0, so the running
# 1.27.0 daemon failed EVERY poll with `literal_error: idiosyncratic_vol` on RegistrySnapshot (the
# asymmetric-upgrade trap, registry-side — D245 class; the parse hole, not the version check, which
# only raises on MAJOR mismatch). Purely additive; enumeration byte-identical (ivol is not
# enumerated by Forge; rv_rank/vol_regime/realized_skew stay volatility). See D261.
# 1.29.0 (2026-07-09, Crucible reply to the D261 outage relay): adds
# `parse_skipping_unknown_literals` — the shared tolerant reader for the unknown-enum face
# (drops `skip_in` collection elements with an unknown Literal member + prunes additive
# fields; strict otherwise). PURELY ADDITIVE (a new function, no Literal/vocab change) → cannot
# reproduce the outage. Forge wires it into the registry loader (D262) and adopts the pin so
# `contracts pin==installed`. Crucible's Ask-1 sequencing (vocabulary additions lead by a
# consumer-adoption handshake; the export-side commit IS the publish) is agreed. See D262.
# 1.30.0 (2026-07-12, Crucible 253da67): adds ONE Literal value —
# `PromotedPortfolio.weighting_scheme += "explicit"` (operator-fixed maximin per-component
# weights queued verbatim; identity-bearing → feeds compute_config_hash). The publisher-side
# crossing-unblock for the FIRST full-gate portfolio promote (pure_sue175) — reconstruction
# was fail-looping on `literal_error` so promoted_portfolios stayed n=0. NO-OP for Forge —
# verified: this literal lives on `PromotedPortfolio`, which Forge NEVER constructs OR parses
# (Forge's Crucible reads are get_recent_gated_runs / get_promoted_strategies → GatedRun only;
# the changed model is QuantIQ-facing). So — UNLIKE the D261 registry-family literal Forge DOES
# read — there is no read-face or inbox-face exposure in EITHER direction, and no D261-Ask-1
# consumer-adoption handshake is owed (Forge is not a weighting_scheme consumer). Enumeration
# byte-identical (no consumed model changed). §13.5 major-check already passes (both major 1);
# this pin is adoption hygiene — the exact-match test_expected_contract_version_matches_installed
# is the forcing function (red until adopted, which would NO-GO deploy-preflight). See D267.
# 1.31.0 (2026-07-13, Crucible cbb8671): adds `load_earnings_covered_symbols_from_export` (+ its
# format registration) — the earnings-coverage MANIFEST loader promised for the D268 stopgap
# (the durable fix that will retire Forge's hardcoded `_NO_EARNINGS_UNDERLYINGS` list). PURELY
# ADDITIVE (a new query function; no model/Literal/vocab change; verified diff 253da67..cbb8671:
# queries.py + formats.py + tests only) → NO-OP for the running daemon; Forge does not call it
# yet. WIRING the manifest is its OWN operator-gated grammar bump (proposal to follow — it
# changes underlying-pool emission); this pin is adoption hygiene per the D262/D267 discipline.
# 1.32.0 (2026-07-20, Crucible 0bc45a8): adds `load_universe_tiers_from_export` + `UniverseTiers`
# — the tiered universe reader (their D291 reply; tier-3 unpin). ADOPTED WITH WIRING in the same
# v41 bump (D292): `_load_underlyings` moves off the flattened reader (identical union by
# contract — and REQUIRED before Crucible retires the transition fold, which would shrink the
# flattened read 118 -> 24), true-tier stamping + the xsect tier-3 exploration share ride the
# tiered view. The deploy relay carries the adoption confirmation that licenses fold retirement.
# 1.33.0 (2026-07-20, Crucible 150e368): `StrategyConfig.tier` widens ge=1 -> ge=0 (tier=0 = the
# explicit all-eligible union scope, their §20 universe-union-ranking pin — the fix for the
# emergent-pool defect their xsect correction disclosed). PURELY PERMISSIVE for Forge (we emit
# 2/3 single-name, constant 2 on xsect since v42/D294 — never 0; stamping 0 waits on their §20
# engine pin + an explicit ask). Pin-only adopt riding the v42 bump per the D262/D267 discipline.
# 1.34.0 (2026-07-21, Crucible cd19305): `load_refutations_from_export` + EXPORT_LAYOUT
# `refutations*.json` — the consumer path for Crucible's docs/refutations.yaml (D313 reply's
# "blessed consumption path" ask, answered same-day). Free-form dicts (vocabulary grows without a
# literal_error wedge), stale-guarded, empty-on-cold. PURELY ADDITIVE for Forge — nothing reads it
# yet (refutations wiring is a separate operator-gated proposal). Pin-only adopt riding the v44
# bump (the exact-match forcing test was red on 1.34.0-installed vs the 1.33.0 pin once the
# editable source moved; v44 is the co-adoption window, as v41/v42 rode 1.32.0/1.33.0). See D317.
# 1.35.0 (2026-07-21, Crucible f5631d7): adds a `lot_floor` Literal to `SizerSpec.mode` (small-
# capital tradeability). NOT a no-op (CORRECTED post-deploy): the registry export ALREADY offered
# `lot_floor` as a sizer_mode, Forge DOES construct SizerSpec during enumeration, and the pre-adopt
# 1.34.0 daemon was FAILING whole iterations on it (`literal_error` on `mode` → iteration skipped,
# no batch). Adopting 1.35.0 makes the mode valid and clears the failures (verified: 0 failed
# iterations post-restart vs the old daemon's lot_floor aborts). No consumed model/hash changed →
# no major-guard trip; a valid lot_floor config enumerates byte-identically, it just no longer
# throws. Adopted in the D326 restart-deploy. See D327.
# 1.36.0 (2026-07-23, Crucible ac9e8f5 "selection provenance on StrategyConfig"): adds THREE
# OPTIONAL fields — `selection_rank`, `selection_pool_size`, `prefilter_sample`. This is the bump
# WE asked for: Crucible could not verify any Forge selection claim because a submitted config
# carried no rank and no pool size, making our measurements "unverifiable assertions" from their
# side (their 2026-07-22 §6). `prefilter_sample` is the explicit marker their condition #1 required
# before we may run the prefilter-holdout campaign — the instrument for the ONE DSR charge both
# repos agree is real and currently unmeasured (D330). PIN-ONLY adopt: Forge does not yet EMIT any
# of the three; all are optional-with-None and verified HASH-EXCLUDED, so §13.4 idempotency and
# hard-rule-#6 determinism are untouched and stamping them later is a separate, safe increment.
# Sequencing is the agreed one (bump -> consumer adopts -> producer emits), and this is the adopt.
# 1.37.0 (2026-07-23, Crucible 9d2d4a9): REPLACES the 1.36.0 `prefilter_sample` bool with
# `selection_arm: Literal["ranked","exploration_holdout","prefilter_sample"] | None`. Forge
# caught that the population axis is TERNARY, not binary: the exploration holdout is
# ranker-unselected but prefilter-SELECTED (guards the ranker hazard only), while a true
# grammar-honest estimate must be unselected by BOTH stages. A bool cannot name three arms.
# The bool had zero emitted rows so nothing is lost. Forge EMITS this one (D333 cont.):
# ranked->"ranked", holdout->"exploration_holdout", young_explore->None (biased, no clean
# arm). Hash-excluded (verified) so idempotency/determinism untouched; adopt-before-emit.
# 1.38.0 (2026-07-23, Crucible b07e42e): forward-compatible promoted-portfolio READER —
# `load_promoted_portfolios_from_export` now tolerates additive fields on re-read instead of
# strict-validating (the same read-side hardening as the 1.26.0 gated/failed loaders). NO
# StrategyConfig model change, so PIN-ONLY adopt, no Forge code change; a forward-compatible
# reader is strictly safer for our promoted-config consumption. Also carries the D334 prune-
# message reword (1d80109). Minor mismatch does NOT halt startup (validate_schema_version
# raises on MAJOR only), so the un-adopted window was benign — adopting to keep pin==installed
# per the bump->adopt discipline and to pick up the safer reader.
# 1.39.0 (2026-07-24, Crucible c625ba8): `generation_arm` ("prior_on"/"prior_off") +
# `generation_prior_id` on StrategyConfig — a SEPARATE axis from `selection_arm` (that says
# which selection population a config came from; this says how its params were drawn), added
# for a prior-ON/prior-OFF generation A/B. Additive and hash-excluded, which for that A/B is
# the precondition rather than tidiness: the two arms differ only in draw weights over one
# population, so if the arm entered the hash an identical config drawn both ways would dedup
# as two strategies and the comparison would measure dedup instead of the prior.
# PIN-ONLY adopt, no Forge code change — and note we deliberately EMIT NEITHER FIELD: the
# generation prior those fields exist for was PARKED on 2026-07-24 (its honest-arm effect is
# p90 +0.0087, needing ~20k/arm to resolve — `v50-winner-neighborhood-priors.md` §8.0), so the
# A/B is withdrawn and Crucible's "clear to emit" GO stands deliberately unused. Adopting
# anyway to keep pin==installed per the bump->adopt discipline; the fields default to None and
# their absence maps to "unset", never to the control arm.
# 1.40.0 (2026-08-01, Crucible): `generation_arm` WIDENED to
# Literal["prior_on","prior_off","baseline","book_usable"] — the fix for the D342 incident,
# where we stamped "baseline"/"book_usable" against the 1.39.0 two-value Literal, took the
# daemon down ~6h and put 350 configs in their inbox/errors. Our names, verbatim.
# THREE DECISIONS THEY MADE THAT WE INHERIT, recorded because they constrain future work:
#   * ONE FIELD, not one per experiment. Consequence, documented on the field: TWO GENERATION
#     EXPERIMENTS CANNOT RUN CONCURRENTLY on `generation_arm`. The prior A/B is parked; if it
#     is ever revived alongside another, that is when a second field gets minted — not before.
#   * The Literal STAYS CLOSED at four values. Their argument is D342 itself: narrowness
#     caught a cross-system stamp bug AT the boundary instead of letting our regime-weight
#     arms silently masquerade as the parked prior A/B. Widening to `str` would trade a loud
#     incident for silent misclassification. We agree; do not ask for `str`.
#   * Adoption order is already safe: their reader fleet (inbox watcher, runners, refit
#     watcher, publishers) restarted on 1.40.0 and a real D342 config with "baseline"
#     round-trips through the live inbox parser. Nothing of ours will be rejected.
# PIN-ONLY adopt, no Forge code change — the emit path (D342's stamp-time `model_validate`)
# already produces these values and simply stops raising. The two deliberately-red D341 tests
# go green here, which is the intended signal that the gap closed rather than a fix to them.
FORGE_EXPECTED_CONTRACT_VERSION: str = "1.40.0"


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
