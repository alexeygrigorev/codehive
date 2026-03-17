"""Lightweight coding agent TUI — runs NativeEngine directly without the backend server."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Static

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
        ("ctrl+c", "quit", "Quit"),
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

        from codehive.engine.native import DEFAULT_MODEL

        model = self._model or DEFAULT_MODEL

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

    def _append_system(self, text: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ChatBubble("system", text))
        scroll.scroll_end(animate=False)

    def _append_user(self, text: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ChatBubble("user", text))
        scroll.scroll_end(animate=False)

    def _append_assistant(self, text: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ChatBubble("assistant", text))
        scroll.scroll_end(animate=False)

    def _append_tool(self, tool_name: str, summary: str) -> None:
        scroll = self.query_one("#code-scroll", VerticalScroll)
        scroll.mount(_ToolCallBubble(tool_name, summary))
        scroll.scroll_end(animate=False)

    def _set_status(self, text: str) -> None:
        self.query_one("#code-status", Static).update(text)

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
        self._busy = True
        self._set_status("[bold yellow]thinking...[/bold yellow]")
        self.query_one("#code-input", Input).disabled = True

        self.run_worker(self._run_agent(text), exclusive=True)

    async def _run_agent(self, message: str) -> None:
        """Run the engine conversation loop and push events to the UI."""
        try:
            async for event in self._engine.send_message(self._session_id, message):
                etype = event.get("type", "")

                if etype == "message.created" and event.get("role") == "assistant":
                    content = event.get("content", "")
                    if content:
                        self._append_assistant(content)

                elif etype == "tool.call.started":
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
            self._busy = False
            self._set_status(f"[dim]project: {self._project_dir}[/dim]")
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
