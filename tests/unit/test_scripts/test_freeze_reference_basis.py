"""The redundancy leg's reference book must be basis-stable, and it must say so out loud.

Freeze condition (C) leg 2 reads `|corr to frozen_b36f49a4|` from Crucible's export. The values
are only comparable across windows if the reference book itself is unchanged -- same components,
same weights, same window, same minting. Crucible agreed (2026-08-02) to flag any change to
`corr_to_book`'s window or `min_overlap` before shipping it, but a promise depends on someone
remembering, and this week produced two defects of exactly that shape on both sides (our
computed-but-never-passed keyword, their computed-but-never-persisted ablation value). So the
promise is converted into a check: fingerprint the reference book's identity fields and refuse
the leg when they move.

Refusing is the whole point. A leg that silently keeps reading after its yardstick was re-minted
would attribute the level shift to our supply -- and since a re-mint can move the level either
way, it could manufacture a false PASS and freeze the grammar on a basis change.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

_SRC = Path(__file__).resolve().parents[3] / "scripts" / "freeze_tail_reading.py"
_spec = importlib.util.spec_from_file_location("freeze_tail_reading", _SRC)
assert _spec is not None
assert _spec.loader is not None
freeze_tail_reading = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(freeze_tail_reading)


def _book(**overrides: Any) -> dict[str, Any]:
    """The reference book VERBATIM as Crucible publishes it, minus any requested change.

    Copied from `corr_to_book_2026-08-02T140046Z.json`. It has to be the real record: the pin is
    a hash of these exact values, so a paraphrased fixture would test the hash function rather
    than the pin, and the first test below would be vacuous.
    """
    book = {
        "label": "frozen_b36f49a4",
        "minted_at": "2026-07-20T22:44:00.490030+00:00",
        "n_days": 2122,
        "spec_note": "second promotion 2026-07-20 (de00e099; freeze b36f49a4fe230f96)",
        "traded_unit": {"overlays": "off", "seed": 42, "vol_target_annual": 0.15},
        "weights": {"65316ca4": 0.5, "6bec53b4": 0.5},
        "window": ["2018-01-02", "2026-06-12"],
    }
    book.update(overrides)
    return book


def _export(tmp_path: Path, book: dict[str, Any] | None, rows: int = 4) -> Path:
    root = tmp_path / "optbt_data" / "exports"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "basis": "pearson of DAILY equity returns, min_overlap=60 sessions",
        "window_days": 14,
        "books": {} if book is None else {"frozen_b36f49a4": book},
        "rows": [
            {"config_hash": f"h{i}", "corr": {"frozen_b36f49a4": 0.1 * i}} for i in range(rows)
        ],
    }
    path = root / "corr_to_book_2026-08-02T140046Z.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_the_pinned_basis_matches_what_crucible_currently_publishes(home: Path) -> None:
    """The pin is only protective if it matches production the day it is written."""
    _export(home, _book())
    corr, fingerprint = freeze_tail_reading._load_corr()
    assert corr, "the unchanged reference book must load"
    assert fingerprint == freeze_tail_reading._REF_BASIS_FP


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("weights", {"65316ca4": 0.6, "6bec53b4": 0.4}),  # re-weighted -> different series
        ("window", ["2018-01-02", "2026-07-31"]),  # extended -> different overlap
        ("n_days", 2200),
        ("minted_at", "2026-08-02T00:51:24.161608+00:00"),  # re-minted
        ("spec_note", "third promotion 2026-08-02"),
    ],
)
def test_any_change_to_the_reference_book_is_refused(home: Path, field: str, value: Any) -> None:
    """Every identity field is load-bearing: a change to any of them changes the series."""
    _export(home, _book(**{field: value}))
    corr, fingerprint = freeze_tail_reading._load_corr()
    assert fingerprint != freeze_tail_reading._REF_BASIS_FP
    assert corr == {}, f"a re-based reference ({field}) must yield no observations, not new ones"


def test_the_reference_book_disappearing_is_refused_not_silently_zero(home: Path) -> None:
    """Crucible could reasonably drop a RETIRED book from the export as housekeeping."""
    _export(home, None)
    corr, fingerprint = freeze_tail_reading._load_corr()
    assert corr == {}
    assert fingerprint is None


def test_a_missing_export_still_fails_open_to_unavailable(home: Path) -> None:
    (home / "optbt_data" / "exports").mkdir(parents=True)
    assert freeze_tail_reading._load_corr() == ({}, None)
