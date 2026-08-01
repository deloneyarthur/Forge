"""Chain-inception floors: don't emit windows a name's option chain cannot cover.

Crucible refuses those configs permanently (pre-IPO chains cannot be backfilled), so each one
burns a submission slot and a runner cycle for a verdict that can only be a refusal.

The behaviours pinned here are the ones that were NOT obvious and that a proxy implementation
would have got wrong: refresh-not-pin (floors move earlier, windows slide), fail-open on a
missing export, the safety margin that drops a name shortly BEFORE it starts failing, and —
the one our own 5-of-5 boundary check could never have caught — that the window LENGTH is a
function of `dte_bucket`, seven years for swing_long against five for everything else.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from forge.enumeration.chain_inception import (
    ChainInceptionExclusions,
    load_chain_inception_floors,
    underlyings_below_inception,
)

# The five names Crucible identified as biting today's 5-year windows.
_LIVE_CLASS = {
    "COIN": "2021-04-20",
    "LCID": "2021-07-26",
    "RIVN": "2021-11-16",
    "CEG": "2022-02-09",
    "ARM": "2023-09-18",
}

# Names Crucible measured as pre-inception for swing_long ONLY — clear of the 5y boundary,
# inside the 7y one. These are six of the fifteen we had filed as permanently dormant.
_SEVEN_YEAR_ONLY = {
    "UVXY": "2020-01-02",
    "RTX": "2020-04-06",
    "SQQQ": "2020-08-21",
    "PLTR": "2020-10-06",
    "DASH": "2020-12-15",
    "ABNB": "2020-12-16",
}


def _write_export(root: Path, floors: dict[str, str], stamp: str = "2026-08-01T075337Z") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"chain_inception_floors_{stamp}.json"
    path.write_text(json.dumps({"schema_version": "1.0", "floors": floors}))
    return path


def test_missing_export_is_fail_open(tmp_path: Path) -> None:
    """No floors file must never block generation — emission stays byte-identical."""
    assert load_chain_inception_floors(tmp_path) == {}
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert excluded.for_bucket("swing_long") == frozenset()
    assert not excluded


def test_malformed_export_is_fail_open(tmp_path: Path) -> None:
    (tmp_path / "chain_inception_floors_bad.json").write_text("{not json")
    assert load_chain_inception_floors(tmp_path) == {}


def test_one_bad_row_does_not_void_the_map(tmp_path: Path) -> None:
    """A single unparseable date must not discard every other name's floor."""
    _write_export(tmp_path, {"RIVN": "2021-11-16", "JUNK": "not-a-date"})
    floors = load_chain_inception_floors(tmp_path)
    assert floors == {"RIVN": date(2021, 11, 16)}


def test_the_live_class_is_excluded_in_every_bucket(tmp_path: Path) -> None:
    _write_export(tmp_path, _LIVE_CLASS)
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    for bucket in ("swing_short", "swing_mid", "swing_long"):
        assert frozenset(_LIVE_CLASS) <= excluded.for_bucket(bucket)


def test_swing_long_is_SEVEN_years_and_the_others_are_five(tmp_path: Path) -> None:
    """The correction that our own verification could not have found.

    Crucible queues each bucket at the history its §8.7 min-trade floor needs: 5y for
    swing_short/swing_mid, 7y for swing_long. All 49 recorded pre-inception failures are
    5y-lane runs, so the 7y trap has never fired — a boundary check against observed
    failures was structurally blind to it. These six names are clear of the 5y line and
    pre-inception under the 7y one TODAY.
    """
    _write_export(tmp_path, _SEVEN_YEAR_ONLY)
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert excluded.for_bucket("swing_long") == frozenset(_SEVEN_YEAR_ONLY)
    assert excluded.for_bucket("swing_mid") == frozenset()
    assert excluded.for_bucket("swing_short") == frozenset()


