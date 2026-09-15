# Task: versionless feedback / learned-weight change — RETIRED

The learned draw weights (`feedback/rejection_weights.py`, the D094 → D108 lineage) and the grammar
proposal machinery left the tree in Batch 5 G3 (D420): they steered a 24/7 daemon that no longer
exists. Forge's final state is the weekly `forge campaign` run (plan 2026-09 §12), whose selection
policy lives in `src/forge/campaign/` (`triggers.py`, `gate.py`, `cells.py`) and is edited like any
other code — TDD, full suite, commit; the next Sunday run deploys it (`docs/tasks/deploy.md`).
Grammar changes are a different thing entirely: preregistration first (`docs/tasks/grammar-change.md`).
