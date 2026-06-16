"""Golden tests: Forge's featurizer + scorer reproduce Crucible's published oracle.

Pinned to the ``published_at=2026-06-16T21:53:46Z`` schema-1 reference vector
(FORGE meta-king A3 relay §3). The *math* is stable; the *weights* refresh
daily, so the oracle + the three reference genomes + their expected scores are
frozen under ``tests/fixtures/king/``. Regenerate the fixtures if the contract
math (not just the weights) ever changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.king import load_oracle, score_genome
from forge.king.oracle import DurableOracle

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "king"
_ORACLE_FIXTURE = _FIXTURES / "oracle_published_2026-06-16T215346Z.json"

# A3 §3 reference table — config_hash -> expected score (match to ~1e-5).
_REFERENCE_SCORES = {
    "d31fa393d20a7bc3": 0.782095,
    "173f2db5cdd873ce": 0.524689,
    "9a2f6fbfa802325b": -0.138255,
}


def _micro_oracle() -> DurableOracle:
    """The A3 §3 self-contained micro-artifact, as a ``DurableOracle``.

    Pins the ridge math (featurize -> impute -> standardize -> dot) independent
    of the live weights.
    """
    return DurableOracle(
        schema_version=1,
        target="cpcv_sharpe_p25",
        n_train=0,
        published_at="micro",
        feature_columns=("cat:hypothesis=mean_reversion", "has_ind:iv_rank", "num:delta_target"),
        weights=(1.0, 2.0, 3.0),
        feature_median=(0.0, 0.0, 0.3),
        feature_mean=(0.5, 0.5, 0.3),
        feature_std=(0.5, 0.5, 0.1),
        intercept=0.5,
        lam=0.0,
        acceptance={"accepted": True},
    )


def test_micro_artifact_with_delta() -> None:
    genome = {
        "hypothesis": "mean_reversion",
        "signals": [{"indicators": ["iv_rank"]}],
        "selector": {"delta_target": 0.4},
    }
    assert score_genome(genome, _micro_oracle()) == pytest.approx(6.5)


def test_micro_artifact_missing_delta_imputes_median() -> None:
    genome = {
        "hypothesis": "mean_reversion",
        "signals": [{"indicators": ["iv_rank"]}],
        "selector": {},
    }
    # delta_target absent -> NaN -> median 0.3 -> z=0 -> drops the third term.
    assert score_genome(genome, _micro_oracle()) == pytest.approx(3.5)


@pytest.mark.parametrize(("config_hash", "expected"), sorted(_REFERENCE_SCORES.items()))
def test_live_reference_genomes_match(config_hash: str, expected: float) -> None:
    oracle = load_oracle(_ORACLE_FIXTURE)
    genome = json.loads((_FIXTURES / f"genome_{config_hash}.json").read_text(encoding="utf-8"))
    assert score_genome(genome, oracle) == pytest.approx(expected, abs=1e-5)
