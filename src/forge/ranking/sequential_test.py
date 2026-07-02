"""Sequential significance test for promotion/flip gates (learned-audit B5 / P3.1).

The rewire + §8.6 streak gates promoted a challenger on "k consecutive per-checkpoint
PASSes." Under a coin-flip null that is a 0.5^k false-promote rate (12.5% at k=3) with no
explicit Type-I control and an absolute per-checkpoint margin that ignores how noisy the
checkpoints are. This replaces it with a **Wald Sequential Probability Ratio Test** on the
stream of per-checkpoint PAIRED deltas (challenger - incumbent, one per fresh window):

    H0: mean delta = 0            (challenger no better than the incumbent)
    H1: mean delta = min_effect   (challenger better by a meaningful margin)

The SPRT accumulates the log-likelihood ratio and stops when it crosses a Wald boundary,
controlling the false-promote rate at ~alpha and the false-reject rate at ~beta over the
WHOLE sequential procedure — i.e. it is valid under the daily peeking the streak does, which
a fixed-sample CI (the D223 `_mean_ci95`) is not. `min_effect` makes the effect size explicit
instead of hiding it in a per-checkpoint margin; `min_observations` refuses to decide on one
or two noisy checkpoints.

Deterministic and pure (hard rules #5/#6) — no RNG, no clock. Variance is a plug-in sample
std (a quasi-SPRT / GLR when `sigma` is None); pass `sigma` from a warmup for the exact Wald
guarantee. Normal model for the deltas (WF / Spearman deltas are ~continuous, roughly
symmetric); the log-LR of Normal(0, σ²) vs Normal(δ, σ²) is (δ/σ²)·(Σx - nδ/2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Floor so a degenerate zero-variance run (all-identical deltas, or n<2) can't divide by
# zero; tiny enough not to distort a real spread.
_SIGMA_FLOOR = 1e-9


@dataclass(frozen=True, slots=True)
class SprtResult:
    """Outcome of the sequential test over the deltas seen so far.

    `decision` is one of ``"promote"`` (log-LR crossed the upper Wald boundary → accept H1),
    ``"reject"`` (crossed the lower boundary → accept H0), or ``"continue"`` (undecided, or
    fewer than `min_observations` deltas). `log_lr` is the accumulated log-likelihood ratio;
    `upper`/`lower` are the Wald boundaries it is compared against.
    """

    decision: str
    n: int
    log_lr: float
    upper: float
    lower: float
    mean_delta: float
    sigma: float


def sequential_mean_test(
    deltas: Sequence[float],
    *,
    alpha: float,
    beta: float,
    min_effect: float,
    sigma: float | None = None,
    min_observations: int = 3,
) -> SprtResult:
    """Wald SPRT for the mean of paired per-checkpoint `deltas`.

    Args:
        deltas: challenger - incumbent, one per fresh-window checkpoint (chronological).
        alpha: target false-promote probability (Type-I), in (0, 1).
        beta: target false-reject probability (Type-II), in (0, 1).
        min_effect: the H1 mean delta to detect (> 0); H0 mean is 0.
        sigma: known per-delta std; when None, the plug-in sample std (floored) is used.
        min_observations: never decide before this many deltas (defers on thin evidence).

    Raises:
        ValueError: on out-of-range `alpha`/`beta`/`min_effect`.
    """
    if not (0.0 < alpha < 1.0):
        msg = f"alpha must be in (0, 1); got {alpha!r}"
        raise ValueError(msg)
    if not (0.0 < beta < 1.0):
        msg = f"beta must be in (0, 1); got {beta!r}"
        raise ValueError(msg)
    if not (min_effect > 0.0) or math.isnan(min_effect) or math.isinf(min_effect):
        msg = f"min_effect must be a finite value > 0; got {min_effect!r}"
        raise ValueError(msg)

    # Wald boundaries on the log-likelihood ratio.
    upper = math.log((1.0 - beta) / alpha)
    lower = math.log(beta / (1.0 - alpha))

    n = len(deltas)
    if n == 0:
        return SprtResult("continue", 0, 0.0, upper, lower, 0.0, 0.0)

    mean = sum(deltas) / n
    if sigma is None:
        if n >= 2:
            var = sum((d - mean) ** 2 for d in deltas) / (n - 1)
            sd = math.sqrt(var)
        else:
            sd = 0.0
        sd = max(sd, _SIGMA_FLOOR)
    else:
        sd = max(sigma, _SIGMA_FLOOR)

    # log-LR of Normal(0, σ²) vs Normal(δ, σ²): (δ/σ²)·(Σx - nδ/2).
    total = sum(deltas)
    log_lr = (min_effect / sd**2) * (total - n * min_effect / 2.0)

    if n < min_observations:
        decision = "continue"
    elif log_lr >= upper:
        decision = "promote"
    elif log_lr <= lower:
        decision = "reject"
    else:
        decision = "continue"

    return SprtResult(decision, n, log_lr, upper, lower, mean, sd)


__all__ = ["SprtResult", "sequential_mean_test"]
