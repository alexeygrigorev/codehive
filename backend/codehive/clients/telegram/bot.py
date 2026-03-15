"""Bot setup: Application builder, command registration, startup/shutdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from codehive.clients.telegram.handlers import (
    answer_handler,
    approve_handler,
    callback_query_handler,
    projects_handler,
    questions_handler,
    reject_handler,
    send_handler,
    sessions_handler,
    start_handler,
    status_handler,
    stop_handler,
    todo_handler,
)
from codehive.clients.telegram.notifications import NotificationDispatcher

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from codehive.config import Settings

# All command names mapped to their handlers
COMMAND_HANDLERS = {
    "start": start_handler,
    "projects": projects_handler,
    "sessions": sessions_handler,
    "status": status_handler,
    "todo": todo_handler,
    "send": send_handler,
    "approve": approve_handler,
    "reject": reject_handler,
    "questions": questions_handler,
    "answer": answer_handler,
    "stop": stop_handler,
}


def create_bot(
    token: str,
    base_url: str = "http://127.0.0.1:8000",
    redis: Redis | None = None,
    settings: Settings | None = None,
) -> Application:
    """Build and return a configured Telegram Application.

    The httpx.AsyncClient is stored in bot_data and shared across handlers.
    If *redis* is provided, a :class:`NotificationDispatcher` is created and
    stored in ``bot_data["notification_dispatcher"]`` for lifecycle management.
    """
    app = Application.builder().token(token).build()

    # Store the HTTP client in bot_data for handlers to access
    app.bot_data["http_client"] = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    # Register all command handlers
    for name, handler_fn in COMMAND_HANDLERS.items():
        app.add_handler(CommandHandler(name, handler_fn))

    # Register inline keyboard callback handler
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # Set up notification dispatcher if Redis is available
    if redis is not None:
        dispatcher = NotificationDispatcher(redis=redis, bot=app.bot, settings=settings)
        app.bot_data["notification_dispatcher"] = dispatcher

    return app


async def start_notification_dispatcher(app: Application) -> None:
    """Start the notification dispatcher if one is configured."""
    dispatcher: NotificationDispatcher | None = app.bot_data.get(  # type: ignore[assignment]
        "notification_dispatcher"
    )
    if dispatcher is not None:
        await dispatcher.start()


async def stop_notification_dispatcher(app: Application) -> None:
    """Stop the notification dispatcher if one is running."""
    dispatcher: NotificationDispatcher | None = app.bot_data.get(  # type: ignore[assignment]
        "notification_dispatcher"
    )
    if dispatcher is not None:
        await dispatcher.stop()


async def shutdown_bot(app: Application) -> None:
    """Clean up resources (stop dispatcher, close the httpx client)."""
    await stop_notification_dispatcher(app)
    client: httpx.AsyncClient = app.bot_data.get("http_client")  # type: ignore[assignment]
    if client:
        await client.aclose()
