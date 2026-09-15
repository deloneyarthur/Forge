# Task: deploy to the live tree (the D104 ritual, weekly cadence)

Scope: getting any code/grammar change into production. Since the 2026-09-14 cutover (D416)
there is no daemon: `forge-campaign.timer` runs `forge campaign` from this working tree every
Sunday 03:00 UTC via editable install, and a reboot re-arms the timer onto whatever the tree
contains — committed or not. So the tree IS the deploy, and the ritual is about what you leave in it.

## Standing rules

- **Grammar bumps build in a worktree** (`git worktree add ../Forge-build <branch>`); other work
  stays in this tree with short dirty windows. Never leave the tree dirty at a stopping point.
- The grammar is FROZEN at v55 (D390): a `grammar.yaml` content change needs an open
  preregistration first (pre-commit `freeze-governance`), then the bump + archive + D-entry.
- Versionless changes (weights, campaign knobs in `forge.yaml` `campaign:`) follow the same gate —
  the full suite is the point.
- The unit file `deploy/systemd/forge-campaign.service` is symlinked live: an edit needs
  `systemctl --user daemon-reload` to take effect; its `FORGE_CAMPAIGN_MODE` line is the one
  operator decision it carries (`live` since D416).

## Steps

```bash
scripts/deploy_preflight.sh                  # GATE: deploy surface clean + FULL suite (covers the contracts pin, D176)
# commit on main in the LIVE tree
uv run forge campaign --dry-run --skip-train --forge-db "$(scripts/live_db_snapshot.sh --max-age-min 720)"   # verify: same plan class, boot 8/8 ok
```

The next Sunday run is the deploy. To deploy sooner, `systemctl --user start forge-campaign.service`
(live mode — it submits if a trigger fires).

## Verify (the dry-run block)

Expect: every `boot <check> ok` line, `grammar_version=v55`, the contracts version, the trained
model ids, five `trigger` lines, and a closing `campaign <run_id>: …` line; **no** traceback /
`SchemaVersionMismatch` / `GrammarVersionError`. A contracts bump leaves the suite red until the
pin in `core/contracts_check.py` is adopted — the preflight NO-GOs until you do, which is the point.

## After

- Update `STATUS.md` (≤ ~800 chars) with the commit + verification evidence.
- Grammar-versioned change → relay the version string + the first live run's timestamp to Crucible
  (`crucible-handoff.md`) so they can run `crucible funnel --compare`.
- Push when the operator expects it; the timer runs from the working tree, not origin.
