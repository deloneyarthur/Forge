"""Stable content hash of a ``RegistrySnapshot`` for the §13.1 determinism triple.

``crucible_contracts.RegistrySnapshot`` has no ``version`` field — only
``crucible_version`` (a string) and ``snapshot_taken_at`` (a datetime) plus
content tuples. §13.1 / CLAUDE.md hard rule #6 wants a single identifier
that changes whenever any registry content changes; we hash the canonical
JSON dump.

The hash is logged alongside (grammar_version, seed) so that any future
reproduction can know exactly which registry produced a given batch.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot


_HASH_LENGTH = 16


def registry_hash(snapshot: RegistrySnapshot) -> str:
    """Stable 16-char sha256 of the canonical JSON dump of ``snapshot``.

    Same snapshot content → same string across runs and platforms. Any
    field change (indicators, signal_types, exit_ids, sizer_modes,
    snapshot_taken_at, crucible_version) yields a different hash.
    """
    payload = json.dumps(
        snapshot.model_dump(mode="json"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:_HASH_LENGTH]
