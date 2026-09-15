# Forge — new-box transfer runbook

Migrating Forge to a new machine. Profile chosen for this transfer:

- **Same user + same paths** (`aj`, `/home/aj/proj/Forge`) → no unit edits.
- **Bring `forge.db`** → preserve the feedback/learning state (months the loop can't reconstruct).
- **Carry the working tree, not a fresh clone** → it preserves `.git` plus any in-flight,
  not-yet-committed operator work, and it carries `crucible_contracts`, which has no git remote
  and cannot be cloned.

The two scripts live beside this file: `stage_transfer.sh` (old box) and `setup_new_box.sh` (new box).

> **`setup_new_box.sh` is current (refreshed D203, eod-check retired D253):** it symlinks **all**
> units in `deploy/systemd/` (`forge-campaign` + `forge-backup`), and its contracts gate derives the
> expected version from `FORGE_EXPECTED_CONTRACT_VERSION` in `contracts_check.py` (no hardcoded
> literal to re-stale). No manual unit-install follow-up is needed — the "verify the units" step
> below is just a check.

---

## The traps this transfer avoids

1. **`crucible_contracts` has no git remote.** Forge installs it as an editable dep via the
   relative path `../crucible_contracts` (`pyproject.toml [tool.uv.sources]`). It must physically
   travel as a sibling of Forge. Forge gates on the version pinned in
   `forge.core.contracts_check.FORGE_EXPECTED_CONTRACT_VERSION` (read the constant in
   `src/forge/core/contracts_check.py` — don't trust any literal written here); a
   mismatch hard-halts at startup (§13.5).
2. **`.venv` is not portable.** uv bakes absolute interpreter paths into it. It is excluded from
   the bundle and rebuilt on the new box with `uv sync`. Same for
   `.mypy_cache/.ruff_cache/.pytest_cache/.hypothesis`.
3. **`forge.db` is held open + gitignored.** `~/forge_data/forge.db` is a multi-GB DuckDB file
   (single copy of every submission, verdict, grammar version/proposal, promoted pattern, shadow
   score). It is under no git, and the running service holds an intermittent RW lock — stop the
   service before copying so the snapshot is consistent (DuckDB + WAL).

> The grammar on the tree is committed (whatever `grammar_version:` reads in `config/grammar.yaml`, archived under
> `config/grammar_archive/`). Carrying `.git` is for any *in-flight* operator work, not because a
> clone would drop the grammar — a clean tree is the production tree (D104).

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
│   ├── Forge/                 # working tree incl. .git (+ any in-flight work)
│   └── crucible_contracts/    # editable dep, version must match Forge's pin
└── forge_data/
    └── forge.db               # accumulated state
```

The bundle carries **only `forge.db`** out of `~/forge_data/`. Everything else there is either
rebuilt or regenerated on the new box:

- `models/`, `ranker_eval/`, `backups/`, `logs/`, `exports/` — recreated by the daemon and its
  timers (see below). The daily ranker-eval timer republishes a fresh learned-verdict + wf_p25
  model within a day, so `models/` need not travel.
- `king_submissions.db` — **do NOT carry it.** The king/oracle arm was retired (D190); a new box
  must not stand up any king DB, oracle, or king timer. If a naive copy drags this file along,
  delete it.

`--stop-service` disables the two Forge timers on the old box. To resume there (e.g. you're not
cutting over yet): `systemctl --user enable --now forge-campaign.timer forge-backup.timer`.

> Coordinate with the Crucible agent: this bundle is the **single source** of
> `crucible_contracts`. The Crucible transfer should point at the same
> `~/proj/crucible_contracts` rather than carry a second, divergent copy.

---

## New box — bootstrap

Mount the drive and run the script straight off it — it lays the repos and `forge.db` down,
verifies the contracts gate, rebuilds the venv, and installs the two Forge timers:

```bash
/media/aj/FLASHDRIVE/proj/Forge/deploy/setup_new_box.sh --from-bundle /media/aj/FLASHDRIVE
```

(The script operates on `~/proj`, not on its own location, so running it from the drive is fine —
`--from-bundle` lays the repos and `forge.db` down first.)

`--from-bundle` rsyncs `proj/*` → `~/proj` and `forge_data/forge.db` → `~/forge_data`, verifies
the contracts version gate, installs uv if absent, rebuilds `.venv` (`uv sync --extra dev` — uv
provisions Python 3.12 if the box lacks it), ensures the data dirs, runs `forge version` +
`forge check`, installs and **enables** the `forge-campaign` + `forge-backup` timers with linger, and
runs the invariant smoke test. There is no daemon unit since the 2026-09-14 cutover (D416).

It deliberately does **not** start the service (pass `--start` to override) — Crucible should come
up first.

### Verify the units (the script installs them all)

`setup_new_box.sh` symlinks every unit in `deploy/systemd/` into `~/.config/systemd/user/`
and enables the timers (the daemon itself starts only with `--start`, after Crucible is up).
Confirm the full set:

```bash
systemctl --user list-timers 'forge-*'    # forge-campaign + forge-backup scheduled
```

The full unit set after bring-up:

| Unit | Cadence | Purpose | Provenance |
|---|---|---|---|
| `forge-backup.timer` | Sunday 04:30 UTC | DR backup of `forge.db` + `models/`, after the campaign run | D195 / G0 |
| `forge-healthcheck.timer` | hourly | `forge healthcheck` — detect an alive-but-unproductive daemon (CRITICAL surfaces in `--state=failed`) | D197 |
| `forge-campaign.timer` | Sunday 03:00 UTC | `scripts/campaign_run.sh` — the weekly zero-input challenger run; `FORGE_CAMPAIGN_MODE` in the unit = `dry-run` (snapshot, nothing submitted) until the Route C cutover flips it to `live` | D410/D411 |

(`forge-eod-check.timer`, a 21:00 headless-Claude EOD report created 06-10, was RETIRED D253 —
alerting superseded by the hourly healthcheck; its prompt had fossilized on a v17 baseline.)

### Data directories

`setup_new_box.sh` ensures `~/forge_data/{logs,exports,approvals}` and the Crucible-owned
`~/optbt_data/{inbox,exports}`. The timer scripts create the rest of `~/forge_data/` on their
first run — no manual step needed:

- `forge campaign` (in-run training, Batch 5 G0) creates `~/forge_data/{models,campaigns}`.
- `scripts/backup_forge_db.sh` creates its destination `~/forge_data/backups`
  (override via `FORGE_BACKUP_DEST` for a true off-box target — see DR note below).

All scripts the timers invoke ride the tree and are committed executable; verify before enabling:

```bash
ls -l ~/proj/Forge/scripts/{backup_forge_db.sh,deploy_preflight.sh,live_db_snapshot.sh,campaign_run.sh}
# all four should be -rwxr-xr-x; chmod +x any that lost the bit in transit
```

(`deploy_preflight.sh` (D199) is the read-only pre-deploy GO/NO-GO gate used by the deploy
ritual, not a timer — but it travels with the tree and should be executable.)

---

## Start order (cross-system)

Forge is a consumer of Crucible's runtime. Bring things up in this order:

1. **Crucible** (its agent): `~/optbt_data` in place, `db_writer` socket live, and the
   registry / gated-runs / promoted-strategies / universe publishers running so
   `~/optbt_data/exports/` is populated.
2. **Forge**: nothing to start — `forge-campaign.timer` fires Sunday 03:00 UTC; run
   `forge campaign --dry-run` by hand to see this week's plan without submitting.

The run builds its feature cache with `require_real=True`, so if Crucible's writer is not up the
run ends as an ERROR record (the unit goes FAILED = the page) and submits nothing — it never
filters against the synthetic cache.

Watch: `journalctl --user -u forge-campaign.service -n 40`. A healthy run prints the boot checks, the
contracts line, `grammar_version` matching `config/grammar.yaml`, the trained model ids, the five
trigger lines and the closing `campaign <run_id>: …` line
prefetch.

---

## Shared seams with Crucible (for the other agent)

| Path / resource | Owner | Forge's relationship |
|---|---|---|
| `~/proj/crucible_contracts` (version == Forge's pin) | shared | editable dep of **both**; one copy, same dir |
| `~/optbt_data/inbox/` | Crucible | Forge **writes** candidates here |
| `~/optbt_data/exports/` | Crucible | Forge **reads** registry / gated / promoted / universe |
| `~/optbt_data/db_writer.sock` + feature cache | Crucible | needed live for Forge's `--require-real-cache` iterations |
| `~/forge_data/forge.db` | Forge | Forge's own state — Crucible never touches it |

---

## Disaster-recovery note

The `forge-backup` timer (D195) writes verified, retained copies of `forge.db` + `models/` to
`FORGE_BACKUP_DEST` (default `~/forge_data/backups`). On a single-NVMe box that default is
**same-disk** — it protects against deletion / bad migration / fs corruption but **not** a physical
disk failure. For true off-box DR, point `FORGE_BACKUP_DEST` at a mounted external/remote target;
nothing else changes. **Operator decision pending:** an off-box destination is not yet configured —
set one on the new box if the host has only one disk.

---

## Post-migration checklist

- [ ] `cd ~/proj/Forge && uv run forge check` → contracts compat (§13.5) + schema OK
- [ ] `uv run forge version` shows Forge + the contracts version matching the pin
      (`FORGE_EXPECTED_CONTRACT_VERSION` in `src/forge/core/contracts_check.py`)
- [ ] `du -h ~/forge_data/forge.db` ≈ matches the old box (state came across)
- [ ] `loginctl show-user $USER -p Linger` → yes (timers run headless)
- [ ] `systemctl --user list-timers 'forge-*'` → `forge-campaign` (Sun 03:00 UTC) and `forge-backup`
      (Sun 04:30 UTC), both scheduled (ranker-eval / prereg-watch / healthcheck retired with the daemon, Batch 5)
- [ ] `ls ~/proj/Forge/scripts/*.sh` → backup / campaign_run / preflight / snapshot scripts present + executable
- [ ] Crucible up + `~/optbt_data/exports/` populated → start Forge
- [ ] First batch in `journalctl` loads the registry + grammar (`grammar_version` matching `config/grammar.yaml`) without
      `SchemaVersionMismatch`
- [ ] `uv run forge healthcheck` → green (alive AND productive) once a batch or two have run
