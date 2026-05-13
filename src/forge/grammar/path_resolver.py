"""Resolve dotted field paths into `StrategyConfig` values.

Supports two equivalent syntaxes per D009:

- §3.4 sugar: ``signals.role.directional`` — filter shorthand. A three-token
  path of the form ``<list_attr>.<attr>.<value>`` matches a list where each
  item's ``<attr>`` equals the literal string ``<value>``.
- JSONPath primitive: ``signals[?(@.role=="directional")]`` — explicit
  filter. Same semantics; preferred in tests and code-generated paths.

Plus plain dotted attribute / index access:

- ``hypothesis``                            → [scalar]
- ``sizer.per_trade_risk_pct``              → [float]
- ``signals``                               → [tuple-of-SignalSpec]
- ``signals[0]``                            → [SignalSpec]
- ``signals[0].indicators``                 → [tuple-of-str]
- ``signals.id``                            → [str, ...]  (projection)

The resolver always returns a ``list`` — callers that expect a single value
must check ``len(result) == 1`` themselves. This is intentional: predicates
like ``cardinality`` care about the count, not the items.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

_BRACKET_RE = re.compile(r"^([A-Za-z_]\w*)(\[.+\])?$")
_INDEX_RE = re.compile(r"^\[(-?\d+)\]$")
_FILTER_RE = re.compile(r'^\[\?\(@\.([A-Za-z_]\w*)\s*==\s*"([^"]*)"\)\]$')


def resolve(root: Any, path: str) -> list[Any]:
    """Resolve ``path`` against ``root``; return the matched values as a list.

    ``root`` may be a Pydantic ``BaseModel``, a dict, a list/tuple, or any
    object exposing the requested attributes. Missing attributes raise
    ``AttributeError`` so a typo in ``grammar.yaml`` becomes a load-time
    failure rather than a silent zero-match.
    """
    if not path:
        msg = "path must be non-empty"
        raise ValueError(msg)

    sugar = _try_sugar_filter(root, path)
    if sugar is not None:
        return sugar

    cursor: list[Any] = [root]
    for token in _tokenize(path):
        cursor = _step(cursor, token)
    return cursor


# ---------------------------------------------------------------------------
# §3.4 sugar form
# ---------------------------------------------------------------------------


def _try_sugar_filter(root: Any, path: str) -> list[Any] | None:
    """If `path` matches `<list_attr>.<attr>.<value>` and `<list_attr>` is a
    list/tuple on `root`, return the filtered items. Else `None` (fall
    through to the standard walker)."""
    if "[" in path or "]" in path:
        return None
    parts = path.split(".")
    if len(parts) != 3:
        return None

    list_attr, item_attr, literal = parts
    if not (_is_ident(list_attr) and _is_ident(item_attr)):
        return None

    try:
        base = _getfield(root, list_attr)
    except (AttributeError, KeyError):
        return None
    if not isinstance(base, list | tuple):
        return None

    matches: list[Any] = []
    for item in base:
        try:
            attr_val = _getfield(item, item_attr)
        except (AttributeError, KeyError):
            continue
        if str(attr_val) == literal:
            matches.append(item)
    return matches


def _is_ident(s: str) -> bool:
    return s.isidentifier()


# ---------------------------------------------------------------------------
# Standard walker
# ---------------------------------------------------------------------------


def _tokenize(path: str) -> list[str]:
    """Split on `.` outside brackets. Each token is `name`, `name[idx]`, or
    `name[?(...)]`, where `name` may itself be empty for trailing brackets."""
    tokens: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in path:
        if ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth -= 1
            buf.append(ch)
        elif ch == "." and depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    if depth != 0:
        msg = f"unbalanced brackets in path: {path!r}"
        raise ValueError(msg)
    return tokens


def _step(cursor: list[Any], token: str) -> list[Any]:
    match = _BRACKET_RE.match(token)
    if not match:
        msg = f"invalid path token: {token!r}"
        raise ValueError(msg)
    name, bracket = match.group(1), match.group(2)

    next_cursor: list[Any] = []
    for node in cursor:
        value = _getfield(node, name)
        if bracket is None:
            if isinstance(value, list | tuple):
                next_cursor.extend(value)
            else:
                next_cursor.append(value)
        else:
            next_cursor.extend(_apply_bracket(value, bracket))
    return next_cursor


def _apply_bracket(value: Any, bracket: str) -> list[Any]:
    idx_match = _INDEX_RE.match(bracket)
    if idx_match:
        if not isinstance(value, list | tuple):
            msg = f"index {bracket} applied to non-list value ({type(value).__name__})"
            raise TypeError(msg)
        return [value[int(idx_match.group(1))]]

    filter_match = _FILTER_RE.match(bracket)
    if filter_match:
        attr, literal = filter_match.group(1), filter_match.group(2)
        if not isinstance(value, list | tuple):
            msg = f"filter {bracket} applied to non-list value ({type(value).__name__})"
            raise TypeError(msg)
        return [item for item in value if str(_getfield(item, attr)) == literal]

    msg = f"unrecognized bracket expression: {bracket!r}"
    raise ValueError(msg)


def _getfield(obj: Any, name: str) -> Any:
    """Read field `name` off `obj`. Pydantic BaseModels expose fields as
    attributes; dicts expose them as keys; anything else falls back to
    `getattr`."""
    if isinstance(obj, BaseModel):
        return getattr(obj, name)
    if isinstance(obj, dict):
        try:
            return obj[name]
        except KeyError as e:
            msg = f"dict key {name!r} not found"
            raise KeyError(msg) from e
    return getattr(obj, name)


__all__ = ["resolve"]
