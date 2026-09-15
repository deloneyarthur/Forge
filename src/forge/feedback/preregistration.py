"""Pre-registration registry + post-cut confirmation (Tier-1a honesty discipline).

WHY this exists. Forge's §8.4 auto-tightening triggers — and, more often, the
operator's manual prunes/retargets — observe a pattern in a cohort and then act on
the *same* cohort that revealed it. "0 promotions in 200+ submissions with param Z
above T -> tighten Z" confirmed on the very batch that motivated it is guaranteed to
look good: it is post-selection bias, the multiple-testing trap one rung down from
the alpha budget (D207; module retired 2026-08-06 with its question answered — the
record is `_archive/ALPHA_BUDGET_SCOPE.md`).

Pre-registration is the fix the GRAMMAR_REVIEW (§5) and LEARNED_SYSTEMS_REVIEW name
but nothing implemented: record the claim *with a cohort cut* before the confirming
data exists, then confirm it only on rows that postdate the cut. The registry is a
git-tracked, append-style JSONL so the prediction is committed before its test —
tamper-evidence comes free from version control.

This module is deliberately decision-agnostic: it does not prune anything. It stores
claims and supplies :func:`confirm_promotion_claim`, whose one job is to refuse to
look at pre-cut data. Predicate-matching (which configs a claim is *about*) is the
caller's — claims are too varied to generalise here — but the statistical guard that
prevents cheating is tested code.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    import duckdb

# Confirmation outcomes. "insufficient" = not enough honest (post-cut) evidence yet.
Outcome = Literal["confirmed", "refuted", "insufficient"]

_DEFAULT_MIN_SAMPLES: Final[int] = 30


@dataclass(frozen=True, slots=True)
class PreregEntry:
    """One pre-registered claim. Immutable once written; `resolve` rewrites a copy."""

    prereg_id: str
    created_at: str  # ISO-8601 UTC, stamped via forge.core.clock at registration
    claim: str  # human description of the predicted pattern
    metric: str  # what is measured, e.g. "promotion_rate"
    predicted: str  # the predicted bound, e.g. "<= 0.005"
    cohort_cut: str  # ISO-8601 UTC; only verdicts strictly AFTER this confirm/refute
    action_if_confirmed: str
    status: str  # "registered" | "confirmed" | "refuted" | "insufficient"
    resolved_at: str | None
    evidence: str | None


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    """Outcome of testing a claim against post-cut data only."""

    outcome: Outcome
    n_post_cut_matched: int
    promotion_rate: float | None  # None when no matched post-cut rows exist


def _to_naive_utc(iso: str) -> datetime | None:
    """Parse an ISO timestamp to a naive datetime (Forge stores UTC; D061).

    Returns None on unparseable input so the row is conservatively excluded — a
    malformed timestamp must never be counted as honest post-cut evidence.
    """
    try:
        return datetime.fromisoformat(iso).replace(tzinfo=None)
    except ValueError:
        return None


def confirm_promotion_claim(
    rows: Iterable[tuple[str, bool, bool]],
    *,
    cohort_cut: str,
    predicted_max_rate: float,
    min_samples: int = _DEFAULT_MIN_SAMPLES,
) -> ConfirmationResult:
    """Confirm "matched configs promote at a rate <= ``predicted_max_rate``" — but
    ONLY on rows that postdate ``cohort_cut``.

    ``rows`` are ``(decided_at_iso, matched, promoted)`` triples. The function keeps
    only rows that are both ``matched`` and strictly after the cut, then compares the
    promotion rate among them to the bound. Pre-cut rows — the ones that motivated the
    claim — are structurally discarded; that exclusion is the whole point.
    """
    cut = _to_naive_utc(cohort_cut)
    n = 0
    promoted = 0
    for decided_at, matched, was_promoted in rows:
        if not matched:
            continue
        ts = _to_naive_utc(decided_at)
        if ts is None or cut is None or ts <= cut:
            continue
        n += 1
        if was_promoted:
            promoted += 1

    if n < min_samples:
        return ConfirmationResult(
            outcome="insufficient",
            n_post_cut_matched=n,
            promotion_rate=(promoted / n) if n else None,
        )
    rate = promoted / n
    outcome: Outcome = "confirmed" if rate <= predicted_max_rate else "refuted"
    return ConfirmationResult(outcome=outcome, n_post_cut_matched=n, promotion_rate=rate)


def load_preregistrations(path: Path) -> list[PreregEntry]:
    """Read the registry; missing file -> empty. Bad lines are skipped, not fatal."""
    if not path.is_file():
        return []
    entries: list[PreregEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(_entry_from_dict(parsed))
    return entries


def append_preregistration(path: Path, entry: PreregEntry) -> None:
    """Append one entry as a JSON line, creating the file/parents if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry), sort_keys=True) + "\n")


def resolve_preregistration(
    path: Path,
    prereg_id: str,
    *,
    outcome: Outcome,
    evidence: str,
    resolved_at: str,
) -> PreregEntry:
    """Mark a registered claim confirmed/refuted/insufficient and rewrite the file.

    Rewriting (vs appending a resolution event) keeps the file a flat list; git
    history preserves the original prediction, so the audit trail survives.
    """
    entries = load_preregistrations(path)
    by_id = {e.prereg_id: i for i, e in enumerate(entries)}
    if prereg_id not in by_id:
        raise KeyError(f"no pre-registration with id {prereg_id!r}")
    idx = by_id[prereg_id]
    updated = replace(entries[idx], status=outcome, evidence=evidence, resolved_at=resolved_at)
    entries[idx] = updated
    body = "".join(json.dumps(asdict(e), sort_keys=True) + "\n" for e in entries)
    path.write_text(body, encoding="utf-8")
    return updated


