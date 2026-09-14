"""Run records and the `forge campaign status` read.

WHY a hand-written codec instead of ``json.dumps(default=str)``: the record is
the replay key for a weekly decision (plan §12.3 step 5) and Crucible's morning
digest reads it (their 09-13 §6), so every value must round-trip losslessly and
predictably. Datetimes are ISO 8601, sets are sorted lists, cell keys are
5-element lists; unknown keys on read are ignored so a newer writer never
breaks an older reader.
"""

from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from forge.campaign.types import (
    BootCheck,
    CampaignSpec,
    CellKey,
    RunRecord,
    TriggerOutcome,
)

if TYPE_CHECKING:
    import duckdb

_RECORD_GLOB = "*.json"


def _plain(value: object) -> object:
    """Recursively convert a record value into JSON-native shapes."""
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, frozenset | set):
        return sorted((_plain(v) for v in value), key=repr)
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def record_to_json(record: RunRecord) -> str:
    return json.dumps(_plain(record), indent=2, sort_keys=True)


def _cell(raw: object) -> CellKey:
    parts = [str(p) for p in cast("Sequence[object]", raw)]
    if len(parts) != 5:
        msg = f"cell key must have 5 parts, got {parts!r}"
        raise ValueError(msg)
    return (parts[0], parts[1], parts[2], parts[3], parts[4])


def _cells(raw: object) -> frozenset[CellKey]:
    return frozenset(_cell(c) for c in cast("Iterable[object]", raw or ()))


def _dt(raw: object) -> datetime | None:
    return datetime.fromisoformat(raw) if isinstance(raw, str) else None


def _spec(raw: Mapping[str, Any]) -> CampaignSpec:
    return CampaignSpec(
        trigger=raw["trigger"],
        cells=_cells(raw.get("cells")),
        budget=int(raw["budget"]),
        reason=str(raw.get("reason", "")),
        replacement_for=_cells(raw.get("replacement_for")),
        indicator_ids=frozenset(str(i) for i in raw.get("indicator_ids", ())),
    )


def _outcome(raw: Mapping[str, Any]) -> TriggerOutcome:
    campaign = raw.get("campaign")
    return TriggerOutcome(
        trigger=raw["trigger"],
        fired=bool(raw["fired"]),
        reason=str(raw.get("reason", "")),
        campaign=_spec(campaign) if isinstance(campaign, Mapping) else None,
    )


def record_from_json(text: str) -> RunRecord:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        msg = "run record must be a JSON object"
        raise ValueError(msg)
    known = {f.name for f in dataclasses.fields(RunRecord)}
    data = {k: v for k, v in raw.items() if k in known}
    started = _dt(data.get("started_at"))
    if started is None:
        msg = "run record missing started_at"
        raise ValueError(msg)
    return RunRecord(
        schema_version=str(data["schema_version"]),
        run_id=str(data["run_id"]),
        started_at=started,
        finished_at=_dt(data.get("finished_at")),
        dry_run=bool(data["dry_run"]),
        status=data["status"],
        grammar_version=data.get("grammar_version"),
        registry_hash=data.get("registry_hash"),
        enumeration_inputs_hash=data.get("enumeration_inputs_hash"),
        seed=data.get("seed"),
        iso_week=str(data["iso_week"]),
        watermarks=dict(data.get("watermarks", {})),
        boot=tuple(BootCheck(**b) for b in data.get("boot", ())),
        designated_id=data.get("designated_id"),
        triggers=tuple(_outcome(t) for t in data.get("triggers", ())),
        campaigns=tuple(_spec(c) for c in data.get("campaigns", ())),
        enumerated=int(data.get("enumerated", 0)),
        kept_in_cells=int(data.get("kept_in_cells", 0)),
        survived_battery=int(data.get("survived_battery", 0)),
        gated_out=dict(data.get("gated_out", {})),
        submitted=int(data.get("submitted", 0)),
        submitted_hashes=tuple(str(h) for h in data.get("submitted_hashes", ())),
        batch_id=data.get("batch_id"),
        baselines=dict(data.get("baselines", {})),
        notes=tuple(str(n) for n in data.get("notes", ())),
    )


