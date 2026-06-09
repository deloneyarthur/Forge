# Task: deploy to the live service (the D104 ritual)

Scope: getting any code/grammar change into the running `forge.service`. Background: a reboot
auto-starts the service onto whatever this tree contains — committed or not — which once silently
deployed ungated code (D104). Hence:

## Standing rules

- **Build in a worktree** while the service runs: `git worktree add ../Forge-build <branch>`.
  The live tree stays `git status`-clean except mid-deploy.
- Never edit `config/grammar.yaml` in the live tree while the service runs — the loop re-reads it
  hot and stamps submissions with the new version before the code exists
  (`grammar_versions.changed_at` = stamp-flip time, never deploy time).
- Versionless changes follow the same ritual — the uncontended-suite gate is the point.

## Steps

```bash
systemctl --user stop forge.service          # journal exit 143 = normal --loop SIGTERM
uv run pytest                                 # FULL suite, uncontended — this is the deploy gate
# commit / merge to main in the LIVE tree (service runs from here via editable install)
systemctl --user reset-failed forge.service
systemctl --user start forge.service
```

## Verify (within the first minutes)

```bash
journalctl --user -u forge.service -n 50 --no-pager
systemctl --user show forge.service -p NRestarts   # expect 0
```

Expect: contracts version startup line, `grammar_version=v{N}`, `registry_loaded_from_export`
(+ registry_hash), a reconcile line; **no** traceback / `SchemaVersionMismatch` /
`GrammarVersionError`.

`blocked: prev batch ... gated` is the §7.3 limiter — normal. Change-specific journal lines
(e.g. `hypothesis_weights:`, `rank_combiner_share`) appear only on the first UNBLOCKED iteration,
which can be hours out under Crucible backpressure.

## After

- Update `STATUS.md` with the deploy timestamp (UTC) + verification evidence.
- Grammar-versioned change → relay version string + deploy timestamp to Crucible
  (`crucible-handoff.md`).
- Push when the operator expects it; service runs from the working tree, not origin.
