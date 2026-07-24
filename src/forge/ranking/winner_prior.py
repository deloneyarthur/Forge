"""Winner-neighborhood prior — a learned generation-side prior over intra-cell params.

WHY: the sampler's learned weights steer WHICH cell enumerates (hypothesis, bucket,
regime gate, underlying) but nothing steers the continuous/ordinal knobs INSIDE a cell
— `delta_target`, exit `n_bars`, gate thresholds, `rank_k`. That surface is where the
v36/D282, v38/D288 and v40/D291 hand-tuned priors lived: each time Crucible measured a
param that mattered, we shipped one scoped constant. This module learns that shape
across every cell at once, from the configs that actually passed.

WHAT IT IS NOT: an edge model. It reorders draws inside a distribution whose honest
ceiling is sub-gate (0 of 302 honest configs clear cpcv 1.5). The realistic payoff is a
higher honest component RATE — pool quality, not a promotion unlock. See the proposal's
honest null.

SAFETY PROPERTIES, all pinned by tests, because this sits in front of a deterministic
enumerator:
  * BOUNDED — every weight lands in [exploration_floor, max_weight]. The prior tilts a
    draw; it can never pin a cell to one param value and end exploration there.
  * FLOORED — an unseen neighborhood keeps `exploration_floor` weight (D067), so
    evidence keeps flowing back to revise the estimate.
  * SHRUNK — a cell's tilt scales with how much honest evidence it has (Beta-style
    pseudo-count), so thin cells stay near-neutral instead of fitting their own noise.
  * NEUTRAL BY DEFAULT — `WinnerPrior.neutral()` returns exactly 1.0 everywhere, so the
    flag-off / cold-start enumeration path is byte-identical (hard rule #6).
  * CONTENT-ADDRESSED — `prior_id` hashes the canonical payload, so the artifact can be
    folded into `enumeration_inputs_hash` and same-seed reproduction stays honest.

TRAINING POPULATION is the caller's responsibility and it matters: seed on HONEST
passers only (`measurement_basis='fullhist_refit'`), never the 5yr screen. Fitting to
screen-passers would learn "what scores well on our own folds" — training on the
validation set one layer up.

Spec: docs/proposals/v50-winner-neighborhood-priors.md
Artifact conventions mirror `forge.ranking.model` (canonical JSON, content-hashed id,
corrupt-skipping `load_latest_*`).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

_LOG = structlog.get_logger(__name__)

PRIOR_SCHEMA_VERSION = 1

# A neighborhood keeps at least this share of a neutral draw, however bad its measured
# outcome. The D067 exploration-floor principle, applied on the param axis: a param
# value that looks dead must still be sampled often enough to revise the estimate.
_DEFAULT_EXPLORATION_FLOOR = 0.25

# ...and no neighborhood may draw more than this multiple of neutral. Caps how far one
# cell's evidence can concentrate the search — the anti-monoculture guard on the param
# axis (the cell-level analogue of `_MR_RANGING_GATE_WEIGHT`).
_DEFAULT_MAX_WEIGHT = 3.0

# Beta-style pseudo-count: a (cell, param, bin) with this many observations gets half
# its evidence-implied tilt; far fewer stays near-neutral. Set at 10 because the
# hand-tuned priors this generalizes (D282/D288/D291) were each justified on tens of
# decided rows per cell, not hundreds.
_DEFAULT_SHRINKAGE_N = 10.0

# Params are binned before pooling: honest n is in the hundreds per cell, so a
# continuous fit would chase noise. Bins are the coarse "neighborhood" the hand-priors
# also used (U[8,12] is a bin, not a point estimate).
_DEFAULT_N_BINS = 4


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _cell_str(cell: Sequence[str]) -> str:
    """Cells are tuples in memory and strings on disk; one encoding both ways so the
    artifact round-trips byte-identically."""
    return "\x1f".join(str(c) for c in cell)


@dataclass(frozen=True, slots=True)
class WinnerPrior:
    """A frozen, content-addressed multiplier over (cell, param, value).

    `weights` maps "cell\x1fparam" -> per-bin multiplier, alongside the bin edges that
    place a value. Everything outside the fitted support returns 1.0 (neutral), so the
    prior only ever reshapes where it has honest evidence.
    """

    schema_version: int
    prior_id: str
    trained_through: datetime
    n_observations: int
    exploration_floor: float
    max_weight: float
    shrinkage_n: float
    # key -> (bin_edges, bin_weights); len(weights) == len(edges) + 1
    weights: tuple[tuple[str, tuple[float, ...], tuple[float, ...]], ...]

    @staticmethod
    def neutral() -> WinnerPrior:
        """The cold-start / flag-off prior: reshapes nothing, anywhere."""
        return WinnerPrior(
            schema_version=PRIOR_SCHEMA_VERSION,
            prior_id="neutral",
            # tz-AWARE: `load_latest_winner_prior` orders on `trained_through`, and a
            # naive sentinel would raise on comparison with real (aware) artifacts.
            trained_through=datetime.min.replace(tzinfo=UTC),
            n_observations=0,
            exploration_floor=_DEFAULT_EXPLORATION_FLOOR,
            max_weight=_DEFAULT_MAX_WEIGHT,
            shrinkage_n=_DEFAULT_SHRINKAGE_N,
            weights=(),
        )

    def weight(self, cell: Sequence[str], param: str, value: float) -> float:
        """Draw multiplier for `value` of `param` within `cell`; 1.0 where unfitted.

        Neutral-on-miss is load-bearing: an unfitted cell or param must leave the
        sampler's existing draw exactly as it was, so activating the prior can only
        change cells the evidence actually covers.
        """
        key = f"{_cell_str(cell)}\x1e{param}"
        for entry_key, edges, bin_weights in self.weights:
            if entry_key != key:
                continue
            idx = 0
            for edge in edges:
                if value < edge:
                    break
                idx += 1
            return bin_weights[min(idx, len(bin_weights) - 1)]
        return 1.0


def _bin_edges(values: Sequence[float], n_bins: int) -> tuple[float, ...]:
    """Quantile edges over the observed support. Quantiles (not equal width) so a
    skewed param still splits its mass; degenerate/duplicate edges collapse, which
    naturally reduces the bin count for near-constant params."""
    ordered = sorted(values)
    edges: list[float] = []
    for i in range(1, n_bins):
        q = ordered[min(len(ordered) - 1, int(i * len(ordered) / n_bins))]
        if not edges or q > edges[-1]:
            edges.append(float(q))
    return tuple(edges)


def _bin_of(value: float, edges: Sequence[float]) -> int:
    idx = 0
    for edge in edges:
        if value < edge:
            break
        idx += 1
    return idx


def fit_winner_prior(
    observations: Iterable[Mapping[str, Any]],
    *,
    trained_through: datetime,
    exempt_cells: frozenset[tuple[str, ...]] | set[tuple[str, ...]] | None = None,
    exploration_floor: float = _DEFAULT_EXPLORATION_FLOOR,
    max_weight: float = _DEFAULT_MAX_WEIGHT,
    shrinkage_n: float = _DEFAULT_SHRINKAGE_N,
    n_bins: int = _DEFAULT_N_BINS,
) -> WinnerPrior:
    """Fit per-(cell, param) bin multipliers from honest observations.

    Each observation is ``{"cell": (...), "params": {name: value}, "outcome": float}``
    where `outcome` is the HONEST outcome (cpcv_sharpe_p25 on the `fullhist_refit`
    lane). Weight is driven by a bin's mean outcome relative to its cell's mean —
    "is this neighborhood better than the rest of its own cell?" — which keeps the
    prior orthogonal to the cell-level weights the sampler already applies.

    `exempt_cells` are returned neutral: cells whose params an operator already pinned
    by hand (D276 resid, D291 timer) must not be reshaped twice on the same evidence.
    """
    rows = list(observations)
    if not rows:
        msg = "no observations to fit a winner prior"
        raise ValueError(msg)

    exempt = {tuple(c) for c in (exempt_cells or set())}

    # (cell, param) -> [(value, outcome)]
    grouped: dict[tuple[tuple[str, ...], str], list[tuple[float, float]]] = defaultdict(list)
    cell_outcomes: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for row in rows:
        cell = tuple(str(c) for c in row["cell"])
        outcome = float(row["outcome"])
        cell_outcomes[cell].append(outcome)
        if cell in exempt:
            continue
        for name, value in dict(row["params"]).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                grouped[(cell, str(name))].append((float(value), outcome))

    cell_mean = {c: sum(v) / len(v) for c, v in cell_outcomes.items()}
    cell_spread = {
        c: (math.sqrt(sum((x - cell_mean[c]) ** 2 for x in v) / len(v)) if len(v) > 1 else 0.0)
        for c, v in cell_outcomes.items()
    }

    entries: list[tuple[str, tuple[float, ...], tuple[float, ...]]] = []
    for (cell, param), pairs in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        spread = cell_spread.get(cell, 0.0)
        if spread <= 0.0 or len(pairs) < 2:
            continue  # nothing to learn from: a cell whose outcomes never vary
        edges = _bin_edges([v for v, _ in pairs], n_bins)
        if not edges:
            continue  # near-constant param: no neighborhoods to distinguish
        buckets: dict[int, list[float]] = defaultdict(list)
        for value, outcome in pairs:
            buckets[_bin_of(value, edges)].append(outcome)

        bin_weights: list[float] = []
        for idx in range(len(edges) + 1):
            outcomes = buckets.get(idx, [])
            if not outcomes:
                # Unobserved neighborhood inside the fitted support: floor it rather
                # than neutral, so the prior does not silently favour gaps.
                bin_weights.append(exploration_floor)
                continue
            n = len(outcomes)
            mean = sum(outcomes) / n
            # Standardized lift over the cell's own mean, shrunk by evidence volume.
            lift = (mean - cell_mean[cell]) / spread
            shrunk = lift * (n / (n + shrinkage_n))
            bin_weights.append(_clamp(math.exp(shrunk), exploration_floor, max_weight))
        entries.append((f"{_cell_str(cell)}\x1e{param}", edges, tuple(bin_weights)))

    prior_id = _compute_prior_id(
        trained_through=trained_through,
        n_observations=len(rows),
        exploration_floor=exploration_floor,
        max_weight=max_weight,
        shrinkage_n=shrinkage_n,
        entries=entries,
    )
    return WinnerPrior(
        schema_version=PRIOR_SCHEMA_VERSION,
        prior_id=prior_id,
        trained_through=trained_through,
        n_observations=len(rows),
        exploration_floor=exploration_floor,
        max_weight=max_weight,
        shrinkage_n=shrinkage_n,
        weights=tuple(entries),
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _payload(
    *,
    trained_through: datetime,
    n_observations: int,
    exploration_floor: float,
    max_weight: float,
    shrinkage_n: float,
    entries: Sequence[tuple[str, tuple[float, ...], tuple[float, ...]]],
) -> dict[str, Any]:
    """The canonical, id-free content — what `prior_id` hashes and what is written."""
    return {
        "schema_version": PRIOR_SCHEMA_VERSION,
        "kind": "winner_prior",
        "trained_through": trained_through.isoformat(),
        "n_observations": n_observations,
        "exploration_floor": exploration_floor,
        "max_weight": max_weight,
        "shrinkage_n": shrinkage_n,
        "weights": [
            {"key": key, "edges": list(edges), "bin_weights": list(bin_weights)}
            for key, edges, bin_weights in entries
        ],
    }


def _compute_prior_id(**kwargs: Any) -> str:
    return hashlib.sha256(_canonical(_payload(**kwargs)).encode("utf-8")).hexdigest()[:16]


def save_winner_prior(prior: WinnerPrior, models_dir: Path) -> Path:
    """Write the canonical artifact; content-hashed name makes this idempotent."""
    models_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload(
        trained_through=prior.trained_through,
        n_observations=prior.n_observations,
        exploration_floor=prior.exploration_floor,
        max_weight=prior.max_weight,
        shrinkage_n=prior.shrinkage_n,
        entries=prior.weights,
    )
    payload["prior_id"] = prior.prior_id
    stamp = prior.trained_through.strftime("%Y%m%dT%H%M%S")
    path = models_dir / f"winner_prior_v{prior.schema_version}_{stamp}Z_{prior.prior_id[:8]}.json"
    path.write_text(_canonical(payload), encoding="utf-8")
    return path


def load_winner_prior(path: Path) -> WinnerPrior:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = tuple(
        (
            str(w["key"]),
            tuple(float(e) for e in w["edges"]),
            tuple(float(b) for b in w["bin_weights"]),
        )
        for w in raw["weights"]
    )
    return WinnerPrior(
        schema_version=int(raw["schema_version"]),
        prior_id=str(raw["prior_id"]),
        trained_through=datetime.fromisoformat(raw["trained_through"]),
        n_observations=int(raw["n_observations"]),
        exploration_floor=float(raw["exploration_floor"]),
        max_weight=float(raw["max_weight"]),
        shrinkage_n=float(raw["shrinkage_n"]),
        weights=entries,
    )


def load_latest_winner_prior(models_dir: Path) -> WinnerPrior | None:
    """Newest valid artifact by (trained_through, prior_id); corrupt files skipped.

    Corrupt-skip rather than raise: a bad artifact must degrade generation to the
    neutral path, never halt the daemon (the `load_latest_robustness_model` contract).
    """
    if not models_dir.is_dir():
        return None
    candidates: list[WinnerPrior] = []
    for path in sorted(models_dir.glob("winner_prior_*.json")):
        try:
            candidates.append(load_winner_prior(path))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            _LOG.warning("winner_prior_artifact_unreadable", path=str(path), error=str(exc))
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.trained_through, p.prior_id))
