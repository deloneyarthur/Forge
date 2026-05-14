"""Tests for ranking.signal_key (Phase 5 module 8, D024/D10).

`content_key(signal) -> str` returns a deterministic hash of
(type, role, sorted(indicators), canonical(params)). Two signals with
the same content but different `id` strings produce the same key —
this matches what we want for diversity / proximity scoring across
batches where signal IDs are content-derived but may collide differently.
"""

from __future__ import annotations

from crucible_contracts import SignalSpec

from forge.ranking.signal_key import content_key


def _spec(
    *,
    id: str = "s1",
    type: str = "threshold",
    role: str = "directional",
    indicators: tuple[str, ...] = ("rsi_2",),
    params: dict[str, object] | None = None,
) -> SignalSpec:
    return SignalSpec(
        id=id,
        type=type,  # type: ignore[arg-type]
        role=role,  # type: ignore[arg-type]
        indicators=indicators,
        params=params if params is not None else {"threshold": 30.0},
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_content_key_is_deterministic() -> None:
    a = content_key(_spec())
    b = content_key(_spec())
    assert a == b


def test_content_key_returns_non_empty_string() -> None:
    k = content_key(_spec())
    assert isinstance(k, str)
    assert k


# ---------------------------------------------------------------------------
# id is NOT in the key
# ---------------------------------------------------------------------------


def test_content_key_ignores_id() -> None:
    a = content_key(_spec(id="alpha"))
    b = content_key(_spec(id="beta"))
    assert a == b


# ---------------------------------------------------------------------------
# Content fields ARE in the key
# ---------------------------------------------------------------------------


def test_content_key_changes_on_type() -> None:
    a = content_key(_spec(type="threshold"))
    b = content_key(_spec(type="rule"))
    assert a != b


def test_content_key_changes_on_role() -> None:
    a = content_key(_spec(role="directional"))
    b = content_key(_spec(role="regime_filter"))
    assert a != b


def test_content_key_changes_on_indicators() -> None:
    a = content_key(_spec(indicators=("rsi_2",)))
    b = content_key(_spec(indicators=("rsi_5",)))
    assert a != b


def test_content_key_changes_on_params() -> None:
    a = content_key(_spec(params={"threshold": 30.0}))
    b = content_key(_spec(params={"threshold": 70.0}))
    assert a != b


# ---------------------------------------------------------------------------
# Order independence — indicators are sorted, params canonicalized
# ---------------------------------------------------------------------------


def test_content_key_is_indicator_order_independent() -> None:
    a = content_key(_spec(indicators=("rsi_2", "rsi_5")))
    b = content_key(_spec(indicators=("rsi_5", "rsi_2")))
    assert a == b


def test_content_key_is_param_key_order_independent() -> None:
    a = content_key(_spec(params={"a": 1, "b": 2}))
    b = content_key(_spec(params={"b": 2, "a": 1}))
    assert a == b
