"""Notification dispatcher: subscribes to Redis event bus, sends Telegram messages."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from codehive.clients.telegram.formatters import (
    format_approval_notification,
    format_question_notification,
    format_session_completed_notification,
    format_session_failed_notification,
    format_subagent_report_notification,
)
from codehive.config import Settings

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from telegram import Bot

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Subscribes to Redis pub/sub session events and sends Telegram notifications.

    The dispatcher listens on the ``session:*:events`` pattern and forwards
    notification-worthy events as formatted Telegram messages to the
    configured chat ID.
    """

    def __init__(self, redis: Redis, bot: Bot, settings: Settings | None = None) -> None:
        self._redis = redis
        self._bot = bot
        self._settings = settings or Settings()
        self._task: asyncio.Task[None] | None = None

    @property
    def chat_id(self) -> str:
        return self._settings.telegram_chat_id

    @property
    def notify_events(self) -> list[str]:
        return self._settings.telegram_notify_events

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
                        logger.exception("Error handling event message")
            finally:
                await pubsub.punsubscribe("session:*:events")
                await pubsub.aclose()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis connection error in notification dispatcher")

    async def _handle_message(self, message: dict) -> None:
        """Parse a Redis pub/sub message and send a Telegram notification."""
        if not self.chat_id:
            return

        raw_data = message.get("data")
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        if not isinstance(raw_data, str):
            return

        event = json.loads(raw_data)
        event_type = event.get("type", "")
        data = event.get("data", {})

        if event_type not in self.notify_events:
            return

        await self._send_notification(event_type, data)

    async def _send_notification(self, event_type: str, data: dict) -> None:
        """Format and send a notification for the given event type."""
        if event_type == "approval.required":
            text, markup = format_approval_notification(data)
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=markup,
            )
        elif event_type == "session.completed":
            text = format_session_completed_notification(data)
            await self._bot.send_message(chat_id=self.chat_id, text=text)
        elif event_type == "session.failed":
            text = format_session_failed_notification(data)
            await self._bot.send_message(chat_id=self.chat_id, text=text)
        elif event_type == "subagent.report_ready":
            text = format_subagent_report_notification(data)
            await self._bot.send_message(chat_id=self.chat_id, text=text)
        elif event_type == "question.created":
            text = format_question_notification(data)
            await self._bot.send_message(chat_id=self.chat_id, text=text)
