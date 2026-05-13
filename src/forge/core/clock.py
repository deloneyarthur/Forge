"""The blessed clock for Forge.

Hard rule #8: no `datetime.now()` / `datetime.utcnow()` outside this module.
All callers go through `utc_now()`. Lint / invariant tests enforce.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a tz-aware UTC datetime."""
    return datetime.now(UTC)
