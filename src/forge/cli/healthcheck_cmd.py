"""`forge healthcheck` — does the daemon look alive AND productive? (ops-sprint item 3)

systemd only knows whether the *process* is up (`Restart=on-failure`). It cannot see
the failure modes that actually bite this pipeline, all of which present as a perfectly
healthy-looking process:

  * **Wedged loop** — the process is `active` but the iteration loop has stopped (the
    `futex_do_wait` at 0% CPU signature). `registry_loaded_from_export` logs *before*
    validation, so the journal's last lines can look normal while nothing advances.
  * **Chronically stalled pipeline** — the loop iterates fine but submits nothing for
    hours/days because Crucible's gate is wedged (the D137 stall guard correctly holding).
    This is *correct* Forge behaviour, but the operator must still be told the pipeline
    is stuck — nothing alerts on it today (the ~32 h stall that motivated this item).
  * **Broken side-timers** — the daily backup (D195) or ranker-eval timer silently stops
    publishing, so backups/models quietly go stale.
  * **Un-adopted contracts** — installed `crucible_contracts` drifts from the pin; the
    §13.5 runtime check is MAJOR-only, so a minor bump runs un-adopted (and a reboot
    surfaces it as a hard halt later).

The checks read the JOURNAL (liveness, submission progress + the block reason — cheap,
no 4.5 GB DB snapshot, and it's what the operator already reads) and the FILESYSTEM
(backup/model freshness), plus the contracts pin. The pure check functions take already-
extracted values so they are fully unit-tested; only the gather glue touches subprocess.

Exit code = the worst level (0 OK / 1 WARN / 2 CRITICAL) for scriptability. The
`forge-healthcheck` timer's unit sets `SuccessExitStatus=1` so only CRITICAL marks the
unit failed (surfacing in the operator's `systemctl --user --state=failed` routine);
WARN stays informational in the journal.
"""

from __future__ import annotations

import enum
import json
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

import typer

from forge.core.clock import utc_now


class Level(enum.IntEnum):
    """Health severity; the int value doubles as the process exit code."""

    OK = 0
    WARN = 1
    CRITICAL = 2


@dataclass(frozen=True, slots=True)
class HealthResult:
    name: str
    level: Level
    message: str


@dataclass(frozen=True, slots=True)
class JournalState:
    """What the daemon's recent journal tells us about progress."""

    last_iteration_at: datetime | None
    last_submit_at: datetime | None
    last_block_at: datetime | None
    last_block_reason: str | None
    # P3.2 (B6): the §6.2 sampler's `_load_hypothesis_weights` degraded to uniform (the
    # learned yield weights failed to load) — a silent-degrade that mutes the whole
    # feedback loop. Warn-once in the daemon; surfaced here so it isn't invisible.
    hypothesis_weights_degraded_at: datetime | None = None


# `<iso-ts> <host> forge[<pid>]: <message>` (journalctl -o short-iso).
_JOURNAL_LINE = re.compile(r"^(?P<ts>\S+)\s+\S+\s+forge\[\d+\]:\s+(?P<msg>.*)$")
_ITER_PREFIX = "--- loop iteration"
_BLOCK_PREFIX = "blocked:"
_SUBMIT_RE = re.compile(r"\bsubmitted=(?P<n>\d+)\b")
_HYPWEIGHTS_DEGRADE_PREFIX = "hypothesis_weights: degraded"


