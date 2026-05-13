"""Integration tests for the grammar pre-commit hook scripts.

Each test sets up a temporary git repo, writes HEAD revisions of the
grammar files (or omits them for first-commit cases), stages changes,
and runs the script via subprocess to assert exit codes and stderr.

The scripts are stdlib-only so they can be exercised without installing
into the test environment.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = os.environ | {
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@x.test",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@x.test",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "t@x.test"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, env=env)
    # Seed: empty commit so HEAD exists.
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=repo,
        check=True,
        env=env,
    )
    (repo / "config").mkdir()
    (repo / "config" / "grammar_archive").mkdir()
    (repo / "docs").mkdir()
    return repo


def _commit_files(repo: Path, files: dict[str, str], message: str) -> None:
    env = _git_env()
    for relpath, content in files.items():
        full = repo / relpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--", *files.keys()], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True, env=env)


def _stage_files(repo: Path, files: dict[str, str]) -> None:
    env = _git_env()
    for relpath, content in files.items():
        full = repo / relpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--", *files.keys()], cwd=repo, check=True, env=env)


def _git_env() -> dict[str, str]:
    return os.environ | {
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@x.test",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@x.test",
    }


def _run_script(script: str, repo: Path) -> tuple[int, str]:
    # Copy the script into the temp repo so its REPO_ROOT lookup works
    # against the repo under test. The script computes REPO_ROOT from
    # its own __file__, so we run a copy.
    target_dir = repo / "scripts"
    target_dir.mkdir(exist_ok=True)
    source = SCRIPTS_DIR / script
    target = target_dir / script
    target.write_bytes(source.read_bytes())
    result = subprocess.run(
        ["python", str(target)],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )
    return result.returncode, result.stderr


# ---------------------------------------------------------------------------
# Version-bump scanner
# ---------------------------------------------------------------------------


def _grammar(version: str, count: int) -> str:
    return f"grammar_version: {version}\nrules:\n  - id: S1\n    count: {count}\n"


def test_version_bump_no_staged_grammar(tmp_path: Path) -> None:
    """An unrelated commit (no grammar changes) — hook is a no-op."""
    repo = _init_repo(tmp_path)
    _commit_files(repo, {"README.md": "x"}, "seed")
    _stage_files(repo, {"README.md": "y"})
    rc, _ = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 0


def test_version_bump_first_commit_with_archive(tmp_path: Path) -> None:
    """Introducing grammar.yaml for the first time. Archive entry for
    the same version must be staged too."""
    repo = _init_repo(tmp_path)
    _stage_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
    )
    rc, _ = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 0


def test_version_bump_first_commit_without_archive_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _stage_files(repo, {"config/grammar.yaml": _grammar("v1", 1)})
    rc, err = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 1
    assert "archive entry" in err
    assert "config/grammar_archive/v1.yaml" in err


def test_version_bump_no_change_passes(tmp_path: Path) -> None:
    """grammar.yaml in HEAD; an unrelated file change is staged."""
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
        "v1",
    )
    _stage_files(repo, {"README.md": "hello"})
    rc, _ = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 0


def test_version_bump_silent_edit_rejected(tmp_path: Path) -> None:
    """grammar.yaml content changed but grammar_version unchanged — the
    bug the hook is for."""
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
        "v1",
    )
    _stage_files(repo, {"config/grammar.yaml": _grammar("v1", 2)})
    rc, err = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 1
    assert "grammar_version" in err
    assert "v1" in err


def test_version_bump_with_archive_passes(tmp_path: Path) -> None:
    """grammar.yaml changed; grammar_version bumped v1 → v2; v1 archived."""
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
        "v1",
    )
    _stage_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v2", 2),
            # The v1 archive file already matches HEAD's grammar.yaml from
            # the seed commit. We stage it explicitly to satisfy the hook,
            # restating the same content.
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
    )
    rc, _ = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 0


def test_version_bump_with_archive_at_head_passes(tmp_path: Path) -> None:
    """v1 → v2 bumped; v1 archive already at HEAD with correct content.
    Re-staging the archive is not required — its post-commit content is
    correct from HEAD."""
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
        "v1",
    )
    _stage_files(repo, {"config/grammar.yaml": _grammar("v2", 2)})
    rc, _ = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 0


def test_version_bump_with_archive_deleted_fails(tmp_path: Path) -> None:
    """v1 → v2 bumped AND the v1 archive is staged for deletion. The
    hook must catch this because the post-commit tree would have no
    archive of the prior version."""
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
        "v1",
    )
    # Write the bump
    (repo / "config" / "grammar.yaml").write_text(_grammar("v2", 2), encoding="utf-8")
    subprocess.run(["git", "add", "config/grammar.yaml"], cwd=repo, check=True, env=_git_env())
    # Delete the archive
    subprocess.run(
        ["git", "rm", "--cached", "-q", "config/grammar_archive/v1.yaml"],
        cwd=repo,
        check=True,
        env=_git_env(),
    )
    rc, err = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 1
    assert "v1.yaml" in err
    assert "not in the index" in err


def test_version_bump_archive_wrong_content_rejected(tmp_path: Path) -> None:
    """Bumped v1 → v2; staged v1 archive doesn't match HEAD's content."""
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v1", 1),
            "config/grammar_archive/v1.yaml": _grammar("v1", 1),
        },
        "v1",
    )
    _stage_files(
        repo,
        {
            "config/grammar.yaml": _grammar("v2", 2),
            "config/grammar_archive/v1.yaml": _grammar("v1", 99),  # tampered
        },
    )
    rc, err = _run_script("check_grammar_version_bump.py", repo)
    assert rc == 1
    assert "does NOT match" in err


# ---------------------------------------------------------------------------
# Doc-sync scanner
# ---------------------------------------------------------------------------


def _grammar_two_rules() -> str:
    return (
        "grammar_version: v1\n"
        "rules:\n"
        "  - id: S1\n"
        "    field: hypothesis\n"
        "  - id: S2\n"
        "    field: signals.role.directional\n"
    )


def _doc(headings: list[str]) -> str:
    body = "# Forge Grammar\n\n"
    for h in headings:
        body += f"## {h}: stuff\n\nBody text.\n\n"
    return body


def test_doc_sync_neither_staged_no_op(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _stage_files(repo, {"README.md": "x"})
    rc, _ = _run_script("check_grammar_doc_sync.py", repo)
    assert rc == 0


def test_doc_sync_in_sync_passes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar_two_rules(),
            "docs/GRAMMAR.md": _doc(["S1", "S2"]),
        },
        "v1",
    )
    _stage_files(
        repo,
        {
            "config/grammar.yaml": _grammar_two_rules() + "  - id: S3\n",
            "docs/GRAMMAR.md": _doc(["S1", "S2", "S3"]),
        },
    )
    rc, _ = _run_script("check_grammar_doc_sync.py", repo)
    assert rc == 0


def test_doc_sync_missing_doc_heading_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar_two_rules(),
            "docs/GRAMMAR.md": _doc(["S1", "S2"]),
        },
        "v1",
    )
    # Add a new rule S3 in grammar but forget the doc.
    _stage_files(
        repo,
        {
            "config/grammar.yaml": _grammar_two_rules() + "  - id: S3\n",
            "docs/GRAMMAR.md": _doc(["S1", "S2"]),
        },
    )
    rc, err = _run_script("check_grammar_doc_sync.py", repo)
    assert rc == 1
    assert "S3" in err
    assert "missing sections" in err


def test_doc_sync_orphan_heading_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit_files(
        repo,
        {
            "config/grammar.yaml": _grammar_two_rules(),
            "docs/GRAMMAR.md": _doc(["S1", "S2"]),
        },
        "v1",
    )
    # Remove S2 from grammar but keep its heading.
    _stage_files(
        repo,
        {
            "config/grammar.yaml": (
                "grammar_version: v1\nrules:\n  - id: S1\n    field: hypothesis\n"
            ),
            "docs/GRAMMAR.md": _doc(["S1", "S2"]),
        },
    )
    rc, err = _run_script("check_grammar_doc_sync.py", repo)
    assert rc == 1
    assert "S2" in err
    assert "not present" in err


@pytest.fixture(autouse=True)
def _ignore_user_git_config(monkeypatch: Any, tmp_path: Path) -> None:
    """Don't read the user's ~/.gitconfig (signing keys, hooks, etc.)
    when running git in tests."""
    sandbox = tmp_path / "git-sandbox-home"
    sandbox.mkdir()
    monkeypatch.setenv("HOME", str(sandbox))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(sandbox))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
