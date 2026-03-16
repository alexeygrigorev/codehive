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
    build_project_keyboard,
    build_session_keyboard,
    format_question_list,
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


async def _fetch_projects(client: httpx.AsyncClient) -> list[dict] | httpx.Response:
    """Fetch projects from the API. Returns list on success, Response on error."""
    resp = await _api_request(client, "get", "/api/projects")
    if resp.status_code >= 400:
        return resp
    return resp.json()


async def _reply_project_keyboard(
    update: Update,
    context: Ctx,
    action: str,
    prompt: str,
) -> None:
    """Fetch projects and reply with an inline keyboard.

    Used by commands that need a project selection step when called
    without arguments.
    """
    client = _get_http_client(context)
    try:
        result = await _fetch_projects(client)
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if isinstance(result, httpx.Response):
        await _reply_error(update, result)
        return
    projects: list[dict] = result
    keyboard = build_project_keyboard(projects, action=action)
    if keyboard is None:
        await update.message.reply_text("No projects found.")  # type: ignore[union-attr]
        return
    await update.message.reply_text(prompt, reply_markup=keyboard)  # type: ignore[union-attr]


async def projects_handler(update: Update, context: Ctx) -> None:
    """Handle /projects -- list all projects as inline keyboard buttons."""
    client = _get_http_client(context)
    try:
        result = await _fetch_projects(client)
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if isinstance(result, httpx.Response):
        await _reply_error(update, result)
        return
    projects: list[dict] = result
    keyboard = build_project_keyboard(projects, action="project")
    if keyboard is None:
        await update.message.reply_text("No projects found.")  # type: ignore[union-attr]
        return
    await update.message.reply_text(  # type: ignore[union-attr]
        "Select a project:", reply_markup=keyboard
    )


async def _fetch_sessions(
    client: httpx.AsyncClient, project_id: str
) -> list[dict] | httpx.Response:
    """Fetch sessions for a project. Returns list on success, Response on error."""
    resp = await _api_request(client, "get", f"/api/projects/{project_id}/sessions")
    if resp.status_code >= 400:
        return resp
    return resp.json()


async def sessions_handler(update: Update, context: Ctx) -> None:
    """Handle /sessions [project_id] -- list sessions for a project.

    Without arguments, shows a project selection keyboard.
    With a project_id, shows sessions as inline keyboard buttons.
    """
    args = context.args or []
    if not args:
        await _reply_project_keyboard(
            update, context, action="sessions_for", prompt="Select a project to view sessions:"
        )
        return
    project_id = args[0]
    client = _get_http_client(context)
    try:
        result = await _fetch_sessions(client, project_id)
    except httpx.ConnectError:
        await update.message.reply_text("Cannot reach server. Is it running?")  # type: ignore[union-attr]
        return
    if isinstance(result, httpx.Response):
        await _reply_error(update, result)
        return
    sessions: list[dict] = result
    keyboard = build_session_keyboard(sessions, action="status")
    if keyboard is None:
        await update.message.reply_text("No sessions found.")  # type: ignore[union-attr]
        return
    await update.message.reply_text(  # type: ignore[union-attr]
        "Select a session:", reply_markup=keyboard
    )


