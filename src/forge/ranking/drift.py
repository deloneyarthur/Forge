"""Distribution-drift + model-adoption primitives (learned-audit P3.2 / B6).

The daily timer trains a fresh learned model each run and the daemon adopts the
newest by mtime — a blind newest-wins rotation with no guard against (a) the input
distribution drifting away from what the model was trained on, or (b) rotating to a
model that is actually *worse* on the recent window. B6 asks for both a drift signal
and an adoption gate.

- `population_stability_index` — PSI between a reference sample (e.g. the training-era
  score distribution) and a current sample. The industry-standard drift metric:
  sum over quantile bins of the reference of (cur - ref) * ln(cur / ref). 0 = identical.
- `psi_severity` — the conventional banding: <0.1 stable, <0.25 moderate, else major.
- `adoption_verdict` — don't rotate to a model whose fresh-window signal (paired IC /
  AUC margin) is non-positive; "gate adoption, not training" (the timer keeps training
  daily; this only governs whether the daemon should switch to the new artifact).

Pure + deterministic (hard rules #5/#6) — no RNG, no clock. The consumers surface these
as telemetry (`forge status` / `eval` / healthcheck); actually blocking a live rotation
is an operator-gated production change built on top of these signals.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_PSI_MODERATE = 0.10
_PSI_MAJOR = 0.25
# Floor so an empty bin contributes a bounded (not infinite) term to the sum.
_PSI_EPS = 1e-6


def population_stability_index(
    reference: Sequence[float],
    current: Sequence[float],
    *,
    n_bins: int = 10,
    eps: float = _PSI_EPS,
) -> float | None:
    """PSI of `current` against `reference`, binned on the reference's quantiles.

    Returns None when either sample has < 2 points (nothing to compare). Bins are the
    reference's `n_bins`-quantile intervals; each side's per-bin proportion is floored
    at `eps` so a bin the current sample vacates (or fills from empty) yields a large
    but finite penalty rather than div-by-zero / log(0)."""
    if len(reference) < 2 or len(current) < 2:
        return None
    ref_sorted = sorted(reference)
    m = len(ref_sorted)
    # Interior quantile edges (n_bins-1 of them); ties collapse bins, which is fine —
    # empty bins just contribute an eps-floored term.
    edges = [ref_sorted[min(round(i / n_bins * (m - 1)), m - 1)] for i in range(1, n_bins)]

    def _counts(xs: Sequence[float]) -> list[int]:
        counts = [0] * n_bins
        for x in xs:
            counts[bisect_right(edges, x)] += 1
        return counts

    ref_counts = _counts(ref_sorted)
    cur_counts = _counts(current)
    n_ref, n_cur = len(reference), len(current)
    psi = 0.0
    for r, c in zip(ref_counts, cur_counts, strict=True):
        rp = max(r / n_ref, eps)
        cp = max(c / n_cur, eps)
        psi += (cp - rp) * math.log(cp / rp)
    return psi


def psi_severity(psi: float | None) -> str:
    """Conventional PSI banding: `unknown` (None) / `stable` (<0.1) / `moderate`
    (<0.25) / `major` (>=0.25)."""
    if psi is None:
        return "unknown"
    if psi <= _PSI_MODERATE:
        return "stable"
    if psi <= _PSI_MAJOR:
        return "moderate"
    return "major"


def adoption_verdict(fresh_signal: float | None, *, min_signal: float = 0.0) -> str:
    """Whether the daemon should ADOPT the newest artifact given its fresh-window signal
    (paired IC for the tail lane, AUC margin for F3). `UNKNOWN` when the window is too
    thin to have a signal; `BLOCK` when the signal fails to clear `min_signal` (default:
    must be strictly positive — a model no better than none is not worth rotating to)."""
    if fresh_signal is None:
        return "UNKNOWN"
    return "ADOPT" if fresh_signal > min_signal else "BLOCK"


__all__ = ["adoption_verdict", "population_stability_index", "psi_severity"]
