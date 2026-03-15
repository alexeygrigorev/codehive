"""Action timeline panel widget: displays session events chronologically."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static


class EventRow(Static):
    """A single event row showing type and timestamp."""

    DEFAULT_CSS = """
    EventRow {
        padding: 0 1;
    }
    """

    def __init__(self, event_type: str, timestamp: str, **kwargs: object) -> None:
        # Format timestamp for display (show time portion if ISO format)
        display_ts = timestamp
        if "T" in timestamp:
            display_ts = timestamp.split("T")[1][:8]  # HH:MM:SS
        markup = f"[bold]{display_ts}[/bold]  {event_type}"
        super().__init__(markup, **kwargs)  # type: ignore[arg-type]


class _TimelineEmpty(Static):
    """Placeholder for empty timeline."""

    DEFAULT_CSS = """
    _TimelineEmpty {
        padding: 1;
        color: $text-muted;
    }
    """


class TimelinePanel(Vertical):
    """Panel listing session events in chronological order."""

    DEFAULT_CSS = """
    TimelinePanel {
        height: 1fr;
        border: solid $primary;
    }
    #timeline-title {
        padding: 0 1;
        text-style: bold;
        background: $primary-background;
    }
    #timeline-scroll {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Timeline", id="timeline-title")
        yield VerticalScroll(
            _TimelineEmpty("No events"),
            id="timeline-scroll",
        )

    def load_events(self, events: list[dict[str, Any]]) -> None:
        """Replace displayed events with the given list (oldest first)."""
        scroll = self.query_one("#timeline-scroll", VerticalScroll)
        scroll.remove_children()
        if not events:
            scroll.mount(_TimelineEmpty("No events"))
            return
        # Sort chronologically (oldest first)
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
        for evt in sorted_events:
            scroll.mount(
                EventRow(
                    event_type=evt.get("type", "unknown"),
                    timestamp=evt.get("timestamp", ""),
                )
            )