def _entry_from_dict(d: dict[str, object]) -> PreregEntry:
    """Build an entry from a parsed JSON object, tolerating missing optional keys."""
    return PreregEntry(
        prereg_id=str(d.get("prereg_id", "")),
        created_at=str(d.get("created_at", "")),
        claim=str(d.get("claim", "")),
        metric=str(d.get("metric", "")),
        predicted=str(d.get("predicted", "")),
        cohort_cut=str(d.get("cohort_cut", "")),
        action_if_confirmed=str(d.get("action_if_confirmed", "")),
        status=str(d.get("status", "registered")),
        resolved_at=_opt_str(d.get("resolved_at")),
        evidence=_opt_str(d.get("evidence")),
    )


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


# ---------------------------------------------------------------------------
# Watch clocks — a registered read must not come due silently (D389/D392)
# ---------------------------------------------------------------------------
# Carried from the retired `scripts/freeze_read_watcher.py` (Batch 5 G0) into the weekly
# run's boot check. The judge never computes the metric: it counts qualifying rows in the
# REGISTERED basis and compares fingerprints. Peeking at the answer to decide whether to
# page would be the read itself.

WatchStatus = Literal["ok", "due", "unwatchable"]
CountRows = Callable[[str, str], int]
"""``(basis_fp, since_iso) -> qualifying rows`` — supplied by the caller, so this stays pure."""


@dataclass(frozen=True, slots=True)
class WatchReport:
    status: WatchStatus
    lines: tuple[str, ...]


def open_registrations_raw(path: Path) -> list[dict[str, Any]]:
    """Registered entries as raw JSON rows (the ``watch`` clock is an additive field the
    typed :class:`PreregEntry` does not carry). Missing file -> empty; bad lines skipped."""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("status") == "registered":
            out.append(row)
    return out


def assess_watch_clocks(entries: Sequence[Mapping[str, Any]], count_rows: CountRows) -> WatchReport:
    """DUE outranks UNWATCHABLE outranks ok; both non-ok states must fail the boot check.

    UNWATCHABLE is the D389 defect itself: a registration with no ``watch: {n, basis_fp}``
    clock is a claim nothing can check — re-register it with a clock or withdraw it."""
    if not entries:
        return WatchReport("ok", ("no open preregistrations",))
    lines: list[str] = []
    any_due = any_unwatchable = False
    for row in entries:
        pid = str(row.get("prereg_id", "?"))
        watch = row.get("watch")
        if not isinstance(watch, Mapping) or "n" not in watch or "basis_fp" not in watch:
            any_unwatchable = True
            lines.append(
                f"UNWATCHABLE {pid}: registered with no machine-readable clock "
                "(needs watch: {n, basis_fp}); re-register it with a clock or withdraw it (D389)"
            )
            continue
        required = int(watch["n"])
        basis_fp = str(watch["basis_fp"])
        since = str(row.get("cohort_cut", ""))
        have = count_rows(basis_fp, since)
        if have >= required:
            any_due = True
            lines.append(
                f"DUE {pid}: {have:,} rows in basis {basis_fp} since {since[:19]} "
                f"(required {required:,}); take the read, it must not be extended"
            )
        else:
            gap = required - have
            lines.append(f"waiting {pid}: {have:,}/{required:,} in basis {basis_fp}, {gap:,} to go")
    status: WatchStatus = "due" if any_due else ("unwatchable" if any_unwatchable else "ok")
    return WatchReport(status, tuple(lines))


def count_basis_rows(conn: duckdb.DuckDBPyConnection, basis_fp: str, since: str) -> int:
    """The honest-arm / stage-one population the freeze reads use, scoped IN SQL to the
    registered basis so a foreign-basis backlog can never inflate a clock (D387/D391)."""
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM submissions s
        JOIN verdicts v ON v.config_hash = s.config_hash
        LEFT JOIN batch_summaries b ON b.forge_batch_id = s.forge_batch_id
        WHERE s.selection_mode = 'prefilter_sample'
          AND v.measurement_basis IS DISTINCT FROM 'fullhist_refit'
          AND TRY_CAST(json_extract_string(
                v.gate_results,'$.cpcv_sharpe_p25.value') AS DOUBLE) IS NOT NULL
          AND split_part(b.enumeration_inputs_hash,'|',2) = ?
          AND s.submitted_at > TRY_CAST(? AS TIMESTAMP)
        """,
        [basis_fp, since],
    ).fetchone()
    return int(row[0]) if row else 0


__all__ = [
    "ConfirmationResult",
    "Outcome",
    "PreregEntry",
    "WatchReport",
    "WatchStatus",
    "append_preregistration",
    "assess_watch_clocks",
    "confirm_promotion_claim",
    "count_basis_rows",
    "load_preregistrations",
    "open_registrations_raw",
    "resolve_preregistration",
]
