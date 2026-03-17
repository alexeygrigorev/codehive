"""Lightweight coding agent TUI — runs NativeEngine directly without the backend server."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Markdown, Static

# ---------------------------------------------------------------------------
# No-op EventBus for standalone mode (no Redis / DB required)
# ---------------------------------------------------------------------------


class _NoOpEventBus:
    """EventBus stub that discards events — used when running without backend."""

    async def publish(self, db: Any, session_id: uuid.UUID, event_type: str, data: dict) -> None:  # noqa: ARG002
        pass


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


_ROLE_STYLES: dict[str, str] = {
    "user": "bold cyan",
    "assistant": "bold green",
    "system": "bold yellow",
    "tool": "bold magenta",
}


class _ChatBubble(Static):
    DEFAULT_CSS = """
    _ChatBubble {
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, role: str, content: str, **kwargs: object) -> None:
        style = _ROLE_STYLES.get(role, "bold")
        # Escape markup characters in content to avoid Textual Rich parsing issues
        safe = content.replace("[", "\\[")
        markup = f"[{style}]{role}[/{style}]: {safe}"
        super().__init__(markup, **kwargs)  # type: ignore[arg-type]


class _ToolCallBubble(Static):
    DEFAULT_CSS = """
    _ToolCallBubble {
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, tool_name: str, summary: str, **kwargs: object) -> None:
        markup = f"[bold magenta]tool[/bold magenta] [dim]{tool_name}[/dim]: {summary}"
        super().__init__(markup, **kwargs)  # type: ignore[arg-type]


class _AssistantMarkdown(Markdown):
    """Markdown widget for assistant messages with appropriate styling.

    On every resize (which happens when Markdown re-renders its content),
    scrolls the parent VerticalScroll to the bottom.
    """

    DEFAULT_CSS = """
    _AssistantMarkdown {
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def on_resize(self) -> None:
        """After Markdown content is laid out, scroll parent to bottom."""
        app = self.app
        if isinstance(app, CodeApp) and not app._user_scrolled_up:
            scroll = app.query_one("#code-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


class CodeApp(App):
    """Standalone coding agent session."""

    TITLE = "Codehive"
    SUB_TITLE = "Code"

    DEFAULT_CSS = """
    #code-scroll {
        height: 1fr;
    }
    #code-input {
        dock: bottom;
    }
    #code-status {
        dock: bottom;
        height: 1;
        background: $primary-background;
        padding: 0 1;
    }
    #code-body {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+l", "clear_chat", "Clear"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+v", "paste", "Paste"),
    ]

    def __init__(
        self,
        project_dir: str,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._project_dir = Path(project_dir).resolve()
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._session_id = uuid.uuid4()
        self._engine: Any = None
        self._busy = False
        self._streaming_widget: _AssistantMarkdown | None = None
        self._streaming_buffer: str = ""
        self._user_scrolled_up = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="code-body"):
            yield VerticalScroll(id="code-scroll")
            yield Static(f"[dim]project: {self._project_dir}[/dim]", id="code-status")
            yield Input(placeholder="Ask the agent anything...", id="code-input")
        yield Footer()

    async def on_mount(self) -> None:
        await self._init_engine()
        self._append_system(f"Session started in {self._project_dir}")
        self.query_one("#code-input", Input).focus()

    async def _init_engine(self) -> None:
        from codehive.engine.native import NativeEngine
        from codehive.execution.diff import DiffService
        from codehive.execution.file_ops import FileOps
        from codehive.execution.git_ops import GitOps
        from codehive.execution.shell import ShellRunner

        # Build Anthropic client
        client_kwargs: dict[str, Any] = {}
        if self._api_key:
            client_kwargs["api_key"] = self._api_key
        if self._base_url:
            client_kwargs["base_url"] = self._base_url
        client = AsyncAnthropic(**client_kwargs)

        from codehive.config import Settings as _Settings
        from codehive.engine.native import DEFAULT_MODEL

        try:
            _settings = _Settings()
            default_model = _settings.default_model or DEFAULT_MODEL
        except Exception:
            default_model = DEFAULT_MODEL

        model = self._model or default_model

        self._engine = NativeEngine(
            client=client,
            event_bus=_NoOpEventBus(),  # type: ignore[arg-type]
            file_ops=FileOps(project_root=self._project_dir),
            shell_runner=ShellRunner(),
            git_ops=GitOps(repo_path=self._project_dir),
            diff_service=DiffService(),
            model=model,
        )
        await self._engine.create_session(self._session_id)

    # ---- UI helpers -------------------------------------------------------

    def on_vertical_scroll_scroll_up(self) -> None:
        """User scrolled up manually — stop auto-scrolling."""
        self._user_scrolled_up = True

    def _auto_scroll(self) -> None:
        """Scroll to bottom unless the user has scrolled up.

        Defers the scroll to after the next layout refresh so that
        newly mounted or updated widgets have their correct size.
        """
        if not self._user_scrolled_up:
            self.call_after_refresh(self._do_scroll_end)

    def _do_scroll_end(self) -> None:
        """Actually perform the scroll — called after layout refresh."""
        self.query_one("#code-scroll", VerticalScroll).scroll_end(animate=False)

    def _append_system(self, text: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ChatBubble("system", text))
        self._auto_scroll()

    def _append_user(self, text: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ChatBubble("user", text))
        # Always scroll to bottom on user message and re-enable auto-scroll
        self._user_scrolled_up = False
        self.call_after_refresh(self._do_scroll_end)

    def _append_assistant(self, text: str) -> None:
        """Mount a final assistant message as a Markdown widget."""
        scroll = self.query_one("#code-scroll", VerticalScroll)
        widget = _AssistantMarkdown(text)
        scroll.mount(widget)
        self._auto_scroll()

    def _append_tool(self, tool_name: str, summary: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ToolCallBubble(tool_name, summary))
        self._auto_scroll()

    def _set_status(self, text: str) -> None:
        self.query_one("#code-status", Static).update(text)

    def _start_streaming_widget(self) -> None:
        """Create a new Markdown widget for streaming assistant output."""
        self._streaming_buffer = ""
        self._streaming_widget = _AssistantMarkdown("")
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(self._streaming_widget)
        self._auto_scroll()

    def _append_streaming_delta(self, text: str) -> None:
        """Append text to the current streaming widget."""
        self._streaming_buffer += text
        if self._streaming_widget is not None:
            self._streaming_widget.update(self._streaming_buffer)
            self._auto_scroll()

    def _finalize_streaming(self, full_text: str) -> None:
        """Finalize the streaming widget with the complete text."""
        if self._streaming_widget is not None:
            self._streaming_widget.update(full_text)
            self._streaming_widget = None
            self._streaming_buffer = ""
            self._auto_scroll()

    # ---- Actions ----------------------------------------------------------

    def action_paste(self) -> None:
        """Paste from system clipboard into the input field."""
        import subprocess

        try:
            # Try xclip first (X11), then xsel, then wl-paste (Wayland)
            for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"], ["wl-paste"]):
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        text = result.stdout
                        if text:
                            inp = self.query_one("#code-input", Input)
                            inp.insert_text_at_cursor(text)
                        return
                except FileNotFoundError:
                    continue
        except Exception:
            pass

    def action_clear_chat(self) -> None:
        """Clear the chat scroll area."""
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.remove_children()

    async def action_new_session(self) -> None:
        """Start a new session -- reset engine state and clear the UI."""
        self.action_clear_chat()
        self._session_id = uuid.uuid4()
        if self._engine is not None:
            await self._engine.create_session(self._session_id)
        self._append_system(f"New session started in {self._project_dir}")
        self._set_status(f"[dim]project: {self._project_dir}[/dim]")

    # ---- Event handling ---------------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        if text in ("/quit", "/exit"):
            self.exit()
            return

        if self._busy:
            self._append_system("Agent is thinking... please wait.")
            return

        self._append_user(text)
        self._user_scrolled_up = False
        self._busy = True
        self._set_status("[bold yellow]thinking...[/bold yellow]")
        self.query_one("#code-input", Input).disabled = True

        self.run_worker(self._run_agent(text), exclusive=True)

    async def _run_agent(self, message: str) -> None:
        """Run the engine conversation loop and push events to the UI."""
        t_start = time.monotonic()
        received_deltas = False
        try:
            async for event in self._engine.send_message(self._session_id, message):
                etype = event.get("type", "")

                if etype == "message.delta" and event.get("role") == "assistant":
                    content = event.get("content", "")
                    if content:
                        if not received_deltas:
                            received_deltas = True
                            self._start_streaming_widget()
                            self._set_status("[bold green]streaming...[/bold green]")
                        self._append_streaming_delta(content)

                elif etype == "message.created" and event.get("role") == "assistant":
                    content = event.get("content", "")
                    if content:
                        if received_deltas:
                            # Finalize the streaming widget with complete text
                            self._finalize_streaming(content)
                            received_deltas = False
                        else:
                            # No deltas were received -- fallback
                            self._append_assistant(content)

                elif etype == "tool.call.started":
                    # Finalize any in-progress streaming before tool calls
                    if received_deltas and self._streaming_widget is not None:
                        self._finalize_streaming(self._streaming_buffer)
                        received_deltas = False
                    tool_name = event.get("tool_name", "?")
                    tool_input = event.get("tool_input", {})
                    summary = _tool_summary(tool_name, tool_input)
                    self._append_tool(tool_name, summary)
                    self._set_status(f"[bold magenta]running {tool_name}...[/bold magenta]")

                elif etype == "tool.call.finished":
                    tool_name = event.get("tool_name", "?")
                    result = event.get("result", {})
                    is_error = result.get("is_error", False)
                    if is_error:
                        content = result.get("content", "")[:200]
                        self._append_tool(tool_name, f"[red]error: {content}[/red]")

        except Exception as exc:
            self._append_system(f"Error: {type(exc).__name__}: {exc}")
        finally:
            elapsed = time.monotonic() - t_start
            self._busy = False
            self._streaming_widget = None
            self._streaming_buffer = ""
            self._set_status(f"[dim]Done in {elapsed:.1f}s | project: {self._project_dir}[/dim]")
            self.query_one("#code-input", Input).disabled = False
            self.query_one("#code-input", Input).focus()


def _tool_summary(tool_name: str, tool_input: dict) -> str:
    """Create a short one-line summary of a tool call."""
    if tool_name == "read_file":
        return tool_input.get("path", "?")
    elif tool_name == "edit_file":
        return tool_input.get("path", "?")
    elif tool_name == "run_shell":
        cmd = tool_input.get("command", "?")
        return cmd[:120]
    elif tool_name == "git_commit":
        return tool_input.get("message", "?")[:80]
    elif tool_name == "search_files":
        return tool_input.get("pattern", "?")
    else:
        return str(tool_input)[:100]
