"""Telegram command handler implementations.

Each handler receives a Telegram Update + context, extracts arguments,
calls the backend API via httpx.AsyncClient, formats the response,
and replies to the user.
"""

from __future__ import annotations

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from codehive.clients.telegram.formatters import (
    format_project_list,
    format_question_list,
    format_session_list,
    format_session_status,
    format_task_list,
)

# Type alias for handler context
Ctx = ContextTypes.DEFAULT_TYPE


async def _api_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs: object,
) -> httpx.Response:
    """Make an API request, returning the response."""
    return await getattr(client, method)(path, **kwargs)


async def _reply_error(update: Update, resp: httpx.Response) -> None:
    """Send a user-friendly error message based on HTTP status."""
    if resp.status_code == 404:
        try:
            detail = resp.json().get("detail", "Not found")
        except Exception:
            detail = "Not found"
        await update.message.reply_text(f"Not found: {detail}")  # type: ignore[union-attr]
    elif resp.status_code == 422:
        try:
            detail = resp.json().get("detail", "Validation error")
        except Exception:
            detail = "Validation error"
        await update.message.reply_text(f"Validation error: {detail}")  # type: ignore[union-attr]
    else:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        await update.message.reply_text(f"Error ({resp.status_code}): {detail}")  # type: ignore[union-attr]


def _get_http_client(context: Ctx) -> httpx.AsyncClient:
    """Get the shared httpx client from bot_data."""
    return context.bot_data["http_client"]  # type: ignore[index]


async def start_handler(update: Update, context: Ctx) -> None:
    """Handle /start -- show welcome message with available commands."""
    text = (
        "Welcome to Codehive!\n\n"
        "Available commands:\n"
        "  /projects - List projects\n"
        "  /sessions <project_id> - List sessions\n"
        "  /status <session_id> - Session status\n"
        "  /todo <session_id> - List tasks\n"
        "  /send <session_id> <message> - Send message\n"
        "  /approve <action_id> - Approve action\n"
        "  /reject <action_id> - Reject action\n"
        "  /questions - List unanswered questions\n"
        "  /answer <question_id> <text> - Answer question\n"
        "  /stop <session_id> - Stop session"
    )
    await update.message.reply_text(text)  # type: ignore[union-attr]


async def projects_handler(update: Update, context: Ctx) -> None:
    """Handle /projects -- list all projects."""
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "get", "/api/projects")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    projects = resp.json()
    await update.message.reply_text(format_project_list(projects))  # type: ignore[union-attr]


async def sessions_handler(update: Update, context: Ctx) -> None:
    """Handle /sessions <project_id> -- list sessions for a project."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /sessions <project_id>")  # type: ignore[union-attr]
        return
    project_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "get", f"/api/projects/{project_id}/sessions")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    sessions = resp.json()
    await update.message.reply_text(format_session_list(sessions))  # type: ignore[union-attr]


async def status_handler(update: Update, context: Ctx) -> None:
    """Handle /status <session_id> -- show session status."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /status <session_id>")  # type: ignore[union-attr]
        return
    session_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "get", f"/api/sessions/{session_id}")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    session = resp.json()
    await update.message.reply_text(format_session_status(session))  # type: ignore[union-attr]


async def todo_handler(update: Update, context: Ctx) -> None:
    """Handle /todo <session_id> -- list tasks."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /todo <session_id>")  # type: ignore[union-attr]
        return
    session_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "get", f"/api/sessions/{session_id}/tasks")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    tasks = resp.json()
    await update.message.reply_text(format_task_list(tasks))  # type: ignore[union-attr]


async def send_handler(update: Update, context: Ctx) -> None:
    """Handle /send <session_id> <message> -- send message to session."""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /send <session_id> <message>")  # type: ignore[union-attr]
        return
    session_id = args[0]
    message = " ".join(args[1:])
    client = _get_http_client(context)
    try:
        resp = await _api_request(
            client, "post", f"/api/sessions/{session_id}/messages", json={"content": message}
        )
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    events = resp.json()
    # Find the assistant's response
    assistant_msgs = [
        e.get("content", "")
        for e in events
        if e.get("type") == "message.created" and e.get("role") == "assistant"
    ]
    if assistant_msgs:
        await update.message.reply_text(assistant_msgs[-1])  # type: ignore[union-attr]
    else:
        await update.message.reply_text("Message sent.")  # type: ignore[union-attr]


async def approve_handler(update: Update, context: Ctx) -> None:
    """Handle /approve <action_id> -- approve a pending approval."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /approve <action_id>")  # type: ignore[union-attr]
        return
    action_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "post", f"/api/sessions/{action_id}/approve")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    await update.message.reply_text("Approved.")  # type: ignore[union-attr]


async def reject_handler(update: Update, context: Ctx) -> None:
    """Handle /reject <action_id> -- reject a pending approval."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /reject <action_id>")  # type: ignore[union-attr]
        return
    action_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "post", f"/api/sessions/{action_id}/reject")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    await update.message.reply_text("Rejected.")  # type: ignore[union-attr]


async def questions_handler(update: Update, context: Ctx) -> None:
    """Handle /questions -- list unanswered questions across sessions."""
    args = context.args or []
    if not args:
        await update.message.reply_text(  # type: ignore[union-attr]
            "Usage: /questions <session_id>"
        )
        return
    session_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(
            client, "get", f"/api/sessions/{session_id}/questions", params={"answered": "false"}
        )
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    questions = resp.json()
    await update.message.reply_text(format_question_list(questions))  # type: ignore[union-attr]


async def answer_handler(update: Update, context: Ctx) -> None:
    """Handle /answer <question_id> <text> -- answer a pending question."""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /answer <question_id> <text>")  # type: ignore[union-attr]
        return
    question_id = args[0]
    answer_text = " ".join(args[1:])
    client = _get_http_client(context)
    try:
        resp = await _api_request(
            client,
            "post",
            f"/api/questions/{question_id}/answer",
            json={"text": answer_text},
        )
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    await update.message.reply_text("Answer submitted.")  # type: ignore[union-attr]


async def stop_handler(update: Update, context: Ctx) -> None:
    """Handle /stop <session_id> -- pause/stop a session."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /stop <session_id>")  # type: ignore[union-attr]
        return
    session_id = args[0]
    client = _get_http_client(context)
    try:
        resp = await _api_request(client, "post", f"/api/sessions/{session_id}/pause")
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if resp.status_code >= 400:
        await _reply_error(update, resp)
        return
    await update.message.reply_text("Session stopped.")  # type: ignore[union-attr]


async def callback_query_handler(update: Update, context: Ctx) -> None:
    """Handle inline keyboard button presses (approve/reject callbacks).

    Expected callback_data format: ``approve:<action_id>`` or ``reject:<action_id>``.
    """
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        await query.edit_message_text("Error: unrecognised callback data.")
        return

    action, action_id = data.split(":", 1)
    if action not in ("approve", "reject"):
        await query.edit_message_text("Error: unrecognised callback data.")
        return

    client: httpx.AsyncClient = context.bot_data["http_client"]  # type: ignore[index]
    endpoint = f"/api/sessions/{action_id}/{action}"
    try:
        resp = await _api_request(client, "post", endpoint)
    except httpx.ConnectError:
        await query.edit_message_text("Error: cannot reach server.")
        return

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        await query.edit_message_text(f"Error: {detail}")
        return

    label = "Approved" if action == "approve" else "Rejected"
    await query.edit_message_text(f"{label} (action {action_id}).")
