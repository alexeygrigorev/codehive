"""Message formatting helpers for Telegram bot responses."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Maximum items per keyboard page before showing "More..." button
PAGE_SIZE = 8


# ---------------------------------------------------------------------------
# Inline keyboard builders
# ---------------------------------------------------------------------------


def build_project_keyboard(
    projects: list[dict],
    action: str = "project",
    offset: int = 0,
) -> InlineKeyboardMarkup | None:
    """Build an inline keyboard with one button per project.

    *action* controls the callback_data prefix (e.g. ``project``,
    ``sessions_for``, ``status_project``, ``todo_project``,
    ``questions_project``, ``stop_project``).

    Returns ``None`` when *projects* is empty so callers can fall back to text.
    """
    if not projects:
        return None
    page = projects[offset : offset + PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for p in page:
        name = p.get("name", "unnamed")
        pid = p.get("id", "?")
        rows.append([InlineKeyboardButton(name, callback_data=f"{action}:{pid}")])
    if offset + PAGE_SIZE < len(projects):
        rows.append(
            [
                InlineKeyboardButton(
                    "More...",
                    callback_data=f"more:{action}:{offset + PAGE_SIZE}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def build_session_keyboard(
    sessions: list[dict],
    action: str = "status",
    offset: int = 0,
) -> InlineKeyboardMarkup | None:
    """Build an inline keyboard with one button per session.

    *action* controls the callback_data prefix (e.g. ``status``, ``todo``,
    ``questions``, ``stop``).

    Returns ``None`` when *sessions* is empty so callers can fall back to text.
    """
    if not sessions:
        return None
    page = sessions[offset : offset + PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for s in page:
        name = s.get("name", "unnamed")
        sid = s.get("id", "?")
        status = s.get("status", "")
        label = f"{name} [{status}]" if status else name
        rows.append([InlineKeyboardButton(label, callback_data=f"{action}:{sid}")])
    if offset + PAGE_SIZE < len(sessions):
        rows.append(
            [
                InlineKeyboardButton(
                    "More...",
                    callback_data=f"more:{action}:{offset + PAGE_SIZE}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def format_project_list(projects: list[dict]) -> str:
    """Format a list of project dicts into a readable string."""
    if not projects:
        return "No projects found."
    lines = ["Projects:\n"]
    for p in projects:
        name = p.get("name", "unnamed")
        pid = p.get("id", "?")
        lines.append(f"  {name} (id: {pid})")
    return "\n".join(lines)


def format_session_list(sessions: list[dict]) -> str:
    """Format a list of session dicts into a readable string."""
    if not sessions:
        return "No sessions found."
    lines = ["Sessions:\n"]
    for s in sessions:
        name = s.get("name", "unnamed")
        sid = s.get("id", "?")
        status = s.get("status", "unknown")
        engine = s.get("engine", "?")
        lines.append(f"  {name} [{status}] (engine: {engine}, id: {sid})")
    return "\n".join(lines)


def format_session_status(session: dict) -> str:
    """Format a single session dict into a status summary."""
    name = session.get("name", "unnamed")
    engine = session.get("engine", "?")
    mode = session.get("mode", "?")
    status = session.get("status", "unknown")
    created = session.get("created_at", "?")
    sid = session.get("id", "?")
    return (
        f"Session: {name}\n"
        f"  ID: {sid}\n"
        f"  Engine: {engine}\n"
        f"  Mode: {mode}\n"
        f"  Status: {status}\n"
        f"  Created: {created}"
    )


def format_task_list(tasks: list[dict]) -> str:
    """Format a list of task dicts with status indicators."""
    if not tasks:
        return "No tasks found."
    status_icons = {
        "pending": "[ ]",
        "running": "[~]",
        "done": "[x]",
        "failed": "[!]",
        "blocked": "[#]",
        "skipped": "[-]",
    }
    lines = ["Tasks:\n"]
    for t in tasks:
        title = t.get("title", t.get("name", "untitled"))
        status = t.get("status", "pending")
        icon = status_icons.get(status, "[?]")
        lines.append(f"  {icon} {title}")
    return "\n".join(lines)


def format_question_list(questions: list[dict]) -> str:
    """Format a list of question dicts showing text and IDs."""
    if not questions:
        return "No unanswered questions."
    lines = ["Pending questions:\n"]
    for q in questions:
        qid = q.get("id", "?")
        text = q.get("text", q.get("question", "?"))
        session_id = q.get("session_id", "?")
        lines.append(f"  [{qid}] (session {session_id}): {text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Notification formatters (for push notifications from event bus)
# ---------------------------------------------------------------------------


def format_approval_notification(data: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Format an approval.required event into text + inline keyboard.

    Returns (message_text, reply_markup).
    """
    session_name = data.get("session_name", "unknown session")
    action_description = data.get("action_description", "Action requires approval")
    action_id = data.get("action_id", "unknown")
    text = (
        f"Approval required\n\n"
        f"Session: {session_name}\n"
        f"Action: {action_description}\n"
        f"Action ID: {action_id}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{action_id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{action_id}"),
            ]
        ]
    )
    return text, keyboard


def format_session_completed_notification(data: dict) -> str:
    """Format a session.completed event into a notification message."""
    session_name = data.get("session_name", "unknown session")
    summary = data.get("summary", "")
    text = f"Session completed\n\nSession: {session_name}"
    if summary:
        text += f"\nSummary: {summary}"
    return text


def format_session_failed_notification(data: dict) -> str:
    """Format a session.failed event into a notification message."""
    session_name = data.get("session_name", "unknown session")
    error = data.get("error", "Unknown error")
    return f"Session failed\n\nSession: {session_name}\nError: {error}"


def format_subagent_report_notification(data: dict) -> str:
    """Format a subagent.report_ready event into a notification message."""
    parent_session = data.get("parent_session", "unknown")
    subagent_name = data.get("subagent_name", "unknown sub-agent")
    status = data.get("status", "unknown")
    return (
        f"Sub-agent report ready\n\n"
        f"Parent session: {parent_session}\n"
        f"Sub-agent: {subagent_name}\n"
        f"Status: {status}"
    )


def format_question_notification(data: dict) -> str:
    """Format a question.created event into a notification message."""
    session_name = data.get("session_name", "unknown session")
    question_text = data.get("question_text", "")
    question_id = data.get("question_id", "unknown")
    return (
        f"New question\n\n"
        f"Session: {session_name}\n"
        f"Question: {question_text}\n"
        f"Answer with: /answer {question_id} <your answer>"
    )


def format_error_rate_spike_notification(data: dict) -> str:
    """Format an error.rate_spike event into a notification message."""
    window_errors = data.get("window_errors", 0)
    window_minutes = data.get("window_minutes", 0)
    errors_per_minute = data.get("errors_per_minute", 0.0)
    return (
        f"Error rate spike detected\n\n"
        f"Errors in last {window_minutes} minutes: {window_errors}\n"
        f"Rate: {errors_per_minute:.2f} errors/minute"
    )
