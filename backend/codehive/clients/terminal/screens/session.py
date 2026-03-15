"""Session screen: chat, ToDo, timeline, and changed files panels."""

from __future__ import annotations

from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from codehive.clients.terminal.widgets.chat import ChatPanel
from codehive.clients.terminal.widgets.files import FilesPanel
from codehive.clients.terminal.widgets.status_indicator import StatusIndicator
from codehive.clients.terminal.widgets.timeline import TimelinePanel
from codehive.clients.terminal.widgets.todo import TodoPanel
from codehive.clients.terminal.ws_client import WSClient


class SessionScreen(Screen):
    """Displays a single session with four panels: chat, todo, timeline, files."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
        ("tab", "focus_next", "Next Panel"),
        ("shift+tab", "focus_previous", "Prev Panel"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    #session-header {
        height: auto;
        padding: 1;
        layout: horizontal;
    }
    #session-name {
        width: 1fr;
        text-style: bold;
    }
    #session-meta {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    #session-body {
        height: 1fr;
    }
    #session-sidebar {
        width: 1fr;
    }
    """

    def __init__(self, session_id: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._session_id = session_id
        self._ws_client: WSClient | None = None

    @property
    def session_id(self) -> str:
        return self._session_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="session-header"):
            yield Static("Loading...", id="session-name")
            yield Static("", id="session-meta")
            yield StatusIndicator("idle", id="session-status")
        with Horizontal(id="session-body"):
            yield ChatPanel(id="chat-panel")
            with Vertical(id="session-sidebar"):
                yield TodoPanel(id="todo-panel")
                yield TimelinePanel(id="timeline-panel")
                yield FilesPanel(id="files-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()
        self._start_ws()

    @work(thread=True)
    def _load_data(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]

        # Fetch session info
        try:
            session = api.get_session(self._session_id)
        except Exception:
            session = {"name": "Error", "engine": "", "mode": "", "status": "unknown"}

        # Fetch tasks
        try:
            tasks = api.list_tasks(self._session_id)
        except Exception:
            tasks = []

        # Fetch events
        try:
            events = api.list_events(self._session_id)
        except Exception:
            events = []

        # Fetch diffs
        try:
            diffs = api.get_diffs(self._session_id)
        except Exception:
            diffs = []

        self.app.call_from_thread(self._apply_data, session, tasks, events, diffs)

    def _apply_data(
        self,
        session: dict[str, Any],
        tasks: list[dict[str, Any]],
        events: list[dict[str, Any]],
        diffs: list[dict[str, Any]],
    ) -> None:
        # Update session header
        self.query_one("#session-name", Static).update(session.get("name", ""))
        meta_parts = [
            session.get("engine", ""),
            session.get("mode", ""),
        ]
        self.query_one("#session-meta", Static).update(" | ".join(p for p in meta_parts if p))

        # Update status indicator
        status = session.get("status", "unknown")
        try:
            old_indicator = self.query_one("#session-status", StatusIndicator)
            new_indicator = StatusIndicator(status, id="session-status")
            old_indicator.replace_with(new_indicator)
        except Exception:
            pass

        # Extract messages from events (type=message.created)
        messages = []
        for evt in events:
            if evt.get("type") == "message.created":
                data = evt.get("data", {})
                if isinstance(data, dict) and "role" in data:
                    messages.append(data)

        # Populate panels
        self.query_one("#chat-panel", ChatPanel).load_messages(messages)
        self.query_one("#todo-panel", TodoPanel).load_tasks(tasks)
        self.query_one("#timeline-panel", TimelinePanel).load_events(events)
        self.query_one("#files-panel", FilesPanel).load_diffs(diffs)

    @work(thread=True)
    def _start_ws(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        base_url = api.base_url
        self._ws_client = WSClient(base_url, self._session_id)
        self._ws_client.connect(self._on_ws_event_thread)

    def _on_ws_event_thread(self, event: dict[str, Any]) -> None:
        """Called from the WS thread; dispatch to UI thread."""
        self.app.call_from_thread(self._handle_ws_event, event)

    def _handle_ws_event(self, event: dict[str, Any]) -> None:
        """Handle a WebSocket event on the UI thread."""
        event_type = event.get("type", "")
        data = event.get("data", {})

        if event_type == "message.created" and isinstance(data, dict):
            self.query_one("#chat-panel", ChatPanel).append_message(
                role=data.get("role", "unknown"),
                content=data.get("content", ""),
            )

        elif event_type in ("task.started", "task.completed"):
            # Reload tasks
            self._reload_tasks()

        elif event_type == "file.changed":
            # Reload diffs
            self._reload_diffs()

        # Always update timeline with new events
        self.query_one("#timeline-panel", TimelinePanel).load_events(
            self._collect_timeline_event(event)
        )

    def _collect_timeline_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Append event to the timeline scroll and return all events for reload."""
        from codehive.clients.terminal.widgets.timeline import (
            EventRow,
            _TimelineEmpty,
        )

        scroll = self.query_one("#timeline-panel").query_one("#timeline-scroll", VerticalScroll)
        # Remove empty placeholder if present
        for placeholder in scroll.query(_TimelineEmpty):
            placeholder.remove()
        scroll.mount(
            EventRow(
                event_type=event.get("type", "unknown"),
                timestamp=event.get("timestamp", ""),
            )
        )
        return []  # We handled it inline

    @work(thread=True)
    def _reload_tasks(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            tasks = api.list_tasks(self._session_id)
        except Exception:
            tasks = []
        self.app.call_from_thread(
            self.query_one("#todo-panel", TodoPanel).load_tasks,
            tasks,
        )

    @work(thread=True)
    def _reload_diffs(self) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            diffs = api.get_diffs(self._session_id)
        except Exception:
            diffs = []
        self.app.call_from_thread(
            self.query_one("#files-panel", FilesPanel).load_diffs,
            diffs,
        )

    def on_chat_panel_message_submitted(self, event: ChatPanel.MessageSubmitted) -> None:
        """Handle user sending a chat message."""
        content = event.content
        # Optimistically show the message
        self.query_one("#chat-panel", ChatPanel).append_message("user", content)
        self._send_message(content)

    @work(thread=True)
    def _send_message(self, content: str) -> None:
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            api.post_message(self._session_id, content)
        except Exception:
            pass

    def action_go_back(self) -> None:
        if self._ws_client:
            self._ws_client.stop()
        self.app.pop_screen()

    def action_quit(self) -> None:
        if self._ws_client:
            self._ws_client.stop()
        self.app.exit()
