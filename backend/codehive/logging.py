"""Structured logging configuration for codehive."""

import json
import logging
import sys
import traceback as tb_module
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id_var", default=None)

# Third-party loggers to quiet down
_NOISY_LOGGERS = ("uvicorn.access", "httpcore", "httpx")


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        log_dict: dict[str, object] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id from ContextVar or extra
        rid = getattr(record, "request_id", None) or request_id_var.get()
        if rid is not None:
            log_dict["request_id"] = rid

        # Include traceback if present
        if record.exc_info and record.exc_info[0] is not None:
            log_dict["traceback"] = "".join(tb_module.format_exception(*record.exc_info))

        # Include any extra fields (skip standard LogRecord attributes)
        _standard = {
            "name",
            "msg",
            "args",
            "created",
            "relativeCreated",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "pathname",
            "filename",
            "module",
            "thread",
            "threadName",
            "process",
            "processName",
            "levelname",
            "levelno",
            "message",
            "msecs",
            "request_id",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _standard and not key.startswith("_"):
                log_dict[key] = value

        return json.dumps(log_dict, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Simple human-readable formatter for local development."""

    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        rid = getattr(record, "request_id", None) or request_id_var.get()
        if rid is not None:
            record.msg = f"[{rid}] {record.msg}"
        result = super().format(record)
        if record.exc_info and record.exc_info[0] is not None:
            result += "\n" + "".join(tb_module.format_exception(*record.exc_info))
        return result


def configure_logging(settings: object | None = None) -> None:
    """Configure the root logger based on application settings.

    Parameters
    ----------
    settings:
        An object with ``log_level`` (str), ``log_json`` (bool), and
        ``log_file`` (str) attributes. If *None*, defaults are used.
    """
    log_level = getattr(settings, "log_level", "INFO") if settings else "INFO"
    log_json = getattr(settings, "log_json", True) if settings else True
    log_file = getattr(settings, "log_file", "") if settings else ""

    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter: logging.Formatter
    if log_json:
        formatter = JSONFormatter()
    else:
        formatter = HumanReadableFormatter()

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates on repeated calls
    root.handlers.clear()

    # Always add stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    # Optionally add file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
