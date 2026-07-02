"""`forge shadow-null` — permutation-test null-correction shadow-count (P1-2).

Two flag-OFF corrections to the §5.3.7 permutation_test are teed up to flip — one
at a time — after the D220 hold clears: `cumulative_trading` (prereg 848a1f67,
FLIP-1, all families) and the `volatility_event` |move| null (prereg e1a43ba8,
FLIP-2, ve-only, requires cumulative mode). This command is the sanctioned
"shadow-count first" step: it runs the real battery over the LIVE feature cache
and scores permutation_test under THREE nulls on the very same configs, reporting
a per-family survival-delta table for EACH sequenced flip. Nothing is submitted;
`prefilter.yaml` is never written; the daemon is untouched.

The three nulls are: A = production (single_day, signed); B = cumulative_trading,
signed (after FLIP-1); C = cumulative_trading + ve |move| (after FLIP-1 AND
FLIP-2). FLIP-1's effect is B vs A (every family); FLIP-2's marginal effect is C
vs B, which is non-zero ONLY for `volatility_event` (|move| is family-scoped) —
so the two sequenced flips are attributed apart rather than conflated. All three
contexts share the feature cache and the seeded RNG, so for every config the
permutation runs draw identical shuffles and the ONLY thing that moves a verdict
is the null construction. The set of configs reaching permutation_test is identical
under all three (filters 1..8 read none of the changed knobs) — a clean
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

    from forge.prefilters.shadow_null import ShadowNullSummary
    from forge.prefilters.types import FilterContext

shadow_null_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Permutation-test null-correction shadow-count (P1-2): per-flip survival delta.",
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


def _collect_tri_null_rows(
    configs: list[StrategyConfig],
    ctx_prod: FilterContext,
    ctx_cumulative: FilterContext,
    ctx_corrected: FilterContext,
) -> tuple[list[tuple[str, bool, bool, bool]], int, int, int]:
    """Score permutation_test under THREE nulls for each config that reaches it:
    A = production (single_day, signed); B = cumulative_trading, signed (flip-1);
    C = cumulative_trading + ve |move| (flip-1 AND flip-2).

    Returns ``(rows, reached_total, unavailable, socket_skips)`` where each row is
    ``(hypothesis, a_passed, b_passed, c_passed)``. Only configs reaching the last
    filter get a row — a config rejected earlier can't be changed by the null. B and
    C differ ONLY for `volatility_event` (|move| is family-scoped), so non-ve configs
    take ``c := b`` for free (one fewer re-score). All three contexts share the
    feature cache (reusing the battery prefetch) and the rng_factory (identical
    shuffles — only the null construction moves a verdict).

    The live writer socket is shared with the daemon and can drop a connection
    mid-run (broken pipe). The Crucible client reconnects on its next call, so a
    single blip should not abort a long telemetry pass: a config whose fetch raises
    `FeatureCacheUnavailableError` is skipped (counted in ``socket_skips``) and the
    loop continues. `reached_total`/`rows` stay consistent — both are advanced only
    after all three evals for a config succeed."""
    from crucible_contracts import FeatureCacheUnavailableError

    from forge.prefilters import default_filters, run_battery
    from forge.prefilters.permutation_test import PermutationTestFilter

    filters = default_filters()
    perm_filter = PermutationTestFilter()
    rows: list[tuple[str, bool, bool, bool]] = []
    reached_total = 0
    unavailable = 0
    socket_skips = 0
    for cfg in configs:
        try:
            report = run_battery(cfg, ctx_prod, filters)
            if report.data_unavailable:
                unavailable += 1
                continue
            pt_a = report.filter_results.get(perm_filter.name)
            if pt_a is None:
                continue
            b_passed = perm_filter.apply(cfg, ctx_cumulative).passed
            c_passed = (
                perm_filter.apply(cfg, ctx_corrected).passed
                if cfg.hypothesis == "volatility_event"
                else b_passed
            )
        except FeatureCacheUnavailableError:
            socket_skips += 1
            continue
        reached_total += 1
        rows.append((cfg.hypothesis, pt_a.passed, b_passed, c_passed))
    return rows, reached_total, unavailable, socket_skips


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
    """Shadow-count the permutation-test null corrections over the live cache.

    Scores permutation_test under three nulls (production / flip-1 cumulative /
    flip-1+flip-2) on the configs that reach it, prints a per-family survival-delta
    table for EACH sequenced flip, and writes one telemetry record.
    """
    from forge.core.clock import utc_now
    from forge.core.contracts_check import check_contracts_version
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates, registry_hash
    from forge.grammar import load_grammar
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters import SyntheticFeatureCache, load_calibration
    from forge.prefilters.shadow_null import (
        ShadowNullRecord,
        corrected_null_calibration,
        cumulative_only_calibration,
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
    cumulative = cumulative_only_calibration(calibration)  # flip-1 (848a1f67)
    corrected = corrected_null_calibration(calibration)  # flip-1 + flip-2 (e1a43ba8)
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
    # Every context shares the cache (reusing the battery prefetch) and rng_factory —
    # only the null construction differs, so each re-score draws identical shuffles.
    ctx_cumulative = replace(ctx_prod, calibration=cumulative)
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

    rows, reached_total, unavailable, socket_skips = _collect_tri_null_rows(
        configs, ctx_prod, ctx_cumulative, ctx_corrected
    )
    # flip-1 (848a1f67, all families): production A -> cumulative B.
    flip1 = summarize_shadow_null(
        ShadowNullRecord(hypothesis=h, prod_passed=a, corr_passed=b) for (h, a, b, _c) in rows
    )
    # flip-2 (e1a43ba8, ve |move|, marginal ON TOP of cumulative): B -> C. Non-ve
    # families show net 0 by construction (|move| is ve-scoped), isolating the ve effect.
    flip2 = summarize_shadow_null(
        ShadowNullRecord(hypothesis=h, prod_passed=b, corr_passed=c) for (h, _a, b, c) in rows
    )
    typer.echo(
        f"\n-- shadow-null: {reached_total} configs reached permutation_test "
        f"({unavailable} data_unavailable, {socket_skips} socket-blip skipped) --"
    )
    _print_table(flip1, label="FLIP-1 cumulative_trading (848a1f67): prod -> cumulative")
    _print_table(flip2, label="FLIP-2 ve |move| (e1a43ba8): cumulative -> +ve|move| (ve only)")

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
        "socket_skips": socket_skips,
        "prod_null": {
            "forward_return_mode": pt.forward_return_mode,
            "volatility_event_absolute_move": pt.volatility_event_absolute_move,
            "forward_horizon_days": pt.forward_horizon_days,
            "n_permutations": pt.n_permutations,
            "p_value_threshold": pt.p_value_threshold,
        },
        "flip1_cumulative_trading": summary_payload(flip1),
        "flip2_ve_absolute_move": summary_payload(flip2),
    }
    out_path = _resolve_out(out, config)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    typer.echo(f"\nappended shadow-null record -> {out_path}")


def _print_table(summary: ShadowNullSummary, *, label: str) -> None:
    """Per-family survival-delta table: reach / before-pass / after-pass / gain / lost / net."""
    typer.echo(f"\n[{label}]")
    typer.echo(
        f"{'family':24s} {'reach':>6s} {'before':>6s} {'after':>6s} "
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
