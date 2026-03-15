"""Log query service: structured querying of session events."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import SessionNotFoundError
from codehive.db.models import Event
from codehive.db.models import Session as SessionModel


class LogQueryResult:
    """Result of a log query with items and total count."""

    def __init__(self, items: list[Event], total: int) -> None:
        self.items = items
        self.total = total


class LogService:
    """Structured query interface over the events table."""

    async def _verify_session(self, db: AsyncSession, session_id: uuid.UUID) -> None:
        """Raise SessionNotFoundError if the session does not exist."""
        session = await db.get(SessionModel, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

    async def query(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        types: list[str] | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LogQueryResult:
        """Query events for a session with optional filters.

        Args:
            db: Async database session.
            session_id: The session to query events for.
            types: Optional list of event types to filter by.
            after: Only return events created after this datetime.
            before: Only return events created before this datetime.
            limit: Maximum number of items to return.
            offset: Number of items to skip.

        Returns:
            LogQueryResult with items and total count.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        await self._verify_session(db, session_id)

        # Build base filter conditions
        conditions = [Event.session_id == session_id]
        if types:
            conditions.append(Event.type.in_(types))
        if after is not None:
            conditions.append(Event.created_at > after)
        if before is not None:
            conditions.append(Event.created_at < before)

        # Get total count
        count_stmt = select(func.count(Event.id)).where(*conditions)
        total = (await db.execute(count_stmt)).scalar_one()

        # Get paginated items
        items_stmt = (
            select(Event)
            .where(*conditions)
            .order_by(Event.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(items_stmt)
        items = list(result.scalars().all())

        return LogQueryResult(items=items, total=total)

    async def export(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        types: list[str] | None = None,
    ) -> list[Event]:
        """Export all events for a session, optionally filtered by type.

        Args:
            db: Async database session.
            session_id: The session to export events for.
            types: Optional list of event types to filter by.

        Returns:
            List of all matching events.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        await self._verify_session(db, session_id)

        conditions = [Event.session_id == session_id]
        if types:
            conditions.append(Event.type.in_(types))

        stmt = select(Event).where(*conditions).order_by(Event.created_at.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())