async def status_handler(update: Update, context: Ctx) -> None:
    """Handle /status [session_id] -- show session status.

    Without arguments, shows a project selection keyboard to drill down.
    """
    args = context.args or []
    if not args:
        await _reply_project_keyboard(
            update, context, action="status_project", prompt="Select a project to view status:"
        )
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
    """Handle /todo [session_id] -- list tasks.

    Without arguments, shows a project selection keyboard to drill down.
    """
    args = context.args or []
    if not args:
        await _reply_project_keyboard(
            update, context, action="todo_project", prompt="Select a project to view tasks:"
        )
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
    """Handle /questions [session_id] -- list unanswered questions.

    Without arguments, shows a project selection keyboard to drill down.
    """
    args = context.args or []
    if not args:
        await _reply_project_keyboard(
            update,
            context,
            action="questions_project",
            prompt="Select a project to view questions:",
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
    """Handle /stop [session_id] -- pause/stop a session.

    Without arguments, shows a project selection keyboard to drill down.
    """
    args = context.args or []
    if not args:
        await _reply_project_keyboard(
            update, context, action="stop_project", prompt="Select a project to stop a session:"
        )
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
    """Handle inline keyboard button presses.

    Dispatches based on the action prefix in callback_data (``action:id``).
    """
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        await query.edit_message_text("Error: unrecognised callback data.")
        return

    action, rest = data.split(":", 1)
    client: httpx.AsyncClient = context.bot_data["http_client"]  # type: ignore[index]

    # --- Approve / Reject (existing) ---
    if action in ("approve", "reject"):
        endpoint = f"/api/sessions/{rest}/{action}"
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
        await query.edit_message_text(f"{label} (action {rest}).")
        return

    # --- Project tapped in /projects -> show sessions ---
    if action == "project":
        project_id = rest
        try:
            result = await _fetch_sessions(client, project_id)
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if isinstance(result, httpx.Response):
            await query.edit_message_text("Error: could not fetch sessions.")
            return
        keyboard = build_session_keyboard(result, action="status")
        if keyboard is None:
            await query.edit_message_text("No sessions found for this project.")
            return
        await query.edit_message_text("Select a session:", reply_markup=keyboard)
        return

    # --- Sessions for project (from /sessions no-arg flow) ---
    if action == "sessions_for":
        project_id = rest
        try:
            result = await _fetch_sessions(client, project_id)
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if isinstance(result, httpx.Response):
            await query.edit_message_text("Error: could not fetch sessions.")
            return
        keyboard = build_session_keyboard(result, action="status")
        if keyboard is None:
            await query.edit_message_text("No sessions found for this project.")
            return
        await query.edit_message_text("Select a session:", reply_markup=keyboard)
        return

    # --- Project selection for status/todo/questions/stop flows ---
    _project_to_session_actions = {
        "status_project": "status",
        "todo_project": "todo",
        "questions_project": "questions",
        "stop_project": "stop",
    }
    if action in _project_to_session_actions:
        project_id = rest
        session_action = _project_to_session_actions[action]
        try:
            result = await _fetch_sessions(client, project_id)
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if isinstance(result, httpx.Response):
            await query.edit_message_text("Error: could not fetch sessions.")
            return
        keyboard = build_session_keyboard(result, action=session_action)
        if keyboard is None:
            await query.edit_message_text("No sessions found for this project.")
            return
        await query.edit_message_text("Select a session:", reply_markup=keyboard)
        return

    # --- Session status ---
    if action == "status":
        session_id = rest
        try:
            resp = await _api_request(client, "get", f"/api/sessions/{session_id}")
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if resp.status_code >= 400:
            await query.edit_message_text("Error: could not fetch session status.")
            return
        session = resp.json()
        await query.edit_message_text(format_session_status(session))
        return

    # --- Todo for session ---
    if action == "todo":
        session_id = rest
        try:
            resp = await _api_request(client, "get", f"/api/sessions/{session_id}/tasks")
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if resp.status_code >= 400:
            await query.edit_message_text("Error: could not fetch tasks.")
            return
        tasks = resp.json()
        await query.edit_message_text(format_task_list(tasks))
        return

    # --- Questions for session ---
    if action == "questions":
        session_id = rest
        try:
            resp = await _api_request(
                client, "get", f"/api/sessions/{session_id}/questions", params={"answered": "false"}
            )
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if resp.status_code >= 400:
            await query.edit_message_text("Error: could not fetch questions.")
            return
        questions = resp.json()
        await query.edit_message_text(format_question_list(questions))
        return

    # --- Stop session ---
    if action == "stop":
        session_id = rest
        try:
            resp = await _api_request(client, "post", f"/api/sessions/{session_id}/pause")
        except httpx.ConnectError:
            await query.edit_message_text("Error: cannot reach server.")
            return
        if resp.status_code >= 400:
            await query.edit_message_text("Error: could not stop session.")
            return
        await query.edit_message_text("Session stopped.")
        return

    # --- Pagination ---
    if action == "more":
        # rest = "<sub_action>:<offset>"
        if ":" not in rest:
            await query.edit_message_text("Error: invalid pagination data.")
            return
        sub_action, offset_str = rest.split(":", 1)
        try:
            offset = int(offset_str)
        except ValueError:
            await query.edit_message_text("Error: invalid pagination offset.")
            return
        # Pagination for project keyboards
        project_actions = {
            "project",
            "sessions_for",
            "status_project",
            "todo_project",
            "questions_project",
            "stop_project",
        }
        if sub_action in project_actions:
            try:
                proj_result = await _fetch_projects(client)
            except httpx.ConnectError:
                await query.edit_message_text("Error: cannot reach server.")
                return
            if isinstance(proj_result, httpx.Response):
                await query.edit_message_text("Error: could not fetch projects.")
                return
            keyboard = build_project_keyboard(proj_result, action=sub_action, offset=offset)
            if keyboard is None:
                await query.edit_message_text("No more projects.")
                return
            await query.edit_message_text("Select a project:", reply_markup=keyboard)
            return
        # Pagination for session keyboards -- not implemented in this issue
        await query.edit_message_text("Error: unsupported pagination action.")
        return

    # --- Unknown action ---
    await query.edit_message_text("Error: unrecognised callback data.")
