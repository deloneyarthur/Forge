"""forge.feedback — Crucible result consumer (reconcile), preregistrations, priors, era cuts.

The analyzer / proposer / learned-weight machinery of the daemon era left in Batch 5 G3
(D420); what remains is what the weekly campaign reads and writes.
"""

from __future__ import annotations

from forge.feedback.types import BatchFeedback, CandidateOutcome

__all__ = ["BatchFeedback", "CandidateOutcome"]
