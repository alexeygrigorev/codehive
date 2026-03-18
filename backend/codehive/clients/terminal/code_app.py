"""Lightweight coding agent TUI — runs NativeEngine directly without the backend server."""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Header, Markdown, Static, TextArea

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


class _ChatInput(TextArea):
    """Multiline input area: Enter submits, Shift+Enter inserts newline.

    Compact when empty (3 lines), grows up to 5 lines, then scrolls internally.
    """

    _MIN_HEIGHT = 3
    _MAX_HEIGHT = 5

    DEFAULT_CSS = """
    _ChatInput {
        height: 3;
    }
    """

    class Submitted(Message):
        """Posted when the user presses Enter to submit text."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.show_line_numbers = False

    async def _on_key(self, event: events.Key) -> None:
        """Intercept Enter to submit; allow Shift+Enter for newlines."""
        if event.key == "enter":
            # Submit the text
            event.stop()
            event.prevent_default()
            text = self.text
            self.post_message(self.Submitted(text))
            return

        if event.key == "shift+enter":
            # Insert a newline character
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            self._resize_to_content()
            return

        # Let TextArea handle everything else
        await super()._on_key(event)
        # After any key, adjust height
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        """Adjust height based on line count, clamped to min/max."""
        line_count = self.document.line_count
        # Add 2 for TextArea chrome (border/padding)
        target = max(self._MIN_HEIGHT, min(line_count + 2, self._MAX_HEIGHT))
        self.styles.height = target

    def clear_input(self) -> None:
        """Clear the text and reset to compact size."""
        self.clear()
        self.styles.height = self._MIN_HEIGHT


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
        min-height: 3;
        max-height: 5;
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
        auto_approve: bool = False,
        backend_url: str | None = None,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._project_dir = Path(project_dir).resolve()
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._auto_approve = auto_approve
        self._always_approved: set[str] = set()
        self._approval_event: asyncio.Event = asyncio.Event()
        self._approval_result: str = ""
        self._session_id = session_id or uuid.uuid4()
        self._engine: Any = None
        self._busy = False
        self._streaming_widget: _AssistantMarkdown | None = None
        self._streaming_buffer: str = ""
        self._user_scrolled_up = False
        self._awaiting_approval = False
        self._backend_url: str | None = backend_url
        self._project_id: uuid.UUID | None = project_id
        self._last_history_timestamp: str = ""  # for deduplication with WebSocket
        self._ws_task: asyncio.Task | None = None  # type: ignore[type-arg]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="code-body"):
            yield VerticalScroll(id="code-scroll")
            yield Static(f"[dim]project: {self._project_dir}[/dim]", id="code-status")
            yield _ChatInput(id="code-input")
        yield Footer()

    async def on_mount(self) -> None:
        await self._init_engine()
        if self._backend_url is not None:
            await self._load_backend_session()
        else:
            self._append_system(f"Session started in {self._project_dir}")
        self.query_one("#code-input", _ChatInput).focus()

    async def _init_engine(self) -> None:
        if self._backend_url is not None:
            # Backend mode: no local engine needed
            self._engine = None
            return

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
            approval_callback=self._approval_callback,
        )
        await self._engine.create_session(self._session_id)

    # ---- Backend session loading ------------------------------------------

    async def _load_backend_session(self) -> None:
        """Load session status and transcript history from the backend.

        If the session is still executing, starts a WebSocket listener to
        stream live events after the historical entries.
        """
        import httpx as _httpx

        self._set_status("[dim]reconnected (loading history...)[/dim]")

        try:
            async with _httpx.AsyncClient(
                base_url=self._backend_url,  # type: ignore[arg-type]
                timeout=30.0,
            ) as client:
                # 1. Check session status
                status_resp = await client.get(f"/api/sessions/{self._session_id}")
                if status_resp.status_code != 200:
                    self._append_system(f"Session started in {self._project_dir}")
                    self._set_status(f"[dim]project: {self._project_dir}[/dim]")
                    return

                session_data = status_resp.json()
                session_status = session_data.get("status", "idle")

                # 2. Load transcript
                transcript_resp = await client.get(
                    f"/api/sessions/{self._session_id}/transcript",
                    params={"format": "json"},
                )
                if transcript_resp.status_code == 200:
                    transcript = transcript_resp.json()
                    entries = transcript.get("entries", [])
                    if entries:
                        self._render_transcript_entries(entries)
                        # Record last timestamp for deduplication
                        last = entries[-1]
                        self._last_history_timestamp = last.get("timestamp", "")
                        # Separator
                        self._append_system("--- reconnected ---")
                    else:
                        self._append_system(f"Session started in {self._project_dir}")
                else:
                    self._append_system(f"Session started in {self._project_dir}")

            # 3. If session is executing, connect WebSocket for live events
            if session_status == "executing":
                self._set_status("[dim]reconnected (catching up)[/dim]")
                self._busy = True
                inp = self.query_one("#code-input", _ChatInput)
                inp.disabled = True
                inp.read_only = True
                self._ws_task = asyncio.create_task(self._stream_ws_events())
            elif session_status == "failed":
                self._set_status("[bold red]session failed[/bold red]")
            else:
                self._set_status("[dim]idle[/dim]")

        except Exception as exc:
            self._append_system(f"Error loading session: {exc}")
            self._set_status(f"[dim]project: {self._project_dir}[/dim]")

    def _render_transcript_entries(self, entries: list[dict]) -> None:
        """Render historical transcript entries into the chat area."""
        for entry in entries:
            entry_type = entry.get("type", "")
            if entry_type == "message":
                role = entry.get("role", "system")
                content = entry.get("content", "")
                if not content:
                    continue
                if role == "user":
                    self._append_user(content)
                elif role == "assistant":
                    self._append_assistant(content)
                else:
                    self._append_system(content)
            elif entry_type == "tool_call":
                tool_name = entry.get("tool_name", "?")
                tool_input = entry.get("input", "")
                summary = tool_input[:100] if tool_input else "..."
                self._append_tool(tool_name, summary)

    async def _stream_ws_events(self) -> None:
        """Connect to the session WebSocket and render live events.

        Skips events that overlap with already-loaded history (deduplication
        by timestamp).
        """
        import json as _json

        try:
            import websockets  # type: ignore[import-untyped]
        except ImportError:
            # Fallback: poll session status instead
            self._append_system("WebSocket library not available, polling for completion...")
            await self._poll_session_status()
            return

        ws_url = self._backend_url or ""
        ws_url = ws_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/sessions/{self._session_id}/ws"

        try:
            async with websockets.connect(ws_url) as ws:
                self._set_status("[dim]connected (live)[/dim]")
                async for raw_msg in ws:
                    try:
                        event = _json.loads(raw_msg)
                    except (ValueError, TypeError):
                        continue

                    # Deduplication: skip events with timestamps <= last history entry
                    event_ts = event.get("created_at", "") or event.get("timestamp", "")
                    if (
                        event_ts
                        and self._last_history_timestamp
                        and event_ts <= self._last_history_timestamp
                    ):
                        continue

                    self._process_ws_event(event)
        except Exception:
            pass  # WebSocket closed or errored -- that's fine
        finally:
            self._busy = False
            self._streaming_widget = None
            self._streaming_buffer = ""
            self._set_status("[dim]idle[/dim]")
            inp = self.query_one("#code-input", _ChatInput)
            inp.disabled = False
            inp.read_only = False
            inp.focus()

    async def _poll_session_status(self) -> None:
        """Fallback: poll GET /api/sessions/{id} until status is no longer executing."""
        import httpx as _httpx

        try:
            async with _httpx.AsyncClient(
                base_url=self._backend_url,  # type: ignore[arg-type]
                timeout=10.0,
            ) as client:
                while True:
                    resp = await client.get(f"/api/sessions/{self._session_id}")
                    if resp.status_code == 200:
                        status = resp.json().get("status", "idle")
                        if status != "executing":
                            break
                    await asyncio.sleep(2.0)
        except Exception:
            pass
        finally:
            self._busy = False
            self._set_status("[dim]idle[/dim]")
            inp = self.query_one("#code-input", _ChatInput)
            inp.disabled = False
            inp.read_only = False
            inp.focus()

    def _process_ws_event(self, event: dict) -> None:
        """Process a single WebSocket event and render it in the UI."""
        etype = event.get("type", "")

        if etype == "message.delta" and event.get("role") == "assistant":
            content = event.get("content", "")
            if content:
                if self._streaming_widget is None:
                    self._start_streaming_widget()
                    self._set_status("[bold green]streaming...[/bold green]")
                self._append_streaming_delta(content)

        elif etype == "message.created" and event.get("role") == "assistant":
            content = event.get("content", "")
            if content:
                if self._streaming_widget is not None:
                    self._finalize_streaming(content)
                else:
                    self._append_assistant(content)

        elif etype == "tool.call.started":
            if self._streaming_widget is not None:
                self._finalize_streaming(self._streaming_buffer)
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

    # ---- Backend async message dispatch -----------------------------------

    async def _send_backend_message_async(self, message: str) -> None:
        """Send a message via the async dispatch endpoint and stream results via WebSocket."""
        import httpx as _httpx

        async with _httpx.AsyncClient(
            base_url=self._backend_url,  # type: ignore[arg-type]
            timeout=30.0,
        ) as client:
            resp = await client.post(
                f"/api/sessions/{self._session_id}/messages/async",
                json={"content": message},
            )
            if resp.status_code == 202:
                # Engine started -- connect WebSocket to stream events
                await self._stream_ws_events()
            elif resp.status_code == 409:
                self._append_system("Session already has a running engine task.")
            else:
                detail = ""
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                self._append_system(f"Error from backend (HTTP {resp.status_code}): {detail}")

    # ---- Approval callback ------------------------------------------------

    async def _approval_callback(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        """Called by NativeEngine before executing destructive tools.

        Returns True to proceed, False to reject.
        """
        # Auto-approve mode: skip all prompts
        if self._auto_approve:
            return True

        # Already approved for this tool type in this session
        if tool_name in self._always_approved:
            return True

        # Build detail string for the prompt
        if tool_name == "run_shell":
            detail = f"command: {tool_input.get('command', '?')}"
        elif tool_name == "edit_file":
            path = tool_input.get("path", "?")
            old = tool_input.get("old_string", "")
            new = tool_input.get("new_string", "")
            detail = f"file: {path}\n  old: {old[:120]}\n  new: {new[:120]}"
        elif tool_name == "git_commit":
            detail = f"message: {tool_input.get('message', '?')}"
        else:
            detail = str(tool_input)[:200]

        # Show the approval prompt in the chat area
        self._append_system(
            f"Approve {tool_name}?\n  {detail}\n[y]es / [n]o / [a]lways approve {tool_name}"
        )

        # Wait for user response via the approval event
        self._awaiting_approval = True
        self._approval_event.clear()
        self._approval_result = ""

        # Temporarily enable input so the user can respond
        inp = self.query_one("#code-input", _ChatInput)
        inp.disabled = False
        inp.read_only = False
        inp.focus()

        await self._approval_event.wait()

        self._awaiting_approval = False
        inp.disabled = True
        inp.read_only = True

        response = self._approval_result.strip().lower()
        if response in ("a", "always"):
            self._always_approved.add(tool_name)
            return True
        if response in ("y", "yes", ""):
            return True
        # Anything else (including "n", "no") is a rejection
        return False

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
            for cmd in (
                ["xclip", "-selection", "clipboard", "-o"],
                ["xsel", "--clipboard", "--output"],
                ["wl-paste"],
            ):
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        text = result.stdout
                        if text:
                            inp = self.query_one("#code-input", _ChatInput)
                            inp.insert(text)
                            inp._resize_to_content()
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
        self._always_approved = set()

        if self._backend_url is not None and self._project_id is not None:
            # Backend mode: create a new session via the API
            import httpx as _httpx

            try:
                async with _httpx.AsyncClient(base_url=self._backend_url, timeout=30.0) as client:
                    resp = await client.post(
                        f"/api/projects/{self._project_id}/sessions",
                        json={
                            "name": "code-session",
                            "engine": "native",
                            "mode": "execution",
                        },
                    )
                    if resp.status_code in (200, 201):
                        self._session_id = uuid.UUID(resp.json()["id"])
                    else:
                        self._append_system(
                            f"Failed to create new session (HTTP {resp.status_code})"
                        )
                        return
            except Exception as exc:
                self._append_system(f"Error creating session: {exc}")
                return
        else:
            self._session_id = uuid.uuid4()
            if self._engine is not None:
                await self._engine.create_session(self._session_id)

        self._append_system(f"New session started in {self._project_dir}")
        self._set_status(f"[dim]project: {self._project_dir}[/dim]")

    # ---- Backend message sending ------------------------------------------

    async def _send_backend_message(self, message: str) -> Any:
        """Send a message to the backend API and yield events from the response."""
        import httpx as _httpx

        async with _httpx.AsyncClient(
            base_url=self._backend_url,  # type: ignore[arg-type]
            timeout=300.0,
        ) as client:
            resp = await client.post(
                f"/api/sessions/{self._session_id}/messages",
                json={"content": message},
            )
            if resp.status_code != 200:
                detail = ""
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                yield {
                    "type": "message.created",
                    "role": "assistant",
                    "content": f"Error from backend (HTTP {resp.status_code}): {detail}",
                }
                return

            events = resp.json()
            for event in events:
                yield event

    # ---- Event handling ---------------------------------------------------

    async def on__chat_input_submitted(self, event: _ChatInput.Submitted) -> None:
        text = event.value.strip()
        inp = self.query_one("#code-input", _ChatInput)
        if not text:
            inp.clear_input()
            return
        inp.clear_input()

        # If we are waiting for an approval response, route it there
        if self._awaiting_approval:
            self._approval_result = text
            self._approval_event.set()
            return

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
        inp.disabled = True
        inp.read_only = True

        self.run_worker(self._run_agent(text), exclusive=True)

    async def _run_agent(self, message: str) -> None:
        """Run the engine conversation loop and push events to the UI."""
        t_start = time.monotonic()
        received_deltas = False
        try:
            if self._backend_url is not None:
                # Use async dispatch + WebSocket so engine survives TUI disconnect
                await self._send_backend_message_async(message)
                return
            else:
                event_iter = self._engine.send_message(self._session_id, message)
            async for event in event_iter:
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
            inp = self.query_one("#code-input", _ChatInput)
            inp.disabled = False
            inp.read_only = False
            inp.focus()


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
