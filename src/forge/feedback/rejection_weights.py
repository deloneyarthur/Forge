"""Failure-bias weights for the enumerator (long-term #1).

Forge's prior-promotion-proximity term in the ranker (§6.2) is the only
memory of past outcomes today, and it's dead until something promotes.
This module gives the enumerator its OWN memory: per-hypothesis posterior
mean of promotion rate, Bayesian-smoothed so untested hypotheses get
near-prior weight and well-tested-but-failing hypotheses get
down-weighted as their sample size grows.

Wiring (separate from this module):
  - cli/main.py computes weights once per iteration via
    `compute_hypothesis_weights(db, gated_runs)`
  - sampler.py accepts an optional `hypothesis_weights` map and
    `rng.choices(weights=...)` instead of `rng.choice(...)`
  - Empty/missing weights → uniform sampling (no behavior change)

Determinism note (hard rule #6 nuance): given the same
`(grammar_version, registry_version, root_seed, iteration,
gated_runs_snapshot)`, enumeration is deterministic. Weights are an
additional input. They change over time as Crucible gates more runs;
that's the *point* — Forge learns. The reproducibility property holds
when the gated_runs snapshot is held constant.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    import duckdb
    from crucible_contracts import GatedRun


# Beta prior over per-hypothesis promotion rate. Mild prior favoring
# exploration: alpha=1, beta=10 → prior mean ~0.09. A hypothesis with
# zero observations gets that weight; a hypothesis with 100 observed
# trials and 0 promotions gets posterior mean = 1/111 ≈ 0.009 — strongly
# down-weighted. A hypothesis with 100 trials and 5 promotions gets
# 6/111 ≈ 0.054 — moderately up-weighted. The (1, 10) choice keeps the
# prior weak enough that data dominates after ~30 trials but strong
# enough that one unlucky batch doesn't zero out a class.
DEFAULT_ALPHA: float = 1.0
DEFAULT_BETA: float = 10.0


def compute_hypothesis_weights(
    db: duckdb.DuckDBPyConnection,
    gated_runs: Sequence[GatedRun],
    *,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
) -> dict[str, float]:
    """Posterior mean of promotion rate per hypothesis, Beta-smoothed.

    Joins Forge's `submissions` table (which has `config_json` containing
    the hypothesis) with the supplied `gated_runs` (which carry the
    promotion decision per `config_hash`). Returns a dict mapping
    hypothesis name → posterior mean in (0, 1).

    A hypothesis seen in `submissions` but not yet present in
    `gated_runs` (still being backtested) contributes nothing. Empty
    `gated_runs` → returns an empty dict; the caller treats that as
    "fall back to uniform sampling."
    """
    if not gated_runs:
        return {}

    promoted_by_hash: dict[str, bool] = {
        gr.run.config_hash: gr.decision.decision == "promote" for gr in gated_runs
    }
    rows = db.execute("SELECT config_hash, config_json FROM submissions").fetchall()
    counts: dict[str, list[int]] = {}  # hypothesis → [total, promoted]
    for config_hash, config_json_raw in rows:
        if config_hash not in promoted_by_hash:
            continue
        cfg = json.loads(config_json_raw) if isinstance(config_json_raw, str) else config_json_raw
        hyp = cfg.get("hypothesis") if isinstance(cfg, dict) else None
        if not isinstance(hyp, str):
            continue
        bucket = counts.setdefault(hyp, [0, 0])
        bucket[0] += 1
        if promoted_by_hash[config_hash]:
            bucket[1] += 1
    return {
        hyp: (alpha + promoted) / (alpha + beta + total)
        for hyp, (total, promoted) in counts.items()
    }


def prior_mean(*, alpha: float = DEFAULT_ALPHA, beta: float = DEFAULT_BETA) -> float:
    """Beta(alpha, beta) prior mean — the weight given to unseen hypotheses."""
    return alpha / (alpha + beta)


# D067 — minimum exploration weight applied across all canonical
# hypotheses to prevent the cold-start death spiral: a hypothesis with
# zero gated history gets prior weight (~0.091), but once a single
# unlucky batch lands it gets posterior ~0.005, then never gets sampled
# again to accumulate corrective evidence. The floor breaks this. Sized
# so that 5 active hypotheses all at floor would each receive ~20% of
# the budget — enough exploration for each to accumulate ~50 gated
# trials per ~250-candidate iteration before the floor releases them
# back to natural posterior dominance. See IMPLEMENTATION_DECISIONS.md
# D067 for full rationale (4039 submissions, 1 mean_reversion / 0
# trend_continuation pre-floor).
DEFAULT_EXPLORATION_FLOOR: float = 0.05


def apply_exploration_floor(
    weights: Mapping[str, float],
    *,
    hypotheses: Iterable[str],
    floor: float = DEFAULT_EXPLORATION_FLOOR,
    fallback: float | None = None,
) -> dict[str, float]:
    """Apply a minimum exploration floor across a canonical hypothesis set.

    For each ``h`` in ``hypotheses``:
      - Present in ``weights``: returns ``max(weights[h], floor)``.
      - Absent from ``weights`` with ``fallback`` set:
        ``max(fallback, floor)`` — used to keep unobserved hypotheses on
        the Beta prior (typically higher than the floor anyway, so the
        prior dominates for true cold-starts while the floor protects
        observed-but-failing hypotheses).
      - Absent with ``fallback=None``: returns ``floor`` directly.

    The returned dict ALWAYS contains every name in ``hypotheses``, so
    the sampler's `weights.get(h, prior_mean)` fallback no longer fires
    for canonical hypotheses — every one is explicitly floored before
    leaving this function. Callers that need the raw posterior should
    call ``compute_hypothesis_weights`` directly.
    """
    result: dict[str, float] = {}
    for h in hypotheses:
        if h in weights:
            result[h] = max(weights[h], floor)
        elif fallback is not None:
            result[h] = max(fallback, floor)
        else:
            result[h] = floor
    return result


__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_BETA",
    "DEFAULT_EXPLORATION_FLOOR",
    "apply_exploration_floor",
    "compute_hypothesis_weights",
    "prior_mean",
]
