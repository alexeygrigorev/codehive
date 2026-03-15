"""Event bus: publish events to DB + Redis pub/sub, query historical events."""

import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.redaction import SecretRedactor
from codehive.db.models import Event
from codehive.db.models import Session as SessionModel


class SessionNotFoundError(Exception):
    """Raised when a session does not exist."""


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
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        message = json.dumps(
            {
                "id": str(event.id),
                "session_id": str(event.session_id),
                "type": event.type,
                "data": event.data,
                "created_at": event.created_at.isoformat(),
            }
        )
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
