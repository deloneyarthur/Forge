"""Reader for the published meta-king durable-score oracle.

Crucible fits a ridge on the full-history durable corpus and republishes it
daily (07:00) as a plain-JSON oracle on the Crucible->Forge exports seam, *iff*
its acceptance gate passes (FORGE meta-king A3 relay §1). This module loads and
validates that artifact into an immutable :class:`DurableOracle`.

Callers re-read it each run via :func:`load_oracle` — the weights refresh daily
and MUST NOT be cached across runs; if ``latest`` stops advancing the acceptance
gate is rejecting and the last good oracle stands as current.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

# The reader is pinned to this schema; a bump means the seam changed shape, so
# the featurizer / ridge contract must be re-verified before trusting scores.
SCHEMA_VERSION = 1

_DEFAULT_REL_PATH = Path("optbt_data") / "exports" / "meta_king_oracle_latest.json"
_SCORER_ARRAYS = ("weights", "feature_median", "feature_mean", "feature_std")
_REQUIRED_KEYS = ("target", "n_train", "published_at", "feature_columns", "scorer")


class OracleError(RuntimeError):
    """Base for meta-king oracle load failures (never silently swallowed)."""


class OracleSchemaError(OracleError):
    """The artifact's ``schema_version`` is not the pinned :data:`SCHEMA_VERSION`."""


class OracleNotAccepted(OracleError):
    """The artifact's acceptance gate did not pass.

    Crucible only republishes ``latest`` when the gate passes, so a
    non-accepted artifact means a hand-edited / corrupt file — refuse to score.
    """


@dataclass(frozen=True, slots=True)
class DurableOracle:
    """Immutable snapshot of the published durable-score ridge.

    The four scorer arrays are all parallel to ``feature_columns``.
    """

    schema_version: int
    target: str
    n_train: int
    published_at: str
    feature_columns: tuple[str, ...]
    weights: tuple[float, ...]
    feature_median: tuple[float, ...]
    feature_mean: tuple[float, ...]
    feature_std: tuple[float, ...]
    intercept: float
    lam: float
    acceptance: Mapping[str, Any]

    @property
    def model_ic(self) -> float | None:
        """The accepted model's in-corpus IC, if the acceptance block carries it."""
        value = self.acceptance.get("model_ic")
        return float(value) if isinstance(value, (int, float)) else None


def default_oracle_path() -> Path:
    """Absolute path to the live ``meta_king_oracle_latest.json`` under ``$HOME``."""
    return Path.home() / _DEFAULT_REL_PATH


def load_oracle(path: Path | None = None) -> DurableOracle:
    """Load and validate the durable-score oracle from ``path``.

    ``path`` defaults to :func:`default_oracle_path`. Always reads from disk (no
    caching) so a daily refit is picked up on the next call.

    Raises:
        OracleError: the file is missing, unreadable, malformed, or has a
            scorer array whose length disagrees with ``feature_columns``.
        OracleSchemaError: ``schema_version`` != :data:`SCHEMA_VERSION`.
        OracleNotAccepted: the acceptance gate did not pass.
    """
    target_path = path if path is not None else default_oracle_path()
    if not target_path.exists():
        msg = f"meta-king oracle not found at {target_path}"
        raise OracleError(msg)
    try:
        raw: Any = json.loads(target_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"meta-king oracle at {target_path} is not valid JSON: {exc}"
        raise OracleError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"meta-king oracle at {target_path} is not a JSON object"
        raise OracleError(msg)

    schema = raw.get("schema_version")
    if schema != SCHEMA_VERSION:
        msg = (
            f"meta-king oracle schema_version={schema!r} but this reader is "
            f"pinned to {SCHEMA_VERSION}; the seam changed shape — re-verify the "
            f"featurizer/ridge contract before trusting scores"
        )
        raise OracleSchemaError(msg)

    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if missing:
        msg = f"meta-king oracle at {target_path} missing keys: {missing}"
        raise OracleError(msg)

    acceptance_raw = raw.get("acceptance")
    acceptance: Mapping[str, Any] = acceptance_raw if isinstance(acceptance_raw, dict) else {}
    if not acceptance.get("accepted", False):
        msg = (
            f"meta-king oracle at {target_path} is not accepted "
            f"(acceptance={acceptance_raw!r}); refusing to score"
        )
        raise OracleNotAccepted(msg)

    scorer = raw["scorer"]
    if not isinstance(scorer, dict):
        msg = f"meta-king oracle at {target_path} has a non-object scorer"
        raise OracleError(msg)

    columns = tuple(str(col) for col in raw["feature_columns"])
    arrays: dict[str, tuple[float, ...]] = {}
    for name in _SCORER_ARRAYS:
        if name not in scorer:
            msg = f"meta-king oracle scorer missing array {name!r}"
            raise OracleError(msg)
        values = tuple(float(v) for v in scorer[name])
        if len(values) != len(columns):
            msg = (
                f"meta-king oracle scorer.{name} has {len(values)} entries but "
                f"there are {len(columns)} feature_columns"
            )
            raise OracleError(msg)
        arrays[name] = values

    if "intercept" not in scorer:
        msg = "meta-king oracle scorer missing 'intercept'"
        raise OracleError(msg)

    return DurableOracle(
        schema_version=SCHEMA_VERSION,
        target=str(raw["target"]),
        n_train=int(raw["n_train"]),
        published_at=str(raw["published_at"]),
        feature_columns=columns,
        weights=arrays["weights"],
        feature_median=arrays["feature_median"],
        feature_mean=arrays["feature_mean"],
        feature_std=arrays["feature_std"],
        intercept=float(scorer["intercept"]),
        lam=float(scorer.get("lam", 0.0)),
        acceptance=acceptance,
    )
