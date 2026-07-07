# Forge — new-box transfer runbook

Migrating Forge to a new machine. Profile chosen for this transfer:

- **Same user + same paths** (`aj`, `/home/aj/proj/Forge`) → no unit edits.
- **Bring `forge.db`** → preserve the feedback/learning state (months the loop can't reconstruct).
- **Carry the working tree, not a fresh clone** → it preserves `.git` plus any in-flight,
  not-yet-committed operator work, and it carries `crucible_contracts`, which has no git remote
  and cannot be cloned.

The two scripts live beside this file: `stage_transfer.sh` (old box) and `setup_new_box.sh` (new box).

> **`setup_new_box.sh` is current (refreshed D203, eod-check retired D253):** it symlinks **all**
> units in `deploy/systemd/` (`forge.service` + every timer), and its contracts gate derives the
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

> The grammar on the tree is committed (currently `grammar_version: v22`, archived under
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

`--stop-service` leaves Forge **stopped** on the old box. To resume producing there
(e.g. you're not cutting over yet): `systemctl --user start forge.service`.

> Coordinate with the Crucible agent: this bundle is the **single source** of
> `crucible_contracts`. The Crucible transfer should point at the same
> `~/proj/crucible_contracts` rather than carry a second, divergent copy.

---

## New box — bootstrap

Mount the drive and run the script straight off it — it lays the repos and `forge.db` down,
verifies the contracts gate, rebuilds the venv, and installs `forge.service`:

```bash
/media/aj/FLASHDRIVE/proj/Forge/deploy/setup_new_box.sh --from-bundle /media/aj/FLASHDRIVE
```

(The script operates on `~/proj`, not on its own location, so running it from the drive is fine —
`--from-bundle` lays the repos and `forge.db` down first.)

`--from-bundle` rsyncs `proj/*` → `~/proj` and `forge_data/forge.db` → `~/forge_data`, verifies
the contracts version gate, installs uv if absent, rebuilds `.venv` (`uv sync --extra dev` — uv
provisions Python 3.12 if the box lacks it), ensures the data dirs, runs `forge version` +
`forge check`, installs and **enables** the `forge.service` user unit with linger, and runs the
invariant smoke test.

It deliberately does **not** start the service (pass `--start` to override) — Crucible should come
up first.

### Verify the units (the script installs them all)

`setup_new_box.sh` symlinks every unit in `deploy/systemd/` into `~/.config/systemd/user/`
and enables the timers (the daemon itself starts only with `--start`, after Crucible is up).
Confirm the full set:

```bash
systemctl --user list-timers 'forge-*'    # all three timers scheduled
systemctl --user is-enabled forge.service
```

The full unit set after bring-up:

| Unit | Cadence | Purpose | Provenance |
|---|---|---|---|
| `forge.service` | 24/7 daemon | the producer loop (`forge run --loop …`) | — |
| `forge-ranker-eval.timer` | 05:00 daily | train + eval the learned verdict / wf_p25 model; publish to `~/forge_data/models/` | F3 / D193 |
| `forge-backup.timer` | 04:00 daily | DR backup of `forge.db` + `models/` | D195 |
| `forge-healthcheck.timer` | hourly | `forge healthcheck` — detect an alive-but-unproductive daemon (CRITICAL surfaces in `--state=failed`) | D197 |

(`forge-eod-check.timer`, a 21:00 headless-Claude EOD report created 06-10, was RETIRED D253 —
alerting superseded by the hourly healthcheck; its prompt had fossilized on a v17 baseline.)

### Data directories

`setup_new_box.sh` ensures `~/forge_data/{logs,exports,approvals}` and the Crucible-owned
`~/optbt_data/{inbox,exports}`. The timer scripts create the rest of `~/forge_data/` on their
first run — no manual step needed:

- `scripts/daily_ranker_eval.sh` creates `~/forge_data/{models,ranker_eval}` (`mkdir -p`).
- `scripts/backup_forge_db.sh` creates its destination `~/forge_data/backups`
  (override via `FORGE_BACKUP_DEST` for a true off-box target — see DR note below).

All scripts the timers invoke ride the tree and are committed executable; verify before enabling:

```bash
ls -l ~/proj/Forge/scripts/{daily_ranker_eval.sh,backup_forge_db.sh,deploy_preflight.sh}
# all three should be -rwxr-xr-x; chmod +x any that lost the bit in transit
```

(`deploy_preflight.sh` (D199) is the read-only pre-deploy GO/NO-GO gate used by the deploy
ritual, not a timer — but it travels with the tree and should be executable.)

---

## Start order (cross-system)

Forge is a consumer of Crucible's runtime. Bring things up in this order:

1. **Crucible** (its agent): `~/optbt_data` in place, `db_writer` socket live, and the
   registry / gated-runs / promoted-strategies / universe publishers running so
   `~/optbt_data/exports/` is populated.
2. **Forge**: `systemctl --user start forge.service`.

The unit runs with `--require-real-cache`, so if Crucible's writer/feature cache is not yet up,
Forge **skips iterations cleanly** rather than submitting a noise-filtered batch — it will not
crash, it just waits.

Watch: `journalctl --user -u forge.service -f`. On a healthy start the journal prints the contracts
line, `grammar_version: v22`, and the enabled rank/yield axes the unit carries
(`--cohort-yield` / `--regime-gate-yield` D182/D183; `--quality-rank` D193) before the per-iteration
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
- [ ] `systemctl --user is-enabled forge.service` → enabled; linger on
- [ ] `systemctl --user list-timers 'forge-*'` → `forge-ranker-eval`, `forge-backup`,
      `forge-healthcheck` all three scheduled (king arm absent — D190; eod-check retired — D253)
- [ ] `ls ~/proj/Forge/scripts/*.sh` → backup/ranker-eval/preflight scripts present + executable
- [ ] Crucible up + `~/optbt_data/exports/` populated → start Forge
- [ ] First batch in `journalctl` loads the registry + grammar (`grammar_version: v22`) without
      `SchemaVersionMismatch`
- [ ] `uv run forge healthcheck` → green (alive AND productive) once a batch or two have run
