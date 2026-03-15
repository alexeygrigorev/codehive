"""Bot setup: Application builder, command registration, startup/shutdown."""

from __future__ import annotations

import httpx
from telegram.ext import Application, CommandHandler

from codehive.clients.telegram.handlers import (
    answer_handler,
    approve_handler,
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


def create_bot(token: str, base_url: str = "http://127.0.0.1:8000") -> Application:
    """Build and return a configured Telegram Application.

    The httpx.AsyncClient is stored in bot_data and shared across handlers.
    """
    app = Application.builder().token(token).build()

    # Store the HTTP client in bot_data for handlers to access
    app.bot_data["http_client"] = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    # Register all command handlers
    for name, handler_fn in COMMAND_HANDLERS.items():
        app.add_handler(CommandHandler(name, handler_fn))

    return app


async def shutdown_bot(app: Application) -> None:
    """Clean up resources (close the httpx client)."""
    client: httpx.AsyncClient = app.bot_data.get("http_client")  # type: ignore[assignment]
    if client:
        await client.aclose()