def parse_forge_journal(lines: Iterable[str]) -> JournalState:
    """Extract the newest iteration / successful-submit / block events.

    Pure: feed it `journalctl -o short-iso` lines (or test fixtures). A submit
    counts only when `submitted=N` has N>0 — a `submitted=0` line is a completed
    cycle that produced no batch, which must not reset the "last submission" clock.
    """
    last_iteration_at: datetime | None = None
    last_submit_at: datetime | None = None
    last_block_at: datetime | None = None
    last_block_reason: str | None = None
    hypothesis_weights_degraded_at: datetime | None = None

    for line in lines:
        m = _JOURNAL_LINE.match(line.rstrip("\n"))
        if m is None:
            continue
        try:
            ts = datetime.fromisoformat(m.group("ts"))
        except ValueError:
            continue
        msg = m.group("msg")
        if msg.startswith(_ITER_PREFIX):
            last_iteration_at = ts
        elif msg.startswith(_BLOCK_PREFIX):
            last_block_at = ts
            last_block_reason = msg[len(_BLOCK_PREFIX) :].strip()
        elif msg.startswith(_HYPWEIGHTS_DEGRADE_PREFIX):
            hypothesis_weights_degraded_at = ts
        else:
            sm = _SUBMIT_RE.search(msg)
            if sm is not None and int(sm.group("n")) > 0:
                last_submit_at = ts

    return JournalState(
        last_iteration_at=last_iteration_at,
        last_submit_at=last_submit_at,
        last_block_at=last_block_at,
        last_block_reason=last_block_reason,
        hypothesis_weights_degraded_at=hypothesis_weights_degraded_at,
    )


def _age_hours(then: datetime, now: datetime) -> float:
    return (now - then).total_seconds() / 3600.0


def check_service_active(is_active: bool) -> HealthResult:
    """The most basic signal: did systemd give up restarting the daemon?"""
    if is_active:
        return HealthResult("service", Level.OK, "forge.service active")
    return HealthResult(
        "service", Level.CRITICAL, "forge.service is NOT active (crashed / stopped)"
    )


def check_loop_liveness(
    last_iteration_at: datetime | None,
    now: datetime,
    *,
    warn_minutes: float,
    critical_minutes: float,
) -> HealthResult:
    """The loop is alive iff it keeps emitting iteration lines.

    Catches the up-but-wedged case systemd can't: a stale iteration clock while
    the process stays `active`.
    """
    if last_iteration_at is None:
        return HealthResult("loop", Level.CRITICAL, "no loop-iteration lines in the journal window")
    mins = (now - last_iteration_at).total_seconds() / 60.0
    if mins >= critical_minutes:
        return HealthResult(
            "loop", Level.CRITICAL, f"loop wedged: last iteration {mins:.0f} min ago"
        )
    if mins >= warn_minutes:
        return HealthResult("loop", Level.WARN, f"last iteration {mins:.0f} min ago")
    return HealthResult("loop", Level.OK, f"iterating (last {mins:.0f} min ago)")


def check_submission_progress(
    last_submit_at: datetime | None,
    now: datetime,
    *,
    last_block_reason: str | None,
    warn_hours: float,
    critical_hours: float,
) -> HealthResult:
    """Is the pipeline actually producing? Distinct from loop liveness.

    A loop that iterates but never submits (a long block) is a stuck pipeline; the
    operator must hear about it even though Forge is behaving correctly. The block
    reason (e.g. "crucible stalled …") is carried into the message so the alert
    points upstream where it belongs.
    """
    reason = f"; last block: {last_block_reason}" if last_block_reason else ""
    if last_submit_at is None:
        return HealthResult(
            "submission",
            Level.CRITICAL,
            f"no successful submission in the journal window{reason}",
        )
    hrs = _age_hours(last_submit_at, now)
    if hrs >= critical_hours:
        return HealthResult("submission", Level.CRITICAL, f"no submission in {hrs:.1f}h{reason}")
    if hrs >= warn_hours:
        return HealthResult("submission", Level.WARN, f"no submission in {hrs:.1f}h{reason}")
    return HealthResult("submission", Level.OK, f"submitting (last {hrs:.1f}h ago)")


