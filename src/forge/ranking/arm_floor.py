"""Per-arm exploration floor — data side (D136; design D132 §F3, floor half).

WHY: the ranker's learned weights condition future submissions on past
choices, so an arm that arrives with no verdict history can be starved
indefinitely — the v17 cold start delivered the new arms to Crucible at ~8x
UNDER their raw emission share (arrivals measured Crucible-side, the
denominator truth). The floor guarantees model-independent coverage for
young arms at the ranking stage; the v18 GO doc (item 5) pulled it forward
of the rest of F3 (the learned-scorer wiring stays double-gated — D132's
coupling rule forbids wiring WITHOUT the floor, not the floor alone).

An **arm** is ``(role, indicator_id)`` for role ∈ {directional,
regime_filter} — the two thesis-bearing roles (the X1/X2 confluence chain
signal is sizing plumbing). An arm is **mature** once it has ≥ K verdicts
in the honest era (decided_at ≥ the D128 clean-era label cut — the same
window the verdict model trains on, so "mature" means "the learner has had
a chance to see it"). Everything else — including arms that have never
produced a verdict — is young and floor-eligible.

The selection mechanics live in ``forge.ranking.diversifier`` (the
reservation phase); this module owns arm extraction and the verdict-count
query.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from forge.feedback.rejection_weights import CLEAN_ERA_LABEL_CUT

if TYPE_CHECKING:
    import duckdb
    from crucible_contracts import StrategyConfig

Arm = tuple[str, str]

# Signal roles that constitute an arm (thesis-bearing). `confluence` is the
# X1/X2 sizing chain — deliberately excluded.
ARM_ROLES: frozenset[str] = frozenset({"directional", "regime_filter"})

# D132 §8 operator-approved floor parameters (K=25 / 2 slots / ≤10% batch —
# the D103 diversifier-floor precedent).
YOUNG_ARM_VERDICT_THRESHOLD: int = 25
ARM_FLOOR_SLOTS_PER_ARM: int = 2
ARM_FLOOR_BATCH_FRACTION: float = 0.10


def extract_arms(config: StrategyConfig) -> frozenset[Arm]:
    """The (role, indicator_id) arms a config carries."""
    return frozenset(
        (signal.role, indicator)
        for signal in config.signals
        if signal.role in ARM_ROLES
        for indicator in signal.indicators
    )


def _arms_from_config_json(config_json: str) -> frozenset[Arm]:
    """`extract_arms` over the raw submissions.config_json payload (cheap
    json parse — no pydantic round-trip for a count query)."""
    signals = json.loads(config_json).get("signals", ())
    return frozenset(
        (signal["role"], indicator)
        for signal in signals
        if signal.get("role") in ARM_ROLES
        for indicator in signal.get("indicators", ())
    )


def compute_mature_arms(
    conn: duckdb.DuckDBPyConnection,
    *,
    era_cut: datetime = CLEAN_ERA_LABEL_CUT,
    threshold: int = YOUNG_ARM_VERDICT_THRESHOLD,
) -> frozenset[Arm]:
    """Arms with ≥ ``threshold`` honest-era verdicts (everything else is
    young). Counts VERDICT rows, not configs — a refit child (same
    config_hash, new run_id) is an independent gate evaluation (D124), and
    the count mirrors the dataset builder's keep-all-refit-rows window."""
    cut = era_cut
    if cut.tzinfo is not None:
        # DuckDB TIMESTAMP columns are naive-UTC by repo convention.
        cut = cut.astimezone(UTC).replace(tzinfo=None)
    rows = conn.execute(
        """
        SELECT s.config_json, COUNT(*)
        FROM verdicts v
        JOIN submissions s ON v.config_hash = s.config_hash
        WHERE v.decided_at >= ?
        GROUP BY s.config_json
        """,
        [cut],
    ).fetchall()
    counts: Counter[Arm] = Counter()
    for config_json, n in rows:
        for arm in _arms_from_config_json(config_json):
            counts[arm] += int(n)
    return frozenset(arm for arm, count in counts.items() if count >= threshold)


__all__ = [
    "ARM_FLOOR_BATCH_FRACTION",
    "ARM_FLOOR_SLOTS_PER_ARM",
    "ARM_ROLES",
    "YOUNG_ARM_VERDICT_THRESHOLD",
    "Arm",
    "compute_mature_arms",
    "extract_arms",
]
