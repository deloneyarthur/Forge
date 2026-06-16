"""forge.king — the meta-king generator arm (FORGE meta-king A3).

Searches the grammar's genome space to maximize Crucible's published
durable-score oracle, and surfaces the top genomes ("kings") for inspection.

Phase 0 is generation-only: it reads the oracle, scores grammar-valid
candidates, and ranks them — it writes NOTHING to Crucible's inbox. The
submission half (source-tagged queueing into the §8.7 pipeline plus the
mandatory DSR trial-laundering guard) is gated on Crucible provenance/DSR
coordination and is deliberately absent from this package.

Public API:

- :func:`load_oracle` / :class:`DurableOracle` — read + validate the published
  ridge (schema-pinned, acceptance-gated, no caching).
- :func:`featurize` / :func:`score_genome` — reproduce the oracle's scorer
  bit-for-bit (verified against Crucible's published reference vectors).
- :func:`search_kings` / :class:`King` / :class:`KingSearchResult` —
  deterministic oracle-ranked search with trial-count (``N``) bookkeeping.
- :func:`gated_tried_hashes` — best-effort dedup set from the gated-runs export.
"""

from __future__ import annotations

from forge.king.dedup import gated_tried_hashes
from forge.king.featurize import featurize
from forge.king.oracle import (
    DurableOracle,
    OracleError,
    OracleNotAccepted,
    OracleSchemaError,
    default_oracle_path,
    load_oracle,
)
from forge.king.score import score_genome
from forge.king.search import King, KingSearchResult, search_kings
from forge.king.submit import (
    KingSubmissionRecord,
    KingSubmissionResult,
    submit_kings,
)

__all__ = [
    "DurableOracle",
    "King",
    "KingSearchResult",
    "KingSubmissionRecord",
    "KingSubmissionResult",
    "OracleError",
    "OracleNotAccepted",
    "OracleSchemaError",
    "default_oracle_path",
    "featurize",
    "gated_tried_hashes",
    "load_oracle",
    "score_genome",
    "search_kings",
    "submit_kings",
]
