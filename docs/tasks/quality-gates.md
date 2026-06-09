# Task: lint, test, commit

Scope: the gates every change passes before commit, and the commit conventions.

## Commands

```bash
uv run pytest                                  # full suite (~1,400). Deploy gate = service stopped
uv run pytest tests/unit/test_grammar          # scope while iterating
uv run pytest -m "not slow"                    # markers: unit/integration/invariants/slow
uv run ruff check src tests scripts            # strict select-set in pyproject.toml
uv run ruff format path/to/changed_file.py     # ONLY files you touched (see below)
uv run mypy --strict src                       # must be zero violations
```

- **ruff format scope**: the committed tree is not format-clean (historical `--no-verify`
  commits). Tree-wide `ruff format` reformats ~27 unrelated files — format only what you edited.
- Full-suite timing: minutes. Test layout + fixture conventions: `tests/README.md`.

## Pre-commit hooks (`.pre-commit-config.yaml`)

| Hook | Fires on | Notes |
|---|---|---|
| ruff + ruff-format | *.py | auto-fixes |
| mypy --strict (local venv) | src/ | runs `uv run mypy` — needs the editable contracts dep, hence local |
| hygiene (whitespace, yaml, large files) | all | |
| grammar-version-bump | `config/grammar.yaml`, archive | enforces hard rule #10; `entry: python scripts/...` — needs `python` on PATH |
| grammar-doc-sync | grammar.yaml, `docs/GRAMMAR.md` | rule ids ↔ headings pairing |

As of 2026-06-09 hooks run clean end-to-end (a stale `uv.lock` previously broke the mypy hook's
stash/restore). History contains `--no-verify` commits with checks run manually — avoid adding
more; if a sandboxed shell lacks `python` on PATH for the grammar hooks, run them via the venv and
record that in the commit/STATUS rather than skipping.

## Commit conventions

- `type(scope): summary` style, lowercase (`fix(scripts): ...`, `docs(STATUS): ...`).
- Commit small: one module + its tests when feasible.
- Every behavior change ships with its D-entry (`IMPLEMENTATION_DECISIONS.md`), a `STATUS.md`
  update, and updates to any doc it invalidates (CLAUDE.md session discipline) in the same or
  adjacent commit.
- TDD evidence in the message where it matters (suite counts, RED→GREEN).
- Don't push unless the operator expects it; the live service runs from the tree, not origin.

## Verify

`git status` clean (live tree must stay clean — `deploy.md`), suite green, ruff + mypy zero on
changed scope.
