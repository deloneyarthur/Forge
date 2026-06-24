#!/usr/bin/env bash
# Pre-deploy readiness gate for the D104 ritual (docs/tasks/deploy.md).
#
# READ-ONLY: it checks, it never stops/starts the service or mutates the tree. Exit 0 =
# GO, non-zero = NO-GO. It codifies the pre-restart checks whose manual omission has
# bitten live deploys:
#   * a dirty tree a reboot would silently deploy (D104),
#   * a stale contracts pin that hard-halts the daemon on restart (D176),
#   * partial feature wiring that runs inert (D185).
# The full suite is the single gate that covers the last two: it includes the
# contracts-pin equality test AND the loop/single-iteration forward tests, so a green
# suite proves both pin-adoption and anti-inertness in one shot.
#
# Run it before you commit + restart. It does NOT replace the ritual's stop→restart
# steps (those are the operator's deliberate action) — it gates them.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

PROJ="$HOME/proj/Forge"
cd "$PROJ" || { echo "deploy-preflight: FATAL cannot cd $PROJ" >&2; exit 2; }

fail=0
note() { echo "deploy-preflight: $*"; }

echo "=== deploy preflight (D104) — read-only readiness gate ==="

# 1. Tree cleanliness. A reboot/restart deploys the WORKING TREE (committed or not),
#    so any uncommitted TRACKED change is a hazard. Untracked files don't deploy, so
#    they're excluded (operator scratch docs are fine).
echo "--- 1. git deploy-surface (src/config/pyproject/uv.lock/deploy deploy on restart) ---"
surface="$(git status --porcelain --untracked-files=no -- src config pyproject.toml uv.lock deploy 2>/dev/null)"
if [ -n "$surface" ]; then
    note "FAIL uncommitted deploy-surface changes (a restart/reboot deploys these):"
    echo "$surface" | sed 's/^/      /'
    note "      -> commit them; land nothing half-applied in the live tree."
    fail=1
else
    note "OK deploy surface clean (src/config/pyproject/uv.lock/deploy committed)"
fi
# Other uncommitted tracked files (docs/tests/scripts) do not change the running
# daemon, so they're informational — they never block a deploy.
others="$(git status --porcelain --untracked-files=no -- ':!src' ':!config' ':!pyproject.toml' ':!uv.lock' ':!deploy' 2>/dev/null)"
if [ -n "$others" ]; then
    note "note: other uncommitted tracked files (don't affect the daemon; not blocking):"
    echo "$others" | sed 's/^/      /'
fi

# 2. The full suite IS the deploy gate (docs/tasks/deploy.md). Covers the contracts-pin
#    equality test (D176) and the loop-forward / anti-inertness tests (D185).
echo "--- 2. full test suite (the deploy gate; covers pin-adoption + anti-inertness) ---"
if uv run pytest -q; then
    note "OK full suite passed"
else
    note "FAIL suite red -- do NOT deploy (fix first; a contracts bump must be adopted, pin bumped)"
    fail=1
fi

echo "=== result ==="
if [ "$fail" -eq 0 ]; then
    note "GO -- tree clean + suite green. Proceed per docs/tasks/deploy.md:"
    note "      systemctl --user stop forge.service && <commit/merge> && systemctl --user start forge.service"
    note "      then verify the journal (contracts line, grammar_version, no traceback)."
    exit 0
fi
note "NO-GO -- resolve the WARN/FAIL above before deploying."
exit 1
