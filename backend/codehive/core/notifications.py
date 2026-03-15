"""Push notification dispatcher: subscribes to Redis event bus, sends web push notifications."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codehive.config import Settings
from codehive.db.models import PushSubscription

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Event types that trigger push notifications, mapped to human-readable titles
_EVENT_TITLES: dict[str, str] = {
    "approval.required": "Approval Required",
    "session.completed": "Session Completed",
    "session.failed": "Session Failed",
    "session.waiting": "Session Waiting",
}


def _build_payload(event_type: str, data: dict) -> dict:
    """Build a push notification payload from an event."""
    title = _EVENT_TITLES.get(event_type, event_type)
    session_name = data.get("session_name", "Unknown session")
    session_id = data.get("session_id", "")

    if event_type == "approval.required":
        body = f"{session_name}: {data.get('action_description', 'Action needs approval')}"
    elif event_type == "session.completed":
        body = f"{session_name}: {data.get('summary', 'Session completed')}"
    elif event_type == "session.failed":
        body = f"{session_name}: {data.get('error', 'Session failed')}"
    elif event_type == "session.waiting":
        body = f"{session_name}: {data.get('reason', 'Waiting for input')}"
    else:
        body = f"{session_name}: {event_type}"

    url = f"/sessions/{session_id}" if session_id else "/"

    return {
        "title": title,
        "body": body,
        "url": url,
        "event_type": event_type,
    }


class PushDispatcher:
    """Subscribes to Redis pub/sub session events and sends web push notifications.

    Listens on ``session:*:events`` and forwards notification-worthy events
    as web push notifications to all stored subscriptions.
    """

    def __init__(
        self,
        redis: Redis,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._redis = redis
        self._session_factory = session_factory
        self._settings = settings or Settings()
        self._task: asyncio.Task[None] | None = None

    @property
    def notify_events(self) -> list[str]:
        return self._settings.push_notify_events

    async def start(self) -> None:
        """Start the dispatcher as a background asyncio task."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        """Cancel the background listener task."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _listen(self) -> None:
        """Subscribe to Redis and dispatch incoming events."""
        try:
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe("session:*:events")
            try:
                async for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        await self._handle_message(message)
                    except Exception:
                        logger.exception("Error handling push event message")
            finally:
                await pubsub.punsubscribe("session:*:events")
                await pubsub.aclose()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis connection error in push notification dispatcher")

    async def _handle_message(self, message: dict) -> None:
        """Parse a Redis pub/sub message and send web push notifications."""
        raw_data = message.get("data")
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        if not isinstance(raw_data, str):
            return

        event = json.loads(raw_data)
        event_type = event.get("type", "")
        data = event.get("data", {})

        # Include session_id from the event envelope into data for payload building
        if "session_id" not in data:
            data["session_id"] = event.get("session_id", "")

        if event_type not in self.notify_events:
            return

        payload = _build_payload(event_type, data)
        await self._send_to_all(payload)

    async def _send_to_all(self, payload: dict) -> None:
        """Send a push notification to all stored subscriptions."""
        if not self._settings.vapid_private_key:
            logger.debug("VAPID private key not configured; skipping push dispatch")
            return

        async with self._session_factory() as db:
            stmt = select(PushSubscription)
            result = await db.execute(stmt)
            subscriptions = list(result.scalars().all())

            if not subscriptions:
                return

            notification_data = json.dumps(payload)
            stale_ids: list = []

            for sub in subscriptions:
                try:
                    webpush(
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                        },
                        data=notification_data,
                        vapid_private_key=self._settings.vapid_private_key,
                        vapid_claims={"sub": self._settings.vapid_mailto},
                    )
                except WebPushException as exc:
                    if (
                        getattr(exc, "response", None) is not None
                        and exc.response.status_code == 410
                    ):
                        stale_ids.append(sub.id)
                        logger.info("Removing stale push subscription: %s", sub.endpoint)
                    else:
                        logger.warning("Push delivery failed for %s: %s", sub.endpoint, exc)

            # Clean up stale subscriptions
            if stale_ids:
                stmt_del = delete(PushSubscription).where(PushSubscription.id.in_(stale_ids))
                await db.execute(stmt_del)
                await db.commit()
