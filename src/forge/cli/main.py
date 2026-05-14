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
from typing import TYPE_CHECKING

import typer

from forge.cli.feedback_cmd import cmd_feedback
from forge.cli.grammar_cmd import grammar_app
from forge.core.logging import configure_logging
from forge.version import __version__

if TYPE_CHECKING:
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
        SyntheticFeatureCache,
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
        feature_cache=SyntheticFeatureCache(root_seed=seed),
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


def _fetch_promoted_configs(
    forge_db_path: Path,
    crucible_db_path: Path | None,
) -> list[StrategyConfig]:
    """Look up the StrategyConfigs Forge submitted that Crucible promoted."""
    from datetime import timedelta

    from crucible_contracts import StrategyConfig, get_promoted_strategies
    from crucible_contracts.exceptions import QueryError

    from forge.core.clock import utc_now
    from forge.persistence.db import db_connection

    if crucible_db_path is None or not crucible_db_path.exists():
        return []
    try:
        gated = get_promoted_strategies(crucible_db_path, since=utc_now() - timedelta(days=90))
    except QueryError:
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


def _run_battery_for_seed(
    grammar: Grammar,
    registry: RegistrySnapshot,
    seed: int,
    max_candidates: int,
    calibration: Calibration,
) -> list[PreFilterReport]:
    """Enumerate and run the §5.2 battery; return one PreFilterReport per config."""
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates
    from forge.prefilters import SyntheticFeatureCache, default_filters, run_battery
    from forge.prefilters.types import FilterContext

    seed_hierarchy = SeedHierarchy(seed)
    ctx = FilterContext(
        registry=registry,
        feature_cache=SyntheticFeatureCache(root_seed=seed),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=seed_hierarchy.rng,
    )
    filters = default_filters()
    return [
        run_battery(cfg, ctx, filters)
        for cfg in enumerate_candidates(
            grammar,
            registry,
            seed=seed,
            max_candidates=max_candidates,
        )
    ]


def _consume_feedback_after_submit(
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
    from forge.core.clock import utc_now
    from forge.feedback.analyzer import analyze_batch
    from forge.feedback.auto_tune import auto_tune
    from forge.feedback.consumer import consume_batch_results
    from forge.feedback.promoted_patterns import record_promoted_patterns
    from forge.feedback.proposal_writer import append_proposal
    from forge.feedback.proposer import propose
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
        for proposal in proposals:
            append_proposal(proposal, open_proposals_path=open_proposals, db=conn)
        if prefilter_yaml.exists():
            calibration = load_calibration(prefilter_yaml)
            auto_tune(
                db=conn,
                calibration=calibration,
                prefilter_yaml_path=prefilter_yaml,
                open_proposals_path=open_proposals,
                at=now,
            )
    typer.echo(
        f"feedback: batch_id={feedback.batch_id} "
        f"gated_count={feedback.gated_count} "
        f"promoted_count={feedback.promoted_count} "
        f"proposals={len(proposals)}"
    )


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

    if crucible_db is not None and not dry_run:
        rate = check_rate_limit(forge_db_path, crucible_db)
        if not rate.clear:
            typer.echo(
                f"blocked: prev batch {rate.blocking_batch_id} is "
                f"{rate.pct_gated:.1%} gated ({rate.gated_count}/"
                f"{rate.submitted_count}); waiting for >=80%"
            )
            return "blocked"

    promoted = _fetch_promoted_configs(forge_db_path, crucible_db)
    reports = _run_battery_for_seed(grammar, registry, seed, max_candidates, calibration)
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
) -> dict[str, object]:
    """Resolve effective run args by merging yaml defaults with CLI overrides.

    D025/D6 — When ``--no-config`` is set or the yaml file is missing,
    fall back to hardcoded defaults. Otherwise load the yaml and use its
    fields as defaults; CLI flags (where non-None) override.
    """
    yaml_loaded: dict[str, object] = {}
    if not no_config and config.exists():
        from forge.config import load_forge_config

        cfg = load_forge_config(config)
        yaml_loaded = {
            "seed": cfg.enumeration.seed,
            "batch_size": cfg.submission.batch_size,
            "max_candidates": cfg.enumeration.max_candidates_per_batch,
            "inbox": cfg.crucible.inbox_path,
            "crucible_db": cfg.crucible.db_path,
            "forge_db": cfg.db_path,
            "poll_interval_seconds": cfg.submission.poll_interval_seconds,
        }

    return {
        "seed": seed if seed is not None else yaml_loaded.get("seed", _RUN_DEFAULT_SEED),
        "batch_size": batch_size
        if batch_size is not None
        else yaml_loaded.get("batch_size", _RUN_DEFAULT_BATCH_SIZE),
        "max_candidates": max_candidates
        if max_candidates is not None
        else yaml_loaded.get("max_candidates", _RUN_DEFAULT_MAX_CANDIDATES),
        "inbox": inbox if inbox is not None else yaml_loaded.get("inbox"),
        "crucible_db": crucible_db if crucible_db is not None else yaml_loaded.get("crucible_db"),
        "forge_db": forge_db if forge_db is not None else yaml_loaded.get("forge_db"),
        "poll_interval_seconds": poll_interval_seconds
        if poll_interval_seconds is not None
        else yaml_loaded.get("poll_interval_seconds", _RUN_DEFAULT_POLL_INTERVAL_SECONDS),
    }


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
    seed = int(resolved["seed"])  # type: ignore[arg-type]
    batch_size = int(resolved["batch_size"])  # type: ignore[arg-type]
    max_candidates = int(resolved["max_candidates"])  # type: ignore[arg-type]
    inbox = resolved["inbox"]  # type: ignore[assignment]
    crucible_db = resolved["crucible_db"]  # type: ignore[assignment]
    forge_db = resolved["forge_db"]  # type: ignore[assignment]
    poll_interval_seconds = int(resolved["poll_interval_seconds"])  # type: ignore[arg-type]

    if not dry_run and inbox is None:
        typer.echo("error: --inbox is required unless --dry-run", err=True)
        raise typer.Exit(code=2)

    forge_db_path = forge_db if forge_db is not None else Path(":memory:")

    if not loop:
        _run_one_iteration(
            seed=seed,
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

    iteration = 0
    try:
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            typer.echo(f"--- loop iteration {iteration} ---")
            _run_one_iteration(
                seed=seed,
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
            if max_iterations is not None and iteration >= max_iterations:
                break
            time.sleep(poll_interval_seconds)
    except KeyboardInterrupt:
        typer.echo("loop: stopped on SIGINT")
    typer.echo(f"loop: stopped after {iteration} iterations")


app.command("feedback")(cmd_feedback)
app.add_typer(grammar_app, name="grammar")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
