"""Error tracking: aggregate errors from events table, detect rate spikes."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codehive.config import Settings
from codehive.db.models import Event

if TYPE_CHECKING:
    from codehive.core.events import EventBus

logger = logging.getLogger(__name__)

# Event types treated as errors
ERROR_EVENT_TYPES = ("session.failed",)

# Well-known system session UUID for publishing system-level events
SYSTEM_SESSION_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _error_filter():
    """Return a SQLAlchemy filter expression matching error events.

    Error events are:
    - Events with type 'session.failed'
    - Events with type 'tool.call.finished' where data contains an 'error' key

    Uses json_extract which works on both PostgreSQL and SQLite.
    """
    return or_(
        Event.type.in_(ERROR_EVENT_TYPES),
        and_(
            Event.type == "tool.call.finished",
            func.json_extract(Event.data, "$.error").isnot(None),
        ),
    )


class ErrorTracker:
    """Aggregates error events from the events table.

    Provides summary, by-type grouping, and recent error listing.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    @property
    def window_minutes(self) -> int:
        return self._settings.error_window_minutes

    async def get_summary(self, db: AsyncSession) -> dict:
        """Return error summary: total count, window count, rate, spike status."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.window_minutes)
        prev_window_start = window_start - timedelta(minutes=self.window_minutes)

        # Total errors
        total_stmt = select(func.count()).select_from(Event).where(_error_filter())
        total_result = await db.execute(total_stmt)
        total_errors = total_result.scalar() or 0

        # Current window errors
        window_stmt = (
            select(func.count())
            .select_from(Event)
            .where(_error_filter(), Event.created_at >= window_start)
        )
        window_result = await db.execute(window_stmt)
        window_errors = window_result.scalar() or 0

        # Previous window errors (for spike detection)
        prev_stmt = (
            select(func.count())
            .select_from(Event)
            .where(
                _error_filter(),
                Event.created_at >= prev_window_start,
                Event.created_at < window_start,
            )
        )
        prev_result = await db.execute(prev_stmt)
        prev_errors = prev_result.scalar() or 0

        # Calculate rate
        errors_per_minute = window_errors / self.window_minutes if self.window_minutes > 0 else 0.0

        # Spike detection
        is_spike = self._is_spike(window_errors, prev_errors)

        return {
            "total_errors": total_errors,
            "window_errors": window_errors,
            "window_minutes": self.window_minutes,
            "errors_per_minute": round(errors_per_minute, 4),
            "is_spike": is_spike,
        }

    def _is_spike(self, current_count: int, previous_count: int) -> bool:
        """Determine if the current error rate constitutes a spike."""
        if current_count < self._settings.error_spike_min_count:
            return False
        if previous_count == 0:
            # If there were no errors before but now there are >= min_count, it is a spike
            return current_count >= self._settings.error_spike_min_count
        ratio = current_count / previous_count
        return ratio >= self._settings.error_spike_threshold

    async def get_errors_by_type(
        self,
        db: AsyncSession,
        *,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Return error counts grouped by event type, ordered by count descending."""
        filters = [_error_filter()]
        if after is not None:
            filters.append(Event.created_at >= after)
        if before is not None:
            filters.append(Event.created_at < before)

        stmt = (
            select(Event.type, func.count().label("count"))
            .where(*filters)
            .group_by(Event.type)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [{"type": row[0], "count": row[1]} for row in rows]

    async def get_recent_errors(
        self,
        db: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[Event]:
        """Return recent error events, most recent first."""
        filters = [_error_filter()]
        if event_type is not None:
            filters.append(Event.type == event_type)

        stmt = (
            select(Event)
            .where(*filters)
            .order_by(Event.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


class ErrorRateMonitor:
    """Background task that periodically checks for error rate spikes.

    When a spike is detected, publishes an ``error.rate_spike`` event
    via the EventBus.
    """

    def __init__(
        self,
        event_bus: EventBus,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._session_factory = session_factory
        self._settings = settings or Settings()
        self._tracker = ErrorTracker(settings=self._settings)
        self._task: asyncio.Task[None] | None = None
        self._last_spike_time: float = 0.0

    async def start(self) -> None:
        """Start the background monitor task."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the background monitor task."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        """Periodically check for error rate spikes."""
        try:
            while True:
                try:
                    await self._check()
                except Exception:
                    logger.exception("Error in error rate monitor check")
                await asyncio.sleep(self._settings.error_monitor_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _check(self) -> None:
        """Run a single spike detection check."""
        async with self._session_factory() as db:
            summary = await self._tracker.get_summary(db)

            if not summary["is_spike"]:
                return

            # Check cooldown
            now = time.monotonic()
            if now - self._last_spike_time < self._settings.error_spike_cooldown_seconds:
                return

            # Publish spike event
            window_errors = summary["window_errors"]
            errors_per_minute = summary["errors_per_minute"]

            # Compute spike ratio for the notification
            now_dt = datetime.now(timezone.utc)
            window_start = now_dt - timedelta(minutes=self._settings.error_window_minutes)
            prev_window_start = window_start - timedelta(
                minutes=self._settings.error_window_minutes
            )
            prev_stmt = (
                select(func.count())
                .select_from(Event)
                .where(
                    _error_filter(),
                    Event.created_at >= prev_window_start,
                    Event.created_at < window_start,
                )
            )
            prev_result = await db.execute(prev_stmt)
            previous_window_errors = prev_result.scalar() or 0
            spike_ratio = (
                round(window_errors / previous_window_errors, 2)
                if previous_window_errors > 0
                else float(window_errors)
            )

            await self._event_bus.publish(
                db,
                SYSTEM_SESSION_ID,
                "error.rate_spike",
                {
                    "window_errors": window_errors,
                    "window_minutes": summary["window_minutes"],
                    "errors_per_minute": errors_per_minute,
                    "spike_ratio": spike_ratio,
                    "previous_window_errors": previous_window_errors,
                    "message": (
                        f"Error rate spike detected: {window_errors} errors "
                        f"in the last {summary['window_minutes']} minutes "
                        f"({errors_per_minute:.2f}/min, {spike_ratio}x normal)"
                    ),
                },
            )
            self._last_spike_time = now
            logger.warning(
                "Error rate spike detected: %d errors in %d minutes",
                window_errors,
                summary["window_minutes"],
            )
