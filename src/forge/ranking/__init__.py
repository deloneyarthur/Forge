"""forge.ranking — the learned ranking models the weekly campaign ranks with.

What remains after Batch 5 G2 (2026-09-15): `features.py` / `dataset.py` (the honest-era
training frame), `model.py` (pure-Python IRLS + artifacts, trained in-run), `shadow.py`
(per-submission shadow scores, the retraining telemetry), `signal_key.py` (signal content keys
+ Jaccard, the gate's duplicate measure) and `types.RankedCandidate`. The §6.2 composite scorer,
the greedy diversifier, the floors and the flip apparatus left with the daemon (D419).
"""

from __future__ import annotations

from forge.ranking.types import RankedCandidate

__all__ = ["RankedCandidate"]
