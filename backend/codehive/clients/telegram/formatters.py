"""Message formatting helpers for Telegram bot responses."""


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
