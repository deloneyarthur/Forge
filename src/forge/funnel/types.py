"""Value types for the pre-filter funnel export (D096 — Part B).

The export completes the two upstream stages of the combined pipeline funnel
described in `FUNNEL_INSTRUMENTATION.md` (the Crucible-side instrument):

    [Forge] enumerated            ← PerGrammarVersionFunnel.enumerated
    [Forge] survived pre-filters  ← PerGrammarVersionFunnel.survived_prefilters

Both structures are clock-free and filesystem-free — the writer
(`forge.funnel.export`) stamps `exported_at` via the blessed clock at
serialization time, keeping aggregation pure and deterministically testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# Bumped only on a breaking change to the export shape; Crucible's funnel reads
# this to parse defensively (its hard rule #7 — degrade gracefully).
SCHEMA_VERSION: Final[str] = "1.0"


@dataclass(frozen=True, slots=True)
class PerGrammarVersionFunnel:
    """One grammar version's aggregated pre-filter funnel.

    `enumerated` and `survived_prefilters` are the two Crucible [Forge-opt]
    stages. `submitted` is the post-diversifier count (bridges to Crucible's
    own "submitted" stage). `rejection_breakdown` is the first-failing-filter
    histogram across the version's batches — the "which pre-filter killed the
    rest" annotation. `enumerated_by_hypothesis` is the "which grammar branch"
    annotation on the enumerated stage.
    """

    grammar_version: str
    batches: int
    enumerated: int
    survived_prefilters: int
    submitted: int
    rejection_breakdown: dict[str, int]
    enumerated_by_hypothesis: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        """JSON-serializable form, keys matching the dispatch-doc schema."""
        return {
            "batches": self.batches,
            "enumerated": self.enumerated,
            "survived_prefilters": self.survived_prefilters,
            "submitted": self.submitted,
            "rejection_breakdown": dict(self.rejection_breakdown),
            "enumerated_by_hypothesis": dict(self.enumerated_by_hypothesis),
        }


@dataclass(frozen=True, slots=True)
class FunnelExport:
    """The full per-grammar-version funnel, minus the write-time timestamp."""

    schema_version: str
    per_grammar_version: dict[str, PerGrammarVersionFunnel]
    # Coverage honesty (no silent truncation): how many batches existed vs how
    # many carried the D096 funnel counts and were therefore included.
    coverage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Clock-free payload; `forge.funnel.export` injects `exported_at`."""
        return {
            "schema_version": self.schema_version,
            "coverage": dict(self.coverage),
            "per_grammar_version": {
                version: funnel.to_dict()
                for version, funnel in sorted(self.per_grammar_version.items())
            },
        }


__all__ = ["SCHEMA_VERSION", "FunnelExport", "PerGrammarVersionFunnel"]
