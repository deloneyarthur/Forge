#!/usr/bin/env python3
"""Pre-commit hook: make the SIGNED grammar freeze structural rather than remembered.

D390 signed the freeze and recorded, in its own "not done here" section, that nothing in the
tree read the declaration -- the existing version-bump scanner would pass a post-freeze bump
without complaint. This closes that gap in the shape hard rule #4 already uses for the
analogous case ("Structurally enforced"), and in the shape D389 asked for after a watcher was
described as armed with no unit behind it: **arm it or delete the claim.**

WHAT IT ENFORCES -- the sequencing half of the declaration's section 6, which is the half a
machine can check:

    once the declaration reads SIGNED, a CONTENT change to config/grammar.yaml requires an
    OPEN preregistration (status 'registered') whose claim states a required n.

WHAT IT DELIBERATELY DOES NOT ENFORCE. Section 6 also requires goldens re-pinned, emission
proof, funnel attribution and a STATUS block. Those are judgements about whether work was done
well, not facts about whether it was sequenced correctly, and a hook that pretended to check
them would give false assurance -- the exact failure this script exists to fix. It checks the
one thing it can actually know.

THE REOPENER ESCAPE, AND WHY IT IS SHAPED THIS WAY. Section 5 reopeners are first-class and
operator-gated; a guard that made them impossible would be wrong. So `FORGE_FREEZE_REOPENER=D###`
overrides -- but ONLY if the same commit stages a decision-log entry whose header carries that
D-number. An override that can be exercised silently is a hole; one that must leave a permanent
record in the log is an escape hatch. Deviations are proposed as Decision Log entries, never
silent edits.

Stdlib only; pre-commit runs it as a `local` hook.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAMMAR_PATH = "config/grammar.yaml"
DECLARATION_PATH = REPO_ROOT / "docs" / "proposals" / "grammar-freeze-declaration.md"
REGISTRY_PATH = REPO_ROOT / "config" / "preregistrations.jsonl"
DECISION_LOG_PATH = "IMPLEMENTATION_DECISIONS.md"

# The declaration's own signed header. Matched on the status line rather than the title so a
# retitle does not silently disarm the guard; `test_the_live_declaration_reads_as_signed`
# fails loudly if this stops matching the real document.
_SIGNED_RE = re.compile(r"^\*\*Status:.*\bSIGNED\b", re.MULTILINE)
_NOT_SIGNED_RE = re.compile(r"^\*\*Status:.*NOT SIGNED", re.MULTILINE)

# D363/D364: a preregistration states the evidence that would settle it, at registration.
_REQUIRED_N_RE = re.compile(r"required\s+n\b", re.IGNORECASE)


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], capture_output=True, cwd=REPO_ROOT, check=False)


def is_signed(declaration: Path) -> bool:
    """True when the declaration's status line reads SIGNED (and not NOT SIGNED)."""
    try:
        text = declaration.read_text(encoding="utf-8")
    except OSError:
        return False
    if _NOT_SIGNED_RE.search(text):
        return False
    return bool(_SIGNED_RE.search(text))


def _open_preregs_with_required_n(registry: Path) -> list[str]:
    """IDs of registered-but-unresolved preregs whose claim states a required n."""
    import json

    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if row.get("status") != "registered":
            continue
        if _REQUIRED_N_RE.search(str(row.get("claim", ""))):
            out.append(str(row.get("prereg_id", "?")))
    return out


def evaluate(
    *,
    grammar_changed: bool,
    declaration: Path,
    registry: Path,
    reopener: str | None,
    staged_decision_log: str,
) -> tuple[bool, str]:
    """Pure decision function. Returns (allowed, human-readable reason)."""
    if not grammar_changed:
        return True, "config/grammar.yaml unchanged — freeze guard not engaged."

    if not declaration.exists():
        return True, "No declaration file found — freeze guard inert."

    if not is_signed(declaration):
        return True, "Freeze declaration is not signed — guard inert (it is not retroactive)."

    if reopener:
        # A reopener must leave a permanent record in the same commit, or it is not an
        # override -- it is an unlogged exception.
        header = re.compile(rf"^##\s+{re.escape(reopener)}\b", re.MULTILINE)
        if header.search(staged_decision_log):
            return True, (
                f"Reopener {reopener} exercised, and the commit stages its Decision Log "
                f"entry. Section 5 reopener — permitted, on the record."
            )
        return False, (
            f"FORGE_FREEZE_REOPENER={reopener} was set, but this commit stages no "
            f"`## {reopener}` entry in {DECISION_LOG_PATH}.\n"
            f"An override that leaves no permanent record is a hole, not an escape hatch.\n"
            f"Write the Decision Log entry naming the section 5 reopener, stage it, commit again."
        )

    open_ids = _open_preregs_with_required_n(registry)
    if open_ids:
        return True, (
            f"Open preregistration(s) with a stated required n: {', '.join(open_ids)}. "
            f"Section 6 sequencing satisfied."
        )

    import json

    any_open = False
    try:
        for raw in registry.read_text(encoding="utf-8").splitlines():
            if raw.strip() and json.loads(raw).get("status") == "registered":
                any_open = True
                break
    except (OSError, json.JSONDecodeError):
        pass

    detail = (
        "an open preregistration exists but its claim does not state a **required n** "
        "(D363/D364) — a claim with no observable is not a preregistration"
        if any_open
        else "there is no open preregistration at all"
    )
    return False, (
        f"REFUSED — the grammar freeze is SIGNED and this commit changes {GRAMMAR_PATH}, but "
        f"{detail}.\n\n"
        f"Section 6, in force since the signature: every post-freeze grammar change is a full "
        f"increment, and the prereg comes BEFORE the edit with its required n stated at "
        f"registration.\n\n"
        f"  Register first:  uv run forge prereg register ...\n"
        f"                   (state the required n in the claim)\n"
        f"  Or, if this is a section 5 reopener, write its Decision Log entry, stage it, and set\n"
        f"    FORGE_FREEZE_REOPENER=D### git commit ...\n"
    )


def _grammar_content_changed() -> bool:
    """True when grammar.yaml is staged AND its indexed content differs from HEAD."""
    staged = _git("diff", "--cached", "--name-only")
    names = {ln.strip() for ln in staged.stdout.decode().splitlines() if ln.strip()}
    if GRAMMAR_PATH not in names:
        return False
    head = _git("show", f"HEAD:{GRAMMAR_PATH}")
    index = _git("show", f":{GRAMMAR_PATH}")
    if index.returncode != 0:
        return False
    if head.returncode != 0:
        return True  # newly added
    return head.stdout != index.stdout


def _staged_decision_log() -> str:
    """The added lines of the staged Decision Log diff (where a new `## D###` header lands)."""
    diff = _git("diff", "--cached", "-U0", "--", DECISION_LOG_PATH)
    if diff.returncode != 0:
        return ""
    return "\n".join(
        ln[1:] for ln in diff.stdout.decode(errors="replace").splitlines() if ln.startswith("+")
    )


def main() -> int:
    allowed, message = evaluate(
        grammar_changed=_grammar_content_changed(),
        declaration=DECLARATION_PATH,
        registry=REGISTRY_PATH,
        reopener=os.environ.get("FORGE_FREEZE_REOPENER") or None,
        staged_decision_log=_staged_decision_log(),
    )
    if not allowed:
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
