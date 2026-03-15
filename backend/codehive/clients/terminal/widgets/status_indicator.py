"""Reusable status badge widget for session statuses."""

from __future__ import annotations

from textual.widgets import Static

# Maps session status -> (display label, CSS class suffix)
_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "idle": ("IDLE", "idle"),
    "planning": ("PLANNING", "planning"),
    "executing": ("EXECUTING", "executing"),
    "waiting_input": ("WAITING", "waiting"),
    "waiting_approval": ("APPROVAL", "waiting"),
    "blocked": ("BLOCKED", "blocked"),
    "completed": ("DONE", "completed"),
    "failed": ("FAILED", "failed"),
}

_DEFAULT_STYLE = ("UNKNOWN", "unknown")


class StatusIndicator(Static):
    """A small badge that renders a session status with a visual style class."""

    DEFAULT_CSS = """
    StatusIndicator {
        width: auto;
        min-width: 10;
        text-align: center;
        padding: 0 1;
    }
    StatusIndicator.status-idle {
        color: $text-muted;
    }
    StatusIndicator.status-planning {
        color: cyan;
    }
    StatusIndicator.status-executing {
        color: green;
    }
    StatusIndicator.status-waiting {
        color: yellow;
    }
    StatusIndicator.status-blocked {
        color: $warning;
    }
    StatusIndicator.status-completed {
        color: $success;
    }
    StatusIndicator.status-failed {
        color: $error;
    }
    StatusIndicator.status-unknown {
        color: $text-muted;
    }
    """

    def __init__(self, status: str, **kwargs: object) -> None:
        label, class_suffix = _STATUS_STYLES.get(status, _DEFAULT_STYLE)
        super().__init__(f"[{label}]", **kwargs)  # type: ignore[arg-type]
        self._status = status
        self._class_suffix = class_suffix
        self.add_class(f"status-{class_suffix}")

    @property
    def status(self) -> str:
        return self._status

    @property
    def class_suffix(self) -> str:
        return self._class_suffix
