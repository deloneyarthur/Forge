"""Structured logging configuration for Forge.

Uses structlog. Console renderer for dev, JSON renderer for production. Called
once at CLI entry; downstream code obtains a logger via `structlog.get_logger`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_LOG_LEVEL_DEFAULT = "INFO"


def configure_logging(level: str = _LOG_LEVEL_DEFAULT, *, json_output: bool = False) -> None:
    """Configure stdlib logging + structlog. Idempotent; safe to call repeatedly."""
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )
