"""Winner-neighborhood prior — the generation-side param prior (v50).

The prior concentrates intra-cell param draws toward the neighborhoods that honest
gate-passers occupy. These tests pin the properties that make it SAFE to put in front
of a deterministic enumerator: bounded reweighting, a floor that can never starve an
unseen neighborhood, and a byte-identical artifact round-trip.

Spec: docs/proposals/v50-winner-neighborhood-priors.md
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from forge.ranking.winner_prior import (
    PRIOR_SCHEMA_VERSION,
    WinnerPrior,
    fit_winner_prior,
    load_latest_winner_prior,
    load_winner_prior,
    save_winner_prior,
)

_CELL = ("mean_reversion", "rsi", "swing_mid")
_OTHER = ("trend_continuation", "donchian", "swing_mid")
_TRAINED = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _obs(cell: tuple[str, ...], param: str, value: float, outcome: float) -> dict[str, object]:
    return {"cell": cell, "params": {param: value}, "outcome": outcome}


def _split_observations() -> list[dict[str, object]]:
    """One cell where LOW `n_bars` is bad and HIGH is good — the v40/D291 shape."""
    rows: list[dict[str, object]] = []
    for i in range(40):
        rows.append(_obs(_CELL, "n_bars", 5.0 + (i % 2), -0.2))
        rows.append(_obs(_CELL, "n_bars", 11.0 + (i % 2), 0.9))
    return rows


class TestFit:
    def test_concentrates_weight_on_the_winning_neighborhood(self) -> None:
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        low = prior.weight(_CELL, "n_bars", 5.0)
        high = prior.weight(_CELL, "n_bars", 11.0)
        assert high > low, "the high-outcome neighborhood must draw more weight"

    def test_unseen_neighborhood_keeps_the_exploration_floor(self) -> None:
        """D067: never starve a neighborhood to zero — evidence must keep flowing."""
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        assert prior.weight(_CELL, "n_bars", 99.0) >= prior.exploration_floor > 0.0

    def test_unseen_cell_falls_back_to_neutral(self) -> None:
        """A cell with no honest evidence must not be reshaped at all."""
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        assert prior.weight(_OTHER, "n_bars", 5.0) == pytest.approx(1.0)

    def test_unseen_param_falls_back_to_neutral(self) -> None:
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        assert prior.weight(_CELL, "delta_target", 0.4) == pytest.approx(1.0)

    def test_weights_are_bounded(self) -> None:
        """Bounded reweighting: the prior tilts the draw, it never pins it. An
        unbounded multiplier would collapse the cell to one param value and end
        exploration in that cell."""
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        for value in (5.0, 6.0, 11.0, 12.0, 99.0):
            assert (
                prior.exploration_floor <= prior.weight(_CELL, "n_bars", value) <= prior.max_weight
            )

    def test_thin_evidence_shrinks_toward_neutral(self) -> None:
        """Beta-style shrinkage: 2 observations must move the weight far less than 80
        do, or the prior fits noise in every sparse cell (spec §2)."""
        thin = [_obs(_CELL, "n_bars", 11.0, 0.9), _obs(_CELL, "n_bars", 5.0, -0.2)]
        thin_prior = fit_winner_prior(thin, trained_through=_TRAINED)
        fat_prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        thin_tilt = abs(thin_prior.weight(_CELL, "n_bars", 11.0) - 1.0)
        fat_tilt = abs(fat_prior.weight(_CELL, "n_bars", 11.0) - 1.0)
        assert thin_tilt < fat_tilt

    def test_exempt_cells_are_not_reshaped(self) -> None:
        """Hand-pinned cells (D276 resid, D291 timer) already concentrate params by
        operator decision; the prior must not double-count them (spec §9c)."""
        prior = fit_winner_prior(
            _split_observations(), trained_through=_TRAINED, exempt_cells={_CELL}
        )
        assert prior.weight(_CELL, "n_bars", 11.0) == pytest.approx(1.0)
        assert prior.weight(_CELL, "n_bars", 5.0) == pytest.approx(1.0)

    def test_rejects_empty_observations(self) -> None:
        with pytest.raises(ValueError, match="no observations"):
            fit_winner_prior([], trained_through=_TRAINED)


class TestArtifact:
    def test_round_trips_byte_identical(self, tmp_path) -> None:
        """Hard rule #6: the artifact is part of enumeration identity, so save→load→
        save must be byte-stable or same-seed reproduction diverges."""
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        first = save_winner_prior(prior, tmp_path)
        reloaded = load_winner_prior(first)
        second = save_winner_prior(reloaded, tmp_path)
        assert first.read_bytes() == second.read_bytes()
        assert reloaded.prior_id == prior.prior_id

    def test_reloaded_prior_gives_identical_weights(self, tmp_path) -> None:
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        reloaded = load_winner_prior(save_winner_prior(prior, tmp_path))
        for value in (5.0, 11.0, 99.0):
            assert reloaded.weight(_CELL, "n_bars", value) == prior.weight(_CELL, "n_bars", value)

    def test_prior_id_is_content_addressed(self) -> None:
        """Same evidence → same id; different evidence → different id. The id is what
        gets folded into enumeration_inputs_hash, so it must track content."""
        a = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        b = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        assert a.prior_id == b.prior_id

        shifted = [*_split_observations(), _obs(_CELL, "n_bars", 11.0, 5.0)]
        assert fit_winner_prior(shifted, trained_through=_TRAINED).prior_id != a.prior_id

    def test_load_latest_skips_corrupt_and_picks_newest(self, tmp_path) -> None:
        old = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        newer = fit_winner_prior(
            _split_observations(), trained_through=datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
        )
        save_winner_prior(old, tmp_path)
        save_winner_prior(newer, tmp_path)
        (
            tmp_path / f"winner_prior_v{PRIOR_SCHEMA_VERSION}_20260726T000000Z_deadbeef.json"
        ).write_text("{not json", encoding="utf-8")
        loaded = load_latest_winner_prior(tmp_path)
        assert loaded is not None
        assert loaded.trained_through == newer.trained_through

    def test_load_latest_returns_none_on_empty_dir(self, tmp_path) -> None:
        assert load_latest_winner_prior(tmp_path / "nope") is None

    def test_artifact_is_sorted_json(self, tmp_path) -> None:
        prior = fit_winner_prior(_split_observations(), trained_through=_TRAINED)
        raw = json.loads(save_winner_prior(prior, tmp_path).read_text(encoding="utf-8"))
        assert raw["schema_version"] == PRIOR_SCHEMA_VERSION
        assert raw["kind"] == "winner_prior"


class TestNeutrality:
    def test_neutral_prior_reshapes_nothing(self) -> None:
        """The flag-off / cold-start path: a neutral prior must return exactly 1.0
        everywhere so the sampler's draw stays byte-identical (hard rule #6)."""
        neutral = WinnerPrior.neutral()
        assert neutral.weight(_CELL, "n_bars", 5.0) == 1.0
        assert neutral.weight(_OTHER, "delta_target", 0.4) == 1.0
