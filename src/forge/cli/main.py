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
    import uuid
    from collections.abc import Mapping, Sequence

    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.feedback.trade_rate_priors import BucketKey, BucketStats
    from forge.feedback.types import BatchFeedback
    from forge.grammar import Grammar
    from forge.prefilters.calibration import Calibration
    from forge.prefilters.types import PreFilterReport
    from forge.ranking.types import RankedCandidate

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
    *,
    require_real: bool = False,
    data_root: Path | None = None,
) -> object:
    """Construct the production FeatureCache; fall back to synthetic on failure.

    Tries `crucible_contracts.FeatureCacheClient` against the writer socket
    under `data_root` (default `~/optbt_data`). When the socket isn't reachable
    (no Crucible running, writer restarting, e.g. in test environments) the
    behaviour depends on `require_real`:

      - `require_real=False` (dev/test default): fall back to
        `SyntheticFeatureCache` so offline flows keep working — but log
        LOUDLY, because synthetic returns are pure noise that make the whole
        pre-filter battery meaningless (the 2026-05-28 RCA: a post-reboot
        silent fallback rejected every config at `permutation_test`).
      - `require_real=True` (production submission path): raise
        `FeatureCacheUnavailableError` rather than degrade silently, so the
        caller can skip the iteration instead of filtering/submitting on noise.

    `data_root` is injectable so tests can point at a socket-free directory
    without depending on whether a live writer exists on the host.
    """
    from pathlib import Path

    from crucible_contracts import FeatureCacheClient, FeatureCacheUnavailableError

    from forge.prefilters import SyntheticFeatureCache
    from forge.prefilters.crucible_feature_cache import CrucibleFeatureCache

    root = data_root if data_root is not None else Path.home() / "optbt_data"
    socket_path = root / "db_writer.sock"
    authkey_path = root / "db_writer.authkey"
    db_path = root / "runs.duckdb"

    unavailable_reason: str | None = None
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
            cache.probe()
            return cache
        except FeatureCacheUnavailableError as exc:
            unavailable_reason = str(exc)
    else:
        unavailable_reason = f"writer socket not found at {socket_path}"

    # Real cache unavailable. Hard rule: production never degrades silently.
    if require_real:
        raise FeatureCacheUnavailableError(
            f"{unavailable_reason}; refusing to run on the synthetic cache "
            "(--require-real-cache is set)."
        )
    typer.echo(
        f"warning: {unavailable_reason}; falling back to SyntheticFeatureCache "
        "— pre-filter results are NOT data-grounded.",
        err=True,
    )
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
    synthetic_cache: bool = typer.Option(
        False,
        "--synthetic-cache",
        help=(
            "Force SyntheticFeatureCache instead of CrucibleFeatureCache. "
            "Use for diagnostic runs at high --max when the real cache is "
            "slow; rejection patterns for structural/grammar-shape filters "
            "(structural_redundancy, signal_density, etc.) are cache-"
            "independent and remain representative."
        ),
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
    if synthetic_cache:
        feature_cache: object = SyntheticFeatureCache(
            root_seed=seed,
            data_history_days=registry.data_history_days,
            start_date=registry.data_start_date,
        )
    else:
        feature_cache = _build_feature_cache(registry, seed)
    ctx = FilterContext(
        registry=registry,
        feature_cache=feature_cache,  # type: ignore[arg-type]
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
_TRADE_RATE_PRIORS_LOAD_FAILED_LOGGED: bool = False


def _format_phase_timings_line(timings: Mapping[str, float]) -> str:
    """D065: render per-phase elapsed seconds for the iteration.

    Single-line, fixed key order so the line is greppable and the order
    matches the actual pipeline flow (reconcile → enumeration → prefetch
    → battery → rank → submit). Missing keys are skipped (an iteration
    that short-circuits early won't have all phases populated).
    """
    order = (
        "reconcile",
        "enumeration",
        "prefetch",
        "battery",
        "rank",
        "submit",
    )
    parts = [f"{k}={timings[k]:.2f}s" for k in order if k in timings]
    return f"phase_timings: {', '.join(parts)}"


def _format_hypothesis_distribution_line(
    label: str,
    distribution: Mapping[str, int],
) -> str:
    """D065: render a hypothesis-keyed count distribution in canonical order.

    Used for both `sampler_attempts` (the input distribution to the
    pre-filter battery) and `ranked_top_n_by_hypothesis` (the output
    distribution after diversification). Stable ordering via the
    canonical `_HYPOTHESES` tuple — missing hypotheses show `=0` so the
    operator's eye-grep doesn't have to infer absence from omission.
    """
    from forge.enumeration.search_space import _HYPOTHESES

    parts = [f"{h}={distribution.get(h, 0)}" for h in _HYPOTHESES]
    return f"{label}: {', '.join(parts)}"


def _echo_dry_run_preview(ranked: Sequence[RankedCandidate]) -> None:
    """Print the ranked-survivor preview for `forge run --dry-run`.

    Extracted from `_run_one_iteration` to keep that function under the
    PLR0915 statement budget; behavior is unchanged (one header line +
    one detail line per candidate).
    """
    typer.echo("dry-run: skipping inbox writes + DB persistence")
    for index, candidate in enumerate(ranked, start=1):
        typer.echo(
            f"[{index:4d}] {candidate.report.config.hypothesis}/"
            f"{candidate.report.config.dte_bucket} "
            f"composite={candidate.composite_score:.4f} "
            f"hash={candidate.report.config.config_hash}"
        )


def _enumerated_by_hypothesis(reports: object) -> dict[str, int]:
    """D096: per-hypothesis count of enumerated configs (input to the battery).

    This is the funnel export's `enumerated_by_hypothesis` — the "which
    grammar branch" annotation Crucible's funnel wants on the enumerated
    stage. Shares its derivation with the journal's `sampler_attempts`
    line (D065) so the persisted column and the log line never drift.
    """
    from collections import Counter as _Counter

    counts: _Counter[str] = _Counter(
        getattr(r, "config", None).hypothesis  # type: ignore[union-attr]
        for r in reports  # type: ignore[attr-defined]
        if getattr(r, "config", None) is not None
    )
    return dict(counts)


def _log_hypothesis_distributions(
    reports: object,
    ranked: object,
) -> None:
    """D065: echo the per-hypothesis sampler→ranker funnel distributions.

    Two lines:
      `sampler_attempts: hyp=N, ...`              (input to prefilter)
      `ranked_top_n_by_hypothesis: hyp=N, ...`    (output of ranker)

    Together with D064's `prefilter_rejections_by_hypothesis` line in
    the middle, the journal carries a complete per-hypothesis funnel
    view in three lines per iteration.
    """
    from collections import Counter as _Counter

    attempts = _enumerated_by_hypothesis(reports)
    survivors: _Counter[str] = _Counter(
        c.report.config.hypothesis
        for c in ranked  # type: ignore[attr-defined]
    )
    typer.echo(_format_hypothesis_distribution_line("sampler_attempts", attempts))
    typer.echo(
        _format_hypothesis_distribution_line("ranked_top_n_by_hypothesis", survivors),
    )


def _log_prefilter_rejections(
    summary: object,  # PrefilterRejectionSummary, typed in submitter
) -> None:
    """D062 + D064: echo per-batch rejection breakdowns to the journal.

    Two lines:
      `prefilter_rejections: filter=N, ...`              (D062 aggregate)
      `prefilter_rejections_by_hypothesis: hyp[filter=N, ...]; ...`
                                                          (D064 partition)

    The aggregate is the bottleneck overview; the per-hypothesis line
    surfaces which filter kills which hypothesis (load-bearing for
    diagnosing why some hypotheses never reach Crucible). Both omitted
    when the summary is empty (no rejections this batch).
    """
    total = getattr(summary, "total", {}) or {}
    by_hyp = getattr(summary, "by_hypothesis", {}) or {}
    if not total:
        return
    aggregate = ", ".join(f"{name}={n}" for name, n in sorted(total.items(), key=lambda kv: -kv[1]))
    typer.echo(f"prefilter_rejections: {aggregate}")
    if not by_hyp:
        return
    parts: list[str] = []
    for hyp in sorted(by_hyp, key=lambda h: -sum(by_hyp[h].values())):
        per_filter = by_hyp[hyp]
        inner = ", ".join(
            f"{name}={n}"
            for name, n in sorted(
                per_filter.items(),
                key=lambda kv: -kv[1],
            )
        )
        parts.append(f"{hyp}[{inner}]")
    typer.echo(f"prefilter_rejections_by_hypothesis: {'; '.join(parts)}")


def _format_hypothesis_weights_line(weights: Mapping[str, float]) -> str:
    """D063: render the effective sampler weights, prior-filled for unobserved.

    Pre-D063 the journal line silently omitted hypotheses with zero gated
    rows, making it look like they were pruned. In reality the sampler
    falls back to `prior_mean` for missing keys (rejection_weights.py),
    so they actually get *higher* weight than observed-but-failing
    hypotheses. The `*` marker calls out prior-filled entries.
    """
    from forge.enumeration.search_space import _HYPOTHESES
    from forge.feedback.rejection_weights import prior_mean

    pm = prior_mean()
    parts = [f"{h}={weights[h]:.3f}" if h in weights else f"{h}={pm:.3f}*" for h in _HYPOTHESES]
    return f"hypothesis_weights: {', '.join(parts)} (*=prior, no data)"


def _load_hypothesis_weights(forge_db_path: Path) -> dict[str, float]:
    """Compute per-hypothesis multi-class reward weights for failure-biased sampling.

    Reads Crucible's gated_runs export (file-based to avoid the writer's
    exclusive DuckDB lock; see contracts v1.8.0) and joins against
    Forge's `submissions` table on config_hash. The weight blends
    trade-production and gate-progress with promotion as the ceiling
    (D094 / improvement-plan Phase 2), so the enumerator keeps a gradient
    even at zero promotions — `compute_hypothesis_weights`' promotion-only
    signal is flat in that regime. Empty result (no exports, no overlap
    with submissions) is the normal cold-start path — the sampler treats
    `{}` as "use uniform `rng.choice`".

    Exceptions on the export read are caught and converted to `{}` so
    a missing/corrupt export file never crashes the iteration loop. The
    catch logs once per process via `_HYPOTHESIS_WEIGHTS_LOAD_FAILED_LOGGED`
    so the operator sees the degradation without a per-iteration spam.
    """
    from crucible_contracts import load_recent_gated_runs_from_export
    from crucible_contracts.exceptions import QueryError

    from forge.enumeration.search_space import _HYPOTHESES, OVERLAY_ONLY_HYPOTHESES
    from forge.feedback.rejection_weights import (
        apply_exploration_floor,
        compute_hypothesis_reward_weights,
        prior_mean,
    )
    from forge.persistence.db import db_connection

    # D067 — sampling hypotheses: canonical minus overlay-only (D066).
    sampling_hypotheses = tuple(h for h in _HYPOTHESES if h not in OVERLAY_ONLY_HYPOTHESES)

    if forge_db_path == Path(":memory:") or not forge_db_path.exists():
        # D067: even on cold start, return floored weights so the journal
        # shows the floor explicitly and the sampler distributes evenly.
        return apply_exploration_floor(
            {},
            hypotheses=sampling_hypotheses,
            fallback=prior_mean(),
        )
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
        return apply_exploration_floor(
            {},
            hypotheses=sampling_hypotheses,
            fallback=prior_mean(),
        )
    if not gated_runs:
        return apply_exploration_floor(
            {},
            hypotheses=sampling_hypotheses,
            fallback=prior_mean(),
        )
    with db_connection(forge_db_path) as conn:
        raw = compute_hypothesis_reward_weights(conn, gated_runs)
    # D067: floor every canonical sampling hypothesis at
    # DEFAULT_EXPLORATION_FLOOR so observed-but-low ones (regime_arbitrage
    # at 0.004, relative_value at 0.003) still get measurable exploration
    # budget. Unobserved hypotheses fall back to the Beta prior (~0.091),
    # which is already above the floor.
    return apply_exploration_floor(
        raw,
        hypotheses=sampling_hypotheses,
        fallback=prior_mean(),
    )


def _load_trade_rate_priors(
    forge_db_path: Path,
    registry: RegistrySnapshot,
    *,
    min_trades: int,
    current_grammar_version: str | None = None,
) -> dict[BucketKey, BucketStats]:
    """D076 / Q16 — compute per-bucket trade-rate posteriors for the empirical
    `expected_trades` filter.

    Mirrors `_load_hypothesis_weights` (gated_runs read via the file-based
    export to dodge the writer's exclusive DuckDB lock; QueryError /
    OSError catches degrade to empty dict; warn-once on first failure).
    Empty dict → filter falls back to the activations heuristic for every
    config, matching pre-D076 behaviour.
    """
    from crucible_contracts import load_recent_gated_runs_from_export
    from crucible_contracts.exceptions import QueryError

    from forge.feedback.trade_rate_priors import compute_trade_rate_priors
    from forge.persistence.db import db_connection

    if forge_db_path == Path(":memory:") or not forge_db_path.exists():
        return {}
    exports_dir = Path.home() / "optbt_data" / "exports"
    try:
        gated_runs = load_recent_gated_runs_from_export(exports_dir, limit=10_000)
    except (QueryError, OSError) as exc:
        global _TRADE_RATE_PRIORS_LOAD_FAILED_LOGGED  # noqa: PLW0603 — warn-once memo
        if not _TRADE_RATE_PRIORS_LOAD_FAILED_LOGGED:
            typer.echo(
                "trade_rate_priors: degraded to activations heuristic — "
                f"export read failed ({type(exc).__name__}: {exc}). "
                "Subsequent failures will be silent this process.",
                err=True,
            )
            _TRADE_RATE_PRIORS_LOAD_FAILED_LOGGED = True
        return {}
    if not gated_runs:
        return {}
    with db_connection(forge_db_path) as conn:
        return compute_trade_rate_priors(
            conn,
            gated_runs,
            registry,
            min_trades=min_trades,
            current_grammar_version=current_grammar_version,
        )


def _fetch_promoted_configs(
    _forge_db_path: Path,
    _crucible_db_path: Path | None,
) -> list[StrategyConfig]:
    """Look up the StrategyConfigs Crucible promoted, for the §6.2 prior-
    promotion-proximity ranking factor.

    Reads `EXPORT_LAYOUT.promoted_strategies_*.json` written by Crucible's
    `crucible-promoted-strategies-publisher` (CRUCIBLE_CHANGES.md §6.3).
    The publisher emits a fresh snapshot every poll interval (~60s); the
    on-disk JSON carries the full `StrategyConfig` for each promoted run,
    so Forge skips its prior submissions-table roundtrip entirely.

    Why not query `runs.duckdb` directly (the prior path): Crucible's
    `db_writer` holds an exclusive write lock for its entire lifetime, so
    `duckdb.connect(..., read_only=True)` raises `IOException: Conflicting
    lock`. The file-based export is the load-bearing cross-process read
    path per CLAUDE.md §13.15. Mirrors `_fetch_hypothesis_weights` (which
    already reads `gated_runs_*.json` via the symmetric export reader).

    Returns `[]` when the export directory is missing, no snapshot exists
    yet, or the file is malformed; logs the degradation once per process.

    The `_forge_db_path` / `_crucible_db_path` kwargs are retained as
    underscored no-op parameters for backwards-compatible call signatures;
    the prior implementation used both for a Forge-side hash → config
    lookup that the JSON export now supplies in one shot.
    """
    from datetime import timedelta

    from crucible_contracts import load_promoted_strategies_from_export
    from crucible_contracts.exceptions import QueryError

    from forge.core.clock import utc_now

    exports_dir = Path.home() / "optbt_data" / "exports"
    try:
        promoted = load_promoted_strategies_from_export(
            exports_dir,
            since=utc_now() - timedelta(days=90),
        )
    except (QueryError, OSError) as exc:
        global _PROMOTED_CONFIGS_LOAD_FAILED_LOGGED  # noqa: PLW0603 — warn-once memo
        if not _PROMOTED_CONFIGS_LOAD_FAILED_LOGGED:
            typer.echo(
                "promoted_configs: prior-promotion-proximity ranking factor "
                f"disabled — export read failed ({type(exc).__name__}: {exc}). "
                "Subsequent failures will be silent this process.",
                err=True,
            )
            _PROMOTED_CONFIGS_LOAD_FAILED_LOGGED = True
        return []
    return [p.strategy_config for p in promoted]


# D060 / P2-5 — warn-once flag for the no-DB code path. NoveltyFilter's
# structural-fingerprint dedup is a no-op when prior_structural_fingerprints
# is empty by default. The demo `forge prefilter` CLI legitimately runs
# without a DB; the autonomous loop should always have one. Surface the
# transition state so a future caller can't silently regress dedup.
_NOVELTY_DEDUP_WARNED = False


def _warn_once_novelty_dedup_disabled() -> None:
    global _NOVELTY_DEDUP_WARNED  # noqa: PLW0603 — module-level warn-once state
    if _NOVELTY_DEDUP_WARNED:
        return
    _NOVELTY_DEDUP_WARNED = True
    import sys

    sys.stderr.write(
        "WARN: forge_db_path=None — NoveltyFilter structural-fingerprint dedup "
        "is disabled for this run. This is expected for the demo `forge prefilter` "
        "CLI; if you see it from the autonomous loop, that's a regression of T2.7 "
        "(D049 / D060 / P2-5).\n"
    )


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
    trade_rate_priors: Mapping[BucketKey, BucketStats] | None = None,
    forge_db_path: Path | None = None,
    timings: dict[str, float] | None = None,
    require_real_cache: bool = False,
) -> list[PreFilterReport]:
    """Enumerate and run the §5.2 battery; return one PreFilterReport per config.

    D065: when `timings` is provided, populates per-phase elapsed seconds
    under keys ``enumeration``, ``prefetch``, ``battery``. Caller-owned
    dict so the outer loop can aggregate with its own phases. Optional —
    `None` keeps the old call signature working for tests that don't care.
    """
    from forge.core.seed import SeedHierarchy
    from forge.enumeration import enumerate_candidates
    from forge.prefilters import default_filters, run_battery
    from forge.prefilters.types import FilterContext

    seed_hierarchy = SeedHierarchy(seed)
    # T2.7 wiring (D049): structural-fingerprint dedup against historical
    # submissions. forge_db_path is optional so the demo `cmd_prefilter`
    # path (no DB) still constructs a valid context.
    #
    # D060 / P2-5: warn-once when the dedup is structurally disabled. The
    # demo CLI path is fine; an autonomous loop that ever invokes this
    # without a DB path is a regression (NoveltyFilter would silently
    # accept structurally-identical configs that it should have rejected).
    if forge_db_path is None:
        _warn_once_novelty_dedup_disabled()
        prior_fingerprints: frozenset[str] = frozenset()
    else:
        prior_fingerprints = _load_prior_structural_fingerprints(forge_db_path)
    from types import MappingProxyType as _MappingProxyType

    ctx = FilterContext(
        registry=registry,
        feature_cache=_build_feature_cache(  # type: ignore[arg-type]
            registry, seed, require_real=require_real_cache
        ),
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=seed_hierarchy.rng,
        prior_structural_fingerprints=prior_fingerprints,
        trade_rate_priors=_MappingProxyType(
            dict(trade_rate_priors) if trade_rate_priors is not None else {},
        ),
    )
    filters = default_filters()
    # D037 — stratified sampling floor: every samplable hypothesis gets
    # at least 2% of the budget (capped at 50%) to prevent the Bayesian
    # failure-bias sampler from collapsing onto 1-2 hypotheses. See
    # IMPLEMENTATION_DECISIONS.md D037.
    import time as _time

    from forge.enumeration.iterator import _PRODUCTION_MIN_HYPOTHESIS_FRACTION

    t0 = _time.monotonic()
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
    t1 = _time.monotonic()
    # Hoist the per-config socket round-trips into one batched prefetch when
    # the cache supports it. CrucibleFeatureCache collapses 5000 x 2 calls
    # into ~20 chunked calls; SyntheticFeatureCache has no batch hook and
    # falls through to the per-config path below.
    batch_prefetch = getattr(ctx.feature_cache, "prefetch_for_batch", None)
    if callable(batch_prefetch):
        batch_prefetch(configs)
    t2 = _time.monotonic()
    reports = [run_battery(cfg, ctx, filters) for cfg in configs]
    t3 = _time.monotonic()
    if timings is not None:
        timings["enumeration"] = t1 - t0
        timings["prefetch"] = t2 - t1
        timings["battery"] = t3 - t2
    return reports


def _ensure_grammar_version_recorded_silently(
    forge_db_path: Path,
    *,
    grammar: object,
    yaml_path: Path,
) -> None:
    """D051: self-heal the grammar_versions audit row for the active grammar.

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
) -> tuple[BatchFeedback, ...]:
    """D046: flush stranded `submitted` rows to `gated` against the export.

    Called at the start of every `_run_one_cycle` invocation before the
    rate-limit check so the oldest-batch heuristic has fresh local state.
    Swallows `QueryError` (Crucible offline) — the rate-limit check will
    handle that case via its own conservative path. Logs the per-batch
    reconciliation count when there's something to report; silent otherwise.

    H-2 (audit 2026-05-29): returns the per-batch `BatchFeedback`s so the
    caller can run the §2.1 step-10/11 feedback chain on a batch that is
    actually gated — previously these were discarded and the chain ran on
    the just-submitted (0-gated) batch, producing nothing.
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
        return ()
    flipped = sum(fb.gated_count for fb in feedbacks)
    if flipped:
        typer.echo(f"reconciled: batches={len(feedbacks)} newly_gated_total={flipped}")
    return feedbacks


def _select_feedback_target_batch(
    candidates: Sequence[tuple[uuid.UUID, int]],
) -> uuid.UUID | None:
    """H-2: pick which reconciled batch the feedback chain should analyze.

    `candidates` is `(batch_id, gated_count)` per reconciled in-flight batch.
    Returns the batch with the MOST real gated outcomes — the richest, most-
    completed learning signal — or `None` when no reconciled batch has any
    gated outcomes (nothing newly completed; the caller then skips the chain
    rather than analyzing the just-submitted 0-gated batch as it did pre-fix).
    Ties keep the first (oldest, since `reconcile_all_pending` orders
    oldest-first) for determinism.
    """
    best: tuple[uuid.UUID, int] | None = None
    for batch_id, gated in candidates:
        if gated <= 0:
            continue
        if best is None or gated > best[1]:
            best = (batch_id, gated)
    return best[0] if best else None


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
    if batch_id is None:
        # H-2: no reconciled batch had gated outcomes this cycle — nothing newly
        # completed to learn from. Skip rather than analyze a 0-gated batch.
        typer.echo("feedback: skipped (no completed batch with gated results this cycle)")
        return

    from forge.core.clock import utc_now
    from forge.feedback.analyzer import analyze_batch
    from forge.feedback.auto_tune import auto_tune
    from forge.feedback.consumer import consume_batch_results
    from forge.feedback.promoted_patterns import record_promoted_patterns
    from forge.feedback.proposal_writer import enrich_and_append_proposals
    from forge.feedback.proposer import propose
    from forge.feedback.stuck_state import is_stuck, most_recent_grammar_change
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
        # D054 — shared T2.3 (counterfactual) + T2.5 (concentration) enrichment.
        # Identical path to manual `forge feedback` (see `cli/feedback_cmd.py`).
        enrich_and_append_proposals(
            proposals,
            feedback=feedback,
            open_proposals_path=open_proposals,
            db=conn,
            at=now,
        )
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


def _run_one_iteration(  # noqa: PLR0915 — D065 observability statements
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
    require_real_cache: bool = False,
    # H-4: §7.3 throttle; mirrors rate_limiter._DEFAULT_THRESHOLD (0.80).
    inflight_threshold: float = 0.80,
) -> str:
    """Run one cycle; return one of 'submitted', 'blocked', 'dry-run', 'skipped'.

    PLR0915 suppression: D062/D064/D065 progressively added per-iteration
    telemetry (rejection counter, per-hypothesis breakdown, phase timings,
    funnel distributions). Each adds 1-3 statements; the budget would
    require fragmenting the linear iteration flow into helpers without
    making it more readable. The function is still one straight-line
    cycle: gate → enumerate → rank → submit → log → feedback.
    """
    import time as _time

    from crucible_contracts import FeatureCacheUnavailableError

    from forge.core.clock import utc_now
    from forge.core.contracts_check import check_contracts_version
    from forge.enumeration import enumeration_inputs_hash, registry_hash
    from forge.funnel import write_funnel_export
    from forge.grammar import load_grammar
    from forge.persistence.db import db_connection
    from forge.persistence.registry_loader import load_registry
    from forge.prefilters import load_calibration
    from forge.ranking import Ranker, load_ranker_config, rank_batch
    from forge.submission import (
        BatchContext,
        check_rate_limit,
        mint_batch_id,
        record_pre_filter_logs_for_rejected,
        submit_batch,
    )
    from forge.submission.submitter import record_prefilter_rejections

    timings: dict[str, float] = {}

    check_contracts_version()
    config_root = Path(__file__).resolve().parents[3] / "config"
    grammar = load_grammar(
        config_root / "grammar.yaml", archive_dir=config_root / "grammar_archive"
    )
    calibration = load_calibration(prefilter_yaml)
    ranker = Ranker(weights=load_ranker_config(config_root / "ranker.yaml").weights)
    registry = load_registry()
    reg_hash = registry_hash(registry)

    typer.echo(
        f"grammar_version={grammar.grammar_version} registry_hash={reg_hash} "
        f"seed={seed} batch_size={batch_size} max={max_candidates}"
    )

    # D051: self-heal the hard-rule-#10 audit trail for manual grammar bumps.
    # The three pre-D051 write paths (auto_tune / apply-proposal / revert) don't
    # fire on operator-edited grammar.yaml, so the `grammar_versions` table was
    # silently empty post-D039 v1→v2. Idempotent: a no-op once the row exists.
    if not dry_run:
        _ensure_grammar_version_recorded_silently(
            forge_db_path,
            grammar=grammar,
            yaml_path=config_root / "grammar.yaml",
        )

    # H-2: BatchFeedbacks from reconcile drive the post-submit feedback chain
    # (which batch is actually gated). Default empty for the dry-run / no-crucible
    # paths where reconcile is skipped.
    reconciled: tuple[BatchFeedback, ...] = ()
    if crucible_db is not None and not dry_run:
        # D046: reconcile every batch with `submitted` rows against the
        # gated-runs export before checking the rate limit. Without this,
        # older batches stay in `submitted` indefinitely and the oldest-batch
        # rate limit logic blocks the loop forever.
        _t_reconcile = _time.monotonic()
        reconciled = _reconcile_pending_silently(forge_db_path, crucible_db)
        timings["reconcile"] = _time.monotonic() - _t_reconcile
        rate = check_rate_limit(forge_db_path, crucible_db, threshold=inflight_threshold)
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
        typer.echo(_format_hypothesis_weights_line(hypothesis_weights))
    # D076 / Q16 — empirical-prior bucket stats for `expected_trades`.
    # Cold start (no exports / no overlap with submissions) returns {};
    # filter falls back to the activations heuristic for every config.
    trade_rate_priors = _load_trade_rate_priors(
        forge_db_path,
        registry,
        min_trades=calibration.expected_trade_count.min_trades,
        # D081: judge each config mostly by trade behaviour under the grammar
        # version it was built on; prior versions are down-weighted, not dropped.
        current_grammar_version=grammar.grammar_version,
    )
    if trade_rate_priors:
        n_buckets = len(trade_rate_priors)
        n_below_floor = sum(
            1
            for s in trade_rate_priors.values()
            if getattr(s, "n_total", 0) < calibration.expected_trade_count.min_bucket_samples
        )
        typer.echo(
            f"trade_rate_priors: buckets={n_buckets} "
            f"below_sample_floor={n_below_floor} "
            f"min_pass_p={calibration.expected_trade_count.min_pass_probability} "
            f"min_samples={calibration.expected_trade_count.min_bucket_samples}"
        )
    try:
        reports = _run_battery_for_seed(
            grammar,
            registry,
            seed,
            max_candidates,
            calibration,
            hypothesis_weights=hypothesis_weights,
            trade_rate_priors=trade_rate_priors,
            forge_db_path=forge_db_path,
            timings=timings,
            require_real_cache=require_real_cache,
        )
    except FeatureCacheUnavailableError:
        # Production safety (2026-05-28 RCA): never filter/submit a batch
        # against the synthetic cache. Skip this iteration; the daemon loop
        # retries on the next poll once Crucible's writer is back.
        typer.echo(
            "skipped: real feature cache unavailable (Crucible writer down?); "
            "refusing to filter/submit on the synthetic fallback. Retrying next poll."
        )
        return "skipped"
    passed = sum(1 for r in reports if r.passed)
    typer.echo(f"enumerated={len(reports)} passed_prefilter={passed}")

    _t_rank = _time.monotonic()
    ranked = rank_batch(
        ranker,
        reports,
        promoted_strategies=tuple(promoted),
        n=batch_size,
    )
    timings["rank"] = _time.monotonic() - _t_rank
    typer.echo(f"ranked_top_n={len(ranked)} (target {batch_size})")
    # D065: complete per-hypothesis funnel — sampler_attempts (input to
    # prefilter) + ranked_top_n_by_hypothesis (output of ranker). With
    # D064's prefilter_rejections_by_hypothesis line in the middle, the
    # journal carries the full per-hypothesis funnel in three lines.
    _log_hypothesis_distributions(reports, ranked)

    if dry_run:
        _echo_dry_run_preview(ranked)
        return "dry-run"

    assert inbox is not None  # CLI guard above
    # H-3/H-7: fold the enumeration-shadowing inputs (auto-tightenings YAML +
    # universe pool) into the batch_id and the recorded identity, so distinct
    # inputs mint distinct batch_ids and a batch is reproducible from state.
    enum_inputs = enumeration_inputs_hash()
    batch = BatchContext(
        batch_id=mint_batch_id(
            seed=seed,
            grammar_version=grammar.grammar_version,
            registry_hash=reg_hash,
            extra_inputs=enum_inputs,
        ),
        grammar_version=grammar.grammar_version,
        registry_hash=reg_hash,
        submitted_at=utc_now(),
        seed=seed,
        enumeration_inputs_hash=enum_inputs,
    )
    _t_submit = _time.monotonic()
    with db_connection(forge_db_path) as conn:
        # D096: persist the funnel's two upstream stages on the batch_summaries
        # row — `enumerated` (configs run through the battery) and `survived`
        # (configs that passed it), plus the per-hypothesis enumerated split.
        result = submit_batch(
            conn,
            batch=batch,
            candidates=ranked,
            inbox_root=inbox,
            enumerated_count=len(reports),
            survived_count=passed,
            enumerated_by_hypothesis=_enumerated_by_hypothesis(reports),
        )
        # D062 + D064: persist per-filter rejection counts to batch_summaries
        # (aggregate + per-hypothesis breakdown). Same connection so the
        # UPDATE sees the INSERT submit_batch just did.
        rejections = record_prefilter_rejections(
            conn,
            batch_id=result.batch_id,
            reports=reports,
        )
        # D076 / Q16: write pre_filter_logs rows for rejected configs too.
        # Pre-D076 the table only held survivor rows (called from
        # submitter), so every filter showed a misleading 100% pass rate.
        # Rejected rows are joinable back to the batch via the new
        # forge_batch_id column; the config_hash column distinguishes
        # them from survivor rows (which now also carry both columns).
        record_pre_filter_logs_for_rejected(
            conn,
            reports=reports,
            batch_id=result.batch_id,
            evaluated_at=batch.submitted_at,
        )
        # D096: refresh the pre-filter funnel export (Part B) + the
        # config_hash->grammar_version join-map (Part A interim) for Crucible's
        # combined funnel. Instrumentation only — a failure here must never
        # crash the production loop, and Crucible's funnel degrades gracefully
        # if the export is stale/absent (their hard rule #7).
        try:
            funnel_path, _ = write_funnel_export(conn, forge_db_path.parent / "exports")
            typer.echo(f"funnel_export: {funnel_path}")
        except Exception as exc:
            typer.echo(f"funnel_export: skipped (non-fatal): {exc}")
    timings["submit"] = _time.monotonic() - _t_submit
    typer.echo(
        f"batch_id={result.batch_id} submitted={result.submitted_count} "
        f"skipped_duplicate={result.skipped_duplicate_count} "
        f"failed={result.failed_count}"
    )
    _log_prefilter_rejections(rejections)
    typer.echo(_format_phase_timings_line(timings))

    if consume_feedback:
        # H-2: analyze the most-recently-completed (most-gated) batch from this
        # iteration's reconcile, NOT result.batch_id — the batch just written to
        # the inbox is 0-gated, so the chain produced nothing on it. None target
        # => no batch has fresh gated data, so skip the chain this iteration.
        feedback_target = _select_feedback_target_batch(
            [(fb.batch_id, fb.gated_count) for fb in reconciled]
        )
        _consume_feedback_after_submit(
            forge_db_path=forge_db_path,
            crucible_db=crucible_db,
            batch_id=feedback_target,
            open_proposals=open_proposals,
            prefilter_yaml=prefilter_yaml,
        )

    return "submitted"


_RUN_DEFAULT_SEED: int = 0
_RUN_DEFAULT_BATCH_SIZE: int = 10
_RUN_DEFAULT_MAX_CANDIDATES: int = 1000
_RUN_DEFAULT_POLL_INTERVAL_SECONDS: int = 600
# H-4 (audit 2026-05-29): no-config fallback for the §7.3 rate-limit threshold.
# Mirrors rate_limiter._DEFAULT_THRESHOLD; forge.yaml's submission.inflight_threshold
# overrides it (previously parsed but never wired to check_rate_limit).
_RUN_DEFAULT_INFLIGHT_THRESHOLD: float = 0.80


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
    inflight_threshold: float


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
    yaml_inflight_threshold: float | None = None
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
        yaml_inflight_threshold = cfg.submission.inflight_threshold

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
        inflight_threshold=yaml_inflight_threshold
        if yaml_inflight_threshold is not None
        else _RUN_DEFAULT_INFLIGHT_THRESHOLD,
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
    require_real_cache: bool = typer.Option(
        False,
        "--require-real-cache",
        help=(
            "skip the iteration (no submit) when Crucible's real feature cache is "
            "unavailable, instead of silently degrading to the synthetic cache. "
            "Production safety; default off so offline dev/test runs work on synthetic."
        ),
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

    from crucible_contracts import SchemaVersionMismatch

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
    inflight_threshold = resolved["inflight_threshold"]

    if not dry_run and inbox is None:
        typer.echo("error: --inbox is required unless --dry-run", err=True)
        raise typer.Exit(code=2)

    # L-9 (audit 2026-05-29): in --loop mode the §7.3 rate limiter is the only
    # backpressure against unbounded submission, and it's silently skipped when
    # crucible_db is None (the rate-limit call site is guarded on it). A loop
    # with no Crucible DB would submit a full batch every poll interval with zero
    # throttle. Production (forge.yaml) always supplies crucible.db_path; this
    # guards the dev/test --no-config invocation. Mirrors the --inbox guard.
    if loop and not dry_run and crucible_db is None:
        typer.echo(
            "error: --crucible-db (or forge.yaml crucible.db_path) is required "
            "with --loop — the §7.3 rate limiter cannot throttle without it",
            err=True,
        )
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
            require_real_cache=require_real_cache,
            inflight_threshold=inflight_threshold,
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
            try:
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
                    require_real_cache=require_real_cache,
                    inflight_threshold=inflight_threshold,
                )
            except (KeyboardInterrupt, SchemaVersionMismatch):
                # SIGINT stops cleanly via the outer handler; a contracts
                # mismatch (§13.5) is a deliberate hard halt. Never swallow.
                raise
            except Exception as exc:
                # One bad iteration (transient DB / IO / export error) must not
                # crash the daemon into a systemd restart loop. Log loudly and
                # continue; poll_interval is the backoff. A persistent error
                # surfaces as a repeating journal line, not a flapping service.
                typer.echo(
                    f"iteration {iteration} failed: {type(exc).__name__}: {exc}; "
                    "continuing next poll",
                    err=True,
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
