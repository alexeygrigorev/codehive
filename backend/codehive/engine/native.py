"""Native engine: Anthropic SDK conversation loop with tool use."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from codehive.core.checkpoint import create_checkpoint
from codehive.core.events import EventBus
from codehive.core.subagent import SubAgentManager
from codehive.core.modes import (
    VALID_MODES,
    ModeNotFoundError,
    build_mode_system_prompt,
    filter_tools_for_mode,
    get_mode,
)
from codehive.core.roles import (
    RoleDefinition,
    RoleNotFoundError,
    build_role_system_prompt,
    filter_tools_for_role,
    load_role,
)
from codehive.engine.orchestrator import (
    ORCHESTRATOR_ALLOWED_TOOLS,
    ORCHESTRATOR_SYSTEM_PROMPT,
    filter_tools,
)
from codehive.engine.tools.spawn_subagent import SPAWN_SUBAGENT_TOOL
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool-use schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
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
                "path": {"type": "string", "description": "File path relative to project root."},
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
    SPAWN_SUBAGENT_TOOL,
]

# Default model for the native engine
DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Tools that trigger an auto-checkpoint before execution
DESTRUCTIVE_TOOLS = {"edit_file", "run_shell", "git_commit"}

logger = logging.getLogger(__name__)


class _SessionState:
    """Internal per-session state."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.paused: bool = False
        self.pending_actions: dict[str, Any] = {}


