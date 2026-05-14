"""Tests for ``forge.ranking.config`` — `load_ranker_config(path)`.

Round-trips `config/ranker.yaml` into a `RankerConfig`. Mirrors the
Phase 3 `load_calibration` loader pattern: required keys present,
unknown keys rejected, value ranges enforced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.ranking.config import load_ranker_config
from forge.ranking.types import RankerConfig

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RANKER_YAML = _REPO_ROOT / "config" / "ranker.yaml"


# ---------------------------------------------------------------------------
# Happy path — round-trips §10.3 defaults
# ---------------------------------------------------------------------------


def test_loads_repo_ranker_yaml_with_defaults() -> None:
    cfg = load_ranker_config(_RANKER_YAML)
    assert isinstance(cfg, RankerConfig)
    assert cfg.weights.signal_density == pytest.approx(0.30)
    assert cfg.weights.novelty == pytest.approx(0.25)
    assert cfg.weights.regime_diversity == pytest.approx(0.20)
    assert cfg.weights.permutation_test == pytest.approx(0.15)
    assert cfg.weights.prior_promotion_proximity == pytest.approx(0.10)
    assert cfg.diversification.method == "greedy"
    assert cfg.diversification.similarity_metric == "jaccard"


# ---------------------------------------------------------------------------
# Fixture helper — write a temp YAML and parse it
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "ranker.yaml"
    target.write_text(body, encoding="utf-8")
    return target


_DEFAULT_BODY = """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: greedy
    similarity_metric: jaccard
"""


def test_round_trips_synthetic_yaml(tmp_path: Path) -> None:
    p = _write(tmp_path, _DEFAULT_BODY)
    cfg = load_ranker_config(p)
    assert cfg.weights.novelty == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Failure modes — structure
# ---------------------------------------------------------------------------


def test_raises_when_top_level_not_mapping(tmp_path: Path) -> None:
    p = _write(tmp_path, "- not\n- a\n- mapping\n")
    with pytest.raises(ValueError, match=r"top-level"):
        load_ranker_config(p)


def test_raises_when_ranker_key_missing(tmp_path: Path) -> None:
    p = _write(tmp_path, "other: 1\n")
    with pytest.raises(ValueError, match=r"top-level"):
        load_ranker_config(p)


def test_raises_when_weights_key_missing(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  diversification:
    method: greedy
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"weights"):
        load_ranker_config(p)


def test_raises_when_diversification_key_missing(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
""",
    )
    with pytest.raises(ValueError, match=r"diversification"):
        load_ranker_config(p)


def test_raises_on_unknown_top_level_key(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        _DEFAULT_BODY + "  extra_section:\n    foo: 1\n",
    )
    with pytest.raises(ValueError, match=r"unknown"):
        load_ranker_config(p)


# ---------------------------------------------------------------------------
# Failure modes — weights
# ---------------------------------------------------------------------------


def test_raises_when_weight_component_missing(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.25
    # prior_promotion_proximity missing
  diversification:
    method: greedy
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"prior_promotion_proximity"):
        load_ranker_config(p)


def test_raises_on_unknown_weight_key(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
    bogus_weight: 0.0
  diversification:
    method: greedy
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"unknown.*bogus_weight"):
        load_ranker_config(p)


def test_raises_when_weights_sum_off(tmp_path: Path) -> None:
    """`RankerWeights.__post_init__` rejects sum != 1.0; the loader
    surfaces it the same way."""
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.50
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: greedy
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"sum to 1\.0"):
        load_ranker_config(p)


def test_raises_on_non_numeric_weight(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: "not-a-number"
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: greedy
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"signal_density"):
        load_ranker_config(p)


# ---------------------------------------------------------------------------
# Failure modes — diversification
# ---------------------------------------------------------------------------


def test_raises_on_unknown_diversification_method(tmp_path: Path) -> None:
    """Phase 4 ships greedy only; dpp is reserved for a later bump."""
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: dpp
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"method"):
        load_ranker_config(p)


def test_raises_on_unknown_similarity_metric(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: greedy
    similarity_metric: cosine
""",
    )
    with pytest.raises(ValueError, match=r"similarity_metric"):
        load_ranker_config(p)


def test_raises_on_missing_method(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    similarity_metric: jaccard
""",
    )
    with pytest.raises(ValueError, match=r"method"):
        load_ranker_config(p)


def test_raises_on_unknown_diversification_key(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
ranker:
  weights:
    signal_density: 0.30
    novelty: 0.25
    regime_diversity: 0.20
    permutation_test: 0.15
    prior_promotion_proximity: 0.10
  diversification:
    method: greedy
    similarity_metric: jaccard
    extra_setting: nope
""",
    )
    with pytest.raises(ValueError, match=r"unknown.*extra_setting"):
        load_ranker_config(p)


# ---------------------------------------------------------------------------
# Missing file
# ---------------------------------------------------------------------------


def test_raises_on_missing_file(tmp_path: Path) -> None:
    p = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        load_ranker_config(p)
