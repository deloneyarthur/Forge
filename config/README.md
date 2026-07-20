# config/ — runtime configuration

Scope: ownership warnings only. File-by-file semantics: `docs/MANPAGE.md` (CONFIG FILES).

- `grammar.yaml` — operator-owned. ANY byte change (comments included) requires a
  `grammar_version` bump + byte-identical archive copy under `grammar_archive/v{N}.yaml`
  (pre-commit hook + loader both enforce). Procedure: `docs/tasks/grammar-change.md`.
  Never edit while `forge.service` runs (`docs/tasks/deploy.md`).
- `grammar_archive/` — frozen history; never edit existing files.
- `auto_tightened_thresholds.yaml` — retired-empty (D206, permanent per D298; the proposer
  script lives in git history); the loader's fingerprint still reads it — don't hand-edit.
- `prefilter.yaml` — operator + auto-tune (tighten-only writes from the daemon).
- `forge.yaml`, `ranker.yaml` — operator-owned; CLI flags override YAML.
