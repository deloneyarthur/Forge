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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer

# The orchestrator calls every step through THIS module's namespace so the test seams
# (`monkeypatch.setattr(run_mod, "boot", ...)`, `run_mod._run_battery`) keep working after the
# Batch 6 A4 split; each name's home is the module it is imported from.
from forge.campaign.boot import boot
from forge.campaign.cells import cell_key, classify_dead, load_book
from forge.campaign.decide import cap_budgets, trigger_inputs
from forge.campaign.exports import watermarks
from forge.campaign.gate import challenger_gate
from forge.campaign.generate import (
    _rank,
    _run_battery,
    _scorer,
    dark_cells,
    enumerate_population,
    select_for_campaigns,
)
from forge.campaign.reconcile import reconcile_and_train
from forge.campaign.report import record_factory, write_record
from forge.campaign.stop import CampaignStopped, sigterm_guard
from forge.campaign.submit import _real_feature_cache, _submit
from forge.campaign.triggers import (
    allocate_budgets,
    evaluate_triggers,
)
from forge.campaign.types import (
    Book,
    CampaignConfig,
    CampaignSpec,
    CellKey,
    RunRecord,
    TriggerOutcome,
)
from forge.core.clock import utc_now

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot

    from forge.prefilters.types import PreFilterReport
    from forge.ranking.types import RankedCandidate

Echo = Callable[[str], None]
FeatureCacheFactory = Callable[["RegistrySnapshot", int], object]


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


def run_campaign(
    *,
    forge_db_path: Path,
    exports_dir: Path,
    inbox_root: Path,
    models_dir: Path,
    records_dir: Path,
    config_root: Path,
    cfg: CampaignConfig,
    dry_run: bool,
    budget_override: int | None = None,
    skip_train: bool = False,
    feature_cache_factory: FeatureCacheFactory | None = None,
    echo: Echo = typer.echo,
) -> RunRecord:
    """Execute one weekly run under the SIGTERM stop guard (REL-4) and return its record.

    The guard lives here, not in the CLI, so every caller of a run — the unit, a hand run, a
    test — gets the same stop contract; the CLI only maps the outcome to an exit code."""
    with sigterm_guard():
        return _run_campaign(
            forge_db_path=forge_db_path,
            exports_dir=exports_dir,
            inbox_root=inbox_root,
            models_dir=models_dir,
            records_dir=records_dir,
            config_root=config_root,
            cfg=cfg,
            dry_run=dry_run,
            budget_override=budget_override,
            skip_train=skip_train,
            feature_cache_factory=feature_cache_factory,
            echo=echo,
        )


def _run_campaign(  # noqa: PLR0912, PLR0915 — one straight-line weekly run, echoed step by step
    *,
    forge_db_path: Path,
    exports_dir: Path,
    inbox_root: Path,
    models_dir: Path,
    records_dir: Path,
    config_root: Path,
    cfg: CampaignConfig,
    dry_run: bool,
    budget_override: int | None = None,
    skip_train: bool = False,
    feature_cache_factory: FeatureCacheFactory | None = None,
    echo: Echo = typer.echo,
) -> RunRecord:
    """Execute one weekly run and return its record (also written to ``records_dir``).

    In a dry run nothing is submitted and ``submitted_hashes`` lists the planned
    selection with ``submitted == 0``, so two dry runs on the same watermarks can
    be compared plan-for-plan."""
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
        forge_db_path=forge_db_path,
    )
    for check in booted.checks:
        echo(f"boot {check.name:<16} {'ok  ' if check.ok else 'FAIL'} {check.detail}")

    _record = record_factory(
        run_id=run_id,
        started=started,
        iso_week=week,
        dry_run=dry_run,
        watermarks=marks,
        boot=booted.checks,
    )

    if not booted.ok or booted.grammar is None or booted.registry is None:
        record = _record(status="boot_failed")
        write_record(records_dir, record)
        echo(f"campaign {run_id}: BOOT FAILED — nothing submitted")
        return record

    grammar, registry = booted.grammar, booted.registry
    notes: list[str] = []
    try:
        from forge.enumeration import enumeration_inputs_hash, registry_hash  # noqa: PLC0415
        from forge.grammar.version_audit import (  # noqa: PLC0415
            ensure_grammar_version_recorded_silently,
        )

        # 1. reconcile + 3. stats + 0.5 train (one connection; battery and submit open their own)
        reconciled = reconcile_and_train(
            forge_db_path=forge_db_path,
            exports_dir=exports_dir,
            registry=registry,
            models_dir=models_dir,
            cfg=cfg,
            skip_train=skip_train,
            notes=notes,
            echo=echo,
        )
        stats = reconciled.stats
        models_trained = dict(reconciled.models)
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
        inputs, baselines = trigger_inputs(
            iso_week=week,
            now=started,
            book=book,
            registry=registry,
            exports_dir=exports_dir,
            records_dir=records_dir,
            stats=stats,
            dead=dead,
            dark=dark,
            cfg=cfg,
        )
        # 7. decide
        outcomes = evaluate_triggers(inputs)
        campaigns = cap_budgets(list(allocate_budgets(outcomes, cfg)), budget_override)
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
            "models": models_trained,
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
        batch_id, submitted, unsubmitted = _submit(
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
            reports=reports,
            notes=notes,
        )
        ensure_grammar_version_recorded_silently(
            forge_db_path, grammar=grammar, yaml_path=config_root / "grammar.yaml"
        )
        if unsubmitted:
            # REL-4: SIGTERM arrived mid-batch; the in-flight candidate completed, the rest
            # never started. The record says so and the unit exits non-zero (the page).
            plural = "" if submitted == 1 else "s"
            notes.append(
                f"stopped by SIGTERM after {submitted} submission{plural}; "
                f"{unsubmitted} planned candidate(s) not submitted"
            )
            record = _record(
                status="error", submitted=submitted, batch_id=batch_id, notes=tuple(notes), **common
            )
            write_record(records_dir, record)
            echo(f"campaign {run_id}: STOPPED by SIGTERM after {submitted} (batch {batch_id})")
            raise CampaignStopped(notes[-1])
        record = _record(
            status="ok", submitted=submitted, batch_id=batch_id, notes=tuple(notes), **common
        )
        write_record(records_dir, record)
        echo(f"campaign {run_id}: submitted {submitted} (batch {batch_id})")
        return record
    except CampaignStopped:
        raise
    except Exception as exc:
        notes.append(f"{type(exc).__name__}: {exc}")
        record = _record(status="error", notes=tuple(notes))
        write_record(records_dir, record)
        echo(f"campaign {run_id}: ERROR {type(exc).__name__}: {exc}")
        raise


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
