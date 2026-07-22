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
import shutil
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
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
    # D261: the registry loader dropped an indicator whose `family` Literal is unknown to
    # Forge's installed contracts (a Crucible family added ahead of Forge's pin adoption).
    # Graceful-degrade instead of failing every poll — but the drop must be visible.
    registry_unknown_family_at: datetime | None = None


# `<iso-ts> <host> forge[<pid>]: <message>` (journalctl -o short-iso).
_JOURNAL_LINE = re.compile(r"^(?P<ts>\S+)\s+\S+\s+forge\[\d+\]:\s+(?P<msg>.*)$")
_ITER_PREFIX = "--- loop iteration"
_BLOCK_PREFIX = "blocked:"
_SUBMIT_RE = re.compile(r"\bsubmitted=(?P<n>\d+)\b")
_HYPWEIGHTS_DEGRADE_PREFIX = "hypothesis_weights: degraded"
_REGISTRY_UNKNOWN_FAMILY_PREFIX = "registry_unknown_family_skipped"


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
    registry_unknown_family_at: datetime | None = None

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
        elif msg.startswith(_REGISTRY_UNKNOWN_FAMILY_PREFIX):
            registry_unknown_family_at = ts
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
        registry_unknown_family_at=registry_unknown_family_at,
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


def check_deployed_code_staleness(
    service_started_at: datetime | None,
    last_src_commit_at: datetime | None,
) -> HealthResult:
    """Is the RUNNING daemon executing code older than HEAD? (D330)

    The 2026-07-22 failure class, hit by both repos in one afternoon: **shipped is
    not deployed.** Crucible committed the DSR deflation-basis exemption at 15:49
    while both runner shards had been up since 21:04 the previous day. The fix was
    correct, unit-tested, invariant-tested and in their Decision Log — and produced
    zero effect for 84 decisions, because a long-running daemon holds its modules in
    memory. It surfaced as an urgent cross-repo bug report against code that was
    already right, which is the most expensive kind of correct measurement: it sends
    the other side hunting a bug that does not exist.

    Neither repo's new enforcement tests can catch this. Ours pins the ranker's
    feature signature, theirs pins the single blocking-failure derivation; both are
    true of the *repository* and say nothing about the *process*. Hence the rule
    this check exists to enforce: **a claim about deployed behaviour needs a check on
    the running process, the same way an architectural claim needs a test and a
    numeric claim needs a reproduction.**

    Forge is more exposed than Crucible here, not less: this working tree IS
    production (D104), so a commit is live-on-reboot but inert until restart —
    the window where the tree and the process disagree is opened by every commit.

    Scope, and its deliberate imprecision: the comparison is against the newest
    commit touching `src/`, not a computed import graph. `forge.cli.main` (the
    daemon entry) imports 57 forge modules including this one, so nearly all of
    `src/` really is in the running process. It will still over-warn on a commit
    the daemon's behaviour does not depend on — accepted, because the message is
    actionable ("restart to deploy it"), the deploy ritual ends in a restart
    anyway, and a check that occasionally says "restart" is a cheaper failure than
    one that stays silent while 84 decisions run stale code.
    """
    if service_started_at is None or last_src_commit_at is None:
        return HealthResult(
            "deploy_staleness",
            Level.WARN,
            "cannot compare service start to last src commit (missing timestamp)",
        )
    if service_started_at >= last_src_commit_at:
        return HealthResult(
            "deploy_staleness", Level.OK, "running daemon started after the last src commit"
        )
    hours = (last_src_commit_at - service_started_at).total_seconds() / 3600.0
    return HealthResult(
        "deploy_staleness",
        Level.WARN,
        f"service is running STALE code: started {hours:.0f}h before the last "
        f"src/ commit — restart to deploy it",
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


def check_earnings_coverage_export(
    newest_mtime: datetime | None,
    now: datetime,
    *,
    warn_days: float = 45.0,
) -> HealthResult:
    """Soft presence + staleness check for Crucible's earnings-coverage manifest (v32/D268).

    Forge intersects its earnings-gated underlying pool with `earnings_covered_symbols.json`
    — the durable replacement for the `_NO_EARNINGS_UNDERLYINGS` stopgap. The sampler reads it
    with `max_age_days=None` so a stale set never HALTS generation (stale coverage beats the
    frozen list; coverage changes slowly), which moves the staleness teeth HERE. Absence is OK:
    the wiring ships dormant until Crucible starts the publisher, so a missing file must not
    pollute OVERALL (the `check_component_contributions_export` precedent). Present & fresh → OK
    with age; present & older than `warn_days` → WARN (the publisher may be dead — the covered
    set is quietly ossifying and a new no-earnings universe add re-opens the SOXL degenerate-leg
    blind spot). No typed read — glob+mtime only, so it does not pre-empt the contracts loader."""
    label = "earnings_coverage"
    if newest_mtime is None:
        return HealthResult(
            label, Level.OK, "no export yet (dormant until Crucible starts the publisher)"
        )
    days = _age_hours(newest_mtime, now) / 24.0
    if days >= warn_days:
        return HealthResult(
            label,
            Level.WARN,
            f"newest earnings-coverage export is {days:.0f}d old (>{warn_days:.0f}d — publisher "
            f"may be dead; coverage set ossifying, D268)",
        )
    return HealthResult(label, Level.OK, f"present ({days:.1f}d old)")


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


def check_inbox_rejections(
    recent_reject_count: int,
    *,
    warn: int,
    critical: int,
) -> HealthResult:
    """Catch the 'submitting-but-rejected' wedge the submission check can't distinguish (D245).

    When Crucible's inbox watcher rejects Forge's submissions — e.g. an ASYMMETRIC
    `crucible_contracts` upgrade where Forge emits a field Crucible's inbox validator
    (holding a stale in-memory model) forbids — every config lands in
    `~/optbt_data/inbox/errors/` instead of running. The daemon then wedges on the §7.3
    per-batch limiter at `0/N gated`, which reads IDENTICALLY to ordinary backpressure,
    so `check_submission_progress` alone reports a generic "no submission in Nh" and the
    real cause (100% rejection) stays invisible — the D245 incident sat silent ~13h.

    `recent_reject_count` = rejected-config files in `inbox/errors/` with a recent mtime.
    Steady state is ~0 (Forge's output always validates against the shared contract), so a
    batch-sized burst is a skew. CRITICAL points at the fix: a contracts bump must restart
    BOTH directions' processes (Forge's submitter AND Crucible's inbox watcher), D245.
    """
    label = "inbox_rejections"
    if recent_reject_count >= critical:
        return HealthResult(
            label,
            Level.CRITICAL,
            f"{recent_reject_count} recent inbox rejections — likely a contracts skew "
            f"(read inbox/errors/*.reason.txt; a contracts bump must restart Crucible's "
            f"inbox watcher, not just Forge — D245)",
        )
    if recent_reject_count >= warn:
        return HealthResult(
            label,
            Level.WARN,
            f"{recent_reject_count} recent inbox rejections — check inbox/errors/*.reason.txt",
        )
    return HealthResult(label, Level.OK, "no recent inbox rejections")


# The ranker-eval + investigate-live probes snapshot forge.db here (the live DB holds an RW
# lock). Referencing the path to check headroom — not creating an insecure temp file (S108).
_EVAL_SNAPSHOT_DIR = "/tmp"  # noqa: S108


def check_tmp_headroom(
    tmp_free_bytes: int | None,
    db_size_bytes: int | None,
    *,
    warn_ratio: float,
    critical_ratio: float,
) -> HealthResult:
    """Headroom in the temp dir for the forge.db snapshot the daily ranker-eval copies (D259).

    `forge-ranker-eval` (and the investigate-live probes) read the live DB via a `cp` of
    forge.db into the temp snapshot dir, because the live DB holds an intermittent RW lock.
    If that dir lacks room for the ~6 GB copy the `cp` fails ('Disk quota exceeded'), the eval
    fails, and the F3 / wf_p25 models silently stale — only surfacing when the model-freshness
    check CRITs ~2 days later (the 2026-07-09 incident: stale 5.5 GB probe snapshots left in
    the temp dir starved the eval's `cp`). This WARNs on the CAUSE (thin headroom) before the
    eval breaks. Ratio to the DB size (not an absolute) so it stays valid as forge.db grows;
    the incident failed at ~3.3x (a quota effect below the raw free space), hence generous
    defaults.
    """
    label = "tmp_headroom"
    if tmp_free_bytes is None or db_size_bytes is None or db_size_bytes <= 0:
        return HealthResult(label, Level.OK, f"n/a ({_EVAL_SNAPSHOT_DIR} or forge.db unmeasured)")
    ratio = tmp_free_bytes / db_size_bytes
    free_g = tmp_free_bytes / 1e9
    db_g = db_size_bytes / 1e9
    if ratio < critical_ratio:
        return HealthResult(
            label,
            Level.CRITICAL,
            f"{_EVAL_SNAPSHOT_DIR} free {free_g:.1f}G is only {ratio:.1f}x forge.db "
            f"({db_g:.1f}G) — the ranker-eval snapshot cp will fail; clear stale snapshots (D259)",
        )
    if ratio < warn_ratio:
        return HealthResult(
            label,
            Level.WARN,
            f"{_EVAL_SNAPSHOT_DIR} free {free_g:.1f}G ({ratio:.1f}x forge.db {db_g:.1f}G) getting "
            f"tight — clear stale snapshots before the ranker-eval cp breaks (D259)",
        )
    return HealthResult(
        label, Level.OK, f"{_EVAL_SNAPSHOT_DIR} free {free_g:.1f}G ({ratio:.1f}x forge.db)"
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


def check_campaign_carriage(
    latest: dict[str, object] | None,
    now: datetime,
    *,
    stale_warn_hours: float = 30.0,
) -> HealthResult:
    """D302 (Theme 5c): surface the daily campaign region-carriage audit.

    The daily eval appends one JSONL row (``campaign_audit.jsonl``); a starved
    campaign there means the selection layer is eating a farming region (the
    D287 class) — WARN with the names so the operator runs `forge campaigns
    audit` for the detail. A stale row WARNs too (the audit silently stopping
    is itself the failure this check exists to catch). No rows yet is OK with
    a note — the wiring is new and the first 05:00 fire may not have happened.
    """
    label = "campaign carriage"
    if latest is None:
        return HealthResult(
            label, Level.OK, "campaign carriage: no campaign-audit rows yet (first 05:00 fire)"
        )
    ts_raw = latest.get("ts")
    try:
        ts = datetime.fromisoformat(str(ts_raw))
    except (TypeError, ValueError):
        return HealthResult(label, Level.WARN, "campaign carriage: latest row has no parseable ts")
    age_hours = (now - ts).total_seconds() / 3600.0
    if age_hours > stale_warn_hours:
        return HealthResult(
            label,
            Level.WARN,
            f"campaign carriage stale: last audit row {age_hours:.0f}h ago",
        )
    starved = latest.get("starved")
    if isinstance(starved, list) and starved:
        names = ", ".join(str(n) for n in starved)
        return HealthResult(
            label,
            Level.WARN,
            f"campaigns STARVED at selection (D287 class): {names} — "
            "run `forge campaigns audit` on a snapshot for detail",
        )
    results = latest.get("results")
    n_audited = len(results) if isinstance(results, list) else 0
    return HealthResult(
        label, Level.OK, f"campaign carriage ok ({n_audited} campaigns audited, none starved)"
    )


def check_activation_probe(
    latest: dict[str, object] | None,
    now: datetime,
    *,
    stale_warn_hours: float = 30.0,
) -> HealthResult:
    """D316 (Theme 2c): surface the daily writer-activation probe.

    The ref_trailing_return class (D290: registered + enumerable, but
    Crucible's writer serves 0 activations → every carrier dies at our
    prefilter) was caught by a MANUAL probe during a deploy; the daily eval
    now runs `forge check-activations` and appends one JSONL row. An INERT
    id there means live enumeration is being drawn-then-killed — WARN with
    the ids. Stale/unparseable rows WARN (a silently dead probe is the
    failure this check exists to catch); no rows yet is OK-with-note.
    """
    label = "activation probe"
    if latest is None:
        return HealthResult(
            label, Level.OK, "activation probe: no activation-probe rows yet (first 05:00 fire)"
        )
    try:
        ts = datetime.fromisoformat(str(latest.get("ts")))
    except (TypeError, ValueError):
        return HealthResult(label, Level.WARN, "activation probe: latest row has no parseable ts")
    age_hours = (now - ts).total_seconds() / 3600.0
    if age_hours > stale_warn_hours:
        return HealthResult(
            label, Level.WARN, f"activation probe stale: last row {age_hours:.0f}h ago"
        )
    inert = latest.get("inert")
    if isinstance(inert, list) and inert:
        ids = ", ".join(str(i) for i in inert)
        return HealthResult(
            label,
            Level.WARN,
            f"INERT directionals (writer serves 0 activations — the D290/D254 "
            f"class): {ids} — carriers are drawn-then-killed at the prefilter",
        )
    probed = latest.get("probed")
    return HealthResult(label, Level.OK, f"activation probe ok ({probed} ids probed, none inert)")


def check_search_multiplicity_census(
    latest: dict[str, object] | None,
    now: datetime,
    *,
    stale_warn_hours: float = 30.0,
    dead_flow_warn: float = 0.05,
) -> HealthResult:
    """D328: the daily grammar-freeze metric. `search_multiplicity_census.jsonl`
    carries freeze metric B — the dead-unprotected share of current submission
    flow (still-emitted cells with ~0 conversion, not protected by a farming
    campaign). Baseline 2.8%; the stream is efficient, so a RISE past the bar
    means a new dead axis started flowing (or a farming campaign that used to
    protect a cell was retired) — WARN so the freeze ledger stays honest.
    `dead_flow_warn` is the operator-tunable bar (freeze-criterion condition B);
    a stale/unparseable file WARNs (a silently dead census is the failure this
    exists to catch); no rows yet is OK-with-note."""
    label = "freeze census"
    if latest is None:
        return HealthResult(label, Level.OK, "freeze census: no census rows yet (first 05:00 fire)")
    try:
        ts = datetime.fromisoformat(str(latest.get("ts")))
    except (TypeError, ValueError):
        return HealthResult(label, Level.WARN, "freeze census: latest row has no parseable ts")
    age_hours = (now - ts).total_seconds() / 3600.0
    if age_hours > stale_warn_hours:
        return HealthResult(
            label, Level.WARN, f"freeze census stale: last row {age_hours:.0f}h ago"
        )
    metric = latest.get("metric_b_flow")
    if not isinstance(metric, (int, float)):
        return HealthResult(label, Level.WARN, "freeze census: latest row has no metric_b_flow")
    n_dead = latest.get("n_dead_cells")
    if metric > dead_flow_warn:
        return HealthResult(
            label,
            Level.WARN,
            f"freeze metric B rose to {100 * metric:.1f}% of flow (> {100 * dead_flow_warn:.0f}% "
            f"bar; {n_dead} dead cells) — a dead axis is flowing or a protection retired; "
            f"re-run the census ledger",
        )
    return HealthResult(
        label, Level.OK, f"freeze metric B {100 * metric:.1f}% of flow ({n_dead} dead cells)"
    )


def check_registry_unknown_family(journal: JournalState) -> HealthResult:
    """D261: the registry loader dropped an indicator whose `family` Literal is unknown to
    Forge's installed contracts — a Crucible family added to a live registry snapshot ahead
    of Forge's pin adoption (the asymmetric-upgrade trap on the registry-READ face). The
    loader degrades gracefully (drop the indicator, keep producing) instead of failing every
    poll, but that WARN is load-bearing: it means a `crucible_contracts` bump is un-adopted
    and the enumerable indicator set is silently reduced until it is. WARN (the daemon still
    produces) and point at the fix — read the release + bump `FORGE_EXPECTED_CONTRACT_VERSION`
    (D261). Appears in the journal window while the condition persists (logged per poll)."""
    when = journal.registry_unknown_family_at
    if when is None:
        return HealthResult("registry_family", Level.OK, "no unknown-family indicators skipped")
    return HealthResult(
        "registry_family",
        Level.WARN,
        f"registry indicator(s) SKIPPED for an unknown `family` ({when:%Y-%m-%d %H:%M}) — a "
        f"contracts family added ahead of Forge's pin; adopt the new crucible_contracts (D261)",
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


def _count_recent_files(directory: Path, pattern: str, now: datetime, window_hours: float) -> int:
    """Count files matching `pattern` in `directory` whose mtime is within `window_hours`.

    Filesystem-only (no DB), matching this module's design. Used for the inbox-rejection
    check: `inbox/errors/*.json` are rejected submissions; a recent-mtime burst is a live
    skew. A wide backlog of old rejections is excluded by the window."""
    if not directory.is_dir():
        return 0
    cutoff = now.timestamp() - window_hours * 3600.0
    return sum(1 for p in directory.glob(pattern) if p.stat().st_mtime >= cutoff)


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


def _read_last_json_line(path: Path) -> dict[str, object] | None:
    """The newest JSONL record in ``path``, or None (missing/empty/corrupt tail)."""
    if not path.is_file():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        rec = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return rec if isinstance(rec, dict) else None


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


def _service_started_at() -> datetime | None:
    """When the RUNNING daemon started. None = unavailable."""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "show", "forge.service", "-p", "ActiveEnterTimestamp"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = proc.stdout.strip().partition("=")[2].strip()
    if not raw:
        return None
    try:  # systemd emits e.g. "Wed 2026-07-22 15:52:49 PDT"
        return datetime.strptime(raw, "%a %Y-%m-%d %H:%M:%S %Z").astimezone(UTC)
    except ValueError:
        return None


def _last_src_commit_at() -> datetime | None:
    """Commit time of the newest commit touching `src/` — the code the daemon imports."""
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", "src"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            cwd=Path(__file__).resolve().parents[3],
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


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
    inbox_reject_window_hours: float = typer.Option(
        6.0, help="Window for counting recent inbox rejections"
    ),
    inbox_reject_warn: int = typer.Option(
        25, help="WARN if this many submissions were rejected at the inbox in the window"
    ),
    inbox_reject_critical: int = typer.Option(
        100, help="CRITICAL (skew) if this many were rejected in the window"
    ),
    tmp_warn_ratio: float = typer.Option(
        5.0, help="WARN if /tmp free is below this multiple of the forge.db size"
    ),
    tmp_critical_ratio: float = typer.Option(
        3.5, help="CRITICAL if /tmp free is below this multiple of the forge.db size"
    ),
) -> None:
    """Report daemon health (alive AND productive); exit 0/1/2 = OK/WARN/CRITICAL."""
    from crucible_contracts import CONTRACT_VERSION

    from forge.core.contracts_check import FORGE_EXPECTED_CONTRACT_VERSION

    now = utc_now()
    results: list[HealthResult] = [
        check_service_active(_service_is_active()),
        check_deployed_code_staleness(_service_started_at(), _last_src_commit_at()),
    ]

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
    # D245: recent inbox rejections — the 'submitting-but-rejected' wedge that reads like
    # ordinary backpressure. Filesystem-only (no DB); errors/*.json are rejected submissions.
    results.append(
        check_inbox_rejections(
            _count_recent_files(
                Path.home() / "optbt_data" / "inbox" / "errors",
                "*.json",
                now,
                inbox_reject_window_hours,
            ),
            warn=inbox_reject_warn,
            critical=inbox_reject_critical,
        )
    )
    # D259: /tmp headroom for the ranker-eval's forge.db snapshot cp. WARNs on the CAUSE
    # (thin /tmp) before the eval's cp fails and silently stales the models.
    try:
        _tmp_free: int | None = shutil.disk_usage(_EVAL_SNAPSHOT_DIR).free
    except OSError:
        _tmp_free = None
    try:
        _db_size: int | None = (data_root / "forge.db").stat().st_size
    except OSError:
        _db_size = None
    results.append(
        check_tmp_headroom(
            _tmp_free, _db_size, warn_ratio=tmp_warn_ratio, critical_ratio=tmp_critical_ratio
        )
    )
    # Crucible's component_contributions export (D216): the Layer-1 decorrelated-
    # supply signal. Soft — absent is expected until the first promotion.
    results.append(
        check_component_contributions_export(
            _newest_mtime(Path.home() / "optbt_data" / "exports", "component_contributions_*.json"),
            now,
        )
    )
    # v32 (D268): Crucible's earnings-coverage manifest — the durable authority the
    # sampler intersects earnings-gated draws with. Soft — absent is expected until the
    # publisher starts; the sampler's max_age_days=None puts the staleness WARN here.
    results.append(
        check_earnings_coverage_export(
            _newest_mtime(Path.home() / "optbt_data" / "exports", "earnings_covered_symbols*.json"),
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
            # D285 (replacing the retired §8.6 clock's spearman_delta, which became
            # self-referential after the gate-tail flip): read the re-wire clock's Δ —
            # the LIVE gate-tail lane's top-K realized WF floor vs the P-alone
            # baseline. A negative delta means the lane orders worse than P alone.
            _read_metric_series(eval_dir / "rewire_streak_wfp25.jsonl", "delta"),
            label="gate-tail drift",
            warn_below=_TAIL_WARN_BELOW,
            critical_below=_TAIL_CRITICAL_BELOW,
            regression_delta=drift_regression_delta,
        )
    )
    # D302 (Theme 5c): the daily campaign region-carriage audit row — a starved
    # farming campaign (the D287 selection-starvation class) or a silently
    # stopped audit both WARN here.
    results.append(
        check_campaign_carriage(_read_last_json_line(eval_dir / "campaign_audit.jsonl"), now)
    )
    # D316 (2c): the daily writer-activation probe — an INERT directional with
    # live carriage (the ref_trailing_return class) or a dead probe both WARN.
    results.append(
        check_activation_probe(_read_last_json_line(eval_dir / "activation_probe.jsonl"), now)
    )
    # D328: the daily grammar-freeze metric (dead-unprotected share of flow) — a
    # rise past the operator bar or a stale census both WARN.
    results.append(
        check_search_multiplicity_census(
            _read_last_json_line(eval_dir / "search_multiplicity_census.jsonl"), now
        )
    )
    if journal is not None:
        results.append(check_hypothesis_weights_fallback(journal))
        # D261: registry-read tolerated an unknown `family` (contracts family added ahead of
        # Forge's pin) → the indicator set is silently reduced until the pin is adopted.
        results.append(check_registry_unknown_family(journal))

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
    "check_earnings_coverage_export",
    "check_file_freshness",
    "check_hypothesis_weights_fallback",
    "check_inbox_rejections",
    "check_learning_drift",
    "check_loop_liveness",
    "check_registry_unknown_family",
    "check_service_active",
    "check_submission_progress",
    "check_tmp_headroom",
    "cmd_healthcheck",
    "parse_forge_journal",
]
