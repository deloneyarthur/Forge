# Forge

Candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

Forge enumerates grammar-valid options strategy configurations, pre-filters them through cheap
statistical checks, and submits survivors to Crucible for full backtest validation. Since the
2026-09-14 cutover it does this once a week with no operator input (`forge campaign`): read the
designated book and Crucible's verdicts, decide whether any cell deserves challengers, submit at
most a few hundred. Most rejections are correct behavior (§1.3); a week that submits nothing is
the design.

## Quick start

```bash
uv venv
uv pip install -e ".[dev]"
forge check    # validates crucible_contracts compat + DB schema
forge --help
uv run pytest
```

In production Forge is two systemd user timers and no daemon (D416): `forge-campaign.timer`
(Sunday 03:00 UTC → `scripts/campaign_run.sh` → `forge campaign`) and `forge-backup.timer`
(Sunday 04:30 UTC). Units in `deploy/systemd/`; the ritual in `docs/tasks/deploy.md`.

## Documentation

| Doc | What |
|---|---|
| `docs/DESIGN.md` | The authoritative spec (source of truth) |
| `CLAUDE.md` | Agent entry point: hard rules, commands, routing to everything else |
| `docs/architecture.md` | As-built component map, data flow, change taxonomy |
| `docs/MANPAGE.md` | Every CLI command, script, config file, DB table, pipeline service |
| `docs/HOW-TO.md` | Operator runbook: the weekly check, recovery, era boundaries |
| `docs/GRAMMAR.md` | Narrative for each grammar rule (sync-enforced with `config/grammar.yaml`) |
| `STATUS.md` | Live project state |
| `docs/proposals/` | Active proposals + the freeze programme (terminal ones: `_archive/PROPOSAL_*.md`) |
| `../PIPELINE.md` | System-of-systems context |
