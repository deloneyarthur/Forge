# config/ — runtime configuration

Scope: ownership warnings only. File-by-file semantics: `docs/MANPAGE.md` (CONFIG FILES).

- `grammar.yaml` — operator-owned. ANY byte change (comments included) requires a
  `grammar_version` bump + byte-identical archive copy under `grammar_archive/v{N}.yaml`
  (pre-commit hook + loader both enforce). Procedure: `docs/tasks/grammar-change.md`.
  Grammar FROZEN at v55 (D390): a content change needs an open preregistration first.
- `grammar_archive/` — frozen history; never edit existing files.
- `auto_tightened_thresholds.yaml` — retired-empty (D206, permanent per D298; the proposer
  script lives in git history); the loader's fingerprint still reads it — don't hand-edit.
- `prefilter.yaml` — operator-owned calibration; nothing writes it (the auto-tune trigger and its
  `auto_tune:` key left with the daemon, D422). Read at every weekly run.
- `forge.yaml` — three keys: `db_path`, `crucible.inbox_path`, optional `campaign:` overrides
  (D422). CLI flags override YAML; `--no-config` = defaults + explicit paths. A retired key fails
  loud (`extra="forbid"`). (`ranker.yaml` was deleted 2026-09-15, D419.)
