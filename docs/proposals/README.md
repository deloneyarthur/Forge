# docs/proposals/ — design records still cited by code, and the live plan

What lives here: the design-of-record for a mechanism that still runs (a surviving module or test
cites the file), the signed freeze declaration (`scripts/check_freeze_governance.py` reads its
`SIGNED` marker), the live §5 reopener dossier (`path-c-scope-expansion.md`), the version proposals
pinned by the emission-policy retirement guards (`v33`/`v34`/`v36`/`v39`/`v41`), and the plan of
record (`repo-simplification-2026-09.md`, until its last batch lands).

Keep / archive discriminator (D202/D241, restated 2026-09-15): a proposal stays while a surviving
`src/` or `tests/` file cites it AND the mechanism it describes is live; otherwise it moves to
`_archive/PROPOSAL_<name>.md` with a one-line ARCHIVED banner in the same commit that deletes its
last citing module. Nothing here is a grammar rule: the grammar is frozen at v55 (D390) and a change
needs a preregistration first (`docs/tasks/grammar-change.md`).
