"""SIGTERM handling for the weekly run (REL-4, Batch 5 G6).

WHY a flag and not an exception: `submitter._submit_one` writes the inbox file inside the DB
transaction, so a signal that unwinds the stack mid-candidate can leave an inbox file with no
committed `submissions` row (the July reliability audit's REL-4). systemd stops the
`forge-campaign` oneshot with SIGTERM. The handler therefore only SETS a flag; `submit_batch`
reads it between candidates, so the in-flight candidate finishes its write + commit and the
next one never starts. The run then records `status: error` and exits non-zero. A second
SIGTERM while the flag is already set raises `KeyboardInterrupt` — the operator's deliberate
hard stop, mirroring SIGINT (the submitter's `except BaseException: ROLLBACK` handles it).

The guard is a context manager because tests share one process: the previous disposition is
restored and the flag cleared on exit, whatever happened inside.
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType

_stop_requested: bool = False


class CampaignStopped(RuntimeError):
    """The run stopped on a SIGTERM between candidates; the record was written first."""


def stop_requested() -> bool:
    return _stop_requested


def request_stop() -> None:
    global _stop_requested  # noqa: PLW0603 — the one process-wide stop flag
    _stop_requested = True


def reset_stop() -> None:
    global _stop_requested  # noqa: PLW0603
    _stop_requested = False


def sigterm_handler(signum: int, frame: FrameType | None) -> None:
    """First SIGTERM: request a stop between candidates. Second: hard stop."""
    del signum, frame
    if _stop_requested:
        raise KeyboardInterrupt
    request_stop()


@contextmanager
def sigterm_guard() -> Iterator[None]:
    """Bind SIGTERM to the stop-flag handler for the duration of a run.

    Only the main thread may install signal handlers; off the main thread (some test
    harnesses) the guard is a no-op except for clearing the flag on exit."""
    reset_stop()
    installed = threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGTERM) if installed else None
    if installed:
        signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        yield
    finally:
        if installed:
            signal.signal(signal.SIGTERM, previous)
        reset_stop()


__all__ = [
    "CampaignStopped",
    "request_stop",
    "reset_stop",
    "sigterm_guard",
    "sigterm_handler",
    "stop_requested",
]
