"""The weekly campaign run — boot, reconcile, read the book, decide, generate, gate, submit.

WHY this shape (plan 2026-09 §12.3, corrected by D409): the population never
changes. The run draws the SAME cold-start v55 sequence the goldens pin
(`enumerate_candidates` with no learned weights) and rejection-samples it to
the cells the triggers named, so hard rule #6 and the signed freeze hold; the
only judgement Forge exercises is which members to submit. Everything the
decision read is written to the run record with the export watermarks, so a
later ``--dry-run`` on the same files reproduces the same plan.

Boot failures are the operator's only page: the CLI exits 2 and the systemd
unit goes FAILED (no ``SuccessExitStatus``). After boot, any exception writes
an ``error`` record and re-raises for the same reason.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

import typer

from forge.campaign.cells import cell_key, classify_dead, load_book, load_cell_stats
from forge.campaign.gate import challenger_gate
from forge.campaign.report import (
    baseline_cells,
    baseline_families,
    baseline_ids,
    baseline_str,
    load_latest_record,
    write_record,
)
from forge.campaign.triggers import (
    allocate_budgets,
    cells_with_indicators,
    evaluate_triggers,
    exploration_rotation,
)
from forge.campaign.types import (
    CAMPAIGN_RUN_SCHEMA,
    Book,
    BootCheck,
    CampaignConfig,
    CampaignSpec,
    CellKey,
    CellStats,
    RunRecord,
    TriggerInputs,
    TriggerOutcome,
)
from forge.core.clock import utc_now
from forge.core.seed import SeedHierarchy

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot, StrategyConfig

    from forge.grammar.models import Grammar
    from forge.prefilters.types import PreFilterReport
    from forge.ranking.types import RankedCandidate

Echo = Callable[[str], None]
FeatureCacheFactory = Callable[["RegistrySnapshot", int], object]

_EXPORT_GLOBS: Mapping[str, str] = MappingProxyType(
    {
        "registry": "registry_snapshot_*.json",
        "universe": "universe_tickers_*.json",
        "gated_runs": "gated_runs_*.json",
        "forge_gated_runs": "forge_gated_runs_*.json",
        "failed_runs": "failed_runs_*.json",
        "refutations": "refutations_*.json",
        "promoted_portfolios": "promoted_portfolios_*.json",
        "component_contributions": "component_contributions_*.json",
        "designation_history": "designation_history*.json",
    }
)


@dataclass(frozen=True, slots=True)
class _Booted:
    checks: tuple[BootCheck, ...]
    grammar: Grammar | None
    registry: RegistrySnapshot | None

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def _newest(exports_dir: Path, glob: str) -> Path | None:
    files = sorted(exports_dir.glob(glob), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def watermarks(exports_dir: Path) -> dict[str, str]:
    """``export -> "<file>@<sha256[:12]>"`` for every export the run reads (content, not mtime)."""
    out: dict[str, str] = {}
    for name, glob in _EXPORT_GLOBS.items():
        newest = _newest(exports_dir, glob)
        if newest is not None:
            out[name] = f"{newest.name}@{_sha(newest)[:12]}"
    return out


def derive_seed(grammar_version: str, registry_hash: str, iso_week: str) -> int:
    """One root seed per (grammar, registry, week): the same week on the same inputs
    replays the same plan (hard rule #6); a new registry or a new week moves it."""
    digest = hashlib.blake2b(
        f"{grammar_version}|{registry_hash}|{iso_week}".encode(), digest_size=4
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def iso_week_of(moment: datetime) -> str:
    return moment.strftime("%G-W%V")


# ---------------------------------------------------------------------------
# step 0 — boot
# ---------------------------------------------------------------------------


def _check(name: str, fn: Callable[[], str]) -> BootCheck:
    try:
        return BootCheck(name, True, fn())
    except Exception as exc:
        return BootCheck(name, False, f"{type(exc).__name__}: {exc}")


def boot(
    *,
    exports_dir: Path,
    inbox_root: Path,
    config_root: Path,
    cfg: CampaignConfig,
    now: datetime,
) -> _Booted:
    """Every precondition the run needs, each as its own row. All run even after
    the first failure so the journal shows the whole picture at once."""
    from crucible_contracts import load_universe_tickers_from_export  # noqa: PLC0415

    from forge.core.contracts_check import check_contracts_version  # noqa: PLC0415
    from forge.feedback.preregistration import load_preregistrations  # noqa: PLC0415
    from forge.grammar import load_grammar  # noqa: PLC0415
    from forge.persistence.registry_loader import load_registry  # noqa: PLC0415

    grammar: Grammar | None = None
    registry: RegistrySnapshot | None = None

    def _grammar() -> str:
        nonlocal grammar
        grammar = load_grammar(
            config_root / "grammar.yaml", archive_dir=config_root / "grammar_archive"
        )
        return f"grammar_version={grammar.grammar_version}"

    def _registry() -> str:
        nonlocal registry
        registry = load_registry(exports_dir=exports_dir)
        taken = registry.snapshot_taken_at
        if taken.tzinfo is None:
            taken = taken.replace(tzinfo=UTC)
        age = now - taken
        if age > timedelta(days=cfg.registry_max_age_days):
            msg = f"registry snapshot is {age.days} d old (max {cfg.registry_max_age_days})"
            raise RuntimeError(msg)
        return f"{len(registry.indicators)} indicators, {age.days} d old"

    def _universe() -> str:
        tickers = load_universe_tickers_from_export(exports_dir, max_age_days=None)
        if not tickers:
            msg = "universe export is empty"
            raise RuntimeError(msg)
        return f"{len(tickers)} tickers"

    def _export(glob: str) -> Callable[[], str]:
        def _present() -> str:
            newest = _newest(exports_dir, glob)
            if newest is None:
                msg = f"no {glob} under {exports_dir}"
                raise FileNotFoundError(msg)
            return newest.name

        return _present

    def _inbox() -> str:
        backlog = len(list(inbox_root.glob("*.json"))) if inbox_root.exists() else 0
        if backlog >= cfg.inbox_backlog_ceiling:
            msg = f"inbox backlog {backlog} >= ceiling {cfg.inbox_backlog_ceiling}"
            raise RuntimeError(msg)
        return f"backlog {backlog}"

    def _preregs() -> str:
        # A registered read that is DUE is the watcher's job (forge-prereg-watch until the
        # cutover folds it in); here an open registration is surfaced, never a failure.
        path = config_root / "preregistrations.jsonl"
        if not path.exists():
            return "no registry"
        open_ids = [e.prereg_id for e in load_preregistrations(path) if e.status == "registered"]
        return f"{len(open_ids)} open" + (f": {', '.join(open_ids)}" if open_ids else "")

    checks = (
        _check("contracts", lambda: f"crucible_contracts {check_contracts_version()}"),
        _check("grammar", _grammar),
        _check("registry", _registry),
        _check("universe", _universe),
        _check("gated_runs", _export(_EXPORT_GLOBS["gated_runs"])),
        _check("failed_runs", _export(_EXPORT_GLOBS["failed_runs"])),
        _check("inbox", _inbox),
        _check("preregistrations", _preregs),
    )
    return _Booted(checks=checks, grammar=grammar, registry=registry)


# ---------------------------------------------------------------------------
# steps 5-8 — population, triggers, selection
# ---------------------------------------------------------------------------


def enumerate_population(
    grammar: Grammar,
    registry: RegistrySnapshot,
    *,
    seed: int,
    attempts: int,
    exports_dir: Path,
    now: datetime,
    min_hypothesis_fraction: float,
) -> list[StrategyConfig]:
    """The unchanged cold-start v55 draw, no learned weights (the goldens' population).

    `below_inception` and `refutation_effects` are the loop's structural inputs
    (both fold into `enumeration_inputs_hash`), passed exactly as the loop passes
    them; every weight map stays None. A capped iterator returns what it yielded."""
    from forge.enumeration import (  # noqa: PLC0415
        EnumerationCapped,
        enumerate_candidates,
        resolve_effects,
    )
    from forge.enumeration.chain_inception import underlyings_below_inception  # noqa: PLC0415

    out: list[StrategyConfig] = []
    try:
        for config in enumerate_candidates(
            grammar,
            registry,
            seed=seed,
            max_candidates=attempts,
            below_inception=underlyings_below_inception(now.date(), exports_dir=exports_dir),
            refutation_effects=resolve_effects(exports_dir=exports_dir),
            min_hypothesis_fraction=min_hypothesis_fraction,
        ):
            out.append(config)
    except EnumerationCapped:
        pass
    return out


def dark_cells(
    sample_cells: Iterable[CellKey], stats: Mapping[CellKey, CellStats]
) -> frozenset[CellKey]:
    """Cells the population can produce that Forge has never submitted or judged."""
    dark: set[CellKey] = set()
    for cell in sample_cells:
        st = stats.get(cell)
        if st is None or (st.submitted == 0 and st.decided == 0):
            dark.add(cell)
    return frozenset(dark)


def _refutation_hash(exports_dir: Path) -> str:
    newest = _newest(exports_dir, _EXPORT_GLOBS["refutations"])
    return _sha(newest) if newest is not None else ""


def _refutation_ids(exports_dir: Path) -> frozenset[str]:
    # The ids Forge is currently routing off (bound AND active): a retraction is an id
    # leaving this set. Unbound entries route nothing, so their arrival or departure is
    # not a generation event.
    from forge.enumeration import resolve_effects  # noqa: PLC0415

    return frozenset(resolve_effects(exports_dir=exports_dir).active_entry_ids)


def _claim_rotation(
    sample: Sequence[tuple[StrategyConfig, CellKey]],
    targets: set[CellKey],
    claimed: set[str],
    *,
    cap: int,
    iso_week: str,
) -> list[tuple[StrategyConfig, CellKey]]:
    """T5: walk cells in the weekly rotation so the first-budget cells win deterministically."""
    by_cell: dict[CellKey, list[tuple[StrategyConfig, CellKey]]] = {}
    for config, cell in sample:
        if cell in targets and config.config_hash not in claimed:
            by_cell.setdefault(cell, []).append((config, cell))
    chosen: list[tuple[StrategyConfig, CellKey]] = []
    for cell in exploration_rotation(targets, iso_week):
        for item in by_cell.get(cell, ()):
            if len(chosen) >= cap:
                return chosen
            chosen.append(item)
    return chosen


def _claim_in_order(
    sample: Sequence[tuple[StrategyConfig, CellKey]],
    targets: set[CellKey],
    claimed: set[str],
    *,
    cap: int,
) -> list[tuple[StrategyConfig, CellKey]]:
    chosen: list[tuple[StrategyConfig, CellKey]] = []
    for config, cell in sample:
        if len(chosen) >= cap:
            break
        if cell in targets and config.config_hash not in claimed:
            chosen.append((config, cell))
    return chosen


def select_for_campaigns(
    campaigns: Sequence[CampaignSpec],
    sample: Sequence[tuple[StrategyConfig, CellKey]],
    *,
    cfg: CampaignConfig,
    iso_week: str,
) -> dict[int, list[tuple[StrategyConfig, CellKey]]]:
    """Rejection-sample the population to each campaign's cells, priority order.

    A config belongs to the first campaign that claims it. T5 walks its cells in
    the weekly rotation order so the first-budget cells win deterministically;
    every other campaign keeps enumeration order. Each campaign keeps at most
    ``budget * oversample_factor`` so the battery and gate have headroom."""
    claimed: set[str] = set()
    picked: dict[int, list[tuple[StrategyConfig, CellKey]]] = {}
    for idx, campaign in enumerate(campaigns):
        cap = campaign.budget * cfg.oversample_factor
        targets = set(campaign.cells)
        if campaign.indicator_ids:
            targets |= cells_with_indicators((c for _, c in sample), campaign.indicator_ids)
        if campaign.trigger == "exploration_floor":
            chosen = _claim_rotation(sample, targets, claimed, cap=cap, iso_week=iso_week)
        else:
            chosen = _claim_in_order(sample, targets, claimed, cap=cap)
        claimed.update(c.config_hash for c, _ in chosen)
        picked[idx] = chosen
    return picked


# ---------------------------------------------------------------------------
# steps 9-11 — battery, gate, rank
# ---------------------------------------------------------------------------


def _run_battery(
    configs: Sequence[StrategyConfig],
    *,
    registry: RegistrySnapshot,
    seed: int,
    forge_db_path: Path,
    config_root: Path,
    feature_cache: object,
) -> list[PreFilterReport]:
    from forge.cli.main import (  # noqa: PLC0415
        _load_prior_structural_fingerprints,
        _load_trade_rate_priors,
    )
    from forge.prefilters import default_filters, run_battery  # noqa: PLC0415
    from forge.prefilters.calibration import load_calibration  # noqa: PLC0415
    from forge.prefilters.types import FilterContext  # noqa: PLC0415

    calibration = load_calibration(config_root / "prefilter.yaml")
    ctx = FilterContext(
        registry=registry,
        feature_cache=feature_cache,  # type: ignore[arg-type]
        prior_config_hashes=frozenset(),
        prior_firing_dates={},
        calibration=calibration,
        rng_factory=SeedHierarchy(seed).rng,
        prior_structural_fingerprints=_load_prior_structural_fingerprints(forge_db_path),
        trade_rate_priors=MappingProxyType(
            dict(
                _load_trade_rate_priors(
                    forge_db_path,
                    registry,
                    min_trades=calibration.expected_trade_count.min_trades,
                )
            )
        ),
    )
    prefetch = getattr(feature_cache, "prefetch_for_batch", None)
    if callable(prefetch):
        prefetch(list(configs))
    filters = default_filters()
    return [run_battery(cfg, ctx, filters) for cfg in configs]


def _scorer(
    models_dir: Path, registry: RegistrySnapshot, notes: list[str]
) -> Callable[[StrategyConfig], tuple[float, float]]:
    """(P(component), composite) per config from the newest artifacts; 0.0 without one.

    Never a Jaccard prior: `promoted_strategies` is retiring and read `[]` since 07-06
    (D409), so the old fallback was a zero prior wearing a name."""
    from forge.cli.main import _QUALITY_LANE_TARGET  # noqa: PLC0415
    from forge.ranking.features import extract_features  # noqa: PLC0415
    from forge.ranking.model import (  # noqa: PLC0415
        load_latest_model,
        load_latest_robustness_model,
        robustness_tail_norm,
        score_features,
    )

    verdict = load_latest_model(models_dir)
    robust = (
        load_latest_robustness_model(models_dir, target=_QUALITY_LANE_TARGET)
        if verdict is not None
        else None
    )
    if verdict is None:
        notes.append("rank: no verdict model artifact; scores are 0.0 (enumeration order)")
    elif robust is None:
        notes.append(f"rank: verdict model {verdict.model_id}, no robustness model")
    else:
        notes.append(f"rank: verdict model {verdict.model_id} x tail_norm {robust.model_id}")

    def _score(config: StrategyConfig) -> tuple[float, float]:
        if verdict is None:
            return (0.0, 0.0)
        feats = extract_features(config, registry).as_dict()
        p = min(1.0, max(0.0, score_features(verdict, feats)))
        if robust is None:
            return (p, p)
        return (p, min(1.0, max(0.0, p * robustness_tail_norm(robust, feats))))

    return _score


def _rank(
    survivors: Sequence[tuple[PreFilterReport, CellKey, int]],
    campaigns: Sequence[CampaignSpec],
    score: Callable[[StrategyConfig], tuple[float, float]],
) -> dict[int, list[RankedCandidate]]:
    """Top `budget` per campaign by score; ties keep enumeration order (stable sort)."""
    from forge.ranking.types import RankedCandidate  # noqa: PLC0415

    scored: dict[int, list[tuple[float, RankedCandidate]]] = {}
    for report, _cell, idx in survivors:
        p, composite = score(report.config)
        cand = RankedCandidate(report=report, prior_promotion_score=p, composite_score=composite)
        scored.setdefault(idx, []).append((composite, cand))
    out: dict[int, list[RankedCandidate]] = {}
    for idx, items in scored.items():
        ordered = sorted(items, key=lambda t: -t[0])
        out[idx] = [cand for _, cand in ordered[: campaigns[idx].budget]]
    return out


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------


def _fmt_outcome(outcome: TriggerOutcome) -> str:
    state = "FIRED" if outcome.fired else "quiet"
    return f"trigger {outcome.trigger:<22} {state:<5} {outcome.reason}"


def _fmt_campaign(campaign: CampaignSpec) -> str:
    extra = f" ids={sorted(campaign.indicator_ids)}" if campaign.indicator_ids else ""
    return (
        f"campaign {campaign.trigger:<22} cells={len(campaign.cells)} "
        f"budget={campaign.budget}{extra}"
    )


def run_campaign(  # noqa: PLR0912, PLR0915 — one straight-line weekly run, echoed step by step
    *,
    forge_db_path: Path,
    exports_dir: Path,
    inbox_root: Path,
    models_dir: Path,
    records_dir: Path,
    config_root: Path,
    crucible_db: Path,
    cfg: CampaignConfig,
    dry_run: bool,
    budget_override: int | None = None,
    feature_cache_factory: FeatureCacheFactory | None = None,
    echo: Echo = typer.echo,
) -> RunRecord:
    """Execute one weekly run and return its record (also written to ``records_dir``).

    In a dry run nothing is submitted and ``submitted_hashes`` lists the planned
    selection with ``submitted == 0``, so two dry runs on the same watermarks can
    be compared plan-for-plan."""
    from forge.persistence.db import db_connection  # noqa: PLC0415

    started = utc_now()
    week = iso_week_of(started)
    run_id = f"{week}-{started:%Y%m%dT%H%M%SZ}"
    marks = watermarks(exports_dir)
    booted = boot(
        exports_dir=exports_dir,
        inbox_root=inbox_root,
        config_root=config_root,
        cfg=cfg,
        now=started,
    )
    for check in booted.checks:
        echo(f"boot {check.name:<16} {'ok  ' if check.ok else 'FAIL'} {check.detail}")

    def _record(**overrides: object) -> RunRecord:
        base: dict[str, object] = {
            "schema_version": CAMPAIGN_RUN_SCHEMA,
            "run_id": run_id,
            "started_at": started,
            "finished_at": utc_now(),
            "dry_run": dry_run,
            "status": "boot_failed",
            "grammar_version": None,
            "registry_hash": None,
            "enumeration_inputs_hash": None,
            "seed": None,
            "iso_week": week,
            "watermarks": marks,
            "boot": booted.checks,
            "designated_id": None,
            "triggers": (),
            "campaigns": (),
            "enumerated": 0,
            "kept_in_cells": 0,
            "survived_battery": 0,
            "gated_out": {},
            "submitted": 0,
            "submitted_hashes": (),
            "batch_id": None,
            "baselines": {},
            "notes": (),
        }
        base.update(overrides)
        return RunRecord(**base)  # type: ignore[arg-type]

    if not booted.ok or booted.grammar is None or booted.registry is None:
        record = _record(status="boot_failed")
        write_record(records_dir, record)
        echo(f"campaign {run_id}: BOOT FAILED — nothing submitted")
        return record

    grammar, registry = booted.grammar, booted.registry
    notes: list[str] = []
    try:
        from crucible_contracts import load_forge_gated_runs_from_export  # noqa: PLC0415

        from forge.cli.main import _ensure_grammar_version_recorded_silently  # noqa: PLC0415
        from forge.enumeration import enumeration_inputs_hash, registry_hash  # noqa: PLC0415
        from forge.feedback.consumer import reconcile_all_pending  # noqa: PLC0415

        # 1. reconcile + 3. stats (one connection; the battery and submit open their own)
        # The forge-scoped 14-day stream (contracts 1.48.0, D412) is the campaign's ledger: a
        # weekly run that boots cold still sees its prior run. Until the cutover the daemon's
        # rate floods it past the 10k cap and it reads `truncated: true` -- then the OLDEST
        # verdicts are the missing ones, so no aged-out flush; after cutover a truncated file
        # means something else is flooding source='forge' and is worth a relay.
        forge_stream = load_forge_gated_runs_from_export(exports_dir)
        with db_connection(forge_db_path) as conn:
            if forge_stream is None:
                notes.append("forge_gated_runs: absent; reconciled from the all-source export")
                echo("reconcile: forge_gated_runs stream ABSENT; all-source export used")
                feedback = reconcile_all_pending(conn, crucible_db, exports_dir=exports_dir)
            else:
                newest_forge = _newest(exports_dir, _EXPORT_GLOBS["forge_gated_runs"])
                n_rows = len(forge_stream.gated_runs)
                span = (
                    f"{n_rows} rows, lookback {forge_stream.lookback_days} d, "
                    f"cap {forge_stream.cap}, truncated={forge_stream.truncated}"
                )
                notes.append(f"forge_gated_runs: {span}")
                warn = (
                    "; WINDOW TRUNCATED: oldest verdicts missing, aged-out flush skipped"
                    if forge_stream.truncated
                    else ""
                )
                echo(f"reconcile: forge_gated_runs {span}{warn}")
                feedback = reconcile_all_pending(
                    conn,
                    crucible_db,
                    exports_dir=exports_dir,
                    runs=forge_stream.gated_runs,
                    source_export=newest_forge.name if newest_forge is not None else None,
                    flush_aged_out=not forge_stream.truncated,
                )
            reconciled = sum(len(fb.outcomes) for fb in feedback)
            notes.append(f"reconciled {reconciled} outcome(s) across {len(feedback)} batch(es)")
            stats = load_cell_stats(conn)
        # 2. the book
        book: Book = load_book(exports_dir)
        dead = classify_dead(stats, cfg)
        # 4. identity
        reg_hash = registry_hash(registry)
        enum_inputs = enumeration_inputs_hash()
        seed = derive_seed(grammar.grammar_version, reg_hash, week)
        echo(
            f"campaign {run_id}: grammar_version={grammar.grammar_version} "
            f"registry_hash={reg_hash} seed={seed} designated={book.designated_id}"
        )
        # 5. the unchanged population
        population = enumerate_population(
            grammar,
            registry,
            seed=seed,
            attempts=cfg.enumeration_attempts,
            exports_dir=exports_dir,
            now=started,
            min_hypothesis_fraction=cfg.min_hypothesis_fraction,
        )
        sample = [(config, cell_key(config)) for config in population]
        dark = dark_cells((cell for _, cell in sample), stats)
        # 6. previous record -> trigger inputs
        prev = load_latest_record(records_dir)
        book_cells_now = frozenset(
            leg.cell for leg in book.legs if leg.portfolio_id == book.designated_id
        )
        families_now = {meta.id: meta.family for meta in registry.indicators}
        ref_hash_now = _refutation_hash(exports_dir)
        ref_ids_now = _refutation_ids(exports_dir)
        inputs = TriggerInputs(
            iso_week=week,
            designated_now=book.designated_id,
            designated_prev=prev.designated_id if prev is not None else None,
            book_cells_now=book_cells_now,
            book_cells_prev=baseline_cells(prev) if prev is not None else None,
            refutation_hash_now=ref_hash_now,
            refutation_hash_prev=baseline_str(prev, "refutation_hash") if prev else None,
            refutation_ids_now=ref_ids_now,
            refutation_ids_prev=baseline_ids(prev, "refutation_ids") if prev else None,
            registry_ids_now=frozenset(families_now),
            registry_ids_prev=baseline_ids(prev, "registry_ids") if prev else None,
            registry_families_now=families_now,
            registry_families_prev=baseline_families(prev) if prev else None,
            cell_stats=stats,
            protected=book.protected_cells,
            dead=dead,
            dark=dark,
            now=started,
            config=cfg,
        )
        baselines: dict[str, object] = {
            "book_cells": sorted(book_cells_now),
            "refutation_hash": ref_hash_now,
            "refutation_ids": sorted(ref_ids_now),
            "registry_ids": sorted(families_now),
            "registry_families": families_now,
        }
        # 7. decide
        outcomes = evaluate_triggers(inputs)
        campaigns = list(allocate_budgets(outcomes, cfg))
        if budget_override is not None:
            remaining = budget_override
            capped: list[CampaignSpec] = []
            for campaign in campaigns:
                take = min(campaign.budget, remaining)
                if take > 0:
                    capped.append(
                        CampaignSpec(
                            campaign.trigger,
                            campaign.cells,
                            take,
                            campaign.reason,
                            campaign.replacement_for,
                            campaign.indicator_ids,
                        )
                    )
                    remaining -= take
            campaigns = capped
        for outcome in outcomes:
            echo(_fmt_outcome(outcome))
        common = {
            "grammar_version": grammar.grammar_version,
            "registry_hash": reg_hash,
            "enumeration_inputs_hash": enum_inputs,
            "seed": seed,
            "designated_id": book.designated_id,
            "triggers": tuple(outcomes),
            "campaigns": tuple(campaigns),
            "enumerated": len(sample),
            "baselines": baselines,
        }
        if not campaigns:
            notes.append(f"dark cells seen: {len(dark)}; protected: {len(book.protected_cells)}")
            record = _record(status="no_trigger", notes=tuple(notes), **common)
            write_record(records_dir, record)
            echo(f"campaign {run_id}: no trigger; boot OK (enumerated {len(sample)}, submitted 0)")
            return record
        for campaign in campaigns:
            echo(_fmt_campaign(campaign))
        # 8. rejection-sample
        picked = select_for_campaigns(campaigns, sample, cfg=cfg, iso_week=week)
        kept = [(config, cell, idx) for idx, items in picked.items() for config, cell in items]
        # 9. battery
        feature_cache = (
            feature_cache_factory(registry, seed)
            if feature_cache_factory is not None
            else _real_feature_cache(registry, seed)
        )
        reports = _run_battery(
            [config for config, _, _ in kept],
            registry=registry,
            seed=seed,
            forge_db_path=forge_db_path,
            config_root=config_root,
            feature_cache=feature_cache,
        )
        survivors = [
            (report, cell, idx)
            for report, (_, cell, idx) in zip(reports, kept, strict=True)
            if report.passed
        ]
        # 10. gate
        gated_out: Counter[str] = Counter()
        admitted: list[tuple[PreFilterReport, CellKey, int]] = []
        for report, cell, idx in survivors:
            decision = challenger_gate(
                report.config, cell, book=book, campaign=campaigns[idx], dead=dead, cfg=cfg
            )
            if decision.keep:
                admitted.append((report, cell, idx))
            else:
                gated_out[str(decision.reason)] += 1
        # 11. rank in-cell
        ranked_by = _rank(admitted, campaigns, _scorer(models_dir, registry, notes))
        ranked: list[RankedCandidate] = []
        lanes: dict[str, frozenset[str]] = {}
        for idx, cands in ranked_by.items():
            ranked.extend(cands)
            tag = f"campaign:{campaigns[idx].trigger}"
            lanes[tag] = lanes.get(tag, frozenset()) | frozenset(
                c.report.config.config_hash for c in cands
            )
        planned = tuple(c.report.config.config_hash for c in ranked)
        echo(
            f"selection: enumerated={len(sample)} kept={len(kept)} survived={len(survivors)} "
            f"gated_out={dict(gated_out)} planned={len(planned)}"
        )
        common.update(
            {
                "kept_in_cells": len(kept),
                "survived_battery": len(survivors),
                "gated_out": dict(gated_out),
                "submitted_hashes": planned,
            }
        )
        if dry_run:
            record = _record(status="ok", submitted=0, notes=tuple(notes), **common)
            write_record(records_dir, record)
            echo(f"campaign {run_id}: DRY RUN — planned {len(planned)}, submitted 0")
            return record
        # 12. submit
        batch_id, submitted = _submit(
            ranked,
            lanes=lanes,
            forge_db_path=forge_db_path,
            inbox_root=inbox_root,
            models_dir=models_dir,
            registry=registry,
            grammar_version=grammar.grammar_version,
            reg_hash=reg_hash,
            enum_inputs=enum_inputs,
            seed=seed,
            enumerated=len(sample),
            survived=len(survivors),
            by_hypothesis=Counter(config.hypothesis for config, _ in sample),
            notes=notes,
        )
        _ensure_grammar_version_recorded_silently(
            forge_db_path, grammar=grammar, yaml_path=config_root / "grammar.yaml"
        )
        record = _record(
            status="ok", submitted=submitted, batch_id=batch_id, notes=tuple(notes), **common
        )
        write_record(records_dir, record)
        echo(f"campaign {run_id}: submitted {submitted} (batch {batch_id})")
        return record
    except Exception as exc:
        notes.append(f"{type(exc).__name__}: {exc}")
        record = _record(status="error", notes=tuple(notes))
        write_record(records_dir, record)
        echo(f"campaign {run_id}: ERROR {type(exc).__name__}: {exc}")
        raise


def _real_feature_cache(registry: RegistrySnapshot, seed: int) -> object:
    from forge.cli.main import _build_feature_cache  # noqa: PLC0415

    return _build_feature_cache(registry, seed, require_real=True)


def _submit(
    ranked: Sequence[RankedCandidate],
    *,
    lanes: Mapping[str, frozenset[str]],
    forge_db_path: Path,
    inbox_root: Path,
    models_dir: Path,
    registry: RegistrySnapshot,
    grammar_version: str,
    reg_hash: str,
    enum_inputs: str,
    seed: int,
    enumerated: int,
    survived: int,
    by_hypothesis: Mapping[str, int],
    notes: list[str],
) -> tuple[str, int]:
    from forge.cli.main import _QUALITY_LANE_TARGET  # noqa: PLC0415
    from forge.funnel.export import write_funnel_export  # noqa: PLC0415
    from forge.persistence.db import db_connection  # noqa: PLC0415
    from forge.ranking.shadow import run_shadow_scoring  # noqa: PLC0415
    from forge.submission.batch import BatchContext, mint_batch_id  # noqa: PLC0415
    from forge.submission.search_multiplicity import (  # noqa: PLC0415
        crucible_record_not_bind_live,
        slot_counts,
        stamp_search_n_trials,
    )
    from forge.submission.submitter import submit_batch  # noqa: PLC0415

    batch = BatchContext(
        batch_id=mint_batch_id(
            seed=seed,
            grammar_version=grammar_version,
            registry_hash=reg_hash,
            extra_inputs=f"{enum_inputs}|campaign",
        ),
        grammar_version=grammar_version,
        registry_hash=reg_hash,
        submitted_at=utc_now(),
        seed=seed,
        enumeration_inputs_hash=enum_inputs,
    )
    candidates = list(ranked)
    with db_connection(forge_db_path) as conn:
        if crucible_record_not_bind_live(conn):
            candidates = stamp_search_n_trials(candidates, slot_counts(conn))
            notes.append("search_n_trials: stamped")
        result = submit_batch(
            conn,
            batch=batch,
            candidates=candidates,
            inbox_root=inbox_root,
            enumerated_count=enumerated,
            survived_count=survived,
            enumerated_by_hypothesis=dict(by_hypothesis),
            extra_lane_hashes=lanes,
        )
        try:
            funnel_path, _ = write_funnel_export(conn, forge_db_path.parent / "exports")
            notes.append(f"funnel_export: {funnel_path.name}")
        except Exception as exc:
            notes.append(f"funnel_export skipped: {type(exc).__name__}: {exc}")
        shadow = run_shadow_scoring(
            conn,
            models_dir=models_dir,
            candidates=candidates,
            registry=registry,
            batch_id=str(result.batch_id),
            scored_at=batch.submitted_at,
            robustness_target=_QUALITY_LANE_TARGET,
        )
        if shadow:
            notes.append(f"shadow_scores={shadow}")
    notes.append(
        f"submit: {result.submitted_count} submitted, {result.skipped_duplicate_count} duplicate, "
        f"{result.failed_count} failed"
    )
    return (str(result.batch_id), result.submitted_count)


__all__ = [
    "boot",
    "dark_cells",
    "derive_seed",
    "enumerate_population",
    "iso_week_of",
    "run_campaign",
    "select_for_campaigns",
    "watermarks",
]
