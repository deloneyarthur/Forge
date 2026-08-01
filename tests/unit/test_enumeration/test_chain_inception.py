"""Chain-inception floors: don't emit windows a name's option chain cannot cover.

Crucible refuses those configs permanently (pre-IPO chains cannot be backfilled), so each one
burns a submission slot and a runner cycle for a verdict that can only be a refusal.

The behaviours pinned here are the ones that were NOT obvious and that a proxy implementation
would have got wrong: refresh-not-pin (floors move earlier, windows slide), fail-open on a
missing export, and the safety margin that drops a name shortly BEFORE it starts failing.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from forge.enumeration.chain_inception import (
    load_chain_inception_floors,
    underlyings_below_inception,
)

# The five names Crucible identified as biting today's windows.
_LIVE_CLASS = {
    "COIN": "2021-04-20",
    "LCID": "2021-07-26",
    "RIVN": "2021-11-16",
    "CEG": "2022-02-09",
    "ARM": "2023-09-18",
}


def _write_export(root: Path, floors: dict[str, str], stamp: str = "2026-08-01T075337Z") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"chain_inception_floors_{stamp}.json"
    path.write_text(json.dumps({"schema_version": "1.0", "floors": floors}))
    return path


def test_missing_export_is_fail_open(tmp_path: Path) -> None:
    """No floors file must never block generation — emission stays byte-identical."""
    assert load_chain_inception_floors(tmp_path) == {}
    assert underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path) == frozenset()


def test_malformed_export_is_fail_open(tmp_path: Path) -> None:
    (tmp_path / "chain_inception_floors_bad.json").write_text("{not json")
    assert load_chain_inception_floors(tmp_path) == {}


def test_one_bad_row_does_not_void_the_map(tmp_path: Path) -> None:
    """A single unparseable date must not discard every other name's floor."""
    _write_export(tmp_path, {"RIVN": "2021-11-16", "JUNK": "not-a-date"})
    floors = load_chain_inception_floors(tmp_path)
    assert floors == {"RIVN": date(2021, 11, 16)}


def test_the_live_class_is_excluded(tmp_path: Path) -> None:
    _write_export(tmp_path, _LIVE_CLASS)
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert excluded == frozenset(_LIVE_CLASS)


def test_the_margin_drops_a_name_BEFORE_it_starts_failing(tmp_path: Path) -> None:
    """LCID is the live case for the margin. Its floor (2021-07-26) sits SIX DAYS inside the
    implied 5y boundary on 2026-08-01, so it has never failed — and would begin failing within
    the week as the window slides. Without the margin we would exclude it only after it had
    already burned runner cycles."""
    _write_export(tmp_path, {"LCID": "2021-07-26"})
    assert "LCID" in underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)


def test_an_old_name_is_not_excluded(tmp_path: Path) -> None:
    """The filter must not sweep up names with real history — that would starve supply to buy
    nothing, since they never fail."""
    _write_export(tmp_path, {"AAPL": "2018-01-02", "SPY": "2018-01-02"})
    assert underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path) == frozenset()


def test_the_window_SLIDES_so_a_name_stops_being_excluded(tmp_path: Path) -> None:
    """Refresh-not-pin, half one. Crucible's own example: PLTR stopped mattering in 2025 and
    ARM stops in 2028. A frozen exclusion list would starve a name that became legal again."""
    _write_export(tmp_path, {"ARM": "2023-09-18"})
    assert "ARM" in underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert "ARM" not in underlyings_below_inception(date(2030, 1, 1), exports_dir=tmp_path)


def test_a_backfilled_floor_moves_EARLIER_and_frees_the_name(tmp_path: Path) -> None:
    """Refresh-not-pin, half two. Floors move earlier when history is backfilled and never
    later — the nine 2026-06-16 ingest-start names are the case. Re-reading the export is how
    we find out; a pinned list would exclude them forever."""
    _write_export(tmp_path, {"WBD": "2026-06-16"}, stamp="2026-08-01T000000Z")
    assert "WBD" in underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    # Crucible backfills; the newest export carries the earlier floor.
    _write_export(tmp_path, {"WBD": "2018-01-02"}, stamp="2026-08-02T000000Z")
    assert "WBD" not in underlyings_below_inception(date(2026, 8, 2), exports_dir=tmp_path)


def test_newest_export_wins(tmp_path: Path) -> None:
    _write_export(tmp_path, {"X": "2025-01-01"}, stamp="2026-07-01T000000Z")
    _write_export(tmp_path, {"Y": "2025-01-01"}, stamp="2026-08-01T000000Z")
    assert set(load_chain_inception_floors(tmp_path)) == {"Y"}
