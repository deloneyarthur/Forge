# fable-audit — Forge audits, 2026-07-01

Four complementary full-repo audits, performed the same day by concurrent Claude Fable 5
sessions, written as durable records so a later agent (e.g. Opus) can execute the workplans
without re-deriving the findings. All were taken against the same snapshot: HEAD `ceeefa4`
plus the uncommitted D216 working-tree changes.

| Folder | Scope | Start at |
|---|---|---|
| `codebase-quality/` | Code quality & structure: src architecture, test suite, tooling/scripts/packaging/ops, repo & docs hygiene. Workplan P0–P3 (items 1–18). | `codebase-quality/README.md` |
| `learned-systems/` | The learned-model systems (F3 ranker, wf_p25 quality lane, gate-then-tail rewire, hypothesis-weight estimand): implementation AND measured live performance, plus promotion/MLOps discipline. Workplan P0–P5. | `learned-systems/README.md` |
| `pipeline-performance/` | Runtime performance of the production loop: where the daemon's ~12.6 CPU-h/day actually goes (submit/reconcile fsync anti-pattern, prefetch re-fetch, export re-parsing), measured baseline + benchmarks, scaling time-bombs. Workplan P0-1–P4-8. | `pipeline-performance/README.md` |
| `strategy-methodology/` | The quant domain content: grammar/§3.5 strategy space, indicator reachability & threshold calibration, prefilter/submission statistical methodology, research-hygiene machinery (alpha budget, prereg, feedback rituals). Includes a measured per-family battery kill table. Workplan P0–P4. | `strategy-methodology/README.md` |

Each subfolder README carries the rules of engagement (CLAUDE.md hard rules, operator gates,
production-tree cautions) — read them before executing anything.

**Overlap note:** a few items appear in more than one workplan (committing the dirty D216
tree, the missing gate-then-tail D-entry, `rejection_weights.py` dead code, `cli/main.py`
loader structure). pipeline-performance overlaps: its P4-8 (`_iter_hypothesis_outcomes`
full-scan) is the same code as codebase-quality's `rejection_weights.py` dead-code item,
and its P1-1 (gated-export parse-once) touches the same `cli/main.py` loader structure.
strategy-methodology overlaps: its P0-4/P3-1 prereg-commit item folds into
codebase-quality item 1; its PRE-H2(d) multiple-testing question is learned-systems
P3.4/B8; its P1-1 permutation_test semantics fix must land BEFORE pipeline-performance
P2-3 memoizes that filter; its D216-activation items (P0-1..P0-5) supersede the framing
of learned-systems P2.1 (activate only with gate-class telemetry + battery context).
If executing multiple plans, land each shared item once and tick it in every plan.
