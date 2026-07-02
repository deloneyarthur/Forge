"""`forge shadow-null` — permutation-test null-correction shadow-count (P1-2).

Two flag-OFF corrections to the §5.3.7 permutation_test are teed up for a flip
after the D220 hold clears: `cumulative_trading` (prereg 848a1f67) and the
`volatility_event` |move| null (prereg e1a43ba8). This command is the sanctioned
"shadow-count first" step: it runs the real battery over the LIVE feature cache
under the production null, then re-scores ONLY permutation_test under the
corrected null on the very same configs, and reports the per-family survival
delta. Nothing is submitted; `prefilter.yaml` is never written; the daemon is
untouched. It exists so the flip's predicted effect (the preregs) is measured on
real data before the operator flips the bit.

The corrected calibration differs from production in exactly two knobs
(`corrected_null_calibration`), and both contexts share the same feature cache
and the same seeded RNG — so for every config the two permutation runs draw the
identical shuffles and the ONLY thing that moves the verdict is the null
construction. The set of configs that reach permutation_test is identical under
both (filters 1..8 read none of the changed knobs), making this a clean
within-population A/B.

Runs against the live Crucible writer socket by default — a separate process
from the daemon, sharing the socket, touching neither `forge.db` nor the daemon
loop. `--synthetic-cache` is a diagnostic escape for offline smoke runs (the
survival numbers are then meaningless noise — flagged loudly).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from crucible_contracts import StrategyConfig

    from forge.prefilters.shadow_null import ShadowNullRecord, ShadowNullSummary
    from forge.prefilters.types import FilterContext

shadow_null_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Permutation-test null-correction shadow-count (P1-2): prod vs corrected null.",
)

# A fixed-seed enumeration is a reproducible, family-diverse sample — NOT the
# live yield-weighted stream. The per-family DELTA (gained/lost) is a property of
# the filter and is what drives the flip decision; the absolute survival RATES are
# diagnostic (empty priors, fixed seed). Default N is generous so thin families
# (volatility_event ~5-11% of the grammar) still accumulate a usable count reaching
# the last filter; bump --max if the ve `reached` count is too small to trust.
_DEFAULT_MAX = 2000


def _resolve_out(out: Path | None, config: Path) -> Path:
    """Telemetry path: explicit `--out`, else `<config db_path parent>/shadow_null/
    shadow_null.jsonl` (alongside the daemon's other artifacts)."""
    if out is not None:
        return out
    if not config.exists():
        typer.echo(f"error: config {config} not found — pass --out explicitly", err=True)
        raise typer.Exit(code=2)
    from forge.config import load_forge_config

    return load_forge_config(config).db_path.parent / "shadow_null" / "shadow_null.jsonl"


def _collect_dual_null_records(
    configs: list[StrategyConfig],
    ctx_prod: FilterContext,
    ctx_corrected: FilterContext,
) -> tuple[list[ShadowNullRecord], int, int]:
    """Run the §5.2 battery under the production null, then re-score ONLY
    permutation_test under the corrected null for each config that reached it.

    Returns ``(records, reached_total, unavailable)``. Only configs that reached
    the last filter get a record — a config rejected earlier can't have its verdict
    changed by the null correction. ``ctx_prod`` and ``ctx_corrected`` share the
    feature cache (so the corrected re-score reuses the battery's prefetch) and the
    rng_factory (so both draw identical shuffles)."""
    from forge.prefilters import default_filters, run_battery
    from forge.prefilters.permutation_test import PermutationTestFilter
    from forge.prefilters.shadow_null import ShadowNullRecord

    filters = default_filters()
    perm_filter = PermutationTestFilter()
    records: list[ShadowNullRecord] = []
    reached_total = 0
    unavailable = 0
    for cfg in configs:
        report = run_battery(cfg, ctx_prod, filters)
        if report.data_unavailable:
            unavailable += 1
            continue
        pt_prod = report.filter_results.get(perm_filter.name)
        if pt_prod is None:
            # Rejected before the last filter — the null correction can't change it.
            continue
        reached_total += 1
        pt_corr = perm_filter.apply(cfg, ctx_corrected)
        records.append(
            ShadowNullRecord(
                hypothesis=cfg.hypothesis,
                prod_passed=pt_prod.passed,
                corr_passed=pt_corr.passed,
            )
        )
    return records, reached_total, unavailable


@shadow_null_app.command("run")
def cmd_run(
    seed: int = typer.Option(0, "--seed", help="RNG root seed (fixed → reproducible sample)"),
    max_candidates: int = typer.Option(
        _DEFAULT_MAX, "--max", "-n", min=1, help="configs to enumerate through the battery"
    ),
    config: Path = typer.Option(
        Path("config/forge.yaml"), "--config", help="forge.yaml (supplies the telemetry dir)"
    ),
    out: Path | None = typer.Option(
        None, "--out", help="telemetry JSONL (default: <config db_path parent>/shadow_null/...)"
    ),
    synthetic_cache: bool = typer.Option(
        False,
        "--synthetic-cache",
        help="Force SyntheticFeatureCache (offline smoke only — survival numbers are noise).",
    ),
) -> None:
    """Shadow-count the permutation-test null correction over the live cache.

    Runs the §5.2 battery under the production null, re-scores permutation_test
    under the corrected null on the configs that reached it, and writes one
    per-family survival-delta record to the telemetry JSONL.
    """
    from forge.core.clock import utc_now
    from forge.core.contracts_check import check_contracts_version
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates, registry_hash
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters import SyntheticFeatureCache, load_calibration
    from forge.prefilters.shadow_null import (
        corrected_null_calibration,
        summarize_shadow_null,
        summary_payload,
    )
    from forge.prefilters.types import FilterContext

    from .main import _build_feature_cache

    check_contracts_version()
    grammar_path = Path(__file__).resolve().parents[3] / "config" / "grammar.yaml"
    archive_dir = grammar_path.parent / "grammar_archive"
    prefilter_yaml = grammar_path.parent / "prefilter.yaml"

    grammar = load_grammar(grammar_path, archive_dir=archive_dir)
    # Real registry — a shadow-count on demo/synthetic data is meaningless. Demo
    # fallback only when the caller explicitly forces the synthetic cache.
    registry = load_registry(allow_demo_fallback=synthetic_cache)
    calibration = load_calibration(prefilter_yaml)
    corrected = corrected_null_calibration(calibration)
    seed_hierarchy = SeedHierarchy(seed)

    if synthetic_cache:
        feature_cache: object = SyntheticFeatureCache(
            root_seed=seed,
            data_history_days=registry.data_history_days,
            start_date=registry.data_start_date,
        )
        cache_kind = "synthetic"
        typer.echo(
            "warning: --synthetic-cache set — survival counts are pure noise, "
            "NOT a valid shadow-count.",
            err=True,
        )
    else:
        # Require the real cache: never shadow-count on a silent synthetic fallback.
        feature_cache = _build_feature_cache(registry, seed, require_real=True)
        cache_kind = "crucible"

    ctx_prod = FilterContext(
        registry=registry,
        feature_cache=feature_cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=seed_hierarchy.rng,
    )
    # Same cache (already prefetched by run_battery) and same rng_factory — only the
    # null construction differs, so the corrected re-score draws identical shuffles.
    ctx_corrected = replace(ctx_prod, calibration=corrected)

    typer.echo(
        f"grammar_version={grammar.grammar_version} "
        f"registry_hash={registry_hash(registry)} "
        f"seed={seed} max={max_candidates} cache={cache_kind}"
    )

    configs = list(
        enumerate_candidates(grammar, registry, seed=seed, max_candidates=max_candidates)
    )
    batch_prefetch = getattr(feature_cache, "prefetch_for_batch", None)
    if callable(batch_prefetch):
        batch_prefetch(configs)

    records, reached_total, unavailable = _collect_dual_null_records(
        configs, ctx_prod, ctx_corrected
    )
    summary = summarize_shadow_null(records)
    _print_table(summary, reached_total=reached_total, unavailable=unavailable)

    pt = calibration.permutation_test
    record: dict[str, object] = {
        "ts": utc_now().isoformat(),
        "grammar_version": grammar.grammar_version,
        "registry_hash": registry_hash(registry),
        "seed": seed,
        "max_candidates": max_candidates,
        "cache_kind": cache_kind,
        "reached_total": reached_total,
        "data_unavailable": unavailable,
        "prod_null": {
            "forward_return_mode": pt.forward_return_mode,
            "volatility_event_absolute_move": pt.volatility_event_absolute_move,
            "forward_horizon_days": pt.forward_horizon_days,
            "n_permutations": pt.n_permutations,
            "p_value_threshold": pt.p_value_threshold,
        },
        "corrected_null": {
            "forward_return_mode": corrected.permutation_test.forward_return_mode,
            "volatility_event_absolute_move": (
                corrected.permutation_test.volatility_event_absolute_move
            ),
        },
        **summary_payload(summary),
    }
    out_path = _resolve_out(out, config)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    typer.echo(f"\nappended shadow-null record -> {out_path}")


def _print_table(summary: ShadowNullSummary, *, reached_total: int, unavailable: int) -> None:
    """Per-family survival table: reach / prod-pass / corr-pass / gain / lost / net."""
    typer.echo(
        f"\n-- shadow-null: {reached_total} configs reached permutation_test "
        f"({unavailable} data_unavailable skipped) --"
    )
    typer.echo(
        f"{'family':24s} {'reach':>6s} {'prodP':>6s} {'corrP':>6s} "
        f"{'gain':>5s} {'lost':>5s} {'net':>5s}"
    )
    for f in summary.per_family:
        typer.echo(
            f"{f.hypothesis:24s} {f.reached:6d} {f.pass_prod:6d} {f.pass_corr:6d} "
            f"{f.gained:5d} {f.lost:5d} {f.net_delta:+5d}"
        )
    typer.echo(
        f"{'TOTAL':24s} {summary.total_reached:6d} {summary.total_pass_prod:6d} "
        f"{summary.total_pass_corr:6d} {summary.total_gained:5d} "
        f"{summary.total_lost:5d} {summary.total_net_delta:+5d}"
    )


__all__ = ["shadow_null_app"]
