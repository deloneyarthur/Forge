"""Pydantic schemas for the hypothesis-grammar engine (Phase 1).

Mirrors DESIGN.md §3.3 (rule shape) and §3.4 (predicate types). YAML parses
straight into a `Grammar` via Pydantic's discriminated-union machinery; each
predicate type has its own subclass so `mypy --strict` can narrow on the
discriminator field.

The `PredicateResult` value type is the contract between the rule engine and
its predicate-impl functions. Predicate impls live in `predicates.py` (built-in
types) and `custom_predicates.py` (escape-hatch registry); both return the
same `PredicateResult` shape.

Architecture rationale: see D017.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GrammarError(Exception):
    """Base for all grammar-engine errors."""


class GrammarLoadError(GrammarError):
    """Raised when `grammar.yaml` fails schema validation or references an
    unknown custom-predicate function name."""


class GrammarVersionError(GrammarError):
    """Raised when `grammar.yaml` content has changed without a corresponding
    `grammar_version` bump and prior-version archive entry. Enforces hard
    rule #10."""


# ---------------------------------------------------------------------------
# Predicate-evaluation result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PredicateResult:
    """Outcome of evaluating one predicate against one config.

    `detail` is the human-readable explanation when `passed` is False; it is
    typically prepended with the rule id by the validator. When `passed` is
    True, `detail` is conventionally the empty string.
    """

    passed: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# Predicate variants — discriminated union via `type` field
# ---------------------------------------------------------------------------


class _PredicateBase(BaseModel):
    """Shared config for every predicate variant. Frozen + extra=forbid so a
    typo in `grammar.yaml` is a load-time failure, not a silent no-op."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CardinalityPredicate(_PredicateBase):
    """Count matches at `field`; assert `count` or [min,max] holds.

    `field` accepts both §3.4 sugar (`signals.role.directional`) and the
    JSONPath primitive (`signals[?(@.role=="directional")]`) per D009.
    Exactly one of `count`, or at least one of `min`/`max`, must be set.
    """

    type: Literal["cardinality"]
    field: str = Field(min_length=1)
    count: int | None = Field(default=None, ge=0)
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _exactly_one_constraint(self) -> CardinalityPredicate:
        has_count = self.count is not None
        has_range = self.min is not None or self.max is not None
        if has_count and has_range:
            msg = "cardinality predicate cannot set both `count` and `min`/`max`"
            raise ValueError(msg)
        if not has_count and not has_range:
            msg = "cardinality predicate must set `count` or at least one of `min`/`max`"
            raise ValueError(msg)
        if self.min is not None and self.max is not None and self.min > self.max:
            msg = f"cardinality predicate: min ({self.min}) > max ({self.max})"
            raise ValueError(msg)
        return self


class NumericalRangePredicate(_PredicateBase):
    """Resolve `field` to a number; assert `min ≤ value ≤ max`. At least one
    of `min`/`max` must be set."""

    type: Literal["numerical_range"]
    field: str = Field(min_length=1)
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _at_least_one_bound(self) -> NumericalRangePredicate:
        if self.min is None and self.max is None:
            msg = "numerical_range predicate must set at least one of `min`/`max`"
            raise ValueError(msg)
        if self.min is not None and self.max is not None and self.min > self.max:
            msg = f"numerical_range predicate: min ({self.min}) > max ({self.max})"
            raise ValueError(msg)
        return self


class CustomPythonPredicate(_PredicateBase):
    """Escape hatch: `function` is a key into `forge.grammar.custom_predicates.REGISTRY`.

    Unknown names raise `GrammarLoadError` at load time so YAML typos surface
    before validation runs.
    """

    type: Literal["custom_python"]
    function: str = Field(min_length=1)


# `requires` / `forbids` / `compatibility` predicate types were removed in Batch 5 G4 (D421):
# no rule in v55 or in any of the 55 archived grammars ever used them, and under the signed
# freeze the loader refusing an unknown type is a feature, not a gap.
Predicate = Annotated[
    CardinalityPredicate | NumericalRangePredicate | CustomPythonPredicate,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Rule + Grammar — the YAML-facing top-level shapes
# ---------------------------------------------------------------------------


class Rule(BaseModel):
    """One §3.3 rule. `predicate` is the discriminated-union variant that
    expresses the rule's logic; `rationale_ref` points at the corresponding
    section in `docs/GRAMMAR.md`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    category: Literal[
        "structural",
        "composition",
        "parameter",
        "exit",
        "regime",
        "risk",
    ]
    version: int = Field(ge=1)
    active: bool = True
    rationale_ref: str = Field(min_length=1)
    predicate: Predicate
    cost_estimate: Literal["low", "medium", "high"]
    evidence_to_relax: tuple[str, ...] = ()


class Grammar(BaseModel):
    """A loaded `grammar.yaml`. `grammar_version` is the SemVer-ish string
    that the archive enforcement key off; `rules` is the ordered tuple of v1
    rules. Ids must be unique."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grammar_version: str = Field(min_length=1)
    generated_at: datetime | None = None
    rules: tuple[Rule, ...]

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> Grammar:
        seen: set[str] = set()
        duplicates: list[str] = []
        for rule in self.rules:
            if rule.id in seen:
                duplicates.append(rule.id)
            seen.add(rule.id)
        if duplicates:
            msg = f"Grammar contains duplicate rule ids: {sorted(set(duplicates))}"
            raise ValueError(msg)
        return self


__all__ = [
    "CardinalityPredicate",
    "CustomPythonPredicate",
    "Grammar",
    "GrammarError",
    "GrammarLoadError",
    "GrammarVersionError",
    "NumericalRangePredicate",
    "Predicate",
    "PredicateResult",
    "Rule",
]
