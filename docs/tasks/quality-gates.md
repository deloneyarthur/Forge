# Task: lint, test, commit

Scope: the gates every change passes before commit, and the commit conventions.

## Commands

```bash
uv run pytest                                  # full suite (count grows — latest in STATUS.md/D-entries). Deploy gate = service stopped
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
| grammar-version-bump | `config/grammar.yaml`, archive | enforces hard rule #10; `entry: uv run python scripts/...` (D351: bare `python` is absent on this box — the hook could never execute until 2026-08-02) |
| grammar-doc-sync | grammar.yaml, `docs/GRAMMAR.md` | rule ids ↔ headings pairing |

History contains `--no-verify` commits with checks run manually — avoid adding more. If a hook
fails to *execute* (as opposed to failing its check), treat that as a broken guard and fix the
hook (the D351 class: a guard that cannot run reads as enforcement while enforcing nothing);
record any manual-verification fallback in the commit/STATUS rather than skipping silently.

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