def check_file_freshness(
    newest_mtime: datetime | None,
    now: datetime,
    *,
    label: str,
    warn_hours: float,
    critical_hours: float,
) -> HealthResult:
    """Generic staleness check for the daily-timer outputs (backups, models)."""
    if newest_mtime is None:
        return HealthResult(label, Level.WARN, f"no {label} found")
    hrs = _age_hours(newest_mtime, now)
    if hrs >= critical_hours:
        return HealthResult(label, Level.CRITICAL, f"newest {label} is {hrs:.1f}h old")
    if hrs >= warn_hours:
        return HealthResult(label, Level.WARN, f"newest {label} is {hrs:.1f}h old")
    return HealthResult(label, Level.OK, f"fresh ({hrs:.1f}h old)")


def check_component_contributions_export(
    newest_mtime: datetime | None,
    now: datetime,
) -> HealthResult:
    """Soft presence check for Crucible's `component_contributions` export (D216).

    The export is scored per-promoted-PORTFOLIO (leave-one-out
    `correlation_to_incumbent` / `marginal_sharpe`), so it is **absent until the
    first promotion** — that is the PBO wall, not a fault. Absence therefore
    returns OK (never a WARN that would pollute OVERALL); present → OK with age.
    Forward-looking ops instrumentation: once books promote and Crucible's
    publisher runs, this shows the Layer-1 contribution signal is flowing (the
    estimand re-aim, held per D216, consumes it). No typed read — glob+mtime
    only, so it does not pre-empt the contracts-hosted loader."""
    label = "component_contributions"
    if newest_mtime is None:
        return HealthResult(label, Level.OK, "no export yet (expected until first promotion)")
    hrs = _age_hours(newest_mtime, now)
    return HealthResult(label, Level.OK, f"present ({hrs:.1f}h old)")


def check_contracts_pin(pinned: str, installed: str) -> HealthResult:
    """Surface contracts drift before a reboot turns it into a hard halt.

    Equal = OK. Same major = WARN (the §13.5 runtime check is MAJOR-only, so a minor
    bump runs un-adopted — read the release + bump the pin). Different major = CRITICAL.
    """
    if pinned == installed:
        return HealthResult("contracts", Level.OK, f"pin == installed ({installed})")
    pinned_major = pinned.split(".", 1)[0]
    installed_major = installed.split(".", 1)[0]
    if pinned_major == installed_major:
        return HealthResult(
            "contracts",
            Level.WARN,
            f"installed {installed} != pin {pinned} (un-adopted minor; adopt it)",
        )
    return HealthResult(
        "contracts",
        Level.CRITICAL,
        f"installed {installed} != pin {pinned} (MAJOR drift — daemon will halt)",
    )


# Drift floors for the learned lanes surfaced by `forge status`. CRITICAL = the lane
# is clearly anti-predictive (worse than no model); the WARN floor = it has lost its
# edge over the §6.2 composite. Conservative, to avoid crying wolf on a noisy small-n
# checkpoint — the regression check (vs the lane's own trailing median) catches drift
# that stays above the floor.
_F3_WARN_BELOW: float = 0.0
_F3_CRITICAL_BELOW: float = -0.05
_TAIL_WARN_BELOW: float = 0.0
_TAIL_CRITICAL_BELOW: float = -0.10


def check_learning_drift(
    values: Sequence[float],
    *,
    label: str,
    warn_below: float,
    critical_below: float,
    regression_delta: float,
    min_history: int = 4,
) -> HealthResult:
    """Flag a learned model that has degraded — the drift a blind daily retrain invites.

    Model adoption is newest-wins (`ranking/model.py`): a bad rotation silently goes
    live and only a human reading `forge status` would catch it. This makes it loud.
    `values` are the qualifying shadow-eval checkpoints (oldest->newest) for one lane —
    AUC margin for F3, Spearman for the wf_p25 tail. CRITICAL when the latest is at or
    below the anti-predictive floor; WARN when it is merely weak or has dropped sharply
    from its own trailing median. Complements D192 continuous training (catches
    regressions) without holding back improvements (no champion/challenger gate).
    """
    if not values:
        return HealthResult(label, Level.WARN, f"{label}: no qualifying eval checkpoints yet")
    latest = values[-1]
    if latest <= critical_below:
        return HealthResult(
            label,
            Level.CRITICAL,
            f"{label} degraded: latest {latest:+.3f} <= floor {critical_below:+.3f}",
        )
    if len(values) >= min_history:
        prior_median = median(values[-min_history:-1])
        if latest <= prior_median - regression_delta:
            return HealthResult(
                label,
                Level.WARN,
                f"{label} regressed: latest {latest:+.3f} vs trailing median {prior_median:+.3f}",
            )
    if latest <= warn_below:
        return HealthResult(
            label, Level.WARN, f"{label} weak: latest {latest:+.3f} <= floor {warn_below:+.3f}"
        )
    return HealthResult(label, Level.OK, f"{label} ok (latest {latest:+.3f})")


