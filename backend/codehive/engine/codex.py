"""Codex engine: OpenAI Responses API conversation loop with tool use."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from codehive.core.compaction import (
    ContextCompactor,
    create_openai_summarizer,
    should_compact,
)
from codehive.core.events import EventBus
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner

logger = logging.getLogger(__name__)

# Default model for the Codex engine
DEFAULT_MODEL = "codex-mini-latest"

# ---------------------------------------------------------------------------
# Tool definitions in Anthropic format (canonical Codehive format).
# We convert these to OpenAI function-calling format at runtime.
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS_ANTHROPIC: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace the first occurrence of old_text with new_text in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root.",
                },
                "old_text": {"type": "string", "description": "Text to find."},
                "new_text": {"type": "string", "description": "Text to replace it with."},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "run_shell",
        "description": "Run a shell command in the project working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "working_dir": {
                    "type": "string",
                    "description": "Working directory (defaults to project root).",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage all changes and commit with the given message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message."},
            },
            "required": ["message"],
        },
    },
    {
        "name": "search_files",
        "description": "List files matching a glob pattern in the project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g. '**/*.py').",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (defaults to project root).",
                },
            },
            "required": ["pattern"],
        },
    },
]


def convert_tool_to_openai(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a Codehive/Anthropic tool definition to OpenAI function-calling format.

    Anthropic format:
        {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI format:
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def get_openai_tools() -> list[dict[str, Any]]:
    """Return all tool definitions in OpenAI function-calling format."""
    return [convert_tool_to_openai(t) for t in TOOL_DEFINITIONS_ANTHROPIC]


class _SessionState:
    """Internal per-session state for Codex engine."""

    def __init__(self) -> None:
        self.input: list[dict[str, Any]] = []
        self.paused: bool = False


class CodexEngine:
    """Engine adapter using the OpenAI Responses API for LLM conversations.

    Implements the EngineAdapter protocol.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        event_bus: EventBus,
        file_ops: FileOps,
        shell_runner: ShellRunner,
        git_ops: GitOps,
        diff_service: DiffService,
        *,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._client = client
        self._event_bus = event_bus
        self._file_ops = file_ops
        self._shell_runner = shell_runner
        self._git_ops = git_ops
        self._diff_service = diff_service
        self._model = model
        self._sessions: dict[uuid.UUID, _SessionState] = {}

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return the list of OpenAI tool schemas."""
        return get_openai_tools()

    # ------------------------------------------------------------------
    # EngineAdapter interface
    # ------------------------------------------------------------------

    async def create_session(self, session_id: uuid.UUID) -> None:
        """Initialise internal state for a new session."""
        self._sessions[session_id] = _SessionState()

    async def send_message(
        self,
        session_id: uuid.UUID,
        message: str,
        *,
        db: Any = None,
        mode: str | None = None,
        role: Any = None,
    ) -> AsyncIterator[dict]:
        """Send a user message and run the conversation loop.

        Yields event dicts for every message exchange and tool call.
        """
        state = self._sessions.get(session_id)
        if state is None:
            state = _SessionState()
            self._sessions[session_id] = state

        # Check if paused before starting
        if state.paused:
            yield {"type": "session.paused", "session_id": str(session_id)}
            return

        # Add the user message to the input
        state.input.append({"role": "user", "content": message})

        # Emit user message event
        if db is not None and self._event_bus is not None:
            await self._event_bus.publish(
                db,
                session_id,
                "message.created",
                {"role": "user", "content": message},
            )
        yield {
            "type": "message.created",
            "role": "user",
            "content": message,
            "session_id": str(session_id),
        }

        tools = get_openai_tools()

        # Conversation loop
        while True:
            if state.paused:
                yield {"type": "session.paused", "session_id": str(session_id)}
                return

            # Call OpenAI Responses API with streaming
            text_content = ""
            function_calls: list[dict[str, Any]] = []
            last_input_tokens: int = 0

            stream = await self._client.responses.create(
                model=self._model,
                input=state.input,
                tools=tools,
                stream=True,
            )

            async for event in stream:
                event_type = getattr(event, "type", None)

                # Collect streaming text deltas
                if event_type == "response.output_text.delta":
                    delta_text = getattr(event, "delta", "")
                    if delta_text:
                        text_content += delta_text
                        delta_event = {
                            "type": "message.delta",
                            "role": "assistant",
                            "content": delta_text,
                            "session_id": str(session_id),
                        }
                        if db is not None and self._event_bus is not None:
                            await self._event_bus.publish(
                                db,
                                session_id,
                                "message.delta",
                                {"role": "assistant", "content": delta_text},
                            )
                        yield delta_event

                # Collect function call items from completed response
                elif event_type == "response.completed":
                    response = getattr(event, "response", None)
                    if response is not None:
                        # Record usage
                        usage = getattr(response, "usage", None)
                        if db is not None and usage is not None:
                            try:
                                from codehive.db.models import UsageRecord

                                usage_record = UsageRecord(
                                    session_id=session_id,
                                    model=getattr(response, "model", None) or self._model,
                                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                                )
                                db.add(usage_record)
                                await db.commit()
                            except Exception as exc:
                                logger.warning(
                                    "Failed to record usage for session %s: %s",
                                    session_id,
                                    exc,
                                )

                        if usage is not None:
                            last_input_tokens = getattr(usage, "input_tokens", 0) or 0

                        # Extract function call items from output
                        output_items = getattr(response, "output", []) or []
                        for item in output_items:
                            item_type = getattr(item, "type", None)
                            if item_type == "function_call":
                                function_calls.append(
                                    {
                                        "call_id": getattr(item, "call_id", ""),
                                        "name": getattr(item, "name", ""),
                                        "arguments": getattr(item, "arguments", "{}"),
                                    }
                                )

            # Check if compaction is needed
            if db is not None and last_input_tokens > 0:
                try:
                    from codehive.core.usage import get_context_window
                    from codehive.db.models import Session as SessionModel

                    session_row = await db.get(SessionModel, session_id)
                    config = (session_row.config or {}) if session_row is not None else {}
                    threshold = config.get("compaction_threshold", 0.80)
                    compaction_enabled = config.get("compaction_enabled", True)
                    preserve_last_n = config.get("compaction_preserve_last_n", 4)

                    context_window = get_context_window(self._model)

                    if compaction_enabled and should_compact(
                        last_input_tokens, context_window, threshold
                    ):
                        summarize_fn = await create_openai_summarizer(self._client)
                        compactor = ContextCompactor(summarize_fn)
                        compact_result = await compactor.compact(
                            state.input,
                            model=self._model,
                            preserve_last_n=preserve_last_n,
                        )
                        if compact_result.compacted:
                            state.input = compact_result.messages
                            # Emit compaction event
                            if self._event_bus is not None:
                                await self._event_bus.publish(
                                    db,
                                    session_id,
                                    "context.compacted",
                                    {
                                        "messages_compacted": compact_result.messages_compacted,
                                        "messages_preserved": compact_result.messages_preserved,
                                        "summary_length": len(compact_result.summary_text),
                                        "threshold_percent": round(
                                            (last_input_tokens / context_window) * 100,
                                            1,
                                        ),
                                        "summary_text": compact_result.summary_text,
                                    },
                                )
                            yield {
                                "type": "context.compacted",
                                "messages_compacted": compact_result.messages_compacted,
                                "messages_preserved": compact_result.messages_preserved,
                                "session_id": str(session_id),
                            }
                except Exception as exc:
                    logger.warning(
                        "Compaction check failed for session %s: %s",
                        session_id,
                        exc,
                    )

            # If there are function calls, execute them
            if function_calls:
                # Add assistant output items to the input for context
                for fc in function_calls:
                    state.input.append(
                        {
                            "type": "function_call",
                            "call_id": fc["call_id"],
                            "name": fc["name"],
                            "arguments": fc["arguments"],
                        }
                    )

                for fc in function_calls:
                    tool_name = fc["name"]
                    try:
                        tool_input = json.loads(fc["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        tool_input = {}

                    # Emit tool.call.started
                    started_event = {
                        "type": "tool.call.started",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_use_id": fc["call_id"],
                        "session_id": str(session_id),
                    }
                    if db is not None and self._event_bus is not None:
                        await self._event_bus.publish(
                            db,
                            session_id,
                            "tool.call.started",
                            {
                                "tool_name": tool_name,
                                "tool_input": tool_input,
                                "tool_use_id": fc["call_id"],
                            },
                        )
                    yield started_event

                    # Execute the tool
                    result = await self._execute_tool(tool_name, tool_input)

                    # Emit tool.call.finished
                    finished_event = {
                        "type": "tool.call.finished",
                        "tool_name": tool_name,
                        "tool_use_id": fc["call_id"],
                        "result": result,
                        "session_id": str(session_id),
                    }
                    if db is not None and self._event_bus is not None:
                        await self._event_bus.publish(
                            db,
                            session_id,
                            "tool.call.finished",
                            {
                                "tool_name": tool_name,
                                "tool_use_id": fc["call_id"],
                                "result": result,
                            },
                        )
                    yield finished_event

                    # Add function call output to input
                    state.input.append(
                        {
                            "type": "function_call_output",
                            "call_id": fc["call_id"],
                            "output": result["content"],
                        }
                    )

                # Continue the loop for the next API call
                continue

            # No function calls -- final text response
            if text_content:
                state.input.append(
                    {
                        "role": "assistant",
                        "content": text_content,
                    }
                )

            assistant_event = {
                "type": "message.created",
                "role": "assistant",
                "content": text_content,
                "session_id": str(session_id),
            }
            if db is not None and self._event_bus is not None:
                await self._event_bus.publish(
                    db,
                    session_id,
                    "message.created",
                    {"role": "assistant", "content": text_content},
                )
            yield assistant_event
            return

    async def start_task(
        self,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        *,
        db: Any = None,
        task_instructions: str | None = None,
    ) -> AsyncIterator[dict]:
        """Feed task instructions into send_message."""
        if task_instructions is None:
            task_instructions = f"Execute task {task_id}"

        async for event in self.send_message(session_id, task_instructions, db=db):
            yield event

    async def pause(self, session_id: uuid.UUID) -> None:
        """Set the pause flag for the session."""
        state = self._sessions.get(session_id)
        if state is None:
            state = _SessionState()
            self._sessions[session_id] = state
        state.paused = True

    async def resume(self, session_id: uuid.UUID) -> None:
        """Clear the pause flag for the session."""
        state = self._sessions.get(session_id)
        if state is not None:
            state.paused = False

    async def approve_action(self, session_id: uuid.UUID, action_id: str) -> dict[str, Any] | None:
        """Approve a pending action (not yet implemented for Codex)."""
        return None

    async def reject_action(
        self, session_id: uuid.UUID, action_id: str, *, reason: str = ""
    ) -> dict[str, Any] | None:
        """Reject a pending action (not yet implemented for Codex)."""
        return None

    async def get_diff(self, session_id: uuid.UUID) -> dict[str, str]:
        """Return the accumulated diff for the session via DiffService."""
        return self._diff_service.get_session_changes(str(session_id))

    # ------------------------------------------------------------------
    # Internal tool dispatch
    # ------------------------------------------------------------------

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch a tool call to the appropriate execution layer component.

        Returns a dict with ``content`` (str) and optionally ``is_error`` (bool).
        """
        try:
            if tool_name == "read_file":
                content = await self._file_ops.read_file(tool_input["path"])
                return {"content": content}

            elif tool_name == "edit_file":
                result = await self._file_ops.edit_file(
                    tool_input["path"],
                    tool_input["old_text"],
                    tool_input["new_text"],
                )
                return {"content": result}

            elif tool_name == "run_shell":
                from pathlib import Path

                working_dir = Path(tool_input.get("working_dir", "."))
                if not working_dir.is_absolute():
                    working_dir = self._file_ops._root / working_dir
                shell_result = await self._shell_runner.run(
                    tool_input["command"],
                    working_dir=working_dir,
                )
                output = shell_result.stdout
                if shell_result.stderr:
                    output += f"\nSTDERR:\n{shell_result.stderr}"
                if shell_result.timed_out:
                    output += "\n[TIMED OUT]"
                return {
                    "content": json.dumps(
                        {
                            "exit_code": shell_result.exit_code,
                            "stdout": shell_result.stdout,
                            "stderr": shell_result.stderr,
                            "timed_out": shell_result.timed_out,
                        }
                    )
                }

            elif tool_name == "git_commit":
                sha = await self._git_ops.commit(tool_input["message"])
                return {"content": f"Committed: {sha}"}

            elif tool_name == "search_files":
                path = tool_input.get("path", ".")
                files = await self._file_ops.list_files(path, tool_input["pattern"])
                return {"content": json.dumps(files)}

            else:
                return {"content": f"Unknown tool: {tool_name}", "is_error": True}

        except Exception as exc:
            return {"content": f"Error: {type(exc).__name__}: {exc}", "is_error": True}
