#!/usr/bin/env bash
#
# setup_new_box.sh — bootstrap Forge on a fresh box. Idempotent; safe to re-run.
#
# Assumes the chosen migration profile: same user + same paths
# (user owns ~/proj/Forge and ~/proj/crucible_contracts), forge.db brought
# over; grammar.yaml is committed (v22), so a clone/copy carries it.
#
# What it does, in order:
#   1. (optional) pull the bundle off the flash drive into ~/proj + ~/forge_data
#   2. verify the sibling layout and that crucible_contracts == the version
#      Forge expects (hard gate — a mismatch halts before anything is built)
#   3. install uv if absent
#   4. drop the non-portable .venv + caches that rode along in the copy
#   5. uv sync --extra dev  (rebuilds .venv; uv provisions Python 3.12 if needed)
#   6. ensure ~/forge_data dirs; place forge.db if --copy-db given
#   7. forge version + forge check  (contracts compat + DB schema-ensure)
#   8. install + enable all systemd user units (daemon + timers) (+ linger);
#      start the daemon only if --start
#   9. invariant smoke test (the must-be-green bar)
#
# Flags:
#   --from-bundle DIR  rsync DIR/proj/ -> ~/proj and DIR/forge_data/forge.db -> ~/forge_data
#   --copy-db SRC      copy a forge.db from SRC into ~/forge_data (e.g. the flash drive)
#   --start            `systemctl --user start forge.service` now
#                      (default: enable only — start AFTER Crucible is up)
#   --skip-tests       skip the invariant smoke test
#
# Usage (one-shot from a mounted flash drive):
#   ~/proj/Forge/deploy/setup_new_box.sh --from-bundle /media/aj/FLASHDRIVE --start
#
set -euo pipefail

PROJ="${PROJ:-$HOME/proj}"
FORGE="$PROJ/Forge"
CONTRACTS="$PROJ/crucible_contracts"
FORGE_DATA="${FORGE_DATA:-$HOME/forge_data}"
OPTBT_DATA="${OPTBT_DATA:-$HOME/optbt_data}"

FROM_BUNDLE=""
COPY_DB=""
START=0
SKIP_TESTS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --from-bundle) FROM_BUNDLE="${2:?--from-bundle needs a DIR}"; shift ;;
    --copy-db)     COPY_DB="${2:?--copy-db needs a SRC}"; shift ;;
    --start)       START=1 ;;
    --skip-tests)  SKIP_TESTS=1 ;;
    -h|--help)     grep '^#' "$0" | sed 's/^#\{1,2\} \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

