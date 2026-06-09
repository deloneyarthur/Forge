"""Phase 6 — CLI completion + help-text audit (§12 / D025/D4).

Mechanical sync guard for the Forge CLI surface. For every registered
Typer command (top-level + sub-app subcommands):

  (1) the command callback has a non-empty docstring (powers `--help`);
  (2) every option declared with `typer.Option(...)` has a non-empty
      ``help=`` string;
  (3) the command name appears at least once in ``README.md`` (the
      Commands + Operations sections must stay in sync with the CLI
      surface — adding a new command must mean adding it to README too).

When a new command lands, this test forces both the docstring + option
help + README mention to be filled in before merge. Cheap, mechanical,
and catches the most common drift.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from pathlib import Path

from typer import Typer

from forge.cli.main import app

# 2026-06-09 docs restructure: the commands reference moved README → MANPAGE.md;
# the CLI↔docs sync guards follow the content to its new owner.
_MANPAGE = Path(__file__).resolve().parents[2] / "docs" / "MANPAGE.md"


def _walk_commands(typer_app: Typer, prefix: str = "") -> Iterable[tuple[str, object]]:
    """Yield (qualified-name, callback) for every command in the tree."""
    for cmd in typer_app.registered_commands:
        # Typer's `command()` decorator stores the original function here.
        callback = cmd.callback
        if callback is None:
            continue
        # CLI display name: explicit `name=` if set, else the function name.
        cli_name = cmd.name or callback.__name__
        yield (f"{prefix}{cli_name}", callback)
    for grp in typer_app.registered_groups:
        if grp.typer_instance is None or grp.name is None:
            continue
        yield from _walk_commands(grp.typer_instance, prefix=f"{grp.name} ")


def _registered_command_names() -> list[str]:
    return [name for name, _ in _walk_commands(app)]


def test_every_command_has_docstring() -> None:
    """Each command's callback must carry a non-empty docstring so
    `forge <cmd> --help` shows real help text."""
    missing: list[str] = []
    for name, callback in _walk_commands(app):
        doc = getattr(callback, "__doc__", None)
        if not doc or not doc.strip():
            missing.append(name)
    assert not missing, f"commands without a docstring: {missing}"


def test_every_option_has_help_text() -> None:
    """Each parameter declared via `typer.Option(...)` (or `typer.Argument(...)`
    with `help=`) must have a non-empty `help=` string."""
    offenders: list[str] = []
    for name, callback in _walk_commands(app):
        sig = inspect.signature(callback)
        for param_name, param in sig.parameters.items():
            default = param.default
            # Typer wraps the default value in OptionInfo / ArgumentInfo.
            if default is inspect.Parameter.empty:
                help_attr = None
            else:
                help_attr = getattr(default, "help", None)
            # `help` exists on OptionInfo/ArgumentInfo even if None; only flag
            # explicit empty/None for typer-wrapped params, not plain
            # int/str defaults.
            if help_attr is None and not hasattr(default, "param_decls"):
                # not a typer-wrapped option/argument — skip
                continue
            if not help_attr or not str(help_attr).strip():
                offenders.append(f"{name}::{param_name}")
    assert not offenders, f"options without help text: {offenders}"


def test_every_command_is_mentioned_in_manpage() -> None:
    """Each CLI command name (e.g. `forge feedback`, `forge grammar
    list-proposals`) must appear at least once in ``docs/MANPAGE.md``. Keeps
    the COMMANDS reference in sync with the actual CLI.
    """
    manpage_text = _MANPAGE.read_text(encoding="utf-8")
    missing: list[str] = []
    for name in _registered_command_names():
        # Match either `forge <name>` or `forge <prefix> <suffix>`.
        needle = f"forge {name}"
        if needle not in manpage_text:
            missing.append(needle)
    assert not missing, f"docs/MANPAGE.md missing references to: {missing}"


def test_root_app_has_help_string() -> None:
    """The top-level `forge` command must carry its own help text so
    `forge --help` is informative."""
    assert app.info.help, "top-level Typer app missing help= text"


def test_each_top_level_command_has_manpage_heading() -> None:
    """The MANPAGE's COMMANDS section gives every top-level command its own
    `### forge <name>` heading. Sanity guard so the reference doesn't go
    stale even when individual mentions exist elsewhere."""
    manpage_text = _MANPAGE.read_text(encoding="utf-8")
    # Top-level commands only (sub-app commands live under their own headings).
    top_level = [name for name, _ in _walk_commands(app) if " " not in name and name != "grammar"]
    missing = [f"### forge {n}" for n in top_level if f"### forge {n}" not in manpage_text]
    assert not missing, f"MANPAGE COMMANDS section missing headings: {missing}"
