"""ToDo list panel widget: displays session tasks with status indicators."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from codehive.clients.terminal.widgets.status_indicator import StatusIndicator


class TaskRow(Static):
    """A single task row showing title and status."""

    DEFAULT_CSS = """
    TaskRow {
        layout: horizontal;
        height: auto;
        padding: 0 1;
    }
    TaskRow > .task-title {
        width: 1fr;
    }
    """

    def __init__(self, title: str, status: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._title = title
        self._status = status

    def compose(self) -> ComposeResult:
        yield Static(self._title, classes="task-title")
        yield StatusIndicator(self._status)


class _TodoEmpty(Static):
    """Placeholder for empty task list."""

    DEFAULT_CSS = """
    _TodoEmpty {
        padding: 1;
        color: $text-muted;
    }
    """


class TodoPanel(Vertical):
    """Panel listing session tasks with their status."""

    DEFAULT_CSS = """
    TodoPanel {
        height: 1fr;
        border: solid $primary;
    }
    #todo-title {
        padding: 0 1;
        text-style: bold;
        background: $primary-background;
    }
    #todo-scroll {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("ToDo", id="todo-title")
        yield VerticalScroll(
            _TodoEmpty("No tasks"),
            id="todo-scroll",
        )

    def load_tasks(self, tasks: list[dict[str, Any]]) -> None:
        """Replace displayed tasks with the given list."""
        scroll = self.query_one("#todo-scroll", VerticalScroll)
        scroll.remove_children()
        if not tasks:
            scroll.mount(_TodoEmpty("No tasks"))
            return
        for task in tasks:
            scroll.mount(
                TaskRow(
                    title=task.get("title", ""),
                    status=task.get("status", "pending"),
                )
            )
