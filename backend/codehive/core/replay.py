"""Replay service: reconstruct chronological timeline from session events."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import SessionNotFoundError
from codehive.db.models import Event
from codehive.db.models import Session as SessionModel

# Mapping from event type (as stored in DB) to replay step_type.
EVENT_TYPE_TO_STEP_TYPE: dict[str, str] = {
    "message.created": "message",
    "tool.call.started": "tool_call_start",
    "tool.call.finished": "tool_call_finish",
    "file.changed": "file_change",
    "task.started": "task_started",
    "task.completed": "task_completed",
    "session.status_changed": "session_status_change",
}

REPLAYABLE_STATUSES = {"completed", "failed"}


class SessionNotReplayableError(Exception):
    """Raised when a session is not in a replayable status."""


class ReplayResult:
    """Result of building a replay timeline."""

    def __init__(
        self,
        session_id: uuid.UUID,
        session_status: str,
        total_steps: int,
        steps: list[dict],
    ) -> None:
        self.session_id = session_id
        self.session_status = session_status
        self.total_steps = total_steps
        self.steps = steps


class ReplayService:
    """Reconstructs an ordered timeline of replay steps from the events table."""

    async def _get_session(self, db: AsyncSession, session_id: uuid.UUID) -> SessionModel:
        """Return the session or raise SessionNotFoundError."""
        session = await db.get(SessionModel, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return session

    @staticmethod
    def _map_step_type(event_type: str) -> str:
        """Map a DB event type to a replay step_type."""
        return EVENT_TYPE_TO_STEP_TYPE.get(event_type, event_type)

    async def build_replay(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> ReplayResult:
        """Build paginated replay steps for a session.

        Args:
            db: Async database session.
            session_id: The session to replay.
            limit: Maximum number of steps to return.
            offset: Number of steps to skip.

        Returns:
            ReplayResult with ordered steps and metadata.

        Raises:
            SessionNotFoundError: If the session does not exist.
            SessionNotReplayableError: If the session is not completed or failed.
        """
        session = await self._get_session(db, session_id)

        if session.status not in REPLAYABLE_STATUSES:
            raise SessionNotReplayableError(
                f"Session {session_id} has status '{session.status}' "
                f"and is not replayable. Only completed or failed sessions can be replayed."
            )

        # Get total count of events
        count_stmt = select(func.count(Event.id)).where(Event.session_id == session_id)
        total_steps = (await db.execute(count_stmt)).scalar_one()

        # Get paginated events ordered chronologically
        events_stmt = (
            select(Event)
            .where(Event.session_id == session_id)
            .order_by(Event.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(events_stmt)
        events = list(result.scalars().all())

        # Build replay steps with sequential indices starting from offset
        steps = []
        for i, event in enumerate(events):
            steps.append(
                {
                    "index": offset + i,
                    "timestamp": event.created_at,
                    "step_type": self._map_step_type(event.type),
                    "data": event.data,
                }
            )

        return ReplayResult(
            session_id=session_id,
            session_status=session.status,
            total_steps=total_steps,
            steps=steps,
        )
