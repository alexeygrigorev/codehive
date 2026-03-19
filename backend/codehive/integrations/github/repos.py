"""GitHub repository listing and cloning via the ``gh`` CLI."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass


@dataclass
class GhStatus:
    """Result of checking ``gh`` CLI availability and auth."""

    available: bool
    authenticated: bool
    username: str | None
    error: str | None


@dataclass
class GhRepo:
    """A single GitHub repository."""

    name: str
    full_name: str
    description: str | None
    language: str | None
    updated_at: str | None
    is_private: bool
    clone_url: str


@dataclass
class GhRepoList:
    """Result of listing GitHub repos."""

    repos: list[GhRepo]
    owner: str | None
    total: int


async def _run_gh(*args: str) -> tuple[int, str, str]:
    """Run a ``gh`` CLI command and return (returncode, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        "gh",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    return process.returncode or 0, stdout, stderr


async def check_gh_status() -> GhStatus:
    """Check whether ``gh`` CLI is installed and authenticated."""
    # Check if gh is available
    try:
        rc, _, _ = await _run_gh("--version")
    except FileNotFoundError:
        return GhStatus(
            available=False,
            authenticated=False,
            username=None,
            error="gh CLI is not installed. Install it from https://cli.github.com/",
        )

    if rc != 0:
        return GhStatus(
            available=False,
            authenticated=False,
            username=None,
            error="gh CLI is not installed. Install it from https://cli.github.com/",
        )

    # Check auth status
    rc, stdout, stderr = await _run_gh("auth", "status")
    if rc != 0:
        return GhStatus(
            available=True,
            authenticated=False,
            username=None,
            error="gh CLI is not authenticated. Run 'gh auth login' to authenticate.",
        )

    # Extract username from auth status output
    username = None
    for line in (stdout + stderr).splitlines():
        if "Logged in to" in line and "account" in line:
            # Format: "Logged in to github.com account username ..."
            parts = line.split("account")
            if len(parts) > 1:
                username = parts[1].strip().split()[0].strip("()")
                break
        elif "Logged in to" in line:
            # Try another format: "Logged in to github.com as username"
            parts = line.split(" as ")
            if len(parts) > 1:
                username = parts[1].strip().split()[0].strip("()")
                break

    return GhStatus(
        available=True,
        authenticated=True,
        username=username,
        error=None,
    )


async def list_repos(
    *,
    owner: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> GhRepoList:
    """List GitHub repositories for the authenticated user or a given owner."""
    args = ["repo", "list"]
    if owner:
        args.append(owner)
    args.extend(
        [
            "--json",
            "name,nameWithOwner,description,primaryLanguage,updatedAt,isPrivate,url",
            "--limit",
            str(limit),
        ]
    )

    rc, stdout, stderr = await _run_gh(*args)
    if rc != 0:
        raise RuntimeError(f"gh repo list failed: {stderr.strip()}")

    raw_repos: list[dict] = json.loads(stdout) if stdout.strip() else []

    repos: list[GhRepo] = []
    for r in raw_repos:
        lang = r.get("primaryLanguage")
        if isinstance(lang, dict):
            lang = lang.get("name")

        repo = GhRepo(
            name=r.get("name", ""),
            full_name=r.get("nameWithOwner", ""),
            description=r.get("description") or None,
            language=lang,
            updated_at=r.get("updatedAt"),
            is_private=r.get("isPrivate", False),
            clone_url=r.get("url", ""),
        )
        repos.append(repo)

    # Client-side search filter
    if search:
        search_lower = search.lower()
        repos = [r for r in repos if search_lower in r.name.lower()]

    # Determine owner from results
    resolved_owner = owner
    if not resolved_owner and repos:
        parts = repos[0].full_name.split("/")
        if len(parts) >= 2:
            resolved_owner = parts[0]

    return GhRepoList(
        repos=repos,
        owner=resolved_owner,
        total=len(repos),
    )


def is_within_home(path: str) -> bool:
    """Check whether *path* is within the user's home directory."""
    home = os.path.expanduser("~")
    normalized = os.path.normpath(os.path.realpath(path))
    return normalized == home or normalized.startswith(home + os.sep)


async def clone_repo(
    *,
    repo_url: str,
    destination: str,
) -> str:
    """Clone a GitHub repo to the given destination.

    Returns the absolute path of the cloned directory.
    Raises ``FileExistsError`` if the destination already exists.
    Raises ``ValueError`` if the destination is outside the home directory.
    Raises ``RuntimeError`` if the clone fails.
    """
    normalized = os.path.normpath(os.path.expanduser(destination))

    if not is_within_home(normalized):
        raise ValueError("Destination path is outside the home directory")

    if os.path.exists(normalized):
        raise FileExistsError(f"Destination directory already exists: {normalized}")

    # Ensure parent directory exists
    parent = os.path.dirname(normalized)
    os.makedirs(parent, exist_ok=True)

    rc, stdout, stderr = await _run_gh("repo", "clone", repo_url, normalized)
    if rc != 0:
        raise RuntimeError(f"Clone failed: {stderr.strip()}")

    return normalized
