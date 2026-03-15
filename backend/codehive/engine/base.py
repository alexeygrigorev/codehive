"""EngineAdapter protocol: defines the interface every engine must satisfy."""

from __future__ import annotations

import uuid
from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class EngineAdapter(Protocol):
    """Protocol that all engine adapters must implement.

    An engine adapter drives a conversation between the user and an LLM,
    executing tool calls through the execution layer and emitting events
    via the event bus.
    """

    async def create_session(self, session_id: uuid.UUID) -> None:
        """Initialise internal state for a new session.

        Args:
            session_id: Unique identifier for the session.
        """
        ...

    async def send_message(self, session_id: uuid.UUID, message: str) -> AsyncIterator[dict]:
        """Send a user message and stream back event dicts.

        The engine runs the full conversation loop (user message -> LLM ->
        tool calls -> tool results -> LLM -> ...) until the model produces
        a final text response with no more tool calls.

        Args:
            session_id: Session to send the message to.
            message: The user's text message.

        Yields:
            Event dicts with at least a ``type`` key (e.g. ``message.created``,
            ``tool.call.started``, ``tool.call.finished``).
        """
        ...

    async def start_task(self, session_id: uuid.UUID, task_id: uuid.UUID) -> AsyncIterator[dict]:
        """Retrieve a task by ID and feed its instructions into send_message.

        Args:
            session_id: Session that owns the task.
            task_id: ID of the task whose instructions to execute.

        Yields:
            Event dicts from the underlying send_message call.
        """
        ...

    async def pause(self, session_id: uuid.UUID) -> None:
        """Set the pause flag so the conversation loop stops after the current step.

        Args:
            session_id: Session to pause.
        """
        ...

    async def resume(self, session_id: uuid.UUID) -> None:
        """Clear the pause flag, allowing the conversation loop to continue.

        Args:
            session_id: Session to resume.
        """
        ...

    async def approve_action(self, session_id: uuid.UUID, action_id: str) -> None:
        """Approve a pending action that requires user confirmation.

        Args:
            session_id: Session containing the pending action.
            action_id: Identifier of the action to approve.
        """
        ...

    async def reject_action(self, session_id: uuid.UUID, action_id: str) -> None:
        """Reject a pending action that requires user confirmation.

        Args:
            session_id: Session containing the pending action.
            action_id: Identifier of the action to reject.
        """
        ...

    async def get_diff(self, session_id: uuid.UUID) -> dict[str, str]:
        """Return the accumulated diff for the session.

        Args:
            session_id: Session to get the diff for.

        Returns:
            Dict mapping file paths to their unified diff text.
        """
        ...
