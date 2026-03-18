"""Codehive CLI with subcommands."""

import argparse
import os
import sys
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:7433"


def _get_base_url(args: argparse.Namespace) -> str:
    """Return the base URL from args, env var, or default."""
    if hasattr(args, "base_url") and args.base_url:
        return args.base_url.rstrip("/")
    return os.environ.get("CODEHIVE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _make_client(base_url: str) -> httpx.Client:
    """Create an httpx client with the given base URL."""
    return httpx.Client(base_url=base_url, timeout=30.0)


def _handle_response_error(resp: httpx.Response, base_url: str) -> None:
    """Check for HTTP errors and print user-friendly messages."""
    if resp.status_code == 404:
        detail = resp.json().get("detail", "Not found")
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)
    elif resp.status_code == 422:
        detail = resp.json().get("detail", "Validation error")
        print(f"Validation error: {detail}", file=sys.stderr)
        sys.exit(1)
    elif resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        print(f"Error ({resp.status_code}): {detail}", file=sys.stderr)
        sys.exit(1)


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    base_url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Make an HTTP request with connection error handling."""
    try:
        resp = getattr(client, method)(path, **kwargs)
    except httpx.ConnectError:
        print(
            f"Cannot connect to server at {base_url}. Is it running?",
            file=sys.stderr,
        )
        sys.exit(1)
    _handle_response_error(resp, base_url)
    return resp


# ---------------------------------------------------------------------------
# Projects commands
# ---------------------------------------------------------------------------


def _projects_list(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    resp = _request(client, "get", "/api/projects", base_url)
    projects = resp.json()
    if not projects:
        print("No projects found.")
        return
    # Print table
    print(f"{'ID':<38} {'Name':<20} {'Path':<30} {'Created'}")
    print("-" * 110)
    for p in projects:
        path = p.get("path") or ""
        created = p.get("created_at", "")
        print(f"{p['id']:<38} {p['name']:<20} {path:<30} {created}")


def _projects_create(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    body: dict[str, Any] = {
        "workspace_id": args.workspace,
        "name": args.name,
    }
    if args.path:
        body["path"] = args.path
    if args.description:
        body["description"] = args.description
    resp = _request(client, "post", "/api/projects", base_url, json=body)
    data = resp.json()
    print(f"Created project {data['name']} ({data['id']})")


# ---------------------------------------------------------------------------
# Sessions commands
# ---------------------------------------------------------------------------


def _sessions_list(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    resp = _request(client, "get", f"/api/projects/{args.project}/sessions", base_url)
    sessions = resp.json()
    if not sessions:
        print("No sessions found.")
        return
    print(f"{'ID':<38} {'Name':<20} {'Engine':<12} {'Mode':<14} {'Status':<10} {'Created'}")
    print("-" * 130)
    for s in sessions:
        print(
            f"{s['id']:<38} {s['name']:<20} {s['engine']:<12} {s['mode']:<14} "
            f"{s['status']:<10} {s.get('created_at', '')}"
        )


def _sessions_create(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    body: dict[str, Any] = {
        "name": args.name,
        "engine": args.engine,
        "mode": args.mode,
    }
    model = getattr(args, "model", "")
    if model:
        body["config"] = {"model": model}
    resp = _request(
        client,
        "post",
        f"/api/projects/{args.project_id}/sessions",
        base_url,
        json=body,
    )
    data = resp.json()
    print(f"Created session {data['name']} ({data['id']})")


def _sessions_status(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    resp = _request(client, "get", f"/api/sessions/{args.session_id}", base_url)
    s = resp.json()
    print(f"ID:         {s['id']}")
    print(f"Name:       {s['name']}")
    print(f"Project:    {s['project_id']}")
    print(f"Engine:     {s['engine']}")
    print(f"Mode:       {s['mode']}")
    print(f"Status:     {s['status']}")
    print(f"Created:    {s.get('created_at', '')}")


def _sessions_pause(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    _request(client, "post", f"/api/sessions/{args.session_id}/pause", base_url)
    print(f"Session {args.session_id} paused.")


def _sessions_rollback(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    # Verify checkpoint belongs to session
    resp = _request(
        client,
        "get",
        f"/api/sessions/{args.session_id}/checkpoints",
        base_url,
    )
    checkpoints = resp.json()
    checkpoint_ids = [c["id"] for c in checkpoints]
    if args.checkpoint not in checkpoint_ids:
        print(
            f"Error: Checkpoint {args.checkpoint} does not belong to session {args.session_id}",
            file=sys.stderr,
        )
        sys.exit(1)
    _request(
        client,
        "post",
        f"/api/checkpoints/{args.checkpoint}/rollback",
        base_url,
    )
    print(f"Rolled back session {args.session_id} to checkpoint {args.checkpoint}.")


def _sessions_chat(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)

    # Verify session exists
    resp = _request(client, "get", f"/api/sessions/{args.session_id}", base_url)
    s = resp.json()
    print(f"Session: {s['name']} (status: {s['status']})")

    # REPL loop
    while True:
        try:
            line = input("> ")
        except EOFError:
            print()
            break
        if line.strip() == "/quit":
            break
        if not line.strip():
            continue

        resp = _request(
            client,
            "post",
            f"/api/sessions/{args.session_id}/messages",
            base_url,
            json={"content": line},
        )
        events = resp.json()
        for event in events:
            if event.get("type") == "message.created" and event.get("role") == "assistant":
                print(event.get("content", ""))


# ---------------------------------------------------------------------------
# Questions commands
# ---------------------------------------------------------------------------


def _questions_list(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    if hasattr(args, "session") and args.session:
        resp = _request(
            client,
            "get",
            f"/api/sessions/{args.session}/questions",
            base_url,
            params={"answered": "false"},
        )
    else:
        resp = _request(
            client,
            "get",
            "/api/questions",
            base_url,
            params={"answered": "false"},
        )
    questions = resp.json()
    if not questions:
        print("No pending questions.")
        return
    print(f"{'ID':<38} {'Session':<38} {'Question':<40} {'Created'}")
    print("-" * 140)
    for q in questions:
        question_text = q["question"][:37] + "..." if len(q["question"]) > 40 else q["question"]
        print(f"{q['id']:<38} {q['session_id']:<38} {question_text:<40} {q.get('created_at', '')}")


def _questions_answer(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    # Resolve session_id from question
    resp = _request(
        client,
        "get",
        f"/api/questions/{args.question_id}",
        base_url,
    )
    question = resp.json()
    session_id = question["session_id"]
    _request(
        client,
        "post",
        f"/api/sessions/{session_id}/questions/{args.question_id}/answer",
        base_url,
        json={"answer": args.answer},
    )
    print(f"Answered question {args.question_id}.")


# ---------------------------------------------------------------------------
# System commands
# ---------------------------------------------------------------------------


def _system_health(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    resp = _request(client, "get", "/api/system/health", base_url)
    data = resp.json()
    maint = "on" if data.get("maintenance") else "off"
    print(f"Version:         {data['version']}")
    print(f"Database:        {data['database']}")
    print(f"Redis:           {data['redis']}")
    print(f"Active sessions: {data['active_sessions']}")
    print(f"Maintenance:     {maint}")


def _system_maintenance(args: argparse.Namespace) -> None:
    base_url = _get_base_url(args)
    client = _make_client(base_url)
    enabled = args.state == "on"
    _request(
        client,
        "post",
        "/api/system/maintenance",
        base_url,
        json={"enabled": enabled},
    )
    if enabled:
        print("Maintenance mode enabled.")
    else:
        print("Maintenance mode disabled.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-platform autonomous coding agent with sub-agent orchestration",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL of the codehive API server (default: http://127.0.0.1:7433)",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Start the codehive API server")
    serve_parser.add_argument("--host", type=str, default=None, help="Bind host")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # projects subcommand group
    projects_parser = subparsers.add_parser("projects", help="Manage projects")
    projects_sub = projects_parser.add_subparsers(dest="action")

    # projects list
    projects_sub.add_parser("list", help="List all projects")

    # projects create
    projects_create_parser = projects_sub.add_parser("create", help="Create a project")
    projects_create_parser.add_argument("name", help="Project name")
    projects_create_parser.add_argument("--workspace", required=True, help="Workspace ID")
    projects_create_parser.add_argument("--path", default=None, help="Project path")
    projects_create_parser.add_argument("--description", default=None, help="Project description")

    # sessions subcommand group
    sessions_parser = subparsers.add_parser("sessions", help="Manage sessions")
    sessions_sub = sessions_parser.add_subparsers(dest="action")

    # sessions list
    sessions_list_parser = sessions_sub.add_parser("list", help="List sessions")
    sessions_list_parser.add_argument("--project", required=True, help="Project ID")

    # sessions create
    sessions_create_parser = sessions_sub.add_parser("create", help="Create a session")
    sessions_create_parser.add_argument("project_id", help="Project ID")
    sessions_create_parser.add_argument("--name", required=True, help="Session name")
    sessions_create_parser.add_argument(
        "--engine", default="native", help="Engine (default: native)"
    )
    sessions_create_parser.add_argument(
        "--mode", default="execution", help="Mode (default: execution)"
    )
    sessions_create_parser.add_argument(
        "--model", default="", help="Model name to use for the session"
    )

    # sessions status
    sessions_status_parser = sessions_sub.add_parser("status", help="Show session status")
    sessions_status_parser.add_argument("session_id", help="Session ID")

    # sessions chat
    sessions_chat_parser = sessions_sub.add_parser("chat", help="Chat with a session")
    sessions_chat_parser.add_argument("session_id", help="Session ID")

    # sessions pause
    sessions_pause_parser = sessions_sub.add_parser("pause", help="Pause a session")
    sessions_pause_parser.add_argument("session_id", help="Session ID")

    # sessions rollback
    sessions_rollback_parser = sessions_sub.add_parser(
        "rollback", help="Rollback a session to a checkpoint"
    )
    sessions_rollback_parser.add_argument("session_id", help="Session ID")
    sessions_rollback_parser.add_argument("--checkpoint", required=True, help="Checkpoint ID")

    # questions subcommand group
    questions_parser = subparsers.add_parser("questions", help="Manage pending questions")
    questions_sub = questions_parser.add_subparsers(dest="action")

    # questions list
    questions_list_parser = questions_sub.add_parser("list", help="List pending questions")
    questions_list_parser.add_argument("--session", default=None, help="Filter by session ID")

    # questions answer
    questions_answer_parser = questions_sub.add_parser("answer", help="Answer a pending question")
    questions_answer_parser.add_argument("question_id", help="Question ID")
    questions_answer_parser.add_argument("answer", help="Answer text")

    # system subcommand group
    system_parser = subparsers.add_parser("system", help="System management")
    system_sub = system_parser.add_subparsers(dest="action")

    # system health
    system_sub.add_parser("health", help="Show system health")

    # system maintenance
    system_maintenance_parser = system_sub.add_parser("maintenance", help="Toggle maintenance mode")
    system_maintenance_parser.add_argument(
        "state", choices=["on", "off"], help="Enable or disable maintenance mode"
    )

    # backup subcommand group
    backup_parser = subparsers.add_parser("backup", help="Database backup management")
    backup_sub = backup_parser.add_subparsers(dest="action")

    # backup create (also the default when no action given)
    backup_sub.add_parser("create", help="Create a new database backup")

    # backup list
    backup_sub.add_parser("list", help="List available backups")

    # backup restore
    backup_restore_parser = backup_sub.add_parser("restore", help="Restore database from backup")
    backup_restore_parser.add_argument("file", help="Backup file path to restore from")
    backup_restore_parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt"
    )

    # tui subcommand
    subparsers.add_parser("tui", help="Launch the interactive terminal dashboard")

    # rescue subcommand
    subparsers.add_parser("rescue", help="Launch rescue mode (emergency TUI)")

    # code subcommand
    code_parser = subparsers.add_parser("code", help="Start a lightweight coding agent session")
    code_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Project directory (default: current directory)",
    )
    code_parser.add_argument(
        "--model", default="", help="Model name (default: claude-sonnet-4-20250514)"
    )
    code_parser.add_argument(
        "--provider",
        default="",
        choices=["anthropic", "zai", ""],
        help="Provider shortcut: anthropic (default) or zai",
    )
    code_parser.add_argument(
        "--auto-approve",
        action="store_true",
        default=False,
        help="Skip all tool confirmation prompts",
    )
    # Mutually exclusive session flags
    code_session_group = code_parser.add_mutually_exclusive_group()
    code_session_group.add_argument(
        "--session",
        default=None,
        help="Connect to a specific existing session (UUID)",
    )
    code_session_group.add_argument(
        "--new",
        action="store_true",
        default=False,
        help="Always create a new session (don't resume the latest)",
    )

    # providers subcommand group
    providers_parser = subparsers.add_parser("providers", help="Manage LLM providers")
    providers_sub = providers_parser.add_subparsers(dest="action")
    providers_sub.add_parser("list", help="List configured providers")

    # telegram subcommand
    subparsers.add_parser("telegram", help="Start the Telegram bot")

    args = parser.parse_args()

    if args.command == "serve":
        _serve(args)
    elif args.command == "backup":
        if args.action == "create" or args.action is None:
            _backup_create(args)
        elif args.action == "list":
            _backup_list(args)
        elif args.action == "restore":
            _backup_restore(args)
        else:
            backup_parser.print_help()
    elif args.command == "code":
        _code(args)
    elif args.command == "providers":
        if args.action == "list":
            _providers_list(args)
        else:
            providers_parser.print_help()
    elif args.command == "tui":
        _tui(args)
    elif args.command == "rescue":
        _rescue(args)
    elif args.command == "telegram":
        _telegram(args)
    elif args.command == "projects":
        if args.action == "list":
            _projects_list(args)
        elif args.action == "create":
            _projects_create(args)
        else:
            projects_parser.print_help()
    elif args.command == "sessions":
        if args.action == "list":
            _sessions_list(args)
        elif args.action == "create":
            _sessions_create(args)
        elif args.action == "status":
            _sessions_status(args)
        elif args.action == "chat":
            _sessions_chat(args)
        elif args.action == "pause":
            _sessions_pause(args)
        elif args.action == "rollback":
            _sessions_rollback(args)
        else:
            sessions_parser.print_help()
    elif args.command == "questions":
        if args.action == "list":
            _questions_list(args)
        elif args.action == "answer":
            _questions_answer(args)
        else:
            questions_parser.print_help()
    elif args.command == "system":
        if args.action == "health":
            _system_health(args)
        elif args.action == "maintenance":
            _system_maintenance(args)
        else:
            system_parser.print_help()
    else:
        parser.print_help()


def _backup_create(args: argparse.Namespace) -> None:
    from codehive.config import Settings
    from codehive.core.backup import create_backup, prune_backups

    settings = Settings()
    try:
        filepath = create_backup(settings.database_url, settings.backup_dir)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Backup created: {filepath}")

    deleted = prune_backups(settings.backup_dir, settings.backup_retention)
    if deleted:
        print(f"Pruned {len(deleted)} old backup(s): {', '.join(deleted)}")


def _backup_list(args: argparse.Namespace) -> None:
    from codehive.config import Settings
    from codehive.core.backup import format_age, format_size, list_backups

    settings = Settings()
    backups = list_backups(settings.backup_dir)
    if not backups:
        print("No backups found.")
        return
    print(f"{'Filename':<45} {'Size':<12} {'Age'}")
    print("-" * 70)
    for b in backups:
        print(f"{b['filename']:<45} {format_size(b['size']):<12} {format_age(b['age_seconds'])}")
    print(f"\n{len(backups)} backup(s) in {settings.backup_dir}")


def _backup_restore(args: argparse.Namespace) -> None:
    from codehive.config import Settings
    from codehive.core.backup import restore_backup

    settings = Settings()

    if not args.yes:
        print("WARNING: This will overwrite the current database with the backup data.")
        try:
            answer = input("Continue? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    try:
        restore_backup(settings.database_url, args.file)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Database restored from {args.file}")


def _resolve_provider(args: argparse.Namespace) -> tuple[str, str, str]:
    """Resolve provider, api_key, base_url, and model from CLI args and env.

    Returns (api_key, base_url, model).
    """
    provider = getattr(args, "provider", "") or ""
    model = getattr(args, "model", "") or ""

    if provider == "zai":
        from codehive.config import Settings

        settings = Settings()
        api_key = (
            os.environ.get("CODEHIVE_ZAI_API_KEY", "")
            or os.environ.get("ZAI_API_KEY", "")
            or settings.zai_api_key
        )
        base_url = settings.zai_base_url
        if not model:
            model = "glm-4.7"
        return api_key, base_url, model

    # Default: anthropic provider
    api_key = os.environ.get("CODEHIVE_ANTHROPIC_API_KEY", "") or os.environ.get(
        "ANTHROPIC_API_KEY", ""
    )
    base_url = os.environ.get("CODEHIVE_ANTHROPIC_BASE_URL", "") or os.environ.get(
        "ANTHROPIC_BASE_URL", ""
    )
    if not api_key:
        try:
            from codehive.config import Settings

            settings = Settings()
            api_key = settings.anthropic_api_key
            base_url = base_url or settings.anthropic_base_url
        except Exception:
            pass

    return api_key, base_url, model


def _probe_backend(backend_url: str) -> bool:
    """Probe GET /api/system/health on the backend. Returns True if reachable and 200."""
    try:
        resp = httpx.get(f"{backend_url}/api/system/health", timeout=3.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout):
        return False
    except Exception:
        return False


def _resolve_project_and_session(
    backend_url: str,
    project_dir: str,
    session_flag: str | None,
    new_flag: bool,
) -> tuple[str, str]:
    """Resolve project_id and session_id from the backend.

    Returns (project_id, session_id) as strings.
    Raises SystemExit on errors.
    """
    import uuid as _uuid

    client = httpx.Client(base_url=backend_url, timeout=30.0)

    # Get or create project by path
    try:
        resp = client.post("/api/projects/by-path", json={"path": project_dir})
    except httpx.ConnectError:
        print("Backend not available, starting local-only session", file=sys.stderr)
        raise SystemExit(None)

    if resp.status_code not in (200, 201):
        print(
            f"Warning: Failed to resolve project (HTTP {resp.status_code}), "
            "starting local-only session",
            file=sys.stderr,
        )
        raise SystemExit(None)

    project = resp.json()
    project_id = project["id"]

    # Session resolution
    if session_flag:
        # Validate it looks like a UUID
        try:
            _uuid.UUID(session_flag)
        except ValueError:
            print(f"Error: Invalid session UUID: {session_flag}", file=sys.stderr)
            sys.exit(1)
        session_id = session_flag
    elif new_flag:
        resp = client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "code-session", "engine": "native", "mode": "execution"},
        )
        if resp.status_code not in (200, 201):
            print(
                f"Warning: Failed to create session (HTTP {resp.status_code}), "
                "starting local-only session",
                file=sys.stderr,
            )
            raise SystemExit(None)
        session_id = resp.json()["id"]
    else:
        # List sessions, pick most recent
        resp = client.get(f"/api/projects/{project_id}/sessions")
        if resp.status_code == 200:
            sessions = resp.json()
            if sessions:
                # Pick the most recent by created_at
                most_recent = max(sessions, key=lambda s: s.get("created_at", ""))
                session_id = most_recent["id"]
            else:
                # No sessions exist, create one
                resp = client.post(
                    f"/api/projects/{project_id}/sessions",
                    json={
                        "name": "code-session",
                        "engine": "native",
                        "mode": "execution",
                    },
                )
                if resp.status_code not in (200, 201):
                    print(
                        f"Warning: Failed to create session (HTTP {resp.status_code}), "
                        "starting local-only session",
                        file=sys.stderr,
                    )
                    raise SystemExit(None)
                session_id = resp.json()["id"]
        else:
            print(
                f"Warning: Failed to list sessions (HTTP {resp.status_code}), "
                "starting local-only session",
                file=sys.stderr,
            )
            raise SystemExit(None)

    client.close()
    return project_id, session_id


def _code(args: argparse.Namespace) -> None:
    import uuid as _uuid

    from codehive.clients.terminal.code_app import CodeApp

    project_dir = os.path.abspath(args.directory)
    if not os.path.isdir(project_dir):
        print(f"Error: {project_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    backend_url = _get_base_url(args)
    session_flag = getattr(args, "session", None)
    new_flag = getattr(args, "new", False)

    # Probe backend
    backend_available = _probe_backend(backend_url)

    if not backend_available:
        print(
            "Backend not available, starting local-only session",
            file=sys.stderr,
        )

    if backend_available:
        try:
            project_id, session_id = _resolve_project_and_session(
                backend_url, project_dir, session_flag, new_flag
            )
        except SystemExit:
            # Fall back to local mode
            backend_available = False
            project_id = None
            session_id = None
        else:
            project_id_uuid = _uuid.UUID(project_id)
            session_id_uuid = _uuid.UUID(session_id)

    if backend_available:
        app = CodeApp(
            project_dir=project_dir,
            auto_approve=getattr(args, "auto_approve", False),
            backend_url=backend_url,
            project_id=project_id_uuid,  # type: ignore[possibly-undefined]
            session_id=session_id_uuid,  # type: ignore[possibly-undefined]
        )
    else:
        api_key, base_url, model = _resolve_provider(args)

        if not api_key:
            print(
                "Error: No API key found. Set CODEHIVE_ANTHROPIC_API_KEY or "
                "ANTHROPIC_API_KEY environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)

        app = CodeApp(
            project_dir=project_dir,
            model=model,
            api_key=api_key,
            base_url=base_url,
            auto_approve=getattr(args, "auto_approve", False),
        )
    app.run()


def _providers_list(args: argparse.Namespace) -> None:
    """Print a table of configured LLM providers."""
    from codehive.config import Settings

    settings = Settings()

    anthropic_key_set = bool(
        settings.anthropic_api_key
        or os.environ.get("CODEHIVE_ANTHROPIC_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    zai_key_set = bool(
        settings.zai_api_key
        or os.environ.get("CODEHIVE_ZAI_API_KEY", "")
        or os.environ.get("ZAI_API_KEY", "")
    )

    anthropic_base = settings.anthropic_base_url or "default"

    providers = [
        {
            "name": "anthropic",
            "base_url": anthropic_base,
            "api_key": "yes" if anthropic_key_set else "no",
            "default_model": settings.default_model,
        },
        {
            "name": "zai",
            "base_url": settings.zai_base_url,
            "api_key": "yes" if zai_key_set else "no",
            "default_model": "glm-4.7",
        },
    ]

    print(f"{'Provider':<12} {'Base URL':<40} {'API Key':<10} {'Default Model'}")
    print("-" * 95)
    for p in providers:
        print(f"{p['name']:<12} {p['base_url']:<40} {p['api_key']:<10} {p['default_model']}")


def _rescue(args: argparse.Namespace) -> None:
    from codehive.clients.terminal.screens.rescue import RescueApp

    base_url = _get_base_url(args)
    app = RescueApp(base_url=base_url)
    app.run()


def _tui(args: argparse.Namespace) -> None:
    from codehive.clients.terminal.app import CodehiveApp

    base_url = _get_base_url(args)
    app = CodehiveApp(base_url=base_url)
    app.run()


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from codehive.config import Settings

    settings = Settings()
    host = args.host or settings.host
    port = args.port or settings.port
    reload = args.reload or settings.debug

    uvicorn.run(
        "codehive.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def _telegram(args: argparse.Namespace) -> None:
    from codehive.clients.telegram.bot import create_bot
    from codehive.config import Settings

    settings = Settings()
    token = settings.telegram_bot_token
    if not token:
        print(
            "Error: CODEHIVE_TELEGRAM_BOT_TOKEN is not set. "
            "Set it via environment variable or .env file.",
            file=sys.stderr,
        )
        sys.exit(1)
    base_url = _get_base_url(args)
    app = create_bot(token=token, base_url=base_url)
    app.run_polling()


if __name__ == "__main__":
    main()
