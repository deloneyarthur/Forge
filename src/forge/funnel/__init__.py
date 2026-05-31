"""Pre-filter funnel export (D096 — FUNNEL_INSTRUMENTATION_FORGE.md Part B).

Exposes Forge's two upstream pipeline-funnel stages (`enumerated`,
`survived pre-filters`) to Crucible's combined funnel, per grammar version,
plus the `config_hash -> grammar_version` join-map that is the interim source
for Crucible's funnel Stage 0 (Part A working path).
"""

from __future__ import annotations

from forge.funnel.aggregate import build_funnel_export, build_version_map
from forge.funnel.export import write_funnel_export
from forge.funnel.types import SCHEMA_VERSION, FunnelExport, PerGrammarVersionFunnel

__all__ = [
    "SCHEMA_VERSION",
    "FunnelExport",
    "PerGrammarVersionFunnel",
    "build_funnel_export",
    "build_version_map",
    "write_funnel_export",
]