def baseline_cells(record: RunRecord) -> frozenset[CellKey] | None:
    """The previous run's designated-book cells, or None when it recorded none."""
    raw = record.baselines.get("book_cells")
    return None if raw is None else _cells(raw)


def baseline_ids(record: RunRecord, key: str) -> frozenset[str] | None:
    raw = record.baselines.get(key)
    return None if raw is None else frozenset(str(i) for i in cast("Iterable[object]", raw))


def baseline_families(record: RunRecord) -> dict[str, str] | None:
    raw = record.baselines.get("registry_families")
    if not isinstance(raw, Mapping):
        return None
    return {str(k): str(v) for k, v in raw.items()}


def baseline_str(record: RunRecord, key: str) -> str | None:
    raw = record.baselines.get(key)
    return str(raw) if raw is not None else None


def write_record(records_dir: Path, record: RunRecord) -> Path:
    """Atomic write (tmp + rename) so a half-written record is never the newest."""
    records_dir.mkdir(parents=True, exist_ok=True)
    target = records_dir / f"{record.run_id}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(record_to_json(record), encoding="utf-8")
    os.replace(tmp, target)
    return target


def load_records(records_dir: Path) -> list[RunRecord]:
    """Every record, oldest first (run ids sort chronologically by construction)."""
    if not records_dir.exists():
        return []
    out = [
        record_from_json(p.read_text(encoding="utf-8"))
        for p in sorted(records_dir.glob(_RECORD_GLOB))
    ]
    out.sort(key=lambda r: r.started_at)
    return out


def load_latest_record(records_dir: Path) -> RunRecord | None:
    records = load_records(records_dir)
    return records[-1] if records else None


def _verdict_counts(conn: duckdb.DuckDBPyConnection, hashes: Sequence[str]) -> tuple[int, int]:
    """(decided, converting) for the record's submissions, from Forge's own ledger."""
    if not hashes:
        return (0, 0)
    from forge.feedback.yield_audit import CONVERTING_DECISIONS  # noqa: PLC0415

    placeholders = ", ".join("?" for _ in hashes)
    rows = conn.execute(
        f"SELECT decision, COUNT(*) FROM verdicts WHERE config_hash IN ({placeholders}) "  # noqa: S608
        "GROUP BY decision",
        list(hashes),
    ).fetchall()
    decided = sum(int(n) for _, n in rows)
    converting = sum(int(n) for d, n in rows if str(d) in CONVERTING_DECISIONS)
    return (decided, converting)


def format_status(
    records: Sequence[RunRecord],
    conn: duckdb.DuckDBPyConnection | None = None,
    *,
    last: int = 8,
) -> str:
    """One line per run, newest first; with a DB, the verdicts each run's submissions earned."""
    if not records:
        return "no campaign runs recorded yet"
    lines: list[str] = []
    for rec in list(records)[-last:][::-1]:
        fired = ",".join(t.trigger for t in rec.triggers if t.fired) or "-"
        camps = "; ".join(f"{c.trigger}:{len(c.cells)}c/{c.budget}" for c in rec.campaigns) or "-"
        line = (
            f"{rec.run_id}  {rec.status:<11} {'dry' if rec.dry_run else 'live':<4} "
            f"fired={fired}  campaigns={camps}  enumerated={rec.enumerated} "
            f"kept={rec.kept_in_cells} survived={rec.survived_battery} submitted={rec.submitted}"
        )
        if conn is not None and rec.submitted_hashes:
            decided, converting = _verdict_counts(conn, rec.submitted_hashes)
            line += f"  verdicts={decided} converting={converting}"
        lines.append(line)
    return "\n".join(lines)


__all__ = [
    "baseline_cells",
    "baseline_families",
    "baseline_ids",
    "baseline_str",
    "format_status",
    "load_latest_record",
    "load_records",
    "record_from_json",
    "record_to_json",
    "write_record",
]