class NativeEngine:
    """Engine adapter using the Anthropic SDK for LLM conversations.

    Implements the EngineAdapter protocol.
    """

    def __init__(
        self,
        client: AsyncAnthropic,
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
        self._task_fetcher: Any = None  # Optional callback for fetching tasks
        self._subagent_manager = SubAgentManager(event_bus=event_bus)

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return the list of Anthropic tool schemas."""
        return TOOL_DEFINITIONS

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
        role: str | RoleDefinition | None = None,
    ) -> AsyncIterator[dict]:
        """Send a user message and run the conversation loop.

        Yields event dicts for every message exchange and tool call.

        When *mode* is ``"orchestrator"``, the tool set is restricted to
        read-only and spawn tools, and the orchestrator system prompt is
        prepended.  Any tool call outside the allowed set is rejected with
        an error result.

        When *role* is provided (name string or RoleDefinition), tool
        filtering and system prompt injection are applied based on the
        role definition.  If both orchestrator mode and a role are active,
        the tool set is the intersection.
        """
        state = self._sessions.get(session_id)
        if state is None:
            state = _SessionState()
            self._sessions[session_id] = state

        is_orchestrator = mode == "orchestrator"
        is_agent_mode = mode is not None and mode in VALID_MODES

        # Resolve agent mode definition
        mode_def = None
        if is_agent_mode:
            try:
                mode_def = get_mode(mode)
            except ModeNotFoundError:
                logger.warning("Mode '%s' not found, ignoring", mode)

        # Resolve role definition
        role_def: RoleDefinition | None = None
        if isinstance(role, RoleDefinition):
            role_def = role
        elif isinstance(role, str):
            try:
                role_def = load_role(role)
            except RoleNotFoundError:
                logger.warning("Role '%s' not found, ignoring", role)

        # Resolve tool set based on mode and role
        tools: list[dict[str, Any]] = TOOL_DEFINITIONS
        if is_orchestrator:
            tools = filter_tools(tools)
        elif mode_def is not None:
            tools = filter_tools_for_mode(TOOL_DEFINITIONS, mode_def)
        if role_def is not None:
            role_filtered = filter_tools_for_role(TOOL_DEFINITIONS, role_def)
            if is_orchestrator or mode_def is not None:
                # Intersection: keep only tools that are in both sets
                current_names = {t["name"] for t in tools}
                role_names = {t["name"] for t in role_filtered}
                intersection = current_names & role_names
                tools = [t for t in TOOL_DEFINITIONS if t["name"] in intersection]
            else:
                tools = role_filtered

        # Check if paused before starting
        if state.paused:
            yield {"type": "session.paused", "session_id": str(session_id)}
            return

        # Add the user message to conversation history
        state.messages.append({"role": "user", "content": message})

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

        # Build API kwargs
        api_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "tools": tools,
            "messages": state.messages,
        }

        # Build system prompt from mode and/or role
        # Order: mode prompt first (cognitive frame), then role prompt (persona)
        system_parts: list[str] = []
        if is_orchestrator:
            system_parts.append(ORCHESTRATOR_SYSTEM_PROMPT)
        elif mode_def is not None:
            mode_prompt = build_mode_system_prompt(mode_def)
            if mode_prompt:
                system_parts.append(mode_prompt)
        if role_def is not None:
            role_prompt = build_role_system_prompt(role_def)
            if role_prompt:
                system_parts.append(role_prompt)
        if system_parts:
            api_kwargs["system"] = "\n\n".join(system_parts)

        # Conversation loop
        while True:
            if state.paused:
                yield {"type": "session.paused", "session_id": str(session_id)}
                return

            # Call Anthropic API
            response = await self._client.messages.create(**api_kwargs)

            # Process content blocks
            tool_use_blocks = []
            text_content = ""

            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            # If there are tool calls, execute them
            if tool_use_blocks:
                # Add the assistant response to history
                state.messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tool_block in tool_use_blocks:
                    # Emit tool.call.started
                    started_event = {
                        "type": "tool.call.started",
                        "tool_name": tool_block.name,
                        "tool_input": tool_block.input,
                        "tool_use_id": tool_block.id,
                        "session_id": str(session_id),
                    }
                    if db is not None and self._event_bus is not None:
                        await self._event_bus.publish(
                            db,
                            session_id,
                            "tool.call.started",
                            {
                                "tool_name": tool_block.name,
                                "tool_input": tool_block.input,
                                "tool_use_id": tool_block.id,
                            },
                        )
                    yield started_event

                    # Defensive: reject disallowed tools based on mode
                    allowed_tool_names = {t["name"] for t in tools}
                    if tool_block.name not in allowed_tool_names:
                        if is_orchestrator:
                            result = {
                                "content": (
                                    f"Tool '{tool_block.name}' is not available in "
                                    f"orchestrator mode. Allowed tools: "
                                    f"{', '.join(sorted(ORCHESTRATOR_ALLOWED_TOOLS))}"
                                ),
                                "is_error": True,
                            }
                        elif mode_def is not None:
                            result = {
                                "content": (
                                    f"Tool '{tool_block.name}' is not available in "
                                    f"'{mode}' mode. Allowed tools: "
                                    f"{', '.join(sorted(allowed_tool_names))}"
                                ),
                                "is_error": True,
                            }
                        else:
                            result = {
                                "content": (
                                    f"Tool '{tool_block.name}' is not available. "
                                    f"Allowed tools: "
                                    f"{', '.join(sorted(allowed_tool_names))}"
                                ),
                                "is_error": True,
                            }
                    else:
                        # Execute the tool
                        result = await self._execute_tool(
                            tool_block.name,
                            tool_block.input,
                            session_id=session_id,
                            db=db,
                        )

                    # Emit tool.call.finished
                    finished_event = {
                        "type": "tool.call.finished",
                        "tool_name": tool_block.name,
                        "tool_use_id": tool_block.id,
                        "result": result,
                        "session_id": str(session_id),
                    }
                    if db is not None and self._event_bus is not None:
                        await self._event_bus.publish(
                            db,
                            session_id,
                            "tool.call.finished",
                            {
                                "tool_name": tool_block.name,
                                "tool_use_id": tool_block.id,
                                "result": result,
                            },
                        )
                    yield finished_event

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": result["content"],
                            **({"is_error": True} if result.get("is_error") else {}),
                        }
                    )

                # Send tool results back to the model
                state.messages.append({"role": "user", "content": tool_results})

                # Continue the loop for the next API call
                continue

            # No tool calls -- final text response
            state.messages.append({"role": "assistant", "content": response.content})

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
        """Feed task instructions into send_message.

        If task_instructions is not provided, requires a task_fetcher callback
        to be set that retrieves task data by ID.
        """
        if task_instructions is None and self._task_fetcher is not None:
            task_data = await self._task_fetcher(task_id)
            task_instructions = task_data.get("instructions", "")
        elif task_instructions is None:
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

    async def approve_action(self, session_id: uuid.UUID, action_id: str) -> None:
        """Approve a pending action."""
        state = self._sessions.get(session_id)
        if state is not None and action_id in state.pending_actions:
            state.pending_actions[action_id]["approved"] = True

    async def reject_action(self, session_id: uuid.UUID, action_id: str) -> None:
        """Reject a pending action."""
        state = self._sessions.get(session_id)
        if state is not None and action_id in state.pending_actions:
            state.pending_actions[action_id]["rejected"] = True

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
        *,
        session_id: uuid.UUID | None = None,
        db: Any = None,
    ) -> dict[str, Any]:
        """Dispatch a tool call to the appropriate execution layer component.

        Returns a dict with ``content`` (str) and optionally ``is_error`` (bool).
        """
        # Auto-checkpoint before destructive tools (best-effort)
        if tool_name in DESTRUCTIVE_TOOLS and session_id is not None and db is not None:
            try:
                tool_desc = tool_name
                if tool_name == "edit_file" and "path" in tool_input:
                    tool_desc = f"{tool_name} {tool_input['path']}"
                elif tool_name == "run_shell" and "command" in tool_input:
                    cmd = tool_input["command"]
                    tool_desc = f"{tool_name} {cmd[:80]}"
                elif tool_name == "git_commit" and "message" in tool_input:
                    tool_desc = f"{tool_name} {tool_input['message'][:80]}"

                label = f"auto: before {tool_desc}"
                await create_checkpoint(
                    db,
                    self._git_ops,
                    session_id=session_id,
                    label=label,
                )
            except Exception as exc:
                logger.warning(
                    "Auto-checkpoint failed before %s (session %s): %s",
                    tool_name,
                    session_id,
                    exc,
                )

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

            elif tool_name == "spawn_subagent":
                if session_id is None or db is None:
                    return {
                        "content": "spawn_subagent requires an active session with DB access",
                        "is_error": True,
                    }
                result = await self._subagent_manager.spawn_subagent(
                    db,
                    parent_session_id=session_id,
                    mission=tool_input["mission"],
                    role=tool_input["role"],
                    scope=tool_input["scope"],
                    config=tool_input.get("config"),
                )
                return {"content": json.dumps(result)}

            else:
                return {"content": f"Unknown tool: {tool_name}", "is_error": True}

        except Exception as exc:
            return {"content": f"Error: {type(exc).__name__}: {exc}", "is_error": True}