def test_an_unknown_bucket_falls_back_to_the_five_year_default(tmp_path: Path) -> None:
    """Mirrors Crucible's queue: a bucket with no entry gets the 1,825-day default. Guessing
    the LONGER window here would over-exclude on a bucket we know nothing about."""
    _write_export(tmp_path, _SEVEN_YEAR_ONLY | _LIVE_CLASS)
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert excluded.for_bucket("some_future_bucket") == frozenset(_LIVE_CLASS)


def test_the_margin_drops_a_name_BEFORE_it_starts_failing(tmp_path: Path) -> None:
    """LCID is the live case for the margin. Its floor (2021-07-26) sits SIX DAYS inside the
    5y boundary on 2026-08-01, so it has never failed there — and would begin failing within
    the week as the window slides. Without the margin we would exclude it only after it had
    already burned runner cycles."""
    _write_export(tmp_path, {"LCID": "2021-07-26"})
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert "LCID" in excluded.for_bucket("swing_mid")


def test_an_old_name_is_not_excluded_in_any_bucket(tmp_path: Path) -> None:
    """The filter must not sweep up names with real history — that would starve supply to buy
    nothing, since they never fail. WMT/BKNG stand for the nine Crucible measured as dormant
    in BOTH lanes."""
    _write_export(tmp_path, {"WMT": "2018-01-02", "BKNG": "2018-01-02"})
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert not excluded
    assert excluded.for_bucket("swing_long") == frozenset()


def test_the_window_SLIDES_so_a_name_stops_being_excluded(tmp_path: Path) -> None:
    """Refresh-not-pin, half one. Crucible's own example: PLTR stopped mattering in 2025 and
    ARM stops in 2028. A frozen exclusion list would starve a name that became legal again."""
    _write_export(tmp_path, {"ARM": "2023-09-18"})
    assert "ARM" in underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path).for_bucket(
        "swing_mid"
    )
    assert "ARM" not in underlyings_below_inception(
        date(2032, 1, 1), exports_dir=tmp_path
    ).for_bucket("swing_mid")


def test_a_backfilled_floor_moves_EARLIER_and_frees_the_name(tmp_path: Path) -> None:
    """Refresh-not-pin, half two. Floors move earlier when history is backfilled and never
    later — the nine 2026-06-16 ingest-start names are the case. Re-reading the export is how
    we find out; a pinned list would exclude them forever."""
    _write_export(tmp_path, {"WBD": "2026-06-16"}, stamp="2026-08-01T000000Z")
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert "WBD" in excluded.for_bucket("swing_mid")
    # Crucible backfills; the newest export carries the earlier floor.
    _write_export(tmp_path, {"WBD": "2018-01-02"}, stamp="2026-08-02T000000Z")
    excluded = underlyings_below_inception(date(2026, 8, 2), exports_dir=tmp_path)
    assert "WBD" not in excluded.for_bucket("swing_mid")


def test_newest_export_wins(tmp_path: Path) -> None:
    _write_export(tmp_path, {"X": "2025-01-01"}, stamp="2026-07-01T000000Z")
    _write_export(tmp_path, {"Y": "2025-01-01"}, stamp="2026-08-01T000000Z")
    assert set(load_chain_inception_floors(tmp_path)) == {"Y"}


def test_none_is_empty_in_every_bucket() -> None:
    """The default threaded through the sampler when no export exists."""
    assert not ChainInceptionExclusions.none()
    assert ChainInceptionExclusions.none().for_bucket("swing_long") == frozenset()
    assert ChainInceptionExclusions.none().all_names() == frozenset()


def test_all_names_is_the_union_for_the_operator_line(tmp_path: Path) -> None:
    """The CLI reports one line per batch; it must name every excluded underlying across
    buckets, not just the 5y set."""
    _write_export(tmp_path, _LIVE_CLASS | _SEVEN_YEAR_ONLY)
    excluded = underlyings_below_inception(date(2026, 8, 1), exports_dir=tmp_path)
    assert excluded.all_names() == frozenset(_LIVE_CLASS) | frozenset(_SEVEN_YEAR_ONLY)
