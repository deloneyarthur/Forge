"""Forge CLI entry point.

Phase 0 ships:
- `forge --help`     : Typer's help text
- `forge version`    : prints Forge + crucible_contracts versions
- `forge check`      : validates contracts compat and DB schema applies

Phase 2 ships:
- `forge enumerate`  : previews grammar-valid candidate configs against
                       a synthetic registry (Phase 4 wires to Crucible).

Phase 3 ships:
- `forge prefilter`  : runs the §5.2 battery against enumerated candidates
                       (uses the synthetic feature cache; Phase 4 wires
                       Crucible's real cache).

Phase 4 ships:
- `forge run`        : full single-batch cycle (enumerate -> prefilter ->
                       rank -> submit). Checks the §7.3 rate limiter
                       against Crucible's gated runs; exits if blocked.

Subcommands for analyze / grammar arrive in their respective phases.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import typer

from forge.cli.feedback_cmd import cmd_feedback
from forge.cli.grammar_cmd import grammar_app
from forge.core.logging import configure_logging
from forge.version import __version__

if TYPE_CHECKING:
    from collections.abc import Mapping

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar import Grammar
    from forge.prefilters.calibration import Calibration
    from forge.prefilters.types import PreFilterReport

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Forge — candidate strategy generator.",
)


@app.callback()
def _root(
    log_level: str = typer.Option("INFO", "--log-level", help="logging level"),
    json_logs: bool = typer.Option(False, "--json-logs", help="JSON log output"),
) -> None:
    configure_logging(level=log_level, json_output=json_logs)


@app.command()
def version() -> None:
    """Print Forge and crucible_contracts versions."""
    from forge.core.contracts_check import check_contracts_version

    contracts_version = check_contracts_version()
    typer.echo(f"forge {__version__} (crucible_contracts {contracts_version})")


@app.command()
def check() -> None:
    """Validate contracts compatibility and that the DB schema applies cleanly."""
    from forge.core.contracts_check import check_contracts_version
    from forge.persistence.db import db_connection

    contracts_version = check_contracts_version()
    typer.echo(f"crucible_contracts: {contracts_version} OK")
    with db_connection(":memory:"):
        pass
    typer.echo("forge schema: OK (in-memory)")


@app.command("enumerate")
def cmd_enumerate(
    seed: int = typer.Option(0, "--seed", help="RNG root seed"),
    max_candidates: int = typer.Option(
        10, "--max", "-n", min=1, help="max grammar-valid configs to yield"
    ),
    summary: bool = typer.Option(False, "--summary", help="print rejection-rule counts at end"),
) -> None:
    """Preview Phase 2 enumeration against a synthetic registry.

    Phase 2 ships ahead of the Phase 4 Crucible-registry wiring, so this
    command uses an inline demo registry rather than a real
    ``RegistrySnapshot``. Reads ``config/grammar.yaml`` for the rule set.
    """
    from collections import Counter
    from pathlib import Path

    from forge.core.contracts_check import check_contracts_version
    from forge.enumeration import enumerate_candidates, registry_hash
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry

    check_contracts_version()
    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()

    typer.echo(
        f"grammar_version={grammar.grammar_version} "
        f"registry_hash={registry_hash(registry)} "
        f"seed={seed} max={max_candidates} (demo registry)"
    )

    counter: Counter[str] = Counter()
    configs = enumerate_candidates(
        grammar,
        registry,
        seed=seed,
        max_candidates=max_candidates,
        rejection_counter=counter,
    )
    index = 0
    for cfg in configs:
        index += 1
        typer.echo(
            f"[{index:4d}] {cfg.hypothesis}/{cfg.dte_bucket} "
            f"sizer={cfg.sizer.mode} hash={cfg.config_hash}"
        )

    if summary:
        total = sum(counter.values())
        typer.echo(f"\n-- rejection summary ({total} rejections over {total + index} attempts) --")
        if not counter:
            typer.echo("  (none — 100% sampler->validator success rate)")
        for rule, count in counter.most_common(10):
            typer.echo(f"  {rule:30s} {count}")


def _build_feature_cache(
    registry: RegistrySnapshot,
    seed: int,
) -> object:
    """Construct the production FeatureCache; fall back to synthetic on failure.

    Tries `crucible_contracts.FeatureCacheClient` against the default
    `~/optbt_data/db_writer.sock`. If the writer socket isn't reachable
    (no Crucible running, e.g. in test environments), falls back to
    `SyntheticFeatureCache` so dev/test flows keep working.
    """
    from pathlib import Path

    from crucible_contracts import FeatureCacheClient, FeatureCacheUnavailableError

    from forge.prefilters import SyntheticFeatureCache
    from forge.prefilters.crucible_feature_cache import CrucibleFeatureCache

    socket_path = Path.home() / "optbt_data" / "db_writer.sock"
    authkey_path = Path.home() / "optbt_data" / "db_writer.authkey"
    db_path = Path.home() / "optbt_data" / "runs.duckdb"
    if socket_path.exists() and authkey_path.exists():
        try:
            client = FeatureCacheClient(
                socket_path=socket_path,
                authkey_path=authkey_path,
                db_path=db_path,
            )
            cache = CrucibleFeatureCache(
                client,
                data_history_days=registry.data_history_days,
                data_start_date=registry.data_start_date,
            )
            # Probe — Crucible's writer may not yet support feature_batch
            # requests (the writer-side handler ships in a separate change).
            # Falls back to SyntheticFeatureCache if the probe fails.
            cache.probe()
            return cache
        except FeatureCacheUnavailableError:
            pass
    return SyntheticFeatureCache(
        root_seed=seed,
        data_history_days=registry.data_history_days,
        start_date=registry.data_start_date,
    )


@app.command("prefilter")
def cmd_prefilter(
    seed: int = typer.Option(0, "--seed", help="RNG root seed"),
    max_candidates: int = typer.Option(
        10, "--max", "-n", min=1, help="max enumerated configs to run through the battery"
    ),
    summary: bool = typer.Option(
        False, "--summary", help="print per-filter rejection counts at end"
    ),
) -> None:
    """Run the §5.2 pre-filter battery against enumerated candidates.

    Phase 3 ships ahead of Phase 4's submission wiring, so this command
    uses the synthetic feature cache and reports per-filter pass/fail
    counts rather than writing reports to ``pre_filter_logs``.
    """
    from collections import Counter
    from pathlib import Path

    from forge.core.contracts_check import check_contracts_version
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates, registry_hash
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters import (
        default_filters,
        load_calibration,
        run_battery,
    )
    from forge.prefilters.types import FilterContext

    check_contracts_version()
    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    prefilter_yaml = grammar_path.parent / "prefilter.yaml"

    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = load_registry()
    calibration = load_calibration(prefilter_yaml)
    seed_hierarchy = SeedHierarchy(seed)
    ctx = FilterContext(
        registry=registry,
        feature_cache=_build_feature_cache(registry, seed),  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=seed_hierarchy.rng,
    )

    typer.echo(
        f"grammar_version={grammar.grammar_version} "
        f"registry_hash={registry_hash(registry)} "
        f"seed={seed} max={max_candidates} (demo cache, demo registry)"
    )

    filters = default_filters()
    rejection_counts: Counter[str] = Counter()
    passed_count = 0
    rejected_count = 0
    for index, cfg in enumerate(
        enumerate_candidates(grammar, registry, seed=seed, max_candidates=max_candidates),
        start=1,
    ):
        report = run_battery(cfg, ctx, filters)
        if report.passed:
            passed_count += 1
            verdict = "PASS"
            reason = ""
        else:
            rejected_count += 1
            verdict = "FAIL"
            # First failing filter is the only one with passed=False; rest absent.
            failing = next(
                (name for name, fr in report.filter_results.items() if not fr.passed),
                "unknown",
            )
            rejection_counts[failing] += 1
            reason = f" rejected_by={failing}"
        typer.echo(
            f"[{index:4d}] {verdict} {cfg.hypothesis}/{cfg.dte_bucket} "
            f"hash={cfg.config_hash}{reason}"
        )

    if summary:
        total = passed_count + rejected_count
        typer.echo(
            f"\n-- battery summary --\n"
            f"  candidates: {total}\n"
            f"  passed:     {passed_count}\n"
            f"  rejected:   {rejected_count}"
        )
        if rejection_counts:
            typer.echo("\n-- rejections by filter --")
            for name, count in rejection_counts.most_common():
                typer.echo(f"  {name:30s} {count}")


# Per-process "warn once" memos so the QueryError-swallow log lines below
# don't spam the daemon journal every 60-second poll iteration.
_HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED: bool = False
_PROMOTED_CONFIGS_LOAD_FAILED_LOGGED: bool = False


def _load_hypothesis_weights(forge_db_path: Path) -> dict[str, float]:
    """Compute per-hypothesis posterior promotion rates for failure-biased sampling.

    Reads Crucible's gated_runs export (file-based to avoid the writer's
    exclusive DuckDB lock; see contracts v1.8.0) and joins against
    Forge's `submissions` table on config_hash. Empty result (no exports,
    no overlap with submissions) is the normal cold-start path — the
    sampler treats `{}` as "use uniform `rng.choice`".

    Exceptions on the export read are caught and converted to `{}` so
    a missing/corrupt export file never crashes the iteration loop. The
    catch logs once per process via `_HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED`
    so the operator sees the degradation without a per-iteration spam.
    """
    from crucible_contracts import load_recent_gated_runs_from_export
    from crucible_contracts.exceptions import QueryError

    from forge.feedback.rejection_weights import compute_hypothesis_weights
    from forge.persistence.db import db_connection

    if forge_db_path == Path(":memory:") or not forge_db_path.exists():
        return {}
    exports_dir = Path.home() / "optbt_data" / "exports"
    try:
        gated_runs = load_recent_gated_runs_from_export(exports_dir, limit=1000)
    except (QueryError, OSError) as exc:
        global _HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED  # noqa: PLW0603 — warn-once memo
        if not _HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED:
            typer.echo(
                "hypothesis_weights: degraded to uniform sampling — "
                f"export read failed ({type(exc).__name__}: {exc}). "
                "Subsequent failures will be silent this process.",
                err=True,
            )
            _HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED = True
        return {}
    if not gated_runs:
        return {}
    with db_connection(forge_db_path) as conn:
        return compute_hypothesis_weights(conn, gated_runs)


def _fetch_promoted_configs(
    forge_db_path: Path,
    crucible_db_path: Path | None,
) -> list[StrategyConfig]:
    """Look up the StrategyConfigs Forge submitted that Crucible promoted.

    Returns `[]` when Crucible is offline or the promotion query fails;
    logs the degradation once per process so the operator can see the
    prior-promotion-proximity ranking signal (§6.2) has gone blind.
    """
    from datetime import timedelta

    from crucible_contracts import StrategyConfig, get_promoted_strategies
    from crucible_contracts.exceptions import QueryError

    from forge.core.clock import utc_now
    from forge.persistence.db import db_connection

    if crucible_db_path is None or not crucible_db_path.exists():
        return []
    try:
        gated = get_promoted_strategies(crucible_db_path, since=utc_now() - timedelta(days=90))
    except QueryError as exc:
        global _PROMOTED_CONFIGS_LOAD_FAILED_LOGGED  # noqa: PLW0603 — warn-once memo
        if not _PROMOTED_CONFIGS_LOAD_FAILED_LOGGED:
            typer.echo(
                "promoted_configs: prior-promotion-proximity ranking factor "
                f"disabled — query failed ({type(exc).__name__}: {exc}). "
                "Subsequent failures will be silent this process.",
                err=True,
            )
            _PROMOTED_CONFIGS_LOAD_FAILED_LOGGED = True
        return []
    promoted_hashes = {g.run.config_hash for g in gated}
    if not promoted_hashes:
        return []
    with db_connection(forge_db_path) as look_conn:
        placeholders = ", ".join("?" * len(promoted_hashes))
        rows = look_conn.execute(
            f"SELECT config_json FROM submissions WHERE config_hash IN ({placeholders})",  # noqa: S608
            list(promoted_hashes),
        ).fetchall()
    return [StrategyConfig.model_validate_json(r[0]) for r in rows]


def _load_prior_structural_fingerprints(forge_db_path: Path) -> frozenset[str]:
    """T2.7 wiring (D049): populate `prior_structural_fingerprints` from
    Forge's historical submissions.

    Reads every `submissions.config_json`, computes the structural
    fingerprint via `forge.prefilters.novelty.compute_structural_fingerprint`,
    and returns the frozenset of unique fingerprints. The novelty filter
    rejects new candidates whose fingerprint exactly matches any of these.

    Cost: O(N) submissions x O(1) hash per. Forge's submissions table
    is small (~4k rows at session-time); the full scan finishes in
    milliseconds.

    Returns an empty frozenset when the DB is `:memory:` or missing —
    novelty's structural check becomes a no-op, matching pre-D049
    behavior.
    """
    if forge_db_path == Path(":memory:") or not forge_db_path.exists():
        return frozenset()
    from crucible_contracts import StrategyConfig

    from forge.persistence.db import db_connection
    from forge.prefilters.novelty import compute_structural_fingerprint

    fingerprints: set[str] = set()
    with db_connection(forge_db_path) as conn:
        rows = conn.execute("SELECT config_json FROM submissions").fetchall()
    for (cj,) in rows:
        try:
            cfg = StrategyConfig.model_validate_json(cj if isinstance(cj, str) else str(cj))
        except (ValueError, TypeError):
            # Skip malformed legacy rows — they shouldn't gate enumeration.
            continue
        fingerprints.add(compute_structural_fingerprint(cfg))
    return frozenset(fingerprints)


def _run_battery_for_seed(
    grammar: Grammar,
    registry: RegistrySnapshot,
    seed: int,
    max_candidates: int,
    calibration: Calibration,
    *,
    hypothesis_weights: Mapping[str, float] | None = None,
    forge_db_path: Path | None = None,
) -> list[PreFilterReport]:
    """Enumerate and run the §5.2 battery; return one PreFilterReport per config."""
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates
    from forge.prefilters import default_filters, run_battery
    from forge.prefilters.types import FilterContext

    seed_hierarchy = SeedHierarchy(seed)
    # T2.7 wiring (D049): structural-fingerprint dedup against historical
    # submissions. forge_db_path is optional so the demo `cmd_prefilter`
    # path (no DB) still constructs a valid context.
    prior_fingerprints = (
        _load_prior_structural_fingerprints(forge_db_path)
        if forge_db_path is not None
        else frozenset()
    )
    ctx = FilterContext(
        registry=registry,
        feature_cache=_build_feature_cache(registry, seed),  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=seed_hierarchy.rng,
        prior_structural_fingerprints=prior_fingerprints,
    )
    filters = default_filters()
    # D037 — stratified sampling floor: every samplable hypothesis gets
    # at least 2% of the budget (capped at 50%) to prevent the Bayesian
    # failure-bias sampler from collapsing onto 1-2 hypotheses. See
    # IMPLEMENTATION_DECISIONS.md D037.
    from forge.enumeration.iterator import _PRODUCTION_MIN_HYPOTHESIS_FRACTION

    configs = list(
        enumerate_candidates(
            grammar,
            registry,
            seed=seed,
            max_candidates=max_candidates,
            hypothesis_weights=hypothesis_weights,
            min_hypothesis_fraction=_PRODUCTION_MIN_HYPOTHESIS_FRACTION,
        )
    )
    # Hoist the per-config socket round-trips into one batched prefetch when
    # the cache supports it. CrucibleFeatureCache collapses 5000 x 2 calls
    # into ~20 chunked calls; SyntheticFeatureCache has no batch hook and
    # falls through to the per-config path below.
    batch_prefetch = getattr(ctx.feature_cache, "prefetch_for_batch", None)
    if callable(batch_prefetch):
        batch_prefetch(configs)
    return [run_battery(cfg, ctx, filters) for cfg in configs]


def _ensure_grammar_version_recorded_silently(
    forge_db_path: Path,
    *,
    grammar: object,
    yaml_path: Path,
) -> None:
    """D047: self-heal the grammar_versions audit row for the active grammar.

    Called at the start of every `_run_one_cycle` invocation (production
    loop). Idempotent — a SELECT-only no-op when the row already exists.
    Errors are swallowed (logged-by-omission rather than crashing the
    iteration) because this is the audit-trail, not a production-data path.
    """
    from forge.core.clock import utc_now
    from forge.feedback.auto_tune import ensure_grammar_version_recorded
    from forge.persistence.db import db_connection

    try:
        with db_connection(forge_db_path) as conn:
            wrote = ensure_grammar_version_recorded(
                conn,
                grammar=grammar,  # type: ignore[arg-type]  # Grammar import is lazy
                yaml_path=yaml_path,
                at=utc_now(),
            )
        if wrote:
            typer.echo(
                f"grammar_versions: recorded manual_bump row for "
                f"{getattr(grammar, 'grammar_version', '?')}"
            )
    except Exception as exc:  # audit row, never crash production
        typer.echo(
            f"grammar_versions: skipped audit row ({type(exc).__name__}: {exc})",
            err=True,
        )


def _reconcile_pending_silently(
    forge_db_path: Path,
    crucible_db: Path,
) -> None:
    """D046: flush stranded `submitted` rows to `gated` against the export.

    Called at the start of every `_run_one_cycle` invocation before the
    rate-limit check so the oldest-batch heuristic has fresh local state.
    Swallows `QueryError` (Crucible offline) — the rate-limit check will
    handle that case via its own conservative path. Logs the per-batch
    reconciliation count when there's something to report; silent otherwise.
    """
    from crucible_contracts.exceptions import QueryError

    from forge.feedback.consumer import reconcile_all_pending
    from forge.persistence.db import db_connection

    try:
        with db_connection(forge_db_path) as conn:
            feedbacks = reconcile_all_pending(conn, crucible_db)
    except QueryError:
        # Crucible offline / both fetch paths failed. The rate-limit check
        # has its own fallback; nothing more to do here.
        return
    if not feedbacks:
        return
    flipped = sum(fb.gated_count for fb in feedbacks)
    if flipped == 0:
        return
    typer.echo(
        f"reconciled: batches={len(feedbacks)} newly_gated_total={flipped}"
    )


def _consume_feedback_after_submit(  # noqa: PLR0915 — T2.3/T2.5 wiring adds statements; refactor would be net harm
    *,
    forge_db_path: Path,
    crucible_db: Path | None,
    batch_id: object | None,
    open_proposals: Path,
    prefilter_yaml: Path,
) -> None:
    """Best-effort feedback chain wrapper for `forge run --consume-feedback`."""
    if crucible_db is None:
        typer.echo("feedback: skipped (no --crucible-db)")
        return
    import uuid as _uuid

    from forge.core.clock import utc_now
    from forge.feedback.analyzer import analyze_batch
    from forge.feedback.auto_tune import auto_tune
    from forge.feedback.consumer import consume_batch_results
    from forge.feedback.promoted_patterns import record_promoted_patterns
    from forge.feedback.proposal_writer import append_proposal
    from forge.feedback.proposer import (
        evaluate_counterfactual,
        propose,
    )
    from forge.feedback.stuck_state import is_stuck, most_recent_grammar_change
    from forge.feedback.trade_concentration import analyze_promotion_concentration
    from forge.feedback.types import GrammarProposal
    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters.calibration import load_calibration

    now = utc_now()
    with db_connection(forge_db_path) as conn:
        feedback = consume_batch_results(conn, crucible_db, batch_id=batch_id)  # type: ignore[arg-type]
        registry = load_registry()
        report = analyze_batch(feedback, registry)
        if report.promoted_patterns:
            record_promoted_patterns(conn, report.promoted_patterns, discovered_at=now)
        proposals = propose(report, feedback, at=now)
        # T2.3 wiring (D050): annotate each proposal with its counterfactual
        # against this batch's promotions. Stored in evidence_json so the
        # operator sees the safe/escalate signal when reviewing in
        # `forge grammar list-proposals` or downstream tooling.
        for proposal in proposals:
            cf = evaluate_counterfactual(
                proposal,
                recent_promoted_count=feedback.promoted_count,
            )
            # GrammarProposal is frozen; build evidence_json delta and
            # construct a copy carrying the counterfactual annotation.
            annotated_evidence = dict(proposal.evidence_json or {})
            annotated_evidence["counterfactual_rejection_rate"] = cf.rejection_rate
            annotated_evidence["counterfactual_promoted_count"] = cf.promoted_count
            proposal_with_cf = GrammarProposal(
                proposal_id=proposal.proposal_id,
                proposed_at=proposal.proposed_at,
                proposal_type=proposal.proposal_type,
                target=proposal.target,
                proposal_yaml=proposal.proposal_yaml,
                rationale=proposal.rationale,
                evidence_json=annotated_evidence,
                sample_size=proposal.sample_size,
                confidence=proposal.confidence,
            )
            append_proposal(proposal_with_cf, open_proposals_path=open_proposals, db=conn)
        # T2.5 wiring (D050): post-batch trade-concentration analyzer.
        # Scan promoted gated runs for concentration suspects; emit a
        # tighten-grammar proposal per flagged run so the operator can
        # review the strategies that promoted on a fragile P&L
        # distribution.
        gated_runs = tuple(o.gated_run for o in feedback.outcomes)
        concentration_flags = analyze_promotion_concentration(gated_runs)
        for flag in concentration_flags:
            cf_proposal = GrammarProposal(
                proposal_id=_uuid.uuid4(),
                proposed_at=now,
                proposal_type="tighten",
                target="grammar",
                proposal_yaml=(
                    "# T2.5 — promoted-strategy concentration suspect.\n"
                    "# Operator: review the trade ledger for this run "
                    "before treating it as a stable promotion.\n"
                ),
                rationale=(
                    f"Promoted run {flag.run_id} has concentration proxy "
                    f"{flag.proxy_score:.3f} > threshold {flag.threshold:.3f} "
                    f"(profit_factor={flag.profit_factor:.2f}, "
                    f"n_trades={flag.n_trades}, win_rate={flag.win_rate:.2f}). "
                    "Likely few outsized winners drive the P&L — operator review."
                ),
                evidence_json={
                    "trigger": "promotion_concentration_suspect",
                    "target": flag.run_id,  # used by intent-dedup
                    "config_hash": flag.config_hash,
                    "proxy_score": flag.proxy_score,
                    "profit_factor": flag.profit_factor,
                    "n_trades": flag.n_trades,
                    "win_rate": flag.win_rate,
                },
                sample_size=flag.n_trades,
            )
            append_proposal(cf_proposal, open_proposals_path=open_proposals, db=conn)
        if prefilter_yaml.exists():
            calibration = load_calibration(prefilter_yaml)
            auto_tune(
                db=conn,
                calibration=calibration,
                prefilter_yaml_path=prefilter_yaml,
                open_proposals_path=open_proposals,
                at=now,
            )
        # D035: floor the zero-promotion streak at the last grammar bump so
        # post-bump batches start fresh; pre-bump stretches don't poison
        # the post-bump warmup window. None floor = all-time count.
        grammar_change_at = most_recent_grammar_change(conn)
        stuck_flag, stuck_streak = is_stuck(conn, since=grammar_change_at)
    typer.echo(
        f"feedback: batch_id={feedback.batch_id} "
        f"gated_count={feedback.gated_count} "
        f"promoted_count={feedback.promoted_count} "
        f"proposals={len(proposals)}"
    )
    # Per-filter failure histogram (Tier 2 #5). Top 5 gates by failure
    # count so the operator can see what's killing candidates without
    # querying the DB. report.gate_failures is pre-sorted by count.
    if report.gate_failures:
        top_gates = report.gate_failures[:5]
        gate_str = ", ".join(
            f"{row.gate_name}={row.failure_count}({row.failure_rate:.0%})" for row in top_gates
        )
        typer.echo(f"feedback_gates: {gate_str}")
    # Per-hypothesis-class telemetry (Tier 2 #4). Helps identify dead
    # vs promising hypothesis families.
    if report.hypothesis_metrics:
        h_str = ", ".join(
            f"{row.hypothesis}={row.sample_size}/p{row.promotion_rate:.0%}"
            for row in report.hypothesis_metrics
        )
        typer.echo(f"feedback_hypotheses: {h_str}")
    # Stuck-state detector (long-term #3). A long run of zero-promotion
    # batches is signal — sterile grammar, prefilter mis-calibration, or
    # pipeline bug. The streak count is always logged so the operator
    # sees the trend; the WARN line fires when crossing threshold.
    if stuck_streak > 0:
        typer.echo(f"stuck_state: zero_promotion_streak={stuck_streak}")
    if stuck_flag:
        typer.echo(
            f"stuck_state: WARN — {stuck_streak} consecutive zero-promotion "
            "batches; investigate grammar / prefilter / pipeline health"
        )


def _next_iteration_number(forge_db_path: Path) -> int:
    """Return the next iteration number (1-indexed) for seed derivation.

    Counts distinct `forge_batch_id`s in the `submissions` table. Each
    iteration produces exactly one `batch_id`, so this gives us a
    persistent counter that survives process restarts: restart → resume
    from where the last process left off rather than re-enumerating the
    seed=0 slice every time.

    Returns `1` when the DB is in-memory or has no prior submissions.
    """
    from forge.persistence.db import db_connection

    if forge_db_path == Path(":memory:"):
        return 1
    if not forge_db_path.exists():
        return 1
    with db_connection(forge_db_path) as conn:
        row = conn.execute("SELECT COUNT(DISTINCT forge_batch_id) FROM submissions").fetchone()
    prior = int(row[0]) if row and row[0] is not None else 0
    return prior + 1


def _effective_seed(root_seed: int, iteration: int) -> int:
    """Derive a per-iteration effective seed from `(root_seed, iteration)`.

    Reproducibility (hard rule #6): given the same root + iteration,
    returns the same effective seed. Each iteration explores a different
    5000-config slice of the grammar without breaking determinism — the
    submitter's §13.4 unique-config-hash index would otherwise reject
    every config in iter 2+ as a duplicate of iter 1.
    """
    from forge.core.seed import SeedHierarchy

    return SeedHierarchy(root_seed).derive(f"batch_{iteration:08d}")


def _run_one_iteration(
    *,
    seed: int,
    batch_size: int,
    max_candidates: int,
    inbox: Path | None,
    crucible_db: Path | None,
    forge_db_path: Path,
    dry_run: bool,
    consume_feedback: bool,
    open_proposals: Path,
    prefilter_yaml: Path,
) -> str:
    """Run one cycle; return one of 'submitted', 'blocked', 'dry-run'."""
    from forge.core.clock import utc_now
    from forge.core.contracts_check import check_contracts_version
    from forge.enumeration import registry_hash
    from forge.grammar import load_grammar
    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters import load_calibration
    from forge.ranking import Ranker, load_ranker_config, rank_batch
    from forge.submission import BatchContext, check_rate_limit, mint_batch_id, submit_batch

    check_contracts_version()
    config_root = Path(__file__).resolve().parents[3] / "config"
    grammar = load_grammar(
        config_root / "grammar.yaml", archive_dir=config_root / "grammar_archive"
    )
    calibration = load_calibration(config_root / "prefilter.yaml")
    ranker = Ranker(weights=load_ranker_config(config_root / "ranker.yaml").weights)
    registry = load_registry()
    reg_hash = registry_hash(registry)

    typer.echo(
        f"grammar_version={grammar.grammar_version} registry_hash={reg_hash} "
        f"seed={seed} batch_size={batch_size} max={max_candidates}"
    )

    # D047: self-heal the hard-rule-#10 audit trail for manual grammar bumps.
    # The three pre-D047 write paths (auto_tune / apply-proposal / revert) don't
    # fire on operator-edited grammar.yaml, so the `grammar_versions` table was
    # silently empty post-D039 v1→v2. Idempotent: a no-op once the row exists.
    if not dry_run:
        _ensure_grammar_version_recorded_silently(
            forge_db_path,
            grammar=grammar,
            yaml_path=config_root / "grammar.yaml",
        )

    if crucible_db is not None and not dry_run:
        # D046: reconcile every batch with `submitted` rows against the
        # gated-runs export before checking the rate limit. Without this,
        # older batches stay in `submitted` indefinitely and the oldest-batch
        # rate limit logic blocks the loop forever.
        _reconcile_pending_silently(forge_db_path, crucible_db)
        rate = check_rate_limit(forge_db_path, crucible_db)
        if not rate.clear:
            typer.echo(
                f"blocked: oldest in-flight batch {rate.blocking_batch_id} is "
                f"{rate.pct_gated:.1%} gated ({rate.gated_count}/"
                f"{rate.submitted_count}); waiting for >={rate.threshold:.0%}"
            )
            return "blocked"

    promoted = _fetch_promoted_configs(forge_db_path, crucible_db)
    hypothesis_weights = _load_hypothesis_weights(forge_db_path)
    if hypothesis_weights:
        weights_str = ", ".join(f"{h}={w:.3f}" for h, w in sorted(hypothesis_weights.items()))
        typer.echo(f"hypothesis_weights: {weights_str}")
    reports = _run_battery_for_seed(
        grammar,
        registry,
        seed,
        max_candidates,
        calibration,
        hypothesis_weights=hypothesis_weights,
        forge_db_path=forge_db_path,
    )
    passed = sum(1 for r in reports if r.passed)
    typer.echo(f"enumerated={len(reports)} passed_prefilter={passed}")

    ranked = rank_batch(
        ranker,
        reports,
        promoted_strategies=tuple(promoted),
        n=batch_size,
    )
    typer.echo(f"ranked_top_n={len(ranked)} (target {batch_size})")

    if dry_run:
        typer.echo("dry-run: skipping inbox writes + DB persistence")
        for index, candidate in enumerate(ranked, start=1):
            typer.echo(
                f"[{index:4d}] {candidate.report.config.hypothesis}/"
                f"{candidate.report.config.dte_bucket} "
                f"composite={candidate.composite_score:.4f} "
                f"hash={candidate.report.config.config_hash}"
            )
        return "dry-run"

    assert inbox is not None  # CLI guard above
    batch = BatchContext(
        batch_id=mint_batch_id(
            seed=seed,
            grammar_version=grammar.grammar_version,
            registry_hash=reg_hash,
        ),
        grammar_version=grammar.grammar_version,
        registry_hash=reg_hash,
        submitted_at=utc_now(),
        seed=seed,
    )
    with db_connection(forge_db_path) as conn:
        result = submit_batch(conn, batch=batch, candidates=ranked, inbox_root=inbox)
    typer.echo(
        f"batch_id={result.batch_id} submitted={result.submitted_count} "
        f"skipped_duplicate={result.skipped_duplicate_count} "
        f"failed={result.failed_count}"
    )

    if consume_feedback:
        _consume_feedback_after_submit(
            forge_db_path=forge_db_path,
            crucible_db=crucible_db,
            batch_id=result.batch_id,
            open_proposals=open_proposals,
            prefilter_yaml=prefilter_yaml,
        )

    return "submitted"


_RUN_DEFAULT_SEED: int = 0
_RUN_DEFAULT_BATCH_SIZE: int = 10
_RUN_DEFAULT_MAX_CANDIDATES: int = 1000
_RUN_DEFAULT_POLL_INTERVAL_SECONDS: int = 600


class _ResolvedRunDefaults(TypedDict):
    """Strongly-typed payload for `_resolve_run_defaults`.

    Replaces the previous `dict[str, object]` return type so call sites
    don't need `# type: ignore[arg-type]` (which was masking real
    mismatches — mypy actually wanted `call-overload`).
    """

    seed: int
    batch_size: int
    max_candidates: int
    inbox: Path | None
    crucible_db: Path | None
    forge_db: Path | None
    poll_interval_seconds: int


def _resolve_run_defaults(
    *,
    config: Path,
    no_config: bool,
    seed: int | None,
    batch_size: int | None,
    max_candidates: int | None,
    inbox: Path | None,
    crucible_db: Path | None,
    forge_db: Path | None,
    poll_interval_seconds: int | None,
) -> _ResolvedRunDefaults:
    """Resolve effective run args by merging yaml defaults with CLI overrides.

    D025/D6 — When ``--no-config`` is set or the yaml file is missing,
    fall back to hardcoded defaults. Otherwise load the yaml and use its
    fields as defaults; CLI flags (where non-None) override.
    """
    yaml_seed: int | None = None
    yaml_batch_size: int | None = None
    yaml_max_candidates: int | None = None
    yaml_inbox: Path | None = None
    yaml_crucible_db: Path | None = None
    yaml_forge_db: Path | None = None
    yaml_poll_interval: int | None = None
    if not no_config and config.exists():
        from forge.config import load_forge_config

        cfg = load_forge_config(config)
        yaml_seed = cfg.enumeration.seed
        yaml_batch_size = cfg.submission.batch_size
        yaml_max_candidates = cfg.enumeration.max_candidates_per_batch
        yaml_inbox = cfg.crucible.inbox_path
        yaml_crucible_db = cfg.crucible.db_path
        yaml_forge_db = cfg.db_path
        yaml_poll_interval = cfg.submission.poll_interval_seconds

    return _ResolvedRunDefaults(
        seed=seed
        if seed is not None
        else (yaml_seed if yaml_seed is not None else _RUN_DEFAULT_SEED),
        batch_size=batch_size
        if batch_size is not None
        else (yaml_batch_size if yaml_batch_size is not None else _RUN_DEFAULT_BATCH_SIZE),
        max_candidates=max_candidates
        if max_candidates is not None
        else (
            yaml_max_candidates if yaml_max_candidates is not None else _RUN_DEFAULT_MAX_CANDIDATES
        ),
        inbox=inbox if inbox is not None else yaml_inbox,
        crucible_db=crucible_db if crucible_db is not None else yaml_crucible_db,
        forge_db=forge_db if forge_db is not None else yaml_forge_db,
        poll_interval_seconds=poll_interval_seconds
        if poll_interval_seconds is not None
        else (
            yaml_poll_interval
            if yaml_poll_interval is not None
            else _RUN_DEFAULT_POLL_INTERVAL_SECONDS
        ),
    )


@app.command("run")
def cmd_run(
    seed: int | None = typer.Option(None, "--seed", help="RNG root seed"),
    batch_size: int | None = typer.Option(
        None, "--batch-size", min=1, help="top-N candidates to submit (§6.4 default 200)"
    ),
    max_candidates: int | None = typer.Option(
        None, "--max", "-n", min=1, help="enumeration cap before pre-filtering"
    ),
    inbox: Path | None = typer.Option(
        None, "--inbox", help="Crucible inbox directory (required unless --dry-run)"
    ),
    crucible_db: Path | None = typer.Option(
        None, "--crucible-db", help="Crucible runs DB (used by §7.3 rate limiter)"
    ),
    forge_db: Path | None = typer.Option(
        None,
        "--forge-db",
        help="Forge state DB (defaults to in-memory; pass a file path for persistence)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="run the pipeline but skip inbox writes + DB persistence",
    ),
    loop: bool = typer.Option(
        False,
        "--loop",
        help="daemon-loop: repeat the cycle, sleeping --poll-interval-seconds between (§7.3)",
    ),
    max_iterations: int | None = typer.Option(
        None,
        "--max-iterations",
        help="cap loop at N iterations (test/bounded operation); default is unbounded",
    ),
    poll_interval_seconds: int | None = typer.Option(
        None,
        "--poll-interval-seconds",
        help="seconds to sleep between iterations in --loop mode (default 600 = 10 min)",
    ),
    consume_feedback: bool = typer.Option(
        False,
        "--consume-feedback",
        help="after submit, run the feedback chain (consumer/analyzer/proposer/auto_tune)",
    ),
    open_proposals: Path = typer.Option(
        Path("OPEN_PROPOSALS.md"),
        "--open-proposals",
        help="path to OPEN_PROPOSALS.md (used by --consume-feedback)",
    ),
    prefilter_yaml: Path = typer.Option(
        Path("config/prefilter.yaml"),
        "--prefilter-yaml",
        help="path to prefilter.yaml (used by --consume-feedback auto-tune)",
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"),
        "--config",
        help="path to forge.yaml (loaded as defaults; CLI flags override)",
    ),
    no_config: bool = typer.Option(
        False,
        "--no-config",
        help="skip yaml loading entirely; use hardcoded defaults + CLI flags only",
    ),
) -> None:
    """Run the full Forge cycle once or in a daemon loop.

    Phase 5 (D024/D7) adds `--loop` for autonomous multi-batch operation.
    Phase 6 (D025/D6) threads `config/forge.yaml` defaults: when the yaml
    is reachable, its fields seed the run parameters; CLI flags override.
    Pass ``--no-config`` for hermetic CLI-only behavior (tests).

    Each iteration runs the §2.1 per-batch order: enumerate → prefilter →
    rank → submit. With `--consume-feedback`, the feedback chain runs
    after submit. The loop sleeps `--poll-interval-seconds` between
    iterations (default 600s per §7.3) and exits cleanly on SIGINT.

    `--max-iterations N` caps the loop for tests / bounded operation.
    """
    import time

    resolved = _resolve_run_defaults(
        config=config,
        no_config=no_config,
        seed=seed,
        batch_size=batch_size,
        max_candidates=max_candidates,
        inbox=inbox,
        crucible_db=crucible_db,
        forge_db=forge_db,
        poll_interval_seconds=poll_interval_seconds,
    )
    seed = resolved["seed"]
    batch_size = resolved["batch_size"]
    max_candidates = resolved["max_candidates"]
    inbox = resolved["inbox"]
    crucible_db = resolved["crucible_db"]
    forge_db = resolved["forge_db"]
    poll_interval_seconds = resolved["poll_interval_seconds"]

    if not dry_run and inbox is None:
        typer.echo("error: --inbox is required unless --dry-run", err=True)
        raise typer.Exit(code=2)

    forge_db_path = forge_db if forge_db is not None else Path(":memory:")

    if not loop:
        iter_number = _next_iteration_number(forge_db_path)
        effective_seed = _effective_seed(seed, iter_number)
        typer.echo(f"iteration={iter_number} root_seed={seed} effective_seed={effective_seed}")
        _run_one_iteration(
            seed=effective_seed,
            batch_size=batch_size,
            max_candidates=max_candidates,
            inbox=inbox,
            crucible_db=crucible_db,
            forge_db_path=forge_db_path,
            dry_run=dry_run,
            consume_feedback=consume_feedback,
            open_proposals=open_proposals,
            prefilter_yaml=prefilter_yaml,
        )
        return

    # Resume the iteration counter from prior batches in the DB so a
    # restart picks up where we left off rather than replaying batch_1.
    # Global iteration counter (persistent across restarts) advances the
    # seed; local counter caps this process's run via --max-iterations.
    iter_offset = _next_iteration_number(forge_db_path) - 1
    local_iter = 0
    iteration = iter_offset
    try:
        while max_iterations is None or local_iter < max_iterations:
            local_iter += 1
            iteration = iter_offset + local_iter
            effective_seed = _effective_seed(seed, iteration)
            typer.echo(f"--- loop iteration {iteration} (effective_seed={effective_seed}) ---")
            _run_one_iteration(
                seed=effective_seed,
                batch_size=batch_size,
                max_candidates=max_candidates,
                inbox=inbox,
                crucible_db=crucible_db,
                forge_db_path=forge_db_path,
                dry_run=dry_run,
                consume_feedback=consume_feedback,
                open_proposals=open_proposals,
                prefilter_yaml=prefilter_yaml,
            )
            if max_iterations is not None and local_iter >= max_iterations:
                break
            time.sleep(poll_interval_seconds)
    except KeyboardInterrupt:
        typer.echo("loop: stopped on SIGINT")
    typer.echo(f"loop: stopped after {local_iter} iterations (global iter={iteration})")


app.command("feedback")(cmd_feedback)
app.add_typer(grammar_app, name="grammar")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
