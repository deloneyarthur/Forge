"""Oracle reader validation: schema pin, acceptance gate, parallel-array lengths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.king.oracle import (
    OracleError,
    OracleNotAccepted,
    OracleSchemaError,
    load_oracle,
)

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "king"
_ORACLE_FIXTURE = _FIXTURES / "oracle_published_2026-06-16T215346Z.json"


def _mutated(tmp_path: Path, **changes: object) -> Path:
    """Write a copy of the fixture oracle with top-level keys overwritten."""
    data = json.loads(_ORACLE_FIXTURE.read_text(encoding="utf-8"))
    data.update(changes)
    out = tmp_path / "oracle.json"
    out.write_text(json.dumps(data), encoding="utf-8")
    return out


def test_loads_published_fixture() -> None:
    oracle = load_oracle(_ORACLE_FIXTURE)
    assert oracle.schema_version == 1
    assert oracle.target == "cpcv_sharpe_p25"
    assert len(oracle.feature_columns) == 75
    for array in (oracle.weights, oracle.feature_median, oracle.feature_mean, oracle.feature_std):
        assert len(array) == len(oracle.feature_columns)
    assert oracle.model_ic == pytest.approx(0.3039, abs=1e-4)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OracleError):
        load_oracle(tmp_path / "nope.json")


def test_schema_mismatch_raises(tmp_path: Path) -> None:
    with pytest.raises(OracleSchemaError):
        load_oracle(_mutated(tmp_path, schema_version=2))


def test_not_accepted_raises(tmp_path: Path) -> None:
    data = json.loads(_ORACLE_FIXTURE.read_text(encoding="utf-8"))
    data["acceptance"]["accepted"] = False
    out = tmp_path / "oracle.json"
    out.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OracleNotAccepted):
        load_oracle(out)


def test_parallel_array_mismatch_raises(tmp_path: Path) -> None:
    data = json.loads(_ORACLE_FIXTURE.read_text(encoding="utf-8"))
    data["scorer"]["weights"] = data["scorer"]["weights"][:-1]
    out = tmp_path / "oracle.json"
    out.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OracleError):
        load_oracle(out)
