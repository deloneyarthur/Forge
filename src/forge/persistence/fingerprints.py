"""Historical structural fingerprints — the novelty filter's memory across batches.

WHY here: T2.7 (D049) dedups new candidates against every config Forge ever
submitted, by the structural fingerprint ``prefilters.novelty`` computes. The
loader lived in ``cli/main.py`` beside the daemon loop; the weekly campaign
needs the same memory, and the loop is retired in the final state (plan
2026-09 §12.4), so the read moves next to the table it reads.
"""

from __future__ import annotations

from pathlib import Path


def load_prior_structural_fingerprints(forge_db_path: Path) -> frozenset[str]:
    """Every distinct structural fingerprint in ``submissions.config_json``.

    O(N) rows x O(1) hash; the full scan is milliseconds at Forge's table
    sizes. Returns an empty frozenset when the DB is ``:memory:`` or missing —
    novelty's structural check becomes a no-op, matching pre-D049 behaviour.
    Malformed legacy rows are skipped: they must not gate enumeration.
    """
    if forge_db_path == Path(":memory:") or not forge_db_path.exists():
        return frozenset()
    from crucible_contracts import StrategyConfig  # noqa: PLC0415

    from forge.persistence.db import db_connection  # noqa: PLC0415
    from forge.prefilters.novelty import compute_structural_fingerprint  # noqa: PLC0415

    fingerprints: set[str] = set()
    with db_connection(forge_db_path) as conn:
        rows = conn.execute("SELECT config_json FROM submissions").fetchall()
    for (cj,) in rows:
        try:
            cfg = StrategyConfig.model_validate_json(cj if isinstance(cj, str) else str(cj))
        except (ValueError, TypeError):
            continue
        fingerprints.add(compute_structural_fingerprint(cfg))
    return frozenset(fingerprints)


__all__ = ["load_prior_structural_fingerprints"]
