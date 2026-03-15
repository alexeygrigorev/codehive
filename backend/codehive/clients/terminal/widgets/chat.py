"""Chat panel widget: displays message history and input for sending messages."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static


_ROLE_STYLES: dict[str, str] = {
    "user": "bold cyan",
    "assistant": "bold green",
    "system": "bold yellow",
}


class ChatMessage(Static):
    """A single chat message with role label and content."""

    DEFAULT_CSS = """
    ChatMessage {
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, role: str, content: str, **kwargs: object) -> None:
        style = _ROLE_STYLES.get(role, "bold")
        markup = f"[{style}]{role}[/{style}]: {content}"
        super().__init__(markup, **kwargs)  # type: ignore[arg-type]


class _EmptyPlaceholder(Static):
    """Placeholder shown when there are no messages."""

    DEFAULT_CSS = """
    _EmptyPlaceholder {
        padding: 1;
        color: $text-muted;
    }
    """


class ChatPanel(Vertical):
    """Chat panel showing message history with an input field at the bottom."""

    DEFAULT_CSS = """
    ChatPanel {
        width: 2fr;
        height: 1fr;
        border: solid $primary;
        padding: 0;
    }
    #chat-title {
        padding: 0 1;
        text-style: bold;
        background: $primary-background;
    }
    #chat-scroll {
        height: 1fr;
    }
    #chat-input {
        dock: bottom;
    }
    """

    class MessageSubmitted(Message):
        """Posted when the user submits a chat message."""

        def __init__(self, content: str) -> None:
            super().__init__()
            self.content = content

    def compose(self) -> ComposeResult:
        yield Static("Chat", id="chat-title")
        yield VerticalScroll(
            _EmptyPlaceholder("No messages"),
            id="chat-scroll",
        )
        yield Input(placeholder="Type a message...", id="chat-input")

    def load_messages(self, messages: list[dict[str, Any]]) -> None:
        """Replace displayed messages with the given list."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.remove_children()
        if not messages:
            scroll.mount(_EmptyPlaceholder("No messages"))
            return
        for msg in messages:
            scroll.mount(
                ChatMessage(
                    role=msg.get("role", "unknown"),
                    content=msg.get("content", ""),
                )
            )

    def append_message(self, role: str, content: str) -> None:
        """Append a single message to the chat display."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        # Remove placeholder(s) if present
        for placeholder in scroll.query(_EmptyPlaceholder):
            placeholder.remove()
        scroll.mount(ChatMessage(role=role, content=content))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            event.input.value = ""
            self.post_message(self.MessageSubmitted(text))
