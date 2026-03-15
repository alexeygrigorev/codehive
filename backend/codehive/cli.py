"""Codehive CLI with subcommands."""

import argparse
import os
import sys
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


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
    body = {
        "name": args.name,
        "engine": args.engine,
        "mode": args.mode,
    }
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
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-platform autonomous coding agent with sub-agent orchestration",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL of the codehive API server (default: http://127.0.0.1:8000)",
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

    # sessions status
    sessions_status_parser = sessions_sub.add_parser("status", help="Show session status")
    sessions_status_parser.add_argument("session_id", help="Session ID")

    # sessions chat
    sessions_chat_parser = sessions_sub.add_parser("chat", help="Chat with a session")
    sessions_chat_parser.add_argument("session_id", help="Session ID")

    args = parser.parse_args()

    if args.command == "serve":
        _serve(args)
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
        else:
            sessions_parser.print_help()
    else:
        parser.print_help()


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


if __name__ == "__main__":
    main()
