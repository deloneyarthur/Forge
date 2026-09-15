#!/usr/bin/env bash
# Pre-deploy readiness gate for the D104 ritual (docs/tasks/deploy.md).
#
# READ-ONLY: it checks, it never touches units or mutates the tree. Exit 0 = GO, non-zero =
# NO-GO. Since the 2026-09-14 cutover (D416) there is no daemon to restart: the weekly
# forge-campaign.timer runs whatever this tree contains, so the two hazards it codifies are
#   * a dirty deploy surface the next Sunday run (or a reboot's re-armed timer) would silently
#     deploy (D104),
#   * a stale contracts pin that fails the run's first boot check (D176).
# The full suite is the single gate covering the pin (the equality test) and the campaign
# path (its hermetic end-to-end tests). Run it before you commit.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

PROJ="$HOME/proj/Forge"
cd "$PROJ" || { echo "deploy-preflight: FATAL cannot cd $PROJ" >&2; exit 2; }

fail=0
note() { echo "deploy-preflight: $*"; }

echo "=== deploy preflight (D104) — read-only readiness gate ==="

# 1. Tree cleanliness. A reboot/restart deploys the WORKING TREE (committed or not),
#    (the next Sunday run / a reboot's re-armed timer), so any uncommitted TRACKED change is a hazard. Untracked files don't deploy, so
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
# Other uncommitted tracked files (docs/tests/scripts) do not change what the weekly run
# executes, so they're informational — they never block a deploy.
others="$(git status --porcelain --untracked-files=no -- ':!src' ':!config' ':!pyproject.toml' ':!uv.lock' ':!deploy' 2>/dev/null)"
if [ -n "$others" ]; then
    note "note: other uncommitted tracked files (don't affect the weekly run; not blocking):"
    echo "$others" | sed 's/^/      /'
fi

# 2. The full suite IS the deploy gate (docs/tasks/deploy.md). Covers the contracts-pin
#    equality test (D176) and the campaign path's end-to-end tests.
echo "--- 2. full test suite (the deploy gate; covers pin-adoption + the campaign path) ---"
if uv run pytest -q; then
    note "OK full suite passed"
else
    note "FAIL suite red -- do NOT deploy (fix first; a contracts bump must be adopted, pin bumped)"
    fail=1
fi

echo "=== result ==="
if [ "$fail" -eq 0 ]; then
    note "GO -- tree clean + suite green. Commit; the next Sunday run deploys (docs/tasks/deploy.md)."
    note "      Verify now with: uv run forge campaign --dry-run --skip-train --forge-db \"\$(scripts/live_db_snapshot.sh --max-age-min 720)\""
    exit 0
fi
note "NO-GO -- resolve the WARN/FAIL above before deploying."
exit 1
