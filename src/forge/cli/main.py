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

Subcommands for rank / submit / analyze / grammar arrive in their
respective phases.
"""

from __future__ import annotations

import typer

from forge.core.logging import configure_logging
from forge.version import __version__

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
    from forge.enumeration._demo_registry import demo_registry
    from forge.grammar import load_grammar

    check_contracts_version()
    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    registry = demo_registry()

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
    from forge.enumeration._demo_registry import demo_registry
    from forge.grammar import load_grammar
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
    registry = demo_registry()
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


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