def check_hypothesis_weights_fallback(journal: JournalState) -> HealthResult:
    """P3.2 (B6): the §6.2 sampler degraded to UNIFORM hypothesis sampling (the learned
    yield/cohort weights failed to load) — the feedback loop is silently muted. WARN
    (not CRITICAL: the daemon still produces; it just stops steering) when the degrade
    line appears in the journal window."""
    when = journal.hypothesis_weights_degraded_at
    if when is None:
        return HealthResult("hypothesis_weights", Level.OK, "hypothesis weights: learned (loaded)")
    return HealthResult(
        "hypothesis_weights",
        Level.WARN,
        f"hypothesis weights: UNIFORM-fallback active (learned load failed; {when:%Y-%m-%d %H:%M})",
    )


def _newest_mtime(directory: Path, pattern: str) -> datetime | None:
    if not directory.is_dir():
        return None
    newest: float | None = None
    for p in directory.glob(pattern):
        mt = p.stat().st_mtime
        if newest is None or mt > newest:
            newest = mt
    if newest is None:
        return None
    return datetime.fromtimestamp(newest, tz=utc_now().tzinfo)


def _read_metric_series(path: Path, metric_key: str) -> list[float]:
    """Qualifying metric values (oldest->newest) from a ranker-eval streak JSONL.

    Mirrors `forge status`: skip non-qualifying checkpoints (stall day / single-class
    window) so the drift verdict isn't tripped by a known-degenerate eval. Cheap and
    lock-free — the JSONL clocks carry no DB lock.
    """
    if not path.is_file():
        return []
    out: list[float] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict) or not rec.get("qualifies"):
            continue
        value = rec.get(metric_key)
        if isinstance(value, (int, float)):
            out.append(float(value))
    return out


