"""Agent-to-agent communication: query, send message, broadcast."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import EventBus
from codehive.core.session import (
    SessionNotFoundError,
    get_session,
    list_child_sessions,
)
from codehive.db.models import Event, Task


# Event type constants
EVENT_AGENT_QUERY = "agent.query"
EVENT_AGENT_MESSAGE = "agent.message"


class AgentCommService:
    """Manages inter-agent communication: query state, send messages, broadcast."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    async def query_agent(
        self,
        db: AsyncSession,
        *,
        target_session_id: uuid.UUID,
        querying_session_id: uuid.UUID | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Query another agent's current state.

        Returns session status, mode, name, current task, and recent events.
        Raises SessionNotFoundError if the target session does not exist.
        """
        session = await get_session(db, target_session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {target_session_id} not found")

        # Fetch current running task (if any)
        current_task: dict[str, Any] | None = None
        task_stmt = (
            select(Task)
            .where(Task.session_id == target_session_id, Task.status == "running")
            .limit(1)
        )
        task_result = await db.execute(task_stmt)
        running_task = task_result.scalars().first()
        if running_task is not None:
            current_task = {
                "id": str(running_task.id),
                "title": running_task.title,
                "status": running_task.status,
            }

        # Fetch recent events
        events_stmt = (
            select(Event)
            .where(Event.session_id == target_session_id)
            .order_by(Event.created_at.asc())
            .limit(limit)
        )
        events_result = await db.execute(events_stmt)
        events = events_result.scalars().all()
        recent_events = [
            {
                "type": ev.type,
                "data": ev.data,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in events
        ]

        # Publish agent.query event on the querying session's stream
        if querying_session_id is not None and self._event_bus is not None:
            await self._event_bus.publish(
                db,
                querying_session_id,
                EVENT_AGENT_QUERY,
                {
                    "queried_session_id": str(target_session_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        return {
            "session_id": str(target_session_id),
            "status": session.status,
            "mode": session.mode,
            "name": session.name,
            "current_task": current_task,
            "recent_events": recent_events,
        }

    async def send_to_agent(
        self,
        db: AsyncSession,
        *,
        sender_session_id: uuid.UUID,
        target_session_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Send a message from one agent to another.

        Creates agent.message events on both the target and sender session streams.
        Raises SessionNotFoundError if either session does not exist.
        """
        # Verify sender exists
        sender = await get_session(db, sender_session_id)
        if sender is None:
            raise SessionNotFoundError(f"Session {sender_session_id} not found")

        # Verify target exists
        target = await get_session(db, target_session_id)
        if target is None:
            raise SessionNotFoundError(f"Session {target_session_id} not found")

        timestamp = datetime.now(timezone.utc).isoformat()
        event_data = {
            "sender_session_id": str(sender_session_id),
            "target_session_id": str(target_session_id),
            "message": message,
            "timestamp": timestamp,
        }

        target_event_id: str | None = None

        if self._event_bus is not None:
            # Event on target session's stream
            target_event = await self._event_bus.publish(
                db,
                target_session_id,
                EVENT_AGENT_MESSAGE,
                event_data,
            )
            target_event_id = str(target_event.id)

            # Audit event on sender session's stream
            await self._event_bus.publish(
                db,
                sender_session_id,
                EVENT_AGENT_MESSAGE,
                event_data,
            )

        return {
            "event_id": target_event_id,
            "target_session_id": str(target_session_id),
            "message": message,
            "timestamp": timestamp,
        }

    async def broadcast(
        self,
        db: AsyncSession,
        *,
        sender_session_id: uuid.UUID,
        message: str,
    ) -> list[str]:
        """Broadcast a message to all sibling sessions.

        Finds the sender's parent, lists all children of that parent,
        and sends the message to each sibling (excluding the sender).

        Raises SessionNotFoundError if the sender session does not exist.
        Raises ValueError if the sender has no parent session.
        Returns list of session IDs that received the message.
        """
        sender = await get_session(db, sender_session_id)
        if sender is None:
            raise SessionNotFoundError(f"Session {sender_session_id} not found")

        if sender.parent_session_id is None:
            raise ValueError(
                f"Session {sender_session_id} has no parent session; cannot broadcast to siblings"
            )

        # Get all siblings (children of the same parent)
        siblings = await list_child_sessions(db, sender.parent_session_id)

        recipients: list[str] = []
        for sibling in siblings:
            if sibling.id == sender_session_id:
                continue
            await self.send_to_agent(
                db,
                sender_session_id=sender_session_id,
                target_session_id=sibling.id,
                message=message,
            )
            recipients.append(str(sibling.id))

        return recipients
