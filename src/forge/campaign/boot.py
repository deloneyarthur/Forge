"""Step 0 of the weekly run: the boot checks (Batch 6 A4 split from run.py).

WHY a module: every precondition the run refuses on lives here, one `_check` each, so a new
precondition is one function and one line in `boot()`; the orchestrator only asks `ok`.
Any FAIL is exit 2 and a FAILED unit -- the operator's only page (plan 2026-09 §12.2)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from forge.campaign.exports import _EXPORT_GLOBS
from forge.campaign.types import (
    BootCheck,
    CampaignConfig,
)
from forge.core.paths import newest_file

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot

    from forge.grammar.models import Grammar


@dataclass(frozen=True, slots=True)
class _Booted:
    checks: tuple[BootCheck, ...]
    grammar: Grammar | None
    registry: RegistrySnapshot | None

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


# ---------------------------------------------------------------------------
# step 0 — boot
# ---------------------------------------------------------------------------


def _check(name: str, fn: Callable[[], str]) -> BootCheck:
    try:
        return BootCheck(name, True, fn())
    except Exception as exc:
        return BootCheck(name, False, f"{type(exc).__name__}: {exc}")


def _prereg_gate(registry_path: Path, forge_db_path: Path | None) -> str:
    """The DUE judge (Batch 5 G0; formerly the forge-prereg-watch timer): a registered read
    that has come due, or a registration nothing can watch, FAILS the boot so the unit pages —
    a read that drifts past its clock stops being the read that was promised (D389/D392).
    Counts are basis-scoped in SQL; the metric itself is never read."""
    from forge.feedback.preregistration import (  # noqa: PLC0415
        assess_watch_clocks,
        count_basis_rows,
        open_registrations_raw,
    )
    from forge.persistence.db import db_connection  # noqa: PLC0415

    entries = open_registrations_raw(registry_path)
    if not entries:
        return "0 open"
    if forge_db_path is None or not forge_db_path.exists():
        report = assess_watch_clocks(entries, lambda _fp, _since: 0)
    else:
        with db_connection(forge_db_path) as conn:
            report = assess_watch_clocks(
                entries, lambda fp, since: count_basis_rows(conn, fp, since)
            )
    detail = "; ".join(report.lines)
    if report.status != "ok":
        raise RuntimeError(f"{report.status.upper()}: {detail}")
    return f"{len(entries)} open, none due: {detail}"


def boot(
    *,
    exports_dir: Path,
    inbox_root: Path,
    config_root: Path,
    cfg: CampaignConfig,
    now: datetime,
    forge_db_path: Path | None = None,
) -> _Booted:
    """Every precondition the run needs, each as its own row. All run even after
    the first failure so the journal shows the whole picture at once."""
    from crucible_contracts import load_universe_tickers_from_export  # noqa: PLC0415

    from forge.core.contracts_check import check_contracts_version  # noqa: PLC0415
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
            newest = newest_file(exports_dir, glob)
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
        return _prereg_gate(config_root / "preregistrations.jsonl", forge_db_path)

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