def _gather_journal(window_hours: float) -> JournalState | None:
    """Read forge.service's recent journal. None = journalctl unavailable/failed."""
    try:
        proc = subprocess.run(
            [
                "journalctl",
                "--user",
                "-u",
                "forge.service",
                "--since",
                f"-{int(window_hours)}h",
                "-o",
                "short-iso",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return parse_forge_journal(proc.stdout.splitlines())


def _service_is_active() -> bool:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "forge.service"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.stdout.strip() == "active"


def cmd_healthcheck(
    data_root: Path = typer.Option(
        Path("~/forge_data").expanduser(), "--data-root", help="Forge data root"
    ),
    submission_warn_hours: float = typer.Option(
        6.0, help="WARN if no submission in this many hours"
    ),
    submission_critical_hours: float = typer.Option(
        24.0, help="CRITICAL if no submission in this many hours"
    ),
    loop_warn_minutes: float = typer.Option(
        15.0, help="WARN if no loop iteration in this many minutes"
    ),
    loop_critical_minutes: float = typer.Option(
        30.0, help="CRITICAL if no loop iteration in this many minutes"
    ),
    drift_regression_delta: float = typer.Option(
        0.25, help="WARN if a learned lane's metric drops this far below its trailing median"
    ),
) -> None:
    """Report daemon health (alive AND productive); exit 0/1/2 = OK/WARN/CRITICAL."""
    from crucible_contracts import CONTRACT_VERSION

    from forge.core.contracts_check import FORGE_EXPECTED_CONTRACT_VERSION

    now = utc_now()
    results: list[HealthResult] = [check_service_active(_service_is_active())]

    journal = _gather_journal(window_hours=max(submission_critical_hours, 48.0))
    if journal is None:
        results.append(
            HealthResult("journal", Level.WARN, "journalctl unavailable — skipped liveness checks")
        )
    else:
        results.append(
            check_loop_liveness(
                journal.last_iteration_at,
                now,
                warn_minutes=loop_warn_minutes,
                critical_minutes=loop_critical_minutes,
            )
        )
        results.append(
            check_submission_progress(
                journal.last_submit_at,
                now,
                last_block_reason=journal.last_block_reason,
                warn_hours=submission_warn_hours,
                critical_hours=submission_critical_hours,
            )
        )

    results.append(
        check_file_freshness(
            _newest_mtime(data_root / "backups", "forge_db_*.duckdb"),
            now,
            label="backup",
            warn_hours=26.0,
            critical_hours=50.0,
        )
    )
    results.append(
        check_file_freshness(
            _newest_mtime(data_root / "models", "verdict_model_*.json"),
            now,
            label="model",
            warn_hours=26.0,
            critical_hours=50.0,
        )
    )
    results.append(check_contracts_pin(FORGE_EXPECTED_CONTRACT_VERSION, CONTRACT_VERSION))
    # Crucible's component_contributions export (D216): the Layer-1 decorrelated-
    # supply signal. Soft — absent is expected until the first promotion.
    results.append(
        check_component_contributions_export(
            _newest_mtime(Path.home() / "optbt_data" / "exports", "component_contributions_*.json"),
            now,
        )
    )

    # Learned-lane drift: a blind daily retrain (newest-wins adoption) can rotate a
    # degraded model live; catch it loudly instead of waiting for a human to read the
    # `forge status` clocks. Reads the same JSONL clocks (no DB).
    eval_dir = data_root / "ranker_eval"
    results.append(
        check_learning_drift(
            _read_metric_series(eval_dir / "streak.jsonl", "auc_margin"),
            label="F3 ranker drift",
            warn_below=_F3_WARN_BELOW,
            critical_below=_F3_CRITICAL_BELOW,
            regression_delta=drift_regression_delta,
        )
    )
    results.append(
        check_learning_drift(
            # P3.2/D229: read the PAIRED delta (tail Spearman - incumbent), the real
            # adoption signal — a negative delta means the lane is worse than the
            # incumbent it would rotate over. Legacy rows (pre-delta) contribute nothing.
            _read_metric_series(eval_dir / "robustness_streak_wfp25.jsonl", "spearman_delta"),
            label="wf_p25 drift",
            warn_below=_TAIL_WARN_BELOW,
            critical_below=_TAIL_CRITICAL_BELOW,
            regression_delta=drift_regression_delta,
        )
    )
    if journal is not None:
        results.append(check_hypothesis_weights_fallback(journal))

    overall = max((r.level for r in results), default=Level.OK)
    for r in results:
        typer.echo(f"[{r.level.name:^4}] {r.name}: {r.message}")
    n_ok = sum(1 for r in results if r.level is Level.OK)
    n_warn = sum(1 for r in results if r.level is Level.WARN)
    n_crit = sum(1 for r in results if r.level is Level.CRITICAL)
    typer.echo(f"healthcheck: OVERALL={overall.name} ({n_ok} ok, {n_warn} warn, {n_crit} crit)")
    raise typer.Exit(code=int(overall))


__all__ = [
    "HealthResult",
    "JournalState",
    "Level",
    "check_component_contributions_export",
    "check_contracts_pin",
    "check_file_freshness",
    "check_hypothesis_weights_fallback",
    "check_learning_drift",
    "check_loop_liveness",
    "check_service_active",
    "check_submission_progress",
    "cmd_healthcheck",
    "parse_forge_journal",
]
