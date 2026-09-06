"""Leg 2 must refuse to judge a newest window that is mostly unjoined to `corr_to_book`.

Since 2026-09-06 Crucible's `corr_to_book_*.json` is cut from a nightly snapshot, so the newest
export trails decisions by 7 to 31 hours and the freshest configs arrive with no correlation row
yet. The population-level 50% join floor cannot see that: a series can be 60% joined overall while
the one window the leg actually judges -- the NEWEST, compared against the prior maximum -- is 30%
joined, or 0% joined. In the 0% case `_tcm_corr` returns NaN, the NaN is dropped, and "newest"
silently becomes the previous window, so the verdict is printed about a window nobody asked about.
A guard that passes on absent data certifies (D387); the leg must say it cannot read the newest
window rather than read the one before it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "scripts" / "freeze_tail_reading.py"
_spec = importlib.util.spec_from_file_location("freeze_tail_reading_newest", _SRC)
assert _spec is not None
assert _spec.loader is not None
freeze_tail_reading = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(freeze_tail_reading)

_WIDTH = 4


def _obs(joined_per_window: list[int]) -> list[tuple[str, float, float | None]]:
    """Two-or-more windows of one cell; `joined_per_window[i]` rows of window i carry a corr."""
    out: list[tuple[str, float, float | None]] = []
    for w, k in enumerate(joined_per_window):
        for i in range(_WIDTH):
            corr = 0.3 + 0.01 * i if i < k else None
            out.append(("mean_reversion/swing_mid", 0.5 + 0.1 * i + 0.01 * w, corr))
    return out


def _run(obs: list[tuple[str, float, float | None]], capsys: pytest.CaptureFixture[str]) -> str:
    joined = sum(1 for o in obs if o[2] is not None)
    freeze_tail_reading._leg2(
        obs, {"mean_reversion/swing_mid": 1.0}, _WIDTH, joined, len(obs), 0.01
    )
    return capsys.readouterr().out


def test_a_fully_joined_series_reads_the_newest_window(capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(_obs([_WIDTH, _WIDTH]), capsys)
    assert "newest vs worst-prior" in out
    assert "UNAVAILABLE" not in out


def test_a_thin_newest_window_is_refused_even_when_the_population_clears_50pct(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """4 of 4 then 1 of 4: population 62.5% clears the old floor; the judged window does not."""
    out = _run(_obs([_WIDTH, 1]), capsys)
    assert "UNAVAILABLE" in out
    assert "newest window" in out
    assert "WORSENED" not in out
    assert "not worsened" not in out


def test_an_unjoined_newest_window_is_not_silently_replaced_by_the_prior_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """4 of 4 then 0 of 4 is exactly 50% joined -- the population floor does not fire -- and the
    newest window's statistic is NaN. Before the guard, the leg dropped the NaN and judged window 1
    as if it were the newest."""
    out = _run(_obs([_WIDTH, 0]), capsys)
    assert "UNAVAILABLE" in out
    assert "newest window" in out
    assert "newest vs worst-prior" not in out


def test_the_population_floor_still_fires_first(capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(_obs([1, 1]), capsys)
    assert "join below 50%" in out
