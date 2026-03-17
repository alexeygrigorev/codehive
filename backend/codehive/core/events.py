"""Event bus: publish events to DB + pub/sub, query historical events.

Provides two implementations:
- ``EventBus`` -- uses Redis pub/sub (requires a running Redis instance).
- ``LocalEventBus`` -- uses asyncio queues for in-process pub/sub.

Use ``create_event_bus()`` to pick the right one based on configuration.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.redaction import SecretRedactor
from codehive.db.models import Event
from codehive.db.models import Session as SessionModel

if TYPE_CHECKING:
    from redis.asyncio import Redis


# Event type constants for agent communication
EVENT_AGENT_QUERY = "agent.query"
EVENT_AGENT_MESSAGE = "agent.message"


class SessionNotFoundError(Exception):
    """Raised when a session does not exist."""


def _serialize_event(event: Event) -> str:
    """Return the JSON string representation used for pub/sub messages."""
    return json.dumps(
        {
            "id": str(event.id),
            "session_id": str(event.session_id),
            "type": event.type,
            "data": event.data,
            "created_at": event.created_at.isoformat(),
        }
    )


class EventBus:
    """Publishes events to the database and Redis pub/sub."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _channel_name(session_id: uuid.UUID) -> str:
        return f"session:{session_id}:events"

    async def publish(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        event_type: str,
        data: dict,
        redactor: SecretRedactor | None = None,
    ) -> Event:
        """Persist an event to the DB and publish to Redis.

        If a *redactor* is provided, all string values in *data* are
        redacted before persisting to the DB and publishing to Redis.

        Returns the created Event model instance.
        """
        if redactor is not None:
            data = redactor.redact_dict(data)

        event = Event(
            session_id=session_id,
            type=event_type,
            data=data,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        message = _serialize_event(event)
        await self._redis.publish(self._channel_name(session_id), message)

        return event

    async def get_events(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        """Return historical events for a session ordered by created_at ascending."""
        # Verify session exists
        session = await db.get(SessionModel, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

        stmt = (
            select(Event)
            .where(Event.session_id == session_id)
            .order_by(Event.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @asynccontextmanager
    async def subscribe(self, session_id: uuid.UUID) -> AsyncIterator[asyncio.Queue[str]]:
        """Subscribe to real-time events via Redis pub/sub.

        Yields an ``asyncio.Queue`` that receives JSON-encoded event strings.
        """
        from redis.asyncio import Redis as _Redis

        redis: _Redis = self._redis
        pubsub = redis.pubsub()
        channel = self._channel_name(session_id)
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def _reader() -> None:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    queue.put_nowait(message["data"].decode("utf-8"))

        task = asyncio.create_task(_reader())
        try:
            yield queue
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()


class LocalEventBus:
    """In-process event bus using asyncio for single-process deployments."""

    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, list[asyncio.Queue[str]]] = defaultdict(list)

    async def publish(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        event_type: str,
        data: dict,
        redactor: SecretRedactor | None = None,
    ) -> Event:
        """Persist an event to the DB and broadcast to in-memory subscribers."""
        if redactor is not None:
            data = redactor.redact_dict(data)

        event = Event(
            session_id=session_id,
            type=event_type,
            data=data,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        message = _serialize_event(event)
        for queue in self._subscribers.get(session_id, []):
            queue.put_nowait(message)

        return event

    async def get_events(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        """Return historical events for a session ordered by created_at ascending."""
        session = await db.get(SessionModel, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

        stmt = (
            select(Event)
            .where(Event.session_id == session_id)
            .order_by(Event.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @asynccontextmanager
    async def subscribe(self, session_id: uuid.UUID) -> AsyncIterator[asyncio.Queue[str]]:
        """Subscribe to real-time events for *session_id*.

        Yields an ``asyncio.Queue`` that receives JSON-encoded event strings.
        On exit the subscriber is removed automatically.
        """
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            yield queue
        finally:
            self._subscribers[session_id].remove(queue)
            # Clean up empty lists to avoid memory leaks
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]


def create_event_bus(redis_url: str = "") -> EventBus | LocalEventBus:
    """Return the appropriate event bus based on configuration.

    If *redis_url* is a non-empty string, returns an ``EventBus`` backed by
    Redis.  Otherwise returns a ``LocalEventBus`` using asyncio queues.
    """
    if redis_url:
        from redis.asyncio import Redis

        redis = Redis.from_url(redis_url)
        return EventBus(redis=redis)
    return LocalEventBus()
