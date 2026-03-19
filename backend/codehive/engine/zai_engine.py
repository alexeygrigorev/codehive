"""Z.ai engine: Anthropic-compatible SDK conversation loop."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator, Callable

from anthropic import AsyncAnthropic

from codehive.core.compaction import (
    ContextCompactor,
    create_anthropic_summarizer,
    should_compact,
)
from codehive.core.knowledge import build_knowledge_context
from codehive.core.approval import (
    ApprovalPolicy,
    check_action,
    create_approval_request,
    get_default_policy,
    resolve_request as resolve_approval_request,
)
from codehive.core.checkpoint import create_checkpoint
from codehive.core.agent_comm import AgentCommService
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
from codehive.engine.tools.get_subsession_result import GET_SUBSESSION_RESULT_TOOL
from codehive.engine.tools.list_subsessions import LIST_SUBSESSIONS_TOOL
from codehive.engine.tools.query_agent import QUERY_AGENT_TOOL
from codehive.engine.tools.send_to_agent import SEND_TO_AGENT_TOOL
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
    QUERY_AGENT_TOOL,
    SEND_TO_AGENT_TOOL,
    GET_SUBSESSION_RESULT_TOOL,
    LIST_SUBSESSIONS_TOOL,
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


class ZaiEngine:
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
        approval_callback: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self._client = client
        self._event_bus = event_bus
        self._file_ops = file_ops
        self._shell_runner = shell_runner
        self._git_ops = git_ops
        self._diff_service = diff_service
        self._model = model
        self._approval_callback = approval_callback
        self._sessions: dict[uuid.UUID, _SessionState] = {}
        self._task_fetcher: Any = None  # Optional callback for fetching tasks
        self._subagent_manager = SubAgentManager(
            event_bus=event_bus,
            engine_builder=self._build_child_engine,
        )
        self._agent_comm = AgentCommService(event_bus=event_bus)
        self._approval_policies: dict[uuid.UUID, ApprovalPolicy] = {}

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

        # Inject project knowledge context if available
        if db is not None:
            try:
                from codehive.db.models import Session as SessionModel

                session_row = await db.get(SessionModel, session_id)
                if session_row is not None:
                    from codehive.core.project import get_project

                    project = await get_project(db, session_row.project_id)
                    if project is not None and project.knowledge:
                        knowledge_block = build_knowledge_context(project.knowledge)
                        if knowledge_block:
                            system_parts.append(knowledge_block)
            except Exception as exc:
                logger.warning(
                    "Failed to load knowledge context for session %s: %s",
                    session_id,
                    exc,
                )

        if system_parts:
            api_kwargs["system"] = "\n\n".join(system_parts)

        # Conversation loop
        while True:
            if state.paused:
                yield {"type": "session.paused", "session_id": str(session_id)}
                return

            # Stream from Anthropic API
            text_content = ""
            async with self._client.messages.stream(**api_kwargs) as stream:
                async for text in stream.text_stream:
                    text_content += text
                    delta_event = {
                        "type": "message.delta",
                        "role": "assistant",
                        "content": text,
                        "session_id": str(session_id),
                    }
                    if db is not None and self._event_bus is not None:
                        await self._event_bus.publish(
                            db,
                            session_id,
                            "message.delta",
                            {"role": "assistant", "content": text},
                        )
                    yield delta_event

                response = await stream.get_final_message()

            # Record usage data
            if db is not None and hasattr(response, "usage") and response.usage:
                try:
                    from codehive.db.models import UsageRecord

                    usage_record = UsageRecord(
                        session_id=session_id,
                        model=response.model or self._model,
                        input_tokens=response.usage.input_tokens or 0,
                        output_tokens=response.usage.output_tokens or 0,
                    )
                    db.add(usage_record)
                    await db.commit()
                except Exception as exc:
                    logger.warning(
                        "Failed to record usage for session %s: %s",
                        session_id,
                        exc,
                    )

            # Check if compaction is needed
            if (
                db is not None
                and hasattr(response, "usage")
                and response.usage
                and response.usage.input_tokens
            ):
                try:
                    from codehive.core.usage import get_context_window
                    from codehive.db.models import Session as SessionModel

                    session_row = await db.get(SessionModel, session_id)
                    config = (session_row.config or {}) if session_row is not None else {}
                    threshold = config.get("compaction_threshold", 0.80)
                    compaction_enabled = config.get("compaction_enabled", True)
                    preserve_last_n = config.get("compaction_preserve_last_n", 4)

                    context_window = get_context_window(self._model)
                    input_tokens = response.usage.input_tokens

                    if compaction_enabled and should_compact(
                        input_tokens, context_window, threshold
                    ):
                        summarize_fn = await create_anthropic_summarizer(self._client)
                        compactor = ContextCompactor(summarize_fn)
                        result = await compactor.compact(
                            state.messages,
                            model=self._model,
                            preserve_last_n=preserve_last_n,
                        )
                        if result.compacted:
                            state.messages = result.messages
                            # Emit compaction event
                            if self._event_bus is not None:
                                await self._event_bus.publish(
                                    db,
                                    session_id,
                                    "context.compacted",
                                    {
                                        "messages_compacted": result.messages_compacted,
                                        "messages_preserved": result.messages_preserved,
                                        "summary_length": len(result.summary_text),
                                        "threshold_percent": round(
                                            (input_tokens / context_window) * 100, 1
                                        ),
                                        "summary_text": result.summary_text,
                                    },
                                )
                            yield {
                                "type": "context.compacted",
                                "messages_compacted": result.messages_compacted,
                                "messages_preserved": result.messages_preserved,
                                "session_id": str(session_id),
                            }
                except Exception as exc:
                    logger.warning(
                        "Compaction check failed for session %s: %s",
                        session_id,
                        exc,
                    )

            # Process content blocks for tool_use
            tool_use_blocks = []
            for block in response.content:
                if block.type == "tool_use":
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

    def get_approval_policy(self, session_id: uuid.UUID) -> ApprovalPolicy:
        """Return the approval policy for a session."""
        if session_id not in self._approval_policies:
            self._approval_policies[session_id] = get_default_policy()
        return self._approval_policies[session_id]

    def set_approval_policy(self, session_id: uuid.UUID, policy: ApprovalPolicy) -> None:
        """Set the approval policy for a session."""
        self._approval_policies[session_id] = policy

    async def approve_action(self, session_id: uuid.UUID, action_id: str) -> dict[str, Any] | None:
        """Approve a pending action and execute the deferred tool call.

        Returns the tool execution result, or None if action not found.
        """
        state = self._sessions.get(session_id)
        if state is None or action_id not in state.pending_actions:
            return None

        action = state.pending_actions[action_id]
        action["approved"] = True

        # Resolve the approval request if stored
        if "approval_request" in action:
            resolve_approval_request(action["approval_request"], approved=True)

        # Execute the deferred tool call
        result = await self._execute_tool_direct(
            action["tool_name"],
            action["tool_input"],
            session_id=session_id,
        )

        # Clean up
        del state.pending_actions[action_id]
        return result

    async def reject_action(
        self, session_id: uuid.UUID, action_id: str, *, reason: str = ""
    ) -> dict[str, Any] | None:
        """Reject a pending action.

        Returns an error result dict, or None if action not found.
        """
        state = self._sessions.get(session_id)
        if state is None or action_id not in state.pending_actions:
            return None

        action = state.pending_actions[action_id]
        action["rejected"] = True

        # Resolve the approval request if stored
        if "approval_request" in action:
            resolve_approval_request(action["approval_request"], approved=False)

        reason_text = f": {reason}" if reason else ""
        result: dict[str, Any] = {
            "content": f"Action rejected{reason_text}. Tool '{action['tool_name']}' was not executed.",
            "is_error": True,
        }

        # Clean up
        del state.pending_actions[action_id]
        return result

    async def get_diff(self, session_id: uuid.UUID) -> dict[str, str]:
        """Return the accumulated diff for the session via DiffService."""
        return self._diff_service.get_session_changes(str(session_id))

    @staticmethod
    async def _build_child_engine(session_config: dict[str, Any], engine_type: str) -> Any:
        """Build an engine for a child session using the shared factory."""
        from codehive.api.routes.sessions import _build_engine

        return await _build_engine(session_config, engine_type=engine_type)

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
        If the tool requires approval, returns a pending-approval result and
        emits an ``approval.required`` event.
        """
        # Check TUI-native approval callback for destructive tools
        if tool_name in DESTRUCTIVE_TOOLS and self._approval_callback is not None:
            approved = await self._approval_callback(tool_name, tool_input)
            if not approved:
                return {
                    "content": (f"Action rejected by user. Tool '{tool_name}' was not executed."),
                    "is_error": True,
                }
            # Callback approved -- skip DB-based approval, go straight to execution
            return await self._execute_tool_direct(
                tool_name, tool_input, session_id=session_id, db=db
            )

        # Check approval policy for destructive tools (DB-based path)
        if tool_name in DESTRUCTIVE_TOOLS and session_id is not None:
            policy = self.get_approval_policy(session_id)
            rule = check_action(policy, tool_name, tool_input)
            if rule is not None:
                # Create an approval request
                from codehive.api.routes.approvals import add_request

                approval_req = create_approval_request(
                    session_id=str(session_id),
                    tool_name=tool_name,
                    tool_input=tool_input,
                    rule=rule,
                )

                # Store in session state
                state = self._sessions.get(session_id)
                if state is None:
                    state = _SessionState()
                    self._sessions[session_id] = state
                state.pending_actions[approval_req.id] = {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "approved": False,
                    "rejected": False,
                    "approval_request": approval_req,
                }

                # Register in the API-level store
                add_request(approval_req)

                # Emit approval.required event
                event_data = {
                    "action_id": approval_req.id,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "description": rule.description,
                    "rule_id": rule.id,
                }
                if db is not None and self._event_bus is not None:
                    await self._event_bus.publish(
                        db,
                        session_id,
                        "approval.required",
                        event_data,
                    )

                return {
                    "content": (
                        f"Action requires approval: {rule.description}. "
                        f"Waiting for user confirmation."
                    ),
                    "is_pending_approval": True,
                }

        return await self._execute_tool_direct(tool_name, tool_input, session_id=session_id, db=db)

    async def _execute_tool_direct(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
        db: Any = None,
    ) -> dict[str, Any]:
        """Execute a tool call without approval checks.

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
                # Emit file.changed event for successful edits
                if session_id is not None and db is not None and self._event_bus is not None:
                    await self._event_bus.publish(
                        db,
                        session_id,
                        "file.changed",
                        {"path": tool_input["path"], "action": "edit"},
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
                # Emit terminal.output event
                if session_id is not None and db is not None and self._event_bus is not None:
                    await self._event_bus.publish(
                        db,
                        session_id,
                        "terminal.output",
                        {
                            "command": tool_input["command"],
                            "exit_code": shell_result.exit_code,
                            "stdout": shell_result.stdout[:10000],
                            "stderr": shell_result.stderr[:10000],
                        },
                    )
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
                try:
                    result = await self._subagent_manager.spawn_subagent(
                        db,
                        parent_session_id=session_id,
                        mission=tool_input["mission"],
                        role=tool_input["role"],
                        scope=tool_input["scope"],
                        engine=tool_input.get("engine"),
                        initial_message=tool_input.get("initial_message"),
                        config=tool_input.get("config"),
                    )
                except Exception as exc:
                    return {"content": str(exc), "is_error": True}
                return {"content": json.dumps(result)}

            elif tool_name == "query_agent":
                if session_id is None or db is None:
                    return {
                        "content": "query_agent requires an active session with DB access",
                        "is_error": True,
                    }
                target_id = uuid.UUID(tool_input["session_id"])
                limit = tool_input.get("limit", 10)
                result = await self._agent_comm.query_agent(
                    db,
                    target_session_id=target_id,
                    querying_session_id=session_id,
                    limit=limit,
                )
                return {"content": json.dumps(result)}

            elif tool_name == "send_to_agent":
                if session_id is None or db is None:
                    return {
                        "content": "send_to_agent requires an active session with DB access",
                        "is_error": True,
                    }
                target_id = uuid.UUID(tool_input["session_id"])
                result = await self._agent_comm.send_to_agent(
                    db,
                    sender_session_id=session_id,
                    target_session_id=target_id,
                    message=tool_input["message"],
                )
                return {"content": json.dumps(result)}

            elif tool_name == "get_subsession_result":
                if session_id is None or db is None:
                    return {
                        "content": "get_subsession_result requires an active session with DB access",
                        "is_error": True,
                    }
                try:
                    child_id = uuid.UUID(tool_input["session_id"])
                    result = await self._subagent_manager.get_result(
                        db,
                        child_session_id=child_id,
                        parent_session_id=session_id,
                    )
                except Exception as exc:
                    return {"content": str(exc), "is_error": True}
                return {"content": json.dumps(result)}

            elif tool_name == "list_subsessions":
                if session_id is None or db is None:
                    return {
                        "content": "list_subsessions requires an active session with DB access",
                        "is_error": True,
                    }
                try:
                    result = await self._subagent_manager.list_subsessions(
                        db,
                        parent_session_id=session_id,
                    )
                except Exception as exc:
                    return {"content": str(exc), "is_error": True}
                return {"content": json.dumps(result)}

            else:
                return {"content": f"Unknown tool: {tool_name}", "is_error": True}

        except Exception as exc:
            return {"content": f"Error: {type(exc).__name__}: {exc}", "is_error": True}
