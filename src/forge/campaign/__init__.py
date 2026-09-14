"""Weekly campaign mode — Forge's final state (plan 2026-09 §12, D406/D409).

WHY a package of its own: the daemon loop (`cli/main.py`) is a 24/7 supply
generator; the campaign is a weekly, zero-input challenger run that reads the
designated book and Crucible's verdict ledger, decides on its own whether any
cell is worth generating for, and submits at most a few hundred configs. The
two share the sampler, the prefilter battery, the submitter, and the consumer;
they do not share orchestration, so the campaign lives beside the loop until
the cutover retires the loop (§12.6 Batch 4).

Layout: ``types`` (the contract), ``cells`` (cell keys, book, verdict stats,
protected/dead classification), ``triggers`` (T1-T5 as pure functions),
``gate`` (the structural challenger gate), ``run`` (the orchestration),
``report`` (run records + status).
"""

from __future__ import annotations
