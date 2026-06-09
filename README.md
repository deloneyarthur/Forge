# Forge

Candidate strategy generator for the Forge → Crucible → QuantIQ pipeline.

Forge enumerates grammar-valid options strategy configurations, pre-filters them through cheap
statistical checks, and submits survivors to Crucible for full backtest validation. It learns
from Crucible's promotion decisions and refines its hypothesis grammar over time. Promotion rates
start near zero and are expected to rise slowly (§1.3); most rejections are correct behavior.

## Quick start

```bash
uv venv
uv pip install -e ".[dev]"
forge check    # validates crucible_contracts compat + DB schema
forge --help
pytest
```

In production Forge runs as a systemd user service:
`forge run --loop --consume-feedback --require-real-cache` (see `deploy/systemd/forge.service`).

## Documentation

| Doc | What |
|---|---|
| `docs/DESIGN.md` | The authoritative spec (source of truth) |
| `CLAUDE.md` | Agent entry point: hard rules, commands, routing to everything else |
| `docs/architecture.md` | As-built component map, data flow, change taxonomy |
| `docs/MANPAGE.md` | Every CLI command, script, config file, DB table, pipeline service |
| `docs/HOW-TO.md` | Operator runbook: start/stop, health checks, recovery |
| `docs/GRAMMAR.md` | Narrative for each grammar rule (sync-enforced with `config/grammar.yaml`) |
| `STATUS.md` | Live project state |
| `../PIPELINE.md` | System-of-systems context |
