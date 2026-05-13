"""The blessed RNG seeding hierarchy for Forge.

Hard rule #8: no naked `random.seed()` / `np.random.default_rng()` outside this
module. Callers obtain a seeded RNG by name from a single root seed; identical
roots and identical names produce identical streams across processes and
machines. Enumeration (§4.4) and submission ordering (§13.1) rely on this.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeedHierarchy:
    """Derives reproducible sub-seeds for named subsystems from a single root."""

    root: int

    def derive(self, name: str) -> int:
        """Return a deterministic 32-bit seed derived from `(root, name)`."""
        h = hashlib.blake2b(f"{self.root}:{name}".encode(), digest_size=4).digest()
        return int.from_bytes(h, byteorder="big", signed=False)

    def rng(self, name: str) -> random.Random:
        """Return a seeded `random.Random` instance for the named subsystem."""
        return random.Random(self.derive(name))
