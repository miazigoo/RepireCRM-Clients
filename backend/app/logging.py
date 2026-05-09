"""Structured logging for the portal backend.

Usage::

    from app.logging import get_logger
    log = get_logger(__name__)
    log.info("order synced", crm_order_id=42, tenant="default")

In development the format is human-readable; in production JSON lines are
emitted so log aggregators (Datadog, Loki, etc.) can parse them directly.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit one JSON line per log record."""

    def format(self, record: logging.LogRecord) -> str:
        extra: dict[str, Any] = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__dict__ and not k.startswith("_")
        }
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        payload.update(extra)
        return json.dumps(payload, default=str, ensure_ascii=False)


class _DevFormatter(logging.Formatter):
    _COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__dict__ and not k.startswith("_")
        }
        msg = record.getMessage()
        if extra:
            kv = "  ".join(f"{k}={v!r}" for k, v in extra.items())
            msg = f"{msg}  [{kv}]"
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return f"{color}{ts} {record.levelname:8s} {record.name}: {msg}{self._RESET}"


def configure_logging(environment: str = "development") -> None:
    """Call once at application startup (done in ``main.py``)."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. during tests)

    handler = logging.StreamHandler(sys.stdout)
    if environment == "production":
        handler.setFormatter(_JsonFormatter())
        root.setLevel(logging.INFO)
    else:
        handler.setFormatter(_DevFormatter())
        root.setLevel(logging.DEBUG)

    root.addHandler(handler)
    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class _BoundLogger:
    """Thin wrapper that attaches key-value context to every log call."""

    __slots__ = ("_log", "_ctx")

    def __init__(self, logger: logging.Logger, **ctx: Any) -> None:
        self._log = logger
        self._ctx = ctx

    def _emit(self, level: int, msg: str, **kw: Any) -> None:
        extra = {**self._ctx, **kw}
        self._log.log(level, msg, extra=extra, stacklevel=2)

    def debug(self, msg: str, **kw: Any) -> None:
        self._emit(logging.DEBUG, msg, **kw)

    def info(self, msg: str, **kw: Any) -> None:
        self._emit(logging.INFO, msg, **kw)

    def warning(self, msg: str, **kw: Any) -> None:
        self._emit(logging.WARNING, msg, **kw)

    def error(self, msg: str, **kw: Any) -> None:
        self._emit(logging.ERROR, msg, **kw)

    def exception(self, msg: str, **kw: Any) -> None:
        self._log.exception(msg, extra={**self._ctx, **kw}, stacklevel=2)

    def bind(self, **ctx: Any) -> "_BoundLogger":
        return _BoundLogger(self._log, **{**self._ctx, **ctx})


def get_logger(name: str, **ctx: Any) -> _BoundLogger:
    """Return a bound logger for ``name``.

    Example::

        log = get_logger(__name__, service="sync")
        log.info("push done", pushed=5)
    """
    return _BoundLogger(logging.getLogger(name), **ctx)
