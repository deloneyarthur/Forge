# Forge — new-box transfer runbook

Migrating Forge to a new machine. Profile chosen for this transfer:

- **Same user + same paths** (`aj`, `/home/aj/proj/Forge`) → no unit edits.
- **Bring `forge.db`** → preserve the feedback/learning state.
- **Flash-drive copy of the working tree** → preserve the uncommitted D103/v9 grammar (last commit is v8).
- **Forge bundle carries `crucible_contracts`** → it has no git remote and cannot be cloned.

The two scripts live beside this file: `stage_transfer.sh` (old box) and `setup_new_box.sh` (new box).

---

## The three traps this transfer avoids

1. **`crucible_contracts` has no git remote.** Forge installs it as an editable dep via the relative path `../crucible_contracts` (`pyproject.toml [tool.uv.sources]`). It must physically travel as a sibling of Forge. Forge gates on **v1.14.0** (`forge.core.contracts_check.FORGE_EXPECTED_CONTRACT_VERSION`); a mismatch halts at startup.
2. **Uncommitted v9 work.** The working tree has the D103/v9 grammar (`config/grammar.yaml` + 8 src/test files + untracked `config/grammar_archive/v9.yaml`), marked "DEPLOY PENDING" in `STATUS.md`. A fresh `git clone` would land on **v8** and silently drop it. The working-tree copy preserves it (and `.git`, so you can still commit it later).
3. **`.venv` is not portable.** uv bakes absolute interpreter paths into it. It is excluded from the bundle and rebuilt on the new box with `uv sync`. Same for `.mypy_cache/.ruff_cache/.pytest_cache/.hypothesis`.

---

## Old box — stage the bundle

```bash
# Preview first (copies nothing):
~/proj/Forge/deploy/stage_transfer.sh /media/aj/FLASHDRIVE

# Real copy, with the service stopped so forge.db is a consistent snapshot:
~/proj/Forge/deploy/stage_transfer.sh /media/aj/FLASHDRIVE --stop-service --go
```

Produces on the drive:

```
/media/aj/FLASHDRIVE/
├── proj/
│   ├── Forge/                 # working tree incl. .git + uncommitted v9
│   └── crucible_contracts/    # v1.14.0, editable dep
└── forge_data/
    └── forge.db               # ~1.27 GB accumulated state
```

`--stop-service` leaves Forge **stopped** on the old box. To resume producing there
(e.g. you're not cutting over yet): `systemctl --user start forge.service`.

> Coordinate with the Crucible agent: this bundle is the **single source** of
> `crucible_contracts`. The Crucible transfer should point at the same
> `~/proj/crucible_contracts` rather than carry a second, divergent copy.

---

## New box — bootstrap

Mount the drive and run the script straight off it — one command does everything
(pull bundle into `~/proj` + `~/forge_data` → verify → build → service → smoke test):

```bash
/media/aj/FLASHDRIVE/proj/Forge/deploy/setup_new_box.sh --from-bundle /media/aj/FLASHDRIVE
```

(The script operates on `~/proj`, not on its own location, so running it from the
drive is fine — `--from-bundle` lays the repos and `forge.db` down first.)

`--from-bundle` rsyncs `proj/*` → `~/proj` and `forge_data/forge.db` → `~/forge_data`,
verifies the contracts version gate, installs uv if absent, rebuilds `.venv`
(`uv sync --extra dev` — uv provisions Python 3.12 if the box lacks it), ensures the
data dirs, runs `forge version` + `forge check`, installs and **enables** the systemd
user unit with linger, and runs the invariant smoke test.

It deliberately does **not** start the service (pass `--start` to override) — Crucible
should come up first.

---

## Start order (cross-system)

Forge is a consumer of Crucible's runtime. Bring things up in this order:

1. **Crucible** (its agent): `~/optbt_data` in place, `db_writer` socket live, and the
   registry / gated-runs / promoted-strategies / universe publishers running so
   `~/optbt_data/exports/` is populated.
2. **Forge**: `systemctl --user start forge.service`.

The unit runs with `--require-real-cache`, so if Crucible's writer/feature cache is
not yet up, Forge **skips iterations cleanly** rather than submitting a noise-filtered
batch — it will not crash, it just waits.

Watch: `journalctl --user -u forge.service -f`.

---

## Shared seams with Crucible (for the other agent)

| Path / resource | Owner | Forge's relationship |
|---|---|---|
| `~/proj/crucible_contracts` (v1.14.0) | shared | editable dep of **both**; one copy, same dir |
| `~/optbt_data/inbox/` | Crucible | Forge **writes** candidates here |
| `~/optbt_data/exports/` | Crucible | Forge **reads** registry / gated / promoted / universe |
| `~/optbt_data/db_writer.sock` + feature cache | Crucible | needed live for Forge's `--require-real-cache` iterations |
| `~/forge_data/forge.db` | Forge | Forge's own state — Crucible never touches it |

---

## Post-migration checklist

- [ ] `cd ~/proj/Forge && uv run forge check` → contracts compat + schema OK
- [ ] `uv run forge version` shows Forge + contracts 1.14.0
- [ ] `git -C ~/proj/Forge status` shows the v9 working-tree changes intact
- [ ] `du -h ~/forge_data/forge.db` ≈ matches the old box (state came across)
- [ ] `systemctl --user is-enabled forge.service` → enabled; linger on
- [ ] Crucible up + `~/optbt_data/exports/` populated → start Forge
- [ ] First batch in `journalctl` loads the registry + grammar without `SchemaVersionMismatch`
- [ ] When ready: run the D103/v9 deploy ritual from `STATUS.md` to commit v9