say()  { printf '\n=== %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

EXCLUDES=(--exclude '.venv' --exclude '__pycache__' --exclude '.mypy_cache'
          --exclude '.ruff_cache' --exclude '.pytest_cache' --exclude '.hypothesis'
          --exclude '.claude')

# --- 1. optional: pull the bundle off the flash drive --------------------------
if [ -n "$FROM_BUNDLE" ]; then
  [ -d "$FROM_BUNDLE/proj/Forge" ] || die "bundle has no proj/Forge at $FROM_BUNDLE"
  say "Copying bundle from $FROM_BUNDLE"
  mkdir -p "$PROJ" "$FORGE_DATA"
  rsync -aH --info=stats1 "${EXCLUDES[@]}" "$FROM_BUNDLE/proj/" "$PROJ/"
  if [ -f "$FROM_BUNDLE/forge_data/forge.db" ]; then
    rsync -aH --info=stats1 "$FROM_BUNDLE/forge_data/forge.db" "$FORGE_DATA/forge.db"
  fi
fi

# --- 2. verify layout + contracts version (hard gate) --------------------------
say "Verifying sibling layout + contracts version"
[ -d "$FORGE" ]     || die "missing $FORGE — place the Forge repo there first"
[ -d "$CONTRACTS" ] || die "missing $CONTRACTS — crucible_contracts must travel with Forge (it has no git remote)"

ctr_ver="$(grep -m1 -oP '^version\s*=\s*"\K[^"]+' "$CONTRACTS/pyproject.toml" || true)"
forge_expects="$(grep -oP 'FORGE_EXPECTED_CONTRACT_VERSION:\s*str\s*=\s*"\K[^"]+' \
                 "$FORGE/src/forge/core/contracts_check.py" || true)"
printf 'crucible_contracts on disk: %s\n' "${ctr_ver:-<unknown>}"
printf 'Forge pin (source of truth): %s\n' "${forge_expects:-<unknown>}"
# The pin in contracts_check.py is the single source of truth; verify the on-disk
# contracts match it. No hardcoded literal here, so this gate never re-stales on a bump.
[ -n "$forge_expects" ] || die "could not read FORGE_EXPECTED_CONTRACT_VERSION from contracts_check.py"
[ "$ctr_ver" = "$forge_expects" ] || die "contracts on disk ($ctr_ver) != Forge's pin ($forge_expects) — repo/contracts out of sync"

# --- 3. uv ---------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || die "uv not on PATH after install — open a new shell or add ~/.local/bin to PATH"
printf 'uv: %s\n' "$(uv --version)"
command -v git >/dev/null 2>&1 || warn "git not found — needed to commit the v9 work later (apt install git)"

# --- 4. drop non-portable build artifacts that rode along ----------------------
say "Removing stale .venv + caches (rebuilt below)"
rm -rf "$FORGE/.venv" "$CONTRACTS/.venv" \
       "$FORGE/.mypy_cache" "$FORGE/.ruff_cache" "$FORGE/.pytest_cache" "$FORGE/.hypothesis"

# --- 5. build the environment --------------------------------------------------
say "uv sync --extra dev (this builds .venv + installs editable contracts + dev tools)"
( cd "$FORGE" && uv sync --extra dev )

# --- 6. data directories -------------------------------------------------------
say "Ensuring data directories"
mkdir -p "$FORGE_DATA/logs" "$FORGE_DATA/exports" "$FORGE_DATA/approvals"
# Crucible owns the *content* of these; create the dirs so Forge's read/write
# paths exist. Forge harmlessly waits/skips until Crucible publishes exports.
mkdir -p "$OPTBT_DATA/inbox" "$OPTBT_DATA/exports"

if [ -n "$COPY_DB" ]; then
  [ -f "$COPY_DB" ] || die "--copy-db: no file at $COPY_DB"
  cp -v "$COPY_DB" "$FORGE_DATA/forge.db"
fi
if [ -f "$FORGE_DATA/forge.db" ]; then
  printf 'forge.db present: %s\n' "$(du -h "$FORGE_DATA/forge.db" | cut -f1)"
else
  warn "no forge.db at $FORGE_DATA — Forge will create a fresh one (no feedback history)"
fi

# --- 7. validate -------------------------------------------------------------
say "forge version + forge check"
( cd "$FORGE" && uv run forge version )
( cd "$FORGE" && uv run forge check )   # contracts compat (§13.5) + DB schema-ensure

# --- 8. systemd user units (daemon + timers) -----------------------------------
say "Installing systemd user units (daemon + timers)"
UNIT_DIR="$HOME/.config/systemd/user"
[ -f "$FORGE/deploy/systemd/forge.service" ] || die "missing unit file $FORGE/deploy/systemd/forge.service"
mkdir -p "$UNIT_DIR"
# Symlink every unit shipped in deploy/systemd/ (forge.service + all timers).
for u in "$FORGE"/deploy/systemd/*.service "$FORGE"/deploy/systemd/*.timer; do
  [ -e "$u" ] || continue
  ln -sfn "$u" "$UNIT_DIR/$(basename "$u")"
done

# enable-linger lets the user units run headless across logout/reboot.
loginctl enable-linger "$USER" 2>/dev/null || warn "enable-linger failed (need: loginctl enable-linger $USER)"
if systemctl --user daemon-reload 2>/dev/null; then
  # Timers run independently of Crucible — enable + start them now.
  for t in forge-ranker-eval forge-backup forge-healthcheck; do
    systemctl --user enable --now "$t.timer" 2>/dev/null || warn "could not enable $t.timer"
  done
  systemctl --user enable forge.service 2>/dev/null || warn "could not enable forge.service"
  if [ "$START" -eq 1 ]; then
    systemctl --user start forge.service && say "forge.service started"
  else
    say "forge.service ENABLED (not started); timers active. Start the daemon AFTER Crucible is up:"
    printf '       systemctl --user start forge.service\n'
  fi
else
  warn "systemctl --user unavailable in this shell (no user D-Bus session)."
  warn "After a real login: systemctl --user daemon-reload && systemctl --user enable --now \\"
  warn "  forge.service forge-ranker-eval.timer forge-backup.timer forge-healthcheck.timer"
fi

# --- 9. smoke test -------------------------------------------------------------
if [ "$SKIP_TESTS" -eq 0 ]; then
  say "Invariant smoke test (tests/invariants)"
  ( cd "$FORGE" && uv run pytest tests/invariants -q )
fi

say "Forge bootstrap complete."
cat <<EOF

Next steps
  1. Bring Crucible up FIRST (its agent owns ~/optbt_data + the db_writer socket
     + the registry / gated-runs / promoted / universe publishers). Forge needs
     ~/optbt_data/exports populated and db_writer.sock live for non-skipped
     iterations (the unit runs with --require-real-cache).
  2. Start Forge:        systemctl --user start forge.service
  3. Watch it:           journalctl --user -u forge.service -f
  4. Confirm health:     cd $FORGE && uv run forge check
  5. Verify the timers:  systemctl --user list-timers 'forge-*'
     (forge-healthcheck reports CRITICAL until the daemon is started — expected.)
EOF
