"""Phase 1 invariants — grammar-engine discipline checks.

Each invariant maps to a CLAUDE.md hard rule or a §13 production-quality
requirement. New rules add tests here; nothing is removed without
operator approval.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

from crucible_contracts import IndicatorMetadata
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "forge"


_FORBIDDEN_FAMILY = "equity"


def test_no_equity_family_in_contracts_indicator_literal() -> None:
    """CLAUDE.md hard rule #7: ``equity`` must never be a valid indicator
    family. Contracts is the upstream guard — the Literal there controls
    every consumer."""
    family_field = IndicatorMetadata.model_fields["family"]
    annot = family_field.annotation
    assert typing.get_origin(annot) is typing.Literal
    families = set(typing.get_args(annot))
    assert _FORBIDDEN_FAMILY not in families, (
        f"`equity` family must not appear in IndicatorMetadata.family "
        f"Literal; found {sorted(families)}"
    )


def test_no_equity_family_constructible() -> None:
    """Pydantic must reject any IndicatorMetadata constructed with
    family='equity'. This is what catches a malformed registry payload."""
    try:
        IndicatorMetadata(
            id="bogus",
            version=1,
            family=_FORBIDDEN_FAMILY,  # type: ignore[arg-type]
            lookback=0,
            params_schema={},
        )
    except ValidationError:
        return
    msg = (
        "IndicatorMetadata accepted family='equity' — hard rule #7 violated. "
        "Check crucible_contracts.models.py for the Literal."
    )
    raise AssertionError(msg)


def test_grammar_source_never_references_equity_family() -> None:
    """Defense in depth: no Forge source file mentions 'equity' as a
    family value. (Surface mentions of equity-pairing semantics elsewhere
    — e.g., EquityHedgeSpec — are allowed; family-value usage is not.)"""
    pattern = re.compile(r'family\s*=\s*"equity"|family:\s*equity', re.IGNORECASE)
    offenders: list[str] = []
    for py in SRC_ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(py.relative_to(REPO_ROOT)))
    assert not offenders, f"`family=equity` reference found in: {offenders}. Hard rule #7."


def test_grammar_yaml_never_references_equity_family() -> None:
    """The grammar config + archive entries must not mention an equity
    family — would either be a no-op (the literal rejects it) or signal
    a smuggled rule."""
    pattern = re.compile(r'family\s*[:=]\s*["\']?equity', re.IGNORECASE)
    for path in [
        REPO_ROOT / "config" / "grammar.yaml",
        *((REPO_ROOT / "config" / "grammar_archive").glob("*.yaml")),
    ]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), f"`family=equity` in {path}"


def test_custom_predicate_registry_does_not_reference_equity() -> None:
    """forge.grammar.custom_predicates module-level constants must not
    contain 'equity' as a value (in any table)."""
    custom_predicates_path = SRC_ROOT / "grammar" / "custom_predicates.py"
    text = custom_predicates_path.read_text(encoding="utf-8")
    assert "equity" not in text.lower().replace("equityhedgespec", ""), (
        "forge.grammar.custom_predicates references 'equity'; investigate."
    )
